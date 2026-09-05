from pathlib import Path

from fixtures.fixture_loader import (
    load_broken_anchor_fixture,
    load_broken_quote_fixture,
    load_valid_fixtures,
    load_valid_subjects,
    load_valid_topics,
)
from worker.entities import (
    Assessment,
    Claim,
    Proposition,
    SourceSubjectRole,
    Subject,
    Tension,
    Topic,
)
from worker.integrity import (
    run_all_checks,
    run_integrity_corpus,
    run_integrity_fixtures,
    verify_anchor_chain,
    verify_assessment_subjects_exist,
    verify_attribution_floor,
    verify_canonical_ids,
    verify_negation_recheck,
    verify_no_page_context,
    verify_no_suppressed_scores,
    verify_quarantine_not_rendered,
    verify_quarantined_propositions_unreachable,
    verify_quotes,
    verify_role_coverage,
    verify_versions_present,
)
from worker.storage import Storage


def test_valid_fixtures_pass_all_checks() -> None:
    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()
    subjects = load_valid_subjects()
    topics = load_valid_topics()
    sample_records = [{"id": "r1", "origin": "youtube"}]
    results = run_all_checks(
        claims=claims,
        utterances=utterances,
        sources=sources,
        tensions=tensions,
        assessments=assessments,
        records=sample_records,
        roles=roles,
        subjects=subjects,
        topics=topics,
    )
    for r in results:
        assert r.passed is True, f"Check {r.name} unexpectedly failed: {r.message}"
        if r.name not in (
            "verify_quarantine_not_rendered",
            "verify_quarantined_propositions_unreachable",
        ):
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


def test_verify_no_suppressed_scores_missing_passed_key_fails() -> None:
    asm_missing_passed = Assessment(
        assessment_id="a_no_passed",
        subject_id="s1",
        topic_id="t1",
        rubric_version="v1.0",
        sufficiency={"claim_count": 5, "source_count": 2, "span_days": 100},
        axes={"consistency": {"score": 0.5}},
    )
    res = verify_no_suppressed_scores([asm_missing_passed])
    assert res.passed is False
    assert res.status == "FAIL"
    assert "sufficiency_verdict_missing" in res.message


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
    store = Storage("social_proof.duckdb", read_only=True)

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
        "verify_canonical_ids": (
            count_query("SELECT count(*) FROM propositions")
            + count_query("SELECT count(*) FROM principles")
            + count_query("SELECT count(*) FROM source_roles")
        ),
        "verify_quarantined_propositions_unreachable": count_query(
            "SELECT count(*) FROM propositions WHERE status = 'quarantined'"
        ),
        "verify_assessment_subjects_exist": count_query("SELECT count(*) FROM assessments"),
    }

    try:
        corpus_results = run_integrity_corpus("social_proof.duckdb")
        assert len(corpus_results) == 13
        for r in corpus_results:
            assert r.examined_count == expected_counts[r.name], (
                f"Check {r.name}: examined_count {r.examined_count} != expected {expected_counts[r.name]}"
            )
    finally:
        store.con.close()


def test_verify_assessment_subjects_exist() -> None:
    subj1 = Subject(subject_id="subj_1", display_name="Subject One")
    top1 = Topic(topic_id="top_1", subject_id="subj_1", label="Topic One")

    # Happy path: subject exists, topic is global
    asm_global = Assessment(
        assessment_id="a_global",
        subject_id="subj_1",
        topic_id="global",
        rubric_version="v1.0",
    )
    # Happy path: subject exists, topic exists in topics
    asm_top = Assessment(
        assessment_id="a_top",
        subject_id="subj_1",
        topic_id="top_1",
        rubric_version="v1.0",
    )
    res_ok = verify_assessment_subjects_exist([asm_global, asm_top], [subj1], [top1])
    assert res_ok.passed is True
    assert res_ok.status == "PASS"

    # Failure 1: unknown subject
    asm_bad_subj = Assessment(
        assessment_id="a_bad_subj",
        subject_id="subj_unknown",
        topic_id="global",
        rubric_version="v1.0",
    )
    res_bad_subj = verify_assessment_subjects_exist([asm_bad_subj], [subj1], [top1])
    assert res_bad_subj.passed is False
    assert res_bad_subj.status == "FAIL"
    assert "references non-existent subject_id 'subj_unknown'" in res_bad_subj.message

    # Failure 2: unknown topic
    asm_bad_top = Assessment(
        assessment_id="a_bad_top",
        subject_id="subj_1",
        topic_id="top_unknown",
        rubric_version="v1.0",
    )
    res_bad_top = verify_assessment_subjects_exist([asm_bad_top], [subj1], [top1])
    assert res_bad_top.passed is False
    assert res_bad_top.status == "FAIL"
    assert "references non-existent topic_id 'top_unknown'" in res_bad_top.message

    # Zero assessments: NOT APPLICABLE
    res_zero = verify_assessment_subjects_exist([], [subj1], [top1])
    assert res_zero.passed is True
    assert res_zero.status == "NOT APPLICABLE — zero rows"


def test_verify_canonical_ids_passes_and_fails() -> None:
    from worker.storage import compute_proposition_id

    text = "Autonomous AI agents interact seamlessly"
    valid_id = compute_proposition_id(text)
    p_valid = Proposition(
        proposition_id=valid_id,
        canonical_text=text,
        claim_count=1,
    )
    claim = Claim(
        claim_id="c1",
        subject_id="s1",
        utterance_id="u1",
        proposition_id=valid_id,
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
    )
    res_pass = verify_canonical_ids([p_valid], [], [claim])
    assert res_pass.passed is True
    assert res_pass.status == "PASS"

    # Fails when ID doesn't match normalized canonical text
    p_bad_id = Proposition(
        proposition_id="wrong_id_value",
        canonical_text=text,
        claim_count=1,
    )
    res_fail_id = verify_canonical_ids([p_bad_id], [], [claim])
    assert res_fail_id.passed is False
    assert res_fail_id.status == "FAIL"
    assert "wrong_id_value" in res_fail_id.message

    # Fails when claim_count drifts
    p_bad_count = Proposition(
        proposition_id=valid_id,
        canonical_text=text,
        claim_count=99,
    )
    res_fail_count = verify_canonical_ids([p_bad_count], [], [claim])
    assert res_fail_count.passed is False
    assert res_fail_count.status == "FAIL"
    assert "claim_count mismatch" in res_fail_count.message

    # Test SourceSubjectRole canonical IDs
    from worker.storage import compute_role_id

    valid_role_id = compute_role_id("src_s1", "subj_1")
    role_valid = SourceSubjectRole(
        role_id=valid_role_id,
        source_id="src_s1",
        subject_id="subj_1",
        tier="B",
        venue_type="own_channel",
        audience_stance="friendly",
        is_adversarial=False,
    )
    res_role_pass = verify_canonical_ids([], [], None, [role_valid])
    assert res_role_pass.passed is True
    assert res_role_pass.status == "PASS"

    # Fails when role_id is hand-built
    role_bad_id = SourceSubjectRole(
        role_id="role_src_s1_subj_1",
        source_id="src_s1",
        subject_id="subj_1",
        tier="B",
        venue_type="own_channel",
        audience_stance="friendly",
        is_adversarial=False,
    )
    res_role_fail = verify_canonical_ids([], [], None, [role_bad_id])
    assert res_role_fail.passed is False
    assert res_role_fail.status == "FAIL"
    assert "role_src_s1_subj_1" in res_role_fail.message

    # Fails when multiple roles share the same (source_id, subject_id) pair
    res_dup_fail = verify_canonical_ids([], [], None, [role_valid, role_bad_id])
    assert res_dup_fail.passed is False
    assert res_dup_fail.status == "FAIL"
    assert "duplicate role pairs" in res_dup_fail.message


def test_verify_quarantined_propositions_unreachable() -> None:
    p_quarantined = Proposition(
        proposition_id="prop_quarantined_01",
        canonical_text="Fabricated proposition",
        status="quarantined",
        quarantine_reason="fabricated_proposition",
        claim_count=0,
    )
    # Passes when quarantined proposition has 0 claims
    res_pass = verify_quarantined_propositions_unreachable([p_quarantined], [])
    assert res_pass.passed is True
    assert res_pass.status == "PASS"

    # Fails when live claim points at quarantined proposition
    claim_bad = Claim(
        claim_id="c_bad",
        subject_id="s1",
        utterance_id="u1",
        proposition_id="prop_quarantined_01",
        stance="support",
        hedging_level=0.1,
        is_own_assertion=True,
    )
    res_fail = verify_quarantined_propositions_unreachable([p_quarantined], [claim_bad])
    assert res_fail.passed is False
    assert res_fail.status == "FAIL"
    assert "references quarantined proposition" in res_fail.message



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
    corrupt_store.close()

    fixtures_results = run_integrity_fixtures()
    corpus_results = run_integrity_corpus(str(corrupt_db))

    assert all(r.passed for r in fixtures_results), "Fixtures unexpectedly failed"
    assert any(not r.passed for r in corpus_results), "Corpus unexpectedly passed on corrupted DB"
    quotes_res = next(r for r in corpus_results if r.name == "verify_quotes")
    assert not quotes_res.passed
    assert quotes_res.status == "FAIL"

    # Assert subprocess exit code is 1
    proc = subprocess.run(
        [sys.executable, "-m", "worker.integrity", "--all", "--db", str(corrupt_db)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, f"Expected returncode 1, got {proc.returncode}"
    assert "FAIL: One or more integrity checks failed." in proc.stdout

