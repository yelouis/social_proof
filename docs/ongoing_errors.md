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

Your selection: Proceed with Option B.

---

### Issue 019: Should a model pre-label the golden corpus?
**Blocks: V6 scope** · **Recommended: Option B** · *Filed in response to "why can't we use a model to label the videos? We just need the transcript, right?"*

Mostly yes — but with two constraints that decide the shape.

**Constraint 1 — never label with the model you are testing.** The corpus exists to measure the extractor. Label with Gemma and test Gemma and you measure self-agreement, which is 1.0 by construction. Label with Opus and test Gemma and you measure *"does Gemma agree with Opus"* — a real question, but a different one, and it can never validate Opus itself.

**Constraint 2 — the hard classes fail in *correlated* ways.** N1–N4 (sarcasm, reported speech, steelman, hypothetical) are in the corpus precisely because they are hard **for language models**. Two models trained on similar data make similar mistakes on deadpan sarcasm. So an LLM labeller silently agrees with the extractor on exactly the cases the corpus was built to catch. The corpus goes blind where you most need it to see, and nothing in the metrics reveals it.

**And a wrinkle in the premise: not every class is transcript-decidable.**

| Class | Transcript enough? |
|---|---|
| **N1 sarcasm** | **No.** Deadpan sarcasm often lives entirely in prosody. A transcript is the one representation that strips it. |
| **N9 misattribution** | **No.** The question *is* whether the speaker label is right; a transcript that already carries speaker labels assumes the answer. |
| N5 conditional, N7 hedge, N12 re-aired archive | Yes — syntactic or metadata, mechanically checkable. |
| N2 reported speech, N3 steelman, N4 hypothetical | Usually — these have lexical markers, but adversarial cases do not. |
| P1 vs P2 (unacknowledged reversal vs reasoned update) | Usually — turns on whether a stated reason exists, which is findable in text. |

**Option A: full human labelling.**
- Pros: no circularity anywhere; the corpus is unimpeachable.
- Cons: hours of listening per subject. Realistically it is the thing that never happens, and a corpus that does not exist measures nothing.

**Option B (recommended): model pre-labels, human adjudicates; class-dependent rigour.**
- A model (**not** the extractor under test) proposes `label + confidence + the span it relied on`. A human confirms or corrects from a review queue.
- **Mechanical classes** (N5, N7, N12, quote-span resolution) may be auto-accepted above a confidence threshold, spot-checked at ~10%.
- **Judgment classes** (N1–N4, N10, P1/P2) require explicit human sign-off. `verified_by` names a person or the case does not count.
- **N1 and N9 additionally require the audio**, not just the transcript.
- **Disagreements are kept as high-value cases** — where the pre-labeller and the human differ is exactly what the corpus should contain.
- Pros: collapses human effort from "listen to 300 hours" to "adjudicate a queue," which is the difference between happening and not. Preserves independence where it matters.
- Cons: a review queue to build; the ~10% spot-check is a real ongoing discipline; still needs a second model available for pre-labelling.

**Option C: model labels everything, no human in the loop.**
- Pros: free and immediate; hundreds of cases overnight.
- Cons: every precision figure becomes "agreement with the labelling model." Correlated failure on N1–N4 makes the number *look* good precisely when the system is worst. This is the failure mode this project has already hit once, in a different costume.

Your selection: Proceed with Option C.

---

### Issue 020: Diarization engine backend and Hugging Face gated access for pyannote.audio
**Blocks: V4** · **Recommended: Option A** · *Filed under LOOP 3 escalation*

`pyannote.audio` pipelines (`pyannote/speaker-diarization-3.1` and `pyannote/embedding`) require accepting user terms on Hugging Face and supplying an authentication token (`HF_TOKEN`). No `HF_TOKEN` is currently set in the local environment.

**Option A (recommended): Provide Hugging Face User Access Token (`HF_TOKEN`) for `pyannote.audio`.**
- Pros: Uses the exact reference diarization architecture specified in `design_source_acquisition.md` §5.1 and produces 512-dim speaker embeddings.
- Cons: Requires accepting model conditions on `hf.co/pyannote/speaker-diarization-3.1` and `hf.co/pyannote/segmentation-3.0` and exporting `HF_TOKEN`.

**Option B: Use an un-gated open-weights speaker embedding extractor (e.g. SpeechBrain `speechbrain/spkrec-ecapa-voxceleb`).**
- Pros: 100% open weights with zero gated credentials, tokens, or sign-up requirements. Runs fully offline immediately.
- Cons: Uses SpeechBrain's ECAPA-TDNN embedding architecture (192-dim normalized vectors) instead of Pyannote's 512-dim embedding architecture.

**Option C: Skip/defer V4 for now and proceed directly to V5 (Real extraction runtime — Gemma 3).**
- Pros: Unblocks immediate execution of V5 without waiting on token configuration.
- Cons: Diarization remains in the stub registry until resolved.

Your selection: Proceed with Option A. Token will be supplied via HF_TOKEN environment variable.

---

### Issue 021: First real ingest subject selection and candidate sources
**Blocks: I0** · **Recommended: Option A** · *Filed under LOOP 3 escalation*

I0 requires ingesting the first real human subject end-to-end to validate the full pipeline (discover → fetch → normalize → transcribe → diarize → attribute → segment → gate → extract → embed → persist) on real material rather than empty stores. Per `agent_execution_guide.md` §16, selecting the subject is strictly the user's call because this is their research tool and the corpus is about real people.

To make tension/reversal detection meaningful on the ingested data, the corpus requires at least 3–4 sources spanning 2+ years on a topic the subject has returned to, beginning with single-speaker Tier B sources (own channel or podcast) before multi-speaker Tier C guest appearances.

**Option A (recommended): User specifies the subject and provides 3–4 URLs (or channel/podcast names) spanning 2+ years on an evolving topic.**
- Pros: Aligns directly with user research intent and ensures the subject has real positions on issues of interest to the user.
- Cons: Requires user selection and input before I0 can proceed.

**Option B: Ingest a canonical public tech/policy figure (e.g. Marc Andreessen or Sam Altman) across 3–4 public YouTube/podcast interviews spanning 2022–2024 on open source AI / licensing.**
- Pros: Concrete and immediately actionable; has well-documented public statements spanning 2+ years on a specific proposition topic (open foundation model weights/licensing) suitable for testing P4 tension detection.
- Cons: Assumes subject selection without explicit user direction.

Your selection: Proceed with Option B. Lets do Elon Musk and the people from the All In Podcast: Chamath Palihapitiya, David Sacks, Jason Calacanis, and David Friedberg since the All In Podcast has a lot of episodes.

---

### Issue 022: `tier` and `venue_type` are per-source, but they are properties of a (source, subject) pair
**Blocks: I0.4** · **Recommended: Option A** · *Surfaced by the Issue 021 subject selection*

`worker/entities.py` puts `tier`, `venue_type`, `audience_stance` and `is_adversarial` on `Source` — one value per source. The All-In selection breaks that.

Take one episode where Elon Musk guests:

| Subject | What that source is to them |
|---|---|
| Palihapitiya, Sacks, Calacanis, Friedberg | **their own show** — Tier B, `own_channel`, `friendly` |
| Musk | **someone else's show** — Tier C, `guest` |

One `Source` row cannot hold both. And this is not cosmetic: **`audience_stance` feeds audience-divergence detection** (`design_rubric_engine.md` §6). Stamping the episode `friendly` because that is how the hosts experience it makes every divergence judgement about Musk wrong — a wrong finding, not a wrong label.

The four hosts on their own show are unaffected, which is why I0.1–I0.3 can proceed and only I0.4 is blocked.

**Option A (recommended): add a `SourceSubjectRole` join.**
`Source` keeps what is true of the artifact — title, publisher, url, hashes, `recorded_at`, `published_at`, `citation_url_template`, `transcription_model`. A new row per (source, subject) carries `tier`, `venue_type`, `audience_stance`, `is_adversarial`.
- Pros: models the thing correctly — venue *is* a relationship, not a property of either side alone. Every multi-subject source works, now and later. One artifact, one transcription, many roles.
- Cons: a schema migration on delivered code (U1), and every reader of venue metadata gains a join.

**Option B: one `Source` row per subject.**
Ingest the same episode N times, once per subject, each with its own tier.
- Pros: no join; existing readers unchanged.
- Cons: `source_id = sha256(canonical_locator)` collides, so subject has to enter the hash — which breaks "one source, one row" and duplicates artifact references, transcription bookkeeping and `audio_deleted_at` across rows that describe the same recording. Storage is fine; the bookkeeping is where this rots.

**Option C: keep venue on `Source`, add per-subject overrides on `Utterance`.**
- Pros: smallest diff.
- Cons: puts the same fact in two places with no rule about which wins, and `Utterance` is already the hottest table. This is the option that looks cheapest today and is worst in a year.

Your selection: Proceed with Option A.

---

### Issue 023: Elon Musk is a poor first subject, for a reason unrelated to the schema
**Blocks: I0 scope** · **Recommended: Option A** · *Raised while planning I0 under Issue 021 = B*

Three things separate Musk from the four All-In hosts. Only the first is already filed.

**1. Schema (Issue 022).** He is a guest where they are hosts, so one episode carries two tiers. Filed separately; a real defect but a bounded one.

**2. He is not a host, so All-In alone cannot clear the sufficiency gate for him.** The four hosts have ~200 episodes of recurring material on the same topics — exactly the shape P4 needs. Musk has a handful of appearances. Ingesting "Musk via All-In" would yield `insufficient_corpus` on essentially every topic, which is the *correct* output and also a wasted ingest. Covering him properly means a different source strategy entirely: solo interviews, earnings calls, keynote Q&A.

**3. The one that actually matters — his primary medium is deferred.** X/Twitter ingest is deferred behind the adapter interface (`master_implementation_plan.md` §9). For most subjects that removes a supplementary channel. For Musk it removes **the** channel: it is where he states most positions, fastest, and where reversals are most visible.

That produces a failure mode the design does not currently defend against. Invariant I5 protects against a corpus that is **thin** — too few claims, so no score. It does nothing about a corpus that is **skewed** — plenty of claims, all drawn from the one medium where he is most rehearsed, none from the medium where he is most spontaneous. The sufficiency gate passes, a confident four-axis score renders, and it is measuring a systematically unrepresentative slice of the person.

**A skewed corpus is more dangerous than a thin one, because nothing on screen says so.**

**Option A (recommended): defer Musk until X ingest exists; ingest the four hosts now.**
- Pros: I0 becomes fully unblocked — no guests means Issue 022 stops blocking anything, and the four hosts on their own show are uniform Tier B. Avoids shipping a skewed corpus on the highest-profile subject. The four hosts are a better test corpus anyway: more episodes, more topical overlap, more genuine cross-person comparison.
- Cons: the subject you named first is not in the first ingest. X ingest has no date.

**Option B: include Musk from long-form only, with an explicit medium-skew flag.**
Add `corpus_composition` to the sufficiency block — which media the claims came from — and surface a warning when one expected medium is absent entirely.
- Pros: keeps him in, and the flag is a genuinely good idea for every subject rather than a patch for one. It closes the thin-versus-skewed gap in I5.
- Cons: real work in the rubric and the UI before I0 can finish, and a warning label is weaker than not making the claim. Readers discount warnings.

**Option C: include Musk and pull X ingest forward out of deferral.**
- Pros: covers him properly, and X is valuable for the other four too.
- Cons: X ingest was deferred for good reasons — paid API tiers, ToS-brittle scraping, historical-depth costs (`master_implementation_plan.md` §9). Putting the project's most fragile dependency on the critical path of its first real ingest is the wrong order.

Your selection: Proceed with Option A.

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

### Measured Values

#### Parameter 004: Speaker Attribution Thresholds (T_high, T_low)
- **Status:** Measured in I0.3 (September 2, 2026); marked **provisional** until golden corpus crosses floor of 5 N9 cases.
- **Measured Confidence Distribution:**
  - Evaluated against 15 hand-labeled turns from a 5-minute panel audio clip (`fixtures/panel/allin_e287_5min.wav`) across all four All-In hosts (Chamath Palihapitiya, David Sacks, Jason Calacanis, David Friedberg).
  - True match cosine similarity: min = 0.648, mean = 0.801, max = 0.958.
  - Cross-subject distractor similarity: max = 0.377 (mean = 0.284).
  - Margin between lowest true turn and highest cross-subject distractor: $\ge 0.271$.
- **Values Set:**
  - $T_{\text{high}} = 0.70$ (with minimum margin to runner-up $\ge 0.10$): high confidence, included in scoring.
  - $T_{\text{low}} = 0.50$: low confidence, stored for review, EXCLUDED from scoring.
  - $< T_{\text{low}}$: discarded.
- **Accuracy on Ground Truth:** 15/15 turns correct (100.0%), zero cross-attribution (Assertion c).

---

## 3. Deliberately not built — do not re-propose

Consolidated from `master_implementation_plan.md` §8 so it is checkable in one place. Re-proposing one of these costs a cycle.

Prediction/forecast scoring · fact-checking of any kind · a single global trust score · a composite of the rubric axes · radar charts · N-way comparison dashboards · face or voice recognition of strangers · scoring private individuals from thin corpora · unofficial X/Twitter scraping · inline article annotation · notification badges or contradiction counts · shareable score images stripped of evidence · sentiment visualisation.

---

## 4. Resolved — index

Selections live with their issue above in the user's own wording. This is the index, plus what each one actually cost or saved downstream.

| # | Selected | Consequence |
|---|---|---|
| **001** | **A** — Specificity as a fourth axis | Computed as a *rate* from deterministic features; no LLM at scoring time (`design_rubric_engine.md` §0, §2A). Introduced parameter 016. |
| **002** | **Extension first, Flutter later** | Flutter deferred. Extension became the only client, which promoted Issue 013 to the critical path. Shared `tokens.json` is the mechanism keeping the design language consistent. |
| **003** | **C** — discard audio, keep the citation link | Reshaped ingest: dual-pass transcription moved to ingest time because there is no later. `citation_url_template` on every Source. ~3 GB → ~70 MB per subject. |
| **005** | **A** — local open-weights embeddings | `nomic-embed-text-v1.5`, 768 dims, fixed in the DuckDB schema. |
| **006** | **B** — scripted external-drive backup | Now the *only* durability story, since Issue 015 removed the cloud copy. |
| **007** | **Local Gemma** | No Anthropic call in the extraction path. Requires grammar-constrained decoding and KV prefix reuse. Cost became wall-clock, not dollars. |
| **009** | **A** — evidence without a score if precision misses | Fallback pre-decided so Phase 5 cannot stall on it. |
| **011** | **A** — `audience_divergence` stays flagged evidence | Not an axis. |
| **013** | **Selection-triggered overlay** | Neither option as offered. Highlight is the query; resolves proposition-first, then topic, then subject-only. Smaller I2 surface and a far more precise query than page inference. Extension carries two depths in one surface. |
| **014** | **B** — deep-link, no in-app playback | Follows from 003. |
| **015** | **A** — drop Firestore | DuckDB is the single system of record. Sync contract, `synced_at`, reconciliation pass and security rules all deleted. No Firestore code was ever written, so this was docs-only. Access control collapses onto the local API's four controls. |
| **017** | **A** — wire every real external now | V2–V5 all unblocked and ordered ahead of any new phase. |
| **018** | **B** — fixtures split from corpus | V6 became a structural fix and moved ahead of V2–V5. Delivered. |
| **019** | *(open)* | Model pre-labelling of the golden corpus. Gates corpus *population*, not V6's structure. |
| **021** | **B**, refined to the four All-In hosts | Subjects for I0. Musk named but subsequently deferred by 023. |
| **022** | **A** — `SourceSubjectRole` join | `tier`/`venue_type`/`audience_stance`/`is_adversarial` move off `Source` onto a per-(source, subject) row. Adapter `tier` class attribute becomes `role(ref, subject)`. New integrity check `verify_role_coverage`. Scheduled as **S0, ahead of I0**, because the corpus is empty and this is the cheapest the migration will ever be. |
| **023** | **A** — defer Musk | Out of the queue until X ingest exists. His primary medium is deferred, and a long-form-only corpus would pass the sufficiency gate while measuring a skewed slice — I5 gates on volume, not composition. Side effect: with no guests in scope, 022 stops blocking I0. |

### What Phases 0–2 actually delivered

Verified in source on August 17, not from commit messages.

**Real:** the integrity pass (all eight checks, with `NOT APPLICABLE` correctly distinguished from `PASS`); DuckDB storage with genuine `vss`, `FLOAT[768]`, HNSW cosine indexing and deterministic IDs; three source adapters behind one Protocol; dual-pass reconciler logic; segmentation; the extraction gate; the five post-extraction validators. Falsification discipline was followed in every commit body.

**Stubbed, and previously reported as measured:** transcription, diarization, the extraction runtime, and embeddings. No external model dependency was ever declared. `tokens_per_second = 35.0` was a hardcoded literal printed as a measurement; `Precision 1.000 / Recall 1.000` came from 16 synthetic cases with one example per class. Tracked as Issues 017 and 018, and as V0–V5 in the execution guide.

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
