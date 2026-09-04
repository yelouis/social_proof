"""Tests for R1 — Media duration, real coverage check, and feed metadata.

Implements agent_execution_guide.md §19 (R1) and design_source_acquisition.md §4, §5.2.
"""

from datetime import datetime
from pathlib import Path

import pytest

from worker.adapters.base import SourceRef
from worker.adapters.podcast import (
    PodcastRSSAdapter,
    parse_itunes_duration,
    parse_rfc822_date,
)
from worker.entities import Source, Subject, Utterance
from worker.ingest import IngestionEngine
from worker.integrity import MIN_UTTERANCE_MEDIA_RATIO, verify_source_productivity
from worker.storage import Storage


def test_parse_itunes_duration_formats() -> None:
    """Verifies parsing of all standard itunes:duration formats into milliseconds."""
    # HH:MM:SS
    assert parse_itunes_duration("01:36:41") == 5_801_000
    assert parse_itunes_duration("1:29:31") == 5_371_000
    assert parse_itunes_duration("00:05:00") == 300_000

    # MM:SS
    assert parse_itunes_duration("96:41") == 5_801_000
    assert parse_itunes_duration("05:00") == 300_000
    assert parse_itunes_duration("00:30") == 30_000

    # Seconds integer / float
    assert parse_itunes_duration("5801") == 5_801_000
    assert parse_itunes_duration("300.5") == 300_500

    # Null / empty / invalid
    assert parse_itunes_duration("") == 0
    assert parse_itunes_duration(None) == 0
    assert parse_itunes_duration("invalid_duration") == 0


def test_parse_rfc822_date() -> None:
    """Verifies parsing of RFC 822 / RFC 2822 pubDate formats into ISO 8601 UTC."""
    raw = "Sat, 29 Aug 2026 01:19:00 +0000"
    parsed = parse_rfc822_date(raw)
    assert parsed == "2026-08-29T01:19:00+00:00"

    raw_gmt = "Mon, 15 Jan 2024 10:00:00 GMT"
    parsed_gmt = parse_rfc822_date(raw_gmt)
    assert parsed_gmt == "2024-01-15T10:00:00+00:00"

    iso_str = "2025-10-03T16:39:00Z"
    parsed_iso = parse_rfc822_date(iso_str)
    assert parsed_iso == "2025-10-03T16:39:00+00:00"

    assert parse_rfc822_date("") is None
    assert parse_rfc822_date(None) is None


def test_verify_source_productivity_unit_both_directions() -> None:
    """Unit test, both directions:

    1% utterance coverage -> FAIL
    95% utterance coverage -> PASS
    """
    # 100-minute episode = 6,000,000 ms
    duration_ms = 6_000_000
    src = Source(
        source_id="src_unit_test",
        title="Unit Test Source",
        publisher="Test",
        canonical_url="https://example.com/audio.mp3",
        artifact_hash="hash123",
        duration_ms=duration_ms,
        ingested_at="2026-09-04T12:00:00Z",
    )

    # Case 1: 1% coverage (60,000 ms span out of 6,000,000 ms) -> FAIL
    utts_1pct = [
        Utterance(
            utterance_id="u1",
            source_id="src_unit_test",
            subject_id="s1",
            text_verbatim="Short span start.",
            start_ms=0,
            end_ms=60_000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="test",
        )
    ]
    res_1pct = verify_source_productivity([src], utts_1pct, min_ratio=0.80)
    assert res_1pct.passed is False
    assert res_1pct.status == "FAIL"
    assert "falls below minimum ratio 80.0%" in res_1pct.message
    assert "1.0%" in res_1pct.message

    # Case 2: 95% coverage (5,700,000 ms span out of 6,000,000 ms) -> PASS
    utts_95pct = [
        Utterance(
            utterance_id="u1",
            source_id="src_unit_test",
            subject_id="s1",
            text_verbatim="Full episode start.",
            start_ms=50_000,
            end_ms=100_000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="test",
        ),
        Utterance(
            utterance_id="u2",
            source_id="src_unit_test",
            subject_id="s1",
            text_verbatim="Full episode end.",
            start_ms=5_700_000,
            end_ms=5_750_000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="test",
        ),
    ]
    res_95pct = verify_source_productivity([src], utts_95pct, min_ratio=0.80)
    assert res_95pct.passed is True
    assert res_95pct.status == "PASS"
    assert "coverage >= 80.0%" in res_95pct.message


def test_verify_source_productivity_fails_on_missing_duration() -> None:
    """Sources with missing or zero duration_ms must fail verify_source_productivity."""
    src = Source(
        source_id="src_nodur",
        title="No Duration Source",
        publisher="Test",
        canonical_url="https://example.com/nodur.mp3",
        artifact_hash="hash123",
        duration_ms=0,
        ingested_at="2026-09-04T12:00:00Z",
    )
    utts = [
        Utterance(
            utterance_id="u1",
            source_id="src_nodur",
            subject_id="s1",
            text_verbatim="Some speech.",
            start_ms=0,
            end_ms=10_000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="test",
        )
    ]
    res = verify_source_productivity([src], utts, min_ratio=0.80)
    assert res.passed is False
    assert res.status == "FAIL"
    assert "missing or zero duration_ms" in res.message


def test_ingest_refuses_to_persist_source_without_duration(tmp_path: Path) -> None:
    """Ingestion engine refuses to persist a source without positive duration_ms."""
    store = Storage(str(tmp_path / "test.duckdb"))
    engine = IngestionEngine(storage=store)
    adapter = PodcastRSSAdapter(cache_dir=tmp_path / "cache")
    subject = Subject(subject_id="s1", display_name="Speaker One")

    # SourceRef without duration_ms in extra
    ref = SourceRef(
        locator="https://example.com/no_duration.mp3",
        tier="B",
        title="Missing Duration Episode",
    )
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"RIFFdummydataWAVEfmt ")

    # Single-speaker ingest must raise ValueError
    with pytest.raises(ValueError, match="missing or invalid duration_ms"):
        engine.ingest_single_speaker_source(
            adapter=adapter,
            ref=ref,
            subject=subject,
            media_file_override=audio_file,
        )

    # Panel ingest must also raise ValueError
    with pytest.raises(ValueError, match="missing or invalid duration_ms"):
        engine.ingest_panel_source(
            adapter=adapter,
            ref=ref,
            subjects=[subject],
            media_file_override=audio_file,
        )


def test_falsification_zero_min_ratio_passes_truncated_corpus() -> None:
    """FALSIFICATION (LOOP 2):

    When min_ratio = 0.0, a truncated source (e.g. 7.7% coverage) passes the check,
    proving that the threshold floor does the work.
    """
    src = Source(
        source_id="src_trunc",
        title="Truncated Source",
        publisher="Test",
        canonical_url="https://example.com/trunc.mp3",
        artifact_hash="hash123",
        duration_ms=5_400_000,  # 90 minutes
        ingested_at="2026-09-04T12:00:00Z",
    )
    # Utterance covering only first 416 seconds (~7.7%)
    utts = [
        Utterance(
            utterance_id="u1",
            source_id="src_trunc",
            subject_id="s1",
            text_verbatim="Truncated start.",
            start_ms=0,
            end_ms=416_000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="test",
        )
    ]
    # Under standard threshold (0.80), this fails
    res_standard = verify_source_productivity([src], utts, min_ratio=0.80)
    assert res_standard.passed is False
    assert "7.7%" in res_standard.message

    # Under falsified threshold (0.0), this passes
    res_falsified = verify_source_productivity([src], utts, min_ratio=0.0)
    assert res_falsified.passed is True
    assert res_falsified.status == "PASS"


def test_live_corpus_coverage_and_date_invariants() -> None:
    """Verifies §19 validation requirements over the live corpus database:

    1. duration_ms is non-null and > 0 on all sources.
    2. published_at is an episode date between 2023 and 2026.
    3. published_at is not within 1 minute of ingested_at.
    4. verify_source_productivity passes with coverage >= 80% on all sources.
    """
    db_path = Path("social_proof.duckdb")
    if not db_path.exists():
        pytest.skip("social_proof.duckdb does not exist")

    store = Storage(str(db_path))
    sources = [
        s
        for r in store.con.execute("SELECT source_id FROM sources").fetchall()
        if (s := store.get_source(r[0])) is not None
    ]
    assert len(sources) >= 4, f"Expected at least 4 sources, found {len(sources)}"

    for s in sources:
        assert s.duration_ms > 0, f"Source {s.source_id} has duration_ms={s.duration_ms}"
        assert s.published_at is not None, f"Source {s.source_id} has published_at=None"
        assert s.ingested_at is not None, f"Source {s.source_id} has ingested_at=None"

        dt_pub = datetime.fromisoformat(s.published_at)
        dt_ing = datetime.fromisoformat(s.ingested_at)
        assert 2023 <= dt_pub.year <= 2026, f"Source {s.source_id} year {dt_pub.year} not in 2023-2026"

        diff_sec = abs((dt_ing - dt_pub).total_seconds())
        assert diff_sec > 60, (
            f"Source {s.source_id} published_at '{s.published_at}' within 1 min of "
            f"ingested_at '{s.ingested_at}' (diff={diff_sec}s)"
        )

    utterances = [
        u
        for r in store.con.execute("SELECT utterance_id FROM utterances").fetchall()
        if (u := store.get_utterance(r[0])) is not None
    ]
    res = verify_source_productivity(sources, utterances, min_ratio=MIN_UTTERANCE_MEDIA_RATIO)
    assert res.passed is True
    assert res.status == "PASS"

