# Engineering Issues & Decisions — Working Log (V2)

**What this file is:** open decisions that need you, the parameters still to be measured, and a record of decisions already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with a line reading exactly `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §1b. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 1 decision made in V2 (Issue 036 — C then A), 0 open. 7 parameters measured (034, 035, 037, 038, 039, 040, 041).**

---

## 1. OPEN — awaiting your selection

*Newest first. Nothing is open right now.*



## 1b. Decision record

| # | Decision | Now lives in |
|---|---|---|
| **036** | **C then A.** First rewrite the rubric as a positive elicitation and move every prompt into editable Markdown (item C1); then run three bigger local models (item B6). Option B ruled out by the local-only constraint; Option D deferred until A's numbers exist and a second labelled episode makes it honest. **Plus: the prompt must live in a `.md` Louis can read and edit without touching Python.** | `design_claim_rubric.md` · `agent_execution_guide.md` C1, B6 |

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
| **041** | `CONSENSUS_PRECISION_BOOST = 75.00% majority precision vs 13.04% single model (3 TP, 1 FP across 405 turns)` — agreement across three open-weights models (Google, Zhipu, Alibaba) on E287 (B6) | B6 | **Measured fact.** Evaluating three local models (`gemma-2-2b-it-4bit`, `glm4:latest` 9B, `qwen2.5vl:7b` 8.3B) under byte-identical positive rubric prompt over all 405 turns shows majority consensus ($\ge 2$ models) boosts precision by 5.75× (+61.96 percentage points) to 75.00%. Any-model consensus lifts recall from 54.55% to 63.64% (+9.09 percentage points, recovering 21 of 33 gold claims). Unanimous false positive across all 3 labs was limited to 1 turn (`t0142`), isolating a genuine rubric boundary ambiguity on forward-looking macro debt projections. Artifact: `v2/artifacts/extraction/b6_agreement_00251a80c868f535.json`. |

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
