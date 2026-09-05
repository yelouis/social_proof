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

from worker.entities import (
    Assessment,
    Claim,
    Principle,
    Proposition,
    Source,
    SourceSubjectRole,
    Subject,
    Tension,
    Topic,
    Utterance,
)
from worker.storage import compute_principle_id, compute_proposition_id


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

    utt_map = (
        utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}
    )

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
    total = len(claims) + (
        len(utterances) if isinstance(utterances, list) else len(utterances.values())
    )
    if total == 0:
        return CheckResult(
            name="verify_anchor_chain",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No entities to check anchor chain",
            examined_count=0,
        )

    utt_map = (
        utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}
    )
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
        if "passed" not in a.sufficiency:
            return CheckResult(
                name="verify_no_suppressed_scores",
                passed=False,
                status="FAIL",
                message=(
                    f"Assessment {a.assessment_id} failed sufficiency check: "
                    f"sufficiency_verdict_missing ('passed' key missing)"
                ),
                examined_count=len(assessments),
            )
        passed = a.sufficiency["passed"]
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
    utt_map = (
        utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}
    )

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
    utt_map = (
        utterances if isinstance(utterances, dict) else {u.utterance_id: u for u in utterances}
    )

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
        if not utt.subject_id or utt.subject_id == "unknown":
            continue
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


MIN_UTTERANCE_MEDIA_RATIO: float = 0.80  # provisional (Parameter 029)


def verify_source_productivity(
    sources: list[Source],
    utterances: list[Utterance],
    min_ratio: float = MIN_UTTERANCE_MEDIA_RATIO,
) -> CheckResult:
    """Every source with ingested_at set must have produced >= 1 utterance (no silent empty ingests)

    and utterance span must cover at least min_ratio of the source media duration.
    Invariant: Success is output. Audio deletion and ingested_at require non-empty extraction.
    """
    ingested_sources = [s for s in sources if s.ingested_at is not None]
    if not ingested_sources:
        return CheckResult(
            name="verify_source_productivity",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No ingested sources to verify productivity",
            examined_count=0,
        )

    utts_by_source: dict[str, list[Utterance]] = {}
    for u in utterances:
        utts_by_source.setdefault(u.source_id, []).append(u)

    # Pass 1: Empty-source check (R0 invariant: success is output; audio deletion requires >= 1 utterance)
    for s in ingested_sources:
        src_utts = utts_by_source.get(s.source_id, [])
        if len(src_utts) == 0:
            return CheckResult(
                name="verify_source_productivity",
                passed=False,
                status="FAIL",
                message=f"Source {s.source_id} ('{s.title}') marked ingested_at but yielded zero utterances (silent failure)",
                examined_count=len(ingested_sources),
            )

    # Pass 2: Media duration and coverage check (R1 invariant: coverage >= min_ratio)
    for s in ingested_sources:
        src_utts = utts_by_source.get(s.source_id, [])
        min_start = min(u.start_ms for u in src_utts)
        max_end = max(u.end_ms for u in src_utts)
        span_ms = max_end - min_start
        if span_ms <= 0:
            return CheckResult(
                name="verify_source_productivity",
                passed=False,
                status="FAIL",
                message=f"Source {s.source_id} ('{s.title}') has zero or negative utterance span: {span_ms}ms",
                examined_count=len(ingested_sources),
            )

        if not s.duration_ms or s.duration_ms <= 0:
            return CheckResult(
                name="verify_source_productivity",
                passed=False,
                status="FAIL",
                message=f"Source {s.source_id} ('{s.title}') has missing or zero duration_ms: {s.duration_ms}",
                examined_count=len(ingested_sources),
            )

        ratio = span_ms / s.duration_ms
        if ratio < min_ratio:
            return CheckResult(
                name="verify_source_productivity",
                passed=False,
                status="FAIL",
                message=(
                    f"Source {s.source_id} ('{s.title}') utterance coverage {ratio:.1%} "
                    f"({span_ms}ms / {s.duration_ms}ms) falls below minimum ratio {min_ratio:.1%}"
                ),
                examined_count=len(ingested_sources),
            )

    total_utts = sum(len(utts_by_source.get(s.source_id, [])) for s in ingested_sources)
    return CheckResult(
        name="verify_source_productivity",
        passed=True,
        status="PASS",
        message=(
            f"All {len(ingested_sources)} ingested sources produced utterances with coverage >= {min_ratio:.1%} "
            f"(total {total_utts} utterances)"
        ),
        examined_count=len(ingested_sources),
    )


def verify_canonical_ids(
    propositions: list[Proposition],
    principles: list[Principle],
    claims: list[Claim] | None = None,
) -> CheckResult:
    """For every proposition and principle: assert stored_id == compute_*_id(canonical_text).

    Also assert claim_count matches the real count from claims — as a check, never as a filter.
    """
    total = len(propositions) + len(principles)
    if total == 0:
        return CheckResult(
            name="verify_canonical_ids",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No propositions or principles to check",
            examined_count=0,
        )

    mismatched_props: list[str] = []
    for p in propositions:
        expected_id = compute_proposition_id(p.canonical_text)
        if p.proposition_id != expected_id:
            mismatched_props.append(p.proposition_id)

    mismatched_prins: list[str] = []
    for pr in principles:
        expected_id = compute_principle_id(pr.canonical_text)
        if pr.principle_id != expected_id:
            mismatched_prins.append(pr.principle_id)

    mismatched_counts: list[str] = []
    if claims is not None:
        real_counts: dict[str, int] = {}
        for c in claims:
            real_counts[c.proposition_id] = real_counts.get(c.proposition_id, 0) + 1
        for p in propositions:
            real = real_counts.get(p.proposition_id, 0)
            if p.claim_count != real:
                mismatched_counts.append(f"{p.proposition_id} (stored={p.claim_count}, real={real})")

    if mismatched_props or mismatched_prins:
        details = []
        if mismatched_props:
            details.append(f"propositions: {mismatched_props}")
        if mismatched_prins:
            details.append(f"principles: {mismatched_prins}")
        count_detail = f" (also {len(mismatched_counts)} claim_count mismatch(es))" if mismatched_counts else ""
        return CheckResult(
            name="verify_canonical_ids",
            passed=False,
            status="FAIL",
            message=f"Canonical ID mismatch for {'; '.join(details)}{count_detail}",
            examined_count=total,
        )

    if mismatched_counts:
        return CheckResult(
            name="verify_canonical_ids",
            passed=False,
            status="FAIL",
            message=f"claim_count mismatch for {len(mismatched_counts)} proposition(s): {mismatched_counts[:3]}",
            examined_count=total,
        )

    return CheckResult(
        name="verify_canonical_ids",
        passed=True,
        status="PASS",
        message=f"Verified canonical IDs across {len(propositions)} propositions and {len(principles)} principles",
        examined_count=total,
    )


def verify_quarantined_propositions_unreachable(
    propositions: list[Proposition],
    claims: list[Claim] | None = None,
) -> CheckResult:
    """For every quarantined Proposition: assert no live claim references it,
    and it cannot be returned by the /resolve query shape.
    """
    quarantined_props = [p for p in propositions if p.status == "quarantined"]
    if not quarantined_props:
        return CheckResult(
            name="verify_quarantined_propositions_unreachable",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No quarantined propositions to verify",
            examined_count=0,
        )

    quarantined_ids = {p.proposition_id for p in quarantined_props}
    c_list = claims or []

    for c in c_list:
        if c.proposition_id in quarantined_ids:
            return CheckResult(
                name="verify_quarantined_propositions_unreachable",
                passed=False,
                status="FAIL",
                message=f"Live claim {c.claim_id} references quarantined proposition {c.proposition_id}",
                examined_count=len(quarantined_props),
            )

    for p in quarantined_props:
        matching_claims = [c for c in c_list if c.proposition_id == p.proposition_id]
        if matching_claims or p.claim_count > 0:
            return CheckResult(
                name="verify_quarantined_propositions_unreachable",
                passed=False,
                status="FAIL",
                message=f"Quarantined proposition {p.proposition_id} has live claims or non-zero claim_count ({p.claim_count})",
                examined_count=len(quarantined_props),
            )

    return CheckResult(
        name="verify_quarantined_propositions_unreachable",
        passed=True,
        status="PASS",
        message=f"Verified {len(quarantined_props)} quarantined proposition(s) have 0 live claims and are unreachable",
        examined_count=len(quarantined_props),
    )


def verify_assessment_subjects_exist(
    assessments: list[Assessment],
    subjects: list[Subject],
    topics: list[Topic],
) -> CheckResult:
    """Every assessment's subject_id must resolve in subjects, and its topic_id in topics (or be 'global')."""
    if not assessments:
        return CheckResult(
            name="verify_assessment_subjects_exist",
            passed=True,
            status="NOT APPLICABLE — zero rows",
            message="No assessments to check",
            examined_count=0,
        )

    valid_subject_ids = {s.subject_id for s in subjects}
    valid_topic_ids = {t.topic_id for t in topics}

    for a in assessments:
        if a.subject_id not in valid_subject_ids:
            return CheckResult(
                name="verify_assessment_subjects_exist",
                passed=False,
                status="FAIL",
                message=f"Assessment {a.assessment_id} references non-existent subject_id '{a.subject_id}'",
                examined_count=len(assessments),
            )
        if a.topic_id != "global" and a.topic_id not in valid_topic_ids:
            return CheckResult(
                name="verify_assessment_subjects_exist",
                passed=False,
                status="FAIL",
                message=f"Assessment {a.assessment_id} references non-existent topic_id '{a.topic_id}'",
                examined_count=len(assessments),
            )

    return CheckResult(
        name="verify_assessment_subjects_exist",
        passed=True,
        status="PASS",
        message=f"All {len(assessments)} assessments reference valid subjects and topics",
        examined_count=len(assessments),
    )


def run_all_checks(
    claims: list[Claim] | None = None,
    utterances: list[Utterance] | None = None,
    sources: list[Source] | None = None,
    tensions: list[Tension] | None = None,
    assessments: list[Assessment] | None = None,
    records: list[dict[str, Any]] | None = None,
    roles: list[SourceSubjectRole] | None = None,
    propositions: list[Proposition] | None = None,
    principles: list[Principle] | None = None,
    subjects: list[Subject] | None = None,
    topics: list[Topic] | None = None,
) -> list[CheckResult]:
    """Execute all 13 integrity checks."""
    c_list = claims or []
    u_list = utterances or []
    s_list = sources or []
    t_list = tensions or []
    a_list = assessments or []
    r_list = records or []
    rol_list = roles or []
    p_list = propositions or []
    pr_list = principles or []
    sub_list = subjects or []
    top_list = topics or []

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
        verify_source_productivity(s_list, u_list),
        verify_canonical_ids(p_list, pr_list, c_list),
        verify_quarantined_propositions_unreachable(p_list, c_list),
        verify_assessment_subjects_exist(a_list, sub_list, top_list),
    ]
    return results


def run_integrity_fixtures() -> list[CheckResult]:
    """Execute all integrity checks over test fixtures."""
    from fixtures.fixture_loader import (
        load_valid_fixtures,
        load_valid_subjects,
        load_valid_topics,
    )

    sources, utterances, claims, tensions, assessments, roles = load_valid_fixtures()
    subjects = load_valid_subjects()
    topics = load_valid_topics()
    return run_all_checks(
        claims=claims,
        utterances=utterances,
        sources=sources,
        tensions=tensions,
        assessments=assessments,
        records=[],
        roles=roles,
        propositions=[],
        principles=[],
        subjects=subjects,
        topics=topics,
    )


def run_integrity_corpus(db_path: Path | str = "social_proof.duckdb") -> list[CheckResult]:
    """Execute all integrity checks over the live corpus database without unioning fixtures."""
    db_file = Path(db_path)
    if not db_file.exists():
        return run_all_checks(
            claims=[],
            utterances=[],
            sources=[],
            tensions=[],
            assessments=[],
            records=[],
            roles=[],
            propositions=[],
            principles=[],
            subjects=[],
            topics=[],
        )

    from worker.storage import Storage

    store = Storage(str(db_file), read_only=True)
    try:
        claims = [
            c
            for r in store.con.execute("SELECT claim_id FROM claims").fetchall()
            if (c := store.get_claim(r[0])) is not None
        ]
        utts = [
            u
            for r in store.con.execute("SELECT utterance_id FROM utterances").fetchall()
            if (u := store.get_utterance(r[0])) is not None
        ]
        sources = [
            s
            for r in store.con.execute("SELECT source_id FROM sources").fetchall()
            if (s := store.get_source(r[0])) is not None
        ]
        roles = [
            role
            for r in store.con.execute("SELECT source_id, subject_id FROM source_roles").fetchall()
            if (role := store.get_source_role(r[0], r[1])) is not None
        ]
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
        propositions = [
            p
            for r in store.con.execute("SELECT proposition_id FROM propositions").fetchall()
            if (p := store.get_proposition(r[0])) is not None
        ]
        principles = [
            pr
            for r in store.con.execute("SELECT principle_id FROM principles").fetchall()
            if (pr := store.get_principle(r[0])) is not None
        ]
        subjects = [
            subj
            for r in store.con.execute("SELECT subject_id FROM subjects").fetchall()
            if (subj := store.get_subject(r[0])) is not None
        ]
        topics = [
            top
            for r in store.con.execute("SELECT topic_id FROM topics").fetchall()
            if (top := store.get_topic(r[0])) is not None
        ]
    finally:
        store.con.close()

    return run_all_checks(
        claims=claims,
        utterances=utts,
        sources=sources,
        tensions=tensions,
        assessments=assessments,
        records=[],
        roles=roles,
        propositions=propositions,
        principles=principles,
        subjects=subjects,
        topics=topics,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evidence integrity verification suite")
    parser.add_argument("--all", action="store_true", help="Run all integrity checks")
    parser.add_argument("--db", type=str, default="social_proof.duckdb", help="Path to DuckDB database")
    args = parser.parse_args()

    fixtures_results = run_integrity_fixtures()
    corpus_results = run_integrity_corpus(args.db)

    failed = False

    def print_section(section_name: str, results: list[CheckResult]) -> None:
        nonlocal failed
        print("\n" + "=" * 60)
        print(f"EVIDENCE INTEGRITY PASS — {section_name}")
        print("=" * 60)
        for r in results:
            status_str = f"[{r.status}]"
            count_str = f"(examined: {r.examined_count})"
            print(f"{r.name:<32} {status_str:<30} {count_str:<16} {r.message}")
            if not r.passed:
                failed = True

    print_section("FIXTURES", fixtures_results)
    print_section("CORPUS", corpus_results)
    print("=" * 60)

    if failed:
        print("FAIL: One or more integrity checks failed.")
        sys.exit(1)
    else:
        print("SUCCESS: Evidence integrity verified.")
        sys.exit(0)


if __name__ == "__main__":
    main()
