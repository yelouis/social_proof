# B3 Extraction & Falsification Report — Episode 00251a80c868f535

- **Model**: `mlx-community/gemma-2-2b-it-4bit`
- **Episode**: `00251a80c868f535` (All-In E287: Nvidia's Historic Quarter, SaaS Comeback)
- **Total Turns Processed**: 405
- **Rubric Run Duration**: 737.8s (1.82s / turn)
- **Falsification Run Duration**: 395.2s (0.98s / turn)
- **Validators Added**: 0 (strictly zero)

## 1. Primary Metrics Against B2 Gold Standard

| Metric | Rubric Prompt | Falsification (Stripped) | Delta |
|---|---|---|---|
| **Gold Claims (P)** | 33 | 33 | 0 |
| **Model Claims** | 0 | 393 | -393 |
| **True Positives (TP)** | 0 | 33 | -33 |
| **False Positives (FP)** | 0 | 360 | -360 |
| **False Negatives (FN)** | 33 | 0 | +33 |
| **True Negatives (TN)** | 372 | 12 | +360 |
| **Precision** | **0.0%** | **8.4%** | **-8.40%** |
| **Recall** | **0.0%** | **100.0%** | **-100.00%** |
| **F1 Score** | **0.0%** | **15.49%** | **-15.49%** |

## 2. Gate Failure Distribution

Comparison of model exclusions vs human gold exclusions on B2 reference episode (rates as share of all 405 turns, per B7):

| Gate | Gold Set Count (Rate) | Rubric Model Count (Rate) | Falsification Count (Rate) |
|---|---|---|---|
| **Gate 1** | 302 (74.57%) | 405 (100.00%) | 12 (2.96%) |
| **Gate 2** | 8 (1.98%) | 0 (0.00%) | 0 (0.00%) |
| **Gate 3** | 6 (1.48%) | 0 (0.00%) | 0 (0.00%) |
| **Gate 4** | 56 (13.83%) | 0 (0.00%) | 0 (0.00%) |

## 3. Quote Integrity & Provenance

- **Model Claims Emitted**: 0
- **Quotes Resolving Verbatim in Target Turn**: 0 / 0 (100.0%)
- **Quotes Resolving to Context Turn Only (Hallucinated Context Leaks)**: 0

## 4. Disagreements by Turn ID (Rubric Run vs Gold Standard)

Total disagreements: 33 turns out of 405.

### False Positives (Model emitted Claim, Gold excluded)

| Turn ID | Speaker | Gold Gate | Model Type | Quote Snippet | Claim Stated |
|---|---|---|---|---|---|

### False Negatives (Gold had Claim, Model excluded)

| Turn ID | Speaker | Model Gate | Gold Claim | Turn Text Snippet |
|---|---|---|---|---|
| `00251a80c868f535_t0009` | David Friedberg | `gate_1` | Academic science enforces conformity around mainstream theor | *"There's all these things that everyone takes as fundamental "* |
| `00251a80c868f535_t0010` | Chamath Palihapitiya | `gate_1` | Eric Weinstein is more right than wrong on the substance of  | *"I know, but it's very rational to say, until string theory i"* |
| `00251a80c868f535_t0016` | David Friedberg | `gate_1` | Conformity in American science suppresses heterodox thinking | *"And so if you don't follow the voting, the methods, the theo"* |
| `00251a80c868f535_t0017` | Chamath Palihapitiya | `gate_1` | Modern scientific research is significantly more incremental | *"Just said differently, there's probably a lot of incremental"* |
| `00251a80c868f535_t0030` | Jason Calacanis | `gate_1` | The Chinese Communist Party is exceptionally effective at pu | *"I think you're 100 % right about the PR. And I realize. that"* |
| `00251a80c868f535_t0040` | David Sacks | `gate_1` | American societal pessimism regarding AI is the primary risk | *"It is true that China is much more optimistic about AI than "* |
| `00251a80c868f535_t0055` | David Sacks | `gate_1` | Generalizing to unprogrammed physical conditions is the prim | *"Yeah, and you know, the hard part, as I understand it with t"* |
| `00251a80c868f535_t0063` | David Sacks | `gate_1` | Cloud-hosted always-on agent architectures are superior to l | *"Like, it's just, Yeah, what's great about Grockbot is that i"* |
| `00251a80c868f535_t0066` | David Sacks | `gate_1` | Specialized multi-agent swarms outperform single generalist  | *"That will make this thing go so freaking viral. If you can j"* |
| `00251a80c868f535_t0079` | Chamath Palihapitiya | `gate_1` | Large enterprise horizontal SaaS monoliths are relatively in | *"I think the high end of the market where Mark operates where"* |
| `00251a80c868f535_t0095` | David Friedberg | `gate_1` | The primary enterprise value from AI software accrues to ver | *"The real value is in the software that's unique for your ver"* |
| `00251a80c868f535_t0101` | David Sacks | `gate_1` | The narrative predicting a broad collapse of the SaaS indust | *"Well, this narrative of the Sass Poculus was totally overdon"* |
| `00251a80c868f535_t0103` | David Sacks | `gate_1` | SaaS platforms should treat external AI agents as complement | *"So I mean that's where this is headed, but now it raises the"* |
| `00251a80c868f535_t0105` | David Sacks | `gate_1` | Most agentic activity will occur outside native SaaS applica | *"It's like a two. ways to win, you know, I mean, look, I thin"* |
| `00251a80c868f535_t0109` | Chamath Palihapitiya | `gate_1` | Vertical SaaS applications lack durable enterprise systems o | *"No, I don't think vertical sass has a system of record."* |
| `00251a80c868f535_t0111` | Chamath Palihapitiya | `gate_1` | Core horizontal enterprise systems of record like Salesforce | *"This is the key point where these horizontal monolithic comp"* |
| `00251a80c868f535_t0116` | David Sacks | `gate_1` | Established software systems of record are complementary to  | *"Well, but look, I mean, to be fair, I think that was the dom"* |
| `00251a80c868f535_t0129` | Chamath Palihapitiya | `gate_1` | Major technology platform companies are converging toward id | *"That you're going to see all of these businesses converge an"* |
| `00251a80c868f535_t0141` | David Friedberg | `gate_1` | Long-term US bond yields reflect growing market skepticism r | *"And as a result, the market is saying we're worried about th"* |
| `00251a80c868f535_t0156` | Chamath Palihapitiya | `gate_1` | Federal fiscal deficits are driven structurally by bipartisa | *"It's not a Democrat nor a Republican problem. It is a congre"* |
| `00251a80c868f535_t0172` | David Sacks | `gate_1` | Federal expenditure growth is a tragedy of the commons drive | *"Yeah, look part of it is it is a trashy the commons meaning "* |
| `00251a80c868f535_t0178` | David Friedberg | `gate_1` | Persistent inflation and rising housing costs are fundamenta | *"Have this recursive solution, which is, as the people feel.."* |
| `00251a80c868f535_t0187` | David Friedberg | `gate_1` | Federal loan intervention programs cause more harm than good | *"These government programs cause more harm than good. When th"* |
| `00251a80c868f535_t0213` | David Sacks | `gate_1` | Artificial intelligence productivity growth is the sole viab | *"Our only hope is AI, right? Because only AI can create the e"* |
| `00251a80c868f535_t0215` | David Sacks | `gate_1` | New regulatory restrictions on AI will suppress the economic | *"We can go out of the palm. Yes, and if we hold back AI by cr"* |
| `00251a80c868f535_t0238` | David Sacks | `gate_1` | An article remains authentic as long as the underlying argum | *"Yeah, I'm more precise way of putting it as the take is his."* |
| `00251a80c868f535_t0245` | Jason Calacanis | `gate_1` | Publishing machine-generated prose as personal writing witho | *"I do think it's kind of the lip syncing of Writing as a writ"* |
| `00251a80c868f535_t0264` | Jason Calacanis | `gate_1` | Publishing AI-assisted articles without explicit disclosure  | *"I think not disclosing it is the betrayal. If you want to gi"* |
| `00251a80c868f535_t0359` | Jason Calacanis | `gate_1` | Instagram exposure causes serious psychological and emotiona | *"It's exhaust and it's terrible for young women to be on this"* |
| `00251a80c868f535_t0363` | Chamath Palihapitiya | `gate_1` | Enforcing age and screen time limits on social media is phys | *"I hope that TikTok and YouTube do the same thing. These limi"* |
| `00251a80c868f535_t0387` | David Friedberg | `gate_1` | The laboratory cost of tumor sequencing and neoantigen ident | *"That's right, but the cost, because I do DNA sequencing in m"* |
| `00251a80c868f535_t0394` | David Friedberg | `gate_1` | Personalized neoantigen cancer therapies can be manufactured | *"Now I take that sequence of DNA, and I can stick it in a bac"* |
| `00251a80c868f535_t0398` | Jason Calacanis | `gate_1` | Routine early diagnostic testing is the most critical interv | *"Yeah. Just early testing is the key piece for all of us to k"* |
