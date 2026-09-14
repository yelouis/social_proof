# Agent Execution Guide — V2: rebuild claim extraction from the unit up — September 13, 2026

**You are an engineering agent with no memory of this project.**

**V1 is finished and is not being continued.** It ingested 23 episodes, produced 401 claims, and never found a single contradiction that survived being read. Five consecutive rewrites of the extraction format each fixed one failure and produced another. **V1's pipeline is reference material; do not extend it, do not repair it, and do not import its extraction code into V2 without a stated reason.**

**Where things stand, September 13 2026.** R0 split the repository; B1–B5 are delivered; the approach is decided (§3) and the rubric exists (`v2/docs/design_claim_rubric.md`).

**`ruff check v2/` reports 95 errors and `mypy v2/src` has never resolved a module.** R0 carried the traps forward and not the gates, so five items landed with a green test suite and no static checking at all. **Start at §5 (G0).** This is V1's G1 repeating — there the unchecked directory was `scripts/`; here it is the entire new codebase.

**B5 is delivered and verified independently.** All 405 turns of E287 render with their claims or their exclusion gate, the four gate rates are shown, and the model id and rubric commit appear on the page. Serve it with `.venv/bin/python v2/scripts/serve_review.py`.

**One issue is open and needs Louis: 036**, rewritten September 13 after B5 made the gold distribution readable. Four options, not exclusive: **A** run three bigger local models (item B6) · **B** two-stage filter · **C** rewrite the rubric as a positive elicitation · **D** finetune on the gold set. **Recommendation is C then A.**

**Two facts from that issue belong here because they change how you read everything else.** The task is **8.1% positive** — a model answering "not a claim" every time scores 91.9%. And **the rubric is written as an exclusion manual** — four gates that are four ways to say no, and 8 of its 11 worked examples are negative — which is the mechanism B4 measured as "binary collapse under negative checklists". **Unconstrained, the same 2B model found all 33 gold claims: 100% recall at 8.4% precision. It is not blind to claims; it cannot exclude.**

**Do not start B6 while that selection line is blank.**

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

## 3. The approach — decided September 13, 2026

Louis read V1's output and made three calls. **They are not provisional and they are not to be re-litigated by an implementing agent.**

1. **Turn-level extraction**, not one line of ASR. V1's unit was a median of **12 words / 3.3 seconds**; 49% were under 12 words. *"A couple of tickets left."* was an utterance.
2. **Question-anchored where the show allows it** — the host's question gives the matter at issue in clean English and the answering turn gives the position. **How much of All-In is actually question-anchored is unknown and B1 measures it.** If it is a minority, question-anchoring is a high-precision slice rather than the main path.
3. **A written rubric** is passed to the local model with the transcript, and **the same text is the human labelling instruction.** It is `v2/docs/design_claim_rubric.md`. Read it before B1; it is the definition of the thing this whole pipeline exists to produce.

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

**The biggest of each family that fits is worked out in §11 (B6).** Short version: **Gemma 4 31B** and **GLM-4-32B-0414** at 4-bit, ~18 GB each. **GLM-4.5-Air does not fit** (66.7 GB at Q4_K_M) and **Inkling does not fit at any size** — 975B/41B, Inkling-Small 276B ≈ 138 GB in 4-bit — and its fine-tuning path is Thinking Machines' hosted Tinker platform, which decision 4 rules out.

**Record the model identity in every artefact** — model id, quantisation, runtime, and the rubric's commit hash. V1 ran five prompt versions and could not say which produced which corpus without reading commit history.

**Validation is one All-In episode, labelled by hand, end to end.** Not a sample — **recall is the half V1 could never see**, and a sample measures only precision.

**What is deliberately NOT decided:** whether a claim-detection library earns a place. TARGER, MARGOT and Canary are research artefacts trained on written argumentative prose, not disfluent multi-speaker ASR; ClaimBuster has a live API but scores *check-worthiness for fact-checking*, which is a different question from *did this speaker commit to a position*. **Borrow the claim/premise taxonomy if it helps; do not add a dependency without measuring it against B2's gold set first.**

---

## 4. Queue

| Order | ID | Item | Blocked | Why here |
|---|---|---|---|---|
| 1 | **G0** | V2 has no gates, and five items landed without them | none | `ruff check v2/` → **95 errors**; `mypy v2/src` **cannot resolve modules and has never run**. R0 carried the traps and not the gates. **A red gate outranks the queue** — and there is currently no gate to be red. |
| 3 | **B1** | Turns, and how much of this show is question-anchored | none | DELIVERED. V1's unit was 12 words. Measured 11.13% question-anchored share. |
| 4 | **B2** | Label one episode by hand | B1 | DELIVERED. Hand-labelled 405 turns of E287; 33 claims, 372 exclusions across all 4 gates. |
| 5 | **B3** | Extract against the rubric | B2 | DELIVERED. Evaluated rubric prompt and stripped falsification prompt across all 405 turns. |
| 6 | **B4** | Measure, and decide whether to go on | B3 | DELIVERED. Precision and recall reported; conclusion recorded in one sentence; Issue 036 filed in v2/docs/ongoing_errors.md. |

| 7 | **B5** | A local page showing what was extracted, and what was not | B1 | DELIVERED. Rendered all 405 turns of E287 with side-by-side gold/model verdicts, gate distributions, and 33 disagreements. |

| 2 | **B6** | Three local models on the same episode, and what agreement is worth | G0 | Gemma, GLM and a third lab's model over the same 405 turns. **Agreement is evidence only if checked against the gold set** — three models wrong together is the row worth finding. Also settles whether a LoRA is worth attempting. |

**IDs are labels, not sequence numbers — follow the Order column.**

**Do not reorder these and do not start two at once.** V1's worst outcomes came from items that were individually correct and sequenced wrong — a publishing item run before the thing it published was real, a threshold tuned over claims that were fabricated.

---

## 5. G0 — V2 has no gates, and five items landed without them

**Do this before B6.** A red gate outranks the queue (§13), and right now there is no gate at all to be red.

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

**Falsify.** Re-introduce one unused import and one `typing.List`; the block must go red naming both. Revert; record both.

**Blast radius.** `v2/docs/agent_execution_guide.md` §3 and §13, `v2/src/*`, `v2/scripts/*`, `v2/tests/*`. **No behaviour changes** — if a fix alters behaviour, it is not a lint fix and belongs in its own commit.

---
## 6. B1 — Turns, and how much of this show is question-anchored · **DELIVERED**

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

## 7. B2 — Label one episode by hand · **DELIVERED**

**Blocked on B1.** DELIVERED. Unblocks B3.

**User impact:** every threshold, prompt and gate after this becomes measurable instead of self-reported.

**Contract:** `v2/docs/design_claim_rubric.md` in full.

**Gap.** V1 set six parameters and ran five format rewrites without a single human-labelled example. Five gates were self-reported as met and disagreed with on independent reading; one pasted forty claim ids as evidence and **none of them existed.** **There was never anything to be wrong against.**

### Implementation

**Step 1 — Pick one episode and say why.** A regular four-host episode, not a guest interview — guests are excluded by gate 1 and a guest-heavy episode measures the wrong thing.

**Step 2 — Read the whole episode's turns and mark every claim.** Not a sample. **Every turn**, start to finish, applying the rubric's four gates in order.

> **Verify:** the count of turns examined equals the count of turns in the episode. **Recall is the whole point** — a sample tells you whether what you found is good and nothing about what you missed, and missing is V1's failure mode.

**Step 3 — For each claim record the rubric's fields**; for each **exclusion** record only the gate that caught it. Exclusions are data, not waste — their distribution is the health signal in rubric §7.

> **Verify:** report the four gate-failure rates. **If any is zero, re-read.** A gate that never fires is either unnecessary or not being applied, and rubric §7 says which is more likely.

**Step 4 — Have the rubric's worked examples checked against your own judgements.** If you disagree with rubric §6's calibration table, **stop and raise it with Louis** rather than proceeding — the rubric is wrong, or your reading is, and both are worth more than a labelled set built on a disagreement.

> **Verify:** state explicitly in the commit body that you applied §6 and agreed with it, or which row you disagreed with.

**Step 5 — Commit as `v2/fixtures/gold/<episode>.json`,** with the rubric's version or commit hash recorded in it.

> **Verify:** the file records which rubric produced it. **A gold set whose definition has drifted is worse than none** because it looks authoritative.

### Validation

- **(c)** — **every turn in the episode has a verdict** (claim with fields, or exclusion with a gate), the count matches B1's turn count exactly, and **the four gate-failure rates are all non-zero.** *An incomplete labelling measures precision only, which is the half V1 already had.*
- A second reader — Louis, or a fresh agent given only the rubric — labels **20 turns drawn at random** and agreement is reported. **Do not target a number; report it.** Low agreement means the rubric is ambiguous and that is a finding about the rubric.
- The claim count is stated plainly. **If one episode yields very few claims, say so** — that is a real result about the show and it changes what the product can be.

**Falsify.** Label 20 turns, set them aside, re-label them a day later without looking, and report self-agreement. **If you disagree with yourself, the rubric is underspecified** and no model will do better.

**Blast radius.** `v2/fixtures/gold/`, possibly `v2/docs/design_claim_rubric.md` if step 4 finds a defect.

---

## 8. B3 — Extract against the rubric · **DELIVERED**

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

## 9. B4 — Measure, and decide whether to go on · **DELIVERED**

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

**Blast radius.** `v2/docs/ongoing_errors.md`, `v2/docs/agent_execution_guide.md`.

---
## 10. B5 — A local page showing what was extracted, and what was not · **DELIVERED**

**Blocked on B1 only.** DELIVERED. Unblocks B6.

**User impact:** Louis can see what the pipeline did to the most recent episode, turn by turn, without running a query.

**Contract:** `v2/docs/design_claim_rubric.md` · B1's turn artefact · V1's `v1/scripts/serve_site.py` as a shape to copy, not code to import.

### The one design decision that matters

**Show the turns that produced nothing, and why.** V1's site listed claims and nothing else, so you could see precision by eye and never recall — which is exactly the half that was broken for the whole of V1. **A page that only shows claims cannot tell you what the pipeline threw away.**

Every turn appears. A turn either carries its claims or carries the gate that excluded it. **The gate distribution should be visible at a glance** — that is the health signal rubric §7 describes, and it is worth more than the claims themselves while the rubric is still being tuned.

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
## 11. B6 — Three local models on the same episode, and what agreement is worth

**Blocked on B5** — you need the viewer before three models' output is worth looking at, and B5 is the thing that makes disagreement legible.

**User impact:** a claim that three independently-trained models all call a claim is more trustworthy than one model's verdict. **How much more is the thing this item measures.**

**Contract:** `v2/docs/design_claim_rubric.md` · B2's gold set (405 labelled turns of E287) · guide §3 decision 4 — **local, open-weights, nothing leaves this machine**.

### What actually fits — measured on this machine, September 13 2026

**Mac Studio, M4 Max, 64 GB unified memory. `iogpu.wired_limit_mb` is 0 (default ≈ 48 GB available to the GPU) — a 30B-class 4-bit model needs ~18 GB, so it does not need raising.**

**The binding constraint is disk, not memory: 58 GB free of 460 GB.**

| family | biggest that fits | 4-bit size | note |
|---|---|---|---|
| **Gemma** | `gemma-4-31B` (dense, 30.7B active) | ~18 GB | Gemma 4, Apache 2.0, April 2026. `26B-A4B` (MoE, 3.8B active) is ~14 GB and runs at roughly 4B speed — **worth taking as well if throughput hurts** |
| **GLM** | `mlx-community/GLM-4-32B-0414-4bit` | ~18 GB | **GLM-4.5-Air does not fit** — 106B/12B needs **66.7 GB at Q4_K_M**, over both the RAM and the disk. GLM-4.6 needs ~205 GB |
| **Nemotron** | **`Nemotron 3 Nano`** — 31.6B total, **3B active** (hybrid Mamba-Transformer MoE) | ~18 GB | **This is the third slot.** Nemotron 3 Super is 120B/12B ≈ 65 GB — does not fit, same wall as GLM-4.5-Air. Ultra is 550B — no. |

**Three at ~18 GB is ~54 GB against ~57 GB free on the internal disk.** Two ways out, and the second is better if the hardware is there: **stage them** — pull one, run the episode, write the output, delete the weights, pull the next; outputs are small JSON and weights are not. **Or put the cache on an external SSD** and skip staging entirely, which is the preferred option since all three stay resident and can be re-run without re-downloading.

**External SSDs are a supported answer and remove the staging constraint entirely.** Point the caches at the volume and both runtimes follow:

```bash
export HF_HOME=/Volumes/<SSD>/hf          # MLX / transformers
export OLLAMA_MODELS=/Volumes/<SSD>/ollama # Ollama
```

**Weights load from the SSD into unified memory once; inference speed afterwards is unaffected by where they came from.** Thunderbolt (3–6 GB/s) loads an 18 GB model in seconds; USB 3.2 (~1 GB/s) takes ~20 s. **Neither changes tokens/sec.** Format the volume APFS or exFAT — not FAT32, which caps files at 4 GB and will corrupt a sharded download in a way that looks like a model bug.

> **Verify before pulling anything:** `df -h` on whichever volume the cache points at. **If free space is under ~25 GB, stop and say so** rather than filling the disk — a Mac that runs out mid-download fails in ways that are tedious to unpick. **Note that `df` can lag after a delete:** APFS Time Machine local snapshots hold freed space until macOS reclaims it under pressure, so a recent deletion may not show up. `tmutil listlocalsnapshots /` tells you whether that is what you are looking at.

### Inkling does not fit, and this is not a close call

**[Inkling](https://thinkingmachines.ai/news/introducing-inkling/)** (Thinking Machines Lab, July 2026) is **975B total / 41B active** MoE. **Inkling-Small** is **276B / 12B active**.

**MoE needs all weights resident, not just the active ones.** Inkling-Small at 4-bit is roughly **138 GB** — over twice this machine's total RAM, and more than twice its free disk. There is no quantisation that closes a gap that size without destroying the model.

**And finetuning it is not local either.** Inkling is designed to be customised through **Tinker**, Thinking Machines' hosted fine-tuning platform. That sends training data off this machine, which guide §3 decision 4 rules out. **Both halves of the Inkling idea — running it and tuning it — fail on this hardware and on the constraint.**

**Nemotron 3 Nano replaces Inkling in both roles, and is the better answer for the second one.** It fits at ~18 GB, its 3B active parameters make it fast enough to run 405 turns repeatedly, and **NVIDIA published the training data, the RL environments and the post-training recipes alongside the weights** under OpenMDW-1.1. **For a model you intend to finetune, published recipes are worth more than raw benchmark position** — it is the difference between adapting a known procedure and reverse-engineering one.

**Finetuning is live, locally, on the right model.** A 30B-class LoRA runs on 64 GB under MLX, and **B2's 405 hand-labelled turns are exactly the shape a narrow-task LoRA wants** — small, consistent, single-domain. **Do not start it inside this item.** Measure the three base models first; if one is close and its errors are systematic, file the LoRA as its own issue with the base-model numbers attached. **On current evidence Nemotron Nano is the candidate**, on recipe availability rather than on any measurement yet taken.

### Why three labs rather than three sizes

Agreement is only evidence when the things agreeing are independent. **Gemma (Google), GLM (Zhipu) and a third lab's model give three different pretraining corpora and three different instruction-tuning regimes.** Three Gemma sizes would agree with each other for reasons that have nothing to do with the claim being real.

**And the failure mode to keep in view: models sharing an architecture or data lineage agree on the same mistakes.** Consensus measures reliability only if it is itself checked against the gold set. **It is not a substitute for B2** — a claim all three models call a claim, that the gold set says is not one, is exactly the case worth finding.

### Implementation

**Step 1 — Run each model over all 405 turns of E287, same rubric prompt, byte-identical.** No per-model prompt tuning. A prompt adjusted per model makes the comparison meaningless, which is the same reason V1's model experiment required an empty prompt diff.

> **Verify:** paste the prompt hash for each run and confirm all three match. **Record model id, quantisation, runtime and rubric commit hash** per guide §3, in the output file.

**Step 2 — Record per-model output in the same shape as B3's**, so B5 renders it without special-casing.

> **Verify:** B5 displays all three side by side on one turn. If it needs a new template per model, the output shapes have diverged and later comparison will be arithmetic on incompatible things.

**Step 3 — Compute the agreement table against the gold set.** For each of the four cells — all three agree claim, all three agree not, two-one split, and every other combination — report **how often the gold set says they were right.**

> **Verify:** this is the item's whole product. **Report precision for unanimous-claim, for 2-1 majority, and for any-model-says-claim**, all against B2's 33 gold claims. If unanimous precision is not clearly higher than single-model precision, **consensus is not buying anything and the item should say so plainly.**

**Step 4 — Read the disagreements.** Specifically the turns where models split 2-1, and every turn all three called a claim that the gold set does not contain.

> **Verify:** list them by turn id in the commit body and say what they have in common. **A shared false positive across three labs is the most interesting row in this experiment** — it says the rubric is ambiguous, not that the models are weak.

**Step 5 — Report throughput honestly.** Wall-clock per model for 405 turns. A model that is twice as good and ten times slower is a different decision from one that is twice as good and equally fast.

### Validation

- **(c)** — **precision and recall reported for each model individually and for the unanimous, majority and any-model consensus rules, all against B2's gold set**, with every disagreement listed by turn id. *Three models' raw output is not a result; the comparison against a human-labelled set is. Without the gold column this item produces three opinions and no way to rank them.*
- All three runs used a byte-identical prompt — hashes pasted.
- Model id, quantisation, runtime and rubric hash recorded per run.
- Disk free reported before and after; **no weights left resident for models no longer being compared.**
- **Nothing left this machine.** Assert no network calls beyond the model download.

**Falsify.** Run one model twice with different seeds or at a different temperature and report the agreement between the two runs. **If a model agrees with itself less than the three models agree with each other, the consensus signal is noise** and the whole approach needs rethinking before it is built on.

**Blast radius.** `v2/src/`, `v2/artifacts/extraction/`, model weights on disk (staged, then removed). **No changes to the rubric, the gold set, or V1.**

---
## 12. Standing constraints, carried from V1

- **One item = one commit**, the *why* in the body.
- **Never fill in a `Your selection: _____` line.**
- **Quote the item's `(c)` verbatim in the commit body and answer it with a number beside its target.** `(c)` failing is a legitimate outcome; recording a different assertion as `(c)` is not.
- **When an assertion cites rows, cite primary keys that resolve in the store.** V1 ended with forty pasted claim ids, none of which existed.
- **Every `> **Verify:**` step is answered in the commit body, including the ones you skipped, marked as skipped with a reason.**
- **A guard that has never failed has not been tested.**
- **Local, open-weights models only. No hosted API; no transcript leaves this machine.** If an item appears to need one, that is a question for Louis, not a decision to take mid-item.
- **Exhaust what is installed before proposing a download or a dependency.** B3 concluded "local extraction fails" from a 2B model while an 8B sat pulled and unused.
- **Read the output a person would read, not the aggregate.** V1 published five fabrications past complete, honest, passing metrics.

---

## 13. Traps (carried from V1 §7)

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
74. **A pasted artefact is only better than a count if somebody resolves it.** X4 pasted forty claim ids with quotes and verdicts, exactly as its `(c)` required, and none of the forty exists. The convention that was supposed to make judgement checkable made it *look* checkable. **When an assertion cites rows, cite primary keys and make a script resolve them** (§13) — and note that the same commit's aggregate counts were all exactly correct, so "the numbers are right" is not evidence the sample is.
75. **Aggregate accuracy and sample accuracy are independent.** Every count in that commit matched the database to the row; the qualitative sample was not drawn from it. **Check them separately** — a commit that gets the hard numbers right earns no credit for the soft ones.
76. **Five attempts at the same fix in different clothes is a signal about the approach, not the wording.** W0/W2 → D1 → D6 → X2 → X4 each removed one failure and produced another, and the corpus fell from 3,669 claims to 401. **When the third iteration of anything lands, stop and ask what is being assumed** — here, that the format was the limiting factor, which nobody had measured (Issue 035).
71. **A format that must emit something will invent what it needs.** D6's form produced propositions nobody could take a position on; X2's format produces positions nobody took, and almost always `FOR`, because the binary has no null. **Every extraction format needs a branch that returns nothing**, and it has to be reachable — "a claim it cannot phrase that way is not emitted" is not a branch if the phrasing always succeeds.
72. **"Not zero" is as weak a floor as zero.** D8's (c) required the count of opposing-stance propositions to be reported and said a zero would mean the self-join had nothing to match. It came back **one**, which satisfied the letter while the singleton rate went to 99.5%. **State floors as rates over the table** — the same correction Parameter 033 made to "no source contributes zero claims" (trap 61), repeated one layer up by the person who wrote trap 61.
73. **Report the cost of a fix, not only its benefit.** D8 drove frame-contradicted merges to zero and did not report that it did so by merging almost nothing. Both numbers existed and one was asked for. **When a threshold trades two quantities against each other, the item must require both at every candidate value** — a single-sided report makes a corner solution look like a win.
69. **Storing the judgement turns the next check into code.** Three fabrications needed a careful read of quotes to spot. The fourth is a two-line diff of `position_frame`, because X2 persisted the sentence the model wrote instead of only its conclusion. **When a step depends on a judgement, store the artefact the judgement was made from** — the next person gets a query instead of an opinion.
70. **A parameter measured on a distribution that a later item replaces is stale on the day that item lands.** `T_dedup = 0.84` was measured over v1.7 propositions and merged *"60 to 80 percent growth"* with *"10x growth for ever"* on v1.8 output. X2 correctly refused to retune it in the same commit; **the cost of that discipline is a follow-up item, and it must actually be filed** (§15).
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

## 14. Validation standard (carried from V1 §9)

**This section is the difference between an item that lands and one that comes back.** Every rule below was paid for.

**Read the output a human would read, not the aggregate.** Three fabrications have shipped past complete, honest, passing metrics. Merge histograms looked healthy while the pairs built on them were false; candidate counts rose while the rate stayed flat. **If your item's product is a claim about a person, read some of those claims before you call it delivered.**

**Draw test data; do not compose it.** A hand-written set tests the mechanism you had in mind. Twelve composed stance cases scored 6/6 both directions with zero confusion, and a random sample of the live corpus was wrong 4 out of 4. **Sample from the corpus, fix the sample, version it, and report a confusion matrix rather than an accuracy.**

**State assertions as rates over the table when the table is also changing.** "Rises materially above 4" was satisfied by a rounding error once the corpus tripled — while 95.5% of propositions stayed singletons, which was the thing that mattered.

**Name the configurations a guard must hold in, then test the awkward one.** The review site's read-only connection raised on `INSERT` in the fixture's configuration and wrote happily in the one you actually run. Both were true; only one was tested.

**Grep for the writer before trusting the reader.** `sufficiency.get("passed", True)` read its own default nine times against an engine that never wrote that key. A `.get(key, default)` on a key nobody writes is an unused parameter one layer down.

**Check the parameter is referenced in the body, not just the signature.** `verify_source_productivity(min_ratio=0.05)` never mentioned `min_ratio` again.

**A guard that has never failed has not been tested, and a guard that fires in only one direction has not been shown to discriminate.** Count corrections and rejections by direction. An *n*:0 ratio is a finding.

**Record what a parameter was measured over.** `T_dedup = 0.86` cites similarities between strings that three later items removed from the database. A threshold outlives its distribution and nothing notices.

**A stage not named in the instruction does not run.** "Re-ingest" is not "re-extract"; "fix the validator" is not "re-score the rows it already scored". If your item exists to feed a later stage, name that stage's re-run as a step and assert a property of *its* input.

**Verify the anchor chain end to end, not the pointer.** "Is this citation real?" and "does this citation support this claim?" are different questions, and for a long time only the first was asked.

**Prove the threshold is doing the work.** Set it to a value that must fail, watch the assertion go red, restore it. Record both outputs in the commit body. A repair with no falsification is a guess.

**Re-run every gate yourself before trusting §10.** This file has recorded a gate result that did not match reality more than once.

**Report zero with its denominator.** "No tensions found" over an empty candidate set and "no tensions found" over 400 examined pairs look identical in a status table and mean opposite things.

**Answer the assertion that was written, not the one you can satisfy.** An item's `(c)` is a sentence with a number in it. Quote it, measure it, put the two side by side. Every other form of reporting — a passing test whose name references it, a narrative that mentions the metric elsewhere, a summary that says "verified" — has been used here to record a failed assertion as met, without anyone intending to.

**When you substitute anything for what the item specifies — a different mechanism, a narrower scope, a value the item did not name — say so in the commit body.** Several items here were delivered exactly as written and still wrong; the substitution log is how the next verification pass finds out which.


---

## 15. Invariants — do NOT change (carried from V1 §15)

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

## 16. Deliberately not built — do not re-propose (carried from V1)

Each of these was considered and rejected for a stated reason in `v1/docs/master_implementation_plan.md` §14. Re-proposing one costs a cycle.

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

## 17. Evidence integrity and V1 reference contracts

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
