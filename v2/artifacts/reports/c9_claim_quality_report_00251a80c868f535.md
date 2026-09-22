# Episode E287 (00251a80c868f535) — Claim Quality Profile (C9)

- **Episode Coverage**: All 405 turns evaluated through Pass 1 extraction funnel.
- **Candidate Claims Scored**: 111 surviving claims evaluated on 8 axes by independent scorer GLM-4-32B at temp 0.0.
- **Audit Trail**: 888 of 888 non-empty reasons verified across all 111 claims $\times$ 8 axes.
- **Scorer Leniency Audit**: Non-2 judgements dropped from 69/888 (7.8%) in C4 to 29/888 (3.3%) in C7 (58.0% reduction).
- **Contestability Adjudication Split**: C7 right: 13 (56.5%) | C4 right: 7 (30.4%) | Borderline: 3 (13.0%).

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
| **Fidelity** | 1.95 | 3 / 0 / 108 | 3 claims (00251a80c868f535_t0127, 00251a80c868f535_t0142, 00251a80c868f535_t0189) | 0.0% | 60.0% | PASSED |
| **Granularity** | 1.97 | 0 / 3 / 108 | 0 claims | 8.6% | 100.0% | PASSED |

### Fidelity Breakdown: Real-Derived vs Invented Perturbations

Per §22, testing only against invented damage (direction inversion) tests only the damage we imagine.
Seeding 3 of 5 pairs from real extraction pipeline failures reveals a striking divergence in scorer behavior:

| Perturbation Class | Seeding Source | Pairs | Sensitivity (`target_drops`) | Off-Target Contamination | Finding |
|---|---|---|---|---|---|
| **Real Failures** | `t0127`, `t0142`, `t0189` | 3 | **33.3%** (1/3) | **0.0%** (0/21) | Catches semantic topic swap (`t0189` inflation -> 0); lenient on pronoun entity resolution (`t0127`, `t0142`). |
| **Invented Inversions** | Direction Inversion (`t0187`, `t0192`) | 2 | **100.0%** (2/2) | **0.0%** (0/14) | Direct contradictions cleanly isolate Fidelity with zero off-target movement. |

> **Key Architectural Finding**: Just as C6 discovered for Granularity, Fidelity exhibits high sensitivity (100.0%) against blunt direction inversions, but materially lower sensitivity (33.3%) against subtle entity substitutions where speakers used pronouns in the raw quote. The axis detects the damage we imagine far better than the real extraction failures produced by LLM pipelines.

---

## 4. FRONT-HALF PIPELINE FILTER (Pre-Filtered by Pass 1 Gates 1 & 2)

Target, Propositionality, and Typing showed zero or near-zero variance across the 111 surviving candidate claims. Step 4 evaluated Target and Propositionality over 40 turns rejected by Pass 1 (banter, show mechanics, host setup) to confirm discrimination:

- **Target**: Rejected turns: 0: 25 (62.5%), 1: 6 (15.0%), 2: 9 (22.5%). Surviving candidate claims: 1x0, 0x1, 110x2 (mean 1.98).
- **Propositionality**: Rejected turns: 0: 7 (17.5%), 1: 15 (37.5%), 2: 18 (45.0%). Surviving candidate claims: 0x0, 0x1, 111x2 (mean 2.00).
- **Typing**: Surviving candidate claims: 0: 0 (0.0%), 1: 0 (0.0%), 2: 111 (100.0%) (mean 2.00). All surviving claims cleanly fit the 5 canonical commitment types.

---

## 5. OFF-TARGET CONTAMINATION COMPARISON (Single Metric: `off_target_drop_rate_pct`)

| Axis | C5 Off-Target | C6 Off-Target | C7 Off-Target | C8 Off-Target | C9 Off-Target (Mixed Real/Invented) | Threshold (<25%) | C9 Sensitivity | C9 Status |
|---|---|---|---|---|---|---|---|---|
| **Voice** | 20.0% | 2.9% | 2.9% | 2.9% | **2.9%** | < 25.0% | 100.0% | **PASSED** |
| **Target** | 40.0% | 0.0% | 0.0% | 0.0% | **0.0%** | < 25.0% | 100.0% | **PASSED** |
| **Propositionality** | 45.7% | 2.9% | 2.9% | 2.9% | **2.9%** | < 25.0% | 100.0% | **PASSED** |
| **Contestability** | 17.1% | 0.0% | 0.0% | 0.0% | **0.0%** | < 25.0% | 100.0% | **PASSED** |
| **Typing** | 51.4% | 2.9% | 2.9% | 2.9% | **2.9%** | < 25.0% | 80.0% | **PASSED** |
| **Decontextualisation** | 8.6% | 8.6% | 8.6% | 8.6% | **8.6%** | < 25.0% | 100.0% | **PASSED** |
| **Fidelity** | 11.4% | 31.4% | 31.4% | 0.0% | **0.0%** | < 25.0% | 60.0% | **PASSED** |
| **Granularity** | 22.9% | 8.6% | 8.6% | 8.6% | **8.6%** | < 25.0% | 100.0% | **PASSED** |

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

### Itemized Adjudication of All 23 Contestability Shifts

- **Three-Way Adjudication Split**: C7 right: 13 (56.5%) | C4 right: 7 (30.4%) | Borderline: 3 (13.0%)
- **Architectural Finding**: Most shifts (13/23 = 56.5%) represent genuine C7 improvements where C4 was over-firing 1s on legitimately contestable claims (macroeconomic debates, software architecture, tech strategy). The panel's single informative axis has not been flattened; calibration removed conservative over-penalization while introducing mild leniency on ~7 consensus claims/platitudes.

| # | Turn ID | Speaker | Claim | C4 Score | C7 Score | Verdict | Adjudication |
|---|---|---|---|---|---|---|---|
| 1 | `t0007` | David Friedberg | *"Eric Weinstein is a heterodox thinker in science"* | 1 | 2 | **C7 is right** | Calling someone a 'heterodox thinker' in science is an evaluative judgment that can be contested by colleagues or mainstream scientists who view his ideas as unverified speculation rather than legitimate heterodoxy. C4 under-scored this as 1. |
| 2 | `t0032` | Jason Calacanis | *"The event described was the largest organized cheering event in human history."* | 1 | 2 | **Borderline** | Superlative historical claim ('largest organized cheering event in human history'). While historically empirical, measuring 'organized cheering' is ambiguous and contestable. |
| 3 | `t0063` | Jason Calacanis | *"Grockbot is as easy to use as ChatGPT."* | 1 | 2 | **C7 is right** | UX / ease of use comparison between competitive AI products is inherently subjective and disputable by informed users. C4 was overly hesitant. |
| 4 | `t0065` | Jason Calacanis | *"Being able to put two people from a team in the same room and having humans in the loop is going to be a very good idea."* | 1 | 2 | **C4 was right** | 'Putting two people in a room with humans in the loop is a good idea' is an uncontroversial, vague workflow platitude that barely invites reasoned dispute from a well-informed opponent. |
| 5 | `t0072` | Jason Calacanis | *"This is the most profitable core business quarter of any public company ever"* | 0 | 2 | **C4 was right** | Whether a public company achieved the most profitable core business quarter is an objective, verifiable empirical financial accounting fact, not an ideological or strategic dispute. C4 correctly identified it as an empirical check. |
| 6 | `t0099` | Jason Calacanis | *"Mark Banyoff is an incredible salesperson"* | 1 | 2 | **C4 was right** | Within enterprise tech, Benioff's status as an exceptional salesperson is near-universal consensus; an opponent would only quibble with the hyperbolic adjective 'incredible'. |
| 7 | `t0102` | David Sacks | *"AI agents need to go to systems of record to get data from a canonical source of truth."* | 1 | 2 | **C7 is right** | Software architects actively debate whether agents need centralized systems of record or can operate over distributed graphs, vector indices, and local ephemeral stores. This is a core architectural thesis. |
| 8 | `t0103` | David Sacks | *"SaaS products now really need to think about the agent interface, not just the user interface."* | 1 | 2 | **C7 is right** | Product prioritization of API/agent interfaces vs human UI is a genuine strategic disagreement among software leaders. |
| 9 | `t0119` | Jason Calacanis | *"Jensen Huang is clearly maximizing his strategy for open source."* | 1 | 2 | **C7 is right** | Interpreting Nvidia's open-source weights releases as 'open source maxing' vs commoditizing the complement to sell proprietary compute chips is actively debated by market strategists. |
| 10 | `t0131` | Chamath Palihapitiya | *"Companies are going to move up the stack and host the model."* | 1 | 2 | **C7 is right** | Whether SaaS platforms or cloud hyperscalers will capture hosting or if specialized model providers will dominate is an unsettled industry forecast. |
| 11 | `t0135` | Jason Calacanis | *"America has a spending problem"* | 1 | 2 | **C7 is right** | 'America has a spending problem' is one of the classic contested macroeconomic/political claims (spending problem vs revenue/taxation problem). Scoring it 1 in C4 was a clear false-mild score. |
| 12 | `t0169` | Jason Calacanis | *"The national debt is increasing at a faster rate than it was a year ago."* | 1 | 2 | **C4 was right** | Year-over-year rate of debt growth is an arithmetic calculation from Treasury reports. Disputing it requires alleging bad data or specific fiscal period definitions, not an ideological stance. |
| 13 | `t0202` | David Friedberg | *"People want to blame someone when a crisis occurs"* | 1 | 2 | **C4 was right** | This is a folk-psychological platitude about human nature during crises rather than a substantive, defendable proposition. |
| 14 | `t0219` | Jason Calacanis | *"People are migrating around the country or to other countries as a way to vote against out of control spending."* | 1 | 2 | **C7 is right** | Economists and demographers hotly contest whether interstate migration is driven by fiscal spending/taxation vs housing costs, weather, or remote work policies. |
| 15 | `t0238` | David Sacks | *"It is a sign of stupidity not to use AI to help one write these days."* | 1 | 2 | **C7 is right** | Normative claim asserting that choosing not to write with AI is foolish; many professional authors and stylists argue that LLM assistance homogenizes prose and degrades cognitive synthesis. |
| 16 | `t0242` | David Sacks | *"The text clearly came from the author's mind and he used AI to help him write it."* | 1 | 2 | **Borderline** | Assessing the authorship distribution between a specific human author and an AI tool is an unverifiable empirical attribution claim. |
| 17 | `t0322` | David Sacks | *"AI gives people superpowers"* | 1 | 2 | **C7 is right** | The thesis that AI confers transformative capability ('superpowers') vs minor productivity enhancements or skill-atrophy is one of the central ongoing debates in AI economics. |
| 18 | `t0333` | Jason Calacanis | *"Jason Calacanis thinks the subject is phoning it in."* | 1 | 2 | **C7 is right** | Characterizing an executive's or politician's public effort as 'phoning it in' is an evaluative judgment subject to sharp disagreement by observers. |
| 19 | `t0356` | Chamath Palihapitiya | *"Using a specific approach to device management allows parents to actually parent versus just policing device usage."* | 1 | 2 | **Borderline** | Parenting philosophy regarding digital boundary enforcement vs active mentorship mixes subjective parenting values with operational software control. |
| 20 | `t0363` | Chamath Palihapitiya | *"parental control apps are not very effective"* | 1 | 2 | **C7 is right** | Tech reviews, parents, and adolescent psychologists frequently dispute the efficacy and bypass rates of device monitoring tools. |
| 21 | `t0392` | David Friedberg | *"David Friedberg does not like the use of the word vaccine to describe mRNA-based cancer immunotherapy."* | 1 | 2 | **C4 was right** | Stating that a speaker 'does not like' a word is a report of personal preference/taste rather than a contestable proposition about the world. |
| 22 | `t0398` | Jason Calacanis | *"People should get tested early and often for cancer"* | 1 | 2 | **C7 is right** | Oncologists and health economists vigorously debate aggressive early screening due to risks of false positives, over-diagnosis, and unnecessary invasive procedures. |
| 23 | `t0399` | David Friedberg | *"The efficacy of CAR T-cell therapy for blood cancers such as multiple myeloma is incredible."* | 1 | 2 | **C4 was right** | The clinical efficacy of CAR-T for refractory multiple myeloma is an established medical fact with published remission rates; only the colloquial intensifier 'incredible' invites dispute. |

### Resolution of t0072 Demonstrative Blind Spot

- **Turn**: `t0072` (Jason Calacanis)
- **Quote**: *"That is the most profitable core business quarter of any public company ever"*
- **Claim**: *"This is the most profitable core business quarter of any public company ever"*
- **Finding**: LLM scorers exhibit systematic leniency toward demonstrative-initial copular sentences (*"This is the most profitable quarter..."*), treating *"This is..."* as a legitimate deictic topic header rather than an unbound indexical and scoring it 2 despite violating the Level-0 anchor. This blind spot is permanently documented in `v2/docs/design_claim_axes.md` beside Axis 6, noting that the mechanical regex proxy is the required check for this class.

---

## 7. FALSIFICATION — Uncalibrated C4 Scorer on Real-Derived Fidelity Perturbations

The real-derived fidelity failure cases (`t0127`, `t0142`, `t0189`) were evaluated through the uncalibrated C4 prompt template (`score_axes_c4_uncalibrated.md`):
- **Target Sensitivity on Real Failures**: 1 of 3 (33.3%) — only `t0189` (inflation) triggered a score drop (Fidelity 0); both `t0127` (Elon Musk) and `t0142` (Janet Yellen) scored Fidelity 2 under the uncalibrated scorer as well.
- **Off-Target Drop Rate**: 0 of 21 comparisons (0.0%).
- **Key Finding**: Calibration did **not** trade fidelity's real-world recall for perturbation score. The uncalibrated scorer suffered from the exact same entity-resolution leniency on `t0127` and `t0142`. Both scorers detect topic/predicate substitutions (`t0189`) and blunt inversions, while missing entity substitutions where pronouns appear in the source quote.
