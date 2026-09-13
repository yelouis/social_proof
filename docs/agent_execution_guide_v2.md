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

- **The traps (V1 guide §6, all 76)** and **the validation standard (§8)**. These are the accumulated record of how this project has fooled itself, and every one was paid for. **Copy them into `v2/docs/agent_execution_guide.md` verbatim**, keeping their numbering so V1's commit messages still resolve.
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

> **Verify:** trap count in `v2/docs/agent_execution_guide.md` equals the count in `v1/docs/agent_execution_guide.md`. **Assert the numbers, not just the count** — a renumbered trap breaks every commit message that cites it.

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

## 5. Traps and validation standard

**Carried from V1 by R0 step 3. Until R0 lands, read them at `docs/agent_execution_guide.md` §6 and §8.**

They are the most valuable artefact V1 produced, and they are not about V1's architecture — they are about how a careful agent working alone arrives at a confident wrong answer. **Read them before writing anything, in V2 as in V1.**
