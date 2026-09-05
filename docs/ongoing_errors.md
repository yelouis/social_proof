# Engineering Issues & Decisions — Working Log

**What this file is:** open decisions that need you, the parameters still to be measured, and a one-line record of every decision already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §4. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 21 decisions made, 0 open.** Live work is queued in `agent_execution_guide.md` §6.

---

## 1. OPEN — awaiting your selection

*Newest first. Nothing is open right now.*

> **For the agent filing a new one:** insert it at the **top** of this section, not the bottom, and use the next free number. Include what is blocked, what you already tried, 2–3 options with honest pros *and* cons, a marked recommendation, and a final `Your selection: _____` line. Then set `blocked_on` in the guide's queue. Never fill the line in.

---

## 2. Parameters to be measured, not selected

**These are not decisions and must not be guessed.** Each is a threshold discovered by running against the golden corpus (`e2e_verification_journeys.md`). An agent that picks a number here and moves on has skipped the work. **Every one is provisional until its class clears the 5-case floor** (Issue 018 = B), and must be labelled provisional in code and in the commit body.

| # | Parameter | Set during | Bias |
|---|---|---|---|
| **004** | Speaker attribution thresholds (high / low) | Phase 1 | **Precision.** A missed utterance costs nothing; a misattributed one is the worst bug in the product. |
| **008** | `T_dedup = 0.86` — proposition semantic deduplication merge threshold (Parameter 008, Item P0); ambiguous-band adjudication does not earn its cost | Phase 2 / P0 | **Toward merging.** Over-splitting hides every contradiction, silently. Measured empirically over live corpus ($n = 1,499$ propositions): $T = 0.86$ merges genuine restatements (China open source sim = 0.8632) while keeping distinct topical claims separate (spatial computing workforce training vs 10x productivity sim = 0.8528; high-speed trains sim = 0.5050). Collapsed 1,499 propositions to 1,425 active survivors (74 merged away, 10 multi-source diff-date propositions, 2 published reversal tensions detected, 83 candidate pairs evaluated). Ambiguous-band adjudication does not earn its cost: the similarity gap between restatements (>=0.86) and distinct claims (<0.86) is clean; adding an ambiguous band introduces latency and pipeline complexity without improving precision. Provisional until 5-case floor. |
| **010** | Topic retrieval similarity + cluster-expansion policy | Phase 3 | **Precision on retrieval, generosity on expansion.** Small slices produce confident wrong scores. |
| **012** | `MIN_CLAIMS = 3`, `MIN_SOURCES = 1`, `MIN_SPAN_DAYS = 0` — sufficiency floor (Item E2, Invariant I5) | Phase 6 / E2 | **Conservative.** `insufficient_corpus` is always safe; a number on thin evidence never is. Evaluated strictly from inputs before scoring (verdict -> scores). Measured over $n = 1,501$ claims across 4 sources and 1,237-day span (Chamath 380 claims / 4 sources / 1,237d, Sacks 566 claims / 4 sources / 1,237d, Jason 209 claims / 4 sources / 1,232d, Friedberg 346 claims / 4 sources / 1,237d; all 4 clear sufficiency on the merits). Per-axis gates: Specificity requires $\ge 3$ own-assertion claims in slice; Consistency requires $\ge 2$ eligible repeat propositions; Update Integrity requires $\ge 2$ stance changes; Even-handedness requires $\ge 4$ directional conflicts with $p < 0.05$. Below floor, emits `passed: False, reason: "insufficient_corpus"` and suppresses all axis calculations. Provisional until 5-subject floor. |
| **016** | `H_max` — hedging ceiling in Specificity's checkability test | Phase 6 | **Toward generosity.** Only pure evasion should fail; too strict and the axis punishes ordinary caution. |
| **026** | `MIN_QUOTE_TOKENS = 7`, `T_ENTAIL_LOW = 0.60`, `T_ENTAIL_HIGH = 0.70` — the entailment guard (Issue 025 = C, Item N0) | X1 / N0 | **Reject boldly, quarantine the middle.** Re-measured over full corpus ($n = 1,501$ total claims, 1,491 own assertions, 10 ambiguous, 14 rejections). Shortest true claim is 7 tokens (range 7–115, median 20; 13 sub-7 token claims rejected). Lowest own-assertion similarity is 0.7005 (range 0.7005–1.0000, median 0.9085; margin to T_ENTAIL_HIGH: +0.0005). Ambiguous band `[0.60, 0.70)` quarantined exactly 10 claims (range 0.6350–0.6999). Rejections below 0.60: 1 claim rejected at 0.58; known fabrications 0.5296 and 0.5337. |
| **029** | `MIN_UTTERANCE_MEDIA_RATIO = 0.80` — source productivity coverage floor | R1 | **Conservative.** Catches truncation without rejecting ordinary podcast silence/intros/outros. Measured truncated corpus at 7.4%–7.9% (< 0.80 -> FAIL); full episodes clear > 0.90. Provisional until 5-case floor. |

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
