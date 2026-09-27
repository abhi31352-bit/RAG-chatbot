"""Tests for prompt construction, provider selection, and the offline responder."""

import pytest

from app.config import settings
from app.exceptions import LLMUnavailableError
from app.rag import generator as gen
from app.rag.generator import (
    NO_CONTEXT_ANSWER,
    OfflineGenerator,
    OpenAIGenerator,
    build_prompt,
    get_generator,
    resolve_llm_provider,
)

CHUNKS = [
    {
        "content": "The final examination accounts for 40 percent of the grade.",
        "metadata": {"filename": "syllabus.pdf", "chunk_index": 0, "page_number": 2},
        "similarity": 0.82,
    },
    {
        "content": "Office hours are Tuesdays from 2pm to 4pm in Gates 412.",
        "metadata": {"filename": "syllabus.pdf", "chunk_index": 3},
        "similarity": 0.41,
    },
    {
        "content": "Week 1 covers linear regression.",
        "metadata": {"filename": "lecture.md", "chunk_index": 0},
        "similarity": 0.12,
    },
]


# -- Prompt construction ---------------------------------------------------


def test_prompt_contains_every_chunk():
    prompt = build_prompt("What counts?", CHUNKS)
    for chunk in CHUNKS:
        assert chunk["content"] in prompt


def test_prompt_labels_sources_for_citation():
    prompt = build_prompt("What counts?", CHUNKS)
    assert "[Source: syllabus.pdf, page 2]" in prompt
    assert "[Source: lecture.md]" in prompt


def test_prompt_includes_the_question():
    assert "What counts?" in build_prompt("What counts?", CHUNKS)


def test_prompt_without_history_says_so():
    assert "No previous conversation." in build_prompt("q", CHUNKS, None)
    assert "No previous conversation." in build_prompt("q", CHUNKS, [])


def test_prompt_includes_history():
    history = [
        {"role": "user", "content": "What is the grading?"},
        {"role": "assistant", "content": "40% exam."},
    ]
    prompt = build_prompt("And the project?", CHUNKS, history)
    assert "Student: What is the grading?" in prompt
    assert "Assistant: 40% exam." in prompt
    assert "No previous conversation." not in prompt


def test_prompt_truncates_long_history():
    history = [
        {"role": "user", "content": f"question number {i}"} for i in range(50)
    ]
    prompt = build_prompt("latest", CHUNKS, history)
    assert "question number 49" in prompt, "the most recent turn must survive"
    assert "question number 0" not in prompt, "the oldest turn should be dropped"


def test_prompt_handles_empty_context():
    prompt = build_prompt("anything", [])
    assert "No course materials were found." in prompt


def test_prompt_does_not_crash_on_missing_metadata():
    prompt = build_prompt("q", [{"content": "text", "metadata": None}])
    assert "[Source: Unknown source]" in prompt


# -- Provider selection ----------------------------------------------------


def _no_keys(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")


def test_offline_when_no_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "auto")
    _no_keys(monkeypatch)
    assert resolve_llm_provider() == "offline"


def test_offline_when_key_is_placeholder(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "auto")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-your-key-here")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-your-key-here")
    assert resolve_llm_provider() == "offline"


def test_openai_when_key_present(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "auto")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-abc123")
    assert resolve_llm_provider() == "openai"


def test_groq_when_groq_key_present(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "auto")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-abc123")
    assert resolve_llm_provider() == "groq"


def test_auto_prefers_groq_when_both_keys_are_present(monkeypatch):
    # Groq is the cheaper endpoint and the one this project targets, so
    # silently preferring a pricier key nobody remembers adding is wrong.
    monkeypatch.setattr(settings, "LLM_PROVIDER", "auto")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-abc123")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-abc123")
    assert resolve_llm_provider() == "groq"


def test_forced_groq_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    _no_keys(monkeypatch)
    with pytest.raises(LLMUnavailableError):
        resolve_llm_provider()


def test_forced_groq_does_not_fall_back_to_an_openai_key(monkeypatch):
    # Asking for one provider and silently being served another is worse than
    # failing, because the reported mode would be a lie.
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-abc123")
    with pytest.raises(LLMUnavailableError):
        resolve_llm_provider()


def test_forced_openai_ignores_a_configured_groq_key(monkeypatch):
    # The only way to reach OpenAI while a Groq key is also set.
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-abc123")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-abc123")
    assert resolve_llm_provider() == "openai"


def test_offline_wins_over_any_configured_key(monkeypatch):
    # The escape hatch: a key is present but must not be called.
    monkeypatch.setattr(settings, "LLM_PROVIDER", "offline")
    _no_keys(monkeypatch)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-abc123")
    assert resolve_llm_provider() == "offline"


def test_forced_openai_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    _no_keys(monkeypatch)
    with pytest.raises(LLMUnavailableError):
        resolve_llm_provider()


def test_get_generator_is_cached():
    assert get_generator() is get_generator()


def test_get_generator_returns_offline_instance():
    assert isinstance(get_generator(), OfflineGenerator)


# -- Offline responder -----------------------------------------------------


def test_offline_answer_quotes_relevant_sentence():
    chunks = [
        {
            "content": "The final examination accounts for 40 percent of the grade. "
            "Office hours are Tuesdays from 2pm to 4pm in Gates 412.",
            "metadata": {"filename": "syllabus.pdf", "chunk_index": 0},
        }
    ]
    prompt = build_prompt("How much does the final exam count for?", chunks)
    answer = OfflineGenerator()._compose(*gen._split_prompt(prompt))

    assert "40 percent" in answer
    assert "syllabus.pdf" in answer, "the answer should cite its source"
    assert "Gates 412" not in answer, "irrelevant sentences should be left out"


def test_offline_answer_with_no_overlap_is_fallback():
    chunks = [
        {
            "content": "The final examination accounts for 40 percent of the grade.",
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    prompt = build_prompt("zzzz qqqq xxxx unrelated nonsense", chunks)
    assert OfflineGenerator()._compose(*gen._split_prompt(prompt)) == NO_CONTEXT_ANSWER


def test_offline_answer_with_no_context_is_fallback():
    assert OfflineGenerator()._compose(*gen._split_prompt(build_prompt("q", []))) == (
        NO_CONTEXT_ANSWER
    )


async def test_offline_stream_pieces_reassemble_to_the_answer():
    chunks = [
        {
            "content": "The final examination accounts for 40 percent of the grade.",
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    prompt = build_prompt("How much does the exam count for?", chunks)
    responder = OfflineGenerator()

    pieces = [piece async for piece in responder.generate_stream(prompt)]
    assert len(pieces) > 1, "offline stream should emit multiple pieces"
    assert "".join(pieces) == responder._compose(*gen._split_prompt(prompt))


async def test_offline_stream_of_fallback_is_emitted():
    pieces = [
        p async for p in OfflineGenerator().generate_stream(build_prompt("q", []))
    ]
    assert "".join(pieces) == NO_CONTEXT_ANSWER


def test_sentence_split_skips_fragments():
    chunks = [
        {
            "content": "Hi. The final examination accounts for 40 percent of the grade.",
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    prompt = build_prompt("How much does the exam count?", chunks)
    _, sentences = gen._split_prompt(prompt)
    assert len(sentences) == 1, "one- and two-word fragments should be dropped"


def test_source_label_has_no_leading_space():
    """'[Source: x]' must yield the label 'x', not ' x'."""
    chunks = [
        {
            "content": "The final examination accounts for 40 percent of the grade.",
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    _, sentences = gen._split_prompt(build_prompt("exam count", chunks))
    assert sentences[0]["label"] == "syllabus.pdf"


def test_source_label_keeps_page_number():
    chunks = [
        {
            "content": "The final examination accounts for 40 percent of the grade.",
            "metadata": {"filename": "syllabus.pdf", "page_number": 2},
        }
    ]
    _, sentences = gen._split_prompt(build_prompt("exam count", chunks))
    assert sentences[0]["label"] == "syllabus.pdf, page 2"


def test_answer_citation_is_not_padded():
    chunks = [
        {
            "content": "The final examination accounts for 40 percent of the grade.",
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    prompt = build_prompt("How much does the exam count for?", chunks)
    answer = OfflineGenerator()._compose(*gen._split_prompt(prompt))
    assert "(syllabus.pdf)" in answer
    assert "( syllabus.pdf)" not in answer


@pytest.mark.parametrize(
    "asked,written",
    [
        ("exam", "examination"),
        ("grading", "grade"),  # English drops the silent e
        ("assignment", "assign"),
        ("presentation", "present"),
        ("students", "student"),
        ("lectures", "lecture"),
    ],
)
def test_word_forms_match_across_stemming(asked, written):
    """Students ask 'exam'; the notes say 'examination'. Both must match."""
    assert gen._overlap(gen._tokens(asked), gen._tokens(written)) > 0


@pytest.mark.parametrize("short,long", [("cat", "catalog"), ("run", "rung"), ("dog", " dogma")])
def test_short_words_are_not_stemmed(short, long):
    """Guarding against 'cat' collapsing into 'catalog'."""
    assert gen._overlap(gen._tokens(short), gen._tokens(long.strip())) == 0


def test_unrelated_words_do_not_match():
    assert gen._overlap(gen._tokens("pasta"), gen._tokens("tomatoes")) == 0


def test_stem_never_collapses_below_the_minimum():
    """Over-stemming would make everything match everything."""
    for word in ("cat", "run", "dog", "bus", "gas"):
        assert len(gen._stem(word)) >= 3
    assert gen._stem("cat") == "cat"


# -- OpenAI generator (no network) -----------------------------------------


def test_openai_generator_constructs_without_a_key():
    """Constructing must not raise; the client is built on first use."""
    assert OpenAIGenerator().mode == "openai"


def test_openai_generator_defers_client_creation():
    assert OpenAIGenerator()._client is None


async def test_openai_failure_becomes_llm_unavailable(monkeypatch):
    """A network failure must surface as a 503-mapped error, not a 500."""
    generator = OpenAIGenerator()

    class Boom:
        @property
        def chat(self):
            raise RuntimeError("connection refused")

    generator._client = Boom()

    with pytest.raises(LLMUnavailableError, match="could not be reached"):
        await generator.generate("prompt")


async def test_openai_stream_setup_failure_becomes_llm_unavailable():
    generator = OpenAIGenerator()

    class Boom:
        @property
        def chat(self):
            raise RuntimeError("nope")

    generator._client = Boom()

    with pytest.raises(LLMUnavailableError):
        async for _ in generator.generate_stream("prompt"):
            pass


def test_repeated_sentence_is_quoted_once():
    """Overlapping chunks repeat text at the seam; quoting it twice reads badly."""
    repeated = "Office hours are held on Tuesdays from 2pm to 4pm in Gates 412."
    chunks = [
        {
            "content": f"{repeated} " * 3,
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    prompt = build_prompt("When are office hours?", chunks)
    answer = OfflineGenerator()._compose(*gen._split_prompt(prompt))
    assert answer.count("Gates 412") == 1


def test_same_sentence_in_two_documents_is_quoted_once():
    """Identical text across documents should not be listed twice."""
    shared = "The final examination accounts for 40 percent of the course grade."
    chunks = [
        {"content": shared, "metadata": {"filename": "syllabus.pdf"}},
        {"content": shared, "metadata": {"filename": "lecture.md"}},
    ]
    prompt = build_prompt("How much is the exam worth?", chunks)
    answer = OfflineGenerator()._compose(*gen._split_prompt(prompt))
    assert answer.count("40 percent") == 1


def test_distinct_sentences_are_all_kept():
    chunks = [
        {
            "content": (
                "The final examination accounts for 40 percent of the course grade. "
                "Homework contributes 30 percent of the course grade."
            ),
            "metadata": {"filename": "syllabus.pdf"},
        }
    ]
    prompt = build_prompt("What counts toward the grade?", chunks)
    answer = OfflineGenerator()._compose(*gen._split_prompt(prompt))
    assert "40 percent" in answer
    assert "Homework" in answer
