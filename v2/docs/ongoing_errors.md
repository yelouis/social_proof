# Engineering Issues & Decisions — Working Log (V2)

**What this file is:** open decisions that need you, the parameters still to be measured, and a record of decisions already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with a line reading exactly `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §1b. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 2 decisions made in V2 (036 — C then A; 043 — re-run B6 at size), 1 open (Issue 044). 12 parameters measured (034, 035, 037, 038 superseded by 040, 039, 040, 041, 042 superseded by 044, 044).**

---

## 1. OPEN — awaiting your selection

*Newest first.*

### Issue 044 — B6 answered its question with two arms. The third never ran, and it was our fault.

**The result is the best news this project has had.** Verified independently — I recomputed every number from the artifacts:

| model | claims | precision | recall |
|---|---|---|---|
| gemma-2-2b (old baseline) | 138 | 13.04% | 54.55% |
| **gemma-4-31b** | 111 | **28.83%** | **96.97%** |
| **GLM-4-32B** | 80 | **31.25%** | 75.76% |
| majority of the two | 73 | 32.88% | 72.73% |

**Capability bought precision *and* recall — not a trade.** Gemma 4 finds 32 of your 33 hand-labelled claims, and the one it missed was rejected by our own quote guard for paraphrasing, not by the model. **Consensus, by contrast, bought +1.6 points of precision for −24 points of recall.** On this evidence agreement between models is not worth much; capability is.

**The third arm is void, and not because of Nemotron.** 401 of its 405 verdicts (99.0%) are parse failures silently recorded as gate-1 exclusions. It is a reasoning model: it thinks in prose before answering, runs out of tokens, and our harness scores "didn't finish" as "not a claim". Raising the budget to 2,500 tokens made it worse — it started counting characters one at a time to compute the `offset` field the prompt asks for, **which `extract.py` computes itself and throws the model's value away.** Removing that dead field took it from 99% unparseable to about 50% in a 4-turn probe, and produced one clean verbatim claim. So "Nemotron scores 0%" has to be retracted; it was never measured.

**Two fixes land regardless and need no decision from you** (filed as C3): delete the discarded `offset` field from the prompt, and stop recording an unparseable generation as an exclusion — it must be counted as `unparseable` and a run with a high rate must fail loudly instead of quietly reporting 0%.

---

**Option A — Re-run all three arms with the corrected prompt.**

- **Pro:** the only way to get a byte-identical three-lab comparison, which is what B6 was for and what you asked for.
- **Pro:** the prompt fix may lift Gemma and GLM too — they are spending tokens on the same discarded field.
- **Con:** ~5–6 hours, and Nemotron may still not parse reliably; a 50% rate in a 4-turn probe is not a promise.
- **Con:** spends the next cycle re-measuring a question that already has an answer.

**Option B — Fix the harness, re-run Nemotron alone, footnote the prompt difference.**

- **Pro:** ~1.5–2 hours, and gets a third lab into the table.
- **Con:** the arms no longer share a prompt, which is the one thing B6's design insisted on. A consensus table with a footnote is weaker than one without.

**Option C — Close B6 at two labs, record why the third is absent, and spend the next cycle on precision.** *(recommended)*

- **Pro:** B6's question is answered. Size matters, consensus does not, and a third small-ish lab is unlikely to reverse a −24-point recall cost.
- **Pro:** **gemma-4-31b at 97% recall is the first extractor worth building on.** It finds nearly everything; the problem is now the 79 false positives, not the misses. That is a different and more tractable problem than the one B6 was posed to solve.
- **Pro:** "a reasoning model does not fit this harness" is itself a finding worth keeping for model selection later.
- **Con:** leaves your three-lab question half-answered on the record, with Nemotron untested rather than tested-and-poor.

---

**My recommendation: C.** B6 has told us what it can. **The binding constraint is no longer which model — it is that 71% of what the best model emits is not a claim**, and no amount of cross-model voting fixes that at an acceptable recall cost. I would take the C3 fixes, close B6 honestly at two labs, and put the next cycle into precision. **If you would rather have the complete three-lab table on the record, A is the right version of that** — B's footnote would undercut the comparison it is meant to produce.

Your selection: _____

## 1b. Decision record

| # | Decision | Now lives in |
|---|---|---|
| **036** | **C then A.** First rewrite the rubric as a positive elicitation and move every prompt into editable Markdown (item C1); then run three bigger local models (item B6). Option B ruled out by the local-only constraint; Option D deferred until A's numbers exist and a second labelled episode makes it honest. **Plus: the prompt must live in a `.md` Louis can read and edit without touching Python.** | `design_claim_rubric.md` · `agent_execution_guide.md` C1, B6 |
| **043** | **A — re-run B6 with the three models originally specced.** `mlx-community/gemma-4-31b-it-4bit` (18.4 GB), `mlx-community/GLM-4-32B-0414-4bit` (18.3 GB), `mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit` (17.8 GB) — all three MLX 4-bit, all three through the existing `mlx_lm` path, 54.5 GB total onto an external SSD. The first pass ran a 2B, a 9B and a 7B vision model and reused C1's artifact as one arm, with every gate green. **The inputs are now asserted in `v2/tests/test_b6_models.py`, committed red.** | `agent_execution_guide.md` §13 · `v2/tests/test_b6_models.py` |

> **Correction to 036's premise, recorded September 14 2026 after C1's falsification.** The issue was framed — by me — as *"the rubric is an exclusion manual used as the prompt verbatim, and that is the cause of the binary collapse."* **That is false.** A full 405-turn run of the **unchanged** exclusion-manual rubric through C1's new positive template reaches **87.88% recall at 13.94% precision**, against C1's own 81.82% / 15.34% (parameter 039). **The collapse was caused by the prompt template's exclusion-first instruction**, which lived in `extract.py`'s f-string — not by the rubric text. The rubric rewrite is a second-order trade: −6 points of recall for +1.4 of precision. **Option C was still the right call** — it produced the editable prompt that fixed the problem — but for a different reason than the one on the ticket.

---

## 2. Parameters to be measured, not selected

| # | Parameter | Set during | Bias |
|---|---|---|---|
| **034** | `QUESTION_ANCHORED_SHARE = 11.13%` — question-anchoring corpus share across 23 episodes (B1) | B1 | **Measured fact.** Demonstrates that question-anchoring is a high-precision slice (< 30%) and cannot serve as the sole extraction backbone for All-In. |
| **035** | `CLAIM_TURN_RATE = 8.15%` — defensible claim density per speaking turn on reference episode E287 (B2) | B2 | **Measured fact.** Out of 405 turns, 33 carry defensible claims; 372 are excluded (Gate 1: 74.57%, Gate 2: 1.98%, Gate 3: 1.48%, Gate 4: 13.83%). |
| **037** | `EXTRACTION_IS_DETERMINISTIC = true` — identical verdicts across repeat runs of the same turns (B7) | B7 | **Measured fact.** `ModelExtractor` pins `make_sampler(temp=0.0)`; three turns of E287 run twice produced byte-identical verdicts. **Holds only while decoding stays greedy** — and the recorded `decoding.seed` is wired to nothing, so varying it changes no output. B6's self-agreement falsification must vary **temperature**, not seed. |
| **038** | `C1_CLAIM_RECOVERY = 69.70% recall, 15.03% precision` — extraction performance under the new prompt template on E287 (C1) | C1 | **Measured fact, corrected on verification.** The run emitted 176 claims (27 TP, 149 FP, 6 FN, 223 TN) for a reported **81.82% / 15.34%**. **23 of those 176 are empty** — `quote` and `claim` both blank — and 4 land on gold-claim turns, so they score as true positives. Excluding them gives **69.70% recall (23/33) and 15.03% precision (23/153)**, which are the honest figures. Gate collapse is genuinely broken either way (gate_1 405 → 67; gates 1/2/3/4 at 16.54/13.33/0.25/26.42%). **C2 fixes the instrument; re-measure after it lands.** |
| **039** | `TEMPLATE_DOMINATES_RUBRIC` — the prompt template, not the rubric text, decides whether extraction collapses (C1) | C1 | **Measured fact.** Four full 405-turn arms on E287: old rubric + old template **0% recall**; old rubric + **new** template **87.88% / 13.94%**; new rubric + new template **81.82% / 15.34%**; stripped control **100% / 8.40%**. Artifact: `v2/artifacts/extraction/c1_falsify_oldrubric_newtemplate_00251a80c868f535.json`. **Tune the template before the rubric.** The rubric is also the human labelling instruction and the verification standard, so changing it costs synchronisation with B2's gold set; the template costs nothing. |
| **040** | `C2_QUOTE_VALIDATOR = 54.55% recall, 13.04% precision` — honest extraction baseline on E287 with Quote Validation Guard (`VALIDATORS_ADDED = 1`) | C2 | **Measured fact.** The Quote Validation Guard rejected 38 claims across 405 turns (9.38% total rejection rate): 23 empty quotes (5.68%), 14 non-verbatim quotes (3.46%), 1 context leak (0.25%). 100.0% of the 138 emitted claims resolve verbatim in their own turn (0 context leaks, 0 empty quotes). Confusion matrix: 18 TP, 120 FP, 15 FN, 252 TN. Recall lost vs C1 reported is -27.27 points (81.82% -> 54.55%); recall lost vs C1 shells removed is -15.15 points (69.70% -> 54.55%). Both floors hold (> 50.0% recall, > 10.0% precision). |
| **041** | `B6_30B_CONSENSUS = 32.88% majority precision, 72.73% recall (24 TP, 49 FP on 73 claims); any-model 100.0% recall (33/33 gold claims) at 27.97% precision` — agreement across three specced 30B open-weights models (Issue 043 = A) on E287 | B6 | **Measured fact.** Evaluating `gemma-4-31b-it-4bit`, `GLM-4-32B-0414-4bit`, and `NVIDIA-Nemotron-3-Nano-30B-A3B-4bit` under byte-identical positive rubric prompt over all 405 turns. Majority consensus ($\ge 2$ models) yields 73 claims (24 TP, 49 FP) at 32.88% precision and 72.73% recall. Any-model consensus achieves **100.0% recall (33/33 gold claims recovered)** at 27.97% precision (33 TP, 85 FP). Falsification confirmed: dropping Nemotron (which emitted 0 claims) leaves 2-model consensus (GLM + Gemma) byte-for-byte identical to 3-model majority (73 claims, 24 TP, 49 FP), proving Nemotron is not contributing. Artifact: `v2/artifacts/extraction/b6_agreement_00251a80c868f535.json`. |
| **042** | `CAPABILITY_MAY_BUY_PRECISION` — larger models emitted fewer claims at higher precision in pilot (superseded by 044) | B6 | **Pilot observation.** Superseded by Parameter 044 measuring 30B-class models at scale. |
| **044** | `CAPABILITY_BUYS_PRECISION_AT_SCALE = 31.25% (GLM-4 32B) & 28.83% / 96.97% recall (Gemma-4 31B) vs 13.04% / 54.55% (Gemma-2 2B)` — model scaling effect on claim extraction on E287 | B6 | **Measured fact.** Scaling from 2B to 30B-class models on the byte-identical prompt more than doubles extraction precision: GLM-4 32B emitted 80 claims (25 TP, 55 FP) at **31.25% precision (+18.21 pts vs 2B)** and 75.76% recall. Gemma-4 31B emitted 111 claims (32 TP, 79 FP) at **28.83% precision (+15.79 pts vs 2B)** and **96.97% recall (recovering 32 of 33 gold claims)**. Its sole missed gold claim (`t0178`) was an attempted extraction rejected by the quote validator for a minor non-verbatim quote mismatch. |
| **045** | `SIZE_BUYS_BOTH = gemma-4-31b at 28.83% precision / 96.97% recall` — 30B-class vs 2B on E287 (B6) | B6 | **Measured fact.** Against gemma-2-2b's 13.04% / 54.55% under the same guard and prompt: precision **2.2x**, recall **1.8x**. GLM-4-32B: 31.25% / 75.76%. **Capability improved both at once — this was not a trade.** Gemma 4 missed one gold claim, and that one was rejected by our own quote guard for paraphrasing. |
| **046** | `CONSENSUS_COSTS_MORE_THAN_IT_BUYS` — majority of two 30B models: +1.6 precision, −24.2 recall (B6) | B6 | **Measured fact.** Best single model 31.25% precision at 75.76% recall; majority 32.88% at 72.73%; any-model 27.97% at 100%. **Cross-model voting is not where the remaining error is.** The third arm was void, but a third lab reversing a −24-point recall cost is not plausible. |
| **047** | `REASONING_MODELS_DO_NOT_FIT_THIS_HARNESS` — Nemotron 3 Nano: 401/405 generations unparseable (B6) | B6 | **Measured fact, and a harness defect not a model result.** It reasons in prose, exhausts the budget, and the parser scores "didn't finish" as a gate-1 exclusion. At 2,500 tokens it counted characters to satisfy the discarded `offset` field. **Its 0% recall is retracted; it was never measured.** C3 fixes the harness; Issue 044 decides whether it is re-run. |

---

## 3. Deliberately not built — do not re-propose

(Carried forward from V1)
- Fact-checking of any kind
- Global single trust scores
- Radar / spider charts
- N-way comparison dashboards
- Face / voice recognition of strangers
- Scraping unofficial Twitter/X APIs
- Pre-mature scaling to multiple episodes before B4 decision
