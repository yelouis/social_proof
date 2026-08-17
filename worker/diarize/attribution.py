"""Speaker attribution engine matching diarized turns to enrollment references.

Implements Parameter 004 (T_high, T_low) and design_source_acquisition.md §5.4.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class SpeakerTurn:
    speaker_cluster_id: str
    start_ms: int
    end_ms: int
    text: str
    voice_embedding: list[float]  # 256 or 512-dim pyannote/speechbrain embedding


@dataclass
class AttributedTurn:
    turn: SpeakerTurn
    subject_id: str | None
    attribution_confidence: Literal["high", "low", "discard"]
    similarity_score: float
    attribution_method: str = "voice_embedding_match"


class SpeakerAttributor:
    """Attributes speaker turns by cosine similarity against enrollment reference.

    Parameter 004:
    - T_high (default 0.75): High confidence, included in scoring.
    - T_low (default 0.50): Low confidence, stored for review, EXCLUDED from scoring.
    - Below T_low: Discarded from subject's corpus.
    """

    def __init__(self, t_high: float = 0.75, t_low: float = 0.50) -> None:
        self.t_high = t_high
        self.t_low = t_low

    def cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def attribute_turn(
        self,
        turn: SpeakerTurn,
        subject_id: str,
        enrollment_embedding: list[float],
    ) -> AttributedTurn:
        sim = self.cosine_similarity(turn.voice_embedding, enrollment_embedding)

        if sim >= self.t_high:
            confidence: Literal["high", "low", "discard"] = "high"
            assigned_subject = subject_id
        elif sim >= self.t_low:
            confidence = "low"
            assigned_subject = subject_id
        else:
            confidence = "discard"
            assigned_subject = None

        return AttributedTurn(
            turn=turn,
            subject_id=assigned_subject,
            attribution_confidence=confidence,
            similarity_score=sim,
        )


def attribute_speaker_turns(
    turns: list[SpeakerTurn],
    subject_id: str,
    enrollment_embedding: list[float],
    attributor: SpeakerAttributor | None = None,
) -> list[AttributedTurn]:
    att = attributor or SpeakerAttributor()
    return [att.attribute_turn(turn, subject_id, enrollment_embedding) for turn in turns]
