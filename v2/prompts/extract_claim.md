<start_of_turn>user
You are an expert claim extraction engine applying the official claim rubric.

{rubric}

---
TASK:
Analyze the target turn from the transcript and determine whether the speaker asserts a defensible claim under the rubric.
Ask: Does this turn contain a position the speaker would defend if challenged? If so, quote it and state it.

{context_turn}

{target_turn}

INSTRUCTIONS:
1. Search the target turn for a defensible claim:
   - Does the speaker commit to a position, make a prediction, offer a causal explanation, make an evaluation, or assert a contested fact?
   - If found, extract a concise verbatim sentence or clause from the target turn as the quote (never from context) and state the claim as a standalone sentence with pronouns resolved.
2. Verify the candidate against the four gates:
   - Gate 1 (Attributable): Is the speaker asserting it in their own voice? (Fails if guest, reporting what others said, asking a question, banter, reading ad copy, or hypothetical).
   - Gate 2 (About the world): Is it about something outside the podcast recording? (Fails if show mechanics, schedule, tickets, greetings, banter).
   - Gate 3 (Contestable): Could a reasonable person disagree? (Fails on tautologies, undisputed facts, product specs).
   - Gate 4 (Standalone): Can a reader tell what is being asserted without conversational context?
3. If a defensible claim is present and passes the gates, output a claim JSON:
```json
{
  "verdict": "claim",
  "turn_id": "{target_turn_id}",
  "speaker": "{target_speaker}",
  "type": "position" | "prediction" | "causal" | "evaluative" | "contested fact",
  "quote": "<exact verbatim substring from target turn text, NEVER from context>",
  "claim": "<the assertion as a standalone sentence with pronouns resolved>"
}
```
4. Only if NO defensible claim is found in the turn (or the candidate fails a gate), output an exclusion JSON with that gate:
```json
{
  "verdict": "exclusion",
  "turn_id": "{target_turn_id}",
  "gate_failed": "gate_1" | "gate_2" | "gate_3" | "gate_4",
  "reason": "<one sentence reason>"
}
```
Respond strictly with a JSON object.
<end_of_turn>
<start_of_turn>model
