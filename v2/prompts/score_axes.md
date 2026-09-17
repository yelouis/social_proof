<start_of_turn>user
You are an expert claim quality scoring engine evaluating candidate claims against the official claim axes rubric.

{axes}

---
TASK:
Score the candidate extracted claim below against the eight axes defined in the rubric above.
Evaluate each axis strictly according to its 0, 1, or 2 anchor definitions:
- Speaker Panel: Voice, Target, Propositionality, Contestability, Typing.
- Extraction Panel: Decontextualisation, Fidelity, Granularity.

Do NOT evaluate whether the claim is factually true. Evaluate only the commitment made by the speaker and how well the candidate claim captures it.

Target Turn:
Turn ID: {turn_id}
Speaker: {speaker}
Text: {turn_text}

Candidate Extracted Claim:
Quote: "{quote}"
Standalone Claim: "{claim}"

INSTRUCTIONS:
Assign an integer score (0, 1, or 2) and a concise one-line reason for each of the eight axes:
1. voice (0, 1, 2): Did the speaker commit in their own voice? (2 = own voice unhedged/committed, 1 = distanced/hedged, 0 = reporting/quote/hypothetical/ad/banter).
2. target (0, 1, 2): Is it about the world or the show? (2 = external entities/events/dynamics, 1 = show industry meta, 0 = show mechanics/banter/schedule).
3. propositionality (0, 1, 2): Does it assert an explicit predicate/relationship? (2 = clear predicate/mechanism, 1 = thin assertion, 0 = bare topic/filler).
4. contestability (0, 1, 2): Could a well-informed opponent dispute it? (2 = genuinely disputed, 1 = mildly contestable, 0 = tautology/undisputed spec/date).
5. typing (0, 1, 2): Does it fit one commitment type cleanly? (2 = clean fit: position, prediction, causal, evaluative, or contested fact; 1 = competing/mushy; 0 = no type fits).
6. decontextualisation (0, 1, 2): Does the standalone claim resolve all pronouns and indexicals? (2 = fully resolved standalone, 1 = minor anchor missing, 0 = unresolved subject/object such as "it", "this", "they", "the individual").
7. fidelity (0, 1, 2): Is the standalone claim entailed by the quote? (2 = strictly entailed, 1 = entailed with added specificity not in quote, 0 = asserts something not in quote).
8. granularity (0, 1, 2): Is it a single atomic claim? (2 = atomic or single causal link, 1 = two linked assertions, 0 = compound blob mashing distinct points).

OUTPUT FORMAT:
Respond strictly with a JSON object in this format:
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
