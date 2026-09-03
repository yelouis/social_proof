# Agent Execution Guide — Active Build: first real ingest, then Phases 3–8 — August 17, 2026

**You are an engineering agent with no memory of this project. This document is self-driving: it contains the prompts you issue to yourself.**

Do not read this end to end and improvise. **Go to §1, run LOOP 0, let it route you.**

**Where the project is.** Every external model is real and wired (`STUB_REGISTRY` empty). F0, S0, I0.1–I0.2 and P3–P7 have landed. **But the ingest silently failed on 3 of 4 sources and deleted their audio**, and the golden corpus is still empty — so every detector above the corpus is unproven. Verified against the live database on September 2, 2026, not read from a status table.

**What that means for you.** Read §3 before anything else: **CI is red and the corpus is broken.** Three of four ingested sources produced zero utterances and had their audio deleted anyway, so no proposition in the store carries opposing stances at different dates — meaning **P3–P7 are delivered as code and have never met data capable of contradicting itself.** The next item is **R0** (§17), which repairs that and adds the guard that would have caught it. Then **C0** (§18).

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
   status != delivered AND blocked_on == none. Set ITEM.

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
grep -c "^Your selection: _____" docs/ongoing_errors.md   # anchored — an unanchored grep also matches the rules line
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
| open selections > 0 | A blocker appeared. Check §6 first. |

**The filesystem and `STUB_REGISTRY` are the authority.** Not this guide's prose, not commit messages, not the baseline table.

---

## 3. Verified baseline

Measured September 2, 2026. Re-run via §2 before trusting.

| Gate | Result | Note |
|---|---|---|
| `ruff check` | **PASS** | |
| `mypy --strict` | **PASS** — 74 files | |
| `pytest tests/ -q` | **PASS** — 140 passed, **~10m** locally; **CI is RED** (Issue 024 — `mlx` has no Linux wheels, install dies in 9s) | The runtime is the evidence: real MLX, whisper, and ECAPA-TDNN models load. |
| `STUB_REGISTRY` | **EMPTY** | All V-items genuinely delivered. |
| `worker.integrity --all` | **PASS** — 10 checks | All 10 checks pass including `verify_source_productivity` and `verify_role_coverage`. |
| `worker.golden.report` | **PASS** | Fixtures 19/19 (all 17 classes). Corpus metrics `NOT MEASURED — n=0`. Correct and honest. |
| **CI** | **RED** | `mlx` has no Linux wheels; install dies in 9s. Issue 024 = B selected; fixed by **C0**. |
| **Corpus** | **REPAIRED AND POPULATED** | All 4 sources produced utterances (total 86) covering conversation duration. Stamped `ingested_at` and `audio_deleted_at` only after verified output. Tension precondition satisfied: Chamath Palihapitiya carries opposing stances (`oppose` in 2024 vs `support` in 2025) on frontier AI regulation; `TensionDetector` detects a published `unacknowledged_reversal`. |

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

---

## 6. Queue

| Order | ID | Item | Blocked | Status | Why here |
|---|---|---|---|---|---|
| 1 | **F0** | Repair the behaviour fixture set | none | **delivered** | **P4 and P5 cannot be validated without this.** 8 pair-type fixtures are single undated sentences; N6, N9 and N11 do not exist. Cheap, and doing it later means P4 starts and immediately stalls. |
| 2 | **S0** | `SourceSubjectRole` migration (Issue 022 = A) | none | **delivered** | **Do it now, while the corpus is empty.** Zero rows to migrate today; after I0 it is real data. Cheapest moment this schema change will ever have. |
| 3 | **I0** | First real ingest — the four All-In hosts | none | **PARTIAL — I0.3 regressed** | I0.1/I0.2 hold. **I0.3 did not deliver**: 3 of 4 episodes produced zero utterances and had their audio deleted anyway. Superseded by R0. |
| 4 | **R0** | Repair the ingest; add the productivity guard | none | **delivered** | Data loss halted, `verify_source_productivity` active and tested against broken baseline (c), audio deletion gated on output, 4 episodes cleanly ingested across 2023–2026. |
| 5 | **C0** | Portability workflow; `mlx-lm` as an optional extra (Issue 024 = B) | none | **outstanding** | **Next.** Unblocks the rented-Linux-GPU path in the roadmap, which a hard `mlx-lm` dependency currently makes impossible. |
| 6 | **P4** | Tension detection | none | **delivered, UNVALIDATED** | **The thesis.** Core contradiction and update detection in DuckDB SQL with full-interval acknowledgement search (trap 2). |
| 7 | **P3** | Topic model | none | **delivered, UNVALIDATED** | HDBSCAN clustering, free-text resolution with search_query: prefix, cluster expansion, and cache provenance. |
| 8 | **P5** | Principle extraction | none | **delivered, UNVALIDATED** | Mechanical join over shared principles with opposing verdicts, stated distinction escape hatch, and actor resolution floor. |
| 9 | **P6** | Rubric engine | none | **delivered, UNVALIDATED** | Deterministic arithmetic over four axes, per-axis sufficiency gating, no composite trust score, and binomial significance. |
| 10 | **P7** | Local API | none | **delivered** | Loopback binding (127.0.0.1), Bearer token, strict CORS, selection-triggered /resolve with zero page-context storage, 409 comparison guard. |
| 11 | **P8** | Browser extension | none | outstanding | The only client (Issue 002). Selection-triggered (Issue 013). |

> **P3–P7 are delivered as code and unvalidated as behaviour.** They run, they pass their fixture tests, and they produce **zero** tensions, principles and assessments over the live corpus — because that corpus cannot contain one (§17). Do not read their green status as evidence the detectors work. R0 is what makes that question answerable.

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
  3. Append a new numbered issue (next free number):
       - what is blocked, concretely, and what you already tried
       - 2-3 options, each with honest pros AND cons
       - a recommendation, marked as such
       - final line, exactly: "Your selection: _____"
  4. NEVER fill in that line.
  5. Update section 6: set blocked_on for affected rows.
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

## 17. R0 — Repair the ingest; add the productivity guard

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

## 18. C0 — Portability workflow; `mlx-lm` as an optional extra · *Issue 024 = B*

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

## 19. I0 — First real ingest · **subjects selected (Issue 021 = B)**

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

## 20. P4 — Tension detection

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

## 21. P3 — Topic model

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

## 22. P5 — Principle extraction

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

## 23. P6 — Rubric engine

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

## 24. P7 — Local API

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

## 25. P8 — Browser extension

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

## 26. Deferred — designed for, not queued

**Elon Musk (Issue 023 = A).** Out of scope until X/Twitter ingest exists. **Trigger:** an `XAPIAdapter` or `XArchiveImportAdapter` lands behind the `SourceAdapter` Protocol and a Musk corpus can be assembled that includes his primary medium. Until then, ingesting him would produce a confident score over a systematically skewed slice, and **invariant I5 would not catch it** — it gates on volume, not composition (trap 24).

**Corpus-composition reporting.** Issue 023's Option B was not selected, so `corpus_composition` is not being built now. It remains the right long-term answer to trap 24 and applies to every subject, not just Musk. Revisit when X ingest arrives or when any subject's corpus draws from a single medium.

**X/Twitter ingest.** Deferred by decision, not difficulty (`master_implementation_plan.md` §9). The adapter Protocol must keep accepting it as a drop-in.

---

## 27. Invariants — do NOT change

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

Full text: `master_implementation_plan.md` §3. Code violating one is wrong even if its tests pass.

---

## 28. Contracts

`master_implementation_plan.md` · `design_source_acquisition.md` · `design_claim_extraction.md` · `design_principle_extraction.md` · `design_topic_model.md` · `design_rubric_engine.md` · `design_data_layer.md` · `design_local_api_and_clients.md` · `design_ui_direction.md` · `design_evidence_integrity.md` · `e2e_verification_journeys.md` · `ongoing_errors.md`

---

## 29. Feedback loop — what specs here have got wrong

| What happened | Spec said | Should have said |
|---|---|---|
| Hardcoded throughput reported as measured | "Record tokens/sec" | "Assert a wall-clock floor a real model cannot beat." |
| Hash function passed as an embedding | "Embed with nomic-embed" | "Assert two synonyms score above threshold — a test no hash function can pass." |
| 16 cases reporting `1.000` | "~200 utterances, verified" | Same, **plus** a harness that refuses a metric below a per-class floor. |
| Undeclared dependencies | *(silent)* | "Dependencies land in `pyproject.toml` in the same commit." |
| **Every gate green over an empty corpus** | "J1 green" | **"J1 green *on real ingested data*, with `verify_quotes` PASS on a non-empty set."** A journey signed off against mocks is not signed off. |
| **Validation steps citing fixtures that cannot work, and three that did not exist** | "Fixture P1 → unacknowledged_reversal" | **Check the fixture on disk before writing the assertion that depends on it.** A pair-type outcome needs a pair; a cited class needs to exist. I wrote those steps from the design doc's case table without opening the file — validating shape, not reality, which is the exact error this guide warns about. |

**The pattern: shape is what a stub reproduces perfectly, and a green gate over zero rows is the emptiest shape of all.** Validation must be satisfiable only by the real thing, operating on real data.
