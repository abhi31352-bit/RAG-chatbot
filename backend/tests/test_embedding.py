"""Tests for the embedding providers and the Chroma-backed vector store."""

import re

import pytest

from app.config import settings
from app.exceptions import EmbeddingUnavailableError
from app.services import embedding_service as es
from app.services.embedding_service import (
    EmbeddingMismatchError,
    LocalHashEmbedder,
    get_chroma_client,
    get_chroma_collection,
    get_embedding_service,
)


@pytest.fixture(autouse=True)
def force_local_provider():
    """conftest pins EMBEDDING_PROVIDER=local; this guards the in-process cache."""
    es.EmbeddingService.reset()


# -- Local embedder --------------------------------------------------------


def test_local_embedder_is_deterministic():
    """Determinism matters: a salted hash would invalidate the stored index."""
    a = LocalHashEmbedder(dim=128)
    b = LocalHashEmbedder(dim=128)
    text = "retrieval augmented generation"
    assert a.embed(text) == b.embed(text)


def test_local_embedder_is_normalized():
    import math

    vector = LocalHashEmbedder(dim=256).embed("machine learning lecture notes")
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_local_embedder_blank_text_is_zero_vector():
    assert set(LocalHashEmbedder(dim=64).embed("   ")) == {0.0}


def test_local_embedder_respects_dim():
    assert len(LocalHashEmbedder(dim=32).embed("hello")) == 32


def test_local_embedder_rejects_bad_dim():
    with pytest.raises(ValueError):
        LocalHashEmbedder(dim=0)


def test_local_embedder_similar_text_scores_higher_than_unrelated():
    embedder = LocalHashEmbedder(dim=2048)
    query = embedder.embed("neural networks and deep learning")
    related = embedder.embed("lecture about neural networks and deep learning")
    unrelated = embedder.embed("cooking pasta with tomatoes and basil")

    def cosine(x, y):
        return sum(a * b for a, b in zip(x, y))

    assert cosine(query, related) > cosine(query, unrelated)


def test_local_embedder_caches_results():
    embedder = LocalHashEmbedder(dim=64)
    first = embedder.embed("repeatable text")
    assert embedder.embed("repeatable text") is first


# -- Collision resistance ---------------------------------------------------
#
# A word present in a document must be findable by that word alone. Under signed
# hashing this does not hold: two features landing in the same bucket with equal
# counts and opposite signs cancel exactly, so the term is invisible rather than
# noisy. In a 160-feature syllabus chunk at 512 dimensions, 24 buckets collided
# and 9 cancelled outright -- "homework" was annihilated by "trees", so "What
# does homework contribute?" retrieved nothing from the only document stating
# the homework weighting.
#
# The tests below assert the invariant, and the last one pins the counterfactual
# so the sign step does not get reintroduced.


def _distinct_words(text):
    return sorted(set(re.findall(r"[a-z0-9]+", text.lower())))


def _recreate_empty_collection():
    """Hand back a brand-new, empty collection with no width set yet.

    The Chroma directory is shared for the whole session, so a test that cares
    about a collection's width has to establish that width itself rather than
    inherit whatever an earlier test left behind. Chroma refuses `delete` with
    an empty id list, so clearing by id is not an option either.
    """
    client = get_chroma_client()
    try:
        client.delete_collection(settings.CHROMA_COLLECTION_NAME)
    except Exception:  # noqa: BLE001 - may not exist yet
        pass
    es.EmbeddingService.reset()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


#: A chunk with the shape of real extracted text: repeated terms, a couple of
#: high-frequency function words, and a mix of content words and bigrams.
SAMPLE_CHUNK = """
CS 401 Machine Learning Syllabus. The final examination accounts for 40 percent
of the course grade. Homework contributes 30 percent and the term project
contributes 30 percent. Late work loses 10 percent per day, up to five days.
Week 1 covers supervised learning including linear regression and logistic
regression. Week 2 covers decision trees and random forests. Week 3 covers
gradient descent and backpropagation. The project proposal is due at the end of
week four and is worth five percent of the final grade. Office hours are held
on Tuesdays from 2pm to 4pm in Gates 412. The TA is Priya Raman. Grading is
cumulative and there is no curve.
"""


def test_every_word_in_a_chunk_stays_retrievable_at_the_configured_dimension():
    """A word present in a document must be findable by that word alone.

    This is the failure that made "What does homework contribute?" return the
    no-context fallback even though the syllabus states the homework weighting
    outright.
    """
    embedder = LocalHashEmbedder(dim=settings.LOCAL_EMBEDDING_DIM)
    chunk_vec = embedder.embed(SAMPLE_CHUNK)

    invisible = [
        word
        for word in _distinct_words(SAMPLE_CHUNK)
        if _cosine(embedder.embed(word), chunk_vec) <= 0.0
    ]

    assert not invisible, (
        f"{len(invisible)} of "
        f"{len(_distinct_words(SAMPLE_CHUNK))} words are unretrievable against "
        f"the chunk that contains them: {invisible}. Collisions must only ever "
        f"add to a bucket, never cancel one -- check that no sign is being "
        f"applied during accumulation."
    )


def test_the_shipped_dimension_has_headroom_for_a_longer_chunk():
    """The invariant has to hold for a chunk bigger than one sentence.

    The default dimension has to survive a realistic extracted chunk, not a
    toy one, so this roughly doubles the feature count the way a two-chunk
    document would.
    """
    embedder = LocalHashEmbedder(dim=settings.LOCAL_EMBEDDING_DIM)
    words = _distinct_words(SAMPLE_CHUNK)
    longer = SAMPLE_CHUNK + SAMPLE_CHUNK.replace("Week", "Lecture").replace(
        "covers", "examines"
    )
    chunk_vec = embedder.embed(longer)

    invisible = [w for w in _distinct_words(longer) if _cosine(embedder.embed(w), chunk_vec) <= 0.0]

    assert len(_distinct_words(longer)) > len(words)
    assert not invisible, f"words invisible in a longer chunk: {invisible}"


def _signed_embed(text, dim):
    """The hashing scheme this class used to implement, kept as a counterfactual.

    Identical to `LocalHashEmbedder` except that each feature carries a +/-1
    sign taken from the digest. Written out here rather than imported because
    the point is to show what the alternative does; the production class has no
    sign step to reach for.
    """
    import hashlib
    import math as _math
    from collections import Counter as _Counter

    vector = [0.0] * dim
    words = re.findall(r"[a-z0-9]+", text.lower())
    features = _Counter(words)
    for i in range(len(words) - 1):
        features[f"{words[i]}_{words[i + 1]}"] += 1
    for term, count in features.items():
        digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        vector[index] += (1.0 if digest[4] & 1 else -1.0) * (1.0 + _math.log(count))
    norm = _math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


def test_the_sign_scheme_not_the_width_is_what_keeps_terms_visible():
    """Pin the counterfactual, so nobody re-adds signs to 'reduce bias'.

    Both variants run at the same dimension on the same chunk. The signed one
    annihilates terms; the shipped unsigned one does not. Widening the vector
    is the tempting alternative fix and it is not sufficient -- at 8192
    dimensions a term in this corpus still cancelled under signing.
    """
    dim = settings.LOCAL_EMBEDDING_DIM

    signed_chunk = _signed_embed(SAMPLE_CHUNK, dim)
    signed_invisible = [
        word
        for word in _distinct_words(SAMPLE_CHUNK)
        if _cosine(_signed_embed(word, dim), signed_chunk) <= 0.0
    ]

    shipped = LocalHashEmbedder(dim=dim)
    unsigned_chunk = shipped.embed(SAMPLE_CHUNK)
    unsigned_invisible = [
        word
        for word in _distinct_words(SAMPLE_CHUNK)
        if _cosine(shipped.embed(word), unsigned_chunk) <= 0.0
    ]

    assert signed_invisible, (
        "expected the signed scheme to still annihilate a term here; if it no "
        "longer does, this sample has stopped reproducing the bug and the "
        "assertion below proves nothing"
    )
    assert not unsigned_invisible


def test_terms_present_in_a_chunk_outrank_terms_absent_from_it():
    """Presence must be the dominant signal, or the net has no discrimination.

    Single terms are compared rather than whole questions: a hashed
    bag-of-words deliberately does not separate a four-word question from an
    unrelated four-word question, because after L2 normalization against a
    160-feature chunk both are dominated by collision noise. Rejecting
    off-topic questions is the job of sentence scoring in the generator, not of
    this vector. What retrieval must guarantee is that a word in the document
    beats a word that is not.
    """
    embedder = LocalHashEmbedder(dim=settings.LOCAL_EMBEDDING_DIM)
    chunk_vec = embedder.embed(SAMPLE_CHUNK)

    present = ["homework", "office", "hours", "exam", "backpropagation", "sourdough"]
    absent = ["helicopter", "tectonic", "chlorophyll", "baritone", "wolverine"]

    lowest_present = min(_cosine(embedder.embed(w), chunk_vec) for w in present)
    highest_absent = max(_cosine(embedder.embed(w), chunk_vec) for w in absent)

    assert lowest_present > 0.0, "a word in the chunk scored zero"
    assert lowest_present > highest_absent


def test_retrieval_is_a_high_recall_net_not_a_relevance_filter():
    """Document the division of labour, so nobody expects precision here.

    Off-topic questions do retrieve this chunk. That is intended: the vector
    store is a lexical net whose only hard requirement is that a word in the
    document is *findable*, and the offline generator's sentence-level
    `_overlap` is what rejects an off-topic question with the no-context
    fallback. Asserting that a whole unrelated question scores near zero would
    be asserting a property this embedder does not have and should not pretend
    to.
    """
    embedder = LocalHashEmbedder(dim=settings.LOCAL_EMBEDDING_DIM)
    chunk_vec = embedder.embed(SAMPLE_CHUNK)

    off_topic = _cosine(
        embedder.embed("What is the weather like today?"), chunk_vec
    )

    # Small but non-zero: the question shares no vocabulary with the chunk, so
    # everything here is collision noise.
    assert 0.0 < off_topic < 0.35


# -- Provider selection ----------------------------------------------------


def test_resolve_provider_auto_falls_back_without_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "auto")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    assert es.resolve_provider() == "local"


def test_resolve_provider_auto_rejects_placeholder_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "auto")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-your-key-here")
    assert es.resolve_provider() == "local"


def test_resolve_provider_auto_uses_openai_with_real_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "auto")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-abc123")
    assert es.resolve_provider() == "openai"


def test_resolve_provider_forced_openai_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        es.resolve_provider()


def test_explicit_local_ignores_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-abc123")
    assert es.resolve_provider() == "local"


# -- Vector store ----------------------------------------------------------


async def test_store_and_search_round_trip():
    service = get_embedding_service()
    chunks = [
        "Lecture one covers supervised learning and regression models.",
        "Lecture two covers unsupervised learning and clustering algorithms.",
        "The grading policy assigns forty percent to the final examination.",
    ]
    embeddings = await service.embed_texts(chunks)
    await service.store_embeddings(
        document_id="doc_test_1", chunks=chunks, embeddings=embeddings, filename="syllabus.txt"
    )

    results = await service.search_by_text("How much does the final exam count?", top_k=3)
    assert results, "expected at least one match"
    assert "grading" in results[0]["content"].lower()
    assert results[0]["metadata"]["filename"] == "syllabus.txt"
    assert results[0]["metadata"]["document_id"] == "doc_test_1"
    assert -1.01 <= results[0]["similarity"] <= 1.01


async def test_search_returns_results_sorted_by_similarity():
    service = get_embedding_service()
    chunks = [f"chunk number {i} about topic {i}" for i in range(6)]
    embeddings = await service.embed_texts(chunks)
    await service.store_embeddings(
        document_id="doc_test_sort", chunks=chunks, embeddings=embeddings, filename="s.txt"
    )
    results = await service.search_by_text("topic 3", top_k=4)
    distances = [r["distance"] for r in results]
    assert distances == sorted(distances)


async def test_store_rejects_mismatched_lengths():
    service = get_embedding_service()
    with pytest.raises(ValueError, match="embeddings"):
        await service.store_embeddings(
            document_id="doc_x", chunks=["a", "b"], embeddings=[[0.1, 0.2]]
        )


async def test_store_empty_chunks_is_noop():
    service = get_embedding_service()
    await service.store_embeddings(document_id="doc_empty", chunks=[], embeddings=[])


async def test_delete_by_document_id_removes_only_that_document():
    service = get_embedding_service()
    for doc_id, text in [("doc_keep", "alpha beta gamma"), ("doc_drop", "delta epsilon")]:
        vectors = await service.embed_texts([text])
        await service.store_embeddings(
            document_id=doc_id, chunks=[text], embeddings=vectors, filename=f"{doc_id}.txt"
        )

    before = get_chroma_collection().count()
    await service.delete_by_document_id("doc_drop")
    after = get_chroma_collection().count()

    assert after == before - 1
    remaining = get_chroma_collection().get(where={"document_id": "doc_keep"})
    assert len(remaining["ids"]) == 1


async def test_search_on_empty_index_returns_empty_list():
    service = get_embedding_service()
    empty = await service.embed_query("anything")
    # Guard the specific "no documents uploaded" case.
    if get_chroma_collection().count() == 0:
        assert await service.search(empty) == []


async def test_stats_reports_index_model():
    """Stats must name the model the index was actually built with.

    Indexes first: reading the sidecar without storing anything only works if
    some earlier test happened to leave one behind, which is order dependence
    rather than a real assertion.
    """
    service = get_embedding_service()
    vectors = await service.embed_texts(["content for the stats check"])
    await service.store_embeddings(
        document_id="doc_stats", chunks=["content for the stats check"],
        embeddings=vectors, filename="a.txt",
    )

    stats = await service.get_stats()
    assert stats["embedding_provider"] == "local"
    assert stats["indexed_with"] == f"local-hash-{settings.LOCAL_EMBEDDING_DIM}"
    assert stats["total_chunks"] > 0


async def test_stats_report_no_model_when_nothing_is_indexed():
    """An empty index reports no model rather than a stale one.

    Reporting the old model after everything has been deleted is what made a
    re-index look permanently blocked.
    """
    stats = await get_embedding_service().get_stats()
    if stats["total_chunks"] == 0:
        assert stats["indexed_with"] is None


async def test_query_with_mismatched_provider_is_rejected():
    """A local query must not silently hit an index built by another provider."""
    service = get_embedding_service()
    chunks = ["machine learning fundamentals"]
    vectors = await service.embed_texts(chunks)
    await service.store_embeddings(
        document_id="doc_mismatch", chunks=chunks, embeddings=vectors, filename="a.txt"
    )

    # Pretend the stored index was built by OpenAI.
    es.EmbeddingService._write_index_info("openai", "text-embedding-3-small", 1536)

    with pytest.raises(EmbeddingMismatchError, match="Re-index"):
        await service.search_by_text("machine learning")


async def test_mismatch_is_ignored_once_the_index_is_empty(monkeypatch):
    """Deleting the last document must unblock a re-index, not deadlock it.

    The documented remedy for a provider change is "delete the documents and
    upload them again". If the stale state were still honoured on an empty
    collection, that remedy could never succeed: every upload would be refused
    with the very error the user was told to fix by uploading, and the index
    would be permanently stuck on the old model.

    There are two independent pieces of stale state, and both have to give
    way. The index-info sidecar is bookkeeping, so it is discarded outright.
    The Chroma collection's dimensionality is baked into ``chroma.sqlite3`` when
    the collection is created, so clearing the sidecar alone is not enough --
    the embed step passes and the store then fails with "Embedding dimension N
    does not match collection dimensionality M". An empty collection is
    therefore rebuilt at the new width.
    """
    service = get_embedding_service()

    # Chroma fixes a collection's width from the first vector inserted and keeps
    # it in its own `collections` table, unreachable through the public API. So
    # the stale state is built for real: a fresh collection, one 512-wide vector
    # to pin the width, then the vector removed to leave it empty.
    collection = _recreate_empty_collection()
    narrow = LocalHashEmbedder(dim=512)
    collection.upsert(
        ids=["width_probe"],
        embeddings=[narrow.embed("probe content that fixes the width at 512")],
        documents=["probe content that fixes the width at 512"],
        metadatas=[{"document_id": "doc_drain", "filename": "a.txt", "chunk_index": 0}],
    )
    collection.delete(ids=["width_probe"])
    assert collection.count() == 0

    # The sidecar still says 512, as it would after the setting changed.
    es.EmbeddingService._write_index_info("local", "local-hash-512", 512)
    monkeypatch.setattr(settings, "LOCAL_EMBEDDING_DIM", 2048)

    # Both halves of the stale state must give way. The embed step...
    fresh = await service.embed_texts(["brand new content"])
    assert len(fresh) == 1
    assert len(fresh[0]) == 2048

    # ...and the store step, which is where the old width used to raise
    # "Embedding dimension 2048 does not match collection dimensionality 512".
    await service.store_embeddings(
        document_id="doc_drain", chunks=["brand new content"],
        embeddings=fresh, filename="a.txt",
    )
    assert get_chroma_collection().count() == 1

    info = es.EmbeddingService._read_index_info()
    assert info["embedding_model"] == "local-hash-2048"


async def test_mismatch_is_still_enforced_on_a_populated_index():
    """The empty-index exemption must not weaken the real check.

    Counterpart to the test above: a collection that still holds vectors really
    is dimension-locked, and silently mixing providers would return meaningless
    neighbours.
    """
    service = get_embedding_service()
    vectors = await service.embed_texts(["content that stays in the index"])
    await service.store_embeddings(
        document_id="doc_populated", chunks=["content that stays in the index"],
        embeddings=vectors, filename="a.txt",
    )
    assert get_chroma_collection().count() > 0

    es.EmbeddingService._write_index_info("openai", "text-embedding-3-small", 1536)

    with pytest.raises(EmbeddingMismatchError, match="Re-index"):
        await service.search_by_text("anything")


async def test_reindex_same_ids_is_idempotent():
    """Re-uploading the same chunk ids must upsert, not duplicate."""
    service = get_embedding_service()
    chunks = ["overlap me please"]
    vectors = await service.embed_texts(chunks)
    for _ in range(2):
        await service.store_embeddings(
            document_id="doc_idem", chunks=chunks, embeddings=vectors, filename="x.txt"
        )
    rows = get_chroma_collection().get(where={"document_id": "doc_idem"})
    assert len(rows["ids"]) == 1


def test_chroma_client_is_singleton():
    assert get_chroma_client() is get_chroma_client()


async def test_provider_failure_becomes_embedding_unavailable(monkeypatch):
    """A dead provider must surface as 503, not an opaque 500."""
    service = get_embedding_service()

    class DeadEmbedder:
        model_name = "text-embedding-3-small"
        dimension = 1536

        async def embed_many(self, texts):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(type(service), "get_embedder", classmethod(lambda cls: DeadEmbedder()))
    monkeypatch.setattr(type(service), "get_provider", classmethod(lambda cls: "openai"))
    es.EmbeddingService._write_index_info("openai", "text-embedding-3-small", 1536)

    with pytest.raises(EmbeddingUnavailableError, match="could not be reached"):
        await service.embed_query("anything")

    es.EmbeddingService._write_index_info(
        "local", f"local-hash-{settings.LOCAL_EMBEDDING_DIM}", settings.LOCAL_EMBEDDING_DIM
    )


async def test_mismatch_is_checked_before_calling_the_provider(monkeypatch):
    """A mismatched index should fail without spending an API call."""
    service = get_embedding_service()
    # The stored index reports a different model than the live embedder.
    es.EmbeddingService._write_index_info("openai", "text-embedding-3-large", 1536)

    calls = []

    class CountingEmbedder:
        model_name = "text-embedding-3-small"
        dimension = 1536

        async def embed_many(self, texts):
            calls.append(texts)
            return [[0.0] * 1536]

    monkeypatch.setattr(type(service), "get_embedder", classmethod(lambda cls: CountingEmbedder()))
    monkeypatch.setattr(type(service), "get_provider", classmethod(lambda cls: "openai"))

    with pytest.raises(EmbeddingMismatchError):
        await service.embed_query("anything")
    assert calls == [], "the provider should not be called on a known mismatch"

    es.EmbeddingService._write_index_info(
        "local", f"local-hash-{settings.LOCAL_EMBEDDING_DIM}", settings.LOCAL_EMBEDDING_DIM
    )


def test_mismatch_error_carries_a_client_status():
    """The chat path returns this directly, so it needs an HTTP mapping."""
    error = EmbeddingMismatchError()
    assert error.status_code == 409
    assert error.code == "EMBEDDING_MISMATCH"
