"""Prompt construction and answer generation.

Three pieces live here:

``build_prompt``
    Assembles the grounding prompt from retrieved chunks and prior turns.

``OpenAIGenerator``
    The production path. The client is created lazily so that importing this
    module never requires an API key -- otherwise the app would fail to start
    on a machine without one.

``OfflineGenerator``
    A dependency-free extractive fallback used when no usable API key is
    present. It quotes the sentences from the retrieved context that best match
    the question. It is *not* a language model and does no paraphrasing or
    synthesis; it exists so retrieval and the chat plumbing stay demonstrable
    without credentials. Responses carry ``mode="offline-extractive"`` so
    callers can tell the difference.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence

from app.config import settings, usable_api_key
from app.exceptions import LLMUnavailableError

logger = logging.getLogger("rag-chatbot")

#: Message returned when retrieval found nothing to answer from.
NO_CONTEXT_ANSWER = (
    "I don't have information about that in the course materials. "
    "Please try rephrasing your question or ask about a different topic."
)

SYSTEM_PROMPT = "You are a helpful teaching assistant."

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WORD = re.compile(r"[a-z0-9]+")

# Words too common to carry any retrieval signal.
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have how i in is it its of on or that
    the this to was were what when where which who why will with you your do does
    did can could should would about there their them they""".split()
)


@dataclass
class Generated:
    """A generated answer plus the mode that produced it."""

    text: str
    mode: str


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def build_prompt(
    question: str,
    context_chunks: Sequence[Dict],
    conversation_history: Optional[Sequence[Dict]] = None,
) -> str:
    """Build the grounding prompt for `question`.

    `context_chunks` are the retrieved chunks. `conversation_history` is a list
    of ``{"role": ..., "content": ...}`` dicts in chronological order.
    """
    context_text = "\n\n---\n\n".join(
        _with_source_label(chunk) for chunk in context_chunks
    )

    history = list(conversation_history or [])[-settings.MAX_HISTORY_MESSAGES :]
    if history:
        history_text = "\n".join(
            f"{_role_label(m.get('role'))}: {m.get('content', '')}".strip()
            for m in history
        )
    else:
        history_text = "No previous conversation."

    return f"""You are a helpful teaching assistant for a university course. \
Answer the student's question based ONLY on the provided course materials.

## Course Materials:
{context_text or "No course materials were found."}

## Conversation History:
{history_text}

## Student Question:
{question}

## Instructions:
- Answer based ONLY on the course materials provided above
- If the answer is not in the materials, say \
"I don't have information about that in the course materials."
- Be clear, concise, and helpful
- Use markdown formatting for better readability
- Cite which document/section the information comes from when possible

## Answer:"""


def _with_source_label(chunk: Dict) -> str:
    """Prefix a chunk with its source so the model can cite it."""
    metadata = chunk.get("metadata") or {}
    filename = metadata.get("filename") or "Unknown source"
    page = metadata.get("page_number")
    label = f"[Source: {filename}" + (f", page {page}" if page else "") + "]"
    return f"{label}\n{chunk.get('content', '')}"


def _role_label(role: Optional[str]) -> str:
    return {"user": "Student", "assistant": "Assistant"}.get(
        (role or "").lower(), "Student"
    )


# ---------------------------------------------------------------------------
# Remote provider (OpenAI or any OpenAI-compatible endpoint, e.g. Groq)
# ---------------------------------------------------------------------------


class OpenAIGenerator:
    """Calls the chat completions API. The client is built on first use.

    The name is historical: this speaks the OpenAI protocol, and Groq serves
    that protocol, so the same class handles both. What distinguishes them is
    the endpoint, which comes from :attr:`Settings.llm_endpoint` rather than
    from this class.
    """

    def __init__(self, provider: str = "openai"):
        self._client = None
        self._provider = provider

    @property
    def mode(self) -> str:
        """The provider that actually serves the answer.

        Reported to the client on every response. It is the honest answer to
        "was a language model called, and by whom", which is why it names the
        provider rather than collapsing every remote call to "openai".
        """
        return self._provider

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            # Resolved per instance rather than read from a module-level
            # constant so that a provider switch between calls cannot leave a
            # client pointed at the previous endpoint with the previous key.
            endpoint = settings.llm_endpoint
            if endpoint is None:
                raise LLMUnavailableError(
                    "No usable API key is configured, so no remote generator "
                    "can be built. Set GROQ_API_KEY or OPENAI_API_KEY."
                )
            _provider, kwargs = endpoint

            self._client = AsyncOpenAI(
                timeout=settings.LLM_TIMEOUT_SECONDS,
                max_retries=2,
                **kwargs,
            )
        return self._client

    def _messages(self, prompt: str) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

    async def generate(self, prompt: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=self._messages(prompt),
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise LLMUnavailableError(
                f"The language model could not be reached: {exc}"
            ) from exc

        content = response.choices[0].message.content
        return content or ""

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=self._messages(prompt),
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                stream=True,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise LLMUnavailableError(
                f"The language model could not be reached: {exc}"
            ) from exc

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as exc:
            # Headers are already sent by the time streaming starts, so this
            # cannot become a 503. Surfacing it as a terminal SSE event is the
            # only way the client learns the answer was cut short.
            logger.exception("Stream failed mid-response")
            yield f"\n\n> Generation failed: {exc}"


# ---------------------------------------------------------------------------
# Offline provider
# ---------------------------------------------------------------------------


class OfflineGenerator:
    """Extractive fallback: quotes the most relevant context sentences.

    Not a language model. It ranks sentences from the retrieved chunks by
    lexical overlap with the question and returns the best few, so the answer
    is always grounded in (and traceable to) the indexed material.
    """

    @property
    def mode(self) -> str:
        return "offline-extractive"

    async def generate(self, prompt: str) -> str:
        question, sentences = _split_prompt(prompt)
        return self._compose(question, sentences)

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        answer = await self.generate(prompt)
        # Emit in word groups so the frontend still exercises its streaming
        # path rather than receiving one giant chunk.
        for piece in _drip(answer):
            yield piece

    def _compose(self, question: str, sentences: List[Dict]) -> str:
        if not sentences:
            return NO_CONTEXT_ANSWER

        query_tokens = _tokens(question)
        if not query_tokens:
            return NO_CONTEXT_ANSWER

        # Overlapping chunks repeat sentences at the seam, and two documents
        # often restate the same policy line. Quote each distinct sentence
        # once, attributing it to the first (highest-ranked) source it came
        # from, rather than printing it twice with different citations.
        scored = []
        seen_text = set()
        for sentence in sentences:
            overlap = _overlap(query_tokens, _tokens(sentence["text"]))
            if overlap < settings.OFFLINE_MIN_SIMILARITY:
                continue
            key = sentence["text"].strip().lower()
            if key in seen_text:
                continue
            seen_text.add(key)
            scored.append((overlap, sentence))

        if not scored:
            return NO_CONTEXT_ANSWER

        # Stable sort: equal scores keep document order.
        scored.sort(key=lambda pair: pair[0], reverse=True)
        best = scored[: settings.OFFLINE_MAX_SENTENCES]

        # Present in document order so the answer reads coherently.
        best.sort(key=lambda pair: pair[1]["order"])

        lines = []
        for _score, sentence in best:
            lines.append(f"- {sentence['text'].strip()} ({sentence['label']})")
        return "\n".join(lines)


def _split_prompt(prompt: str):
    """Recover the question and context sentences from a built prompt.

    The offline generator receives the same rendered prompt as the LLM path so
    both share one prompt builder; these two helpers read it back apart.
    """
    question = ""
    context = ""

    if "## Student Question:" in prompt:
        tail = prompt.split("## Student Question:", 1)[1]
        question = tail.split("## Instructions:", 1)[0].strip()

    if "## Course Materials:" in prompt:
        body = prompt.split("## Course Materials:", 1)[1]
        context = body.split("## Conversation History:", 1)[0]

    sentences: List[Dict] = []
    order = 0
    for block in context.split("\n\n---\n\n"):
        lines = block.strip().split("\n", 1)
        label = lines[0].strip() if lines else ""
        if label.startswith("[Source:") and label.endswith("]"):
            # Slicing off "[Source:" leaves the separator space behind.
            label = label[len("[Source:") : -1].strip()
        else:
            label = ""
        body_text = lines[1] if len(lines) > 1 else block
        for raw in _SENTENCE_SPLIT.split(body_text):
            text = (raw or "").strip()
            if len(text.split()) < 3:
                continue
            sentences.append({"text": text, "label": label, "order": order})
            order += 1

    return question, sentences


def _tokens(text: str) -> List[str]:
    """Content words plus bigrams, in order, stopwords removed.

    Order is preserved because `_overlap` needs bigrams as adjacent pairs.
    """
    words = [w for w in _WORD.findall((text or "").lower()) if w not in _STOPWORDS]
    tokens = list(words)
    # Bigrams give a little word-order sensitivity, matching the embedder.
    tokens.extend(f"{words[i]}_{words[i + 1]}" for i in range(len(words) - 1))
    return tokens


#: Shortest stem that may be compared. Four characters keeps
#: "exam"/"examination" and "assign"/"assignment" together while leaving
#: "cat"/"catalog" and "run"/"rung" apart.
_MIN_STEM = 4

#: Suffixes stripped before comparing word forms, longest first.
_SUFFIXES = ("ations", "ation", "ing", "ings", "ments", "ment", "ed", "es", "s")


def _stem(token: str) -> str:
    """Reduce a word to a comparable stem.

    A prefix comparison alone is not enough: "grading" does not start with
    "grade", because English drops the silent e. So common suffixes are
    stripped first, then a trailing e. A stem is never taken below
    ``_MIN_STEM`` characters, which is what stops "cat" collapsing into
    "catalog".
    """
    if "_" in token:
        # Bigrams are positional, not morphological; leave them alone.
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM:
            return token[: -len(suffix)]
    if token.endswith("e") and len(token) - 1 >= _MIN_STEM:
        return token[:-1]
    return token


def _matches(query_token: str, sentence_token: str) -> bool:
    if query_token == sentence_token:
        return True
    # Bigrams contain an underscore; do not try to stem across the join.
    if "_" in query_token or "_" in sentence_token:
        return False
    a, b = _stem(query_token), _stem(sentence_token)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= _MIN_STEM and longer.startswith(shorter)


def _overlap(query_tokens: List[str], sentence_tokens: List[str]) -> float:
    """Cosine-style score with light stemming.

    Exact set intersection alone scores zero for "exam" against
    "examination", which is a question a student will definitely ask.
    """
    if not query_tokens or not sentence_tokens:
        return 0.0

    distinct_sentence = set(sentence_tokens)
    matched = sum(
        1
        for token in set(query_tokens)
        if any(_matches(token, other) for other in distinct_sentence)
    )
    if not matched:
        return 0.0
    return matched / ((len(set(query_tokens)) ** 0.5) * (len(distinct_sentence) ** 0.5))


def _drip(text: str, words_per_chunk: int = 6) -> List[str]:
    """Split text into small pieces to imitate token-by-token streaming."""
    words = text.split(" ")
    pieces = []
    for i in range(0, len(words), words_per_chunk):
        piece = " ".join(words[i : i + words_per_chunk])
        if i:
            piece = " " + piece
        pieces.append(piece)
    return pieces or [text]


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def _has_usable_openai_key() -> bool:
    return usable_api_key(settings.OPENAI_API_KEY)


def _has_usable_groq_key() -> bool:
    return usable_api_key(settings.GROQ_API_KEY)


def resolve_llm_provider() -> str:
    """Return 'groq', 'openai' or 'offline'.

    Which API is used is decided by :attr:`Settings.llm_endpoint`, which
    prefers Groq when both keys are present. An explicit ``LLM_PROVIDER``
    overrides that, and is the only way to reach OpenAI while a Groq key is
    also configured.
    """
    requested = (settings.LLM_PROVIDER or "auto").strip().lower()
    if requested == "offline":
        return "offline"

    if requested in ("groq", "openai"):
        # An explicit choice must not fall through to whichever other key
        # happens to be set: asking for one provider and silently being given
        # another is worse than failing.
        if requested == "groq" and not _has_usable_groq_key():
            raise LLMUnavailableError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is missing or is still the "
                ".env.example placeholder"
            )
        if requested == "openai" and not _has_usable_openai_key():
            raise LLMUnavailableError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is missing or is still "
                "the .env.example placeholder"
            )
        return requested

    endpoint = settings.llm_endpoint
    return endpoint[0] if endpoint else "offline"


_generator: Optional[Any] = None


def get_generator():
    """Return the shared generator for the configured provider."""
    global _generator
    if _generator is None:
        provider = resolve_llm_provider()
        if provider == "offline":
            _generator = OfflineGenerator()
        else:
            _generator = OpenAIGenerator(provider)
        logger.info("LLM provider: %s (%s)", _generator.mode, settings.LLM_MODEL)
    return _generator


def reset_generator() -> None:
    """Drop the cached generator. Used by tests and provider switches."""
    global _generator
    _generator = None
