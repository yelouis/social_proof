"""Unit, integration, and falsification tests for Transcription, VAD, and Audio Disposal (U3)."""

from pathlib import Path

import pytest

from worker.entities import IngestJob, Source
from worker.storage import Storage
from worker.transcribe.engine import (
    AudioSegment,
    MockTranscriptionEngine,
    TranscriptionPipeline,
)


def test_vad_gate_drops_silence_spans(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    pipeline = TranscriptionPipeline(storage=store, vad_energy_threshold=0.05)

    segments = [
        AudioSegment(start_ms=0, end_ms=30000, energy=0.0),      # 30s leading silence
        AudioSegment(start_ms=30000, end_ms=45000, energy=0.01),  # background noise below threshold
        AudioSegment(start_ms=45000, end_ms=60000, energy=0.85),  # actual speech
    ]

    filtered = pipeline.vad_filter(segments)
    assert len(filtered) == 1
    assert filtered[0].start_ms == 45000
    assert filtered[0].end_ms == 60000


def test_synthetic_negation_test_flags_negation_uncertain(tmp_path: Path) -> None:
    """Synthetic negation test: Take a clip with a known 'I don't think X',

    force pass 2 to a transcript missing the 'don't', and assert the utterance
    comes back negation_uncertain = True.
    """
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")

    seg = AudioSegment(start_ms=1000, end_ms=5000, energy=0.9)
    # Pass 1 contains negation: "I don't think we should do this"
    # Pass 2 dropped negation: "I think we should do this"
    mock_engine = MockTranscriptionEngine(
        pass1_script=[(seg, "I don't think we should do this")],
        pass2_script=[(seg, "I think we should do this")],
    )

    pipeline = TranscriptionPipeline(storage=store, engine=mock_engine)

    source = Source(
        source_id="src_neg_01",
        tier="B",
        title="Podcast with negation",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=neg01",
        artifact_hash="hash_neg_01",
        citation_url_template="https://youtu.be/neg01?t={seconds}",
    )
    store.insert_source(source)

    audio_file = tmp_path / "audio_neg.wav"
    audio_file.write_bytes(b"RIFF_AUDIO_NEG")

    utterances = pipeline.transcribe_source(
        source=source,
        subject_id="subj_01",
        audio_path=audio_file,
        segments=[seg],
    )

    assert len(utterances) == 1
    utt = utterances[0]
    assert utt.text_verbatim == "I don't think we should do this"
    assert utt.negation_uncertain is True
    assert utt.dual_pass_agreement is False
    assert utt.transcription_pass_count == 2


def test_dual_pass_agreement_when_passes_match(tmp_path: Path) -> None:
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    seg = AudioSegment(start_ms=1000, end_ms=5000, energy=0.9)
    mock_engine = MockTranscriptionEngine(
        pass1_script=[(seg, "We should definitely invest in safety research")],
        pass2_script=[(seg, "We should definitely invest in safety research")],
    )
    pipeline = TranscriptionPipeline(storage=store, engine=mock_engine)

    source = Source(
        source_id="src_agree_01",
        tier="B",
        title="Agreement podcast",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=agree01",
        artifact_hash="hash_agree_01",
        citation_url_template="https://youtu.be/agree01?t={seconds}",
    )
    store.insert_source(source)

    audio_file = tmp_path / "audio_agree.wav"
    audio_file.write_bytes(b"RIFF_AUDIO_AGREE")

    utterances = pipeline.transcribe_source(
        source=source,
        subject_id="subj_01",
        audio_path=audio_file,
        segments=[seg],
    )

    assert len(utterances) == 1
    utt = utterances[0]
    assert utt.negation_uncertain is False
    assert utt.dual_pass_agreement is True
    assert utt.transcription_pass_count == 2

    # Check word timestamps in Parquet artifact
    assert utt.word_timestamps_ref is not None
    words = store.artifacts.get_word_timestamps(utt.word_timestamps_ref)
    assert words is not None
    assert len(words) == 7
    # Timestamps monotonic and inside segment bounds
    for i in range(len(words) - 1):
        assert words[i]["start_ms"] <= words[i]["end_ms"]
        assert words[i]["end_ms"] <= words[i + 1]["start_ms"]
        assert words[i]["start_ms"] >= seg.start_ms
        assert words[i]["end_ms"] <= seg.end_ms


def test_audio_disposal_on_success_and_preservation_on_error(tmp_path: Path) -> None:
    """Assert audio is deleted on success and preserved on failure."""
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")
    seg = AudioSegment(start_ms=0, end_ms=5000, energy=0.9)
    mock_engine = MockTranscriptionEngine(pass1_script=[(seg, "Hello world")])
    pipeline = TranscriptionPipeline(storage=store, engine=mock_engine)

    # 1. Success case: Audio deleted
    source1 = Source(
        source_id="src_disp_01",
        tier="B",
        title="Episode 1",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=disp01",
        artifact_hash="hash_disp_01",
    )
    store.insert_source(source1)

    audio1 = tmp_path / "audio_success.wav"
    audio1.write_bytes(b"AUDIO_DATA_1")
    job1 = IngestJob(job_id="job_01", subject_id="subj_01", adapter="YouTube", status="running", stage="transcribe")

    pipeline.transcribe_source(source1, "subj_01", audio1, [seg], job=job1)
    assert not audio1.exists(), "Audio file must be deleted after successful transcription"
    updated_src1 = store.get_source("src_disp_01")
    assert updated_src1 is not None and updated_src1.audio_deleted_at is not None
    assert job1.status == "completed"

    # 2. Failure case: Audio preserved
    source2 = Source(
        source_id="src_disp_02",
        tier="B",
        title="Episode 2",
        publisher="Host",
        canonical_url="https://youtube.com/watch?v=disp02",
        artifact_hash="hash_disp_02",
    )
    store.insert_source(source2)

    audio2 = tmp_path / "audio_fail.wav"
    audio2.write_bytes(b"AUDIO_DATA_2")
    job2 = IngestJob(job_id="job_02", subject_id="subj_01", adapter="YouTube", status="running", stage="transcribe")

    with pytest.raises(RuntimeError, match="Simulated transcription failure"):
        pipeline.transcribe_source(source2, "subj_01", audio2, [seg], job=job2, force_error=True)

    assert audio2.exists(), "Audio file must be PRESERVED when transcription fails"
    assert job2.status == "failed"


def test_falsification_disabled_vad_allows_silence_segments(tmp_path: Path) -> None:
    """Falsification test: Disabling VAD gate allows silent segments to produce hallucinations."""
    store = Storage(db_path=str(tmp_path / "test.duckdb"), artifact_dir=tmp_path / "artifacts")

    # Pipeline with VAD disabled (threshold = -1.0)
    pipeline_no_vad = TranscriptionPipeline(storage=store, vad_energy_threshold=-1.0)

    silence_segments = [
        AudioSegment(start_ms=0, end_ms=30000, energy=0.0),
    ]
    filtered = pipeline_no_vad.vad_filter(silence_segments)
    assert len(filtered) == 1  # Falsification confirmed: silent segment not dropped!
