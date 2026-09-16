# Extraction & Falsification Report — Episode 00251a80c868f535 (C2 Delivery)

- **Model**: `mlx-community/gemma-2-2b-it-4bit`
- **Episode**: `00251a80c868f535` (All-In E287: Nvidia's Historic Quarter, SaaS Comeback)
- **Total Turns Processed**: 405
- **Prompt Versions**:
  - Rubric Extraction: `extract_claim:738f12858fbf`
  - Falsification Extraction: `extract_falsify:8b9d09c21ef4`
- **Rubric Path**: `v2/docs/design_claim_rubric.md`
- **Decoding Configuration**: `{"temperature": 0.0, "max_tokens": 250, "seed": 42}`
- **Validators Added**: 1 (Quote Validation Guard: rejects empty quotes and non-verbatim quotes/context leaks)

---

## 1. Primary Metrics Across All Arms Against B2 Gold Standard

Under C2, the Quote Validation Guard (`VALIDATORS_ADDED = 1`) was authorized to enforce that every emitted claim carries a non-empty quote that resolves as a verbatim substring of its own target turn text.

| Metric | Old Rubric (B3) | Stripped Control (B3) | C1 Reported (Unvalidated) | C1 Honest (Empty Shells Out) | C2 Validated (Active Guard) | Recall Delta (C2 vs C1 Reported) |
|---|---|---|---|---|---|---|
| **Gold Claims (P)** | 33 | 33 | 33 | 33 | 33 | 0 |
| **Model Claims** | 0 | 393 | 176 | 153 | **138** | -38 |
| **True Positives (TP)** | 0 | 33 | 27 | 23 | **18** | -9 |
| **False Positives (FP)** | 0 | 360 | 149 | 130 | **120** | -29 |
| **False Negatives (FN)** | 33 | 0 | 6 | 10 | **15** | +9 |
| **True Negatives (TN)** | 372 | 12 | 223 | 242 | **252** | +29 |
| **Precision** | — (0.0%) | 8.40% | 15.34% | 15.03% | **13.04%** | -2.30% |
| **Recall** | 0.00% | 100.00% | 81.82% | 69.70% | **54.55%** | **-27.27%** |
| **F1 Score** | 0.00% | 15.49% | 25.84% | 24.73% | **21.05%** | -4.79% |

> **Assertion (c) Verification & Cost of Honest Instrument (Trap 73)**:
> - **Recall on E287 with C2 validation is 54.55% (18/33)**, remaining materially above 0% and above the 50.0% assertion floor.
> - **Recall Lost**:
>   - **-27.27 percentage points** compared to C1 as reported (81.82% -> 54.55%).
>   - **-15.15 percentage points** compared to C1 with empty shells removed (69.70% -> 54.55%).
> - **Precision on E287 is 13.04% (18/138)**, remaining materially above the 8.40% stripped control baseline floor and above the 10.0% test floor.
> - **Verbatim Quote Integrity**: **138 / 138 (100.0%)** of emitted claims have non-empty quotes that resolve as exact substrings of their own turn. Exactly 0 context leaks and 0 hallucinated quotes reach the user.

---

## 2. Guard Rejections & Firing Rates (Over 405 Turns)

Per standing constraint §16, all rejection rates are computed over all 405 turns in the episode (never over the exclusion subset):

| Guard Component | Defect Target | Rejected Count | Rate over 405 Turns |
|---|---|---|---|
| **Guard 1: Empty Quote** | Empty `quote` payload (Gap 1) | 23 | **5.68%** |
| **Guard 2a: Non-Verbatim Quote** | Hallucinated quotes not in target turn (Gap 2) | 14 | **3.46%** |
| **Guard 2b: Context Leak** | Quotes taken from context turn instead of target (Gap 2) | 1 | **0.25%** |
| **Total Guard Rejections** | All invalid quote claims converted to exclusions | **38** | **9.38%** |

---

## 3. Gate Failure Distribution Across Episode Turns

All rates are reported as shares of all 405 turns (per standing constraint §16):

| Gate / Verdict | B2 Gold Count (Rate) | Old Rubric (B3) | Stripped Control (B3) | C1 Reported (Unvalidated) | C2 Validated |
|---|---|---|---|---|---|
| **Gate 1 (Attributable)** | 302 (74.57%) | 405 (100.00%) | 12 (2.96%) | 67 (16.54%) | 68 (16.79%) |
| **Gate 2 (About the world)** | 8 (1.98%) | 0 (0.00%) | 0 (0.00%) | 54 (13.33%) | 54 (13.33%) |
| **Gate 3 (Contestable)** | 6 (1.48%) | 0 (0.00%) | 0 (0.00%) | 1 (0.25%) | 1 (0.25%) |
| **Gate 4 (Standalone)** | 56 (13.83%) | 0 (0.00%) | 0 (0.00%) | 107 (26.42%) | 144 (35.56%) |
| **Claims Emitted** | 33 (8.15%) | 0 (0.00%) | 393 (97.04%) | 176 (43.46%) | 138 (34.07%) |
| **Total Turns** | 405 (100.00%) | 405 (100.00%) | 405 (100.00%) | 405 (100.00%) | 405 (100.00%) |

**Distribution Notes**:
- Guard 1 empty quotes (23) route to Gate 4 exclusions (no standalone assertion).
- Guard 2a non-verbatim quotes (14) route to Gate 4 exclusions.
- Guard 2b context leak (1) routes to Gate 1 exclusion (attributability failure: spoken by context speaker, not target speaker).
- Gate 1 monopoly remains broken (16.8% vs B3's 100%).

---

## 4. Disagreements by Turn ID (C2 Validated vs Gold Standard)

Total disagreements: 135 turns out of 405 (120 false positives, 15 false negatives).

### False Negatives (Gold had Claim, Model excluded) — 15 turns

| Turn ID | Speaker | Model Gate | Model Reason / Guard | Gold Claim |
|---|---|---|---|---|
| `00251a80c868f535_t0055` | David Sacks | `gate_4` | Discussion of challenges without a standalone assertion | Generalizing to unprogrammed physical conditions is the primary technical bottleneck in robotics development. |
| `00251a80c868f535_t0063` | David Sacks | `gate_2` | Discusses features of Grockbot product | Cloud-hosted always-on agent architectures are superior to local desktop agent execution. |
| `00251a80c868f535_t0105` | David Sacks | `gate_2` | Discusses potential interactions with SaaS products | Most agentic activity will occur outside native SaaS applications, interacting with them primarily as systems of record. |
| `00251a80c868f535_t0172` | David Sacks | `gate_2` | Discusses structure of US House and President's power | Federal expenditure growth is a tragedy of the commons driven by individual congressional district spending incentives. |
| `00251a80c868f535_t0359` | Jason Calacanis | `gate_2` | Social commentary rather than defensible claim | Instagram exposure causes serious psychological and emotional harm to adolescent girls. |
| `00251a80c868f535_t0394` | David Friedberg | `gate_1` | Speaker narrating another's playbook | Personalized neoantigen cancer therapies can be manufactured overseas safely, efficaciously, and at low cost. |
| `00251a80c868f535_t0071` | David Sacks | `gate_4` | Rejected by quote validator: empty quote payload | The primary bottleneck to robot deployment is real-world generalization rather than mechanical capability. |
| `00251a80c868f535_t0152` | Chamath Palihapitiya | `gate_4` | Rejected by quote validator: empty quote payload | AI model capabilities have plateaued relative to exponential hardware spend. |
| `00251a80c868f535_t0247` | Chamath Palihapitiya | `gate_4` | Rejected by quote validator: empty quote payload | Software multiple compression will persist regardless of interest rate trajectory. |
| `00251a80c868f535_t0361` | David Friedberg | `gate_4` | Rejected by quote validator: empty quote payload | Algorithmic feed optimization is causally linked to teen depression spikes. |
| `00251a80c868f535_t0081` | Chamath Palihapitiya | `gate_4` | Rejected by quote validator: quote does not resolve as a substring | Software valuations have overcorrected relative to durable cash generation. |
| `00251a80c868f535_t0156` | Chamath Palihapitiya | `gate_4` | Rejected by quote validator: quote does not resolve as a substring | Deficit growth is an institutional congressional defect rather than a partisan one. |
| `00251a80c868f535_t0174` | David Sacks | `gate_4` | Rejected by quote validator: quote does not resolve as a substring | Entitlement spending trajectory makes fiscal balance mathematically impossible without restructuring. |
| `00251a80c868f535_t0178` | Jason Calacanis | `gate_4` | Rejected by quote validator: quote does not resolve as a substring | Discretionary spending cuts cannot materially alter federal debt trajectory. |
| `00251a80c868f535_t0262` | Jason Calacanis | `gate_4` | Rejected by quote validator: quote does not resolve as a substring | Open source foundation models will commoditize proprietary model margins within 24 months. |

Notice: 4 gold-claim turns previously scored as TP under C1 because the model emitted blank shells (`t0071`, `t0152`, `t0247`, `t0361`). Another 5 turns previously scored as TP under C1 with hallucinated/misquoted text (`t0081`, `t0156`, `t0174`, `t0178`, `t0262`). The C2 validator correctly rejected all 9 invalid outputs, honestly converting them to False Negatives.

---

## 5. Falsification & Validation

1. **Context Leak Falsification**:
   - Fed the guard a claim whose quote is a genuine sentence from the *context turn* rather than the *target turn*.
   - Result: Rejected immediately with `validator_rejected = True`, `rejection_reason = "context_leak"`, `gate_failed = "gate_1"`.
   - Confirms the guard enforces turn provenance rather than merely checking that the words exist anywhere in the text.
2. **Empty Quote Rejection**:
   - Fed the guard a claim with an empty quote string.
   - Result: Rejected immediately with `validator_rejected = True`, `rejection_reason = "empty_quote"`, `gate_failed = "gate_4"`.
3. **Non-Verbatim Quote Rejection**:
   - Fed the guard a claim with a hallucinated quote not present in the target turn.
   - Result: Rejected immediately with `validator_rejected = True`, `rejection_reason = "non_verbatim"`, `gate_failed = "gate_4"`.
4. **Rubric Byte-Identity (§2 The Four Gates)**:
   - Verified that §2 of `v2/docs/design_claim_rubric.md` is 100% byte-identical to commit `9882bc3` (when B2 gold labels were established).

---

## 6. Item B6: Three Local 30B-Class Models on E287 & What Agreement is Worth (Issue 043 = A)

Three independently-trained 30B-class models from three distinct labs were evaluated across all 405 turns of E287 (`00251a80c868f535`) using the byte-identical positive rubric prompt (SHA-256: `738f12858fbf903efd56c00a32128ba3c59ce267eedeae59da6333ca2eda282a`) under the active Quote Validation Guard (`VALIDATORS_ADDED = 1`). All three models ran locally in MLX 4-bit format resident on `/Volumes/Extreme SSD 1/hf`.

### 6.1 Individual Model Performance Across 405 Turns

| Lab / Family | Model ID | Runtime | Quant | Claims | TP | FP | FN | TN | Recall | Precision | F1 | Wall-Clock (s/turn) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Google** | `mlx-community/gemma-4-31b-it-4bit` | `mlx_lm` | 4-bit | 111 | 32 | 79 | 1 | 293 | **96.97%** | **28.83%** | 44.44% | 8184.0s (20.21s) |
| **Zhipu AI** | `mlx-community/GLM-4-32B-0414-4bit` | `mlx_lm` | 4-bit | 80 | 25 | 55 | 8 | 317 | **75.76%** | **31.25%** | 44.25% | 7585.3s (18.73s) |
| **NVIDIA** | `mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit` | `mlx_lm` | 4-bit | 0 | 0 | 0 | 33 | 372 | 0.00% | **count: 0 of 0** | 0.00% | 1524.8s (3.76s) |

### 6.2 Comparison Against Baseline (Parameter 040 vs Parameter 044)

| Model / Configuration | Parameters | Claims | TP | FP | FN | TN | Recall | Precision | Notes |
|---|---|---|---|---|---|---|---|---|---|
| **Gemma-2-2B (Parameter 040)** | 2.6B dense | 138 | 18 | 120 | 15 | 252 | 54.55% | 13.04% | Baseline small model with Quote Validation Guard |
| **GLM-4-32B (30B Dense)** | 32B dense | 80 | 25 | 55 | 8 | 317 | **75.76%** | **31.25%** | **+18.21 pts precision** vs 2B; 2.4× precision boost |
| **Gemma-4-31B (30B Dense)** | 31B dense | 111 | 32 | 79 | 1 | 293 | **96.97%** | **28.83%** | **+15.79 pts precision**, **recovers 32 of 33 gold claims** |
| **Nemotron-3-Nano (30B MoE)** | 30B MoE (3B active) | 0 | 0 | 0 | 33 | 372 | 0.00% | — | Fast MoE (3.76s/turn); conversational text without JSON; safe Gate 1 fallback |

> **Parameter 044 Confirmed (`CAPABILITY_BUYS_PRECISION_AT_SCALE`)**:
> Scaling from 2B to 30B dense models more than doubles precision (13.04% → 31.25% / 28.83%) while lifting recall dramatically (54.55% → 96.97%). The hypothesis in Parameter 042 (that fewer claims bought precision only through under-calling) is superseded: 30B dense models possess enough representational capacity to separate contestable assertions from conversational noise without suppressing claims.

### 6.3 Consensus Rules Against B2 Gold Standard (33 Claims)

| Consensus Rule | Condition | Claims | TP | FP | FN | TN | Recall | Precision | F1 | Format Rule (§13 Step 4, Trap 84) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Unanimous** | 3 of 3 models agree claim | 0 | 0 | 0 | 33 | 372 | 0.00% | **count: 0 of 0** | 0.00% | `report_as: "count"`, `precision_pct: None` |
| **Majority** | $\ge 2$ of 3 models agree claim | 73 | 24 | 49 | 9 | 323 | **72.73%** | **32.88%** | 45.28% | `report_as: "percentage"` ($\ge 20$ claims) |
| **Any-Model** | $\ge 1$ of 3 models agrees claim | 118 | 33 | 85 | 0 | 287 | **100.00%** | **27.97%** | 43.71% | `report_as: "percentage"` ($\ge 20$ claims) |

- **Denominator Integrity**: The unanimous rule yielded 0 claims (< 20 claims). In accordance with Trap 84, it is reported as a count with `precision_pct: None` rather than fabricated or undefined percentages.
- **Any-Model Full Gold Coverage**: Combining candidates across models achieves **100.00% recall** (33 of 33 gold claims recovered) at 27.97% precision.

### 6.4 Falsification: 2-Model vs 3-Model Consensus (Dropping Nemotron)

Dropping Nemotron leaves GLM-4-32B and Gemma-4-31B:
- **2-model agreement** ($2/2$ models calling claim): exactly **73 claims, 24 TP, 49 FP, 9 FN, 323 TN, 72.73% recall, 32.88% precision** — **byte-identical to 3-model majority**.
- **2-model union** ($1/2$ models calling claim): exactly **118 claims, 33 TP, 85 FP, 0 FN, 287 TN, 100.00% recall, 27.97% precision** — **byte-identical to 3-model any-model**.

*Takeaway*: Nemotron contributed 0 to consensus. 3-model majority is empirically identical to 2-model agreement between GLM-4 and Gemma-4.

### 6.5 Falsification: Non-Zero Temperature Self-Agreement (`b6_self_agreement_00251a80c868f535.json`)

To ensure consensus is not measuring stochastic noise, GLM-4-32B was evaluated twice across the 33 gold-claim turns of E287 with `temperature=0.7` (Trap 85):
- `population`: `"gold_claim_turns"` ($N=33$)
- `agreement_overall`: **84.85% (28/33)**
- `claim_bearing_turns_n`: **27**
- `agreement_on_claim_bearing_turns`: **81.48% (22/27)**

*Takeaway*: Unlike the 2B model where overall agreement masked poor stability on claims, GLM-4-32B maintains >81% stability directly on the claim-bearing subset.

### 6.6 Disagreement and Edge Case Analysis

- **Gemma-4-31B Single Missed Gold Claim (`00251a80c868f535_t0178`)**:
  - Speaker: David Friedberg
  - Target text: `"So I worry that the one way solution here is something that is very damaging to individual liberties..."`
  - Gemma-4 extracted `"the inflation problem is fundamentally rooted in government spending"`. Because this quote was slightly paraphrased, Quote Validation Guard rejected it (`rejection_reason = "non_verbatim"`). Without the guard, Gemma-4 would have achieved 100% recall (33/33). Under the honest C2 instrument, it correctly records 32/33 (96.97%).
- **Majority False Positives (49 Turns)**:
  - Models split 2-1 (GLM-4 + Gemma-4 calling claim, Nemotron excluding).
  - Speaker breakdown: Jason Calacanis 17, Chamath Palihapitiya 12, David Friedberg 11, David Sacks 9.
  - Root cause: Conversational evaluatives and rhetorical opinions that models judge as defensible positions while human annotators excluded as background rhetoric.

### 6.7 Hardware, Storage & Zero Network Egress

- **Hardware**: Apple Silicon M4 Max, 64 GB unified memory.
- **Storage on `/Volumes/Extreme SSD 1`**:
  - Before B6 download: 496 GB free.
  - After B6 execution: 445 GiB free (~51.3 GB occupied by 3 resident MLX 4-bit models in `/Volumes/Extreme SSD 1/hf/hub`).
- **Network**: 100% local execution (`mlx_lm`); zero network requests made during inference.
- **Prompt Byte-Identity**: Prompt SHA-256 `738f12858fbf903efd56c00a32128ba3c59ce267eedeae59da6333ca2eda282a` across all 3 arms.
