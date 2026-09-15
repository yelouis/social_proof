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
