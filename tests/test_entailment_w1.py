"""Tests for Item W1: Entailment does not survive re-pointing.

Implements validation assertions from agent_execution_guide.md §17l:
- (c) verify_entailment_holds FAILS against pre-repair un-gated merge state, naming
  the 6 claims including 4415459696a8fbc0 and 4a3ef2cdc190f1b1.
- Both directions: valid entailment passes; hand-repointing a claim to an unrelated proposition fails.
- Re-running merge re-points strictly fewer claims (69 < 74) and every re-pointed claim
  clears T_ENTAIL_HIGH against its new text.
- Exactly one source of truth for t_dedup across the codebase.
- LOOP 2 Falsification: disabling re-point entailment validation yields RED (failing claims);
  reverting to enabled yields GREEN.
"""

import re
import shutil
from pathlib import Path

import pytest

from worker.entities import Claim, Proposition
from worker.extract.dedup import DEFAULT_T_DEDUP, DEFAULT_T_ENTAIL_HIGH, get_embedder
from worker.integrity import verify_entailment_holds
from worker.storage import Storage


@pytest.fixture
def live_db() -> Storage:
    """Read-only access to production database per Trap 37."""
    return Storage(db_path="social_proof.duckdb", read_only=True)


def test_entailment_w1_assertion_c_fails_on_unrepaired_merge(tmp_path: Path) -> None:
    """Assertion (c): verify_entailment_holds FAILS when propositions are merged without

    entailment validation, specifically naming the failing claims including
    '4415459696a8fbc0' and '4a3ef2cdc190f1b1'.
    """
    temp_db_path = tmp_path / "unrepaired_test.duckdb"
    shutil.copy("social_proof.duckdb", temp_db_path)

    store = Storage(str(temp_db_path))
    # Re-run merge with validate_entailment_on_repoint=False to simulate pre-repair state
    stats = store.reresolve_propositions(
        t_dedup=DEFAULT_T_DEDUP,
        from_pre_merge=True,
        validate_entailment_on_repoint=False,
    )
    assert stats["repointed_propositions_count"] == 74, "Pre-repair merge re-pointed 74 claims"

    # Run verify_entailment_holds over the un-repaired state
    claims = [
        c
        for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
        if (c := store.get_claim(r[0])) is not None
    ]
    propositions = [
        p
        for r in store.con.execute("SELECT proposition_id FROM propositions").fetchall()
        if (p := store.get_proposition(r[0])) is not None
    ]

    result = verify_entailment_holds(claims, propositions, embedder=get_embedder())
    store.close()

    assert result.passed is False, "Expected verify_entailment_holds to FAIL on un-repaired merge"
    assert result.status == "FAIL"
    assert "4415459696a8fbc0" in result.message, "Expected 4415459696a8fbc0 to be named in failure"
    assert "4a3ef2cdc190f1b1" in result.message, "Expected 4a3ef2cdc190f1b1 to be named in failure"
    assert "6 published claims failed entailment" in result.message


def test_entailment_w1_both_directions(live_db: Storage) -> None:
    """Both directions on entailment verification:

    1. Genuinely entails current proposition -> PASS.
    2. Hand-repoint to unrelated proposition -> FAILS.
    """
    embedder = get_embedder()

    # Pick a clean published claim from the corpus
    row = live_db.con.execute(
        """
        SELECT claim_id, quote_text, proposition_id
        FROM claims
        WHERE is_own_assertion = True AND exclusion_reason IS NULL
        LIMIT 1
        """
    ).fetchone()
    assert row is not None
    cid, qtext, pid = row

    prop = live_db.get_proposition(pid)
    assert prop is not None

    claim_valid = Claim(
        claim_id="clm_valid_test",
        subject_id="subj_test",
        utterance_id="utt_test",
        proposition_id=prop.proposition_id,
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
        quote_text=qtext,
    )

    # 1. Valid entailment passes
    res_valid = verify_entailment_holds([claim_valid], [prop], embedder=embedder)
    assert res_valid.passed is True
    assert res_valid.status == "PASS"

    # 2. Hand-repoint to unrelated proposition -> FAILS
    unrelated_prop = Proposition(
        proposition_id="prop_unrelated_trains",
        canonical_text="High speed bullet trains traveling at 125 miles per hour.",
        status="active",
    )
    claim_bad = Claim(
        claim_id="clm_bad_test",
        subject_id="subj_test",
        utterance_id="utt_test",
        proposition_id=unrelated_prop.proposition_id,
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
        quote_text=qtext,
    )
    res_bad = verify_entailment_holds([claim_bad], [unrelated_prop], embedder=embedder)
    assert res_bad.passed is False
    assert res_bad.status == "FAIL"
    assert "clm_bad_test" in res_bad.message


def test_entailment_w1_repoint_strictly_fewer_and_clears_floor(live_db: Storage) -> None:
    """With re-point validation active, strictly fewer claims are re-pointed than P0 (69 < 74),

    and every re-pointed claim clears T_ENTAIL_HIGH against its new text.
    """
    con = live_db.con

    # Check how many claims changed proposition_id from pre-merge
    repointed_claims = con.execute(
        """
        SELECT c.claim_id, c.quote_text, c.proposition_id, p.canonical_text
        FROM claims c
        JOIN claims_pre_merge c_pre ON c.claim_id = c_pre.claim_id
        JOIN propositions p ON c.proposition_id = p.proposition_id
        WHERE c.proposition_id != c_pre.proposition_id
        """
    ).fetchall()

    assert len(repointed_claims) < 74, f"Expected strictly fewer than 74 re-pointed claims, got {len(repointed_claims)}"
    assert len(repointed_claims) == 69, f"Expected exactly 69 re-pointed claims, got {len(repointed_claims)}"

    # Check that each re-pointed claim clears T_ENTAIL_HIGH
    embedder = get_embedder()
    cache = live_db.get_entailment_cache()
    for cid, qtext, pid, ptext in repointed_claims:
        if (cid, pid) in cache:
            sim = cache[(cid, pid)]
        else:
            q_vec = embedder.embed_document(qtext.strip())
            p_vec = embedder.embed_document(ptext.strip())
            from worker.extract.dedup import cosine_similarity
            sim = cosine_similarity(q_vec, p_vec)
        assert sim >= DEFAULT_T_ENTAIL_HIGH, (
            f"Re-pointed claim {cid} failed T_ENTAIL_HIGH ({DEFAULT_T_ENTAIL_HIGH}): sim={sim:.4f}"
        )


def test_entailment_w1_single_source_of_truth_for_t_dedup() -> None:
    """t_dedup has exactly one canonical definition in worker/extract/dedup.py.

    No other module should hardcode or re-default t_dedup to a different value.
    """
    assert DEFAULT_T_DEDUP == 0.86

    # Grep codebase for t_dedup defaults
    py_files = list(Path("worker").rglob("*.py")) + list(Path("scripts").rglob("*.py"))
    hardcoded_085_pattern = re.compile(r"t_dedup\s*:\s*float\s*=\s*0\.85")

    for f in py_files:
        content = f.read_text(encoding="utf-8")
        assert not hardcoded_085_pattern.search(content), f"Found hardcoded 0.85 t_dedup in {f}"


def test_entailment_w1_falsification_loop_2(tmp_path: Path) -> None:
    """LOOP 2 Falsification:

    1. Break: Disable re-point entailment validation (validate_entailment_on_repoint=False)
       and re-resolve -> verify_entailment_holds goes RED with 6 failing claims.
    2. Revert: Enable re-point entailment validation (validate_entailment_on_repoint=True)
       and re-resolve -> verify_entailment_holds goes GREEN (all published claims pass).
    Both outcomes observed.
    """
    temp_db_path = tmp_path / "falsify_w1.duckdb"
    shutil.copy("social_proof.duckdb", temp_db_path)

    store = Storage(str(temp_db_path))

    # 1. Break: validate_entailment_on_repoint=False -> RED
    store.reresolve_propositions(t_dedup=DEFAULT_T_DEDUP, from_pre_merge=True, validate_entailment_on_repoint=False)
    claims_broken = [
        c
        for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
        if (c := store.get_claim(r[0])) is not None
    ]
    props_broken = [
        p
        for r in store.con.execute("SELECT proposition_id FROM propositions").fetchall()
        if (p := store.get_proposition(r[0])) is not None
    ]
    res_broken = verify_entailment_holds(claims_broken, props_broken, embedder=get_embedder())
    assert res_broken.passed is False, "Falsification: Broken merge must go RED on verify_entailment_holds"
    assert res_broken.status == "FAIL"
    assert "4415459696a8fbc0" in res_broken.message
    assert "4a3ef2cdc190f1b1" in res_broken.message

    # 2. Revert: validate_entailment_on_repoint=True -> GREEN
    store.reresolve_propositions(t_dedup=DEFAULT_T_DEDUP, from_pre_merge=True, validate_entailment_on_repoint=True)
    claims_fixed = [
        c
        for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
        if (c := store.get_claim(r[0])) is not None
    ]
    props_fixed = [
        p
        for r in store.con.execute("SELECT proposition_id FROM propositions").fetchall()
        if (p := store.get_proposition(r[0])) is not None
    ]
    cache = store.get_entailment_cache()
    res_fixed = verify_entailment_holds(claims_fixed, props_fixed, embedder=get_embedder(), cache=cache)
    assert res_fixed.passed is True, "Revert: Fixed merge must go GREEN on verify_entailment_holds"
    assert res_fixed.status == "PASS"

    store.close()
