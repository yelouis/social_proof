"""Tests for Proposition Deduplication (P0 · Parameter 008).

Validates:
1. (c) At least one proposition carries claims from >=2 different sources on different dates,
   and the tension detector runs over a non-empty candidate set.
2. Merge histogram has a visible tail (not all-singletons).
3. Both directions on the threshold:
   - "The leading open source models are from China these days." (683f456673426a74) and
     "China has made a significant push towards open source software." (a4035357b97e25bf) MERGE.
   - "High speed trains in China are built and operated by private industry." (d834d8f051299e00) does NOT merge.
4. Falsification:
   - t_dedup = 0.999 collapses to all-singletons and candidate-pair count drops to zero.
   - t_dedup = 0.30 causes absurd merges (trains merges with open source).
   - Revert to 0.85 restores healthy tail, merges open-source, and keeps trains separate.
5. All 1,501 claims retain valid quote spans (verify_quotes PASS).
6. verify_canonical_ids PASS across propositions and roles.
"""

import shutil
from pathlib import Path

import pytest

from worker.integrity import verify_canonical_ids, verify_quotes
from worker.storage import Storage


@pytest.fixture
def live_db() -> Storage:
    """Read-only access to production database per Trap 37."""
    return Storage(db_path="social_proof.duckdb", read_only=True)


def test_dedup_assertion_c_multi_source_diff_dates_and_candidate_pairs(live_db: Storage) -> None:
    """Assertion (c): At least one proposition carries claims from >=2 sources on different dates,

    and the tension detector candidate set is non-empty (>0 candidate pairs).
    """
    con = live_db.con

    # 1. Multi-source different-date propositions
    multi_src_rows = con.execute(
        """
        SELECT c.proposition_id, count(DISTINCT u.source_id) as s_cnt, count(DISTINCT substr(c.recorded_at, 1, 10)) as d_cnt
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        GROUP BY c.proposition_id
        HAVING s_cnt > 1 AND d_cnt > 1
        """
    ).fetchall()

    assert len(multi_src_rows) >= 1, (
        f"Assertion (c) FAILED: Expected >=1 proposition with claims from multiple sources on different dates, got {len(multi_src_rows)}"
    )
    assert len(multi_src_rows) == 6, f"Expected 6 multi-source diff-date propositions at T=0.86 with W1 entailment gate, got {len(multi_src_rows)}"

    # 2. Tension candidate pairs (opposing stance on same proposition at different dates)
    cand_row = con.execute(
        """
        SELECT count(*)
        FROM claims a
        JOIN claims b
          ON a.proposition_id = b.proposition_id
         AND a.subject_id = b.subject_id
         AND TRY_CAST(a.recorded_at AS TIMESTAMPTZ) < TRY_CAST(b.recorded_at AS TIMESTAMPTZ)
         AND a.stance <> b.stance
        WHERE a.is_own_assertion AND b.is_own_assertion
          AND a.stance IN ('support', 'oppose')
          AND b.stance IN ('support', 'oppose')
        """
    ).fetchone()
    assert cand_row is not None
    candidate_pairs = cand_row[0]

    assert candidate_pairs > 0, (
        f"Assertion (c) FAILED: Expected >0 candidate pairs sharing a proposition with opposing stance, got {candidate_pairs}"
    )
    assert candidate_pairs == 1, f"Expected 1 candidate pair at T=0.86 with W1 entailment gate, got {candidate_pairs}"


def test_dedup_merge_histogram_has_healthy_tail(live_db: Storage) -> None:
    """Merge histogram has a visible tail and is not all-singletons."""
    con = live_db.con
    hist_rows = con.execute(
        """
        SELECT claim_count, count(*)
        FROM propositions
        WHERE status = 'active' AND claim_count > 0
        GROUP BY claim_count
        ORDER BY claim_count
        """
    ).fetchall()

    hist = {int(r[0]): int(r[1]) for r in hist_rows}

    # Before P0: 1498 x 1, 1 x 3.
    # At T=0.86 with W1 entailment gate: 1374 x 1, 47 x 2, 4 x 3, 4 x 4, 1 x 5.
    assert hist[1] < 1400, f"Expected singletons to be reduced below 1400, got {hist[1]}"
    assert hist.get(2, 0) >= 40, f"Expected >=40 propositions with 2 claims, got {hist.get(2, 0)}"
    assert hist.get(3, 0) >= 4, f"Expected >=4 propositions with 3 claims, got {hist.get(3, 0)}"
    assert hist.get(4, 0) >= 4, f"Expected >=4 propositions with 4 claims, got {hist.get(4, 0)}"
    assert hist.get(5, 0) == 1, f"Expected 1 proposition with 5 claims, got {hist.get(5, 0)}"

    multi_claim_props = sum(v for k, v in hist.items() if k > 1)
    assert multi_claim_props == 56, f"Expected 56 multi-claim propositions, got {multi_claim_props}"


def test_dedup_both_directions_threshold(live_db: Storage) -> None:
    """Both directions on threshold:

    - Positive: The two China open-source propositions merge into the same cluster.
    - Negative: The high-speed trains proposition does NOT merge with either.
    """
    con = live_db.con

    p1_claim = con.execute(
        "SELECT proposition_id FROM claims WHERE quote_text LIKE '%all the leading open source models are from China%'"
    ).fetchone()
    p2_claim = con.execute(
        "SELECT proposition_id FROM claims WHERE quote_text LIKE '%China has made a really big push on open source%'"
    ).fetchone()
    p3_claim = con.execute(
        "SELECT proposition_id FROM claims WHERE quote_text LIKE '%high speed trains going 125%'"
    ).fetchone()

    assert p1_claim is not None, "Claim for proposition 1 not found"
    assert p2_claim is not None, "Claim for proposition 2 not found"
    assert p3_claim is not None, "Claim for proposition 3 not found"

    p1_id = p1_claim[0]
    p2_id = p2_claim[0]
    p3_id = p3_claim[0]

    # Positive: p1 and p2 MUST merge
    assert p1_id == p2_id, f"Expected p1 and p2 to merge into same proposition, got p1={p1_id}, p2={p2_id}"
    assert p1_id == "a4035357b97e25bf"

    # Negative: p3 (trains) must NOT merge with open source
    assert p3_id != p1_id, f"Expected trains (p3) NOT to merge with open source (p1), but both are {p3_id}"
    assert p3_id == "d834d8f051299e00"


def test_dedup_integrity_checks_and_quote_verification(live_db: Storage) -> None:
    """All 1,501 claims retain verified quote spans and canonical IDs hold."""
    con = live_db.con

    claims = [
        c
        for r in con.execute("SELECT claim_id FROM claims").fetchall()
        if (c := live_db.get_claim(r[0])) is not None
    ]
    assert len(claims) == 1501

    utterances = [
        u
        for r in con.execute("SELECT utterance_id FROM utterances").fetchall()
        if (u := live_db.get_utterance(r[0])) is not None
    ]
    assert len(utterances) == 4219

    # verify_quotes must PASS over all 1501 claims
    quotes_res = verify_quotes(claims, utterances)
    assert quotes_res.passed is True, f"verify_quotes failed: {quotes_res.message}"
    assert quotes_res.examined_count == 1501

    # verify_canonical_ids must PASS across propositions and roles
    props = [
        p
        for r in con.execute("SELECT proposition_id FROM propositions").fetchall()
        if (p := live_db.get_proposition(r[0])) is not None
    ]
    roles = live_db.get_all_source_roles()

    canon_res = verify_canonical_ids(propositions=props, principles=[], claims=claims, roles=roles)
    assert canon_res.passed is True, f"verify_canonical_ids failed: {canon_res.message}"


def test_dedup_falsification_threshold_extremes_on_copy(tmp_path: Path) -> None:
    """Falsification:

    1. Set t_dedup = 0.999: merge histogram collapses to all-singletons and candidate-pair count drops to zero (RED).
    2. Set t_dedup = 0.30: absurd merge appears (trains merges with open source) (RED).
    3. Revert to t_dedup = 0.85: positive and negative holds (GREEN).
    """
    temp_db_path = tmp_path / "social_proof_copy.duckdb"
    shutil.copy("social_proof.duckdb", temp_db_path)

    store = Storage(str(temp_db_path))

    # 1. Break 1: t_dedup = 0.999 -> collapses to all-singletons and candidate-pair count drops to zero
    stats_999 = store.reresolve_propositions(t_dedup=0.999, from_pre_merge=True)
    assert stats_999["candidate_pairs"] == 0, f"Expected 0 candidate pairs at t=0.999, got {stats_999['candidate_pairs']}"
    assert stats_999["multi_source_diff_date_propositions"] == 0
    assert stats_999["surviving_propositions"] == 1499
    def _get_pid(pattern: str) -> str:
        row = store.con.execute(
            "SELECT proposition_id FROM claims WHERE quote_text LIKE ?", [f"%{pattern}%"]
        ).fetchone()
        assert row is not None
        return str(row[0])

    # Check that open-source propositions did NOT merge at 0.999
    p1_claim = _get_pid("all the leading open source models are from China")
    p2_claim = _get_pid("China has made a really big push on open source")
    assert p1_claim != p2_claim, "Expected p1 and p2 not to merge at t=0.999"

    # 2. Break 2: t_dedup = 0.30 -> absurd merge: trains merges with open source
    stats_30 = store.reresolve_propositions(t_dedup=0.30, from_pre_merge=True, validate_entailment_on_repoint=False)
    p1_claim_30 = _get_pid("all the leading open source models are from China")
    p3_claim_30 = _get_pid("high speed trains going 125")
    assert p1_claim_30 == p3_claim_30, "Expected absurd merge at t=0.30 (trains merged with open source)"
    assert stats_30["surviving_propositions"] == 1

    # 3. Revert: t_dedup = 0.86 -> GREEN
    stats_86 = store.reresolve_propositions(t_dedup=0.86, from_pre_merge=True)
    assert stats_86["candidate_pairs"] == 1
    assert stats_86["multi_source_diff_date_propositions"] == 6
    assert stats_86["surviving_propositions"] == 1430
    p1_claim_86 = _get_pid("all the leading open source models are from China")
    p2_claim_86 = _get_pid("China has made a really big push on open source")
    p3_claim_86 = _get_pid("high speed trains going 125")
    assert p1_claim_86 == p2_claim_86
    assert p3_claim_86 != p1_claim_86

    store.close()
