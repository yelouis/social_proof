# Engineering Issues & Decisions — Working Log (V2)

**What this file is:** open decisions that need you, the parameters still to be measured, and a record of decisions already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §4. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 0 decisions made in V2, 1 open (Issue 036).**

---

## 1. OPEN — awaiting your selection

### Issue 036 — Extraction model capacity and pipeline architecture following B4 evaluation

- **Blocked on:** Scaling extraction to a second episode.
- **What was measured (B1 through B4 findings):**
  - **B1**: 20,666 raw utterances grouped into 5,589 conversational turns (median 23 words, mean 60.3 words). Question-anchored turns represent **11.13%** of the show, proving question-anchoring is a high-precision slice (< 30%) and cannot serve as the primary extraction backbone.
  - **B2**: Hand-labelled gold standard on All-In E287 (`00251a80c868f535`, 405 turns). Yielded exactly **33 claims (8.15%)** and **372 exclusions (91.85%)**. Gate failure rates: Gate 1 = 74.57%, Gate 2 = 1.98%, Gate 3 = 1.48%, Gate 4 = 13.83%. Calibration agreement: 11/11 (100%). Second-reader agreement: 19/20 (95.0%).
  - **B3 & B4 Extraction Measurements** (local `gemma-2-2b-it-4bit` on MLX, 0 validators):
    - **Rubric Prompt**: Processed 405/405 turns. Model claims emitted: **0**. Exclusions: **405** (100.0% under Gate 1). **Precision: 0.0%, Recall: 0.0%, F1: 0.0%**.
    - **Falsification Run (Stripped prompt, "extract claims")**: Processed 405/405 turns. Model claims emitted: **393**. Exclusions: **12**. **Recall: 100.0%** (33/33 gold claims captured), **Precision: 8.40%** (33/393), **FP: 360, F1: 15.49%**.
  - **Diagnostic finding**: The local 2B model suffers from complete binary collapse under negative checklists. When the 4 rubric gates are present in the prompt, it latches onto Gate 1 phrasing (*"narrating another's playbook"*, *"reporting what someone else said"*) as a universal catch-all justification, vetoing 100% of turns (even unambiguous host assertions). When the rubric is stripped, it swings to the opposite extreme, declaring 97.0% of turns to be claims.
  - **Conclusion in one sentence**: The written claim rubric with local 2B extraction does not work as a standalone zero-validator pipeline on multi-speaker podcast audio, achieving 0.0% recall (405/405 Gate 1 over-exclusions) on the full rubric prompt and 8.40% precision (393/405 over-extractions) when stripped, presenting the architectural decision of whether to scale local model parameters, benchmark a frontier model ceiling, or implement a two-stage filter.

#### Options

- **Option A (Recommended) — Scale local model size to Gemma-2-27B (or Gemma-3-12B/27B 4-bit) on MLX.**
  - *Pros*: Preserves the core architectural invariant of local-only inference on Apple Silicon; zero cloud API cost or data egress; tests whether multi-gate instruction-following capacity is the sole bottleneck.
  - *Cons*: Slower inference (~5–8s/turn vs 1.8s/turn); requires ~16GB unified memory for 4-bit weights.
> **Added by the verification pass, September 13, 2026 — read before selecting.**
>
> **Option B is ruled out by a standing constraint.** Louis has confirmed the model must be local and open-weights; no transcript leaves this machine. That is a property of the product, not a cost decision, and it is now recorded in `agent_execution_guide.md` §3 and §10. **The live choice is A or C.**
>
> **And Option A should start with a model that is already here.** `gemma4:latest` is **pulled in Ollama on this machine right now** — 8.0B, `Q4_K_M`, **131,072 context** — and has never been tried. B3 ran `gemma-2-2b-it-4bit`, the *smallest* model present, because it happened to be in the MLX cache. **Trying the 8B costs one command and no download; proposing a 12B or 27B download before doing so is skipping the free experiment.**
>
> The context window may also be part of the diagnosis rather than a separate issue. The rubric is ~1,400 words ≈ 2,000 tokens against the 2B's 8k window — **a large fraction of its attention budget spent on the instruction before it reads a single turn.** Gemma4's 131k removes that pressure entirely, so an 8B run separates "not enough parameters" from "not enough room to think", which the current evidence cannot.

- **Option B — Benchmark a frontier model (Claude 3.5 Sonnet or Gemini 1.5 Pro) on reference episode E287.**
  - *Pros*: Immediately establishes the empirical performance ceiling of the written rubric on conversational speech; reveals whether prompt phrasing or model capability is the limiting factor.
  - *Cons*: Introduces external cloud API dependency and cost; requires key provisioning.
- **Option C — Implement a two-stage extraction architecture (Stage 1 Recall Filter -> Stage 2 Gate Adjudication).**
  - *Pros*: Leverages the fact that the unconstrained prompt achieves 100% recall (33/33) on E287; isolates gate decisions into discrete single-gate evaluation calls that smaller models can execute without negative-checklist interference.
  - *Cons*: Adds pipeline complexity and doubles per-turn inference passes.

Your selection: _____

---

## 2. Parameters to be measured, not selected

| # | Parameter | Set during | Bias |
|---|---|---|---|
| **034** | `QUESTION_ANCHORED_SHARE = 11.13%` — question-anchoring corpus share across 23 episodes (B1) | B1 | **Measured fact.** Demonstrates that question-anchoring is a high-precision slice (< 30%) and cannot serve as the sole extraction backbone for All-In. |
| **035** | `CLAIM_TURN_RATE = 8.15%` — defensible claim density per speaking turn on reference episode E287 (B2) | B2 | **Measured fact.** Out of 405 turns, 33 carry defensible claims; 372 are excluded (Gate 1: 74.57%, Gate 2: 1.98%, Gate 3: 1.48%, Gate 4: 13.83%). |

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
