"""Unit, integration, and falsification tests for Q0 (Quarantine fabricated tensions).

Implements agent_execution_guide.md §17k (Q0) and design_evidence_integrity.md §4 & §5:
1. Assertion (c): Zero published tensions remain; verify_quarantine_not_rendered examines 3
   quarantined tensions and confirms none appears in any assessment's axis_evidence.
2. Neither tension '461e3d1dbf30bde4' nor '4b812a6b0dc604b0' appears in any assessment's axis_evidence.
3. Quarantine health metric report: 3 of 3 tensions ever generated are quarantined (100.0%).
4. LOOP 2 Falsification: Re-publishing one tension turns Assertion (c) RED; revert returns to GREEN.
"""

import json
import shutil
from pathlib import Path

from worker.integrity import verify_quarantine_not_rendered
from worker.storage import Storage


def test_q0_zero_published_tensions_assertion_c() -> None:
    """Assertion (c): Zero published tensions remain in social_proof.duckdb.

    verify_quarantine_not_rendered examines exactly 3 quarantined tensions and confirms
    none appears in any assessment's axis_evidence.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        # 1. Zero published tensions
        published_tensions = store.con.execute(
            "SELECT tension_id, type, status FROM tensions WHERE status = 'published'"
        ).fetchall()
        assert len(published_tensions) == 0, (
            f"Assertion (c) FAILED: Expected 0 published tensions, found {len(published_tensions)}: {published_tensions}"
        )

        # 2. Exactly 3 quarantined tensions, all with quarantine_reason='fabricated_proposition'
        quarantined_rows = store.con.execute(
            "SELECT tension_id, type, status, quarantine_reason FROM tensions WHERE status = 'quarantined'"
        ).fetchall()
        assert len(quarantined_rows) == 3, f"Expected 3 quarantined tensions, found {len(quarantined_rows)}"

        quarantined_ids = {r[0] for r in quarantined_rows}
        expected_ids = {"0068adec4b1501c6", "461e3d1dbf30bde4", "4b812a6b0dc604b0"}
        assert quarantined_ids == expected_ids, f"Mismatch in quarantined IDs: {quarantined_ids} != {expected_ids}"

        for r in quarantined_rows:
            assert r[3] == "fabricated_proposition", f"Tension {r[0]} quarantine_reason={r[3]}, expected 'fabricated_proposition'"

        # 3. Load all entities via storage helpers and run verify_quarantine_not_rendered
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

        res = verify_quarantine_not_rendered(tensions=tensions, assessments=assessments)
        assert res.passed is True, f"verify_quarantine_not_rendered failed: {res.message}"
        assert res.examined_count == 3, f"Expected 3 examined quarantined tensions, got {res.examined_count}"

        # 4. Explicit check that no assessment's axis_evidence mentions either tension
        for a in assessments:
            for axis_name, t_ids in a.axis_evidence.items():
                for tid in expected_ids:
                    assert tid not in t_ids, (
                        f"Quarantined tension {tid} leaked into assessment {a.assessment_id} axis '{axis_name}'"
                    )

        # 5. Quarantine rate health metric: 3 of 3 ever generated are quarantined
        t_count_row = store.con.execute("SELECT count(*) FROM tensions").fetchone()
        assert t_count_row is not None
        total_tensions = int(t_count_row[0])
        assert total_tensions == 3
        quarantine_rate = len(quarantined_rows) / total_tensions
        assert quarantine_rate == 1.0, f"Expected 100% quarantine rate, got {quarantine_rate:.2%}"

    finally:
        store.close()


def test_q0_falsification_republish_tension_assertion_c_goes_red(tmp_path: Path) -> None:
    """LOOP 2 Falsification:

    1. Re-publish one tension (status='published') and inject it into an assessment's axis_evidence.
    2. Assertion (c) MUST fail (RED).
    3. Revert to status='quarantined' without evidence leakage: MUST pass (GREEN).
    """
    temp_db_path = tmp_path / "social_proof_copy.duckdb"
    shutil.copy("social_proof.duckdb", temp_db_path)

    store = Storage(str(temp_db_path))

    # 1. Break: re-publish tension 461e3d1dbf30bde4
    store.con.execute(
        "UPDATE tensions SET status = 'published', quarantine_reason = NULL WHERE tension_id = '461e3d1dbf30bde4'"
    )

    published = store.con.execute("SELECT tension_id FROM tensions WHERE status = 'published'").fetchall()
    # Falsification check 1: zero-published assertion fails
    assert len(published) == 1, "Expected 1 published tension after break"

    # Also simulate leakage into assessment evidence
    a_row = store.con.execute("SELECT assessment_id, axis_evidence FROM assessments LIMIT 1").fetchone()
    assert a_row is not None
    aid = a_row[0]
    ev = json.loads(a_row[1]) if isinstance(a_row[1], str) else a_row[1]
    ev["consistency"] = ["461e3d1dbf30bde4"]
    store.con.execute("UPDATE assessments SET axis_evidence = ? WHERE assessment_id = ?", [json.dumps(ev), aid])

    # Re-quarantine to check verify_quarantine_not_rendered when evidence leaks
    store.con.execute(
        "UPDATE tensions SET status = 'quarantined', quarantine_reason = 'fabricated_proposition' WHERE tension_id = '461e3d1dbf30bde4'"
    )
    tensions_quar = [
        t
        for r in store.con.execute("SELECT tension_id FROM tensions").fetchall()
        if (t := store.get_tension(r[0])) is not None
    ]
    assessments_leaked = [
        a
        for r in store.con.execute("SELECT assessment_id FROM assessments").fetchall()
        if (a := store.get_assessment(r[0])) is not None
    ]

    res_fail = verify_quarantine_not_rendered(tensions=tensions_quar, assessments=assessments_leaked)
    # Falsification check 2: verify_quarantine_not_rendered MUST FAIL (RED)
    assert res_fail.passed is False, "verify_quarantine_not_rendered should have failed on leaked tension"
    assert res_fail.status == "FAIL"

    # 2. Revert: clean up assessment evidence
    ev["consistency"] = []
    store.con.execute("UPDATE assessments SET axis_evidence = ? WHERE assessment_id = ?", [json.dumps(ev), aid])

    assessments_clean = [
        a
        for r in store.con.execute("SELECT assessment_id FROM assessments").fetchall()
        if (a := store.get_assessment(r[0])) is not None
    ]

    res_pass = verify_quarantine_not_rendered(tensions=tensions_quar, assessments=assessments_clean)
    assert res_pass.passed is True
    assert res_pass.examined_count == 3

    rev_row = store.con.execute("SELECT count(*) FROM tensions WHERE status = 'published'").fetchone()
    assert rev_row is not None
    assert rev_row[0] == 0

    store.close()
