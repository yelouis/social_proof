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

## 2. R0 — Split the repository into `v1/` and `v2/`

**User impact:** none. This is the item that makes it possible to start over without deleting the record.

### What goes where, and the one judgement that matters

**`v1/` is reference. `v2/` is the build.** The split is not a straight move, because **the most valuable thing V1 produced is not its code.**

**Move into `v1/` — reference only, do not extend:**

```
v1/worker/        v1/scripts/       v1/tests/        v1/fixtures/
v1/golden/        v1/extension/     v1/artifacts/    v1/social_proof.duckdb
v1/docs/          (all 13 design docs + the V1 execution guide + ongoing_errors.md)
v1/conftest.py    v1/pyproject.toml (a copy — see step 4)
```

**Carry forward into `v2/` — these are not version-specific and must not be archived:**

- **The traps (V1 guide §6 — numbered 17–76, 62 present; 1–16 live in commit `217b383`)** and **the validation standard (§8)**. These are the accumulated record of how this project has fooled itself, and every one was paid for. **Copy them into `v2/docs/agent_execution_guide.md` verbatim**, keeping their numbering so V1's commit messages still resolve.
- **The invariants (V1 guide §16)** — I1–I10. They are claims about the product, not about the pipeline.
- **`docs/master_implementation_plan.md` §8**, the deliberate non-goals. Re-proposing one costs a cycle.
- **`design_evidence_integrity.md`** in full. Quarantine semantics, the anchor chain, and *"evidence about the store must be resolvable against the store"* survive any rewrite of extraction.

**Leave at the repository root:** `README.md`, `.gitignore`, `.github/`, `.venv/`.

> **Verify:** after the move, `grep -rn "worker\." v2/ --include="*.md"` returns nothing that points at V1 code paths. **A V2 doc that references `worker/extract/` has imported V1's assumptions along with its path.**

### Steps

**Step 1 — Move with `git mv`, one commit, no edits.** Content changes in the same commit as a move make the diff unreadable and hide what was altered.

> **Verify:** `git show --stat` shows renames only — no insertions or deletions beyond the rename lines. If content changed, split the commit.

**Step 2 — Create the V2 skeleton.**

```
v2/docs/agent_execution_guide.md     ← this file, moved here
v2/docs/                             ← V2 design docs, written later, not now
v2/                                  ← no code yet
```

> **Verify:** `v2/` contains documentation and nothing else. **Do not scaffold a package, a worker, or a schema.** The extraction approach is undecided and any scaffold will encode an assumption about it.

**Step 3 — Copy the carry-forward material into `v2/docs/agent_execution_guide.md`.** Traps verbatim with numbering intact, the validation standard verbatim, the invariants, and a pointer to `v1/docs/` for everything else.

> **Verify:** **62 traps, numbered 17–76 with no gaps introduced**, matching `v1/docs/agent_execution_guide.md` number by number. Traps 1–16 are not in that file — they live at `217b383:docs/agent_execution_guide.md` §1 and the V1 guide points there; carry the pointer, not the text. **Assert the numbers, not just the count** — a renumbered trap breaks every commit message that cites it.

**Step 4 — Make V1 runnable but inert.** The review site is the only part of V1 worth still being able to start. Keep `v1/pyproject.toml` and `v1/scripts/serve_site.py` working with paths adjusted; confirm the site still serves.

> **Verify:** `cd v1 && .venv/bin/python scripts/serve_site.py` serves the site and `/` returns 200 with 23 episodes listed. **If you cannot make this work in fifteen minutes, stop and say so** — V1 being startable is a convenience, not a requirement, and it is not worth restructuring the package to get.

**Step 5 — Update the README.** One short section: V1 is the reference implementation and what it established; V2 is the rebuild and what it is rebuilding. **Link the three root causes in §1 above** rather than restating them.

> **Verify:** a reader who has never seen this repo can tell from the README which directory is live. That is the whole job of this step.

### Validation

- **(c)** — **`git log --follow` resolves for a file moved into `v1/`** (try `v1/worker/extract/validators.py`), and the trap numbering in `v2/docs/agent_execution_guide.md` matches `v1/`'s exactly, asserted number by number. *History-preservation is the entire point of moving rather than copying, and trap numbering is the entire point of carrying them forward rather than rewriting them. A move that breaks either has thrown away what it was protecting.*
- `v2/` contains no code.
- The V1 site starts and serves, or the commit body says why it does not.
- Nothing under `v1/` was edited in the move commit.

**Falsify.** Check out the commit before R0 and confirm the tree is unchanged from it apart from paths — `git diff --stat <before> <after> -M` should report renames and the two new/edited docs, nothing else.

**Blast radius.** Every path in the repository. `README.md`. No code logic.

---

## 3. What happens after R0

**Nothing, until Louis selects an extraction approach.** The candidates are being discussed now; the shortlist and their trade-offs will be filed in `v2/docs/ongoing_errors.md` §1 as an open issue with a `Your selection: _____` line.

**Two things are already known to be prerequisites regardless of which is chosen**, and the second matters more than it sounds:

1. **The extraction unit must be larger than one ASR line.** Turn-level at minimum. This is V1's root cause ① and no format choice survives ignoring it.
2. **A human-labelled gold set must exist before any threshold is tuned.** V1 set six parameters and ran five format rewrites without one, and every gate it reported was scored against its own output. **Build the labelled set first, from V1's existing transcripts** — they are real, they are verbatim-verified, and they cost nothing to reuse. **This is the one piece of V1 worth taking wholesale.**

**Do not begin either without the selection.** Both shape what a claim *is*, and that is the decision being made.

---

## 4. Standing constraints, carried from V1

- **One item = one commit**, the *why* in the body.
- **Never fill in a `Your selection: _____` line.**
- **Quote the item's `(c)` verbatim in the commit body and answer it with a number beside its target.** `(c)` failing is a legitimate outcome; recording a different assertion as `(c)` is not.
- **When an assertion cites rows, cite primary keys that resolve in the store.** V1 ended with forty pasted claim ids, none of which existed.
- **Every `> **Verify:**` step is answered in the commit body, including the ones you skipped, marked as skipped with a reason.**
- **A guard that has never failed has not been tested.**
- **Read the output a person would read, not the aggregate.** V1 published five fabrications past complete, honest, passing metrics.

---

## 5. Traps (carried from V1 §6)

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

## 6. Validation standard (carried from V1 §8)

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

**Re-run every gate yourself before trusting §4.** This file has recorded a gate result that did not match reality more than once.

**Report zero with its denominator.** "No tensions found" over an empty candidate set and "no tensions found" over 400 examined pairs look identical in a status table and mean opposite things.

**Answer the assertion that was written, not the one you can satisfy.** An item's `(c)` is a sentence with a number in it. Quote it, measure it, put the two side by side. Every other form of reporting — a passing test whose name references it, a narrative that mentions the metric elsewhere, a summary that says "verified" — has been used here to record a failed assertion as met, without anyone intending to.

**When you substitute anything for what the item specifies — a different mechanism, a narrower scope, a value the item did not name — say so in the commit body.** Several items here were delivered exactly as written and still wrong; the substitution log is how the next verification pass finds out which.


---

## 7. Invariants — do NOT change (carried from V1 §16)

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

## 8. Deliberately not built — do not re-propose (carried from V1)

Each of these was considered and rejected for a stated reason in `v1/docs/master_implementation_plan.md` §8. Re-proposing one costs a cycle.

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

## 9. Evidence integrity and V1 reference contracts

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
