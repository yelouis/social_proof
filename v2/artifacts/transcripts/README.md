# V2 Transcripts & Turn Segmentation (Item B1 Artefact)

This directory contains turn-segmented transcripts for all 23 All-In podcast episodes in the corpus.
Raw 12-word ASR utterances from `v1/social_proof.duckdb` have been grouped into speaking turns,
non-show material (sponsor ad reads, cold-open teasers, and outro remixes) has been stripped,
and interrogative question-anchoring has been classified per turn.

## Summary Metrics

- **Episodes:** 23
- **Total Utterances:** 20,666
- **Total Speaking Turns:** 5,589
- **Retained Turns:** 5,484 (98.1%)
- **Stripped Turns:** 105 (1.9%)
- **Question-Anchored Turns:** 622 of 5,589 (11.13%)

## Turn Length vs. Utterance Length Distribution

| Metric | Raw Utterances | All Turns | Retained Turns | Enrolled Speaker Turns |
|---|---|---|---|---|
| **Median Words** | 12.0 | 23.0 | 23.0 | 39.0 |
| **Mean Words** | 16.3 | 60.3 | 61.0 | 70.3 |
| **Min Words** | 2 | 2 | 2 | 2 |
| **Max Words** | 278 | 400 | 400 | 400 |

> **Finding on Step 1:** Median turn length (23.0 words overall, 39.0 words for enrolled speakers) is several times
> median utterance length (12.0 words). Turns capture complete thoughts and conversational exchanges.

> **Finding on Step 3 (Question-Anchoring):** Question-anchored turns represent **11.13%** of all turns (11.27% of retained turns).
> Because this is well under the ~30% threshold, question-anchoring is a high-precision slice rather than the main extraction path.
> Downstream extraction in B3 cannot rely exclusively on question-anchoring.

## Episode Catalog

| Source ID | Title | Utterances | Turns | Retained | Stripped | Q-Anchored | Q-Anchored % |
|---|---|---|---|---|---|---|---|
| [`00251a80c868f535`](00251a80c868f535.md) | All-In E287: Nvidia's Historic Quarter,  | 1195 | 405 | 393 | 12 | 43 | 10.6% |
| [`04ff0000906a6d10`](04ff0000906a6d10.md) | Mark Cuban on the AI Bubble: Who Actuall | 615 | 146 | 135 | 11 | 14 | 9.6% |
| [`0da89e82768a50ca`](0da89e82768a50ca.md) | Saronic Founders: Autonomous Warships, C | 542 | 91 | 82 | 9 | 15 | 16.5% |
| [`149ff5f2de5ff53a`](149ff5f2de5ff53a.md) | All-In E124: AutoGPT potential, AI regul | 992 | 339 | 337 | 2 | 34 | 10.0% |
| [`210596c997be283b`](210596c997be283b.md) | Chip Stocks Crash, $20B Fund Margin Call | 1018 | 341 | 339 | 2 | 33 | 9.7% |
| [`39b1ef6934b6da6b`](39b1ef6934b6da6b.md) | All-In E165: SaaS recovery & AI investin | 1017 | 361 | 360 | 1 | 40 | 11.1% |
| [`3db1487d23e98021`](3db1487d23e98021.md) | Michael Kratsios: Trump's Science Agenda | 522 | 117 | 109 | 8 | 27 | 23.1% |
| [`56d255b85535c7b0`](56d255b85535c7b0.md) | More Trillion Dollar IPOs, Anthropic $3T | 1154 | 263 | 262 | 1 | 21 | 8.0% |
| [`5d5cfe08c004e87c`](5d5cfe08c004e87c.md) | GPT-6 Hits AGI? Tech Euphoria 2.0, SF Ma | 1051 | 279 | 278 | 1 | 20 | 7.2% |
| [`5e502bb23b6abe5c`](5e502bb23b6abe5c.md) | Can the AI Industry Regulate Itself? Str | 1016 | 337 | 335 | 2 | 27 | 8.0% |
| [`601ab4063555d485`](601ab4063555d485.md) | Eric Weinstein: The State of American Sc | 911 | 140 | 136 | 4 | 23 | 16.4% |
| [`6244e2a46bed1e89`](6244e2a46bed1e89.md) | Open Source Wins, AGI Is Here, and Scors | 657 | 161 | 156 | 5 | 23 | 14.3% |
| [`7162cad935e62307`](7162cad935e62307.md) | Dario Defends Himself, Datacenter Panic, | 1070 | 360 | 357 | 3 | 46 | 12.8% |
| [`79178e47abe6f799`](79178e47abe6f799.md) | Rahm Emanuel: Trump's Foreign Policy, Ch | 854 | 109 | 109 | 0 | 9 | 8.3% |
| [`79e5cda81c5740e9`](79e5cda81c5740e9.md) | The $1/Hour Worker: Four Robotics CEOs o | 902 | 148 | 145 | 3 | 23 | 15.5% |
| [`79f3aaf4ae50dde5`](79f3aaf4ae50dde5.md) | Former Intel CEO on What Went Wrong, Wha | 504 | 111 | 105 | 6 | 15 | 13.5% |
| [`842461fade162070`](842461fade162070.md) | The Fight Over Open Source AI, Anthropic | 1169 | 386 | 384 | 2 | 26 | 6.7% |
| [`8550481c62a4fddf`](8550481c62a4fddf.md) | The Trillion-Dollar Industries AI Is Dis | 503 | 115 | 106 | 9 | 22 | 19.1% |
| [`934af82db84bb725`](934af82db84bb725.md) | AI Sovereignty Wars, Palantir-Nvidia Dea | 1197 | 382 | 381 | 1 | 36 | 9.4% |
| [`9f0b2524821a07d1`](9f0b2524821a07d1.md) | Flock CEO Garrett Langley on Controversy | 681 | 146 | 135 | 11 | 14 | 9.6% |
| [`b4745416c5fc24ee`](b4745416c5fc24ee.md) | Google's AI Brain Drain, SpaceX's Huge Q | 907 | 217 | 215 | 2 | 31 | 14.3% |
| [`d4852b73b3a043bf`](d4852b73b3a043bf.md) | All-In E245: Open Source AI Models, Stat | 1015 | 320 | 319 | 1 | 52 | 16.2% |
| [`ef1c1f5096bc9d01`](ef1c1f5096bc9d01.md) | Anthropic's $2T IPO, Zuck's AI Manifesto | 1174 | 315 | 306 | 9 | 28 | 8.9% |

## Stripped Spans Catalog

Stripped spans encompass sponsor ad reads, cold open soundbites, and terminal outro remix songs.

| Episode | Span (seconds) | Duration (s) | Type | Description |
|---|---|---|---|---|
| `00251a80c868f535` | 4890.0s - 4971.0s | 81.0s | ad_read | All-In Summit sponsor block (Ironhouse, merch.com, Oracle F1, EY) |
| `00251a80c868f535` | 5740.0s - 5800.3s | 60.3s | outro | Outro remix collage ('Besties are gone...') |
| `04ff0000906a6d10` | 50.0s - 83.5s | 33.5s | ad_read | AppLovin ad read |
| `04ff0000906a6d10` | 960.0s - 998.0s | 38.0s | ad_read | Northwest Registered Agent ad read |
| `04ff0000906a6d10` | 2493.7s - 2496.3s | 2.6s | outro | Outro stinger |
| `0da89e82768a50ca` | 41.0s - 68.5s | 27.5s | ad_read | Creative Planning ad read |
| `0da89e82768a50ca` | 1252.0s - 1283.5s | 31.5s | ad_read | Northwest Registered Agent ad read |
| `0da89e82768a50ca` | 2893.4s - 2896.0s | 2.6s | outro | Outro stinger |
| `149ff5f2de5ff53a` | 5560.0s - 5583.5s | 23.5s | outro | Outro remix collage ('What you're that beat...') |
| `210596c997be283b` | 5755.3s - 5784.6s | 29.4s | outro | Outro remix collage ('Beef, what you're the beef...') |
| `39b1ef6934b6da6b` | 5272.4s - 5283.1s | 10.7s | outro | Outro remix collage |
| `3db1487d23e98021` | 0.0s - 44.2s | 44.2s | cold_open | Cold open teaser soundbites |
| `3db1487d23e98021` | 3338.0s - 3355.9s | 18.0s | outro | Outro stinger |
| `56d255b85535c7b0` | 6120.0s - 6122.0s | 2.0s | outro | Outro stinger |
| `5d5cfe08c004e87c` | 5474.5s - 5479.6s | 5.1s | outro | Outro stinger |
| `5e502bb23b6abe5c` | 5381.7s - 5391.1s | 9.5s | outro | Outro stinger |
| `601ab4063555d485` | 0.0s - 24.5s | 24.5s | cold_open | Cold open teaser clips |
| `601ab4063555d485` | 25.0s - 48.5s | 23.5s | ad_read | Creative Planning ad read |
| `601ab4063555d485` | 5400.0s - 5417.3s | 17.3s | outro | Outro stinger |
| `6244e2a46bed1e89` | 75.0s - 108.5s | 33.5s | ad_read | AppLovin ad read |
| `6244e2a46bed1e89` | 2432.0s - 2451.0s | 19.0s | ad_read | Nasdaq ad read |
| `6244e2a46bed1e89` | 3831.6s - 3834.3s | 2.7s | outro | Outro stinger |
| `7162cad935e62307` | 5416.0s - 5445.8s | 29.8s | outro | Outro remix collage |
| `79e5cda81c5740e9` | 20.0s - 56.5s | 36.5s | ad_read | AppLovin ad read |
| `79e5cda81c5740e9` | 4109.7s - 4112.8s | 3.1s | outro | Outro stinger |
| `79f3aaf4ae50dde5` | 72.5s - 99.5s | 27.0s | ad_read | Airwallex ad read |
| `79f3aaf4ae50dde5` | 2963.4s - 2981.2s | 17.8s | outro | Outro remix collage |
| `842461fade162070` | 2740.0s - 2759.0s | 19.0s | ad_read | 8090 promo code / free consultation |
| `8550481c62a4fddf` | 0.0s - 15.0s | 15.0s | cold_open | Cold open teaser clip |
| `8550481c62a4fddf` | 16.0s - 60.9s | 44.9s | ad_read | Airwallex ad read |
| `8550481c62a4fddf` | 1877.0s - 1902.5s | 25.5s | ad_read | Oracle Cloud Infrastructure ad read |
| `8550481c62a4fddf` | 3087.0s - 3089.6s | 2.6s | outro | Outro stinger |
| `9f0b2524821a07d1` | 99.5s - 136.5s | 37.0s | ad_read | AppLovin ad read |
| `9f0b2524821a07d1` | 1560.0s - 1598.5s | 38.5s | ad_read | Numerals sales tax ad read |
| `9f0b2524821a07d1` | 3336.8s - 3354.6s | 17.7s | outro | Outro stinger |
| `b4745416c5fc24ee` | 4504.9s - 4514.5s | 9.7s | outro | Outro stinger |
| `d4852b73b3a043bf` | 5324.3s - 5370.4s | 46.1s | outro | Outro remix collage |
| `ef1c1f5096bc9d01` | 3464.0s - 3493.5s | 29.5s | ad_read | All-In Summit swag / merch.com plug |
| `ef1c1f5096bc9d01` | 5940.0s - 5967.3s | 27.3s | outro | Outro remix collage |

## Invariant & Integrity Verification

- `v1/social_proof.duckdb` SHA-256 Hash: `03c1cd0e4f267161cd7110d530c01ac2cdef20a5dde8b36c84a383fea72a6dbe` (VERIFIED UNCHANGED).
- All 23 episodes processed with zero data loss and zero modifications to source files.