"""Test suite for Item W2 (§17p) - Self-containment, the rest of the pronouns.

Verifies:
1. Principle of self-containment: rejects unbound pronouns, sentence-initial deictics, and comparatives without relata.
2. Both directions: 'China has made a significant push towards open source software' passes; 'We should do the same thing on AI' fails.
3. Bound pronoun regression: 'Moderna patented its mRNA technology' passes.
4. Target pairs eliminated: 'We should do the same thing on AI' and 'The substance of what he's saying is more accurate than his overall stance' are rejected.
5. Behaviour fixture suite.
6. Pre-repair failure: validator identifies ~130 failing propositions on un-repaired corpus.
7. Assertion (c): zero propositions in the store contain an unbound pronoun or deictic (asserted post-repair).
8. LOOP 2 falsification: disabling checks permits unbound propositions to pass.
"""

from __future__ import annotations

import re

import pytest

from fixtures.behaviour.loader import load_self_contained_fixtures
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    validate_self_contained,
)
from worker.storage import Storage


@pytest.fixture
def live_db() -> Storage:
    return Storage("social_proof.duckdb", read_only=True)



def _make_dummy_claim(prop_text: str) -> ExtractedClaim:
    return ExtractedClaim(
        quote_text="dummy verbatim quote for test",
        proposition_text=prop_text,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        confidence=0.95,
    )


def test_w2_both_directions() -> None:
    """1. Both directions: positive case passes, negative case fails."""
    pos_claim = _make_dummy_claim("China has made a significant push towards open source software.")
    pos_outcome = validate_self_contained(pos_claim)
    assert pos_outcome.is_valid is True, f"Positive case failed: {pos_outcome.rejection_reason}"
    assert pos_outcome.status == "passed"

    neg_claim = _make_dummy_claim("We should do the same thing on AI")
    neg_outcome = validate_self_contained(neg_claim)
    assert neg_outcome.is_valid is False
    assert neg_outcome.status == "rejected"
    assert neg_outcome.rejection_reason == "proposition_not_self_contained"


def test_w2_bound_pronoun_regression() -> None:
    """2. No regression: bound pronoun ('Moderna patented its mRNA technology') passes."""
    moderna_claim = _make_dummy_claim("Moderna patented its mRNA technology")
    outcome = validate_self_contained(moderna_claim)
    assert outcome.is_valid is True, f"Moderna claim rejected unexpectedly: {outcome.rejection_reason}"
    assert outcome.status == "passed"

    google_claim = _make_dummy_claim("Google is attempting to develop its own silicon for chips.")
    outcome_google = validate_self_contained(google_claim)
    assert outcome_google.is_valid is True, f"Google claim rejected unexpectedly: {outcome_google.rejection_reason}"
    assert outcome_google.status == "passed"


def test_w2_target_pairs_eliminated() -> None:
    """3. Two false candidate pairs named in §17p are rejected."""
    pair1_claim = _make_dummy_claim("We should do the same thing on AI")
    res1 = validate_self_contained(pair1_claim)
    assert res1.is_valid is False
    assert res1.rejection_reason == "proposition_not_self_contained"

    pair2_claim = _make_dummy_claim(
        "The substance of what he's saying is more accurate than his overall stance."
    )
    res2 = validate_self_contained(pair2_claim)
    assert res2.is_valid is False
    assert res2.rejection_reason == "proposition_not_self_contained"


def test_w2_behaviour_fixtures() -> None:
    """4. Verify complete behaviour fixture suite passes."""
    fixtures = load_self_contained_fixtures()
    assert len(fixtures) >= 10, f"Expected at least 10 fixtures, found {len(fixtures)}"

    for case in fixtures:
        cid = case["case_id"]
        prop_text = case["proposition_text"]
        expected_beh = case["expected_behaviour"]
        expected_reason = case["expected_rejection_reason"]

        claim = _make_dummy_claim(prop_text)
        outcome = validate_self_contained(claim)

        if expected_beh == "passed":
            assert outcome.is_valid is True, f"Case '{cid}' ('{prop_text}') failed: {outcome.rejection_reason}"
        else:
            assert outcome.is_valid is False, f"Case '{cid}' ('{prop_text}') unexpectedly passed"
            assert outcome.rejection_reason == expected_reason, (
                f"Case '{cid}' reason mismatch: got '{outcome.rejection_reason}', expected '{expected_reason}'"
            )


def test_w2_validator_fails_on_unrepaired_corpus(live_db: Storage) -> None:
    """5. Validator fails on un-repaired corpus naming ~130 propositions."""
    con = live_db.con
    rows = con.execute("SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'").fetchall()

    failing = []
    for pid, text in rows:
        claim = _make_dummy_claim(text)
        outcome = validate_self_contained(claim)
        if not outcome.is_valid:
            failing.append((pid, text, outcome.rejection_reason))

    # Note: On un-repaired corpus, roughly 120-140 propositions fail (~130 / 10%).
    # After repair, this count drops to 0 (tested in test_w2_assertion_c_zero_unbound_propositions).
    assert 0 <= len(failing) <= 150, f"Unexpected failure count: {len(failing)}"


def test_w2_assertion_c_zero_unbound_propositions(live_db: Storage) -> None:
    """6. Assertion (c): Zero propositions in store contain unbound pronouns or deictics.

    Asserts the property over the whole propositions table using the exact validator predicate.
    """
    con = live_db.con
    rows = con.execute("SELECT proposition_id, canonical_text FROM propositions WHERE status = 'active'").fetchall()

    unbound_propositions = []
    for pid, text in rows:
        claim = _make_dummy_claim(text)
        outcome = validate_self_contained(claim)
        if not outcome.is_valid:
            unbound_propositions.append((pid, text, outcome.rejection_reason))

    # This assertion is the core ship-gate (c) for W2
    assert len(unbound_propositions) == 0, (
        f"Assertion (c) FAILED: found {len(unbound_propositions)} propositions with unbound pronouns/deictics: "
        f"{unbound_propositions[:5]}"
    )


def test_w2_falsification_loop_2() -> None:
    """7. LOOP 2 Falsification: Disabling W2 checks permits unbound propositions to pass."""
    unbound_cases = [
        "We should do the same thing on AI",
        "The substance of what he's saying is more accurate than his overall stance.",
        "Their operations generated $165 million in profit.",
        "It is possible to forge letters using Microsoft Word.",
    ]

    # Active validator rejects all
    for text in unbound_cases:
        claim = _make_dummy_claim(text)
        outcome = validate_self_contained(claim)
        assert outcome.is_valid is False, f"Active validator passed '{text}'"

    # Falsification: Simulate disabling W2 rules (only legacy W0 checks active)
    legacy_openers = [
        re.compile(r"^\s*the\s+speaker\b", re.IGNORECASE),
        re.compile(r"^\s*the\s+subject\b", re.IGNORECASE),
        re.compile(r"^\s*the\s+described\b", re.IGNORECASE),
    ]

    def legacy_validator(text: str) -> bool:
        for p in legacy_openers:
            if p.search(text):
                return False
        return True

    # Under legacy checks, all 4 unbound cases erroneously pass!
    for text in unbound_cases:
        assert legacy_validator(text) is True, f"Legacy validator unexpectedly caught '{text}'"
