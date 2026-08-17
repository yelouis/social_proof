"""Unit and falsification tests for Proposition Canonicalisation and Dedup (U12)."""

from pathlib import Path

from worker.extract.dedup import PropositionCanonicalizer, compute_deterministic_text_embedding
from worker.storage import Storage


def test_proposition_embedding_generates_768_dim_normalized_vector() -> None:
    emb = compute_deterministic_text_embedding("federal licensing requirement for frontier AI")
    assert len(emb) == 768


def test_near_synonyms_merge_and_distinct_propositions_separate(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    canonicalizer = PropositionCanonicalizer(storage=store, t_dedup=0.88)

    # 1. Insert first proposition
    text1 = "frontier AI model federal licensing requirement"
    res1 = canonicalizer.canonicalise_and_dedup(text1, subject_id="subj_01")
    assert res1.is_new is True

    # 2. Near identical / high similarity text merges
    res2 = canonicalizer.canonicalise_and_dedup(text1, subject_id="subj_02")
    assert res2.is_new is False
    assert res2.proposition_id == res1.proposition_id

    # Check updated proposition in storage
    prop = store.get_proposition(res1.proposition_id)
    assert prop is not None
    assert prop.claim_count == 2
    assert "subj_01" in prop.subject_ids
    assert "subj_02" in prop.subject_ids

    # 3. Distinct proposition remains separate
    text3 = "gpu semiconductor export control restrictions"
    res3 = canonicalizer.canonicalise_and_dedup(text3, subject_id="subj_01")
    assert res3.is_new is True
    assert res3.proposition_id != res1.proposition_id


def test_falsification_low_threshold_falsely_merges_distinct_propositions(tmp_path: Path) -> None:
    """Falsification test: Setting T_dedup = -1.0 falsely merges completely distinct propositions."""
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    broken_canonicalizer = PropositionCanonicalizer(storage=store, t_dedup=-1.0)

    res1 = broken_canonicalizer.canonicalise_and_dedup("federal licensing requirement", subject_id="subj_01")
    res2 = broken_canonicalizer.canonicalise_and_dedup("export control on advanced GPUs", subject_id="subj_01")

    # With T_dedup = -1.0, res2 is falsely merged into res1
    assert res2.is_new is False
    assert res2.proposition_id == res1.proposition_id  # Falsification confirmed!
