# Engineering Issues & Decisions — Working Log

**What this file is:** open decisions that need you, the parameters still to be measured, and a one-line record of every decision already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §4. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 24 decisions made, 1 open (034).** Live work is queued in `agent_execution_guide.md` §6.

---

## 1. OPEN — awaiting your selection

*Newest first.*

### 034 — Three prompt iterations have not produced a position-bearing proposition table, and each one costs a corpus

**Blocks:** any further work on the extraction form. **Filed:** September 9, 2026, from a live query at `3100a48`.

**What was measured.** Three passes have now tried to fix proposition form, each correct in its own terms, each shrinking the corpus, and none producing a table you can detect a contradiction in:

| | claims | propositions | ≤5 words | cross-episode candidates |
|---|---|---|---|---|
| after C1 | 3,669 | 3,477 | — | 0 |
| after D1 *(noun-phrase form)* | 2,174 | 2,113 | 25.8% | 4 (all false) |
| after D5 repair | 2,261 | 2,161 | 25.8% | 6 (all false) |
| **after D6** *(position floor)* | **1,027** | **1,007** | **17.4%** | **0** |

**The corpus is 28% of its post-C1 size and the candidate set is back where it started.**

**And the acceptance gate keeps passing when an independent reading fails it.** D6's (c) required 16 of 20 randomly drawn propositions to pass the position test and reported **18/20 (90%)**. I drew 20 with a recorded seed (`20260909`) and applied D6's own test — *are "supports X" and "opposes X" both coherent and different?* — and got **9/20 strict, 13/20 charitable.** Below the gate either way. The failures are not exotic:

> *implementing software inside of an organization* · *prompt length for ai model development* · *understanding of partisanship and gamesmanship in negotiations* · *a good deal to be made* · *finding it very hard to get to two by 2040*

This is the third time a judgement-based gate has been recorded as met while an independent reading disagreed — D2 recorded six false pairs as *"hand-read and verified"*, D1 recorded a failed (c) as verified, and now this. **The pattern is not carelessness. It is that the test is applied by looking at a proposition and asking whether it seems positionable, which is much easier to answer yes to than actually writing the two sentences out.**

**What is not in question.** D6's mechanical floor is real and working (495 of 2,161 old propositions rejected, 22.9%), Parameter 033 still holds across all 23 sources, and D6 reported its 55% claim loss honestly and reconciled it. This is not a quality-of-work problem.

---

**Option A — A fourth prompt iteration, with the gate applied by writing the sentences.** Keep the approach; change only how the gate is scored: the agent must write out *"<subject> supports X"* and *"<subject> opposes X"* for each of the 20 and paste both sentences into the commit body, so a reader can check the judgement instead of taking the count.

- **Pro:** smallest change. The mechanical floor is already in place, and each pass has genuinely improved the named metric.
- **Pro:** it directly attacks the thing that keeps going wrong — the gate, not the prompt.
- **Con:** three passes have not converged, and each costs a full re-extraction plus another slice of the corpus. There is no evidence a fourth converges.
- **Con:** it still asks a model to produce a neutral matter at issue and hope it is positionable, which is the part that has failed repeatedly.

**Option B — Elicit the position and the proposition together.** ← **recommended**

Change what the extractor is asked for. Instead of *"give me the neutral matter at issue"* and labelling stance afterwards, ask it to emit, per claim, the pair **"the speaker is FOR / AGAINST ⟨X⟩"** — and take ⟨X⟩ as the proposition. **A claim it cannot phrase that way is not emitted.**

- **Pro:** the position test stops being a judgement applied afterwards and becomes a **property of the output format.** *"implementing software inside of an organization"* cannot be produced, because "the speaker is FOR implementing software inside of an organization" is not a sentence the model would generate about that utterance.
- **Pro:** it does not change the schema or violate §2. ⟨X⟩ is still stance-neutral and polarity still lives in `stance`; only the elicitation changes, so the proposition self-join and everything downstream is untouched.
- **Pro:** it removes the failure mode that has now cost three passes — a gate scored by impression.
- **Con:** a real change to the extraction contract, and `design_claim_extraction.md` §2 needs restating to describe the frame without weakening stance-neutrality.
- **Con:** the corpus shrinks again on the next extraction, and we do not know by how much until it runs.

**Option C — Accept that most utterances carry no positionable claim, and stop trying.** Keep the current form, drop the target, and let the corpus be small and clean.

- **Pro:** honest, and free. 1,027 claims across 23 episodes with a working mechanical floor is a real artefact, and the review site renders it today.
- **Pro:** stops spending re-extractions on a target that has not moved.
- **Con:** the product's central claim stays undemonstrated, and **P4–P6 remain unvalidated as behaviour**, which has been true for the entire build.
- **Con:** it does not fix the propositions that *do* get through — 45–65% of them still fail the position test, so any future finding is built on the same ground.

**Recommendation: B.** The thing that has failed three times is not the prompt wording; it is that *"is this positionable?"* is asked after the fact and answered generously. B makes it unanswerable rather than easy — the format either produces the sentence or it does not. **A is worth folding into B regardless**: whichever option you pick, the gate should be scored by pasting the two sentences, not by reporting a count.

Your selection: _____

---

> **For the agent filing a new one:** insert it at the **top** of this section, not the bottom, and use the next free number. Include what is blocked, what you already tried, 2–3 options with honest pros *and* cons, a marked recommendation, and a final `Your selection: _____` line. Then set `blocked_on` in the guide's queue. Never fill the line in.

---

## 2. Parameters to be measured, not selected

**These are not decisions and must not be guessed.** Each is a threshold discovered by running against the golden corpus (`e2e_verification_journeys.md`). An agent that picks a number here and moves on has skipped the work. **Every one is provisional until its class clears the 5-case floor** (Issue 018 = B), and must be labelled provisional in code and in the commit body.

| # | Parameter | Set during | Bias |
|---|---|---|---|
| **004** | Speaker attribution thresholds (high / low); summit / remote margin calibration: `best_sim >= 0.60` with `margin >= 0.25` | Phase 1 / C1 | **Precision.** A missed utterance costs nothing; a misattributed one is the worst bug in the product. In live summit / reverberant acoustics (e.g. Paris Robotics Summit), host similarity drops to ~0.61, but separation margin to distractors remains >= 0.25 (4x the 0.10 floor), providing unequivocal identity evidence without false positives. |
| **008** | `T_dedup = 0.84` — proposition semantic deduplication merge threshold (single source of truth in `worker/extract/dedup.py`, Item W1 & Item D2); ambiguous-band adjudication does not earn its cost; re-pointing guarded by entailment validation (`T_ENTAIL_HIGH = 0.70`); indexical propositions prohibited (Item W0); canonical noun-phrase matter at issue enforced (Item D1); position-bearing matter at issue enforced (Item D6) | Phase 2 / P0 / W1 / W0 / C1 / D1 / D2 / D6 | **Toward merging, guarded by entailment and self-containedness.** Over-splitting hides every contradiction, silently. Re-measured September 6, 2026 over live corpus ($n = 2,191$ active propositions, 2,261 claims, prompt `v1.6` with canonical noun-phrase matter at issue, 0% finite verbs, 0 polarity violations, 23 sources). 1-NN cosine similarity distribution ($n=2,191$): min 0.5861, max 0.9940, mean 0.7586, std 0.0586; deciles D10 0.6902, D20 0.7078, D30 0.7238, D40 0.7396, D50 0.7547, D60 0.7688, D70 0.7837, D80 0.8072, D90 0.8351, D100 0.9940 (p95 0.8543). Threshold $T_{\text{dedup}} = 0.84$ selected above D90: both canonical directions pass (China open source pairs merge at 0.8498 and 0.8575 $\ge 0.84$; high speed trains does not merge at 0.6749 and 0.4774 $\ll 0.84$). Under Item D6, bare-topic propositions were pruned via mechanical floor (`validate_position_bearing`) and prompt `v1.7`. Re-extraction across all 23 sources produced 1,027 claims across 1,007 active propositions with $T_{\text{dedup}} = 0.84$ preserved unchanged. Claim count shortfall from 2,261 to 1,027 is fully reconciled: 583 bare-topic rejections, 110 question exclusions (I7), 313 quote verbatim misses, 115 entailment rejections, 62 stance direction rejections. All 6 candidate pairs from D2 were false reversals on bare topics and eliminated under the position test. Result: 0 published tensions, 3 quarantined historical fabrications preserved (100.0% quarantine rate). |
| **010** | Topic retrieval similarity + cluster-expansion policy | Phase 3 | **Precision on retrieval, generosity on expansion.** Small slices produce confident wrong scores. |
| **012** | `MIN_CLAIMS = 3`, `MIN_SOURCES = 1`, `MIN_SPAN_DAYS = 0` — sufficiency floor (Item E2, Invariant I5) | Phase 6 / E2 / W0 | **Conservative.** `insufficient_corpus` is always safe; a number on thin evidence never is. Evaluated strictly from inputs before scoring (verdict -> scores). Measured over clean corpus $n = 1,362$ claims across 4 sources and 1,237-day span (Chamath 343 claims / 4 sources / 1,237d, Sacks 504 claims / 4 sources / 1,237d, Jason 190 claims / 4 sources / 1,232d, Friedberg 325 claims / 4 sources / 1,237d; all 4 clear sufficiency on the merits). Per-axis gates: Specificity requires $\ge 3$ own-assertion claims in slice; Consistency requires $\ge 2$ eligible repeat propositions; Update Integrity requires $\ge 2$ stance changes; Even-handedness requires $\ge 4$ directional conflicts with $p < 0.05$. Below floor, emits `passed: False, reason: "insufficient_corpus"` and suppresses all axis calculations. Provisional until 5-subject floor. |
| **016** | `H_max` — hedging ceiling in Specificity's checkability test | Phase 6 | **Toward generosity.** Only pure evasion should fail; too strict and the axis punishes ordinary caution. |
| **026** | `MIN_QUOTE_TOKENS = 7`, `T_ENTAIL_LOW = 0.60`, `T_ENTAIL_HIGH = 0.70` — the entailment guard (Issue 025 = C, Item N0, dynamically guarded on re-pointing in Item W1) | X1 / N0 / W1 / C1 | **Reject boldly, quarantine the middle; enforce on re-pointing.** Re-measured over 23-source corpus ($n = 3,669$ claims): all 3,342 published claims clear entailment (>= 0.70) against current propositions. Extraction-time entailment validation embeds canonical normalized proposition string matching Check #14. Zero stored claims fail entailment against their current proposition. |
| **029** | `MIN_UTTERANCE_MEDIA_RATIO = 0.80` — source productivity coverage floor | R1 | **Conservative.** Catches truncation without rejecting ordinary podcast silence/intros/outros. Measured truncated corpus at 7.4%–7.9% (< 0.80 -> FAIL); full episodes clear > 0.90. Provisional until 5-case floor. |
| **031** | `delta = 0.05` — stance direction margin (Validator 7, Items S1 / §17n, D3 / §17t, D4 / §13w); augmented with scope-aware syntactic negation analysis (governance of proposition predicate, continuation modals, epistemic verbs, discourse markers, conversational qualifiers); standing bidirectional correction counters (`stance_corrected_to_support`, `stance_corrected_to_oppose`); `hedge` stance literal retired in favor of `hedging_level: float` on `Literal["support", "oppose", "mixed"]` | S1 (§17n) / D3 (§17t) / D4 (§13w) | **Directional entailment and scope-aware syntactic governance.** Sentence embeddings represent negation weakly ($sim(Q, P) \approx sim(Q, \neg P)$ within $\pm 0.005$), while un-scoped syntactic negation matches negators indiscriminately across quotes (causing a near 100% false-flip rate on live support claims containing negation, Item D4). Under Item D4, `has_syntactic_negation` enforces syntactic scope governance over proposition predicates while excluding non-scoping idioms, double-negative continuation modals (*"not going to stop"*), epistemic verbs (*"never predict that"*), attenuating qualifiers (*"not that much of an increase"*), and contrastive foil subclauses. Re-measured over drawn random sample from live corpus ($n=80$ own-assertion claims, seed 168): confusion matrix shows True Support: 75/75 (100.0%) ended Support, 0/75 (0.00%) ended Oppose (0.00% false-flip rate, down from 100% of negation claims under unmodified D3); True Oppose: 5/5 (100.0%) ended Oppose, 0/5 (0.00%) ended Support (Issue 018 = B 5-case floor satisfied); zero confusion errors across all 80 cases. All 4 canonical quotes end as `support`. Re-validated live corpus ($n=1,884$ own-assertion claims): 2 support $\to$ oppose flips, 6 oppose $\to$ support flips, 1,876 unchanged. Post-revalidation corpus ($n=2,174$): support 1,817 (83.58%), oppose 309 (14.21%), mixed 48 (2.21%), hedge 0 (0.00%). |
| **032** | `MIN_REVERSAL_GAP_DAYS = 0.0` (unmeasured / provisional until cross-episode candidates exist); same-source automatic disqualification (`source_a_id == source_b_id`) routes to `stance_conflict_reviews` with reason `same_source_stance_conflict` | T1 / C1 | **Toward requiring more time.** An unacknowledged reversal is by definition a change of mind over time; two claims within a single recording or episode are part of one continuous speech-act context (rhetorical setup, clarification, or hedge) and must be disqualified. False reversal is a published accusation; missed reversal is silence. Measured over 23-source corpus: 6 same-episode pairs disqualified and routed to review surface; all candidate pairs examined and rejected (0 false reversals published). Numeric gap parameter marked provisional/unmeasured until cross-episode candidates exist. |
| **033** | `MIN_CLAIMS_PER_HOUR = 3.0` — source claims-per-hour rate floor (Item D5 / §13x); replaces C1's zero-floor rule (`no source contributes zero claims`) with an audio-duration rate check in `worker/integrity.py` (`verify_claims_per_hour`) | D5 (§13x) | **Conservative rate floor guarding against silent truncation and starved sources.** Derived from empirical 23-source distribution: guest-dominated interview panels yield 6.7 to 7.5 claims/hr (Mark Cuban: 7.20 claims/hr pre-repair, Rahm Emanuel: 6.70 claims/hr, Saronic: 7.45 claims/hr), whereas starved sources due to extraction omission or truncation fall below 1.0 claim/hr (Robotics CEOs summit panel fell to 0.87 claims/hr under D1 omission). Red-first verified: check FAILS on pre-repair corpus naming `79e5cda81c5740e9` (0.87 < 3.0). Post-repair with host utterances extracted: Robotics CEOs rose to 50 claims (43.74 claims/hr), Mark Cuban rose to 43 claims (61.94 claims/hr), corpus grew 2,174 -> 2,261 claims; all 23 sources clear floor (observed range: 6.70 – 152.04 claims/hr). Provisional until 5-case floor. |

---

## 3. Deliberately not built — do not re-propose

Consolidated from `master_implementation_plan.md` §8 so it is checkable in one place. Re-proposing one of these costs a cycle.

Prediction/forecast scoring · fact-checking of any kind · a single global trust score · a composite of the rubric axes · radar charts · N-way comparison dashboards · face or voice recognition of strangers · scoring private individuals from thin corpora · unofficial X/Twitter scraping · inline article annotation · notification badges or contradiction counts · shareable score images stripped of evidence · sentiment visualisation.

**Deferred, not rejected** — designed for, with the trigger named: X/Twitter ingest · Elon Musk as a subject (Issue 023, waits on X ingest) · `corpus_composition` medium-skew reporting · the Flutter client · the ambient client.

---

## 4. Decision record

Newest first. One row each; **the design doc named is where that decision now lives** and is the thing to read. Full options and trade-offs are in git history.

| # | Decision | Now lives in |
|---|---|---|
| **030** | **A** — expand the corpus **chronologically, no selection**: a contiguous run of episodes, every one ingested, the rule recorded before the run. Rejected picking by theme: it buys overlap with the product's visible impartiality. | `design_source_acquisition.md` §2 · `agent_execution_guide.md` C1 |
| **033** | **Amends 028** — the review site is **served live from DuckDB per request**, not pre-rendered. The static export produced 2,593 HTML files and 27 MB for 1,288 claims; it is deleted. Write safety now comes from opening the database `read_only=True` rather than from having no server. | `design_ui_direction.md` §6b · `agent_execution_guide.md` U1 |
| **028** | **The review site**: panel shows *everything* (timeline, axes, tensions, principles) · **local only**, no hosting · **static export** DuckDB→JSON, no server and no write path · **fix findings first** — not built until a tension survives being read by hand | `design_ui_direction.md` §6 · `agent_execution_guide.md` U1 |
| **027** | **A** — repair the proposition table in place: normalize canonical IDs, merge the forked rows, backfill embeddings for live propositions, quarantine the fabricated proposition. Nothing purged. | `design_data_layer.md` §3–§4 · `design_evidence_integrity.md` §4 · `design_local_api_and_clients.md` §4 · `agent_execution_guide.md` D0 |
| **025** | **C** — entailment guard: embedding similarity + minimum quote length, ambiguous band quarantines | `design_claim_extraction.md` §8 validator 6 · `design_evidence_integrity.md` E2b |
| **024** | **B** — CI's one job is portability; `mlx-lm` optional, workflow renamed for its scope | `agent_execution_guide.md` C0 (delivered) |
| **023** | **A** — defer Musk until X ingest exists; his primary medium is excluded, and I5 gates volume not composition | `agent_execution_guide.md` §Deferred |
| **022** | **A** — `SourceSubjectRole`: tier and venue belong to a (source, subject) pair | `design_data_layer.md` §2–§3 · `design_source_acquisition.md` §2, §4 |
| **021** | **B** — first subjects are the four All-In hosts | `agent_execution_guide.md` I0 |
| **020** | **A** — `pyannote.audio`; token via `HF_TOKEN`, fail loudly if absent, never downgrade silently | `design_source_acquisition.md` §5.4 |
| **019** | **C** — model labels the corpus, no human in the loop | `e2e_verification_journeys.md` §2. **Consequence: metrics are named `agreement_with_labeller`, never `precision`.** |
| **018** | **B** — behaviour fixtures split from golden corpus; a fixture may never produce a rate | `e2e_verification_journeys.md` §2 |
| **017** | **A** — wire every real external before any new phase | delivered (V0–V6) |
| **015** | **A** — drop Firestore; DuckDB is the only store | `design_data_layer.md` (whole doc) |
| **014** | **B** — no in-app playback; `cite` deep-links to the source at its offset | `design_ui_direction.md` §2 |
| **013** | **selection-triggered** — highlight is the query; proposition-first resolution, two depths | `design_local_api_and_clients.md` §4 · `design_ui_direction.md` §6 |
| **011** | **A** — `audience_divergence` stays flagged evidence, not an axis | `design_rubric_engine.md` §6 |
| **009** | **A** — if Even-handedness precision misses, ship the pairs as evidence with no score | `design_principle_extraction.md` §8 |
| **007** | **local Gemma** for extraction; revisit only with data | `design_claim_extraction.md` §6 |
| **006** | **B** — scripted external-drive backup; now the only durability story | `design_data_layer.md` §1 |
| **005** | **A** — `nomic-embed-text-v1.5`, 768 dims, fixed in the schema | `design_data_layer.md` §4 |
| **003** | **C** — discard audio, keep the citation deep link | `design_source_acquisition.md` §5.2–5.3 |
| **002** | **extension first**, Flutter deferred, one shared `tokens.json` | `design_local_api_and_clients.md` §5 |
| **001** | **A** — Specificity as a fourth axis, computed as a rate from deterministic features | `design_rubric_engine.md` §0, §2A |

### Three that changed the shape of the build

Worth knowing even if you read nothing else above.

- **003 = C** moved the negation re-check into ingest. With the audio deleted there is no later, so **every source pays for two transcription passes, always**, and a `negation_uncertain` flag is permanent.
- **015 = A** collapsed the entire access-control surface onto the local API. There is no database server, so `design_local_api_and_clients.md` §2's four controls are load-bearing rather than defence in depth.
- **019 = C** means every corpus metric measures *agreement with the labelling model*, not accuracy — and the N1–N4 speech-act classes are exactly where a model labeller and the extractor fail together. Those figures are the least informative in the report, not the most reassuring.

---

## 5. Where the detail lives

| Question | Document |
|---|---|
| What to build next, with validation | `agent_execution_guide.md` |
| Invariants, phases, non-goals | `master_implementation_plan.md` |
| First-hand boundary, ingest, transcription, diarization | `design_source_acquisition.md` |
| Utterance → claim; the six extraction validators | `design_claim_extraction.md` |
| Even-handedness machinery | `design_principle_extraction.md` |
| Topic clustering and free-text resolution | `design_topic_model.md` |
| Axis formulas, tension types, sufficiency gates | `design_rubric_engine.md` |
| Schema, deterministic IDs, versioning | `design_data_layer.md` |
| API contract, security, `/resolve` | `design_local_api_and_clients.md` |
| Timelines, tension cards, rendering absence | `design_ui_direction.md` |
| What the system may and may not assert | `design_evidence_integrity.md` |
| Fixtures vs golden corpus; journeys | `e2e_verification_journeys.md` |
