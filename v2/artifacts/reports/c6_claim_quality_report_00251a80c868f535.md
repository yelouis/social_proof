# Episode E287 (00251a80c868f535) — Claim Quality Profile (C6)

- **Claims found**: 111
- **Claim density**: 27.4% of 405 turns
- **Non-empty reasons verified**: 888 of 888 (100.0%)

## SPEAKER PANEL (how good were the claims made)

| Axis | Mean | Dist [0 / 1 / 2] | Step 4 Note / Status | Off-Target Drop |
|---|---|---|---|---|
| **Voice** | 1.94 | 3 / 1 / 107 | Varies on real claims | 5.7% |
| **Target** | 2.00 | 0 / 0 / 111 | Pre-filtered by Pass 1 (Step 4 rejected turns: 25x0, 6x1, 9x2) | 2.9% |
| **Propositionality** | 2.00 | 0 / 0 / 111 | Pre-filtered by Pass 1 (Step 4 rejected turns: 7x0, 15x1, 18x2) | 5.7% |
| **Contestability** | 1.65 | 4 / 31 / 76 | Varies on real claims | 8.6% |
| **Typing** | 1.98 | 0 / 2 / 109 | Varies on real claims | 2.9% |

## EXTRACTION PANEL (how well we captured them)

| Axis | Mean | Dist [0 / 1 / 2] | 0-Scores Listed by Turn ID | Off-Target Drop |
|---|---|---|---|---|
| **Decontextualisation** | 1.62 | 18 / 6 / 87 | 18 claims (00251a80c868f535_t0007, 00251a80c868f535_t0010, 00251a80c868f535_t0022...) | 14.3% |
| **Fidelity** | 1.94 | 3 / 1 / 107 | 3 claims (00251a80c868f535_t0144, 00251a80c868f535_t0189, 00251a80c868f535_t0232) | 14.3% |
| **Granularity** | 2.00 | 0 / 0 / 111 | 0 claims | 2.9% |

## Step 4 Architectural Conclusion: Target & Propositionality

On 40 turns rejected by Pass 1 (banter, show mechanics, host setup):
- **Target**: 0: 25 turns, 1: 6 turns, 2: 9 turns.
- **Propositionality**: 0: 7 turns, 1: 15 turns, 2: 18 turns.

**Conclusion**: Both axes discriminate cleanly on raw uncurated dialogue. Their zero variance among the 111 extracted claims was purely survivor bias: Pass 1 Gates 1 & 2 already screened out show banter and non-propositional fragments. They belong in the front-half pipeline filter, not as an episode Speaker panel metric.
