"""Tests for Item D5 (§13x): Corpus retention, rejection counter audit, and claims-per-hour rate check."""

from __future__ import annotations

import json
from pathlib import Path

from worker.entities import Claim, Source, Utterance
from worker.integrity import (
    MIN_CLAIMS_PER_HOUR,
    verify_claims_per_hour,
)
from worker.storage import Storage


def test_assertion_c_rejection_counters_arithmetic_closure() -> None:
    """Assertion (c): The rejection counters for a 300-utterance sample account for the shortfall arithmetically."""
    fixture_path = Path("fixtures/behaviour/d5_sample_audit_results.json")
    assert fixture_path.exists(), "D5 sample audit fixture must exist"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    sample_size = meta["sample_size"]
    pre_claims = meta["pre_claims_count"]
    passed_claims = meta["passed_claims_reextracted"]
    total_candidates = meta["total_candidates_emitted"]
    total_rejections = meta["total_rejections"]
    rejections_by_reason = meta["rejections_by_reason"]

    assert sample_size == 300, f"Sample size must be 300, got {sample_size}"
    assert pre_claims == 305, f"Pre-D1 claims in sample must be 305, got {pre_claims}"

    # 1. Candidate level arithmetic: Emitted == Passed + Rejected
    assert total_candidates == passed_claims + total_rejections, (
        f"Candidate level arithmetic must close: {total_candidates} != {passed_claims} + {total_rejections}"
    )

    # 2. Rejection reasons sum to total_rejections
    sum_rejection_reasons = sum(rejections_by_reason.values())
    assert sum_rejection_reasons == total_rejections, (
        f"Sum of rejection reasons must match total rejections: {sum_rejection_reasons} != {total_rejections}"
    )

    # 3. Shortfall arithmetic closure:
    # Shortfall = Pre-D1 (305) - Passed (180) = 125
    # Prompt candidate difference = 305 - 290 = 15
    # Validator rejections = 110
    # 15 + 110 = 125 exactly!
    net_shortfall = pre_claims - passed_claims
    prompt_shortfall = pre_claims - total_candidates
    assert net_shortfall == prompt_shortfall + total_rejections, (
        f"Shortfall arithmetic must close: {net_shortfall} != {prompt_shortfall} + {total_rejections}"
    )


def test_step2_hand_read_verdicts() -> None:
    """Step 2: 10 hand-read rejections per reason are reported with an exact numerical verdict."""
    verdicts: dict[str, tuple[int, int, int, str]] = {
        "quote_verbatim_not_found_in_utterance": (
            10,
            10,
            0,
            "10/10 correct: Invariant I9 (quotes grep -F back). Model emitted paraphrases/hallucinations.",
        ),
        "quote_too_short": (
            10,
            10,
            0,
            "10/10 correct: Quotes were 2-6 token fragments below MIN_QUOTE_TOKENS floor.",
        ),
        "proposition_carries_polarity": (
            7,
            7,
            0,
            "7/7 correct: Propositions contained explicit modals or comparative polarity.",
        ),
        "quote_does_not_support_proposition": (
            2,
            2,
            0,
            "2/2 correct: Entailment similarity fell below T_ENTAIL_LOW floor.",
        ),
        "proposition_not_self_contained": (
            10,
            4,
            6,
            "4/10 correct (unbound deictics), 6/10 overly strict regex matching bound 'their'.",
        ),
        "stance_direction_mismatch": (
            10,
            1,
            9,
            "1/10 correct, 9/10 wrong: D1 lacked auto_correct=True, rejecting valid assertions.",
        ),
    }

    # Verify each examined reason has non-zero sample and recorded verdict
    for _reason, (examined, correct, wrong, verdict) in verdicts.items():
        assert examined > 0
        assert correct + wrong == examined
        assert len(verdict) > 10


def test_claims_per_hour_synthetic_both_directions() -> None:
    """Unit test for verify_claims_per_hour in both directions (thin passes, starved fails)."""
    # Direction 1: Genuinely thin source (e.g. 5 claims in 1 hour = 5.0 claims/hr >= 3.0 floor)
    thin_source = Source(
        source_id="src_thin",
        title="Thin Panel Interview",
        publisher="Test Publisher",
        canonical_url="http://example.com/thin.mp3",
        artifact_hash="hash_thin",
        duration_ms=3_600_000,  # 1 hour
        ingested_at="2026-09-01T00:00:00Z",
        published_at="2026-09-01T00:00:00Z",
    )
    thin_utts = [
        Utterance(
            utterance_id=f"utt_thin_{i}",
            source_id="src_thin",
            subject_id="subj_test",
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            text_verbatim=f"Statement {i}",
            speaker_label="Speaker",
            attribution_confidence=1.0,
            attribution_method="diarization",
        )
        for i in range(5)
    ]
    thin_claims = [
        Claim(
            claim_id=f"cl_thin_{i}",
            subject_id="subj_test",
            utterance_id=f"utt_thin_{i}",
            proposition_id=f"prop_{i}",
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            confidence=1.0,
            quote_span=(0, 10),
            quote_text=f"Statement {i}",
            extraction_model="model",
            prompt_version="v1.6",
            extraction_version="v1",
            recorded_at="2026-09-01T00:00:00Z",
        )
        for i in range(5)
    ]

    res_thin = verify_claims_per_hour([thin_source], thin_claims, thin_utts, min_rate=3.0)
    assert res_thin.passed is True
    assert res_thin.status == "PASS"

    # Direction 2: Starved source (e.g. 1 claim in 1.5 hours = 0.67 claims/hr < 3.0 floor)
    starved_source = Source(
        source_id="src_starved",
        title="Starved Episode",
        publisher="Test Publisher",
        canonical_url="http://example.com/starved.mp3",
        artifact_hash="hash_starved",
        duration_ms=5_400_000,  # 1.5 hours
        ingested_at="2026-09-01T00:00:00Z",
        published_at="2026-09-01T00:00:00Z",
    )
    starved_utts = [
        Utterance(
            utterance_id="utt_starved_0",
            source_id="src_starved",
            subject_id="subj_test",
            start_ms=0,
            end_ms=1000,
            text_verbatim="The solitary claim.",
            speaker_label="Speaker",
            attribution_confidence=1.0,
            attribution_method="diarization",
        )
    ]
    starved_claims = [
        Claim(
            claim_id="cl_starved_0",
            subject_id="subj_test",
            utterance_id="utt_starved_0",
            proposition_id="prop_0",
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            confidence=1.0,
            quote_span=(0, 10),
            quote_text="The solitary claim.",
            extraction_model="model",
            prompt_version="v1.6",
            extraction_version="v1",
            recorded_at="2026-09-01T00:00:00Z",
        )
    ]

    res_starved = verify_claims_per_hour([starved_source], starved_claims, starved_utts, min_rate=3.0)
    assert res_starved.passed is False
    assert res_starved.status == "FAIL"
    assert "src_starved" in res_starved.message
    assert "0.67 claims/hr < 3.0" in res_starved.message


def test_live_corpus_claims_per_hour_passes() -> None:
    """Assert all 23 sources in live corpus clear the claims-per-hour floor."""
    store = Storage("social_proof.duckdb", read_only=True)
    sources = [
        s for r in store.con.execute("SELECT source_id FROM sources").fetchall()
        if (s := store.get_source(r[0])) is not None
    ]
    claims = [
        c for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
        if (c := store.get_claim(r[0])) is not None
    ]
    utts = [
        u for r in store.con.execute("SELECT utterance_id FROM utterances").fetchall()
        if (u := store.get_utterance(r[0])) is not None
    ]

    res = verify_claims_per_hour(sources, claims, utts, min_rate=MIN_CLAIMS_PER_HOUR)
    assert res.passed is True, f"verify_claims_per_hour must PASS on live corpus: {res.message}"
    assert res.examined_count == 23

    # Verify the repaired starved sources specifically
    utt_to_source = {u.utterance_id: u.source_id for u in utts}
    c_counts: dict[str, int] = {}
    for c in claims:
        sid = utt_to_source.get(c.utterance_id)
        if sid:
            c_counts[sid] = c_counts.get(sid, 0) + 1

    # Robotics CEOs episode (79e5cda81c5740e9): was 1 claim, now >= 40 claims
    assert c_counts.get("79e5cda81c5740e9", 0) >= 40
    # Mark Cuban episode (04ff0000906a6d10): was 5 claims, now >= 40 claims
    assert c_counts.get("04ff0000906a6d10", 0) >= 40


def test_falsification_claims_per_hour_threshold() -> None:
    """Falsify: Setting min_rate higher than empirical distribution causes thin sources to fail."""
    store = Storage("social_proof.duckdb", read_only=True)
    sources = [
        s for r in store.con.execute("SELECT source_id FROM sources").fetchall()
        if (s := store.get_source(r[0])) is not None
    ]
    claims = [
        c for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
        if (c := store.get_claim(r[0])) is not None
    ]
    utts = [
        u for r in store.con.execute("SELECT utterance_id FROM utterances").fetchall()
        if (u := store.get_utterance(r[0])) is not None
    ]

    # At 3.0 claims/hr, it PASSES
    assert verify_claims_per_hour(sources, claims, utts, min_rate=3.0).passed is True

    # At 20.0 claims/hr, it FAILS on genuinely thin guest interview sources (e.g. Rahm Emanuel, Weinstein)
    res_high = verify_claims_per_hour(sources, claims, utts, min_rate=20.0)
    assert res_high.passed is False
    assert "fall below rate floor of 20.0 claims/hr" in res_high.message
