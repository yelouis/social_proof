# Engineering Issues & Decisions — Working Log (V2)

**What this file is:** open decisions that need you, the parameters still to be measured, and a record of decisions already made.

**Rules:**
- **Open issues live in §1, newest first.** Anything needing your input is at the top of this file — you should never scroll to find it.
- Every open issue ends with `> **Verification pass, September 13 2026 — how B6 relates to these options.**
>
> **Option A is now an item.** §11 (B6) runs **Gemma 4 31B**, **GLM-4-32B-0414** and **Nemotron 3 Nano** — three ~18 GB 4-bit models from three labs — over the same 405 turns, measured against B2's gold set. **Selecting A means "run B6"**, not "design something new".
>
> **Option B stays ruled out** by the local-only constraint (guide §3 decision 4, §12).
>
> **Option C — a two-stage filter — is still genuinely open and independent of B6.** It is not superseded: a cheap high-recall first pass followed by rubric adjudication could work regardless of which base model wins, and B6 does not test it.
>
> **So the live question is narrower than it was: A, C, or both.** B6 also produces the evidence C would need — if all three models fail the same way, a filter is unlikely to rescue them; if they fail differently, a filter has something to work with.

Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- **Once selected, a decision moves out of §1.** Its consequence is written into the design doc that owns it, and it becomes one row in §4. The full option text stays in git history — this file is a queue, not an archive.
- Recommendations are marked. A recommendation is not a decision.

**Status: 0 decisions made in V2, 1 open (Issue 036).**

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
