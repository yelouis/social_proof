# Rubric Engine — Tension Types, Axis Formulas & The Sufficiency Gate

**Contract for:** Phases 4 and 6. Turns the structured claim layer into Tensions, and Tensions into scores.

**Standing rule for this whole document:** every number the system displays decomposes into the Tensions that produced it, and every Tension opens to two verbatim quotes with dates and sources. A score the user cannot drill into is a bug (invariant I3).

---

## 0. How the axes are computed — no LLM runs at scoring time

**Every axis is arithmetic and SQL over already-extracted rows. Not one of them calls a language model.**

The LLM appears exactly once in the entire system — at extraction (`design_claim_extraction.md`) — and its output is frozen into `Claim` rows stamped with an `extraction_version`. Everything above that layer is deterministic computation. This is a deliberate architectural property, and four things depend on it:

1. **Reproducibility.** The same corpus at the same versions produces the same number, byte for byte, on every run. An LLM-as-judge at scoring time would make the number resample every time you looked at it.
2. **Auditability.** Any score can be recomputed by hand from the rows. "Why is Consistency 0.61?" has an arithmetic answer, not a vibe.
3. **Version comparison actually means something.** `design_data_layer.md` §6 requires that scores be comparable only within a version. That guarantee is empty if the scorer is stochastic.
4. **It's free.** Rescoring a whole corpus after a formula change costs no tokens, so tuning against the golden corpus is not rate-limited by a bill.

**Two kinds of model, kept strictly separate.** A *generative* model (Gemma at extraction) is sampled and non-reproducible, so its output is captured once and version-stamped. A *deterministic* model — the pinned NER tagger used for Specificity features in §2A — returns the same output for the same input every time, and is treated like any other pure function. It still carries a version (`nlp_version`) on every row it touches, for the same reason everything else does.

If you find yourself writing "ask the model whether this person is being consistent," stop. That is the un-auditable design this whole layer exists to replace.

---

## 1. Tension types

A **Tension** is a detected pair of Claims in conflict. It is always the unit of evidence; axes are aggregations over Tensions and never over anything else.

| Type | Detected when | Feeds |
|---|---|---|
| `unacknowledged_reversal` | Same proposition, opposing stance, later claim carries no acknowledgement of change | Consistency ↓ |
| `acknowledged_update` | Same proposition, opposing stance, **with** a change marker | Update Integrity ↑ |
| `principle_conflict` | Same principle, different actor, opposite verdict, no stated distinction | Even-handedness ↓ |
| `audience_divergence` | Same proposition, opposing stance, **within a short window**, across venues of differing `audience_stance` | Reported as evidence; see §6 |

### Detection preconditions (all types)

Both claims must satisfy, or no Tension is created:

- `is_own_assertion = true` on both (invariant I7)
- `attribution_confidence = high` on both underlying utterances (`design_source_acquisition.md` §5.4)
- Stance in `{support, oppose}` — a `hedge`-vs-`support` pair is not a reversal
- **Matching `condition`** — a conditional claim does not contradict an unconditional one (`design_claim_extraction.md` §5)
- Both claims' `quote_span` resolves against stored source text (invariant I9)
- The negation re-check has passed on both (`design_source_acquisition.md` §5.3)

Any Tension failing a precondition is written with `status: quarantined` and a `quarantine_reason`. **Quarantined Tensions never reach a score and never render.** They exist so the failure rate is measurable.

### The acknowledgement window

An `unacknowledged_reversal` becomes an `acknowledged_update` if *any* claim between the two dates, on the same proposition, carries a `change_marker` (`design_claim_extraction.md` §4). The acknowledgement does not have to be in the same utterance as the new position — people announce a change once and then just hold the new view.

**Search the whole interval, not just the later utterance.** Getting this wrong converts every honest updater in the corpus into a flip-flopper, which inverts invariant I6.

---

## 2. Consistency

Over propositions in the resolved topic slice that have **≥2 own-assertion claims at different times** (call these *eligible*):

```
weight(pair)  = (1 − hedging_a) × (1 − hedging_b)
penalty       = Σ weight(p) over unacknowledged_reversal pairs
consistency   = 1 − penalty / eligible_proposition_count      # clamped to [0, 1]
```

Hedging weighting is deliberate: reversing a flat assertion is a full-weight event, while "I could see it going either way" followed by a firm position is barely a reversal at all. It also partly compensates for the absence of a Specificity axis — **partly**, which is the argument in Issue 001.

**Gate:** requires a minimum eligible-proposition count. Below it, `consistency = null`, reason `insufficient_repeat_coverage`. A subject who said one thing once has no consistency, and the correct output is not 1.0.

---

## 2A. Specificity *(Issue 001, Option A — selected)*

**What it closes.** The other three axes all reward a subject who never commits to anything: no reversals to find, no updates to disclose, no principle stated firmly enough to apply unevenly. Specificity is what stops "said nothing checkable" from scoring like "was principled." It is the axis that makes the other three mean something.

**It is a rate, not a weighted index.** No magic coefficients to defend — one threshold and three boolean features:

```
checkable(claim) :=
      hedging_level ≤ H_max
  AND stance IN {support, oppose}                        -- a hedge stance is not a commitment
  AND (has_named_entity OR has_numeric OR has_temporal_anchor)

specificity = |checkable| / |own-assertion claims in slice|
```

### The three features, all deterministic

| Feature | Source | Rule |
|---|---|---|
| `hedging_level` | Extraction (`design_claim_extraction.md`) | Already on the row. Frozen at `extraction_version`. |
| `has_named_entity` | Pinned NER tagger over `quote_span` | True if any `PERSON`, `ORG`, `GPE`, `LAW`, `PRODUCT`, or `EVENT` entity. Records `nlp_version`. |
| `has_numeric` | Regex over `quote_span` | Digits, spelled-out numbers, percentages, currency, orders of magnitude. |
| `has_temporal_anchor` | NER `DATE`/`TIME` + regex | An explicit year, date, or bounded horizon ("by 2030", "within six months"). **Vague futures do not count** — "soon", "eventually", "at some point" are the exact evasion this axis is measuring. |

`H_max` is **measured on the golden corpus, not chosen** — added to `ongoing_errors.md` §2 as parameter **016**.

**Gate:** requires a minimum own-assertion claim count in the slice. Below it, `specificity = null`, reason `insufficient_corpus` — same as every other axis.

### Why this shape rather than a weighted sum

A weighted formula (`w₁·(1−hedging) + w₂·entity_density + …`) would need four coefficients nobody can defend, and the resulting number would be uninterpretable. A rate is directly readable — *"38% of their claims on this topic are checkable"* — and it decomposes exactly the way the standing rule demands: the user clicks through to two lists, the checkable claims and the unfalsifiable ones, each with its quote. That also delivers Issue 001's Option B benefit for free, since the score *is* the displayed percentage.

### The reading that must be on screen

**A low Specificity is not a character judgment.** Some people are cautious because they are careful, and some topics genuinely do not admit confident claims. The UI states the count plainly and lets the reader decide; it never labels the subject evasive. What Specificity is *for* is context on the other three numbers — a Consistency of 0.95 next to a Specificity of 0.12 is a very different record from 0.95 next to 0.71, and without the second number those two look identical.

---

## 3. Update Integrity

Over every detected stance change in the slice, acknowledged or not:

```
score = (1.0 × acknowledged_with_reason
       + 0.5 × acknowledged_without_reason
       + 0.0 × unacknowledged) / total_changes
```

> **`total_changes = 0` yields `null`, never 1.0.**

This is the same class of loophole as the specificity gap, and it is closed here rather than argued about later: a person who has never publicly changed their mind on anything has not demonstrated integrity in updating. They have demonstrated nothing. The system says `no_updates_detected` and shows the count.

**Gate:** requires a minimum change count. Two updates is an anecdote, not a rate.

---

## 4. Even-handedness

The pattern is the finding — a single principle conflict is never reported as a double standard (`design_principle_extraction.md` §6).

For each non-distinguished `principle_conflict`, code a direction:

```
+1  lenient verdict → ally,     strict verdict → opponent
−1  lenient verdict → opponent, strict verdict → ally
 0  neither actor has a resolved affinity
```

```
directional = Σ direction over conflicts with direction ≠ 0
n           = count of those conflicts
alignment   = |directional| / n
even_handedness = 1 − alignment
```

**Then a significance check, and it is not optional.** Three conflicts that happen to cut the same way is a coin landing heads three times. Run a two-sided binomial test on the ±1 split at p = 0.5; if the result is not distinguishable from chance, emit `even_handedness = null` with reason `pattern_not_significant` and show the conflicts as evidence anyway. The user still sees everything; the system just declines to call it a pattern.

`actor_affinity` is derived exclusively from the subject's own corpus — who they praise, endorse, defend. Never from an external political map (invariant I2).

**Gate:** requires a minimum directional-conflict count *and* a passing significance test.

---

## 5. The sufficiency gate is per-axis (invariant I5)

There is no single global threshold. Each axis has its own precondition, and an Assessment routinely has some axes scored and others null:

```json
{
  "sufficiency": {"claim_count": 84, "source_count": 11, "span_days": 1290},
  "axes": {
    "consistency":      {"score": 0.72, "n": 19},
    "specificity":      {"score": 0.38, "n": 84, "checkable": 32},
    "update_integrity": {"score": null, "reason": "no_updates_detected", "n": 0},
    "even_handedness":  {"score": null, "reason": "pattern_not_significant", "n": 4}
  }
}
```

Three rules that follow, and they are absolute:

1. **A null axis is never rendered as zero, low, or "poor."** It renders as its reason.
2. **A suppressed score is never computed.** If it is computed and stored-but-hidden, some future client will render it. Do not compute it (`design_data_layer.md` §8).
3. **No composite.** There is no single number combining the three axes. Averaging them would reintroduce the trust score the project explicitly rejected (`master_implementation_plan.md` §8), and it would silently treat a null axis as a value.

---

## 6. Audience divergence — evidence, not an axis

Same proposition, opposing stance, inside a short window, across venues with different `audience_stance` (`design_source_acquisition.md` §2). Genuinely striking when real, and a genuine edge over manual research, since it requires venue metadata a human reader rarely has.

It is **not** an axis, because the base rate is too low to score: most subjects have zero instances, which would make the axis null for nearly everyone. It surfaces in the timeline as a flagged pair with both venues named. Promoting it to an axis is **Issue 011**.

---

## 7. Version discipline

Every Assessment records `rubric_version`, `detector_version`, `extraction_version`, `embedding_model`, and `nlp_version` (the pinned NER tagger behind Specificity's features — §2A).

- Changing any formula, weight, threshold, or significance test **bumps `rubric_version`**.
- A bumped version writes a **new** Assessment; the old one is retained.
- **Every displayed score states its version.**
- Head-to-head comparison **refuses** to compare Assessments computed under different versions — recompute, or decline (`design_data_layer.md` §6).

---

## 8. Failure modes

| Failure | Consequence | Mitigation |
|---|---|---|
| Acknowledgement searched only in the later utterance | Every honest updater scored as a flip-flopper — inverts I6 | §1 — search the whole interval |
| Null treated as zero downstream | Thin records look damning | §5.1; assert in tests that null renders as its reason |
| Composite score added "for convenience" | Rebuilds the rejected trust score | §5.3 — no composite, and it is a non-goal, not a preference |
| Single principle conflict reported as hypocrisy | Overreach that discredits the product | §4 significance test |
| Conditional paired with unconditional | Every economist becomes a hypocrite | §1 preconditions |
| Low-confidence attribution reaches a score | False accusation | §1 preconditions — `high` only |
| Quarantined Tensions silently ignored | Failure rate invisible | Quarantine count surfaced in the assessment payload |
| Rubric edited without a version bump | Silent historical drift | §7 |

---

## 9. Open decisions

**Resolved:** Issue 001 → Specificity added as a scored axis (§2A). Issue 011 → `audience_divergence` stays as flagged evidence (§6), not an axis. Issue 009 → if Even-handedness precision misses the bar, ship the principle pairs as evidence with no score (`design_principle_extraction.md` §8).

**Still to measure, not choose** (`ongoing_errors.md` §2):
- **Issue 012** — the per-axis gate thresholds.
- **Issue 016** — `H_max`, the hedging ceiling in the Specificity checkability test (§2A).
