# Agent Execution Guide — Active Build: first real ingest, then Phases 3–8 — August 17, 2026

**You are an engineering agent with no memory of this project. This document is self-driving: it contains the prompts you issue to yourself.**

Do not read this end to end and improvise. **Go to §1, run LOOP 0, let it route you.**

**Where the project is.** X0 is delivered and its work holds — the fabricated tension is quarantined and the 9 surviving claims are verbatim and genuinely supported. But a verification pass on **September 4, 2026** found a red gate and five defects the docs did not know about, and **`mypy` is RED at HEAD**.

**What that means for you.** Start at **G0** (§17b): the gate repair. Nothing else begins until it is green. Then M0 and E0 — two items about numbers and checks that look like measurements and are not. **X1 and R1 are both blocked on Issue 027**, which is open and needs a selection. Read §3 and §5 traps 28–34 before anything else. **Do not treat P4–P7's green status as evidence they work** — the one tension they have ever produced was wrong, and the integrity pass that certifies them has never examined a real assessment (§17d).

**Every number, threshold, field name and literal string in the design docs is deliberate. Implement as written.** Where a doc says a value must be *measured* (`ongoing_errors.md` §2), measure it.

---

## The loops

| Loop | When | §
|---|---|---|
| **LOOP 0 — ORIENT** | Start of every session | §1 |
| **LOOP 1 — IMPLEMENT** | Per work item | §7 |
| **LOOP 2 — FALSIFY** | Inside LOOP 1, mandatory | §8 |
| **LOOP 3 — ESCALATE** | Blocked, or a decision is the user's | §9 |
| **LOOP 4 — CLOSE OUT** | Queue empty | §10 |
| **LOOP 5 — DECOMPOSE** | Item too big for one commit | §11 |
| **LOOP 6 — RESUME** | Context reset mid-item | §12 |
| **LOOP 7 — REPAIR** | A gate went red | §13 |

---

## 1. LOOP 0 — ORIENT

```text
LOOP 0 — ORIENT

1. Run the state-detection block in §2. Read its output.

2. Is the working tree dirty (uncommitted changes)?
     YES -> enter LOOP 6 (RESUME, §12). Someone stopped mid-item. Do not
            start new work on top of half-finished work.
     NO  -> continue.

3. Compare gate results to the baseline in §3.
     Any gate RED that §3 records PASS -> enter LOOP 7 (REPAIR, §13).
     All match                          -> continue.

4. Read the queue in §6. Walk it top to bottom. Select the FIRST row where
   status is NOT one of {delivered, superseded} AND blocked_on == none.
   Set ITEM.

   "superseded" means the row's remaining work is tracked under another ID.
   It is not a to-do. Do not open it; the row names its successor.

5. No such row -> LOOP 4 (CLOSE OUT, §10). Stop.

6. Read ITEM's own section in full. Read every contract doc it cites.
   The guide points; the doc specifies. Reading only the guide is not enough.

7. Estimate: can ITEM land as ONE commit with one coherent message?
     NO  -> enter LOOP 5 (DECOMPOSE, §11). It returns a sub-item; use that.
     YES -> enter LOOP 1 (IMPLEMENT, §7) with ITEM.
```

---

## 2. State detection

```bash
#!/usr/bin/env bash          # run under bash: compgen is a bash builtin
cd "$(git rev-parse --show-toplevel)"
echo "=== HEAD ==="   && git log --oneline -1
echo "=== DIRTY? ===" && git status --porcelain | head
echo "=== GATES ==="
.venv/bin/python -m ruff  check worker/ tests/ fixtures/ golden/ 2>&1 | tail -2
.venv/bin/python -m mypy        worker/ tests/ fixtures/ golden/ 2>&1 | tail -2
.venv/bin/python -m pytest tests/ -q                             2>&1 | tail -3
echo "=== STUBS (must be EMPTY) ==="
.venv/bin/python -c "from worker import STUB_REGISTRY; print(STUB_REGISTRY or 'EMPTY')"
echo "=== CORPUS: has anything real been ingested? ==="
# NB: use [ -e ] tests, not `ls ... | head || echo` — the || binds to head,
# which always succeeds, so the negative branch would never fire.
compgen -G "*.duckdb" >/dev/null && ls -1 *.duckdb || echo "  NO DATABASE — I0 not delivered"
[ -d artifacts ] && ls -1 artifacts | head -3      || echo "  NO ARTIFACTS — I0 not delivered"
echo "=== PHASE MODULES ==="
for m in topics tension principles rubric api; do
  { [ -e "worker/$m" ] || [ -e "worker/$m.py" ]; } && echo "  $m: built" || echo "  $m: MISSING"
done
echo "=== GOLDEN CORPUS SIZE (drives every metric floor) ==="
.venv/bin/python -c "
import json,os
for p in ['golden/cases.json','fixtures/behaviour/cases.json']:
    d=json.load(open(p)) if os.path.exists(p) else []
    c=d if isinstance(d,list) else d.get('cases',[])
    print(f'  {p}: {len(c)}')"
echo "=== OPEN SELECTIONS ==="
# Open issues live at the TOP of ongoing_errors.md section 1, newest first.
grep -c "^Your selection: _____" docs/ongoing_errors.md   # anchored — unanchored also matches the rules line
```

**Interpreting it:**

| Signal | Means |
|---|---|
| dirty tree | Someone stopped mid-item → LOOP 6 |
| `STUB_REGISTRY` non-empty | A V-item regressed. Should be `EMPTY`. |
| `NO DATABASE` | **I0 not delivered.** Nothing real has been processed. |
| a phase module `MISSING` | Its P-item is outstanding, whatever any commit says. |
| `golden/cases.json: 0` | Every corpus metric is `NOT MEASURED`. Expected until subjects are ingested. |
| pytest under ~5s | Impossible now — real models are loaded. Under 5s means something got mocked out. |
| open selections > 0 | A blocker appeared. It is at the **top** of `ongoing_errors.md` §1 — read it there, then check §6 for which rows it blocks. |

**The filesystem and `STUB_REGISTRY` are the authority.** Not this guide's prose, not commit messages, not the baseline table.

---

## 3. Verified baseline

Measured **September 4, 2026** at `5f881ea`. Re-run via §2 before trusting.

| Gate | Result | Note |
|---|---|---|
| `ruff check` | **PASS** | |
| `mypy --strict` | **PASS** — clean on 78 files | Repaired in G0 (narrowed `Claim | None` and `quote_text` in `tests/test_segmentation_x0.py`). |
| `pytest tests/ -q` | **PASS** — 167 passed in **99s** | `requires_models` tests ran (not skipped, no deselection in `addopts`). ~99s is well above trap 18's 35s floor. |
| `STUB_REGISTRY` | **EMPTY** | All V-items genuinely delivered. |
| `worker.integrity --all` | **PASS — independent populations** | 12 checks evaluated. FIXTURES and CORPUS reported separately without unioning. `verify_canonical_ids` and `verify_quarantined_propositions_unreachable` both PASS. Real assessments loaded (9 checked). |
| `worker.golden.report` | **PASS** | Fixtures 19/19 (all 17 classes). Corpus metrics `NOT MEASURED — n=0`. Correct and honest. |
| **CI / Portability** | **PASS** | `portability.yml` tests base install without Apple extra; runs lint, mypy, and non-model tests (134 passed in ~12s). |
| **Corpus** | **POPULATED, PARTIALLY REPAIRED** | 4 sources, **361 utterances**, 9 claims, 12 propositions, 9 assessments. The silent-failure bug **is** fixed. But each source covers only **~416.5s of a 60–90 min episode** (~7.7%), and `verify_source_productivity` does not catch it. **Cause found — `scripts/populate_corpus.py:259` caps the download at 10MB via an HTTP `Range` header.** See §19; do not go hunting for it again. |
| **Propositions** | **REPAIRED (D0 DELIVERED)** | 12 propositions total, 8 carrying live claims all embedded with `nomic-embed-text-v1.5` via `embed_document`. 4 orphaned/quarantined rows. `claim_count` matches real claims on every row. Three forked rows merged/updated. Fabricated proposition `db3ec63d33cf6f0a` quarantined. `/resolve` filters structurally for `status = 'active'` and live claims existence. Issue 027 = A; item D0 delivered. |
| **`source_count`** | **MEASURED** | Sacks and Friedberg record 2; Jason and Chamath record 1. Resolved through utterance anchor chain, `hasattr` removed, I3 anchor-chain violation raises if unresolvable. Item M0 delivered. |
| **Published tension** | **QUARANTINED — X0 delivered** | Tension `0068adec4b1501c6` is `status='quarantined'`, `quarantine_reason='fabricated_proposition'`, and its two claims are gone. Verified. The 9 surviving claims were read individually: quotes are verbatim and the propositions are genuinely supported. The fabricated proposition `db3ec63d33cf6f0a` is quarantined and unreachable from `/resolve`. |

---

## 4. Standing constraints

- **One item = one commit**, the *why* in the body. Too big → LOOP 5.
- **Never fill in a `Your selection: _____` line.**
- **A stub is not a delivery.** Real dependency runs, or it isn't done.
- **Dependencies land in `pyproject.toml` in the same commit.**
- **Never print a number you did not measure.** Constants, projections from constants, and metrics below their floor render `NOT MEASURED`.
- **Every integration item needs one assertion a stub cannot satisfy** (trap 17). The single most important rule here.
- **A guard that has never failed has not been tested.** LOOP 2 is mandatory.
- **All writes go through the worker** (I8). **No LLM at scoring time.** **Audio deleted after transcription** (Issue 003). **DuckDB is the only store** (Issue 015).
- **Update every doc your change invalidates, in the same commit.**
- **`ongoing_errors.md` is a queue, not an archive.** File new issues at the **top** of §1. When one is selected, move it out: write the consequence into the design doc that owns it, add a row to §4, delete the option text. Git history keeps the reasoning.

---

## 5. Traps

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
27. **Local green does not mean CI green.** LOOP 0 checks the local battery and has no CI signal at all, so CI stayed red across several commits unnoticed (Issue 024).
28. **A real quote does not make a real claim.** `verify_quotes` proves the words were said. It never proves they said *that*. A published tension was traced to two genuine quotes carrying a wholly invented proposition, and all five extraction validators passed. **"Is this citation real?" and "does this citation support this claim?" are different questions, and only the first was ever asked.**
29. **A parameter that is declared, defaulted, and never referenced is not a check.** `verify_source_productivity(min_ratio=0.05)` never uses `min_ratio` — and could not, since no media duration is stored. The function reads as a coverage check and is a non-emptiness check. Grep for the parameter in the body, not just the signature.
30. **Fragmentary input invites fabrication.** Utterances split on length rather than sentence boundaries end mid-word. Asking a model to find a *position* in a fragment that cannot hold one is how invented propositions get attached to real words. Fix the segmentation before blaming the extractor.
31. **`hasattr` on a dataclass field is a silent default, not a check.** `engine.py:82` guards `hasattr(c, "source_id")` on an entity whose source is reachable only through its utterance. The guard is always False, the set stays empty, and a `max(…, 1 …)` fallback supplies a plausible number. Nothing fails and nothing logs. **Use direct attribute access on declared fields so a rename fails loudly**, and treat every fallback that manufactures a value as a place a bug can hide indefinitely.
32. **A verification pass that unions fixtures with production data cannot tell you which one passed.** `worker.integrity --all` extends fixture lists with live DB rows and checks the union — and silently omits assessments from the DB side entirely. **Report populations separately, and print the examined count for each**, or a green pass means nothing you can act on.
33. **A deterministic ID is only as canonical as its normalization.** `compute_proposition_id` lowercases and collapses whitespace but does not strip terminal punctuation, so `"…than Western nations"` and `"…than Western nations."` are different propositions. **No similarity threshold can merge them — the split happens before similarity is computed.** Over-splitting hides contradictions silently, which is the exact failure parameter 008's bias is written against.
34. **Fixing a measurement without fixing where the measurement comes from is self-confirming.** A coverage check whose duration is read from the truncated download computes ~100% and passes on a corpus that is 92% unread. **The denominator must come from outside the artifact being checked.**

---

## 6. Queue

| Order | ID | Item | Blocked | Status | Why here |
|---|---|---|---|---|---|
| 1 | **G0** | Repair the `mypy` gate | none | **delivered** | 11 errors in `tests/test_segmentation_x0.py` repaired; mypy clean on 78 files. |
| 2 | **M0** | `source_count` is a constant, not a measurement | none | **delivered** | Resolved through utterance anchor chain without `hasattr`; Sacks/Friedberg 2, Jason/Chamath 1, zero claims 0, unresolvable raises. |
| 3 | **E0** | Integrity pass must check the corpus, not a union | none | **delivered** | FIXTURES and CORPUS evaluated and reported independently; assessments loaded from DB; examined counts reported. |
| 4 | **D0** | Proposition table repair (**Issue 027 = A**) | none | **delivered** | Normalized canonical IDs, merged three forked rows, backfilled embeddings for all 8 live propositions, quarantined fabricated db3ec63d33cf6f0a, and added structural read filters. |
| 5 | **X1** | Entailment validator (Issue 025 = C) | none | outstanding | Mechanism settled. Unblocked by D0. |
| 6 | **R1** | Media duration + real coverage check; fix truncation | **X1** | outstanding | Cause of the truncation is **found** (§19) — do not re-hunt it. The re-ingest is the largest extraction run yet and must not precede the entailment guard. |
| 7 | **F0** | Repair the behaviour fixture set | none | **delivered** | 20/20 across all 17 classes. |
| 8 | **S0** | `SourceSubjectRole` migration (Issue 022 = A) | none | **delivered** | Landed while the corpus was empty, as intended. |
| 9 | **I0** | First real ingest — the four All-In hosts | none | **superseded → R1** | I0.1/I0.2 hold. I0.3's remaining work is the truncation, tracked in R1. **Not a to-do; do not open it.** |
| 10 | **R0** | Repair the ingest; add the productivity guard | none | **superseded → R1** | Empty-source bug fixed and deletion gated. The coverage half is R1. **Not a to-do; do not open it.** |
| 11 | **X0** | Quarantine the fabricated tension; fix segmentation | none | **delivered** | Verified independently: tension quarantined, claims removed, 9 survivors read one by one and genuinely supported. |
| 12 | **C0** | Portability workflow; `mlx-lm` optional (Issue 024 = B) | none | **delivered** | |
| 13 | **P4** | Tension detection | none | **delivered · fixtures only** | |
| 14 | **P3** | Topic model | none | **delivered · fixtures only** | |
| 15 | **P5** | Principle extraction | none | **delivered · fixtures only** | |
| 16 | **P6** | Rubric engine | none | **delivered · fixtures only** | **See M0** — its sufficiency block prints a constant. |
| 17 | **P7** | Local API | none | **delivered** | **See Issue 027** — `/resolve` currently reaches only orphaned propositions. |
| 18 | **P8** | Browser extension | none | **delivered** | |

> **P3–P7 are delivered as code and unvalidated as behaviour.** They run, they pass their fixture tests, and they produce **zero** published tensions and principles over the live corpus — because a corpus drawn from 7.7% of four episodes cannot contain one (trap 26). Do not read their green status as evidence the detectors work. **R1 is what makes that question answerable**, and E0 is what makes the answer trustworthy when it arrives.

**Delivered — do NOT rework:** V0–V6 (all externals real, `STUB_REGISTRY` empty), U0–U13 (storage, integrity, adapters, reconciler, segmentation, gate, validators). Detail in git history; §14 has the short list.

**IDs are labels, not sequence numbers.** Follow the **Order** column.

---

## 7. LOOP 1 — IMPLEMENT

```text
LOOP 1 — IMPLEMENT <ITEM>

STEP 1 — LOAD
  Read <ITEM>'s section. Read every contract doc it cites, in full.
  Write down BEFORE coding:
    a. one-line user impact
    b. exact files you expect to touch (blast radius)
    c. THE ONE assertion that cannot pass unless the thing genuinely works
  Cannot name (c)? -> LOOP 3. The item is underspecified.

STEP 2 — DECLARE
  Needs a package? Add to pyproject.toml NOW and install.
  Needs a credential, gated download, or a human judgement? -> LOOP 3
  BEFORE writing code. Never stub around a missing credential.

STEP 3 — BUILD
  Implement as specified. Numbers and literal strings are decisions.
  Impossible value? Keep the intent, deviate minimally, record it in the
  commit body.

STEP 4 — VALIDATE
  Write every assertion under the item's Validation heading. Run them.
  All pass, including (c).

STEP 5 — FALSIFY
  Enter LOOP 2. Mandatory. Do not proceed until it completes.

STEP 6 — BATTERY
  Run §2. All gates green. Record REAL numbers. Anything unmeasured is
  "NOT MEASURED".

STEP 7 — PROPAGATE (same commit)
  - §3 baseline numbers
  - §6 queue row -> delivered
  - any design_*.md whose described behaviour changed
  - ongoing_errors.md §2 if you measured a parameter
  - ongoing_errors.md §4 if a selection was consumed

STEP 8 — COMMIT
  One item, one commit. Body contains:
    - why, in prose
    - the falsification: what broke, that it went RED, revert, GREEN
    - deviations, with reasons
    - measured numbers

STEP 9 — LOOP
  Return to LOOP 0. Re-detect state; never pick the next item from memory.
```

---

## 8. LOOP 2 — FALSIFY

```text
LOOP 2 — FALSIFY <ITEM>

1. Take the assertion from LOOP 1 STEP 1(c).
2. Break the CODE UNDER IT — not the assertion.
     deleting the assertion proves nothing
     deleting the behaviour it guards proves everything
3. Run it. It MUST go RED.
     Still GREEN -> the assertion is decorative. Rewrite it, restart LOOP 2.
     This is a finding: you found a test that cannot fail.
4. Revert. Run again. MUST go GREEN.
5. Record BOTH outcomes verbatim in the commit body:
     "Falsification: <break> -> <assertion> FAILED as expected.
      Reverted -> PASSED. Both outcomes observed."
6. Return to LOOP 1 STEP 6.
```

---

## 9. LOOP 3 — ESCALATE

```text
LOOP 3 — ESCALATE

Trigger on ANY of:
  - a specified value is impossible and intent cannot be preserved
  - the design as written cannot work
  - a credential, gated download, or human judgement is required
  - you cannot name an assertion that proves the thing works
  - a needed selection is still "Your selection: _____"

Do:
  1. STOP. No more code on this item.
  2. Open docs/ongoing_errors.md section 1.
  3. INSERT a new numbered issue at the TOP of section 1 — newest first, so
     the user never scrolls to find what is blocking. Use the next free
     number (highest existing + 1; numbers stay ascending, ORDER is
     descending). Include:
       - what is blocked, concretely, and what you already tried
       - 2-3 options, each with honest pros AND cons
       - a recommendation, marked as such
       - final line, exactly: "Your selection: _____"
  4. NEVER fill in that line.
  5. Update section 6: set blocked_on for affected rows.
  5b. When that issue is later SELECTED: move it OUT of ongoing_errors
      section 1. Write its consequence into the design doc that owns it,
      add one row to section 4's decision record naming that doc, and
      delete the option text. That file is a queue, not an archive —
      git history keeps the reasoning.
  6. Return to LOOP 0. Nothing unblocked -> LOOP 4.
```

---

## 10. LOOP 4 — CLOSE OUT

```text
LOOP 4 — CLOSE OUT

Reached only when no row in section 6 is both undelivered and unblocked.

1. Run section 2. Record numbers in section 3.
2. Confirm STUB_REGISTRY is EMPTY.
3. Report:
     - what landed, with measured numbers
     - what is blocked, and on which issue
     - any issue filed via LOOP 3
4. STOP. Do not invent work.

Legitimate resume triggers only:
     - a "Your selection:" line gets filled
     - a gate in section 3 goes red
     - the user asks for something specific
```

---

## 11. LOOP 5 — DECOMPOSE

Phase items (P3–P8) are subsystems, not commits. This loop turns one into a queue.

```text
LOOP 5 — DECOMPOSE <ITEM>

1. Read <ITEM>'s section and its contract doc in full.
2. Split into sub-items that each satisfy ALL of:
     - lands as ONE commit with one coherent message
     - has its own falsifiable assertion
     - leaves the repo GREEN when committed alone
   If a split leaves gates red, it is not a valid split. Merge it back.
3. Order them so each builds only on what is already committed.
4. Write the list into this guide under <ITEM>'s section as a checklist:
       <ITEM>.1  <name>   [ ]
       <ITEM>.2  <name>   [ ]
   Commit that plan BY ITSELF, before writing code. The plan is the
   contract for the rest of the item and must survive a context reset.
5. Set ITEM = the first unchecked sub-item. Enter LOOP 1.
6. After each sub-item commits, tick its box in the same commit and
   return to LOOP 0.

Rule of thumb: a sub-item is too big if its commit message needs more
than one "and". Three to six sub-items per phase is typical.
```

---

## 12. LOOP 6 — RESUME

A long build will outlive a context window. This is how the next agent picks up without redoing or half-doing work.

```text
LOOP 6 — RESUME

Entered when LOOP 0 finds a dirty working tree.

1. git diff --stat  and  git status --porcelain
2. git log --oneline -3   ->  which item was in flight?
3. Find that item's section. Find its sub-item checklist (LOOP 5 STEP 4)
   if it has one. The last ticked box tells you where work stopped.
4. Run the gates (section 2). Classify:

   GREEN and the change looks complete
     -> finish LOOP 1 from STEP 5 (FALSIFY). Do NOT skip falsification
        just because someone else wrote the code.

   GREEN but the change looks partial
     -> finish it. Re-derive intent from the item's spec, NOT from the
        half-written code. Partial code is a guess; the spec is the contract.

   RED
     -> enter LOOP 7 (REPAIR).

   Cannot tell what was intended
     -> git stash the changes, re-read the item spec, restart LOOP 1
        from STEP 1. Discarding half an unclear implementation costs less
        than shipping a misunderstanding.

5. Never commit someone else's uncommitted work without running its
   falsification yourself. An unfalsified guard is not a guard.
```

---

## 13. LOOP 7 — REPAIR

```text
LOOP 7 — REPAIR

Entered when a gate that section 3 records PASS comes back RED.

1. STOP all feature work. A red gate outranks the queue.
2. Identify the gate and read its failure output in full. Do not skim.
3. git log --oneline -5 and bisect if needed: which commit turned it red?
4. Classify:
     the code is wrong    -> fix the code
     the test is wrong    -> fix the test, and say so explicitly in the
                             commit body. This is the ONLY circumstance in
                             which a test may change to reach green.
     the baseline is stale -> section 3 was never re-measured. Correct
                             section 3, and note the drift.
5. NEVER weaken an assertion, delete a test, or narrow a scope to reach
   green. If that seems like the answer, it is a LOOP 3 escalation.
6. Falsify the fix (LOOP 2). A repair with no falsification is a guess.
7. Commit the repair ALONE, then return to LOOP 0.
```

---

## 14. Delivered — do NOT rework

**V0–V6:** fabricated-throughput removal; stub registry + CI guard; fixture/corpus split with metric floor and parameter-readiness report; real `nomic-embed-text-v1.5` embeddings with task prefixes; real `faster-whisper` dual-pass transcription with audio disposal; real `pyannote.audio` diarization; real Gemma runtime on MLX. `STUB_REGISTRY` is empty.

**U0–U13:** integrity pass (eight checks, `NOT APPLICABLE` correctly distinguished from `PASS`); DuckDB with `vss`, `FLOAT[768]`, HNSW cosine, deterministic IDs; three source adapters behind one Protocol; dual-pass reconciler; segmentation; extraction gate; five post-extraction validators.

**Accepted equivalents — do not "fix" back:** the `TranscriptionEngine` Protocol + `Mock` test-double split; `LocalGemmaRuntime`'s shape. Both better than the spec implied.

---

## 15. F0 — Repair the behaviour fixture set

**User impact:** the tests that are supposed to prove contradiction detection works become capable of proving it.

**Gap — verified on disk, not inferred.** `fixtures/behaviour/cases.json` holds 16 cases. Two defects:

1. **Eight pair-type classes are single, undated sentences.** `P1, P2, P3, P4, N5, N7, N8, N12` each describe an outcome that requires **two** utterances separated in time, and each is stored as one snippet. There is no date field in the schema at all. A reversal cannot be expressed, so it cannot be tested.
2. **`N6`, `N9` and `N11` do not exist.** N6 (principle applied differently **with** a stated distinction) is P5's most important guard — it is the fairness escape hatch. N9 (misattribution trap) is the zero-tolerance gate. N11 (thin corpus) proves the sufficiency gate.

**Implementation**
1. **Extend the schema.** A case carries `utterances: [...]`, each with `text`, `recorded_at` (ISO 8601), `span`, and where relevant `speaker`, `venue_type`, `audience_stance`. Single-utterance classes (`N1–N4`, `N10`, `N13`) carry a one-element list — **uniform shape, no special case.**
2. **Rebuild the eight pair cases as genuine pairs**, each with dates that make the outcome derivable rather than asserted:
   - **P1** — oppose at T1, support at T2, **no acknowledgement anywhere between.**
   - **P2** — oppose at T1, support at T2, **plus a third utterance in the interval carrying the change marker.** This is what makes the acknowledgement-window falsification meaningful.
   - **P3** — same principle, two different actors, opposite verdicts, no distinction.
   - **P4** — same proposition, opposite stances, **within one week**, one `friendly` venue and one `adversarial`.
   - **N5** — one conditional (with `condition` text) and one unconditional on the same proposition.
   - **N7** — `hedging_level` high at T1, low at T2.
   - **N8** — same wording, dates ≥ 8 years apart, different referent.
   - **N12** — `recorded_at` 2018, `published_at` 2024, paired with a genuine 2024 claim.
3. **Add the three missing classes.**
   - **N6** — P3's pair plus a `stated_distinction` utterance giving a real reason. Expected: `distinguished`, excluded from scoring.
   - **N9** — one source, **two speakers**, host asserts X and guest asserts not-X, with speaker labels. Expected: **zero** cross-attribution.
   - **N11** — a subject with 6 claims on a topic. Expected: `insufficient_corpus`, **no number computed**.
4. Update `fixtures/behaviour/loader.py` and the report block. **Fixtures stay PASS/FAIL** — this changes their shape, never their status as non-metrics (`e2e_verification_journeys.md` §2).
5. Keep `locator_kind: "synthetic"` on every case.

**Validation**
- Loader **rejects** a pair-type case carrying fewer than two utterances, and any case whose utterances lack `recorded_at`. ← **(c)** *This is the assertion that makes the defect unrepeatable.*
- All 17 classes present; assert the set of `type` values equals the table in `e2e_verification_journeys.md` §2 — so a class can never go missing silently again.
- Utterances within a case are orderable by `recorded_at`; P2's marker utterance falls strictly between its pair.
- Fixture report still prints **PASS/FAIL only** — no rate, no decimal, no ratio.

**Falsify.** Strip `recorded_at` from one P1 utterance. The loader must go RED. Then delete the N6 case; the class-completeness assertion must go RED. Revert both; record all four outcomes.

**Blast radius.** `fixtures/behaviour/`, `worker/golden/report.py`, `tests/test_golden_harness.py`, `docs/e2e_verification_journeys.md` §2 (document the utterance-list schema).

---

## 16. S0 — `SourceSubjectRole` migration · *Issue 022 = A*

**User impact:** the system can hold the truth that one recording means different things to different people in it — which is what a four-host podcast with an occasional guest actually is.

**Why now, before I0.** The corpus is **empty**. Zero sources, zero utterances, zero claims. A schema change that today is a pure code edit becomes a data migration the moment I0.3 writes its first episode. **This is the cheapest this change will ever be**, and it is the only reason S0 sits ahead of the ingest that motivated it.

**Gap.** `worker/entities.py` puts `tier`, `venue_type`, `audience_stance` and `is_adversarial` on `Source` — one value per source. They are properties of a **(source, subject) pair**. One All-In episode is Tier B / `own_channel` / `friendly` for its four hosts and Tier C / `guest` for a visitor, simultaneously. And `audience_stance` feeds audience-divergence detection (`design_rubric_engine.md` §6), so a single stamped value yields a wrong **finding**, not a cosmetic mislabel.

**Contract:** `design_data_layer.md` §2 and §3 (already updated); `design_source_acquisition.md` §2 and §4.

**Implementation**
1. New entity `SourceSubjectRole`: `role_id`, `source_id`, `subject_id`, `tier`, `venue_type`, `audience_stance`, `is_adversarial`. Deterministic id `sha256(source_id | subject_id)[:16]` — so re-ingest upserts rather than duplicates, same as every other id.
2. **Remove those four fields from `Source`.** It keeps only what is true of the artifact: title, publisher, url, hashes, `citation_url_template`, `interlocutor`, `recorded_at`, `published_at`, `authorship_confidence`, and the ingest bookkeeping.
3. DuckDB table with a foreign key to both sides, plus an index on `(source_id, subject_id)`.
4. **`SourceAdapter.tier` stops being a class attribute.** It becomes `role(ref, subject) -> SourceSubjectRole`, because an adapter has no single tier — YouTube yields Tier B or C depending on whose channel it is. Update all three existing adapters.
5. Ingest writes **one role row per subject found in a source.**
6. **Add a ninth integrity check, `verify_role_coverage`:** every utterance's `(source_id, subject_id)` pair resolves to a role row. An utterance attributed to a subject with no role for that source is an orphan and fails the pass.
7. Update every reader of venue metadata to join through the new table. The one that matters most is the `audience_divergence` detector — it must read the role's `audience_stance`, never the source's.

**Validation**
- **Persist one source with two subjects at different tiers — Tier B for one, Tier C for the other — and assert both round-trip intact, neither overwriting the other.** ← **(c)** *This assertion is impossible to satisfy under the old schema, which is exactly why it is the one that matters.*
- `Source` no longer exposes `tier`; assert `mypy` rejects an access to it.
- Deterministic id: writing the same `(source, subject)` pair twice yields one row.
- `verify_role_coverage` fails on an utterance whose pair has no role row, and reports `NOT APPLICABLE — zero rows` on an empty store rather than `PASS`.
- All three adapters implement `role()`; assert the Protocol is satisfied.

**Falsify.** Restore `tier` on `Source` and have the writer use it. The two-tier round-trip must go RED. Then delete a role row for an ingested utterance; `verify_role_coverage` must go RED. Revert both; record all four outcomes.

**Blast radius.** `worker/entities.py`, `worker/storage.py`, `worker/adapters/*` (all three), `worker/integrity.py` (new check), `tests/`, `docs/design_data_layer.md` §2–§3 and `docs/design_source_acquisition.md` §2, §4 (both already updated — verify the code matches).

---

## 16b. R0 — Repair the ingest; add the productivity guard · **SUPERSEDED → R1**

> **Do not open this as a work item.** The empty-source bug is fixed and audio deletion is gated; both hold. The coverage half was never implemented and is tracked in **§19 (R1)**, which also names the root cause. This section is kept for the reasoning only.

**User impact:** the corpus stops containing three episodes' worth of nothing, and the pipeline stops reporting success when it produced no output.

**Gap — measured against the live database, not inferred.**

```
utt=  0  ingested_at=True  audio_deleted=True  All-In E124 (2023-04-14)
utt=  0  ingested_at=True  audio_deleted=True  All-In E165 (2024-02-09)
utt=  0  ingested_at=True  audio_deleted=True  All-In E245 (2025-10-03)
utt= 15  ingested_at=True  audio_deleted=True  All-In E287 (2026-09-03)  ← 0s–300s only
```

Three failures compounding:

1. **Silent ingest failure.** Three sources produced zero utterances, were stamped `ingested_at`, and **had their audio deleted anyway.** Under Issue 003 = C the audio is gone, so these cannot be re-transcribed — only re-fetched.
2. **Truncation.** The one source that produced anything covers **0s–300s** — five minutes of a roughly ninety-minute episode. 15 utterances, not the hundreds an episode yields.
3. **Nothing caught either.** `verify_anchor_chain` asks whether pointers *resolve*. A source with no utterances has no dangling pointers — it is simply empty, and every check stayed green. **Success was defined as "no exception raised," never as "output exists."**

The consequence for everything above it: all 15 claims share one date and one stance per proposition, so **a reversal is structurally impossible.** P4, P5 and P6 report zero and pass. They have never met data capable of contradicting itself (trap 26).

**Implementation**
1. **Add `verify_source_productivity` — the tenth integrity check.** A source with `ingested_at` set and zero utterances is a **FAIL**, not a pass. Same for a source whose utterance span covers implausibly little of its media duration; make the ratio a named constant and record it.
2. **Gate audio deletion on productivity.** `audio_deleted_at` may only be set for a source that produced ≥1 utterance. `design_source_acquisition.md` §5.2 says deletion is "the last step, after everything above has succeeded" — **success was never defined, so an empty run qualified.** Define it: success is output.
3. **Find the root cause before re-running.** Three sources failing identically is a systematic fault, not three coincidences — a fetch returning HTML, a VAD gate rejecting everything, an adapter yielding an empty media path. Read the ingest job records. **Do not re-run and hope.**
4. **Investigate the 5-minute truncation separately.** It may share a root cause or may not. Check whether the fetch downloaded a preview, whether a duration cap exists, or whether transcription stopped early.
5. **Re-fetch and re-ingest all four sources.** The audio is unrecoverable locally; re-download from source.
6. **Then re-run P4, P5 and P6 against the repaired corpus** and record what they find. If P4 still reports zero across four episodes spanning 2023–2026 on overlapping topics, that is a finding worth reporting — but it is only meaningful once the corpus can hold a tension.

**Validation**
- **`verify_source_productivity` FAILS against the database as it stands today** — three sources, zero utterances. ← **(c)** *An integrity check that passes on a known-broken store is not a check. This one must go red before it earns its place.*
- After repair, every source has ≥1 utterance and the check passes on a non-empty set.
- **Audio-deletion gate:** simulate a source that transcribes to zero utterances; assert `audio_deleted_at` stays **null** and the audio file survives.
- Utterance span covers a plausible fraction of media duration for all four sources.
- At least one proposition carries **≥2 claims with opposing stances at different dates** — the structural precondition for P4 to be testable at all. If the repaired corpus still cannot produce one, say so explicitly rather than reporting P4 as validated.

**Falsify.** Restore the ungated deletion and re-run the zero-utterance simulation; the audio-survival assertion must go RED. Then re-point `verify_source_productivity` at a healthy store and confirm it passes, so it is discriminating rather than always-failing.

**Blast radius.** `worker/integrity.py` (new check), `worker/transcribe/` or wherever deletion is triggered, the ingest job records, `tests/`, `docs/design_source_acquisition.md` §5.2 (define success as output), §3 baseline, §6 queue, `docs/e2e_verification_journeys.md` (J1's gate did not catch this — add the productivity assertion).

---

## 17. X0 — Quarantine the fabricated tension; fix segmentation

**User impact:** the database stops containing a false accusation, and the pipeline stops manufacturing them.

**Gap.** The live store holds **one tension, status `published`**, and it is wrong:

```
PROPOSITION (both claims):
  "Mandatory state and federal licensing regimes for frontier artificial intelligence models"
CLAIM A  oppose  2024-02-09  quote: "collection like robots or robots having"
CLAIM B  support 2025-10-03  quote: "steal happening right now. I really"
```

Neither quote is about licensing. The extractor invented the proposition, two inventions collided, and the detector — working correctly on garbage input — published a reversal.

**Every guard passed.** `verify_quotes` confirms the words are real; the fabrication is in the *proposition*, and nothing checks that (trap 28). And the utterances are cut mid-word — `"...appendages like huma"`, `"...as it is bullsh-sh-"` — because segmentation splits on length, not sentence boundaries. **A fragment cannot hold a position, so asking for one invites invention** (trap 30).

**Implementation**
1. **Quarantine the existing tension first, before any code change.** `status: quarantined`, reason `fabricated_proposition`. `design_evidence_integrity.md` §5: quarantine first, investigate second. A false finding stops being displayed in the same instant it is suspected.
2. **Segment on sentence and pause boundaries**, not fixed length. Use the word timestamps already stored: break on terminal punctuation and on pauses above a threshold, with a maximum length as a *fallback* rather than the primary rule.
3. **Re-segment and re-extract the existing corpus.** Claim ids include `extraction_version`, so bump it — old claims stay inert and auditable rather than colliding (`design_claim_extraction.md` §9).
4. **Do not tune `T_dedup` to make this go away.** Over-merging is a plausible contributor, but the primary defect is that a proposition was invented for a fragment. Fix the input; measure dedup afterwards.

**Validation**
- **Zero utterances begin or end mid-word.** Assert every `text_verbatim` starts with a capital or opening quote and ends with terminal punctuation, allowing a named list of exceptions. ← **(c)** *No fixture can satisfy this on the old segmenter; it is only satisfiable by genuinely re-segmenting real audio.*
- The fabricated tension is `quarantined` and appears in no assessment's `axis_evidence`.
- After re-extraction, **re-inspect every surviving claim by hand** — there are fewer than 20. For each, read the quote and the proposition and confirm the quote supports it. Record the count checked in the commit body. *At this corpus size manual review is cheap and is the only thing that actually establishes ground truth.*
- Median utterance length rises materially; record before and after.

**Falsify.** Restore fixed-length segmentation and re-run. The mid-word assertion must go RED. Revert; record both.

**Blast radius.** `worker/segment.py`, `worker/extract/`, the corpus (re-extraction), `tests/`, `fixtures/behaviour/` (add a mid-word-fragment case), §3, §6.

---

## 17b. G0 — Repair the `mypy` gate · *LOOP 7*

**This is a LOOP 7 repair, not a LOOP 1 item.** A red gate outranks the queue; nothing below it starts until this is green.

**Gap — measured September 4, 2026 at `5f881ea`.** §3 records `mypy --strict` PASS on 74 files. It is now **RED: 11 errors across 78 files**, all in `tests/test_segmentation_x0.py`, all from one line. It arrived with X0, at HEAD.

**Root cause.** Line 52:

```python
claims = [store.get_claim(cid) for cid in claim_ids if cid]
```

`get_claim` returns `Claim | None`. The `if cid` filter tests the **id**, not the result, so `claims` is `list[Claim | None]` and all ten subsequent attribute accesses are `union-attr` errors.

**Implementation.** Filter on the result, using the walrus idiom `worker/integrity.py:632` already uses:

```python
claims = [c for cid in claim_ids if (c := store.get_claim(cid)) is not None]
```

Then add the assertion the narrowing makes necessary: `assert len(claims) == len(claim_ids)`. Without it, an unresolvable claim id silently shortens the list, and `assert len(claims) >= 9` would pass on a corpus that had lost a claim — the narrowing would have converted a data defect into a quieter test.

**Validation.** `mypy --strict` clean on 78 files. The suite still reports 157 passed.

**Falsify.** Revert the narrowing alone. mypy must return the *same* 11 errors — proving the fix is the narrowing and not something incidental that came with it. Revert back; record both.

**Blast radius.** `tests/test_segmentation_x0.py`, §3 baseline.

---

## 17c. M0 — `source_count` is a constant wearing a measurement's name

**User impact:** the sufficiency gate stops reporting `1` for every subject regardless of how many sources they were read from.

**Contract:** `design_rubric_engine.md` (sufficiency) · invariant **I5** · the standing constraint *never print a number you did not measure*.

**Gap — confirmed at runtime, not read off.** `worker/rubric/engine.py:82`:

```python
if hasattr(c, "source_id") and c.source_id:
    sources.add(c.source_id)
```

`Claim` has no `source_id`. Its fields are `claim_id, subject_id, utterance_id, proposition_id, …` — the source is reachable only *through* the utterance. So `hasattr(c, "source_id")` is **always False**, `sources` is always empty, and line 99's

```python
"source_count": max(len(sources), 1 if claim_count > 0 else 0),
```

returns **1** for every assessment that has any claim at all. Verified: `hasattr(c, "source_id") == False` on a real loaded claim.

Measured against the corpus: Sacks and Friedberg each draw on **2** distinct sources. All 8 assessments record `source_count: 1`.

**Why it matters, and why it looks harmless.** `source_count` feeds I5. Today every axis is gated off for other reasons, so the wrong number changes no output — which is exactly why it survived. After R1 it will change output: a subject read from eight sources still reports 1 and is **suppressed as insufficient**. A guard that always returns the most conservative value is not safe; it has stopped being a gate and become an unconditional suppressor, and it fails in the direction that hides real findings.

The general form is worth more than the instance: **`hasattr` on a dataclass field converts a schema error into a silent default.** Nothing fails, nothing logs, and the fallback supplies a plausible number.

**Implementation**
1. Resolve the source through the anchor chain that already exists:
   ```python
   utt = self.storage.get_utterance(c.utterance_id)
   if utt is not None:
       sources.add(utt.source_id)
   ```
   Direct attribute access, no `hasattr` — a future rename must fail loudly.
2. **Delete the `max(…, 1 …)` fallback.** If `claim_count > 0` and no source resolves, that is an I3 anchor-chain violation and must raise. Defaulting to 1 is how the bug stayed invisible.
3. Grep the rest of `worker/` for `hasattr(` on entity fields and fix the same pattern wherever the attribute is a declared field.

**Validation**
- **(c)** — an assessment for a subject whose claims come from **2 distinct sources records `source_count: 2`.** Checkable against the live corpus today: `subj_david_sacks` and `subj_david_friedberg` both must read 2, and `subj_jason_calacanis` and `subj_chamath_palihapitiya` must read 1. *Neither the `hasattr` code nor any stub returning a constant can produce that spread — it requires a real join over real rows.*
- A subject with zero claims still records `source_count: 0`, not 1.
- `mypy --strict` stays clean after `hasattr` is removed; if it now reports an error, that error is the bug this item exists for.

**Falsify.** Restore the `hasattr` guard. The (c) assertion must go RED with `source_count == 1` for Sacks and Friedberg. Revert; record both.

**Blast radius.** `worker/rubric/engine.py`, `tests/`, §3 baseline. **Not** proposition `claim_count` — that column's fate is Issue 027's to decide (A recomputes it, B removes it), so leave it alone here or the two changes collide.

---

## 17d. E0 — The integrity pass must check the corpus, not a union with fixtures

**User impact:** the pass that certifies evidence integrity starts telling you something about your data.

**Contract:** `design_evidence_integrity.md` (the ten checks) · trap 21.

**Gap — measured.** `worker/integrity.py:624-659` calls `load_valid_fixtures()`, then **extends** those lists with rows from `social_proof.duckdb` and runs every check over the union. It reports *"11 claims, 363 utterances, 6 sources"* against a database that holds **9, 361, and 4**.

Two defects, and the second is the serious one:

1. **A PASS is over a union**, so it cannot distinguish "the corpus is sound" from "the fixtures carried it." Several checks `return` on the first failure, so row ordering can mask a bad row as well.
2. **Assessments are never loaded from the database at all.** The DB block extends sources, utterances, claims, roles and tensions — and not assessments. `verify_no_suppressed_scores` and `verify_versions_present` have therefore **never examined a real assessment**; both report over 1 fixture row while 8 real ones sit unchecked. *I read all 8 by hand: they are correctly gated, so nothing is hidden today.* But the check that would tell you is the one that is not running, and `verify_quarantine_not_rendered` — the guarantee X0 was written to establish — is also evaluated against fixture assessments rather than the real ones.

This is trap 21 in a new location: green over data that is not the product's.

**Implementation**
1. Run the suite **twice** and report two labelled sections, `FIXTURES` and `CORPUS`. Never union them. Exit non-zero if **either** fails.
2. Load assessments from the DB in the corpus run, alongside the five entity types already loaded.
3. When the database is absent or empty, the corpus run reports `NOT APPLICABLE — zero rows` per check. That vocabulary already exists in the pass and is already correct; do not invent a second one.
4. Print the examined counts per section, so a future reader can see at a glance which population each number came from.

**Validation**
- **(c)** — for every check in the CORPUS section, `examined_count` equals the count the test computes itself with `SELECT count(*)` against `social_proof.duckdb`, **assessments included**. Compute the expected numbers in the test rather than hardcoding today's; the point is the population, not the size. *A union cannot satisfy this, and neither can a run that never loads assessments.*
- **Both directions:** copy the DB to a scratch file, insert a claim whose quote does not appear in its utterance, and point the pass at it. CORPUS must FAIL while FIXTURES still PASSes — proving the two report independently rather than sharing a verdict.
- The exit code is non-zero when the corpus fails and the fixtures pass.

**Falsify.** Re-union the two lists. The (c) assertion must go RED because `examined_count` exceeds the database count. Revert; record both.

**Blast radius.** `worker/integrity.py`, `tests/`, §3 baseline, `docs/design_evidence_integrity.md` (the pass now has two populations; say so).

---

## 17e. D0 — Proposition table repair · *Issue 027 = A*

**User impact:** `/resolve` stops returning propositions nobody ever said, and the entailment guard X1 depends on becomes buildable.

**Contract:** `design_data_layer.md` §3 (normalization, the recompute invariant) and §2/§4 (the two new columns) · `design_evidence_integrity.md` §4 (quarantine extends to propositions) · `design_local_api_and_clients.md` §4 (the read filter).

**Gap.** Full statement in `ongoing_errors.md` §4 row 027 and this guide's §3. In one paragraph: X0 removed the claims of six propositions but left the rows, their `claim_count` values and — critically — **all seven embeddings**, which belong exclusively to that dead generation. The eight propositions carrying today's live claims have **no embedding at all**, so `/resolve`'s join (`worker/api/server.py:172`) reaches only orphans, one of which is the fabricated `db3ec63d33cf6f0a`. Separately, `compute_proposition_id` does not strip terminal punctuation, so three propositions exist twice, differing only by a final period.

---

### The migration is contained — verify that, do not assume it

`proposition_id` feeds `claim_id`, which feeds `tension_id`, which feeds `axis_evidence`. A change to proposition IDs can therefore cascade through the entire store. **On today's data it does not**, and this was measured, not reasoned:

| stored id | recomputes to | live claims | note |
|---|---|---|---|
| `932587f9999e7a8e` | `81eb3fb1db151083` | 0 | orphan; no target row exists |
| `b64d953ec975ceb8` | `86ad084395852d91` | 0 | **merges into a live row** |
| `a88324f4a7506c06` | `167e87f2d9561d79` | 0 | **merges into a live row** |
| *all other 11* | unchanged | — | includes **all 8** live propositions |

**Every ID that moves belongs to a proposition with zero live claims.** No `claim_id`, `tension_id`, `assessment_id` or `axis_evidence` entry changes. The migration touches the dead generation only.

**This is a property of today's rows, not of the fix.** After R1's re-ingest, a live proposition may well end in a period, and then the cascade is real. **Step 2 below therefore re-derives this table at runtime and refuses to proceed if a live proposition's ID would move.** Do not port the numbers above into code as an expectation.

---

### Implementation

**1. One shared normalizer.**

`worker/storage.py:39-41` and `:54-55` contain the same normalization inline, for propositions and principles respectively. Extract it once:

```python
_TERMINAL = ".!?…\"'”’"

def normalize_canonical_text(text: str) -> str:
    """Canonical form for content-derived IDs. See design_data_layer.md §3."""
    collapsed = " ".join(text.strip().lower().split())
    return collapsed.rstrip(_TERMINAL).rstrip()
```

Both `compute_proposition_id` and `compute_principle_id` call it. **They must not diverge** — principles carry the identical defect today and fixing only one leaves the same bug in the other layer.

Scope it deliberately: **terminal punctuation and nothing else.** Unicode dash folding, quote folding and stopword removal are all defensible and all change every ID again. If one is wanted later it is a fresh decision, not an extension of this one. Say so in the docstring.

Stripping is idempotent and order-independent, and it can only merge two texts that differ *solely* by trailing punctuation — which is the definition of the same proposition. It will also fold a text ending `"…in the U.S."` to `"…in the u.s"`; that is harmless, because both spellings map to one bucket consistently.

**2. Migrate the existing rows, refusing to cascade.**

Write this as a one-shot migration in `worker/storage.py` (or `scripts/`, if that is where migrations live — check before inventing a location). It must be **idempotent**: running it twice changes nothing the second time.

1. For every proposition, compute `new_id = compute_proposition_id(canonical_text)`.
2. **Guard first, before any write.** If any proposition whose `new_id != proposition_id` has **≥1 live claim**, `raise` with the list. That case is a full cascade migration — claims, tensions and assessments all need rewriting — and it is out of D0's scope. Failing loudly is correct; a partial migration here corrupts the anchor chain.
3. For each moving row where the target id **already exists**: the target is the survivor. Repoint `proposition_embeddings` only if the target has none, then delete the source row. *(This is the one deletion D0 performs, and it is a duplicate-key merge, not a purge — the surviving row carries the identical text.)*
4. For each moving row where the target does **not** exist: update the id in place, and in `proposition_embeddings` with it.
5. Recompute `claim_count` for every row as `SELECT count(*) FROM claims WHERE proposition_id = ?`. It is currently wrong on all 14.

**3. Add `status` and `quarantine_reason` to `propositions`.**

Mirror the columns `tensions` already has (`worker/entities.py:157-158`), with one deliberate difference: the vocabulary is **`active` / `quarantined`**, not `published` / `quarantined` / `dismissed`. A proposition is never itself rendered — it is a join key — so "published" would claim something untrue about it. Default `active`; add both to the `Proposition` dataclass, the DuckDB DDL, and the upsert in `worker/storage.py:669-692`.

Then mark the fabrication:

```
db3ec63d33cf6f0a  status='quarantined'  quarantine_reason='fabricated_proposition'
```

matching the reason string already on tension `0068adec4b1501c6`, so the two halves of one incident are greppable together.

**4. Embed every live proposition.**

Backfill `proposition_embeddings` for all propositions with ≥1 live claim — 8 rows today, none of which currently has one. Use the same `embed_document` path as `worker/ingest.py:193`, so prefixes match what X1 will use (`search_document:` on both sides — trap 7).

**Do not inherit an embedding across a merge.** In step 2.3 the surviving row's text differs from the absorbed row's by a period; the vector was computed on the absorbed text. Re-embed from the surviving row's own `canonical_text`. **An embedding must correspond to the exact text of the row it hangs on**, or the provenance chain quietly stops being true — and X1 is about to make decisions from these vectors.

Leave orphan embeddings in place. Louis selected A: nothing is purged. *(Pruning `proposition_embeddings` down to the readable set is a B-time cleanup; noted in §28 so it is not lost.)*

**5. Make the read path filter structurally, not on the counter.**

`worker/api/server.py:169-177` and every other proposition read: exclude `status = 'quarantined'`, and exclude propositions with no live claims using an existence test against `claims` — **not** `claim_count`:

```sql
WHERE p.status = 'active'
  AND EXISTS (SELECT 1 FROM claims c WHERE c.proposition_id = p.proposition_id)
```

`claim_count` stays as a reporting field and never gates behaviour. It has already drifted silently once across all 14 rows; a denormalized counter that gates a read is a second copy of the truth waiting to disagree with the first.

**6. Two new integrity checks** in `worker/integrity.py`, both cheap and both aimed at the class of defect rather than this instance:

- **`verify_canonical_ids`** — for every proposition and every principle, `stored_id == compute_*_id(canonical_text)`. This is the check whose absence let the fork exist, and it will catch any future normalization drift on the commit that introduces it rather than three phases later.
- **`verify_quarantined_propositions_unreachable`** — no quarantined proposition is returned by the `/resolve` query shape, and no live claim points at one. The tension equivalent (`verify_quarantine_not_rendered`) already exists; propositions had no such guard, which is how the fabrication stayed the most reachable row in the store.

Also assert `claim_count` matches the real count — as a **check**, never as a filter.

---

### Validation

- **(c)** — `/resolve` on the selected text *"China is much more optimistic about AI than we are"* returns proposition `86ad084395852d91`, which carries **2 live claims** from two named subjects. Today the same call can only reach a row with **zero** live claims. *No stub, no fixture and no query rewrite satisfies this: it needs the backfilled embedding, the merged id, and the EXISTS filter all correct at once. If any one of the three is wrong, the call returns an orphan or nothing.*
- **Both directions, or the filter is untested in one of them:** `/resolve` on text matching the fabricated licensing proposition returns **no proposition** — falling through to the topic path or to no match — and specifically never returns `db3ec63d33cf6f0a`.
- `verify_canonical_ids` **FAILS on the corpus as it stands today**, before the migration, naming exactly the three forked rows. Run it and see it red first. A check that has only ever been green on repaired data has not been tested.
- After migration: 12 propositions, 8 with live claims, all 8 with an embedding; `claim_count` matches the real count on every row; no proposition has both `status='quarantined'` and a live claim.
- Idempotence: run the migration twice; the second run reports zero changes and the DB hash is unchanged.
- The guard in step 2.2 fires: construct a fixture DB where a proposition **with** a live claim ends in a period, run the migration, and assert it **raises** rather than writing. This is the assertion that keeps D0 safe after R1 changes the data underneath it.
- `mypy --strict` and `ruff` clean; the full suite still passes.

**Falsify.** Skip step 4 (leave the live propositions unembedded) and re-run the (c) assertion — it must go RED, returning an orphan or nothing, proving the backfill is what does the work and not the filter alone. Then restore step 4 and skip step 5 instead; (c) must go RED again, this time by returning `db3ec63d33cf6f0a` for the licensing text. **Both halves must be shown to be load-bearing**; either one alone leaves the fabrication reachable. Revert; record all three results.

**Blast radius.** `worker/storage.py` (normalizer, DDL, upsert, migration), `worker/entities.py` (`Proposition`), `worker/api/server.py` (`/resolve`), `worker/integrity.py` (two checks), `worker/ingest.py` (embed-on-write for new propositions), `tests/`, the corpus (in-place migration), `docs/design_data_layer.md` §2–§4, `docs/design_evidence_integrity.md` §4, `docs/design_local_api_and_clients.md` §4, §3, §6.

---

## 18. X1 — Entailment validator · *Issue 025 = C*

**User impact:** a quote can no longer carry a claim it does not support. This is the guard that would have stopped the fabricated tension from ever being written.

**BLOCKED on D0 (§17e) — read it before planning.** Step 3 below embeds the proposition, and **no surviving proposition has an embedding**: all 7 rows in `proposition_embeddings` belong to the pre-X0 generation whose claims X0 removed. Both sides of the cosine are missing, so the (c) assertion cannot be reached. **Issue 027 = A** settles how the table is repaired; D0 does it. When D0 lands, the 8 live propositions are embedded with `embed_document` — the same prefix this validator must use — so do not re-embed them here.

**Contract:** `design_claim_extraction.md` §8 validator 6 (mechanism, verbatim) · `design_evidence_integrity.md` §2 rule E2b.

**Gap.** Five extraction validators all passed on a claim whose proposition was invented. They check that the quote *resolves*, that the proposition carries no polarity, that ranges and enums are valid, and that fields are internally consistent. **None asks whether the quote says what the proposition claims** (trap 28).

**Implementation**
1. Add validator 6 to the chain in `worker/extract/validators.py`, running **after** the quote-resolution check — there is no point testing entailment against a quote that does not exist.
2. **Length floor first**, because it is free: reject when the quote is shorter than `MIN_QUOTE_TOKENS`. Both known fabrications were 6-token fragments, so this alone catches them.
3. **Then embedding similarity.** Embed quote and proposition with the already-loaded `nomic-embed`, **both with the `search_document:` prefix** — this is document-to-document, not a query lookup. Mixing prefixes puts the two in different regions of the space and the similarity stops meaning anything (trap 7).
4. **Three outcomes, not two:**
   - `sim < T_ENTAIL_LOW` → **reject**, `quote_does_not_support_proposition`
   - `T_ENTAIL_LOW ≤ sim < T_ENTAIL_HIGH` → **quarantine**, `entailment_ambiguous`
   - `sim ≥ T_ENTAIL_HIGH` → pass
   The middle band must quarantine rather than publish. A borderline claim is precisely where a hard threshold is least trustworthy, and `design_evidence_integrity.md` §6 requires uncertainty be surfaced rather than silently resolved either way.
5. **Thresholds are parameter 026 — measured, not chosen.** Derive initial values from the corpus you have: the two known fabrications must fall below `T_ENTAIL_LOW`, and every hand-verified true claim from X0 must clear `T_ENTAIL_HIGH`. Record them as **provisional** in code and in the commit body.
   **The two fabricated claims are no longer rows** — X0 deleted them. Their text is in this guide's §3 history and in `4a62c3f`; reconstruct them as a behaviour fixture rather than expecting to query them.
   **Watch `MIN_QUOTE_TOKENS` in particular.** Both known fabrications were 6-token fragments, and `tests/test_segmentation_x0.py` currently asserts a floor of `>= 6` — which the fabrications would pass. A live claim sits at 7 tokens (`ae322a98ececbe5f`, *"until string theory is proved, it's unproved."*) and is tautological. The floor and the corpus are close enough together that the number must be measured against both, not inherited from the test.
6. Log every rejection with its reason and keep the counters. **The rejection rate is the early-warning signal for a prompt or model regression** — if entailment rejections climb after a prompt edit, the prompt got worse, and the counter is how you find out.

**Validation**
- **Both directions, or the validator is untested in one of them:**
  - the two fabricated claims from X0 are **rejected** ← **(c)**
  - every hand-verified true claim from X0 **passes**
  A validator that rejects everything is exactly as useless as one that rejects nothing, and only checking rejection would hide that.
- Prefix test: embedding a pair with mismatched prefixes yields a materially different similarity. Assert it — this is trap 7 made falsifiable rather than folklore.
- A claim scoring inside the ambiguous band is written `quarantined`, never `published`, and appears in no assessment's `axis_evidence`.
- No LLM call anywhere in the validator (`design_rubric_engine.md` §0 stays true).

**Falsify.** Set `T_ENTAIL_LOW = 0.0`. The two fabricated claims must pass, and the (c) assertion must go RED — proving the threshold does the work rather than the surrounding code. Revert; record both.

**Blast radius.** `worker/extract/validators.py`, `worker/extract/dedup.py` (embedder reuse), `tests/`, `fixtures/behaviour/` (add a fabricated-proposition case), `docs/ongoing_errors.md` §2 (record 026 as provisional), §3 baseline, §6 queue.

---

## 19. R1 — Media duration and a real coverage check; fix the truncation

**User impact:** the system reads whole episodes instead of the first seven minutes, and can tell when it hasn't.

**Blocked on X1** — see the queue. The re-ingest in step 5 is the largest extraction run this project will have done; it must not run before the entailment guard exists. Issue 027 = A preserved that ordering deliberately.

**The cap is found. Do not go looking for it again.** `scripts/populate_corpus.py:259`:

```python
extra={"max_bytes": 10_000_000},  # 10MB chunk (~7-8 minutes of real audio)
```

which `worker/adapters/podcast.py:111` turns into an HTTP `Range: bytes=0-10000000` header. A deliberate development shortcut, commented as such, never removed. It explains the measurement exactly: four different episodes ending at 416.2, 416.5, 416.5 and 416.5 seconds — **a byte cap on a variable-bitrate MP3 gives near-identical but not equal durations**, which is why the figures looked like a cap rather than a coincidence. The pipeline itself is innocent: `worker/ingest.py:307-318` segments the full duration of whatever file it is handed.

**The trap this sets for the fix — read before writing any code.** R1's other half adds `duration_ms` and wires `min_ratio`. **If duration is measured from the downloaded file, the coverage check is self-confirming**: the truncated download *is* the whole file as far as the pipeline can see, the ratio computes to ~100%, and the check passes on a corpus that is 92% unread. Duration must come from **source metadata, not from the artifact** — `<itunes:duration>` in the RSS item. `parse_feed_xml` (`worker/adapters/podcast.py:83-99`) currently extracts title, `pubDate` and the enclosure URL and ignores everything else.

**A third defect, same layer, same commit.** Every source's `published_at` is **ingest wall-clock time** — all four read `2026-09-03T18:3x`, the minute the script ran. `PodcastRSSAdapter.fetch` stamps `datetime.now(UTC)` while `parse_feed_xml` has already parsed the real `pubDate` and discarded it. `recorded_at` is hand-set in the populate script for three sources and defaulted to ingest time for the fourth (E287). **The product's output is a dated timeline**; ordering by `published_at` today is ordering by ingest order.

**Implementation**
1. Parse `<itunes:duration>` and `pubDate` in `parse_feed_xml`; carry both through `RawSource.metadata`.
2. Add `duration_ms` to `Source`, populated from that feed metadata. Assert ingest **refuses to persist a source without it** — a nullable duration reintroduces the inert check this item exists to remove.
3. Set `published_at` from the feed's `pubDate`, never from `now()`. Set `recorded_at` from the feed as well where available; where it genuinely is not, leave it null rather than defaulting to now.
4. **Wire `min_ratio`**: fail when `span_ms / duration_ms < min_ratio`. `MIN_UTTERANCE_MEDIA_RATIO = 0.05` would pass today's 7.7% and is useless — the floor exists to catch truncation, so it belongs near full coverage. Treat it as provisional and record it as such.
5. Remove `max_bytes` from `populate_corpus.py`, then re-ingest all four episodes at full length. **Record real throughput** — a 90-minute episode is the first honest measurement of ingest cost this project will have.

**Validation**
- **(c)** — `verify_source_productivity` **FAILS against the corpus exactly as it stands today**, reporting ~7.7% coverage on all four sources, *before* any re-ingest. Run it and see it red. *A coverage check that passes on a store known to be 92% unread is not a check, and this is the assertion no stub and no re-run can fake.*
- After re-ingest, every source's `span_ms / duration_ms` clears the floor.
- Unit test, **both directions**: a source with `duration_ms` set and one utterance covering 1% of it → FAIL; the same source at 95% → PASS.
- `duration_ms` is non-null on every source; ingest raises on a source without it.
- `published_at` on all four sources is a 2023–2026 episode date drawn from the feed, and **not** within a minute of `ingested_at`. Assert the inequality — it is the cheapest possible test for this class of defect and it would have caught it.

**Falsify.** Set `min_ratio = 0.0` and confirm today's truncated corpus passes — proving the threshold does the work rather than the surrounding code. Then restore `max_bytes` on one source and confirm the check catches it. Revert both; record both.

**Blast radius.** `worker/entities.py`, `worker/storage.py`, `worker/integrity.py`, `worker/adapters/podcast.py`, `scripts/populate_corpus.py`, the corpus (full re-ingest), `docs/design_data_layer.md` §2, `docs/design_source_acquisition.md` §4 and §5.2, §3, §6.

---

## 20. C0 — Portability workflow; `mlx-lm` as an optional extra · *Issue 024 = B*

**User impact:** the project can be installed on a machine that is not your Mac — which is what the roadmap's rented-GPU ingest step requires, and what it currently cannot do.

**Gap.** `mlx-lm>=0.20.0` is a hard dependency in `pyproject.toml`, and `mlx` publishes **no Linux wheels at all**:

```
$ pip download mlx --platform manylinux2014_x86_64 --only-binary=:all:
ERROR: Could not find a version that satisfies the requirement mlx (from versions: none)
```

So `pip install -e ".[dev]"` fails during resolution on any non-Apple machine — the 9-second CI failure. Two consequences, and the second is the one that matters: the workflow is red, **and the package cannot be installed on the Linux/CUDA boxes the scaling path depends on.**

**Implementation**
1. **Move `mlx-lm` to an optional extra:**
   ```toml
   [project.optional-dependencies]
   apple = ["mlx-lm>=0.20.0"]
   ```
   Base install becomes portable; `pip install -e ".[apple]"` is what you run on the Mac.
2. **Lazy-import mlx inside the runtime.** `worker/extract/runtime.py` must import cleanly with mlx absent — the import moves inside `LocalGemmaRuntime.__init__` or a `_load()`. Missing mlx raises a message naming the fix verbatim: `pip install -e ".[apple]"`. **Do not fall back to a stub** (trap 19); the correct behaviour is a clear failure.
3. **Register and apply a pytest marker.** In `[tool.pytest.ini_options]`:
   ```toml
   markers = ["requires_models: loads a real model; cannot run on a hosted CI runner"]
   ```
   Then mark **every** test that loads MLX, faster-whisper, ECAPA-TDNN or `sentence-transformers`.
4. **Rename the workflow `ci.yml` → `portability.yml`, and its `name:` to `portability`.** This is not cosmetic. A badge reading **CI** implies everything passed; one reading **portability** claims exactly what it verified — the same discipline the fixture/corpus split applies to metrics. A partial green badge is only honest when it is named for its scope.
5. Workflow steps, and nothing more:
   ```yaml
   - pip install -e ".[dev]"          # the real check: does it install off-Mac?
   - ruff check worker/ tests/
   - mypy worker/
   - pytest -m "not requires_models"
   ```

**Validation**
- **The `portability` workflow goes green on GitHub.** ← **(c)** *This one is unusual and worth naming: it cannot be verified locally, because the thing being tested is behaviour on a machine you do not have. Push it and read the result. A local pass proves nothing here — that is the entire point of the item.*
- `pytest -m requires_models` selects a **non-empty** set. *Registering the marker and never applying it would leave the fast suite silently running everything;* this assertion catches that.
- `pytest -m "not requires_models"` completes in **well under a minute** — the runtime is the evidence no model loaded (trap 18, inverted).
- `python -c "import worker.extract.runtime"` succeeds with mlx uninstalled; instantiating `LocalGemmaRuntime` then raises an error whose text contains `.[apple]`.
- `grep -c "mlx" pyproject.toml` shows it only under `optional-dependencies`.

**Falsify.** Move `mlx-lm` back to hard dependencies and push. The workflow must go RED again. Then strip the `requires_models` mark from one model test and confirm the fast suite's runtime jumps — proving the marks are load-bearing rather than decorative. Revert both; record all four outcomes.

**Blast radius.** `pyproject.toml`, `.github/workflows/` (rename), `worker/extract/runtime.py`, every model-loading test, `README.md` if it carries a badge, §3 baseline (add a CI row), §6 queue.

---

## 21. I0 — First real ingest · **SUPERSEDED → R1**

> **Do not open this as a work item.** I0.1 (enrollment) and I0.2 (single-speaker ingest) hold. I0.3's remaining defect is the 10MB download cap, tracked in **§19 (R1)**. This section is kept for the enrollment and panel detail, which R1's re-ingest still depends on.

*Subjects selected: Issue 021 = B.*

**Subjects:** Chamath Palihapitiya, David Sacks, Jason Calacanis, David Friedberg — the four All-In hosts. **Primary source:** the All-In Podcast.

> **Elon Musk is deferred — Issue 023 = A.** He is out of I0 entirely and out of the queue; see §24 for the trigger. He was named in the Issue 021 selection, but his primary medium is X, which is deferred (`master_implementation_plan.md` §9), and a long-form-only corpus would clear the sufficiency gate while measuring a systematically unrepresentative slice of him. **Do not ingest him.** The four hosts are the better first corpus regardless.

**User impact:** the system processes real human beings for the first time. Until now every green gate has been green over nothing.

### Read this before planning — the selection changed I0's shape

This guide previously said *"start single-speaker so diarization is not also on trial."* **That instruction cannot hold as written.** All-In is a four-host panel with interruptions and crosstalk — by `design_source_acquisition.md` §5.4 it is the single hardest attribution case in the design, and trap 11 exists because panels break every positional heuristic *silently*.

That is not a reason to push back on the choice. It is an excellent corpus for this product: five people, the same room, the same recurring topics across years, high-quality audio, hundreds of episodes, and public figures with enough material to clear the sufficiency gate. It also exercises cross-person comparison — which nothing else in the plan would have done this early.

**But the de-risking intent must be preserved by decomposition rather than abandoned.** The split below is the LOOP 5 output; it is already done, so use it rather than re-deriving one.

### Sub-items (LOOP 5 checklist — tick in the same commit)

```
I0.1  Enrollment for the four hosts           [x]
I0.2  Single-speaker ingest, one subject      [x]
I0.3  Multi-speaker panel, 3-4 episodes       [x]
```

---

### I0.1 — Enrollment, and the pre-flight nobody thinks to run

**Why first.** With five speakers who all appear in the same episodes, voice enrollment is not a detail — it is the precondition for any attribution at all. Enrollment must come from sources where attribution is **certain**: a solo interview, a monologue, or their own single-host show. Calacanis's *This Week in Startups* is a natural fit; each of the others has solo interview material.

**Implementation**
1. For each of the four, take a clean single-speaker sample and build a reference voice embedding. **Enrollment is a deliberate, recorded act** — never a by-product of ingest (`design_source_acquisition.md` §5.4).
2. Record, per subject: the source, the exact span used, and its duration.

**Validation**
- **Mutual distinguishability — run this before ingesting anything.** Compute pairwise cosine similarity across all four enrollment embeddings. **Assert every cross-subject pair sits well below `T_low`.** ← **(c)**
  If two subjects' enrollments are close, diarization *will* confuse them on the panel, and you will discover it as silently misattributed claims rather than as a failing test. **Finding that here costs an afternoon; finding it after ingest costs a corpus.**
- Assert each enrollment sample is genuinely single-speaker — run diarization over the sample itself and assert one cluster.

**Falsify.** Enroll the same person twice under two subject ids. The distinguishability assertion must go RED — proving it can detect closeness rather than always passing.

---

### I0.2 — Single-speaker ingest

Preserves the original de-risking intent: prove transcription, gating, extraction and persistence work on real audio **before** diarization is also on trial.

**Implementation.** Take one enrollment-grade single-speaker source and run the whole pipeline: `discover → fetch → normalize → transcribe (dual pass) → diarize → attribute → segment → gate → extract → embed → persist`. Record real wall-clock throughput per stage into the ingest job — nobody collects these later.

**Validation — journeys J1 and J11 on real data**
- Every `text_verbatim` `grep -F`-resolves against the stored transcript. ← **(c)**
- `verify_quotes` and `verify_anchor_chain` report **PASS on a non-empty set**, not `NOT APPLICABLE`.
- **Open one citation URL by hand.** It must land within a couple of seconds of the quote. Record the URL and timestamp in the commit body.
- Word timestamps monotonic and inside media duration.
- `audio_deleted_at` set and audio gone; audio **still present** if any stage raised.
- Re-run ingest: zero new rows, zero re-transcription (J11).

**Falsify.** Corrupt one stored `text_verbatim` by a character. `verify_quotes` must go RED **on real data**.

---

### I0.3 — The panel

**Implementation**
1. **3–4 All-In episodes spanning 2+ years**, chosen on a topic the hosts genuinely return to — AI regulation, open-source models, interest rates, or remote work all qualify. **A reversal needs two claims on the same proposition at different times; episodes chosen for variety rather than topical overlap will produce nothing for P4 to find.**
2. **Do not ingest the archive.** Four episodes, not two hundred. Prove the path first.
3. All four hosts are Tier B on their own show: `venue_type: own_channel`, `audience_stance: friendly`.
4. Expect the failures mocks never surfaced — crosstalk, interruptions, laughter, music stings, three people talking at once. **Each one you fix adds a `fixtures/behaviour/` case in the same commit.**

**Validation**
- **Hand-label a 5-minute segment** with speaker turns, then assert the pipeline's attribution matches it exactly. **Zero cross-attribution.** ← **(c)** This is the real-world N9, and it is a gate at zero, not a target.
- Sub-threshold utterances stored `attribution_confidence: low` and **excluded from every score**, visible in review.
- All four subjects resolvable; claims distributed across hosts rather than collapsing onto one.
- Record the measured attribution confidence distribution. **Parameter 004 gets set here** — from this measurement, marked provisional until the golden corpus grows.

**Falsify.** Swap two hosts' enrollment embeddings. Cross-attribution must go non-zero against the hand-labelled segment.

---

**Prerequisite:** S0. With Musk deferred every host shares the same tier on their own show, so the `SourceSubjectRole` join is not strictly *needed* for I0 — but it lands first anyway, because migrating an empty store costs nothing and migrating a populated one does not.

**Blast radius (whole item).** `worker/` wherever real data breaks it, `fixtures/behaviour/`, §3, `docs/ongoing_errors.md` §2 (parameter 004), `docs/e2e_verification_journeys.md` (mark J1/J11 passing, with the date).

---

## 22. P4 — Tension detection

**User impact:** the product's core claim starts working — *here are two things you said that cannot both be your view.*

**Contract:** `design_rubric_engine.md` §1. Read it fully; this section does not repeat the tension-type table.

**Likely LOOP 5 split:** (1) the reversal self-join, (2) the acknowledgement window, (3) the six preconditions + quarantine, (4) audience divergence.

**Implementation**
1. `worker/tension/detect.py`. The core detector is the self-join in `design_data_layer.md` §4 — **in DuckDB, not in Python.** Pulling the claims table into memory to loop over it is the design error that store was chosen to prevent.
2. Implement all four types: `unacknowledged_reversal`, `acknowledged_update`, `principle_conflict` (stub until P5), `audience_divergence`.
3. **All six preconditions, every type**, or no Tension is created: both `is_own_assertion`; both `attribution_confidence = high`; both stances in `{support, oppose}`; **matching `condition`**; both `quote_span` resolve; both `negation_uncertain = false`.
4. **The acknowledgement window — trap 2, and the thing most likely to be got wrong.** A reversal becomes an `acknowledged_update` if **any** claim on the same proposition, at **any** point in the interval between the two dates, carries a `change_marker`. **Search the whole interval, not just the later utterance.** Getting this wrong converts every honest updater into a flip-flopper and inverts invariant I6.
5. Failing a precondition writes `status: quarantined` with a reason. **Never silently drop** — the quarantine rate is the health metric for the pipeline.
6. Deterministic `tension_id` from the sorted claim pair (`design_data_layer.md` §3), so the same tension cannot appear twice under a different ordering.

**Validation** — fixtures give PASS/FAIL; corpus metrics stay `NOT MEASURED` while `golden/` is empty.
- Fixture **P1** → `unacknowledged_reversal`.
- Fixture **P2** → `acknowledged_update`, **and no Consistency penalty**. ← **(c)**
- **N5** conditional vs unconditional → **no Tension**.
- **N7** hedge then firm → low-weight, not full-weight.
- A claim with `negation_uncertain = true` → quarantined, reason `negation_uncertain`.
- The detector runs as SQL: assert the query plan touches the index, and that no code path materialises the full claims table.

**Falsify.** Narrow the acknowledgement search to the later utterance only. **P2 must flip to `unacknowledged_reversal`.** This is the most important falsification in the project — it is the check that stops the system punishing honesty.

**Blast radius.** `worker/tension/`, `tests/`, `docs/e2e_verification_journeys.md` J5, §3, §6.

---

## 23. P3 — Topic model

**User impact:** you can ask about any topic in your own words and get that person's record on it.

**Contract:** `design_topic_model.md`.

**Likely split:** (1) clustering + labels, (2) free-text resolution + cache, (3) drift guards.

**Implementation**
1. Cluster **propositions**, never raw utterances — they are already stance-neutral and deduplicated. Clustering raw text splits every issue into a pro cloud and an anti cloud, which is precisely backwards.
2. HDBSCAN over proposition embeddings. **Keep noise points** — unclustered residue is the subject's idiosyncratic positions, often the interesting ones, and they stay individually queryable.
3. Label clusters with the local model. **Labels are cosmetic**; retrieval never goes through the label string, so a bad label is a UI annoyance, not a correctness bug.
4. Free-text resolution: normalise → embed with **`search_query:`** prefix (trap 7) → k-NN over propositions embedded with `search_document:` → **expand to full clusters** where a seed proposition is a member. Expansion is what stops a narrow query scoring against three cherry-picked propositions.
5. Cache key **must** include `embedding_model` and `cluster_version` (`design_topic_model.md` §3). Omit them and an embedding upgrade silently rewrites history while every cached number keeps its old timestamp.
6. Drift guard: flag reversal pairs spanning more than the configured window and route them to Update Integrity before Consistency.

**Validation**
- Same query, twice, **in separate processes** → byte-identical proposition set and identical cache key. ← **(c)**
- Query resolving below threshold → `no_coverage`, rendered distinctly from a low score.
- Assert the two task prefixes are actually applied — a unit test that fails if either is dropped.

**Falsify.** Bump `embedding_model` in the cache key. The cache must **miss**, not silently return the stale set.

**Blast radius.** `worker/topics/`, `tests/`, J4, §3, §6.

---

## 24. P5 — Principle extraction

**User impact:** the system can spot a double standard — the same principle applied to one person and not another.

**Contract:** `design_principle_extraction.md`. **Read it fully. This is the highest-risk component in the project.**

**Likely split:** (1) principle extraction with actor slot, (2) actor resolution, (3) stated-distinction detection, (4) conflict detection + significance test.

**Implementation**
1. Extract the **general rule a judgment implies**, actor left as a slot. Prompt asks one question: *"What general rule would have to be true for this specific judgment to follow?"* — and **"return nothing" is the common correct answer.** Most claims imply no principle.
2. `canonical_text` carries **no actor and no verdict** — same discipline as stance-neutral propositions, same failure if violated.
3. **Generality calibration.** Too specific and nothing clusters; too general and everything collides. Measure cluster-size distribution: many small clusters, few giant ones. **A cluster with hundreds of members is too abstract to mean anything** — split or discard.
4. **Actor resolution.** Coreference within the source, plus a per-subject alias map. **Unresolved → `actor: unknown` → excluded from conflict detection. Never guess** — a misattributed actor is a false hypocrisy accusation with a real name on it.
5. **Stated distinction — build this BEFORE the conflict detector.** If the speaker says why two cases differ, the pair is `distinguished`, recorded with its verbatim quote, and excluded from the score. A system that flags principled reasoning as hypocrisy discredits itself.
6. Conflict = same principle, different actor, opposite verdict, no stated distinction, both actors resolved.
7. **Score the pattern, never the instance.** Derive `actor_affinity` from the subject's own corpus only — never an external political map (invariant I2).

**Validation**
- Fixture **P3** → `principle_conflict`.
- Fixture **N6** (stated distinction present) → `distinguished`, **excluded from scoring**. ← **(c)**
- A principle application with unresolved actor never enters a conflict.
- Cluster-size ceiling enforced; assert an over-general principle is rejected.

**Falsify.** Disable stated-distinction detection. **N6 must become a published conflict.**

**Blast radius.** `worker/principles/`, `worker/tension/` (the `principle_conflict` type), `tests/`, J6, §3, §6.

---

## 25. P6 — Rubric engine

**User impact:** the four numbers appear — and, just as importantly, correctly refuse to appear when the evidence is thin.

**Contract:** `design_rubric_engine.md` §0 and §2–§7.

**Likely split:** (1) Consistency + Specificity, (2) Update Integrity, (3) Even-handedness + significance test, (4) sufficiency gates + Assessment materialisation.

**Implementation**
1. **No LLM runs here** (`design_rubric_engine.md` §0). Every axis is arithmetic and SQL over existing rows. If you are writing *"ask the model whether this is consistent"*, stop.
2. **Consistency** — hedging-weighted unacknowledged reversals over eligible propositions.
3. **Specificity** — a **rate**, not a weighted index: `checkable / own-assertion claims`, where checkable means `hedging_level ≤ H_max` AND stance in `{support, oppose}` AND (named entity OR numeric OR temporal anchor). Features from a **pinned NER tagger** + regex, recorded as `nlp_version`. `H_max` is parameter 016 — **measured, and provisional while the corpus is thin.**
4. **Update Integrity** — `(1.0·acked_with_reason + 0.5·acked_without) / total_changes`. **Zero changes yields `null`, never 1.0.** A person who never changed their mind has demonstrated nothing.
5. **Even-handedness** — directional alignment over principle conflicts, **then a two-sided binomial test at p=0.5**. Not significant → `null`, reason `pattern_not_significant`, **and show the conflicts as evidence anyway.**
6. **Per-axis gates**, not one global gate. An Assessment routinely has some axes scored and others null.
7. **Below a gate, do not compute the number.** Not computed-and-hidden — some future client will render it.
8. **No composite. Anywhere.** No average, no letter grade. It rebuilds the trust score the project rejected.
9. Every Assessment records `rubric_version`, `extraction_version`, `detector_version`, `embedding_model`, `nlp_version`.

**Validation**
- Axis below gate: assert the stored document contains `null` and **no numeric value anywhere in the record**. ← **(c)**
- Zero position changes → Update Integrity `null`, not `1.0`.
- Three same-direction conflicts → `pattern_not_significant`, conflicts still returned as evidence.
- Grep the whole codebase for a composite/average across axes → zero hits.
- Every axis score decomposes to the tension ids that produced it.

**Falsify.** Compute a below-gate score and store it behind a suppression flag. The "no numeric value anywhere" assertion must go RED.

**Blast radius.** `worker/rubric/`, `tests/`, `docs/ongoing_errors.md` §2 (record 012/016 as provisional), §3, §6.

---

## 26. P7 — Local API

**User impact:** something outside Python can finally read the corpus.

**Contract:** `design_local_api_and_clients.md`. **§2 (security) is not optional and is now the entire access-control surface** — Issue 015 removed database rules, so there is nothing behind this.

**Likely split:** (1) server + security controls, (2) read endpoints, (3) `POST /resolve`, (4) ingest job endpoints + SSE.

**Implementation**
1. FastAPI. **Bind `127.0.0.1` only** — assert at startup, never `0.0.0.0`.
2. **Bearer token** generated on first run, stored in the OS keychain.
3. **Strict CORS** — the extension origin only. **Reject `*` unconditionally**, including in development, where "temporarily" becomes permanent.
4. Bad token and unknown route return the **same** response, so the API is not a discovery surface.
5. **No write endpoints** (I8). `POST /ingest` enqueues; it does not write to the claim store.
6. Endpoints per §3 of the contract. **Every response carrying a score carries its versions.**
7. **`POST /resolve` — selection-triggered** (Issue 013). Takes `selected_text` + bounded context. Resolves **proposition first**, then topic, then subject-only. Context is for pronoun disambiguation only.
8. **The I2 boundary, enforced by test:** selected text and context live in a request-scoped buffer, are never written anywhere, and **a proposition is matched, never created.** Treat both as hostile input.

**Validation**
- Startup binds loopback; assert a non-loopback bind raises.
- A request from a disallowed origin is rejected; `*` is never accepted.
- **After a `/resolve` call, assert zero rows anywhere with `origin = 'page_context'`.** ← **(c)**
- No route mutates the store — enumerate routes, assert all read-only except the ingest enqueue.
- A score response without its versions fails schema validation.

**Falsify.** Persist the selection text deliberately. The `page_context` assertion must go RED.

**Blast radius.** `worker/api/`, `pyproject.toml`, `tests/`, J8, §3, §6.

---

## 27. P8 — Browser extension

**User impact:** the product exists where you actually read.

**Contract:** `design_ui_direction.md` §6 (two depths) and §1–§5 (rendering rules); `design_local_api_and_clients.md` §5.

**Likely split:** (1) `tokens.json` + build, (2) selection trigger + `/resolve`, (3) Depth 1 overlay, (4) Depth 2 expanded view.

**Implementation**
1. **`tokens.json` first** — colour, type scale, spacing, radii — generating the extension's CSS custom properties, and later Dart constants. This is the concrete form of the Issue 002 requirement that the design language stay consistent.
2. **Selection-triggered.** Fires on highlight. **Never scans on page load.** No toolbar badge, no count — that turns a research tool into an outrage feed.
3. **Depth 1 overlay:** resolved proposition first (not the person), one quote chosen for contrast, all four axes including nulls, `cite` deep link. Anchored near the selection, dismissible, **never modifies the page.**
4. **Three non-error states**, visually distinct from failures: proposition matched · topic only · nothing in corpus.
5. **Depth 2:** full timeline, all axes with evidence, tension cards. Same components, more of the same payloads — **not a second implementation.**
6. Bearer token in extension storage, unreadable by page scripts.

**Validation**
- **A `null` axis renders as its reason, never as `0` or an empty bar.** ← **(c)**
- Every rendered claim shows quote + date + resolvable link (I3).
- Every score shows its `rubric_version`.
- No composite score renders anywhere.
- Page DOM is unmodified after the overlay opens and closes — assert a before/after snapshot.
- Token is not reachable from page context.

**Falsify.** Render a `null` axis through the numeric path. The null-rendering assertion must go RED.

**Blast radius.** `extension/`, `tokens.json`, `tests/`, §3, §6, `docs/design_ui_direction.md` if any rendering rule changes.

---

## 28. Deferred — designed for, not queued

**Elon Musk (Issue 023 = A).** Out of scope until X/Twitter ingest exists. **Trigger:** an `XAPIAdapter` or `XArchiveImportAdapter` lands behind the `SourceAdapter` Protocol and a Musk corpus can be assembled that includes his primary medium. Until then, ingesting him would produce a confident score over a systematically skewed slice, and **invariant I5 would not catch it** — it gates on volume, not composition (trap 24).

**Corpus-composition reporting.** Issue 023's Option B was not selected, so `corpus_composition` is not being built now. It remains the right long-term answer to trap 24 and applies to every subject, not just Musk. Revisit when X ingest arrives or when any subject's corpus draws from a single medium.

**X/Twitter ingest.** Deferred by decision, not difficulty (`master_implementation_plan.md` §9). The adapter Protocol must keep accepting it as a drop-in.

**Proposition-table purge (Issue 027 Option B, not selected).** A was selected, which keeps the orphaned pre-X0 propositions and their embeddings. The remaining cleanup — deleting the five non-fabricated orphans, pruning `proposition_embeddings` to the readable set, and replacing `claim_count` with a computed view — is right eventually and wrong now, because R1's re-ingest repopulates the table. **Trigger:** R1 has landed and the corpus is final. Doing it before then pays for the same migration twice.

---

## 29. Invariants — do NOT change

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

Full text: `master_implementation_plan.md` §3. Code violating one is wrong even if its tests pass.

---

## 30. Contracts

`master_implementation_plan.md` · `design_source_acquisition.md` · `design_claim_extraction.md` · `design_principle_extraction.md` · `design_topic_model.md` · `design_rubric_engine.md` · `design_data_layer.md` · `design_local_api_and_clients.md` · `design_ui_direction.md` · `design_evidence_integrity.md` · `e2e_verification_journeys.md` · `ongoing_errors.md`

---

## 31. Feedback loop — what specs here have got wrong

| What happened | Spec said | Should have said |
|---|---|---|
| Hardcoded throughput reported as measured | "Record tokens/sec" | "Assert a wall-clock floor a real model cannot beat." |
| Hash function passed as an embedding | "Embed with nomic-embed" | "Assert two synonyms score above threshold — a test no hash function can pass." |
| 16 cases reporting `1.000` | "~200 utterances, verified" | Same, **plus** a harness that refuses a metric below a per-class floor. |
| Undeclared dependencies | *(silent)* | "Dependencies land in `pyproject.toml` in the same commit." |
| **Every gate green over an empty corpus** | "J1 green" | **"J1 green *on real ingested data*, with `verify_quotes` PASS on a non-empty set."** A journey signed off against mocks is not signed off. |
| **Validation steps citing fixtures that cannot work, and three that did not exist** | "Fixture P1 → unacknowledged_reversal" | **Check the fixture on disk before writing the assertion that depends on it.** A pair-type outcome needs a pair; a cited class needs to exist. I wrote those steps from the design doc's case table without opening the file — validating shape, not reality, which is the exact error this guide warns about. |

| **`source_count` reported as a measurement for every assessment ever written** | "Compute sufficiency from claims, sources, span" | **"Assert the count *differs* across subjects who genuinely differ."** One subject's number is satisfiable by a constant; a spread is not. The `hasattr` guard made the constant invisible, and every assessment agreed with it. |
| **The integrity pass green over a union of fixtures and live rows** | "Run the ten checks; `NOT APPLICABLE` is not `PASS`" | Same, **plus** "report each population separately and print what was examined." The vocabulary for honesty was already there; the pass just had nothing to apply it to. |
| **A cap found only by reading the script that wrote the corpus** | "Find why every source truncates" | **"Read the code that produced the data before reading the code that processes it."** Three sections of pipeline were searched before `populate_corpus.py`, where the cap sits on one commented line. |

**The pattern: shape is what a stub reproduces perfectly, and a green gate over zero rows is the emptiest shape of all.** Validation must be satisfiable only by the real thing, operating on real data. **And a number that never varies is a shape too** — the newest three entries above are all constants that passed for measurements.
