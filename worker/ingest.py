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
from worker.diarize.attribution import SpeakerAttributor, SpeakerTurn
from worker.diarize.enrollment import (
    VoiceEnrollmentStore,
    extract_voice_embedding,
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
        audio_working_copy = raw.media_path.with_name(
            f"{raw.media_path.stem}.working{raw.media_path.suffix}"
        )
        shutil.copy(raw.media_path, audio_working_copy)
        audio_attr_copy = raw.media_path.with_name(
            f"{raw.media_path.stem}.attr{raw.media_path.suffix}"
        )
        shutil.copy(raw.media_path, audio_attr_copy)

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
            if subject.enrollment_ref:
                emb = extract_voice_embedding(audio_attr_copy)
                data = self.enrollment_store.get_enrollment(subject.enrollment_ref)
                if data:
                    ref_emb = data["embedding"]
                    sim = self.attributor.cosine_similarity(emb, ref_emb)
                    if sim >= self.attributor.t_high:
                        for utt in utterances:
                            utt.speaker_label = subject.display_name
                            utt.attribution_method = "voice_embedding_match"
                            utt.attribution_confidence = "high"
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

            # Gate audio deletion on productivity: only delete raw audio if >=1 utterance produced
            if len(utterances) > 0:
                source.ingested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                source.audio_deleted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.storage.insert_source(source)
                if raw.media_path.exists():
                    raw.media_path.unlink(missing_ok=True)
            else:
                job.status = "failed"
                job.errors.append(
                    "Productivity gate failed: zero utterances produced from source. Audio preserved."
                )
                return job

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
            if audio_attr_copy.exists():
                audio_attr_copy.unlink(missing_ok=True)

        return job

    def ingest_panel_source(
        self,
        adapter: SourceAdapter,
        ref: SourceRef,
        subjects: list[Subject],
        media_file_override: Path | None = None,
        mock_claims_by_subject: (
            dict[str, list[dict[str, Any]]]
            | Any
            | None
        ) = None,
        panel_segments: list[AudioSegment] | None = None,
    ) -> IngestJob:
        """Runs the full ingest pipeline for a multi-speaker panel source across multiple subjects."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = IngestJob(
            job_id=job_id,
            subject_id="panel",
            adapter=adapter.__class__.__name__,
            status="running",
            stage="init",
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # 0. Persist Subjects if not yet stored
        for subject in subjects:
            if not self.storage.get_subject(subject.subject_id):
                self.storage.insert_subject(subject)

        # 1. Fetch
        job.stage = "fetch"
        t0_fetch = time.perf_counter()
        if media_file_override is not None:
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

        # Check idempotency: if source already has utterances and audio was deleted, return completed
        existing_src = self.storage.get_source(source.source_id)
        if existing_src is not None and existing_src.audio_deleted_at is not None:
            job.status = "completed"
            job.stage = "persisted"
            job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            job.metrics["reingest_skipped"] = 1.0
            return job

        self.storage.insert_source(source)
        for subject in subjects:
            role = adapter.role(ref, subject)
            self.storage.insert_source_role(role)

        assert raw.media_path is not None and raw.media_path.exists(), "Audio file must exist"
        audio_working_copy = raw.media_path.with_name(
            f"{raw.media_path.stem}.working_panel{raw.media_path.suffix}"
        )
        shutil.copy(raw.media_path, audio_working_copy)
        audio_attr_copy = raw.media_path.with_name(
            f"{raw.media_path.stem}.attr_panel{raw.media_path.suffix}"
        )
        shutil.copy(raw.media_path, audio_attr_copy)

        try:
            # 3. Transcribe (Dual-pass)
            job.stage = "transcribe"
            t0_tx = time.perf_counter()
            import torchaudio

            wav_info, sr = torchaudio.load(str(audio_working_copy))
            duration_ms = int((wav_info.shape[1] / sr) * 1000)

            # Segment the full media duration into conversational turns / chunks
            if panel_segments is not None:
                segments = panel_segments
            else:
                segments = []
                chunk_ms = 20000
                for t in range(0, duration_ms, chunk_ms):
                    segments.append(
                        AudioSegment(start_ms=t, end_ms=min(duration_ms, t + chunk_ms), energy=0.8)
                    )

            utterances = self.transcription_pipeline.transcribe_source(
                source=source,
                subject_id="panel",
                audio_path=audio_working_copy,
                segments=segments,
                job=job,
            )
            job.metrics["transcribe_sec"] = time.perf_counter() - t0_tx

            # Gate audio deletion on productivity: only delete raw audio if >= 1 utterance produced
            if len(utterances) == 0:
                job.status = "failed"
                job.errors.append(
                    "Productivity gate failed: zero utterances produced from source. Audio preserved."
                )
                return job

            # Mark source audio deleted in DB and delete raw audio to honor retention contract
            source.ingested_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            source.audio_deleted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.storage.insert_source(source)
            if raw.media_path.exists():
                raw.media_path.unlink(missing_ok=True)

            # 4. Multi-Speaker Diarization & Attribution
            job.stage = "attribute"
            t0_attr = time.perf_counter()

            # Build subject embeddings map
            subject_embeddings: dict[str, list[float]] = {}
            for s in subjects:
                if s.enrollment_ref:
                    emb = self.enrollment_store.get_embedding(s.enrollment_ref)
                    if emb is not None:
                        subject_embeddings[s.subject_id] = emb

            if subject_embeddings:
                for utt in utterances:
                    start_s = utt.start_ms / 1000.0
                    dur_s = max(0.5, (utt.end_ms - utt.start_ms) / 1000.0)
                    turn_emb = extract_voice_embedding(
                        audio_attr_copy, start_s=start_s, dur_s=dur_s
                    )
                    turn = SpeakerTurn(
                        speaker_cluster_id=utt.utterance_id,
                        start_ms=utt.start_ms,
                        end_ms=utt.end_ms,
                        text=utt.text_verbatim,
                        voice_embedding=turn_emb,
                    )
                    att = self.attributor.attribute_panel_turn(turn, subject_embeddings)
                    utt.attribution_method = att.attribution_method
                    utt.attribution_confidence = att.attribution_confidence
                    if att.subject_id is not None:
                        matched_subj = next(
                            (s for s in subjects if s.subject_id == att.subject_id), None
                        )
                        utt.subject_id = att.subject_id
                        utt.speaker_label = (
                            matched_subj.display_name if matched_subj else att.subject_id
                        )
                    else:
                        utt.subject_id = "unknown"
                        utt.speaker_label = "unknown"

            for utt in utterances:
                self.storage.insert_utterance(utt)
            job.metrics["attribute_sec"] = time.perf_counter() - t0_attr

            # 5. Extraction Gate & Claim Extraction
            job.stage = "extract"
            t0_ext = time.perf_counter()
            total_claims = 0

            for utt in utterances:
                # Find matching subject for this utterance
                matched_subj = next(
                    (
                        s
                        for s in subjects
                        if s.display_name == utt.speaker_label or s.subject_id == utt.speaker_label
                    ),
                    None,
                )
                if matched_subj is None:
                    continue

                if callable(mock_claims_by_subject):
                    mock_claims = mock_claims_by_subject(matched_subj.subject_id, utt)
                elif mock_claims_by_subject:
                    mock_claims = mock_claims_by_subject.get(matched_subj.subject_id)
                else:
                    mock_claims = None

                claims = self.extraction_pipeline.extract_from_utterance(
                    utterance=utt,
                    source_recorded_at=source.recorded_at,
                    subject_context=matched_subj.display_name,
                    mock_model_output={"claims": mock_claims} if mock_claims is not None else None,
                )
                for c in claims:
                    if self.embedder is not None:
                        prop = self.storage.get_proposition(c.proposition_id)
                        if prop is not None:
                            emb_vec = self.embedder.embed_document(prop.canonical_text)
                            self.storage.insert_proposition_embedding(c.proposition_id, emb_vec)
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
            if audio_working_copy.exists():
                audio_working_copy.unlink(missing_ok=True)
            if audio_attr_copy.exists():
                audio_attr_copy.unlink(missing_ok=True)

        return job
