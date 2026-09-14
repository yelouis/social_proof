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

### Issue 036 — Extraction produced zero claims. Four ways forward, and they are not exclusive.

**Blocks:** B6, and any extraction work beyond one episode. **Rewritten:** September 13, 2026, after B5 made the gold distribution readable.

## What was measured

| | |
|---|---|
| turns in E287 | **405** |
| gold claims (hand-labelled, B2) | **33 — 8.1%** |
| model claims, rubric prompt | **0** · precision 0.0%, recall 0.0% |
| model claims, rubric **stripped** ("extract claims") | **393 of 405 — 97%.** Recall **100% (33/33)**, precision **8.4%** |
| model | `gemma-2-2b-it-4bit`, MLX, zero validators |
| question-anchored turns (B1) | **11.1%** |

**The model did not fail randomly. It collapsed to a degenerate answer, twice, in opposite directions.** With the rubric it vetoed every turn citing Gate 1. With the rubric removed it called almost everything a claim.

**And the second collapse is better news than it looks.** Unconstrained, the 2B found **all 33 gold claims — 100% recall.** It is not blind to claims; it cannot *exclude*. **The missing capability is discrimination, not detection**, and that is a much better position to start from than the headline 0% suggests.

## Two facts that reframe the choice, and the second is my error

**① The task is heavily imbalanced.** Claims are **8.1%** of turns. **A model that answers "not a claim" every single time scores 91.9% accuracy.** That is a strong attractor for a small model, and it is exactly where the 2B landed.

**② The rubric is written as an exclusion manual, and it is used as the prompt verbatim.** Counting its own text: **four gates, which are four ways to say no**, four *"Fails when / Fails on"* blocks, and **8 of its 11 worked examples are "not a claim."** B4's diagnostic named the mechanism without naming the cause — *"binary collapse under negative checklists."*

**I wrote that rubric. Handing a negative checklist to a small model on a task where "no" is right 92% of the time is a setup for the collapse that was measured**, and it means the 0% recall is not yet evidence about model capacity. It may be evidence about the prompt.

---

## Option A — Run three bigger local models (item B6)

**Gemma 4 31B**, **GLM-4-32B-0414**, **Nemotron 3 Nano** — ~18 GB each at 4-bit, three different labs, same 405 turns, measured against the gold set.

**Pros**
- Directly tests whether capacity is the bottleneck, which is currently assumed and unmeasured.
- Three independent labs makes agreement meaningful rather than shared-lineage echo.
- The item is already specified and the hardware is confirmed to fit.
- Produces the evidence every other option needs — including whether the models fail the *same* way or different ways.

**Cons**
- **Runs the flawed prompt.** If all three do badly against an exclusion-shaped rubric, the natural reading is "local models can't do this," which may be wrong and is expensive to un-conclude.
- Hours of inference across three models × 405 turns, plus ~54 GB of downloads.
- Does not address the 8.1% base rate, which is a property of the task rather than the model.

---

## Option B — Two-stage filter

A cheap high-recall first pass keeps candidate turns; the rubric adjudicates only those.

**Pros**
- **Attacks the imbalance directly.** If stage 1 keeps 20% of turns at high recall, stage 2 sees a ~40% base rate instead of 8% — the degenerate always-no answer stops being cheap.
- Stage 1 can be non-neural and nearly free: discourse markers (*"I think"*, *"the reality is"*), turn length, first-person assertion.
- Composes with every other option rather than competing.
- **The measured 100% recall of the unconstrained prompt means a stage 1 exists that loses nothing.**

**Cons**
- **Stage 1's recall becomes a hard ceiling.** Anything it drops is unrecoverable, and V1's whole failure was invisible recall loss.
- Two components to tune instead of one, with the gold set split across both.
- If the rubric is the problem, this does not fix it — it just feeds a broken adjudicator fewer turns.
- **The obvious stage 1 is not actually a filter.** The unconstrained prompt has 100% recall but keeps **97% of turns** — it removes 12 of 405. A workable stage 1 must be high-recall **and** selective, and nothing measured so far is both. That component would have to be built and tuned before this option is testable.

---

## Option C — Rewrite the rubric as a positive elicitation ← **recommended first**

Same four gates as *reasoning*, but the prompt asks for what to find rather than what to reject: *"Does this turn contain a position the speaker would defend if challenged? If so, quote it and state it."* Exclusions become the residue rather than the instruction.

**Pros**
- **Cheapest thing on this list by a wide margin** — hours, no downloads, no new hardware, one episode to re-measure.
- Directly targeted at the measured mechanism. B3's own falsification is the evidence: the rubric text flipped the model from 97% claims to 0%. **The text is doing the damage.**
- V1 already learned this once — X2's position frame worked because it asked for a positive thing. This is the same lesson in a new place.
- **It de-risks Option A.** Run A against a fixed rubric and a poor result means something; run it against this one and it may not.

**Cons**
- The 2B may collapse the other way, toward 97% again — the positive framing has its own degenerate answer.
- Rewriting the rubric means **B2's gold set was labelled against the old text.** The labels should survive (the gates are the same reasoning), but that must be checked rather than assumed.
- It is a fix to my error, so treat my confidence in it accordingly — the honest test is whether recall moves, not whether the new text reads better.

---

## Option D — Finetune a local model on the gold set

LoRA on Nemotron 3 Nano (or whichever base wins A) using B2's 405 labelled turns.

**Pros**
- **Learns the 8.1% base rate from data instead of being told it in prose.** That is precisely what prompting has failed to convey, and the reason this is stronger than it first looks.
- NVIDIA published Nemotron's training data, RL environments and post-training recipes — adapting a known procedure rather than reverse-engineering one.
- Runs locally on this machine under MLX; no constraint is bent.

**Cons**
- **405 examples is small**, and 33 positives is very small. Real risk of memorising one episode's speakers and topics.
- **No held-out set exists.** Training on the only labelled episode leaves nothing honest to measure against — a second labelled episode becomes a prerequisite, which is another day of reading.
- Slowest and most complex path, and it presupposes a base model that is already close.

---

## Recommendation

**C, then A. They are one week apart in cost and the order matters.**

C is hours and attacks the mechanism that was actually measured. A is the substantial experiment, and running it against a rubric known to induce collapse risks buying an expensive wrong conclusion about local models.

**B composes with either and is worth doing if C alone does not move recall.** **D should wait for A's numbers and needs a second labelled episode before it can be honest.**

**Selecting more than one is fine — say the order.** If you want the big models running tonight regardless, say "A first" and I will spec it that way; the cost is interpretive, not fatal.

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
