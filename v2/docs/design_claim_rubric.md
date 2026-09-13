# The Claim Rubric — what counts, what doesn't, and why

**This document is the definition of a claim for V2.** It is used in three places and **the text must be identical in all three**, or they drift and nothing is measurable:

1. the prompt given to the local model,
2. the instruction given to a human building the labelled set,
3. the standard a verification pass applies when reading output.

**If you change this file, the prompt and the labelling instruction change in the same commit.**

---

## 1. The one-sentence test

> **A claim is a sentence the speaker would defend if someone challenged it.**

Everything below is that sentence made decidable. When a case is genuinely ambiguous after applying the four gates, **exclude it** and record why — V1's failure was never too few claims, it was claims that were not claims.

---

## 2. The four gates

**All four must pass.** They are ordered cheapest-first; stop at the first failure and record which one.

### Gate 1 — Attributable

**Is *this speaker* asserting it, in their own voice?**

This gate does most of the work. Of seven claims sampled from V1 and judged not to be claims, **five failed here.**

Fails when the speaker is:

- **reporting what someone else said or wanted** — *"They wanted regulatory approval for models that use 10 to the 25th Flops, right?"*
- **narrating someone else's strategy or playbook** — *"Number one, brand yourself as a safe AI company."*
- **describing a speech, article, or event** — *"That was the whole thrust of the speech was declaring we were in an AI race."*
- **reading advertising copy** — *"Stop paying the legacy tax and start building the future at airwallex dot com slash all-in."*
- **voicing a position in order to reject it** — *"You can say, okay, Verizon's responsible if people use it in a terrorist attack."*
- **asking, rather than asserting** — *"So you're saying the substance of what he says will no longer matter?"*
- **speculating as a hypothetical they do not hold** — *"let me tell you what would happen if we created a new regulatory body."*

**A guest is not a host.** Only enrolled subjects produce claims; a guest's assertions are context, not record.

### Gate 2 — About the world

**Is it about something outside this recording?**

Fails on the show, the schedule, the sponsor, the audience, the other hosts' banter, and the conversation's own mechanics.

- *"A couple of tickets left."* — fails
- *"Let's go right at that to start."* — fails
- *"We have a few scholarship tickets left."* — fails

### Gate 3 — Contestable

**Could a reasonable, well-informed person disagree?**

Fails on tautologies, definitions, arithmetic, and facts nobody disputes.

- *"until string theory is proved, it's unproved"* — fails, tautology
- *"Azure holds a FedRAMP High authorization"* — fails, uncontested and checkable
- *"There was a federal moratorium on state AI regulation"* — fails, a historical fact stated flatly

**A description is not automatically excluded.** *"The leading open source models are from China these days"* is descriptive **and** contestable — it passes. The test is disagreement, not grammatical mood.

### Gate 4 — Standalone

**Can a reader who sees only this sentence tell what is being asserted?**

Fails on unresolved pronouns, deixis, and back-references.

- *"I think that's right."* — fails
- *"It's going to be a lot bigger than people think."* — fails; *it* is unbound
- *"We're now the AI can take complicated tasks."* — fails; incoherent

**Resolve rather than reject where the turn makes it obvious.** If the speaker said *"…state AI regulation. It's going to be a disaster,"* the claim is *state AI regulation will be a disaster* — record the resolved form and keep the verbatim quote as the citation.

---

## 3. Claim types

**Every claim carries exactly one type.** The taxonomy is not decoration — it tells the model what shape to aim at, and it tells the rubric engine which axis a claim can feed.

| type | shape | example |
|---|---|---|
| **position** | normative — *should*, *must*, *ought* | *state-level AI regulation should be pre-empted federally* |
| **prediction** | a future state, dated or datable | *AI becomes a duopoly between OpenAI and Anthropic* |
| **causal** | X because Y · X drives Y | *the political forces stopping data centers are behind the chip export controls* |
| **evaluative** | X is good / bad / overrated / a mistake | *Anthropic's safety positioning is regulatory capture* |
| **contested fact** | X is the case, and it is genuinely disputed | *the leading open source models come from China* |

**If no type fits, it is not a claim.** That is the intended behaviour, not a gap to be patched by adding a sixth type.

---

## 4. What is recorded

For each claim:

| field | notes |
|---|---|
| `quote` | **verbatim** span from the transcript. Never paraphrased, never cleaned up. |
| `claim` | the assertion as a standalone sentence — pronouns resolved, ASR errors corrected **only where unambiguous** |
| `type` | one of the five above |
| `speaker` | an enrolled subject; never a guest, never `unknown` |
| `turn_id` + offset | where it was said |
| `gate_failed` | on exclusion: which of the four, and nothing else |

**The quote and the claim are different fields and both are required.** V1 conflated them and spent five rewrites on the consequences: the quote is evidence, the claim is what is being asserted, and a claim that cannot be stated separately from its quote has not been understood.

---

## 5. Worked examples

Drawn from V1's live corpus. **These are the calibration set — a labeller who disagrees with these should stop and raise it rather than proceed.**

| quote | verdict |
|---|---|
| *"the same political forces that are stopping data centers are also behind all these new export controls on chips"* | **CLAIM** · causal |
| *"I could see AI easily becoming another tech market that becomes a duopoly"* | **CLAIM** · prediction (hedged — hedging is recorded, not disqualifying) |
| *"anthropic is guilty of regulatory capture"* | **CLAIM** · evaluative |
| *"I don't think Democrats have the solution to the problem"* | **CLAIM** · evaluative |
| *"Number one, brand yourself as a safe AI company."* | **not a claim** · gate 1 — narrating another's playbook |
| *"They wanted regulatory approval for models that use 10 to the 25th Flops, right?"* | **not a claim** · gate 1 — reporting |
| *"That was the whole thrust of the speech…"* | **not a claim** · gate 1 — describing a speech |
| *"The question is whether at lower levels of the bureaucracy you can get mistakes"* | **not a claim** · gate 1 — raises a question |
| *"A couple of tickets left."* | **not a claim** · gate 2 |
| *"Azure holds a FedRAMP High authorization"* | **not a claim** · gate 3 |
| *"I think that's right."* | **not a claim** · gate 4 |

---

## 6. Why the gates are ordered this way

Cheapest first, and **most-violated first**. Gate 1 rejected five of the seven V1 samples; it is also decidable from the turn alone without embeddings, similarity, or a second model call.

**The ordering is also the diagnostic.** Exclusions are recorded with the gate that caught them, so the distribution is a standing health signal:

- **gate 1 spiking** → the unit is too small, or guest and ad segments are leaking in
- **gate 2 spiking** → segment boundaries are wrong; ad reads are not being stripped
- **gate 3 near zero** → the model is not testing contestability, only grammar
- **gate 4 spiking** → turns are being split mid-thought

**A gate that never fires is not evidence the corpus is clean.** V1's own-assertion guard sat at 0.7% for months and was wrong; when it was fixed it went to 8.2%. **Report all four rates every run and treat any of them near zero as a defect until shown otherwise.**
