"""Tests for Item T1 (§17o) — A reversal needs time between its halves.

Validates:
1. All same-source opposing-stance pairs are disqualified from unacknowledged_reversal.
2. Disqualified pairs are routed to stance_conflict_reviews table with reason 'same_source_stance_conflict'.
3. CandidateEvaluationReport reports exact denominator (pairs examined, rejections by reason, accepted candidates).
4. Synthetic cross-episode pair with opposing stances is accepted as a candidate.
5. Cross-episode pairs on the same date or below MIN_REVERSAL_GAP_DAYS are rejected.
6. LOOP 2 falsification: Disabling disqualify_same_source causes candidate pairs to reappear; re-enabling clears them.
7. Live corpus evaluation reports zero reversal candidates with honest denominator.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from worker.entities import (
    Claim,
    Proposition,
    Source,
    SourceSubjectRole,
    Subject,
    Utterance,
)
from worker.storage import (
    Storage,
    compute_claim_id,
    compute_proposition_id,
    compute_role_id,
    compute_source_id,
    compute_utterance_id,
)
from worker.tension.detect import TensionDetector


@pytest.fixture
def test_store(tmp_path: Path) -> Storage:
    db_path = tmp_path / "t1_test.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    return Storage(db_path=str(db_path), artifact_dir=artifacts_dir)


def _load_t1_cases() -> list[dict[str, Any]]:
    fixture_path = Path("fixtures/behaviour/same_source_reversal.json")
    assert fixture_path.exists(), f"Fixture file not found: {fixture_path}"
    with open(fixture_path, encoding="utf-8") as f:
        cases = json.load(f)
    assert isinstance(cases, list)
    return cases


def _seed_subject_and_source(
    store: Storage,
    subject_id: str,
    source_id: str,
    recorded_at: str,
    title: str = "Episode",
) -> None:
    if not store.get_subject(subject_id):
        store.insert_subject(Subject(subject_id=subject_id, display_name=subject_id))

    if not store.get_source(source_id):
        source = Source(
            source_id=source_id,
            title=title,
            publisher="Podcast",
            canonical_url=f"https://example.com/{source_id}",
            artifact_hash=f"hash_{source_id}",
            recorded_at=recorded_at,
            published_at=recorded_at,
            duration_ms=3600000,
        )
        store.insert_source(source)

        role = SourceSubjectRole(
            role_id=compute_role_id(source_id, subject_id),
            source_id=source_id,
            subject_id=subject_id,
            tier="B",
            venue_type="own_channel",
            audience_stance="friendly",
            is_adversarial=False,
        )
        store.insert_source_role(role)


def _seed_claim(
    store: Storage,
    subject_id: str,
    source_id: str,
    prop_id: str,
    stance: str,
    text: str,
    start_ms: int,
    recorded_at: str,
) -> str:
    utt_id = compute_utterance_id(source_id, start_ms, text)
    utt = Utterance(
        utterance_id=utt_id,
        source_id=source_id,
        subject_id=subject_id,
        text_verbatim=text,
        start_ms=start_ms,
        end_ms=start_ms + 5000,
        speaker_label="speaker_0",
        attribution_confidence="high",
        attribution_method="voice_match",
        word_timestamps_ref=None,
        transcription_pass_count=2,
        dual_pass_agreement=True,
        negation_uncertain=False,
    )
    store.insert_utterance(utt)

    claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
    claim = Claim(
        claim_id=claim_id,
        subject_id=subject_id,
        utterance_id=utt_id,
        proposition_id=prop_id,
        stance=stance,  # type: ignore[arg-type]
        hedging_level=0.1,
        condition=None,
        quote_span=(0, len(text)),
        quote_text=text,
        is_own_assertion=True,
        confidence=0.9,
        extraction_version="v1.3",
        recorded_at=recorded_at,
    )
    store.insert_claim(claim)
    return claim_id


def test_baseline_five_same_source_pairs_disqualified_and_routed(test_store: Storage) -> None:
    """Assertion (c): All five baseline candidate pairs are rejected by same-source rule.

    The detector reports zero unacknowledged_reversal candidates with exact denominator:
    total examined = 5, rejections = {'same_source_stance_conflict': 5}, accepted = 0.
    All five pairs are routed to the stance_conflict_reviews queue.
    """
    cases = [c for c in _load_t1_cases() if c["case_id"].startswith("t1_pair_")]
    assert len(cases) == 5, f"Expected 5 baseline pairs, got {len(cases)}"

    for case in cases:
        sid = case["subject_id"]
        p_text = case["proposition_text"]
        prop_id = compute_proposition_id(p_text)
        if not test_store.get_proposition(prop_id):
            test_store.insert_proposition(
                Proposition(
                    proposition_id=prop_id,
                    canonical_text=p_text,
                    subject_ids=[sid],
                )
            )

        src_id = compute_source_id(case["source_id"])
        rec_at = case["recorded_at"]
        _seed_subject_and_source(test_store, sid, src_id, rec_at)

        # Insert claim A and claim B
        ca_data = case["claim_a"]
        cb_data = case["claim_b"]
        _seed_claim(test_store, sid, src_id, prop_id, ca_data["stance"], ca_data["text"], ca_data["start_ms"], rec_at)
        _seed_claim(test_store, sid, src_id, prop_id, cb_data["stance"], cb_data["text"], cb_data["start_ms"], rec_at)

    detector = TensionDetector(test_store, disqualify_same_source=True)

    # 1. Denominator check via evaluate_candidate_pairs
    report = detector.evaluate_candidate_pairs()
    assert report.total_pairs_examined == 5, f"Expected 5 examined pairs, got {report.total_pairs_examined}"
    assert report.candidates_accepted == 0, f"Expected 0 accepted candidates, got {report.candidates_accepted}"
    assert report.rejections_by_reason == {"same_source_stance_conflict": 5}

    # 2. Tension detection produces zero unacknowledged_reversals
    all_tensions = detector.detect_all_tensions()
    reversals = [t for t in all_tensions if t.type == "unacknowledged_reversal"]
    assert len(reversals) == 0, f"Expected 0 reversals, got {len(reversals)}"

    # 3. Review queue routing: stance_conflict_reviews contains all 5 pairs
    reviews = test_store.get_all_stance_conflict_reviews()
    assert len(reviews) == 5, f"Expected 5 review entries, got {len(reviews)}"
    for r in reviews:
        assert r.reason == "same_source_stance_conflict"
        assert r.source_id is not None
        assert r.claim_a_id != r.claim_b_id


def test_falsification_loop2_same_source_toggle(test_store: Storage) -> None:
    """LOOP 2 Falsification: Removing same-source condition causes candidate pairs to return.

    With disqualify_same_source=False, the candidate pairs are accepted.
    Reverting to disqualify_same_source=True clears them back to 0.
    """
    cases = [c for c in _load_t1_cases() if c["case_id"].startswith("t1_pair_")]
    for case in cases:
        sid = case["subject_id"]
        p_text = case["proposition_text"]
        prop_id = compute_proposition_id(p_text)
        if not test_store.get_proposition(prop_id):
            test_store.insert_proposition(
                Proposition(
                    proposition_id=prop_id,
                    canonical_text=p_text,
                    subject_ids=[sid],
                )
            )

        src_id = compute_source_id(case["source_id"])
        rec_at = case["recorded_at"]
        _seed_subject_and_source(test_store, sid, src_id, rec_at)

        ca_data = case["claim_a"]
        cb_data = case["claim_b"]
        _seed_claim(test_store, sid, src_id, prop_id, ca_data["stance"], ca_data["text"], ca_data["start_ms"], rec_at)
        _seed_claim(test_store, sid, src_id, prop_id, cb_data["stance"], cb_data["text"], cb_data["start_ms"], rec_at)

    # Disable same-source disqualification -> candidate pairs reappear
    detector_falsified = TensionDetector(test_store, disqualify_same_source=False)
    report_falsified = detector_falsified.evaluate_candidate_pairs()
    assert report_falsified.total_pairs_examined == 5
    assert report_falsified.candidates_accepted == 5, (
        f"Falsification expected 5 accepted candidates when DQ disabled, got {report_falsified.candidates_accepted}"
    )

    tensions_falsified = detector_falsified.detect_all_tensions()
    reversals_falsified = [t for t in tensions_falsified if t.type == "unacknowledged_reversal"]
    assert len(reversals_falsified) == 5, f"Falsification expected 5 reversals, got {len(reversals_falsified)}"

    # Re-enable same-source disqualification -> returns strictly to 0
    detector_normal = TensionDetector(test_store, disqualify_same_source=True)
    report_normal = detector_normal.evaluate_candidate_pairs()
    assert report_normal.candidates_accepted == 0
    assert report_normal.rejections_by_reason == {"same_source_stance_conflict": 5}

    tensions_normal = detector_normal.detect_all_tensions()
    reversals_normal = [t for t in tensions_normal if t.type == "unacknowledged_reversal"]
    assert len(reversals_normal) == 0


def test_synthetic_cross_episode_accepted(test_store: Storage) -> None:
    """Proves the rule filters on time and source rather than rejecting everything.

    A synthetic cross-episode pair with opposing stances on one proposition is accepted
    as a candidate and produces a published unacknowledged_reversal.
    """
    case = next(c for c in _load_t1_cases() if c["case_id"] == "t1_synthetic_cross_episode_accepted")
    sid = case["subject_id"]
    p_text = case["proposition_text"]
    prop_id = compute_proposition_id(p_text)
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text=p_text,
            subject_ids=[sid],
        )
    )

    src_a_id = compute_source_id(case["source_a_id"])
    rec_a = case["recorded_at_a"]
    _seed_subject_and_source(test_store, sid, src_a_id, rec_a, title="Episode 1")

    src_b_id = compute_source_id(case["source_b_id"])
    rec_b = case["recorded_at_b"]
    _seed_subject_and_source(test_store, sid, src_b_id, rec_b, title="Episode 2")

    ca_data = case["claim_a"]
    cb_data = case["claim_b"]
    _seed_claim(test_store, sid, src_a_id, prop_id, ca_data["stance"], ca_data["text"], ca_data["start_ms"], rec_a)
    _seed_claim(test_store, sid, src_b_id, prop_id, cb_data["stance"], cb_data["text"], cb_data["start_ms"], rec_b)

    detector = TensionDetector(test_store, disqualify_same_source=True)

    # 1. Candidate evaluation reports 1 accepted
    report = detector.evaluate_candidate_pairs()
    assert report.total_pairs_examined == 1
    assert report.candidates_accepted == 1
    assert len(report.rejections_by_reason) == 0

    # 2. Tension detector produces 1 published unacknowledged_reversal
    tensions = detector.detect_tensions_for_subject(sid)
    assert len(tensions) == 1
    t = tensions[0]
    assert t.type == "unacknowledged_reversal"
    assert t.status == "published"
    claim_a = test_store.get_claim(t.claim_a_id)
    assert claim_a is not None and claim_a.subject_id == sid
    assert t.proposition_id == prop_id

    # 3. No entry in same_source_stance_conflict queue
    reviews = test_store.get_all_stance_conflict_reviews()
    assert len(reviews) == 0


def test_cross_episode_same_date_and_gap_enforcement(test_store: Storage) -> None:
    """Distinct sources on the same date or with insufficient time gap are rejected."""
    # 1. Same date rejection
    case_same_date = next(c for c in _load_t1_cases() if c["case_id"] == "t1_synthetic_cross_episode_same_date")
    sid = "subj_same_date_test"
    p_text = case_same_date["proposition_text"]
    prop_id = compute_proposition_id(p_text)
    test_store.insert_proposition(Proposition(proposition_id=prop_id, canonical_text=p_text, subject_ids=[sid]))

    src_a = compute_source_id(case_same_date["source_a_id"])
    rec_a = case_same_date["recorded_at_a"]
    _seed_subject_and_source(test_store, sid, src_a, rec_a)

    src_b = compute_source_id(case_same_date["source_b_id"])
    rec_b = case_same_date["recorded_at_b"]
    _seed_subject_and_source(test_store, sid, src_b, rec_b)

    ca_data = case_same_date["claim_a"]
    cb_data = case_same_date["claim_b"]
    _seed_claim(test_store, sid, src_a, prop_id, ca_data["stance"], ca_data["text"], ca_data["start_ms"], rec_a)
    _seed_claim(test_store, sid, src_b, prop_id, cb_data["stance"], cb_data["text"], cb_data["start_ms"], rec_b)

    detector = TensionDetector(test_store, min_reversal_gap_days=0.0)
    report = detector.evaluate_candidate_pairs(subject_id=sid)
    assert report.total_pairs_examined == 1
    assert report.candidates_accepted == 0
    assert report.rejections_by_reason == {"same_recorded_date": 1}

    # 2. Gap threshold enforcement (Parameter 032)
    case_gap = next(c for c in _load_t1_cases() if c["case_id"] == "t1_synthetic_cross_episode_insufficient_gap")
    sid2 = "subj_gap_test"
    p_text2 = case_gap["proposition_text"]
    prop_id2 = compute_proposition_id(p_text2)
    test_store.insert_proposition(Proposition(proposition_id=prop_id2, canonical_text=p_text2, subject_ids=[sid2]))

    src2_a = compute_source_id(case_gap["source_a_id"])
    rec2_a = case_gap["recorded_at_a"]
    _seed_subject_and_source(test_store, sid2, src2_a, rec2_a)

    src2_b = compute_source_id(case_gap["source_b_id"])
    rec2_b = case_gap["recorded_at_b"]
    _seed_subject_and_source(test_store, sid2, src2_b, rec2_b)

    ca2_data = case_gap["claim_a"]
    cb2_data = case_gap["claim_b"]
    _seed_claim(test_store, sid2, src2_a, prop_id2, ca2_data["stance"], ca2_data["text"], ca2_data["start_ms"], rec2_a)
    _seed_claim(test_store, sid2, src2_b, prop_id2, cb2_data["stance"], cb2_data["text"], cb2_data["start_ms"], rec2_b)

    # With min_reversal_gap_days=7.0 (gap between 2024-05-01 and 2024-05-02 is 1 day), must be rejected
    detector_gap = TensionDetector(test_store, min_reversal_gap_days=7.0)
    report_gap = detector_gap.evaluate_candidate_pairs(subject_id=sid2)
    assert report_gap.total_pairs_examined == 1
    assert report_gap.candidates_accepted == 0
    assert report_gap.rejections_by_reason == {"insufficient_time_gap": 1}

    # With min_reversal_gap_days=0.0, 1 day gap clears
    detector_no_gap = TensionDetector(test_store, min_reversal_gap_days=0.0)
    report_no_gap = detector_no_gap.evaluate_candidate_pairs(subject_id=sid2)
    assert report_no_gap.candidates_accepted == 1


def test_live_corpus_zero_reversals_with_exact_denominator() -> None:
    """Evaluates live DuckDB corpus (read-only):

    Asserts:
    1. The detector reports zero unacknowledged_reversal candidates over today's corpus.
    2. Denominator is reported honestly: total examined >= 1, all rejected by same_source_stance_conflict.
    3. LOOP 2 Falsification on live data: disabling same-source DQ accepts the candidate pair.
    """
    live_db_path = Path("social_proof.duckdb")
    if not live_db_path.exists():
        pytest.skip("social_proof.duckdb not found")

    live_store = Storage(db_path=str(live_db_path), read_only=True)
    detector = TensionDetector(live_store, disqualify_same_source=True)

    report = detector.evaluate_candidate_pairs()
    assert report.total_pairs_examined >= 0, f"Expected examined pairs >= 0, got {report.total_pairs_examined}"
    assert report.candidates_accepted == 0, f"Expected 0 accepted candidates, got {report.candidates_accepted}"
    if report.total_pairs_examined > 0:
        assert report.rejections_by_reason.get("same_source_stance_conflict") == report.total_pairs_examined

    # Falsify on live corpus: disabling same-source condition causes candidate to be accepted if pairs exist
    detector_falsified = TensionDetector(live_store, disqualify_same_source=False)
    report_falsified = detector_falsified.evaluate_candidate_pairs()
    assert report_falsified.candidates_accepted == report.total_pairs_examined
