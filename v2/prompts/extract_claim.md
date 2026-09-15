<start_of_turn>user
You are an expert claim extraction engine applying the official claim rubric.

{rubric}

---
TASK:
Analyze the target turn from the transcript and determine whether it contains a defensible claim under the rubric, or must be excluded under Gate 1, 2, 3, or 4.

{context_turn}

{target_turn}

INSTRUCTIONS:
1. Apply the four gates in order:
   - Gate 1 (Attributable): Is the speaker asserting it in their own voice? (Fails if guest, unknown speaker, reporting what others said, asking a question, banter, reading ad copy, or hypothetical).
   - Gate 2 (About the world): Is it about something outside the podcast recording? (Fails if show mechanics, schedule, tickets, greetings, banter).
   - Gate 3 (Contestable): Could a reasonable person disagree? (Fails on tautologies, undisputed facts, product specs).
   - Gate 4 (Standalone): Can a reader tell what is being asserted without conversational context?
2. If ANY gate fails, output an exclusion JSON with that gate:
```json
{
  "verdict": "exclusion",
  "turn_id": "{target_turn_id}",
  "gate_failed": "gate_1" | "gate_2" | "gate_3" | "gate_4",
  "reason": "<one sentence reason>"
}
```
3. If ALL four gates pass, output a claim JSON:
```json
{
  "verdict": "claim",
  "turn_id": "{target_turn_id}",
  "speaker": "{target_speaker}",
  "type": "position" | "prediction" | "causal" | "evaluative" | "contested fact",
  "quote": "<exact verbatim substring from target turn text, NEVER from context>",
  "claim": "<the assertion as a standalone sentence with pronouns resolved>",
  "offset": <character start offset of quote in target turn text>
}
```
Respond strictly with a JSON object.
<end_of_turn>
<start_of_turn>model
