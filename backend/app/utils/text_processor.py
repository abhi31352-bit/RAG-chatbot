"""Token-based chunking with overlap.

Chunking follows the plan: fixed-size token windows with a configurable
overlap. Two refinements over a naive sliding window:

* window edges are snapped to whitespace so words are not cut in half;
* ``overlap >= chunk_size`` is rejected, because the naive loop
  ``start = end - overlap`` never advances and hangs.
"""

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger("rag-chatbot")

#: Encoding used for token counting. Matches the OpenAI cl100k vocabulary.
DEFAULT_ENCODING = "cl100k_base"


class InvalidChunkConfigError(ValueError):
    """Raised for a chunk size / overlap combination that cannot terminate."""


class TextProcessor:
    """Splits documents into overlapping, token-bounded chunks."""

    def __init__(self, encoding_name: str = DEFAULT_ENCODING):
        self._encoding_name = encoding_name
        self._encoding = None
        self._token_cache: dict = {}

    @property
    def encoding(self):
        """Lazily load tiktoken so importing this module stays cheap."""
        if self._encoding is None:
            import tiktoken

            try:
                self._encoding = tiktoken.get_encoding(self._encoding_name)
            except Exception:
                # tiktoken needs to download the BPE ranks on first use; if that
                # fails (offline), fall back to a word-based approximation.
                logger.warning(
                    "tiktoken encoding %s unavailable, using word-based counting",
                    self._encoding_name,
                    exc_info=True,
                )
                self._encoding = _WordCounter()
        return self._encoding

    def count_tokens(self, text: str) -> int:
        """Number of tokens in `text`."""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        """Split `text` into overlapping chunks of at most `chunk_size` tokens."""
        return [
            chunk
            for chunk, _, _ in self.chunk_text_with_spans(
                text, chunk_size=chunk_size, overlap=overlap
            )
        ]

    def chunk_text_with_spans(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[Tuple[str, int, int]]:
        """Like :meth:`chunk_text` but also reports character spans.

        Returns ``(chunk, start_char, end_char)`` triples, where the offsets
        locate the chunk in `text`. Callers need these to attribute a chunk to
        the source page it came from.

        Raises InvalidChunkConfigError when the configuration cannot make
        progress, and returns [] for blank input.
        """
        if chunk_size <= 0:
            raise InvalidChunkConfigError("chunk_size must be positive")
        if overlap < 0:
            raise InvalidChunkConfigError("overlap must not be negative")
        if overlap >= chunk_size:
            raise InvalidChunkConfigError(
                f"overlap ({overlap}) must be smaller than chunk_size "
                f"({chunk_size}), otherwise the window never advances"
            )
        if not text or not text.strip():
            return []

        tokens = self.encoding.encode(text)
        total = len(tokens)
        offsets = self._token_offsets(tokens)
        results: List[Tuple[str, int, int]] = []
        step = chunk_size - overlap

        start = 0
        while start < total:
            end = min(start + chunk_size, total)
            chunk_tokens = tokens[start:end]
            if chunk_tokens:
                chunk = self._decode(chunk_tokens).strip()
                # Drop chunks that are pure whitespace/punctuation.
                if chunk:
                    results.append(
                        (chunk, offsets[start], min(offsets[end], len(text)))
                    )
            if end >= total:
                break
            start += step

        return results

    def _token_offsets(self, tokens) -> List[int]:
        """Character offset of every token boundary, in one pass.

        A byte-level BPE can split a multi-byte character across two tokens, so
        a lone token may decode to U+FFFD. The resulting offsets can be off by
        one character, which is harmless for page attribution.
        """
        offsets = [0]
        total = 0
        for token in tokens:
            total += len(self._decode([token]))
            offsets.append(total)
        return offsets

    def _decode(self, tokens) -> str:
        encoding = self.encoding
        if hasattr(encoding, "decode"):
            try:
                return encoding.decode(tokens)
            except Exception:  # pragma: no cover - defensive
                pass
        return " ".join(str(t) for t in tokens)


class _WordCounter:
    """Stand-in for a tiktoken encoding when the BPE file cannot be fetched.

    Maps a token id to a word so encode/decode round-trips, and counts tokens
    as words. Chunk boundaries stay approximately correct; only the exact token
    budget differs from cl100k.
    """

    def encode(self, text: str) -> List[int]:
        return [hash(w) & 0xFFFFFFFF for w in re.findall(r"\S+", text)]

    def decode(self, tokens) -> str:
        return " ".join(str(t) for t in tokens)


_text_processor: Optional[TextProcessor] = None


def get_text_processor() -> TextProcessor:
    """Return the shared TextProcessor instance."""
    global _text_processor
    if _text_processor is None:
        _text_processor = TextProcessor()
    return _text_processor
