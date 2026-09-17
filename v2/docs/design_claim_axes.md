# The seven axes of a good claim — and what an episode score means

**Status:** design, September 16 2026. Owns the definition of *claim quality*. `design_claim_rubric.md` owns the definition of *what a claim is*; this file owns *how good it is*. **If you change this file, the scoring prompt and the episode report change in the same commit.**

---

## 1. What this measures, and what it refuses to measure

> **Per episode: how good are the claims being made?**

**This is not fact-checking and must never become it.** Nothing here asks whether a claim is *true*. A confident, well-typed, contestable prediction that turns out wrong scores **high** on every axis below, because the product tracks what a person committed to and whether they held it — not whether they were right.

That is also why **uncontested facts are excluded rather than rewarded** (Axis 4). *"Nvidia makes H100 GPUs"* is true, checkable and worthless here: nobody can change their mind about it.

| | standard fact-checking | this |
|---|---|---|
| question | is the statement true? | what did the speaker commit to? |
| target | check-worthy empirical facts | positions, predictions, causal theories, evaluations |
| excludes | opinions and values | uncontested facts |
| output | a truth rating | a commitment record, and whether it held |

---

## 2. The split that makes the score mean anything

The seven axes do not all measure the same subject, and averaging them into one number would produce a figure nobody can act on.

**Four axes describe what the speaker did.** Three describe what our pipeline did with it.

| panel | axes | answers | a bad score means |
|---|---|---|---|
| **Speaker** | Voice · Target · Propositionality · Contestability · Typing | how good were the claims *made* | the hosts hedged, narrated, or said nothing arguable |
| **Extraction** | Decontextualisation · Fidelity · Granularity | how well did *we* capture them | our prompt is sloppy — **not an episode property** |

**The episode score is the Speaker panel.** The Extraction panel is a quality gate on ourselves and is reported separately, never blended in. **A single number mixing them cannot distinguish "the hosts were vague this week" from "our extractor got worse", which are opposite problems with opposite fixes.**

Measured on `gemma-4-31b`'s 111 claims from E287, the Extraction panel already has something to say: **6 claims (5.4%) carry an unresolved referent** — including `t0010`, a claim the gold set and the model agree on, which reads *"The individual discussed is more right on the substance of what he is saying than he is wrong."* **It names nobody.** Binary claim/not-claim could never have surfaced that.

---

## 3. The axes

Each axis scores **0, 1 or 2**. The anchors are written so that 1 is a real middle, not a place to hide.

### Speaker panel — how good was the claim that was made

#### Axis 1 · Voice — *did this speaker commit to it?*
A claim needs epistemic commitment. Reading an ad, interviewing a guest, voicing someone else's position to reject it, or posing a hypothetical are not commitments.

| | |
|---|---|
| **2** | asserted in the speaker's own voice, unhedged or hedged in a way that still commits — *"the CCP is brilliant at PR"* |
| **1** | own voice but heavily distanced — *"some people would say…"*, *"I could see X happening"* |
| **0** | reporting, narrating, quoting, asking, ad copy, or a hypothetical — *"They wanted approval for models using 10^25 flops"* |

> **This is where the current extractor loses most of its precision.** 86% of `gemma-4-31b`'s 79 disagreements with the gold set fail on Voice, and 59 of those are narration or anecdote.

#### Axis 2 · Target — *is it about the world, or about the show?*
| **2** | about entities, dynamics or events outside the recording |
| **1** | about the industry the show covers, but self-referential — *"our audience already knows this"* |
| **0** | show mechanics, scheduling, ticket sales, greetings, banter |

#### Axis 3 · Propositionality — *does it assert something?*
A topic is not a proposition (trap 43). A claim needs a subject and a predicate that carries a truth value, a mechanism, or a judgement.

| **2** | explicit predicate relating concepts — *"cloud-hosted agent architectures are superior to local execution"* |
| **1** | asserts something but thinly — *"AI is a big deal"* |
| **0** | a bare topic (*"enterprise AI deployment"*) or meta-commentary (*"I think that's right"*) |

#### Axis 4 · Contestability — *could a well-informed person disagree?*
| **2** | genuinely disputed — a reasonable opponent holds the other view |
| **1** | mildly contestable; most informed people would agree but not all |
| **0** | tautology (*"until string theory is proved, it's unproved"*), undisputed spec or date |

**This axis is what keeps the project out of fact-checking.** A claim scoring 0 here is excluded *because* it is uncontroversially true.

#### Axis 5 · Typing — *what kind of commitment is it?*
Exactly one of **position** (normative), **prediction** (temporal), **causal** (mechanistic), **evaluative** (judgement), **contested fact** (disputed empirical). If none fits, it is usually filler.

| **2** | one type fits cleanly |
| **1** | two types compete, or the type is right but the modality is mushy |
| **0** | no type fits |

### Extraction panel — how well did we capture it

#### Axis 6 · Decontextualisation — *does it stand alone?*
Every pronoun, indexical and temporal anchor resolved, without semantic drift. Unbound referents are embedding attractors (trap 42): *"They are doing this because of that"* matches everything and poisons clustering.

| **2** | fully resolved; a reader seeing only this sentence understands it |
| **1** | one minor unresolved anchor (a date, a vague "recently") |
| **0** | unresolved subject or object — *"It is very hard to control government spending"*, *"This is the most profitable quarter of any public company ever"* |

#### Axis 7 · Fidelity — *is the claim entailed by the quote?*
Trap 28: a real quote does not make a real claim. The pipeline has already shipped genuine quotes carrying invented propositions.

| **2** | the quote strictly entails the standalone claim |
| **1** | entailed but with added specificity the quote does not carry |
| **0** | the claim asserts something the quote does not say |

> **Fidelity must not be scored by the model that wrote the claim.** A model asked whether it hallucinated says no. Score it with a *different* model, or with a mechanical entailment check. This is the one axis where self-assessment is worthless by construction.

#### Axis 8 · Granularity — *one claim, or several tangled together?*
| **2** | atomic, or a single causal link (A causes B) |
| **1** | two linked assertions that belong together |
| **0** | a compound blob mashing distinct points that could be separately true or false |

**There are eight axes, not seven.** Target appears as *[Target]* in the summary checklist but was missing from the axis list; it is separate from Voice — *"we have a great show today"* is own-voice and still fails.

---

## 4. The episode report

**No single scalar.** The output per episode is a profile:

```
Episode E287 — claim quality
  claims found            111
  claim density           27.4% of 405 turns
  SPEAKER PANEL   (how good were the claims made)
    Voice             mean 1.4   ·  2: 52%  1: 31%  0: 17%
    Target            mean 1.9   ·  ...
    Propositionality  mean 1.7
    Contestability    mean 1.2
    Typing            mean 1.8
  EXTRACTION PANEL (how well we captured them)
    Decontextualisation  mean 1.8  ·  0-scores: 6 claims, listed by turn id
    Fidelity             mean 1.6  ·  scored by GLM-4-32B, not by the extractor
    Granularity          mean 1.9
```

**Density and quality are different questions and both are reported.** An episode with four excellent claims is not the same as one with forty mediocre ones, and a mean that hides the count says nothing.

**Every 0 is listed by turn id.** A distribution nobody can resolve to specific claims is the defect trap 74 was written for.

---

## 5. Worked examples, drawn from E287

| quote → claim | V | T | P | C | Ty | D | F | G |
|---|---|---|---|---|---|---|---|---|
| *"the Chinese, the CCP is f***ing brilliant at PR"* → **The Chinese Communist Party is brilliant at PR** | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| *"he's more right on the substance of what he's saying than he is wrong"* → **The individual discussed is more right on the substance…** | 2 | 2 | 2 | 1 | 2 | **0** | 2 | 2 |
| *"there's probably a lot of incrementalism in 2026 that didn't exist in 1926"* → **There is probably a lot of incrementalism in 2026…** | 1 | 2 | 2 | 1 | 1 | 2 | 2 | 2 |
| *"They got a bunch of Chinese people to fill a stadium and cheer for AI"* → **The Chinese government got people to fill a stadium…** | **0** | 2 | 2 | 1 | 1 | 1 | 1 | 2 |
| *"it was pretty obvious to me in May that Salesforce specifically was meaningfully oversold"* → **Salesforce was meaningfully oversold in May** | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

**The last row is the one to look at.** B2's gold set labels that turn an exclusion — it is 310 words and mostly narrative — and under binary scoring it counts against the extractor as a false positive. **Under the axes it scores 2 across the board, which is the correct answer.** This is the unit mismatch of parameter 048 resolving itself: the question stops being *"is this turn a claim?"* and becomes *"how good is the claim inside it?"*

---

## 6. What this replaces

**Axis scoring replaces the binary claim/not-claim verdict as the pipeline's output.** The four gates of `design_claim_rubric.md` survive as the *definition* and as Axes 1–4; what changes is that a candidate is no longer accepted or rejected, it is scored, and a threshold over the Speaker panel decides what reaches the page.

**B2's gold set is binary and no longer matches this output shape.** It remains valid as a recall check — the 33 turns it marks as claims should still be found — but it cannot validate an axis score, because nobody has labelled an axis.

**Issue 045 = B: no hand-labelled axis set will be produced.** The scorer is validated instead by three mechanical proxies, by **perturbation** — damaging a known-good claim on one axis and asserting only that axis falls — and by cross-model agreement used as a diagnostic rather than as proof (§18 of the execution guide).

> **Know which property you have measured.** Perturbation establishes that the scorer is **sensitive** to each axis. It does not establish that its absolute level matches a human's: a scorer that answers 1 where a careful reader would say 0 passes every check here. **Every episode report must carry that caveat** until a labelled set exists, and no threshold for what reaches the timeline should be set from these numbers alone.
