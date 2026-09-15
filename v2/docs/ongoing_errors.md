# Engineering Issues & Decisions — Working Log (V2)

**What this file is:** open decisions that need you, the parameters still to be measured, and a record of decisions already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with a line reading exactly `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §1b. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 1 decision made in V2 (Issue 036 — C then A), 0 open. 3 parameters measured (034, 035, 037).**

---

## 1. OPEN — awaiting your selection

*Newest first. Nothing is open right now.*



## 1b. Decision record

| # | Decision | Now lives in |
|---|---|---|
| **036** | **C then A.** First rewrite the rubric as a positive elicitation and move every prompt into editable Markdown (item C1); then run three bigger local models (item B6). Option B ruled out by the local-only constraint; Option D deferred until A's numbers exist and a second labelled episode makes it honest. **Plus: the prompt must live in a `.md` Louis can read and edit without touching Python.** | `design_claim_rubric.md` · `agent_execution_guide.md` C1, B6 |

---

## 2. Parameters to be measured, not selected

| # | Parameter | Set during | Bias |
|---|---|---|---|
| **034** | `QUESTION_ANCHORED_SHARE = 11.13%` — question-anchoring corpus share across 23 episodes (B1) | B1 | **Measured fact.** Demonstrates that question-anchoring is a high-precision slice (< 30%) and cannot serve as the sole extraction backbone for All-In. |
| **035** | `CLAIM_TURN_RATE = 8.15%` — defensible claim density per speaking turn on reference episode E287 (B2) | B2 | **Measured fact.** Out of 405 turns, 33 carry defensible claims; 372 are excluded (Gate 1: 74.57%, Gate 2: 1.98%, Gate 3: 1.48%, Gate 4: 13.83%). |
| **037** | `EXTRACTION_IS_DETERMINISTIC = true` — identical verdicts across repeat runs of the same turns (B7) | B7 | **Measured fact.** `ModelExtractor` pins `make_sampler(temp=0.0)`; three turns of E287 run twice produced byte-identical verdicts. **Holds only while decoding stays greedy** — and the recorded `decoding.seed` is wired to nothing, so varying it changes no output. B6's self-agreement falsification must vary **temperature**, not seed. |

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
