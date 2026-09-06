# Agent Execution Guide — Active Build: first real ingest, then Phases 3–8 — August 17, 2026

**You are an engineering agent with no memory of this project.**

**Read §1 first; it says where to start.** There is no routing machinery below — you are expected to organise the work yourself. What is fixed is §4 (what you may not change), §5 (what has bitten this project), §7 (what counts as evidence) and each item's own assertions.

**Where the project is.** Twenty-one items delivered. **D3 verified on September 6, 2026 by running its validator over the live corpus**, which is not what its own tests do. The instrument genuinely fires both ways now — over a random 300-claim sample it would flip **25 `support`→`oppose` and 12 `oppose`→`support`** — and D3's root-cause diagnosis was correct and honestly reported: `nomic-embed` cannot separate `P` from `¬P` at the ±0.005 the old margin needed. `hedge` is properly retired, enum and data both.

**Two problems, and the second is the subtle one.**

1. **The validator has never been run over the corpus.** Stance counts are identical to before D3 — support 3,020 / oppose 437 / mixed 212. Roughly **12% of own-assertion claims carry a stance the current validator disagrees with**, and the pipeline fix applies only to future extractions. This is trap 35 again: a stage not named in the instruction did not run, and the instruction was mine.
2. **Its new direction is wrong on live data.** I read the flips by hand. **All four `support`→`oppose` flips I read are false**, every one the same mistake — negation matched without scope. *"the rest of the world's **not** going to **stop** using these models"* reads as opposition to *"the rest of the world will continue to use LLMs"*. The `oppose`→`support` flips all look correct; **the defect is one-directional.**

**And the reason it did not show up: the evaluation set could not contain the failure.** D3 hand-wrote 12 cases, 6 per class, and scored **6/6 both ways with zero confusion**. A random live sample gives **4/4 wrong** in one direction. The cases were composed to illustrate the rule rather than drawn from the corpus, so every one had a negator whose scope was the proposition — the easy shape.

**What that means for you. Do not re-validate the corpus yet** — it would rewrite ~266 claims to `oppose` using the direction that is broken. **D1** (§13u) first: it is still the root cause of the zero, and its polarity work removes one of the two causes of D4's false flips. Then **D4** (§13w), then **D2** (§13v). Read §3 and §5 traps 28–59 first.

**Items now carry per-step checks, written as `> **Verify:**` after the step they belong to.** Run each before starting the next step. Several are **red-first**: they tell you to run something and *watch it fail* before you fix anything, because a check that has only ever been green on repaired data has not been tested.

**Every number, threshold, field name and literal string in the design docs is deliberate. Implement as written.** Where a doc says a value must be *measured* (`ongoing_errors.md` §2), measure it.

---

## 1. Where to start

**Run §2's state-detection block and read its output.** Then read §3, §5, §7 and §6 — the baseline, the traps, the validation standard, and the queue. Then read your item's own section **and every contract doc it cites, in full.** The guide points; the design docs specify. Reading only the guide has produced three of this project's published fabrications.

**Pick the first row in §6 whose status is not `delivered` or `superseded` and whose `Blocked` column is `none`.** If the tree is dirty, deal with that first — someone stopped mid-item and half-finished work is not a base to build on. If a gate §3 records as passing comes back red, that outranks the queue.

**You are trusted to organise your own work.** There is no prescribed routine below beyond §8, which is short. Sequence, batching and when to commit are yours to judge. What is *not* yours to judge is in §4, and what counts as evidence is in §5.

**The one thing to internalise before anything else:** every item in §6 is here because a previous agent's work passed all its gates and was still wrong. Not careless work — *good* work, measured against assertions that could not tell the difference. §5 exists to make that less likely, and §27 records each specific way it has happened.

---

## 2. State detection

```bash
#!/usr/bin/env bash          # run under bash: compgen is a bash builtin
cd "$(git rev-parse --show-toplevel)"
echo "=== HEAD ==="   && git log --oneline -1
echo "=== DIRTY? ===" && git status --porcelain | head
echo "=== GATES ==="
.venv/bin/python -m ruff  check worker/ tests/ fixtures/ golden/ scripts/ 2>&1 | tail -2
.venv/bin/python -m mypy        worker/ tests/ fixtures/ golden/ scripts/ 2>&1 | tail -2
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
| dirty tree | Someone stopped mid-item → §9 |
| `STUB_REGISTRY` non-empty | A V-item regressed. Should be `EMPTY`. |
| `NO DATABASE` | **I0 not delivered.** Nothing real has been processed. |
| a phase module `MISSING` | Its P-item is outstanding, whatever any commit says. |
| `golden/cases.json: 0` | Every corpus metric is `NOT MEASURED`. Expected until subjects are ingested. |
| pytest under ~5s | Impossible now — real models are loaded. Under 5s means something got mocked out. |
| open selections > 0 | A blocker appeared. It is at the **top** of `ongoing_errors.md` §1 — read it there, then check §6 for which rows it blocks. |

**The filesystem and `STUB_REGISTRY` are the authority.** Not this guide's prose, not commit messages, not the baseline table.

---

## 3. Verified baseline

Measured **September 5, 2026** at `0301265`, by querying the live system rather than reading status rows. Re-run via §2 before trusting.

| Gate | Result | Note |
|---|---|---|
| `ruff check` | **PASS** | Clean across worker/, tests/, fixtures/, golden/, scripts/. |
| `mypy --strict` | **PASS on 100 files** | Clean across worker/, tests/, fixtures/, golden/, scripts/. Item G1, W0, S1, U1 & A0 delivered. |
| `pytest tests/ -q` | **PASS** — **235 passed in 332s** | Re-measured September 6 over the 23-source corpus. Well above trap 18's 35s floor. | `requires_models` tests ran (not skipped, no deselection in `addopts`). All 235 unit, behavioural, and falsification tests pass. |
| `STUB_REGISTRY` | **EMPTY** | All V-items genuinely delivered. |
| `worker.integrity --all` | **PASS — 14 checks, independent populations, active sufficiency verdicts, referential integrity, and entailment validation** | G1, E1, N0, P0, W1, W0, S1 & C1 delivered: 14 checks, FIXTURES and CORPUS reported separately with no union; `verify_quotes` examined 3,669 claims; `verify_anchor_chain` examined 24,335 entities; `verify_canonical_ids` examined 3,569 entities (3,477 propositions, 0 principles, 92 roles); `verify_quarantined_propositions_unreachable` examined 1 quarantined proposition (`db3ec63d33cf6f0a`); `verify_assessment_subjects_exist` verified all 8 assessments; `verify_source_productivity` verified 23/23 sources >= 80.0%; `verify_entailment_holds` examined 3,669 claims against current propositions (PASS, all 3,342 published claims >= 0.70; 327 excluded/quarantined). |
| `worker.golden.report` | **PASS** | Fixtures 20/20 (all 17 classes). Corpus metrics `NOT MEASURED — n=0`. Correct and honest. |
| **Working tree** | **CLEAN** | All gates pass; C1 delivered and verified live from DuckDB. |
| **Review site** | **DELIVERED (U1 DELIVERED)** | Served live from DuckDB on local API (`/`, `/episode/{source_id}`, `/claim/{claim_id}`, `/person/{subject_id}`) with `read_only=True` connection guarantee. Static export and `site/` deleted (Issue 033). Assertion (c) full sweep verified (200 OK, verbatim quotes verified, zero quarantined IDs). Empty sections render with honest reasons (§4). Zero links to offset 00:00. |
| **Site read-only guarantee** | **DELIVERED · VERIFIED (A0 DELIVERED)** | Deleted silent fallback to `storage.con.cursor()`. When `Storage` is writable and holding the lock, `create_app` raises `RuntimeError` naming the cause, strictly enforcing the read-only guarantee. Assertion (c) verified in `test_review_site_u1.py`; falsification verified (restoring fallback fails assertion (c)). |
| **Proposition form** | **75.2% ARE FULL CLAUSES** | `design_claim_extraction.md` §2 specifies a noun-phrase *matter at issue* with polarity stripped (`federal licensing of frontier AI models`). 2,615 of 3,477 contain a finite verb, and many carry **positive** polarity — *"Forces should be allowed to play out"*, *"democrats are favored to win the house"* — which §2 forbids and the validator does not catch, since it rejects only negative forms. **This is why nothing merges.** Item D1. |
| **Merge rate** | **UNCHANGED BY A 6× CORPUS** | 0.954 → **0.948** propositions per claim; **95.5% singletons**. Of the 63 propositions spanning 2+ episodes, 9 carry more than one stance and **0 are cross-source `support`↔`oppose`.** `T_dedup = 0.86` was measured over a corpus replaced twice since. Item D2. |
| **Stance direction** | **BIDIRECTIONAL, BUT WRONG ONE WAY** | D3 delivered a genuinely two-way validator — over 300 live claims it would flip 25 `support`→`oppose` and 12 `oppose`→`support`. **But all four `support`→`oppose` flips I read are false**: negation is matched anywhere in the quote with no scope test, so *"not going to stop using"* reads as opposition to *"will continue to use"*. The 12-case hand-written eval scored 6/6 both ways and could not see it. **It has also never been run over the corpus** — stance counts are unchanged, so ~12% of claims carry a stance the validator disagrees with. Item D4. |
| **`hedge`** | **RETIRED (D3 DELIVERED)** | Enum standardised to `support\|oppose\|mixed` across entities, schema, prompt and scripts; the single legacy claim migrated to `support` with `hedging_level=0.7`. **0 claims carry `hedge`.** Verified. |
| **Corpus overlap** | **67 PROPOSITIONS SPAN 2+ EPISODES (C1 DELIVERED)** | 56 span 2 episodes, 11 span 3 episodes (up materially from 4). Materially clears Assertion (c) under Issue 030 = A. Contiguous 20-episode chronological expansion fixed prior to run. |
| **CI / Portability** | **PASS** | `portability.yml` tests base install without Apple extra; runs lint, mypy, and non-model tests across all 5 directories. |
| **Corpus** | **POPULATED, FULL COVERAGE (R1, N0, P0, W1, W0 & C1 DELIVERED)** | 23 contiguous sources (20 contiguous + 3 historical bootstrap episodes), **20,666 utterances**, **3,669 claims**, **3,477 propositions** (3,476 active, 1 quarantined), 92 roles, 8 assessments. Coverage across all sources >= 80.0% (Parameter 029). Feed duration and pubDate parsed; zero-claim rule strictly verified across every source. |
| **Propositions** | **3,476 ACTIVE (W2 & C1 DELIVERED)** | Deduplication unified at empirical Parameter 008 ($T_{\text{dedup}} = 0.86$) with strict re-point entailment validation (`T_ENTAIL_HIGH = 0.70`) and zero unbound pronouns or indexicals. 67 multi-episode propositions. Top merged clusters verified as single propositions rather than broad topics. Falsification verified. |
| **`source_count`** | **MEASURED** | All 4 hosts draw on all episodes. Resolved through the utterance anchor chain, `hasattr` removed, I3 violation raises. Item M0 delivered, independently confirmed against ground truth. |
| **`source_roles`** | **92 ROWS FOR 92 PAIRS (G1 & C1 DELIVERED)** | Generated via `compute_role_id()`. 92 rows across 23 sources for 4 hosts. `verify_canonical_ids` and `verify_role_coverage` PASS across all 20,666 utterances. |
| **Sufficiency verdict** | **DELIVERED · VERIFIED (E2 DELIVERED)** | Parameter 012 sufficiency floor enforced strictly on inputs BEFORE scoring (`MIN_CLAIMS=3`, `MIN_SOURCES=1`, `MIN_SPAN_DAYS=0`). Dependency runs one way: verdict -> scores. When `passed` is False, all axis calculations are suppressed (`reason: "insufficient_corpus"`). Live corpus hosts all clear sufficiency on the merits. |
| **Corpus — claims** | **3,669 CLAIMS (N0, P0, W0, S1, W2 & C1 DELIVERED)** | Ingested and extracted across all 20,666 utterances. Validator 7 (`validate_stance_direction`) and I7 speech act sensitivity active in prompt `v1.5` and validator chain. Every source contributes >= 1 claim. |
| **Assessments** | **EVALUATED, REFERENTIALLY GUARDED** | 8 rows across 2 topics (`top_ai_reg`, `global`). Sufficiency verdict `passed: True` across all 4 enrolled hosts. |
| **Published tensions** | **0 PUBLISHED · 3 QUARANTINED (100% QUARANTINE RATE)** | Both fabrications (`461e3d1dbf30bde4` and `4b812a6b0dc604b0`) quarantined as `fabricated_proposition`, joining `0068adec4b1501c6`. All 8 assessments recomputed without them (`design_evidence_integrity.md` §5). `verify_quarantine_not_rendered` examines quarantined tensions and passes; none appears in any assessment's `axis_evidence`. Item Q0 delivered. |
| **Candidate pairs** | **0 PUBLISHED (6 EXAMINED UNDER C1)** | Evaluated with honest denominator via `evaluate_candidate_pairs`: 6 pairs examined on live corpus, all 6 rejected for `same_source_stance_conflict` and routed to review surface; 0 false reversals published (all 7 initial candidates hand-read and corrected for tone/negation mislabelling). Falsification verified: Pre-expansion corpus yields 0 examined candidates. |
| **Reversals — same-source disqualification** | **DELIVERED · VERIFIED (T1 DELIVERED)** | Same-source opposing claims automatically disqualified from `unacknowledged_reversal` and routed to `stance_conflict_reviews` with reason `same_source_stance_conflict`. Parameter 032 `MIN_REVERSAL_GAP_DAYS = 0.0` (provisional). Candidate evaluation reports exact denominator. Item T1 delivered. |
| **`stance`** | **VALIDATED (S1 DELIVERED)** | Validator 7 (`validate_stance_direction`) certifies directional alignment ($P$ vs $\neg P$) with margin $\delta = 0.05$. Inverted oppose claims corrected to support. Genuine oppose claims survive. |
| **`is_own_assertion`** | **SENSITIVITY RAISED — 7.78% (S1 DELIVERED)** | Over 90 non-assertive quotes excluded (`exclusion_reason="question"` or `"hypothetical"`), maintaining floor > 5.0%. Measured via `get_exclusion_rate()`. |
| **Propositions — residual indexicals** | **0% — ZERO UNBOUND PRONOUNS / DEICTICS (W2 DELIVERED)** | Extended validator to enforce the principle of self-containment against the property: rejects sentence-initial pronouns/deictics, unbound third-person pronouns (`they/their`, `he/his/him`), and comparatives without relata (`the same`, `such`, `the other`). Preserves bound pronouns with internal antecedents (`Moderna patented its mRNA technology`). Pre-repair RED state verified (132 failing propositions across 139 claims). Re-extracted under `v1.5` prompt; active store contains exactly 0 unbound propositions (Assertion c). Both target false candidate pairs eliminated. Item W2 delivered. |
| **Entailment after merge** | **DELIVERED · VERIFIED (W1 DELIVERED)** | Re-pointing strictly validates entailment (`T_ENTAIL_HIGH = 0.70`); refuses merge when quote does not entail target proposition. Check #14 `verify_entailment_holds` asserts entailment holds across all stored claims against current propositions (PASS on 1,288 claims). Falsification verified. |
| **Propositions — indexical** | **0% — ZERO INDEXICAL PROPOSITIONS (W0 DELIVERED)** | 192 indexical propositions across 204 claims identified and repaired. Fixed prompt `v1.3` with Rule 3 explicitly prohibiting indexical frames; added `validate_self_contained` validator (`proposition_not_self_contained`); Precondition 6 in tension detector. Cleaned live corpus contains exactly 0 indexical propositions. Item W0 delivered. |
| **`t_dedup`** | **DELIVERED · VERIFIED (W1 DELIVERED)** | Unified at `T_dedup = 0.86` with single source of truth in `worker/extract/dedup.py`. Hardcoded `0.85` removed from `worker/extract/extract.py`. |

---

## 4. Standing constraints

- **One item = one commit**, the *why* in the body. Too big → split it (§9).
- **Never fill in a `Your selection: _____` line.**
- **A stub is not a delivery.** Real dependency runs, or it isn't done.
- **Dependencies land in `pyproject.toml` in the same commit.**
- **Never print a number you did not measure.** Constants, projections from constants, and metrics below their floor render `NOT MEASURED`.
- **Every integration item needs one assertion a stub cannot satisfy** (trap 17). The single most important rule here.
- **A guard that has never failed has not been tested.** Falsification is mandatory (§7, §8 step 6).
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
27. **Local green does not mean CI green.** §2's block checks the local battery and has no CI signal at all, so CI stayed red across several commits unnoticed (Issue 024).
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
44. **A constant documented in one module and re-defaulted in a caller's signature runs at the caller's value.** `dedup.py` and `ongoing_errors.md` §2 both record `T_dedup = 0.86`; `extract.py:26` defaults 0.85 and wins. **Grep for the parameter name across every signature, not just its definition** — the measurement is worthless if it describes a value that never executes.
40. **Deterministic IDs only hold while every writer uses the helper.** Two `scripts/` build `f"role_{sid}_{subj_id}"` by hand instead of calling `compute_role_id`, so the primary key sees two different ids for one pair and the "every write is an upsert" guarantee silently becomes "every run inserts again." **Grep for hand-built id strings, not just for the helper's callers** — and note that `scripts/` is where this happened, because `scripts/` is outside every gate.

---

## 6. Queue

| Order | ID | Item | Blocked | Status | Why here |
|---|---|---|---|---|---|
| 1 | **D1** | Propositions drifted back into full clauses | none | **outstanding** | **Still the root cause of the zero**, and its polarity fix removes one of the two causes of D4's false flips. Its re-extraction will run validator 7 over everything, so D4 must not ship a broken direction into it — but D1's own work does not depend on D4. |
| 2 | **D4** | Validator 7's new direction is wrong on live data | **D1** | **outstanding** | Bidirectional at last, and all four `support`→`oppose` flips read by hand are false. The 12-case curated eval could not detect it. **Do not re-validate the corpus until the false-flip rate is measured.** |
| 3 | **D2** | Re-measure parameter 008 against a corpus that exists | **D1** | **outstanding** | `T_dedup = 0.86` merges 4.5% of the table and was fitted to a 1,499-proposition corpus that was 7% indexical attractors, replaced twice since. |
| 4 | **D3** | Validator 7 has only ever corrected in one direction | none | **delivered · verified** | Augmented Validator 7 with syntactic negation analysis; standing bidirectional correction counters reported (`stance_corrected_to_support`, `stance_corrected_to_oppose`); 12 hand-labelled cases verified with 4 support $\to$ oppose corrections (Assertion c) and 2 oppose $\to$ support corrections; 0 confusion errors; falsification verified; `hedge` resolved to float level across schema, entities, and DB; 240/240 tests pass. |
| 5 | **A0** | The site's read-only guarantee has a silent escape hatch | none | **delivered · verified** | Deleted silent fallback to `storage.con.cursor()` in `worker/api/server.py`; `create_app` raises `RuntimeError` if read-only connection cannot be established; Assertion (c) verified in `tests/test_review_site_u1.py`; falsification verified (restoring fallback fails assertion (c), reverting passes); all 235 tests pass. |
| 6 | **C1** | Expand the corpus chronologically (**Issue 030 = A**) | none | **delivered · verified** | Expanded from 4 to 23 contiguous sources (20 contiguous All-In episodes E279–E288 + 3 historical bootstrap episodes), 20,666 utterances, 3,669 claims, 3,477 propositions, 92 roles. Multi-episode propositions rose from 4 to 67, satisfying Assertion (c). Candidate evaluation reports exact denominator (6 examined, 6 rejected by same-source rule, 0 false reversals published after hand-reading). Zero-claim rule strictly verified across all 23 sources; all 14 integrity checks PASS. falsification verified. |
| 7 | **S1** | Nothing validates `stance` or `is_own_assertion` | none | **delivered · verified** | Implemented Validator 7 (`validate_stance_direction`) certifying directional alignment ($P$ vs $\neg P$, Parameter 031 margin $\delta=0.05$); raised Invariant I7 speech-act sensitivity (regex detection of interrogative and hypothetical quotes). Corrected 2 mislabelled oppose claims to support (`af95392de868a188` and `7f571f16d81af8c5`), downgraded 97 non-assertive quotes, raising I7 exclusion rate to 7.78% (106/1,362 claims, floor > 5%). Eliminated all 4 target candidate pairs identified in §13n. Surviving own-assertion oppose claims: 73 ($\ge 50$). All 14 integrity checks PASS. Both threshold directions and falsification verified. |
| 8 | **T1** | A reversal needs time between its halves | none | **delivered · verified** | Implemented same-source automatic disqualification (`source_a_id == source_b_id`) in `worker/tension/detect.py`; routed disqualified same-source opposing pairs to review surface `stance_conflict_reviews` in `worker/storage.py` with reason `same_source_stance_conflict`; added Parameter 032 `MIN_REVERSAL_GAP_DAYS = 0.0` (unmeasured / provisional); implemented `CandidateEvaluationReport` reporting exact examined denominator and rejection reasons. Verified: all 5 baseline pairs disqualified and routed to review table; 0 reversal candidates over live corpus (1 examined, 1 rejected by same-source rule); synthetic cross-episode pair accepted (1 published reversal); falsification verified (disabling same-source condition causes candidates to reappear; restoring clears them to 0). |
| 9 | **W2** | Self-containment, the rest of the pronouns | none | **delivered · verified** | Completed self-containment against the property: extended `validate_self_contained` (`proposition_not_self_contained`) to reject sentence-initial pronouns/deictics, unbound third-person pronouns (`they/their`, `he/his/him`), and comparatives without relata (`the same`, `such`, `the other`), while preserving bound pronouns (`Moderna patented its mRNA technology`). Updated prompt to `v1.5` (`gemma-3-27b-it:v1.5:s1`). Pre-repair RED state verified (132 failing propositions across 139 claims). Re-extracted affected candidate utterances under live MLX Gemma (65 new clean claims produced, 63 invalid proposals rejected by validator), purged orphaned propositions, deduplicated at T=0.86 with W1 entailment guard. Post-repair store verified with exactly 0 unbound propositions (Assertion c). Both target false candidate pairs eliminated. falsification verified. 14/14 integrity checks and 225/225 tests PASS. |
| 10 | **U1** | The review site, served live from DuckDB (**Issues 028 + 033**) | none | **delivered · verified** | Served live from DuckDB per request on local API (`/`, `/episode/{source_id}`, `/claim/{claim_id}`, `/person/{subject_id}`) with `read_only=True` connection guarantee. Static export and `site/` deleted (Issue 033). Shared query layer (`worker/api/queries.py`) enforces structural exclusion of quarantined tensions (`status='published'`) and quarantined propositions (`status='active'`), verifies quotes verbatim against utterances per claim, and enforces zero links to offset 00:00 (disabled with explicit reason). Templates (`worker/api/templates.py`) render all sections always with honest absence reasons (§4). Assertion (c) full sweep over all 1,288 claims verified (HTTP 200, 0 quarantined IDs, verbatim quotes verified). Render time 4.27ms for heaviest route. 9/9 tests pass. |
| 11 | **Q0** | Quarantine both published tensions | none | **delivered · verified** | Quarantined both published tensions (`461e3d1dbf30bde4` and `4b812a6b0dc604b0`) as `fabricated_proposition`, joining `0068adec4b1501c6`. Recomputed all 8 assessments without them (`design_evidence_integrity.md` §5). `verify_quarantine_not_rendered` examines 3 quarantined tensions and passes; no assessment mentions either tension ID. Quarantine rate is 3/3 (100.0%). Falsification verified (re-publishing turns Assertion (c) RED). |
| 12 | **W1** | Entailment does not survive re-pointing | none | **delivered · verified** | Re-pointing strictly gated by quote entailment validation (`T_ENTAIL_HIGH = 0.70`). Refused 8 candidate claim merges where entailment fell below floor (0.6444–0.6962), leaving 1,430 active propositions (69 merged away). Check #14 `verify_entailment_holds` implemented in `worker/integrity.py` with DuckDB caching (`claim_entailment_cache`), passing on 1,501 claims. Single source of truth for `T_dedup = 0.86` across `dedup.py` and `extract.py`. Assertion (c) and falsification verified (disabling re-validation fails `verify_entailment_holds` with 6 claims). |
| 13 | **W0** | Propositions must be self-contained, not indexical | **W1** | **delivered · verified** | Stripped actor frames and unbound indexicals at extraction: fixed prompt to `v1.3` (`gemma-3-27b-it:v1.3:s1`) with Rule 3; implemented `validate_self_contained` validator (`proposition_not_self_contained`) running before entailment; added Precondition 6 to tension detection. Pre-repair RED state verified (192 indexical propositions across 204 claims). Live corpus repaired: old indexical claims deleted, 204 candidate utterances re-extracted (122 indexical rejections, 65 clean new claims produced), orphaned propositions purged, deduplicated at T=0.86 with W1 entailment gate. Zero propositions now match indexical patterns (down from 7%). Top 5 merged clusters inspected and confirmed single propositions. 4 multi-source diff-date propositions, 4 concordant candidate pairs examined, 0 opposing-stance false positives from attractor propositions. All 14 integrity checks PASS on fixtures and corpus. |
| 14 | **G1** | Two `role_id` schemes; `scripts/` outside every gate | none | **delivered · verified** | `scripts/` brought under `ruff` and `mypy` gates (0 errors on 86 files). Hand-built `f"role_..."` replaced with `compute_role_id()` across `scripts/`. 16 duplicate rows deleted (32 → 16). `verify_canonical_ids` extended to cover `source_roles` and pair uniqueness. |
| 15 | **E2** | The sufficiency verdict is circular | none | **delivered · verified** | Broken circularity: `passed` derived strictly from inputs (`claim_count >= 3`, `source_count >= 1`, `span_days >= 0`, Parameter 012) BEFORE scoring. Dependency is one-way (verdict -> scores); if `passed` is False, axis scoring is suppressed. Assertion (c) and the other direction verified. |
| 16 | **P0** | Proposition dedup never runs | none | **delivered · produced two fabrications** | Wired semantic deduplication into extraction path (`ClaimExtractionPipeline`). Parameter 008 measured empirically at $T_{\text{dedup}} = 0.86$ over 1,499 live propositions; ambiguous-band adjudication does not earn its cost. Collapsed to 1,425 active survivors (74 merged away); 10 multi-source diff-date propositions; 83 candidate pairs evaluated, yielding 2 published unacknowledged reversal tensions. Both threshold directions and falsification verified (0.999 collapses to singletons/0 candidates; 0.30 causes absurd merge; 0.86 GREEN). |
| 17 | **E1** | The assessment layer is unguarded | none | **delivered · half** | Referential integrity, the missing-key FAIL, the removed default, the deleted pollution row and read-only tests are all real and verified. **The verdict semantics are not — see E2.** |
| 18 | **N0** | Extract over the full corpus | none | **delivered · verified** | Extraction is real and verified: 1,501 claims across all 4 episodes (284 / 332 / 408 / 477), Validator 6 rejecting 194 of 1,686 (11.5%), parameter 026 re-measured over n=1,501. With P0 deduplication delivered, candidate pairs considered across subjects is 83 (71 concordant, 10 same-date, 2 evaluated by detector yielding 2 published tensions), fully satisfying Assertion (c). |
| 19 | **G0** | Repair the `mypy` gate | none | **delivered · verified** | Walrus narrowing at `test_segmentation_x0.py:53`; mypy clean on **80** files (re-measured). |
| 20 | **M0** | `source_count` is a constant, not a measurement | none | **delivered · verified** | Resolved through utterance anchor chain without `hasattr`; Sacks/Friedberg 2, Jason/Chamath 1, zero claims 0, unresolvable raises. |
| 21 | **E0** | Integrity pass must check the corpus, not a union | none | **delivered · verified** | FIXTURES and CORPUS evaluated and reported independently; assessments loaded from DB; examined counts reported. |
| 22 | **D0** | Proposition table repair (**Issue 027 = A**) | none | **delivered · verified** | Normalized canonical IDs, merged three forked rows, backfilled embeddings for all 8 live propositions, quarantined fabricated db3ec63d33cf6f0a, and added structural read filters. |
| 23 | **X1** | Entailment validator (Issue 025 = C) | none | **delivered · guarantee voided by P0** | Validator 6 added after quote resolution; MIN_QUOTE_TOKENS=7, T_ENTAIL_LOW=0.60, T_ENTAIL_HIGH=0.70; fabrications rejected, 9 live claims pass, prefix sensitivity verified, ambiguous band quarantined and excluded from axis_evidence. **Correct and wired, but has never run over extraction output it did not inherit — all rejection counters are zero. N0 is its first real test.** |
| 24 | **R1** | Media duration + real coverage check; fix truncation | none | **delivered · audio only** | Feed duration parsed, published_at preserved, MIN_UTTERANCE_MEDIA_RATIO=0.80 enforced, 10MB byte cap removed; full re-ingest yields 4,219 utterances at 99.7%–100.0% coverage across all 4 sources. **The claims were not regenerated — see N0.** |
| 25 | **F0** | Repair the behaviour fixture set | none | **delivered** | 20/20 across all 17 classes. |
| 26 | **S0** | `SourceSubjectRole` migration (Issue 022 = A) | none | **delivered** | Landed while the corpus was empty, as intended. |
| 27 | **I0** | First real ingest — the four All-In hosts | none | **superseded → R1** | I0.1/I0.2 hold. I0.3's remaining work is the truncation, tracked in R1. **Not a to-do; do not open it.** |
| 28 | **R0** | Repair the ingest; add the productivity guard | none | **superseded → R1** | Empty-source bug fixed and deletion gated. The coverage half is R1. **Not a to-do; do not open it.** |
| 29 | **X0** | Quarantine the fabricated tension; fix segmentation | none | **delivered** | Verified independently: tension quarantined, claims removed, 9 survivors read one by one and genuinely supported. |
| 30 | **C0** | Portability workflow; `mlx-lm` optional (Issue 024 = B) | none | **delivered** | |
| 31 | **P4** | Tension detection | none | **delivered · fixtures only** | |
| 32 | **P3** | Topic model | none | **delivered · fixtures only** | |
| 33 | **P5** | Principle extraction | none | **delivered · fixtures only** | |
| 34 | **P6** | Rubric engine | none | **delivered · fixtures only** | **See E1** — it never records the I5 verdict it computes, so the check for suppressed scores cannot fire. |
| 35 | **P7** | Local API | none | **delivered** | `/resolve` now filters structurally on `status='active'` + live-claim existence; the 8 reachable propositions all carry claims. Verified. |
| 36 | **P8** | Browser extension | none | **delivered** | |

> **P3–P7 are delivered as code and still unvalidated as behaviour.** R1 gave them the audio; N0 gave them 1,501 claims. They still report zero, and the reason has moved rather than gone: it is no longer a thin corpus but a **structural** one. Every claim owns a private proposition, so the detector's join has nothing to match. A corpus that cannot *represent* a reversal produces zero whether the detector works or not — trap 26, one layer below where it was first found. **P0 is the last prerequisite; E2 is what makes the answer trustworthy when it arrives.**

**Delivered — do NOT rework:** V0–V6 (all externals real, `STUB_REGISTRY` empty), U0–U13 (storage, integrity, adapters, reconciler, segmentation, gate, validators). Detail in git history; §10 has the short list.

**IDs are labels, not sequence numbers.** Follow the **Order** column.

---

## 7. Validation standard

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

**Re-run every gate yourself before trusting §3.** This file has recorded a gate result that did not match reality more than once.

**Report zero with its denominator.** "No tensions found" over an empty candidate set and "no tensions found" over 400 examined pairs look identical in a status table and mean opposite things.

**When you substitute anything for what the item specifies — a different mechanism, a narrower scope, a value the item did not name — say so in the commit body.** Several items here were delivered exactly as written and still wrong; the substitution log is how the next verification pass finds out which.

---

## 8. The loop

Not a routine to execute mechanically. It is the shortest description of what a finished item looks like here; adapt the order to the work.

```
(1)  READ the item's section and every contract doc it cites, in full.
(2)  If the item says "determine X first" or "run it before the repair",
     DO THAT AND RECORD THE OUTPUT before writing the fix.
(3)  WRITE the assertion marked (c) first. RUN IT. WATCH IT FAIL.
     Put the failing output in the commit body. If it passes before you
     have written anything, the assertion is wrong -- fix it, or say so.
(4)  IMPLEMENT as specified. RECORD ANY SUBSTITUTION YOU MAKE.
(5)  VALIDATE step by step, using the per-step checks in the item.
     Do not batch them to the end; a step that silently did nothing is
     cheapest to find immediately after it ran.
(6)  FALSIFY: remove the fix or neuter the threshold, confirm (c) goes
     red, restore. Record both outputs.
(7)  READ THE OUTPUT a person would see. Not the counts -- the rows.
(8)  ENUMERATE every caller of anything you changed and run them.
(9)  RE-RUN the full battery from section 2, exit codes bare.
(10) COMMIT: one item, the WHY in the body, with the numbers you measured,
     the falsification results, and any substitution. Update every doc the
     change invalidates in the same commit.
```

---

## 9. When the situation is unusual

**A gate §3 records as passing comes back red.** It outranks the queue. Find the commit that turned it, then decide: the code is wrong (fix the code), the test is wrong (fix the test **and say so explicitly in the commit body** — this is the only circumstance in which a test may change to reach green), or §3 is stale (correct §3 and note the drift). **Never weaken an assertion, delete a test, or narrow a scope to reach green.** If that looks like the answer, it is a question for Louis.

**The tree is dirty.** Someone stopped mid-item. Read the diff, decide whether it is worth finishing or reverting, and say which you did. Do not build on top of it.

**The item is too big for one commit.** Split it into sub-items that each land with a coherent message and their own validation, and tick them in the same commit. Say in the commit body which sub-item this is and what remains.

**The item needs a decision that is Louis's.** File it at the **top** of `ongoing_errors.md` §1 with what is blocked, what you already tried, 2–3 options with honest pros *and* cons, a marked recommendation, and a final `Your selection: _____` line. **Never fill that line in.** Then set `Blocked` in §6 and stop; do not guess and proceed.

**The item's spec looks wrong.** Say so, in the commit body or as a new issue, and record what you did instead. **Several items here were implemented exactly as written and were still wrong, because the spec was.** Being right about that is worth more than being compliant.

---

## 10. Delivered — do NOT rework

**V0–V6:** fabricated-throughput removal; stub registry + CI guard; fixture/corpus split with metric floor and parameter-readiness report; real `nomic-embed-text-v1.5` embeddings with task prefixes; real `faster-whisper` dual-pass transcription with audio disposal; real `pyannote.audio` diarization; real Gemma runtime on MLX. `STUB_REGISTRY` is empty.

**U0–U13:** integrity pass (eight checks, `NOT APPLICABLE` correctly distinguished from `PASS`); DuckDB with `vss`, `FLOAT[768]`, HNSW cosine, deterministic IDs; three source adapters behind one Protocol; dual-pass reconciler; segmentation; extraction gate; five post-extraction validators.

**Accepted equivalents — do not "fix" back:** the `TranscriptionEngine` Protocol + `Mock` test-double split; `LocalGemmaRuntime`'s shape. Both better than the spec implied.

---

## 11. F0 — Repair the behaviour fixture set

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

## 12. S0 — `SourceSubjectRole` migration · *Issue 022 = A*

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

## 12b. R0 — Repair the ingest; add the productivity guard · **SUPERSEDED → R1**

> **Do not open this as a work item.** The empty-source bug is fixed and audio deletion is gated; both hold. The coverage half was never implemented and is tracked in **§15 (R1)**, which also names the root cause. This section is kept for the reasoning only.

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

## 13. X0 — Quarantine the fabricated tension; fix segmentation

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

## 13b. G0 — Repair the `mypy` gate · *red-gate repair*

**This is a red-gate repair (§9), not a queue item.** A red gate outranks the queue; nothing below it starts until this is green.

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

## 13c. M0 — `source_count` is a constant wearing a measurement's name

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

## 13d. E0 — The integrity pass must check the corpus, not a union with fixtures

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

## 13e. D0 — Proposition table repair · *Issue 027 = A*

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

Leave orphan embeddings in place. Louis selected A: nothing is purged. *(Pruning `proposition_embeddings` down to the readable set is a B-time cleanup; noted in §24 so it is not lost.)*

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

## 13f. E1 — The assessment layer is unguarded · **DELIVERED IN HALF**

> **Verified September 5, 2026.** The referential half is real: `verify_assessment_subjects_exist` is present and wired (13 checks), the `subj_nonexistent_subject` row is gone, a missing `passed` key now FAILs, and tests open the corpus `read_only=True`. **The verdict half is not.** `engine.py:142` sets `passed = any_scored`, computed from the scores the check exists to police, so `verify_no_suppressed_scores` is now tautological. **See §13i (E2).** Kept below for the reasoning.

**User impact:** the check that exists to stop a score being published over insufficient evidence becomes able to fire at all.

**Contract:** `design_evidence_integrity.md` §3 · `design_rubric_engine.md` (sufficiency) · invariant **I5**.

**Gap — two defects, found by running the pass E0 built.**

**(a) `verify_no_suppressed_scores` is inert on every real assessment.** `worker/integrity.py:222` reads

```python
passed = a.sufficiency.get("passed", True)
```

and `worker/rubric/engine.py:103` writes a sufficiency dict containing **`claim_count`, `source_count`, `span_days` — and no `passed` key.** So on every real assessment the check reads **its own default**, `True`, meaning *sufficient*, and the loop body never executes. It fires only on fixtures, which set the key explicitly (`fixtures/fixture_loader.py:163` sets `True`, `tests/test_integrity.py:103` sets `False`) — which is why it has always looked healthy.

E0 is what made this visible rather than what caused it. The CORPUS section now prints `verify_no_suppressed_scores [PASS] (examined: 9)`, which reads as nine real assessments verified and is nine defaults read. **Before E0 the check examined one fixture row and the question could not be asked.**

This is trap 29 and trap 31 on the same line: a default that manufactures the safe-sounding value, on a key nobody writes.

**(b) Nothing relates an assessment to a subject.** `subj_nonexistent_subject` has an assessment row in `social_proof.duckdb` and **no row in `subjects`**. `verify_anchor_chain` walks claims → utterances → sources and stops there, so all 12 checks pass over it. A test wrote into the production corpus and the integrity pass is content.

**Implementation**

1. **Make the engine write the verdict it already computes.** Find where the I5 decision is actually applied — the per-axis gating in `worker/rubric/engine.py` — and persist it as `sufficiency["passed"]: bool`, plus `sufficiency["reason"]` when False. **If no single place makes that decision, that is itself the finding:** I5 is being applied per-axis and never recorded, and it must be recorded before anything can check it.
2. **Remove the default.** `passed = a.sufficiency["passed"]`; a missing key **FAILS** the check with reason `sufficiency_verdict_missing`. A verdict that was never written is a defect, not a pass — that is the entire lesson of the line being replaced. Do not substitute `.get("passed", False)`; a silent flip to the conservative value is the same bug wearing the other mask.
3. **New check `verify_assessment_subjects_exist`** — every assessment's `subject_id` resolves in `subjects`, and its `topic_id` in `topics`. Cheap, and it closes the referential gap the anchor chain never covered.
4. **Delete the `subj_nonexistent_subject` assessment** from the corpus. Do it after step 3 can prove it was there.
5. **Stop tests writing to the production corpus.** Reads are legitimate — X0's assertion (c) needs real data and several tests open `Storage("social_proof.duckdb")` deliberately. **Writes are not.** Open the corpus `read_only=True` in tests; any test needing to write takes a temp copy.

**Validation**

- **(c)** — `verify_no_suppressed_scores` **FAILS against the corpus as it stands today**, because no real assessment carries a `passed` key. **Run it before touching the engine and watch it go red.** *A check that has only ever returned PASS by reading its own default has never been executed once, and its green history is worth nothing.*
- **Both directions:** after the engine writes verdicts, a subject below the I5 floor records `passed: False` with no axis score; hand-set one axis score on that assessment and the check must FAIL.
- `verify_assessment_subjects_exist` **FAILS today**, naming `subj_nonexistent_subject`, and passes after step 4. Run it before the deletion, or you have tested nothing.
- **No test writes to the corpus:** record `social_proof.duckdb`'s mtime and size before a full `pytest tests/ -q`, and assert both are unchanged after. This catches the whole class, not the one row.

**Falsify.** Restore `.get("passed", True)`. The (c) assertion must go green again over a corpus that still holds no verdicts — proving the default, and nothing else, was producing the PASS. Revert; record both.

**Blast radius.** `worker/integrity.py`, `worker/rubric/engine.py`, `tests/`, the corpus (one row deleted), `docs/design_evidence_integrity.md` §3, `docs/design_rubric_engine.md`, §3, §6.

---

## 13g. N0 — Extract over the full corpus · **DELIVERED · (c) NOT SATISFIED**

> **Verified September 5, 2026.** The extraction is real and the numbers hold: 1,501 claims across all four episodes, rejection counters genuinely non-zero, parameter 026 re-measured over n=1,501. **But this item's (c) required a detected tension *or* a report of the candidate pairs considered and why each was rejected, and neither exists** — because proposition dedup never ran, so the candidate set is empty by construction (§13j, P0). The work was done correctly against a prerequisite nobody had identified. Kept below for the reasoning.

**User impact:** the detectors finally meet material capable of contradicting itself, and the entailment guard runs for the first time over output it did not hand-pick.

**Contract:** `design_claim_extraction.md` (the six validators, `extraction_version`) · `design_data_layer.md` §3 and §6 · `ongoing_errors.md` §2 parameter 026 · trap 26.

**Gap — measured after R1 landed.** R1 delivered the **audio** and not the **claims**:

| | before R1 | after R1 |
|---|---|---|
| utterances | 361 | **4219** |
| coverage | 7.7% | **99.7–100%** |
| claims | 9 | **9** |
| extraction_version | `gemma-3-27b-it:v1.1:s1` | **unchanged** |
| published tensions | 0 | **0** |
| principles | 0 | **0** |

The corpus grew **11.7×** and the claim set did not move. `All-In E245` carries **1015 utterances and zero claims.** The 9 claims are still exactly the ones X0 hand-verified over the truncated window, so every conclusion trap 26 warns about still holds: the detectors report zero over a corpus that cannot yet contain a reversal, and **X1 — now wired, correct, and shipped — has never once run over extraction output it did not inherit.** Its rejection counters are all zero.

**This is a spec defect, not an agent error.** §15 said *"re-ingest all four at full length"* and never said *re-extract*. The agent implemented exactly what was written. Recorded in §27.

**Implementation**

1. **Run extraction across all 4219 utterances.** Bump `extraction_version`: the prompt is unchanged but the corpus is not, and `claim_id` hashes the version, so old and new claims coexist and stay auditable instead of colliding (`design_data_layer.md` §3).
2. **X1 stays in the chain.** `validate_extracted_claim` runs entailment at position 2, immediately after quote resolution. Note that passing `embedder=None` does **not** skip it — `validators.py:128` loads a real embedder — so there is no accidental-bypass path to worry about, and no reason to add one.
3. **Record the rejection counters. This is the point of the run.** Report `VALIDATOR_REJECTION_COUNTERS` per reason — `quote_too_short`, `quote_does_not_support_proposition`, `entailment_ambiguous` — as counts and as a rate over claims attempted. §14 step 6 makes this the early-warning signal for prompt and model regression; this run establishes its baseline.
4. **Measure parameter 026 properly, for the first time.** The shipped values were fitted to 9 claims and 2 reconstructed fabrications — far below the 5-case-per-class floor (Issue 018 = B), and correctly labelled provisional at `validators.py:17`. They were measured honestly, and the recorded numbers show how little room they have:

   | threshold | value | nearest real observation | margin |
   |---|---|---|---|
   | `T_ENTAIL_HIGH` | 0.70 | lowest true-claim similarity **0.7091** | **0.009** |
   | `T_ENTAIL_LOW` | 0.60 | highest fabrication similarity **0.5337** | 0.066 |
   | `MIN_QUOTE_TOKENS` | 7 | shortest true claim is **exactly 7 tokens** | **0** |

   **Two of the three have effectively no margin.** One ordinary claim phrased slightly more tersely, or one embedding drift, and a true claim is rejected or quarantined. That is not an argument for loosening them now — it is the reason they must be re-derived over a real distribution rather than a hand-verified nine. Keep them provisional until each class clears the floor, and **state in the commit body what n each threshold was measured over.**
5. **Re-run P4, P5 and P6** over the result.

**Validation**

- **(c)** — **the run reports either at least one detected tension, or the candidate pairs it considered and why each was rejected.** Four episodes spanning 2023-04 to 2026-08 — a 1237-day span is already recorded for Sacks — across ~1000 utterances each. A corpus this size returning zero reversals *and* zero updates *and* zero principle conflicts is either a real finding about these four people or a broken detector, and **the run must be able to say which.** *Zero with no denominator is precisely the shape trap 26 describes, and a stub reproduces it perfectly.*
- **Every source contributes claims.** E245's 1015 utterances yielding zero is a red flag, not a result. Assert no source has zero claims, and if one does, investigate before proceeding.
- **The rejection counters are non-zero.** A guard that rejected nothing across 4219 utterances has not been tested (standing constraint: *a guard that has never failed has not been tested*).
- `verify_quotes` PASS over the new claim set; `verify_canonical_ids` still reports 0 mismatches once new propositions land — the normalization D0 introduced must survive contact with a real extraction run.
- Wall-clock throughput recorded for the full run.

**Falsify.** Set `T_ENTAIL_LOW = 0.0` and re-run over a sample. `quote_does_not_support_proposition` rejections must fall to zero, proving the threshold rather than the surrounding code is doing the work. Then set `MIN_QUOTE_TOKENS = 100` and confirm nearly everything is rejected. Revert both; record all three results.

**Blast radius.** `worker/extract/*`, the corpus (new claims, new propositions), `docs/ongoing_errors.md` §2 (026 re-measured, with n), §3, §6, and the status rows for **P4, P5, P6 — which this run finally makes answerable.**

---

## 13h. G1 — Two `role_id` schemes, and a directory outside every gate · **DELIVERED · VERIFIED**

> **Verified September 5, 2026.** `ruff` and `mypy` both clean over `scripts/` (6 files). Hand-built `role_id` strings gone from both scripts; `source_roles` is 16 rows for 16 pairs; `verify_canonical_ids` now examines 1,445 entities including all 16 roles. Kept below for the reasoning.

**User impact:** none directly. This is the item that stops the next three from being written on sand.

**Contract:** `design_data_layer.md` §3 (deterministic IDs) · §2 of this guide (the state-detection block).

**Gap — two halves of one problem.**

**(a) `scripts/` is outside every gate.** §2's block runs `ruff` and `mypy` over `worker/ tests/ fixtures/ golden/`. It has never covered `scripts/`. Run it now and it is **RED: 17 mypy errors in `scripts/resegment_and_reextract.py`.** `ruff` passes.

This is not a tidiness point. `scripts/` is where the code that **mutates the production corpus** lives — `populate_corpus.py`, `reextract_corpus.py`, `resegment_and_reextract.py`, `migrate_propositions.py`. The 10MB truncation cap that cost this project a full re-ingest sat in `populate_corpus.py:259`, in a directory nothing checks. **The most consequential code in the repo is the least examined.**

**(b) Two `role_id` schemes coexist, and the corpus has 16 duplicate roles.** `source_roles` holds **32 rows for 16 real (source, subject) pairs.** Every pair appears twice, with identical payload and two different ids:

```
cda1c06f47ac585f                             <- compute_role_id(), sha256(source_id|subject_id)[:16]
role_149ff5f2de5ff53a_subj_david_friedberg   <- f"role_{sid}_{subj_id}", hand-built
```

The hand-built form comes from `scripts/reextract_corpus.py:205` and `scripts/resegment_and_reextract.py:260`, both of which bypass `compute_role_id`. The `PRIMARY KEY (role_id)` cannot prevent this: the two ids differ, so the upsert that was supposed to be idempotent inserts a second row instead.

**This breaks the guarantee `design_data_layer.md` §3 is built on** — *"re-running ingest writes the same IDs, so every write is an upsert and nothing duplicates."* That holds only while every writer derives ids the same way. And **nothing catches it**: `verify_canonical_ids` covers propositions and principles only, and `verify_role_coverage` asks whether utterances *resolve to* a role, never whether roles are unique — so it reports `PASS (examined: 4219)` over a table that is 100% duplicated.

The count also tells a story worth reading: `source_roles` was 32, R1's re-ingest brought it to 16, and N0 took it back to 32. **A clean rebuild is being re-polluted by every script run.**

**Implementation**
1. **Extend the gates to `scripts/`.** Change §2's block and any CI invocation to `ruff check worker/ tests/ fixtures/ golden/ scripts/` and the same for `mypy`. Then fix the 17 errors. Do this first — the rest of this item edits files that are currently unchecked.
2. **Delete both hand-built id constructions.** `scripts/reextract_corpus.py:205` and `scripts/resegment_and_reextract.py:260` call `compute_role_id(source_id, subject_id)`. Grep the whole repo for other hand-built ids — `f"role_`, `f"claim_`, `f"prop_`, string concatenation into an id field — and route every one through the `compute_*` helpers in `worker/storage.py`.
3. **De-duplicate `source_roles`**: keep the row whose `role_id == compute_role_id(source_id, subject_id)`, delete the other. 32 → 16.
4. **Extend `verify_canonical_ids` to roles** — and to every entity whose id is content-derived. The check exists; it is simply scoped too narrowly. `design_data_layer.md` §3 lists eight id formulas; the check should cover every one it can reach.

**Validation**
- **(c)** — `verify_canonical_ids` **FAILS against the corpus as it stands today**, naming the 16 hand-built role rows. **Run it before step 3 and watch it go red.** *A check that has only ever been green on data it does not cover has not been tested, and this one currently passes while every role row in the store is duplicated.*
- After step 3: `source_roles` has exactly 16 rows, one per (source, subject) pair, every `role_id` equal to its recomputation.
- **Idempotence, which is the actual guarantee:** run `reextract_corpus.py` (or its dry-run path) twice against a scratch copy and assert `source_roles` row count is unchanged the second time. This is what "every write is an upsert" means, and it has never been asserted.
- `ruff` and `mypy` clean over `scripts/` as well as the four existing directories.

**Falsify.** Restore one hand-built `role_id` and re-run the pass; `verify_canonical_ids` must go red naming that row. Revert; record both.

**Blast radius.** `scripts/*.py`, `worker/integrity.py`, §2's state-detection block, `.github/workflows/portability.yml`, the corpus (16 rows deleted), `docs/design_data_layer.md` §3, §3, §6.

---

## 13i. E2 — The sufficiency verdict is circular, so the check still cannot fail · **DELIVERED · VERIFIED**

> **Verified September 5, 2026.** `engine.py:126` sets `"passed": is_sufficient`, computed from `MIN_CLAIMS`/`MIN_SOURCES` against the counts **before** any axis is scored. The verdict no longer depends on the scores it gates; the circularity is gone. Kept below for the reasoning.

**User impact:** the guard against publishing a score over insufficient evidence becomes capable of failing, which is the only thing that makes it a guard.

**Contract:** `design_rubric_engine.md` (sufficiency, per-axis gating) · invariant **I5** · `ongoing_errors.md` §2 parameter 012.

**Gap.** E1 was asked to make `verify_no_suppressed_scores` able to fire. It removed the `.get("passed", True)` default — correctly — and a missing key now FAILs. **But the verdict it now reads is derived from the thing it is supposed to police.**

`worker/rubric/engine.py:141-142`:

```python
any_scored = any(ax["score"] is not None for ax in axes.values())
sufficiency["passed"] = any_scored
```

`worker/integrity.py:235`:

```python
passed = a.sufficiency["passed"]
if not passed:
    for axis_name, axis_val in a.axes.items():
        if axis_val.get("score") is not None:
            return FAIL
```

`passed` is **defined as** "at least one axis has a score." So `not passed` is true **only when every axis score is None**, and the loop then searches for a non-null score among axes that are all null by construction. **The branch can never return FAIL.** The check reports `PASS (examined: 8)` and will report it forever.

E1 did not fail to change anything — it changed the shape and the defect survived. The key is present, the default is gone, the code reads correctly, and the check is exactly as inert as it was before. **This is the third time this project has shipped a guard that cannot fail** (`min_ratio` declared and unreferenced, trap 29; `.get` on a key nobody writes, trap 36; and now a verdict computed from the evidence it is meant to gate).

**Implementation**
1. **Derive `passed` from the sufficiency criteria, never from the outcome.** The inputs are already in the dict — `claim_count`, `source_count`, `span_days` — and the thresholds are parameter 012 (per-axis sufficiency gates, *"conservative; `insufficient_corpus` is always safe"*). Compute the verdict from those inputs against those thresholds, before any axis is scored.
2. **Then let the verdict gate the scoring**, rather than reading it back off the result: if `passed` is False, no axis is scored and `reason` is `insufficient_corpus`. The dependency must run verdict → scores, one direction only.
3. **Parameter 012 is measured, not chosen** (`ongoing_errors.md` §2). With 1501 claims across four sources and a 1237-day span there is finally a distribution to measure it against. Record the values as provisional and say what n they came from.
4. Keep the missing-key FAIL that E1 added. That part is right.

**Validation**
- **(c)** — construct an assessment whose sufficiency inputs are **below** the parameter-012 floor and hand-set one axis score on it; `verify_no_suppressed_scores` must **FAIL**. *Today no such assessment can exist, because `passed` is false only when every score is already null — so this case is unreachable, and constructing it is precisely the proof that the circularity is gone.*
- **The other direction:** an assessment above the floor with all axis scores null is legitimate (the axes had nothing to say) and must **PASS**. If your fix makes this fail, `passed` has become the outcome again with the sign flipped.
- Over the live corpus: all four subjects have 209–566 claims across 4 sources, so all should record `passed: True` on the merits, not because scores happen to exist.
- A subject with 1 claim from 1 source records `passed: False`, `reason: insufficient_corpus`, and no axis score.

**Falsify.** Restore `sufficiency["passed"] = any_scored`. The (c) assertion must become **unconstructible** — you will not be able to write the failing case at all. That inability *is* the bug, and being unable to express the test is the clearest possible demonstration of it. Revert; record both.

**Blast radius.** `worker/rubric/engine.py`, `worker/integrity.py`, `tests/`, `docs/design_rubric_engine.md`, `docs/ongoing_errors.md` §2 (012 measured), §3, §6.

---

## 13j. P0 — Proposition deduplication never runs, so no contradiction can be detected · **DELIVERED · PRODUCED TWO FABRICATIONS**

> **Verified September 5, 2026.** The mechanism works: dedup is wired into `ClaimExtractionPipeline`, 1,503 propositions merged to 1,429, the histogram has a real tail (one proposition with 8 claims, four with 4, six with 3, 45 with 2), 12 opposing-stance candidate pairs exist where there were none, and the content merges are largely sound — *"China has made a significant push towards open source software"* absorbed exactly the restatements §13j predicted it should.
>
> **But the two tensions it published are both fabrications** (§13k), and the merge silently voided X1's entailment guarantee for every re-pointed claim (§13l). The root cause is upstream of this item: 7% of propositions are indexical templates that no threshold can separate (§13m). **P0 did what it was asked. What it was asked was not sufficient.** Kept below for the reasoning.

**User impact:** the product can finally find the thing it exists to find. Until this lands it cannot, at any corpus size.

**Contract:** `design_claim_extraction.md` (dedup) · `design_topic_model.md` · `ongoing_errors.md` §2 **parameter 008** · `design_rubric_engine.md` (tension types).

**Gap — this is why N0 produced 1501 claims and zero findings.**

| | count |
|---|---|
| claims | **1501** |
| distinct propositions used by claims | **1499** |
| propositions carrying more than one claim | **1** |
| published tensions | **0** |

**Every claim was given its own private proposition.** `worker/tension/detect.py:73` joins `ON a.proposition_id = b.proposition_id` — that is how a contradiction is found: two claims, same proposition, opposing stance. With 1499 propositions for 1501 claims there is nothing to join, and I measured it directly: **0 pairs share a proposition with opposing stance.** A reversal is not undetected; it is *unrepresentable*.

**Cause.** `worker/extract/extract.py` imports only `get_embedder` from `worker/extract/dedup.py`. The merge logic in that module — `t_dedup = 0.88`, embedding-nearest-neighbour, the whole apparatus — **is never called from the extraction path.** New propositions are created by `compute_proposition_id(text)`, which hashes exact normalized text. D0 made that normalization correct, and correct exact-text hashing still cannot merge *"The leading open source models are from China these days"* with *"China has made a significant push towards open source software."*

This is parameter 008's stated bias arriving exactly as written: **"Over-splitting hides every contradiction, silently."** It did, and every gate stayed green while it happened.

**A numbering discrepancy to resolve while you are here.** `worker/extract/dedup.py:9` and `:127` call the threshold **"Parameter 002"**. `ongoing_errors.md` §2 calls the proposition merge threshold **008**. One of them is wrong, and the consequence is that the parameter is not tracked where the doc says it is. Fix the code comment to 008 unless git history shows 002 was the original and §2 is the error — check before changing.

**Implementation**
1. **Wire the merge into the extraction path.** Every extracted claim resolves its proposition through dedup — nearest neighbour over `proposition_embeddings` above `t_dedup`, else create — instead of hashing its text directly. Reuse the embedding that D0's backfill path already computes; do not embed twice.
2. **Measure parameter 008. Do not accept 0.88 because it is written down.** It is provisional and has never been exercised. The corpus now gives you a real distribution: embed all 1499 propositions, examine the nearest-neighbour similarity distribution, and choose the threshold where genuine restatements merge and genuinely different claims do not. **Bias toward merging** (§2). Record the value with its n.
3. **Decide the ambiguous band.** Parameter 008's second half is *"whether ambiguous-band adjudication earns its cost."* You now have the data to answer it. If a band is used, it quarantines rather than guessing, per `design_evidence_integrity.md` §6.
4. **Re-run P4/P5/P6** over the merged propositions.
5. **Do not re-extract.** The claims are fine; their propositions are what need collapsing. This is a re-resolution pass over existing claims, which also makes it cheap to re-run at several thresholds while measuring step 2.

**Validation**
- **(c)** — **at least one proposition carries claims from two different sources on different dates**, and the tension detector runs over a non-empty candidate set. *Report the candidate-pair count explicitly.* Today that count is **0 pairs sharing a proposition with opposing stance**, and a detector with zero candidates cannot be said to have run at all. *No stub and no threshold tweak fabricates a shared proposition across two real episodes eighteen months apart.*
- **Report the merge histogram**: propositions by claim count. Today it is `1498 × 1 claim, 1 × 3 claims`. A healthy result has a visible tail. **If after merging the histogram is still almost entirely singletons, the threshold is wrong and step 2 was not really done.**
- **Both directions on the threshold:** the two "China open source" propositions quoted above must merge; *"High speed trains in China are built and operated by private industry"* must **not** merge with either. Assert both — a threshold that merges everything is as useless as one that merges nothing.
- If tensions are still zero after a genuine merge, **that is now a publishable finding rather than an artefact** — report the candidate pairs considered and why each was rejected. That was N0's (c) and it was never satisfied, because there were no candidates to consider.
- `verify_canonical_ids` still passes; `verify_quotes` still passes over all 1501 claims.

**Falsify.** Set `t_dedup = 0.999`. The merge histogram must collapse back to all-singletons and the candidate-pair count to zero, reproducing today's state exactly — proving the threshold, and not some other change, is what produces the merges. Then set `t_dedup = 0.30` and confirm absurd merges appear (the trains proposition joining the open-source ones). Revert; record all three.

**Blast radius.** `worker/extract/extract.py`, `worker/extract/dedup.py`, the corpus (proposition re-resolution, claim re-pointing), `worker/tension/*`, `docs/ongoing_errors.md` §2 (008 measured, with n), `docs/design_claim_extraction.md`, §3, §6, and **P4/P5/P6, which this is the last prerequisite for.**

---

## 13k. Q0 — Quarantine both published tensions · **DO THIS FIRST**

**User impact:** the system stops asserting two things about two real people that are not true.

**Contract:** `design_evidence_integrity.md` §4 (quarantine) and §5 (*quarantine first, investigate second*) · trap 28.

**Gap.** P0 produced the first two tensions this system has ever published. **I read both by hand. Both are fabrications.** They share one merged proposition — *"The speaker believes they created the subject matter."*

| | tension `461e3d1dbf30bde4` (Friedberg) | tension `4b812a6b0dc604b0` (Sacks) |
|---|---|---|
| quote A | *"I think I created it, you know, put it out there and said, like he's trying to show everyone…"* | *"But, eventually, for this to, I think, really take off."* |
| quote B | *"And when people were saying this, they were, they were told you were creating conspiracy theories."* | *"I mean, he doesn't have those kinds of powers."* |

Sacks's pair contains **no assertion about creating anything, in either quote.** Neither quote is about the proposition, and the two are not about each other. Severity is recorded as `1.0` on both.

**Every one of the thirteen integrity checks passes over these.** `verify_quotes` passes because the words were said. `verify_attribution_floor` and `verify_negation_recheck` now examine 2 published tensions and clear them. This is trap 28 exactly, and the second time this project has published a fabrication — the first was X0's.

**Implementation**
1. Set `status='quarantined'`, `quarantine_reason='fabricated_proposition'` on `461e3d1dbf30bde4` and `4b812a6b0dc604b0`. Same reason string as tension `0068adec4b1501c6`, so all three are greppable as one class.
2. Recompute the affected assessments without them (`design_evidence_integrity.md` §5 step 2).
3. **Do not delete, and do not fix the underlying proposition here.** The rows are the evidence W0 and W1 are measured against. Quarantine first, investigate second — that is the documented order and it exists for exactly this moment.

**Validation**
- **(c)** — zero published tensions remain, and `verify_quarantine_not_rendered` examines **3** quarantined tensions and confirms none appears in any assessment's `axis_evidence`.
- No assessment's `axis_evidence` mentions either tension id.
- The quarantine rate is now reportable: 3 of 3 tensions ever generated were quarantined. **That number is the health metric** (`design_evidence_integrity.md` §4); record it rather than hiding it.

**Falsify.** Re-publish one and confirm the (c) assertion goes red. Revert; record both.

**Blast radius.** The corpus (2 rows), `worker/rubric/engine.py` (recompute), §3, §6.

---

## 13l. W1 — Entailment does not survive re-pointing

**User impact:** a claim can no longer end up attached to a proposition its quote was never checked against — which is how both fabrications in Q0 were built.

**Contract:** `design_claim_extraction.md` §8 validator 6 · `design_evidence_integrity.md` §2 rule E2b · traps 28 and 36.

**Gap — this is the mechanism, not the symptom.** X1 validates that a quote entails its proposition **at extraction time**. P0's merge then **re-points `claim.proposition_id` to a different proposition and never re-checks.** Traced on real rows:

| claim | proposition at validation | proposition now |
|---|---|---|
| `4415459696a8fbc0` | The speaker believes that the subject will eventually take off. | The speaker believes they **created the subject matter**. |
| `4a3ef2cdc190f1b1` | The speaker believes the subject does not possess the described powers. | The speaker believes they **created the subject matter**. |
| `605435bdc82ba70f` | People were told that the speaker was creating conspiracy theories. | The speaker believes they **created the subject matter**. |

Each passed validator 6 honestly, against text it no longer carries. **74 propositions were merged away, and every claim that pointed at one is now in this state.** X1's guarantee is void for all of them and nothing reports it, because **X1 is an extraction-time validator and there is no integrity-pass equivalent** — so no check in the thirteen asks whether a *stored* claim still entails its *current* proposition.

**A second defect in the same path.** `worker/extract/dedup.py` documents `T_dedup = 0.86` and `ongoing_errors.md` §2 records 0.86 as the measured value — but `worker/extract/extract.py:26` defaults `t_dedup: float = 0.85` and passes it into the canonicalizer, overriding it. **The measured value is not the running value.** Parameter 008 was measured at one threshold and the pipeline merges at another.

**Implementation**
1. **Re-validate on re-point.** Any code path that changes a claim's `proposition_id` must re-run `validate_entailment` against the **new** proposition text. On reject, the claim is not re-pointed — it keeps its own proposition and the merge is refused for that claim. On the ambiguous band, quarantine.
2. **Add `verify_entailment_holds` to the integrity pass.** For every stored claim, recompute the quote↔proposition similarity against its *current* proposition and assert it clears `T_ENTAIL_HIGH`. This is the check whose absence let a merge silently void X1. It is not cheap — 1501 embeddings — so cache by `(claim_id, proposition_id)` and only recompute when the pair changes.
3. **One source of truth for `t_dedup`.** Delete the default in `extract.py:26`; import the constant from `dedup.py` so there is exactly one place it can be set. Then confirm which value actually produced the current corpus and say so in the commit body — the measurement in `ongoing_errors.md` §2 claims 0.86 and may need re-running at the value that really ran.
4. Grep for the same pattern elsewhere: a constant documented in one module and re-defaulted in a caller's signature.

**Validation**
- **(c)** — `verify_entailment_holds` **FAILS against the corpus as it stands today**, naming the claims re-pointed by P0's merge, including `4415459696a8fbc0` and `4a3ef2cdc190f1b1`. **Run it before any repair and watch it go red.** *These claims passed validator 6 when written and cannot pass it now; no stub and no shape-test reproduces that, because it requires the real embedder over the real stored pair.*
- **Both directions:** a claim whose quote genuinely entails its current proposition passes; hand-repoint one to an unrelated proposition and it fails.
- After step 1: re-running the merge on a scratch copy re-points strictly fewer claims than before, and every re-pointed claim clears `T_ENTAIL_HIGH` against its new text.
- `t_dedup` has exactly one definition in the codebase. Assert it by grep in a test if that is what it takes.

**Falsify.** Disable the re-validation in step 1 and re-run the merge on a scratch copy; `verify_entailment_holds` must go red again with a comparable count. Revert; record both.

**Blast radius.** `worker/extract/dedup.py`, `worker/extract/extract.py`, `worker/integrity.py`, `tests/`, `docs/design_claim_extraction.md` §8, `docs/design_evidence_integrity.md` §3, `docs/ongoing_errors.md` §2 (008 re-stated at the value that runs), §3, §6.

---

## 13m. W0 — Propositions must be self-contained, not indexical

**User impact:** propositions become things that can be true or false about the world, rather than templates that collapse into each other.

**Contract:** `design_data_layer.md` §2 (*propositions are global, not nested under a subject*) · `design_claim_extraction.md` (extraction prompt, validators) · `ongoing_errors.md` §2 parameter 008.

**Gap — the root cause of Q0. And note this is an existing rule being violated, not a missing one.** `design_claim_extraction.md` §2 already defines the canonical form as *"a neutral, tenseless statement of the matter at issue, **with the actor and the polarity stripped out**"* — and instructs that it be enforced *"in the extraction prompt **and** in a validator."* **Only the polarity half was ever given a validator.** The actor half was left to the prompt alone, and the v1.2 prompt drifted from it. A rule the model can violate silently is not a rule — §2 says so in those words, about the other half of the same sentence.

The v1.2 extraction prompt emits propositions with **unbound indexicals**:

- **100 of 1429 propositions (7.0%)** begin *"The speaker…"*
- **26** contain *"the subject"*; one contains *"the described powers"*

*"The speaker believes they created the subject matter"* names no speaker and no subject matter. It cannot be true or false on its own, and it **directly violates `design_data_layer.md` §2**: propositions are global precisely so that *"two people can only be compared on a topic if they are being measured against the same propositions."* A proposition whose referent is whoever happens to be pointing at it is not global; it is a template that every subject collides inside.

**And it is an embedding attractor.** Similarity between *"The speaker believes X"* and *"The speaker believes Y"* is dominated by the shared frame, not by X and Y — so dedup merges them at any plausible threshold. One such proposition absorbed **eight** unrelated claims:

```
The speaker believes they created the subject matter.   <- 8 claims
   <- The speaker believes that something was not taught to the subject.
   <- The speaker finds the subject interesting.
   <- People were told that the speaker was creating conspiracy theories.
   <- The speaker believes that the subject will eventually take off.
   <- The speaker believes the subject does not possess the described powers.
   ...
```

**7 of the 12 opposing-stance candidate pairs sit on indexical propositions, and both Q0 fabrications came from this one.** No value of `t_dedup` fixes this, because the similarity being thresholded is not measuring the claim.

**A separate, milder defect worth fixing in the same pass: merging on topic rather than proposition.** Even among content-bearing propositions the merge is loose — *"DNA sequencing involves chopping up DNA"* absorbed *"…allows analyzing the sequence of genes and proteins in cancer samples"*, *"…involves multiplying DNA by millions of times"* and *"…is relatively inexpensive"*. Those are four different facts about one topic. *"Moderna's mRNA technology was patented and commercially developed"* absorbed *"…should be directly injected into the body"* — a description merged with a recommendation. **Topic is not proposition**, and `design_topic_model.md` already owns the former.

**Implementation**
1. **Fix the prompt.** A proposition must be a standalone declarative sentence, resolvable without knowing who said it: no *"the speaker"*, no bare *"the subject"*, no unbound *"they"/"it"/"this"*. Name the referent or do not emit the claim. Add few-shot examples of the failure and its repair.
2. **Add a validator that rejects indexical propositions** — before entailment, since it is cheap and deterministic. A regex over a small banned-opener list (`the speaker`, `the subject`, `the described`) plus a check for a sentence-initial unbound pronoun catches the observed 100%. Rejection reason `proposition_not_self_contained`. **Add a fixture case for it**, since a validator with no failing fixture is untested.
3. **Repair the existing 126.** Re-extract the affected claims under the fixed prompt. Do **not** hand-edit proposition text: the id is derived from it, and rewriting text without re-deriving ids and re-validating entailment is how W1's defect was created.
4. **Re-measure parameter 008 afterwards.** The current value was fitted to a population 7% of which were attractors; the distribution it was measured against was not the distribution it will run against. Re-derive, record with n, keep provisional.
5. **Decide whether stance-opposition alone should ever publish a tension.** Both Q0 fabrications had `severity 1.0` from `stance='support'` vs `stance='oppose'` on a shared proposition. If the proposition is weak, opposing stances are noise. Consider requiring both claims to independently clear entailment against the shared proposition **and** the proposition to be non-indexical before a tension may publish. If that is a design change rather than a fix, it is Louis's call — file it per §9 rather than deciding it here.

**Validation**
- **(c)** — after repair, **zero propositions match the indexical patterns**, and re-running tension detection over the repaired corpus produces **either a tension whose two quotes a reader agrees are about the same proposition, or an explicit report of the candidate pairs considered and why each was rejected.** *Print the pairs. A count alone is what let P0 look successful.*
- The new validator **FAILS on the 126 existing propositions** when run against today's corpus. Run it before the repair — a validator that has only ever seen clean data has not been tested.
- The merge histogram after repair has a tail that survives inspection: **read the five largest merged clusters by hand and confirm each groups restatements of one proposition, not one topic.** This is a judgement call and it must be made by a person looking at text, not by a threshold.
- `verify_entailment_holds` (W1) passes over the repaired corpus.
- Both directions on the validator: *"China has made a significant push towards open source software"* passes; *"The speaker believes they created the subject matter"* is rejected.

**Falsify.** Disable the validator and re-extract a sample; indexical propositions must reappear at roughly 7%. Revert; record both.

**Blast radius.** `worker/extract/runtime.py` (prompt), `worker/extract/validators.py`, `worker/extract/schema.py`, `fixtures/behaviour/`, the corpus (re-extraction of affected claims), `docs/design_claim_extraction.md`, `docs/design_data_layer.md` §2, `docs/ongoing_errors.md` §2 (008 re-measured), §3, §6.

---

## 13n. S1 — Nothing validates `stance` or `is_own_assertion`

**User impact:** the two fields the contradiction detector actually keys on stop being the only unchecked things in the claim.

**Contract:** `design_claim_extraction.md` §2 (stance carries polarity) and §3 (own-assertion guards, invariant **I7**) · `design_rubric_engine.md` (tension types).

**Gap — read off the five surviving candidate pairs, every one of which is false.**

Six validators run on every extraction. They check that the quote is verbatim, that it entails the proposition, that the proposition carries no polarity, that speech acts are consistent, that confidence clears a floor, and that the schema is valid. **None of them checks the two fields a tension is made of.**

**(a) `stance` is unvalidated, and validator 6 cannot cover it.** Entailment asks *"does this quote support this proposition?"* — it is **stance-blind by construction**, so a quote that is genuinely about the proposition passes whether it is labelled `support` or `oppose`. Two of the five pairs are one person saying the same thing twice, labelled both ways:

> **Friedberg, E287, same episode.** `support`: *"We have fundamental fiscal spending problem with the federal government right now."* · `oppose`: *"And the big problem at this point is the federal government is spending so much."*

> **Sacks, E124, same episode.** `oppose`: *"you can just tell the AI to do something for you pretty complicated and it will be able to do it."* · `support`: *"We're now the AI can take complicated tasks."*

Both pairs would render as a person contradicting themselves. Both are the person agreeing with themselves, twice.

**(b) The own-assertion guard is under-firing.** **1353 of 1362 claims are `is_own_assertion = True`; only 9 (0.7%) are excluded**, all for `entailment_ambiguous` rather than for speech act. In four hours of unscripted conversation among four people who constantly voice positions in order to reject them, 0.7% is not a plausible exclusion rate. Two more pairs come from this:

> **Calacanis, E245.** `support`: *"You can say, okay, Verizon's responsible of people use it in a terrorist attack."* · `oppose`: *"Verizon's not responsible of people use it to coordinate a bank robbery."* — one continuous analogy, seconds apart. He is stating a position **in order to reject it**, which invariant I7 exists to exclude.

> **Chamath, E287.** `mixed`: *"So you're saying the substance of what he says will no longer matter to you…"* — **a question**, recorded as a claim.

**Implementation**
1. **Validator 7 — stance direction.** After entailment establishes *aboutness*, check *direction*. Entailment already computes an embedding for the quote and the proposition; the cheap version compares the quote against the proposition and against its negated form and requires the labelled stance to be the nearer. **Whatever mechanism you choose, it must be able to reject** — a stance validator that never fires is the fourth guard this project has shipped unable to fail.
2. **Raise I7's sensitivity, and measure it.** Interrogatives, conditionals introduced by *"you can say"* / *"they'd argue"* / *"the argument is"*, and second-person framings (*"you're saying…"*) are reported speech or rhetorical setup, not own assertions. `design_claim_extraction.md` §3 already specifies this guard; it is firing at 0.7% and the observed misses are all in this shape.
3. **Report the exclusion rate as a first-class number**, next to the validator rejection counters. It is the same early-warning signal §14 step 6 established for entailment: a rate that collapses means a guard stopped working, not that the corpus got cleaner.
4. **Fixtures for both**, in `fixtures/behaviour/`: the Verizon analogy, the Chamath question, and the two same-stance-labelled-differently pairs. A validator with no failing fixture is untested (trap 22).

**Validation**
- **(c)** — **all four of the pairs quoted above stop being candidate pairs**, each for the right reason: the two stance errors corrected, the analogy and the question excluded as non-own-assertions. Assert them individually by claim id, not as an aggregate count. *An aggregate can be satisfied by rejecting everything; naming the four proves the guards discriminate.*
- **Both directions:** a genuine `oppose` claim is still labelled `oppose` and still counted. Assert at least one real opposing claim survives — a stance validator that collapses everything to `support` would satisfy (c) and destroy the product.
- The I7 exclusion rate is reported and is **materially above 0.7%**. Do not target a number; report what the corpus gives once interrogatives and reported speech are excluded, and say what n it came from.
- `verify_entailment_holds` still passes over every surviving claim.

**Falsify.** Disable validator 7 and re-run; the two stance pairs must reappear as candidates. Disable the I7 change and re-run; the Verizon and Chamath pairs must reappear. Revert; record all three.

**Blast radius.** `worker/extract/validators.py`, `worker/extract/runtime.py` (prompt), `fixtures/behaviour/`, the corpus (re-validation of stance on existing claims), `docs/design_claim_extraction.md` §2–§3, `docs/ongoing_errors.md` §2 (a new parameter if the stance check has a threshold), §3, §6.

---

## 13o. T1 — A reversal needs time between its halves

**User impact:** the system stops calling a single continuous argument a change of mind.

**Contract:** `design_rubric_engine.md` (tension types) · `design_claim_extraction.md` §4 (temporal self-reference).

**Gap.** `unacknowledged_reversal` is by definition a claim about **change over time**. `worker/tension/detect.py` requires a shared proposition, the same subject and opposing stances — and **nothing about when the two claims were made.**

**All five surviving candidate pairs are same-episode.** There are **zero** cross-episode candidates in the entire corpus:

```
same_source = True :  5 pairs
same_source = False:  0 pairs
```

Two claims seconds apart in one conversation are not a reversal; they are almost always rhetorical structure — a position voiced then rejected, a question then its answer, a hedge then its firming-up. This one structural condition would have blocked **all five** of today's false candidates.

**Be precise about what this does and does not fix.** It would **not** have caught the two tensions Q0 quarantined — those were genuinely cross-episode (E124 2023 vs E287 2026, E165 2024 vs E287 2026) and false for a different reason. **T1 is a cheap filter, not a correctness fix.** S1 and W2 are the correctness fixes; do not let a green T1 suggest the detector is sound.

**Implementation**
1. Require a minimum gap between the two claims for `unacknowledged_reversal`. **Same source is an automatic disqualification** regardless of timestamps — a single recording is one speech act context.
2. **The gap is a parameter to be measured, not chosen** — add it to `ongoing_errors.md` §2 with the bias stated: *toward requiring more time*, since a false reversal is a published accusation and a missed one is silence. Today's corpus supports only the same-source rule, since there are no cross-episode candidates at all; record the numeric gap as unmeasured until candidates exist.
3. A same-episode pair with opposing stances is still **evidence worth keeping** — it usually means a stance error (S1) or a rhetorical setup (I7). Route it to a review surface with reason `same_source_stance_conflict` rather than discarding it. That queue is the fastest signal S1's guards are working.

**Validation**
- **(c)** — all five current candidate pairs are rejected by the same-source rule, and the detector reports **zero** `unacknowledged_reversal` candidates over today's corpus **with the count of pairs it examined and rejected, by reason.** *Zero with a denominator is a result; zero without one is what P0 shipped.*
- A synthetic cross-episode pair with opposing stances on one proposition **is** accepted as a candidate — proving the rule filters on time and source rather than rejecting everything.
- The `same_source_stance_conflict` queue is non-empty and contains the five pairs.

**Falsify.** Remove the same-source condition; the five pairs must return as candidates. Revert; record both.

**Blast radius.** `worker/tension/detect.py`, `worker/storage.py` (review queue), `tests/`, `docs/design_rubric_engine.md`, `docs/ongoing_errors.md` §2, §3, §6.

---

## 13p. W2 — Self-containment, the rest of the pronouns

**User impact:** finishes W0. A proposition stops depending on a pronoun whose referent is in an utterance the reader cannot see.

**Contract:** `design_claim_extraction.md` §2 (the actor must be stripped) · `design_data_layer.md` §2 (propositions are global).

**Gap.** W0 delivered exactly what it specified and the specification was too narrow. The named patterns are **gone — 0 of 1303 propositions** begin *"The speaker"* or contain *"the subject"* or *"the described"*. But the validator was written against that list rather than against the principle, and unbound referents remain:

| pattern | propositions | share |
|---|---|---|
| bare `they` / `their` | **82** | 6.3% |
| starts `It` / `This` / `That` | **23** | 1.8% |
| bare `he` / `his` / `him` | **13** | 1.0% |
| contains `the same` | **12** | 0.9% |

Roughly **130 propositions (10%)** still cannot be resolved standing alone. Two of the five false candidate pairs sit on them — *"We should do the same thing on AI"* (same as **what**?) and *"The substance of what **he's** saying is more accurate than **his** overall stance"* (**who**?).

**The lesson is about how the item was written, not about the agent.** §13m listed the three observed patterns and the implementation copied the list. **A validator built from a list of observed failures catches the failures you observed.** Write it against the property — *resolvable without external context* — and let the list be examples.

**Implementation**
1. Extend the self-containment validator: reject a proposition containing any pronoun or deictic without an antecedent **inside the proposition itself** — third-person pronouns, sentence-initial `It`/`This`/`That`, and comparatives with no relatum (`the same`, `such`, `the other`). Keep `proposition_not_self_contained` as the reason so the class stays greppable.
2. **State the principle in the docstring**, above the pattern list, so the next extension is a matter of adding a case rather than rediscovering the rule.
3. Re-extract the ~130 affected claims. **Do not hand-edit proposition text** — the id derives from it (`design_data_layer.md` §3) and W1's entailment cache keys on the pair.
4. Re-run `verify_canonical_ids` and `verify_entailment_holds` afterwards.

**Validation**
- **(c)** — **zero propositions in the store contain an unbound pronoun or deictic**, checked by the same predicate the validator uses, run as a query over the live corpus. And the two named pairs above are gone. *Assert the property over the whole table, not a spot check of the four patterns in the table above — that is the mistake this item exists to correct.*
- The validator **FAILS on today's corpus** naming ~130 propositions. Run it before the re-extraction.
- **Both directions:** *"China has made a significant push towards open source software"* passes; *"We should do the same thing on AI"* is rejected.
- No regression: propositions with a *bound* pronoun (*"Moderna patented its mRNA technology"* — `its` resolves inside) still pass. A validator that rejects every pronoun is over-strict and will hollow out the corpus.

**Falsify.** Disable the extension and re-extract a sample; unbound-pronoun propositions must reappear at roughly 10%. Revert; record both.

**Blast radius.** `worker/extract/validators.py`, `worker/extract/runtime.py` (prompt), `fixtures/behaviour/`, the corpus (re-extraction), `docs/design_claim_extraction.md` §2, §3, §6.

---
## 13q. U1 — The review site, served live from DuckDB · *Issue 028, amended by Issue 033*

**User impact:** you can read what the system found, by episode and by person, without a build step and without 2,593 files on disk.

**This item was rewritten on September 5, 2026.** An earlier attempt built the static export Issue 028 originally specified. It produced **2,593 HTML files and 27 MB for 1,288 claims** — one page per claim, plus per-person and per-episode duplicates of the same rows. That output has been deleted. **Issue 033 replaces the static export with a local server that queries DuckDB per request.**

**Start here — the tree is dirty and two gates are red.** `scripts/export_site.py` and `tests/test_review_site_u1.py` are uncommitted, and between them hold the one `ruff` F541 and the two `mypy` errors currently failing §2's block. **Both files are obsolete under Issue 033. Deleting them is the red-gate repair (§9)** — do it in the first commit of this item, before writing anything new. Also revert the uncommitted change to `scripts/build_tokens.py` unless you can state why the new architecture needs it.

**Contract:** `design_ui_direction.md` §2 (timeline), §3 (citation-first, **I3**), §4 (rendering null), §5 (tension card), §6b (the review site) · `design_local_api_and_clients.md` §2 (the four security controls) · Issue 014 (no in-app playback) · Issues 028 and 033.

### Issue 033 — what changed and what did not

| | Issue 028 (superseded) | Issue 033 (current) |
|---|---|---|
| **Rendering** | Pre-rendered static HTML, one file per claim | **Server-rendered per request**, no generated files |
| **Data access** | JSON export snapshot | **Queries DuckDB live**, computed on demand |
| **Build step** | `export_site.py` before every view | **None** |
| **Write safety** | Guaranteed by having no server | **Guaranteed by opening DuckDB `read_only=True`** |

**Unchanged from Issue 028, and still binding:** the panel shows **everything** (timeline, four axes, tensions, principles); it is **local only**; and it is **not shipped until a finding survives being read by hand.** See the gate note below, which has become the interesting part.

### The gate has moved, and you need to know why before you plan

Issue 028 gated this site on *"one tension surviving being read by hand."* **S1, T1 and W2 are all delivered and correct, and the corpus now yields zero tension candidates at all** — not zero *published* tensions, zero *candidates*:

```
opposing-stance pairs, own assertions only :  0
  ... of those, cross-source (T1 rule)     :  0
propositions with claims from 2+ sources   :  4      (out of 1,229)
```

**Only four propositions in the entire corpus appear in more than one episode.** Four episodes spanning 2023–2026 barely revisit the same ground, so a cross-episode reversal is not merely undetected — there is no pair to detect. **The bottleneck has moved from correctness to corpus coverage**, which is Issue 030, open and awaiting a selection.

**Do not read this as a reason to stall U1.** It is the reason `design_ui_direction.md` §4 exists. Claims, quotes, speakers, timestamps and deep links are all real, verbatim-verified and worth reading today. **Build the site; render the finding sections as honest, reasoned absence.** The ship gate stands — *nothing shown may be false* — and an empty tension section with a stated reason satisfies it completely.

### Implementation

**1. Extend the existing local API; do not start a second service.** `worker/api/server.py` already binds loopback-only, already holds the four controls in `design_local_api_and_clients.md` §2, and already has the query layer `/resolve` uses. Add HTML routes to it, server-rendered (Jinja2 or equivalent). One codebase, one security surface, no build step.

**2. Open DuckDB `read_only=True`, and let that be the guarantee.** The static plan was safe because it had no write path; this plan is safe because the connection cannot write. **Assert it** — a test that opens the site's connection and attempts an `INSERT` must raise.

**3. One shared query layer, and the exclusions live in it.** Quarantined tensions (`status='published'` only) and quarantined propositions (`status='active'` only) are filtered **in the queries**, never in a template. Every route calls the same functions. *A renderer that filters is one conditional away from publishing a fabrication, and this project has published three.*

**4. Verify the quote in the query layer, not at render.** Before any claim is returned to a template, its `quote_text` must be confirmed present in its utterance's `text_verbatim`. The store passed this when written; the page is where a reader would be misled, so check it there. Fail the request loudly rather than rendering an unverified quote.

**5. Four routes, computed per request:**

```
GET /                     episodes newest-first: title, date, duration, claim count
GET /episode/{source_id}  claims grouped by person, timestamp order
GET /claim/{claim_id}     the Social Proof panel
GET /person/{subject_id}  that person across all episodes
```

**6. The Social Proof panel** — `design_ui_direction.md` §2–§5 for one claim: the quote verbatim with speaker, episode, timestamp, stance and hedging; a **`cite`** deep link opening the source at the quote's offset, **disabled with a stated reason** where no `citation_url_template` exists (§3 — never link to 00:00); **the timeline** of every other claim by that person on the same proposition, each with its own quote and `cite`; **the four axes** with evidence decomposition or an explicit insufficiency reason; **tensions** (published only) as §5 cards; **principles**, same treatment. **Every section renders always.** Absence is rendered with its reason, never omitted.

**7. Reuse the extension's design tokens** (§157). No second component set, no second visual language.

### Validation

- **(c)** — **no route can render a quarantined tension, a quarantined proposition, or a claim whose quote is not verbatim in its utterance.** Prove it against the live corpus: request `/claim/{id}` for every claim in the store, assert every response is 200, and assert no response body contains any of the three quarantined tension ids or the quarantined proposition id. *This is the assertion that makes the site safe to look at, and it is exactly the failure — a fabrication rendered as a finding — that this project has shipped three times. Aggregate counts do not satisfy it; the sweep does.*
- **The read-only guarantee is tested:** the site's connection raises on `INSERT`. Not asserted by inspection of the connection string — by attempting the write.
- **Rendering null is tested, not assumed:** on today's corpus, which has zero tensions and zero principles, `/claim/{id}` still renders a tensions section and a principles section, each with a stated reason. **Assert the reason strings appear in the HTML.** A blank or omitted section fails.
- **No generated pages:** assert the repository and working tree contain no `site/` directory and no build artefact after the server has been exercised. `.gitignore` should not need to mention one.
- Every `cite` is a real URL with a timestamp or is disabled with a reason. **Zero links to offset 0.**
- Claim counts shown per episode equal `SELECT count(*)` per source.
- Page render time for the heaviest route (an episode with ~330 claims) is recorded. If it is slow, say so with the number rather than adding a cache; a cache is a second copy of the truth and this project has been bitten by one already (trap 36).

**Falsify.** Point the query layer at `status` unfiltered so a quarantined tension becomes reachable, and confirm the (c) sweep goes red naming it. Then remove a source's `citation_url_template` and confirm the affordance renders disabled rather than linking to 00:00. Revert; record both.

**Blast radius.** `worker/api/server.py`, templates under `worker/api/`, `tests/`, deletion of `scripts/export_site.py` and `tests/test_review_site_u1.py`, `docs/design_ui_direction.md` §6b, `docs/design_local_api_and_clients.md` §3 (new routes), `docs/ongoing_errors.md` §4 (Issue 033), §3, §6.

---
## 13r. A0 — The site's read-only guarantee has a silent escape hatch · DELIVERED · VERIFIED

**User impact:** the review site becomes incapable of writing to the corpus in the configuration you actually run it in, not just the one the test uses.

**Contract:** `design_local_api_and_clients.md` §3 (review-site routes open `read_only=True`) · invariant **I8** (all writes go through the worker) · Issue 033.

**Gap — verified by attempting the write, in both configurations.** `worker/api/server.py:80-87`:

```python
if storage.read_only:
    read_only_con = duckdb.connect(str(storage.db_path), read_only=True)
else:
    try:
        read_only_con = duckdb.connect(str(storage.db_path), read_only=True)
    except Exception:
        read_only_con = storage.con.cursor()      # <-- writable
```

DuckDB refuses a second connection with a different configuration while one is open, so **the `except` fires exactly when the worker already holds the file** — the normal local configuration where worker and API share a process. I ran both cases:

| configuration | site connection | `CREATE TABLE` + `INSERT` |
|---|---|---|
| `Storage(read_only=True)` — what `tests/test_review_site_u1.py` boots | true read-only | **raises `InvalidInputException`** ✓ |
| `Storage(...)` writable, holding the lock | `storage.con.cursor()` | **SUCCEEDS — 1 row written** ✗ |

**The guarantee holds in the tested configuration and silently does not hold in the one where it matters.** The U1 test asserts the connection raises on `INSERT` and passes, because its fixture takes the first branch and never reaches the fallback.

This is the project's signature failure in a new place: a guard exercised only where it cannot fail. It is also a **silent downgrade**, which Issue 020 already ruled against in another layer — *fail loudly if absent, never downgrade silently*.

**Implementation**
1. **Delete the fallback.** If a read-only connection cannot be opened, **raise** with a message naming the cause. A review site that cannot guarantee it is a reader should refuse to start, not quietly become a writer.
2. If sharing one process with a writing worker is a configuration you want to support, support it deliberately — open the site's connection against a **snapshot copy**, or run the site in its own process. Both are honest; the cursor fallback is not. **This may be a real design question rather than a fix; if so file it for Louis per §9, rather than deciding it inside this item.**
3. Keep the first branch as-is. It is correct.

**Validation**
- **(c)** — **construct the failing configuration and assert it now raises**: a writable `Storage` holding the lock, then `create_app`, and either `create_app` raises or the resulting connection rejects an `INSERT`. *This is the exact case the current test cannot reach, and reaching it is the whole item. Run it against today's code first and watch the write succeed — that is the bug, reproduced.*
- The existing `read_only=True` fixture still passes unchanged.
- Grep the codebase for other `except Exception:` blocks that substitute a more-capable object for a less-capable one, and list what you find in the commit body. This pattern is worth knowing the extent of.

**Falsify.** Restore the fallback; the (c) assertion must go red with the write succeeding. Revert; record both.

**Blast radius.** `worker/api/server.py`, `tests/test_review_site_u1.py`, `docs/design_local_api_and_clients.md` §3, §3, §6.

---

## 13s. C1 — Expand the corpus chronologically · *Issue 030 = A*

**User impact:** the corpus gets enough overlap for a reversal to be possible at all. Today it is not.

**Contract:** `design_source_acquisition.md` §2, §4 (source selection, roles) · Issue 030 = A · Issue 021 = B (the four hosts) · trap 24 (composition skew).

**Gap.** With S1, T1 and W2 all correct, the four-episode corpus yields **zero** opposing-stance candidate pairs among own assertions, because **only 4 propositions out of 1,229 appear in more than one episode.** A reversal needs one proposition, two episodes and opposing stances. That pair does not exist — not because the detector is broken, but because four episodes spanning three years barely revisit the same ground.

**Issue 030 = A: scale chronologically, no selection.** Take a **contiguous run** of episodes and ingest all of them. The rule is the point: no episode is chosen for what it contains, so nothing in the resulting corpus can be attributed to your picking. For a product whose subject is even-handedness, *"we took everything in this range"* is worth more than the efficiency of choosing by theme.

**Implementation**
1. **Write the selection rule down before you run anything**, in the commit body and in `design_source_acquisition.md`: the exact episode range, the date it was fixed, and the statement that every episode in the range is ingested without exception. **A rule recorded after the fact is not a rule.**
2. **Recommended range: the 20 most recent episodes**, contiguous. This maximises the chance that the same proposition recurs, which is the measured bottleneck.
3. **Cost, from R1's and N0's recorded figures — this is measured, not estimated:** ingest ran at **~12.8× realtime (~430s per 90-minute episode)** and extraction at **~480s per episode** (1,921s across 4). That is **~15 minutes per episode end-to-end**, so **20 episodes ≈ 5 hours**. Confirm against your machine before committing to the full run; ingest 2 first and re-measure.
4. **Enrol roles for every new source.** `SourceSubjectRole` is per (source, subject) — Issue 022 = A — and the four hosts need a row per episode. `verify_role_coverage` will catch a miss, and `verify_canonical_ids` now covers roles, so use `compute_role_id` and never a hand-built string (trap 40).
5. **Re-run the full chain** — extraction, dedup, tension detection, P5, P6 — and report the merge histogram and candidate-pair count as N0 and P0 should have.

**Validation**
- **(c)** — **propositions appearing in 2 or more episodes rises materially above 4**, and the detector reports a **non-empty candidate set with its denominator**: pairs examined, pairs rejected, and the reason for each rejection. *Zero candidates with a denominator is a result; the four-episode corpus could not even produce the denominator.*
- **Read by hand every candidate pair the detector would publish, before recording this item delivered.** This is not optional and it is not satisfiable by a count. Three of this project's fabrications passed every aggregate check that existed at the time; all three were obvious on sight.
- Every new source: `duration_ms` non-null, coverage ≥ 0.80, `published_at` from the feed and not ingest time, 4 role rows, and zero claims is a failure not a result.
- `verify_quotes`, `verify_canonical_ids`, `verify_entailment_holds` all PASS over the enlarged corpus.
- **Composition is reported, not assumed** (trap 24): the corpus is still one show and one medium. Say so in the commit body. Growing it does not fix the skew, and I5 gates volume rather than composition.

**Falsify.** Take the pre-expansion corpus and confirm the candidate count is 0 with the same reporting code — proving the new candidates come from the new episodes and not from a change in how candidates are counted. Record both.

**Blast radius.** `scripts/populate_corpus.py`, the corpus (20 new sources, ~80 role rows, ~6,000 new claims), `docs/design_source_acquisition.md` §2, `docs/ongoing_errors.md` §2 (008, 026, 032 re-measurable at n≫), §3, §6, and **P4/P5/P6 — which this is finally the corpus for.**

---
## 13t. D3 — Validator 7 has only ever corrected in one direction · **DELIVERED · ONE DIRECTION WRONG**

> **Verified September 6, 2026 by running the validator over the live corpus**, which its own tests do not do. It is genuinely bidirectional — 25 `support`→`oppose` and 12 `oppose`→`support` over a random 300-claim sample — and the root-cause diagnosis was correct. `hedge` is properly retired. **But all four `support`→`oppose` flips I read are false, and it has never been run over the corpus.** See §13w (D4). Kept below for the reasoning.

**User impact:** `oppose` stops quietly becoming `support`, which is the difference between a corpus that can contain a reversal and one that cannot.

**Contract:** `design_claim_extraction.md` §2 · `ongoing_errors.md` §2 parameter 031 · trap 45.

**Gap.** Validator 7 decides stance direction by comparing the quote against the proposition and against its negation: if `sim(Q, P) > sim(Q, ¬P)`, the quote asserts `P` and a label of `oppose` is corrected to `support`. **Every recorded correction has gone that way.**

| where | corrections | direction |
|---|---|---|
| S1, parameter 031 | 2 | oppose → support |
| C1 commit body | 7 | oppose → support |
| **total** | **9** | **oppose → support, 0 the other way** |

Meanwhile the stance distribution has drifted with it:

| | before S1 | now |
|---|---|---|
| `support` | 82.7% | **82.3%** |
| `oppose` | **15.2%** | **11.9%** |

**The mechanism is known and it is not neutral.** Sentence embeddings represent negation weakly — *"X is dangerous"* and *"X is not dangerous"* sit close together, and both sit closer to *"X is dangerous"* than to a synthesised `¬P`. So `sim(Q, P) > sim(Q, ¬P)` will hold for almost any quote that is merely **about** `P`, and the test will read `support`. **A validator that has never once fired in the other direction has not been shown to discriminate; it may simply be a support-detector.**

This does not mean the nine corrections were wrong — I have not read them. It means the test's asymmetry is unmeasured, and it feeds the field the entire tension detector keys on.

**Implementation**
1. **Measure the validator against known-oppose claims.** Take a hand-labelled set — at least 5 per class (Issue 018 = B) — of quotes that genuinely oppose their proposition, and check what validator 7 says. **If it corrects them to `support`, the mechanism is wrong, not the labels.**
2. **Report corrections by direction**, as a standing counter alongside the rejection counters: `stance_corrected_to_support`, `stance_corrected_to_oppose`. A ratio that stays at *n*:0 is the signal to stop trusting it.
3. **If embeddings cannot resolve negation at this margin** — parameter 031's `delta = 0.05` is small — say so and change the instrument rather than the threshold. A dependency-parse negation check, or the extractor stating stance with its reasoning and a separate check on that, are both honest alternatives. **Do not widen `delta` until the direction ratio improves; that is fitting the threshold to the answer.**
4. Resolve `hedge` as a stance value while you are here. `entities.py:73` allows `Literal["support","oppose","mixed","hedge"]`, but `design_claim_extraction.md` §2 treats hedging as a **level** (`hedging_level`, a float) on a `support`/`oppose` stance, and its worked example is *"`support`, hedging 0.8"*. **One claim in 3,669 uses `hedge`.** Two representations of one thing, and the detector keys on stance — pick one. If `hedge` stays, §2 must say what it means and how the detector treats it.

**Validation**
- **(c)** — **DELIVERED · VERIFIED**: Over the 12-case hand-labelled set (`fixtures/behaviour/stance_validation_eval.json`), Validator 7 augmented with syntactic negation analysis corrected **4 claims from `support` to `oppose`** (`oppose_1_licensing`, `oppose_2_ai_licensing_neg`, `oppose_4_ubi_reject`, `oppose_5_spending_denial`), satisfying Assertion (c).
- Both directions on the hand-labelled set: all 6 genuine supports ended as `support` (including 2 corrected from `oppose` $\to$ `support`), all 6 genuine opposes ended as `oppose`. Confusion counts: 0 false supports, 0 false opposes (12/12 correct).
- Bidirectional standing counters reported: `stance_corrected_to_oppose = 4`, `stance_corrected_to_support = 2`.
- Corpus distribution after migration: `support` 3,020 (82.31%), `oppose` 437 (11.91%), `mixed` 212 (5.78%), `hedge` 0 (0.00%). Single legacy hedge claim migrated to support with `hedging_level = 0.7`.
- `Literal["support", "oppose", "mixed"]` enforced across entities, schema, and runtime.

**Falsify.** Feed the validator a quote that plainly negates its proposition and confirm it labels `oppose`. Verified in `tests/test_stance_direction_d3.py`: plain negation quote is corrected to `oppose`. Under legacy embedding instrument alone without syntactic analysis, `sim_neg > sim_pos + 0.05` is never met and the correction fails.

**Blast radius.** `worker/extract/validators.py`, `fixtures/behaviour/stance_validation_eval.json`, `docs/design_claim_extraction.md` §2, `docs/ongoing_errors.md` §2 (031 re-measured; `hedge` resolved), §3, §6.

---

## 13u. D1 — Propositions drifted back into full clauses, and that is why nothing merges

**User impact:** two phrasings of the same matter start resolving to the same proposition, which is the precondition for finding a contradiction at all.

**Contract:** `design_claim_extraction.md` §2 (canonical form — **the single most important rule**) · `design_data_layer.md` §2 (propositions are global) · `ongoing_errors.md` §2 parameter 008.

**Gap — measured, and it explains the zero.** `design_claim_extraction.md` §2 defines the canonical form as *"a neutral, tenseless statement of the **matter at issue**, with the actor and the polarity stripped out"*, and its worked example is a **noun phrase**: `federal licensing of frontier AI models`. What the extractor produces now:

- **75.2% of propositions (2,615 of 3,477) contain a finite verb** — they are full clauses, not matters at issue.
- Many carry **polarity**, which §2 forbids outright: *"Forces should be allowed to play out"*, *"democrats are favored to win the house in the upcoming election"*, *"Azure is cheaper than running a database on-premise"*. **The polarity validator only rejects negative forms** (`should not|shouldn't|must not|never|oppose|against|no `), so positive polarity passes freely — and a proposition that already takes the position makes `support` redundant and `oppose` incoherent.

**This is the cause of the merge failure, and the merge failure is the cause of the zero.** Full clauses naming one matter embed far apart — *"Azure is cheaper than on-prem"* and *"cloud costs less than running your own database"* share a matter and almost no surface. Noun phrases naming that matter do not have that problem. The numbers:

| | before C1 (1,288 claims) | after C1 (3,669 claims) |
|---|---|---|
| propositions per claim | 0.954 | **0.948** |
| singleton propositions | 95.4% | **95.5%** |
| propositions spanning 2+ episodes | 4 (0.33%) | 63 (1.8%) |
| cross-source `support`↔`oppose` pairs | 0 | **0** |

**A six-fold corpus changed the merge rate by 0.006.** Scaling did not fix overlap because overlap was never limited by corpus size — it is limited by propositions being too specific to recur. Of the 63 propositions that do span episodes, only 9 carry more than one stance, and none is a cross-source `support`↔`oppose` pair.

**Implementation — each step carries its own check. Run the check before starting the next step.**

**Step 0 — Record the baseline you must beat.** Before changing anything, run and paste into the commit body:

```sql
SELECT count(*) FROM propositions;                                   -- expect 3477
SELECT count(*) FROM claims;                                         -- expect 3669
-- singleton rate
SELECT count(*) FROM (SELECT proposition_id FROM claims GROUP BY 1 HAVING count(*)=1);  -- expect 3318
-- full-clause rate: propositions containing a finite verb
--   regex: \b(is|are|was|were|will|would|can|could|should|has|have|do|does|did)\b
--   expect 2615 of 3477 = 75.2%
```

> **Verify:** your numbers match these within a few rows. **If they do not, stop and say so** — the corpus has moved since this item was written and every target below needs recomputing.

**Step 1 — Extend the polarity validator, and watch it go red on today's corpus.** `worker/extract/validators.py` currently rejects only `\b(should not|shouldn't|must not|never|oppose|against|no )\b`. Extend it to positive and modal polarity: bare `should`/`must`/`ought`, comparatives of evaluation (`better|worse|cheaper|faster|stronger than`), and outcome predictions (`is favored to`, `will win`, `will beat`). Keep the existing reason string `proposition_carries_polarity`.

> **Verify (this is a red-first step):** run the extended validator over all 3,477 stored propositions **before touching the prompt**. **It must reject a substantial set**, and *"Forces should be allowed to play out"*, *"democrats are favored to win the house in the upcoming election"* and *"Azure is cheaper than running a database on-premise"* must each be among them. **Record the count and three examples in the commit body.** If it rejects nothing, the patterns are wrong and step 2 will paper over it.

**Step 2 — Extend the same validator to negation inside subordinate clauses.** §2 now says negation is polarity. *"Running a Chinese model does not necessarily mean data goes to China"* and *"The device will not be similar to an iPad"* must be rejected; the current list misses both because the negator is not one of the listed modals.

> **Verify:** those two exact strings are rejected. **This step is also D4's dependency** — it removes one of the two causes of validator 7's false flips — so state in the commit body how many stored propositions carried negation.

**Step 3 — Restore the canonical form in the prompt.** `worker/extract/runtime.py`. A proposition is the **matter at issue**: noun phrase where that reads naturally, tenseless, actor stripped, polarity stripped in both directions. Use §2's table as few-shot examples verbatim — `federal licensing of frontier AI models` is the shape.

> **Verify:** extract from **20 utterances only** and read all 20 propositions by hand. **Do not proceed to the full run until you have.** At least 15 of 20 should be noun phrases; every one must pass the step 1–2 validators. If they are still full clauses, the prompt change did not take, and a 5-hour re-extraction will bake that in.

**Step 4 — Decide the form check honestly.** A deterministic "is this a full clause" test is harder than a regex. **Try it; if you cannot make one that discriminates, say so in the commit body and rely on the prompt plus the polarity validators.** Do not ship a validator that cannot fail — that has happened four times here (§5 traps 29, 36, 38, 52).

> **Verify:** if you ship a form check, it must reject *"Azure is cheaper than running a database on-premise"* and accept *"federal licensing of frontier AI models"*. If you do not ship one, the commit body says why.

**Step 5 — Re-extract the full corpus.** Proposition text changes wholesale, ids change, and `claim_id` hashes `proposition_id`, so this is a full re-derivation. **Do not hand-edit proposition text** — W1's defect was created exactly that way. Bump `prompt_version`; old claims stay auditable.

> **Verify immediately after, before any analysis:** `verify_quotes`, `verify_canonical_ids` and `verify_entailment_holds` all PASS; no source has zero claims; claim count is within ~20% of 3,669. **A large drop means the new validators are rejecting good claims** — investigate before continuing.

**Step 6 — Re-run dedup at the existing `T_dedup = 0.86`.** Do **not** retune it here; that is D2, and changing form and threshold together makes neither measurable.

> **Verify — this is the whole point of the item:** recompute the singleton rate. **It must fall materially below 95%.** Report it beside 95.5%. If it has not moved, the form change did not fix merging and D2 will not save it — stop and report that, which is a legitimate delivery.

**Step 7 — Re-run tension detection and report the denominator.** Pairs examined, pairs rejected, reason for each.

> **Verify:** read every candidate pair the detector would publish, by hand. Not a sample — all of them. This project has published three fabrications, and all three were obvious on sight and invisible in aggregate.

**Validation**
- **(c)** — **the singleton rate falls materially below 95%**, and **`propositions spanning 2+ episodes` rises well above 1.8% of the table**, over the *same 23 episodes*. *Same corpus, different form: this isolates the change to proposition shape and cannot be satisfied by adding episodes, which is what C1 already proved does not work.*
- **Read the ten largest merge clusters by hand** and confirm each groups restatements of **one matter at issue**, not one topic (trap 43). This is a judgement and it must be made by a person reading text.
- Zero propositions contain positive or negative polarity, checked by the extended validator over the whole table.
- Both directions: *"federal licensing of frontier AI models"* passes; *"Forces should be allowed to play out"* is rejected.
- `verify_entailment_holds`, `verify_quotes` and `verify_canonical_ids` all PASS after re-extraction.

**Falsify.** Revert the prompt to v1.5 and re-extract a sample; the singleton rate must return to ~95%. Revert; record both.

**Blast radius.** `worker/extract/runtime.py` (prompt), `worker/extract/validators.py`, `fixtures/behaviour/`, the corpus (full re-extraction), `docs/design_claim_extraction.md` §2, `docs/ongoing_errors.md` §2, §3, §6.

---

## 13v. D2 — Re-measure parameter 008 against a corpus that exists

**Blocked on D1.** Measuring the merge threshold before proposition form is fixed measures the wrong distribution.

**Contract:** `ongoing_errors.md` §2 parameter 008 · `design_claim_extraction.md` §2 (Deduplication).

**Gap.** `T_dedup = 0.86` was measured during P0, over a corpus that **no longer exists in any respect that matters**: 1,499 propositions, 7% of them indexical attractors (*"The speaker believes…"*), before W0 and W2 rewrote proposition text wholesale and before C1 tripled the corpus. The recorded justification cites specific similarities — *"China open source sim = 0.8632"*, *"spatial computing … sim = 0.8528"* — computed over propositions that have since been replaced.

**A threshold measured against a distribution that has been replaced is not a measured threshold.** It is currently merging 4.5% of propositions, which is the observable consequence.

**Implementation**
**Each step carries its own check. Run the check before starting the next step.**

1. After D1, embed every proposition and **plot the nearest-neighbour similarity distribution.** Choose the threshold where genuine restatements merge and distinct matters do not — §2's bias is **toward merging**, because over-splitting hides every contradiction silently and over-merging produces visible, fixable false positives.
   > **Verify:** the distribution shows visible structure — a mass of near-duplicates and a mass of unrelated pairs — **before** you pick anything. If it is unimodal there is no threshold to find, and the honest delivery is to report that embedding similarity over proposition text cannot separate restatement from difference at this corpus size. **Paste the decile boundaries into the commit body.**
2. **Record the value with its n and the date**, and state that it supersedes P0's measurement and why.
   > **Verify:** `ongoing_errors.md` §2's row for parameter 008 names the corpus it was measured over — claim count, proposition count, prompt version — so the next reader can tell when it has expired. Nobody could do that for `0.86`, which is why it outlived two corpora.
3. Re-examine whether the ambiguous band earns its cost. Issue 008 concluded it does not, over the old distribution. **That conclusion inherits the old distribution's flaw** and should be re-taken, not assumed.
4. Re-run tension detection and report the candidate denominator.
   > **Verify:** read every candidate pair by hand before recording the item delivered. **All three fabrications this project published were obvious on sight and invisible in aggregate.**

**Validation**
- **(c)** — **at least one proposition carries claims from two different episodes with opposing stances**, i.e. the candidate set is non-empty for the first time — **or** the item reports, with the distribution plot and the pairs it considered, that no threshold in a defensible range produces one. *Both are real results. A number with no denominator is not.*
- Both directions at the chosen threshold: the two "China open source" propositions merge; *"high speed trains in China are built and operated by private industry"* does not.
- The merge histogram is reported before and after.

**Falsify.** Set `t_dedup = 0.999` and confirm the histogram collapses to all-singletons, reproducing today's state — proving the threshold and not some other change drives the merges. Then `0.30` and confirm absurd merges appear. Revert; record all three.

**Blast radius.** `worker/extract/dedup.py`, the corpus (proposition re-resolution), `docs/ongoing_errors.md` §2 (008 superseded), `docs/design_claim_extraction.md`, §3, §6.

---
## 13w. D4 — Validator 7 now fires both ways, and its new direction is wrong on live data

**User impact:** stance corrections stop introducing errors at roughly the rate they remove them.

**Contract:** `design_claim_extraction.md` §2 · `ongoing_errors.md` §2 parameter 031 · Issue 018 = B (the 5-case floor) · traps 20, 22, 56.

**Do not re-validate the corpus with the current validator. That is the first thing to know.** It would rewrite roughly 266 claims to `oppose` and 128 to `support`, and the `oppose` direction is the one producing errors.

**What D3 got right, verified independently.** The instrument does now discriminate. I ran the new `validate_stance_direction` over a random 300-claim sample of live own-assertion claims:

```
would flip support -> oppose : 25
would flip oppose -> support : 12
unchanged                    : 263
```

That is a genuinely bidirectional validator, and D3's root-cause diagnosis was correct and honestly reported — `nomic-embed` cannot separate `P` from `¬P` at the ±0.005 the old margin needed, so parameter 031's `delta = 0.05` was unreachable in one direction. `hedge` is also properly retired: the enum is `support|oppose|mixed` and **0 claims** carry `hedge`.

**What is wrong.** I read the flips by hand, as §27 now requires. **All four `support` → `oppose` flips I read are false.** All four are the same mistake — **negation detected without scope**:

| proposition | quote | why the flip is wrong |
|---|---|---|
| *the rest of the world will continue to utilize LLMs even if the US does* | *"the rest of the world's **not** going to **stop** using these models"* | `not stop` = continue. The quote **agrees**. |
| *understanding user intent … is a significant advance* | *"we would **never** have been able to predict … that we go from a great summarizer to actually understanding your intent"* | `never` negates *predict*, not the proposition. |
| *anthropic's growth rate is significantly faster than openai's* | *"That's **not** that much of an increase when anthropic is growing 10x and openAI 4x"* | `not` negates *much of an increase*. |
| *Running a Chinese model on your own infrastructure does **not** necessarily mean data will go to China* | *"a lot of people think the data must be going back to China, but **it's not** if it's run on your own infrastructure"* | **Both** carry negation. Two negatives read as opposition; the quote agrees. |

The four `oppose` → `support` flips I read all look **correct** — that direction is doing real work. The defect is one-directional.

**Two causes, and the second is D1's:**
1. **`has_syntactic_negation` matches a negator anywhere in the quote**, with no notion of what it scopes over. *"not going to stop"*, *"never … predict"*, *"not that much"* all register as opposition to whatever the proposition says.
2. **Propositions that themselves contain negation** — *"does not necessarily mean"*, *"The device will not be similar to an iPad"*. `design_claim_extraction.md` §2 forbids polarity in a proposition and **negation is polarity**; the existing validator only rejects a fixed list of negative modals, so `does not … mean` passes. When both sides carry a negator, naive matching inverts a claim that agrees. **D1's polarity work removes this class; do D1 and then re-measure.**

**And the reason none of this showed up: the evaluation set could not contain the failure.** D3 built 12 hand-written cases, 6 per class, and scored **6/6 both ways with zero confusion**. A random live sample gives **4/4 wrong** in one direction. The cases were composed to illustrate the rule rather than **drawn from the corpus**, so every one had a negator whose scope was the proposition — the easy shape. **A curated set tests the mechanism you had in mind; only a drawn set tests the one you built** (traps 20 and 22).

**Implementation**
**Each step carries its own check. Run the check before starting the next step.**

1. **Rebuild the evaluation set by sampling, not by writing.** Draw ≥ 40 own-assertion claims at random from the live corpus with a **recorded seed**, hand-label each, and commit the sample as a fixture. Issue 018 = B's 5-case floor is a floor, not a target, and a curated set does not satisfy it in spirit.
   > **Verify:** the fixture records the seed and the query used to draw it, and **the labels were assigned before running the validator** — otherwise you are labelling to agree with it. State in the commit body how many of the 40 you labelled `oppose`; if that is far from the corpus's 11.9%, the draw is not representative and you should redraw.
2. **Report a confusion matrix, not an accuracy.** Four cells, both directions, with the count of live claims each rate implies. The single number this item exists to produce is the **false-flip rate in the `support` → `oppose` direction**, currently unmeasured and near 100% on the sample read during verification.
   > **Verify (red-first):** run the **current, unmodified** validator over the drawn set and record its matrix as the baseline. **You must see the `support`→`oppose` direction fail here.** If it does not, the draw missed the failure mode — redraw, larger, before changing any code.
3. **Give negation a scope test.** Matching a negator anywhere in the quote is not enough. A dependency parse that checks whether the negation governs the predicate the proposition names is the honest version; a heuristic that at minimum excludes negation of a *different* verb would catch three of the four failures above. **If neither is achievable at acceptable cost, report that and leave stance to the extractor with the validator restricted to the `oppose` → `support` direction it demonstrably gets right** — a validator that runs in one direction knowingly is far better than one that runs in two and is wrong in one.
4. **Only after the false-flip rate is known and acceptable, re-validate the corpus.** Then say in the commit body how many claims changed in each direction, and re-run tension detection with its denominator.
   > **Verify:** before running it, **state the number of claims you expect to change in each direction** from the measured rates. Run it. Compare prediction to outcome in the commit body. A prediction that matches is worth more than either number alone; one that does not is a finding.
5. Do **D1 first** — its polarity fix removes cause (2), and D1's re-extraction will run validator 7 over everything, so shipping a validator with an 8%-of-claims false-flip rate into that run would bake the errors in.

**Validation**
- **(c)** — over the **drawn** evaluation set, the `support` → `oppose` direction's false-flip rate is **measured and reported**, and the four claims quoted above end as `support`. *The current validator flips all four to `oppose`; a curated set of 12 cannot detect that, and reproducing it is the whole item.*
- Both directions on the drawn set, as a confusion matrix with counts.
- The corpus is **not** re-validated until step 4's condition is met. Assert the stance distribution is unchanged by this item alone.
- `oppose` → `support` precision does not regress: the four flips I read in that direction still flip.

**Falsify.** Run the current validator over the drawn set and record its confusion matrix as the baseline. Any change must beat it, in both directions, on the same set. Record both.

**Blast radius.** `worker/extract/validators.py`, `fixtures/behaviour/stance_validation_eval.json` (rebuilt by sampling), `docs/design_claim_extraction.md` §2, `docs/ongoing_errors.md` §2 (031 re-measured with a confusion matrix), §3, §6.

---
## 14. X1 — Entailment validator · *Issue 025 = C*

**User impact:** a quote can no longer carry a claim it does not support. This is the guard that would have stopped the fabricated tension from ever being written.

**BLOCKED on D0 (§13e) — read it before planning.** Step 3 below embeds the proposition, and **no surviving proposition has an embedding**: all 7 rows in `proposition_embeddings` belong to the pre-X0 generation whose claims X0 removed. Both sides of the cosine are missing, so the (c) assertion cannot be reached. **Issue 027 = A** settles how the table is repaired; D0 does it. When D0 lands, the 8 live propositions are embedded with `embed_document` — the same prefix this validator must use — so do not re-embed them here.

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

## 15. R1 — Media duration and a real coverage check; fix the truncation · **DELIVERED**

**User impact:** the system reads whole episodes instead of the first seven minutes, and can tell when it hasn't.

**Blocked on X1** — see the queue. The re-ingest in step 5 is the largest extraction run this project will have done; it must not run before the entailment guard exists. Issue 027 = A preserved that ordering deliberately.

**The cap is found. Do not go looking for it again.** `scripts/populate_corpus.py:259`:

```python
extra = ({"max_bytes": 10_000_000},)  # 10MB chunk (~7-8 minutes of real audio)
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

## 16. C0 — Portability workflow; `mlx-lm` as an optional extra · *Issue 024 = B*

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

## 17. I0 — First real ingest · **SUPERSEDED → R1**

> **Do not open this as a work item.** I0.1 (enrollment) and I0.2 (single-speaker ingest) hold. I0.3's remaining defect is the 10MB download cap, tracked in **§15 (R1)**. This section is kept for the enrollment and panel detail, which R1's re-ingest still depends on.

*Subjects selected: Issue 021 = B.*

**Subjects:** Chamath Palihapitiya, David Sacks, Jason Calacanis, David Friedberg — the four All-In hosts. **Primary source:** the All-In Podcast.

> **Elon Musk is deferred — Issue 023 = A.** He is out of I0 entirely and out of the queue; see §20 for the trigger. He was named in the Issue 021 selection, but his primary medium is X, which is deferred (`master_implementation_plan.md` §9), and a long-form-only corpus would clear the sufficiency gate while measuring a systematically unrepresentative slice of him. **Do not ingest him.** The four hosts are the better first corpus regardless.

**User impact:** the system processes real human beings for the first time. Until now every green gate has been green over nothing.

### Read this before planning — the selection changed I0's shape

This guide previously said *"start single-speaker so diarization is not also on trial."* **That instruction cannot hold as written.** All-In is a four-host panel with interruptions and crosstalk — by `design_source_acquisition.md` §5.4 it is the single hardest attribution case in the design, and trap 11 exists because panels break every positional heuristic *silently*.

That is not a reason to push back on the choice. It is an excellent corpus for this product: five people, the same room, the same recurring topics across years, high-quality audio, hundreds of episodes, and public figures with enough material to clear the sufficiency gate. It also exercises cross-person comparison — which nothing else in the plan would have done this early.

**But the de-risking intent must be preserved by decomposition rather than abandoned.** The split below is already done; use it rather than re-deriving one.

### Sub-items — tick in the same commit

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

## 18. P4 — Tension detection

**User impact:** the product's core claim starts working — *here are two things you said that cannot both be your view.*

**Contract:** `design_rubric_engine.md` §1. Read it fully; this section does not repeat the tension-type table.

**Likely split:** (1) the reversal self-join, (2) the acknowledgement window, (3) the six preconditions + quarantine, (4) audience divergence.

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

## 19. P3 — Topic model

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

## 20. P5 — Principle extraction

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

## 21. P6 — Rubric engine

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

## 22. P7 — Local API

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

## 23. P8 — Browser extension

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

## 24. Deferred — designed for, not queued

**Elon Musk (Issue 023 = A).** Out of scope until X/Twitter ingest exists. **Trigger:** an `XAPIAdapter` or `XArchiveImportAdapter` lands behind the `SourceAdapter` Protocol and a Musk corpus can be assembled that includes his primary medium. Until then, ingesting him would produce a confident score over a systematically skewed slice, and **invariant I5 would not catch it** — it gates on volume, not composition (trap 24).

**Corpus-composition reporting.** Issue 023's Option B was not selected, so `corpus_composition` is not being built now. It remains the right long-term answer to trap 24 and applies to every subject, not just Musk. Revisit when X ingest arrives or when any subject's corpus draws from a single medium.

**X/Twitter ingest.** Deferred by decision, not difficulty (`master_implementation_plan.md` §9). The adapter Protocol must keep accepting it as a drop-in.

**Proposition-table purge (Issue 027 Option B, not selected).** A was selected, which keeps the orphaned pre-X0 propositions and their embeddings. The remaining cleanup — deleting the five non-fabricated orphans, pruning `proposition_embeddings` to the readable set, and replacing `claim_count` with a computed view — is right eventually and wrong now, because R1's re-ingest repopulates the table. **Trigger:** R1 has landed and the corpus is final. Doing it before then pays for the same migration twice.

---

## 25. Invariants — do NOT change

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

Full text: `master_implementation_plan.md` §3. Code violating one is wrong even if its tests pass.

---

## 26. Contracts

`master_implementation_plan.md` · `design_source_acquisition.md` · `design_claim_extraction.md` · `design_principle_extraction.md` · `design_topic_model.md` · `design_rubric_engine.md` · `design_data_layer.md` · `design_local_api_and_clients.md` · `design_ui_direction.md` · `design_evidence_integrity.md` · `e2e_verification_journeys.md` · `ongoing_errors.md`

---

## 27. Feedback loop — what specs here have got wrong

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

| **R1 grew the corpus 11.7× and left the claim count at 9** | "Re-ingest all four at full length once found. Record real throughput." | **"Re-ingest, then re-extract over the new utterances, then re-run P4–P6."** The item existed to give the detectors material. It delivered audio. **A stage not named in the instruction does not run** — and the agent was right to implement exactly what was written. |
| **A check that read its own default nine times and printed PASS** | "Report each population separately and print what was examined" | Same, **plus** "assert the reader's key is one the writer actually writes." E0 made `verify_no_suppressed_scores` examine 9 real assessments, which is how the inertness became visible — the fix surfaced the defect, it did not cause it. |

**The pattern: shape is what a stub reproduces perfectly, and a green gate over zero rows is the emptiest shape of all.** Validation must be satisfiable only by the real thing, operating on real data. **And a number that never varies is a shape too** — several entries above are constants that passed for measurements.

| **1,501 claims, 1,499 propositions, zero findings** | "Run extraction across all 4219 utterances. Every source contributes claims." | **"...and assert that propositions are *shared*: report the histogram of claims-per-proposition and require a tail."** Claim count measures extraction; **only proposition sharing measures whether the corpus can hold a contradiction.** N0's (c) asked for a tension or a candidate report, which was right — but a prerequisite made both unreachable, and nothing in the item's own assertions could tell the difference between "no candidates" and "no findings". |
| **E1 removed a default and the check stayed inert** | "Remove the default. A missing verdict FAILs." | Same, **plus** "the verdict must be computed from the sufficiency inputs, never from the axis scores." The instruction said what to delete and not what the replacement had to be independent of — so the inertness survived the rewrite intact. |

| **The first two tensions ever published were both false** | "At least one proposition carries claims from two different sources on different dates, and the tension detector runs over a non-empty candidate set. Report the candidate-pair count." | **"...and read the resulting tensions by hand before recording the item as delivered."** Every assertion in P0's (c) was satisfied — candidate pairs existed, the histogram grew a tail, the merges looked right in aggregate. **Aggregate statistics cannot distinguish a real finding from a fabrication; only reading the output can.** When an item's product is a claim about a person, one human-legible example is the assertion. |
| **A merge that voided a validator nothing re-ran** | "Re-resolve propositions over existing claims. Do not re-extract." | Same, **plus** "re-run every validator whose input the re-resolution changes." The instruction correctly avoided re-extraction and did not notice that re-pointing a claim changes the exact pair validator 6 had certified. |

| **All five surviving candidate pairs false, in three new ways** | "Read the five largest merge clusters by hand and confirm each groups restatements of one proposition." | **"...and read every candidate pair the detector would publish, before recording the item delivered."** Reading the *merges* was right and insufficient: the merges were sound and the pairs built on them were not. **Read the thing the user would see, not the intermediate the fix touched.** |
| **W0 removed three patterns and left ten percent** | "Reject `the speaker`, bare `the subject`, `the described`." | **"Reject any proposition not resolvable without external context; the three patterns above are examples."** The item handed the implementation a list, so it got a list. |

| **2,593 HTML files for 1,288 claims** | "Static export: dump DuckDB to JSON at build time and serve a static site." | **"...and say how many files that produces at the corpus's current size."** The option was chosen for its safety properties — no server, no write path — and those were real. Nobody costed the output. **When an architecture's cost scales with row count, put the row count in the option.** |

| **A read-only guarantee that writes** | "Open DuckDB `read_only=True`, and let that be the guarantee. Assert it — a test that attempts an `INSERT` must raise." | **"...and name the configurations it must hold in."** The instruction was followed exactly: the connection is opened read-only, and a test attempts the write and sees it raise. Both true, in one branch of two. **An assertion that does not say *under what conditions* will be satisfied under the convenient one.** |

| **Six-fold corpus, still zero findings** | "Propositions appearing in 2+ episodes rises materially above 4, and the detector reports a non-empty candidate set with its denominator." | **"...and the singleton rate falls."** The assertion was met — overlap rose 4 → 63 — and it was met while 95.5% of propositions stayed singletons, because *rises materially above 4* is satisfiable by a rounding error once the table triples. **State the assertion as a rate over the table, not as a count**, whenever the table's size is also changing. |

| **A validator that fires both ways and is wrong one way** | "Validator 7 corrects at least one claim from support to oppose over a hand-labelled set of genuine oppositions." | **"...over a set drawn at random from the corpus, reported as a confusion matrix."** The assertion was met exactly — one direction fired, both classes scored 6/6 — on twelve cases written to illustrate the rule. **When an assertion permits the author to supply the test data, it measures intent rather than behaviour.** |

**The newest pattern: a correct fix to the wrong scope reads exactly like success.** And the sharpest version this project has produced: **Issue 030 was the right decision against the wrong diagnosis.** The corpus did need expanding and expanding it was done well; it simply was not what stood between the pipeline and a finding. **Before committing hours of compute to a diagnosis, check that the cheap query agrees with it.** R1's gates were green, its coverage real, its numbers honest, and the thing it existed to enable did not happen. N0 then repeated it one layer down. **Check what the item was *for*, not only what it said** — and when an item's purpose is to feed a downstream stage, make one of its assertions a property of *that stage's input*, not of its own output.
