<start_of_turn>user
You are a claim extraction tool. Extract claims from the following speaking turn.

{context_turn}

{target_turn}

If the target turn contains a claim, output:
```json
{
  "verdict": "claim",
  "turn_id": "{target_turn_id}",
  "speaker": "{target_speaker}",
  "type": "position" | "prediction" | "causal" | "evaluative" | "contested fact",
  "quote": "<verbatim quote>",
  "claim": "<statement of claim>",
  "offset": 0
}
```

If the target turn does not contain a claim, output:
```json
{
  "verdict": "exclusion",
  "turn_id": "{target_turn_id}",
  "gate_failed": "gate_1",
  "reason": "No claim found"
}
```
<end_of_turn>
<start_of_turn>model
