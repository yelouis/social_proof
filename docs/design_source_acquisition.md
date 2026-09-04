# Source Acquisition & The First-Hand Boundary

**Contract for:** Phase 1. Owns everything from "we want to track this person" to "verbatim, dated, attributed utterances are in the store."

**Why this doc is long:** acquisition is where the project lives or dies, and it is where the two worst possible bugs live — **misattributing someone else's words to the subject**, and **a transcription error that manufactures a contradiction**. Both produce a confident, well-cited, completely false accusation against a real named person. Everything downstream is arithmetic; this layer is the only place the system touches reality.

---

## 1. The admissibility rule

An utterance is admissible if and only if **all three** hold:

1. **Verbatim.** The stored text is the words the subject produced, not a summary, paraphrase, or characterisation of them.
2. **Durably anchored.** It derives from an artifact that still exists and can be re-checked — audio, video, the subject's own published text, or an official transcript produced by the body that recorded it.
3. **Attributed by a stated method.** *How* we know the subject said it is recorded on the row, with a confidence value. "It was in their feed" and "voice-matched at 0.91 against enrollment" are both valid; neither is assumed.

Anything failing one of the three is not "low quality." It is **inadmissible** and does not enter the corpus.

---

## 2. Source tiers

All four tiers are in bounds. They differ in attribution difficulty and in how much the venue shapes what was said — both of which get recorded, because audience-divergence detection (`design_rubric_engine.md`) reads them.

| Tier | What | Attribution | Notes |
|---|---|---|---|
| **A** | **Self-published text** — their X account, blog, Substack, newsletter | Account-level, near-certain | Words *and* venue are theirs. The cleanest signal in the system. |
| **B** | **Self-published audio/video** — their own podcast, YouTube channel | Diarization needed if multi-speaker | Venue is theirs; audience is self-selected and friendly. Record that. |
| **C** | **Guest appearances** — someone else's podcast, stream, panel, conference | **Diarization + voice ID required** | Where most substantive opinion actually lives, and the highest misattribution risk. Venue metadata is essential. |
| **D** | **Institutional records** — congressional testimony, depositions, earnings calls, regulatory filings, official statements under their name | Official transcript, speaker-labelled | Highest-value contradiction fodder: on the record, adversarial, and already transcribed. |
| **E** | **Long-form authored** — books, papers, whitepapers, published letters | Byline, with a caveat | Ghostwriting and co-authorship are real. Requires `authorship_confidence`; a co-authored paper is not a personal assertion. |

### Venue metadata — per (source, subject), not per source

**Issue 022 = A.** Venue is a property of the *relationship* between a subject and a source, not of either alone. A four-host podcast is `own_channel` for its hosts and `guest` for whoever visits — in the same episode. These live on a `SourceSubjectRole` row (`design_data_layer.md` §2), one per subject present in the source:

```
tier            : A | B | C | D | E
venue_type      : own_channel | guest | institutional | authored | self_published_text
audience_stance : friendly | neutral | adversarial | unknown
is_adversarial  : bool     # was THIS subject being challenged?
```

These stay on the Source, because they describe the artifact:

```
interlocutor    : free text, null for solo
recorded_at     : ISO 8601, timezone-explicit — the ORIGINAL recording date
published_at    : ISO 8601
```

**Ingest writes one role row per subject it finds in a source.** An utterance attributed to a subject with no role row for that source is an orphan, and the integrity pass fails on it.

`audience_stance` and `is_adversarial` are what make "says one thing on a friendly show, another under hostile questioning, same week" detectable. Without them that signal is invisible.

---

## 3. Explicitly inadmissible

This list is the operational form of invariant **I1**. It is not a filter to be tuned; these never enter the corpus.

| Excluded | Why |
|---|---|
| News articles, op-eds, or analysis **about** the subject | Not their words. Invariant I1. |
| **A quote of the subject inside an article** | Looks first-hand and is not. The publication chose the excerpt, the surrounding framing, and often trimmed the sentence. There is no durable artifact to re-check against — fails rule 2. Get the underlying recording or drop it. |
| Wikipedia, encyclopaedias, summaries, fact-checks | Secondary by definition. |
| Statements by a spokesperson, press office, or campaign | Not the subject's words unless personally signed — then Tier D with reduced `authorship_confidence`. |
| **Bare retweets / reshares with no added text** | Endorsement is ambiguous and the words are someone else's. For a quote-post, **only the subject's added text** is the utterance; the quoted content is context stored on the Source, never a Claim. |
| Machine translations of the subject's speech | The stance-bearing words are a model's, not theirs. Store the original-language utterance; translate at display time only, flagged. |
| Any audio whose authenticity is unverified | Synthetic speech is cheap now. A clip with no provenance chain to a publisher is not evidence. |

### The news-as-index rule (invariant I2), operationally

The browser extension will send page text to the local API. That text is used **only** to resolve *which subject* and *which topic*, and then discarded.

- Article text lives in a **request-scoped buffer**. It is never written to DuckDB or the artifact store.
- No `Source`, `Utterance`, `Claim`, or embedding may be derived from it.
- **Enforced by test**, not by discipline: after an extension-originated resolution request, assert that no row anywhere in the store has `origin = 'page_context'`. See `e2e_verification_journeys.md`.

---

## 4. The adapter interface

Every source type implements one interface. X/Twitter is deferred (`master_implementation_plan.md` §9) but must drop in here without touching anything else — that is the entire point of the abstraction.

```python
class SourceAdapter(Protocol):

    def role(self, ref: SourceRef, subject: Subject) -> SourceSubjectRole:
        """Tier and venue for THIS subject in THIS source (Issue 022 = A).
        The same episode is Tier B / own_channel for a host and
        Tier C / guest for a visitor. An adapter has no single tier."""

    def discover(self, subject: Subject, since: datetime | None) -> Iterable[SourceRef]:
        """Find candidate sources. Cheap, metadata only, no media fetched."""

    def fetch(self, ref: SourceRef) -> RawSource:
        """Retrieve the artifact. Idempotent and cached by content hash."""

    def normalize(self, raw: RawSource) -> NormalizedSource:
        """Audio → 16 kHz mono; text → UTF-8 with byte offsets preserved."""

    def provenance(self, ref: SourceRef) -> Provenance:
        """How we know this is the subject. Never inferred by the pipeline."""
```

**Planned adapters:** `YouTubeAdapter` (yt-dlp), `PodcastRSSAdapter` (feed + enclosure), `CongressionalRecordAdapter`, `SECFilingAdapter`, `EarningsCallAdapter`, `SubstackAdapter`, `EPUBAdapter`. **Deferred:** `XAPIAdapter`, `XArchiveImportAdapter`, `SelfPublishedCorpusAdapter` (the opt-in path).

**Never build:** an adapter that reads a news site. There is no configuration under which that is correct.

---

## 5. Pipeline

```
discover → fetch → normalize → transcribe → diarize → attribute → segment → persist
                                    │            │          │
                                    │            │          └── below threshold ⇒ quarantine
                                    │            └── pyannote.audio speaker turns
                                    └── word-level timestamps REQUIRED
```

### 5.1 Fetch and cache

Cache by **content hash**, not URL. Podcast feeds re-issue URLs; CDNs rotate them. Never re-fetch or re-transcribe an artifact whose hash is known. Respect `robots.txt` and rate limits; ingest is a background job with no deadline, so back off generously rather than parallelising hard.

### 5.2 Transcription

**Word-level timestamps are mandatory.** They are the anchor that makes invariant I3 enforceable, and — under Issue 003 Option C, where the audio is deleted — they are the *only* thing that lets a citation deep link point at the right second. A transcript without them is unusable here regardless of its accuracy.

Recommended: `faster-whisper` with `large-v3` locally — free, private, and fast enough on Apple Silicon that a 3-hour episode is a background task, not a bill. Fall back to a hosted API only for backlog burst.

**Guards that are not optional:**

- **VAD-gate the input.** Whisper hallucinates fluent text over silence and music. Voice-activity detection before transcription removes most of it.
- **Drop utterances with no corresponding audio energy.** A transcript segment over a silent span is a hallucination, full stop.
- **Audio is deleted after transcription** (Issue 003, Option C). What survives is the transcript, the word timestamps, and a **citation deep link** — a URL that opens the original source at the right offset. Disk per subject drops from ~3 GB to ~70 MB.
- **Productivity gate — success is output.** `audio_deleted_at` and `ingested_at` may only be set if the source produced $\ge 1$ utterance. An empty run qualifies as a failure, never success: the audio file on disk is preserved, `audio_deleted_at` remains null, and the job is marked failed. Deleting audio after an empty extraction is silent data loss (Trap 25).
- **Every Source therefore carries `citation_url_template`**, and every Utterance can render a deep link at its own offset. Format is per-adapter: YouTube `…&t=1234s`, podcast enclosure `…#t=1234`, institutional transcripts by paragraph anchor. An adapter that cannot produce a deep link must say so explicitly (`citation_url_template: null`) rather than emitting a bare source URL that lands the reader at 00:00 with no way to find the quote.
- **The consequence you must design around:** once audio is gone it cannot be re-transcribed. Every check that needs audio has to run **during ingest, while the file is still on disk**. See §5.3 — this is not a detail, it reshapes the pipeline.

### 5.3 The negation trap

> **A transcription error that drops a negation manufactures a contradiction.**

"I don't think we should regulate this" transcribing as "I think we should regulate this" produces a *perfect* false positive: correct speaker, correct topic, correct date, opposite stance. It will look exactly like a real finding and it will be completely wrong.

Mitigations, all required:

1. **Dual-pass transcription at ingest time, on every source, before the audio is deleted.** Two passes with different decoding parameters (differing beam size and temperature — not the same call twice, which just reproduces the same error). Under the retain-audio policy this check could have been deferred until a Tension appeared; under Issue 003 Option C **there is no later**. Every source pays for two passes, always.
2. **Reconcile at the span level and store the result.** Where the passes agree, store the text and mark `dual_pass_agreement: true`. Where they disagree **anywhere inside a span containing a negation cue** (`not`, `n't`, `never`, `no`, `without`, `hardly`, `fails to`, `rather than`), store the pass-1 text but mark the utterance `negation_uncertain: true`. That flag is permanent — it can never be re-checked.
3. **A `negation_uncertain` utterance may never produce a published Tension.** Any Tension with such an utterance on either side is quarantined with reason `negation_uncertain`. The claim still exists and still appears on the timeline; it just cannot be half of an accusation.
4. **Never let a single transcription pass produce a published accusation.** This is now enforced structurally, because the second pass is the only chance the pipeline gets.

**Cost of the policy:** transcription time doubles (~2 passes × real-time-fraction), paid once per source. On Apple Silicon with `faster-whisper` `large-v3` this is background compute, not money. That is the trade Issue 003 Option C makes: 40× less disk, 2× the one-time compute, and no ability to ever re-check.

### 5.4 Diarization and speaker attribution

This is the highest-risk step in the system. Misattributing the host's words to the guest generates a false contradiction against a real named person.

**Runtime — Issue 020 = Option A.** Diarization runs on `pyannote.audio`, whose pretrained pipelines are gated on Hugging Face. **The token is read from the `HF_TOKEN` environment variable and never committed.** A missing token must fail loudly at pipeline construction with a message naming the variable and the model card to accept — never fall back to a heuristic diarizer, because a silent downgrade here produces misattributed speech, which is the worst bug in the product (§5.4).

**Enrollment.** Each subject has a reference voice embedding, built from a source where attribution is certain — their own solo podcast, or a hand-verified clip. Enrollment is a deliberate, recorded act, never a by-product of ingest.

**Attribution rules:**

- Diarize into speaker turns, then match each speaker cluster to enrollment by embedding similarity.
- **Above the high threshold** ⇒ attributed, `attribution_confidence: high`.
- **Between thresholds** ⇒ stored with `attribution_confidence: low`, and **excluded from all scoring**. Visible in a review queue; never counted.
- **Below the low threshold** ⇒ not the subject. Discarded from the subject's corpus.
- **Never attribute by turn order, position, or "the guest speaks second."** Interruptions, three-way panels, and clip shows break every positional heuristic, and they break it silently.
- **Single-speaker sources still get a check.** A "solo" episode with a surprise guest is common.

**Thresholds are not guessed.** They are set from the golden corpus (`e2e_verification_journeys.md`) by measuring the false-attribution rate directly, and the target is asymmetric: **a missed utterance costs nothing; a misattributed one is the worst bug in the product.** Tune for precision, accept the recall loss.

### 5.5 Segmentation

Merge contiguous same-speaker turns into utterances, splitting on long pauses and at a maximum length. Each Utterance persists:

```
source_id · speaker_label · attribution_confidence · attribution_method
text_verbatim · start_ms · end_ms · word_timestamps
transcription_model · transcription_pass_count · language
```

`text_verbatim` is immutable. Cleanup, normalisation, and translation all happen downstream on copies. **Invariant I9's `grep -F` check runs against this field**, so anything that rewrites it breaks the integrity pass by construction — which is the intent.

---

## 6. Ingest is per-person, once, forever

The cost model is friendly and the design should lean on it: **ingesting a subject is a bounded one-time job, then a small incremental tail.** A figure with five years of podcasts might be 300 hours of audio — an overnight run locally, then an hour a week to stay current.

- Ingest is **on demand**, triggered per subject. Nothing crawls continuously.
- Everything is cached by content hash and **never recomputed**.
- Re-running ingest on a subject is idempotent and cheap; only new sources do work.
- Model upgrades are the one exception, and they are a deliberate, versioned re-run — every row records `transcription_model`, so a re-run is scoped to rows below the new version rather than the whole corpus.

---

## 7. Failure modes to design against

| Failure | Consequence | Mitigation |
|---|---|---|
| Whisper hallucinates over music/silence | Fabricated quote, fully "sourced" | VAD gate; drop zero-energy spans |
| Dropped negation | **Perfect false contradiction** | §5.3 — two-pass re-check on any claim in a Tension |
| Host's words attributed to guest | False accusation against a real person | §5.4 — voice ID, precision-biased thresholds, no positional heuristics |
| Clip show / re-aired archive audio | Old statement dated as new; false "reversal" | Date from *original* recording, not publication. Detect re-used audio by content hash. |
| Ghostwritten book | Personal assertion that isn't personal | Tier E carries `authorship_confidence`; below threshold, excluded from scoring |
| Feed re-issues URLs | Duplicate ingest, doubled evidence weight | Cache by content hash, never URL |
| Synthetic/deepfaked audio | Fabricated evidence | Provenance chain to a known publisher required; unverified audio is inadmissible |
| Sarcasm in a serious register | False stance | Not solvable here — handled at extraction (`design_claim_extraction.md` §I7 guards) |

---

## 8. Open decisions

Tracked in `ongoing_errors.md`; they change what gets built in this layer.

- **Issue 003** — audio retention policy and disk budget.
- **Issue 004** — attribution thresholds, and whether low-confidence utterances are visible at all or hidden entirely.
