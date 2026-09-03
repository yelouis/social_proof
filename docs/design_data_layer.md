# Data Layer — Storage & Schema

**Contract for:** the store. Read before writing any persistence code.

> **Issue 015 = Option A — Firestore is dropped.** DuckDB is the single system of record. There is no publish path, no `synced_at` bookkeeping, no reconciliation pass, and no security rules to maintain. Firestore's two original justifications — sync, and native client reads for Flutter — were both removed by later decisions: clients read the local HTTP API rather than a database, and Issue 002 deferred Flutter. What remained was a sync contract with no consumer.
>
> **The collection paths below are retained as the logical schema.** They document entity nesting and field names, which the DuckDB tables mirror. Read `subjects/{id}/claims/{id}` as "the claims belonging to a subject," not as a Firestore path.

---

## 1. Two layers, two jobs

There are two places data lives, and confusing them is the most likely source of a hard bug in this system.

| Layer | Holds | Authority | If you lose it |
|---|---|---|---|
| **Artifact store** — local disk, content-addressed | Compressed audio, raw transcripts **with word timestamps**, extraction prompt/response logs | **Irreplaceable without re-fetching the internet.** Back this up. | Re-download and re-transcribe everything. Expensive and sometimes impossible — sources get deleted. |
| **DuckDB** — one local file | Every structured row, **plus embeddings as vectors**, plus the analytical indices | **System of record.** "Stored" means "in DuckDB." | Rebuild from the artifact store by re-running extraction. Expensive in compute, but no source data is lost. |

**Why word timestamps do not go in DuckDB rows:** a three-hour episode has ~30k words. Word-level timing is a re-verification and anchoring asset read in bulk, not a field rendered on a card. It lives on disk as Parquet, referenced by hash, and DuckDB reads it directly when needed.

**Why DuckDB and not something simpler:** contradiction detection is a self-join over thousands of rows plus vector similarity. That combination is the entire workload, and DuckDB does both in one process against one file with no server. A document store could hold the rows but could not run the query; a plain vector index could run the similarity but not the join.

**Backups matter more now.** With no cloud copy, Issue 006's scripted external-drive backup is the *only* durability story. It covers both the DuckDB file and the artifact store.

---

## 2. Schema (logical)

```
subjects/{subject_id}
  display_name, aliases[], handles{platform: handle}
  enrollment_ref            # artifact hash of the reference voice sample
  corpus_stats{source_count, utterance_count, claim_count, earliest, latest}
  created_at, updated_at

  sources/{source_id}          # facts about the ARTIFACT only
    title, publisher, canonical_url, artifact_hash
    citation_url_template   # e.g. "https://youtu.be/ID?t={seconds}" — null if the
                            # platform has no deep link. NEVER a bare URL that
                            # lands the reader at 00:00. (Issue 003 Option C)
    interlocutor
    recorded_at             # the ORIGINAL recording date, not publication
    published_at
    authorship_confidence   # Tier E only
    ingest_job_id, transcription_model, ingested_at
    audio_deleted_at        # audio is not retained; this records when it went

  source_roles/{role_id}       # id = sha256(source_id | subject_id)[:16]
    source_id, subject_id      # Issue 022 = A: tier and venue are properties
    tier                       # of the (source, subject) PAIR, not of either
    venue_type                 # side alone. One All-In episode is Tier B /
    audience_stance            # own_channel / friendly for its four hosts and
    is_adversarial             # Tier C / guest for a guest, simultaneously.

  utterances/{utterance_id}
    source_id
    text_verbatim           # IMMUTABLE. Invariant I9 greps against this.
    start_ms, end_ms
    speaker_label, attribution_confidence, attribution_method
    word_timestamps_ref     # artifact hash → Parquet on disk. Not inlined.
                            # With audio deleted, this is the ONLY thing that can
                            # place a citation link at the right second.
    language, transcription_pass_count
    dual_pass_agreement     # bool — the two ingest-time passes matched on this span
    negation_uncertain      # bool — passes disagreed near a negation cue.
                            # PERMANENT: audio is gone, it can never be re-checked.
                            # Bars this utterance from any published Tension.

  claims/{claim_id}
    utterance_id, proposition_id
    stance                  # support | oppose | mixed | hedge
    hedging_level           # 0.0 flat assertion … 1.0 pure hedge
    is_own_assertion        # false ⇒ excluded from scoring, retained for review
    exclusion_reason        # reported_speech | hypothetical | sarcasm | steelman | joke | null
    confidence
    quote_span              # [start_char, end_char] into text_verbatim
    extraction_model, prompt_version

  topics/{topic_id}           # per-subject clusters
    label, proposition_ids[], global_topic_id (nullable)

  tensions/{tension_id}
    type                    # unacknowledged_reversal | acknowledged_update
                            # | principle_conflict | audience_divergence
    claim_a_id, claim_b_id
    proposition_id | principle_id
    severity, detector_version
    status                  # published | quarantined | dismissed
    quarantine_reason

  assessments/{assessment_id}   # id = hash(topic_id + rubric_version)
    topic_id, rubric_version, extraction_model_set
    sufficiency{passed, claim_count, source_count, span_days, threshold_set}
    axes{consistency, specificity, update_integrity,       # each: score | null
         even_handedness}                                  # + reason when null
    axis_evidence{axis: [tension_id]}
    computed_at

propositions/{proposition_id}      # GLOBAL, not per-subject
  canonical_text, embedding_ref, subject_ids[], claim_count

principles/{principle_id}          # GLOBAL
  canonical_text                   # actor left as a slot
  actor_slot_examples[], embedding_ref, subject_ids[]

ingest_jobs/{job_id}
  subject_id, adapter, status, stage, counts{}, errors[], started_at, finished_at
```

**Why `source_roles` exists.** `tier`, `venue_type`, `audience_stance` and `is_adversarial` used to sit on `Source`, one value per source. That is wrong for any source with more than one subject in it — and `audience_stance` feeds audience-divergence detection (`design_rubric_engine.md` §6), so a single stamped value produces a wrong *finding* rather than a cosmetic mislabel. Every reader of venue metadata joins through this table.

**Propositions and principles are global, not nested under a subject.** That is deliberate and it is what makes Phase 10 head-to-head comparison possible: two people can only be compared on a topic if they are being measured against *the same propositions*. Nesting them per subject would forfeit that permanently.

---

## 3. Deterministic IDs

Every ID is derived from content. This is what makes re-ingest idempotent for free.

```
source_id      = sha256(canonical_locator)[:16]
utterance_id   = sha256(source_id | start_ms | text_verbatim)[:16]
proposition_id = sha256(canonical_text_normalized)[:16]
claim_id       = sha256(utterance_id | proposition_id | stance | extraction_version)[:16]
principle_id   = sha256(canonical_text_normalized)[:16]
role_id        = sha256(source_id | subject_id)[:16]
tension_id     = sha256(sorted(claim_a_id, claim_b_id) | type)[:16]
assessment_id  = sha256(subject_id | topic_id | rubric_version)[:16]
```

Consequences worth stating plainly, because they remove whole categories of bug:

- **Re-running ingest writes the same IDs**, so every write is an upsert and nothing duplicates.
- **A feed that re-issues its URLs cannot produce a duplicate source**, because the locator is canonicalised and the audio is hashed.
- **The same tension cannot be reported twice** under a different id ordering, because the claim pair is sorted before hashing.
- **Changing the rubric produces a new assessment id** rather than overwriting the old one. See §6.
- **Re-extracting under an improved prompt or model produces new claim ids**, because `extraction_version` — the tuple `(model_id, prompt_version, schema_version)` — is part of the hash. Old claims stay inert and auditable instead of colliding with, or silently duplicating, the new ones. Every query filters to the active extraction version. See `design_claim_extraction.md` §9.

---

## 4. DuckDB tables

```sql
-- The store itself. Field names mirror the logical schema in §2.
CREATE TABLE utterances (
  utterance_id VARCHAR PRIMARY KEY, subject_id VARCHAR, source_id VARCHAR,
  text_verbatim VARCHAR, start_ms BIGINT, end_ms BIGINT,
  attribution_confidence DOUBLE, recorded_at TIMESTAMPTZ,
  dual_pass_agreement BOOLEAN, negation_uncertain BOOLEAN
);

CREATE TABLE claims (
  claim_id VARCHAR PRIMARY KEY, subject_id VARCHAR, utterance_id VARCHAR,
  proposition_id VARCHAR, stance VARCHAR, hedging_level DOUBLE,
  is_own_assertion BOOLEAN, exclusion_reason VARCHAR,
  recorded_at TIMESTAMPTZ
);

-- 768 dims: nomic-embed-text-v1.5, run locally (Issue 005, Option A).
-- The width is FIXED here. Changing the embedding model re-embeds every
-- proposition and principle and invalidates every cached topic resolution.
CREATE TABLE proposition_embeddings (
  proposition_id VARCHAR PRIMARY KEY, embedding FLOAT[768]
);

INSTALL vss; LOAD vss;
CREATE INDEX prop_hnsw ON proposition_embeddings
  USING HNSW (embedding) WITH (metric = 'cosine');
```

`recorded_at` is denormalised onto `claims` specifically so reversal detection is a single self-join with no source lookup:

```sql
-- The core detector, in full. This query is why the store is DuckDB.
SELECT a.claim_id, b.claim_id, a.proposition_id
FROM claims a JOIN claims b
  ON a.proposition_id = b.proposition_id
 AND a.subject_id     = b.subject_id
 AND a.recorded_at    < b.recorded_at
 AND a.stance <> b.stance
WHERE a.is_own_assertion AND b.is_own_assertion
  AND a.stance IN ('support','oppose') AND b.stance IN ('support','oppose');
```

That query is a self-join plus a vector lookup. Any store that cannot serve both is the wrong store — if you find yourself pulling the whole claims table into Python to run it, escalate rather than implement it.

---

## 5. Write and read paths

**One store, one writer, no sync.**

```
Worker  ──write──▶  DuckDB  ◀──read──  Analysis engine
                      │
                      └────read────▶  Local API  ──▶  clients
```

- **The ingestion worker is the only writer** (invariant I8). It writes in a single transaction per unit of work; DuckDB's transactional guarantee is the whole durability story, and a crash mid-write rolls back cleanly.
- **The analysis engine reads DuckDB directly**, in-process.
- **Clients never open DuckDB.** They read the local HTTP API, which is the only thing that ever renders a row to a client (`design_local_api_and_clients.md`).

**Resumability** comes from deterministic IDs (§3) rather than from bookkeeping: re-running an interrupted job re-derives the same IDs, so every write is an idempotent upsert and the job simply picks up where it stopped. There is nothing to reconcile.

**Concurrency.** DuckDB permits one writer. Run ingest as a single worker process; if parallel adapters are ever added, they fan out on *fetch and transcribe* and funnel through one writer at the end.

---

## 6. Versioning — a score is only comparable to itself

Every derived row records the machinery that produced it: `extraction_model`, `prompt_version`, `detector_version`, `rubric_version`, `embedding_model`, and `nlp_version` (the pinned NER tagger behind Specificity — `design_rubric_engine.md` §2A).

> **A score computed under a different rubric version is not comparable to one computed under another. Not "roughly comparable." Not comparable.**

Rules:

- Changing an axis formula, a threshold, or an extraction prompt **bumps a version**.
- A bumped version produces a **new** assessment document; the old one is retained, not overwritten.
- **Every displayed score states its rubric version.** A number on screen with no version is a bug.
- Head-to-head comparison (Phase 10) **must refuse** to compare two assessments computed under different versions. Recompute, or decline.

This is what stops the system from silently drifting into "scores went up last month" when what actually happened was a prompt edit.

---

## 7. Access control

There are no database security rules to write, because there is no database server — the store is a file on your disk, protected by filesystem permissions.

That moves the entire access-control surface to **one place: the local HTTP API.** A `127.0.0.1` server is reachable by any web page the user has open, so `design_local_api_and_clients.md` §2 is now the *only* thing standing between a hostile page and the corpus. Its four controls — loopback bind, bearer token, strict CORS, and read-only endpoints — are load-bearing rather than defence-in-depth.

Invariant I8 is likewise enforced structurally rather than declaratively: the API exposes no write endpoints, and only the worker process opens the DuckDB file for writing.

---

## 8. What must never be stored

| Never stored | Enforcement |
|---|---|
| **Article text from the extension** (`origin = 'page_context'`) | Request-scoped buffer only. Asserted by test after every extension-originated request — invariant I2, `e2e_verification_journeys.md`. |
| Any derived row traceable to page context | Provenance chain check in the integrity pass |
| Mutated `text_verbatim` | The `grep -F` pass (I9) fails by construction if it is rewritten |
| Voice embeddings of anyone who is not an enrolled subject | Diarization clusters are discarded after attribution — invariant I10 |
| Scores below the sufficiency gate | `axes.*` is `null` with `sufficiency.passed = false`; a number is never written and then hidden — invariant I5 |

That last one matters more than it looks. If a score is computed and stored but suppressed at render time, some future client will render it. Do not compute it.

---

## 9. Open decisions

- **Issue 005** — embedding model and dimension, which fixes the DuckDB vector width and is expensive to change later.
- **Issue 006** — whether the artifact store is backed up to cloud storage, and what that costs at a realistic corpus size.
