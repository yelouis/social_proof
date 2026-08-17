# Principle Extraction — The Even-Handedness Machinery

**Contract for:** Phase 5. The highest-risk component in the system, and the one that produces its most valuable output.

**Read `design_claim_extraction.md` first.** This layer sits on top of Claims and reuses their anchoring discipline.

---

## 1. The reframe that makes this buildable

Even-handedness naively requires recognizing **structurally parallel situations** — noticing that two events are analogous but with different actors. That is an open research problem and a bad foundation for a product.

The reframe: don't match situations. **Match principles.**

Every judgment about a specific case implies a general rule. Extract that rule as a separate object with the actor left as a **slot**:

> *"Senator Alvarez misled the committee and should resign."*
> → principle: **`an elected official who knowingly misleads an oversight body should resign`**
> → actor: `Senator Alvarez` · verdict: `applies`

> *"The calls for Whitcomb to step down are absurd — everyone misspeaks under pressure."*
> → principle: **`an elected official who knowingly misleads an oversight body should resign`**
> → actor: `Rep. Whitcomb` · verdict: `does not apply`

Same principle. Different actor. Opposite verdict. **That is a mechanical join**, not a judgment call — and principles are short canonical strings, so they embed and cluster exactly like propositions do.

---

## 2. Schema

```
Principle {
  principle_id            # global, shared across subjects (design_data_layer.md §2)
  canonical_text          # actor as a slot: "an elected official who {…} should resign"
  actor_role              # the slot's type: elected_official | company | journalist | …
}

PrincipleApplication {
  application_id
  principle_id
  claim_id                # the anchor — inherits quote_span, source, date
  subject_id              # who is applying the principle
  actor                   # WHO it lands on, resolved (§5)
  actor_affinity          # ally | opponent | neutral | self | unknown  (§6)
  verdict                 # applies | does_not_apply | applies_partially
  stated_distinction      # §4 — the fairness escape hatch, and it is load-bearing
  confidence
}
```

**Canonical text carries no actor and no verdict.** Same discipline as stance-neutral propositions (`design_claim_extraction.md` §2), same failure if violated: `Alvarez should resign` and `Whitcomb should not resign` are two principles that never meet, and every double standard in the corpus becomes invisible.

---

## 3. Extraction

The prompt asks one question, and its phrasing is the whole design:

> *"What general rule would have to be true for this specific judgment to follow? State it with the actor left as a slot. If the speaker is making a judgment about a particular case only, and no general rule is implied, return nothing."*

The last sentence matters as much as the first. Not every claim implies a principle, and a model that manufactures one for every opinion generates a conflict graph made entirely of noise. Most claims should yield **no** principle.

**Generality calibration is the hard parameter.** Too specific (`a senator from a coastal state who misleads a committee about shipping subsidies should resign`) and no two applications ever cluster. Too general (`bad behaviour should have consequences`) and everything collides with everything. Calibrate against the golden corpus by measuring cluster size distribution: a healthy principle space has many small clusters and few giant ones. **A cluster with hundreds of members is a sign the principle is too abstract to mean anything** — split it or discard it.

---

## 4. The stated distinction — the fairness escape hatch

**This is the single most important fairness mechanism in the system, and it must be built before, not after, the conflict detector.**

Applying a principle differently is not hypocrisy when the speaker *says why* and the reason is a real distinction:

> *"Whitcomb corrected the record within a day. Alvarez let it stand for eight months. That's the difference."*

That is principled reasoning, and a system that flags it as a double standard is not just wrong — it is wrong in the direction that discredits the whole product. Capture it:

```
stated_distinction {
  present: true,
  text: "corrected within a day vs. let it stand eight months",
  quote_span: [...]        # anchored, like everything else
}
```

**Where a stated distinction is present, the pair is not a conflict.** It is recorded as a `distinguished` application — visible in the evidence trail, excluded from the Even-handedness score.

### The relevant-difference problem, stated honestly

Any two situations differ in *some* way. Hypocrisy is not "treated two different things differently" — it is *"invoked a difference that wasn't load-bearing in the original principle."* Whether the cited difference is load-bearing is a genuine judgment call, and **the system does not make it.**

What the system does instead:

1. Detects the *shape* — same principle, different actor, opposite verdict.
2. Surfaces the stated distinction alongside it, verbatim, if one exists.
3. Lets the reader judge whether the distinction holds.
4. Scores the **pattern**, not the instance (§6).

That is a real limitation and it belongs in the UI copy, not buried here.

---

## 5. Actor resolution

A principle application is worthless without knowing who it landed on, and speech is full of `"them"`, `"the administration"`, `"my old employer"`, `"those guys"`.

- Resolve within the source first — coreference over the transcript, which is where most pronouns bind.
- Maintain a per-subject alias map (`"the agency"` → a specific institution) built during ingest.
- **Unresolved actor ⇒ `actor: unknown` ⇒ excluded from conflict detection.** Never guess. A misattributed actor produces a false accusation of hypocrisy with a real name attached — the worst output the system can emit.
- Actors are entities, not strings. `"Sen. Alvarez"`, `"Alvarez"`, and `"the senator from Delaware"` must resolve to one id or the join fails.

---

## 6. Conflict detection and scoring — the pattern is the finding

```sql
SELECT a.application_id, b.application_id, a.principle_id
FROM principle_applications a JOIN principle_applications b
  ON a.principle_id = b.principle_id
 AND a.subject_id   = b.subject_id
 AND a.actor       <> b.actor
 AND a.verdict     <> b.verdict
WHERE a.actor <> 'unknown' AND b.actor <> 'unknown'
  AND NOT a.stated_distinction.present
  AND NOT b.stated_distinction.present;
```

> **One conflicting pair is weak evidence and must never be reported as hypocrisy.** People are inconsistent about small things for uninteresting reasons, extraction is imperfect, and any single pair might have a distinction the speaker made in a source you haven't ingested.

**The finding is the pattern.** Even-handedness scores on whether conflicts *align with actor affinity* — whether the principle is reliably applied to opponents and reliably excused for allies. A subject with twelve principle conflicts distributed randomly across actor affinity has a messy record. A subject with six conflicts that all cut the same way has a double standard, and that is a claim worth making.

`actor_affinity` is derived from the subject's *own corpus* — who they praise, endorse, and align themselves with — never from an external political taxonomy. Importing a left/right map would be exactly the agenda injection invariant I2 exists to prevent.

Scoring formula and thresholds: `design_rubric_engine.md`.

---

## 7. Failure modes

| Failure | Consequence | Mitigation |
|---|---|---|
| **Principle too abstract** | Everything conflicts with everything; the axis is noise | Cluster-size ceiling; discard giant clusters |
| **Principle too specific** | Nothing ever clusters; the axis is silent | Generality calibrated on the golden corpus |
| Verdict baked into `canonical_text` | Conflicts undetectable | Validator, same as §2 of the extraction contract |
| Actor misresolved | **False hypocrisy accusation against a named person** | `unknown` excluded outright; never guess |
| Stated distinction missed | Principled reasoning flagged as a double standard | §4 built first, measured on golden-corpus positives |
| Legitimate change over time | A 2019 verdict vs a 2024 verdict is an *update*, not a double standard | Cross-check against Update Integrity; wide-gap pairs route to the reversal detector instead |
| Principle inferred where none was implied | Conflict graph made of noise | "Return nothing" is the common correct answer; golden-corpus negatives cover it |
| Single-pair reporting | Overreach that discredits the product | §6 — the pattern is the finding |

---

## 8. If this axis can't be made precise enough

A stated fallback, so it is a decision rather than a scramble: **ship the evidence without the score.** Show detected principle pairs — both quotes, both actors, both dates, any stated distinction — as a "possible double standards" section with no number attached, and drop Even-handedness from the rubric until precision on the golden corpus clears the bar.

That degrades gracefully to the most defensible thing the system can say: *here are two things you said; you judge.* Tracked as **Issue 009**.
