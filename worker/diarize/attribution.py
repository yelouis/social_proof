"""Speaker attribution engine matching diarized turns to enrollment references.

Implements Parameter 004 (T_high, T_low) and design_source_acquisition.md §5.4.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pyannote.audio import Inference, Model, Pipeline


@dataclass
class SpeakerTurn:
    speaker_cluster_id: str
    start_ms: int
    end_ms: int
    text: str
    voice_embedding: list[float]  # 256 or 512-dim pyannote embedding


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


class PyannoteDiarizer:
    """Production speaker diarization and voice embedding wrapper using pyannote.audio.

    Implements design_source_acquisition.md §5.1 and Parameter 004.
    """

    def __init__(
        self,
        use_auth_token: str | None = None,
        embedding_extractor: Any | None = None,
        pipeline_instance: Any | None = None,
    ) -> None:
        self.auth_token = use_auth_token or os.environ.get("HF_TOKEN")
        self.embedding_extractor = embedding_extractor
        self.pipeline_instance = pipeline_instance

    def extract_embedding(self, audio_path: str | Path) -> list[float]:
        """Extracts a 512-dim speaker voice embedding from audio."""
        if self.embedding_extractor is not None:
            emb_res: Any = self.embedding_extractor(str(audio_path))
            return [float(x) for x in emb_res.tolist()]

        model_cls: Any = Model
        model = model_cls.from_pretrained("pyannote/embedding", use_auth_token=self.auth_token)
        if model is None:
            raise RuntimeError("Failed to load pyannote embedding model")
        inference: Any = Inference(model, window="whole")
        raw_emb: Any = inference(str(audio_path))
        data: Any = getattr(raw_emb, "data", raw_emb)
        return [float(x) for x in data.tolist()]

    def diarize(self, audio_path: str | Path) -> list[SpeakerTurn]:
        """Runs pyannote diarization pipeline to segment multi-speaker audio."""
        if self.pipeline_instance is not None:
            res: list[SpeakerTurn] = self.pipeline_instance(str(audio_path))
            return res

        pipeline_cls: Any = Pipeline
        pipeline = pipeline_cls.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=self.auth_token,
        )
        if pipeline is None:
            raise RuntimeError("Failed to load pyannote speaker diarization pipeline")

        diarization: Any = pipeline(str(audio_path))
        turns: list[SpeakerTurn] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append(
                SpeakerTurn(
                    speaker_cluster_id=speaker,
                    start_ms=int(turn.start * 1000),
                    end_ms=int(turn.end * 1000),
                    text="",
                    voice_embedding=[],
                )
            )
        return turns


class MockDiarizer:
    """Mock speaker diarizer for tests and offline development."""

    def __init__(self, turns: list[SpeakerTurn] | None = None) -> None:
        self.turns = turns or []

    def diarize(self, audio_path: str | Path) -> list[SpeakerTurn]:
        return self.turns


def attribute_speaker_turns(
    turns: list[SpeakerTurn],
    subject_id: str,
    enrollment_embedding: list[float],
    attributor: SpeakerAttributor | None = None,
) -> list[AttributedTurn]:
    att = attributor or SpeakerAttributor()
    return [att.attribute_turn(turn, subject_id, enrollment_embedding) for turn in turns]
