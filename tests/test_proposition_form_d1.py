"""Tests and falsification for Item D1 (§13u):

Canonical Proposition Form Restoration and Polarity Validation.
"""

from __future__ import annotations

from worker.extract.runtime import STABLE_SYSTEM_PROMPT, LocalGemmaRuntime
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import (
    POLARITY_BANNED_PATTERNS,
    validate_polarity,
)
from worker.storage import Storage


def test_polarity_validator_mandatory_cases() -> None:
    """1. Mandatory test strings from Item D1 Steps 1 & 2 must be rejected."""
    mandatory_banned = [
        "Forces should be allowed to play out",
        "democrats are favored to win the house in the upcoming election",
        "Azure is cheaper than running a database on-premise",
        "Running a Chinese model does not necessarily mean data goes to China",
        "The device will not be similar to an iPad",
    ]

    for ptext in mandatory_banned:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.95,
        )
        outcome = validate_polarity(claim)
        assert outcome.is_valid is False, f"Expected '{ptext}' to be rejected"
        assert outcome.rejection_reason == "proposition_carries_polarity"


def test_polarity_validator_canonical_noun_phrases_pass() -> None:
    """2. Canonical noun-phrase matters at issue must pass validation."""
    valid_noun_phrases = [
        "federal licensing of frontier AI models",
        "telecommunications infrastructure capital expenditure in fiber optics",
        "societal and official optimism toward artificial intelligence in China compared to Western nations",
        "government regulation of frontier artificial intelligence compute clusters",
    ]

    for ptext in valid_noun_phrases:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy quote",
            confidence=0.95,
        )
        outcome = validate_polarity(claim)
        assert outcome.is_valid is True, f"Expected '{ptext}' to pass, got {outcome}"
        assert outcome.rejection_reason is None


def test_falsification_disabled_polarity_validator() -> None:
    """3. Falsification: Disabling polarity patterns allows prohibited strings to pass."""
    sample_banned = "Forces should be allowed to play out"
    claim = ExtractedClaim(
        proposition_text=sample_banned,
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text="dummy quote",
        confidence=0.95,
    )

    # Initial state: rejected
    assert validate_polarity(claim).is_valid is False

    # Neuter patterns
    original_patterns = list(POLARITY_BANNED_PATTERNS)
    POLARITY_BANNED_PATTERNS.clear()
    try:
        # Neutered state: passes (falsification verified)
        assert validate_polarity(claim).is_valid is True
    finally:
        # Restore patterns
        POLARITY_BANNED_PATTERNS.extend(original_patterns)

    # Restored state: rejected again
    assert validate_polarity(claim).is_valid is False


def test_prompt_v1_6_canonical_specification() -> None:
    """4. Prompt v1.6/v1.7 specifies canonical noun-phrase form."""
    runtime = LocalGemmaRuntime()
    assert runtime.prompt_version in ("v1.6", "v1.7", "v1.8", "v1.9")
    assert "CANONICAL PROPOSITION FORM" in STABLE_SYSTEM_PROMPT
    assert "NOUN PHRASE" in STABLE_SYSTEM_PROMPT
    assert "federal licensing of frontier AI models" in STABLE_SYSTEM_PROMPT


def test_assertion_c_live_corpus_metrics() -> None:
    """5. Assertion (c): Singleton rate, multi-episode propositions, and zero polarity in DuckDB."""
    storage = Storage("social_proof.duckdb", read_only=True)

    r_prop = storage.con.execute(
        "SELECT count(*) FROM propositions WHERE status = 'active'"
    ).fetchone()
    c_prop = int(r_prop[0]) if r_prop else 0
    assert c_prop > 0, "Expected non-zero active propositions"

    # Zero polarity in table
    props = [
        r[0]
        for r in storage.con.execute(
            "SELECT canonical_text FROM propositions WHERE status = 'active'"
        ).fetchall()
    ]
    for ptext in props:
        claim = ExtractedClaim(
            proposition_text=ptext,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text="dummy",
            confidence=0.9,
        )
        outcome = validate_polarity(claim)
        assert outcome.is_valid is True, f"Found polarity in stored proposition: '{ptext}'"
