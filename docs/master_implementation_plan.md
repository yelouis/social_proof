# Social Proof — Master Implementation Plan

**What this is:** the big picture. Phases, invariants, and the shape of the system. Every detail lives in a `design_*.md` contract; this file exists so a reader knows what is being built and why, in under fifteen minutes.

**Status:** pre-implementation. No code exists yet. Open design decisions awaiting a selection are in `ongoing_errors.md`.

---

## 1. The one sentence

**Social Proof builds a dated timeline of what a person has actually said about a topic — from first-hand sources only — and scores how well their own record holds together.**

It never tells you whether someone is *right*. It tells you whether they have been *consistent*, whether they *owned* their changes of mind, and whether they apply their stated principles *evenly*. Those are three things you can determine without appealing to any outside authority, and that is the entire design thesis.

---

## 2. Why the constraints are the architecture

The project's defining constraint — **no news, no commentary, no secondary sources** — is usually stated as an editorial preference. It is not. It is what makes the system buildable and defensible by one person.

Excluding secondary sources turns Social Proof into a **closed-corpus self-consistency checker**. It needs no ground truth about the world. It never adjudicates a disputed fact. Its strongest possible claim is:

> Here are two things you said. Both verbatim. Both dated. Both sourced. They cannot both be your view.

That claim requires no journalism, no fact-checking partnership, and no editorial position. It is checkable by the reader in about ten seconds, because both quotes are on screen with links. A system that only ever makes that claim has a dramatically smaller surface for both error and liability than one that says "this person is wrong."

**Consequence, and it is load-bearing:** prediction scoring is **out of scope**. Grading a forecast requires knowing what actually happened, and outcomes come from exactly the sources being excluded. Do not add it. See §8.

---

## 3. Invariants

These are not preferences. Code that violates one of these is wrong even if it passes its tests.

| # | Invariant |
|---|---|
| **I1** | **First-hand only.** The corpus contains only utterances the subject produced. Never a paraphrase, never a report of what they said, never a summary. |
| **I2** | **News as index, never as evidence.** A news article may be read to determine *who* and *what topic*. Its content never enters the corpus and never influences a score. The article is a pointer; it is discarded after resolution. |
| **I3** | **Nothing renders without an anchor.** Every displayed claim carries a verbatim quote, a timestamp or document offset, and a resolvable source locator. A finding with no anchor is a bug, not a low-confidence result. |
| **I4** | **No external ground truth.** The system never evaluates whether a claim is true. It compares the subject only against themselves. |
| **I5** | **Corpus-sufficiency gate.** Below the evidence threshold for a (subject, topic) pair, the system emits `insufficient_corpus` — never a number. Absence of evidence is reported as absence, never as a poor score. |
| **I6** | **A reasoned update is a positive.** Changing position with a stated reason raises the record's standing. Only *unacknowledged* reversals cost. A system that punishes updating measures dogmatism, not trustworthiness. |
| **I7** | **Own assertions only.** A claim counts only if the subject was asserting it themselves. Quoting someone to disagree, hypotheticals, steelmanning, sarcasm, and jokes are excluded — and the exclusion is recorded, not silently dropped. |
| **I8** | **All writes go through the ingestion worker.** Clients read. They never write to the claim store. |
| **I9** | **Every quoted string must `grep -F` back to its stored source text.** Enforced by an automated pass, not by reviewer diligence. |
| **I10** | **No biometric identification.** Subjects are resolved by stated identity — name, handle, or supplied identifier. Never by face or voice matching against a stranger. Voice fingerprints are used *only* to attribute speech within a source to an already-known subject. |

---

## 4. System shape

Social Proof is **not an app**. It is a local analysis engine with a stable API and several thin clients. This shape is what makes the browser overlay, the desktop deep-dive, and any future ambient client the same product rather than three products.

```
┌──────────────────────────────────────────────────────────────┐
│  CLIENTS  (thin, read-only, all speak one contract)          │
│                                                              │
│   Browser extension        Flutter macOS app     [future]    │
│   overlay on any page      deep-dive timelines   ambient     │
└──────────────────────────┬───────────────────────────────────┘
                           │  localhost HTTP  (design_local_api_and_clients.md)
┌──────────────────────────┴───────────────────────────────────┐
│  ANALYSIS ENGINE   (Python, local)                           │
│  topic resolution · tension detection · principle conflict   │
│  · rubric computation · sufficiency gate                     │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│  STORE            (design_data_layer.md)                     │
│  Firestore  = system of record, canonical, client-readable   │
│  DuckDB     = local analytical mirror, vector search, joins  │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│  INGESTION WORKER  (Python, local — the only writer)         │
│  adapters → fetch → transcribe → diarize → attribute →       │
│  segment → extract claims → extract principles → embed       │
└──────────────────────────────────────────────────────────────┘
```

**Why Python owns the bottom half:** transcription (Whisper), diarization (pyannote), embeddings, and structured extraction are all Python-ecosystem problems. **Why Firestore is in the middle:** it is the system of record, it syncs, and it is what a Flutter client reads natively. **Why DuckDB sits beside it:** contradiction detection is a self-join over thousands of rows plus vector similarity, and Firestore has neither joins nor vector search. See `design_data_layer.md` for the sync contract and why the mirror is derived rather than authoritative.

---

## 5. Core entities

The whole system is this chain. Nothing floats free of it — that is what makes I3 and I9 enforceable.

```
Subject ──< Source ──< Utterance ──< Claim ──> Proposition ──< Topic
                                       │
                                       └────> Principle
```

| Entity | Is | Key property |
|---|---|---|
| **Subject** | A person being tracked | Resolved by stated identity, never by face |
| **Source** | One podcast episode, tweet, hearing, chapter | Carries venue, date, audience, and a permanent locator |
| **Utterance** | A contiguous span attributed to the subject within a source | Verbatim text + offset/timestamp. **The anchor for everything above it.** |
| **Claim** | One extracted position | Stance, hedging level, `is_own_assertion`, confidence — anchored to exactly one Utterance |
| **Proposition** | The canonical, deduplicated *thing being claimed* | The unit of comparison. Two claims contradict only if they share a Proposition. |
| **Principle** | The general rule a claim implies, with the actor left as a slot | Powers even-handedness (`design_principle_extraction.md`) |
| **Topic** | A cluster of Propositions | Free-text queries resolve to a set of these |
| **Tension** | A detected pair of Claims in conflict, with a type | Always carries both anchors |
| **Assessment** | A materialized rubric result for one (Subject, Topic) | Axis scores + the Tensions backing each |

**The single most important modelling decision:** the unit of comparison is a **Proposition**, not a topic. "Their view on AI regulation" is too coarse to compare against itself. Once each utterance is reduced to a canonical proposition plus a stance, contradiction detection stops being a fuzzy judgment call and becomes a database query — *same proposition, opposing stance, no intervening acknowledged update*. The model does the extraction; the database does the detection. That split is what makes results auditable and reproducible.

---

## 6. The rubric

Three axes, selected. A fourth is proposed and awaiting a decision — see **Issue 001** in `ongoing_errors.md`, which argues the current three are gameable without it.

| Axis | Measures | Fails when |
|---|---|---|
| **Consistency** | Unacknowledged stance reversals on shared Propositions | They said X, later said not-X, never marked the change |
| **Update Integrity** | When position changed, was the change acknowledged and reasoned? | They changed quietly, or claimed they never changed |
| **Even-handedness** | Is a stated Principle applied the same way regardless of the actor it lands on? | Same principle, different actor, opposite verdict |

Formulas, weighting, thresholds, and the sufficiency gate are specified in `design_rubric_engine.md`. Two properties are fixed here:

- **Scores are per (subject, topic), never global.** There is no "trustworthiness of a person." The product does not support the question.
- **Every axis score decomposes into the Tensions that produced it**, each openable to two verbatim quotes. A score the user cannot drill into is a bug.

---

## 7. Phases

Logic before surfaces. The golden corpus (`e2e_verification_journeys.md`) starts at Phase 2 and grows with every phase after it — there is no point building a detector you cannot measure.

### Phase 0 — Corpus spine
Subject, Source, Utterance. Ingest **one** person from **one** source type, end to end. Prove verbatim anchoring and the `grep -F` back-check (I9) before anything is built on top.
*Done when:* one subject's transcript is stored, every utterance resolves to a timestamp, and the integrity pass is green.

### Phase 1 — Source adapters
The adapter interface, then implementations: self-published (own channel/blog), guest appearances, institutional records, long-form authored. Diarization and speaker attribution. Provenance and the first-hand boundary rules.
*Contract:* `design_source_acquisition.md`

### Phase 2 — Claim extraction
Utterance → Proposition + stance + hedging. The I7 guards: reported speech, hypotheticals, sarcasm, steelmanning. Proposition canonicalisation and dedup.
*Contract:* `design_claim_extraction.md`. **Golden corpus starts here.**

### Phase 3 — Topic model
Cluster Propositions per subject. Resolve free-text topic queries to cluster sets. Cache resolution so scores are stable and repeatable across runs.
*Contract:* `design_topic_model.md`

### Phase 4 — Tension detection
Reversal detection over shared Propositions. Acknowledged-update detection, which is what separates I6's positive case from the negative one. Audience-divergence detection using venue metadata.
*Contract:* `design_rubric_engine.md` §Tension types

### Phase 5 — Principle extraction
Implied-principle extraction with an actor slot; principle clustering; conflict detection across actors. This powers Even-handedness and is the highest-risk component in the system.
*Contract:* `design_principle_extraction.md`

### Phase 6 — Rubric engine
Axis formulas, the corpus-sufficiency gate (I5), Assessment materialisation, and score decomposition into evidence.
*Contract:* `design_rubric_engine.md`

### Phase 7 — Local API
FastAPI on localhost. The one contract every client speaks. Subject resolution, topic resolution, assessment retrieval, evidence drill-down, ingest triggering.
*Contract:* `design_local_api_and_clients.md`

### Phase 8 — Browser extension
Page → who and what topic (I2: index only) → overlay the timeline and rubric in place. This is the primary consumer surface and the reason the whole system exists in the reading moment rather than the researching moment.

### Phase 9 — Flutter deep-dive client
macOS app for the long-form surface: full timelines, evidence browsing, corpus management, ingest queue. See **Issue 002** in `ongoing_errors.md` — the shift to an API-plus-thin-clients shape means Flutter is now one surface among several rather than *the* app, and that deserves an explicit selection.
*Contract:* `design_ui_direction.md`

### Phase 10 — Head-to-head comparison
Exactly two subjects, one shared time axis, divergence points marked. Plus single-axis ranked lists. The N-way dashboard is a deliberate non-goal (§8).

---

## 8. Deliberately not built — do not re-propose

Each of these was considered and rejected for a stated reason. Re-proposing one costs a cycle.

| Not building | Why |
|---|---|
| **Prediction / forecast scoring** | Requires outcome data, which requires the excluded sources. Breaks I4 at the root. |
| **Fact-checking of any kind** | The system's defensibility comes from never asserting what is true. |
| **A single global trust score per person** | Collapses "never says anything falsifiable" and "consistently wrong" into similar numbers. The product does not support the question. |
| **Radar / spider charts for comparison** | Enclosed area is meaningless and axis ordering changes the shape. Head-to-head pairs instead. |
| **N-way comparison dashboards** | The overwhelm problem. Pairs, or a ranked list on one axis. |
| **Face or voice recognition of strangers** | Processes biometrics of everyone in frame *before* consent can be established. Illegal under Illinois BIPA, Texas CUBI, and GDPR Art. 9 regardless of opt-in design; no supported API on consumer AR hardware. Violates I10. |
| **Scoring private individuals from thin corpora** | The engine needs thousands of dated statements. Forty tweets does not produce a weak score — it produces a *confident* score computed on noise. Blocked by I5. |
| **Unofficial X/Twitter scraping** | ToS violation, brittle, and makes the most fragile component load-bearing. Deferred behind the adapter interface instead. |

---

## 9. Deferred — designed for, not built

These are not rejected. The data model and adapter interface must accommodate them, and nothing else should be built in a way that blocks them.

- **X/Twitter ingest.** Deferred by decision, not by difficulty. The source adapter interface must accept it as a drop-in — an official API adapter and an archive-import adapter, both behind the same interface.
- **Self-published opt-in corpora.** The inversion of the ambient idea: a person voluntarily publishes their own verifiable claim history as a portable record they control and benefit from. Same engine, same rubric, subject-owned. This is the only consent-clean path to non-public-figure subjects, and it is just another source adapter. Design the `Subject` model so a self-asserted corpus is a first-class source type.
- **Ambient client.** Viable *only* against stated identity (I10) and *only* for subjects who clear the sufficiency gate (I5). Under those two constraints it is a thin client on the Phase 7 API, not a new system.

---

## 10. Where the detail lives

| Question | Document |
|---|---|
| What counts as first-hand? How is audio ingested? | `design_source_acquisition.md` |
| How does an utterance become a structured claim? | `design_claim_extraction.md` |
| How is even-handedness actually computed? | `design_principle_extraction.md` |
| How is a "topic" defined and resolved? | `design_topic_model.md` |
| What are the axis formulas and tension types? | `design_rubric_engine.md` |
| Firestore schema, DuckDB mirror, sync | `design_data_layer.md` |
| The API contract and the clients | `design_local_api_and_clients.md` |
| Timelines, head-to-head, citation rendering | `design_ui_direction.md` |
| The anti-defamation contract | `design_evidence_integrity.md` |
| Golden corpus and end-to-end journeys | `e2e_verification_journeys.md` |
| What to build next, in order, with validation | `agent_execution_guide.md` |
| Open decisions awaiting a selection | `ongoing_errors.md` |
