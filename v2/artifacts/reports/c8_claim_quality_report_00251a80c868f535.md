# Episode E287 (00251a80c868f535) — Claim Quality Profile (C8)

- **Episode Coverage**: All 405 turns evaluated through Pass 1 extraction funnel.
- **Candidate Claims Scored**: 111 surviving claims evaluated on 8 axes by independent scorer GLM-4-32B at temp 0.0.
- **Audit Trail**: 888 of 888 non-empty reasons verified across all 111 claims $\times$ 8 axes.
- **Scorer Leniency Audit**: Non-2 judgements dropped from 69/888 (7.8%) in C4 to 29/888 (3.3%) in C7 (58.0% reduction).

---

## 1. EPISODE FUNNEL (Episode-Wide: All 405 Turns)

> **Note on Funnel Scope**: The Episode Funnel evaluates the entire conversation (all 405 turns) before extraction filtering. It measures conversational quality and assertion density across the full episode, capturing variation that candidate-level panels cannot see.

| Outcome / Gate | Turns | Share of Episode | Description |
|---|---|---|---|
| **Claim Emitted** | 111 | **27.4%** | Passed all 4 extraction gates; advanced to Claim Quality scoring |
| **Gate 1 — Not Speaker's Own Assertion** | 174 | **43.0%** | Narration, reported speech, questions, quotes, and conversational banter |
| **Gate 2 — Show / Industry Meta** | 37 | 9.1% | Discussion about the podcast itself, hosts, audio, production, or sponsors |
| **Gate 3 — Not Contestable** | 4 | 1.0% | Undisputed empirical definitions, dates, specifications, or tautologies |
| **Gate 4 — Not Standalone / Fragmentary** | 79 | **19.5%** | Sentence fragments, conversational agreements ('yeah', 'right'), or unanchored remarks |
| **Total Episode Turns** | **405** | **100.0%** | **Sum of all episode turns (sums exactly to 405)** |

---

## 2. SPEAKER PANEL (Survivor-Only: How Good Were the Claims Made)

> **Note on Survivor Bias**: Evaluated strictly across the 111 claims that survived Pass 1 filtering. Voice and Contestability show genuine variance among surviving claims; Target, Propositionality, and Typing were pre-screened by Pass 1.

| Axis | Mean | Dist [0 / 1 / 2] | Off-Target Contamination (`off_target_drop_rate_pct`) | Sensitivity | Status |
|---|---|---|---|---|---|
| **Voice** | 1.98 | 1 / 0 / 110 | 2.9% | 100.0% | Varies on survivors |
| **Contestability** | 1.88 | 1 / 11 / 99 | 0.0% | 100.0% | Varies on survivors |

---

## 3. EXTRACTION PANEL (Survivor-Only: How Well We Captured Them)

| Axis | Mean | Dist [0 / 1 / 2] | 0-Scores Listed by Turn ID | Off-Target Contamination (`off_target_drop_rate_pct`) | Sensitivity | Status |
|---|---|---|---|---|---|---|
| **Decontextualisation** | 1.84 | 9 / 0 / 102 | 9 claims (00251a80c868f535_t0010, 00251a80c868f535_t0022, 00251a80c868f535_t0032...) | 8.6% | 100.0% | PASSED |
| **Fidelity** | 1.95 | 3 / 0 / 108 | 3 claims (00251a80c868f535_t0127, 00251a80c868f535_t0142, 00251a80c868f535_t0189) | 0.0% | 100.0% | PASSED |
| **Granularity** | 1.97 | 0 / 3 / 108 | 0 claims | 8.6% | 100.0% | PASSED |

---

## 4. FRONT-HALF PIPELINE FILTER (Pre-Filtered by Pass 1 Gates 1 & 2)

Target, Propositionality, and Typing showed zero or near-zero variance across the 111 surviving candidate claims. Step 4 evaluated Target and Propositionality over 40 turns rejected by Pass 1 (banter, show mechanics, host setup) to confirm discrimination:

- **Target**: Rejected turns: 0: 25 (62.5%), 1: 6 (15.0%), 2: 9 (22.5%). Surviving candidate claims: 1x0, 0x1, 110x2 (mean 1.98).
- **Propositionality**: Rejected turns: 0: 7 (17.5%), 1: 15 (37.5%), 2: 18 (45.0%). Surviving candidate claims: 0x0, 0x1, 111x2 (mean 2.00).
- **Typing**: Surviving candidate claims: 0: 0 (0.0%), 1: 0 (0.0%), 2: 111 (100.0%) (mean 2.00). All surviving claims cleanly fit the 5 canonical commitment types.

---

## 5. OFF-TARGET CONTAMINATION COMPARISON (Single Metric: `off_target_drop_rate_pct`)

| Axis | C5 Off-Target | C6 Off-Target | C7 Off-Target | C8 Off-Target (Rebuilt) | Threshold (<25%) | Sensitivity (>=80%) | C8 Status |
|---|---|---|---|---|---|---|---|
| **Voice** | 20.0% | 2.9% | 2.9% | **2.9%** | < 25.0% | 100.0% | **PASSED** |
| **Target** | 40.0% | 0.0% | 0.0% | **0.0%** | < 25.0% | 100.0% | **PASSED** |
| **Propositionality** | 45.7% | 2.9% | 2.9% | **2.9%** | < 25.0% | 100.0% | **PASSED** |
| **Contestability** | 17.1% | 0.0% | 0.0% | **0.0%** | < 25.0% | 100.0% | **PASSED** |
| **Typing** | 51.4% | 2.9% | 2.9% | **2.9%** | < 25.0% | 80.0% | **PASSED** |
| **Decontextualisation** | 8.6% | 8.6% | 8.6% | **8.6%** | < 25.0% | 100.0% | **PASSED** |
| **Fidelity** | 11.4% | 31.4% | 31.4% | **0.0%** | < 25.0% | 100.0% | **PASSED** |
| **Granularity** | 22.9% | 8.6% | 8.6% | **8.6%** | < 25.0% | 100.0% | **PASSED** |

---

## 6. SCORER LENIENCY ADJUDICATION (C4 vs C7 Across 111 Claims $\times$ 8 Axes)

### Before / After 0 / 1 / 2 Score Distribution Table

| Axis | C4 Dist [0/1/2] | C4 Mean | C4 Non-2 | C7 Dist [0/1/2] | C7 Mean | C7 Non-2 | Net Change |
|---|---|---|---|---|---|---|---|
| **Voice** | 3 / 1 / 107 | 1.94 | 4 | 1 / 0 / 110 | 1.98 | 1 | -3 |
| **Target** | 0 / 0 / 111 | 2.00 | 0 | 1 / 0 / 110 | 1.98 | 1 | +1 |
| **Propositionality** | 0 / 0 / 111 | 2.00 | 0 | 0 / 0 / 111 | 2.00 | 0 | +0 |
| **Contestability** | 4 / 31 / 76 | 1.65 | 35 | 1 / 11 / 99 | 1.88 | 12 | -23 |
| **Typing** | 0 / 2 / 109 | 1.98 | 2 | 0 / 0 / 111 | 2.00 | 0 | -2 |
| **Decontextualisation** | 18 / 6 / 87 | 1.62 | 24 | 9 / 0 / 102 | 1.84 | 9 | -15 |
| **Fidelity** | 3 / 1 / 107 | 1.94 | 4 | 3 / 0 / 108 | 1.95 | 3 | -1 |
| **Granularity** | 0 / 0 / 111 | 2.00 | 0 | 0 / 3 / 108 | 1.97 | 3 | +3 |
| **Total** | — | — | **69 (7.8%)** | — | — | **29 (3.3%)** | **-40 (-58.0%)** |

### One-by-One Adjudication of the 9 Dropped Decontextualisation Zeros

Calibration removed 9 decontextualisation zeros (18 -> 9), and C7's zeros are a strict subset of C4's. Below is the itemized adjudication:

#### 1. Turn `t0007` — C7 is right, C4 was wrong
- **Quote**: *"He is a heterodox thinker in science"*
- **Standalone Claim**: *"Eric Weinstein is a heterodox thinker in science"*
- **C4 Score**: 0 (Reason: *Unresolved subject 'He' - doesn't name who is being discussed*)
- **C7 Score**: 2 (Reason: *The standalone claim 'Eric Weinstein is a heterodox thinker in science' resolves all pronouns and indexicals, standing completely on its own.*)
- **Adjudication**: The quote contains 'He is a heterodox thinker in science'. The extracted claim fully resolved 'He' to 'Eric Weinstein is a heterodox thinker in science'. C4 penalized the quote's pronoun, while C7 correctly judged that the standalone claim is completely self-contained.

#### 2. Turn `t0099` — C7 is right, C4 was wrong
- **Quote**: *"He is just an incredible salesperson"*
- **Standalone Claim**: *"Mark Banyoff is an incredible salesperson"*
- **C4 Score**: 0 (Reason: *Unresolved subject 'He' refers to Mark Banyoff mentioned earlier.*)
- **C7 Score**: 2 (Reason: *Fully resolved; a reader seeing only this sentence understands it.*)
- **Adjudication**: The quote contains 'He is just an incredible salesperson'. The claim fully resolved 'He' to 'Mark Banyoff is an incredible salesperson'. C4 penalized the quote's pronoun, whereas C7 correctly recognized that the standalone sentence requires no external context.

#### 3. Turn `t0113` — C7 is right, C4 was wrong
- **Quote**: *"I don't know that he understood the difference between vertical and horizontal sass"*
- **Standalone Claim**: *"Chamath Palihapitiya believes that David Sacks did not understand the difference between vertical and horizontal SaaS."*
- **C4 Score**: 0 (Reason: *Unresolved referent: 'he' (David Sacks) not explicitly named in standalone claim*)
- **C7 Score**: 2 (Reason: *Fully resolved standalone claim; all pronouns and indexicals are resolved by naming Chamath Palihapitiya and David Sacks.*)
- **Adjudication**: The claim 'Chamath Palihapitiya believes that David Sacks did not understand the difference between vertical and horizontal SaaS' explicitly names both entities. C4 claimed 'he' was not explicitly named in the standalone claim, which was factually untrue. C7 correctly scored 2.

#### 4. Turn `t0131` — C7 is right, C4 was wrong
- **Quote**: *"And then you're going to see them go up the stack and host the model"*
- **Standalone Claim**: *"Companies are going to move up the stack and host the model."*
- **C4 Score**: 0 (Reason: *Unresolved referent 'them' - unclear who 'them' refers to in standalone claim*)
- **C7 Score**: 2 (Reason: *The standalone claim resolves all pronouns and indexicals, standing completely on its own.*)
- **Adjudication**: The quote says 'And then you're going to see them go up the stack'. The claim resolved 'them' to 'Companies are going to move up the stack and host the model'. C4 penalized the quote's 'them'. C7 correctly scored the resolved standalone claim as 2.

#### 5. Turn `t0144` — C7 is right on decontextualisation; C4 was off-target
- **Quote**: *"I think that drug is sending his signal to the market and saying, guys, this is not essence responsibility"*
- **Standalone Claim**: *"David Friedberg believes that drug is signaling to the market that this is not his responsibility"*
- **C4 Score**: 0 (Reason: *Standalone claim introduces 'David Friedberg believes' which is not in the quote.*)
- **C7 Score**: 2 (Reason: *The standalone claim resolves all pronouns and indexicals: 'drug' refers to 'drug', 'his' refers to 'drug', and 'this' refers to 'responsibility'.*)
- **Adjudication**: Claim: 'David Friedberg believes that drug is signaling to the market that this is not his responsibility'. C4 gave 0 because the claim introduced 'David Friedberg believes', which is an ungrounded attribution belonging to Fidelity. C7 correctly recognized that as a standalone sentence, it does not carry dangling unresolved indexicals.

#### 6. Turn `t0162` — C4 was right, C7 was wrong / overly lenient
- **Quote**: *"the U .S. government is not in a position to do it because Congress cannot get their act together on spending"*
- **Standalone Claim**: *"The U.S. government is not in a position to perform this action because Congress cannot get their act together on spending."*
- **C4 Score**: 0 (Reason: *Unresolved referent *)
- **C7 Score**: 2 (Reason: *The standalone claim resolves all pronouns and indexicals. 'The U.S. government' and 'Congress' are clearly named entities, and 'this action' refers to the context of the trade deals mentioned in the quote.*)
- **Adjudication**: Claim: 'The U.S. government is not in a position to perform this action because Congress cannot get their act together on spending.' The phrase 'perform this action' contains an unresolved demonstrative noun phrase requiring context to know what action is meant. C7's reason admitted 'this action refers to the context of the trade deals mentioned in the quote', proving it violated standalone decontextualisation.

#### 7. Turn `t0168` — Borderline / C7 defensible
- **Quote**: *"the only thing that solves it now is getting the budget. under control, which is a congressional act, it must happen"*
- **Standalone Claim**: *"The only thing that solves the current situation is getting the budget under control through a congressional act, which must happen."*
- **C4 Score**: 0 (Reason: *Uses unresolved pronoun 'it' referring to 'some extreme pain'*)
- **C7 Score**: 2 (Reason: *The standalone claim resolves all pronouns and indexicals, referring to 'the current situation' and 'a congressional act'.*)
- **Adjudication**: Claim: 'The only thing that solves the current situation is getting the budget under control through a congressional act, which must happen.' C4 penalized 'the current situation' as an unresolved 'it'. However, 'the current situation' is a broad categorical subject rather than a dangling grammatical pronoun. C7's score 2 is defensible.

#### 8. Turn `t0194` — Borderline / C7 defensible
- **Quote**: *"you need mass of public pressure to control it"*
- **Standalone Claim**: *"Mass public pressure is required to control the structural nature of the system."*
- **C4 Score**: 0 (Reason: *Standalone claim contains unresolved reference 'the system'.*)
- **C7 Score**: 2 (Reason: *The standalone claim resolves all pronouns and indexicals, standing completely on its own.*)
- **Adjudication**: Claim: 'Mass public pressure is required to control the structural nature of the system.' C4 penalized 'the system' as an unresolved reference. C7 treated 'the structural nature of the system' as a coherent abstract political concept. C7's 2 is defensible.

#### 9. Turn `t0385` — C7 is right, C4 was wrong
- **Quote**: *"what's interesting about this is it is much more of a technique than a drug"*
- **Standalone Claim**: *"The cancer vaccine system is more of a technique than a drug."*
- **C4 Score**: 0 (Reason: *Unresolved referent 'this' - unclear what system is being discussed.*)
- **C7 Score**: 2 (Reason: *The standalone claim 'The cancer vaccine system is more of a technique than a drug.' resolves all pronouns and indexicals, standing completely on its own without relying on the quote or turn text.*)
- **Adjudication**: Quote: 'what's interesting about this is it is much more of a technique than a drug'. Claim: 'The cancer vaccine system is more of a technique than a drug.' The claim completely resolved 'this / it' to 'The cancer vaccine system'. C4 penalized the quote's 'this'. C7 correctly scored 2.

### Resolution of t0072 (Bare Demonstrative 'This')

- **Turn**: `t0072`
- **Quote**: *"That is the most profitable core business quarter of any public company ever"*
- **Standalone Claim**: *"This is the most profitable core business quarter of any public company ever"*
- **Scored**: C4 = 2, C7 = 2
- **Finding**: t0072 ('This is the most profitable core business quarter of any public company ever') scored 2 in both C4 and C7. Under the axes doc's Level-0 anchor ('unresolved subject or object such as "it", "this"'), this claim strictly violates decontextualisation: 'This' refers to Nvidia's Q2 earnings mentioned in the surrounding conversation, but neither Nvidia nor Q2 appears in the standalone claim. The model scored it 2 because LLMs exhibit leniency toward grammatically complete copular sentences starting with demonstratives ('This is...'), treating 'This' as a legitimate deictic topic header rather than an unbound indexical. Mechanical regex proxies catch leading demonstratives immediately; prompt-only LLM scoring does not. Per §21 constraints, candidate scores are not manually modified mid-item; t0072 is recorded as an established model leniency defect.

---

## 7. FALSIFICATION — Uncalibrated C4 Scorer on Rebuilt Fidelity Perturbations

The rebuilt direction-inverting fidelity perturbations were re-run through the uncalibrated C4 prompt template (`score_axes_c4_uncalibrated.md`):
- **Target Sensitivity**: 5 of 5 (100.0%)
- **Off-Target Drop Rate**: 0 of 35 comparisons (0.0%)
- **Finding**: Direction inversion cleanly isolates Fidelity under both calibrated and uncalibrated prompt templates because preserving the exact subject, speaker, and domain terminology prevents triggering the uncalibrated scorer's decontextualisation and voice penalties.
