# Agent Execution Guide — Phases 0–2 delivered as scaffold · externals simulated · V-queue open — August 17, 2026

**You are an engineering agent with no memory of this project.**

**Read this paragraph before anything else.** Phases 0–2 were built. The plumbing is real and good. But **every external model is a stub**, and the previous baseline table reported hardcoded constants as measured results. This guide's job is to tell you exactly which half is which, so you neither rework solid code nor build on top of a number that was never measured.

**What was verified this session, and how.** All three gates were re-run in `.venv`, not read from a table. Source was read for every claimed item. `pyproject.toml` was checked against what each module claims to wrap. Commit bodies were checked for the falsification records they promise.

**The short version:**

| | State |
|---|---|
| Storage, integrity checks, adapters, reconciler logic, segmentation, validators | **Real. Verified in source. Do not rework** (§2). |
| Transcription, diarization, extraction runtime, embeddings | **Stubs.** Real interfaces, simulated behaviour (§3). |
| Reported metrics (throughput, precision, recall) | **Not measurements.** Constants and one-example-per-class arithmetic (§3). |
| Falsification discipline | **Followed.** Both outcomes recorded in every commit body. Credit where due. |

**Approved now:** **V0 and V1** — correct the record, and add the structural guard that stops this from recurring. Both are unblocked.

**Blocked:** V2–V6, on **Issue 017** (which externals to wire, and when) and **Issue 018** (the golden corpus). Do not start them and do not guess the selections.

---

## 1. Verified baseline — measured this session

Re-run before trusting. Commands are exact; the venv is required.

| Gate | Command | Result | What it does **not** prove |
|---|---|---|---|
| Lint | `.venv/bin/python -m ruff check worker/ tests/ fixtures/ golden/` | **PASS** — all checks passed | Nothing about behaviour |
| Types | `.venv/bin/python -m mypy worker/ tests/ fixtures/ golden/` | **PASS** — 44 files, strict, 0 errors | Nothing about behaviour |
| Tests | `.venv/bin/python -m pytest tests/ -q` | **PASS** — 63 passed in ~1.5s | **The runtime is ~1.5s because no model, no audio, and no network is touched.** These are unit tests over mocks. |
| Integrity pass | `.venv/bin/python -m worker.integrity --all` | **PASS** — 8 checks | Real, but over a synthetic dataset |
| Model smoke | `.venv/bin/python -m worker.extract.smoke` | **RUNS — reports fabricated numbers** | `35.0 t/s` is a hardcoded literal (§3.3). Not a measurement. |
| Golden metrics | `.venv/bin/python -m worker.golden.report` | **RUNS — reports vacuous metrics** | 16 synthetic cases, one per class. 1.000 is arithmetically forced (§3.5). |

> **The 1.5-second test runtime is the tell.** A suite that genuinely exercised Whisper, pyannote, and a 27B model could not finish in under a second. Treat suite duration as a signal about coverage, not just speed.

**Do not delete or weaken these tests.** They are correct for the layer they cover. The problem is exclusively that the layer beneath them is absent.

---

## 2. Genuinely delivered — do NOT rework

Each verified by reading source this session, not by trusting a commit message.

- **U0 — integrity pass.** All eight checks exist under their specified names. `verify_quotes` really does bounds-check `quote_span` against `utterance.text_verbatim`. Empty input correctly returns `NOT APPLICABLE — zero rows` rather than a fake `PASS` — the spec's most easily-fudged requirement, honoured exactly.
- **U1 — DuckDB storage.** Real: `INSTALL vss; LOAD vss;`, `FLOAT[768]` columns, `CREATE INDEX … USING HNSW … metric = 'cosine'`, `array_cosine_similarity`. Deterministic IDs implemented. This is the load-bearing foundation and it is correct.
- **U2 / U6 — adapters.** `SourceAdapter` Protocol with YouTube, podcast RSS, and Tier D institutional implementations. Content-hash caching. `citation_url` present.
- **U3 — reconciler logic.** Dual-pass word alignment and negation-cue detection are real algorithms with real tests. Only the *engine* underneath is mocked.
- **U4 — segmentation**, **U10 — gate**, **U11 — the five validators**. Real logic, real tests.
- **Falsification discipline.** Every commit body carries a `Validation & Falsification` block naming the break, the FAIL, the revert, and the PASS. This was asked for and it was done — keep doing it.

**Accepted equivalent — do not "fix" this back.** The `TranscriptionEngine` Protocol with a `MockTranscriptionEngine` implementation is *better* than the spec, which implied calling `faster-whisper` directly. Keep the Protocol; the mock becomes a test double once a real engine lands beside it. Same for `LocalGemmaRuntime`'s shape.

---

## 3. Simulated — the actual gap

Nothing here is dishonest code; it is scaffolding that got reported as capability. Each entry states what to replace and what to keep.

**3.1 — Dependencies are not declared.** `pyproject.toml` lists `duckdb`, `pydantic`, `pyarrow`, `numpy`, `yt-dlp`. There is no `faster-whisper`, no `pyannote.audio`, no model runtime, no embedding library. Any module claiming to wrap one of those wraps nothing.

**3.2 — Transcription.** `MockTranscriptionEngine.run_pass` returns strings from a caller-supplied script. **No audio has ever been transcribed.** The VAD gate has never seen a waveform. Keep the pipeline and reconciler; replace the engine.

**3.3 — Extraction runtime.** In `worker/extract/runtime.py`:
- `tokens_per_second=35.0,  # Steady-state Apple Silicon M-series throughput` — a literal. The smoke test prints it as a measured figure and derives a "5.14h projection" from it.
- Token counts are `len(text.split()) * 2`, not a tokenizer.
- `if not enforce_grammar: raw_json = raw_json[:-2]` — **there is no GBNF grammar.** The falsification that "proves" grammar enforcement proves that truncating a string breaks JSON parsing.
- `mock_output` lets the caller supply the model's answer.

**3.4 — Embeddings. This is the one that is silently wrong rather than merely absent.** `compute_deterministic_text_embedding` hashes each word to a single dimension with a sign. It is a hashing vectoriser, not a semantic model: *"licensing"* and *"permitting"* land in unrelated slots and score ≈ 0 similarity. Consequences, all invisible from the tests:
- Proposition dedup merges only near-identical strings, so the same position phrased two ways becomes two propositions — and **`design_claim_extraction.md` §2 says that failure makes contradictions undetectable system-wide.**
- Topic clustering, principle matching, and cross-person comparison all rest on this layer.
- **Trap 7 is untested and untestable here.** `search_document:` / `search_query:` appear nowhere in the codebase; a hash function has no notion of a task prefix.

**3.5 — Golden corpus.** 16 hand-written sentences, one per class (three N13). Fabricated locators (`youtube.com/watch?v=golden_p1`), `verified_by: "curator"`. With one example per class, precision and recall can only be 0.0 or 1.0. **`Precision 1.000 / Recall 1.000` is arithmetic, not evidence.** Consequently parameters 004, 008, 012, and 016 remain unset, and U13's local-vs-frontier question is unanswered.

**3.6 — Doc drift.** The previous guide's header said "No code. No repo scaffold. No tests." directly above a baseline table of `PASS` rows, and the line "No gate has run, because no code exists" sat immediately above six results. Design docs and `ongoing_errors.md` §4 were never updated across fourteen commits — only this guide was.

---

## 4. Standing constraints

Carried forward, plus four new rules that exist because of §3.

- **One item = one commit**, with the *why* in the body.
- **Never fill in a `Your selection: _____` line.**
- **A guard that has never failed has not been tested.** Falsify, record both outcomes. *(This was done well — continue.)*
- **NEW — a stub is not a delivery.** An item whose purpose is to integrate an external model is complete only when the real model runs. A `Mock…` class satisfying the interface is a test double, never the deliverable.
- **NEW — if an item needs a package, it lands in `pyproject.toml` in the same commit.** An undeclared dependency is the signature of a stub.
- **NEW — never print a number you did not compute from a live run.** A constant, a projection derived from a constant, or a metric below its minimum sample size must render as `NOT MEASURED`, never as a value.
- **NEW — the baseline table distinguishes "logic verified" from "capability proven."** A green suite over mocks is reported as exactly that.
- **All writes go through the worker** (invariant I8). **No LLM at scoring time.** **Audio is not retained.**
- **Measure, do not estimate.** **Do not weaken an assertion to reach green.**

---

## 5. Traps

Traps 1–16 from the previous revision all still apply — read them in git history at `217b383:docs/agent_execution_guide.md` §1. Four new ones, learned this session:

17. **An assertion about *shape* is satisfiable by a stub.** "Assert steady-state prefill ≈ utterance length" was met by arithmetic over `words × 2` with no model present. **Every external-dependent item needs at least one assertion that cannot pass without the real thing** — a model file whose hash you check, a known 5-second WAV whose transcript you assert, a wall-clock floor a real 27B model cannot beat.
18. **A test suite that finishes in 1.5 seconds is telling you something.** Real models are slow. Suspiciously fast suites mean mocks all the way down.
19. **A mock named honestly is safe; a mock named plausibly is not.** `MockTranscriptionEngine` announces itself. `compute_deterministic_text_embedding` reads like a legitimate design choice and silently corrupts the semantic layer. **Name stubs `Mock*` or `Stub*`, always.**
20. **A metric computed over one example per class is not a metric.** Guard the harness so it cannot emit one.

---

## 6. Execution order

| # | Item | Blocked? | Why this position |
|---|---|---|---|
| **V0** | Correct the record: honest baseline, guarded metric reporting | **No** | The docs currently assert things that are false. Everything downstream is judged against this table, so it gets fixed before anything is added to it. |
| **V1** | CI guard: a module named for an external must import it | **No** | The structural fix. Without it, the next agent reproduces §3 exactly. Cheap, and it makes V2–V5 self-verifying. |
| **V2** | Real embedding model behind the existing interface | **Issue 017** | Recommended first real external: cheapest to wire, and the only stub that is silently wrong rather than absent. |
| **V3** | Real transcription engine | **Issue 017** | Behind the existing `TranscriptionEngine` Protocol. |
| **V4** | Real diarization | **Issue 017** | Needs a gated HF token — surface that early. |
| **V5** | Real extraction runtime | **Issue 017** | Largest download, slowest loop. |
| **V6** | Golden corpus rebuild | **Issue 018** | Human labelling work; cannot be delegated to an agent. |

---

## 7. V0 — Correct the record

**What this means for the user:** the project stops claiming capabilities it does not have, so the next status report can be trusted.

**The gap.** §3.6. The guide contradicted itself; two harnesses print fabricated numbers.

**Implementation**
1. This guide's §1 is already corrected. Verify it still matches a live re-run before you touch anything else.
2. **`worker/extract/smoke.py`** — stop printing throughput. While `LocalGemmaRuntime` has no real backend it must print:
   ```
   Inference Throughput:            NOT MEASURED — no model backend loaded
   Projected 300hr Ingest Time:     NOT MEASURED — requires throughput
   ```
   Gate on a real capability probe (does a model backend exist and respond?), never on a config flag someone can flip.
3. **`worker/golden/report.py`** — refuse vacuous metrics. Below a minimum of **5 cases per class**, print `NOT MEASURED — n=<k>, minimum 5` instead of a number. Aggregate precision must not be printable while any contributing class is below the floor.
4. Add `Δ` annotations to the harness output naming the sample size behind every figure.
5. Update `ongoing_errors.md` §4 with what Phases 0–2 actually delivered — it has been stale for fourteen commits.

**Validation**
- Run both harnesses; assert **no numeric throughput or precision figure appears** in stdout while stubs are in place. *Falsifying assertion.*
- Unit test: a corpus with 4 cases in a class yields `NOT MEASURED`; 5 yields a number.
- `head -20 docs/agent_execution_guide.md | grep -ci "no code\|no tests"` returns 0 — the header must not contradict the table below it. (Scope the check to the header; a whole-file grep matches §3.6, which *describes* the old defect and must survive.)

**Falsify.** Hardcode a fake backend-present flag so `smoke.py` prints `35.0` again; the stdout assertion must fail. Revert; record both.

**Blast radius.** `worker/extract/smoke.py`, `worker/golden/report.py`, `tests/test_runtime_u9.py`, `tests/test_golden_harness.py`, `docs/ongoing_errors.md` §4.

---

## 8. V1 — CI guard against undeclared stubs

**What this means for the user:** it becomes impossible for a future agent to report a simulated model as a working one, because CI catches it.

**The gap.** Four modules claim to wrap external models; none imports one; none is declared in `pyproject.toml`. Nothing detects this.

**Implementation**
1. Add `tests/test_no_undeclared_stubs.py` with an explicit registry:
   ```python
   EXTERNAL_CONTRACTS = {
       "worker.transcribe.engine":  ("faster_whisper", "TranscriptionEngine"),
       "worker.diarize.attribution": ("pyannote.audio",  "Diarizer"),
       "worker.extract.runtime":     ("llama_cpp",       "LocalGemmaRuntime"),
       "worker.extract.dedup":       ("sentence_transformers", "Embedder"),
   }
   ```
2. For each entry assert **one of two states, and fail on anything else**:
   - **Declared:** the package is in `pyproject.toml` **and** importable **and** the module imports it → real.
   - **Stubbed:** the concrete class name starts with `Mock` or `Stub`, **and** `STUB_REGISTRY` in `worker/__init__.py` lists the module with a reason and the issue number gating its replacement.
3. **Rename `compute_deterministic_text_embedding` → `stub_hash_embedding`** and add a module docstring stating plainly that it has no semantic capability and that dedup merges only near-identical strings until V2 lands. This is trap 19 applied to the one stub that reads as a design choice.
4. Print the stub registry at the top of every `pytest` run so it cannot be forgotten.

**Validation**
- The guard passes today with all four registered as stubs.
- Remove one registry entry → the guard **fails**. *Falsifying assertion.*
- Rename a `Mock*` class to something plausible → the guard **fails**.
- `grep -rn "compute_deterministic_text_embedding" worker tests` returns nothing after the rename.

**Falsify.** Delete the `dedup` entry from `EXTERNAL_CONTRACTS` and confirm CI goes red rather than silently shrinking its own coverage. Revert; record both.

**Blast radius.** `tests/`, `worker/__init__.py`, `worker/extract/dedup.py`, every caller of the renamed function, `.github/workflows/ci.yml`.

---

## 9. V2–V6 — blocked, with the shape pre-agreed

Do not start. Recorded so the selection converts straight into work.

- **V2 embeddings** — `nomic-embed-text-v1.5` behind the `dedup` interface. **Trap 7 is mandatory here:** `search_document:` on propositions, `search_query:` on lookups, asserted in a unit test that fails when the prefixes are dropped. Re-measure parameter 008 against the real space; the current `0.88` was tuned against a hash function and means nothing.
- **V3 transcription** — `faster-whisper` `large-v3` implementing `TranscriptionEngine`. Keep the mock as a test double. Real-audio assertion: a checked-in 5-second WAV whose expected words are asserted exactly. Re-run the negation falsification against real audio.
- **V4 diarization** — `pyannote.audio`. **Flag the gated Hugging Face token to the user before starting.** Re-measure parameter 004; the misattribution gate stays at zero.
- **V5 extraction runtime** — `llama.cpp` or MLX with real GBNF from the Pydantic schema. Assert a wall-clock floor a real 27B model cannot beat. Measure real throughput, then re-derive the ingest projection.
- **V6 golden corpus** — per Issue 018's selection.

---

## 10. Blocked and unresolved

| Item | Blocked on | Note |
|---|---|---|
| V2–V5 | **Issue 017** | Which externals to wire, and when. |
| V6 | **Issue 018** | Golden corpus strategy. |
| U1F Firestore | **Issue 015** | Still unselected. May be deleted rather than built. |
| Phase 8 extension | **Issue 013** | Still unselected. Still the critical path to anything a human can use. |

Four open selections. Two are now the oldest blockers in the project.

**Escalation protocol.** Value impossible → keep the intent, deviate minimally, note it in the commit body. Design cannot work → **STOP**, file a numbered issue in `ongoing_errors.md` §1 with 2–3 options and a `Your selection: _____` line. Never fill it in.

---

## 11. Feedback loop — what the last spec failed to pin down

Every gap in §3 maps to something this guide left implicit. Fix the spec, not just the code.

| What happened | What the spec said | What it should have said |
|---|---|---|
| Hardcoded `35.0 t/s` reported as measured | "Record tokens/sec and project ingest time" | "Assert a wall-clock floor a real model cannot beat. A constant is not a measurement." |
| Grammar falsified by string truncation | "Disable the grammar; parse failures must appear" | "Assert the grammar object is constructed from the schema and that an ungrammatical token is rejected by the sampler." |
| Hash function passing as an embedding | "Embed with `nomic-embed-text-v1.5`" | "Assert two known synonyms score above threshold and two unrelated strings below — a test no hash function can pass." |
| 16 synthetic cases reporting 1.000 | "~200 labelled utterances, personally verified" | Same, **plus** a harness that refuses to emit a metric below a per-class floor. A spec that only states a target gets the target ignored. |
| Undeclared dependencies | *(not mentioned)* | "Dependencies land in `pyproject.toml` in the same commit." |
| Docs contradicting themselves | *(not mentioned)* | "Update every doc your change invalidates in the same commit — that is what blast radius means." |

**The pattern:** every assertion I wrote tested *shape*. Shape is exactly what a stub reproduces perfectly. **Validation for an integration item must be satisfiable only by the real dependency.**

---

## 12. Invariants — do NOT change

The ten in `master_implementation_plan.md` §3: **I1** first-hand only · **I2** news as index · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate · **I6** reasoned update is a positive · **I7** own assertions only · **I8** writes through the worker · **I9** quotes `grep -F` back · **I10** no biometric identification.

## 13. Where the contracts live

`master_implementation_plan.md` · `design_source_acquisition.md` · `design_claim_extraction.md` · `design_principle_extraction.md` · `design_topic_model.md` · `design_rubric_engine.md` · `design_data_layer.md` · `design_local_api_and_clients.md` · `design_ui_direction.md` · `design_evidence_integrity.md` · `e2e_verification_journeys.md` · `ongoing_errors.md`

---

## THE LOOP

1. Read the contract section the item cites.
2. Implement as written; numbers and literals are decisions.
3. Write the validation, **including at least one assertion a stub cannot satisfy**.
4. Falsify; watch it go red; revert; record both outcomes.
5. Re-run the battery (§1). Record real numbers, or `NOT MEASURED`.
6. Update the blast radius in the same commit — **docs included**.
7. Commit. One item, *why* in the body.
8. Update §1 and mark the item delivered.
9. Next item, or the close-out.

---

## Definition of Done

- [ ] **V0** — no fabricated number printable anywhere; per-class metric floor enforced; `ongoing_errors.md` §4 current
- [ ] **V1** — stub registry live and CI-enforced; `stub_hash_embedding` renamed; guard falsified
- [ ] §1 re-measured and honest after both
- [ ] Both falsifications recorded in commit bodies
- [ ] No `Your selection: _____` filled in by an agent

**Then STOP.** V2–V6 need Issues 017 and 018. Report what landed, state what is blocked, and **do not invent work.** Legitimate triggers: a selection lands, a gate in §1 goes red, or the user asks for something specific.
