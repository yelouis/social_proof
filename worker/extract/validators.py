"""The five post-extraction validators enforcing data contracts and Invariant I7.

Implements design_claim_extraction.md §3-§5 and agent_execution_guide.md §11 (U11).
"""

import re
from dataclasses import dataclass

from worker.entities import Utterance
from worker.extract.schema import ExtractedClaim

# Banned polarity tokens in proposition_text (must live exclusively in stance)
POLARITY_BANNED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:should not|shouldn't|must not|mustn't|cannot|can't)\b", re.IGNORECASE),
    re.compile(r"\b(?:never|oppose|opposing|against|prohibit|prohibiting|illegal)\b", re.IGNORECASE),
    re.compile(r"\b(?:is bad|is harmful|is evil|is wrong)\b", re.IGNORECASE),
]

VALID_STANCES: set[str] = {"support", "oppose", "mixed", "hedge"}
VALID_EXCLUSIONS: set[str] = {
    "reported_speech",
    "hypothetical",
    "sarcasm",
    "steelman",
    "joke",
    "question",
    "quote_agreement_unclear",
}


@dataclass
class ValidationOutcome:
    is_valid: bool
    rejection_reason: str | None = None
    resolved_quote_span: tuple[int, int] | None = None


def validate_quote_verbatim(claim: ExtractedClaim, utterance_text: str) -> ValidationOutcome:
    """Validator 1: Exact verbatim substring check acting as evidence.

    quote_text must resolve in text_verbatim.
    """
    quote = claim.quote_text.strip()
    if not quote:
        return ValidationOutcome(False, "quote_verbatim_empty")

    idx = utterance_text.find(quote)
    if idx == -1:
        # Fallback: case-insensitive match
        idx_lower = utterance_text.lower().find(quote.lower())
        if idx_lower == -1:
            return ValidationOutcome(False, "quote_verbatim_not_found_in_utterance")
        idx = idx_lower

    span = (idx, idx + len(quote))
    return ValidationOutcome(True, resolved_quote_span=span)


def validate_polarity(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 2: Proposition text must be stance-neutral and contain no polarity words."""
    prop_text = claim.proposition_text
    for pat in POLARITY_BANNED_PATTERNS:
        if pat.search(prop_text):
            return ValidationOutcome(False, f"polarity_violation_in_proposition: {pat.pattern}")
    return ValidationOutcome(True)


def validate_speech_acts(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 3: Invariant I7 speech-act validation."""
    if not claim.is_own_assertion:
        if not claim.exclusion_reason or claim.exclusion_reason not in VALID_EXCLUSIONS:
            return ValidationOutcome(False, "excluded_claim_missing_valid_exclusion_reason")
    elif claim.exclusion_reason is not None:
        return ValidationOutcome(False, "own_assertion_cannot_have_exclusion_reason")
    return ValidationOutcome(True)


def validate_confidence_floor(claim: ExtractedClaim, floor: float = 0.70) -> ValidationOutcome:
    """Validator 4: Confidence floor check."""
    if claim.confidence < floor:
        return ValidationOutcome(False, f"confidence_below_floor: {claim.confidence:.2f} < {floor:.2f}")
    return ValidationOutcome(True)


def validate_schema(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 5: Schema conformity (stance enum, hedging bounds)."""
    if claim.stance not in VALID_STANCES:
        return ValidationOutcome(False, f"invalid_stance: {claim.stance}")
    if not (0.0 <= claim.hedging_level <= 1.0):
        return ValidationOutcome(False, f"hedging_level_out_of_bounds: {claim.hedging_level}")
    return ValidationOutcome(True)


def validate_extracted_claim(
    claim: ExtractedClaim,
    utterance: Utterance,
    confidence_floor: float = 0.70,
) -> tuple[bool, str | None, tuple[int, int] | None]:
    """Runs all 5 validators in sequence."""
    # 1. Quote Verbatim
    res_quote = validate_quote_verbatim(claim, utterance.text_verbatim)
    if not res_quote.is_valid:
        return False, res_quote.rejection_reason, None

    # 2. Polarity
    res_pol = validate_polarity(claim)
    if not res_pol.is_valid:
        return False, res_pol.rejection_reason, None

    # 3. Speech Acts
    res_sa = validate_speech_acts(claim)
    if not res_sa.is_valid:
        return False, res_sa.rejection_reason, None

    # 4. Confidence Floor
    res_conf = validate_confidence_floor(claim, confidence_floor)
    if not res_conf.is_valid:
        return False, res_conf.rejection_reason, None

    # 5. Schema
    res_schema = validate_schema(claim)
    if not res_schema.is_valid:
        return False, res_schema.rejection_reason, None

    return True, None, res_quote.resolved_quote_span
