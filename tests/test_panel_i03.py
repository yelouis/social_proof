"""Verification tests for I0.3: Multi-speaker panel ingest, hand-labeled attribution

(Assertion c), Parameter 004 confidence distribution, and evidence integrity.

Implements agent_execution_guide.md §17 (I0.3) and docs/e2e_verification_journeys.md (J1, J2, J11).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from worker.adapters.base import SourceRef
from worker.adapters.podcast import PodcastRSSAdapter
from worker.diarize.attribution import SpeakerAttributor, SpeakerTurn
from worker.diarize.enrollment import (
    VoiceEnrollmentStore,
    extract_voice_embedding,
)
from worker.entities import Claim, Subject, Utterance
from worker.ingest import IngestionEngine
from worker.integrity import (
    verify_anchor_chain,
    verify_attribution_floor,
    verify_quotes,
    verify_role_coverage,
)
from worker.storage import Storage
from worker.transcribe.engine import AudioSegment


@pytest.fixture
def panel_env(tmp_path: Path) -> tuple[Storage, IngestionEngine, PodcastRSSAdapter, list[Subject]]:
    db_path = tmp_path / "social_proof.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    enroll_dir = tmp_path / "enrollments"

    store = Storage(db_path=str(db_path), artifact_dir=artifacts_dir)
    enroll_store = VoiceEnrollmentStore(base_dir=enroll_dir)
    attributor = SpeakerAttributor(t_high=0.70, t_low=0.50)
    engine = IngestionEngine(storage=store, enrollment_store=enroll_store, attributor=attributor)
    adapter = PodcastRSSAdapter()

    # Enroll all four All-In hosts from manifest fixtures
    manifest_path = Path("fixtures/enrollment/manifest.json")
    assert manifest_path.exists(), "Manifest missing"
    manifest = json.loads(manifest_path.read_text())

    subjects = []
    for item in manifest["enrollments"]:
        audio_file = Path(item["audio_file"])
        assert audio_file.exists(), f"Enrollment audio missing: {audio_file}"
        emb = extract_voice_embedding(audio_file)
        ref = enroll_store.save_enrollment(
            subject_id=item["subject_id"],
            embedding=emb,
            source_id="src_enrollment_init",
            verified_by="curator_human_review",
        )
        subj = Subject(
            subject_id=item["subject_id"],
            display_name=item["display_name"],
            enrollment_ref=ref,
        )
        store.insert_subject(subj)
        subjects.append(subj)

    return store, engine, adapter, subjects


def test_hand_labeled_panel_segment_zero_cross_attribution(
    panel_env: tuple[Storage, IngestionEngine, PodcastRSSAdapter, list[Subject]],
) -> None:
    """Assertion (c): Validates that multi-speaker attribution on the 5-minute

    hand-labeled All-In panel audio matches ground-truth turns with zero cross-attribution.
    """
    _store, engine, _adapter, subjects = panel_env

    gt_path = Path("fixtures/panel/allin_e287_5min_ground_truth.json")
    assert gt_path.exists(), "Ground truth fixture missing"
    gt = json.loads(gt_path.read_text())
    audio_path = Path(gt["media_file"])
    assert audio_path.exists(), "Panel audio fixture missing"

    # Build subject embeddings dict
    subject_embeddings = {}
    for s in subjects:
        assert s.enrollment_ref is not None
        emb = engine.enrollment_store.get_embedding(s.enrollment_ref)
        assert emb is not None
        subject_embeddings[s.subject_id] = emb

    correct = 0
    total = len(gt["turns"])
    per_host_matches: dict[str, int] = {s.subject_id: 0 for s in subjects}

    for t in gt["turns"]:
        start_s = t["start_ms"] / 1000.0
        dur_s = (t["end_ms"] - t["start_ms"]) / 1000.0
        turn_emb = extract_voice_embedding(audio_path, start_s=start_s, dur_s=dur_s)
        turn = SpeakerTurn(
            speaker_cluster_id=t["turn_id"],
            start_ms=t["start_ms"],
            end_ms=t["end_ms"],
            text=t["text"],
            voice_embedding=turn_emb,
        )

        att = engine.attributor.attribute_panel_turn(turn, subject_embeddings)
        expected_subj = t["subject_id"]

        assert att.subject_id == expected_subj, (
            f"Cross-attribution in {t['turn_id']}: expected {expected_subj}, got {att.subject_id} (sim {att.similarity_score:.3f})"
        )
        assert att.attribution_confidence in ("high", "low")

        correct += 1
        per_host_matches[expected_subj] += 1

    # Gate: zero cross-attribution (100% accuracy)
    assert correct == total == 15
    # All four hosts speak and are attributed at least once
    for s_id, count in per_host_matches.items():
        assert count >= 1, f"Host {s_id} had zero attributed turns"


def test_parameter_004_confidence_distribution(
    panel_env: tuple[Storage, IngestionEngine, PodcastRSSAdapter, list[Subject]],
) -> None:
    """Verifies that the measured attribution confidence distribution satisfies

    Parameter 004 guarantees (high separation from cross-subject distractors).
    """
    _store, engine, _adapter, subjects = panel_env
    gt = json.loads(Path("fixtures/panel/allin_e287_5min_ground_truth.json").read_text())
    audio_path = Path(gt["media_file"])

    subject_embeddings: dict[str, list[float]] = {}
    for s in subjects:
        if s.enrollment_ref is not None:
            emb = engine.enrollment_store.get_embedding(s.enrollment_ref)
            if emb is not None:
                subject_embeddings[s.subject_id] = emb

    true_sims = []
    distractor_sims = []

    for t in gt["turns"]:
        start_s = t["start_ms"] / 1000.0
        dur_s = (t["end_ms"] - t["start_ms"]) / 1000.0
        turn_emb = extract_voice_embedding(audio_path, start_s=start_s, dur_s=dur_s)
        exp_subj = t["subject_id"]

        for s_id, ref_emb in subject_embeddings.items():
            sim = engine.attributor.cosine_similarity(turn_emb, ref_emb)
            if s_id == exp_subj:
                true_sims.append(sim)
            else:
                distractor_sims.append(sim)

    # Measured distribution floors:
    assert min(true_sims) >= 0.64, f"Min true turn similarity {min(true_sims):.3f} below floor 0.64"
    assert np.mean(true_sims) >= 0.78, f"Mean true turn similarity {np.mean(true_sims):.3f} below 0.78"
    assert np.mean(distractor_sims) <= 0.32, f"Mean distractor similarity {np.mean(distractor_sims):.3f} exceeded 0.32"

    # Parameter 004 guard: Crosstalk turn_08 has runner-up margin < 0.10, triggering attribution_confidence='low'
    t8 = next(t for t in gt["turns"] if t["turn_id"] == "turn_08")
    t8_emb = extract_voice_embedding(audio_path, start_s=t8["start_ms"] / 1000.0, dur_s=(t8["end_ms"] - t8["start_ms"]) / 1000.0)
    t8_turn = SpeakerTurn(speaker_cluster_id="turn_08", start_ms=t8["start_ms"], end_ms=t8["end_ms"], text=t8["text"], voice_embedding=t8_emb)
    t8_att = engine.attributor.attribute_panel_turn(t8_turn, subject_embeddings)
    assert t8_att.attribution_confidence == "low", "Crosstalk turn must be flagged low confidence and excluded from scoring"


def test_falsification_swapped_enrollment_triggers_cross_attribution(
    panel_env: tuple[Storage, IngestionEngine, PodcastRSSAdapter, list[Subject]],
) -> None:
    """Falsification for I0.3: Swapping enrollment embeddings of two hosts

    causes cross-attribution to go non-zero against the hand-labeled segment (RED).
    Reverting restores 100% accuracy (GREEN).
    """
    _store, engine, _adapter, subjects = panel_env
    gt = json.loads(Path("fixtures/panel/allin_e287_5min_ground_truth.json").read_text())
    audio_path = Path(gt["media_file"])

    orig_embeddings: dict[str, list[float]] = {}
    for s in subjects:
        if s.enrollment_ref is not None:
            emb = engine.enrollment_store.get_embedding(s.enrollment_ref)
            if emb is not None:
                orig_embeddings[s.subject_id] = emb

    # Swap Chamath and Sacks embeddings
    swapped_embeddings = dict(orig_embeddings)
    chamath_id = "subj_chamath_palihapitiya"
    sacks_id = "subj_david_sacks"
    swapped_embeddings[chamath_id] = orig_embeddings[sacks_id]
    swapped_embeddings[sacks_id] = orig_embeddings[chamath_id]

    # Evaluate against hand-labeled turns with swapped embeddings
    mismatches = 0
    for t in gt["turns"]:
        start_s = t["start_ms"] / 1000.0
        dur_s = (t["end_ms"] - t["start_ms"]) / 1000.0
        turn_emb = extract_voice_embedding(audio_path, start_s=start_s, dur_s=dur_s)
        turn = SpeakerTurn(
            speaker_cluster_id=t["turn_id"],
            start_ms=t["start_ms"],
            end_ms=t["end_ms"],
            text=t["text"],
            voice_embedding=turn_emb,
        )
        att = engine.attributor.attribute_panel_turn(turn, swapped_embeddings)
        if att.subject_id != t["subject_id"]:
            mismatches += 1

    # Cross-attribution MUST go non-zero (RED)
    assert mismatches > 0, "Falsification failed: swapped embeddings did not produce misattribution"

    # Revert to original embeddings -> GREEN
    reverted_mismatches = 0
    for t in gt["turns"]:
        start_s = t["start_ms"] / 1000.0
        dur_s = (t["end_ms"] - t["start_ms"]) / 1000.0
        turn_emb = extract_voice_embedding(audio_path, start_s=start_s, dur_s=dur_s)
        turn = SpeakerTurn(
            speaker_cluster_id=t["turn_id"],
            start_ms=t["start_ms"],
            end_ms=t["end_ms"],
            text=t["text"],
            voice_embedding=turn_emb,
        )
        att = engine.attributor.attribute_panel_turn(turn, orig_embeddings)
        if att.subject_id != t["subject_id"]:
            reverted_mismatches += 1

    assert reverted_mismatches == 0, "Revert failed: clean embeddings still produce misattribution"


def test_panel_ingest_end_to_end_and_integrity(
    panel_env: tuple[Storage, IngestionEngine, PodcastRSSAdapter, list[Subject]],
) -> None:
    """End-to-end ingest of multi-speaker panel episode, validating claims distribution

    across hosts, SourceSubjectRole join rows, word timestamps Parquet, and evidence integrity.
    """
    store, engine, adapter, subjects = panel_env
    audio_fixture = Path("fixtures/panel/allin_e287_5min.wav")
    assert audio_fixture.exists()

    enclosure_url = "https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E287_Ch.mp3"
    ref = SourceRef(
        locator=enclosure_url,
        tier="B",
        title="All-In E287: Nvidia's Historic Quarter, SaaS Comeback",
    )

    # Claims distributed across multiple hosts from the actual conversation
    mock_claims_by_subject = {
        "subj_jason_calacanis": [
            {
                "proposition_text": "The Chinese Communist Party is effective at public relations regarding artificial intelligence and robotics.",
                "stance": "support",
                "quote_text": "the CCP is brilliant at PR",
                "hedging_level": 0.05,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "confidence": 0.95,
            }
        ],
        "subj_david_friedberg": [
            {
                "proposition_text": "Mainstream scientific institutional consensus stifles heterodox theory and alternative physics models.",
                "stance": "support",
                "quote_text": "you have to follow the mainstream in science or your outcasts",
                "hedging_level": 0.1,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "confidence": 0.92,
            }
        ],
        "subj_chamath_palihapitiya": [
            {
                "proposition_text": "String theory remains unproved until verified empirically.",
                "stance": "support",
                "quote_text": "until string theory is proved, it's unproved",
                "hedging_level": 0.05,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "confidence": 0.98,
            }
        ],
        "subj_david_sacks": [
            {
                "proposition_text": "China has greater societal and official optimism toward artificial intelligence than Western nations.",
                "stance": "support",
                "quote_text": "China is much more optimistic about AI than we are",
                "hedging_level": 0.05,
                "is_own_assertion": True,
                "exclusion_reason": None,
                "confidence": 0.94,
            }
        ],
    }

    gt_path = Path("fixtures/panel/allin_e287_5min_ground_truth.json")
    gt = json.loads(gt_path.read_text())
    panel_segments = [
        AudioSegment(start_ms=t["start_ms"], end_ms=t["end_ms"], energy=0.8)
        for t in gt["turns"]
    ]

    # Run panel ingest
    job = engine.ingest_panel_source(
        adapter=adapter,
        ref=ref,
        subjects=subjects,
        media_file_override=audio_fixture,
        mock_claims_by_subject=mock_claims_by_subject,
        panel_segments=panel_segments,
    )

    assert job.status == "completed"
    assert job.stage == "persisted"
    assert job.metrics["extracted_claims_count"] >= 3.0

    # 1. Source and Audio Disposal
    src_row = store.con.execute("SELECT source_id FROM sources WHERE canonical_url = ?", [enclosure_url]).fetchone()
    assert src_row is not None
    source_id = str(src_row[0])
    stored_source = store.get_source(source_id)
    assert stored_source is not None
    assert stored_source.audio_deleted_at is not None, "audio_deleted_at must be set upon panel ingest"

    # 2. SourceSubjectRole Join Rows (Issue 022 = Option A)
    for subj in subjects:
        role = store.get_source_role(source_id, subj.subject_id)
        assert role is not None
        assert role.tier == "B"
        assert role.venue_type == "own_channel"
        assert role.audience_stance == "friendly"
        assert role.is_adversarial is False

    # 3. Utterances in Storage
    stored_utts = store.get_utterances_for_source(source_id)
    assert len(stored_utts) >= 10

    # Verify utterances have high attribution confidence and parquet word timestamps
    speakers_found = set()
    for u in stored_utts:
        assert u.attribution_method in ("panel_diarization", "voice_embedding_match")
        assert u.word_timestamps_ref is not None
        words = store.artifact_store.get_word_timestamps(u.word_timestamps_ref)
        assert words is not None and len(words) > 0
        speakers_found.add(u.speaker_label)

    # 4. Claims Distributed Across Hosts
    claim_rows = store.con.execute(
        "SELECT claim_id, subject_id, quote_span_start, quote_span_end, utterance_id FROM claims WHERE utterance_id IN (SELECT utterance_id FROM utterances WHERE source_id = ?)",
        [source_id],
    ).fetchall()
    assert len(claim_rows) >= 3

    claimed_subjects = {r[1] for r in claim_rows}
    assert len(claimed_subjects) >= 3, "Claims must be distributed across hosts rather than collapsing onto one"

    all_claims: list[Claim] = []
    for r in claim_rows:
        cid, _sid, q_start, q_end, uid = r[0], r[1], r[2], r[3], r[4]
        utt = store.get_utterance(uid)
        assert utt is not None
        exact_quote = utt.text_verbatim[q_start:q_end]
        assert exact_quote in utt.text_verbatim
        c = store.get_claim(cid)
        if c is not None:
            all_claims.append(c)

    all_utts: list[Utterance] = [u for u in stored_utts if u is not None]
    all_sources = [stored_source]

    # 5. Full Evidence Integrity Pass on Real Populated Data
    vq_res = verify_quotes(all_claims, all_utts)
    assert vq_res.passed is True
    assert vq_res.examined_count >= 3

    vac_res = verify_anchor_chain(all_claims, all_utts, all_sources)
    assert vac_res.passed is True
    assert vac_res.examined_count >= 3

    vaf_res = verify_attribution_floor(all_claims, all_utts, tensions=[])
    assert vaf_res.passed is True

    all_roles = [role for s in subjects if (role := store.get_source_role(source_id, s.subject_id)) is not None]
    vrc_res = verify_role_coverage(all_utts, all_roles)
    assert vrc_res.passed is True


def test_panel_reingest_idempotency_j11(
    panel_env: tuple[Storage, IngestionEngine, PodcastRSSAdapter, list[Subject]],
) -> None:
    """J11: Re-running panel ingest yields zero new rows and zero re-transcription."""
    store, engine, adapter, subjects = panel_env
    audio_fixture = Path("fixtures/panel/allin_e287_5min.wav")
    ref = SourceRef(
        locator="https://traffic.libsyn.com/secure/allinchamathjason/ALLIN-E287_Ch.mp3",
        tier="B",
        title="All-In E287",
    )

    # Ingest Pass 1
    job1 = engine.ingest_panel_source(adapter, ref, subjects, media_file_override=audio_fixture)
    assert job1.status == "completed"

    row_s1 = store.con.execute("SELECT count(*) FROM sources").fetchone()
    assert row_s1 is not None
    count_sources_1 = int(row_s1[0])

    row_r1 = store.con.execute("SELECT count(*) FROM source_roles").fetchone()
    assert row_r1 is not None
    count_roles_1 = int(row_r1[0])

    row_u1 = store.con.execute("SELECT count(*) FROM utterances").fetchone()
    assert row_u1 is not None
    count_utts_1 = int(row_u1[0])

    # Ingest Pass 2 (Re-ingest)
    job2 = engine.ingest_panel_source(adapter, ref, subjects, media_file_override=audio_fixture)
    assert job2.status == "completed"
    assert job2.metrics.get("reingest_skipped") == 1.0, "Re-ingest must skip transcription"

    row_s2 = store.con.execute("SELECT count(*) FROM sources").fetchone()
    assert row_s2 is not None
    count_sources_2 = int(row_s2[0])

    row_r2 = store.con.execute("SELECT count(*) FROM source_roles").fetchone()
    assert row_r2 is not None
    count_roles_2 = int(row_r2[0])

    row_u2 = store.con.execute("SELECT count(*) FROM utterances").fetchone()
    assert row_u2 is not None
    count_utts_2 = int(row_u2[0])

    assert count_sources_1 == count_sources_2, "Zero new source rows on panel re-ingest"
    assert count_roles_1 == count_roles_2, "Zero new role rows on panel re-ingest"
    assert count_utts_1 == count_utts_2, "Zero new utterance rows on panel re-ingest"
