from pathlib import Path

from fixtures.fixture_loader import (
    load_broken_anchor_fixture,
    load_broken_quote_fixture,
    load_valid_fixtures,
)
from worker.entities import Assessment, Claim, Tension
from worker.integrity import (
    run_all_checks,
    run_integrity_corpus,
    run_integrity_fixtures,
    verify_anchor_chain,
    verify_attribution_floor,
    verify_negation_recheck,
    verify_no_page_context,
    verify_no_suppressed_scores,
    verify_quarantine_not_rendered,
    verify_quotes,
    verify_role_coverage,
    verify_versions_present,
)
from worker.storage import Storage


def test_valid_fixtures_pass_all_checks() -> None:
    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()
    sample_records = [{"id": "r1", "origin": "youtube"}]
    results = run_all_checks(
        claims=claims,
        utterances=utterances,
        sources=sources,
        tensions=tensions,
        assessments=assessments,
        records=sample_records,
        roles=roles,
    )
    for r in results:
        assert r.passed is True, f"Check {r.name} unexpectedly failed: {r.message}"
        if r.name != "verify_quarantine_not_rendered":
            assert r.status == "PASS", f"Check {r.name} status expected 'PASS', got '{r.status}'"
        else:
            assert r.status == "NOT APPLICABLE — zero rows"


def test_verify_quotes_fails_on_broken_fixture() -> None:
    sources, utterances, broken_claims = load_broken_quote_fixture()
    result = verify_quotes(broken_claims, utterances)
    assert result.passed is False
    assert result.status == "FAIL"
    assert "out of bounds" in result.message or "failed substring" in result.message


def test_verify_anchor_chain_fails_on_orphan() -> None:
    sources, utterances, claims = load_broken_anchor_fixture()
    result = verify_anchor_chain(claims, utterances, sources)
    assert result.passed is False
    assert result.status == "FAIL"
    assert "references non-existent source" in result.message


def test_empty_set_emits_not_applicable_never_pass() -> None:
    """Empty-set checks emit NOT APPLICABLE; a test asserts the string is not PASS."""
    results = run_all_checks(
        claims=[],
        utterances=[],
        sources=[],
        tensions=[],
        assessments=[],
        records=[],
    )
    for r in results:
        assert r.passed is True
        assert r.status == "NOT APPLICABLE — zero rows"
        assert r.status != "PASS"


def test_verify_no_page_context_catches_violation() -> None:
    clean_records = [{"id": "1", "origin": "feed"}, {"id": "2", "origin": "youtube"}]
    res_clean = verify_no_page_context(clean_records)
    assert res_clean.passed is True
    assert res_clean.status == "PASS"

    polluted_records = [{"id": "1", "origin": "feed"}, {"id": "2", "origin": "page_context"}]
    res_polluted = verify_no_page_context(polluted_records)
    assert res_polluted.passed is False
    assert res_polluted.status == "FAIL"
    assert "origin='page_context'" in res_polluted.message


def test_verify_no_suppressed_scores_catches_hidden_numbers() -> None:
    valid_assessment = Assessment(
        assessment_id="a1",
        subject_id="s1",
        topic_id="t1",
        rubric_version="v1.0",
        sufficiency={"passed": False, "reason": "insufficient_corpus"},
        axes={"consistency": {"score": None, "reason": "insufficient_corpus"}},
    )
    res_valid = verify_no_suppressed_scores([valid_assessment])
    assert res_valid.passed is True

    # Violation: sufficiency failed, but a numeric score was stored anyway
    suppressed_assessment = Assessment(
        assessment_id="a2",
        subject_id="s1",
        topic_id="t1",
        rubric_version="v1.0",
        sufficiency={"passed": False, "reason": "insufficient_corpus"},
        axes={"consistency": {"score": 0.82, "reason": "hidden_score"}},
    )
    res_invalid = verify_no_suppressed_scores([suppressed_assessment])
    assert res_invalid.passed is False
    assert res_invalid.status == "FAIL"
    assert "has non-null score: 0.82" in res_invalid.message


def test_verify_quarantine_not_rendered() -> None:
    quarantined_tension = Tension(
        tension_id="tns_q1",
        type="unacknowledged_reversal",
        claim_a_id="c1",
        claim_b_id="c2",
        status="quarantined",
        quarantine_reason="low_confidence",
    )
    leaking_assessment = Assessment(
        assessment_id="a1",
        subject_id="s1",
        topic_id="t1",
        rubric_version="v1.0",
        axis_evidence={"consistency": ["tns_q1"]},
    )
    res = verify_quarantine_not_rendered([quarantined_tension], [leaking_assessment])
    assert res.passed is False
    assert res.status == "FAIL"
    assert "contains quarantined tension" in res.message


def test_verify_attribution_floor_rejects_low_confidence() -> None:
    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()
    # Change one utterance attribution_confidence to "low"
    utterances[0].attribution_confidence = "low"
    res = verify_attribution_floor(claims, utterances, tensions)
    assert res.passed is False
    assert res.status == "FAIL"
    assert "expected 'high'" in res.message


def test_verify_negation_recheck_rejects_uncertain_negation() -> None:
    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()
    # Flag one utterance as negation_uncertain
    utterances[0].negation_uncertain = True
    res = verify_negation_recheck(tensions, claims, utterances)
    assert res.passed is False
    assert res.status == "FAIL"
    assert "negation_uncertain=True" in res.message


def test_verify_versions_present_rejects_missing_versions() -> None:
    incomplete_assessment = Assessment(
        assessment_id="a1",
        subject_id="s1",
        topic_id="t1",
        rubric_version="",  # missing
        detector_version="v1.0",
        embedding_model="nomic-embed-text-v1.5",
    )
    res = verify_versions_present([incomplete_assessment])
    assert res.passed is False
    assert res.status == "FAIL"
    assert "rubric_version" in res.message


def test_verify_role_coverage_fails_on_missing_role() -> None:
    _, utterances, _, _, _, roles = load_valid_fixtures()
    # Delete the role corresponding to the first utterance
    filtered_roles = [r for r in roles if not (r.source_id == utterances[0].source_id and r.subject_id == utterances[0].subject_id)]
    res = verify_role_coverage(utterances, filtered_roles)
    assert res.passed is False
    assert res.status == "FAIL"
    assert "no matching SourceSubjectRole row" in res.message


def test_verify_role_coverage_empty_set_emits_not_applicable() -> None:
    res = verify_role_coverage([], [])
    assert res.passed is True
    assert res.status == "NOT APPLICABLE — zero rows"
    assert res.status != "PASS"


def test_integrity_pass_corpus_examined_counts_match_db_assertion_c() -> None:
    """Assertion (c) for E0: examined_count for every check in CORPUS matches SELECT count(*)."""
    store = Storage("social_proof.duckdb")

    def count_query(query: str) -> int:
        res = store.con.execute(query).fetchone()
        assert res is not None
        return int(res[0])

    expected_counts = {
        "verify_quotes": count_query("SELECT count(*) FROM claims"),
        "verify_anchor_chain": (
            count_query("SELECT count(*) FROM claims")
            + count_query("SELECT count(*) FROM utterances")
        ),
        "verify_no_page_context": 0,
        "verify_no_suppressed_scores": count_query("SELECT count(*) FROM assessments"),
        "verify_quarantine_not_rendered": count_query("SELECT count(*) FROM tensions WHERE status = 'quarantined'"),
        "verify_attribution_floor": count_query("SELECT count(*) FROM tensions WHERE status = 'published'"),
        "verify_negation_recheck": count_query("SELECT count(*) FROM tensions WHERE status = 'published'"),
        "verify_versions_present": count_query("SELECT count(*) FROM assessments"),
        "verify_role_coverage": count_query("SELECT count(*) FROM utterances"),
        "verify_source_productivity": count_query("SELECT count(*) FROM sources WHERE ingested_at IS NOT NULL"),
    }

    corpus_results = run_integrity_corpus("social_proof.duckdb")
    assert len(corpus_results) == 10
    for r in corpus_results:
        assert r.examined_count == expected_counts[r.name], (
            f"Check {r.name}: examined_count {r.examined_count} != expected {expected_counts[r.name]}"
        )


def test_integrity_pass_both_directions_independent_verdict(tmp_path: Path) -> None:
    """Both directions: Corrupted corpus fails CORPUS run while FIXTURES still passes.

    Also asserts that running main() exits non-zero (code 1) on corrupted corpus.
    """
    import shutil
    import subprocess
    import sys

    # Copy DB to scratch
    corrupt_db = tmp_path / "corrupt.duckdb"
    shutil.copy("social_proof.duckdb", corrupt_db)

    # Insert a claim whose quote does not appear in its utterance
    corrupt_store = Storage(str(corrupt_db))
    first_utt = corrupt_store.con.execute("SELECT utterance_id, subject_id FROM utterances LIMIT 1").fetchone()
    assert first_utt is not None
    bad_claim = Claim(
        claim_id="c_bad_quote",
        subject_id=first_utt[1],
        utterance_id=first_utt[0],
        proposition_id="p_corrupt",
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
        quote_span=(0, 20),
        quote_text="NONEXISTENT QUOTE TEXT IN UTTERANCE",
    )
    corrupt_store.insert_claim(bad_claim)

    fixtures_results = run_integrity_fixtures()
    corpus_results = run_integrity_corpus(str(corrupt_db))

    assert all(r.passed for r in fixtures_results), "Fixtures unexpectedly failed"
    assert any(not r.passed for r in corpus_results), "Corpus unexpectedly passed on corrupted DB"
    quotes_res = next(r for r in corpus_results if r.name == "verify_quotes")
    assert not quotes_res.passed
    assert quotes_res.status == "FAIL"

    # Close connection so subprocess can open the database file without lock conflict
    corrupt_store.con.close()

    # Assert subprocess exit code is 1
    proc = subprocess.run(
        [sys.executable, "-m", "worker.integrity", "--all", "--db", str(corrupt_db)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, f"Expected returncode 1, got {proc.returncode}"
    assert "FAIL: One or more integrity checks failed." in proc.stdout

