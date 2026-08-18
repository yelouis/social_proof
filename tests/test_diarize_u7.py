from pathlib import Path

import numpy as np

from worker.diarize.attribution import (
    PyannoteDiarizer,
    SpeakerAttributor,
    SpeakerTurn,
    attribute_speaker_turns,
)
from worker.diarize.enrollment import VoiceEnrollmentStore


def test_voice_enrollment_store_round_trip(tmp_path: Path) -> None:
    store = VoiceEnrollmentStore(base_dir=tmp_path / "enroll")
    emb = [1.0, 0.0, 0.5, -0.5] + [0.0] * 252

    ref = store.save_enrollment(
        subject_id="subj_solo_01",
        embedding=emb,
        source_id="src_solo_01",
        verified_by="curator_alice",
    )
    assert len(ref) == 64

    data = store.get_enrollment(ref)
    assert data is not None
    assert data["subject_id"] == "subj_solo_01"
    assert data["verified_by"] == "curator_alice"
    assert len(data["embedding"]) == 256


def test_speaker_attribution_thresholds() -> None:
    attributor = SpeakerAttributor(t_high=0.75, t_low=0.50)
    enrollment_v = [1.0, 0.0, 0.0, 0.0]

    # Turn 1: High similarity (0.90) -> high
    turn_high = SpeakerTurn(
        speaker_cluster_id="spk_0",
        start_ms=0,
        end_ms=5000,
        text="High match statement",
        voice_embedding=[0.9, 0.1, 0.0, 0.0],
    )
    res_high = attributor.attribute_turn(turn_high, "subj_01", enrollment_v)
    assert res_high.attribution_confidence == "high"
    assert res_high.subject_id == "subj_01"
    assert res_high.similarity_score > 0.75

    # Turn 2: Medium similarity (0.60) -> low (excluded from scoring)
    turn_low = SpeakerTurn(
        speaker_cluster_id="spk_1",
        start_ms=5000,
        end_ms=10000,
        text="Medium match statement",
        voice_embedding=[0.6, 0.8, 0.0, 0.0],
    )
    res_low = attributor.attribute_turn(turn_low, "subj_01", enrollment_v)
    assert res_low.attribution_confidence == "low"
    assert res_low.subject_id == "subj_01"
    assert 0.50 <= res_low.similarity_score < 0.75

    # Turn 3: Low similarity (0.10) -> discard
    turn_discard = SpeakerTurn(
        speaker_cluster_id="spk_2",
        start_ms=10000,
        end_ms=15000,
        text="Other speaker turn",
        voice_embedding=[0.1, 0.99, 0.0, 0.0],
    )
    res_discard = attributor.attribute_turn(turn_discard, "subj_01", enrollment_v)
    assert res_discard.attribution_confidence == "discard"
    assert res_discard.subject_id is None


def test_phase_1_gate_journey_j2_and_golden_n9_misattribution_trap() -> None:
    """Golden Case N9 (Journey J2): Host asserts X, Guest asserts not-X in the same episode.

    Zero utterances may be cross-attributed to the wrong speaker.
    Misattribution rate must be strictly 0.
    """
    guest_subject_id = "subj_guest_dr_smith"
    guest_voice_ref = [1.0, 0.0, 0.0, 0.0] + [0.0] * 252

    turns = [
        # Host turn: "I think we should strictly ban open source weights."
        SpeakerTurn(
            speaker_cluster_id="spk_host",
            start_ms=1000,
            end_ms=6000,
            text="I think we should strictly ban open source weights.",
            voice_embedding=[0.05, 0.95, 0.0, 0.0] + [0.0] * 252,
        ),
        # Guest turn: "I completely disagree, open weights are fundamental to safety."
        SpeakerTurn(
            speaker_cluster_id="spk_guest",
            start_ms=7000,
            end_ms=13000,
            text="I completely disagree, open weights are fundamental to safety.",
            voice_embedding=[0.95, 0.05, 0.0, 0.0] + [0.0] * 252,
        ),
    ]

    attributor = SpeakerAttributor(t_high=0.75, t_low=0.50)

    # Attribute turns against Guest enrollment:
    attributed_for_guest = attribute_speaker_turns(turns, guest_subject_id, guest_voice_ref, attributor)

    # Assert Host turn was DISCARDED from Guest's corpus
    assert attributed_for_guest[0].attribution_confidence == "discard"
    assert attributed_for_guest[0].subject_id is None

    # Assert Guest turn was ATTRIBUTED with HIGH confidence
    assert attributed_for_guest[1].attribution_confidence == "high"
    assert attributed_for_guest[1].subject_id == guest_subject_id

    # Compute Misattribution Rate (must be 0)
    misattributions = sum(
        1 for a in attributed_for_guest
        if a.turn.speaker_cluster_id == "spk_host" and a.attribution_confidence == "high"
    )
    misattribution_rate = misattributions / len(turns)
    assert misattribution_rate == 0.0, "Misattribution rate must be strictly 0"


def test_falsification_swapped_enrollment_triggers_misattributions() -> None:
    """Falsification test: Swapping speaker enrollment embeddings causes misattribution count > 0."""
    guest_subject_id = "subj_guest_dr_smith"

    # Deliberately SWAP: pass host voice as guest enrollment
    swapped_guest_voice_ref = [0.0, 1.0, 0.0, 0.0] + [0.0] * 252

    host_turn = SpeakerTurn(
        speaker_cluster_id="spk_host",
        start_ms=1000,
        end_ms=6000,
        text="Host speech",
        voice_embedding=[0.05, 0.95, 0.0, 0.0] + [0.0] * 252,
    )

    attributor = SpeakerAttributor(t_high=0.75, t_low=0.50)
    res = attributor.attribute_turn(host_turn, guest_subject_id, swapped_guest_voice_ref)

    # Host turn is falsely assigned to Guest with high confidence
    assert res.attribution_confidence == "high"
    assert res.subject_id == guest_subject_id  # Falsification confirmed!


def test_pyannote_diarizer_wrapper_with_embedding_extractor() -> None:
    """Tests PyannoteDiarizer with embedding extraction."""
    def mock_extractor(path: str) -> np.ndarray:
        return np.ones(512, dtype=np.float32)

    diarizer = PyannoteDiarizer(embedding_extractor=mock_extractor)
    emb = diarizer.extract_embedding("dummy_path.wav")
    assert len(emb) == 512
    assert emb[0] == 1.0


def test_pyannote_diarizer_pipeline_turns() -> None:
    """Tests PyannoteDiarizer turn extraction."""
    mock_turns = [
        SpeakerTurn(
            speaker_cluster_id="SPEAKER_00",
            start_ms=0,
            end_ms=3000,
            text="",
            voice_embedding=[0.9] * 512,
        ),
        SpeakerTurn(
            speaker_cluster_id="SPEAKER_01",
            start_ms=3500,
            end_ms=7000,
            text="",
            voice_embedding=[0.1] * 512,
        ),
    ]

    diarizer = PyannoteDiarizer(pipeline_instance=lambda path: mock_turns)
    turns = diarizer.diarize("dummy_path.wav")
    assert len(turns) == 2
    assert turns[0].speaker_cluster_id == "SPEAKER_00"
    assert turns[1].speaker_cluster_id == "SPEAKER_01"
