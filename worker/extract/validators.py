"""The six post-extraction validators enforcing data contracts and Invariant I7.

Implements design_claim_extraction.md §3-§5, §8 (Validator 6) and agent_execution_guide.md §18 (X1).
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from worker.entities import Utterance
from worker.extract.schema import ExtractedClaim

logger = logging.getLogger(__name__)

# Parameter 026: Entailment guard thresholds (provisional, measured against live corpus & X0 fabrications)
# Measured in Issue 025/X1:
# - Known fabrications: 6 tokens, similarities 0.5296 and 0.5337
# - Live verified claims: 7 to 41 tokens (min 7 on string theory claim), similarities 0.7091 to 0.9311
MIN_QUOTE_TOKENS: int = 7
T_ENTAIL_LOW: float = 0.60
T_ENTAIL_HIGH: float = 0.70

# Rejection counters for observability / regression detection
VALIDATOR_REJECTION_COUNTERS: Counter[str] = Counter()
# Invariant I7 speech-act exclusion counters (Item S1 / §17n)
VALIDATOR_EXCLUSION_COUNTERS: Counter[str] = Counter()


def get_rejection_counts() -> dict[str, int]:
    """Returns a snapshot of validation rejections and quarantines."""
    return dict(VALIDATOR_REJECTION_COUNTERS)


def reset_rejection_counts() -> None:
    """Resets validation counters (useful for test isolation)."""
    VALIDATOR_REJECTION_COUNTERS.clear()


def get_exclusion_counts() -> dict[str, int]:
    """Returns a snapshot of Invariant I7 speech-act exclusions."""
    return dict(VALIDATOR_EXCLUSION_COUNTERS)


def reset_exclusion_counts() -> None:
    """Resets speech-act exclusion counters."""
    VALIDATOR_EXCLUSION_COUNTERS.clear()


def get_exclusion_rate(storage: Any) -> tuple[int, int, float]:
    """Computes (excluded_count, total_claims, exclusion_rate_pct) from database."""
    row = storage.con.execute("""
        SELECT
            count(*) FILTER (WHERE NOT is_own_assertion),
            count(*),
            (count(*) FILTER (WHERE NOT is_own_assertion) * 100.0) / NULLIF(count(*), 0)
        FROM claims
    """).fetchone()
    if not row or row[1] == 0:
        return 0, 0, 0.0
    return int(row[0]), int(row[1]), float(row[2])


# Invariant I7 speech act patterns (Item S1 / §17n)
QUESTION_SPEECH_ACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(?:so\s+)?you(?:'re|\s+are)\s+saying\b", re.IGNORECASE),
    re.compile(
        r"^\s*(?:are\s+you|do\s+you|can\s+you|should\s+we|would\s+you|is\s+it|is\s+that|why\s+do|why\s+would|what\s+is|what\s+if)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\?\s*$"),
]

RHETORICAL_SPEECH_ACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*you\s+can\s+say\s*,\s*okay\b", re.IGNORECASE),
    re.compile(r"^\s*(?:someone|they)(?:'d|\s+would|\s+might)\s+say\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+argument\s+(?:could|would)\s+be\b", re.IGNORECASE),
    re.compile(r"^\s*suppose\s+that\b", re.IGNORECASE),
]

# Banned polarity tokens in proposition_text (must live exclusively in stance)
POLARITY_BANNED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:should not|shouldn't|must not|mustn't|cannot|can't)\b", re.IGNORECASE),
    re.compile(r"\b(?:never|oppose|opposing|against|prohibit|prohibiting|illegal)\b", re.IGNORECASE),
    re.compile(r"\b(?:is bad|is harmful|is evil|is wrong)\b", re.IGNORECASE),
]

# Banned indexical patterns in proposition_text (must be self-contained and global, Item W0 / §17m)
INDEXICAL_BANNED_OPENERS: list[re.Pattern[str]] = [
    re.compile(r"^\s*the\s+speaker\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+subject\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+described\b", re.IGNORECASE),
    re.compile(r"^\s*(?:they|he|she|this|that|these|those)\b", re.IGNORECASE),
]

INDEXICAL_BANNED_ANYWHERE: list[re.Pattern[str]] = [
    re.compile(r"\bthe\s+speaker\b", re.IGNORECASE),
    re.compile(r"\bthe\s+subject\b", re.IGNORECASE),
    re.compile(r"\bthe\s+described\s+powers?\b", re.IGNORECASE),
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
    "entailment_ambiguous",
}


@dataclass
class ValidationOutcome:
    is_valid: bool
    rejection_reason: str | None = None
    resolved_quote_span: tuple[int, int] | None = None
    status: Literal["passed", "rejected", "quarantined"] = "passed"
    similarity: float | None = None
    prop_embedding: list[float] | None = None
    quote_embedding: list[float] | None = None

    def __iter__(self) -> Any:
        """Allows 3-element tuple unpacking (is_valid, rejection_reason, span) for backward compatibility."""
        return iter((self.is_valid, self.rejection_reason, self.resolved_quote_span))


def validate_quote_verbatim(claim: ExtractedClaim, utterance_text: str) -> ValidationOutcome:
    """Validator 1: Exact verbatim substring check acting as evidence.

    quote_text must resolve in text_verbatim.
    """
    quote = claim.quote_text.strip()
    if not quote:
        return ValidationOutcome(False, "quote_verbatim_empty", status="rejected")

    idx = utterance_text.find(quote)
    if idx == -1:
        # Fallback: case-insensitive match
        idx_lower = utterance_text.lower().find(quote.lower())
        if idx_lower == -1:
            return ValidationOutcome(
                False, "quote_not_verbatim_in_utterance", status="rejected"
            )
        idx = idx_lower

    return ValidationOutcome(True, resolved_quote_span=(idx, idx + len(quote)), status="passed")


def validate_entailment(
    claim: ExtractedClaim,
    embedder: Any | None = None,
    min_quote_tokens: int = MIN_QUOTE_TOKENS,
    t_low: float = T_ENTAIL_LOW,
    t_high: float = T_ENTAIL_HIGH,
) -> ValidationOutcome:
    """Validator 6: Entailment guard (Issue 025 = C, Item X1 / §18).

    Guarantees quote actually supports proposition.
    Rejects arbitary or fabricated quotes via token length floor and embedding similarity.
    """
    quote = claim.quote_text.strip()
    token_count = len(quote.split())
    if token_count < min_quote_tokens:
        VALIDATOR_REJECTION_COUNTERS["quote_too_short"] += 1
        logger.info(
            "Validator 6 rejected claim (quote_too_short: %d < %d tokens). Quote: '%s'",
            token_count,
            min_quote_tokens,
            quote,
        )
        return ValidationOutcome(False, rejection_reason="quote_too_short", status="rejected")

    if embedder is None:
        from worker.extract.dedup import get_embedder

        embedder = get_embedder()

    from worker.extract.dedup import cosine_similarity

    # Crucial: both use 'search_document:' prefix (Trap 7: avoiding asymmetric prefix spaces)
    vec_quote = embedder.embed_document(quote)
    vec_prop = embedder.embed_document(claim.proposition_text.strip())
    sim = cosine_similarity(vec_quote, vec_prop)

    if sim < t_low:
        VALIDATOR_REJECTION_COUNTERS["quote_does_not_support_proposition"] += 1
        logger.info(
            "Validator 6 rejected claim (quote_does_not_support_proposition: sim=%.4f < %.4f). Prop: '%s', Quote: '%s'",
            sim,
            t_low,
            claim.proposition_text,
            quote,
        )
        return ValidationOutcome(
            is_valid=False,
            rejection_reason="quote_does_not_support_proposition",
            status="rejected",
            similarity=sim,
            prop_embedding=vec_prop,
            quote_embedding=vec_quote,
        )
    elif sim < t_high:
        VALIDATOR_REJECTION_COUNTERS["entailment_ambiguous"] += 1
        logger.info(
            "Validator 6 quarantined claim (entailment_ambiguous): %.4f <= sim=%.4f < %.4f. Prop: '%s', Quote: '%s'",
            t_low,
            sim,
            t_high,
            claim.proposition_text,
            quote,
        )
        return ValidationOutcome(
            is_valid=True,
            rejection_reason="entailment_ambiguous",
            status="quarantined",
            similarity=sim,
            prop_embedding=vec_prop,
            quote_embedding=vec_quote,
        )

    return ValidationOutcome(
        is_valid=True,
        rejection_reason=None,
        status="passed",
        similarity=sim,
        prop_embedding=vec_prop,
        quote_embedding=vec_quote,
    )


def validate_self_contained(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator: Proposition text must be self-contained, global, and free of unbound indexicals.

    Implements design_claim_extraction.md §2, design_data_layer.md §2, and Item W0 (§17m).
    Rejects propositions containing 'the speaker', 'the subject', 'the described',
    or sentence-initial unbound pronouns ('they', 'he', 'she', 'this', 'that', 'these', 'those').
    """
    prop_text = (claim.proposition_text or "").strip()
    for pat in INDEXICAL_BANNED_OPENERS:
        if pat.search(prop_text):
            VALIDATOR_REJECTION_COUNTERS["proposition_not_self_contained"] += 1
            return ValidationOutcome(
                is_valid=False,
                rejection_reason="proposition_not_self_contained",
                status="rejected",
            )
    for pat in INDEXICAL_BANNED_ANYWHERE:
        if pat.search(prop_text):
            VALIDATOR_REJECTION_COUNTERS["proposition_not_self_contained"] += 1
            return ValidationOutcome(
                is_valid=False,
                rejection_reason="proposition_not_self_contained",
                status="rejected",
            )
    return ValidationOutcome(True, status="passed")


def validate_stance_direction(
    claim: ExtractedClaim,
    embedder: Any | None = None,
    delta: float = 0.05,
    prop_embedding: list[float] | None = None,
    quote_embedding: list[float] | None = None,
) -> ValidationOutcome:
    """Validator 7: Stance direction validation (Item S1, §17n).

    Verifies directional alignment between quote_text and proposition_text.
    Validator 6 certifies aboutness (entailment), while Validator 7 certifies direction.

    Compares quote embedding against proposition P and its negated form not-P:
    - For oppose: the quote must be closer to not-P than to P (sim_pos <= sim_neg).
      If the quote is strictly closer to P than to not-P, rejects with 'stance_direction_mismatch'.
    - For support: the quote must be closer to P than to not-P (sim_neg <= sim_pos + 0.05).
      If the quote is clearly closer to not-P than to P, rejects with 'stance_direction_mismatch'.
    """
    stance = claim.stance
    if stance not in ("support", "oppose"):
        return ValidationOutcome(True, status="passed")

    prop = (claim.proposition_text or "").strip()
    quote = (claim.quote_text or "").strip()
    if not prop or not quote:
        return ValidationOutcome(True, status="passed")

    if embedder is None:
        from worker.extract.dedup import get_embedder

        embedder = get_embedder()

    from worker.extract.dedup import cosine_similarity

    neg_prop = f"It is not the case that {prop[0].lower() + prop[1:] if prop else prop}"
    v_prop = prop_embedding if prop_embedding is not None else embedder.embed_document(prop)
    v_neg_prop = embedder.embed_document(neg_prop)
    v_quote = quote_embedding if quote_embedding is not None else embedder.embed_document(quote)

    sim_pos = cosine_similarity(v_quote, v_prop)
    sim_neg = cosine_similarity(v_quote, v_neg_prop)

    if stance == "oppose" and sim_pos > sim_neg:
        VALIDATOR_REJECTION_COUNTERS["stance_direction_mismatch"] += 1
        logger.info(
            "Validator 7 rejected claim (stance_direction_mismatch): stance='oppose' but sim_pos=%.4f > sim_neg=%.4f. Prop: '%s', Quote: '%s'",
            sim_pos,
            sim_neg,
            prop,
            quote,
        )
        return ValidationOutcome(
            is_valid=False,
            rejection_reason="stance_direction_mismatch",
            status="rejected",
            similarity=sim_pos,
        )

    if stance == "support" and sim_neg > sim_pos + 0.05:
        VALIDATOR_REJECTION_COUNTERS["stance_direction_mismatch"] += 1
        logger.info(
            "Validator 7 rejected claim (stance_direction_mismatch): stance='support' but sim_neg=%.4f > sim_pos=%.4f + 0.05. Prop: '%s', Quote: '%s'",
            sim_neg,
            sim_pos,
            prop,
            quote,
        )
        return ValidationOutcome(
            is_valid=False,
            rejection_reason="stance_direction_mismatch",
            status="rejected",
            similarity=sim_pos,
        )

    return ValidationOutcome(True, status="passed", similarity=sim_pos)


def validate_polarity(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 2: Proposition text must be stance-neutral and contain no polarity words."""
    prop_text = claim.proposition_text
    for pat in POLARITY_BANNED_PATTERNS:
        if pat.search(prop_text):
            return ValidationOutcome(
                False, f"polarity_violation_in_proposition: {pat.pattern}", status="rejected"
            )
    return ValidationOutcome(True, status="passed")


def validate_speech_acts(
    claim: ExtractedClaim,
    utterance: Utterance | None = None,
) -> ValidationOutcome:
    """Validator 3: Invariant I7 speech-act validation with enhanced sensitivity (Item S1, §17n).

    Automatically identifies and excludes rhetorical setups and interrogatives
    from own assertions, setting is_own_assertion=False and appropriate exclusion_reason.
    """
    quote = (claim.quote_text or "").strip()
    utt_text = (utterance.text_verbatim or "").strip() if utterance else ""

    # 1. Question / interrogative detection
    if claim.is_own_assertion:
        for pat in QUESTION_SPEECH_ACT_PATTERNS:
            if pat.search(quote) or (utt_text and pat.search(utt_text)):
                claim.is_own_assertion = False
                claim.exclusion_reason = "question"
                VALIDATOR_EXCLUSION_COUNTERS["question"] += 1
                logger.info(
                    "Invariant I7 excluded claim as question: '%s'",
                    quote,
                )
                break

    # 2. Rhetorical / hypothetical setup detection
    if claim.is_own_assertion:
        for pat in RHETORICAL_SPEECH_ACT_PATTERNS:
            if pat.search(quote) or (utt_text and pat.search(utt_text)):
                claim.is_own_assertion = False
                claim.exclusion_reason = "hypothetical"
                VALIDATOR_EXCLUSION_COUNTERS["hypothetical"] += 1
                logger.info(
                    "Invariant I7 excluded claim as hypothetical/rhetorical: '%s'",
                    quote,
                )
                break

    # 3. Schema consistency check
    if not claim.is_own_assertion:
        if not claim.exclusion_reason or claim.exclusion_reason not in VALID_EXCLUSIONS:
            return ValidationOutcome(
                False, "excluded_claim_missing_valid_exclusion_reason", status="rejected"
            )
    elif claim.exclusion_reason is not None:
        return ValidationOutcome(
            False, "own_assertion_cannot_have_exclusion_reason", status="rejected"
        )
    return ValidationOutcome(True, status="passed")


def validate_confidence_floor(claim: ExtractedClaim, floor: float = 0.70) -> ValidationOutcome:
    """Validator 4: Confidence floor check."""
    if claim.confidence < floor:
        return ValidationOutcome(
            False,
            f"confidence_below_floor: {claim.confidence:.2f} < {floor:.2f}",
            status="rejected",
        )
    return ValidationOutcome(True, status="passed")


def validate_schema(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 5: Schema conformity (stance enum, hedging bounds)."""
    if claim.stance not in VALID_STANCES:
        return ValidationOutcome(False, f"invalid_stance: {claim.stance}", status="rejected")
    if not (0.0 <= claim.hedging_level <= 1.0):
        return ValidationOutcome(
            False, f"hedging_level_out_of_bounds: {claim.hedging_level}", status="rejected"
        )
    return ValidationOutcome(True, status="passed")


def validate_extracted_claim(
    claim: ExtractedClaim,
    utterance: Utterance,
    confidence_floor: float = 0.70,
    embedder: Any | None = None,
    min_quote_tokens: int = MIN_QUOTE_TOKENS,
    t_low: float = T_ENTAIL_LOW,
    t_high: float = T_ENTAIL_HIGH,
) -> ValidationOutcome:
    """Runs validators in sequence:

    1. Quote Verbatim (substring in utterance)
    2. Self-Contained (Item W0: reject indexicals and unbound pronouns before embedder)
    3. Entailment (Validator 6: length floor, document-to-document embedding similarity)
    4. Stance Direction (Validator 7, Item S1: verify directional entailment P vs ~P)
    5. Polarity (neutral proposition text)
    6. Speech Acts (Invariant I7: exclusions vs own assertions, interrogative/rhetorical sensitivity)
    7. Confidence Floor (confidence >= floor)
    8. Schema (valid stance, hedging level in [0, 1])
    """
    # 1. Quote Verbatim
    res_quote = validate_quote_verbatim(claim, utterance.text_verbatim)
    if not res_quote.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_quote.rejection_reason or "quote_verbatim_failed"] += 1
        return res_quote

    # 2. Self-Contained / Non-Indexical (Item W0 / §17m)
    res_self_contained = validate_self_contained(claim)
    if not res_self_contained.is_valid:
        return res_self_contained

    # 3. Entailment (Validator 6) runs immediately after self-contained check
    res_entail = validate_entailment(
        claim=claim,
        embedder=embedder,
        min_quote_tokens=min_quote_tokens,
        t_low=t_low,
        t_high=t_high,
    )
    if not res_entail.is_valid:
        return res_entail

    # If ambiguous, mark claim as excluded/quarantined so speech acts validation succeeds
    if res_entail.status == "quarantined":
        claim.is_own_assertion = False
        claim.exclusion_reason = "entailment_ambiguous"

    # 4. Stance Direction (Validator 7, Item S1 / §17n)
    # Evaluated when claim clears entailment (not quarantined or rejected)
    if res_entail.status != "quarantined":
        res_stance = validate_stance_direction(
            claim,
            embedder=embedder,
            prop_embedding=res_entail.prop_embedding,
            quote_embedding=res_entail.quote_embedding,
        )
        if not res_stance.is_valid:
            return res_stance

    # 5. Polarity
    res_pol = validate_polarity(claim)
    if not res_pol.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_pol.rejection_reason or "polarity_failed"] += 1
        return res_pol

    # 6. Speech Acts (Invariant I7 with enhanced sensitivity, Item S1 / §17n)
    res_sa = validate_speech_acts(claim, utterance)
    if not res_sa.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_sa.rejection_reason or "speech_acts_failed"] += 1
        return res_sa

    # 7. Confidence Floor
    res_conf = validate_confidence_floor(claim, confidence_floor)
    if not res_conf.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_conf.rejection_reason or "confidence_floor_failed"] += 1
        return res_conf

    # 8. Schema
    res_schema = validate_schema(claim)
    if not res_schema.is_valid:
        VALIDATOR_REJECTION_COUNTERS[res_schema.rejection_reason or "schema_failed"] += 1
        return res_schema

    return ValidationOutcome(
        is_valid=True,
        rejection_reason=res_entail.rejection_reason,
        resolved_quote_span=res_quote.resolved_quote_span,
        status=res_entail.status,
        similarity=res_entail.similarity,
        prop_embedding=res_entail.prop_embedding,
        quote_embedding=res_entail.quote_embedding,
    )
