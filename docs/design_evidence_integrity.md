# Evidence Integrity — The Contract

**Contract for:** every phase. This document constrains all of them.

**Why it exists.** Social Proof makes claims about real, named people. Right now it is local and single-user, so the external exposure is close to zero — but the discipline is not primarily about liability. **A false finding is worthless to you.** The entire value of the tool is that when it says "you said both of these," you can trust it without re-checking. A system that is right 90% of the time forces you to verify everything, which is the work you were trying to avoid. Integrity discipline is what makes the output *useful*, and it happens to also be what makes it safe to share later. Building it in now costs a fraction of retrofitting it.

---

## 1. What the system may and may not assert

| May assert | May never assert |
|---|---|
| "On these two dates, you said these two things." | "You lied." |
| "No acknowledgement of this change appears in the corpus." | "You never acknowledged it." *(absolute, beyond the corpus)* |
| "These two applications of the same stated principle differ, and no distinction was given." | "You are a hypocrite." |
| "This claim was made on a friendly show and the opposite under adversarial questioning, the same week." | "You tell different audiences what they want to hear." |
| "Insufficient corpus to assess." | A number computed on thin evidence. |

The pattern: **every assertion is scoped to the corpus and to the record, never to the person's character or intent.** The system observes; the reader concludes. This is not hedging — it is the actual epistemic position, and stating it accurately is what makes the strong findings credible.

---

## 2. The five operational rules

Collected here because they are enforced together by one pass.

| # | Rule | Enforced by |
|---|---|---|
| **E1** | Every rendered claim carries a verbatim quote, a date, and a resolvable source locator. | Widget tests + integrity pass |
| **E2** | Every quoted string `grep -F`-matches its stored source text. | `verify_quotes` (§3) |
| **E2b** | Every quote **supports the proposition attached to it.** E2 alone proved words were said; it never proved they said *that*. A published tension was traced to two real quotes carrying an invented proposition — Issue 025. | Extraction validator 6 (`design_claim_extraction.md` §8) |
| **E3** | Nothing derived from page context ever persists. | `verify_no_page_context` (§3) |
| **E4** | Below the per-axis gate, no number is computed — not computed-and-hidden. | `verify_no_suppressed_scores` (§3) |
| **E5** | Any Tension whose preconditions fail is quarantined, never rendered. | `verify_quarantine_not_rendered` (§3) |

---

## 3. The automated integrity pass

Runs on every ingest completion and in CI. **A failure is a build failure, not a warning.** Findings are the product; a warning in a log is a finding nobody reads.

Evaluates two independent populations — `FIXTURES` and `CORPUS` — reporting each separately and never unioning them. Each check prints its examined count. If the corpus database is absent or empty, the corpus run reports `NOT APPLICABLE — zero rows`. Exit is non-zero if either population fails.

```
verify_quotes
    For every Claim: grep -F the quote_span substring against
    utterances.text_verbatim. Zero tolerance — one miss fails the pass.
    This is the check that catches fabrication.

verify_anchor_chain
    Every Claim → Utterance → Source resolves. No orphans, no dangling
    source_ids, no utterance whose source was deleted.

verify_no_page_context
    After each /resolve call in the suite: assert zero rows anywhere with
    origin = 'page_context'. Invariant I2, enforced rather than intended.

verify_no_suppressed_scores
    For every Assessment: sufficiency must explicitly carry `passed: bool`.
    If `passed` is missing, the check fails with `sufficiency_verdict_missing`.
    When `passed` is False: assert every axis score is literally null, not a number
    behind a flag. Invariant I5.

verify_quarantine_not_rendered
    For every quarantined Tension: assert it appears in no assessment's
    axis_evidence and in no timeline payload.

verify_attribution_floor
    Every Claim participating in a published Tension traces to an
    utterance with attribution_confidence = high.

verify_negation_recheck
    Every published Tension's two claims have transcription_pass_count ≥ 2.
    design_source_acquisition.md §5.3 — the dropped-negation guard.

verify_versions_present
    Every Assessment carries rubric_version, extraction_version,
    detector_version, embedding_model. A score without provenance
    cannot be reproduced or retired.

verify_canonical_ids
    For every proposition and principle, stored_id == compute_*_id(canonical_text).
    Also asserts claim_count matches the real count from claims table.

verify_quarantined_propositions_unreachable
    For every quarantined Proposition, no live claim references it, and it cannot
    be returned by the /resolve query shape (active status and live claims required).

verify_assessment_subjects_exist
    For every Assessment: its subject_id resolves in subjects, and its topic_id
    resolves in topics or is 'global'. Prevents test pollution and unlinked assessments.
```

---

## 4. Quarantine

A Tension that fails a precondition is **written with `status: quarantined` and a reason** — not silently dropped.

Dropping hides the failure rate. Quarantining makes it a measurable number: how many findings the system generated and then declined to publish, and why. That number is the health metric for the whole pipeline. A quarantine rate that suddenly falls to zero usually means a precondition stopped being checked, not that quality improved.

Quarantined Tensions are visible in a review surface. **They never enter a score and never render as findings.**

### Propositions quarantine too (Issue 027 = A)

Quarantine was originally a Tension-only mechanism, and that was too narrow. The fabricated licensing proposition survived X0's cleanup precisely because **the tension was quarantined and the proposition it carried was not** — leaving the invented text in the store, still embedded, and still the most reachable row `/resolve` could return.

A Proposition therefore carries `status` and `quarantine_reason` as well. The vocabulary is **`active` / `quarantined`**, not the Tension's `published` / `quarantined` / `dismissed`: a proposition is never itself rendered — it is a join key — so "published" would assert something untrue about it.

**A quarantined Proposition is unreachable, not merely unrendered.** No read path returns it, `/resolve` included, and no new claim may be attached to one. `verify_quarantined_propositions_unreachable` enforces this in the integrity pass.

### Assessments are referentially guarded

`verify_assessment_subjects_exist` requires every assessment's `subject_id` to resolve in `subjects` and its `topic_id` in `topics`. The anchor chain covers claims → utterances → sources and stopped there, so an assessment naming a subject that did not exist sat in the production corpus and passed all twelve checks before it.

**A sufficiency verdict is a stored fact, not an inference.** `verify_no_suppressed_scores` reads `sufficiency["passed"]` with **no default**: a missing verdict is a FAIL, not a pass. That verdict must be computed from the sufficiency *inputs* — claim count, source count, span — against the I5 thresholds, and **never from whether any axis produced a score.** A verdict derived from the scores it exists to gate makes the check tautological: `not passed` becomes true only when every score is already null, and the search for a suppressed score can never find one.

**The rule this generalises to: when a finding is quarantined, quarantine what it was made of.** A false finding assembled from a fabricated part leaves that part behind, and the part is what gets reused.

---

## 5. Correction path

Every Tension card carries `report a problem` (`design_ui_direction.md` §5). One click:

1. Quarantines the Tension immediately, with reason `user_reported`.
2. Recomputes the affected Assessment without it.
3. Files it for review with the full anchor chain attached.

**Quarantine first, investigate second.** A suspected false finding should stop being displayed and stop affecting a score in the same instant it is reported — the cost of wrongly quarantining a true finding is that you look at it again later; the cost of continuing to display a false one is the thing this whole document exists to prevent.

---

## 6. Uncertainty is displayed, not hidden

Where the system is unsure, it says so on the surface rather than resolving the uncertainty silently in either direction:

- Low-confidence extraction → the Tension is quarantined, not shown with a small warning icon.
- Unresolved actor in a principle application → excluded from conflict detection entirely, never guessed.
- Ambiguous quote-agreement → `exclusion_reason: quote_agreement_unclear`, excluded from scoring, visible in review.
- Wide-gap reversal → labelled with the interval in plain language, routed to Update Integrity before Consistency.

A confident-looking finding built on a coin flip is worse than no finding, because it spends the credibility that makes the good findings worth reading.

---

## 7. If this ever leaves your machine

Not in scope, but the design should not foreclose it. Before any surface is shared with anyone else:

- The integrity pass must be green, and its results must be visible to the reader, not just to the operator.
- Subjects must be public figures with corpora clearing the sufficiency gate (invariant I5).
- No composite scores, no shareable score images stripped of evidence (`design_ui_direction.md` §8).
- A correction path must exist for the *subject*, not only for the user.

Everything above is already true of the local design, which is the point — the local version is not a relaxed version of the shareable one.
