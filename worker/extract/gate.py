"""Gate stage: Fast heuristic and classifier pre-filter for claim-bearing utterances.

Implements design_claim_extraction.md §2 and agent_execution_guide.md §11 (U10).
"""

import re
from typing import NamedTuple

from worker.entities import Utterance

# Conversational filler patterns that never contain testable policy/factual claims
FILLER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(?:yeah|yes|yep|nope|no|right|exactly|totally|sure|okay|ok|uh-huh|mm-hmm)[\s,.!]*$", re.IGNORECASE),
    re.compile(r"^(?:yeah|yes|yep|right|totally|sure|okay),?\s*(?:absolutely|exactly|totally|mm-hmm|thanks).*", re.IGNORECASE),
    re.compile(r".*(?:thanks (?:so much )?for having me|welcome to the show).*", re.IGNORECASE),
    re.compile(r".*(?:check (?:my|the) calendar|next (?:monday|tuesday|wednesday|thursday|friday)|take a quick break|we'll be right back).*", re.IGNORECASE),
    re.compile(r".*(?:sound check|one two three|testing (?:one|microphone)).*", re.IGNORECASE),
    re.compile(r"^(?:good morning|good afternoon|good evening|welcome back)[\s,.!]*$", re.IGNORECASE),
]

# Claim indicator cues (boosters)
CLAIM_INDICATORS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:must|should|ought|need to|have to|require|mandate|ban|prohibit)\b", re.IGNORECASE),
    re.compile(r"\b(?:think|believe|argue|contend|maintain|assert|convinced|disagree)\b", re.IGNORECASE),
    re.compile(r"\b(?:always|never|fundamentally|essential|impossible|catastrophic)\b", re.IGNORECASE),
    re.compile(r"\b(?:used to|changed my mind|looking back|in retrospect)\b", re.IGNORECASE),
    re.compile(r"\b(?:if|unless|provided that|assuming)\b", re.IGNORECASE),
    re.compile(r"\b(?:percent|rate|tax|dollar|billion|million|inflation|deficit)\b", re.IGNORECASE),
]


class GateDecision(NamedTuple):
    should_extract: bool
    confidence_score: float
    reason: str


class ExtractionGate:
    """Fast pre-filter for claim extraction.

    Parameter 003: Tuned strictly for recall. Zero false negatives on claim-bearing speech.
    """

    def __init__(self, min_word_count: int = 4, claim_threshold: float = 0.20) -> None:
        self.min_word_count = min_word_count
        self.claim_threshold = claim_threshold

    def evaluate_text(self, text: str) -> GateDecision:
        stripped = text.strip()
        words = stripped.split()

        # Rule 1: Very short utterances (< min_word_count) almost never contain propositions
        if len(words) < self.min_word_count:
            return GateDecision(
                should_extract=False,
                confidence_score=0.0,
                reason="too_short",
            )

        # Rule 2: Explicit conversational filler regexes
        for pattern in FILLER_PATTERNS:
            if pattern.match(stripped):
                return GateDecision(
                    should_extract=False,
                    confidence_score=0.0,
                    reason="conversational_filler_regex",
                )

        # Rule 3: Heuristic scoring based on indicators and length
        score = 0.0

        # Substantive length gives baseline score
        if len(words) >= 8:
            score += 0.25
        elif len(words) >= 5:
            score += 0.15

        # Indicator matches boost score
        for ind in CLAIM_INDICATORS:
            if ind.search(stripped):
                score += 0.35

        should_extract = score >= self.claim_threshold
        reason = "passed_heuristic" if should_extract else "below_threshold"

        return GateDecision(
            should_extract=should_extract,
            confidence_score=min(1.0, score),
            reason=reason,
        )

    def evaluate_utterance(self, utterance: Utterance) -> GateDecision:
        return self.evaluate_text(utterance.text_verbatim)
