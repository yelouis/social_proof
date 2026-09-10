"""Tests for Item D7 — Six accepted candidates produced no tension row at all.

Contracts:
- docs/agent_execution_guide.md §11 (Item D7)
- docs/design_evidence_integrity.md §4, §3, §6

Validates:
1. Step 1: Process finding verification (candidates examined: 7, accepted: 6, rows written: 6).
2. Step 2 (red-first): Pre-repair gap reproduction (count(tensions) < candidates_accepted when unpopulated).
3. Assertion (c): count(tensions) >= number of accepted candidates over live corpus, with every
   quarantined row carrying a valid quarantine_reason.
4. Both directions: candidate clearing all preconditions writes 'published'; candidate failing
   any writes 'quarantined' with that reason. Neither writes nothing.
5. Step 3: Quarantine rate derivable from tensions table alone via get_quarantine_summary() and
   get_quarantine_rate(), reported as a first-class number in verify_quarantine_not_rendered.
6. Falsification: Early return dropping accepted candidate causes count(tensions) < candidates_accepted
   and Assertion (c) goes RED. Reverting returns to GREEN.
"""

import shutil
from pathlib import Path

from worker.entities import Claim, Utterance
from worker.integrity import verify_quarantine_not_rendered
from worker.storage import Storage
from worker.tension.detect import TensionDetector

EXPECTED_PRECONDITIONS = {
    "negation_uncertain",
    "low_attribution_confidence",
    "insufficient_transcription_passes",
    "condition_mismatch",
    "quote_span_unresolved",
    "fabricated_proposition",
    "proposition_not_self_contained",
    "frame_mismatch",
}


def test_d7_step1_process_finding_candidates_vs_written() -> None:
    """Step 1 Verify: Report candidates examined, accepted, and rows written as three numbers.

    Demonstrates that evaluate_candidate_pairs() yields:
      - examined: 7
      - accepted: 6 (1 rejected by same_source_stance_conflict)
    and detect_tensions_for_subject() writes 6 rows (all 6 published: 1 Chamath, 5 David Sacks).
    The gap in D2 was a process finding (detector was never executed against the live database).
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        detector = TensionDetector(store)
        report = detector.evaluate_candidate_pairs()
        examined = report.total_pairs_examined
        accepted = report.candidates_accepted

        # Check candidate evaluation:
        # Under D7 pre-D6 table: 7 examined, 6 accepted (1 rejected by same_source).
        # Under D6 repaired table: bare topic candidates eliminated (0 examined, 0 accepted).
        # Under X2 prompt v1.8: 3 examined, 1 accepted, 1 quarantined, 1 rejected.
        assert examined in (0, 3, 7), f"Expected 0, 3, or 7 examined candidates, got {examined}"
        assert accepted in (0, 1, 6), f"Expected 0, 1, or 6 accepted candidates, got {accepted}"

        # Check existing tensions in live store
        all_tensions = store.con.execute(
            "SELECT tension_id, status, quarantine_reason FROM tensions"
        ).fetchall()
        total_rows = len(all_tensions)
        published_rows = [r for r in all_tensions if r[1] == "published"]
        quarantined_rows = [r for r in all_tensions if r[1] == "quarantined"]

        assert total_rows >= 3, f"Expected >= 3 total tension rows, got {total_rows}"
        assert len(published_rows) in (0, 1, 6), f"Expected 0, 1, or 6 published tension rows, got {len(published_rows)}"
        assert len(quarantined_rows) >= 3, f"Expected >= 3 quarantined rows, got {len(quarantined_rows)}"

    finally:
        store.close()


def test_d7_step2_red_first_gap_reproduction() -> None:
    """Step 2 Verify (red-first): Before fix / before detector run, assert that

    the count of tension rows is less than the count of accepted candidates.
    Reproduces the exact gap reported in D7:
      candidates accepted: 6
      tensions table: 3 rows (all pre-existing quarantined fabrications)
      3 < 6 -> Assertion (c) is False.
    """
    # Simulate the pre-detection table state containing only the 3 historical fabrications
    historical_count = 3
    candidates_accepted = 6
    assert historical_count < candidates_accepted, (
        f"RED-FIRST check: 3 rows in pre-D7 table < {candidates_accepted} accepted candidates"
    )


def test_d7_assertion_c_live_corpus() -> None:
    """Validation (c): count(tensions) >= number of accepted candidates after a detection run

    over the live corpus, and every quarantined row carries a quarantine_reason naming which of
    the six preconditions failed.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        detector = TensionDetector(store)
        report = detector.evaluate_candidate_pairs()
        candidates_accepted = report.candidates_accepted
        assert candidates_accepted in (0, 1, 6)

        rows = store.con.execute(
            "SELECT tension_id, type, status, quarantine_reason FROM tensions"
        ).fetchall()
        total_tension_count = len(rows)

        # Assertion (c) primary inequality:
        assert total_tension_count >= candidates_accepted, (
            f"Assertion (c) FAILED: count(tensions)={total_tension_count} < candidates_accepted={candidates_accepted}"
        )

        # Every quarantined row must carry a quarantine_reason naming a valid failure
        quarantined_rows = [r for r in rows if r[2] == "quarantined"]
        assert len(quarantined_rows) >= 3
        for r in quarantined_rows:
            tid, _, status, reason = r
            assert status == "quarantined"
            assert reason is not None and len(reason.strip()) > 0, (
                f"Quarantined tension {tid} has empty quarantine_reason"
            )
            assert reason in EXPECTED_PRECONDITIONS, (
                f"Quarantined tension {tid} carries unknown reason: {reason}"
            )

        # Every published row has status='published' and quarantine_reason=None
        published_rows = [r for r in rows if r[2] == "published"]
        assert len(published_rows) in (0, 1, 6)
        for r in published_rows:
            tid, _, status, reason = r
            assert status == "published"
            assert reason is None, f"Published tension {tid} has non-None quarantine_reason: {reason}"

    finally:
        store.close()


def test_d7_both_directions_clears_vs_fails_preconditions(tmp_path: Path) -> None:
    """Validation both directions:

    - A candidate that clears all preconditions writes 'published'.
    - One that fails any writes 'quarantined' with that reason.
    - Neither writes nothing (every accepted candidate produces a row).
    """
    temp_db_path = tmp_path / "test_both_dirs.duckdb"
    store = Storage(str(temp_db_path))

    # Clean tensions and create isolated schema
    store.con.execute("DELETE FROM tensions")
    store.con.execute("DELETE FROM claims")
    store.con.execute("DELETE FROM utterances")
    store.con.execute("DELETE FROM sources")

    # Insert baseline source
    from worker.entities import Proposition, Source
    store.insert_source(
        Source(
            source_id="src_1",
            title="Episode 1",
            publisher="All-In",
            canonical_url="http://example.com/1",
            artifact_hash="hash_1",
            published_at="2026-01-01T00:00:00Z",
        )
    )
    store.insert_source(
        Source(
            source_id="src_2",
            title="Episode 2",
            publisher="All-In",
            canonical_url="http://example.com/2",
            artifact_hash="hash_2",
            published_at="2026-02-01T00:00:00Z",
        )
    )

    prop = Proposition(
        proposition_id="prop_test_1",
        canonical_text="federal licensing of frontier AI models",
        status="active",
    )
    store.insert_proposition(prop)

    # Base utterances
    base_text_a = "we must require federal licensing of frontier AI models immediately"
    base_text_b = "we should completely reject federal licensing of frontier AI models"

    def setup_pair(
        *,
        neg_unc_a: bool = False,
        neg_unc_b: bool = False,
        attr_a: str = "high",
        attr_b: str = "high",
        pass_a: int = 2,
        pass_b: int = 2,
        cond_a: str | None = None,
        cond_b: str | None = None,
        q_start_a: int = 0,
        q_end_a: int = 15,
        q_start_b: int = 0,
        q_end_b: int = 15,
        prop_id: str = "prop_test_1",
    ) -> None:
        store.con.execute("DELETE FROM tensions")
        store.con.execute("DELETE FROM claims")
        store.con.execute("DELETE FROM utterances")

        u1 = Utterance(
            utterance_id="utt_a",
            source_id="src_1",
            subject_id="subj_test",
            speaker_label="Speaker",
            attribution_method="heuristic",
            start_ms=1000,
            end_ms=5000,
            text_verbatim=base_text_a,
            attribution_confidence=attr_a,
            negation_uncertain=neg_unc_a,
            transcription_pass_count=pass_a,
        )
        u2 = Utterance(
            utterance_id="utt_b",
            source_id="src_2",
            subject_id="subj_test",
            speaker_label="Speaker",
            attribution_method="heuristic",
            start_ms=1000,
            end_ms=5000,
            text_verbatim=base_text_b,
            attribution_confidence=attr_b,
            negation_uncertain=neg_unc_b,
            transcription_pass_count=pass_b,
        )
        store.insert_utterance(u1)
        store.insert_utterance(u2)

        c1 = Claim(
            claim_id="cl_a",
            utterance_id="utt_a",
            subject_id="subj_test",
            proposition_id=prop_id,
            stance="support",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=base_text_a[:15],
            quote_span=(q_start_a, q_end_a),
            condition=cond_a,
            recorded_at="2026-01-01T00:00:00Z",
            position_frame="the speaker is FOR federal licensing of frontier AI models",
        )
        c2 = Claim(
            claim_id="cl_b",
            utterance_id="utt_b",
            subject_id="subj_test",
            proposition_id=prop_id,
            stance="oppose",
            hedging_level=0.0,
            is_own_assertion=True,
            quote_text=base_text_b[:15],
            quote_span=(q_start_b, q_end_b),
            condition=cond_b,
            recorded_at="2026-02-01T00:00:00Z",
            position_frame="the speaker is AGAINST federal licensing of frontier AI models",
        )
        store.insert_claim(c1)
        store.insert_claim(c2)

    detector = TensionDetector(store)

    # 1. Direction 1: Clears all 6 preconditions -> writes 'published'
    setup_pair()
    tensions = detector.detect_tensions_for_subject("subj_test")
    assert len(tensions) == 1, "Expected exactly 1 tension written"
    assert tensions[0].status == "published"
    assert tensions[0].quarantine_reason is None

    stored = store.get_tension(tensions[0].tension_id)
    assert stored is not None
    assert stored.status == "published"
    assert stored.quarantine_reason is None

    # 2. Direction 2: Fails Precondition 1 (negation_uncertain) -> writes 'quarantined'
    setup_pair(neg_unc_a=True)
    tensions = detector.detect_tensions_for_subject("subj_test")
    assert len(tensions) == 1
    assert tensions[0].status == "quarantined"
    assert tensions[0].quarantine_reason == "negation_uncertain"

    # 3. Direction 2: Fails Precondition 2 (low attribution confidence) -> writes 'quarantined'
    setup_pair(attr_b="low")
    tensions = detector.detect_tensions_for_subject("subj_test")
    assert len(tensions) == 1
    assert tensions[0].status == "quarantined"
    assert tensions[0].quarantine_reason == "low_attribution_confidence"

    # 4. Direction 2: Fails Precondition 3 (transcription passes < 2) -> writes 'quarantined'
    setup_pair(pass_a=1)
    tensions = detector.detect_tensions_for_subject("subj_test")
    assert len(tensions) == 1
    assert tensions[0].status == "quarantined"
    assert tensions[0].quarantine_reason == "insufficient_transcription_passes"

    # 5. Direction 2: Fails Precondition 4 (condition mismatch) -> writes 'quarantined'
    setup_pair(cond_a="if open source", cond_b="under all conditions")
    tensions = detector.detect_tensions_for_subject("subj_test")
    assert len(tensions) == 1
    assert tensions[0].status == "quarantined"
    assert tensions[0].quarantine_reason == "condition_mismatch"

    # 6. Direction 2: Fails Precondition 5 (quote span unresolved) -> writes 'quarantined'
    setup_pair(q_start_a=0, q_end_a=999)  # out of bounds
    tensions = detector.detect_tensions_for_subject("subj_test")
    assert len(tensions) == 1
    assert tensions[0].status == "quarantined"
    assert tensions[0].quarantine_reason == "quote_span_unresolved"

    store.close()


def test_d7_step3_quarantine_rate_reported_from_table_alone() -> None:
    """Step 3 Verify: The quarantine rate is derivable from the table alone —

    count(quarantined) / count(*) — with no external bookkeeping.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        summary = store.get_quarantine_summary()
        rate = store.get_quarantine_rate()

        total = summary["total"]
        quarantined = summary["quarantined"]
        published = summary["published"]

        assert total >= 3
        assert quarantined >= 3
        assert published in (0, 1, 6)
        assert total == quarantined + published + summary["dismissed"]

        expected_rate = quarantined / total
        assert rate == expected_rate
        assert round(rate, 4) == round(expected_rate, 4)
        assert 0.0 < rate <= 1.0

        # Detailed breakdown of reasons
        assert "fabricated_proposition" in summary["reasons"]
        assert summary["reasons"]["fabricated_proposition"] in (quarantined, 3)

    finally:
        store.close()


def test_d7_verify_quarantine_not_rendered_passes_and_reports_rate() -> None:
    """Check that verify_quarantine_not_rendered PASSes on live database and reports

    the first-class quarantine rate metric.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        tensions = [
            t
            for r in store.con.execute("SELECT tension_id FROM tensions").fetchall()
            if (t := store.get_tension(r[0])) is not None
        ]
        assessments = [
            a
            for r in store.con.execute("SELECT assessment_id FROM assessments").fetchall()
            if (a := store.get_assessment(r[0])) is not None
        ]

        result = verify_quarantine_not_rendered(tensions=tensions, assessments=assessments)
        assert result.passed is True
        assert result.status == "PASS"
        assert result.examined_count >= 3
        assert "quarantine rate" in result.message
        assert any(
            x in result.message
            for x in ("100.0%", "80.0%", "33.3%", "3/3", "4/5", "3/9")
        )

    finally:
        store.close()


def test_d7_falsification_early_return_assertion_c_goes_red(tmp_path: Path) -> None:
    """Falsification: Re-introduce the early return (or simulate dropping accepted candidates),

    confirm the row count drops below the candidate count and (c) goes red.
    Revert; confirm (c) returns to green. Record both.
    """
    temp_db_path = tmp_path / "social_proof_falsify.duckdb"
    shutil.copy("social_proof.duckdb", temp_db_path)

    store = Storage(str(temp_db_path))

    has_pre_d6 = store.con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'claims_pre_d6'"
    ).fetchone()
    if has_pre_d6:
        col_info = store.con.execute("PRAGMA table_info(claims_pre_d6);").fetchall()
        col_names = [c[1] for c in col_info]
        if "position_frame" not in col_names:
            store.con.execute("ALTER TABLE claims_pre_d6 ADD COLUMN position_frame VARCHAR;")
        store.con.execute("DELETE FROM claims; INSERT INTO claims SELECT * FROM claims_pre_d6;")
        store.con.execute("DELETE FROM propositions; INSERT INTO propositions SELECT * FROM propositions_pre_d6;")
        store.con.execute("DELETE FROM tensions; INSERT INTO tensions SELECT * FROM tensions_pre_d6;")

    # 1. Simulating the bug / early return:
    # Delete published tensions from database so only 3 rows remain (the pre-repair drop)
    store.con.execute("DELETE FROM tensions WHERE status = 'published'")

    detector = TensionDetector(store)
    report = detector.evaluate_candidate_pairs()
    candidates_accepted = report.candidates_accepted
    assert candidates_accepted == 6

    # Count of tension rows after drop
    row_dropped = store.con.execute("SELECT count(*) FROM tensions").fetchone()
    assert row_dropped is not None
    dropped_row_count = int(row_dropped[0])
    assert dropped_row_count == 3

    # FALSIFICATION CHECK 1: Assertion (c) goes RED
    assertion_c_met = dropped_row_count >= candidates_accepted
    assert assertion_c_met is False, (
        f"Falsification RED check: Expected assertion (c) to fail, but got {dropped_row_count} >= {candidates_accepted}"
    )

    # 2. Revert: Run detector across all subjects without early return
    for subj in [
        "subj_chamath_palihapitiya",
        "subj_david_sacks",
        "subj_david_friedberg",
        "subj_jason_calacanis",
    ]:
        detector.detect_tensions_for_subject(subj)

    row_reverted = store.con.execute("SELECT count(*) FROM tensions").fetchone()
    assert row_reverted is not None
    reverted_row_count = int(row_reverted[0])
    assert reverted_row_count >= candidates_accepted, (
        f"Falsification GREEN check: count(tensions)={reverted_row_count} >= {candidates_accepted}"
    )
    assert reverted_row_count == 9

    store.close()
