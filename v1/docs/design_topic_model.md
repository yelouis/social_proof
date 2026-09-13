# Topic Model — Clustering and Free-Text Resolution

**Contract for:** Phase 3. Answers "which claims are about the thing the user asked about?"

**Selected approach:** hybrid — cluster propositions per subject after ingest, resolve free-text queries against those clusters at query time, cache the resolution. This is what lets the product honour "any given topic" while keeping rubric scores cheap, stable, and repeatable.

---

## 1. Why not the simpler options

| Alternative | Why not |
|---|---|
| Pure free-text, computed fresh each query | Scores drift between identical queries. A number that changes when you reload is not a measurement. |
| Auto-discovered topics only, browse-first | Can't answer a topic the subject touches glancingly, and per-subject clusters make cross-person comparison meaningless. |
| Curated global taxonomy | Rigorous but must be maintained by hand, and misses every topic not anticipated. |

The hybrid keeps free-text flexibility *and* score stability, at the cost of a caching layer — which is the cheapest of the three costs.

---

## 2. Clustering, after ingest

Cluster **Propositions**, never raw utterances. Propositions are already deduplicated and stance-neutral (`design_claim_extraction.md` §2), so the cluster space is small, clean, and free of polarity artefacts — clustering raw text would split every issue into a "pro" cloud and an "anti" cloud, which is precisely wrong.

```
propositions (per subject)
  → embed canonical_text
  → HDBSCAN over the embedding space
  → clusters + noise
  → LLM labels each cluster from its members
```

- **Noise points are kept.** HDBSCAN's unclustered residue is not garbage — it is the subject's idiosyncratic positions, which are often the interesting ones. They remain individually queryable.
- **Labels are cosmetic.** They exist for browsing. Retrieval never goes through the label string, so a bad label is a UI annoyance, not a correctness bug.
- Clusters are per-subject; the propositions inside them are **global** (`design_data_layer.md` §2). That asymmetry is what makes §5 work.

---

## 3. Free-text resolution

```
query "AI regulation"
  → normalize (casefold, collapse whitespace, strip punctuation)
  → embed
  → k-NN over this subject's proposition embeddings, above similarity threshold
  → expand: pull in full clusters where a seed proposition is a member
  → resolved set: [proposition_id, …]
  → cache
```

Cluster expansion is what stops a narrow query from scoring against three cherry-picked propositions when the subject has forty on the topic. A slice that is too small is the single easiest way to produce a misleading score, and it fails *silently* — so expansion runs first and the sufficiency gate (`design_rubric_engine.md`) checks the result.

### The cache key, and the mistake to avoid

```
resolution_key = sha256(subject_id | normalized_query | embedding_model | cluster_version)
```

**`embedding_model` and `cluster_version` must be in the key.** Omit them and an embedding upgrade silently changes every historical score while every cached number keeps its old timestamp — the exact "scores went up last month" failure that versioning discipline exists to prevent (`design_data_layer.md` §6). Changing either invalidates resolutions by construction, which is the intent.

---

## 4. Topic drift over time

"AI safety" in 2016 and "AI safety" in 2026 are not the same conversation. A ten-year corpus can produce a false reversal purely because the words stayed the same while the referent moved.

The proposition layer absorbs most of this — propositions are specific enough that a 2016 alignment-theory position and a 2026 model-release position are different propositions and never pair. Two guards for the residue:

- **Flag wide-gap pairs.** A reversal spanning more than a configured window is surfaced with an explicit "positions are N years apart" marker, and routed to Update Integrity before Consistency (`design_rubric_engine.md`).
- **Never merge propositions across an era boundary on embedding similarity alone.** Where the ambiguous band is hit and the dates are far apart, adjudicate explicitly rather than merging.

---

## 5. Cross-person comparison comes almost free

Because Propositions are global while clusters are per-subject, two subjects querying the same topic resolve to **overlapping proposition sets**. Comparison then happens at the proposition level — *did A and B take opposing stances on this exact proposition?* — with no shared taxonomy to maintain and no alignment step.

This is why the global/per-subject split in the data layer was worth the awkwardness. Phase 10 head-to-head (`design_ui_direction.md`) is a query, not a subsystem.

---

## 6. Failure modes

| Failure | Consequence | Mitigation |
|---|---|---|
| Query resolves to too few propositions | Confident score on a cherry-picked slice | Cluster expansion, then the sufficiency gate — emit `insufficient_corpus`, never a number |
| Query resolves to nothing | — | `no_coverage`. Distinct from a low score and rendered differently |
| Threshold too loose | Unrelated propositions dragged in; contradictions across unrelated topics | Tuned on the golden corpus, biased toward precision |
| Embedding upgrade | Silent score drift | §3 cache key |
| Giant catch-all cluster | Topic label means nothing; expansion pulls in the whole corpus | Cluster-size ceiling; split or mark unusable |
| Topic drift | False reversal across a decade | §4 |

---

## 7. Open decisions

- **Issue 005** (shared with `design_data_layer.md`) — embedding model and dimension.
- **Issue 010** — retrieval similarity threshold and cluster-expansion policy, both of which trade slice size against slice purity.
