# Agent Execution Guide — Active Build: V-queue · all selections in · zero blockers — August 17, 2026

**You are an engineering agent with no memory of this project. This document is designed to be self-driving: it contains the prompts you issue to yourself.**

Do not read this top to bottom and then improvise. **Go to §1, run LOOP 0, and let it route you.**

---

## 1. LOOP 0 — ORIENT (run once, at the start of every session)

Issue this to yourself verbatim:

```text
LOOP 0 — ORIENT

1. Run the state-detection block in §2 and read its output.
2. Compare the gate results to the baseline table in §3.
   - Any gate RED that §3 records as PASS  → STOP. Report the regression. Do not start new work.
   - All gates match §3                    → continue.
3. Read the queue table in §6. Walk it top to bottom and select the FIRST item where:
       status != delivered   AND   blocked_on == none
4. If no such item exists → go to §19 (LOOP 4 — CLOSE OUT). Stop here.
5. Otherwise set ITEM = that identifier (e.g. "V2").
6. Read the item's own section in full (§10–§16). Read every contract doc it cites.
   Reading the guide alone is not sufficient; the guide points, the doc specifies.
7. Enter LOOP 1 (§7) with ITEM.
```

---

## 2. State detection

One block. Run it before anything else; it answers "where am I" without trusting any prose.

```bash
cd "$(git rev-parse --show-toplevel)"
echo "=== HEAD ==="        && git log --oneline -1
echo "=== CLEAN? ==="      && git status --porcelain | head
echo "=== GATES ==="
.venv/bin/python -m ruff check worker/ tests/ fixtures/ golden/ 2>&1 | tail -2
.venv/bin/python -m mypy  worker/ tests/ fixtures/ golden/       2>&1 | tail -2
.venv/bin/python -m pytest tests/ -q                             2>&1 | tail -3
echo "=== STUB REGISTRY (source of truth for V2-V5 progress) ==="
.venv/bin/python -c "from worker import STUB_REGISTRY; [print(f'{k}: {v}') for k,v in STUB_REGISTRY.items()]" \
  2>/dev/null || echo "  STUB_REGISTRY not present yet -> V1 is not delivered"
echo "=== DECLARED EXTERNALS ==="
grep -E "faster-whisper|pyannote|llama-cpp|sentence-transformers|mlx" pyproject.toml || echo "  none declared"
echo "=== CORPUS SPLIT (V6 delivered?) ==="
[ -d fixtures/behaviour ] && echo "  fixtures/behaviour present -> V6 delivered" || echo "  no fixtures/behaviour -> V6 NOT delivered"
echo "=== OPEN SELECTIONS ==="
grep -c "^Your selection: _____" docs/ongoing_errors.md   # anchored: an unanchored grep also matches the rules line that documents the convention
```

**Interpreting it:**

| Signal | Means |
|---|---|
| `STUB_REGISTRY not present` | V1 not delivered. Everything after it is unverifiable. |
| A module still listed in `STUB_REGISTRY` | Its V-item is **not** delivered, whatever any commit message says. |
| `none declared` under externals | No real model is wired. V2–V5 all outstanding. |
| pytest finishes in under ~5s | Still mocks all the way down. A real model cannot run that fast. |
| open selections > 0 | A new blocker appeared. Check §6 before starting anything. |

**The stub registry is the authority on V2–V5 progress.** Not the baseline table, not commit messages, not this guide's prose.

---

## 3. Verified baseline

Measured on August 17, 2026. Re-run via §2 before trusting.

| Gate | Result | What it does **not** prove |
|---|---|---|
| `ruff check` | **PASS** | Nothing about behaviour |
| `mypy --strict` | **PASS** — 44 files | Nothing about behaviour |
| `pytest tests/ -q` | **PASS** — 63 passed, ~1.5s | **~1.5s means no model, no audio, no network.** Unit tests over mocks. |
| `worker.integrity --all` | **PASS** — 8 checks | Real logic, synthetic data |
| `worker.extract.smoke` | **PASS** — gated on backend | Correctly prints `NOT MEASURED` while no model backend is loaded. |
| `worker.golden.report` | **RUNS — vacuous metrics** | 16 cases, one per class. `1.000` is arithmetic. Fixed by V6. |

**Do not weaken or delete existing tests.** They are correct for the layer they cover; the layer beneath them is what's missing.

---

## 4. Standing constraints

- **One item = one commit**, the *why* in the body.
- **Never fill in a `Your selection: _____` line.**
- **A stub is not a delivery.** An integration item is done when the real dependency runs. A `Mock*` class satisfying an interface is a test double.
- **If an item needs a package, it lands in `pyproject.toml` in the same commit.** An undeclared dependency is the signature of a stub.
- **Never print a number you did not compute from a live run.** Constants, projections from constants, and metrics below their sample floor render as `NOT MEASURED`.
- **Every integration item needs at least one assertion a stub cannot satisfy** (trap 17). This is the single most important rule in this document.
- **A guard that has never failed has not been tested.** LOOP 2 is mandatory, not optional.
- **All writes go through the worker** (I8). **No LLM at scoring time.** **Audio is deleted after transcription** (Issue 003).
- **DuckDB is the only store** (Issue 015). No Firestore, no sync, no `synced_at`.
- **Update every doc your change invalidates, in the same commit.** That is what blast radius means.

---

## 5. Traps

Traps 1–16 are in git history at `217b383:docs/agent_execution_guide.md` §1 — **read them before writing code in their layer.** The four that caused the last failure:

17. **An assertion about *shape* is satisfiable by a stub.** "Assert prefill ≈ utterance length" was met by arithmetic over `words × 2` with no model loaded. Every integration item needs an assertion that cannot pass without the real dependency.
18. **A suite that finishes in 1.5 seconds is telling you something.** Real models are slow.
19. **A mock named honestly is safe; a mock named plausibly is not.** `MockTranscriptionEngine` announces itself; `compute_deterministic_text_embedding` read like a design choice and silently broke the semantic layer. Name stubs `Mock*` or `Stub*`, always.
20. **A metric over one example per class is not a metric.** Guard the harness so it cannot emit one.

---

## 6. Queue

**Issue 017 = Option A: wire every real external now, before any new phase.** V0 and V1 come first anyway — they are cheap, and V1 is what makes V2–V5 impossible to fake.

| Order | ID | Item | Blocked on | Status | Position rationale |
|---|---|---|---|---|---|
| 1 | **V0** | Stop reporting fabricated throughput | none | **delivered** | The runtime prints a hardcoded constant as a measurement. Fix the instrument before taking any reading. |
| 2 | **V1** | Stub registry + CI guard | none | **delivered** | The structural fix. Its registry becomes the V2–V5 checklist: each later item flips one entry from `stubbed` to `declared`, so the queue verifies itself. |
| 3 | **V6** | Split behaviour fixtures from the golden corpus | none | open | **Moved ahead of V2–V5 by the Issue 018 selection.** Every measurement V2–V5 report flows through this harness; splitting afterwards means re-doing their numbers. Also carries the metric floor, since that is the same file and the same concern. |
| 4 | **V2** | Real embeddings — `nomic-embed-text-v1.5` | none | open | First real external: cheapest to wire, and the only stub that is *silently wrong* rather than merely absent. |
| 5 | **V3** | Real transcription — `faster-whisper` | none | open | Behind the existing `TranscriptionEngine` Protocol. First item that produces real corpus material. |
| 6 | **V4** | Real diarization — `pyannote.audio` | none | open | **Needs a gated Hugging Face token — raise it with the user via LOOP 3 before writing code.** |
| 7 | **V5** | Real extraction runtime — Gemma 3 | none | open | Largest download, slowest loop, most to measure. |

> **IDs are labels, not sequence numbers.** `V6` runs third. Do not renumber to "tidy" this — commit messages and `ongoing_errors.md` reference these IDs, and renaming them breaks every inbound pointer. Follow the **Order** column.

**No queued item is blocked.** Issue 019 is open but gates only the *population* of the golden corpus, not V6's structural work — see §16's scope boundary. `grep -c "^Your selection: _____"` returns 1.

**Already resolved, do not re-open:** Firestore purge (Issue 015 = A) — no Firestore code was ever written; docs cleaned in `1dee614`. Selection-triggered overlay (Issue 013) — designed in `design_local_api_and_clients.md` §4 and `design_ui_direction.md` §6; **do not start building it until the V-queue is empty** (Issue 017 = A).

---

## 7. LOOP 1 — IMPLEMENT (per item)

Issue this to yourself, substituting `ITEM`:

```text
LOOP 1 — IMPLEMENT <ITEM>

STEP 1 — LOAD
  Read this guide's section for <ITEM>. Read every contract doc it cites, in full.
  Write down, before coding:
    a. the one-line user impact
    b. the exact files you expect to touch (the blast radius)
    c. the ONE assertion in this item that a stub cannot satisfy
  If you cannot name (c), STOP and enter LOOP 3 — the item is underspecified.

STEP 2 — DECLARE
  If this item integrates an external package:
    - add it to pyproject.toml NOW, in this commit
    - install it into .venv
    - if it needs a credential or a gated download, STOP and enter LOOP 3
      before writing code. Do not stub around a missing credential.

STEP 3 — BUILD
  Implement exactly as specified. Numbers, field names and literal strings are
  decisions, not suggestions. If a specified value is impossible, keep the intent,
  deviate minimally, and record the deviation in the commit body.

STEP 4 — VALIDATE
  Write every assertion listed under the item's Validation heading.
  Run them. All must pass, including (c) from STEP 1.

STEP 5 — FALSIFY
  Enter LOOP 2 (§8). Do not skip it. Do not proceed until it completes.

STEP 6 — BATTERY
  Run §2's state-detection block. All gates must be green.
  Record the REAL numbers. Any number you did not measure is "NOT MEASURED".

STEP 7 — PROPAGATE
  Update every doc invalidated by this change, in this same commit:
    - this guide's §3 baseline
    - this guide's §6 queue row -> status delivered
    - the STUB_REGISTRY entry, if this item replaced a stub
    - any design_*.md whose described behaviour changed
    - ongoing_errors.md §4 if a selection was consumed

STEP 8 — COMMIT
  One item, one commit. Body must contain:
    - why this change, in prose
    - the falsification: what you broke, that it went RED, that you reverted, that it went GREEN
    - any deviation from spec, with the reason
    - the measured numbers

STEP 9 — LOOP
  Return to LOOP 0 (§1). Do not select the next item by memory; re-detect state.
```

---

## 8. LOOP 2 — FALSIFY (nested inside LOOP 1 STEP 5)

A guard that has never failed has not been tested. This loop is how you find out whether the test you just wrote is load-bearing or decorative.

```text
LOOP 2 — FALSIFY <ITEM>

1. Identify the single assertion that most matters — normally (c) from LOOP 1 STEP 1.
2. Break the thing it protects. Not the assertion: the CODE UNDER IT.
     - deleting the assertion proves nothing
     - deleting the behaviour it guards proves everything
3. Run the test. It MUST go RED.
     - if it stays GREEN -> the assertion is decorative. Rewrite it and restart LOOP 2.
       This is a finding, not a nuisance: you just discovered a test that cannot fail.
4. Revert the break. Run again. It MUST go GREEN.
5. Record BOTH outcomes verbatim in the commit body:
     "Falsification: <what was broken> -> <assertion> FAILED as expected.
      Reverted -> PASSED. Both outcomes observed."
6. Return to LOOP 1 STEP 6.
```

---

## 9. LOOP 3 — ESCALATE (when blocked)

```text
LOOP 3 — ESCALATE

Trigger this when ANY of:
  - a specified value is impossible and the intent cannot be preserved
  - the design as written cannot work
  - the item needs a credential, gated download, or human judgement
  - you cannot name an assertion a stub could not satisfy
  - a selection you need is still "Your selection: _____"

Do:
  1. STOP. Write no more code on this item.
  2. Open docs/ongoing_errors.md section 1.
  3. Append a new numbered issue (next free number) containing:
       - what is blocked, concretely, and what you already tried
       - 2-3 options, each with honest pros AND cons
       - a recommendation, marked as such
       - a final line, exactly: "Your selection: _____"
  4. NEVER fill in that line.
  5. Update this guide's section 6: set blocked_on for the affected items.
  6. Return to LOOP 0. If nothing else is unblocked, go to LOOP 4.
```

---

## 10. V0 — Stop reporting fabricated throughput

**User impact:** the project stops claiming performance it has never measured, so the next status report can be trusted.

**Gap.** `worker/extract/runtime.py` contains `tokens_per_second=35.0,  # Steady-state Apple Silicon M-series throughput` — a literal. `worker/extract/smoke.py` prints it as a measurement and derives a "5.14h 300hr projection" from it. No model backend exists.

> **Scope note:** the golden-report metric floor used to live here. It moved to **V6**, because it is the same file and the same concern as the fixture/corpus split and doing it twice is waste.

**Implementation**
1. **Delete the `35.0` literal.** `GenerationStats.tokens_per_second` becomes `float | None`, populated only from a real timing — `time.perf_counter()` around an actual generation call — and `None` otherwise.
2. **Gate every performance figure on a live capability probe**, not a config flag someone can flip: does a model backend exist and return a completion? While it does not, `smoke.py` prints exactly:
   ```
   Inference Throughput:            NOT MEASURED — no model backend loaded
   Projected 300hr Ingest Time:     NOT MEASURED — requires measured throughput
   ```
3. Any derived figure inherits its weakest input: a projection built on `NOT MEASURED` is itself `NOT MEASURED`, never a number.
4. Keep `prefill_tokens` reporting, but label it `approx (word-count heuristic)` until V5 replaces it with the runtime's own counter. **An approximation that says so is fine; one that doesn't is the bug.**

**Validation**
- Run `worker.extract.smoke`; assert **no numeric throughput and no numeric projection appears in stdout** while no backend is loaded.
- Assert `GenerationStats.tokens_per_second is None` on every call from the stub path.
- `grep -rn "35\.0" worker/` returns nothing.
- ← *the assertion that matters is inverted here: it must go RED the moment a fabricated number returns.*

**Falsify.** Re-introduce a fake `backend_present = True` so `smoke.py` prints `35.0`. The stdout assertion must go RED. Revert; record both.

**Blast radius.** `worker/extract/runtime.py`, `worker/extract/smoke.py`, `tests/test_runtime_u9.py`, this guide's §3.

---

## 11. V1 — Stub registry and CI guard

**User impact:** a future agent cannot report a simulated model as a working one, because CI catches it.

**Gap.** Four modules claim to wrap external models; none imports one; none is declared. Nothing detects this.

**Implementation**
1. `worker/__init__.py` gains:
   ```python
   STUB_REGISTRY: dict[str, str] = {
       "worker.transcribe.engine":   "MockTranscriptionEngine — real engine pending V3",
       "worker.diarize.attribution": "synthetic vectors — pyannote pending V4",
       "worker.extract.runtime":     "no backend — Gemma pending V5",
       "worker.extract.dedup":       "stub_hash_embedding — nomic pending V2",
   }
   ```
2. `tests/test_no_undeclared_stubs.py` holds the contract:
   ```python
   EXTERNAL_CONTRACTS = {
       "worker.transcribe.engine":   ("faster_whisper",        "TranscriptionEngine"),
       "worker.diarize.attribution": ("pyannote.audio",        "Diarizer"),
       "worker.extract.runtime":     ("llama_cpp",             "LocalGemmaRuntime"),
       "worker.extract.dedup":       ("sentence_transformers", "Embedder"),
   }
   ```
   For each entry assert **exactly one** of two states, failing on anything else:
   - **declared** — the package is in `pyproject.toml`, importable, **and** the module imports it;
   - **stubbed** — the concrete class name starts with `Mock`/`Stub` **and** the module is listed in `STUB_REGISTRY` with a reason.
3. **Rename `compute_deterministic_text_embedding` → `stub_hash_embedding`** and give it a module docstring stating plainly: no semantic capability, dedup merges only near-identical strings, `T_dedup = 0.88` is meaningless until V2. Trap 19 applied to the one stub that read as a design choice.
4. Print `STUB_REGISTRY` at the top of every pytest run so it cannot be forgotten.

**Validation**
- Guard passes today with all four registered as stubs.
- Delete one `EXTERNAL_CONTRACTS` entry → guard **FAILS**. ← *the load-bearing assertion: a guard that shrinks its own coverage must not go quiet*
- Rename a `Mock*` class to something plausible → guard **FAILS**.
- `grep -rn "compute_deterministic_text_embedding" worker tests` returns nothing.

**Falsify.** Remove the `dedup` entry; confirm CI goes RED rather than silently covering less.

**Blast radius.** `worker/__init__.py`, `worker/extract/dedup.py` + every caller, `tests/`, `.github/workflows/ci.yml`, `conftest.py`.

---

## 12. V2 — Real embeddings

**User impact:** the system can finally tell that "licensing" and "permitting" are the same idea — without which no contradiction across differently-worded claims is ever detected.

**Gap.** `stub_hash_embedding` hashes each word to one dimension. Synonyms score ≈ 0. Per `design_claim_extraction.md` §2 this makes contradictions undetectable system-wide, and the tests cannot see it because plausible vectors come out either way.

**Implementation**
1. Declare `sentence-transformers` in `pyproject.toml`. Model: **`nomic-ai/nomic-embed-text-v1.5`**, 768 dims — matching the fixed DuckDB width (`design_data_layer.md` §4).
2. Implement `Embedder` in `worker/extract/dedup.py` alongside the stub. Load once into a long-lived object; never per call.
3. **Task prefixes are mandatory (trap 7).** Propositions and principles embed as `search_document: <text>`; query-side lookups as `search_query: <text>`. Getting this wrong does not error — it silently degrades everything.
4. Keep `stub_hash_embedding` as a test double, renamed and registered.
5. Flip the `dedup` entry in `STUB_REGISTRY` to declared.
6. **Re-measure parameter 008 (`T_dedup`).** The current `0.88` was tuned against a hash function and carries no information. The golden corpus will still be empty at this point (Issue 018 = B grows it during ingest), so set `T_dedup` from the synonym/antonym pairs in V2's own validation, mark it **`[provisional]`**, and confirm V6's readiness report shows `008 NOT MEASURABLE`. Firm it up when the corpus crosses 5 dedup pairs.

**Validation**
- **Synonym test:** `"federal licensing of frontier models"` vs `"federal permitting for large training runs"` score **above** `T_dedup`. **No hash function can pass this.** ← *the stub-proof assertion*
- **Antonym-of-topic test:** two unrelated propositions score **below** `T_dedup`.
- **Prefix test:** embedding the same string with `search_document:` and with `search_query:` yields **different** vectors. Fails if prefixes were dropped.
- Assert the loaded model reports 768 dims; a mismatch must raise at startup, not at insert time.
- Assert the model loads once — call twice, assert one load.

**Falsify.** Drop the task prefixes and re-run the synonym test; record the measured similarity delta. This turns trap 7 from folklore into a number.

**Blast radius.** `pyproject.toml`, `worker/extract/dedup.py`, `worker/__init__.py`, `tests/test_dedup_u12.py`, `tests/test_no_undeclared_stubs.py`, `docs/design_topic_model.md` if the threshold moves.

---

## 13. V3 — Real transcription

**User impact:** the corpus starts containing words a person actually said, instead of strings a test supplied.

**Gap.** `MockTranscriptionEngine` returns scripted text. No audio has ever been transcribed; the VAD gate has never seen a waveform.

**Implementation**
1. Declare `faster-whisper`. Model `large-v3`. Implement `WhisperTranscriptionEngine` satisfying the existing `TranscriptionEngine` Protocol — **do not modify the Protocol or the pipeline**; the split is an accepted equivalent and it is good.
2. **Word-level timestamps are mandatory** (`word_timestamps=True`). Under Issue 003 the audio is deleted, so these are the only thing that can place a citation link at the right second.
3. Wire the two real passes: pass 1 `beam_size=5, temperature=0.0`; pass 2 `beam_size=1, temperature=0.2`. The reconciler already exists and is correct — feed it real output.
4. VAD gate before transcription.
5. Audio deletion stays last, and only on success.
6. Commit a **5-second WAV fixture** with known content.

**Validation**
- **Real-audio assertion:** transcribing the fixture returns the expected words, in order. **No mock can pass this without the file.** ← *stub-proof*
- Word timestamps monotonic and within media duration.
- **Silence test on real audio:** a clip with 30 s of leading silence yields zero segments over that span.
- **Re-run the negation falsification against real audio** — the synthetic version proved the reconciler; this proves the pipeline.
- Assert `audio_deleted_at` set on success, and audio **still present** when transcription raises.
- Record real throughput (audio-minutes per wall-minute) into the ingest job.

**Falsify.** Disable the VAD gate; the real-audio silence test must go RED.

**Blast radius.** `pyproject.toml`, `worker/transcribe/engine.py`, `fixtures/`, `tests/test_transcribe.py`, `worker/__init__.py`, this guide's §3.

---

## 14. V4 — Real diarization

**User impact:** when the system says a person said something, it is that person and not the host across the table.

**Gap.** No `pyannote`. Attribution compares synthetic numpy vectors.

> **Before writing any code: `pyannote.audio` requires accepting a licence on Hugging Face and a gated access token.** If you do not have one, enter **LOOP 3** and ask. Do not stub around a missing credential — that is exactly how this project got here.

**Implementation**
1. Declare `pyannote.audio`. Token read from env, never committed.
2. Implement `Diarizer` producing real speaker turns.
3. Enrollment stays a deliberate, recorded act: reference embedding from a source where attribution is certain.
4. Banding unchanged: above `T_high` → `high`; between → `low`, stored, **excluded from scoring**; below `T_low` → discarded.
5. **Never attribute by turn order** (trap 11).
6. **Re-measure parameter 004** against real audio. Bias hard toward precision — a missed utterance costs nothing, a misattributed one is the worst bug in the product.

**Validation**
- **Two-speaker fixture:** a real clip with two speakers, hand-labelled. Assert zero cross-attribution. ← *stub-proof*
- Golden case N9 (host asserts X, guest asserts not-X) → **misattribution rate 0**. A gate, not a target.
- Sub-threshold utterances stored `low` and absent from every score.

**Falsify.** Swap the two enrollment embeddings; misattribution must go non-zero on the real fixture.

**Blast radius.** `pyproject.toml`, `worker/diarize/`, `fixtures/`, `tests/test_diarize_u7.py`, `worker/__init__.py`, `docs/ongoing_errors.md` §2 (record measured 004).

---

## 15. V5 — Real extraction runtime

**User impact:** claims get extracted by an actual model instead of being handed to the code by a test.

**Gap.** No backend, no grammar. `mock_output` lets callers supply the answer.

**Implementation**
1. Declare `llama-cpp-python` (or `mlx-lm`). Model **`gemma-3-27b-it` Q4_K_M**, falling back to `gemma-3-12b-it` if RAM is tight. Record the actual choice in `extraction_version` — it is part of the reproducibility contract.
2. **Long-lived process** holding model and KV prefix. Never spawn per utterance.
3. **Real KV prefix reuse.** System prompt prefilled once; per-subject context strictly after it (trap 6).
4. **Real GBNF grammar** generated from the Pydantic schema via `json_schema_to_grammar.py`. Delete the `raw_json[:-2]` simulation.
5. Greedy: `temperature=0`, fixed seed.
6. Remove the `mock_output` parameter from the production path.
7. Measure real throughput; re-derive the ingest projection from it.

**Validation**
- **Wall-clock floor:** 100 real completions cannot finish in under a threshold a stub would beat. Assert elapsed time exceeds it. ← *stub-proof, and the assertion whose absence caused the original failure*
- **Real prefix reuse:** steady-state prefill token counts come from the runtime's own reporting, not `len(text.split())*2`.
- **1,000 grammar-constrained generations → zero JSON parse failures.**
- **Grammar is real:** assert the grammar object is constructed from the schema and that an ungrammatical token is rejected by the sampler.
- Record measured tokens/sec and the derived projection in the commit body.

**Falsify.** Interpolate the subject name into the system prompt; the prefix-reuse assertion must go RED with a real measurement behind it.

**Blast radius.** `pyproject.toml`, `worker/extract/runtime.py`, `worker/extract/smoke.py`, `tests/test_runtime_u9.py`, `worker/__init__.py`, this guide's §3.

---

## 16. V6 — Split behaviour fixtures from the golden corpus · *runs THIRD*

**Issue 018 = Option B.** This is no longer a blocked labelling job. It is an unblocked structural fix, and it runs before V2–V5 because every number they report flows through this harness.

**User impact:** a precision figure starts meaning something. Right now `1.000` is printed over sixteen invented sentences, and there is no way for a reader to tell.

**Gap.** One body of data serves two incompatible purposes. `golden/cases.json` holds 16 hand-written sentences with fabricated locators, and the harness reports rates over them as if they measured quality.

### The distinction to implement

Read `e2e_verification_journeys.md` §2 in full first. The contract in one line: **a fixture may never contribute to a metric, and a corpus case may never be hand-written.**

| | Behaviour fixtures | Golden corpus |
|---|---|---|
| Path | `fixtures/behaviour/` | `golden/` |
| Locator | synthetic, openly so | real `source_id` + span |
| Output | **PASS / FAIL only** | measured rates |
| Grows by | a case per fixed regression | labelling as subjects ingest |

**Implementation**
1. **Move the 16 cases** to `fixtures/behaviour/cases.json`. Add `"locator_kind": "synthetic"` to every one, and **drop `verified_by: "curator"`** — a fixture has an author, not a verifier, and the field was misleading.
2. **Give `golden/` a real schema**: `case_id`, `class`, `subject_id`, `source_id`, `utterance_id`, `span`, `expected_behaviour`, `verified_by`, `verified_at`, `locator_kind: "real"`, plus two fields that exist because of **Issue 019**:
   - `label_source` — `human` | `model_assisted` | `model_only`
   - `labeller_model` — the model that pre-labelled, or null

   **A schema-level rule, enforced in the loader: `labeller_model` may never equal the extractor under test.** That is the circularity guard, and it belongs in code rather than in a reviewer's memory. The corpus starts **empty**, and an empty corpus is a correct state, not an error.
3. **Split the loaders.** `fixtures/behaviour/loader.py` and `golden/loader.py` are separate modules with separate types. **A single function must not be able to return both** — that is what makes the blend structurally impossible rather than merely discouraged.
4. **Rewrite `worker/golden/report.py` into two reporting blocks that cannot be summed:**
   ```
   BEHAVIOUR FIXTURES (regression only — never a quality measure)
     P1 unacknowledged_reversal ......... PASS
     N3 steelman ........................ PASS
     ...                                  16/16 PASS

   GOLDEN CORPUS METRICS
     Precision .......... NOT MEASURED — n=0, minimum 5
     Recall ............. NOT MEASURED — n=0, minimum 5
     N1–N4 guards ....... NOT MEASURED — n=0, minimum 5
     Misattribution (N9)  NOT MEASURED — n=0, minimum 5
   ```
5. **Enforce the per-class floor of 5.** Below it a class prints `NOT MEASURED — n=<k>, minimum 5`. **Aggregate precision is unprintable while any contributing class is below floor** — an aggregate over vacuous classes is itself vacuous.
6. **Add the parameter readiness report.** This is what converts Option B's "grow it over time" from an intention into a work queue:
   ```
   PARAMETER READINESS
     004 T_high / T_low  NOT MEASURABLE — need 5 N9 cases, have 0
     008 T_dedup         NOT MEASURABLE — need 5 dedup pairs, have 0   [provisional 0.88]
     012 sufficiency     NOT MEASURABLE — need 5 N11 cases, have 0
     016 H_max           NOT MEASURABLE — need 5 hedge-boundary cases, have 0
   ```
   Each line names **exactly what to label next** to unblock that parameter. Any parameter with a value while `NOT MEASURABLE` renders it as `[provisional]`, in the report and in the commit body of whatever set it.

**Validation**
- Fixture block prints **PASS/FAIL and no rate whatsoever**. Assert no `%`, no decimal, no ratio appears in that block. ← *load-bearing: this is the assertion that keeps the two bodies apart*
- Corpus block with an empty corpus prints `NOT MEASURED — n=0`, **not** `0.0` and **not** `1.0`.
- Add 4 synthetic cases to `golden/` → still `NOT MEASURED`. Add a 5th → a number appears.
- Assert `golden/loader.py` **rejects** a case with `locator_kind: "synthetic"`, and the fixture loader rejects `"real"`. Type-level separation, not convention.
- Readiness report names a concrete next action per parameter.
- **Circularity guard:** a case whose `labeller_model` equals the configured extractor is **rejected by the loader**. Assert it raises.
- Metrics are reported **split by `label_source`**, so a run can never blend human-verified and model-only cases into one figure.

**Falsify.** Point `golden/loader.py` at `fixtures/behaviour/cases.json`. The `locator_kind` rejection must go RED — proving the separation is enforced rather than merely documented. Revert; record both.

**Blast radius.** `golden/`, `fixtures/`, `worker/golden/report.py`, `tests/test_golden_harness.py`, `tests/test_phase2_gate_u13.py`, `docs/e2e_verification_journeys.md` §2 and J3, `docs/ongoing_errors.md` §2.

> **Scope boundary.** V6 builds the *structure*: the split, the floor, the readiness report, and the schema fields above. **How the corpus then gets populated is Issue 019 and is not part of V6.** Build the schema so either answer fits; do not build a labelling pipeline until that selection lands.

---

## 17. Delivered — do NOT rework

Verified in source on August 17, not from commit messages.

- **U0 integrity pass** — all eight checks present under their specified names; `verify_quotes` genuinely bounds-checks against `text_verbatim`; empty input returns `NOT APPLICABLE`, not a fake `PASS`.
- **U1 DuckDB** — real `vss`, `FLOAT[768]`, HNSW cosine index, `array_cosine_similarity`, deterministic IDs.
- **U2/U6 adapters** — Protocol plus YouTube, podcast RSS, institutional. Content-hash caching, `citation_url`.
- **U3 reconciler logic**, **U4 segmentation**, **U10 gate**, **U11 five validators** — real algorithms, real tests.
- **Falsification discipline** — recorded in every commit body as specified. Keep doing it.

**Accepted equivalents — do not "fix" back:** the `TranscriptionEngine` Protocol + `Mock` implementation split, and `LocalGemmaRuntime`'s shape. Both are better than the spec implied. Keep the mocks as test doubles once real engines land beside them.

---

## 18. Invariants — do NOT change

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

Full text: `master_implementation_plan.md` §3. Code violating one is wrong even if its tests pass.

---

## 19. LOOP 4 — CLOSE OUT

```text
LOOP 4 — CLOSE OUT

Reached only when no item in section 6 is both undelivered and unblocked.

1. Run section 2 one final time. Record the numbers in section 3.
2. Confirm STUB_REGISTRY is empty, or that every remaining entry maps to a
   blocked item.
3. Write a report containing:
     - what landed this session, with measured numbers
     - what is blocked, and on which issue number
     - any new issue you filed via LOOP 3
4. STOP. Do not invent work.

The only legitimate triggers for resuming are:
     - a "Your selection:" line gets filled in
     - a gate in section 3 goes red
     - the user asks for something specific
```

---

## 20. Feedback loop — what the last spec got wrong

Every gap in the previous cycle traces to a spec that tested shape. Fix the spec, not only the code.

| What happened | Spec said | Should have said |
|---|---|---|
| `35.0 t/s` reported as measured | "Record tokens/sec" | "Assert a wall-clock floor a real model cannot beat." |
| Grammar falsified by string truncation | "Disable the grammar; parse failures appear" | "Assert the grammar is built from the schema and the sampler rejects an ungrammatical token." |
| Hash function passing as an embedding | "Embed with nomic-embed-text-v1.5" | "Assert two synonyms score above threshold — a test no hash function can pass." |
| 16 cases reporting 1.000 | "~200 utterances, personally verified" | Same, **plus** a harness that refuses a metric below a per-class floor, **plus** separate loaders so fixtures and corpus cannot be summed. A target alone gets ignored; a structure that makes the mistake impossible does not. |
| Undeclared dependencies | *(silent)* | "Dependencies land in `pyproject.toml` in the same commit." |
| Docs contradicting themselves | *(silent)* | "Update every doc your change invalidates in the same commit." |

**The pattern: shape is exactly what a stub reproduces perfectly. Validation for an integration item must be satisfiable only by the real dependency.**
