"""Word-level dual-pass transcription reconciler and dropped-negation detector.

Implements design_source_acquisition.md §5.3 and agent_execution_guide.md §7 (U3).
"""

import difflib
from dataclasses import dataclass
from typing import Any

NEGATION_CUES: frozenset[str] = frozenset([
    "not",
    "n't",
    "never",
    "no",
    "none",
    "without",
    "hardly",
    "barely",
    "fails to",
    "rather than",
    "unless",
    "neither",
    "nor",
    "dont",
    "don't",
    "doesnt",
    "doesn't",
    "didnt",
    "didn't",
    "wont",
    "won't",
    "cant",
    "can't",
    "cannot",
    "shouldnt",
    "shouldn't",
    "wouldnt",
    "wouldn't",
    "couldnt",
    "couldn't",
    "isnt",
    "isn't",
    "arent",
    "aren't",
    "wasnt",
    "wasn't",
    "werent",
    "weren't",
])


@dataclass
class WordTimestamp:
    word: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "confidence": self.confidence,
        }


@dataclass
class TranscriptionPassResult:
    text: str
    words: list[WordTimestamp]
    beam_size: int
    temperature: float


@dataclass
class ReconciliationResult:
    text_verbatim: str
    words: list[WordTimestamp]
    dual_pass_agreement: bool
    negation_uncertain: bool
    differing_regions_count: int


def normalize_word(w: str) -> str:
    """Normalizes word for alignment comparison by stripping punctuation and lowercasing."""
    return "".join(c for c in w.lower() if c.isalnum() or c == "'")


def is_negation_cue(phrase: str) -> bool:
    norm = normalize_word(phrase)
    if norm in NEGATION_CUES:
        return True
    for cue in NEGATION_CUES:
        if " " in cue and cue in phrase.lower():
            return True
        if norm == normalize_word(cue):
            return True
    return False


def reconcile_dual_pass(
    pass1: TranscriptionPassResult,
    pass2: TranscriptionPassResult,
    negation_window_words: int = 3,
) -> ReconciliationResult:
    """Aligns pass1 and pass2 word sequences using difflib.SequenceMatcher.

    For each differing region, checks whether any negation cue falls inside it
    or within `negation_window_words` words on either side.

    Returns pass1 text/words with dual_pass_agreement and negation_uncertain flags.
    """
    words1 = [w.word for w in pass1.words]
    words2 = [w.word for w in pass2.words]

    norm1 = [normalize_word(w) for w in words1]
    norm2 = [normalize_word(w) for w in words2]

    matcher = difflib.SequenceMatcher(None, norm1, norm2)
    opcodes = matcher.get_opcodes()

    differing_regions = 0
    negation_uncertain = False

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue

        differing_regions += 1

        # Check differing region in pass1 and pass2, plus context window
        start1 = max(0, i1 - negation_window_words)
        end1 = min(len(words1), i2 + negation_window_words)
        span_words_1 = words1[start1:end1]
        text_span_1 = " ".join(span_words_1).lower()

        start2 = max(0, j1 - negation_window_words)
        end2 = min(len(words2), j2 + negation_window_words)
        span_words_2 = words2[start2:end2]
        text_span_2 = " ".join(span_words_2).lower()

        # Check for negation cues in span
        touches_cue = False
        for w in span_words_1 + span_words_2:
            if is_negation_cue(w):
                touches_cue = True
                break

        if not touches_cue:
            for cue in NEGATION_CUES:
                if cue in text_span_1 or cue in text_span_2:
                    touches_cue = True
                    break

        if touches_cue:
            negation_uncertain = True

    dual_pass_agreement = (differing_regions == 0)

    return ReconciliationResult(
        text_verbatim=pass1.text,
        words=pass1.words,
        dual_pass_agreement=dual_pass_agreement,
        negation_uncertain=negation_uncertain,
        differing_regions_count=differing_regions,
    )
