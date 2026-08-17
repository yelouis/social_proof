"""Transcription engine, VAD gate, and audio disposal pipeline.

Implements design_source_acquisition.md §5.2-§5.3 and agent_execution_guide.md §7 (U3).
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from worker.entities import IngestJob, Source, Utterance
from worker.storage import Storage, compute_utterance_id
from worker.transcribe.reconciler import (
    ReconciliationResult,
    TranscriptionPassResult,
    WordTimestamp,
    reconcile_dual_pass,
)


@dataclass
class AudioSegment:
    start_ms: int
    end_ms: int
    energy: float  # 0.0 to 1.0; 0.0 means complete silence / no speech activity


class TranscriptionEngine(Protocol):
    def run_pass(
        self,
        audio_path: Path,
        segment: AudioSegment,
        beam_size: int,
        temperature: float,
    ) -> TranscriptionPassResult:
        ...


class MockTranscriptionEngine:
    """Mock/deterministic transcription engine for testing dual-pass and VAD."""

    def __init__(
        self,
        pass1_script: list[tuple[AudioSegment, str]] | None = None,
        pass2_script: list[tuple[AudioSegment, str]] | None = None,
    ) -> None:
        self.pass1_script = pass1_script or []
        self.pass2_script = pass2_script or []

    def run_pass(
        self,
        audio_path: Path,
        segment: AudioSegment,
        beam_size: int,
        temperature: float,
    ) -> TranscriptionPassResult:
        script = self.pass1_script if (temperature == 0.0 and beam_size == 5) else self.pass2_script
        matched_text = ""
        for seg, text in script:
            if seg.start_ms == segment.start_ms and seg.end_ms == segment.end_ms:
                matched_text = text
                break

        if not matched_text and script:
            matched_text = script[0][1]

        # Generate word timestamps
        words_raw = matched_text.split()
        word_objs: list[WordTimestamp] = []
        if words_raw:
            duration_per_word = max(10, (segment.end_ms - segment.start_ms) // len(words_raw))
            for i, w in enumerate(words_raw):
                w_start = segment.start_ms + i * duration_per_word
                w_end = min(segment.end_ms, w_start + duration_per_word)
                word_objs.append(WordTimestamp(word=w, start_ms=w_start, end_ms=w_end, confidence=0.98))

        return TranscriptionPassResult(
            text=matched_text,
            words=word_objs,
            beam_size=beam_size,
            temperature=temperature,
        )


class TranscriptionPipeline:
    """End-to-end VAD gating, dual-pass transcription, Parquet artifact storage, and audio disposal."""

    def __init__(
        self,
        storage: Storage,
        engine: TranscriptionEngine | None = None,
        vad_energy_threshold: float = 0.05,
    ) -> None:
        self.storage = storage
        self.engine = engine or MockTranscriptionEngine()
        self.vad_energy_threshold = vad_energy_threshold

    def vad_filter(self, segments: list[AudioSegment]) -> list[AudioSegment]:
        """VAD gate: Drops segments with no corresponding audio energy.

        A segment over a silent span is a hallucination, full stop.
        """
        return [s for s in segments if s.energy >= self.vad_energy_threshold]

    def transcribe_source(
        self,
        source: Source,
        subject_id: str,
        audio_path: Path,
        segments: list[AudioSegment],
        job: IngestJob | None = None,
        force_error: bool = False,
    ) -> list[Utterance]:
        """Runs VAD, dual-pass transcription, word reconciler, artifact persistence,

        and deletes audio only on successful completion.
        """
        start_wall_time = time.perf_counter()
        created_utterances: list[Utterance] = []

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

        try:
            # 1. VAD Gate
            valid_segments = self.vad_filter(segments)

            total_audio_duration_ms = 0

            # 2. Transcribe valid segments
            for seg in valid_segments:
                seg_duration = seg.end_ms - seg.start_ms
                total_audio_duration_ms += seg_duration

                # Pass 1: beam_size = 5, temp = 0.0
                pass1 = self.engine.run_pass(audio_path, seg, beam_size=5, temperature=0.0)

                # Pass 2: beam_size = 1, temp = 0.2
                pass2 = self.engine.run_pass(audio_path, seg, beam_size=1, temperature=0.2)

                # Reconcile at word level with SequenceMatcher
                reconciliation: ReconciliationResult = reconcile_dual_pass(pass1, pass2)

                if not reconciliation.text_verbatim.strip():
                    continue

                # 3. Persist word timestamps as Parquet to artifact store
                words_dict = [w.to_dict() for w in reconciliation.words]
                parquet_hash = self.storage.artifacts.put_word_timestamps(words_dict)

                # 4. Create Utterance
                utt_id = compute_utterance_id(source.source_id, seg.start_ms, reconciliation.text_verbatim)
                utt = Utterance(
                    utterance_id=utt_id,
                    source_id=source.source_id,
                    subject_id=subject_id,
                    text_verbatim=reconciliation.text_verbatim,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    speaker_label="speaker_0",
                    attribution_confidence="high",
                    attribution_method="single_speaker_baseline",
                    word_timestamps_ref=parquet_hash,
                    language="en",
                    transcription_pass_count=2,
                    dual_pass_agreement=reconciliation.dual_pass_agreement,
                    negation_uncertain=reconciliation.negation_uncertain,
                )
                self.storage.insert_utterance(utt)
                created_utterances.append(utt)

            if force_error:
                raise RuntimeError("Simulated transcription failure")

            # 5. Measure throughput
            end_wall_time = time.perf_counter()
            wall_minutes = max(0.001, (end_wall_time - start_wall_time) / 60.0)
            audio_minutes = total_audio_duration_ms / 60000.0
            throughput = audio_minutes / wall_minutes

            if job:
                job.counts["audio_minutes"] = int(audio_minutes)
                job.counts["throughput_ratio"] = int(throughput)
                job.status = "completed"

            # 6. Audio Disposal (Issue 003 Option C) - ONLY on success
            if audio_path.exists():
                audio_path.unlink()
            source.audio_deleted_at = datetime.now(UTC).isoformat()
            self.storage.insert_source(source)

            return created_utterances

        except Exception as e:
            # If transcription raises an error, audio is preserved
            if job:
                job.errors.append(str(e))
                job.status = "failed"
            raise e
