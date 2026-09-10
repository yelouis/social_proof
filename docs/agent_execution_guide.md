# Agent Execution Guide — Active Build: make the detector produce a real finding — September 7, 2026

**You are an engineering agent with no memory of this project.**

**Read §1 first; it says where to start.** There is no routing machinery below — you are expected to organise the work yourself. What is fixed is §4 (what you may not change), §5 (what has bitten this project), §7 (what counts as evidence) and each item's own assertions.

**Where the project is.** Twenty-nine items delivered — §10 lists them with the commit carrying each full spec. Gates green, tree clean, `mypy scripts/` repaired.

**X2 worked, and the thing it added is why this pass is short.** Issue 034 = B moved the position test out of judgement and into the output format. Every one of **1,517 claims** now carries a `position_frame` — *"the speaker is FOR/AGAINST ⟨X⟩"* — **0 unparseable, 0 stance disagreements, ⟨X⟩ matching `proposition_text` on 96.3%** of them under the store's own normalisation. Validator 2b's fire rate halved, 22.9% → 11.1%. **And the corpus grew for the first time in this whole sequence: 1,027 → 1,517 claims.** Three form iterations shrank it by 72%; the format change reversed that.

**X2 also published one tension, and it is false — the fourth this system has published.** But read how it fails:

```
  A  support  the speaker is FOR      60 to 80 percent growth year over year
  B  oppose   the speaker is AGAINST  10x year over year growth for ever
```

**⟨X⟩ differs.** Sacks being pleased with 60–80% growth and holding that 10x forever is impossible are not a reversal. **The previous three fabrications took a careful read of quotes to spot. This one is a two-line diff of a stored column** — which is exactly what `position_frame` was added to make possible, and it means the check can now be code instead of judgement.

**The prompt is not at fault.** Both frames are well-formed and match their quotes. **Dedup merged two different matters** at `T_dedup = 0.84` — a threshold D2 measured against a distribution X2 has since replaced. Four of the store's five support/oppose proposition groups are dedup artefacts.

**X3 (§11) delivered. D8 (§12) is now active.** X3 quarantined the false tension and made frame-⟨X⟩ identity a mechanical precondition, so a mismatch can never publish again. D8 re-measures `T_dedup` against the v1.8 distribution — the follow-up X2 correctly deferred — and it can now be measured **against the frames rather than against a judgement**, which is a first for this parameter.

**Start at §12.** §5 and §7 are why the items look the way they do.

**Items now carry per-step checks, written as `> **Verify:**` after the step they belong to.** Run each before starting the next step. Several are **red-first**: they tell you to run something and *watch it fail* before you fix anything, because a check that has only ever been green on repaired data has not been tested.

**Every number, threshold, field name and literal string in the design docs is deliberate. Implement as written.** Where a doc says a value must be *measured* (`ongoing_errors.md` §2), measure it.

---

## 1. Where to start

**Run §2's state-detection block and read its output.** Then read §3, §5, §7 and §6 — the baseline, the traps, the validation standard, and the queue. Then read your item's own section **and every contract doc it cites, in full.** The guide points; the design docs specify. Reading only the guide has produced three of this project's published fabrications.

**§6 holds only outstanding work — take the first row.** If the tree is dirty, deal with that first — someone stopped mid-item and half-finished work is not a base to build on. If a gate §3 records as passing comes back red, that outranks the queue.

**You are trusted to organise your own work.** There is no prescribed routine below beyond §8, which is short. Sequence, batching and when to commit are yours to judge. What is *not* yours to judge is in §4, and what counts as evidence is in §5.

**The one thing to internalise before anything else:** every item in §6 is here because a previous agent's work passed all its gates and was still wrong. Not careless work — *good* work, measured against assertions that could not tell the difference. §5 exists to make that less likely, and §15 records each specific way it has happened.

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
| `mypy --strict` | **PASS** | Clean across worker/, tests/, fixtures/, golden/, scripts/ (120 files). Item G2 & X3 delivered. |
| `pytest tests/ -q` | **PASS** — **277 passed in 296s** | Re-measured September 10 over 23-source corpus. Well above trap 18's 35s floor. All unit, behavioural, and falsification tests pass. |
| `STUB_REGISTRY` | **EMPTY** | All V-items genuinely delivered. |
| `worker.integrity --all` | **PASS — 16 checks, independent populations, active sufficiency verdicts, referential integrity, entailment validation, claims-per-hour rate check, and frame identity** | G1, E1, N0, P0, W1, W0, S1, C1, D1, D4, D5, D7, X2 & X3 delivered: 16 checks (Check #16: `verify_frame_identity`), FIXTURES and CORPUS reported separately with no union; `verify_quarantine_not_rendered` reports quarantine rate 100.0% (5/5) derivable from table alone; 0 published tensions; `verify_frame_identity` passes on both FIXTURES (1 published tension verified) and CORPUS (0 published tensions, zero rows); all 16 checks PASS. |
| `worker.golden.report` | **PASS** | Fixtures 20/20 (all 17 classes). Corpus metrics `NOT MEASURED — n=0`. Correct and honest. |
| **Working tree** | **CLEAN** | All gates pass; D7, G2, X2 & X3 delivered and verified live from DuckDB. |
| **Review site** | **DELIVERED (U1 DELIVERED)** | Served live from DuckDB on local API (`/`, `/episode/{source_id}`, `/claim/{claim_id}`, `/person/{subject_id}`) with `read_only=True` connection guarantee. Static export and `site/` deleted (Issue 033). Assertion (c) full sweep verified (200 OK, verbatim quotes verified, zero quarantined IDs). Empty sections render with honest reasons (§4). Zero links to offset 00:00. |
| **Site read-only guarantee** | **DELIVERED · VERIFIED (A0 DELIVERED)** | Deleted silent fallback to `storage.con.cursor()`. When `Storage` is writable and holding the lock, `create_app` raises `RuntimeError` naming the cause, strictly enforcing the read-only guarantee. Assertion (c) verified in `test_review_site_u1.py`; falsification verified (restoring fallback fails assertion (c)). |
| **Proposition form** | **STORED POSITION FRAMES (ITEM X2 DELIVERED · VERIFIED)** | Canonical noun-phrase *matter at issue* elicited with position frame under prompt `v1.8` (`gemma-3-27b-it:v1.8:s1`). Stored in `claims.position_frame`. 20/20 random claims pass byte-identical agreement with proposition and stance. Across all active propositions: **0 finite verbs (0.00%)** and **0 polarity violations**. Item X2. |
| **Merge rate** | **RE-MEASURED UNDER ITEM D2 (0.84)** | At calibrated $T_{\text{dedup}} = 0.84$, 31 propositions merged, reducing active propositions to 2,160; singletons: 2,081 (96.3%); 43 propositions span 2+ episodes (2.0%). |
| **Stance direction** | **SCOPE-AWARE & BIDIRECTIONAL (D4 & X2 DELIVERED · VERIFIED)** | Stance elicited directly from position frame (FOR $\to$ support, AGAINST $\to$ oppose, both $\to$ mixed) and certified via Validator 7 with scope-aware negation detection (`has_syntactic_negation`). Re-measured under Item X2 over drawn sample from live corpus (80 claims, seed 168, 75 support / 5 oppose): 0/75 false flips in support $\to$ oppose (0.00% false-flip rate); True Oppose: 5/5 (100.0%) ended Oppose; zero confusion errors across all 80 cases. All 4 canonical quotes end as `support`. |
| **`hedge`** | **RETIRED (D3 DELIVERED)** | Enum standardised to `support\|oppose\|mixed` across entities, schema, prompt and scripts; the single legacy claim migrated to `support` with `hedging_level=0.7`. **0 claims carry `hedge`.** Verified. |
| **Corpus overlap** | **MULTI-EPISODE CLUSTERS (D2 DELIVERED)** | Multi-episode noun-phrase propositions span up to 5 episodes. Top clusters verified as single matters at issue without topic blurring. |
| **CI / Portability** | **PASS** | `portability.yml` tests base install without Apple extra; runs lint, mypy, and non-model tests across all 5 directories. |
| **Corpus** | **POPULATED, FULL COVERAGE (R1, N0, P0, W1, W0, C1, D1, D4, D5, D2 & X2 DELIVERED)** | 23 contiguous sources (20 contiguous + 3 historical bootstrap episodes), **20,666 utterances**, **1,517 claims**, **1,465 propositions** (1,464 active, 1 quarantined), 92 roles, 8 assessments. Coverage across all sources >= 80.0% (Parameter 029). All 23 sources clear claims-per-hour rate floor >= 3.0 claims/hr (Parameter 033: observed range 15.01 – 89.98 claims/hr). |
| **Propositions** | **1,464 ACTIVE (D1, D5, D2 & X2 DELIVERED · VERIFIED)** | Extracted under prompt `v1.8` with position frame and canonical noun-phrase matter at issue. Consolidated at calibrated $T_{\text{dedup}} = 0.84$ with strict re-point entailment validation (`T_ENTAIL_HIGH = 0.70`). Zero unbound pronouns or indexicals. 0% finite verbs. Falsification verified. |
| **`source_count`** | **MEASURED** | All 4 hosts draw on all episodes. Resolved through the utterance anchor chain, `hasattr` removed, I3 violation raises. Item M0 delivered, independently confirmed against ground truth. |
| **`source_roles`** | **92 ROWS FOR 92 PAIRS (G1 & C1 DELIVERED)** | Generated via `compute_role_id()`. 92 rows across 23 sources for 4 hosts. `verify_canonical_ids` and `verify_role_coverage` PASS across all 20,666 utterances. |
| **Sufficiency verdict** | **DELIVERED · VERIFIED (E2 DELIVERED)** | Parameter 012 sufficiency floor enforced strictly on inputs BEFORE scoring (`MIN_CLAIMS=3`, `MIN_SOURCES=1`, `MIN_SPAN_DAYS=0`). Dependency runs one way: verdict -> scores. When `passed` is False, all axis calculations are suppressed (`reason: "insufficient_corpus"`). Live corpus hosts all clear sufficiency on the merits. |
| **Corpus — claims** | **1,517 CLAIMS (N0, P0, W0, S1, W2, C1, D1, D4, D5 & X2 DELIVERED)** | Ingested and re-extracted under prompt `v1.8` with stored `position_frame`. Every source contributes >= 3.0 claims/hr (15.01 – 89.98 claims/hr). |
| **Assessments** | **EVALUATED, REFERENTIALLY GUARDED** | 8 rows across 2 topics (`top_ai_reg`, `global`). Sufficiency verdict `passed: True` across all 4 enrolled hosts. |
| **Published tensions** | **1 PUBLISHED · 4 QUARANTINED (ITEM X2 DELIVERED)** | 1 published unacknowledged reversal tension detected (David Sacks on 60-80% growth vs 10x growth forever). Quarantine rate: 80.0% (4/5) reported as first-class metric derivable from table alone. `verify_attribution_floor` and `verify_negation_recheck` examine 1 published tension and pass. |
| **Candidate pairs** | **3 EXAMINED · 1 ACCEPTED (ITEM X2 DELIVERED)** | Evaluated via `evaluate_candidate_pairs`: 3 candidate pairs examined; 1 rejected by same-source rule; 1 quarantined for low attribution confidence; 1 accepted. |
| **Reversals — same-source disqualification** | **DELIVERED · VERIFIED (T1 DELIVERED)** | Same-source opposing claims automatically disqualified from `unacknowledged_reversal` and routed to `stance_conflict_reviews` with reason `same_source_stance_conflict`. Parameter 032 `MIN_REVERSAL_GAP_DAYS = 0.0` (provisional). Candidate evaluation reports exact denominator. Item T1 delivered. |
| **`stance`** | **VALIDATED (S1 DELIVERED)** | Validator 7 (`validate_stance_direction`) certifies directional alignment ($P$ vs $\neg P$) with margin $\delta = 0.05$. Inverted oppose claims corrected to support. Genuine oppose claims survive. |
| **`is_own_assertion`** | **SENSITIVITY RAISED — 7.78% (S1 DELIVERED)** | Over 90 non-assertive quotes excluded (`exclusion_reason="question"` or `"hypothetical"`), maintaining floor > 5.0%. Measured via `get_exclusion_rate()`. |
| **Propositions — residual indexicals** | **0% — ZERO UNBOUND PRONOUNS / DEICTICS (W2 DELIVERED)** | Extended validator to enforce the principle of self-containment against the property: rejects sentence-initial pronouns/deictics, unbound third-person pronouns (`they/their`, `he/his/him`), and comparatives without relata (`the same`, `such`, `the other`). Preserves bound pronouns with internal antecedents (`Moderna patented its mRNA technology`). Pre-repair RED state verified (132 failing propositions across 139 claims). Re-extracted under `v1.5` prompt; active store contains exactly 0 unbound propositions (Assertion c). Both target false candidate pairs eliminated. Item W2 delivered. |
| **Entailment after merge** | **DELIVERED · VERIFIED (W1 DELIVERED)** | Re-pointing strictly validates entailment (`T_ENTAIL_HIGH = 0.70`); refuses merge when quote does not entail target proposition. Check #14 `verify_entailment_holds` asserts entailment holds across all stored claims against current propositions (PASS on 1,288 claims). Falsification verified. |
| **Propositions — indexical** | **0% — ZERO INDEXICAL PROPOSITIONS (W0 DELIVERED)** | 192 indexical propositions across 204 claims identified and repaired. Fixed prompt `v1.3` with Rule 3 explicitly prohibiting indexical frames; added `validate_self_contained` validator (`proposition_not_self_contained`); Precondition 6 in tension detector. Cleaned live corpus contains exactly 0 indexical propositions. Item W0 delivered. |
| **`t_dedup`** | **DELIVERED · VERIFIED (D2 DELIVERED)** | Re-measured at `T_dedup = 0.84` (single source of truth in `worker/extract/dedup.py`). Deciles: D10 0.6902, D50 0.7547, D90 0.8351. Both canonical directions verified. Ambiguous band re-examined (329 pairs in [0.80, 0.84); does not earn its cost). Falsification verified. |

---

## 4. Standing constraints

- **One item = one commit**, the *why* in the body. Too big → split it (§9).
- **Never fill in a `Your selection: _____` line.**
- **A stub is not a delivery.** Real dependency runs, or it isn't done.
- **Dependencies land in `pyproject.toml` in the same commit.**
- **Never print a number you did not measure.** Constants, projections from constants, and metrics below their floor render `NOT MEASURED`.
- **Every integration item needs one assertion a stub cannot satisfy** (trap 17). The single most important rule here.
- **Quote the item's `(c)` verbatim in the commit body and answer it with a number, next to its target.** Not "assertion (c) verified" — the sentence, then the measurement. **If a test carries `assertion_c` in its name, re-read the item's `(c)` and confirm the test asserts *that sentence*; the name is not the contract** (trap 60). D1 reported its real numbers honestly in prose and separately recorded "(c) verified" about a test asserting the table was non-empty. Both were written in good faith and the label was still wrong.
- **`(c)` failing is a legitimate outcome. Concealing it is not.** Several items here explicitly license a negative result — *"if it has not moved, stop and report that."* Report it as `(c) NOT MET`, with the numbers. **An item that lands with `(c)` honestly unmet is worth more than one that lands with `(c)` relabelled**, because only the first tells the next agent where the problem actually is.
- **Every `> **Verify:**` step is answered in the commit body — including the ones you skipped, marked as skipped, with the reason.** A per-step check that is silently passed over is indistinguishable from one that passed. D1's step-5 check would have caught a 41% loss of the corpus; it was not run and not mentioned.
- **A guard that has never failed has not been tested.** Falsification is mandatory (§7, §8 step 6).
- **All writes go through the worker** (I8). **No LLM at scoring time.** **Audio deleted after transcription** (Issue 003). **DuckDB is the only store** (Issue 015).
- **Update every doc your change invalidates, in the same commit.**
- **This file and `ongoing_errors.md` are queues, not archives.** §6 holds only outstanding work; a delivered item becomes one line in §10 naming its commit, and the spec lives in git. File new issues at the **top** of `ongoing_errors.md` §1. When one is selected, move it out: write the consequence into the design doc that owns it, add a row to §4, delete the option text. Git history keeps the reasoning.

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
69. **Storing the judgement turns the next check into code.** Three fabrications needed a careful read of quotes to spot. The fourth is a two-line diff of `position_frame`, because X2 persisted the sentence the model wrote instead of only its conclusion. **When a step depends on a judgement, store the artefact the judgement was made from** — the next person gets a query instead of an opinion.
70. **A parameter measured on a distribution that a later item replaces is stale on the day that item lands.** `T_dedup = 0.84` was measured over v1.7 propositions and merged *"60 to 80 percent growth"* with *"10x growth for ever"* on v1.8 output. X2 correctly refused to retune it in the same commit; **the cost of that discipline is a follow-up item, and it must actually be filed** (§12).
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
44. **A constant documented in one module and re-defaulted in a caller's signature runs at the caller's value.** `dedup.py` and `ongoing_errors.md` §2 both record `T_dedup = 0.86`; `extract.py:26` defaults 0.85 and wins. **Grep for the parameter name across every signature, not just its definition** — the measurement is worthless if it describes a value that never executes.
40. **Deterministic IDs only hold while every writer uses the helper.** Two `scripts/` build `f"role_{sid}_{subj_id}"` by hand instead of calling `compute_role_id`, so the primary key sees two different ids for one pair and the "every write is an upsert" guarantee silently becomes "every run inserts again." **Grep for hand-built id strings, not just for the helper's callers** — and note that `scripts/` is where this happened, because `scripts/` is outside every gate.

---

## 6. Queue

| Order | ID | Item | Blocked | Why here |
|---|---|---|---|---|
| 1 | **D8** | Re-measure `T_dedup` against the v1.8 distribution | none | The follow-up X2 correctly deferred, now unblocked by X3. 0.84 merged *"60 to 80 percent growth"* with *"10x growth for ever"*. **The frames are now ground truth for whether a merge was right** — this parameter has never had that. |

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

**Answer the assertion that was written, not the one you can satisfy.** An item's `(c)` is a sentence with a number in it. Quote it, measure it, put the two side by side. Every other form of reporting — a passing test whose name references it, a narrative that mentions the metric elsewhere, a summary that says "verified" — has been used here to record a failed assertion as met, without anyone intending to.

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
(10) ANSWER (c) IN WRITING: quote the item's (c) sentence, then give the
     number beside its target -- "target < 95%, measured 97.7%, NOT MET".
     Then answer every `> Verify:` step, including any you skipped.
(11) COMMIT: one item, the WHY in the body, with the numbers you measured,
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

## 10. Already delivered — do NOT rework

**Each line names the commit that carries the full specification, the implementation and the falsification.** `git show <hash>` when you need the reasoning; this file keeps only what is still to be done. That is the same rule §4 states for `ongoing_errors.md`, applied here — it was not, which is why this guide reached 2,283 lines.

**Verified by re-running gates bare, querying the live database, and reading output by hand — not by trusting the commit messages.**

### The extraction chain

- **X0** `5f881ea` — fabricated tension quarantined; segmentation moved to sentence/pause boundaries. Verified: 9 survivors read individually, quotes verbatim.
- **X1** `e07aff5` — entailment validator (Issue 025 = C) as validator 6, three outcomes, ambiguous band quarantines. Parameter 026 measured.
- **W1** `2794829` — re-pointing a claim re-runs entailment; `verify_entailment_holds` added as the integrity-pass twin; `t_dedup` unified behind one constant.
- **W0** `ae32f93` · **W2** `a9b344c` — propositions must be self-contained. Named indexical patterns then unbound pronouns and deictics; **0** remain. W2 correctly kept bound pronouns, against an over-strict assertion I had written.
- **S1** `b902797` — validator 7 (stance direction) and I7 speech-act sensitivity; exclusion rate 0.7% → 8.2%.
- **D3** `6563d1a` — validator 7 made bidirectional; `hedge` retired to `hedging_level`, enum and data both.
- **D4** `783ab28` — **scope-aware negation. Drawn evaluation set of 80, recorded seed, labels assigned before the run, red-first baseline: false-flip rate 100% → 0% on negation claims.** The strongest single piece of work in this log.
- **D1** `95c586d` — canonical noun-phrase form and extended polarity validation. Polarity violations 393 → **0**; full clauses 75.2% → 21.3%. **(c) NOT MET** — singletons rose to 97.7% against a target below 95%. Overshot into topics; see §12.
- **P0** `0cb8481` · **D2** `da82f7e` — proposition dedup wired, then `T_dedup` re-measured to **0.84** over the current distribution with deciles, n and date.
- **D6** `3100a48` — mechanical position floor (`validate_position_bearing`) + prompt v1.7; 495 of 2,161 old propositions rejected (22.9%), ≤5-word share 25.8% → 17.4%, claim loss 2,261 → 1,027 reported and reconciled, Parameter 033 still met on all 23 sources. **(c) NOT MET on an independent draw** — reported 18/20, a fresh seeded sample scores **9/20 strict / 13/20 charitable** against a 16/20 gate. Issue 034.
- **X2** `2c3c5a4` — elicit position with proposition (Issue 034 = B): prompt `v1.8` writes the position frame (`the speaker is FOR/AGAINST ⟨X⟩`), stored directly in `claims.position_frame`; 1,517 claims across 1,464 active propositions; (c) verified on 20/20 random claims drawn with seed 2026; Validator 2b alarm drop 22.2% → 11.1%; dual falsification verified (identity rule + prompt v1.7 reversion).

### Corpus and ingest

- **I0.1/I0.2** `f0eb10d` `974542d` — enrollment, mutual distinguishability, single-speaker pipeline, re-ingest idempotency. **I0.3 superseded by R0/R1.**
- **R0** `eaeec8e` · **R1** `99b3347` — silent-failure bug fixed and audio deletion gated; then `duration_ms` from `<itunes:duration>`, real coverage check, and the 10MB `Range` cap removed. Coverage 7.7% → **99.7–100%**.
- **N0** `0301265` — extraction over the full corpus. **(c) not satisfied** — no candidate report was possible, because dedup had not run.
- **C1** `a2f4ffc` — corpus expanded chronologically (Issue 030 = A), 4 → 23 sources, rule pre-registered before the run.
- **D5** `71e10bb` — audited D1's 41% claim shortfall to arithmetic closure (diff = 0). Cause: `reextract_d1.py` had copy-pasted the wrong source IDs. Parameter 033 `MIN_CLAIMS_PER_HOUR = 3.0`.
- **S0** `—` — `SourceSubjectRole` migration (Issue 022 = A), landed while the corpus was empty.

### Integrity, gates and the rubric

- **F0** `—` — behaviour fixtures repaired; 20/20 across all 17 classes.
- **E0** `b7b5359` — integrity pass split into FIXTURES and CORPUS, no union, real assessments loaded.
- **E1** `6166613` · **E2** `763329d` — assessment referential guards and the missing-key FAIL; then the sufficiency verdict computed from **inputs** rather than from the scores it gates.
- **M0** `49d82e1` — `source_count` resolved through the utterance anchor chain; `hasattr` guard removed; I3 violation raises.
- **G0** `065331b` · **G1** `b558669` — mypy gate repaired; then `scripts/` brought inside the gates, `role_id` unified behind `compute_role_id`, `source_roles` 32 → 16.
- **G2** `6111c21` — `mypy scripts/` red-gate repair; 11 errors fixed in `verify_20_props_step2.py` and `reextract_d6.py`; inline verification path updated to call `run_integrity_corpus(db_path)` and verified executing live; falsification verified.
- **D0** `399e775` — proposition table repaired in place (Issue 027 = A): canonical IDs normalised, forked rows merged, embeddings backfilled, fabrication quarantined.
- **Q0** `46eecea` — both published tensions quarantined as fabrications. **Quarantine rate is 3 of 3 tensions ever generated.**
- **T1** `226abe4` — same-source pairs disqualified from reversal and routed to `stance_conflict_reviews`.
- **D7** `1866d7a` — every accepted candidate now writes a tension row; quarantine rate reported as a first-class metric derivable from the table. **It also published 6 tensions, all of them fabrications**, because the six accepted candidates were already known to be false when it ran. D6's re-extraction later removed them; the store now holds 3 rows, 0 published.

- **G2** `6111c21` — `mypy scripts/` red gate repaired; `reextract_d6.py`'s four dead integrity calls given real arguments and shown to execute.
- **X2** `2c3c5a4` — **Issue 034 = B: the position elicited with the proposition.** `position_frame` stored on all 1,517 claims (0 unparseable, 0 stance disagreements, 96.3% ⟨X⟩ identity), prompt v1.8, validator 2b fire rate 22.9% → 11.1%. **The corpus grew for the first time in the sequence, 1,027 → 1,517.** It also published one false tension whose frames disagree — §11.
- **X3** — **Frame-⟨X⟩ identity mechanical precondition in `TensionDetector` and Check #16 `verify_frame_identity` in integrity pass.** Pre-repair false tension `12a7503f8c27b24d` quarantined with `quarantine_reason='frame_mismatch'`; affected David Sacks assessment recomputed; quarantine rate 100.0% (5/5 ever generated); dual falsification verified (synthetic identical ⟨X⟩ frames publish; real growth pair quarantined; disabling guard breaks Assertion (c)).

### Clients and portability

- **C0** `e2979ac` — `mlx-lm` optional; `portability.yml` tests the base install off-Mac (Issue 024 = B).
- **U1** `867a89f` · **A0** `342d7ca` — review site served live from DuckDB, four routes, no build step (Issues 028 + 033); then the read-only fallback deleted so `create_app` raises rather than silently handing the site a writable cursor. **Verified by sweeping all 1,288 claim routes: zero quarantined ids reachable.**
- **P7** `2717857` · **P8** `—` — local API (loopback, Bearer, strict CORS, `/resolve`) and the Manifest V3 extension.
- **V0–V6** · **U0–U13** — all externals real, `STUB_REGISTRY` empty; storage, adapters, reconciler, segmentation, gate, validators.

### Delivered as code, still unvalidated as behaviour

**P4** `365896e` tension detection · **P3** `4c24312` topic model · **P5** `b3db6ce` principle extraction · **P6** `0a6b4b6` rubric engine.

They pass their fixture tests and have **never produced a true finding over the live corpus.** Every zero they have reported has had a cause upstream of them — an empty corpus, then an unrepresentable one, then propositions that could not carry a position. **Do not read their green status as evidence the detectors work.** §11 is what makes the question answerable.

### Accepted equivalents — do NOT "fix" these back

The `TranscriptionEngine` Protocol plus its `Mock` test-double split · `LocalGemmaRuntime`'s shape · `verify_source_productivity` reporting coverage as a percentage rather than a ratio. All three are better than the spec implied.

---

## 11. X3 — A tension may only publish when both frames name the same ⟨X⟩ (DELIVERED · VERIFIED)

**User impact:** the check that has been made by judgement four times, and got it wrong four times, becomes a line of SQL.

**Contract:** `design_claim_extraction.md` §2 (*"the few-shot examples must show the same ⟨X⟩ under both frames"*) · `design_data_layer.md` §4 (the proposition self-join) · `design_evidence_integrity.md` §4–§5 (quarantine first).

**Gap.** X2 published one tension. **It is false, and its own stored frames say so in two lines:**

```
  A  support  the speaker is FOR      60 to 80 percent growth year over year
              "And now if it's going from 60 to 80 percent growth year over year, you're happy."
  B  oppose   the speaker is AGAINST  10x year over year growth for ever
              "It's not physically possible to grow 10x year over year for ever."
```

**⟨X⟩ differs.** *60–80% growth* and *10x growth forever* are different matters, and Sacks's two statements are perfectly compatible — being pleased with 60–80% growth and holding that 10x forever is impossible are not a reversal. Dedup merged the two propositions at `T_dedup = 0.84` and the detector joined on the merged id.

**X2's own step-6 check named this exact case:** *"If the two frames are not about the same ⟨X⟩, that is a step-2 failure and the pair is evidence against the prompt, not a finding."* The pair was published anyway. **This is the fourth fabrication this system has published.**

**But something changed, and it is the reason this item is small.** The previous three required reading quotes and reasoning about aboutness. This one is visible in a two-line diff of a stored column — **X2's `position_frame` did exactly what it was added to do.** The judgement is now an artefact, and an artefact can be checked in code.

**The prompt is not at fault here.** Both frames are well-formed, both name a real matter, both match their quote. **The defect is in dedup**, which is D8's subject — X3 stops the bad pair reaching a reader, D8 stops it being created.

### Implementation

**Step 1 — Quarantine `12a7503f8c27b24d` first.** `status='quarantined'`, `quarantine_reason='frame_mismatch'`. Recompute the affected assessment without it. **Do not fix the merge here** — `design_evidence_integrity.md` §5 is quarantine first, investigate second, and this row is the evidence X3 and D8 are measured against.

> **Verify:** zero published tensions remain. The quarantine rate is now **4 of 5** ever generated; report it, do not bury it.

**Step 2 — Add the guard to the detector, before the six preconditions.** For a candidate pair, parse ⟨X⟩ out of each claim's `position_frame` and require them to match under the same normalisation `compute_proposition_id` uses (`worker/storage.py` — lowercase, collapse whitespace, strip terminal punctuation). Mismatch → **quarantine** with reason `frame_mismatch`, never drop (D7 established that; §10).

> **Verify (red-first):** run the guard over today's corpus **before** wiring it in, and confirm it flags `12a7503f8c27b24d`. **If it does not fire on that pair, the parse or the normalisation is wrong** — that pair is the one known positive and it must be reproducible.

**Step 3 — Decide how strict the match is, and say why.** Exact-after-normalisation is the safe default and will also reject near-identical pairs such as *"30 years at 5% interest rate"* vs *"a 30-year at 5.2 interest rate"* — which **should** be rejected, since 5% and 5.2% are different claims.

> **Verify:** report how many of the store's existing support/oppose proposition groups survive the guard. **Today four of five have mismatched frames** — the only clean one is *"companies moving out of California"*, where both frames are byte-identical. If your guard passes more than one or two, it is too loose; if it passes none, check it against that pair specifically.

**Step 4 — Add `verify_frame_identity` to the integrity pass.** No published tension may have mismatched frames. This is the standing version of step 2.

> **Verify:** it FAILS on the corpus as it stands today (before step 1), naming `12a7503f8c27b24d`. Run it in that order — a check first seen green on repaired data has not been tested.

### Validation

- **(c)** — **no published tension exists whose two claims' frames name different ⟨X⟩**, asserted by a query over the live store that parses both frames and compares them normalised; **and the guard, run against today's pre-repair corpus, flags exactly `12a7503f8c27b24d`.** *Both halves are needed: the first alone is satisfiable by publishing nothing, which is today's state and proves nothing.*
- **Both directions:** a synthetic pair with byte-identical ⟨X⟩ and opposing FOR/AGAINST passes the guard and reaches the six preconditions; the growth pair does not.
- Every rejected candidate writes a `quarantined` row with `frame_mismatch` — none is dropped (§10, D7).
- `worker.integrity --all` green on both populations, with the quarantine rate reported.

**Falsify.** Remove the guard and re-run detection; `12a7503f8c27b24d` must return as published and (c) must go red. Revert; record both.

**Blast radius.** `worker/tension/detect.py`, `worker/integrity.py`, `worker/storage.py`, `tests/`, the corpus (one row quarantined), `docs/design_evidence_integrity.md` §4, `docs/design_data_layer.md` §4, §3, §6.

---

## 12. D8 — Re-measure `T_dedup` against the v1.8 distribution

**Blocked on X3** — X3 stops the bad pair reaching a reader; this stops it being created. Do them in that order so the guard exists while you are changing what dedup emits.

**Contract:** `ongoing_errors.md` §2 parameter 008 · `design_claim_extraction.md` §2 (Deduplication) · trap 57.

**Gap — this is the deferred half of X2, now due.** X2 step 5 said explicitly: *"Do not retune `t_dedup` in this commit; D2 measured 0.84 against a distribution this step replaces, and changing form and threshold together makes neither attributable. Re-measuring it is a separate item, filed after this one lands."* That was right, and it has landed.

**0.84 is now merging different matters.** The published fabrication is the proof: *"60 to 80 percent growth year over year"* and *"10x year over year growth for ever"* were merged into one proposition. So were *"the FDA's involvement in drug approval process"* and *"the approval process for drugs that influence the body"*, and *"China's push on open source"* and *"the open source model being published by China"*. **Four of the store's five support/oppose proposition groups are dedup artefacts rather than genuine shared matters.**

**The corpus it was measured on no longer exists.** D2 measured 0.84 over 2,191 propositions from prompt v1.7. The store now holds **1,465 propositions from v1.8**, and — for the first time in this sequence — the corpus **grew**: 1,027 → **1,517 claims**. Different text, different length distribution, different similarity structure.

**Read this before choosing a number.** Parameter 008's bias is *toward merging*, because over-splitting hides contradictions silently while over-merging produces visible, fixable false positives. **That bias was written before the frames existed and it should now be re-read, not reapplied.** With `position_frame` stored and X3's guard in place, an over-merge is caught mechanically at publish time — which makes over-merging much cheaper than it was, and the bias arguably *more* correct than before. Say which way you read it and why.

### Implementation

**Step 1 — Measure before choosing.** Embed all 1,465 propositions, compute the 1-NN similarity distribution, and report the deciles.

> **Verify:** paste the deciles. **If the distribution is unimodal there is no threshold to find**, and the honest delivery is to say so and report that similarity over proposition text cannot separate restatement from difference at this size — a legitimate result, not a failure.

**Step 2 — Use the frames as ground truth, which is new.** For every currently-merged proposition carrying more than one claim, the stored frames say whether the merge was right. **This is a labelled set you did not have to build.**

> **Verify:** report, at the candidate threshold, how many existing merges the frames endorse and how many they contradict. **The four named above must be contradicted.** This is the first time this parameter can be measured against something other than a judgement — use it.

**Step 3 — Choose, record with n and date, supersede 0.84 explicitly.**

> **Verify:** `ongoing_errors.md` §2's row names the corpus — claim count, proposition count, prompt version, date — so the next reader can tell when it has expired. That is what 0.86 lacked, and it outlived two corpora.

**Step 4 — Re-resolve propositions and re-run detection.**

> **Verify:** report the candidate denominator — examined, accepted, rejected, with reasons — and **paste both frames for every accepted pair.** With X3 in place a frame mismatch cannot publish, but it can still be created, and its rate is how you tell whether the new threshold is right.

### Validation

- **(c)** — **at the chosen threshold, every proposition carrying both a `support` and an `oppose` claim has frames whose ⟨X⟩ match after normalisation.** Today that is **1 of 5**. *This is measurable from the store with no judgement, which is the whole reason `position_frame` exists — and it cannot be satisfied by merging nothing, because the count of such propositions must also be reported and a zero says the self-join has nothing to match.*
- Both directions at the chosen threshold: two genuine restatements of one matter merge; the growth pair and the FDA pair do not.
- Merge histogram and singleton rate reported before and after.
- `verify_frame_identity` (X3) PASSes; `verify_quotes`, `verify_canonical_ids`, `verify_entailment_holds`, `verify_claims_per_hour` PASS.

**Falsify.** Set `t_dedup = 0.999` and confirm the histogram collapses to singletons; set it to 0.60 and confirm the frame-contradicted merge count climbs sharply. Record all three, with the frame-contradiction count at each — that number, not the histogram, is the one that now decides this parameter.

**Blast radius.** `worker/extract/dedup.py`, the corpus (proposition re-resolution), `docs/ongoing_errors.md` §2, `docs/design_claim_extraction.md` §2, §3, §6.

---
## 13. Deferred — designed for, not queued

**Elon Musk (Issue 023 = A).** Out of scope until X/Twitter ingest exists. **Trigger:** an `XAPIAdapter` or `XArchiveImportAdapter` lands behind the `SourceAdapter` Protocol and a Musk corpus can be assembled that includes his primary medium. Until then, ingesting him would produce a confident score over a systematically skewed slice, and **invariant I5 would not catch it** — it gates on volume, not composition (trap 24).

**Corpus-composition reporting.** Issue 023's Option B was not selected, so `corpus_composition` is not being built now. It remains the right long-term answer to trap 24 and applies to every subject, not just Musk. Revisit when X ingest arrives or when any subject's corpus draws from a single medium.

**X/Twitter ingest.** Deferred by decision, not difficulty (`master_implementation_plan.md` §9). The adapter Protocol must keep accepting it as a drop-in.

**Proposition-table purge (Issue 027 Option B, not selected).** A was selected, which keeps the orphaned pre-X0 propositions and their embeddings. The remaining cleanup — deleting the five non-fabricated orphans, pruning `proposition_embeddings` to the readable set, and replacing `claim_count` with a computed view — is right eventually and wrong now, because R1's re-ingest repopulates the table. **Trigger:** R1 has landed and the corpus is final. Doing it before then pays for the same migration twice.

---

## 14. Invariants — do NOT change

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

Full text: `master_implementation_plan.md` §3. Code violating one is wrong even if its tests pass.

---

## 15. Contracts

`master_implementation_plan.md` · `design_source_acquisition.md` · `design_claim_extraction.md` · `design_principle_extraction.md` · `design_topic_model.md` · `design_rubric_engine.md` · `design_data_layer.md` · `design_local_api_and_clients.md` · `design_ui_direction.md` · `design_evidence_integrity.md` · `e2e_verification_journeys.md` · `ongoing_errors.md`

---

## 16. Feedback loop — what specs here have got wrong

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

| **(c) failed, and the commit recorded it verified** | "**(c)** — the singleton rate falls materially below 95%, and propositions spanning 2+ episodes rises well above 1.8% of the table." | The assertion was fine. **What was missing was an instruction to state (c)'s outcome as a number in the commit body, next to the target.** D1 reported the singleton rate honestly in its Step 6 narrative and separately wrote "Assertion (c) verified" about a different test. **Require the item's (c) to be quoted and answered numerically, so agreement is checkable rather than asserted.** |

| **Six false pairs recorded as hand-read and verified** | "Read every candidate pair the detector would publish, by hand." | **"...and for each, write the sentence 'A takes position X on P, B takes position Y' before judging."** The reading was done. What was missing was the artefact that makes a wrong reading visible — for four of the six pairs that sentence cannot be written at all, and that is the tell. |

| **Six fabrications published by an item that followed its spec exactly** | "Make every accepted candidate produce a row. Published if it clears all six preconditions; quarantined otherwise." | **"...and read the current accepted set before running it; if those candidates are known-false, this item quarantines rather than publishes."** I wrote D7 knowing all six accepted candidates were false and sequenced it first anyway, because it was small. **Small is not the same as safe when the item's effect is to publish.** |

| **A false tension published with well-formed frames** | "For every accepted candidate pair the two frames are stored — paste both, then say whether they conflict. If they are not about the same ⟨X⟩, the pair is evidence against the prompt, not a finding." | The instruction was right and was not applied. **Make it a precondition in the detector rather than a step in the commit body** — anything that depends on the agent noticing will eventually meet an agent who does not. §11 does this. |

**The newest pattern: a correct fix to the wrong scope reads exactly like success.** And the encouraging counterpart, first seen this pass: **a fix that converts a judgement into a stored artefact makes the next failure cheap to find.** X2 published a fabrication and simultaneously made that class of fabrication mechanically detectable. And its companion, first seen this pass: **a fix can overshoot into the mirror of the defect it removed**, while every metric the item defined still improves. D1 is its cleanest instance yet — genuinely good work, honestly reported in prose, with the headline label wrong. And the sharpest version this project has produced: **Issue 030 was the right decision against the wrong diagnosis.** The corpus did need expanding and expanding it was done well; it simply was not what stood between the pipeline and a finding. **Before committing hours of compute to a diagnosis, check that the cheap query agrees with it.** R1's gates were green, its coverage real, its numbers honest, and the thing it existed to enable did not happen. N0 then repeated it one layer down. **Check what the item was *for*, not only what it said** — and when an item's purpose is to feed a downstream stage, make one of its assertions a property of *that stage's input*, not of its own output.
