"""Item X4 (§11) Tests — The frame is fabricated onto claims that carry no position.

Validates:
1. reports_fact is in VALID_EXCLUSIONS and accepted by Claim/ExtractedClaim schemas.
2. Prompt v1.9 contains RULE 0 reachable decline branch asking if the speaker takes a side.
3. Both directions by utterance ID:
   - 03821a2c2f50bc9a (Azure Fed ramp) produces no claim.
   - 73c1f91e3d98e960 (hardware spend) produces AGAINST.
4. Descriptive utterances decline to empty list when speaker takes no normative side.
"""

from typing import get_args

from worker.entities import Claim
from worker.extract.runtime import STABLE_SYSTEM_PROMPT, LocalGemmaRuntime
from worker.extract.schema import ExtractedClaim
from worker.extract.validators import VALID_EXCLUSIONS, validate_speech_acts
from worker.storage import Storage


def test_reports_fact_in_exclusion_vocabulary() -> None:
    """1. reports_fact is a recognized exclusion reason across schemas and validators."""
    assert "reports_fact" in VALID_EXCLUSIONS

    # Check ExtractedClaim schema
    ec_excl_type = ExtractedClaim.model_fields["exclusion_reason"].annotation
    literal_args = get_args(get_args(ec_excl_type)[0])
    assert "reports_fact" in literal_args

    # Check Claim entity schema
    # In Claim dataclass, exclusion_reason is Literal[...] | None
    claim = Claim(
        claim_id="test_claim_fact",
        utterance_id="utt_1",
        subject_id="subj_1",
        proposition_id="prop_1",
        quote_text="Azure holds a Fed ramp, high authorization.",
        quote_span=(0, 42),
        stance="support",
        hedging_level=0.0,
        is_own_assertion=False,
        exclusion_reason="reports_fact",
        confidence=0.9,
    )
    assert claim.exclusion_reason == "reports_fact"
    assert claim.is_own_assertion is False


def test_validator_accepts_reports_fact() -> None:
    """2. Speech-act validator passes claims with exclusion_reason='reports_fact'."""
    ec = ExtractedClaim(
        position_frame="the speaker is FOR cloud certification standards",
        proposition_text="cloud certification standards",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=False,
        exclusion_reason="reports_fact",
        quote_text="Azure holds a Fed ramp, high authorization.",
        confidence=0.9,
    )
    result = validate_speech_acts(ec)
    assert result.is_valid is True
    assert ec.exclusion_reason == "reports_fact"


def test_prompt_v1_9_has_reachable_decline_branch() -> None:
    """3. Prompt v1.9 contains Rule 0 and decline examples."""
    runtime = LocalGemmaRuntime()
    assert runtime.prompt_version == "v1.9"
    assert (
        "RULE 0: DOES THE SPEAKER TAKE A SIDE?" in STABLE_SYSTEM_PROMPT
        or "0. MANDATORY FIRST STEP" in STABLE_SYSTEM_PROMPT
    )
    assert "THE REACHABLE DECLINE BRANCH" in STABLE_SYSTEM_PROMPT
    assert 'return {"claims": []}' in STABLE_SYSTEM_PROMPT
    assert "reports_fact" in STABLE_SYSTEM_PROMPT


def test_both_directions_by_utterance_id() -> None:
    """4. In live store: Azure Fed ramp has no claim; hardware spend has AGAINST claim."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        # Direction 1: Azure Fed ramp (03821a2c2f50bc9a) produces no claim
        azure_claims = store.con.execute(
            "SELECT claim_id, position_frame FROM claims WHERE utterance_id = '03821a2c2f50bc9a'"
        ).fetchall()
        assert len(azure_claims) == 0, (
            f"Expected 0 claims for Azure Fed ramp, got {len(azure_claims)}: {azure_claims}"
        )

        # Direction 2: Hardware spend (73c1f91e3d98e960) produces AGAINST claim
        spend_claims = store.con.execute(
            "SELECT claim_id, stance, position_frame FROM claims WHERE utterance_id = '73c1f91e3d98e960'"
        ).fetchall()
        assert len(spend_claims) > 0, "Expected at least 1 claim for hardware spend"
        assert any(c[1] == "oppose" for c in spend_claims), (
            f"Expected oppose stance, got {spend_claims}"
        )
    finally:
        store.close()
