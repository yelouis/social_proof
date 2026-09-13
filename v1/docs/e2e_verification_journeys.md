# Golden Corpus & End-to-End Verification Journeys

**Contract for:** every phase from 2 onward. Nothing in the logic layer is "done" until its journey passes.

---

## 1. Why this doc comes before the detector

**You cannot tell a working contradiction detector from a confident one by looking at its output.** Both produce plausible pairs of quotes. The difference only shows up against cases where you already know the right answer.

Every threshold in `ongoing_errors.md` §2 is set here. Every claim of "precision" traces here. A phase that ships without its cases has not been verified — it has been demonstrated, which is a different and much weaker thing.

**Since Issue 018 = Option B, be precise about which of the two bodies (§2) any given claim rests on.** A green fixture suite says a code path still fires. It says nothing whatsoever about quality, and a report that implies otherwise is the defect this section exists to prevent.

---

## 2. Two corpora, and they must never be blended

**Issue 018 = Option B.** There are two distinct bodies of labelled data with two distinct jobs. Reporting them through one number is exactly how `Precision 1.000` came to be printed over sixteen invented sentences.

| | **Behaviour fixtures** | **Golden corpus** |
|---|---|---|
| Lives in | `fixtures/behaviour/` | `golden/` |
| Content | Hand-written sentences, one or more per case class | Labelled utterances from **real ingested sources** |
| Locators | Synthetic, and openly so | Real `source_id` + span into the artifact store |
| Answers | *"Does this code path still fire?"* | *"How good is this system?"* |
| Output | **PASS / FAIL only.** Never a rate. | Measured precision, recall, per-class rates |
| Grows by | Adding a case when a bug is found | Labelling as subjects get ingested |
| Verified by | The author of the case | A human who listened to or read the original |

**The rule that makes this work: a fixture may never contribute to a metric, and a corpus case may never be hand-written.** The harness loads them separately and reports them in separate blocks. If a single number ever spans both, the split has failed.

The sixteen existing cases become **behaviour fixtures**. They keep all of their regression value and lose their claim to measure anything.

### Scale — the golden corpus

Small and deliberate beats large and sloppy. Target **3–5 subjects, 2–3 topics each, ~200 labelled utterances, ~40 labelled Tension candidates**, every one personally verified against the original. A thousand auto-labelled examples are worth less than forty you checked.

Under Option B this accumulates **as subjects are ingested** rather than blocking the build. The consequence to plan around: **parameters 004, 008, 012 and 016 stay provisional until their relevant class crosses the floor of 5 cases.** Anything tuned before then is a placeholder and must be labelled as one in the code and in the commit body.

### Scale — the behaviour fixtures

At least one per class, more when a bug is found. **A fixture is added every time a regression is fixed** — that is the mechanism by which this set stays useful rather than ossifying.

### Schema — behaviour fixtures

Every behaviour fixture case carries `utterances: [...]`, with uniform shape across both single- and multi-utterance cases:
- `text`: verbatim utterance text
- `recorded_at`: ISO 8601 timestamp string (e.g. `2024-03-02T18:00:00Z`). Loader enforces presence and ISO 8601 validity on every utterance.
- `span`: character offsets `[start, end]`
- Optional utterance metadata: `speaker`, `venue_type` (`friendly` / `adversarial`), `audience_stance`, `hedging_level`, `condition`, `stated_distinction`, `published_at`, `change_marker`.

Single-utterance classes (`N1–N4`, `N10`, `N13`) carry a one-element list. Pair and sequence classes (`P1–P4`, `N5–N9`, `N11–N12`) carry two or more utterances (`N11` requires at least 6). The loader rejects any pair-type fixture with fewer than 2 utterances.

### Composition — the negatives are the important half

A corpus of only true contradictions measures recall and tells you nothing about false-positive rate, which is the failure mode that matters here.

| # | Case | Expected behaviour |
|---|---|---|
| **P1** | Verified unacknowledged reversal | Tension `unacknowledged_reversal`, Consistency ↓ |
| **P2** | Verified reasoned update ("I used to think X, changed my mind because Y") | `acknowledged_update`, Update Integrity ↑, **not** a Consistency penalty |
| **P3** | Verified principle conflict, no distinction given | `principle_conflict` |
| **P4** | Verified audience divergence (same week, opposite venues) | Flagged pair |
| **N1** | Sarcasm — deadpan register, inverted meaning | No claim, or `exclusion_reason: sarcasm` |
| **N2** | Reported speech — "their argument is that X" | `is_own_assertion: false`, `reported_speech` |
| **N3** | Steelman — "the strongest case for X is…" | `is_own_assertion: false`, `steelman` |
| **N4** | Hypothetical — "suppose X were true" | `is_own_assertion: false`, `hypothetical` |
| **N5** | Conditional vs unconditional on the same proposition | **No Tension** — `condition` mismatch |
| **N6** | Principle applied differently **with** a stated distinction | **No Tension** — `distinguished` |
| **N7** | Hedge followed by firm position | Low-weight or no reversal, not a full-weight one |
| **N8** | Topic drift — same words, 8 years apart, different referent | No Tension, or wide-gap flagged |
| **N9** | **Misattribution trap** — host asserts X, guest asserts not-X, same episode | **No Tension.** Both claims correctly attributed |
| **N10** | Quote-agreement unclear — reads a tweet aloud, no comment | Excluded, `quote_agreement_unclear` |
| **N11** | Thin-corpus subject, 6 claims on the topic | `insufficient_corpus`, **no number computed** |
| **N12** | Re-aired archive audio published years after recording | Dated to original recording, no false reversal |

**N9 is the one to build first.** Cross-speaker misattribution is the failure that produces a confident, well-cited, completely false accusation against a real named person, and it is invisible in any output that doesn't specifically test for it.

### Metrics and targets — golden corpus only

### How the corpus is labelled — Issue 019 = Option C

The golden corpus is **labelled by a model, with no human in the loop.** That choice buys scale, and it costs something specific that must be visible in every number it produces:

> **A metric computed over model-labelled cases measures *agreement with the labeller*, not accuracy.**

Two consequences, both mandatory:

1. **Name the metrics for what they are.** The harness prints `agreement_with_labeller`, never `precision`, for any class whose cases are `label_source: model_only`. A number called "precision" over an answer key the machine wrote is the same category of error as `Precision 1.000` over sixteen invented sentences — it claims more than it verified.
2. **Never label with the model under test.** Enforced in the loader: a case whose `labeller_model` equals the configured extractor is rejected. Otherwise the system grades itself and scores perfectly by construction.

**The known blind spot, recorded so it is not rediscovered as a surprise.** N1–N4 (sarcasm, reported speech, steelman, hypothetical) are hard *for language models*, and models trained on similar data fail on them in correlated ways. A model labeller will therefore tend to agree with the extractor on exactly the cases the corpus exists to catch. **N1–N4 agreement figures are the least informative numbers in the report and must never be read as the most reassuring.** If any class is later hand-verified, mark it `label_source: human` and report it separately — a mixed figure hides which half is load-bearing.

**These are computed over the golden corpus and nothing else.** Each is suppressed as `NOT MEASURED — n=<k>, minimum 5` until its class clears the floor.

| Metric | Target | Why |
|---|---|---|
| Tension **precision** (published findings that are real) | **≥ 0.95** | A false finding costs more than ten missed ones. This is the number that matters. |
| Tension recall | ≥ 0.60 | Missing findings is acceptable; the tool is still useful at 60%. |
| Misattribution rate (N9) | **0** | Not a target — a gate. Non-zero blocks the phase. |
| False-exclusion rate (real claims wrongly excluded by I7 guards) | ≤ 0.10 | Measurable only because exclusions are recorded, not dropped. |
| Quote-span resolution failures | **0** | Any failure is fabrication. |

---

## 3. Journeys

Each journey names its phase, its gate, and — critically — **how to make it fail**.

> **A guard that has never failed has not been tested.** For every journey, deliberately break the thing it protects, watch it go red, then revert. Record both outcomes in the commit body. A green suite proves nothing about a check that would stay green if the check were deleted.

---

### J1 — Cold ingest, one subject, one source · *Phase 0*
**Status:** PASSING (September 2, 2026 — delivered in I0.2; updated in R0)
Ingest one subject from one podcast episode end to end.
**Gate:** every utterance has word timestamps; every `text_verbatim` `grep -F`-resolves; the anchor chain Claim→Utterance→Source has no orphans; **source productivity passes (`verify_source_productivity`: source yields ≥1 utterance covering a plausible fraction of media duration; audio deletion strictly gated on output).**
**Falsify:** corrupt one stored `text_verbatim` by a single character; `verify_quotes` must fail. Simulate a zero-utterance ingest; `audio_deleted_at` must remain null and audio must survive.

### J2 — Guest appearance with diarization · *Phase 1*
**Status:** PASSING (September 2, 2026 — delivered in I0.3)
Ingest a multi-speaker episode containing golden case **N9**.
**Gate:** zero utterances attributed to the wrong speaker; sub-threshold utterances stored with `attribution_confidence: low` and excluded from scoring.
**Falsify:** swap the enrollment embeddings of two speakers; the misattribution count must go non-zero.

### J3 — Extraction guard suite · *Phase 2*
Two halves, reported separately (§2).
**Fixture gate (PASS/FAIL, no rates):** run extraction over `fixtures/behaviour/`. All of N1–N4 and N10 excluded with the correct `exclusion_reason`; no proposition text contains polarity; every `quote_text` resolves.
**Corpus metrics (suppressed until each class clears 5):** false-exclusion rate and precision over `golden/`, with **N1–N4 reported as their own line** — a good aggregate will hide a bad number on the four speech-act guards, which is exactly where a local model is weakest.
**Falsify:** remove the steelman clause from the extraction prompt; the N3 fixture must go RED.

### J4 — Topic resolution stability · *Phase 3*
**Status:** PASSING (September 2, 2026 — delivered in P3)
Resolve the same free-text query twice, in separate processes.
**Gate:** byte-identical resolved proposition sets and an identical cache key.
**Falsify:** bump `embedding_model` in the key; the cache must miss rather than silently return the stale set.

### J5 — Reversal vs. reasoned update · *Phase 4*
**Status:** PASSING (September 2, 2026 — delivered in P4)
Run detection over P1 and P2.
**Gate:** P1 → `unacknowledged_reversal`. P2 → `acknowledged_update` and **no Consistency penalty**. N5 and N7 produce no full-weight Tension.
**Falsify:** narrow the acknowledgement search to the later utterance only; P2 must flip to `unacknowledged_reversal`. This is the single most important falsification in the suite — it is the check that keeps the system from punishing honesty.

### J6 — Principle conflict and the stated distinction · *Phase 5*
**Status:** PASSING (September 2, 2026 — delivered in P5)
Run over P3 and N6.
**Gate:** P3 → `principle_conflict`. N6 → `distinguished`, excluded from the score. Every actor resolved or marked `unknown`; no `unknown` actor enters a conflict.
**Falsify:** disable stated-distinction detection; N6 must become a published conflict.

### J7 — Sufficiency gate · *Phase 6*
**Status:** PASSING (September 2, 2026 — delivered in P6)
Assess golden subject N11.
**Gate:** the axis is `null` with a reason. **Assert no number exists anywhere in the stored document** — not hidden, not behind a flag, not zero.
**Falsify:** compute-and-suppress instead of not computing; the assertion must fail.

### J8 — News as index, never evidence · *Phase 8*
**Status:** PASSING (September 2, 2026 — delivered in P7)
`POST /resolve` with a real article, then sweep the store.
**Gate:** zero rows with `origin = 'page_context'`; no `Source`, `Utterance`, `Claim`, `Proposition`, or embedding traceable to the article; resolution returns only pre-existing corpus ids.
**Falsify:** persist the page text deliberately; `verify_no_page_context` must fail.

### J9 — Cross-version comparison refusal · *Phase 10*
Compare two subjects whose assessments were computed under different `rubric_version`s.
**Gate:** `409`, with a recompute offer. Never a silent comparison.
**Falsify:** remove the version check; the comparison must succeed, proving the check was load-bearing.

### J10 — Negation trap · *Phase 4*
Synthetically strip the negation from one transcript span of a known non-reversal.
**Gate:** the two-pass re-check (`design_source_acquisition.md` §5.3) disagrees, and the resulting Tension is **quarantined, not published**.
**Falsify:** disable the second pass; the fabricated contradiction must publish. That it *can* publish is the whole reason the guard exists.

### J11 — Re-ingest idempotency · *Phase 1*
**Status:** PASSING (September 2, 2026 — delivered in I0.2)
Run ingest twice on the same subject with no new sources.
**Gate:** zero new rows, zero duplicate ids, zero re-transcription, and no change to any assessment.
**Falsify:** make one id non-deterministic; duplicates must appear.

### J12 — Integrity pass gates the build · *All phases*
**Gate:** the full pass in `design_evidence_integrity.md` §3 runs in CI and **fails the build**, not the log.
**Falsify:** introduce one unresolvable `quote_span`; CI must go red.

---

## 4. Standing verification rules

Carried over from hard-won experience on a prior project; each of these has cost a cycle somewhere.

1. **A guard that has never failed has not been tested.** Falsify every journey; record both outcomes.
2. **Measure, do not estimate.** Cost figures come from `count_tokens`, precision from the golden corpus, thresholds from measurement. A number in a doc with no measurement behind it is a guess wearing a lab coat.
3. **A verdict line must not name a verification method the report has no data for.** If a run happened and its output was lost, that is **NOT RUN**, not "verified."
4. **A green suite is not evidence about anything it cannot observe.** The extraction suite says nothing about diarization; the widget suite says nothing about what the worker actually wrote.
5. **Every quoted string in any report must be findable with `grep -F`.** Applies to the reports agents write about this system, not only to the system's own output.
6. **Do not weaken an assertion or delete a test to reach green.** If a gate is wrong, change it deliberately, in its own commit, with the reason recorded.
7. **Line numbers drift.** Re-grep for the expression; never cite a bare line number as a permanent reference.
