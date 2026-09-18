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
   CRITICAL VOICE RULE: If the candidate claim reports or attributes what someone else said, argues, speculated, or claimed (e.g., 'Critics argue...', 'Elon Musk has claimed...', 'Some analysts reported...', 'Industry observers speculate...', 'Television pundits frequently argue...'), the speaker is merely reporting an external claim rather than making their own commitment. It MUST be scored 0 or 1, NEVER 2.
2. target (0, 1, 2): Is it about the world or the show? (2 = external entities/events/dynamics, 1 = show industry meta, 0 = show mechanics/banter/schedule/show self-assessment). Note: An unhedged opinion or prediction about the podcast itself or its panel is target=0 or 1, but retains full voice=2, propositionality=2, and contestability=2.
3. propositionality (0, 1, 2): Does it assert an explicit predicate/relationship? (2 = clear predicate/mechanism relating concepts, 1 = thin assertion e.g. 'AI is a big deal', 0 = bare topic/filler).
   CRITICAL PROPOSITIONALITY RULE: An assertion of generic importance or thin relevance without a concrete causal mechanism or empirical consequence (e.g. 'X is a very big deal', 'X is remarkably important', 'X is a notable engineering pursuit', 'X matters a lot', 'X is definitely significant') is a thin assertion and MUST be scored 1, NEVER 2.
4. contestability (0, 1, 2): Could a well-informed opponent dispute it? (2 = genuinely disputed, 1 = mildly contestable, 0 = undisputed empirical fact/spec/date or tautology). Note: An undisputed empirical fact or date has contestability=0, but retains typing=2 (empirical fact) and propositionality=2.
5. typing (0, 1, 2): Does it fit one commitment type cleanly?
   - 2 = clean fit into exactly one type: position (normative/recommendation), prediction (future forecast), causal (mechanism), evaluative (value judgment), or empirical fact.
   - 1 = two types compete, or the modality is mushy/vague/ambiguous without a clear mechanism or forecast (e.g. 'there is an unspecified dynamic...', 'shares an ambiguous relationship', 'could have some kind of undetermined relationship', 'reflect assorted continuous interactions', 'involve several ongoing considerations'). Any assertion describing vague, mushy, or ambiguous relations between concepts MUST be scored 1, NEVER 2.
   - 0 = no type fits (conversational filler, conversational agreement, or unclassifiable fluff).
6. decontextualisation (0, 1, 2): Does the standalone claim resolve all pronouns and indexicals? (2 = fully resolved standalone, 1 = minor anchor missing, 0 = unresolved subject/object such as "it", "this", "they", "the individual", "the company").
   CRITICAL DECONTEXTUALISATION RULE: The standalone claim must stand completely on its own WITHOUT relying on the quote or turn text. If a reader seeing ONLY the standalone claim sentence does not know who or what 'They', 'This', 'It', or placeholder terms like 'the company discussed' or 'the discussed entity' refers to because the entity is not named in the claim itself, it is NOT fully resolved and MUST be scored 0 or 1, NEVER 2. Even if the quote mentions the entity, an unresolved pronoun or placeholder term in the standalone claim MUST score 0 or 1.
7. fidelity (0, 1, 2): Is the standalone claim entailed by the quote? (2 = strictly entailed, 1 = entailed with added specificity not in quote, 0 = asserts something not in quote).
8. granularity (0, 1, 2): Is it a single atomic claim?
   - 2 = strictly atomic single proposition (e.g. 'A causes B'). Must assert only ONE point without secondary descriptive/relative clauses, and never bundle a critique with an affirmative explanation.
   - 1 = two linked assertions, an assertion with a relative or descriptive clause (', which is...', ', caused by...'), a critique bundled with an alternative explanation, or any compound statement over 25 words.
   - 0 = compound blob mashing distinct points or multiple clauses that could be separately true or false.
   CRITICAL GRANULARITY RULE: Score 2 is strictly reserved for a single atomic proposition without secondary descriptive or relative clauses. Syntactic and structural compound rules:
   1) Any claim with a chained causal assertion or relative clause (e.g. ', caused by...', ', which is...', ', who is...') embeds a secondary proposition or causal link and MUST be scored 1, NEVER 2.
   2) Any claim that bundles a critique of an inaccurate heuristic or concept together with an alternative thesis of how it actually works (e.g., asserting that treating AI as a replacement is not accurate AND asserting that AI is a magnification of human creativity) bundles two linked assertions and MUST be scored 1, NEVER 2.
   3) Any claim that embeds secondary background claims, multiple clauses, or exceeds 35 words is compound and MUST be scored 1 or 0, NEVER 2.

CRITICAL ORTHOGONALITY RULE:
Evaluate each axis in strict isolation based ONLY on its specific anchor definition.
- A claim about the show (target=0) can still have voice=2, propositionality=2, contestability=2, and typing=2 if it makes a committed, contestable assertion about the show.
- An undisputed empirical fact or date (contestability=0) still has typing=2 (empirical fact), voice=2, and propositionality=2.
- A thin assertion (propositionality=1) still has voice=2, contestability=2, and typing=2.
- A mushy modality claim (typing=1) still has target=2, voice=2, and propositionality=2.
Never let a low score on one axis pull down independent scores on other axes.

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
