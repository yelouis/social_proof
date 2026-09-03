"""Validation and falsification tests for Voice Enrollment of the four All-In hosts (I0.1).

Covers:
- Extraction of reference voice embeddings for Chamath, Sacks, Calacanis, and Friedberg.
- Mutual distinguishability: every pairwise cosine similarity sits strictly below T_low (0.50) (c).
- Single-speaker cluster verification over each enrollment sample.
- Falsification: enrolling the same speaker under two IDs triggers distinguishability failure.
"""

import json
from pathlib import Path

import pytest

from worker.diarize.enrollment import (
    VoiceEnrollmentStore,
    extract_voice_embedding,
    verify_mutual_distinguishability,
    verify_single_speaker,
)
from worker.entities import Subject
from worker.storage import Storage


def test_enrollment_extraction_and_store_round_trip(tmp_path: Path) -> None:
    manifest_path = Path("fixtures/enrollment/manifest.json")
    assert manifest_path.exists(), "Enrollment manifest missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    enrollments = manifest["enrollments"]
    assert len(enrollments) == 4

    store = VoiceEnrollmentStore(base_dir=tmp_path / "enrollments")

    for item in enrollments:
        audio_path = Path(item["audio_file"])
        assert audio_path.exists(), f"Audio fixture missing: {audio_path}"

        emb = extract_voice_embedding(audio_path)
        assert len(emb) == 192, f"Expected 192-dim ECAPA embedding, got {len(emb)}"

        ref = store.save_enrollment(
            subject_id=item["subject_id"],
            embedding=emb,
            source_id="src_allin_e287",
            verified_by=item["verified_by"],
            metadata={
                "display_name": item["display_name"],
                "source_url": item["source_url"],
                "duration_ms": item["duration_ms"],
                "span_start_ms": item["span_start_ms"],
                "span_end_ms": item["span_end_ms"],
            },
        )
        assert len(ref) == 64

        saved = store.get_enrollment(ref)
        assert saved is not None
        assert saved["subject_id"] == item["subject_id"]
        assert saved["metadata"]["display_name"] == item["display_name"]
        assert saved["metadata"]["duration_ms"] == item["duration_ms"]


def test_four_hosts_mutual_distinguishability_below_t_low() -> None:
    """Pre-flight check (c): compute pairwise cosine similarity across all four enrollment

    embeddings and assert every cross-subject pair sits well below T_low (0.50).
    """
    manifest_path = Path("fixtures/enrollment/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    embeddings: dict[str, list[float]] = {}
    for item in manifest["enrollments"]:
        emb = extract_voice_embedding(item["audio_file"])
        embeddings[item["subject_id"]] = emb

    # Compute pairwise similarities and enforce T_low = 0.50 threshold
    similarities = verify_mutual_distinguishability(embeddings, t_low=0.50)

    # 4 subjects = 6 pairs
    assert len(similarities) == 6

    # Verify every cross-subject pair is well separated
    for (s1, s2), sim in similarities.items():
        assert sim < 0.50, f"Subjects {s1} and {s2} are too close: {sim:.4f} >= 0.50"
        print(f"Distinguishability: {s1} vs {s2} = {sim:.4f} (PASS < 0.50)")


def test_each_enrollment_sample_is_single_speaker() -> None:
    """Assert each enrollment sample is genuinely single-speaker — exactly 1 cluster."""
    manifest_path = Path("fixtures/enrollment/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for item in manifest["enrollments"]:
        audio_path = Path(item["audio_file"])
        assert verify_single_speaker(audio_path, window_s=3.0, hop_s=1.5, t_low=0.50) is True


def test_duckdb_storage_subject_enrollment_ref(tmp_path: Path) -> None:
    """Enrolled subjects with enrollment_ref round-trip in DuckDB storage."""
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    manifest_path = Path("fixtures/enrollment/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    v_store = VoiceEnrollmentStore(base_dir=tmp_path / "enrollments")

    for item in manifest["enrollments"]:
        emb = extract_voice_embedding(item["audio_file"])
        ref = v_store.save_enrollment(
            subject_id=item["subject_id"],
            embedding=emb,
            source_id="src_allin_e287",
            verified_by=item["verified_by"],
        )

        subj = Subject(
            subject_id=item["subject_id"],
            display_name=item["display_name"],
            enrollment_ref=ref,
        )
        store.insert_subject(subj)

        fetched = store.get_subject(subj.subject_id)
        assert fetched is not None
        assert fetched.subject_id == subj.subject_id
        assert fetched.display_name == subj.display_name
        assert fetched.enrollment_ref == ref


def test_falsification_same_person_enrolled_twice_fails_distinguishability() -> None:
    """Falsification test for I0.1: Enrolling the same person twice under two subject IDs

    causes mutual distinguishability assertion to fail (go RED).
    """
    manifest_path = Path("fixtures/enrollment/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_item = manifest["enrollments"][0]

    emb = extract_voice_embedding(first_item["audio_file"])

    # Enroll the same person twice under two subject IDs
    cloned_embeddings = {
        "subj_person_real": emb,
        "subj_person_clone": emb,  # identical voice embedding
    }

    with pytest.raises(AssertionError, match="Mutual distinguishability failure"):
        verify_mutual_distinguishability(cloned_embeddings, t_low=0.50)
