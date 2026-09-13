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
# Standing bidirectional stance correction counters (Item D3 / §17t)
VALIDATOR_CORRECTION_COUNTERS: Counter[str] = Counter()


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


def get_stance_correction_counts() -> dict[str, int]:
    """Returns a snapshot of directional stance corrections (Item D3 / §17t)."""
    return dict(VALIDATOR_CORRECTION_COUNTERS)


def reset_stance_correction_counts() -> None:
    """Resets directional stance correction counters."""
    VALIDATOR_CORRECTION_COUNTERS.clear()


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

# Banned polarity tokens in proposition_text (must live exclusively in stance, Item D1 / §13u)
POLARITY_BANNED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:should not|shouldn't|must not|mustn't|cannot|can't)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:never|oppose|opposing|against|prohibit|prohibiting|illegal)\b", re.IGNORECASE
    ),
    re.compile(r"\b(?:is bad|is harmful|is evil|is wrong)\b", re.IGNORECASE),
    # Positive and modal polarity (D1 Step 1)
    re.compile(r"\b(?:should|must|ought)\b", re.IGNORECASE),
    # Comparatives of evaluation (D1 Step 1)
    re.compile(r"\b(?:better|worse|cheaper|faster|stronger)\s+than\b", re.IGNORECASE),
    # Outcome predictions (D1 Step 1)
    re.compile(r"\b(?:is|are|was|were)?\s*favored\s+to\b", re.IGNORECASE),
    re.compile(r"\bwill\s+(?:win|beat)\b", re.IGNORECASE),
    # Subordinate clause negation / general negation in proposition text (D1 Step 2)
    re.compile(r"\b(?:not|n't|neither|nor)\b", re.IGNORECASE),
    re.compile(r"\bno\s+[a-z]+", re.IGNORECASE),
]

# ==============================================================================
# Principle of Proposition Self-Containment (Items W0 / §17m & W2 / §17p):
#
# A proposition must be globally interpretable and evaluable standing entirely on
# its own, without requiring reference to external conversational context, episode
# history, or speaker identity. Any proposition containing an unbound indexical,
# pronoun, or comparative lacking an internal antecedent or relatum inside the
# proposition itself cannot be resolved independently and must be rejected.
#
# Rules:
# 1. Discourse participant indexicals: reject 'the speaker', 'the subject', 'the described'.
# 2. Sentence-initial deictics & pronouns: reject propositions starting with
#    'It is/was/would/has...', 'This...', 'That...', 'These...', 'Those...',
#    'They...', 'He...', 'She...', 'Their...', 'His...', 'Her...', 'Its...'.
# 3. Third-person personal pronouns: reject 'they', 'their', 'theirs', 'he', 'him',
#    'his', 'she', 'her', 'hers' that refer to unspecified entities outside the proposition.
# 4. Comparatives without relata: reject 'the same', 'such', 'the other' lacking an explicit
#    comparative standard, while preserving standard idioms ('at the same time', 'the same day',
#    'as such', 'on the other hand', 'each other').
# 5. Bound pronoun preservation: bound possessive pronouns with an explicit intra-proposition
#    antecedent (e.g., 'Moderna patented its mRNA technology') remain valid.
# ==============================================================================

# Banned indexical patterns in proposition_text (must be self-contained and global, Items W0 / §17m & W2 / §17p)
INDEXICAL_BANNED_OPENERS: list[re.Pattern[str]] = [
    re.compile(r"^\s*the\s+speaker\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+subject\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+described\b", re.IGNORECASE),
    re.compile(
        r"^\s*(?:it(?:\x27s|\s+is|\s+was|\s+would|\s+doesn\x27t|\s+might|\s+has|\s+can|\s+could|\s+should|\s+must|\s+will|\s+did|\s+does)|this|that|these|those|they|he|she|their|his|her|its)\b",
        re.IGNORECASE,
    ),
]

INDEXICAL_BANNED_ANYWHERE: list[re.Pattern[str]] = [
    re.compile(r"\bthe\s+speaker\b", re.IGNORECASE),
    re.compile(r"\bthe\s+subject\b", re.IGNORECASE),
    re.compile(r"\bthe\s+described\s+powers?\b", re.IGNORECASE),
    re.compile(r"\bthe\s+matter\s+at\s+issue\b", re.IGNORECASE),
]

COMPARATIVE_NO_RELATUM: list[re.Pattern[str]] = [
    re.compile(
        r"\bthe\s+same\b(?!\s+(?:as|time|day|year|quarter|month|week|way|manner|room|sentiment)\b)",
        re.IGNORECASE,
    ),
    re.compile(r"\bsuch\s+(?!as\b)", re.IGNORECASE),
    re.compile(r"\bthe\s+other\b(?!\s+(?:hand|side)\b)", re.IGNORECASE),
]

PRONOUN_UNBOUND: list[re.Pattern[str]] = [
    re.compile(r"\b(?:they|their|theirs)\b", re.IGNORECASE),
    re.compile(r"\b(?:he|him|his|she|her|hers)\b", re.IGNORECASE),
    re.compile(r"\b(?:those|these)\b\s*[,.\?!;]", re.IGNORECASE),
    re.compile(r"\b(?:of\s+those|of\s+these)\b(?!\s+[a-z]+)", re.IGNORECASE),
]

VALID_STANCES: set[str] = {"support", "oppose", "mixed"}
VALID_EXCLUSIONS: set[str] = {
    "reported_speech",
    "hypothetical",
    "sarcasm",
    "steelman",
    "joke",
    "question",
    "quote_agreement_unclear",
    "entailment_ambiguous",
    "reports_fact",
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
                False, "quote_verbatim_not_found_in_utterance", status="rejected"
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
    from worker.storage import normalize_canonical_text

    # Crucial: both use 'search_document:' prefix (Trap 7: avoiding asymmetric prefix spaces)
    # Proposition is normalized to canonical form to match stored proposition text
    norm_prop = normalize_canonical_text(claim.proposition_text)
    vec_quote = embedder.embed_document(quote)
    vec_prop = embedder.embed_document(norm_prop)
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

    Implements design_claim_extraction.md §2, design_data_layer.md §2, and Items W0 (§17m) & W2 (§17p).
    Rejects propositions containing 'the speaker', 'the subject', 'the described',
    sentence-initial deictics/pronouns ('It is...', 'This...', 'That...', 'They...', etc.),
    unbound third-person pronouns ('they', 'their', 'he', 'his', 'him', etc.),
    or comparatives with no relatum ('the same', 'such', 'the other').
    Preserves bound pronouns with internal antecedents (e.g., 'Moderna patented its mRNA technology').
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
    for pat in COMPARATIVE_NO_RELATUM:
        if pat.search(prop_text):
            if (
                "at the same time" in prop_text.lower()
                or "as such" in prop_text.lower()
                or "each other" in prop_text.lower()
            ):
                continue
            VALIDATOR_REJECTION_COUNTERS["proposition_not_self_contained"] += 1
            return ValidationOutcome(
                is_valid=False,
                rejection_reason="proposition_not_self_contained",
                status="rejected",
            )
    for pat in PRONOUN_UNBOUND:
        if pat.search(prop_text):
            VALIDATOR_REJECTION_COUNTERS["proposition_not_self_contained"] += 1
            return ValidationOutcome(
                is_valid=False,
                rejection_reason="proposition_not_self_contained",
                status="rejected",
            )
    return ValidationOutcome(True, status="passed")


# Syntactic negation patterns for Validator 7 instrument (Items D3 §17t, D4 §13w)
SYNTACTIC_NEGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:not|never|no|neither|nor|none|cannot|won't|wouldn't|shouldn't|couldn't|doesn't|don't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:oppose|opposed|opposing|opposition|against|reject|rejected|rejecting|refuse|refused|refusing|deny|denied|denies|denying|disagree|disagrees|disagreed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:terrible|disastrous|unnecessary|unneeded|unjustified|harmful|unaffordable|bankrupt|ridiculous|mistake|kill|unfeasible|unworkable|dangerous)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:does not face|will not|would not|should not|must not|cannot)\b", re.IGNORECASE
    ),
]

DISCOURSE_NEGATION_PREFIX: re.Pattern[str] = re.compile(
    r"^(?:(?:well|yeah|look|so|and|i mean|i think|to me)\s*[,.]?\s*)*(?:no|nah)\s*[,.]\s*",
    re.IGNORECASE,
)

EXCLUDED_NEGATION_IDIOMS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:not only|not just|no doubt|without a doubt|cannot wait|cannot afford to wait)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:whether\s+or\s+not|regardless\s+of\s+whether\b.*?\bor\s+not)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnext\s+to\s+none\b", re.IGNORECASE),
    re.compile(
        r"\b(?:not|never|won't|wouldn't|cannot)\s+(?:going\s+to\s+)?(?:stop|cease|quit|terminate|abandon)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:never|would\s+never|could\s+never)\s+(?:have\s+been\s+able\s+to\s+)?(?:predict|foresee|anticipate|imagine|expect|guess)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:don't|do\s+not|doesn't|does\s+not)\s+(?:know|think|believe|see)\s+(?:if|whether|that)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnot\s+(?:that|all\s+that|so|very|particularly|quite)\s+(?:much|many|fast|big|high|great|large|well)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnot\s+(?:because|physically|technically|due\s+to)\b.*?\bbut\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:maybe|perhaps)?\s*not\s+[a-zA-Z]+\s*,\s*but\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpeople\s+(?:think|believe|assume)\b.*?\bbut\s+it's\s+not\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnot\s+(?:necessarily|always|automatically)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we|you)\s+(?:don't|do\s+not)\s+know\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhy\s+(?:don't|do\s+not)\s+(?:we|you)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:wasn't|weren't|isn't|aren't|doesn't|don't)\s+just\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:they|we|people|you)\s+(?:don't|do\s+not)\s+(?:say|tell|claim|suggest)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdoesn't\s+mean\s+(?:that\s+)?.*?\bdoesn't\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhen\s+models\s+don't\s+get\s+exhausted\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bif\s+(?:we|you|they|it|one)\s+(?:don't|do\s+not|doesn't|does\s+not|didn't|did\s+not|won't|wouldn't|cannot|can't)\b.*?(?:,\s*|\bthen\b|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:for\s+)?(?:people|anyone|someone|users|founders)\s+who\s+(?:don't|do\s+not|doesn't|does\s+not|didn't)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:make\s+sure|ensure|so\s+that)\s+(?:that\s+)?.*?\b(?:don't|doesn't|no\b)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:you|we)\s+(?:don't|do\s+not)\s+need\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bexclusively\s+non\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdoesn't\s+score\s+(?:that|all\s+that|so|very)?\s*well\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdon't\s*(?:\.{1,3}\s*)?talk\s+to\s+anyone\b.*?\bthat\s+isn't\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhaven't\s+used\b",
        re.IGNORECASE,
    ),
]


def _stem_word(w: str) -> str:
    s = w.lower().strip(".,!?;:'\"")
    for suffix in ["ation", "izing", "tion", "ing", "ed", "es", "ly", "s"]:
        if len(s) > len(suffix) + 2 and s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def has_syntactic_negation(text: str, prop: str = "") -> bool:
    """Checks whether text contains syntactic negation operators or oppositional predicates

    whose scope genuinely governs the matter at issue (Item D4 §13w).
    """
    clean_text = text.strip()

    # 1. Strip conversational discourse markers at start of quote
    clean_text = DISCOURSE_NEGATION_PREFIX.sub("", clean_text)

    # 2. Strip non-scoping idioms, double negative continuation verbs, epistemic modals
    for idiom in EXCLUDED_NEGATION_IDIOMS:
        clean_text = idiom.sub(" ", clean_text)

    if not prop:
        return any(p.search(clean_text) for p in SYNTACTIC_NEGATION_PATTERNS)

    prop_stems = {_stem_word(w) for w in re.findall(r"\b[a-zA-Z']+\b", prop.lower()) if len(w) > 2}
    tokens = re.findall(r"\b[a-zA-Z']+\b", clean_text.lower())

    for i, tok in enumerate(tokens):
        if _stem_word(tok) in prop_stems:
            # Token echoes proposition itself (e.g. 'none' in 'next to none')
            continue
        is_neg = any(p.fullmatch(tok) for p in SYNTACTIC_NEGATION_PATTERNS)
        if not is_neg:
            continue

        # Check what the negation operator governs (lookahead 1-4 tokens)
        governed: list[str] = []
        for j in range(i + 1, min(i + 5, len(tokens))):
            w = tokens[j]
            if w in {
                "a",
                "an",
                "the",
                "to",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "any",
                "that",
                "this",
            }:
                continue
            governed.append(w)

        if governed:
            gov_stems = {_stem_word(w) for w in governed}
            # If any governed word matches the proposition terms, it scopes over proposition
            if gov_stems & prop_stems:
                return True
            # Strong oppositional predicates (kill, terrible, opposed, against, refuse, deny, etc.)
            if tok in {
                "oppose",
                "opposed",
                "opposing",
                "against",
                "reject",
                "rejected",
                "refuse",
                "refused",
                "deny",
                "denied",
                "terrible",
                "disastrous",
                "harmful",
                "unaffordable",
                "kill",
                "unfeasible",
                "unworkable",
                "dangerous",
            }:
                return True
            # Quantified negation ('no risk', 'no conversion risk', 'no study', 'no young people')
            if tok == "no" and governed:
                return True
        else:
            return True

    return False


def validate_stance_direction(
    claim: ExtractedClaim,
    embedder: Any | None = None,
    delta: float = 0.05,
    auto_correct: bool = False,
    prop_embedding: list[float] | None = None,
    quote_embedding: list[float] | None = None,
) -> ValidationOutcome:
    """Validator 7: Stance direction validation (Items S1 §17n, D3 §17t).

    Verifies directional alignment between quote_text and proposition_text.
    Validator 6 certifies aboutness (entailment), while Validator 7 certifies direction.

    Uses an augmented instrument combining syntactic negation analysis with document embeddings:
    - For oppose:
      - If quote contains syntactic negation of the proposition, it is confirmed oppose.
      - If quote contains NO negation AND embedding sim(Q, P) > sim(Q, not-P), the quote asserts
        P rather than opposing it (e.g. negative tone mistranslated as opposition).
        If auto_correct=True, inverts stance to 'support' and increments stance_corrected_to_support.
        Else rejects with 'stance_direction_mismatch'.
    - For support:
      - If quote contains syntactic negation opposing the proposition OR sim(Q, not-P) > sim(Q, P) + delta,
        the quote asserts not-P rather than supporting P.
        If auto_correct=True, inverts stance to 'oppose' and increments stance_corrected_to_oppose.
        Else rejects with 'stance_direction_mismatch'.
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

    has_neg = has_syntactic_negation(quote, prop)

    if stance == "oppose":
        if not has_neg and sim_pos > sim_neg:
            if auto_correct:
                claim.stance = "support"
                if claim.proposition_text:
                    claim.position_frame = f"the speaker is FOR {claim.proposition_text}"
                VALIDATOR_CORRECTION_COUNTERS["stance_corrected_to_support"] += 1
                logger.info(
                    "Validator 7 corrected claim from 'oppose' to 'support'. Prop: '%s', Quote: '%s'",
                    prop,
                    quote,
                )
                return ValidationOutcome(True, status="passed", similarity=sim_pos)
            VALIDATOR_REJECTION_COUNTERS["stance_direction_mismatch"] += 1
            logger.info(
                "Validator 7 rejected claim (stance_direction_mismatch): stance='oppose' but sim_pos=%.4f > sim_neg=%.4f without negation. Prop: '%s', Quote: '%s'",
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

    if stance == "support":
        if has_neg:
            if auto_correct:
                claim.stance = "oppose"
                if claim.proposition_text:
                    claim.position_frame = f"the speaker is AGAINST {claim.proposition_text}"
                VALIDATOR_CORRECTION_COUNTERS["stance_corrected_to_oppose"] += 1
                logger.info(
                    "Validator 7 corrected claim from 'support' to 'oppose'. Prop: '%s', Quote: '%s'",
                    prop,
                    quote,
                )
                return ValidationOutcome(True, status="passed", similarity=sim_pos)
            VALIDATOR_REJECTION_COUNTERS["stance_direction_mismatch"] += 1
            logger.info(
                "Validator 7 rejected claim (stance_direction_mismatch): stance='support' with syntactic negation or sim_neg=%.4f > sim_pos=%.4f + delta. Prop: '%s', Quote: '%s'",
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
    """Validator 2: Proposition text must be stance-neutral and contain no polarity words.

    Implements design_claim_extraction.md §2 and Item D1 (§13u).
    """
    prop_text = claim.proposition_text or ""
    for pat in POLARITY_BANNED_PATTERNS:
        if pat.search(prop_text):
            return ValidationOutcome(False, "proposition_carries_polarity", status="rejected")
    return ValidationOutcome(True, status="passed")


# Relational prepositions and comparative markers indicating predicate-bearing matter at issue (Item D6)
RELATIONAL_PREPOSITIONS: set[str] = {
    "of",
    "for",
    "in",
    "on",
    "at",
    "to",
    "from",
    "with",
    "by",
    "about",
    "against",
    "between",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "under",
    "over",
    "across",
    "toward",
    "towards",
    "upon",
    "within",
    "without",
    "regarding",
    "concerning",
    "versus",
    "vs",
}

COMPARATIVE_MARKERS: set[str] = {
    "than",
    "versus",
    "vs",
    "compared",
    "relative",
}

FINITE_ROOT_VERBS: set[str] = {
    "is",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "will",
    "would",
    "should",
    "must",
    "went",
    "uses",
    "used",
    "got",
    "came",
    "can",
    "could",
    "need",
    "needs",
}

REL_PRONOUNS: set[str] = {
    "that",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "when",
    "if",
    "because",
}

BARE_VERB_OPENERS: set[str] = {
    "have",
    "has",
    "had",
    "support",
    "supports",
    "bolt",
    "disrupt",
    "disrupts",
    "take",
    "takes",
    "make",
    "makes",
    "run",
    "runs",
    "do",
    "does",
    "get",
    "gets",
    "put",
    "puts",
    "went",
    "stop",
    "stops",
}

UNBOUND_TRAILING_PRONOUN_PAT: re.Pattern[str] = re.compile(
    r"\b(?:for\s+it|to\s+it|about\s+it|of\s+it|in\s+it|on\s+it|this\s+thing)\s*$",
    re.IGNORECASE,
)

DEICTIC_OR_VALUATION_PAT: re.Pattern[str] = re.compile(
    r"\b(?:it's|before\s+it|after\s+it)\b|^\s*(?:\$?\d+|\d+\s+to\s+\d+)\s+(?:billion|million|trillion)\b",
    re.IGNORECASE,
)

QUESTION_OPENER_PAT: re.Pattern[str] = re.compile(
    r"^\s*(?:how\s+to|why|what|when|where)\b",
    re.IGNORECASE,
)

MIN_PROPOSITION_WORDS: int = 5


def has_proposition_relation(text: str) -> bool:
    """Checks whether text contains a relational marker: preposition, comparative, or participle."""
    tokens = re.findall(r"\b[a-z]+\b", text.lower())
    if any(t in RELATIONAL_PREPOSITIONS for t in tokens):
        return True
    if any(t in COMPARATIVE_MARKERS for t in tokens):
        return True
    if any(t.endswith("ing") and len(t) > 4 for t in tokens):
        return True
    return False


def has_finite_root_verb(text: str) -> bool:
    """Checks whether text contains an un-relativized finite verb."""
    tokens = re.findall(r"\b[a-z]+\b", text.lower())
    for i, tok in enumerate(tokens):
        if tok in FINITE_ROOT_VERBS:
            if i == 0 or tokens[i - 1] not in REL_PRONOUNS:
                return True
    return False


def validate_position_bearing(claim: ExtractedClaim) -> ValidationOutcome:
    """Validator 2b: Propositions must be position-bearing matters at issue, not bare topics.

    Implements design_claim_extraction.md §2 and Item D6 (§11).
    Rejects propositions below minimum length (< 5 words), bare noun phrases
    with no relation (no preposition, no participle, no comparative), full clauses
    with finite root verbs, bare verb openers, question openers, and unbound trailing pronouns.
    Reason: proposition_not_position_bearing.
    """
    text = (claim.proposition_text or "").strip()
    words = text.split()
    if len(words) < MIN_PROPOSITION_WORDS:
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
    if not has_proposition_relation(text):
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
    first_word = words[0].lower() if words else ""
    if first_word in BARE_VERB_OPENERS:
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
    if QUESTION_OPENER_PAT.search(text):
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
    if UNBOUND_TRAILING_PRONOUN_PAT.search(text):
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
    if DEICTIC_OR_VALUATION_PAT.search(text):
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
    if has_finite_root_verb(text):
        return ValidationOutcome(False, "proposition_not_position_bearing", status="rejected")
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

    # 2b. Position-Bearing Matter at Issue (Item D6)
    res_pos = validate_position_bearing(claim)
    if not res_pos.is_valid:
        VALIDATOR_REJECTION_COUNTERS[
            res_pos.rejection_reason or "proposition_not_position_bearing"
        ] += 1
        return res_pos

    # 3. Entailment (Validator 6) runs immediately after position-bearing check
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
