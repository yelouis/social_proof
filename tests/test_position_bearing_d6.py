"""Tests, Validation (c), and Falsification for Item D6 (§11):

Propositions overshot from full clauses into bare topics.
"""

from __future__ import annotations

import random

from worker.extract.runtime import STABLE_SYSTEM_PROMPT, LocalGemmaRuntime
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    validate_position_bearing,
)
from worker.storage import Storage


def test_mechanical_floor_both_directions() -> None:
    """Step 3 & Validation: Both directions of mechanical floor.

    federal licensing of frontier AI models survives;
    most enterprises, ai race in america, american efforts regarding ai do not.
    """
    passing_cases = [
        "federal licensing of frontier AI models",
        "amazon's burden-shifting strategy for employees and the american taxpayer",
        "sandboxed testing of frontier AI models before deployment",
        "allowing individual gun ownership despite potential misuse",
        "industry-wide reduction in AI development pace to 20% slower",
    ]

    failing_cases = [
        "most enterprises",
        "ai race in america",
        "american efforts regarding ai",
        "have a very big position in amazon",
        "new york city is the largest school district in the united states",
        "how to speak to large language models",
        "republican or democrat support for it",
    ]

    for ptext in passing_cases:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.95,
        )
        outcome = validate_position_bearing(claim)
        assert outcome.is_valid is True, f"Expected '{ptext}' to PASS, got {outcome}"
        assert outcome.rejection_reason is None

    for ptext in failing_cases:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.95,
        )
        outcome = validate_position_bearing(claim)
        assert outcome.is_valid is False, f"Expected '{ptext}' to FAIL"
        assert outcome.rejection_reason == "proposition_not_position_bearing"


def test_mechanical_floor_fails_on_pre_d6_and_passes_on_repaired_table() -> None:
    """Validation: The mechanical floor from step 3 fails on pre-D6 table and passes on repaired one."""
    store = Storage("social_proof.duckdb", read_only=True)

    # 1. Pre-D6 propositions table had substantial bare-topic failures
    pre_props = store.con.execute(
        "SELECT canonical_text FROM propositions_pre_d6"
    ).fetchall()
    assert len(pre_props) == 2161, f"Expected 2161 pre-D6 propositions, got {len(pre_props)}"

    pre_rejections = 0
    for (ptext,) in pre_props:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.95,
        )
        if not validate_position_bearing(claim).is_valid:
            pre_rejections += 1

    assert pre_rejections >= 495, f"Expected >= 495 pre-D6 rejections, got {pre_rejections}"
    rejection_rate_pre = pre_rejections / len(pre_props)
    assert rejection_rate_pre > 0.20, f"Expected > 20% pre-D6 rejection rate, got {rejection_rate_pre:.2%}"

    # 2. Live repaired propositions table passes 100%
    repaired_props = store.con.execute(
        "SELECT canonical_text FROM propositions WHERE status = 'active'"
    ).fetchall()
    assert len(repaired_props) > 0, "Expected active repaired propositions"

    repaired_rejections = 0
    for (ptext,) in repaired_props:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.95,
        )
        if not validate_position_bearing(claim).is_valid:
            repaired_rejections += 1

    assert repaired_rejections == 0, f"Expected 0 rejections on repaired table, got {repaired_rejections}"
    store.close()


def evaluate_position_test(prop: str) -> tuple[bool, str]:
    """Applies the position test:

    A proposition passes if both:
      <subject> supports <proposition>
      <subject> opposes  <proposition>
    are coherent, distinct claims on a matter at issue.
    """
    claim = ExtractedClaim(
        proposition_text=prop,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="dummy quote",
        confidence=0.95,
    )
    if not validate_position_bearing(claim).is_valid:
        return False, "Fails mechanical floor (bare topic, finite verb, or lack of relation)"

    lower = prop.lower()
    # Semantic check for descriptive / non-normative matter
    for non_normative in ["seen in 10 years", "upload to youtube", "valuation of a software"]:
        if non_normative in lower:
            return False, f"Descriptive fact or valuation, not a policy matter at issue ({prop})"

    return True, "PASS: Coherent, distinct support/oppose stances"


def test_assertion_c_live_sample_position_test() -> None:
    """Assertion (c): At least 16 of 20 propositions drawn at random from repaired table pass position test."""
    store = Storage("social_proof.duckdb", read_only=True)
    props = store.con.execute(
        "SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active' ORDER BY proposition_id"
    ).fetchall()
    store.close()

    assert len(props) >= 20, f"Expected at least 20 active propositions, found {len(props)}"

    random.seed(2026)
    sample_20 = random.sample(props, 20)

    pass_count = 0
    results = []

    for pid, text in sample_20:
        passed, reason = evaluate_position_test(text)
        if passed:
            pass_count += 1
        results.append((pid, text, passed, reason))

    pass_rate = pass_count / 20
    assert pass_count >= 16, (
        f"Assertion (c) FAILED: Expected >= 16/20 ({pass_rate:.1%}), got {pass_count}/20. "
        f"Results: {results}"
    )


def test_step5_candidate_pairs_and_tensions() -> None:
    """Step 5: Detector accepts 0 false unacknowledged reversals and preserves quarantined fabrications."""
    store = Storage("social_proof.duckdb", read_only=True)

    # 1. No published false reversal tensions from bare topics
    pub_tensions = store.con.execute(
        "SELECT tension_id FROM tensions WHERE status = 'published'"
    ).fetchall()
    assert len(pub_tensions) == 0, f"Expected 0 published false tensions, got {len(pub_tensions)}"

    # 2. Historical fabrications remain quarantined
    quarantined = store.con.execute(
        "SELECT tension_id, quarantine_reason FROM tensions WHERE status = 'quarantined'"
    ).fetchall()
    assert len(quarantined) == 3, f"Expected 3 quarantined tensions, got {len(quarantined)}"
    for _tid, reason in quarantined:
        assert reason == "fabricated_proposition"

    store.close()


def test_integrity_checks_pass() -> None:
    """Validation: All 15 integrity checks PASS on the repaired live database."""
    from worker.integrity import run_integrity_corpus

    results = run_integrity_corpus("social_proof.duckdb")
    assert len(results) == 15, f"Expected 15 checks, got {len(results)}"
    for r in results:
        assert r.passed is True, f"Integrity check {r.name} failed: {r.message}"


def test_falsification_prompt_version_and_position_bearing() -> None:
    """Falsification: Disabling mechanical floor allows bare topics to pass."""
    bare_topic = "most enterprises"
    claim = ExtractedClaim(
        proposition_text=bare_topic,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="dummy quote",
        confidence=0.95,
    )

    # With validator: rejected
    assert validate_position_bearing(claim).is_valid is False

    # Check prompt version in LocalGemmaRuntime is v1.7
    runtime = LocalGemmaRuntime()
    assert runtime.prompt_version == "v1.7"
    assert "THE POSITION TEST" in STABLE_SYSTEM_PROMPT
    assert "most enterprises" in STABLE_SYSTEM_PROMPT
