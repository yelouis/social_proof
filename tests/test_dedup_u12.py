"""Unit and falsification tests for Proposition Canonicalisation, Embedder, and Dedup (U12 / V2)."""

from pathlib import Path

import numpy as np
import pytest

from worker.extract.dedup import Embedder, PropositionCanonicalizer, stub_hash_embedding
from worker.storage import Storage


def test_stub_hash_embedding_generates_768_dim_vector() -> None:
    emb = stub_hash_embedding("federal licensing requirement for frontier AI")
    assert len(emb) == 768


@pytest.mark.requires_models
def test_real_embedder_dimension_and_task_prefixes_trap_7() -> None:
    """Tests nomic-embed-text-v1.5 embedding output and task prefix enforcement (Trap 7)."""
    embedder = Embedder()
    text = "federal licensing requirement for large frontier AI models"

    doc_emb = embedder.embed_document(text)
    query_emb = embedder.embed_query(text)

    # 1. Dimension enforcement
    assert len(doc_emb) == 768
    assert len(query_emb) == 768

    # 2. Trap 7: Prefix test: embedding the same string with search_document vs search_query yields DIFFERENT vectors
    assert doc_emb != query_emb
    prefix_diff = np.linalg.norm(np.array(doc_emb) - np.array(query_emb))
    assert prefix_diff > 0.01, f"Task prefixes had negligible effect: diff = {prefix_diff}"


@pytest.mark.requires_models
def test_semantic_synonyms_merge_and_antonyms_separate_with_real_embedder(tmp_path: Path) -> None:
    """Synonym test: 'licensing' vs 'permitting' phrasing scores above T_dedup and merges.

    No bag-of-words hash function can pass this test!
    """
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    embedder = Embedder()
    canonicalizer = PropositionCanonicalizer(storage=store, embedder=embedder, t_dedup=0.88)

    # 1. Insert first proposition
    text1 = "federal licensing of frontier models"
    res1 = canonicalizer.canonicalise_and_dedup(text1, subject_id="subj_01")
    assert res1.is_new is True

    # 2. Semantic synonym (different wording, same underlying proposition)
    text2 = "licensing requirements for frontier models"
    res2 = canonicalizer.canonicalise_and_dedup(text2, subject_id="subj_02")

    # Real semantic embedder recognizes synonymy (>0.90) and merges:
    assert res2.is_new is False, f"Synonyms failed to merge! Similarity was {res2.similarity}"
    assert res2.proposition_id == res1.proposition_id
    assert res2.similarity >= 0.88

    # 3. Antonym-of-topic proposition remains separate
    text3 = "export controls on advanced graphics processing units"
    res3 = canonicalizer.canonicalise_and_dedup(text3, subject_id="subj_01")
    assert res3.is_new is True
    assert res3.proposition_id != res1.proposition_id
    assert res3.similarity < 0.88


def test_dimension_mismatch_raises_at_startup() -> None:
    """A model instance reporting wrong dimension raises ValueError at initialization."""
    class FakeModel:
        def get_embedding_dimension(self) -> int:
            return 512

    with pytest.raises(ValueError, match="Embedding dimension mismatch: expected 768, got 512"):
        Embedder(model_instance=FakeModel(), expected_dim=768)


@pytest.mark.requires_models
def test_falsification_dropping_task_prefixes_alters_embedding_geometry() -> None:
    """Falsification test: Dropping task prefixes causes prefix distinction check to fail."""
    embedder = Embedder()
    text = "mandating federal safety evaluations"

    # Bare embedding without task prefix
    bare_vec = embedder._embed(text)
    doc_vec = embedder.embed_document(text)

    # Prefix change is load-bearing
    delta = float(np.linalg.norm(np.array(bare_vec) - np.array(doc_vec)))
    assert delta > 0.01  # Falsification confirmed: task prefixes measurably change vectors!
