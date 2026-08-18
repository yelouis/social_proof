# Engineering Issues & Decisions — Working Log

**What this file is:** the live queue of open design decisions, each with options and trade-offs, awaiting your selection. Once selected, an issue moves to §4 with the rationale preserved.

**Rules:**
- Every open issue ends with `Your selection: _____`. **That line is yours. An agent must never fill it in on its own behalf.**
- An issue marked **Blocks: Phase N** must be resolved before that phase starts. The rest can wait.
- Recommendations are marked, but a recommendation is not a decision.

**Status: pre-implementation.** No code exists. Everything below is a design decision, not a bug.

---

## 1. Decisions awaiting your selection

Ordered by when they block work.

---

### Issue 001: The missing Specificity / falsifiability axis
**Blocks: Phase 6** · **Recommended: Option A**

The selected rubric is Consistency + Update Integrity + Even-handedness. All three reward a subject who never commits to a checkable position: no reversals to find, no updates to disclose, no principle stated firmly enough to apply unevenly. **Pure hedging scores as perfect integrity.**

`design_rubric_engine.md` §2 mitigates this by weighting reversals by `(1 − hedging)`, so a hedged statement contributes less to a *penalty*. That is not the same as rewarding specificity — it reduces the downside of vagueness without ever recording its cost.

**Option A (recommended): add Specificity as a fourth scored axis.**
Measure the share of claims in the slice that are concrete and checkable — named entities, numbers, dates, unhedged assertions — versus pure hedges. Score it alongside the other three.
- Pros: closes the loophole properly. Makes the other three axes mean something by establishing that the subject was actually saying things. Cheap — `hedging_level` and entity density are already extracted, so no new model calls.
- Cons: a fourth number to define, defend, and gate. Some subjects are legitimately cautious in ways this reads as evasion.

**Option B: display specificity as context, don't score it.**
Show "62% of claims on this topic were hedged" next to the rubric, unscored.
- Pros: closes the interpretive loophole for an attentive reader at almost no design cost, and avoids defending a fourth formula.
- Cons: an unscored number gets ignored, and it doesn't help cross-person comparison at all.

**Option C: leave the rubric at three axes.**
- Pros: fewer moving parts; ships sooner.
- Cons: the system's highest scores go to its least informative subjects, and that will not be obvious to a reader until they've trusted a few of them.

Your selection: Proceed with Option A. However, I want to go over how you will go about measuring these axis. Are you just going to pass it to an LLM or will there be a shared rubric?

---

### Issue 002: Flutter's role after the shift to API-plus-thin-clients
**Blocks: Phase 7** · **Recommended: Option A**

The stack decision was Flutter + Firebase. The browser-extension requirement then reshaped the architecture into a local API with several thin clients (`design_local_api_and_clients.md` §1), so Flutter is now one surface among several rather than *the* app. That is a real change to a decision you made, and it should be explicit.

**Option A (recommended): keep Flutter as the deep-dive client, extension as the reading-moment client.**
- Pros: reuses what you know from Gaslight. Native macOS app for long research sessions, where a browser tab is genuinely worse. Clean split — extension for the glance, Flutter for the dig.
- Cons: two UI codebases in two languages (Dart + JS). Timeline and tension-card rendering get built twice.

**Option B: drop Flutter; ship a local web client the extension can also open.**
- Pros: one UI codebase, one language. The extension and the deep-dive share components outright. Fastest path to both surfaces.
- Cons: abandons the Flutter familiarity that motivated the original choice; a browser tab is a worse home for a long research session.

**Option C: Flutter first, extension deferred to v2.**
- Pros: honours the original stack decision without qualification.
- Cons: defers the best idea in the project. The reading-moment overlay is what makes this useful when you aren't already suspicious.

Your selection: Lets just do the extension first. We can do the flutter app later. I just want the design language to be consistent once we do the flutter app.

---

### Issue 005: Embedding model and dimension
**Blocks: Phase 2** · **Recommended: Option A**

Fixes the DuckDB vector width, the proposition-dedup quality, and the topic-resolution quality. Expensive to change later — a switch re-embeds every proposition and principle and invalidates every cached topic resolution (`design_topic_model.md` §3).

**Option A (recommended): a local open-weights embedding model.**
- Pros: free at any volume, fully offline, no per-call latency in the dedup hot path — which runs on every extracted claim. Fits local-first.
- Cons: one more model to manage locally; quality is good but not frontier.

**Option B: a hosted embedding API.**
- Pros: strongest retrieval quality, nothing to run locally.
- Cons: a network call in the dedup path, per-call cost across hundreds of thousands of propositions, and it breaks the offline property.

**Option C: local by default, hosted for the ambiguous adjudication band only.**
- Pros: cheap bulk, high quality exactly where merges are genuinely uncertain.
- Cons: two embedding spaces cannot be compared — the adjudication would have to be an LLM equivalence call rather than a second embedding. Workable but more machinery.

Your selection: Proceed with Option A.

---

### Issue 003: Audio retention policy and disk budget
**Blocks: Phase 1** · **Recommended: Option A**

`design_source_acquisition.md` §5.2 keeps compressed audio so any disputed claim can be re-heard, and `design_ui_direction.md` §2 puts a `play` affordance on every audio-derived claim. Opus at ~24 kbps is roughly 10 MB/hour — a 300-hour subject is ~3 GB, and twenty subjects is ~60 GB.

**Option A (recommended): keep compressed audio for all ingested sources indefinitely.**
- Pros: `play the tape` is the highest-trust element in the product. Makes the negation re-check (§5.3) possible at any time. Sources get deleted from the internet; your copy does not.
- Cons: tens of GB, growing. Needs a backup story (Issue 006).

**Option B: keep audio only for sources that produced a published Tension.**
- Pros: cuts storage by roughly an order of magnitude.
- Cons: you cannot re-check a claim that wasn't in a Tension *yet* — and new Tensions appear whenever the corpus grows or the rubric changes. Deletes exactly what a future finding needs.

**Option C: keep word timestamps only; discard audio after transcription.**
- Pros: minimal disk.
- Cons: kills `play the tape` and the negation re-check. The one thing you want when a finding is challenged is the tape.

Your selection: Proceed with Option C. Make sure to store the link to the tape though so the user can go to the citation.

---

### Issue 007: Extraction model
**Blocks: Phase 2** · **Recommended: Option A**

Two-stage pipeline (`design_claim_extraction.md` §6): `claude-haiku-4-5` gates, and a stronger model extracts. The gate choice is settled; the extractor is not. Estimated one-time cost per large subject, batched with a cached prompt: **~$37 with `claude-opus-5`**, roughly half that with `claude-sonnet-5`.

**Option A (recommended): `claude-opus-5` for extraction.**
- Pros: extraction is the quality-critical step — the I7 speech-act guards, stance-neutral canonicalisation, and change-marker detection are exactly the subtle judgments where capability shows. Errors here propagate into every score and are expensive to find later. ~$37 once per subject is not the constraint on this project.
- Cons: roughly 2× the extraction cost of Sonnet 5.

**Option B: `claude-sonnet-5` for extraction.**
- Pros: about half the cost; strong on structured extraction.
- Cons: the failure modes you'd be trading for are the silent ones — a missed steelman or a polarity leak doesn't announce itself, it just quietly corrupts an axis.

**Option C: Sonnet 5 by default, Opus 5 re-extraction on any claim entering a Tension.**
- Pros: cheap bulk, frontier quality precisely where a claim is about to become a published finding.
- Cons: two extraction versions coexisting in one corpus, which complicates the version discipline in `design_claim_extraction.md` §9. Defensible, but it is the most machinery of the three.

Your selection: Lets do a local model like Gemma that fits on my computer for now.

---

### Issue 009: Even-handedness fallback if precision doesn't clear the bar
**Blocks: Phase 5** · **Recommended: Option A**

`design_principle_extraction.md` is the highest-risk component. If golden-corpus precision on principle conflicts comes in low, decide *now* what happens, rather than under pressure mid-phase.

**Option A (recommended): ship the evidence without the score.**
Show detected principle pairs — both quotes, both actors, both dates, any stated distinction — under "possible double standards," with no number. Drop the axis from the rubric until precision clears the bar.
- Pros: degrades to the most defensible thing the system can say. The user still gets the hardest-to-find evidence; the system just declines to quantify it.
- Cons: the rubric drops to two axes (three with Issue 001), and the most distinctive measurement is missing.

**Option B: keep the axis but raise the significance threshold until precision is acceptable.**
- Pros: preserves the rubric shape; the axis nulls out for most subjects rather than disappearing.
- Cons: an axis that is null for nearly everyone is dead weight that still has to be explained on every screen.

**Option C: block Phase 6 until Even-handedness meets the bar.**
- Pros: ships the intended rubric or nothing.
- Cons: makes the whole rubric hostage to the single hardest component.

Your selection: Proceed with Option A.

---

### Issue 006: Artifact store backup
**Blocks: Phase 1** · **Recommended: Option B**

The artifact store (audio, raw transcripts with word timestamps) is the only irreplaceable layer — Firestore and DuckDB are mutually recoverable, but a lost artifact requires re-downloading sources that may no longer exist (`design_data_layer.md` §1).

**Option A: no backup; accept re-ingest as the recovery path.**
- Pros: zero cost, zero setup.
- Cons: deleted podcasts and pulled videos are permanently gone. Re-transcribing 300 hours is an overnight job even when the sources survive.

**Option B (recommended): local external-drive backup, scripted and manual.**
- Pros: cheap, offline, no third party sees the corpus. Matches local-first.
- Cons: only as reliable as your habit of running it.

**Option C: cloud object storage.**
- Pros: durable and automatic.
- Cons: ongoing cost that grows with the corpus, and it puts the full audio archive on someone else's infrastructure — a meaningful change to the local-first posture.

Your selection: Proceed with Option B.

---

### Issue 011: Promote `audience_divergence` to a fourth (or fifth) axis
**Blocks: Phase 6** · **Recommended: Option A**

Currently flagged evidence, not scored (`design_rubric_engine.md` §6). It is arguably the most striking thing the system can find, and it is only findable because venue metadata is captured.

**Option A (recommended): keep it as flagged evidence.**
- Pros: the base rate is very low — most subjects have zero instances, so the axis would be null for nearly everyone. As a flag it costs nothing and lands hard when it fires.
- Cons: not counted anywhere, so a subject who does this systematically isn't scored down for it.

**Option B: promote it to a scored axis with its own gate.**
- Pros: systematic audience-shifting is real and arguably the most damning thing here.
- Cons: another mostly-null axis to explain, and it needs a same-window definition that will produce false positives on genuinely evolving views.

Your selection: Proceed with Option A.

---

### Issue 013: Extension overlay — inline or popup
**Blocks: Phase 8** · **Recommended: Option A**

**Option A (recommended): corner-anchored inline overlay, dismissible, never modifying the page.**
- Pros: visible in the reading moment without a click, which is the entire point.
- Cons: overlays fight with site layouts and sticky headers; needs per-site defensive CSS.

**Option B: extension popup only, with a toolbar indicator.**
- Pros: zero page interference, much simpler.
- Cons: requires a click, so it only helps when you're already suspicious — losing the main advantage over passive lookup. A toolbar indicator also edges toward the notification-badge non-goal (`design_ui_direction.md` §8).

Your selection: How about if the user highlights text, we look at the context of what fact they are trying to check against and we then pull up the context as an overlay along with an expandable view for the full timeline and trust vectors.

---

### Issue 014: `play the tape` in v1
**Blocks: Phase 9** · Depends on Issue 003 · **Recommended: Option A**

**Option A (recommended): ship it in v1.**
- Pros: the highest-trust element in the product — the user hears the person say it. Word timestamps already make it nearly free once audio is retained.
- Cons: only works if Issue 003 lands on Option A. Adds audio playback plumbing to the Flutter client.

**Option B: defer to v2; link out to the source at its timestamp instead.**
- Pros: no playback code; YouTube and most podcast players accept a timestamp fragment.
- Cons: dead when the source is removed, which is exactly when you most want the tape.

Your selection: Proceed with Option B.

---

### Issue 015: Is Firestore still earning its place?
**Blocks: Phase 1** · **Recommended: Option A** · *Filed after the Issue 002 selection*

Firestore was chosen for two reasons: sync, and native client reads for a Flutter app. **Both were undercut by decisions since made.** The extension requirement moved us to an API-plus-thin-clients architecture, so clients read HTTP rather than Firestore directly — and Issue 002 defers Flutter entirely. What remains is a sync contract to maintain, a network dependency inside a local-first tool, and a second store to keep consistent, in exchange for a benefit nothing currently uses.

DuckDB already holds every row and is the only store that can run the core contradiction join.

**Option A (recommended): drop Firestore. DuckDB is the single store; the local API serves every client from it.**
- Pros: one store, no sync contract, no reconciliation pass, no `synced_at` bookkeeping, no emulator in CI. Materially less to build in U1 and less to get wrong forever after. Fully offline.
- Cons: no cloud copy, so the backup story (Issue 006, Option B) becomes the only durability story. Re-adding a sync layer later means writing the publish path then.

**Option B: keep Firestore as specified.**
- Pros: a hosted path already exists if this ever becomes multi-user; a cloud copy of derived data survives a disk failure.
- Cons: pays a real, permanent complexity cost now for a capability with no current consumer.

**Option C: defer the decision — build U1 against a storage interface with a DuckDB implementation only.**
- Pros: costs almost nothing now and keeps both doors open.
- Cons: an interface designed with no second implementation usually fits the second one badly. This tends to be the choice that feels safe and buys little.

Your selection: Proceed with Option A.

---

### Issue 017: The external models are simulated, and were reported as measured
**Blocks: Phase 3** · **Recommended: Option B** · *Filed after the August 17 verification pass*

Phases 0–2 are built and the plumbing is real, but **every external model is a stub**. `pyproject.toml` declares `duckdb`, `pydantic`, `pyarrow`, `numpy`, `yt-dlp` — there is no `faster-whisper`, no `pyannote.audio`, no local-model runtime, and no embedding model.

| Layer | What exists | What does not |
|---|---|---|
| U3 transcription | Dual-pass reconciler, VAD gate, negation-cue alignment — all real logic | `MockTranscriptionEngine` returns scripted strings. No audio has ever been transcribed. |
| U7 diarization | Threshold comparison, enrollment store, high/low/discard banding | No `pyannote`. Attribution is compared over synthetic numpy vectors. |
| U9 extraction runtime | Protocol, prompt, KV-prefix accounting, schema validation | `tokens_per_second = 35.0` is a **hardcoded literal**. No Gemma, no GBNF grammar — "grammar enforcement" is falsified by `raw_json[:-2]`. |
| U12 embeddings | DuckDB VSS, HNSW cosine index, `array_cosine_similarity` — genuinely wired | `compute_deterministic_text_embedding` is a **bag-of-words hash projection**, not a semantic model. |

**The embedding stub is the dangerous one, and it is different in kind from the others.** The rest are honestly named `Mock…`; this one produces plausible 768-dim vectors and plausible cosine numbers, so the dedup tests pass and nothing looks wrong. But it hashes each word to one dimension — *"licensing"* and *"permitting"* land in unrelated slots and score ~0 similarity. Proposition dedup therefore merges only near-identical strings, which silently disables the semantic layer that topic resolution, principle clustering, and cross-person comparison all sit on. Trap 7 (nomic's `search_document:` / `search_query:` prefixes) appears nowhere in the codebase, and **cannot** be tested against a hash function.

**Option A: wire every real external now, before any new phase.**
- Pros: ends the possibility of reporting a constant as a measurement. The `Protocol` boundaries already exist, so this is additive rather than a rewrite.
- Cons: slow. Model downloads, a gated Hugging Face token for `pyannote`, and hours of real transcription. Phases 3+ stall behind it.

**Option B (recommended): wire the embedding model now; defer Whisper, pyannote, and Gemma.**
- Pros: targets the one stub that is silently wrong rather than merely absent. `nomic-embed-text-v1.5` is a few hundred MB and runs in seconds — for that price, dedup, topic clustering, and principle matching all become real, and trap 7 becomes testable. The other three stay behind honest `Mock` names.
- Cons: transcription and diarization remain unproven, so no corpus is real end-to-end yet.

**Option C: keep all mocks through Phase 6; wire everything at once before the client.**
- Pros: fastest route to a complete architecture; every logic layer gets built and unit-tested cheaply.
- Cons: you will not learn that a real Whisper transcript looks nothing like a scripted mock until six phases sit on that assumption. This is the classic integrate-at-the-end failure, and it is the most expensive way to find out.

Your selection: Proceed with Option A.

---

### Issue 018: The golden corpus is 16 synthetic sentences, so its metrics are vacuous
**Blocks: parameters 004, 008, 012, 016** · **Recommended: Option B** · *Filed after the August 17 verification pass*

`golden/cases.json` holds **16 hand-written sentences** — one per case type, three for N13. Source locators are fabricated (`https://youtube.com/watch?v=golden_p1`), and `verified_by` is the string `"curator"` rather than a person who listened to anything.

The reported **Precision 1.000 / Recall 1.000** is not a measurement. With exactly one example per class, each metric can only be 0.0 or 1.0, and the sentences were written to trigger the code paths that then classify them. The spec called for ~200 labelled utterances across 3–5 real subjects (`e2e_verification_journeys.md` §2).

Nothing that depends on measurement can proceed: attribution thresholds (004), the dedup threshold (008), the sufficiency gates (012), and `H_max` (016) are all still unset, and the local-vs-frontier extraction question in U13 cannot be answered.

**Option A: rebuild against real ingested sources before Phase 3.**
- Pros: the only version that can measure anything. Unblocks all four parameters at once.
- Cons: genuine human labelling work — hours of listening, and it cannot be delegated to an agent.

**Option B (recommended): keep the 16 as unit fixtures under an honest name; grow the real corpus as subjects get ingested.**
- Pros: stops the 16 from masquerading as a measurement while keeping their value as regression tests. Labelling proceeds in parallel with the build instead of blocking it.
- Cons: thresholds stay unset longer, and the temptation to ship on fixture numbers persists.

**Option C: accept the synthetic corpus as sufficient.**
- Pros: nothing blocks.
- Cons: every precision figure in this project becomes decorative, and the four measured parameters can never be set honestly.

Your selection: _____

---

## 2. Parameters to be measured, not selected

**These are not decisions and should not be guessed.** Each is a threshold whose correct value is discovered by running against the golden corpus (`e2e_verification_journeys.md`). An agent that picks a number here and moves on has skipped the work.

| # | Parameter | Set during | Bias |
|---|---|---|---|
| **004** | Speaker attribution thresholds (high / low) | Phase 1 | **Precision.** A missed utterance costs nothing; a misattributed one is the worst bug in the product. |
| **008** | Proposition merge threshold + whether ambiguous-band adjudication earns its cost | Phase 2 | **Toward merging.** Over-splitting hides every contradiction, silently. |
| **010** | Topic retrieval similarity threshold + cluster-expansion policy | Phase 3 | **Precision on retrieval, generosity on expansion.** Small slices produce confident wrong scores. |
| **012** | Per-axis sufficiency gates (min eligible propositions, min changes, min directional conflicts) | Phase 6 | **Conservative.** `insufficient_corpus` is always a safe answer; a number on thin evidence never is. |
| **016** | `H_max` — the hedging ceiling in Specificity's checkability test (`design_rubric_engine.md` §2A) | Phase 6 | **Toward generosity.** Set it so genuinely committed statements count as checkable; only pure evasion should fail. Too strict and the axis reads as punishing ordinary caution. |

Each must be recorded with the measurement that produced it, not just the value.

---

## 3. Deliberately not built — do not re-propose

Consolidated from `master_implementation_plan.md` §8 so it is checkable in one place. Re-proposing one of these costs a cycle.

Prediction/forecast scoring · fact-checking of any kind · a single global trust score · a composite of the rubric axes · radar charts · N-way comparison dashboards · face or voice recognition of strangers · scoring private individuals from thin corpora · unofficial X/Twitter scraping · inline article annotation · notification badges or contradiction counts · shareable score images stripped of evidence · sentiment visualisation.

---

## 4. Resolved — index

Selections live with their issue above, with the user's own wording preserved. This is the index.

| # | Selected | Consequence |
|---|---|---|
| **001** | **A** — Specificity as a fourth scored axis | `design_rubric_engine.md` §2A. Computed as a *rate* from deterministic features, no LLM at scoring time (§0). Introduces parameter 016. |
| **002** | **Extension first, Flutter later** | Phase 9 deferred. Extension becomes the only planned client, which promotes **Issue 013 to the critical path**. Design tokens must be authored so a Flutter client can mirror them later — U12 in the execution guide. |
| **003** | **C** — discard audio, keep the citation link | **Reshapes the ingest pipeline.** Dual-pass transcription must run at ingest, before deletion; there is no later. `citation_url_template` on every Source. Disk drops ~3 GB → ~70 MB per subject. |
| **005** | **A** — local open-weights embeddings | `nomic-embed-text-v1.5`, **768 dims**, fixed in the DuckDB schema. |
| **006** | **B** — local external-drive backup, scripted | Much smaller job now that 003 removed the audio. |
| **007** | **Local model (Gemma)** | No Anthropic call in the extraction path. Requires grammar-constrained decoding and KV prefix reuse. Cost becomes wall-clock, not dollars. |
| **009** | **A** — evidence without a score if precision misses | Fallback pre-decided, so Phase 5 can't stall on it. |
| **011** | **A** — `audience_divergence` stays flagged evidence | Not an axis. |
| **014** | **B** — no in-app playback; deep-link to the source | Follows necessarily from 003. |
| **013** | **NOT YET SELECTED** | **Now blocks the only client.** See §1. |
| **015** | **NOT YET SELECTED** | Filed this session. Blocks U1's shape. |

---

## 5. Where the detail lives

| Question | Document |
|---|---|
| Big picture, phases, invariants | `master_implementation_plan.md` |
| What to build next, with validation | `agent_execution_guide.md` |
| First-hand boundary, ingest pipeline | `design_source_acquisition.md` |
| Utterance → structured claim | `design_claim_extraction.md` |
| Even-handedness machinery | `design_principle_extraction.md` |
| Topic clustering and resolution | `design_topic_model.md` |
| Axis formulas, tension types, gates | `design_rubric_engine.md` |
| Schema, mirror, sync, versioning | `design_data_layer.md` |
| API contract and clients | `design_local_api_and_clients.md` |
| Timelines, tension cards, null states | `design_ui_direction.md` |
| The anti-defamation contract | `design_evidence_integrity.md` |
| Golden corpus and journeys | `e2e_verification_journeys.md` |
