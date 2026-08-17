# Social Proof

**A closed-corpus self-consistency engine.** It builds a dated timeline of what a person has actually said about a topic — from first-hand sources only — and scores how well their own record holds together.

> **Status: design only.** There is no code in this repository yet. What's here is a complete implementation specification: twelve design contracts, a decision log, a verification plan, and a build guide written for an engineering agent with no prior context.

---

## What it does, and what it deliberately doesn't

It never tells you whether someone is **right**. It tells you whether they have been **consistent**, whether they **owned** their changes of mind, whether they apply their stated principles **evenly**, and whether they say anything **checkable** in the first place.

Those four things can be determined without appealing to any outside authority, and that is the entire design thesis.

The defining constraint — **no news, no commentary, no secondary sources** — is usually read as an editorial preference. It isn't. Excluding secondary sources makes this a closed-corpus consistency checker that needs no ground truth about the world and never adjudicates a disputed fact. Its strongest possible claim is:

> Here are two things you said. Both verbatim. Both dated. Both sourced. They cannot both be your view.

That claim needs no journalism and no editorial position, and a reader can check it in about ten seconds because both quotes are on screen with links.

**Explicit non-goals:** fact-checking, prediction scoring, a single composite "trust score," face recognition, scoring private individuals from thin corpora, and share cards that strip a number from its evidence. Each is rejected for a stated reason in [`docs/master_implementation_plan.md`](docs/master_implementation_plan.md) §8.

---

## The four axes

| Axis | Measures | Fails when |
|---|---|---|
| **Consistency** | Unacknowledged stance reversals on shared propositions | They said X, later said not-X, never marked the change |
| **Specificity** | Share of claims that are concrete and checkable | They speak entirely in hedges — which would otherwise score as perfect integrity |
| **Update Integrity** | When position changed, was it acknowledged and reasoned? | They changed quietly, or claimed they never changed |
| **Even-handedness** | Is a stated principle applied the same way regardless of who it lands on? | Same principle, different actor, opposite verdict, no distinction given |

Scores are always per `(subject, topic)`. There is no "trustworthiness of a person" — the product does not support the question.

**No language model runs at scoring time.** The only generative model in the system is the claim extractor; everything above it is arithmetic over structured rows. That is what makes any score reproducible byte-for-byte and recomputable by hand. See [`docs/design_rubric_engine.md`](docs/design_rubric_engine.md) §0.

---

## Architecture

A local analysis engine with one HTTP contract and several thin clients.

```
CLIENTS      browser extension · desktop app · (future) ambient
                              │  localhost HTTP
ANALYSIS     topic resolution · tension detection · rubric · sufficiency gate
                              │
STORE        DuckDB (vectors, joins) · artifact store (transcripts, timestamps)
                              │
INGEST       adapters → transcribe → diarize → attribute → extract → embed
```

Python owns ingestion and analysis (Whisper, pyannote, local Gemma, embeddings). Clients are read-only and contain no detection logic — if a client ever needed to know what makes two statements contradictory, the boundary would be in the wrong place.

---

## Evidence discipline

The system makes claims about real, named people, so the integrity rules are load-bearing rather than decorative — a finding you have to double-check is worth nothing.

- Every displayed claim carries a verbatim quote, a date, and a resolvable source link.
- **Every quoted string must `grep -F` back to its stored source text.** Automated; a failure breaks the build.
- Below a per-axis evidence floor the system emits `insufficient_corpus` — and the number is **never computed**, not computed-and-hidden.
- A reasoned change of mind **raises** the score. A system that punishes updating measures dogmatism, not trustworthiness.
- Quoting someone to disagree, hypotheticals, steelmanning, and sarcasm are excluded — and the exclusion is *recorded*, so the false-exclusion rate is measurable.
- One conflicting pair is never reported as hypocrisy. Only a pattern that survives a significance test is.

Full contract: [`docs/design_evidence_integrity.md`](docs/design_evidence_integrity.md).

---

## Documentation

| Doc | Covers |
|---|---|
| [`master_implementation_plan.md`](docs/master_implementation_plan.md) | Invariants, system shape, phases, non-goals |
| [`agent_execution_guide.md`](docs/agent_execution_guide.md) | Zero-context build guide: known traps, work items, validation, falsification |
| [`ongoing_errors.md`](docs/ongoing_errors.md) | Decision log — options, trade-offs, selections, and parameters that must be *measured* rather than chosen |
| [`design_source_acquisition.md`](docs/design_source_acquisition.md) | The first-hand boundary, ingest pipeline, transcription safeguards |
| [`design_claim_extraction.md`](docs/design_claim_extraction.md) | Utterance → proposition + stance; speech-act guards |
| [`design_principle_extraction.md`](docs/design_principle_extraction.md) | The even-handedness machinery |
| [`design_topic_model.md`](docs/design_topic_model.md) | Clustering and free-text topic resolution |
| [`design_rubric_engine.md`](docs/design_rubric_engine.md) | Axis formulas, tension types, sufficiency gates |
| [`design_data_layer.md`](docs/design_data_layer.md) | Schema, deterministic IDs, versioning |
| [`design_local_api_and_clients.md`](docs/design_local_api_and_clients.md) | API contract, security, the news-as-index boundary |
| [`design_ui_direction.md`](docs/design_ui_direction.md) | Timelines, tension cards, rendering absence |
| [`design_evidence_integrity.md`](docs/design_evidence_integrity.md) | What the system may and may not assert |
| [`e2e_verification_journeys.md`](docs/e2e_verification_journeys.md) | Golden corpus and end-to-end journeys |

---

## Two ideas worth stealing even if you never build this

**The unit of comparison is a stance-neutral proposition, not a topic.** Once each utterance reduces to a canonical proposition plus a stance, contradiction detection stops being a fuzzy model judgment and becomes a database query — *same proposition, opposing stance, no intervening acknowledged update*. The model does extraction; the database does detection. That split is what makes findings auditable.

**Even-handedness works by matching principles, not situations.** Recognising that two events are "structurally parallel" is an open research problem. Extracting the general rule a judgment implies, with the actor left as a slot, is a short canonical string you can embed and cluster like anything else — and then a double standard is a join.

---

## License

MIT
