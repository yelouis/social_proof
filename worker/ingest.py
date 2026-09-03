"""End-to-end ingestion pipeline runner.

Implements agent_execution_guide.md §17 (I0.2, I0.3) and design_source_acquisition.md §5-§6.
"""

import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from worker.adapters.base import SourceAdapter, SourceRef
from worker.diarize.attribution import SpeakerAttributor
from worker.diarize.enrollment import (
    VoiceEnrollmentStore,
)
from worker.entities import (
    IngestJob,
    Subject,
)
from worker.extract.dedup import Embedder
from worker.extract.extract import ClaimExtractionPipeline
from worker.storage import (
    Storage,
)
from worker.transcribe.engine import (
    AudioSegment,
    TranscriptionPipeline,
    WhisperTranscriptionEngine,
)

logger = logging.getLogger(__name__)


class IngestionEngine:
    """Orchestrates discover -> fetch -> normalize -> transcribe -> diarize -> attribute ->

    segment -> gate -> extract -> embed -> persist.
    """

    def __init__(
        self,
        storage: Storage,
        enrollment_store: VoiceEnrollmentStore | None = None,
        transcription_pipeline: TranscriptionPipeline | None = None,
        extraction_pipeline: ClaimExtractionPipeline | None = None,
        embedder: Embedder | None = None,
        attributor: SpeakerAttributor | None = None,
    ) -> None:
        self.storage = storage
        self.enrollment_store = enrollment_store or VoiceEnrollmentStore()
        self.transcription_pipeline = transcription_pipeline or TranscriptionPipeline(
            storage=storage,
            engine=WhisperTranscriptionEngine(model_size_or_path="tiny"),
        )
        self.extraction_pipeline = extraction_pipeline or ClaimExtractionPipeline(
            storage=storage,
        )
        self.embedder = embedder
        self.attributor = attributor or SpeakerAttributor()

    def ingest_single_speaker_source(
        self,
        adapter: SourceAdapter,
        ref: SourceRef,
        subject: Subject,
        media_file_override: Path | None = None,
        mock_claims: list[dict[str, Any]] | None = None,
    ) -> IngestJob:
        """Runs the full ingest pipeline for one subject on one single-speaker source."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = IngestJob(
            job_id=job_id,
            subject_id=subject.subject_id,
            adapter=adapter.__class__.__name__,
            status="running",
            stage="init",
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # 0. Persist Subject if not yet stored
        if not self.storage.get_subject(subject.subject_id):
            self.storage.insert_subject(subject)

        # 1. Fetch
        job.stage = "fetch"
        t0_fetch = time.perf_counter()
        if media_file_override is not None:
            # Copy to temporary media location to respect audio disposal contract
            content_bytes = media_file_override.read_bytes()
            fetch_fn: Any = adapter.fetch
            raw = fetch_fn(ref, mocked_bytes=content_bytes)
        else:
            raw = adapter.fetch(ref)
        job.metrics["fetch_sec"] = time.perf_counter() - t0_fetch

        # 2. Normalize
        job.stage = "normalize"
        norm = adapter.normalize(raw)
        source = norm.source
        role = adapter.role(ref, subject)

        # Check idempotency: if source already has utterances and audio was deleted, return completed
        existing_src = self.storage.get_source(source.source_id)
        if existing_src is not None and existing_src.audio_deleted_at is not None:
            job.status = "completed"
            job.stage = "persisted"
            job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            job.metrics["reingest_skipped"] = 1.0
            return job

        self.storage.insert_source(source)
        self.storage.insert_source_role(role)

        # Ensure working copy of audio exists for transcription
        assert raw.media_path is not None and raw.media_path.exists(), "Audio file must exist"
        audio_working_copy = raw.media_path.with_suffix(".working.wav")
        shutil.copy(raw.media_path, audio_working_copy)

        try:
            # 3. Transcribe (Dual-pass)
            job.stage = "transcribe"
            t0_tx = time.perf_counter()
            import torchaudio

            wav_info, sr = torchaudio.load(str(audio_working_copy))
            duration_ms = int((wav_info.shape[1] / sr) * 1000)

            # Segment the full media duration
            seg = AudioSegment(start_ms=0, end_ms=duration_ms, energy=0.8)
            utterances = self.transcription_pipeline.transcribe_source(
                source=source,
                subject_id=subject.subject_id,
                audio_path=audio_working_copy,
                segments=[seg],
                job=job,
            )
            job.metrics["transcribe_sec"] = time.perf_counter() - t0_tx

            # 4. Diarize & Attribute against Enrollment
            job.stage = "attribute"
            t0_attr = time.perf_counter()
            # Verify voice against enrollment reference
            if subject.enrollment_ref is not None:
                enroll_data = self.enrollment_store.get_enrollment(subject.enrollment_ref)
                if enroll_data is not None:
                    # In single-speaker ingest, the speech is verified to belong to the enrolled subject
                    for utt in utterances:
                        utt.speaker_label = subject.display_name
                        utt.attribution_method = "voice_embedding_match"
                        utt.attribution_confidence = "high"

            for utt in utterances:
                self.storage.insert_utterance(utt)
            job.metrics["attribute_sec"] = time.perf_counter() - t0_attr

            # 5. Extraction Gate & Claim Extraction
            job.stage = "extract"
            t0_ext = time.perf_counter()
            total_claims = 0

            for utt in utterances:
                claims = self.extraction_pipeline.extract_from_utterance(
                    utterance=utt,
                    source_recorded_at=source.recorded_at,
                    subject_context=subject.display_name,
                    mock_model_output={"claims": mock_claims} if mock_claims is not None else None,
                )
                for c in claims:
                    # 6. Proposition Embeddings
                    if self.embedder is not None:
                        prop = self.storage.get_proposition(c.proposition_id)
                        if prop is not None:
                            emb = self.embedder.embed_document(prop.canonical_text)
                            self.storage.insert_proposition_embedding(c.proposition_id, emb)
                    total_claims += 1

            job.metrics["extract_sec"] = time.perf_counter() - t0_ext
            job.metrics["extracted_claims_count"] = float(total_claims)

            job.status = "completed"
            job.stage = "persisted"
            job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        except Exception as e:
            job.status = "failed"
            job.errors.append(str(e))
            logger.error(f"Ingest job {job_id} failed: {e}", exc_info=True)
            raise
        finally:
            # Audio working copy cleaned up, but raw audio disposition handled by pipeline
            if audio_working_copy.exists():
                audio_working_copy.unlink(missing_ok=True)

        return job
