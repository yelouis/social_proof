# Engineering Issues & Decisions — Working Log (V2)

**What this file is:** open decisions that need you, the parameters still to be measured, and a record of decisions already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with a line reading exactly `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §1b. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 4 decisions made in V2 (036 — C then A; 043 — re-run B6 at size; 044 — close B6 at two labs, next cycle on precision; 045 — cross-model agreement, no hand labels), 0 open. 14 parameters measured (034, 035, 037, 038 superseded by 040, 039, 040, 041, 042 superseded by 044, 044, 045, 046, 047, 048, 049).**

---

## 1. OPEN — awaiting your selection

*Newest first. Nothing is open right now.*

## 1b. Decision record

| # | Decision | Now lives in |
|---|---|---|
| **036** | **C then A.** First rewrite the rubric as a positive elicitation and move every prompt into editable Markdown (item C1); then run three bigger local models (item B6). Option B ruled out by the local-only constraint; Option D deferred until A's numbers exist and a second labelled episode makes it honest. **Plus: the prompt must live in a `.md` Louis can read and edit without touching Python.** | `design_claim_rubric.md` · `agent_execution_guide.md` C1, B6 |
| **043** | **A — re-run B6 with the three models originally specced.** `mlx-community/gemma-4-31b-it-4bit` (18.4 GB), `mlx-community/GLM-4-32B-0414-4bit` (18.3 GB), `mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit` (17.8 GB) — all three MLX 4-bit, all three through the existing `mlx_lm` path, 54.5 GB total onto an external SSD. The first pass ran a 2B, a 9B and a 7B vision model and reused C1's artifact as one arm, with every gate green. **The inputs are now asserted in `v2/tests/test_b6_models.py`, committed red.** | `agent_execution_guide.md` §13 · `v2/tests/test_b6_models.py` |
| **044** | **C — close B6 at two labs and spend the next cycle on precision.** The Nemotron arm is not re-run: it was never measured (401/405 unparseable) and a third lab reversing a −24-point recall cost is not plausible. **C3's two harness fixes land regardless**, and the next item is **C4**, which adjudicates the 79 false positives before anything is tuned. | `agent_execution_guide.md` §13 (B6, closed), §16 (C3), §17 (C4) |
| **045** | **B — cross-model agreement instead of a hand-labelled calibration set.** No human axis labels will be produced for now. **C5 therefore does not rest on agreement**, which measures consistency rather than correctness: three mechanical proxies check Decontextualisation, Granularity and Fidelity; **perturbation gives all eight axes a known answer by construction**; agreement is kept as a diagnostic for ambiguous axis definitions, and self-agreement as the floor. **The open gap is calibration — sensitivity is proved, absolute level is not** — and a hand-labelled set remains the only thing that closes it. | `agent_execution_guide.md` §18 (C5) · `design_claim_axes.md` §6 |

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
| **048** | `FP_RATE_SCALES_WITH_TURN_LENGTH` — 1.3% at ≤20 words to 92.9% at 200+, recall flat (B6 / C4) | B6 | **Measured fact.** Among the 372 gold-exclusion turns of E287, `gemma-4-31b` false-positive rate by length: 0–20w **3/223 (1.3%)**, 20–50w 16/68, 50–100w 28/43, 100–200w 19/24, 200+w **13/14 (92.9%)**. Recall is ~100% in every band. **B2 labelled turns; the extractor finds spans** — on short turns the same question, on long turns not. **This is a unit mismatch before it is a precision problem**, and C4 adjudicates 30 of the 79 disagreements before anything is tuned. |
| **049** | `UNPARSEABLE_GENERATION_GATE = 5.0% threshold` — unparseable rate gating on extraction runs (C3) | C3 | **Measured fact.** Under C3, unparseable generations record `parse_status: "unparseable"`, are excluded from precision/recall, and runs > 5% unparseable fail loudly. Existing Nemotron artifact re-scored at 401/405 (99.01%) unparseable (flagged invalid, confusion matrix suppressed); Gemma-4-31B and GLM-4-32B re-scored at 0/405 unparseable. Template prompt hash updated 738f12858fbf -> 503a35f05563 with offset field removed. |

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
