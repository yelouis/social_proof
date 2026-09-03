"""Tests for P5 — Principle extraction and conflict detection.

Implements agent_execution_guide.md §20 (P5) and design_principle_extraction.md.
Validates:
- Fixture P3: Verified principle conflict across opposing verdicts on same principle
- Fixture N6: Stated distinction present -> distinguished, excluded from scoring (Assertion c)
- Falsification: Disabling stated distinction detection flips N6 to published principle_conflict
- Unresolved actors ('unknown') never enter conflict detection
- Generality calibrator ceiling enforcement
- TensionDetector integration
"""

from pathlib import Path

import pytest

from fixtures.behaviour.loader import load_behaviour_cases
from worker.entities import (
    Claim,
    Principle,
    PrincipleApplication,
    Source,
    SourceSubjectRole,
    Subject,
    Utterance,
)
from worker.principles.calibration import GeneralityCalibrator
from worker.principles.conflict import PrincipleConflictDetector
from worker.principles.distinction import StatedDistinctionDetector
from worker.storage import (
    Storage,
    compute_application_id,
    compute_claim_id,
    compute_principle_id,
    compute_role_id,
    compute_source_id,
    compute_utterance_id,
)
from worker.tension.detect import TensionDetector


@pytest.fixture
def test_store(tmp_path: Path) -> Storage:
    db_path = tmp_path / "principle_test.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    return Storage(db_path=str(db_path), artifact_dir=artifacts_dir)


def test_fixture_p3_principle_conflict(test_store: Storage) -> None:
    """Fixture P3: Opposing verdicts on the same principle without stated distinction produces principle_conflict."""
    cases = load_behaviour_cases()
    p3 = next(c for c in cases if c.type == "P3")

    subject = Subject(subject_id=p3.subject_id, display_name="Dr. Golden P3")
    test_store.insert_subject(subject)

    principle_text = "an official who knowingly misleads oversight should resign"
    principle_id = compute_principle_id(principle_text)
    principle = Principle(
        principle_id=principle_id,
        canonical_text=principle_text,
        actor_role="official",
        subject_ids=[subject.subject_id],
    )
    test_store.insert_principle(principle)

    # Two utterances: Alvarez (applies), Hayes (does_not_apply)
    actors = ["Senator Alvarez", "Director Hayes"]
    verdicts = ["applies", "does_not_apply"]
    affinities = ["opponent", "ally"]

    for i, u in enumerate(p3.utterances):
        src_id = compute_source_id(f"p3_src_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Press",
            canonical_url=f"{p3.source_locator}_{i}",
            artifact_hash=f"hash_{i}",
            recorded_at=u.recorded_at,
        )
        test_store.insert_source(source)

        role = SourceSubjectRole(
            role_id=compute_role_id(src_id, subject.subject_id),
            source_id=src_id,
            subject_id=subject.subject_id,
            tier="B",
            venue_type="own_channel",
            audience_stance="friendly",
            is_adversarial=False,
        )
        test_store.insert_source_role(role)

        utt_id = compute_utterance_id(src_id, i * 1000, u.text)
        utt = Utterance(
            utterance_id=utt_id,
            source_id=src_id,
            subject_id=subject.subject_id,
            text_verbatim=u.text,
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="voice_match",
            transcription_pass_count=2,
        )
        test_store.insert_utterance(utt)

        claim_id = compute_claim_id(utt_id, principle_id, "support" if i == 0 else "oppose", "v1")
        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=principle_id,
            stance="support" if i == 0 else "oppose",
            hedging_level=0.05,
            is_own_assertion=True,
            quote_span=(0, len(u.text)),
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

        app_id = compute_application_id(claim_id, principle_id, actors[i], verdicts[i])
        app = PrincipleApplication(
            application_id=app_id,
            principle_id=principle_id,
            claim_id=claim_id,
            subject_id=subject.subject_id,
            actor=actors[i],
            actor_affinity=affinities[i],  # type: ignore[arg-type]
            verdict=verdicts[i],  # type: ignore[arg-type]
            stated_distinction=None,
            confidence=1.0,
            recorded_at=u.recorded_at,
        )
        test_store.insert_principle_application(app)

    detector = PrincipleConflictDetector(storage=test_store)
    conflicts, distinguished = detector.detect_conflicts_for_subject(subject.subject_id)

    assert len(conflicts) == 1
    assert len(distinguished) == 0
    t = conflicts[0]
    assert t.type == "principle_conflict"
    assert t.status == "published"
    assert t.principle_id == principle_id


def test_fixture_n6_distinction_excluded_from_scoring(test_store: Storage) -> None:
    """Fixture N6: Stated distinction present -> marked distinguished and excluded from hypocrisy scoring (Assertion c)."""
    cases = load_behaviour_cases()
    n6 = next(c for c in cases if c.type == "N6")

    subject = Subject(subject_id=n6.subject_id, display_name="Dr. Golden N6")
    test_store.insert_subject(subject)

    principle_text = "an official who knowingly misleads oversight should resign"
    principle_id = compute_principle_id(principle_text)
    principle = Principle(
        principle_id=principle_id,
        canonical_text=principle_text,
        actor_role="official",
        subject_ids=[subject.subject_id],
    )
    test_store.insert_principle(principle)

    actors = ["Senator Alvarez", "Director Hayes"]
    verdicts = ["applies", "does_not_apply"]
    affinities = ["opponent", "ally"]

    # Utterance 3 contains the stated distinction
    distinction_text = n6.utterances[2].stated_distinction

    for i in (0, 1):
        u = n6.utterances[i]
        src_id = compute_source_id(f"n6_src_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Press",
            canonical_url=f"{n6.source_locator}_{i}",
            artifact_hash=f"hash_{i}",
            recorded_at=u.recorded_at,
        )
        test_store.insert_source(source)

        utt_id = compute_utterance_id(src_id, i * 1000, u.text)
        utt = Utterance(
            utterance_id=utt_id,
            source_id=src_id,
            subject_id=subject.subject_id,
            text_verbatim=u.text,
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="voice_match",
            transcription_pass_count=2,
        )
        test_store.insert_utterance(utt)

        claim_id = compute_claim_id(utt_id, principle_id, "support" if i == 0 else "oppose", "v1")
        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=principle_id,
            stance="support" if i == 0 else "oppose",
            hedging_level=0.05,
            is_own_assertion=True,
            quote_span=(0, len(u.text)),
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

        # Attach stated distinction to Hayes application
        app_dist = distinction_text if i == 1 else None
        app_id = compute_application_id(claim_id, principle_id, actors[i], verdicts[i])
        app = PrincipleApplication(
            application_id=app_id,
            principle_id=principle_id,
            claim_id=claim_id,
            subject_id=subject.subject_id,
            actor=actors[i],
            actor_affinity=affinities[i],  # type: ignore[arg-type]
            verdict=verdicts[i],  # type: ignore[arg-type]
            stated_distinction=app_dist,
            confidence=1.0,
            recorded_at=u.recorded_at,
        )
        test_store.insert_principle_application(app)

    detector = PrincipleConflictDetector(storage=test_store, enable_stated_distinction=True)
    conflicts, distinguished = detector.detect_conflicts_for_subject(subject.subject_id)

    # Must NOT produce a published conflict
    assert len(conflicts) == 0, f"Expected 0 published conflicts, got {conflicts}"
    # Must be recorded as distinguished
    assert len(distinguished) == 1
    d = distinguished[0]
    assert d["status"] == "distinguished"
    assert "subpoena" in str(d["distinction"]).lower()


def test_falsification_disabling_stated_distinction_causes_n6_to_publish_conflict(test_store: Storage) -> None:
    """Falsification test: Disabling stated distinction detection causes N6 to flip to a published conflict (RED).

    Re-enabling it restores distinguished status (GREEN).
    """
    cases = load_behaviour_cases()
    n6 = next(c for c in cases if c.type == "N6")

    subject = Subject(subject_id="subj_falsify_n6", display_name="Falsify N6")
    test_store.insert_subject(subject)

    principle_text = "an official who knowingly misleads oversight should resign"
    principle_id = compute_principle_id(principle_text)
    test_store.insert_principle(Principle(principle_id=principle_id, canonical_text=principle_text, subject_ids=[subject.subject_id]))

    distinction_text = n6.utterances[2].stated_distinction

    for i in (0, 1):
        u = n6.utterances[i]
        src_id = compute_source_id(f"falsify_n6_src_{i}")
        test_store.insert_source(
            Source(
                source_id=src_id,
                title=f"S{i}",
                publisher="Press",
                canonical_url=f"url_{i}",
                artifact_hash=f"hash_{i}",
                recorded_at=u.recorded_at,
            )
        )

        utt_id = compute_utterance_id(src_id, i * 1000, u.text)
        test_store.insert_utterance(
            Utterance(
                utterance_id=utt_id,
                source_id=src_id,
                subject_id=subject.subject_id,
                text_verbatim=u.text,
                start_ms=1000,
                end_ms=2000,
                speaker_label="speaker_0",
                attribution_confidence="high",
                attribution_method="voice_match",
            )
        )
        claim_id = compute_claim_id(utt_id, principle_id, "support" if i == 0 else "oppose", "v1")
        test_store.insert_claim(
            Claim(
                claim_id=claim_id,
                subject_id=subject.subject_id,
                utterance_id=utt_id,
                proposition_id=principle_id,
                stance="support" if i == 0 else "oppose",
                hedging_level=0.05,
                is_own_assertion=True,
                quote_span=(0, len(u.text)),
                recorded_at=u.recorded_at,
            )
        )

        app_id = compute_application_id(claim_id, principle_id, "Alvarez" if i == 0 else "Hayes", "applies" if i == 0 else "does_not_apply")
        test_store.insert_principle_application(
            PrincipleApplication(
                application_id=app_id,
                principle_id=principle_id,
                claim_id=claim_id,
                subject_id=subject.subject_id,
                actor="Alvarez" if i == 0 else "Hayes",
                verdict="applies" if i == 0 else "does_not_apply",
                stated_distinction=distinction_text if i == 1 else None,
                recorded_at=u.recorded_at,
            )
        )

    # 1. Disable stated distinction detection -> flips to published principle_conflict (RED)
    disabled_detector = PrincipleConflictDetector(storage=test_store, enable_stated_distinction=False)
    conflicts_disabled, _ = disabled_detector.detect_conflicts_for_subject(subject.subject_id)
    assert len(conflicts_disabled) == 1, "Falsification failed: disabling distinction did not publish conflict"
    assert conflicts_disabled[0].type == "principle_conflict"

    # 2. Re-enable stated distinction detection -> restores distinguished (GREEN)
    enabled_detector = PrincipleConflictDetector(storage=test_store, enable_stated_distinction=True)
    conflicts_enabled, distinguished_enabled = enabled_detector.detect_conflicts_for_subject(subject.subject_id)
    assert len(conflicts_enabled) == 0, "Failed to exclude distinguished pair when enabled"
    assert len(distinguished_enabled) == 1


def test_unresolved_actor_never_enters_conflict(test_store: Storage) -> None:
    """Actor resolution floor: An application with actor='unknown' is excluded from conflict detection."""
    subject = Subject(subject_id="subj_unknown_actor", display_name="Unknown Actor Test")
    test_store.insert_subject(subject)

    principle_text = "an institution that conceals safety audit findings should lose accreditation"
    principle_id = compute_principle_id(principle_text)
    test_store.insert_principle(Principle(principle_id=principle_id, canonical_text=principle_text, subject_ids=[subject.subject_id]))

    for i in (0, 1):
        src_id = f"src_unk_{i}"
        test_store.insert_source(Source(source_id=src_id, title=f"S{i}", publisher="Press", canonical_url=f"url_{i}", artifact_hash=f"hash_{i}"))
        utt_id = f"utt_unk_{i}"
        test_store.insert_utterance(
            Utterance(
                utterance_id=utt_id,
                source_id=src_id,
                subject_id=subject.subject_id,
                text_verbatim=f"Statement {i}",
                start_ms=1000,
                end_ms=2000,
                speaker_label="speaker_0",
                attribution_confidence="high",
                attribution_method="voice_match",
            )
        )
        claim_id = f"claim_unk_{i}"
        test_store.insert_claim(
            Claim(
                claim_id=claim_id,
                subject_id=subject.subject_id,
                utterance_id=utt_id,
                proposition_id=principle_id,
                stance="support" if i == 0 else "oppose",
                hedging_level=0.0,
                is_own_assertion=True,
                quote_span=(0, 11),
            )
        )
        # Application 1 has resolved actor, Application 2 has UNRESOLVED actor ('unknown')
        actor = "Enron" if i == 0 else "unknown"
        app_id = f"app_unk_{i}"
        test_store.insert_principle_application(
            PrincipleApplication(
                application_id=app_id,
                principle_id=principle_id,
                claim_id=claim_id,
                subject_id=subject.subject_id,
                actor=actor,
                verdict="applies" if i == 0 else "does_not_apply",
            )
        )

    detector = PrincipleConflictDetector(storage=test_store)
    conflicts, distinguished = detector.detect_conflicts_for_subject(subject.subject_id)

    # Must NOT produce any conflicts because one actor is unknown
    assert len(conflicts) == 0
    assert len(distinguished) == 0


def test_generality_calibrator_cluster_ceiling() -> None:
    """Generality calibrator rejects over-general principles exceeding cluster ceiling."""
    calibrator = GeneralityCalibrator(max_cluster_size=30)

    # 1. Healthy cluster size (12 members)
    is_ok_1, reason_1 = calibrator.check_cluster_size(12)
    assert is_ok_1 is True
    assert reason_1 is None

    # 2. Over-general cluster size (45 members)
    is_ok_2, reason_2 = calibrator.check_cluster_size(45)
    assert is_ok_2 is False
    assert "exceeds ceiling" in str(reason_2)


def test_generality_calibrator_canonical_text_discipline() -> None:
    """Generality calibrator rejects principles mentioning specific actors or lacking generic slot."""
    calibrator = GeneralityCalibrator()

    # 1. Valid canonical text
    valid_res = calibrator.validate_canonical_text("an elected official who misleads oversight should resign")
    assert valid_res.is_valid is True

    # 2. Invalid: mentions specific named person entity
    invalid_res = calibrator.validate_canonical_text("Senator Alvarez who misleads oversight should resign")
    assert invalid_res.is_valid is False
    assert "must not mention specific actors" in str(invalid_res.reason)


def test_stated_distinction_detector_regex() -> None:
    """StatedDistinctionDetector catches contrastive phrasing."""
    detector = StatedDistinctionDetector()

    text = "The difference between Alvarez and Hayes is that Alvarez was under sworn subpoena whereas Hayes spoke informally."
    res = detector.detect_stated_distinction(text)
    assert res.present is True
    assert res.distinction_text is not None


def test_tension_detector_integration_with_principles(test_store: Storage) -> None:
    """TensionDetector sweeps and detects principle conflicts in detect_all_tensions_for_subject."""
    subject = Subject(subject_id="subj_td_integ", display_name="Tension Integ")
    test_store.insert_subject(subject)

    p_text = "an official who knowingly misleads oversight should resign"
    p_id = compute_principle_id(p_text)
    test_store.insert_principle(Principle(principle_id=p_id, canonical_text=p_text, subject_ids=[subject.subject_id]))

    for i in (0, 1):
        src_id = f"src_td_{i}"
        test_store.insert_source(Source(source_id=src_id, title=f"S{i}", publisher="Press", canonical_url=f"url_{i}", artifact_hash=f"hash_{i}"))
        utt_id = f"utt_td_{i}"
        test_store.insert_utterance(
            Utterance(
                utterance_id=utt_id,
                source_id=src_id,
                subject_id=subject.subject_id,
                text_verbatim=f"Statement {i}",
                start_ms=1000,
                end_ms=2000,
                speaker_label="speaker_0",
                attribution_confidence="high",
                attribution_method="voice_match",
            )
        )
        claim_id = f"claim_td_{i}"
        test_store.insert_claim(
            Claim(
                claim_id=claim_id,
                subject_id=subject.subject_id,
                utterance_id=utt_id,
                proposition_id=p_id,
                stance="support" if i == 0 else "oppose",
                hedging_level=0.0,
                is_own_assertion=True,
                quote_span=(0, 11),
            )
        )
        app_id = f"app_td_{i}"
        test_store.insert_principle_application(
            PrincipleApplication(
                application_id=app_id,
                principle_id=p_id,
                claim_id=claim_id,
                subject_id=subject.subject_id,
                actor="ActorA" if i == 0 else "ActorB",
                verdict="applies" if i == 0 else "does_not_apply",
            )
        )

    tension_detector = TensionDetector(storage=test_store)
    all_tensions = tension_detector.detect_all_tensions_for_subject(subject.subject_id)

    principle_tensions = [t for t in all_tensions if t.type == "principle_conflict"]
    assert len(principle_tensions) == 1
    assert principle_tensions[0].status == "published"
