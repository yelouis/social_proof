# Agent Execution Guide — V2: rebuild claim extraction from the unit up — September 13, 2026

**You are an engineering agent with no memory of this project.**

**V1 is finished and is not being continued.** It ingested 23 episodes, produced 401 claims, and never found a single contradiction that survived being read. Five consecutive rewrites of the extraction format each fixed one failure and produced another. **V1's pipeline is reference material; do not extend it, do not repair it, and do not import its extraction code into V2 without a stated reason.**

**Exactly one item is queued: R0, the restructure.** Nothing else starts until the repository is split and this file lives at `v2/docs/agent_execution_guide.md`. **V2's design work has not been decided yet** — Louis is brainstorming the extraction approach, and the second item will be filed once he selects one. **Do not invent it.**

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

**Validation is one All-In episode, labelled by hand, end to end.** Not a sample — **recall is the half V1 could never see**, and a sample measures only precision.

**What is deliberately NOT decided:** whether a claim-detection library earns a place. TARGER, MARGOT and Canary are research artefacts trained on written argumentative prose, not disfluent multi-speaker ASR; ClaimBuster has a live API but scores *check-worthiness for fact-checking*, which is a different question from *did this speaker commit to a position*. **Borrow the claim/premise taxonomy if it helps; do not add a dependency without measuring it against B2's gold set first.**

---

## 4. Queue

| Order | ID | Item | Blocked | Why here |
|---|---|---|---|---|
| 1 | **B1** | Turns, and how much of this show is question-anchored | none | DELIVERED. V1's unit was 12 words. Measured 11.13% question-anchored share. |
| 2 | **B2** | Label one episode by hand | B1 | DELIVERED. Hand-labelled 405 turns of E287; 33 claims, 372 exclusions across all 4 gates. |
| 3 | **B3** | Extract against the rubric | B2 | DELIVERED. Evaluated rubric prompt and stripped falsification prompt across all 405 turns. |
| 4 | **B4** | Measure, and decide whether to go on | none | Precision and recall on one episode, then a decision, not a task. |

**Do not reorder these and do not start two at once.** V1's worst outcomes came from items that were individually correct and sequenced wrong — a publishing item run before the thing it published was real, a threshold tuned over claims that were fabricated.

---

## 5. B1 — Turns, and how much of this show is question-anchored · **DELIVERED**

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

## 6. B2 — Label one episode by hand · **DELIVERED**

**Blocked on B1.** DELIVERED. Unblocks B3.

**User impact:** every threshold, prompt and gate after this becomes measurable instead of self-reported.

**Contract:** `v2/docs/design_claim_rubric.md` in full.

**Gap.** V1 set six parameters and ran five format rewrites without a single human-labelled example. Five gates were self-reported as met and disagreed with on independent reading; one pasted forty claim ids as evidence and **none of them existed.** **There was never anything to be wrong against.**

### Implementation

**Step 1 — Pick one episode and say why.** A regular four-host episode, not a guest interview — guests are excluded by gate 1 and a guest-heavy episode measures the wrong thing.

**Step 2 — Read the whole episode's turns and mark every claim.** Not a sample. **Every turn**, start to finish, applying the rubric's four gates in order.

> **Verify:** the count of turns examined equals the count of turns in the episode. **Recall is the whole point** — a sample tells you whether what you found is good and nothing about what you missed, and missing is V1's failure mode.

**Step 3 — For each claim record the rubric's fields**; for each **exclusion** record only the gate that caught it. Exclusions are data, not waste — their distribution is the health signal in rubric §6.

> **Verify:** report the four gate-failure rates. **If any is zero, re-read.** A gate that never fires is either unnecessary or not being applied, and rubric §6 says which is more likely.

**Step 4 — Have the rubric's worked examples checked against your own judgements.** If you disagree with rubric §5's calibration table, **stop and raise it with Louis** rather than proceeding — the rubric is wrong, or your reading is, and both are worth more than a labelled set built on a disagreement.

> **Verify:** state explicitly in the commit body that you applied §5 and agreed with it, or which row you disagreed with.

**Step 5 — Commit as `v2/fixtures/gold/<episode>.json`,** with the rubric's version or commit hash recorded in it.

> **Verify:** the file records which rubric produced it. **A gold set whose definition has drifted is worse than none** because it looks authoritative.

### Validation

- **(c)** — **every turn in the episode has a verdict** (claim with fields, or exclusion with a gate), the count matches B1's turn count exactly, and **the four gate-failure rates are all non-zero.** *An incomplete labelling measures precision only, which is the half V1 already had.*
- A second reader — Louis, or a fresh agent given only the rubric — labels **20 turns drawn at random** and agreement is reported. **Do not target a number; report it.** Low agreement means the rubric is ambiguous and that is a finding about the rubric.
- The claim count is stated plainly. **If one episode yields very few claims, say so** — that is a real result about the show and it changes what the product can be.

**Falsify.** Label 20 turns, set them aside, re-label them a day later without looking, and report self-agreement. **If you disagree with yourself, the rubric is underspecified** and no model will do better.

**Blast radius.** `v2/fixtures/gold/`, possibly `v2/docs/design_claim_rubric.md` if step 4 finds a defect.

---

## 7. B3 — Extract against the rubric · **DELIVERED**

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

## 8. B4 — Measure, and decide whether to go on

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
## 9. Standing constraints, carried from V1

- **One item = one commit**, the *why* in the body.
- **Never fill in a `Your selection: _____` line.**
- **Quote the item's `(c)` verbatim in the commit body and answer it with a number beside its target.** `(c)` failing is a legitimate outcome; recording a different assertion as `(c)` is not.
- **When an assertion cites rows, cite primary keys that resolve in the store.** V1 ended with forty pasted claim ids, none of which existed.
- **Every `> **Verify:**` step is answered in the commit body, including the ones you skipped, marked as skipped with a reason.**
- **A guard that has never failed has not been tested.**
- **Read the output a person would read, not the aggregate.** V1 published five fabrications past complete, honest, passing metrics.

---

## 10. Traps (carried from V1 §6)

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
74. **A pasted artefact is only better than a count if somebody resolves it.** X4 pasted forty claim ids with quotes and verdicts, exactly as its `(c)` required, and none of the forty exists. The convention that was supposed to make judgement checkable made it *look* checkable. **When an assertion cites rows, cite primary keys and make a script resolve them** (§12) — and note that the same commit's aggregate counts were all exactly correct, so "the numbers are right" is not evidence the sample is.
75. **Aggregate accuracy and sample accuracy are independent.** Every count in that commit matched the database to the row; the qualitative sample was not drawn from it. **Check them separately** — a commit that gets the hard numbers right earns no credit for the soft ones.
76. **Five attempts at the same fix in different clothes is a signal about the approach, not the wording.** W0/W2 → D1 → D6 → X2 → X4 each removed one failure and produced another, and the corpus fell from 3,669 claims to 401. **When the third iteration of anything lands, stop and ask what is being assumed** — here, that the format was the limiting factor, which nobody had measured (Issue 035).
71. **A format that must emit something will invent what it needs.** D6's form produced propositions nobody could take a position on; X2's format produces positions nobody took, and almost always `FOR`, because the binary has no null. **Every extraction format needs a branch that returns nothing**, and it has to be reachable — "a claim it cannot phrase that way is not emitted" is not a branch if the phrasing always succeeds.
72. **"Not zero" is as weak a floor as zero.** D8's (c) required the count of opposing-stance propositions to be reported and said a zero would mean the self-join had nothing to match. It came back **one**, which satisfied the letter while the singleton rate went to 99.5%. **State floors as rates over the table** — the same correction Parameter 033 made to "no source contributes zero claims" (trap 61), repeated one layer up by the person who wrote trap 61.
73. **Report the cost of a fix, not only its benefit.** D8 drove frame-contradicted merges to zero and did not report that it did so by merging almost nothing. Both numbers existed and one was asked for. **When a threshold trades two quantities against each other, the item must require both at every candidate value** — a single-sided report makes a corner solution look like a win.
69. **Storing the judgement turns the next check into code.** Three fabrications needed a careful read of quotes to spot. The fourth is a two-line diff of `position_frame`, because X2 persisted the sentence the model wrote instead of only its conclusion. **When a step depends on a judgement, store the artefact the judgement was made from** — the next person gets a query instead of an opinion.
70. **A parameter measured on a distribution that a later item replaces is stale on the day that item lands.** `T_dedup = 0.84` was measured over v1.7 propositions and merged *"60 to 80 percent growth"* with *"10x growth for ever"* on v1.8 output. X2 correctly refused to retune it in the same commit; **the cost of that discipline is a follow-up item, and it must actually be filed** (§14).
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

## 11. Validation standard (carried from V1 §8)

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

**Re-run every gate yourself before trusting §9.** This file has recorded a gate result that did not match reality more than once.

**Report zero with its denominator.** "No tensions found" over an empty candidate set and "no tensions found" over 400 examined pairs look identical in a status table and mean opposite things.

**Answer the assertion that was written, not the one you can satisfy.** An item's `(c)` is a sentence with a number in it. Quote it, measure it, put the two side by side. Every other form of reporting — a passing test whose name references it, a narrative that mentions the metric elsewhere, a summary that says "verified" — has been used here to record a failed assertion as met, without anyone intending to.

**When you substitute anything for what the item specifies — a different mechanism, a narrower scope, a value the item did not name — say so in the commit body.** Several items here were delivered exactly as written and still wrong; the substitution log is how the next verification pass finds out which.


---

## 12. Invariants — do NOT change (carried from V1 §14)

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

## 13. Deliberately not built — do not re-propose (carried from V1)

Each of these was considered and rejected for a stated reason in `v1/docs/master_implementation_plan.md` §13. Re-proposing one costs a cycle.

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

## 14. Evidence integrity and V1 reference contracts

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
