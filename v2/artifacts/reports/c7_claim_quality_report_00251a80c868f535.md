# Episode E287 (00251a80c868f535) — Claim Quality Profile (C7)

- **Claims evaluated**: 111
- **Claim density**: 27.4% of 405 turns
- **Audit Trail**: 888 of 888 non-empty reasons verified across all 111 claims $\times$ 8 axes.
- **Speaker Panel Status**: Target, Propositionality, and Typing removed due to Pass 1 survivor bias / unvarying candidate distribution; placed in Front-Half Pipeline Filter section below.

## SPEAKER PANEL (how good were the claims made)

| Axis | Mean | Dist [0 / 1 / 2] | Off-Target Contamination (`off_target_drop_rate_pct`) | Status |
|---|---|---|---|---|
| **Voice** | 1.98 | 1 / 0 / 110 | 2.9% | Varies on real claims |
| **Contestability** | 1.88 | 1 / 11 / 99 | 0.0% | Varies on real claims |

## EXTRACTION PANEL (how well we captured them)

| Axis | Mean | Dist [0 / 1 / 2] | 0-Scores Listed by Turn ID | Off-Target Contamination (`off_target_drop_rate_pct`) |
|---|---|---|---|---|
| **Decontextualisation** | 1.84 | 9 / 0 / 102 | 9 claims (00251a80c868f535_t0010, 00251a80c868f535_t0022, 00251a80c868f535_t0032...) | 8.6% |
| **Fidelity** | 1.95 | 3 / 0 / 108 | 3 claims (00251a80c868f535_t0127, 00251a80c868f535_t0142, 00251a80c868f535_t0189) | 31.4% |
| **Granularity** | 1.97 | 0 / 3 / 108 | 0 claims | 8.6% |

## FRONT-HALF PIPELINE FILTER (Pre-Filtered by Pass 1 Gates 1 & 2)

Target, Propositionality, and Typing showed zero or near-zero variance across the 111 extracted candidate claims. Per Step 4, Target and Propositionality were evaluated over 40 turns rejected by Pass 1 (banter, show mechanics, host setup) to resolve survivor bias:

- **Target**: 0: 25 turns (62.5%), 1: 6 turns (15.0%), 2: 9 turns (22.5%). Real candidate claims: 1x0, 0x1, 110x2 (mean 1.98).
- **Propositionality**: 0: 7 turns (17.5%), 1: 15 turns (37.5%), 2: 18 turns (45.0%). Real candidate claims: 0x0, 0x1, 111x2 (mean 2.00).
- **Typing**: Candidate claims: 0: 0 turns (0.0%), 1: 0 turns (0.0%), 2: 111 turns (100.0%) (mean 2.00). Pass 1 screened out conversational filler/banter (typing 0), and under the calibrated prompt's clear taxonomy of 5 commitment types (position, prediction, causal mechanism, evaluative judgment, empirical fact), all 111 candidate claims cleanly fit a single type without ambiguity (in C4, two borderline claims t0017 and t0032 scored 1 due to prompt ambiguity).

**Architectural Conclusion**: Target and Propositionality discriminate cleanly on uncurated raw dialogue (62.5% and 17.5% 0-scores respectively). Their lack of discrimination among extracted candidates was survivor bias: Pass 1 Gates 1 & 2 screened out banter and non-propositional fragments before scoring. Typing similarly shows that all 111 surviving candidates cleanly fit canonical commitment types. Per §20, an axis that cannot vary is not a measurement of the episode and must never be reported as a scalar mean of 2.00; these axes are permanently removed from the Speaker panel and assigned to the front-half extraction pipeline filter.

## OFF-TARGET CONTAMINATION COMPARISON (Single Metric: `off_target_drop_rate_pct`)

| Axis | C5 Off-Target | C6 Off-Target | C7 Off-Target | Threshold (<25%) | Status |
|---|---|---|---|---|---|
| **Voice** | 20.0% | 2.9% | 2.9% | < 25.0% | PASSED |
| **Target** | 40.0% | 0.0% | 0.0% | < 25.0% | PASSED |
| **Propositionality** | 45.7% | 2.9% | 2.9% | < 25.0% | PASSED |
| **Contestability** | 17.1% | 0.0% | 0.0% | < 25.0% | PASSED |
| **Typing** | 51.4% | 2.9% | 2.9% | < 25.0% | PASSED |
| **Decontextualisation** | 8.6% | 8.6% | 8.6% | < 25.0% | PASSED |
| **Fidelity** | 11.4% | 31.4% | 31.4% | < 25.0% | FAILED (regressed) |
| **Granularity** | 22.9% | 8.6% | 8.6% | < 25.0% | PASSED |

## FIDELITY CONTAMINATION DIAGNOSIS (Step 3)

- **Measured Rate**: 31.4% (11/35)
- **Contaminated Axes**: contestability: 1, decontextualisation: 4, granularity: 1, propositionality: 1, target: 1, typing: 1, voice: 2
- **Breakdown by Pair**:
  * `fidelity_01` (00251a80c868f535_t0181): 7 drops (voice, target, propositionality, contestability, typing, decontextualisation, granularity)
  * `fidelity_02` (00251a80c868f535_t0183): 1 drops (voice)
  * `fidelity_03` (00251a80c868f535_t0185): 1 drops (decontextualisation)
  * `fidelity_04` (00251a80c868f535_t0187): 1 drops (decontextualisation)
  * `fidelity_05` (00251a80c868f535_t0192): 1 drops (decontextualisation)
- **Root Cause**: Fidelity perturbations replaced claims with statements about entirely different, unrelated topics (e.g., Tesla Optimus robot, CCP PR, inflation, Salesforce, academic science) on turns concerning California debt, railways, and student loans. Under C6's stricter voice and decontextualisation rules, GLM-4 penalizes Voice ('not said by speaker') and Decontextualisation ('introduces concepts not in quote'). In fidelity_01, the model concluded the claim was completely unrelated to the speaker's statement, collapsing all 7 other axes to 0.
