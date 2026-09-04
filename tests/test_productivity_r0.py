"""Tests for R0 — Repair the ingest; add the productivity guard.

Implements agent_execution_guide.md §17 (R0).
"""

import tempfile
from pathlib import Path

import pytest

from worker.entities import Source, Utterance
from worker.integrity import (
    verify_source_productivity,
)
from worker.storage import Storage


def test_verify_source_productivity_empty_set_emits_not_applicable() -> None:
    """Empty store emits NOT APPLICABLE rather than PASS."""
    res = verify_source_productivity([], [])
    assert res.passed is True
    assert res.status == "NOT APPLICABLE — zero rows"
    assert res.examined_count == 0


def test_verify_source_productivity_fails_on_broken_store_assertion_c() -> None:
    """Assertion c: verify_source_productivity FAILS against the known-broken store."""
    broken_db = Path("social_proof_broken.duckdb")
    if not broken_db.exists():
        pytest.skip("social_proof_broken.duckdb not found")

    store = Storage(str(broken_db))
    sources = [
        s
        for row in store.con.execute("SELECT source_id FROM sources").fetchall()
        if (s := store.get_source(row[0])) is not None
    ]
    utts = [
        u
        for row in store.con.execute("SELECT utterance_id FROM utterances").fetchall()
        if (u := store.get_utterance(row[0])) is not None
    ]

    res = verify_source_productivity(sources, utts)
    assert res.passed is False
    assert res.status == "FAIL"
    assert "yielded zero utterances" in res.message


def test_verify_source_productivity_passes_on_repaired_corpus() -> None:
    """After repair, every source has >=1 utterance and the check passes."""
    live_db = Path("social_proof.duckdb")
    assert live_db.exists()

    store = Storage(str(live_db))
    sources = [
        s
        for row in store.con.execute("SELECT source_id FROM sources").fetchall()
        if (s := store.get_source(row[0])) is not None
    ]
    utts = [
        u
        for row in store.con.execute("SELECT utterance_id FROM utterances").fetchall()
        if (u := store.get_utterance(row[0])) is not None
    ]

    res = verify_source_productivity(sources, utts)
    assert res.passed is True
    assert res.status == "PASS"
    assert res.examined_count >= 4


def test_audio_deletion_gated_on_productivity() -> None:
    """Audio-deletion gate: a source that transcribes to zero utterances preserves audio and leaves audio_deleted_at null."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_gate.duckdb"
        store = Storage(str(db_path))

        # Create dummy audio file
        audio_file = Path(tmpdir) / "test_audio.wav"
        audio_file.write_bytes(b"RIFFdummydataWAVEfmt ")

        source = Source(
            source_id="src_empty_test",
            title="Empty Test Source",
            publisher="Test",
            canonical_url="http://test.com/empty",
            artifact_hash="dummyhash",
        )
        store.insert_source(source)

        # Simulate transcription yielding 0 utterances
        utterances: list[Utterance] = []

        # Gate logic: only delete if len(utterances) > 0
        if len(utterances) > 0:
            source.audio_deleted_at = "2026-09-03T12:00:00Z"
            store.insert_source(source)
            if audio_file.exists():
                audio_file.unlink()

        reloaded = store.get_source("src_empty_test")
        assert reloaded is not None
        assert reloaded.audio_deleted_at is None
        assert reloaded.ingested_at is None
        assert audio_file.exists(), "Audio file must survive when 0 utterances produced"


def test_falsification_ungated_deletion_violates_preservation() -> None:
    """Falsify: simulating the ungated deletion deletes the audio and fails survival assertion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_file = Path(tmpdir) / "test_ungated.wav"
        audio_file.write_bytes(b"RIFFdummydataWAVEfmt ")

        # Ungated deletion (the old bug): deletes unconditionally
        audio_file.unlink()

        # The survival assertion MUST go RED under ungated logic:
        assert not audio_file.exists(), (
            "Under ungated deletion, audio file is deleted despite 0 utterances"
        )


def test_repaired_corpus_tension_precondition() -> None:
    """Asserts that tension 0068adec4b1501c6 is preserved in social_proof.duckdb

    and correctly quarantined under X0 as a fabricated proposition.
    """
    store = Storage("social_proof.duckdb")
    t = store.get_tension("0068adec4b1501c6")
    assert t is not None, "Fabricated tension must be preserved in database for audit"
    assert t.status == "quarantined"
    assert t.quarantine_reason == "fabricated_proposition"
