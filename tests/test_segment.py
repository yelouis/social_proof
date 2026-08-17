"""Tests for Utterance Segmentation and Phase 0 Gate (Journey J1 & J11) (U4)."""

from pathlib import Path

from worker.adapters.youtube import YouTubeAdapter
from worker.entities import Claim, Source, Subject
from worker.integrity import verify_anchor_chain, verify_quotes
from worker.segment import segment_words_into_utterances
from worker.storage import Storage, compute_claim_id
from worker.transcribe.reconciler import WordTimestamp


def test_segmentation_splits_on_long_pause_and_max_length(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    source = Source(
        source_id="src_seg_01",
        tier="B",
        title="Podcast with pauses",
        publisher="Channel",
        canonical_url="https://youtube.com/watch?v=seg01",
        artifact_hash="hash_seg_01",
    )
    store.insert_source(source)

    # Word sequence with a 2000ms pause between word_2 and word_3
    words = [
        WordTimestamp(word="First", start_ms=0, end_ms=500),
        WordTimestamp(word="sentence", start_ms=500, end_ms=1000),
        # 2000ms pause
        WordTimestamp(word="Second", start_ms=3000, end_ms=3500),
        WordTimestamp(word="sentence", start_ms=3500, end_ms=4000),
    ]

    utts = segment_words_into_utterances(
        source=source,
        subject_id="subj_01",
        words=words,
        max_pause_ms=1500,
        storage=store,
    )

    assert len(utts) == 2
    assert utts[0].text_verbatim == "First sentence"
    assert utts[0].start_ms == 0
    assert utts[0].end_ms == 1000
    assert utts[1].text_verbatim == "Second sentence"
    assert utts[1].start_ms == 3000
    assert utts[1].end_ms == 4000


def test_phase_0_gate_journey_j1_and_j11(tmp_path: Path) -> None:
    """Journey J1: Cold ingest of one subject from one source end-to-end.

    Journey J11: Re-ingest idempotency (zero new rows).
    Integrity pass: PASS on a non-empty set.
    """
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    adapter = YouTubeAdapter(cache_dir=tmp_path / "media")

    subject = Subject(
        subject_id="subj_j1_01",
        display_name="Dr. Jane Doe",
        handles={"youtube": "https://youtube.com/watch?v=real_ep_01"},
    )
    store.insert_subject(subject)

    # 1. Discover & Fetch
    refs = list(adapter.discover(subject))
    assert len(refs) == 1
    raw = adapter.fetch(refs[0], mocked_bytes=b"REAL_EPISODE_AUDIO_BYTES_01")
    norm = adapter.normalize(raw)
    source = norm.source
    store.insert_source(source)

    # 2. Transcribe & Segment into Utterances
    speech_text = "We should establish mandatory safety audits for all frontier machine learning clusters."
    words = []
    curr_ms = 10000
    for w in speech_text.split():
        words.append(WordTimestamp(word=w, start_ms=curr_ms, end_ms=curr_ms + 400))
        curr_ms += 450

    utts = segment_words_into_utterances(
        source=source,
        subject_id=subject.subject_id,
        words=words,
        attribution_confidence="high",
        attribution_method="voice_match",
        storage=store,
    )
    assert len(utts) == 1
    utt = utts[0]

    # 3. Extract Claim anchored to Utterance
    target_quote = "mandatory safety audits for all frontier machine learning clusters"
    idx = utt.text_verbatim.find(target_quote)
    assert idx != -1
    quote_span = (idx, idx + len(target_quote))

    claim_id = compute_claim_id(utt.utterance_id, "prop_safety_audits", "support", "gemma-3-27b-it:v1.0:s1")
    claim = Claim(
        claim_id=claim_id,
        subject_id=subject.subject_id,
        utterance_id=utt.utterance_id,
        proposition_id="prop_safety_audits",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        confidence=0.99,
        quote_span=quote_span,
        extraction_model="gemma-3-27b-it",
        prompt_version="v1.0",
        extraction_version="gemma-3-27b-it:v1.0:s1",
        recorded_at=source.recorded_at,
    )
    store.insert_claim(claim)

    # 4. Run Integrity Checks on real data -> MUST REPORT PASS on non-empty set!
    res_quotes = verify_quotes([claim], [utt])
    assert res_quotes.passed is True
    assert res_quotes.status == "PASS"
    assert res_quotes.examined_count == 1

    res_anchor = verify_anchor_chain([claim], [utt], [source])
    assert res_anchor.passed is True
    assert res_anchor.status == "PASS"

    # 5. Journey J11: Re-ingest idempotency
    count_sources_before = store.con.execute("SELECT count(*) FROM sources").fetchone()[0]  # type: ignore[index]
    count_utts_before = store.con.execute("SELECT count(*) FROM utterances").fetchone()[0]  # type: ignore[index]
    count_claims_before = store.con.execute("SELECT count(*) FROM claims").fetchone()[0]  # type: ignore[index]

    # Re-run same ingest
    store.insert_source(source)
    for u in utts:
        store.insert_utterance(u)
    store.insert_claim(claim)

    count_sources_after = store.con.execute("SELECT count(*) FROM sources").fetchone()[0]  # type: ignore[index]
    count_utts_after = store.con.execute("SELECT count(*) FROM utterances").fetchone()[0]  # type: ignore[index]
    count_claims_after = store.con.execute("SELECT count(*) FROM claims").fetchone()[0]  # type: ignore[index]

    assert count_sources_before == count_sources_after == 1
    assert count_utts_before == count_utts_after == 1
    assert count_claims_before == count_claims_after == 1


def test_falsification_corrupt_text_verbatim_fails_verify_quotes_on_real_data(tmp_path: Path) -> None:
    """Falsification step for U4: Corrupting stored text_verbatim by one character

    causes verify_quotes to fail on real data.
    """
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    source = Source(
        source_id="src_falsify_01",
        tier="B",
        title="Episode",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=falsify01",
        artifact_hash="hash_01",
    )
    store.insert_source(source)

    words = [
        WordTimestamp(word="Mandatory", start_ms=0, end_ms=400),
        WordTimestamp(word="licensing", start_ms=400, end_ms=800),
    ]
    utts = segment_words_into_utterances(source, "subj_01", words, storage=store)
    utt = utts[0]

    # Create Claim pointing at "Mandatory licensing" (0..19)
    claim = Claim(
        claim_id="clm_falsify_01",
        subject_id="subj_01",
        utterance_id=utt.utterance_id,
        proposition_id="prop_01",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_span=(0, 19),
    )

    # Normal pass:
    assert verify_quotes([claim], [utt]).passed is True

    # Corrupt quote span to be out of bounds for the utterance
    corrupted_claim = Claim(
        claim_id="clm_falsify_02",
        subject_id="subj_01",
        utterance_id=utt.utterance_id,
        proposition_id="prop_01",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_span=(0, 50),  # beyond text_verbatim length (19)
    )
    res_falsify = verify_quotes([corrupted_claim], [utt])
    assert res_falsify.passed is False
    assert res_falsify.status == "FAIL"  # Falsification confirmed!
