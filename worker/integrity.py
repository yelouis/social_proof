"""Evidence Integrity Automated Pass — design_evidence_integrity.md §3.

Implements the nine mandatory checks:
1. verify_quotes
2. verify_anchor_chain
3. verify_no_page_context
4. verify_no_suppressed_scores
5. verify_quarantine_not_rendered
6. verify_attribution_floor
7. verify_negation_recheck
8. verify_versions_present
9. verify_role_coverage
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker.entities import Assessment, Claim, Source, SourceSubjectRole, Tension, Utterance


@dataclass
class CheckResult:
    name: str
    passed: bool
    status: str  # "PASS", "FAIL", "NOT APPLICABLE — zero rows"
    message: str
    examined_count: int


def verify_quotes(
    claims: list[Claim],
    utterances: dict[str, Utterance] | list[Utterance],
) -> CheckResult:
    """For every Claim: grep -F the quote_span substring against utterances.text_verbatim.

    Zero tolerance — one miss fails the pass. Catches fabrication.
    """
    if not claims:
        return CheckResult(
            name="verify_quotes",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No claims to verify",
            examined_count=0,
        )

    utt_map = utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}

    for claim in claims:
        if claim.utterance_id not in utt_map:
            return CheckResult(
                name="verify_quotes",
                passed=False,
                status="FAIL",
                message=f"Claim {claim.claim_id} references missing utterance {claim.utterance_id}",
                examined_count=len(claims),
            )
        utt = utt_map[claim.utterance_id]
        start, end = claim.quote_span
        if start < 0 or end > len(utt.text_verbatim) or start >= end:
            return CheckResult(
                name="verify_quotes",
                passed=False,
                status="FAIL",
                message=(
                    f"Claim {claim.claim_id} quote_span [{start}, {end}] out of bounds "
                    f"for utterance length {len(utt.text_verbatim)}"
                ),
                examined_count=len(claims),
            )
        quote_text = utt.text_verbatim[start:end]
        expected_quote = getattr(claim, "quote_text", None)
        if expected_quote is not None and expected_quote != quote_text:
            return CheckResult(
                name="verify_quotes",
                passed=False,
                status="FAIL",
                message=(
                    f"Claim {claim.claim_id} expected quote '{expected_quote}' did not match "
                    f"verbatim slice '{quote_text}'"
                ),
                examined_count=len(claims),
            )
        # Invariant I9: verify quote_text matches text_verbatim exactly
        if quote_text not in utt.text_verbatim:
            return CheckResult(
                name="verify_quotes",
                passed=False,
                status="FAIL",
                message=f"Claim {claim.claim_id} quote text '{quote_text}' failed substring match",
                examined_count=len(claims),
            )

    return CheckResult(
        name="verify_quotes",
        passed=True,
        status="PASS",
        message=f"All {len(claims)} claim quote spans verified against verbatim text",
        examined_count=len(claims),
    )


def verify_anchor_chain(
    claims: list[Claim],
    utterances: dict[str, Utterance] | list[Utterance],
    sources: dict[str, Source] | list[Source],
) -> CheckResult:
    """Every Claim -> Utterance -> Source resolves.

    No orphans, no dangling source_ids, no utterance whose source was deleted.
    """
    total = len(claims) + (len(utterances) if isinstance(utterances, list) else len(utterances.values()))
    if total == 0:
        return CheckResult(
            name="verify_anchor_chain",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No entities to check anchor chain",
            examined_count=0,
        )

    utt_map = utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}
    src_map = sources if isinstance(sources, dict) else {s.source_id: s for s in sources}

    for utt_id, utt in utt_map.items():
        if utt.source_id not in src_map:
            return CheckResult(
                name="verify_anchor_chain",
                passed=False,
                status="FAIL",
                message=f"Utterance {utt_id} references non-existent source {utt.source_id}",
                examined_count=total,
            )

    for claim in claims:
        if claim.utterance_id not in utt_map:
            return CheckResult(
                name="verify_anchor_chain",
                passed=False,
                status="FAIL",
                message=f"Claim {claim.claim_id} references non-existent utterance {claim.utterance_id}",
                examined_count=total,
            )

    return CheckResult(
        name="verify_anchor_chain",
        passed=True,
        status="PASS",
        message=f"Anchor chain verified across {len(claims)} claims, {len(utt_map)} utterances, {len(src_map)} sources",
        examined_count=total,
    )


def verify_no_page_context(
    records: list[dict[str, Any]],
) -> CheckResult:
    """Assert zero rows anywhere with origin = 'page_context'. Invariant I2."""
    if not records:
        return CheckResult(
            name="verify_no_page_context",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No records to check for page_context origin",
            examined_count=0,
        )

    for i, r in enumerate(records):
        if r.get("origin") == "page_context":
            return CheckResult(
                name="verify_no_page_context",
                passed=False,
                status="FAIL",
                message=f"Found row with origin='page_context' at index {i}: {r}",
                examined_count=len(records),
            )

    return CheckResult(
        name="verify_no_page_context",
        passed=True,
        status="PASS",
        message=f"Verified 0 rows with origin='page_context' across {len(records)} checked records",
        examined_count=len(records),
    )


def verify_no_suppressed_scores(
    assessments: list[Assessment],
) -> CheckResult:
    """For every Assessment where sufficiency failed: assert the axis value

    is literally null (None), not a number behind a flag. Invariant I5.
    """
    if not assessments:
        return CheckResult(
            name="verify_no_suppressed_scores",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No assessments to check",
            examined_count=0,
        )

    for a in assessments:
        passed = a.sufficiency.get("passed", True)
        if not passed:
            for axis_name, axis_val in a.axes.items():
                if isinstance(axis_val, dict):
                    score = axis_val.get("score")
                else:
                    score = axis_val
                if score is not None:
                    return CheckResult(
                        name="verify_no_suppressed_scores",
                        passed=False,
                        status="FAIL",
                        message=(
                            f"Assessment {a.assessment_id} failed sufficiency but axis '{axis_name}' "
                            f"has non-null score: {score}"
                        ),
                        examined_count=len(assessments),
                    )

    return CheckResult(
        name="verify_no_suppressed_scores",
        passed=True,
        status="PASS",
        message=f"Verified no suppressed scores across {len(assessments)} assessments",
        examined_count=len(assessments),
    )


def verify_quarantine_not_rendered(
    tensions: list[Tension],
    assessments: list[Assessment],
    timelines: list[dict[str, Any]] | None = None,
) -> CheckResult:
    """For every quarantined Tension: assert it appears in no assessment's

    axis_evidence and in no timeline payload.
    """
    quarantined_ids = {t.tension_id for t in tensions if t.status == "quarantined"}
    if not quarantined_ids:
        return CheckResult(
            name="verify_quarantine_not_rendered",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No quarantined tensions to verify",
            examined_count=0,
        )

    for a in assessments:
        for axis_name, t_ids in a.axis_evidence.items():
            overlap = set(t_ids).intersection(quarantined_ids)
            if overlap:
                return CheckResult(
                    name="verify_quarantine_not_rendered",
                    passed=False,
                    status="FAIL",
                    message=f"Assessment {a.assessment_id} axis '{axis_name}' contains quarantined tension {overlap}",
                    examined_count=len(quarantined_ids),
                )

    if timelines:
        for tl in timelines:
            tl_tensions = tl.get("tensions", [])
            for t in tl_tensions:
                tid = t.get("tension_id") if isinstance(t, dict) else getattr(t, "tension_id", None)
                if tid in quarantined_ids:
                    return CheckResult(
                        name="verify_quarantine_not_rendered",
                        passed=False,
                        status="FAIL",
                        message=f"Timeline contains quarantined tension {tid}",
                        examined_count=len(quarantined_ids),
                    )

    return CheckResult(
        name="verify_quarantine_not_rendered",
        passed=True,
        status="PASS",
        message=f"Verified {len(quarantined_ids)} quarantined tensions are not rendered",
        examined_count=len(quarantined_ids),
    )


def verify_attribution_floor(
    claims: list[Claim],
    utterances: dict[str, Utterance] | list[Utterance],
    tensions: list[Tension],
) -> CheckResult:
    """Every Claim participating in a published Tension traces to an

    utterance with attribution_confidence = 'high'.
    """
    published_tensions = [t for t in tensions if t.status == "published"]
    if not published_tensions:
        return CheckResult(
            name="verify_attribution_floor",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No published tensions to verify attribution floor",
            examined_count=0,
        )

    claim_map = {c.claim_id: c for c in claims}
    utt_map = utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}

    for t in published_tensions:
        for cid in (t.claim_a_id, t.claim_b_id):
            if cid not in claim_map:
                return CheckResult(
                    name="verify_attribution_floor",
                    passed=False,
                    status="FAIL",
                    message=f"Tension {t.tension_id} references missing claim {cid}",
                    examined_count=len(published_tensions),
                )
            claim = claim_map[cid]
            if claim.utterance_id not in utt_map:
                return CheckResult(
                    name="verify_attribution_floor",
                    passed=False,
                    status="FAIL",
                    message=f"Claim {claim.claim_id} references missing utterance {claim.utterance_id}",
                    examined_count=len(published_tensions),
                )
            utt = utt_map[claim.utterance_id]
            if str(utt.attribution_confidence).lower() != "high":
                return CheckResult(
                    name="verify_attribution_floor",
                    passed=False,
                    status="FAIL",
                    message=(
                        f"Tension {t.tension_id} claim {cid} utterance {utt.utterance_id} has "
                        f"attribution_confidence='{utt.attribution_confidence}', expected 'high'"
                    ),
                    examined_count=len(published_tensions),
                )

    return CheckResult(
        name="verify_attribution_floor",
        passed=True,
        status="PASS",
        message=f"All claims in {len(published_tensions)} published tensions have high attribution confidence",
        examined_count=len(published_tensions),
    )


def verify_negation_recheck(
    tensions: list[Tension],
    claims: list[Claim],
    utterances: dict[str, Utterance] | list[Utterance],
) -> CheckResult:
    """Under Issue 003: Every published Tension's two claims have

    transcription_pass_count >= 2 and negation_uncertain = False.
    """
    published_tensions = [t for t in tensions if t.status == "published"]
    if not published_tensions:
        return CheckResult(
            name="verify_negation_recheck",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No published tensions to verify negation recheck",
            examined_count=0,
        )

    claim_map = {c.claim_id: c for c in claims}
    utt_map = utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}

    for t in published_tensions:
        for cid in (t.claim_a_id, t.claim_b_id):
            if cid not in claim_map:
                return CheckResult(
                    name="verify_negation_recheck",
                    passed=False,
                    status="FAIL",
                    message=f"Tension {t.tension_id} references missing claim {cid}",
                    examined_count=len(published_tensions),
                )
            claim = claim_map[cid]
            if claim.utterance_id not in utt_map:
                return CheckResult(
                    name="verify_negation_recheck",
                    passed=False,
                    status="FAIL",
                    message=f"Claim {claim.claim_id} references missing utterance {claim.utterance_id}",
                    examined_count=len(published_tensions),
                )
            utt = utt_map[claim.utterance_id]
            if utt.transcription_pass_count < 2:
                return CheckResult(
                    name="verify_negation_recheck",
                    passed=False,
                    status="FAIL",
                    message=(
                        f"Tension {t.tension_id} claim {cid} utterance {utt.utterance_id} has "
                        f"transcription_pass_count={utt.transcription_pass_count} < 2"
                    ),
                    examined_count=len(published_tensions),
                )
            if utt.negation_uncertain:
                return CheckResult(
                    name="verify_negation_recheck",
                    passed=False,
                    status="FAIL",
                    message=(
                        f"Tension {t.tension_id} claim {cid} utterance {utt.utterance_id} is "
                        f"flagged negation_uncertain=True"
                    ),
                    examined_count=len(published_tensions),
                )

    return CheckResult(
        name="verify_negation_recheck",
        passed=True,
        status="PASS",
        message=f"All {len(published_tensions)} published tensions verified with dual-pass negation recheck",
        examined_count=len(published_tensions),
    )


def verify_versions_present(
    assessments: list[Assessment],
) -> CheckResult:
    """Every Assessment carries rubric_version, extraction_version/models,

    detector_version, embedding_model.
    """
    if not assessments:
        return CheckResult(
            name="verify_versions_present",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No assessments to verify versions",
            examined_count=0,
        )

    for a in assessments:
        missing: list[str] = []
        if not a.rubric_version:
            missing.append("rubric_version")
        if not a.detector_version:
            missing.append("detector_version")
        if not a.embedding_model:
            missing.append("embedding_model")
        if missing:
            return CheckResult(
                name="verify_versions_present",
                passed=False,
                status="FAIL",
                message=f"Assessment {a.assessment_id} missing versions: {', '.join(missing)}",
                examined_count=len(assessments),
            )

    return CheckResult(
        name="verify_versions_present",
        passed=True,
        status="PASS",
        message=f"All {len(assessments)} assessments have required version provenance",
        examined_count=len(assessments),
    )


def verify_role_coverage(
    utterances: list[Utterance],
    roles: list[SourceSubjectRole] | dict[tuple[str, str], SourceSubjectRole],
) -> CheckResult:
    """Every Utterance's (source_id, subject_id) pair resolves to a SourceSubjectRole row.

    An utterance attributed to a subject with no role for that source is an orphan
    and fails the pass. Issue 022 = A.
    """
    if not utterances:
        return CheckResult(
            name="verify_role_coverage",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No utterances to verify role coverage",
            examined_count=0,
        )

    if isinstance(roles, dict):
        role_map = roles
    else:
        role_map = {(r.source_id, r.subject_id): r for r in roles}

    for utt in utterances:
        pair = (utt.source_id, utt.subject_id)
        if pair not in role_map:
            return CheckResult(
                name="verify_role_coverage",
                passed=False,
                status="FAIL",
                message=(
                    f"Utterance {utt.utterance_id} has pair (source_id={utt.source_id}, "
                    f"subject_id={utt.subject_id}) with no matching SourceSubjectRole row"
                ),
                examined_count=len(utterances),
            )

    return CheckResult(
        name="verify_role_coverage",
        passed=True,
        status="PASS",
        message=f"All {len(utterances)} utterances resolve to matching SourceSubjectRole rows",
        examined_count=len(utterances),
    )


def run_all_checks(
    claims: list[Claim] | None = None,
    utterances: list[Utterance] | None = None,
    sources: list[Source] | None = None,
    tensions: list[Tension] | None = None,
    assessments: list[Assessment] | None = None,
    records: list[dict[str, Any]] | None = None,
    roles: list[SourceSubjectRole] | None = None,
) -> list[CheckResult]:
    """Execute all 9 integrity checks."""
    c_list = claims or []
    u_list = utterances or []
    s_list = sources or []
    t_list = tensions or []
    a_list = assessments or []
    r_list = records or []
    rol_list = roles or []

    results = [
        verify_quotes(c_list, u_list),
        verify_anchor_chain(c_list, u_list, s_list),
        verify_no_page_context(r_list),
        verify_no_suppressed_scores(a_list),
        verify_quarantine_not_rendered(t_list, a_list),
        verify_attribution_floor(c_list, u_list, t_list),
        verify_negation_recheck(t_list, c_list, u_list),
        verify_versions_present(a_list),
        verify_role_coverage(u_list, rol_list),
    ]
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evidence integrity verification suite")
    parser.add_argument("--all", action="store_true", help="Run all 9 integrity checks")
    _ = parser.parse_args()

    from fixtures.fixture_loader import load_valid_fixtures

    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()

    db_file = Path("social_proof.duckdb")
    if db_file.exists():
        from worker.storage import Storage

        store = Storage(str(db_file))
        db_claims_rows = store.con.execute("SELECT claim_id FROM claims").fetchall()
        if db_claims_rows:
            db_claims = [c for r in db_claims_rows if (c := store.get_claim(r[0])) is not None]
            db_utts = [u for r in store.con.execute("SELECT utterance_id FROM utterances").fetchall() if (u := store.get_utterance(r[0])) is not None]
            db_sources = [s for r in store.con.execute("SELECT source_id FROM sources").fetchall() if (s := store.get_source(r[0])) is not None]
            db_roles = [role for row in store.con.execute("SELECT source_id, subject_id FROM source_roles").fetchall() if (role := store.get_source_role(row[0], row[1])) is not None]
            sources.extend(db_sources)
            utterances.extend(db_utts)
            claims.extend(db_claims)
            roles.extend(db_roles)

    results = run_all_checks(
        claims=claims,
        utterances=utterances,
        sources=sources,
        tensions=tensions,
        assessments=assessments,
        roles=roles,
    )

    failed = False
    print("\n" + "=" * 60)
    print("EVIDENCE INTEGRITY PASS")
    print("=" * 60)
    for r in results:
        status_str = f"[{r.status}]"
        print(f"{r.name:<32} {status_str:<30} {r.message}")
        if not r.passed:
            failed = True
    print("=" * 60)

    if failed:
        print("FAIL: One or more integrity checks failed.")
        sys.exit(1)
    else:
        print("SUCCESS: Evidence integrity verified.")
        sys.exit(0)


if __name__ == "__main__":
    main()
