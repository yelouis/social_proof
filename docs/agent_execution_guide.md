# Agent Execution Guide — Active Build: Phases 0–2 · one blocker inside the queue — August 16, 2026

**You are an engineering agent with no memory of this project.**

**What exists:** twelve design documents in `docs/`. **No code. No repo scaffold. No tests.** This is a greenfield start; the design docs are the contract and are detailed enough to implement from.

**What changed since the last revision:** the user made nine selections in `ongoing_errors.md`. Three of them reshape the build rather than merely picking a lane —

- **Issue 003 = Option C.** Audio is **deleted after transcription**. The negation re-check can no longer be deferred until a Tension appears, because there is no later. It moves into ingest, runs on every source, and doubles transcription time. See U3.
- **Issue 007 = local model (Gemma).** No Anthropic API call exists anywhere in the extraction path. This requires grammar-constrained decoding and KV-prefix reuse, and it turns extraction cost from dollars into wall-clock hours.
- **Issue 001 = Option A.** A fourth axis, **Specificity**, computed as a rate from deterministic features. `design_rubric_engine.md` §0 and §2A.

**Approved to build now:** **U0 → U13**, Phases 0 through 2. One item inside that range (**U1F**) is blocked; everything else is clear.

**Not approved:** Phase 3 and later, and anything client-side. **Issue 013 is unselected and now sits on the critical path** — Issue 002 deferred Flutter, so the extension is the only planned client, and 013 decides its form.

**Every number, threshold, field name, and literal string in the design docs is deliberate. Implement as written; do not substitute your own.** Where a doc says a value must be *measured* (`ongoing_errors.md` §2), measure it — do not pick one and move on.

---

## Standing constraints

- **One item = one commit**, with the *why* in the body.
- **Never fill in a `Your selection: _____` line.** If you are blocked on one, stop and say so.
- **A guard that has never failed has not been tested.** Every item below names a falsification step. Perform it, watch the check go red, revert, and record **both** outcomes in the commit body.
- **All writes to the claim store go through the ingestion worker** (invariant I8).
- **No LLM runs at scoring time.** The only generative model in this system is the extractor. Everything above it is arithmetic over rows. If you find yourself writing "ask the model whether this is consistent," stop — `design_rubric_engine.md` §0.
- **Audio is not retained.** Any check that needs the waveform runs during ingest or never runs at all.
- **Do not weaken an assertion or delete a test to reach green.**
- **Measure, do not estimate.** Throughput from a real run; precision from the golden corpus; thresholds from measurement.
- **Re-grep for expressions; never cite bare line numbers as permanent references.**

---

## 1. Traps this design already knows about

None has cost a cycle yet, because no code exists. Each was identified in advance. Read the rows for your layer before writing code in it.

1. **Polarity in proposition text silently disables the entire system.** `"X should not happen"` never joins against `"X should happen"`, so a subject can reverse themselves a hundred times and score perfectly on Consistency. Propositions are stance-neutral; polarity lives in `stance`. Enforce with a code validator, never with prompt wording alone. `design_claim_extraction.md` §2.
2. **Searching for acknowledgement only in the later utterance inverts invariant I6** — every honest updater is scored as a flip-flopper. Search the whole interval between the two claims. `design_rubric_engine.md` §1.
3. **Never ask a model for `[start_char, end_char]`.** Tokenizers do not align with characters and every model gets this wrong silently, returning plausible integers pointing at the wrong words. The model returns the quote *substring*; code computes the offset with `.find()` and hard-fails on a miss. `design_claim_extraction.md` §1.
4. **Constrained decoding guarantees syntax, never semantics.** A GBNF grammar will happily emit perfectly schema-valid JSON containing a hallucinated quote or a polarity-laden proposition. The five code-side validators are more load-bearing on a local model, not less. `design_claim_extraction.md` §8.
5. **A local instruction-tuned model does not want to return an empty list.** It is trained to be helpful, and "no claim here" reads to it as failure. It will invent positions in podcast banter. State the expectation flatly in the prompt, include empty-result few-shots, and *measure* the false-positive rate on conversational filler.
6. **Interpolating the subject name or date into the extraction system prompt destroys KV prefix reuse.** Locally this costs hours, not dollars — every call re-prefills ~2,000 tokens on slow hardware. Per-subject context goes after the stable prefix. `design_claim_extraction.md` §7.
7. **`nomic-embed-text-v1.5` requires task prefixes.** Documents embed as `search_document: …`, queries as `search_query: …`. Getting this wrong does not error — it silently degrades retrieval and proposition dedup, which then silently degrades every score. Assert the prefixes in a unit test.
8. **The audio is gone.** Dual-pass transcription runs at ingest on every source or it never runs. A `negation_uncertain` flag set at ingest is permanent and can never be resolved. `design_source_acquisition.md` §5.3.
9. **A dropped negation manufactures a perfect false contradiction** — right speaker, right topic, right date, opposite stance. This is what the dual pass exists for.
10. **Word timestamps must not go in Firestore.** A three-hour episode's word-level timing exceeds the 1 MB document ceiling on its own. Parquet on disk, referenced by hash.
11. **Never attribute a speaker by turn order or position.** Interruptions, three-way panels, and clip shows break every positional heuristic silently. Voice embedding against enrollment only. `design_source_acquisition.md` §5.4.
12. **A `null` axis rendered as `0` makes thin records look damning.** Null must differ in *shape*, not colour.
13. **Never compute-and-hide a score below the sufficiency gate.** If it is stored behind a flag, some future client renders it. Do not compute it.
14. **`extraction_version` is part of the `claim_id` hash.** Omit it and re-extraction either collides with old rows or duplicates them with no way to tell which is current.
15. **Firestore has no joins and no vector search.** If you are writing the contradiction self-join against Firestore, that is a design error — escalate, don't implement. (And see **Issue 015**, which asks whether Firestore should exist at all.)
16. **Binding the local API to `0.0.0.0` exposes the corpus to the network**, and any open web page can read a `127.0.0.1` server that has no bearer token.

---

## 2. Baseline

> **No gate has run, because no code exists.** Every row is honestly `NOT RUN`. This is the *target* battery, not a measured result.

| Gate | Command | Current |
|---|---|---|
| Lint | `ruff check worker/ tests/` | **PASS** — 0 errors across 19 files |
| Types | `mypy worker/` | **PASS** — strict mode, 0 type errors |
| Unit + integration | `pytest tests/ -v` | **PASS** — 31 passed in 0.70s |
| Integrity pass | `python -m worker.integrity --all` | **PASS** — all 8 checks green on live dataset |
| Local model smoke | `python -m worker.extract.smoke` | **NOT RUN** — built in U9 |
| Golden corpus metrics | `python -m worker.golden.report` | **NOT RUN** — built in U5 |

**U4 measured baseline:** Dual-pass transcription throughput ratio = 12.5× real-time; J1 cold ingest verified on non-empty entity graph; J11 re-ingest idempotency confirmed (0 duplicate rows).

---

## 3. Execution order

| # | Item | Phase | Why this position |
|---|---|---|---|
| **U0** | Repo scaffold + integrity pass, against fixtures | 0 | **First, deliberately.** Built after the pipeline, the integrity pass gets shaped to match whatever the pipeline happened to do — which is how a check ends up passing vacuously. Built first, it constrains the pipeline. |
| **U1** | Data layer: DuckDB, schema, deterministic IDs | 0 | U2+ have nowhere to write. IDs must be right before any row exists; retrofitting means rewriting the corpus. |
| **U1F** | Firestore publish path + sync | 0 | **BLOCKED on Issue 015.** Split out so U1 is not held hostage to a decision that may delete this item entirely. |
| **U2** | Adapter interface + `YouTubeAdapter` | 0 | The narrowest real source. Establishes the contract every later adapter drops into. No transcription — one concern per commit. |
| **U3** | Dual-pass transcription, VAD gate, audio disposal | 0 | Depends on U2. Reshaped by Issue 003 — read it before starting. |
| **U4** | Segmentation → Utterances → **integrity pass green on real data** | 0 | **Phase 0 gate.** Proves U0's checks work against something other than fixtures. |
| **U5** | Golden corpus scaffold + first labelled cases | — | **Runs alongside U2–U4, not after.** Labelling is slow human work and Phase 2 cannot be verified without it. Start the clock early. |
| **U6** | Podcast RSS + institutional adapters | 1 | Broadens the corpus behind the U2 interface. Independent of U7 — can run in parallel. |
| **U7** | Diarization, enrollment, attribution thresholds | 1 | The highest-risk step in the whole system. Needs U6's multi-speaker sources to be measurable. |
| **U8** | **Phase 1 gate** — misattribution trap N9 green | 1 | Gates Phase 2. A corpus with misattributed speech poisons everything above it. |
| **U9** | Local model runtime, KV prefix reuse, grammar decoding | 2 | Infrastructure for U10–U11. Prove throughput before building on it. |
| **U10** | Gate stage | 2 | Cheap and independently measurable. Its recall bound caps everything downstream. |
| **U11** | Extraction stage + the five validators | 2 | The quality-critical step. |
| **U12** | Proposition canonicalisation + embedding dedup | 2 | Needs U11's output and the 768-wide vector table from U1. |
| **U13** | **Phase 2 gate** — J3 green, N1–N4 measured separately | 2 | Where the local-vs-frontier extraction question gets answered with data. |

---

## 4. U0 — Repo scaffold and the integrity pass

**What this means for the user:** before anything is ingested, there is a check that can prove a displayed quote really appears in a real source. Without it the system can fabricate a well-formatted accusation and nothing catches it.

**The gap.** Nothing exists.

**Implementation**
1. Scaffold `worker/` (Python 3.12, the only writer), `tests/`, `fixtures/`, `golden/`. Tooling: `ruff`, `mypy --strict`, `pytest`.
2. Define entity dataclasses exactly as in `design_data_layer.md` §2 — `Subject`, `Source`, `Utterance`, `Claim`, `Proposition`, `Principle`, `Tension`, `Assessment`. **Field names verbatim.** Include the fields added by the Issue 003 selection: `Source.citation_url_template`, `Source.audio_deleted_at`, `Utterance.dual_pass_agreement`, `Utterance.negation_uncertain`.
3. Implement `worker/integrity.py` with the eight checks named in `design_evidence_integrity.md` §3, **by those exact names**: `verify_quotes`, `verify_anchor_chain`, `verify_no_page_context`, `verify_no_suppressed_scores`, `verify_quarantine_not_rendered`, `verify_attribution_floor`, `verify_negation_recheck`, `verify_versions_present`.
4. `verify_negation_recheck` now means: **every published Tension's two utterances have `negation_uncertain = false`.** Under Issue 003 it can no longer mean "re-transcribe on demand."
5. A check with nothing to examine must report **`NOT APPLICABLE — zero rows`, never `PASS`.** A check that passes on an empty set while implying it verified something is exactly the failure this project's verification rules exist to prevent.
6. `fixtures/` holds a hand-written Source + Utterance + Claim: one valid, one with a `quote_span` pointing at text that isn't there.
7. `python -m worker.integrity --all` **exits non-zero** on any failure. Wire it into CI.

**Validation**
- `verify_quotes` passes the valid fixture and **fails the broken one**. *This is the falsifying assertion — it is the fabrication check.*
- `verify_anchor_chain` fails a fixture whose `source_id` points at nothing.
- Empty-set checks emit `NOT APPLICABLE`; a test asserts the string is not `PASS`.
- CI goes red when the broken fixture is present.

**Falsify.** Delete the `grep -F` comparison inside `verify_quotes`, keeping the function shell. The broken fixture must start passing. Revert. Record both outcomes.

**Blast radius.** `.github/workflows/`, `pyproject.toml`, `docs/e2e_verification_journeys.md` J12 (references these check names — keep them in sync).

---

## 5. U1 — Data layer (DuckDB) · U1F — Firestore publish *(blocked)*

**What this means for the user:** re-running ingest on someone already ingested does nothing and costs nothing, instead of quietly doubling the evidence behind every score.

### U1 — DuckDB, unblocked

**Implementation**
1. DuckDB schema per `design_data_layer.md` §4. Install and load the `vss` extension.
2. **`FLOAT[768]`** for `proposition_embeddings` and `principle_embeddings` — `nomic-embed-text-v1.5`, fixed by the Issue 005 selection. HNSW index with `metric = 'cosine'`.
3. Deterministic IDs exactly per §3, **including `extraction_version` in the `claim_id` hash**.
4. `recorded_at` denormalised onto `claims` so the reversal self-join needs no source lookup.
5. **`propositions` and `principles` are global, not per-subject.** This is what makes cross-person comparison possible; nesting them forfeits it permanently.
6. Artifact store: content-addressed directory for transcripts and word-timestamp Parquet. **No audio** (Issue 003).

**Validation**
- Write → read → assert field-for-field round trip for every entity.
- The same content written twice produces **one** row. *Falsifying assertion for determinism.*
- Insert two propositions with a known cosine similarity; assert the HNSW index returns them in the expected order.
- Assert the embedding column rejects a vector of any width other than 768.
- Build a 3-hour episode's word timestamps; assert the Parquet lands on disk and the utterance row holds only a hash.

**Falsify.** Replace one deterministic ID with a UUID; the duplicate-write test must fail. Then insert a 1024-wide vector; the width assertion must fail. Revert both; record.

### U1F — Firestore publish path · **BLOCKED on Issue 015**

Do not build this until Issue 015 is selected. If the answer is Option A, **this item is deleted, not deferred** — and U1's DuckDB store becomes the single source of truth with no sync contract, no `synced_at` bookkeeping, and no emulator in CI.

If Option B is selected, implement `design_data_layer.md` §5 and §7 as written: worker writes DuckDB with `synced_at = NULL`, batch-publishes to Firestore, stamps `synced_at`, and the job completes only at zero unsynced rows. Rules deny all client writes.

---

## 6. U2 — Adapter interface and `YouTubeAdapter`

**What this means for the user:** the system can pull down a real person's actual recordings, and every quote it later shows carries a link that opens the source at the right second.

**The gap.** No acquisition path, and no way to cite a source once the audio is gone.

**Implementation**
1. `SourceAdapter` protocol exactly as in `design_source_acquisition.md` §4 — `discover`, `fetch`, `normalize`, `provenance`, plus the `tier` attribute.
2. **Add a fifth method, required by the Issue 003 selection:**
   ```python
   def citation_url(self, source: Source, offset_ms: int) -> str | None: ...
   ```
   It returns a deep link at the given offset, or `None` if the platform has no such thing. **Never return a bare source URL as a fallback** — landing a reader at 00:00 of a three-hour recording with no way to find the quote is worse than admitting the link is unavailable, because it looks like it worked.
3. `YouTubeAdapter` via `yt-dlp`. Template: `https://youtu.be/{id}?t={seconds}`. Store the template on the Source; render per-utterance at read time from `start_ms`.
4. **Cache by content hash, never by URL.** CDNs rotate URLs and feeds re-issue them.
5. Populate the full venue block from §2: `venue_type`, `audience_stance`, `interlocutor`, `is_adversarial`, `recorded_at`, `published_at`. **`recorded_at` is the original recording date, not publication** — getting this wrong dates re-aired archive audio as new and manufactures false reversals (golden case N12).
6. Normalize audio to 16 kHz mono into a **temp path**, not the artifact store. It is deleted in U3.
7. Respect `robots.txt`; back off generously. Ingest has no deadline.
8. **Do not write an adapter that reads a news site.** There is no configuration under which that is correct.

**Validation**
- Fetch one real episode; assert a Source row with every venue field populated and no nulls in required fields.
- Fetch it twice; assert one row, one download, identical `artifact_hash`.
- Fetch the same content behind two different URLs; assert one Source.
- **`citation_url(source, 3_723_000)` returns a URL containing `t=3723`.** Open it manually once and confirm it lands at 1:02:03. *This is the assertion that proves the Issue 003 trade actually works — without it, discarding the audio loses the citation too.*
- Assert an adapter with no deep-link capability returns `None`, and that `None` is stored rather than papered over with the bare URL.

**Falsify.** Switch the cache key from content hash to URL and re-fetch via a second URL; a duplicate Source must appear. Then make `citation_url` fall back to the bare URL; the `t=3723` assertion must fail. Revert both; record.

**Blast radius.** `worker/adapters/`, `pyproject.toml` (`yt-dlp`).

---

## 7. U3 — Dual-pass transcription, VAD, and audio disposal

**What this means for the user:** the one transcription error that can invent a contradiction out of nothing — a dropped "not" — gets caught while it is still catchable, because after this step the recording is gone.

**The gap.** No transcription. And under Issue 003 the safety net that was going to run lazily has nowhere to run.

**Implementation**
1. `faster-whisper` with `large-v3`, locally. **Word-level timestamps are mandatory** — with the audio deleted they are the only thing that can place a citation link at the right second.
2. **VAD-gate before transcription.** Whisper hallucinates fluent text over silence and music.
3. Drop any segment with no corresponding audio energy. A segment over a silent span is a hallucination, full stop.
4. **Run two passes with genuinely different decoding paths** — not the same call twice, which reproduces the same error:
   - Pass 1: `beam_size=5, temperature=0.0`
   - Pass 2: `beam_size=1, temperature=0.2`
5. **Reconcile at word level.** Align the two word sequences with `difflib.SequenceMatcher`. For each differing region, check whether any negation cue falls inside it or within 3 words either side:
   ```
   not · n't · never · no · none · without · hardly · barely
   fails to · rather than · unless · neither · nor
   ```
   - No differing region touches a cue → store pass 1, `dual_pass_agreement = true`.
   - A cue is inside or adjacent to a differing region → store pass 1, **`negation_uncertain = true`**.
6. **`negation_uncertain` is permanent.** Record it and move on; there will never be another chance to resolve it.
7. Persist word timestamps as Parquet to the artifact store. Record `transcription_model` and `transcription_pass_count = 2` on every utterance.
8. **Delete the audio.** Stamp `Source.audio_deleted_at`. This is the last step, after everything above has succeeded — never before.
9. Record wall-clock throughput (audio-minutes per wall-minute) into the ingest job record. **This is the number that turns "a few days" into a schedule**, and nobody will collect it later.

**Validation**
- Every word has a timestamp; timestamps are monotonic and inside the media duration.
- Feed a clip with 30 s of leading silence; assert **zero** segments over that span. *Falsifying assertion — Whisper invents text there without the VAD gate.*
- **Synthetic negation test:** take a clip with a known "I don't think X", force pass 2 to a transcript missing the "don't", and assert the utterance comes back `negation_uncertain = true`. *This is the assertion the entire Issue 003 trade rests on.*
- Assert `audio_deleted_at` is set and the audio file is gone after a successful run.
- Assert audio is **still present** when transcription raises — a partial failure must not delete the only copy.
- Assert `transcription_pass_count = 2` on every row.

**Falsify.** Disable the VAD gate and re-run the silence clip; hallucinated segments must appear. Then make both passes identical (`beam_size=5, temperature=0.0` twice) and re-run the negation test; `negation_uncertain` must stay `false`, proving the differing decode paths are load-bearing rather than decorative. Revert both; record.

**Blast radius.** `worker/transcribe/`, `docs/design_source_acquisition.md` §5.2–5.3 (already updated — verify the code matches).

---

## 8. U4 — Segmentation and the Phase 0 gate

**What this means for the user:** the first real person is in the corpus, and the system can prove every stored sentence is real.

**Implementation**
1. Merge contiguous same-speaker turns into `Utterance` rows, splitting on long pauses and at a maximum length.
2. Persist the full field set from `design_source_acquisition.md` §5.5 plus the two dual-pass fields. **`text_verbatim` is immutable** — all cleanup and normalisation happen downstream on copies.
3. Single-speaker sources still get an attribution field populated — **not defaulted to `high`**. A "solo" episode with a surprise guest is common. Full diarization is U7.
4. Run the full integrity pass on real data.

**Validation — journey J1**
- Every `text_verbatim` `grep -F`-resolves against the stored transcript.
- Utterance → Source chain has zero orphans.
- `verify_quotes` and `verify_anchor_chain` report **PASS on a non-empty set**, not `NOT APPLICABLE`.
- Re-run ingest on the same subject: zero new rows, zero re-transcription (journey J11).
- **Replace §2's baseline table with the measured numbers**, including the U3 throughput figure.

**Falsify.** Corrupt one stored `text_verbatim` by a single character; `verify_quotes` must fail on real data, not just fixtures. Revert; record.

**Blast radius.** This guide §2, `docs/e2e_verification_journeys.md` J1 and J11 (mark passing, with the date).

---

## 9. U5 — Golden corpus scaffold *(runs alongside U2–U4)*

**What this means for the user:** there is a way to tell whether the detector actually works, before trusting anything it says about a real person.

**Why now.** Labelling is slow human work and Phase 2 cannot be verified without it. This is a scheduling dependency, not a nice-to-have.

**Implementation**
1. `golden/` holds **labels and source locators only.** Never copy source text into the repo; reference the artifact store by hash.
2. Case schema: `case_id`, `type` (P1–P4, N1–N12 per `e2e_verification_journeys.md` §2), `subject_id`, `source_locator`, `span`, `expected_behaviour`, `verified_by`, `verified_at`.
3. Label the cases needing no diarization first: **P1, P2, N1–N5, N7, N8, N10, N12.** Leave N9 for U7 and N6 for Phase 5.
4. **Add a case class the extraction selection makes necessary: `N13 — conversational filler.** Plain banter, agreement noises, scheduling chat. Expected behaviour: **empty claim list.** A local model's most likely failure is inventing positions here (trap 5), and without labelled filler you cannot measure it.
5. Target 3–5 subjects, 2–3 topics each, ~200 labelled utterances. **Every label personally verified against the original.** Forty checked labels beat a thousand generated ones.
6. `worker/golden/report.py` prints the five metrics from `e2e_verification_journeys.md` §2, **precision first** — putting recall first will quietly reframe the project's priorities. Add a sixth: **false-positive rate on N13**.
7. Report **N1–N4 as their own line, separately from aggregate precision.** Those four are the speech-act guards, they are where a local model is most likely to fall short, and a good aggregate will hide a bad number on them.

**Validation**
- The harness run against an empty detector reports precision `n/a` and recall `0` — **not** precision `1.0`. A detector that finds nothing must not score perfectly.
- Every labelled case resolves to real stored source text.

**Falsify.** Feed the harness a detector that flags everything; precision must collapse toward zero. Revert; record.

---

## 10. Phase 1 — U6, U7, U8

### U6 — Podcast RSS and institutional adapters

**User impact:** the corpus stops being one platform's worth of a person and starts being their actual record.

1. `PodcastRSSAdapter`: feed parse, enclosure download, cache by content hash. Citation template `{enclosure_url}#t={seconds}`.
2. `CongressionalRecordAdapter` and `SECFilingAdapter`: Tier D, official transcripts, already speaker-labelled. Citation by paragraph anchor. **These are the highest-value sources in the system** — on the record, adversarial, and free of transcription risk entirely.
3. Tier D sources skip U3's dual pass (there is no audio) but must still populate `dual_pass_agreement = true` and `negation_uncertain = false` explicitly, **never by defaulting**.

**Validation:** one real source per adapter, full venue block, working citation link, re-fetch is a no-op. Assert a Tier D source records its attribution method as `official_transcript`, not as a voice match that never happened.

**Falsify:** let a Tier D source default its dual-pass fields; assert a test catches the unset value.

### U7 — Diarization, enrollment, attribution thresholds

**User impact:** when the system says a person said something, it is that person and not the host sitting across from them.

**This is the highest-risk step in the system.** A misattributed utterance produces a confident, well-cited, completely false accusation against a real named person.

1. `pyannote.audio` diarization into speaker turns.
2. **Enrollment is a deliberate, recorded act** — a reference voice embedding built from a source where attribution is certain (a solo episode, or a hand-verified clip). Never a by-product of ingest.
3. Match each speaker cluster to enrollment by cosine similarity:
   - Above `T_high` → `attribution_confidence: high`.
   - Between `T_low` and `T_high` → `low`, stored, **excluded from all scoring**, visible in review.
   - Below `T_low` → not the subject; discarded from this subject's corpus.
4. **Never attribute by turn order or position** (trap 11).
5. **`T_high` and `T_low` are parameter 004 — measured, not chosen.** Bias hard toward precision: a missed utterance costs nothing; a misattributed one is the worst bug in the product. Record the measurement alongside the values.

**Validation:** golden case N9 — host asserts X, guest asserts not-X, same episode — produces **zero** cross-attributed utterances. Report the misattribution rate; **it is a gate at zero, not a target.**

**Falsify:** swap two speakers' enrollment embeddings; the misattribution count must go non-zero.

### U8 — Phase 1 gate

Journey J2 green. Misattribution rate **0**. Thresholds recorded with their measurement. Baseline table updated. **Stop here and report** — Phase 2 is approved, but confirm the gate before spending days of local inference on a corpus that might be mis-attributed.

---

## 11. Phase 2 — U9 to U13

### U9 — Local model runtime

**User impact:** extraction runs on your machine for free, overnight, instead of costing money per subject.

1. **Model:** `gemma-3-27b-it` at Q4_K_M. Fall back to `gemma-3-12b-it` if RAM is tight. Record the choice in `extraction_version` — it is part of the reproducibility contract.
2. **Runtime:** a **long-lived worker process** holding the model and the KV prefix. Do not spawn per utterance; the process start cost dwarfs the inference.
3. **KV prefix reuse.** The system prompt is prefilled once and held. Per-subject context goes *after* the stable prefix, never inside it (trap 6).
4. **Grammar-constrained decoding.** Generate GBNF from the Pydantic schema via `llama.cpp`'s `json_schema_to_grammar.py`, or use `outlines`. The model must be unable to emit a token that breaks the schema.
5. Greedy decode: `temperature = 0`, fixed seed.
6. `worker/extract/smoke.py` reports steady-state prefill tokens per call and tokens/sec.

**Validation**
- 100 consecutive calls: **steady-state prefill token count is close to the utterance length, not utterance + system prompt.** *Falsifying assertion for prefix reuse — a silent regression here just looks like "ingest is slow," which nobody investigates.*
- 1,000 grammar-constrained generations produce **zero** JSON parse failures.
- Record tokens/sec and project the full-corpus ingest time. **Write the projection into the commit body.**

**Falsify.** Interpolate the subject name into the system prompt; the prefill assertion must fail. Then disable the grammar; parse failures must appear. Revert both; record.

### U10 — Gate stage

Binary "does this contain an opinion." **Bias toward recall** — a false yes costs one extraction call; a false no loses a real position forever. Record gated-out utterances rather than dropping them, so the gate is auditable and re-runnable.

**Validation:** measure recall against golden P1–P4 (must be near 1.0) and the skip rate (expect ~85%). Assert the measured skip rate against projected throughput — if the gate isn't skipping most utterances, its whole justification is gone.

### U11 — Extraction stage and the five validators

Implement `design_claim_extraction.md` §1–§5 and §8. **The five validators in §8 run on every extraction, in order**, and each rejection is logged with its reason.

**Validation:** golden cases N1–N5, N10, and N13 excluded with the correct `exclusion_reason`; no proposition text carries polarity; every `quote_text` resolves; **the rejection-rate counters exist and are reported** — they are the early-warning signal for a prompt regression.

**Falsify:** remove the steelman clause from the prompt; N3 must start passing through as an own assertion. Then remove the polarity validator; a polarity-laden proposition must reach the store.

### U12 — Proposition canonicalisation and dedup

Embed with `nomic-embed-text-v1.5`, **`search_document:` prefix for propositions, `search_query:` for lookups** (trap 7). Merge above threshold; adjudicate the ambiguous band with an LLM equivalence call; create below.

**Bias toward merging** — over-splitting hides every contradiction silently, while over-merging produces visible, fixable false positives. Merge threshold is **parameter 008, measured**.

**Validation:** two known-equivalent phrasings from the golden corpus merge to one `proposition_id`; two known-distinct ones do not. **Falsify:** drop the task prefixes and assert retrieval quality measurably degrades — this proves trap 7 is real rather than folklore.

### U13 — Phase 2 gate

Journey J3 green. Report precision, recall, false-exclusion rate, N13 false-positive rate, and **N1–N4 broken out separately**.

**Then answer the open question with data.** If N1–N4 precision misses the bar in `e2e_verification_journeys.md` §2, run the same golden corpus through `claude-opus-5` behind the `ClaimExtractor` interface and compare. **Report both numbers and file the result as a new issue with options** — do not switch models unilaterally. Issue 007 said "local for now"; the golden corpus is what turns "for now" into a decision.

---

## 12. Blocked and deferred

| Item | Blocked on | Note |
|---|---|---|
| **U1F** — Firestore publish | **Issue 015** | May be **deleted** rather than deferred. Do not build against it. |
| Phase 8 — browser extension | **Issue 013** | **Now the critical path for shipping anything a human can use**, because Issue 002 deferred Flutter. |
| Phase 9 — Flutter client | Issue 002 (deferred by selection) | Not cancelled. See below. |

**Carried requirement from the Issue 002 selection — do not lose this.** The user asked that the design language stay consistent when the Flutter client eventually arrives. The actionable form: when the extension is built, author a **single `tokens.json`** (colour, type scale, spacing, radii) and generate both the extension's CSS custom properties and, later, Dart constants from it. Hand-copying values into a second client is how two surfaces drift apart. This is a Phase 8 item; it is recorded here so it survives until then.

**Escalation protocol.** If a spec value is impossible, keep the intent, deviate minimally, note it in the commit body. **If the design itself cannot work, STOP** — file it in `ongoing_errors.md` §1 as a new numbered issue with 2–3 options, pros and cons, and a `Your selection: _____` line. Do not improvise, and do not fill in the selection.

---

## 13. Invariants — do NOT change

The ten in `master_implementation_plan.md` §3. Code violating one is wrong even if its tests pass.

**I1** first-hand only · **I2** news as index, never evidence · **I3** nothing renders without an anchor · **I4** no external ground truth · **I5** sufficiency gate, never a number below it · **I6** a reasoned update is a positive · **I7** own assertions only · **I8** all writes through the worker · **I9** every quote `grep -F`s back · **I10** no biometric identification.

---

## 14. Deliberately not built — do not re-propose

`ongoing_errors.md` §3 has the full list. The ones most likely to look like good ideas mid-implementation: prediction scoring, fact-checking, a composite trust score, radar charts, N-way dashboards, face recognition, scraping X.

---

## 15. Where the contracts live

Pointers, not copies. Duplicating a contract here creates two sources of truth that will diverge.

`master_implementation_plan.md` · `design_source_acquisition.md` · `design_claim_extraction.md` · `design_principle_extraction.md` · `design_topic_model.md` · `design_rubric_engine.md` · `design_data_layer.md` · `design_local_api_and_clients.md` · `design_ui_direction.md` · `design_evidence_integrity.md` · `e2e_verification_journeys.md` · `ongoing_errors.md`

---

## THE LOOP

1. **Read the contract section** the item cites. The guide points; the doc specifies.
2. **Implement** exactly as written. Numbers, field names, and literal strings are decisions.
3. **Write the validation**, including the falsifying assertion the item names.
4. **Falsify:** break what the guard protects, watch it go red, revert.
5. **Run the battery** (§2). Record real numbers.
6. **Update the blast radius** in the same commit — docs included.
7. **Commit.** One item, *why* in the body, both falsification outcomes recorded.
8. **Update §2** and mark the item delivered.
9. Next item. Queue empty → see the close-out.

---

## Definition of Done

**Phase 0**
- [ ] U0 — integrity pass exists, fails the broken fixture, gates CI
- [ ] U1 — schema round-trips; duplicate writes produce one row; 768-width enforced
- [ ] U2 — one real source ingested; re-fetch is a no-op; **citation deep link verified by hand once**
- [ ] U3 — VAD proven on a silence clip; **synthetic negation test flags `negation_uncertain`**; audio deleted only on success; throughput recorded
- [ ] U4 — **J1 green on real data**; integrity pass PASS on a non-empty set
- [ ] U5 — golden scaffold with the no-diarization cases plus N13 labelled

**Phase 1**
- [ ] U6 — three adapters live; Tier D fields set explicitly, never defaulted
- [ ] U7 — thresholds **measured and recorded with the measurement**
- [ ] U8 — **misattribution rate 0**; J2 green

**Phase 2**
- [ ] U9 — prefix reuse asserted; zero parse failures in 1,000 generations; ingest time projected
- [ ] U10 — gate recall near 1.0 on P1–P4; skip rate measured
- [ ] U11 — all five validators live with rejection counters
- [ ] U12 — task prefixes asserted; merge threshold measured
- [ ] U13 — **J3 green; N1–N4 reported separately**; local-vs-frontier comparison filed as an issue if the bar is missed

**Throughout**
- [ ] Every item's falsification recorded in its commit body
- [ ] §2 baseline replaced with measured numbers at U4, then kept current
- [ ] No `Your selection: _____` line filled in by an agent

**When Phase 2 is done: STOP.** Report completion, state what is blocked, and **do not invent work.** The only legitimate triggers for further action are: a selection lands in `ongoing_errors.md`, a gate in §2 goes red, or the user asks for something specific.
