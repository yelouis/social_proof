<start_of_turn>user
You are an independent quality auditor measuring epistemic commitment and extraction accuracy on conversational claims.

RUBRIC SPECIFICATION:
{axes}

---
CONTEXT AND INPUT DATA:
Transcript Turn:
- Turn ID: {turn_id}
- Speaker Label: {speaker}
- Full Turn Content: {turn_text}

Candidate Claim Formulation:
- Source Quote: "{quote}"
- Proposed Standalone Claim: "{claim}"

AUDIT REQUIREMENTS:
Please audit the proposed candidate claim across each of the eight standard evaluation axes specified in the rubric.
Do not judge truth value or empirical correctness. Evaluate the speaker's stated commitment and the fidelity of the standalone extraction.
Every axis receives an integer evaluation rating of 0, 1, or 2, paired with a brief explanatory rationale.

Review the dimensions in two panels:
[Extraction Quality Dimensions]
- decontextualisation (0, 1, 2): Autonomous comprehensibility without external conversation context. Unresolved referents or indexicals ("it", "they", "this", "the speaker") score 0. Minor missing anchors score 1. Fully self-contained statements score 2.
- fidelity (0, 1, 2): Entailment by the source quote. Extrapolations or unsupported assertions score 0. Entailments with ungrounded specificity score 1. Strict semantic entailment scores 2.
- granularity (0, 1, 2): Atomicity of assertion. Multi-claim compound blobs score 0. Linked assertions score 1. Single propositions or tight causal links score 2.

[Speaker Commitment Dimensions]
- voice (0, 1, 2): Degree of speaker ownership. Attributed hearsay, jokes, or quotes score 0. Hedged or distanced stances score 1. Direct, committed personal assertions score 2.
- target (0, 1, 2): Subject of focus. Show mechanics, banter, or meta scheduling score 0. Meta-commentary on the media industry scores 1. External world events, market dynamics, and phenomena score 2.
- propositionality (0, 1, 2): Falsifiable predicate structure. Incomplete thoughts, conversational filler, or bare topic headers score 0. Thin descriptive remarks score 1. Clear relational mechanisms score 2.
- contestability (0, 1, 2): Capacity for dispute. Tautologies, definitions, or undisputed facts score 0. Mildly debatable assertions score 1. Substantially contested positions score 2.
- typing (0, 1, 2): Categorical taxonomy fit. Vague unclassifiable remarks score 0. Ambiguous hybrid types score 1. Unambiguous fit into position, prediction, causal, evaluative, or contested fact scores 2.

RETURN FORMAT:
Provide your verdict as a single JSON code block:
```json
{
  "turn_id": "{turn_id}",
  "voice": 0 | 1 | 2,
  "voice_reason": "<one-line reason>",
  "target": 0 | 1 | 2,
  "target_reason": "<one-line reason>",
  "propositionality": 0 | 1 | 2,
  "propositionality_reason": "<one-line reason>",
  "contestability": 0 | 1 | 2,
  "contestability_reason": "<one-line reason>",
  "typing": 0 | 1 | 2,
  "typing_reason": "<one-line reason>",
  "decontextualisation": 0 | 1 | 2,
  "decontextualisation_reason": "<one-line reason>",
  "fidelity": 0 | 1 | 2,
  "fidelity_reason": "<one-line reason>",
  "granularity": 0 | 1 | 2,
  "granularity_reason": "<one-line reason>"
}
```
<end_of_turn>
<start_of_turn>model
