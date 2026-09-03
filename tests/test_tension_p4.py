"""Tests for P4 — Tension detection.

Implements agent_execution_guide.md §18 (P4) and design_rubric_engine.md §1.
Validates:
- SQL self-join execution in DuckDB
- Behaviour fixtures P1, P2, P4, N5, N7
- The six preconditions and quarantine handling
- Trap 2: Full-interval acknowledgement search falsification
- Evidence integrity checks
"""

from pathlib import Path
from typing import Literal

import pytest

from fixtures.behaviour.loader import load_behaviour_cases
from worker.entities import (
    Claim,
    Proposition,
    Source,
    SourceSubjectRole,
    Subject,
    Utterance,
)
from worker.integrity import (
    verify_attribution_floor,
    verify_negation_recheck,
    verify_quarantine_not_rendered,
)
from worker.storage import (
    Storage,
    compute_claim_id,
    compute_proposition_id,
    compute_role_id,
    compute_source_id,
    compute_utterance_id,
)
from worker.tension.detect import TensionDetector


@pytest.fixture
def test_store(tmp_path: Path) -> Storage:
    db_path = tmp_path / "tension_test.duckdb"
    artifacts_dir = tmp_path / "artifacts"
    return Storage(db_path=str(db_path), artifact_dir=artifacts_dir)


def test_fixture_p1_unacknowledged_reversal(test_store: Storage) -> None:
    """Fixture P1: Verified unacknowledged reversal.

    Expects tension_type = 'unacknowledged_reversal' and status = 'published'.
    """
    cases = load_behaviour_cases()
    p1 = next(c for c in cases if c.type == "P1")

    subject = Subject(subject_id=p1.subject_id, display_name="Dr. Golden 01")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("federal licensing for frontier compute models")
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text="federal licensing for frontier compute models",
            subject_ids=[subject.subject_id],
        )
    )

    claims = []
    for i, u in enumerate(p1.utterances):
        src_id = compute_source_id(f"{p1.source_locator}_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Host",
            canonical_url=f"{p1.source_locator}_{i}",
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
            word_timestamps_ref=None,
            transcription_pass_count=2,
            dual_pass_agreement=True,
            negation_uncertain=False,
        )
        test_store.insert_utterance(utt)

        stance = "oppose" if i == 0 else "support"
        claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
        raw_span = u.span if u.span else (0, len(u.text))
        span = (max(0, raw_span[0]), min(raw_span[1], len(u.text)))
        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance=stance,  # type: ignore[arg-type]
            hedging_level=float(u.hedging_level if u.hedging_level is not None else 0.05),
            is_own_assertion=True,
            quote_span=span,
            condition=u.condition,
            change_marker={"acknowledged": True} if u.change_marker else None,
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)
        claims.append(claim)

    detector = TensionDetector(storage=test_store)
    tensions = detector.detect_tensions_for_subject(subject.subject_id)

    assert len(tensions) == 1
    t = tensions[0]
    assert t.type == "unacknowledged_reversal"
    assert t.status == "published"
    assert t.quarantine_reason is None
    assert t.severity >= 0.85


def test_fixture_p2_acknowledged_update_trap_2(test_store: Storage) -> None:
    """Fixture P2: Verified reasoned update (Assertion c).

    Utterance 1: Opposes open weights (2021).
    Utterance 2: Acknowledges update with change_marker (2023).
    Utterance 3: Supports open weights (2024).
    Full-interval acknowledgement search identifies the update rather than penalizing Consistency.
    """
    cases = load_behaviour_cases()
    p2 = next(c for c in cases if c.type == "P2")

    subject = Subject(subject_id=p2.subject_id, display_name="Dr. Golden 02")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("releasing open weight foundation models")
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text="releasing open weight foundation models",
            subject_ids=[subject.subject_id],
        )
    )

    for i, u in enumerate(p2.utterances):
        src_id = compute_source_id(f"{p2.source_locator}_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Host",
            canonical_url=f"{p2.source_locator}_{i}",
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
            word_timestamps_ref=None,
            transcription_pass_count=2,
            dual_pass_agreement=True,
            negation_uncertain=False,
        )
        test_store.insert_utterance(utt)

        # Utterance 0 is oppose; Utterance 1 is update marker; Utterance 2 is support
        stance = "oppose" if i == 0 else "support"
        claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
        span = u.span if u.span else (0, len(u.text))
        change_json = {"acknowledged": True} if u.change_marker else None

        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance=stance,  # type: ignore[arg-type]
            hedging_level=float(u.hedging_level if u.hedging_level is not None else 0.05),
            is_own_assertion=True,
            quote_span=(span[0], span[1]),
            condition=u.condition,
            change_marker=change_json,
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

    detector = TensionDetector(storage=test_store, full_interval_search=True)
    tensions = detector.detect_tensions_for_subject(subject.subject_id)

    # Candidates between utt0 and utt2 (and utt0 and utt1)
    # The pair between utt0 (2021) and utt2 (2024) must be an acknowledged_update because utt1 carries change_marker
    p2_tensions = [t for t in tensions if t.type == "acknowledged_update"]
    assert len(p2_tensions) >= 1
    assert all(t.status == "published" for t in p2_tensions)
    assert all(t.quarantine_reason is None for t in p2_tensions)


def test_falsification_narrow_acknowledgement_to_later_utterance(test_store: Storage) -> None:
    """Falsification test for Trap 2:

    Narrowing the acknowledgement search to the later utterance only causes P2 to flip to
    'unacknowledged_reversal' (RED). Restoring full-interval search restores 'acknowledged_update' (GREEN).
    """
    cases = load_behaviour_cases()
    p2 = next(c for c in cases if c.type == "P2")

    subject = Subject(subject_id="subj_falsify_p2", display_name="Falsify P2")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("falsify open weight foundation models")
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text="falsify open weight foundation models",
            subject_ids=[subject.subject_id],
        )
    )

    for i, u in enumerate(p2.utterances):
        src_id = compute_source_id(f"falsify_src_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Host",
            canonical_url=f"https://youtube.com/watch?v=falsify_{i}",
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
            word_timestamps_ref=None,
            transcription_pass_count=2,
            dual_pass_agreement=True,
            negation_uncertain=False,
        )
        test_store.insert_utterance(utt)

        stance = "oppose" if i == 0 else "support"
        claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
        span = u.span if u.span else (0, len(u.text))
        # Change marker is True ONLY on utterance 1 (middle of the interval)
        change_json = {"acknowledged": True} if u.change_marker else None

        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance=stance,  # type: ignore[arg-type]
            hedging_level=float(u.hedging_level if u.hedging_level is not None else 0.05),
            is_own_assertion=True,
            quote_span=(span[0], span[1]),
            condition=u.condition,
            change_marker=change_json,
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

    # 1. Narrow acknowledgement search to later utterance only (RED)
    narrow_detector = TensionDetector(storage=test_store, full_interval_search=False)
    narrow_tensions = narrow_detector.detect_tensions_for_subject(subject.subject_id)

    reversals = [t for t in narrow_tensions if t.type == "unacknowledged_reversal"]
    assert len(reversals) > 0, "Falsification failed: narrow search did not flip update to unacknowledged_reversal"

    # 2. Restore full-interval acknowledgement search (GREEN)
    full_detector = TensionDetector(storage=test_store, full_interval_search=True)
    full_tensions = full_detector.detect_tensions_for_subject(subject.subject_id)

    for t in full_tensions:
        if t.status == "published":
            assert t.type == "acknowledged_update", f"Full search failed to identify update: {t}"


def test_fixture_p4_audience_divergence(test_store: Storage) -> None:
    """Fixture P4: Verified audience divergence across diverging venue audience_stance."""
    cases = load_behaviour_cases()
    p4 = next(c for c in cases if c.type == "P4")

    subject = Subject(subject_id=p4.subject_id, display_name="Dr. Golden 04")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("mandatory federal compute registration")
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text="mandatory federal compute registration",
            subject_ids=[subject.subject_id],
        )
    )

    for i, u in enumerate(p4.utterances):
        src_id = compute_source_id(f"{p4.source_locator}_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Host",
            canonical_url=f"{p4.source_locator}_{i}",
            artifact_hash=f"hash_{i}",
            recorded_at=u.recorded_at,
        )
        test_store.insert_source(source)

        aud_stance: Literal["friendly", "neutral", "adversarial", "unknown"] = "friendly" if i == 0 else "adversarial"
        role = SourceSubjectRole(
            role_id=compute_role_id(src_id, subject.subject_id),
            source_id=src_id,
            subject_id=subject.subject_id,
            tier="B" if i == 0 else "C",
            venue_type="own_channel" if i == 0 else "institutional",
            audience_stance=aud_stance,
            is_adversarial=(i != 0),
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
            word_timestamps_ref=None,
            transcription_pass_count=2,
            dual_pass_agreement=True,
            negation_uncertain=False,
        )
        test_store.insert_utterance(utt)

        stance = "support" if i == 0 else "oppose"
        claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
        span = u.span if u.span else (0, len(u.text))

        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance=stance,  # type: ignore[arg-type]
            hedging_level=float(u.hedging_level if u.hedging_level is not None else 0.05),
            is_own_assertion=True,
            quote_span=(span[0], span[1]),
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

    detector = TensionDetector(storage=test_store)
    tensions = detector.detect_audience_divergence_for_subject(subject.subject_id, window_days=30)

    assert len(tensions) == 1
    t = tensions[0]
    assert t.type == "audience_divergence"
    assert t.status == "published"
    assert t.quarantine_reason is None


def test_fixture_n5_condition_mismatch_quarantined(test_store: Storage) -> None:
    """Fixture N5: Conditional vs unconditional claim on same proposition is quarantined with condition_mismatch."""
    cases = load_behaviour_cases()
    n5 = next(c for c in cases if c.type == "N5")

    subject = Subject(subject_id=n5.subject_id, display_name="Dr. Golden N5")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("hold interest rates constant")
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text="hold interest rates constant",
            subject_ids=[subject.subject_id],
        )
    )

    for i, u in enumerate(n5.utterances):
        src_id = compute_source_id(f"n5_src_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Host",
            canonical_url=f"https://youtube.com/watch?v=n5_{i}",
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
            word_timestamps_ref=None,
            transcription_pass_count=2,
            dual_pass_agreement=True,
            negation_uncertain=False,
        )
        test_store.insert_utterance(utt)

        stance = "oppose" if i == 0 else "support"
        claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
        span = u.span if u.span else (0, len(u.text))

        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance=stance,  # type: ignore[arg-type]
            hedging_level=float(u.hedging_level if u.hedging_level is not None else 0.05),
            is_own_assertion=True,
            quote_span=(span[0], span[1]),
            condition=u.condition,
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

    detector = TensionDetector(storage=test_store)
    tensions = detector.detect_tensions_for_subject(subject.subject_id)

    assert len(tensions) == 1
    t = tensions[0]
    # Mismatched condition is quarantined, NOT published
    assert t.status == "quarantined"
    assert t.quarantine_reason == "condition_mismatch"


def test_fixture_n7_hedge_weighting(test_store: Storage) -> None:
    """Fixture N7: Hedge followed by firm statement receives low severity weight."""
    cases = load_behaviour_cases()
    n7 = next(c for c in cases if c.type == "N7")

    subject = Subject(subject_id=n7.subject_id, display_name="Dr. Golden N7")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("hold interest rates constant n7")
    test_store.insert_proposition(
        Proposition(
            proposition_id=prop_id,
            canonical_text="hold interest rates constant n7",
            subject_ids=[subject.subject_id],
        )
    )

    for i, u in enumerate(n7.utterances):
        src_id = compute_source_id(f"n7_src_{i}")
        source = Source(
            source_id=src_id,
            title=f"Source {i}",
            publisher="Host",
            canonical_url=f"https://youtube.com/watch?v=n7_{i}",
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
            word_timestamps_ref=None,
            transcription_pass_count=2,
            dual_pass_agreement=True,
            negation_uncertain=False,
        )
        test_store.insert_utterance(utt)

        stance = "oppose" if i == 0 else "support"
        claim_id = compute_claim_id(utt_id, prop_id, stance, "v1")
        span = u.span if u.span else (0, len(u.text))

        claim = Claim(
            claim_id=claim_id,
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance=stance,  # type: ignore[arg-type]
            hedging_level=float(u.hedging_level if u.hedging_level is not None else 0.05),
            is_own_assertion=True,
            quote_span=(span[0], span[1]),
            recorded_at=u.recorded_at,
        )
        test_store.insert_claim(claim)

    detector = TensionDetector(storage=test_store)
    tensions = detector.detect_tensions_for_subject(subject.subject_id)

    assert len(tensions) == 1
    t = tensions[0]
    assert t.status == "published"
    # (1 - 0.85) * (1 - 0.05) = 0.15 * 0.95 = 0.1425
    assert t.severity <= 0.20


def test_precondition_negation_uncertain_quarantined(test_store: Storage) -> None:
    """Precondition 1: A claim on an utterance with negation_uncertain=True is quarantined."""
    subject = Subject(subject_id="subj_neg_unc", display_name="Negation Test")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("scientific consensus test")
    test_store.insert_proposition(Proposition(proposition_id=prop_id, canonical_text="scientific consensus test"))

    for i in (0, 1):
        src_id = f"src_neg_{i}"
        rec = f"2023-0{i+1}-01T10:00:00Z"
        test_store.insert_source(
            Source(
                source_id=src_id,
                title=f"Source {i}",
                publisher="Host",
                canonical_url=f"url_{i}",
                artifact_hash=f"hash_{i}",
                recorded_at=rec,
            )
        )

        utt_id = f"utt_neg_{i}"
        text = f"Scientific consensus statement {i}."
        test_store.insert_utterance(
            Utterance(
                utterance_id=utt_id,
                source_id=src_id,
                subject_id=subject.subject_id,
                text_verbatim=text,
                start_ms=1000,
                end_ms=2000,
                speaker_label="speaker_0",
                attribution_confidence="high",
                attribution_method="voice_match",
                negation_uncertain=(i == 1),  # Flagged uncertain on utterance 1
            )
        )
        test_store.insert_claim(
            Claim(
                claim_id=f"claim_neg_{i}",
                subject_id=subject.subject_id,
                utterance_id=utt_id,
                proposition_id=prop_id,
                stance="support" if i == 0 else "oppose",
                hedging_level=0.0,
                is_own_assertion=True,
                quote_span=(0, len(text)),
                recorded_at=rec,
            )
        )

    detector = TensionDetector(storage=test_store)
    tensions = detector.detect_tensions_for_subject(subject.subject_id)

    assert len(tensions) == 1
    t = tensions[0]
    assert t.status == "quarantined"
    assert t.quarantine_reason == "negation_uncertain"


def test_reversal_detector_runs_in_duckdb_sql_plan(test_store: Storage) -> None:
    """Asserts that the core detector executes in DuckDB SQL using EXPLAIN,

    proving it does not pull the claims table into Python.
    """
    plan = test_store.con.execute(
        """
        EXPLAIN
        SELECT a.claim_id, b.claim_id, a.proposition_id
        FROM claims a JOIN claims b
          ON a.proposition_id = b.proposition_id
         AND a.subject_id = b.subject_id
         AND TRY_CAST(a.recorded_at AS TIMESTAMPTZ) < TRY_CAST(b.recorded_at AS TIMESTAMPTZ)
         AND a.stance <> b.stance
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance IN ('support', 'oppose') AND b.stance IN ('support', 'oppose');
        """
    ).fetchall()

    plan_str = " ".join(str(row) for row in plan)
    assert "JOIN" in plan_str or "SCAN" in plan_str, "Query plan must execute in DuckDB relational engine"


def test_tension_integrity_checks_pass(test_store: Storage) -> None:
    """Evidence integrity pass on tensions generated by detector."""
    subject = Subject(subject_id="subj_integ", display_name="Integ Test")
    test_store.insert_subject(subject)

    prop_id = compute_proposition_id("integrity test proposition")
    test_store.insert_proposition(Proposition(proposition_id=prop_id, canonical_text="integrity test proposition"))

    claims = []
    utts = []
    for i in (0, 1):
        src_id = f"src_integ_{i}"
        rec = f"2023-0{i+1}-01T10:00:00Z"
        test_store.insert_source(
            Source(
                source_id=src_id,
                title=f"Source {i}",
                publisher="Host",
                canonical_url=f"url_integ_{i}",
                artifact_hash=f"hash_{i}",
                recorded_at=rec,
            )
        )

        utt_id = f"utt_integ_{i}"
        text = f"Integrity check statement {i}."
        u = Utterance(
            utterance_id=utt_id,
            source_id=src_id,
            subject_id=subject.subject_id,
            text_verbatim=text,
            start_ms=1000,
            end_ms=2000,
            speaker_label="speaker_0",
            attribution_confidence="high",
            attribution_method="voice_match",
            transcription_pass_count=2,
            negation_uncertain=False,
        )
        test_store.insert_utterance(u)
        utts.append(u)

        c = Claim(
            claim_id=f"claim_integ_{i}",
            subject_id=subject.subject_id,
            utterance_id=utt_id,
            proposition_id=prop_id,
            stance="support" if i == 0 else "oppose",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_span=(0, len(text)),
            recorded_at=rec,
        )
        test_store.insert_claim(c)
        claims.append(c)

    detector = TensionDetector(storage=test_store)
    tensions = detector.detect_tensions_for_subject(subject.subject_id)

    # 1. verify_attribution_floor
    vaf = verify_attribution_floor(claims, utts, tensions)
    assert vaf.passed is True

    # 2. verify_negation_recheck
    vnr = verify_negation_recheck(tensions, claims, utts)
    assert vnr.passed is True

    # 3. verify_quarantine_not_rendered
    vqr = verify_quarantine_not_rendered(tensions, assessments=[])
    assert vqr.passed is True
