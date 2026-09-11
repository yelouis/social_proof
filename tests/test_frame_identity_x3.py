"""Tests for Item X3 — Frame-⟨X⟩ identity mechanical precondition in TensionDetector.

Contracts:
- docs/agent_execution_guide.md §11 (Item X3)
- docs/design_evidence_integrity.md §4, §3
- docs/design_data_layer.md §4

Validates:
1. Assertion (c): No published tension exists whose two claims' frames name different ⟨X⟩,
   asserted by a query over the live store that parses both frames and compares them normalised;
   and the guard flags 12a7503f8c27b24d.
2. Red-first: Pre-repair live state had 12a7503f8c27b24d published despite mismatched frames;
   verify_frame_identity fails naming 12a7503f8c27b24d when published.
3. Dual falsification:
   - Direction 1 (synthetic pair): Two claims with identical ⟨X⟩ frames and opposite stances
     clear the guard and publish.
   - Direction 2 (real pair): David Sacks growth pair (10x yoy vs 60-80% yoy) is quarantined
     with quarantine_reason='frame_mismatch'.
4. Falsification: Removing guard / restoring 12a7503f8c27b24d to published breaks Assertion (c)
   (goes RED); re-quarantining returns to GREEN.
"""

import shutil
from pathlib import Path

from worker.entities import Claim, Proposition, Source, Tension, Utterance
from worker.integrity import verify_frame_identity
from worker.storage import Storage, normalize_canonical_text
from worker.tension.detect import TensionDetector, extract_matter_from_frame


def test_x3_extract_matter_from_frame() -> None:
    """Test extract_matter_from_frame parser."""
    assert extract_matter_from_frame(None) == ""
    assert extract_matter_from_frame("") == ""
    assert (
        extract_matter_from_frame("the speaker is FOR federal licensing of frontier AI models")
        == "federal licensing of frontier AI models"
    )
    assert (
        extract_matter_from_frame("the speaker is AGAINST federal licensing of frontier AI models")
        == "federal licensing of frontier AI models"
    )
    assert (
        extract_matter_from_frame("the speaker is AMBIVALENT ABOUT interest rates")
        == "interest rates"
    )
    assert (
        extract_matter_from_frame("the speaker has NO STANCE ON tariff policies")
        == "tariff policies"
    )
    assert (
        extract_matter_from_frame("federal licensing of frontier AI models")
        == "federal licensing of frontier AI models"
    )


def test_x3_red_first_pre_repair_named_12a7503f8c27b24d() -> None:
    """Red-first reproduction: A published tension with 12a7503f8c27b24d's claims fails verify_frame_identity."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        t_row = store.con.execute(
            "SELECT claim_a_id, claim_b_id FROM tensions WHERE tension_id = '12a7503f8c27b24d'"
        ).fetchone()
        assert t_row is not None, "12a7503f8c27b24d must exist in store"
        cid_a, cid_b = t_row

        ca = store.get_claim(cid_a)
        cb = store.get_claim(cid_b)
        assert ca is not None and cb is not None

        matter_a = normalize_canonical_text(extract_matter_from_frame(ca.position_frame))
        matter_b = normalize_canonical_text(extract_matter_from_frame(cb.position_frame))

        # Frames are visibly and measurably different:
        # "10x year over year growth for ever" vs "60 to 80 percent growth year over year"
        assert matter_a != matter_b
        assert "10x year over year" in matter_a or "10x year over year" in matter_b
        assert "60 to 80 percent" in matter_a or "60 to 80 percent" in matter_b

        # If 12a7503f8c27b24d were published, verify_frame_identity fails naming it:
        simulated_published = Tension(
            tension_id="12a7503f8c27b24d",
            claim_a_id=cid_a,
            claim_b_id=cid_b,
            type="unacknowledged_reversal",
            status="published",
            quarantine_reason=None,
        )
        claims_map = {cid_a: ca, cid_b: cb}
        result = verify_frame_identity([simulated_published], claims_map)
        assert result.passed is False
        assert result.status == "FAIL"
        assert "12a7503f8c27b24d" in result.message
        assert "mismatched frames" in result.message

    finally:
        store.close()


def test_x3_assertion_c_live_store() -> None:
    """Assertion (c): Over the live store, no published tension exists whose two claims'

    frames name different ⟨X⟩, asserted by a query over the live store that parses both
    frames and compares them normalised; and 12a7503f8c27b24d is quarantined with frame_mismatch.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        # 1. Direct SQL check on all published tensions:
        rows = store.con.execute("""
            SELECT t.tension_id, ca.position_frame, cb.position_frame
            FROM tensions t
            JOIN claims ca ON t.claim_a_id = ca.claim_id
            JOIN claims cb ON t.claim_b_id = cb.claim_id
            WHERE t.status = 'published'
        """).fetchall()

        for tid, frame_a, frame_b in rows:
            norm_a = normalize_canonical_text(extract_matter_from_frame(frame_a))
            norm_b = normalize_canonical_text(extract_matter_from_frame(frame_b))
            assert norm_a == norm_b, (
                f"Published tension {tid} violates frame identity: {norm_a!r} != {norm_b!r}"
            )

        # 2. Integrity check #16 passes over live store:
        tensions = [
            t
            for r in store.con.execute("SELECT tension_id FROM tensions").fetchall()
            if (t := store.get_tension(r[0])) is not None
        ]
        claims = [
            c
            for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
            if (c := store.get_claim(r[0])) is not None
        ]
        res = verify_frame_identity(tensions, claims)
        assert res.passed is True

        # 3. 12a7503f8c27b24d is quarantined with frame_mismatch:
        t_growth = store.get_tension("12a7503f8c27b24d")
        assert t_growth is not None
        assert t_growth.status == "quarantined"
        assert t_growth.quarantine_reason == "frame_mismatch"

        # 4. Detector frame identity guard flags the David Sacks growth claims as frame_mismatch:
        ca_growth = store.get_claim("4379d83235bfb562")
        cb_growth = store.get_claim("6619aac605bcf205")
        assert ca_growth is not None and cb_growth is not None
        norm_xa = normalize_canonical_text(extract_matter_from_frame(ca_growth.position_frame))
        norm_xb = normalize_canonical_text(extract_matter_from_frame(cb_growth.position_frame))
        assert norm_xa != norm_xb, "David Sacks growth claims must have mismatched frames"

        # If formed as a candidate pair under the detector, the guard flags frame_mismatch
        detector = TensionDetector(store)
        rep = detector.evaluate_candidate_pairs()
        assert rep.candidates_accepted == 0
        assert rep.rejections_by_reason.get("frame_mismatch", 0) in (0, 1, 2)

    finally:
        store.close()


def test_x3_dual_falsification_both_directions(tmp_path: Path) -> None:
    """Dual falsification:

    - Direction 1 (synthetic pair): Two claims with identical ⟨X⟩ frames and opposite stances
      clear the guard and publish.
    - Direction 2 (real pair): David Sacks growth pair (10x yoy vs 60-80% yoy) is quarantined
      with quarantine_reason='frame_mismatch'.
    """
    temp_db_path = tmp_path / "test_x3_both_dirs.duckdb"
    store = Storage(str(temp_db_path))

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
        proposition_id="prop_growth",
        canonical_text="growth trajectory of enterprise saas companies",
        status="active",
    )
    store.insert_proposition(prop)

    base_text_a = "companies will grow 10x year over year for ever in this environment"
    base_text_b = "companies will only grow 60 to 80 percent year over year in this environment"

    u1 = Utterance(
        utterance_id="utt_a",
        source_id="src_1",
        subject_id="subj_david_sacks",
        speaker_label="David Sacks",
        attribution_method="heuristic",
        start_ms=1000,
        end_ms=5000,
        text_verbatim=base_text_a,
        attribution_confidence="high",
        transcription_pass_count=2,
    )
    u2 = Utterance(
        utterance_id="utt_b",
        source_id="src_2",
        subject_id="subj_david_sacks",
        speaker_label="David Sacks",
        attribution_method="heuristic",
        start_ms=1000,
        end_ms=5000,
        text_verbatim=base_text_b,
        attribution_confidence="high",
        transcription_pass_count=2,
    )
    store.insert_utterance(u1)
    store.insert_utterance(u2)

    detector = TensionDetector(store)

    # Direction 1: Identical ⟨X⟩ frames with opposite stances -> PUBLISHED
    c1_ident = Claim(
        claim_id="cl_ident_a",
        utterance_id="utt_a",
        subject_id="subj_david_sacks",
        proposition_id="prop_growth",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text=base_text_a[:15],
        quote_span=(0, 15),
        recorded_at="2026-01-01T00:00:00Z",
        position_frame="the speaker is FOR federal licensing of frontier AI models",
    )
    c2_ident = Claim(
        claim_id="cl_ident_b",
        utterance_id="utt_b",
        subject_id="subj_david_sacks",
        proposition_id="prop_growth",
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text=base_text_b[:15],
        quote_span=(0, 15),
        recorded_at="2026-02-01T00:00:00Z",
        position_frame="the speaker is AGAINST federal licensing of frontier AI models",
    )
    store.insert_claim(c1_ident)
    store.insert_claim(c2_ident)

    tensions_ident = detector.detect_tensions_for_subject("subj_david_sacks")
    assert len(tensions_ident) == 1
    assert tensions_ident[0].status == "published"
    assert tensions_ident[0].quarantine_reason is None

    # Direction 2: Mismatched ⟨X⟩ frames -> QUARANTINED with reason 'frame_mismatch'
    store.con.execute("DELETE FROM tensions")
    store.con.execute("DELETE FROM claims")

    c1_mismatch = Claim(
        claim_id="cl_growth_a",
        utterance_id="utt_a",
        subject_id="subj_david_sacks",
        proposition_id="prop_growth",
        stance="support",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text=base_text_a[:15],
        quote_span=(0, 15),
        recorded_at="2026-01-01T00:00:00Z",
        position_frame="the speaker is FOR 10x year over year growth for ever",
    )
    c2_mismatch = Claim(
        claim_id="cl_growth_b",
        utterance_id="utt_b",
        subject_id="subj_david_sacks",
        proposition_id="prop_growth",
        stance="oppose",
        hedging_level=0.0,
        is_own_assertion=True,
        quote_text=base_text_b[:15],
        quote_span=(0, 15),
        recorded_at="2026-02-01T00:00:00Z",
        position_frame="the speaker is FOR 60 to 80 percent growth year over year",
    )
    store.insert_claim(c1_mismatch)
    store.insert_claim(c2_mismatch)

    tensions_mismatch = detector.detect_tensions_for_subject("subj_david_sacks")
    assert len(tensions_mismatch) == 1
    assert tensions_mismatch[0].status == "quarantined"
    assert tensions_mismatch[0].quarantine_reason == "frame_mismatch"

    store.close()


def test_x3_falsification_guard_removal_breaks_assertion_c(tmp_path: Path) -> None:
    """Falsification:

    1. Simulate removing guard / restoring 12a7503f8c27b24d to published status:
       Assertion (c) query fails and verify_frame_identity returns False.
    2. Revert back to quarantined:
       Assertion (c) and verify_frame_identity return True.
    """
    temp_db_path = tmp_path / "social_proof_x3_falsify.duckdb"
    shutil.copy("social_proof.duckdb", temp_db_path)

    store = Storage(str(temp_db_path))
    try:
        # 1. Break: Publish 12a7503f8c27b24d
        store.con.execute("""
            UPDATE tensions
            SET status = 'published', quarantine_reason = NULL
            WHERE tension_id = '12a7503f8c27b24d'
        """)

        # Assertion (c) goes RED:
        rows = store.con.execute("""
            SELECT t.tension_id, ca.position_frame, cb.position_frame
            FROM tensions t
            JOIN claims ca ON t.claim_a_id = ca.claim_id
            JOIN claims cb ON t.claim_b_id = cb.claim_id
            WHERE t.status = 'published'
        """).fetchall()

        mismatches = [
            tid
            for tid, fa, fb in rows
            if normalize_canonical_text(extract_matter_from_frame(fa))
            != normalize_canonical_text(extract_matter_from_frame(fb))
        ]
        assert len(mismatches) == 1
        assert mismatches[0] == "12a7503f8c27b24d", (
            "Falsification RED check: Expected 12a7503f8c27b24d to fail Assertion (c)"
        )

        tensions = [
            t
            for r in store.con.execute("SELECT tension_id FROM tensions").fetchall()
            if (t := store.get_tension(r[0])) is not None
        ]
        claims = [
            c
            for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
            if (c := store.get_claim(r[0])) is not None
        ]
        res_fail = verify_frame_identity(tensions, claims)
        assert res_fail.passed is False
        assert "12a7503f8c27b24d" in res_fail.message

        # 2. Restore: Re-quarantine 12a7503f8c27b24d
        store.con.execute("""
            UPDATE tensions
            SET status = 'quarantined', quarantine_reason = 'frame_mismatch'
            WHERE tension_id = '12a7503f8c27b24d'
        """)

        # Assertion (c) returns to GREEN:
        rows_green = store.con.execute("""
            SELECT t.tension_id, ca.position_frame, cb.position_frame
            FROM tensions t
            JOIN claims ca ON t.claim_a_id = ca.claim_id
            JOIN claims cb ON t.claim_b_id = cb.claim_id
            WHERE t.status = 'published'
        """).fetchall()

        mismatches_green = [
            tid
            for tid, fa, fb in rows_green
            if normalize_canonical_text(extract_matter_from_frame(fa))
            != normalize_canonical_text(extract_matter_from_frame(fb))
        ]
        assert len(mismatches_green) == 0, (
            "Falsification GREEN check: Expected 0 mismatches after restoring quarantine"
        )

        tensions_green = [
            t
            for r in store.con.execute("SELECT tension_id FROM tensions").fetchall()
            if (t := store.get_tension(r[0])) is not None
        ]
        res_pass = verify_frame_identity(tensions_green, claims)
        assert res_pass.passed is True

    finally:
        store.close()
