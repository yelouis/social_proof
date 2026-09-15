# Extraction & Falsification Report — Episode 00251a80c868f535 (C1 Delivery)

- **Model**: `mlx-community/gemma-2-2b-it-4bit`
- **Episode**: `00251a80c868f535` (All-In E287: Nvidia's Historic Quarter, SaaS Comeback)
- **Total Turns Processed**: 405
- **C1 Rubric Run Duration**: 841.4s (2.08s / turn)
- **Prompt Versions**:
  - Rubric Extraction: `extract_claim:738f12858fbf`
  - Falsification Extraction: `extract_falsify:8b9d09c21ef4`
- **Rubric Path**: `v2/docs/design_claim_rubric.md`
- **Decoding Configuration**: `{"temperature": 0.0, "max_tokens": 250, "seed": 42}`
- **Validators Added**: 0 (strictly zero)

---

## 1. Primary Metrics Against B2 Gold Standard

| Metric | Old Rubric (B3) | Stripped Control (B3) | New Rubric (C1) | Delta (C1 vs Old) | Delta (C1 vs Stripped) |
|---|---|---|---|---|---|
| **Gold Claims (P)** | 33 | 33 | 33 | 0 | 0 |
| **Model Claims** | 0 | 393 | 176 | +176 | -217 |
| **True Positives (TP)** | 0 | 33 | 27 | +27 | -6 |
| **False Positives (FP)** | 0 | 360 | 149 | +149 | -211 |
| **False Negatives (FN)** | 33 | 0 | 6 | -27 | +6 |
| **True Negatives (TN)** | 372 | 12 | 223 | -149 | +211 |
| **Precision** | **—** (0.0%) | **8.40%** | **15.34%** | **+15.34%** | **+6.94%** |
| **Recall** | **0.00%** | **100.00%** | **81.82%** | **+81.82%** | **-18.18%** |
| **F1 Score** | **0.00%** | **15.49%** | **25.84%** | **+25.84%** | **+10.35%** |

> **Assertion (c) Verification**:
> - **Recall on E287 (81.82%) is materially above 0%** (27 of 33 gold claims retrieved).
> - **Precision on E287 (15.34%) is materially above the 8.40% precision floor** set by the degenerate stripped baseline, representing an 82.6% relative improvement in precision while eliminating 211 false positives.

---

## 2. Gate Failure Distribution

All rates are reported as shares of all 405 turns (per B7 standing constraint §15):

| Gate / Verdict | B2 Gold Count (Rate) | Old Rubric (B3) | Stripped Control (B3) | New Rubric (C1) |
|---|---|---|---|---|
| **Gate 1 (Attributable)** | 302 (74.57%) | 405 (100.00%) | 12 (2.96%) | 67 (16.54%) |
| **Gate 2 (About the world)** | 8 (1.98%) | 0 (0.00%) | 0 (0.00%) | 54 (13.33%) |
| **Gate 3 (Contestable)** | 6 (1.48%) | 0 (0.00%) | 0 (0.00%) | 1 (0.25%) |
| **Gate 4 (Standalone)** | 56 (13.83%) | 0 (0.00%) | 0 (0.00%) | 107 (26.42%) |
| **Claims Emitted** | 33 (8.15%) | 0 (0.00%) | 393 (97.04%) | 176 (43.46%) |
| **Total Turns** | 405 (100.00%) | 405 (100.00%) | 405 (100.00%) | 405 (100.00%) |

**Distribution Takeaway**:
Under the Old Rubric, the model suffered total gate collapse (100% Gate 1, 0 claims). Under C1's positive rubric and elicitation prompt, Gate 1 monopoly is broken: the model actively reasons across Gate 1 (16.5%), Gate 2 (13.3%), Gate 3 (0.3%), and Gate 4 (26.4%), successfully distinguishing conversational deixis and mechanics from defensible positions.

---

## 3. Quote Integrity & Provenance

- **Model Claims Emitted**: 176
- **Verbatim Quote Matches in Target Turn**: 138 / 176 (78.41%)
- **Quotes Resolving to Context Turn Only (Hallucinated Context Leaks)**: 1 / 176 (0.57%)

---

## 4. Disagreements by Turn ID (C1 Run vs Gold Standard)

Total disagreements: 155 turns out of 405 (down from 360 disagreements in the stripped control).

### False Negatives (Gold had Claim, Model excluded) — 6 turns

| Turn ID | Speaker | Model Gate | Model Reason | Gold Claim |
|---|---|---|---|---|
| `00251a80c868f535_t0055` | David Sacks | `gate_4` | Discussion of challenges without a standalone assertion | Generalizing to unprogrammed physical conditions is the primary technical bottleneck in robotics development. |
| `00251a80c868f535_t0063` | David Sacks | `gate_2` | Discusses features of Grockbot product | Cloud-hosted always-on agent architectures are superior to local desktop agent execution. |
| `00251a80c868f535_t0105` | David Sacks | `gate_2` | Discusses potential interactions with SaaS products | Most agentic activity will occur outside native SaaS applications, interacting with them primarily as systems of record. |
| `00251a80c868f535_t0172` | David Sacks | `gate_2` | Discusses structure of US House and President's power | Federal expenditure growth is a tragedy of the commons driven by individual congressional district spending incentives. |
| `00251a80c868f535_t0359` | Jason Calacanis | `gate_2` | Social commentary rather than defensible claim | Instagram exposure causes serious psychological and emotional harm to adolescent girls. |
| `00251a80c868f535_t0394` | David Friedberg | `gate_1` | Speaker narrating another's playbook | Personalized neoantigen cancer therapies can be manufactured overseas safely, efficaciously, and at low cost. |

---

## 5. Falsification & Scientific Diagnosis

We conducted two controlled falsification checks to isolate the mechanism of the 0% collapse:

1. **Old Prompt Template + Old Rubric**:
   - Evaluated on sample turns (9, 10, 40, 60).
   - Result: **0 claims, 100% Gate 1 exclusions** (identical to B3 collapse).
2. **Old Rubric Text through New Positive Prompt Template**:
   - Evaluated across all 33 gold claims.
   - Result: **29 / 33 claims recovered (87.9% recall)**.

**Diagnosis for Issue 036**:
The collapse in B3 was primarily driven by the **negative, exclusion-first prompt structure** (`"Apply the four gates in order... If ANY gate fails, output an exclusion JSON"`), which handed the model four reasons to say "no" before ever asking what to find. Moving the prompts to editable Markdown (`v2/prompts/extract_claim.md`) and restructuring them to elicit defensible claims first—using the gates as verification rather than a gauntlet—completely resolved the collapse.
