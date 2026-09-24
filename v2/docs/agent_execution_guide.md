# Agent Execution Guide — V2: rebuild claim extraction from the unit up — September 13, 2026

**You are an engineering agent with no memory of this project.**

**V1 is finished and is not being continued.** It ingested 23 episodes, produced 401 claims, and never found a single contradiction that survived being read. Five consecutive rewrites of the extraction format each fixed one failure and produced another. **V1's pipeline is reference material; do not extend it, do not repair it, and do not import its extraction code into V2 without a stated reason.**

**Where things stand, September 13 2026.** R0 split the repository; B1–B5 are delivered; the approach is decided (§4) and the rubric exists (`v2/docs/design_claim_rubric.md`).

**`ruff check v2/` reports 95 errors and `mypy v2/src` has never resolved a module.** R0 carried the traps forward and not the gates, so five items landed with a green test suite and no static checking at all. **Start at §3 (state detection) then §6 (G0).** This is V1's G1 repeating — there the unchecked directory was `scripts/`; here it is the entire new codebase.

**B5 is delivered and verified independently.** All 405 turns of E287 render with their claims or their exclusion gate, the four gate rates are shown, and the model id and rubric commit appear on the page. Serve it with `.venv/bin/python v2/scripts/serve_review.py`.

**Issue 036 is decided: C then A**, plus a directory requirement. **C1 (§7)** rewrites the rubric as a positive elicitation and moves every prompt into `v2/prompts/*.md` that Louis can read and edit without touching Python. **B6 (§13)** then runs three bigger local models. Option B stays ruled out by the local-only constraint; Option D — finetuning — waits for B6's numbers and needs a second labelled episode before it can be measured honestly.

**Three numbers to carry into C1, because they are what "better" is measured against.** The task is **8.1% positive** — answering "not a claim" every time scores 91.9%. The old rubric produced **0 claims, 0% recall.** The same 2B model with the rubric **stripped** produced **393 claims, 100% recall, 8.4% precision** — so it is not blind to claims, it cannot exclude. **The stripped control is the recall ceiling and the precision floor; beating one is easy and beating neither is the likely failure.**

---

## 1. What V1 established, and what it cost

Read this once. It is the reason V2 exists and it is short.

| | |
|---|---|
| ingested | 23 episodes, 20,666 utterances, 99.7–100% audio coverage |
| claims | 401 |
| propositions | 401 — **nothing merges, so nothing recurs** |
| tensions ever generated | **5, all quarantined as fabrications** |
| extraction format rewrites | **5** (W0/W2 → D1 → D6 → X2 → X4) |
| corpus across those rewrites | 3,669 → 2,174 → 1,027 → 1,517 → **401** |

**Three root causes, all confirmed against the live store. V2 must answer each of them or it will repeat V1.**

**① The extraction unit is one line of ASR.** Median utterance is **12 words / 3.3 seconds**; 49% are under 12 words. *"A couple of tickets left."* is an utterance. **A position is made across a speaking turn, not in twelve words**, so the model was asked to find a claim in a window that usually cannot hold one — and obliged by inventing.

**② Nothing was ever measured against a human-labelled set.** Every threshold, prompt and gate in V1 was tuned against the model's own output. Five gates were self-reported as met and disagreed with on independent reading; one pasted forty claim ids as evidence and **none of them existed**. **V2 needs a gold standard before it needs a pipeline.**

**③ Half the corpus is unattributable, and sponsor copy became opinion.** Attribution confidence is **45% `discard`, 29% `low`, 27% `high`** — claims are correctly gated to high/low, but nearly half the audio is unusable. And an Airwallex ad read, mis-segmented into a 278-word block, produced *"the speaker is FOR airwallets built for the future"* attributed to a host. **Ad reads, guest speech and reported speech are three different exclusions and V1 had a guard for none of them.**

---

## 2. R0 — Split the repository · **DELIVERED** (`b4e7319`, `3c58e91`)

`v1/` is reference. `v2/` is the build. The 62 traps (17–76) carried forward with numbering intact, along with the validation standard, the invariants, the deliberate non-goals, and evidence-integrity contracts. **Do not extend V1, do not repair it, and do not import its extraction code without a stated reason.**

---

## 3. State detection

```bash
#!/usr/bin/env bash          # run under bash: compgen is a bash builtin
cd "$(git rev-parse --show-toplevel)"
echo "=== HEAD ==="   && git log --oneline -1
echo "=== DIRTY? ===" && git status --porcelain | head
echo "=== GATES ==="
.venv/bin/python -m ruff  check v2/
.venv/bin/python -m mypy        v2/src v2/scripts v2/tests
.venv/bin/python -m pytest v2/tests -q
echo "=== EPISODE ARTEFACTS: transcripts, gold, extractions ==="
echo "  Transcripts: $(ls -1 v2/artifacts/transcripts/*.json 2>/dev/null | wc -l | tr -d ' ') episodes"
echo "  Gold:        $(ls -1 v2/fixtures/gold/*.json 2>/dev/null | wc -l | tr -d ' ') episodes"
echo "  Extractions: $(ls -1 v2/artifacts/extraction/*.json 2>/dev/null | wc -l | tr -d ' ') runs"
echo "=== OPEN SELECTIONS ==="
grep -c "^Your selection: _____" v2/docs/ongoing_errors.md 2>/dev/null || true
```

**Interpreting it:**

| Signal | Means |
|---|---|
| dirty tree | Someone stopped mid-item → check git status |
| `ruff` red | Code quality / import / style violation → fix before proceeding |
| `mypy` red | Type error or module resolution failure → fix before proceeding |
| `pytest` red | Regression in test suite → investigate and repair |
| 0 gold episodes | B2 gold set missing |
| open selections > 0 | Unresolved architectural decisions in `v2/docs/ongoing_errors.md` |

---

## 4. The approach — decided September 13, 2026

Louis read V1's output and made three calls. **They are not provisional and they are not to be re-litigated by an implementing agent.**

1. **Turn-level extraction**, not one line of ASR. V1's unit was a median of **12 words / 3.3 seconds**; 49% were under 12 words. *"A couple of tickets left."* was an utterance.
2. **Question-anchored where the show allows it** — the host's question gives the matter at issue in clean English and the answering turn gives the position. **How much of All-In is actually question-anchored is unknown and B1 measures it.** If it is a minority, question-anchoring is a high-precision slice rather than the main path.
3. **A written rubric** is passed to the local model with the transcript, and **the same text is the human labelling instruction.** **Issue 036 added: every prompt lives in `v2/prompts/*.md`, readable and editable without touching Python** — code substitutes placeholders and does nothing else. A prompt assembled in an f-string is a prompt only an engineer can tune. It is `v2/docs/design_claim_rubric.md`. Read it before B1; it is the definition of the thing this whole pipeline exists to produce.

4. **The model is local and open-weights. Not negotiable, and not a default to revisit when something is hard.** No hosted API, no frontier model, no transcript leaving this machine. Social Proof reads what named people said; that it never leaves the laptop is a property of the product, not a cost saving.

**Measured on this machine, September 13 2026 — Mac Studio, M4 Max, 64 GB, `iogpu.wired_limit_mb = 0` (default ≈ 48 GB to the GPU), 58 GB free disk of 460 GB. The binding constraint is disk, not memory.**

**What is already installed:**

| runtime | status | model | size / context |
|---|---|---|---|
| **Ollama** `/opt/homebrew/bin/ollama` | installed | **`gemma4:latest` — already pulled** | 8.0B, `Q4_K_M`, **131,072 ctx** |
| **MLX** `mlx_lm` 0.31.3 | installed | `gemma-2-2b-it-4bit` in HF cache | 2B, 4-bit, 8k ctx |

**B3 used the 2B.** That is the smallest model on the machine, chosen because it happened to be cached, and it produced 0% precision and 0% recall. **An 8B with a 131k context was sitting unused the whole time.** Before concluding anything about local capacity, **try `gemma4:latest` — it costs one command and no download.**

Gemma4's context matters too: the rubric is ~1,400 words, so the rubric plus a turn plus its preceding turn fits many times over. **Do not build chunking machinery for a context problem you do not have** — the 2B's 8k window, most of it consumed by the rubric, is a plausible contributor to the collapse B4 measured.

**GLM and Qwen are equally acceptable if they measure better.** The constraint is local and open-weights, not a family.

**The biggest of each family that fits is worked out in §13 (B6).** Short version: **Gemma 4 31B** and **GLM-4-32B-0414** at 4-bit, ~18 GB each. **GLM-4.5-Air does not fit** (66.7 GB at Q4_K_M) and **Inkling does not fit at any size** — 975B/41B, Inkling-Small 276B ≈ 138 GB in 4-bit — and its fine-tuning path is Thinking Machines' hosted Tinker platform, which decision 4 rules out.

**Record the model identity in every artefact** — model id, quantisation, runtime, and the rubric's commit hash. V1 ran five prompt versions and could not say which produced which corpus without reading commit history.

**Validation is one All-In episode, labelled by hand, end to end.** Not a sample — **recall is the half V1 could never see**, and a sample measures only precision.

**What is deliberately NOT decided:** whether a claim-detection library earns a place. TARGER, MARGOT and Canary are research artefacts trained on written argumentative prose, not disfluent multi-speaker ASR; ClaimBuster has a live API but scores *check-worthiness for fact-checking*, which is a different question from *did this speaker commit to a position*. **Borrow the claim/premise taxonomy if it helps; do not add a dependency without measuring it against B2's gold set first.**

---

## 5. Queue

| Order | ID | Item | Blocked | Why here |
|---|---|---|---|---|
| 1 | **G0** | V2 has no gates, and five items landed without them | none | **DELIVERED**. Wired §3 state detection into guide, clean ruff & mypy (17 files), pytest 35 passed. |
| 2 | **B7** | Make the review page report what actually ran | none | **DELIVERED** (`bd5ecbf`, `3f0b8cc`). Provenance read off the extractor that ran, `rubric_commit` derived from git (`9882bc3`), denominators unified, stale-server footer, backfilled artifacts marked. **Verified independently by a real model load and a real single-turn run.** Closed against `v2/tests/test_b7_provenance.py`, committed red: the suite went `39 passed, 6 xfailed` → `45 passed`. |
| 3 | **C1** | Turn the rubric positive; move every prompt into editable Markdown (**Issue 036 = C**) | G0, B7 | **DELIVERED** (`b37003e`, `a58d573`). Collapse broken: recall 0% → 81.8%, precision 8.4% → 15.3%. Job 1's byte-identical move verified across all 405 prompts. **The falsification fired: Issue 036's diagnosis was wrong** — the old rubric text through the new template reaches 87.9% recall, so the template caused the collapse, not the rubric. |
| 4 | **C2** | A claim with nothing in it is not a claim | C1 | **DELIVERED**. Quote Validation Guard added (`VALIDATORS_ADDED = 1`). 38 claims rejected (23 empty, 14 non-verbatim, 1 context leak; 9.38% rate). 100% of 138 emitted claims resolve verbatim in target turn. Honest recall 54.55% (-27.27 pts vs reported C1), precision 13.04%. Falsification confirmed. Unblocks B6. |
| 5 | **B6** | Three local models on the same episode, and what agreement is worth (**036 = A**, **043 = A**, **044 = C**) | C1, C2 | **CLOSED at two labs** (`1c95cbd`). `gemma-4-31b` **28.83% precision / 96.97% recall**, `GLM-4-32B` **31.25% / 75.76%**, against gemma-2-2b's 13.04% / 54.55%. **Capability bought precision and recall; consensus bought +1.6 points of precision for −24 of recall.** Nemotron never ran — 99% unparseable — and is not re-run. |
| 6 | **C3** | A generation we could not read is not a verdict | none | **DELIVERED** (`176dc0f`). Verified by re-scoring all three B6 arms myself: Nemotron 401/405 unparseable, `invalid`, confusion matrix suppressed; gemma-4 and GLM-4 at 0 with metrics preserved. `offset` gone from the prompt, still computed in code. |
| 7 | **C4** | Score every candidate on the eight axes, and report the episode | none | **DELIVERED, `(c)` honestly failed** (`7fe5c0f`). 111 candidates scored by GLM-4-32B, extractor and scorer recorded distinctly, both panels separate, no composite. **Three axes came back with zero variance and the commit says so** — which is what the item asked for. |
| 8 | **C5** | Validate the scorer without human labels (**Issue 045 = B**) | C4 | **DELIVERED** (`5763ab9` red → `79678f5`). Floor holds: self-agreement 86.7% above cross-model 80.0%. Tier 3 names contestability the most ambiguous axis at 73.3%. **Tier 2 passed every axis — and that is the finding, because it was not enough.** |
| 9 | **C6** | Four of the eight axes are not being read | none | **DELIVERED in part** (`df9f92f`). Contamination genuinely fixed on 7 of 8 axes — typing 51.4%→2.9%, propositionality 45.7%→2.9%, target 40%→0%. Granularity now scores 1 on all three natural compounds. **Step 4 is the best output:** Target and Propositionality discriminate 25/6/9 and 7/15/18 on rejected turns, so their 0/0/111 was survivor bias, not a broken axis. |
| 10 | **C7** | The fix was demonstrated but never applied, and fidelity regressed | none | **DELIVERED in part** (`6460d21`). 111 re-scored (3,969s); granularity `0/0/111` → **`0/3/108`**. One metric named and gated, with **fidelity 31.4% printed as FAILED**. **And the diagnosis redirects the fix:** `fidelity_01` alone causes 7 of 11 off-target drops because the perturbation swaps in an unrelated topic — the instrument is at fault, not the scorer. |
| 11 | **C8** | Three residues, and a report that answers a narrower question | none | **DELIVERED** (`a67dd8e`). All three clauses verified: fidelity **5/5 at 0.0% off-target**, funnel sums to 405, before/after table matches to the digit (69→29) with **all nine zeros adjudicated one by one** — six C7-right, one C4-right, two borderline. `t0072` resolved by naming it a scorer defect rather than editing the score. |
| 12 | **C9** | The constraint I wrote and did not apply, and the axis nobody adjudicated | none | **DELIVERED** (`d148d6d`, `e1a1b73`). Contestability: 13 / 7 / 3. Real-derived fidelity scored both sides by the calibrated scorer — **1 of 2 valid pairs**, `t0127` missed, `t0189` caught, `t0142` invalid (its original already fails). Fixture SHA recorded in the artifact and matching disk; instrument named in every column. |
| 13 | **C10** | Everything we know is one episode | C9 | **NEXT.** **Step 0, committed separately first:** the report generator marks fidelity `PASSED` at 3/5 because its status column ignores sensitivity, and counts invalid pairs as misses — fix both before E165 is printed. Then **E165 (`39b1ef6934b6da6b`)**, byte-identical pipeline, no gold set: **stability, not accuracy.** |
| 14 | **B1** | Turns, and how much of this show is question-anchored | none | DELIVERED. V1's unit was 12 words. Measured 11.13% question-anchored share. |
| 15 | **B2** | Label one episode by hand | B1 | DELIVERED. Hand-labelled 405 turns of E287; 33 claims, 372 exclusions across all 4 gates. |
| 16 | **B3** | Extract against the rubric | B2 | DELIVERED. Evaluated rubric prompt and stripped falsification prompt across all 405 turns. |
| 17 | **B4** | Measure, and decide whether to go on | B3 | DELIVERED. Precision and recall reported; conclusion recorded in one sentence; Issue 036 filed in v2/docs/ongoing_errors.md. |
| 18 | **B5** | A local page showing what was extracted, and what was not | B1 | DELIVERED. Rendered all 405 turns of E287 with side-by-side gold/model verdicts, gate distributions, and 33 disagreements. |

**IDs are labels, not sequence numbers — follow the Order column.**

**Do not reorder these and do not start two at once.** V1's worst outcomes came from items that were individually correct and sequenced wrong — a publishing item run before the thing it published was real, a threshold tuned over claims that were fabricated.

---

## 6. G0 — V2 has no gates, and five items landed without them · **DELIVERED**

**Do this before B6.** A red gate outranks the queue (§25), and right now there is no gate at all to be red.

**User impact:** none directly. This is the item that makes every later "delivered" mean something.

**Contract:** V1 guide §2's state-detection block — the thing R0 did not carry across.

### Gap

**`v2/` has never been linted or type-checked.** Measured September 13, 2026:

```
ruff check v2/   → 95 errors
mypy v2/src      → cannot resolve modules; type checking never ran
pytest v2/tests  → 35 passed
```

**R0 carried the traps, the validation standard, the invariants, the non-goals and the evidence-integrity contracts. It did not carry the gates** — and nothing in the V2 guide mentions `ruff`, `mypy` or `pytest`, so five items (B1–B5) landed with a green test suite and no static checking whatsoever.

**This is V1's G1 repeating exactly.** There, `scripts/` sat outside the gate command and accumulated 17 mypy errors, four of which were integrity calls that could not execute. **Here the excluded directory is the entire new codebase.**

The 95 are mostly mechanical — 33 `UP006` (`typing.List` → `list`), 17 `F401` unused imports, 12 `FURB167`, 9 `UP035`, 4 `I001` import ordering. **But 4 are `F841`, unused local variables, and those are worth reading rather than auto-fixing**: an assigned-and-never-used variable is sometimes a result someone forgot to check.

The mypy failure is a configuration problem, not a code problem:

```
v2/src/turns.py: Source file found twice under different module names:
                 "src.turns" and "v2.src.turns"
```

**mypy has never type-checked a line of V2.**

### Implementation

**Step 1 — Add the state-detection block to the guide, as §3, before fixing anything.** Copy V1's shape: `ruff`, `mypy`, `pytest`, and a line reporting which episode artefacts exist. **The block is the deliverable; the fixes are a consequence of having it.**

> **Verify:** run the block and paste its output. **It must be red.** A state-detection block first seen green proves nothing about whether it would catch anything.

**Step 2 — Fix the mypy configuration so it actually runs.** `__init__.py` placement, `--explicit-package-bases`, or `MYPYPATH` — whichever is least surprising. The `v2/src` and `src` double-naming comes from running mypy from the repository root against a nested package.

> **Verify:** `mypy v2/src v2/scripts v2/tests` reports a **file count** and either errors or success. **A run that resolves nothing is not a passing run** — V1 recorded `mypy scripts/` as passing for weeks while it was silently checking zero files in one configuration and 17 errors in another.

**Step 3 — Fix the 95, reading the `F841`s rather than auto-fixing them.** `ruff --fix` handles most. **For each of the four unused variables, say in the commit body what it was assigned from and why discarding it is correct.**

> **Verify:** `ruff check v2/` clean, and the four `F841` resolutions explained. **If any turns out to be a dropped result, that is a bug found by this item** and should be called out rather than quietly deleted.

**Step 4 — Wire the block into the guide's §3 so the next agent runs it first**, and add a standing constraint that a new directory is added to the gate command in the same commit that creates it.

> **Verify:** the constraint names the failure it prevents — V1's `scripts/`, V2's whole tree — so a reader understands it is a scar, not a style preference.

### Validation

- **(c)** — **`ruff check v2/` and `mypy v2/src v2/scripts v2/tests` both pass, having first been shown red with their output pasted**, and the state-detection block in the guide runs both. *The red-first half is the assertion: a gate added and immediately green is indistinguishable from a gate that checks nothing, which is exactly how `mypy scripts/` passed in V1 while resolving no files.*
- `pytest v2/tests` still reports 35 passed — **no test weakened or deleted to reach green.**
- The four `F841`s are explained individually.

> **Correction, recorded on verification.** The commit body states that none of the four `F841` variables were "dropped results or masked bugs". Three of the four are correctly assessed. The fourth — `total_model_exclusions` in `review.py` — **was the correct denominator for the model gate percentages, computed and never applied**; removing it left the model column on `/405` and the gold column on `/372`. It was evidence of an unfinished consistency, not dead code. **B7 (§14) owns the fix.** Everything else in G0 verified independently: ruff 95 → 0 and the mypy module collision were both reproduced from `f0ba620` in a scratch worktree before the green was accepted, and the rendered review page is byte-identical (935,336 bytes) before and after.

**Falsify.** Re-introduce one unused import and one `typing.List`; the block must go red naming both. Revert; record both.

**Blast radius.** `v2/docs/agent_execution_guide.md` §3 and §25, `v2/src/*`, `v2/scripts/*`, `v2/tests/*`. **No behaviour changes** — if a fix alters behaviour, it is not a lint fix and belongs in its own commit.

---
## 7. C1 — Turn the rubric positive, and move every prompt into editable Markdown · *Issue 036 = C* · **DELIVERED** (`b37003e`, `a58d573`)

**The collapse is broken and the `(c)` holds** — but the falsification fired, and **Issue 036's diagnosis was wrong.**

**Job 1 verified independently.** Prompts moved to `v2/prompts/extract_claim.md` and `extract_falsify.md`; code calls `load_prompt_template` and five `.replace()` calls, no conditional assembly. **I rebuilt all 405 prompts of both types under the pre-move and post-move code and diffed them: zero differences.** A genuine no-op, which is what makes job 2's measurement attributable.

**Job 2's run is real**: 841s over 405 turns, `provenance_source: "recorded"`, `prompt_version: extract_claim:738f12858fbf`. Metrics on disk match the commit body exactly.

### What the four arms actually say

Every arm below is a full 405-turn run with a committed artifact. **The third row is mine** — the committed falsification measured only the 33 gold-claim turns, where precision is unmeasurable by construction, and reported recall alone.

| arm | claims | recall | precision | F1 |
|---|---|---|---|---|
| old rubric + old template (B3) | 0 | 0.0% | — | 0.0% |
| stripped control (B3) | 393 | 100% | 8.40% | 15.49% |
| **old rubric + NEW template** (`c1_falsify_oldrubric_newtemplate_…json`) | **208** | **87.88%** | **13.94%** | **24.07%** |
| new rubric + new template (C1) | 176 | 81.82% | 15.34% | 25.84% |

**The rubric was not the cause.** With its exclusion-manual text completely unchanged, the new template reaches 87.88% recall. **The collapse was caused by the prompt template's exclusion-first instruction** — *"Apply the four gates in order… if ANY gate fails, output an exclusion"* — which handed the model four reasons to say no before asking what to find. That instruction lived in `extract.py`'s f-string, which job 1 moved byte-identically and job 2 rewrote.

The rubric rewrite is a real but second-order effect: **−6 points of recall for +1.4 points of precision, +1.8 F1.** Worth keeping, not worth the diagnosis.

**This corrects Issue 036's framing, which was mine.** "The rubric is an exclusion manual used as the prompt verbatim, and that is the cause of the binary collapse" is **false**. The rubric text was a passenger. B7's `rubric_content_hash` is what separates the two arms — same template hash, different rubric hash — on its first real use.

**A competing explanation, tested and rejected.** `parse_model_verdict` falls back to `exclusion`/`gate_1` on unparseable output, which is exactly B3's signature, and job 2 also raised `max_tokens` 150 → 250. If B3's collapse had been truncation, the rubric and template would both be exonerated. It was not: only **2 of 405** B3 verdicts were malformed-JSON fallbacks. The exclusions were genuine.

### What survived, and what B2 is still worth

**The four gate definitions are byte-identical across the rewrite** — the diff touches §1's framing, one bold marker, four added positive examples and one removed negative. So B2's 405 labels remain valid by construction, which is stronger than the 10-sample check the item was asked for. Worked examples are **8 positive, 6 negative**, positives leading.

**One thing was lost and is worth watching.** §1 previously read *"When a case is genuinely ambiguous after applying the four gates, **exclude it**"*. That tie-break is gone. With 149 false positives against 33 gold claims, it may be the cheapest precision available.

**Residue carried to C2 (§15)**: 23 emitted claims are empty, 5 quotes exist nowhere in the episode, and the item's test pins 13 exact numbers.

---

## 8. B1 — Turns, and how much of this show is question-anchored · **DELIVERED**

**Blocked on R0.** DELIVERED. Unblocks B2.

**User impact:** the transcript becomes readable by a person, which is the precondition for labelling it.

**Contract:** `v2/docs/design_claim_rubric.md` gate 4 · V1's `utterances` table (read-only).

**Gap.** V1's extraction unit is one line of ASR — **median 12 words, 3.3 seconds, 49% under 12 words.** *"A couple of tickets left."* is an utterance. A position is made across a speaking turn, and asking a model to find one in twelve words is what produced five rewrites of the extraction format.

**Turns are also a measurement, and that is half of why this item exists.** Nobody knows how much of All-In is question-anchored. It is four co-hosts talking over each other as often as it is an interview, and **if interrogative-preceded turns are 20% of the show, question-anchoring is a high-precision slice rather than the main path** — which changes B3's design. Measure before designing around it.

### Implementation

**Step 1 — Build turns from V1's utterances, read-only.** Group consecutive utterances by the same `subject_id` into one turn. Break a turn on: a speaker change, a gap over ~2s, or a hard cap (~400 words) so one mis-segmented block cannot become the whole episode.

> **Verify:** print the turn-length distribution against the utterance distribution. **Median turn should be several times median utterance (12 words).** If it is not, the grouping is not grouping — most likely `subject_id` is alternating on noise.

**Step 2 — Strip what is not the show.** Ad reads, cold opens, and the outro. Sponsor segments are the highest-value exclusion: V1 turned an Airwallex ad into *"the speaker is FOR airwallets built for the future"* attributed to a host. Detect by CTA phrasing (`dot com slash`, `promo code`, `our sponsor`) plus the fact that ad reads are contiguous blocks.

> **Verify:** list every stripped span with its timestamps and **read them.** Report what fraction of the episode was stripped. **A sponsor block that survives is a claim generator; a real segment that gets stripped is silent data loss** — both directions matter and only reading catches either.

**Step 3 — Classify each turn as question-anchored or not.** A turn is question-anchored when the immediately preceding turn from a *different* speaker ends in an interrogative.

> **Verify (this is the number the design depends on):** report the percentage, per episode and overall. **State it plainly in the commit body.** If it is under ~30%, say so and flag that B3 cannot rely on question-anchoring as its main path.

**Step 4 — Emit a readable transcript artefact.** One file per episode: turn id, speaker, timestamp, text, `is_question_anchored`, `stripped` reason if any. **This file is what a human reads in B2.**

> **Verify:** open it and read five minutes of it. **If it does not read like a conversation, B2 cannot be done from it** and no amount of downstream cleverness recovers that.

### Validation

- **(c)** — **on one episode, a person reads the emitted transcript end to end and confirms it reads as a conversation**: speakers attributed correctly through at least three exchanges, no ad copy in the retained text, no turn ending mid-sentence. *No metric substitutes for this. The artefact's entire purpose is to be read, and V1 never produced one that was.*
- Turn-length distribution reported against utterance distribution.
- Question-anchored percentage reported.
- Stripped spans listed with timestamps and total duration.
- **Nothing is written to V1's database.** Assert its file hash is unchanged.

**Falsify.** Disable the speaker-change break; turns must collapse into a handful of giant blocks. Disable ad stripping; the Airwallex block must reappear in the retained text. Record both.

**Blast radius.** `v2/` only. V1 is read-only.

---

## 9. B2 — Label one episode by hand · **DELIVERED**

**Blocked on B1.** DELIVERED. Unblocks B3.

**User impact:** every threshold, prompt and gate after this becomes measurable instead of self-reported.

**Contract:** `v2/docs/design_claim_rubric.md` in full.

**Gap.** V1 set six parameters and ran five format rewrites without a single human-labelled example. Five gates were self-reported as met and disagreed with on independent reading; one pasted forty claim ids as evidence and **none of them existed.** **There was never anything to be wrong against.**

### Implementation

**Step 1 — Pick one episode and say why.** A regular four-host episode, not a guest interview — guests are excluded by gate 1 and a guest-heavy episode measures the wrong thing.

**Step 2 — Read the whole episode's turns and mark every claim.** Not a sample. **Every turn**, start to finish, applying the rubric's four gates in order.

> **Verify:** the count of turns examined equals the count of turns in the episode. **Recall is the whole point** — a sample tells you whether what you found is good and nothing about what you missed, and missing is V1's failure mode.

**Step 3 — For each claim record the rubric's fields**; for each **exclusion** record only the gate that caught it. Exclusions are data, not waste — their distribution is the health signal in rubric §8.

> **Verify:** report the four gate-failure rates. **If any is zero, re-read.** A gate that never fires is either unnecessary or not being applied, and rubric §8 says which is more likely.

**Step 4 — Have the rubric's worked examples checked against your own judgements.** If you disagree with rubric §7's calibration table, **stop and raise it with Louis** rather than proceeding — the rubric is wrong, or your reading is, and both are worth more than a labelled set built on a disagreement.

> **Verify:** state explicitly in the commit body that you applied §7 and agreed with it, or which row you disagreed with.

**Step 5 — Commit as `v2/fixtures/gold/<episode>.json`,** with the rubric's version or commit hash recorded in it.

> **Verify:** the file records which rubric produced it. **A gold set whose definition has drifted is worse than none** because it looks authoritative.

### Validation

- **(c)** — **every turn in the episode has a verdict** (claim with fields, or exclusion with a gate), the count matches B1's turn count exactly, and **the four gate-failure rates are all non-zero.** *An incomplete labelling measures precision only, which is the half V1 already had.*
- A second reader — Louis, or a fresh agent given only the rubric — labels **20 turns drawn at random** and agreement is reported. **Do not target a number; report it.** Low agreement means the rubric is ambiguous and that is a finding about the rubric.
- The claim count is stated plainly. **If one episode yields very few claims, say so** — that is a real result about the show and it changes what the product can be.

**Falsify.** Label 20 turns, set them aside, re-label them a day later without looking, and report self-agreement. **If you disagree with yourself, the rubric is underspecified** and no model will do better.

**Blast radius.** `v2/fixtures/gold/`, possibly `v2/docs/design_claim_rubric.md` if step 4 finds a defect.

---

## 10. B3 — Extract against the rubric · **DELIVERED**

**Blocked on B2.** Running extraction before the gold set exists is how V1 tuned six parameters against its own output.

**User impact:** the first V2 claims.

**Contract:** `v2/docs/design_claim_rubric.md` · B1's turn artefact · B2's gold set.

### Implementation

**Step 1 — Build the prompt from the rubric file, not from a paraphrase of it.** Load `design_claim_rubric.md` and interpolate it. **The prompt must not restate the rubric in its own words** — the whole point is that the model, the labeller and the verifier share one text.

> **Verify:** assert in a test that the rubric file's §2 and §3 appear verbatim in the prompt. **If they are paraphrased, they will drift**, and V1's five rewrites were five paraphrases of a rule nobody changed.

**Step 2 — Feed one turn at a time, with the preceding turn as context.** The preceding turn is needed for gate 1 (is this answering a question, or rejecting a position just voiced?) and gate 4 (what does *it* refer to?). **Context is read, never quoted from.**

> **Verify:** assert no emitted quote resolves to the context turn rather than the target turn. This is a cheap check and it catches a whole class of misattribution.

**Step 3 — Require the model to emit exclusions, not silence.** For every turn: either claims, or an exclusion with the gate. **A turn that returns nothing is a bug**, because it is indistinguishable from a turn that was never processed. V1's decline branch fired 3 times in 401 claims and nobody could tell whether it was working.

> **Verify:** turns processed equals turns in the episode, and every turn has a verdict.

**Step 4 — Do not add validators yet.** V1 had seven, and they were repairs for a prompt that was asking the wrong question. **Run the rubric alone first and measure it.** Add a guard only when B4 shows a specific failure the prompt cannot fix, and say which.

> **Verify:** the commit body states how many validators were added: the expected answer is zero.

### Validation

- **(c)** — **on B2's episode, precision and recall against the gold set are both reported**, with the confusion counts and every disagreement listed by turn id. *Both numbers, or neither means anything: V1 could always find claims and never knew what it missed.*
- Gate-failure distribution reported and compared to B2's human distribution. **A large divergence is the finding** — it says the model is applying a different rubric than the text it was given.
- Every quote resolves verbatim to its turn.

**Falsify.** Strip the rubric from the prompt, leaving only *"extract claims"*, and re-run the same episode. Report both precision and recall. **If the rubric adds nothing, that is the finding** and it should be reported rather than buried.

**Blast radius.** `v2/` only.

---

## 11. B4 — Measure, and decide whether to go on · **DELIVERED**

**Blocked on B3.**

**User impact:** an honest answer about whether V2's approach works, before any of it is scaled.

**Gap.** V1 never had this step. It scaled to 23 episodes and 20,666 utterances before discovering that its claims were not claims.

### Implementation

1. Report **precision and recall** against B2's gold set, with every disagreement listed by turn id.
2. **Read every claim B3 emitted that the gold set does not contain**, and every gold claim B3 missed. Say which failures share a cause.
3. State a conclusion **in a sentence**: the approach works and should be scaled, it works on a slice — say which — or it does not work and here is the evidence.

> **Verify:** the conclusion names the next decision, not the next task. **If recall is 40%, "improve the prompt" is not a conclusion** — whether 40% is enough for the product is a question for Louis, and it belongs in `v2/docs/ongoing_errors.md` §1 with options.

### Validation

- **(c)** — **precision and recall both reported over B2's full episode, with every disagreement listed by turn id and read.** *A single aggregate is what let V1 run for weeks on a corpus of invented claims.*
- **Do not scale to a second episode inside this item.** Whether to scale is B4's output, not its method.

**Falsify.** Score 20 of B3's outputs blind — source hidden, order shuffled — and compare to your attributed verdicts. Report the agreement rate; a poor one means the measurement is your reading rather than the model.

> **Known limitation, recorded during G0's verification.** `run_blind_scoring` computed `matches_gate` and never read it, so **the agreement figure is verdict-level only and was never gate-level.** G0 removed the dead variable correctly. B4's conclusion does not depend on it — the rubric run assigned 100% of its exclusions to `gate_1`, so gate agreement could only have reinforced the collapse finding — but **no number in this item may be described as gate agreement.**

**Blast radius.** `v2/docs/ongoing_errors.md`, `v2/docs/agent_execution_guide.md`.

---
## 12. B5 — A local page showing what was extracted, and what was not · **DELIVERED**

**Blocked on B1 only.** DELIVERED. Unblocks B6.

**User impact:** Louis can see what the pipeline did to the most recent episode, turn by turn, without running a query.

**Contract:** `v2/docs/design_claim_rubric.md` · B1's turn artefact · V1's `v1/scripts/serve_site.py` as a shape to copy, not code to import.

### The one design decision that matters

**Show the turns that produced nothing, and why.** V1's site listed claims and nothing else, so you could see precision by eye and never recall — which is exactly the half that was broken for the whole of V1. **A page that only shows claims cannot tell you what the pipeline threw away.**

Every turn appears. A turn either carries its claims or carries the gate that excluded it. **The gate distribution should be visible at a glance** — that is the health signal rubric §8 describes, and it is worth more than the claims themselves while the rubric is still being tuned.

### Implementation

**Step 1 — Read artefacts from disk. No database.** V2 has no store and must not get one before the approach is proven; a schema now encodes assumptions B4 might overturn. Read B1's turn file, B2's gold file if present, B3's claim file if present.

> **Verify:** the page renders with **only** B1's output present — turns, speakers, timestamps, ad-stripped spans marked — and says plainly that no claims have been extracted yet. **If it errors or renders blank without B3, it cannot be used during B2**, which is most of its value.

**Step 2 — One page per episode, turns in document order.** For each turn: speaker, timestamp, verbatim text, and then either its claims (quote, claim, type) or its exclusion gate. **Do not paginate or collapse** — reading the episode end to end is the point.

> **Verify:** the turn count on the page equals B1's turn count for that episode. **A viewer that silently drops turns is the same defect as a pipeline that does**, and it would hide it.

**Step 3 — Put the gate distribution at the top.** Four counts and four percentages, from the page's own data. Link each to the turns it caught.

> **Verify:** the percentages match what B3 reported in its commit body. **If they disagree, one of the two is computing from a different set** and that is a finding, not a rounding difference.

**Step 4 — On B2's labelled episode, show model and human side by side.** Three states per turn: both agree it is a claim, both agree it is not, **they disagree** — and make disagreement visually obvious.

> **Verify:** the disagreement count matches B4's. **This view is how B4's "read every disagreement" step is actually performed**; if it does not agree with B4's numbers, B4 was reading something else.

**Step 5 — Show the model identity on every page.** Model id, quantisation, runtime, prompt version, and the rubric commit hash that produced these claims.

> **Verify:** change the model, re-run, and confirm the page says so. **An output you cannot attribute to a model and a rubric version is not evidence** — V1 spent five rewrites unable to say which prompt produced which corpus without reading commit history.

**Step 6 — Serve on loopback, read-only, one command.**

```
.venv/bin/python v2/scripts/serve_review.py
```

Print the URL on startup. Same posture as V1: `127.0.0.1` only, no writes, no network calls from the page.

> **Verify:** start it, open it, **read one full episode in it.** Say in the commit body that you did and what you noticed — that reading is the item's actual deliverable.

### Validation

- **(c)** — **every turn in the most recent episode appears on the page**, count matching B1's, each carrying either its claims or its exclusion gate; and the four gate percentages shown match B3's reported figures. *A viewer that shows only claims satisfies nothing here — it is the exclusions that make recall visible, and recall is what V1 could never see.*
- The page renders correctly with B1's output alone, with B1+B2, and with all three.
- Model id, quantisation, runtime, prompt version and rubric hash appear on every page.
- **No network requests from the served page.** Assert it; a local tool that phones out is not a local tool.
- Serves from `127.0.0.1` and writes nothing.

**Falsify.** Point it at a turn file with three turns removed; the count check must fail and name the discrepancy. Restore; record both.

**Blast radius.** `v2/scripts/serve_review.py`, `v2/templates/` or equivalent. **Reads artefacts, writes nothing.**

---
## 13. B6 — Three local models on the same episode, and what agreement is worth · **CLOSED at two labs** (`1c95cbd`) · *Issue 044 = C*

**Issue 043 = A was executed properly.** The three named models ran, the inputs held, and `test_b6_models.py` passes with only its `xfail` marker deleted — `git diff` on that file shows nothing else. Wall-clocks are physically coherent: **8,184s and 7,585s for the dense 31B/32B (~20s per turn), 1,525s for Nemotron's 3B-active MoE.**

### The finding, recomputed independently from the artifacts

| model | claims | TP | precision | recall |
|---|---|---|---|---|
| gemma-2-2b (parameter 040 baseline) | 138 | 18 | 13.04% | 54.55% |
| **`gemma-4-31b-it-4bit`** | 111 | 32 | **28.83%** | **96.97%** |
| **`GLM-4-32B-0414-4bit`** | 80 | 25 | **31.25%** | 75.76% |
| majority ≥2/3 | 73 | 24 | 32.88% | 72.73% |
| any ≥1/3 | 118 | 33 | 27.97% | 100% |

**Capability bought precision *and* recall — not a trade.** That settles parameter 042's hypothesis in the strongest form available. **Consensus bought +1.6 points of precision for −24 points of recall**, so on this evidence agreement between models is worth little and capability is worth a lot. Gemma 4's single missed gold claim, `t0178`, was rejected by C2's own quote guard for paraphrasing — **the model found all 33.**

Self-agreement was measured where it can disagree: GLM-4-32B at temperature 0.7 over the 33 gold-claim turns gives **84.85% overall and 81.48% across the 27 claim-bearing turns** — two figures close together, which is what a real stability measurement looks like.

### The third arm is void, and the cause is ours

**401 of Nemotron's 405 verdicts (99.0%) are parse failures silently recorded as gate-1 exclusions.** Gemma and GLM had **0**. It is a reasoning model: it thinks in prose, exhausts the token budget, and `parse_model_verdict` scores "didn't finish" as "not a claim". Raising the budget to 2,500 tokens made it worse — it began counting characters one at a time to compute the `offset` field, **which `extract.py` computes itself at line 248 and discards** (with C2's guard on, the branch that reads the model's value is unreachable). Removing that field took a 4-turn probe from 99% unparseable to ~50% and produced one clean verbatim claim.

**"Nemotron 3 Nano scores 0%" is retracted. It was never measured**, and "unanimous = 0 claims" is an artifact of a silent arm, not a fact about three-lab agreement.

**Issue 044 = C: the third arm is not re-run.** It was never measured, and a third lab reversing a −24-point recall cost is not plausible on this evidence. **"A reasoning model does not fit this harness" is kept as a finding for model selection** (parameter 047). The harness itself is fixed by C3 (§16); the next cycle goes to precision, which is C4 (§17).

---

## 14. B7 — Make the review page report what actually ran · **DELIVERED** (`bd5ecbf`, `3f0b8cc`)

Three gaps. The first attempt closed two and **relocated** the third; the second closed it properly against a committed failing test.

**What it established, now the contract:**

- **Provenance is read off the extractor instance that actually ran.** `model_id`, `runtime` and `quantisation` come from the object; `quantisation` is derived from the loaded model's own config (`config["quantization"]["bits"]`), not by matching a substring. `rubric_commit` is computed at run time by `get_rubric_commit()` from `git log -1 --format=%h -- <rubric path>`; `prompt_version` is a SHA-256 of the rubric text actually sent.
- **Gate failure rates are shares of all turns** — promoted to a standing constraint (§24).
- **A running server displays the HEAD it started with**, so a stale process is visible rather than merely plausible.

**Verified independently, not from the commit body.** A real `ModelExtractor()` load reports `quantisation: 4-bit` derived from config. A real single-turn run records `rubric_commit: 9882bc3` — the commit that actually touched the rubric; the previous `23da31c` is the B1 commit and never did. The gold fixture's 405 verdicts, 33 claims and 372 exclusions are unchanged across that correction. Both artifacts' stored `gate_failure_rates_*` were recomputed: gold `81.18 → 74.57`, falsification model `100.0 → 2.96`. And **three turns run twice produced identical verdicts**, so extraction is reproducible under the pinned greedy sampler (parameter 037).

`test_b5.py`'s four literal assertions — trap 81, a test that pinned the defect in place — were rewritten to assert against `model_provenance`, rather than deleted or reverted around.

**The method that worked, and why it is now §26's rule.** The first attempt satisfied a prose assertion by moving the constants one file upstream. The second was handed `v2/tests/test_b7_provenance.py`: committed red, `xfail(strict=True)`, with `warn_unused_ignores` in `mypy.ini`. It made the tests pass with the file otherwise unmodified — `git diff` shows only the marker and the `type: ignore` deleted — and **both tripwires fired as designed**, the suite going from `39 passed, 6 xfailed` to `45 passed`.

**Residue carried to B6 (§13)**, which is the item it breaks: the recorded `decoding` block claims a seed that is wired to nothing.

---

## 15. C2 — A claim with nothing in it is not a claim · **DELIVERED** (`92a1062`)

**Verified independently against the artifact**: of 138 emitted claims, **0 have an empty quote and 0 carry a quote that fails to resolve in their own turn**. Guard rejections are exactly as reported — **23 empty, 14 non-verbatim, 1 context leak, 38 total (9.38% of 405 turns)** — and `VALIDATORS_ADDED` is 1.

**What it cost, stated rather than buried.** Recall fell from a reported 81.82% to **54.55% (18/33)**, and precision from 15.34% to **13.04% (18/138)**. The commit reports the loss in points against both the inflated figure and the honest one. **That is the correct delivery** — C1's 81.82% was never real, and the guard also rejected 5 true positives whose quotes were not verbatim.

**Both test repairs are real.** `test_c1_extraction_artifact_metrics` dropped its 13 equality snapshots and kept the floors (`recall > 50.0`, `precision > 10.0`), so the re-run that produced these numbers did not read as a regression. `test_job2_gold_exclusions_survive` now shells `git show 9882bc3:v2/docs/design_claim_rubric.md` and asserts §2 is byte-identical — it reads the rubric, which the version it replaced never did.

**Now a standing constraint (§24):** an emitted record must carry the field it exists to carry, and the rejection rate is published as a rate over all turns.

---

## 16. C3 — A generation we could not read is not a verdict · **DELIVERED** (`176dc0f`)

**Verified by re-scoring all three B6 arms myself**, not from the commit body:

| arm | unparseable | status | confusion matrix |
|---|---|---|---|
| Nemotron 3 Nano | **401/405 (99.01%)** | `invalid` | **suppressed** |
| `gemma-4-31b` | 0/405 | ok | `{tp 32, fp 79, tn 293, fn 1}` — unchanged |
| `GLM-4-32B` | 0/405 | ok | `{tp 25, fp 55, tn 317, fn 8}` — unchanged |

`raise_on_high_unparseable=True` raises `UnparseableRateError` naming the rate. **The threshold fires on the silent arm and not on the real ones, and the matrix is genuinely withheld rather than reported.** `offset` is gone from `extract_claim.md` (prompt hash `738f12858fbf` → `503a35f05563`) and still computed in code at `target_text.find(quote)`.

---

## 17. C4 — Score every candidate on the eight axes · **DELIVERED, `(c)` honestly failed** (`7fe5c0f`)

**Three axes came back with zero variance, and the commit says so plainly** — which is what the item asked for when that happened. 111 candidates scored by `GLM-4-32B`, extracted by `gemma-4-31b`, `scoring_model_id` distinct and recorded. The episode report carries both panels separately with **no composite score**, and B5 renders it.

Verified independently from the artifact:

| axis | 0 | 1 | 2 | mean |
|---|---|---|---|---|
| contestability | 4 | 31 | 76 | 1.65 |
| decontextualisation | 18 | 6 | 87 | 1.62 |
| fidelity | 3 | 1 | 107 | 1.94 |
| voice | 3 | 1 | 107 | 1.94 |
| typing | 0 | 2 | 109 | 1.98 |
| **granularity** | 0 | 0 | 111 | **2.00** |
| **propositionality** | 0 | 0 | 111 | **2.00** |
| **target** | 0 | 0 | 111 | **2.00** |

**The proxy cross-check was done properly and corrected the guide.** My unresolved-referent regex flags six claims; the item resolved each and found **four of the six are mine, not the model's**: `t0111`, `t0172`, `t0238`, `t0359` open with an expletive *"It is very hard to control government spending…"*, where the logical subject is a postposed clause and nothing is unresolved. `t0072` is a genuine model miss. **The mechanical proxy for decontextualisation has a 67% false-positive rate and must not be tightened into a check** — it stays a disagreement detector, as §18 says.

---

## 18. C5 — Validate the scorer without human labels · **DELIVERED** (`5763ab9` red, `79678f5` green) · *Issue 045 = B*

**The tiers worked, and tier 4 was reported first as required.** Self-agreement **86.7%** against cross-model **80.0%** — the floor holds, so the tiers above it mean something. Tier 3 names **contestability** the most ambiguous axis at 73.3% agreement, which is a real, non-circular finding about the axis definition.

Tier 2 passed every axis on target sensitivity (≥4 of 5 pairs). **And that is the finding, because it is not enough.**

---

## 19. C6 — Four of the eight axes are not being read · **DELIVERED in part** (`df9f92f`)

**The contamination fix is real and large.** On the metric C5 measured, seven of eight axes improved sharply:

| axis | C5 | C6 |
|---|---|---|
| typing | 51.4% | **2.9%** |
| propositionality | 45.7% | **2.9%** |
| target | 40.0% | **0.0%** |
| granularity | 22.9% | **8.6%** |
| voice | 20.0% | **2.9%** |
| contestability | 17.1% | **0.0%** |
| decontextualisation | 8.6% | 8.6% |
| **fidelity** | 11.4% | **31.4%** |

**Granularity now scores 1 on all three natural compound claims** — `t0016`, `t0255`, `t0389` — using a neat inversion: the real 42-word claim is the *damaged* side of the pair and a hand-written atomic version is the original. **Step 4 is the item's best output:** scored over 40 turns Pass 1 rejected, Target comes back 25/6/9 and Propositionality 7/15/18. **Both axes discriminate perfectly well on raw dialogue; their 0/0/111 was survivor bias from Pass 1**, not a broken axis.

### Correction — a finding of mine that was wrong

**I reported that `reasons` was empty on 888 of 888 judgements. It was not.** The reasons were present in C4's artifact all along, keyed `{axis}_reason`; I looked up `{axis}` and read the zero as a defect. **C6's Step 1 was therefore a non-task**, and the guide sent an agent to build what already existed. `verify_888_reasons` confirms 888 of 888, and so does reading the file with the right key. Recorded as trap 94.

---

## 20. C7 — The fix was demonstrated but never applied, and fidelity regressed · **DELIVERED in part** (`6460d21`)

**The re-score happened and it worked.** 111 candidates, 3,969s, GLM-4-32B. Granularity moved `0/0/111` → **`0/3/108`** — the three natural compounds now score 1, which is what C6 calibrated for and never applied. Every remaining axis varies.

**One metric, named and gated, with the failure printed.** The report carries a single `off_target_drop_rate_pct` column across C5, C6 and C7 and marks **fidelity `31.4%` — FAILED (regressed)**. After trap 95, that is the right delivery.

**And the fidelity diagnosis redirects the fix.** `fidelity_01` alone causes **7 of the 11** off-target drops: the perturbation replaces the claim with a statement about a *wholly different topic*, so under C6's stricter rules the model correctly drops Voice (*"not said by speaker"*) and Decontextualisation (*"introduces concepts not in the quote"*) as well. **Fidelity's regression is a perturbation-design artifact, not a scorer defect** — the instrument is at fault, which is the opposite of what C7's `(c)` assumed and a better finding than passing would have been.

Target, Propositionality and Typing are removed from the Speaker panel and recorded in a front-half filter section with Step 4's numbers attached.

---

## 21. C8 — Three residues, and a report that answers a narrower question · **DELIVERED** (`a67dd8e`)

**All three `(c)` clauses verified independently from the artifacts.**

**Fidelity is isolated.** Rebuilt as direction inversions that keep subject, speaker and domain terms, the five pairs give **5/5 sensitivity at 0.0% off-target** — recomputed by hand. Every axis is now under 8.6%.

**The funnel sums to 405** — 111 claims (27.4%), gate 1 174 (43.0%), gate 2 37 (9.1%), gate 3 4 (1.0%), gate 4 79 (19.5%) — and is labelled episode-wide against the panels' survivor-only.

**The leniency question got a real answer.** The before/after table matches my computation to the digit (**69 → 29 non-2, −58.0%**), and all nine dropped decontextualisation zeros were adjudicated one by one: **six where C7 is right and C4 was wrong, one where C4 was right (`t0162`), two borderline.** So calibration mostly stopped bleeding rather than stopping scoring — which is what the item was filed to find out.

**`t0072` was resolved by a third route and the right one.** Rather than force a score or explain the anchor away, the item states that the claim *does* violate the level-0 anchor, that the model is lenient toward demonstrative-initial copular sentences, and records it as an established scorer defect. **Declining to hand-edit a score mid-item is correct.**

**The falsification fired and confirms C7's diagnosis.** The uncalibrated C4 scorer also gets 5/5 at 0.0% on the rebuilt pairs. My criterion read that as *"the rebuild made the axis trivially easy"*; the better reading is that **fidelity's contamination was always the fixture's and never the scorer's**, which is exactly what C7 diagnosed. Both scorers isolate a perturbation that does not disturb the other axes. **That is the fixture working, not a bar being lowered** — with the caveat C9 picks up.

---

## 22. C9 — The constraint I wrote and did not apply, and the axis nobody adjudicated · **DELIVERED** (`d148d6d`, `e1a1b73`)

### What landed, and it is the harder half

**Contestability is adjudicated in full.** All 23 changes published by turn id with a three-way split: **C7 right 13 (56.5%), C4 right 7 (30.4%), borderline 3 (13.0%).** Set against decontextualisation's 1-of-9, **calibration cost seven genuine non-2 scores on the one Speaker-panel axis with variance.** That is the real price of the 69 → 29 shift and it is now on the record.

**The fixture carries three well-formed real-derived fidelity pairs**, each with an original and a perturbation drawn from an actual pipeline failure:

| pair | original → perturbed |
|---|---|
| `t0127` | *"He is going to own open source"* → *"**Elon Musk** is going to own open source"* |
| `t0142` | → injects *"**Treasury Secretary Janet Yellen**"* as the entity covered |
| `t0189` | *"the core root of America becoming a socialist country"* → *"the core root of **inflation**"* |

**And the finding is the one the item was filed to look for.** The scorer catches **topic substitution** (`t0189` → 0) and is **lenient on entity substitution** (`t0127`, `t0142` both scored 2). **This is C6's granularity lesson transferring exactly as predicted** — the axis detects the damage we imagine better than the failures the pipeline actually produces. The falsification settles the cause: the uncalibrated C4 scorer has the **same** blind spot, so calibration did not create it.

`design_claim_axes.md` now carries the `t0072` demonstrative blind spot beside Axis 6.

### The remainder, verified (`e1a1b73`)

**The calibrated scorer now meets the real cases.** `c9_perturbations_scored`'s fidelity block has a new SHA (`b77fc06c…` against C8's `a5bdd8f2…`), contains `t0127`, `t0142` and `t0189`, and scores **both sides on all eight axes**. **The scored artifact's 40 turn ids match the fixture's 40 exactly**, which settles the question the falsification asked — the generator reads the right pairs.

**Trap 100's fix landed without being required:** the artifact records `fixture_path` and `fixture_sha256`, and the recorded hash matches the file on disk. **Trap 101's fix landed too:** every C9 column in the cross-item table names its instrument in the header — *"C9 Off-Target (GLM-4-32B Calibrated)"* — and fidelity's C9 cells are C9's own measurement.

**Under one scorer the result holds.** Calibrated real-derived sensitivity is 1 of 3, the same as the uncalibrated run — so the earlier comparison was between instruments but the conclusion survived it.

### Three corrections to how it was recorded

**`t0142` is an invalid pair, not a miss.** Under the calibrated scorer its perturbed claim — the injected *Janet Yellen* — **scores 0, caught**, with the reason *"not entailed by the quote."* It registers no drop only because the **original also scores 0**: its source quote is ASR-garbled (*"Brooks drugs note is coverage for best and at a pointing responsibility back to Congress…"*) and the scorer judges the clean claim unsupported too. **A pair whose original already fails the targeted axis has nowhere to fall** and must be excluded, not counted as a miss. **Valid real-derived sensitivity is 1 of 2** — `t0189` caught, `t0127` missed.

**So the entity-substitution blind spot rests on one case**, `t0127` (*He* → *Elon Musk*). The report and parameter 068 said *"lenient on `t0127` and `t0142`"* and *"both score 2 under calibrated"*; the second is the uncalibrated result and was false for the calibrated scorer. **Parameter 068 is corrected.** The report text is not, and is C10's Step 0.

**Fidelity is marked `PASSED` at 60% sensitivity.** Every tier-2 item since C5 has required target sensitivity **≥4 of 5**; typing at 4/5 passes correctly and fidelity at 3/5 does not. **The status column evaluates off-target only** — trap 93, recurring after it was written down. **Fidelity falling below the bar once real cases are included is the expected and informative result**, not a regression; it should read *below bar — see real/invented breakdown*, not `PASSED`.

**The falsification test is weaker than specified** — it asserts the on-disk artifact differs from C8's rather than deleting and regenerating — **but the substance is established** by the 40-of-40 turn-id match above.

---

## 23. C10 — Everything we know is one episode

**Unblocked by C9** — measure a second episode with a settled instrument, not a moving one.

**User impact:** Louis asked *"per episode, how good are the claims being made?"* Every number in this project comes from **one** episode. Nothing yet distinguishes a property of All-In from a property of E287.

**Contract:** `v2/artifacts/transcripts/39b1ef6934b6da6b.json` · the existing pipeline, unchanged.

### Why this episode

**E165 (`39b1ef6934b6da6b`), "SaaS recovery & AI investing".** 361 turns, four known hosts, no guest, and **11.1% question-anchored against E287's 11.13%** — the closest structural match in the corpus, chosen on B2's own criteria (a regular four-host episode, not a guest interview, since guests are excluded by gate 1 and would measure the wrong thing).

**There will be no gold set for it.** Issue 045 = B settled that no hand labels are produced. **This item measures stability, not accuracy** — and must say so in every sentence that reports a number.

### Implementation

**Step 0 — fix the report generator first, and commit it separately.** C10's product is a report, and the generator that will print it has two defects C9 exposed:

1. **The status column gates on off-target only.** Make `PASSED` require **both** `off_target_drop_rate_pct < 25%` **and** target sensitivity **≥4 of 5**, and print which criterion failed. Fidelity must then read *below bar* at 3/5 — **with the real/invented breakdown beside it**, because a mixed set is expected to score lower and that is the point of including real cases.
2. **Invalid pairs are counted as misses.** A pair whose original already scores 0 on the targeted axis cannot register a drop. Exclude it from sensitivity, report it by id as `invalid_pair`, and state the denominator. **`t0142` is the live example.**

> **Verify:** regenerate C9's report and confirm fidelity reads below bar at **1 of 2 valid real-derived pairs**, with `t0142` listed as invalid. **Then commit, and only then start Step 1** — so E165's report is printed by the corrected generator and E287's can be regenerated by the same one.

**Step 1 — run the unchanged pipeline end to end**: extraction with `gemma-4-31b`, the C2 quote guard, then axis scoring with `GLM-4-32B`. **Change nothing.** Budget roughly 2 hours for extraction and 1 for scoring.

> **Verify:** the prompt hashes recorded for E165 are byte-identical to E287's. **If any differ, the comparison is between two pipelines and not two episodes.**

**Step 2 — report the funnel and both panels beside E287's**, in one table, two columns.

**Step 3 — say which numbers moved and which held.** The interesting result is either way:

- **Gate 1 near 43% again** would make *"two in five turns are narration or reported speech"* a property of the show. **Far from it** makes it a property of E287.
- **Claim density near 27%** would make the funnel a usable episode metric. A large swing means density tracks topic, not quality.
- **Contestability's distribution** is the Speaker panel's only informative axis; if it does not move across two episodes with different subject matter, it may not be measuring the episode at all.

> **Verify:** every comparison is stated as *E287 vs E165*, never as an average of the two. **Two episodes is not a corpus**, and a mean over two hides exactly the variation this item exists to expose.

### Validation

- **(c)** — **the full funnel and both panels for E165, produced by a byte-identical pipeline, reported beside E287's with per-metric deltas and an explicit statement of which held and which moved.** *Every parameter in `ongoing_errors.md` §2 was measured on one episode. Until a second exists, none of them is known to describe All-In rather than E287 — and this item cannot establish accuracy, only stability.*
- Prompt hashes identical to E287's, pasted.
- No averaging across the two episodes anywhere.
- Unparseable rate reported for E165; C3's threshold must not fire.
- `ruff`, `mypy`, `pytest` clean.

**Falsify.** Split **E287 itself** into two halves and run the funnel over each. **If E287's own halves differ by as much as E287 differs from E165, the between-episode comparison is measuring within-episode noise** and a two-episode conclusion is not available at this sample size. Report both spreads.

**Blast radius.** Step 0: `v2/src/run_c9.py` (or wherever the status column and sensitivity are computed), `v2/artifacts/reports/`, `v2/tests/`. Steps 1–3: `v2/artifacts/extraction/`, `v2/artifacts/reports/`, `v2/tests/`. **No change to prompts, rubric, axes doc, gold set, or V1** — Step 0 changes how results are *printed*, never how they are *measured*, and the pipeline must be untouched for the comparison to mean anything.

---

## 24. Standing constraints, carried from V1

- **A filter upstream of a metric absorbs the variation the metric is meant to show.** Pass 1 enforces voice, target and propositionality, so among the claims that reach scoring those axes cannot move — the Speaker panel is left measuring contestability alone. **Report the funnel over everything, not only the profile over the survivors**; all 405 turns already carry a Pass-1 label at no cost.
- **A status field must evaluate every criterion the item's `(c)` names, and say which one failed.** Trap 93 — a validation gating on the flattering half of its own output — recurred in C9, where fidelity was marked `PASSED` at 60% sensitivity because the column checked off-target alone. **Twice is a pattern; it is now a constraint.**
- **A fix validated on constructed cases is not delivered until it has run over the corpus the product renders.** C6 calibrated the scorer against 40 perturbation pairs and never re-scored the 111 candidates, so the episode report still shows the numbers the fix was built to change.
- **An axis that cannot vary is not a measurement, and a mean of 2.00 must never be reported as one.** Three of the eight came back identical on all 111 claims. **Report the distribution, not the mean**, and treat zero variance as a defect to explain rather than a score.
- **A perturbation set built only from damage you invented tests only the damage you imagined.** Granularity detects two unrelated claims joined by "and" in 5 of 5 pairs and scores 2 on every naturally compound claim in the episode. **Seed perturbation sets from real failures once you have them.**
- **Agreement between models is a confidence signal, never a correctness one.** Two models given the same rubric share its blind spots — B6 measured three labs agreeing on `t0142`, which the gold set calls an exclusion. **Where no human label exists, get ground truth by construction instead**: damage a known-good item on one axis and assert that axis falls. Agreement's honest use is diagnostic — an axis two capable models disagree on is badly defined.
- **This is not fact-checking and must never become it.** No axis, gate or score asks whether a claim is *true*. A confident prediction that turns out wrong scores high; an uncontested fact is excluded *because* nobody can change their mind about it. **The product is a record of what someone committed to and whether it held** — see `design_claim_axes.md` §1.
- **Claim quality and extraction quality are reported separately and never blended into one score.** The Speaker panel says how good the claims were; the Extraction panel says how well we captured them. **They have opposite fixes.**
- **A generation that could not be parsed is not a verdict.** Count it as `unparseable`, report the rate, exclude it from precision and recall, and fail loudly above ~5%. Nemotron's 401 unreadable generations of 405 were recorded as gate-1 exclusions and reported as 0% recall for the model.
- **Do not ask a model for a value the code computes.** The prompt's `offset` field is overwritten at `extract.py:248` and unreachable under C2's guard; it cost every model tokens on every turn and made a reasoning model unusable.
- **An emitted record must carry the field it exists to carry, and the rejection rate is published as a rate over the whole population.** C1 emitted 23 claims with no quote and no claim text; four scored as true positives and lifted reported recall from 69.70% to 81.82%. C2's guard rejects them and publishes 38 rejections as 9.38% of 405 turns (`VALIDATORS_ADDED = 1`).
- **A rate whose denominator is under about 20 is written as a count.** "75.00% precision, a 5.75x boost" was three correct predictions out of four.
- **Provenance is read off the object that did the work, never from a module constant.** Model id, runtime and quantisation come from the extractor instance that ran; a commit hash is computed from the file it names; a prompt version is a hash of the text actually sent. **If a value cannot be derived, record `unknown` — never a default that is right today.** B7 was filed, half-fixed by relocating the constants one file upstream, and closed only once the assertion moved to the write path.
- **Gate failure rates are shares of all turns in the episode, never of the exclusion subset.** 302 of 405 is **74.57%**. Share-of-exclusions renders a 12-exclusion run and a 405-exclusion run identically at 100%, which is how three denominators for one number coexisted across B2's fixture, B3's report and B5's page until B7.

- **One item = one commit**, the *why* in the body.
- **Never fill in a `Your selection: _____` line.**
- **Quote the item's `(c)` verbatim in the commit body and answer it with a number beside its target.** `(c)` failing is a legitimate outcome; recording a different assertion as `(c)` is not.
- **When an assertion cites rows, cite primary keys that resolve in the store.** V1 ended with forty pasted claim ids, none of which existed.
- **Every `> **Verify:**` step is answered in the commit body, including the ones you skipped, marked as skipped with a reason.**
- **A guard that has never failed has not been tested.**
- **Local, open-weights models only. No hosted API; no transcript leaves this machine.** If an item appears to need one, that is a question for Louis, not a decision to take mid-item.
- **Exhaust what is installed before proposing a download or a dependency.** B3 concluded "local extraction fails" from a 2B model while an 8B sat pulled and unused.
- **Read the output a person would read, not the aggregate.** V1 published five fabrications past complete, honest, passing metrics.
- **Any new directory containing Python code must be added to the gate commands (`ruff check`, `mypy`, `pytest`) in the same commit that creates it.** Prevents unmonitored code rot — V1's `scripts/` sat outside gates and accumulated 17 errors; V2's entire tree landed without gates for five items.

---

## 25. Traps (carried from V1 §6)

Traps 1–16: `217b383:docs/agent_execution_guide.md` §1. Read them before writing in their layer. The ones that have already bitten:

17. **An assertion about *shape* is satisfiable by a stub.** Every integration item needs one that cannot pass without the real dependency.
18. **A suite that finishes too fast is telling you something.** Real models are slow; ~35s is the current floor.
19. **A mock named honestly is safe; a mock named plausibly is not.** Name stubs `Mock*`/`Stub*`.
20. **A metric over one example per class is not a metric.**
21. **Green gates over an empty corpus prove nothing about the product.** Everything currently passes with zero real rows. `verify_quotes` on zero claims is `NOT APPLICABLE`, not success. **I0 exists because of this.**
22. **A fixture can be structurally incapable of testing what it is labelled as.** Eight pair-type fixtures were single undated sentences carrying two-utterance expected outcomes, and three classes were missing outright — while the harness reported 16/16 PASS. **A green fixture suite says the cases that exist pass, never that the cases you need exist.** F0 exists because of this. Assert class-completeness against the contract table, not against whatever happens to be on disk.
23. **A source's tier and venue can differ per subject.** All-In is Tier B for its four hosts and Tier C for a guest, in the same episode. `venue_type` and `audience_stance` are properties of a (source, subject) pair, not of the source — and `audience_stance` feeds audience-divergence detection, so getting it wrong produces a wrong *finding*. Issue 022.
24. **A corpus can be skewed without being thin, and nothing catches that.** Invariant I5 gates on *volume* — too few claims, no score. It says nothing about *composition*. A subject whose primary medium is excluded (Musk without X) yields plenty of claims, passes the gate, and renders a confident score over a systematically unrepresentative slice. Issue 023.
25. **"Ingested" is not the same as "produced anything."** Three sources were stamped `ingested_at` *and* `audio_deleted_at` while yielding zero utterances. Every integrity check verifies that pointers *resolve* — none verified that the pipeline *emitted* anything. **Success must be defined as output, not as absence of exception**, and any irreversible step (audio deletion) must be gated on that definition.
26. **A detector finding nothing over a corpus that cannot contain the thing is not a true negative — it is an untested detector.** Every claim in the store is from one day with one stance, so a reversal is impossible by construction. P4/P5/P6 report zero and are green; they have never met data capable of contradicting itself.
27. **Local green does not mean CI green.** §3's block checks the local battery and has no CI signal at all, so CI stayed red across several commits unnoticed (Issue 024).
28. **A real quote does not make a real claim.** `verify_quotes` proves the words were said. It never proves they said *that*. A published tension was traced to two genuine quotes carrying a wholly invented proposition, and all five extraction validators passed. **"Is this citation real?" and "does this citation support this claim?" are different questions, and only the first was ever asked.**
29. **A parameter that is declared, defaulted, and never referenced is not a check.** `verify_source_productivity(min_ratio=0.05)` never uses `min_ratio` — and could not, since no media duration is stored. The function reads as a coverage check and is a non-emptiness check. Grep for the parameter in the body, not just the signature.
30. **Fragmentary input invites fabrication.** Utterances split on length rather than sentence boundaries end mid-word. Asking a model to find a *position* in a fragment that cannot hold one is how invented propositions get attached to real words. Fix the segmentation before blaming the extractor.
31. **`hasattr` on a dataclass field is a silent default, not a check.** `engine.py:82` guards `hasattr(c, "source_id")` on an entity whose source is reachable only through its utterance. The guard is always False, the set stays empty, and a `max(…, 1 …)` fallback supplies a plausible number. Nothing fails and nothing logs. **Use direct attribute access on declared fields so a rename fails loudly**, and treat every fallback that manufactures a value as a place a bug can hide indefinitely.
32. **A verification pass that unions fixtures with production data cannot tell you which one passed.** `worker.integrity --all` extends fixture lists with live DB rows and checks the union — and silently omits assessments from the DB side entirely. **Report populations separately, and print the examined count for each**, or a green pass means nothing you can act on.
33. **A deterministic ID is only as canonical as its normalization.** `compute_proposition_id` lowercases and collapses whitespace but does not strip terminal punctuation, so `"…than Western nations"` and `"…than Western nations."` are different propositions. **No similarity threshold can merge them — the split happens before similarity is computed.** Over-splitting hides contradictions silently, which is the exact failure parameter 008's bias is written against.
34. **Fixing a measurement without fixing where the measurement comes from is self-confirming.** A coverage check whose duration is read from the truncated download computes ~100% and passes on a corpus that is 92% unread. **The denominator must come from outside the artifact being checked.**
35. **"Re-ingest" and "re-extract" are different runs, and a stage not named in the instruction does not happen.** R1 multiplied the corpus 11.7× and left the claim count at exactly 9, because the spec said one and not the other. The agent was correct; the spec was short. **When a work item exists to give a downstream stage material, name that stage's re-run as an explicit step.**
36. **A `.get(key, default)` on a key nobody writes is an unused parameter one layer down.** `verify_no_suppressed_scores` read `sufficiency.get("passed", True)` against an engine that writes only `claim_count`, `source_count` and `span_days` — so it returned its own default nine times and printed PASS over nine real assessments. **Grep for the writer before trusting the reader**, exactly as trap 29 says to grep the body before trusting the signature.
37. **A test that opens the production database can write to it.** `subj_nonexistent_subject` holds an assessment in the live corpus and no row in `subjects`. Tests legitimately *read* the corpus — assertion (c) often needs real data — but a test that needs to *write* must take a copy, and the corpus should be opened `read_only=True` from tests.
38. **A verdict computed from the evidence it gates is not a verdict.** E1 replaced `sufficiency.get("passed", True)` with `passed = any_scored` — so "did sufficiency pass?" became "did anything get scored?", and the check that asks *"if sufficiency failed, is any score present?"* can never find one. **A guard's input must be independent of its subject.** When a fix removes a default, check what replaced it: the same inertness survives a rewrite easily.
39. **A uniqueness bug hides behind a coverage check.** `verify_role_coverage` asks whether every utterance *resolves to* a role and passes over a `source_roles` table where every row is duplicated. Resolution and uniqueness are different questions, and only the first was asked — the same error shape as trap 28 (*"is this citation real?"* vs *"does it support this claim?"*).
77. **A test that asserts an issue is still open fails when the process works.** `test_ongoing_errors_issue_036_filed_correctly` asserted that Issue 036 was present with a blank selection line; it went red the moment Louis decided. **Assert the durable fact — that the issue is tracked, open or recorded — not the transient one.** The same test also asserted no line began "Your selection: C", which a test cannot distinguish from the user's own answer and so was never sound.
74. **A pasted artefact is only better than a count if somebody resolves it.** X4 pasted forty claim ids with quotes and verdicts, exactly as its `(c)` required, and none of the forty exists. The convention that was supposed to make judgement checkable made it *look* checkable. **When an assertion cites rows, cite primary keys and make a script resolve them** (§24) — and note that the same commit's aggregate counts were all exactly correct, so "the numbers are right" is not evidence the sample is.
75. **Aggregate accuracy and sample accuracy are independent.** Every count in that commit matched the database to the row; the qualitative sample was not drawn from it. **Check them separately** — a commit that gets the hard numbers right earns no credit for the soft ones.
76. **Five attempts at the same fix in different clothes is a signal about the approach, not the wording.** W0/W2 → D1 → D6 → X2 → X4 each removed one failure and produced another, and the corpus fell from 3,669 claims to 401. **When the third iteration of anything lands, stop and ask what is being assumed** — here, that the format was the limiting factor, which nobody had measured (Issue 035).
71. **A format that must emit something will invent what it needs.** D6's form produced propositions nobody could take a position on; X2's format produces positions nobody took, and almost always `FOR`, because the binary has no null. **Every extraction format needs a branch that returns nothing**, and it has to be reachable — "a claim it cannot phrase that way is not emitted" is not a branch if the phrasing always succeeds.
72. **"Not zero" is as weak a floor as zero.** D8's (c) required the count of opposing-stance propositions to be reported and said a zero would mean the self-join had nothing to match. It came back **one**, which satisfied the letter while the singleton rate went to 99.5%. **State floors as rates over the table** — the same correction Parameter 033 made to "no source contributes zero claims" (trap 61), repeated one layer up by the person who wrote trap 61.
73. **Report the cost of a fix, not only its benefit.** D8 drove frame-contradicted merges to zero and did not report that it did so by merging almost nothing. Both numbers existed and one was asked for. **When a threshold trades two quantities against each other, the item must require both at every candidate value** — a single-sided report makes a corner solution look like a win.
69. **Storing the judgement turns the next check into code.** Three fabrications needed a careful read of quotes to spot. The fourth is a two-line diff of `position_frame`, because X2 persisted the sentence the model wrote instead of only its conclusion. **When a step depends on a judgement, store the artefact the judgement was made from** — the next person gets a query instead of an opinion.
70. **A parameter measured on a distribution that a later item replaces is stale on the day that item lands.** `T_dedup = 0.84` was measured over v1.7 propositions and merged *"60 to 80 percent growth"* with *"10x growth for ever"* on v1.8 output. X2 correctly refused to retune it in the same commit; **the cost of that discipline is a follow-up item, and it must actually be filed** (§26).
78. **An unused variable can be the answer, not the leftover.** G0's `F841` sweep discarded `total_model_exclusions = sum(model_gate_counts.values())` as dead; it was the correct denominator for the column rendered beside it, computed and never applied. Three of that sweep's four discards were genuinely dead, which is what made the fourth easy to wave through. **Audit every `F841` against what the surrounding code divides by, returns or renders — an unused result is a dropped one until you show otherwise.**
79. **A dev server that walks to a free port lets a stale process answer the documented URL.** `serve_review.py` auto-increments 8787→8807, so a forgotten instance kept serving pre-commit output on 8788 while the new one moved silently to 8789 — HTTP 200, a plausible page, two commits out of date. **Stamp the HEAD hash and artifact mtimes into anything you will later cite as "I looked at it"**, and run `lsof -nP -iTCP:<port> -sTCP:LISTEN` before believing a page.
80. **An assertion that tests the read path is satisfied by moving the constant upstream.** B7's `(c)` required that editing an extraction artifact changed what the page rendered. It did — because the constants had been relocated out of the renderer and into the writer, where they are stamped into every artifact unconditionally. The page then reported a constant correctly. **When the defect is "this value is not measured", the assertion has to name the point of measurement, not the point of display**; a test that never imports the function which writes the value cannot see the bug. Written by the same person who wrote trap 17, about the same mistake one layer along.
81. **A test that asserts a literal appears on the page pins the defect in place.** `test_b5.py:202-205` asserts `"4-bit" in html`, `"mlx" in html.lower()` and `"23da31c" in html`. All three pass today and all three fail the moment those values become real rather than constant — so the test **defends the defect and rewards reverting the fix.** **Assert that the page shows what the source of truth holds, not that it shows a particular string.** A pinning test converts every later correction into a regression, and the agent hitting that red is being told, wrongly, that its fix broke something.
82. **One fabricated field discredits an otherwise correct provenance block.** B7's fix records model id, runtime, quantisation, rubric commit and prompt hash — every one genuinely derived — and then `"seed": 42`, wired to nothing. **A block that is four-fifths measured reads as fully measured**, and the next item to trust it is B6, whose own falsification was written as "run one model twice with different seeds". **Check each field of a provenance record separately against the thing it claims to describe** — the trustworthy neighbours are what make the invented one invisible.
83. **A falsification run on positives only cannot measure precision, and will be read as if it did.** C1's falsification evaluated the old rubric through the new template **across the 33 gold claims** and reported 87.9% recall. With no negatives in the sample there are no false positives to count, so the arm that was supposed to decide whether the rubric rewrite earned its place reported only the half that flatters it. **Run a falsification over the same population as the thing it is being compared to** — the full 405 turns gave 87.88% recall at 13.94% precision, and only then is the comparison a comparison.
84. **An empty verdict is still a verdict, and the scorer will count it.** 23 of C1's 176 emitted claims carry an empty `quote` and an empty `claim`; four land on gold-claim turns and score as true positives, lifting reported recall from 69.70% to 81.82%. **A format that must emit something will emit nothing and have it counted** (trap 71's twin). Assert that each emitted record carries the field it exists to carry, and report the rate at which it does not.
85. **A self-agreement test on a model that almost never fires measures the floor.** B6 ran GLM twice at temperature 0.7 over 21 arbitrary turns and reported 21/21 stability. GLM emits a claim on 0.7% of turns, so the sample almost certainly held none and the test compared 21 "no"s. Re-run over the 33 gold-claim turns it gave 2 claims then 3, agreeing on only 2 of the 3 turns where a claim was ever emitted. **Measure agreement on the population that can disagree, and report it beside the overall figure** — when the two diverge, the overall one is describing the exclusion rate.
86. **A substituted input is not a smaller version of the experiment, it is a different one.** B6 was specced for the biggest model each lab fits in 64 GB and ran a 2B, a 9B and a 7B vision model; one arm was a copy of an earlier run. Every number was correct and reproducible, so nothing in the gates or the arithmetic could catch it. **When an item names specific inputs, assert the inputs** — the artifact records `model_id`, so the check is one line and nobody wrote it.
87. **A parse failure that defaults to a valid-looking verdict turns "we could not read this" into "the model said no".** `parse_model_verdict` scores anything it cannot parse as `exclusion`/`gate_1`. Nemotron hit that path on 401 of 405 turns and was published as scoring 0% recall, with "unanimous agreement" computed across an arm that never voted. **Every fallback needs a status field and a rate** — and a rate that high has to stop the run, because the output was a clean, plausible, entirely fictional confusion matrix.
88. **A field the code overwrites still costs whatever it costs to produce.** The prompt asks for a character `offset` that `extract.py` recomputes and, under C2's guard, can never read. Cheap for most models; for a reasoning model it was fatal — measured, it spent 2,500 tokens counting characters one at a time. **Grep the prompt's output schema against what the parser actually uses**, the same way trap 29 says to grep a parameter against its body.
89. **A per-turn label and a per-span extraction are different questions, and the metric between them silently measures the difference.** B2 labelled whether a *turn* asserts a claim; the extractor answers whether a turn *contains* one. On short turns they coincide — 1.3% disagreement under 20 words — and on 200+ word turns they disagree 92.9% of the time, with recall unaffected at every length. `t0084` is 310 words of narrative containing *"Salesforce specifically was meaningfully oversold"*: the gold says exclusion, the model is right. **When precision varies monotonically with an input dimension nobody chose, suspect the unit before the model** — and adjudicate a sample before tuning against the target.
90. **A binary verdict hides quality problems inside the things it accepts.** `t0010` is a claim B2 and `gemma-4-31b` both accept, and its standalone proposition reads *"The individual discussed is more right on the substance of what he is saying than he is wrong."* **It names nobody** — an embedding attractor (trap 42) sitting inside a true positive. Across the 111 emitted claims, 6 carry an unresolved referent, 3 are compound blobs, and 39 restate their quote near-verbatim. **None of that was visible while the output was a yes or a no.** When a metric is binary, ask what it is averaging over.
91. **A validation suite with no ground truth can still be built, if you make the ground truth yourself.** Axis scoring removed the only labelled set, and cross-model agreement cannot tell consistency from correctness. **A perturbation has a known answer because you caused it** — replace a claim's subject with a pronoun and Decontextualisation must fall, and nothing else should. **This proves sensitivity, not calibration**: a scorer that drops 2 → 1 where a human would say 0 passes and is still wrong. Say which of the two you have measured, every time.
92. **Two weak signals that agree are worth more than either alone, and neither item will report it.** C4 found three axes with zero variance; C5 found off-target contamination of 40–51% on three axes. Separately each reads as a quirk. Crossed, they split the eight axes exactly: every axis the scorer reads has off-target under 25% and real variance, every axis it does not is pinned at 2 and moves when something else breaks. **When two items measure the same object from different angles, read their artifacts together** — the finding was on disk and in neither commit body.
93. **A validation that gates on the flattering half of its own output will pass.** C5's tier 2 reported off-target drops exactly as specified and set `all_axes_pass` from target sensitivity alone, so four unread axes passed. **If you require a number to be reported, require it to be gated too** — a threshold nobody set is a number nobody used.
94. **A key-lookup mistake reads as a defect, and the guide will send someone to fix what already works.** I reported `reasons` empty on 888 of 888 judgements; they were present all along under `{axis}_reason` while I queried `{axis}`. C6's Step 1 was a non-task built on my error. **Before filing an absence as a finding, print the keys** — a zero from the wrong key looks exactly like a zero from missing data.
95. **A second metric introduced alongside the first lets the threshold move without anyone deciding to move it.** C6 added `victim_off_target_drop_rate_pct` beside the `off_target_drop_rate_pct` the threshold was written against, and reported the new one against the old bar. Fidelity's 11.4% → 31.4% regression rendered as 11.4% → 14.3%. **Both numbers were in the artifact and nothing was concealed** — which is the point: **name the metric a threshold gates, in the same sentence as the threshold**, or the comparison silently changes shape.
96. **A calibration that removes low scores and finds none has not been shown to be more accurate, only quieter.** C6's calibration cut non-2 judgements across the 111 from 69 to 29, and C7's decontextualisation zeros are a strict subset of C4's — nine removed, none added. The one case with an established right answer, `t0072`'s unresolved demonstrative, is still missed by both. **When a fix reduces a detector's firing rate, adjudicate what it stopped firing on** before calling the rate an improvement.
97. **A perturbation can be so destructive that the scorer is right to fail every axis.** Fidelity's 31.4% off-target came from replacing a claim with an unrelated topic, which legitimately breaks Voice and Decontextualisation too — one pair caused 7 of 11 drops. **A single-axis perturbation has to leave the other axes true**, or the contamination it measures is the fixture's, not the model's.
98. **A lesson learned on one axis does not transfer itself to the next.** After granularity passed an invented perturbation and missed every real compound, I wrote the standing constraint that a perturbation set built only from imagined damage tests only what you imagined — and then wrote C8's fidelity spec without requiring a single real case. **When you add a standing constraint, grep the open queue for the items it now binds** and amend them in the same commit, or it applies only to the item that produced it.
99. **Adjudicate the biggest change, not the one the spec happened to name.** C8 read all nine dropped decontextualisation zeros because the `(c)` said nine. Contestability moved by twenty-three in the same table, on the only Speaker-panel axis with variance. **A spec that names a number freezes attention on it** — say "the largest movement in the table" when that is what you mean.
100. **A fixture updated is not a measurement taken.** C9 rewrote three fidelity perturbations from real pipeline failures and the scored artifact's fidelity block came back byte-identical to C8's — same SHA, same three old turns. The run was never re-executed against the new fixture. **Hash the input fixture into the output artifact**, and assert the two agree, or a stale result and a fresh one are indistinguishable.
101. **Two numbers in one column must come from one instrument.** C9's report puts *real 33.3%* beside *invented 100%*; the first was scored by the uncalibrated prompt and the second by the calibrated one. Nothing was hidden — both artifacts are on disk and named. **Put the instrument in the column header**, not in a paragraph below the table, whenever a table spans more than one run.
102. **A perturbation pair whose original already fails the targeted axis cannot register a drop, and counting it as a miss understates the scorer.** `t0142`'s perturbed claim — an injected *Janet Yellen* — was caught with an explicit non-entailment reason, but its original also scored 0 because the source quote is ASR-garbled. It was tallied as a miss and cited as evidence of the very blind spot it contradicts. **Real-derived pairs inherit the transcript's noise: check the original scores 2 on the targeted axis before counting the pair**, and report exclusions by id.
66. **An item whose effect is to publish must be checked against what it will publish.** D7 was told to make every accepted candidate produce a tension row, and did — publishing six findings that the same guide, two sections below, documented as false. The spec was followed exactly. **Before running an item that writes user-visible output, read what is currently in its input.**
67. **A judgement gate is scored generously unless the judgement is written down.** Three times now a gate has been recorded as met while an independent reading disagreed — six false pairs "hand-read and verified", a failed (c) recorded verified, and a position test reported at 18/20 that a seeded redraw scores 9–13/20. **Require the artefact, not the count**: paste the two sentences, quote the pair, show the working. A number is not checkable; a sentence is.
68. **A repair loop that shrinks its subject on every pass is not converging.** Three extraction-form passes took the corpus from 3,669 claims to 1,027 and the candidate set from 0 to 6 to 0. **Track the trajectory across passes, not the delta within one** — each pass improved its own metric and the sequence went nowhere.
63. **Fixing a form defect can overshoot into its mirror image.** D1 was told propositions were full clauses and made them noun phrases; a quarter are now bare topics — *"most enterprises"* — which carry a position no better than a clause carried none. **When an item removes a property, state the floor as well as the ceiling**, or the next reading finds the opposite failure with the same metric looking healthy.
64. **A hand-read reaches a wrong conclusion when the artefact cannot carry the distinction.** Six candidate pairs were read and recorded verified; all six are false, because a topic-shaped proposition makes a false pair structurally identical to a real one. **Reading is necessary and not sufficient — say what the reader must be able to write down.** D6 requires the sentence *"A takes position X, B takes position Y"*; a pair for which it cannot be written is not a contradiction, whatever its stance labels say.
65. **An acceptance gate that measures the wrong property passes cheerfully.** D1's 20-utterance sample reported "18/21 are noun phrases" — true, and blind to the defect that made the whole re-extraction miss. **The sample gate must test the property the item exists to produce**, not the one that is easy to count.
60. **A test named after an assertion is not that assertion.** `test_assertion_c_live_corpus_metrics` asserts that the proposition table is non-empty and carries no polarity. The item's (c) was about the singleton rate and the multi-episode share, both of which moved the wrong way. **Before recording (c) as verified, re-read the item's (c) sentence and check the test asserts that sentence** — the name is not the contract.
61. **A floor of zero does not notice starvation.** *"No source contributes zero claims"* stayed green while a 90-minute episode fell to one claim. **State coverage rules as a rate against the thing that varies** — claims per hour of audio — and derive the floor from the observed distribution.
62. **Tightening a validator shrinks the corpus, and the shrinkage is a measurement nobody takes.** D1's re-extraction cost 41% of claims. The rejection counters that would have explained it were not captured, so the loss has no attribution at all. **Capture the counters on every extraction run, and reconcile them against the change in row count** — if the arithmetic does not close, the loss is happening somewhere you are not looking.
58. **A hand-written evaluation set tests the mechanism you had in mind, not the one you built.** Twelve composed cases scored 6/6 both ways with zero confusion; a random sample of the live corpus was wrong 4 out of 4 in one direction, because every composed case had a negator whose scope was the proposition — the shape the author was thinking of. **Draw the evaluation set from the corpus, keep it fixed, and report a confusion matrix rather than an accuracy.**
59. **Fixing a validator does not fix the rows it already scored.** D3 made stance bidirectional and the corpus kept every stance the old one-directional instrument assigned. **A validator change has two deliverables — the code and the re-scoring — and the second only happens if the item names it.** (Same shape as trap 35, one layer down.)
55. **Scaling a corpus does not scale overlap.** Six times the claims moved the merge rate by 0.006 and left cross-source candidates at zero, because overlap is limited by how *specific* propositions are, not by how many there are. **Before spending hours of compute on more data, check that the data you have is being collapsed correctly** — the ratio of propositions to claims answers it in one query.
56. **A validator that has only ever fired one way has not been shown to discriminate.** Nine stance corrections, all `oppose`→`support`, zero the other way, on an instrument — embedding similarity to a synthesised negation — that is known to handle negation weakly. **Count corrections by direction and treat an n:0 ratio as a finding**, not as evidence the corpus is clean.
57. **A threshold outlives the distribution it was measured on, and nothing notices.** `T_dedup = 0.86` was fitted to propositions that W0, W2 and C1 have since replaced wholesale, and its recorded justification cites similarities between strings no longer in the table. **Record what a parameter was measured over, and re-measure when that changes** — a citation to a vanished row is not evidence.
52. **A guard tested only in the configuration where it cannot fail has not been tested.** The site's read-only connection raises on `INSERT` when the fixture opens storage read-only, and writes happily when storage is writable and holding the lock — which is the configuration you run. **Enumerate the configurations a guard has to hold in, and test the awkward one.**
53. **A `try/except` that substitutes a more-capable object for a less-capable one is a silent privilege escalation.** `except Exception: read_only_con = storage.con.cursor()` turns "this is a reader" into "this can write" with no log and no error. Issue 020 already ruled on the general form — *fail loudly if absent, never downgrade silently* — in a different layer. **Grep for the shape, not just this instance.**
54. **How a corpus was chosen is part of what it can support.** A tool that judges whether someone applied their principles evenly cannot rest on episodes picked because they looked promising. **Record the selection rule before the run** — "everything in this range" needs no trust, "the relevant ones" needs a lot (Issue 030 = A).
49. **Pre-rendering a page per row is a database with worse ergonomics.** The static export wrote 2,593 HTML files and 27 MB for 1,288 claims, duplicating the same rows across per-claim, per-person and per-episode pages. **When the data already lives in a queryable store, serve from it** — a build step that materialises every view is a cache of a thing you already have, and it goes stale the moment the corpus changes.
50. **A blocked item can be built anyway, and nothing in this guide stops it.** U1's queue row read `blocked_on: S1, T1, W2 + one real finding` and it was implemented before any of those landed. Nothing notices work that happens off the queue. **When an item is blocked on a judgement rather than a commit, say in the item what evidence unblocks it and who decides.**
51. **A correct pipeline can produce nothing, and that is a different finding from a broken one.** Zero candidate pairs over four episodes is a coverage measurement, not a detector fault — and it looks identical in a status table to the three broken zeros that preceded it. **Report the denominator that makes them distinguishable:** 4 propositions span more than one episode, out of 1,229.
45. **A validator that checks *aboutness* cannot check *direction*.** Validator 6 asks whether a quote supports its proposition and passes it either way it is labelled, so `stance` — the field the whole contradiction detector keys on — went unchecked through six validators. **Enumerate the fields a downstream stage reads, and confirm something validates each one.**
46. **A guard's firing rate is a measurement, and a suspiciously low one is a finding.** `is_own_assertion` excluded 9 of 1362 claims (0.7%) across four hours of unscripted conversation full of questions and hypotheticals. Nothing was red. **Report every guard's rate next to its rejections; a rate that looks too clean usually means the guard stopped reaching its subject.**
47. **A validator written from a list of observed failures catches the failures you observed.** W0 named three indexical patterns and the implementation matched them exactly — leaving 130 propositions with unbound `they`, `he` and `the same`. **State the property in the spec and the docstring; let the patterns be examples, never the definition.**
48. **A same-context pair is not a change of mind.** Every `unacknowledged_reversal` candidate in the corpus is two claims from one episode, usually a position voiced then rejected. A tension type that asserts change over time must require time. **Check that a detector's structural preconditions actually encode the claim its name makes.**
41. **A validator's guarantee expires the moment its subject is mutated.** X1 checked quote↔proposition at extraction. A later merge re-pointed the claim to different text and nothing re-checked, so 74 propositions' worth of claims carry conclusions validated against sentences they no longer reference. **An extraction-time validator needs an integrity-pass twin, or it certifies a snapshot and not the store.**
42. **A proposition with an unbound indexical is a template, and templates are embedding attractors.** *"The speaker believes they created the subject matter"* names nobody. Similarity between two such strings measures the shared frame, not the content, so they merge at any threshold and drag unrelated claims together. **Reject them at extraction; no downstream parameter can compensate.**
43. **Topic is not proposition.** *"DNA sequencing involves chopping up DNA"* absorbed *"…is relatively inexpensive"*; *"Moderna's mRNA was patented"* absorbed *"…should be directly injected into the body"*. Both merges are about one subject and are not the same assertion. `design_topic_model.md` owns grouping-by-subject; the proposition layer must stay narrower than it.
44. **A constant documented in one module and re-defaulted in a caller's signature runs at the caller's value.** `dedup.py` and `ongoing_errors.md` §3 both record `T_dedup = 0.86`; `extract.py:26` defaults 0.85 and wins. **Grep for the parameter name across every signature, not just its definition** — the measurement is worthless if it describes a value that never executes.
40. **Deterministic IDs only hold while every writer uses the helper.** Two `scripts/` build `f"role_{sid}_{subj_id}"` by hand instead of calling `compute_role_id`, so the primary key sees two different ids for one pair and the "every write is an upsert" guarantee silently becomes "every run inserts again." **Grep for hand-built id strings, not just for the helper's callers** — and note that `scripts/` is where this happened, because `scripts/` is outside every gate.


---

## 26. Validation standard (carried from V1 §8)

**This section is the difference between an item that lands and one that comes back.** Every rule below was paid for.

**When an item comes back a second time, stop specifying it in prose and commit the test.** B7 was described carefully and still came back, because prose leaves the implementer deciding what counts as satisfying it — and the fix that got chosen satisfied the sentence while leaving the defect in place. A committed failing test removes that discretion: the agent's job becomes making code pass a test it did not write and may not edit. **Commit it red, marked `xfail(strict=True)` so the suite stays green until the work lands and then goes red until the marker is removed.** See `v2/tests/test_b7_provenance.py`.

**Assert at the point of measurement, never at the point of display.** When the defect is "this value is not measured", an assertion that the page reflects the file is satisfied by writing the constant into the file. **Name the function that produces the value and assert on what it wrote** — and check the test imports that function at all. `test_b7.py` never imported `run_episode_extraction`, so it could not have caught the bug it was written for.

**Assert the inputs, not only the outputs.** B6 produced correct, reproducible numbers from three models nobody chose, and reused an earlier run as one arm. Ruff, mypy, pytest and the arithmetic were all green and none of them could see it. **When an item names specific inputs — a model, a corpus, a file — assert on the identity the artifact records.** It is one line, and it is the only thing standing between a careful-looking result and a different experiment.

**A test gated on nothing passes vacuously; a test gated on the old state passes wrongly.** The first draft of `test_b6_models.py` iterated whatever arms were on disk: two assertions went green against the *old* models, and would have gone green against an empty directory once those were cleared. **Route every per-item check through a helper that first asserts the expected inputs are present**, so the test is red before the work and meaningful after it.

**One call cannot distinguish a constant from a correct reading.** Any assertion about a recorded value needs two runs with two different inputs and a comparison between them. A single run agrees with a hard-coded answer perfectly.

**Read the output a human would read, not the aggregate.** Three fabrications have shipped past complete, honest, passing metrics. Merge histograms looked healthy while the pairs built on them were false; candidate counts rose while the rate stayed flat. **If your item's product is a claim about a person, read some of those claims before you call it delivered.**

**Draw test data; do not compose it.** A hand-written set tests the mechanism you had in mind. Twelve composed stance cases scored 6/6 both directions with zero confusion, and a random sample of the live corpus was wrong 4 out of 4. **Sample from the corpus, fix the sample, version it, and report a confusion matrix rather than an accuracy.**

**State assertions as rates over the table when the table is also changing.** "Rises materially above 4" was satisfied by a rounding error once the corpus tripled — while 95.5% of propositions stayed singletons, which was the thing that mattered.

**Name the configurations a guard must hold in, then test the awkward one.** The review site's read-only connection raised on `INSERT` in the fixture's configuration and wrote happily in the one you actually run. Both were true; only one was tested.

**Grep for the writer before trusting the reader.** `sufficiency.get("passed", True)` read its own default nine times against an engine that never wrote that key. A `.get(key, default)` on a key nobody writes is an unused parameter one layer down.

**Check the parameter is referenced in the body, not just the signature.** `verify_source_productivity(min_ratio=0.05)` never mentioned `min_ratio` again.

**A guard that has never failed has not been tested, and a guard that fires in only one direction has not been shown to discriminate.** Count corrections and rejections by direction. An *n*:0 ratio is a finding.

**Allocate a new number by scanning every section of the tracking doc, not just the one you are writing in.** Decisions and parameters share one number space, and two writers have now collided four times — 044, 045, 056 and 060 were each issued twice. **Grep the whole file for the number before using it.**

**Record what a parameter was measured over.** `T_dedup = 0.86` cites similarities between strings that three later items removed from the database. A threshold outlives its distribution and nothing notices.

**A stage not named in the instruction does not run.** "Re-ingest" is not "re-extract"; "fix the validator" is not "re-score the rows it already scored". If your item exists to feed a later stage, name that stage's re-run as a step and assert a property of *its* input.

**Verify the anchor chain end to end, not the pointer.** "Is this citation real?" and "does this citation support this claim?" are different questions, and for a long time only the first was asked.

**Prove the threshold is doing the work.** Set it to a value that must fail, watch the assertion go red, restore it. Record both outputs in the commit body. A repair with no falsification is a guess.

**Re-run every gate yourself before trusting §11.** This file has recorded a gate result that did not match reality more than once.

**Report zero with its denominator.** "No tensions found" over an empty candidate set and "no tensions found" over 400 examined pairs look identical in a status table and mean opposite things.

**Answer the assertion that was written, not the one you can satisfy.** An item's `(c)` is a sentence with a number in it. Quote it, measure it, put the two side by side. Every other form of reporting — a passing test whose name references it, a narrative that mentions the metric elsewhere, a summary that says "verified" — has been used here to record a failed assertion as met, without anyone intending to.

**When you substitute anything for what the item specifies — a different mechanism, a narrower scope, a value the item did not name — say so in the commit body.** Several items here were delivered exactly as written and still wrong; the substitution log is how the next verification pass finds out which.


---

## 27. Invariants — do NOT change (carried from V1 §14)

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

Full invariant definitions (carried from `v1/docs/master_implementation_plan.md` §3):

| # | Invariant |
|---|---|
| **I1** | **First-hand only.** The corpus contains only utterances the subject produced. Never a paraphrase, never a report of what they said, never a summary. |
| **I2** | **News as index, never as evidence.** A news article may be read to determine *who* and *what topic*. Its content never enters the corpus and never influences a score. The article is a pointer; it is discarded after resolution. |
| **I3** | **Nothing renders without an anchor.** Every displayed claim carries a verbatim quote, a timestamp or document offset, and a resolvable source locator. A finding with no anchor is a bug, not a low-confidence result. |
| **I4** | **No external ground truth.** The system never evaluates whether a claim is true. It compares the subject only against themselves. |
| **I5** | **Corpus-sufficiency gate.** Below the evidence threshold for a (subject, topic) pair, the system emits `insufficient_corpus` — never a number. Absence of evidence is reported as absence, never as a poor score. |
| **I6** | **A reasoned update is a positive.** Changing position with a stated reason raises the record's standing. Only *unacknowledged* reversals cost. A system that punishes updating measures dogmatism, not trustworthiness. |
| **I7** | **Own assertions only.** A claim counts only if the subject was asserting it themselves. Quoting someone to disagree, hypotheticals, steelmanning, sarcasm, and jokes are excluded — and the exclusion is recorded, not silently dropped. |
| **I8** | **All writes go through the ingestion worker.** Clients read. They never write to the claim store. |
| **I9** | **Every quoted string must `grep -F` back to its stored source text.** Enforced by an automated pass, not by reviewer diligence. |
| **I10** | **No biometric identification.** Subjects are resolved by stated identity — name, handle, or supplied identifier. Never by face or voice matching against a stranger. Voice fingerprints are used *only* to attribute speech within a source to an already-known subject. |

---

## 28. Deliberately not built — do not re-propose (carried from V1)

Each of these was considered and rejected for a stated reason in `v1/docs/master_implementation_plan.md` §15. Re-proposing one costs a cycle.

Each of these was considered and rejected for a stated reason. Re-proposing one costs a cycle.

| Not building | Why |
|---|---|
| **Prediction / forecast scoring** | Requires outcome data, which requires the excluded sources. Breaks I4 at the root. |
| **Fact-checking of any kind** | The system's defensibility comes from never asserting what is true. |
| **A single global trust score per person** | Collapses "never says anything falsifiable" and "consistently wrong" into similar numbers. The product does not support the question. |
| **Radar / spider charts for comparison** | Enclosed area is meaningless and axis ordering changes the shape. Head-to-head pairs instead. |
| **N-way comparison dashboards** | The overwhelm problem. Pairs, or a ranked list on one axis. |
| **Face or voice recognition of strangers** | Processes biometrics of everyone in frame *before* consent can be established. Illegal under Illinois BIPA, Texas CUBI, and GDPR Art. 9 regardless of opt-in design; no supported API on consumer AR hardware. Violates I10. |
| **Scoring private individuals from thin corpora** | The engine needs thousands of dated statements. Forty tweets does not produce a weak score — it produces a *confident* score computed on noise. Blocked by I5. |
| **Unofficial X/Twitter scraping** | ToS violation, brittle, and makes the most fragile component load-bearing. Deferred behind the adapter interface instead. |

---

## 29. Evidence integrity and V1 reference contracts

The integrity contract survives any rewrite of extraction:
- **E1–E5 Operational Rules:** Every rendered claim carries a verbatim quote, a date, and a resolvable source locator (E1). Every quoted string `grep -F` matches stored source text (E2). Every quote supports the proposition attached to it (E2b). Nothing derived from page context ever persists (E3). Below sufficiency gates, scores are null, never computed-and-hidden (E4). Precondition failures quarantine tensions, never rendered (E5).
- **Quarantine Semantics:** Findings that fail preconditions are quarantined with explicit reasons (`status: quarantined`), never silently dropped. Dropping hides failure rates; quarantining creates a measurable health metric. Quarantined findings never enter scores or public renders.
- **Evidence Resolvability:** Evidence about the store must be resolvable against the store. Citations of rows must cite primary keys that resolve in the database.
- **V1 Contracts as Reference Material:** All 13 V1 design documents, verification journeys, decision logs, and pipeline architectures are archived in `v1/docs/` for reference. Do not extend or repair them.

| Reference Contract | Path in v1/ |
|---|---|
| Master Implementation Plan | `v1/docs/master_implementation_plan.md` |
| Evidence Integrity Contract | `v1/docs/design_evidence_integrity.md` |
| Claim Extraction Design | `v1/docs/design_claim_extraction.md` |
| Source Acquisition & Diarization | `v1/docs/design_source_acquisition.md` |
| Principle Extraction | `v1/docs/design_principle_extraction.md` |
| Topic Model | `v1/docs/design_topic_model.md` |
| Rubric Engine | `v1/docs/design_rubric_engine.md` |
| Data Layer & DuckDB Schema | `v1/docs/design_data_layer.md` |
| Local API & Clients | `v1/docs/design_local_api_and_clients.md` |
| UI Direction | `v1/docs/design_ui_direction.md` |
| E2E Verification Journeys | `v1/docs/e2e_verification_journeys.md` |
| Decision Log & Historical Issues | `v1/docs/ongoing_errors.md` |
| V1 Agent Execution Guide | `v1/docs/agent_execution_guide.md` |
