# Claim Extraction — Utterance → Structured Position

**Contract for:** Phase 2. Turns verbatim speech into the structured layer everything downstream queries.

**The thesis in one line:** the model does *extraction*; the database does *detection*. An LLM asked "did this person contradict themselves?" gives an unauditable opinion. An LLM asked "what proposition is being asserted here, and with what stance?" gives a row — and contradiction becomes a `WHERE` clause. That split is why findings in this system are reproducible.

---

## 1. The job

**Utterance → 0..n Claims.** Most utterances produce **zero** claims. Greetings, banter, questions, and "yeah, exactly" are not positions. An extractor that finds a claim in everything is broken, and its output will bury the real signal.

```
Claim {
  utterance_id      # the anchor — exactly one
  proposition_id    # canonical, stance-NEUTRAL (§2)
  stance            # support | oppose | mixed | hedge
  hedging_level     # 0.0 flat assertion … 1.0 pure hedge
  is_own_assertion  # false ⇒ excluded from scoring, retained for review
  exclusion_reason  # reported_speech | hypothetical | sarcasm | steelman
                    # | joke | question | quote_agreement_unclear | null
  quote_span        # [start_char, end_char] into utterance.text_verbatim
  condition         # text of the "if…" clause, or null (§5)
  prior_stance_reported   # §4 — the Update Integrity signal
  change_marker           # §4
  confidence
  extraction_model · prompt_version · extraction_version
}
```

**`quote_span` is not optional.** It is the exact substring of the utterance that constitutes the evidence, and it is what invariant I9's `grep -F` pass checks. A claim whose span does not resolve to real text in `text_verbatim` is a hallucination and must fail the integrity pass, not be rendered with a warning.

### The model returns the quote text, not the offsets

**Never ask a model for `[start_char, end_char]`.** Character offsets require counting characters, tokenizers do not align with characters, and every model — local or frontier — is unreliable at it. The failure is silent: you get plausible-looking integers pointing at the wrong words.

```python
quote_text = extracted.quote_text          # the model returns the substring
idx = utterance.text_verbatim.find(quote_text)
if idx == -1:
    reject_claim(reason="quote_not_found")  # hard fail — this is the fabrication check
quote_span = (idx, idx + len(quote_text))   # computed, never generated
```

If the substring appears more than once, take the first occurrence and flag `quote_ambiguous` — rare, and not worth a second model call. This is strictly better than generated offsets on any model, and it is what makes the whole extraction stage viable on a local model.

---

## 2. Propositions are stance-neutral — the single most important rule

> **A Proposition never contains polarity. Polarity lives in `stance`, always.**

Get this wrong and the system silently never works. If the extractor emits `"AI should be federally licensed"` for one utterance and `"AI should not be federally licensed"` for another, those are two different `proposition_id`s, the self-join in `design_data_layer.md` §4 matches nothing, and a person can reverse themselves in public a hundred times with a perfect Consistency score.

**Canonical form:** a neutral, tenseless statement of the *matter at issue*, with the actor and the polarity stripped out.

| Utterance | ❌ Wrong proposition | ✅ Right proposition | stance |
|---|---|---|---|
| "We absolutely need federal licensing for frontier models." | `AI should be federally licensed` | `federal licensing of frontier AI models` | `support` |
| "Licensing would kill open source. Terrible idea." | `AI should not be licensed` | `federal licensing of frontier AI models` | `oppose` |
| "I could see licensing working, maybe." | `AI licensing might work` | `federal licensing of frontier AI models` | `support`, hedging 0.8 |

Enforce it in the extraction prompt *and* in a validator: reject any proposition text matching `\b(should not|shouldn't|must not|never|oppose|against|no )\b` at canonicalisation time. A rule the model can violate silently is not a rule.

### The actor must be stripped too, and that half was never enforced

The canonical form above strips **the actor as well as the polarity**. Only the polarity half ever got a validator, and the actor half drifted: the v1.2 prompt emitted propositions like **`The speaker believes they created the subject matter`** — 100 of 1,429 propositions (7%) began *"The speaker"*, and 26 more contained a bare *"the subject"*.

Such a string is not a proposition. It names no referent, so it cannot be true or false, and it **breaks the globality guarantee in `design_data_layer.md` §2** — propositions are shared across subjects precisely so two people can be compared on the same matter, and a proposition whose subject is whoever happens to point at it is shared by accident rather than by meaning.

**It is also an embedding attractor.** Similarity between *"The speaker believes X"* and *"The speaker believes Y"* is dominated by the shared frame rather than by X and Y, so deduplication merges them at any plausible threshold. One such proposition absorbed eight unrelated claims — about conspiracy theories, about something taking off, about a third party's powers — and the two tensions that resulted were the second and third fabrications this system has published.

**Therefore:** a proposition must be a standalone declarative resolvable without knowing who uttered it. No `the speaker`, no bare `the subject`, no sentence-initial unbound pronoun. **Reject at canonicalisation time with reason `proposition_not_self_contained`,** alongside the polarity check. *No downstream merge threshold can compensate for this, because the similarity being thresholded is not measuring the claim.*

### Deduplication

New proposition text → embed → nearest-neighbour search in DuckDB (`design_data_layer.md` §4). Above the merge threshold, reuse the existing `proposition_id`. Below, create new. **Issue 008 settled the ambiguous band: adjudication does not earn its cost** — the similarity gap between restatements and distinct claims was clean enough that a second model call added latency without precision.

**Re-pointing a claim invalidates its entailment check.** Validator 6 certifies that a quote supports *the proposition text it was checked against*. A merge that changes `claim.proposition_id` changes exactly that pair, so **entailment must be re-run against the new text, and the merge refused for any claim that fails it.** This is not defence in depth: a merge that skipped it re-pointed claims validated against *"the subject will eventually take off"* onto *"they created the subject matter"*, and the integrity pass had no equivalent of validator 6 to notice. **An extraction-time validator needs an integrity-pass twin, or it certifies a snapshot rather than the store.**

**Merge propositions, not topics.** *"DNA sequencing involves chopping up DNA"* and *"DNA sequencing is relatively inexpensive"* are two facts about one subject, not one assertion phrased twice. Grouping by subject is `design_topic_model.md`'s job; the proposition layer must stay strictly narrower, or a tension degrades into "these two claims are about the same area" rather than "these two claims cannot both be held".

**Bias toward merging.** An over-split proposition space is the same failure as polarity-in-text: two phrasings of one issue never compare, and every contradiction is invisible. Over-merging produces false positives, which are visible and fixable; under-merging produces false negatives, which are not.

---

## 3. The own-assertion guards (invariant I7)

The highest-volume false-positive source in the system. **Do not ask the model to "detect sarcasm."** Ask it to classify the **speech act**: *is the speaker asserting this as their own current view?*

| Excluded | Looks like | Why it's fatal if missed |
|---|---|---|
| `reported_speech` | "The argument from the other side is that X" | Attributes an opponent's position to the speaker |
| `hypothetical` | "Suppose X were true — then…" | Turns a thought experiment into a commitment |
| `steelman` | "The strongest case for X is…" | Punishes exactly the intellectual virtue the product should reward |
| `sarcasm` | "Oh sure, X, brilliant." | Inverts the stance |
| `joke` | Podcast banter | Noise |
| `question` | "Should we do X?" | Not a position |
| `quote_agreement_unclear` | Reading someone's tweet aloud without comment | Genuinely ambiguous — exclude, don't guess |

**Exclusions are recorded, never dropped.** The claim row is written with `is_own_assertion: false` and an `exclusion_reason`. This is what makes the false-exclusion rate measurable against the golden corpus (`e2e_verification_journeys.md`) — a filter you cannot measure is a filter you cannot tune.

---

## 4. Temporal self-reference — where Update Integrity gets its input

This is the most valuable and most overlooked extraction output. A single utterance can carry *three* time-indexed facts:

> "I used to think open weights were reckless. Watching the last two years changed my mind — I think the diffusion argument won."

- **current stance** on the proposition: `support`
- **`prior_stance_reported`**: `oppose` — a *self-reported* earlier position
- **`change_marker`**: `{acknowledged: true, reason_given: true, reason_text: "the diffusion argument won"}`

That row single-handedly converts what would otherwise be scored as an unacknowledged reversal into a **reasoned update** — invariant I6's positive case. Without these fields, Update Integrity has no signal and the rubric punishes honesty.

Detect change markers on: *"I used to", "I've changed my mind", "I was wrong about", "I no longer", "unlike what I said", "I've updated"*. Treat the list as a starting point measured against the golden corpus, not as the definition.

**A self-reported prior stance is not evidence of the prior stance.** It is evidence that they *claim* one. If the corpus contains an actual dated utterance of the earlier position, that is the stronger record — and a mismatch between the two is itself a finding ("says they always believed X; said not-X in 2021"), which is exactly what Update Integrity is for.

---

## 5. Conditionals

*"If inflation stays above 4%, we should raise rates"* is not the same claim as *"we should raise rates."* Store the antecedent in `condition`. **A conditional claim does not contradict an unconditional one** — the tension detector must check `condition` before pairing, or every economist in the corpus becomes a hypocrite.

---

## 6. Two-stage pipeline — the gate is what makes this affordable

Running a frontier model over every utterance in a 300-hour corpus is the difference between a hobby project and a bill. Most utterances contain no position at all.

```
utterance ──▶ [ GATE ]  does this contain an opinion at all?
                 │  ~85% no  ──▶ recorded as gated_out, no model call
                 ▼  ~15% yes
              [ EXTRACT ]  full structured extraction
```

**Both stages run on a local model** (Issue 007 — selected). Target: **Gemma 3 27B at Q4** via MLX or `llama.cpp`, falling back to **Gemma 3 12B** if RAM is tight. No Anthropic API call appears anywhere in the extraction path.

- **Gate:** same local model, short binary prompt, or a smaller sibling if throughput demands it. Bias toward **recall** — a false "yes" costs one extraction call; a false "no" silently loses a real position forever.
- **Extract:** the full structured extraction, with constrained decoding (§8).

### The gate's purpose changed, and it still earns its place

Under a hosted extractor the gate existed to save money. Locally it costs nothing per call — so the reason is now **throughput**. Local inference is slow: a 27B model at Q4 on Apple Silicon runs on the order of tens of tokens per second, and a 300-hour corpus is ~36k utterances. Skipping ~85% of them at a cheap binary classification is roughly a **6× reduction in wall-clock ingest time**, turning a week into a day. Keep the gate.

### Cost, per subject, one time

**Zero dollars, one to three days of background compute.** The trade Issue 007 makes is money for wall-clock time, on a machine that is otherwise idle overnight. Measure actual throughput on your hardware during Phase 2 and record it — a real tokens-per-second figure turns "a few days" into a schedule.

### Build the extractor behind an interface

```python
class ClaimExtractor(Protocol):
    model_id: str          # goes into extraction_version — see §9
    def gate(self, utterance: str) -> bool: ...
    def extract(self, utterance: str) -> ExtractionResult: ...
```

`LocalGemmaExtractor` is the only implementation today. The interface exists so a hosted extractor can be dropped in without touching the pipeline — and the trigger for doing so is **empirical, not aspirational**: if golden-corpus precision on the I7 guards (N1–N4) misses the bar in `e2e_verification_journeys.md` §2, run the same corpus through `claude-opus-5` and compare. That comparison is the whole reason the golden corpus is built before the extractor.

**The known weak spot to watch:** speech-act classification. Sarcasm, steelmanning, and devil's-advocate framing are the subtlest judgments in the whole schema, and they are where a 27B model is most likely to fall short of a frontier one. The errors are silent — a steelman scored as an own assertion doesn't crash anything, it just quietly corrupts an axis. **Measure N1–N4 specifically and separately**; do not let a good aggregate precision number hide a bad number on those four.

---

## 7. KV cache prefix reuse — the local analogue, and it matters more here

The extraction prompt (taxonomy, canonicalisation rules, exclusion definitions, few-shot examples) is large and byte-identical on every call. Locally there is no billing cache — there is a **KV cache**, and reusing its prefix is the difference between hours and days.

Without reuse, every one of ~5.4k extraction calls re-prefills a ~2,000-token system prompt on local hardware. With reuse, the prefix is prefilled once and only the utterance is processed per call.

```
[ SYSTEM PROMPT — stable, ~2000 tokens, prefilled once and held ]
[ utterance text — the only thing that varies, appended last     ]
```

- `llama.cpp`: `--prompt-cache` plus automatic prefix reuse; keep the process warm across the batch rather than spawning per utterance.
- MLX: hold the model and the prefix KV state in one long-lived worker process.

> **The invalidator is the same one, and locally it costs time instead of money:** interpolating the subject's name, the source date, or the venue into the system prompt. Prefix reuse is a byte-prefix match — one changed byte at the top and every call re-prefills from scratch. **Per-subject context goes after the stable prefix, never inside it.**

**Assert it, don't assume it.** Instrument prefill token counts per call and assert in the ingest smoke test that the steady-state count is close to the utterance length, not to the utterance plus the system prompt. A silent regression here looks like "ingest is just slow," which is exactly the kind of thing nobody investigates.

---

## 8. Structured output on a local model — constrained decoding, not prompt-hoped

There is no `output_config.format` here. A local model asked politely for JSON will produce malformed JSON often enough to matter, and a `json.loads`-in-a-retry-loop is the scaffold this design exists to avoid.

**Use constrained decoding.** Generate a GBNF grammar from the Pydantic schema (`llama.cpp`'s `json_schema_to_grammar.py`) and constrain sampling to it, or use `outlines` / LM Format Enforcer for the equivalent at the Python layer. The model then *cannot* emit a token that breaks the schema.

> **Constrained decoding guarantees syntax, never semantics.** You will get perfectly schema-valid JSON containing a hallucinated quote, a polarity-laden proposition, or a confidently mislabelled speech act. **The code-side validators below are more load-bearing on a local model, not less** — they are the only thing standing between a weaker extractor and a corrupted corpus.

### Validators that run on every extraction, in order

1. **`quote_text` resolves** in `text_verbatim` via `.find()` — §1. Hard reject on miss. *This is the fabrication check.*
2. **Proposition carries no polarity** — reject on `\b(should not|shouldn't|must not|never|oppose|against)\b` in the canonical text. §2. Retry once with the violation quoted back; reject on a second failure.
3. **Numeric ranges** — `hedging_level` and `confidence` in `[0,1]`. JSON Schema cannot express this; check it in code.
4. **Enum membership** — `stance` and `exclusion_reason` against the allowed sets. Grammar should cover this; verify anyway.
5. **Consistency** — `is_own_assertion: false` requires a non-null `exclusion_reason`, and vice versa.
6. **Entailment — the quote must actually support the proposition.** *(Added September 3, 2026 after a published tension was traced to two fabricated propositions — Issue 025.)*

   Validators 1–5 all passed on this claim:
   ```
   proposition: "Mandatory state and federal licensing regimes for frontier AI models"
   quote:       "collection like robots or robots having"
   ```
   The quote resolves. It carries no polarity. Ranges and enums are valid. **And the proposition is pure invention.** Validator 1 asks *"are these words real?"*; nothing asked *"do these words say that?"* — which is the question that separates a citation from an accusation.

   **Mechanism — Issue 025 = Option C.** Two deterministic tests, both cheap because the embedder is already loaded:

   ```python
   # 1. Length floor. Both fabrications above were six-word fragments.
   if token_count(quote_text) < MIN_QUOTE_TOKENS:
       reject(reason="quote_too_short")

   # 2. Entailment by embedding similarity, nomic-embed, pinned.
   sim = cosine(embed("search_document: " + quote_text),
                embed("search_document: " + proposition_text))
   if sim < T_ENTAIL_LOW:   reject(reason="quote_does_not_support_proposition")
   elif sim < T_ENTAIL_HIGH: quarantine(reason="entailment_ambiguous")
   ```

   **Both prefixes are `search_document:`** — this is a document-to-document comparison, not a query lookup. Using `search_query:` on either side puts them in different regions of the space and the similarity becomes meaningless (trap 7).

   **The middle band quarantines rather than rejects.** A borderline claim is exactly where a hard rule is least trustworthy, and `design_evidence_integrity.md` §6 requires uncertainty be shown rather than silently resolved in either direction.

   `MIN_QUOTE_TOKENS`, `T_ENTAIL_LOW` and `T_ENTAIL_HIGH` are **measured, not chosen** — `ongoing_errors.md` §2, parameter 026. Provisional until the golden corpus grows, and labelled as such wherever they appear.

   This stays deterministic, so §0's "no LLM at scoring time" rule survives and the same corpus always yields the same rejections.

   **Re-validating entailment on proposition deduplication / re-pointing (Item W1):**
   When proposition deduplication merges propositions based on proposition-to-proposition cosine similarity ($T_{dedup} = 0.86$), claims originally attached to the merged proposition are candidates to re-point to the survivor proposition. However, proposition similarity does not imply quote entailment! If $\text{sim}(\text{quote}, \text{survivor\_proposition}) < T_{ENTAIL\_HIGH} (0.70)$, the claim does not entail the survivor proposition. In that case, the re-point is **refused**, and the claim retains its own proposition (or stays unmerged). This preserves invariant X1 through deduplication. Integrity check #14 (`verify_entailment_holds`) verifies this across all published claims.

**Segmentation is a precondition for all six.** Utterances split on length rather than sentence boundaries produce fragments that begin and end mid-word (`"...as it is bullsh-sh-"`). Asking a model to find a *position* in a fragment that cannot hold one is what invites fabrication in the first place. **Segment on sentence and pause boundaries; a validator is defence in depth, not a substitute for coherent input.**

Log every rejection with its reason. **The rejection rate is a quality signal for the model itself** — if polarity rejections climb after a prompt edit, the prompt got worse, and you will only know because the counter moved.

### The local-model failure mode to watch: it wants to find something

Instruction-tuned models are trained to be helpful, and "return an empty list" reads to them like failure. A local extractor will invent a claim in podcast banter more readily than a frontier one will.

- State it flatly and early in the prompt: **most utterances contain no claim, and an empty list is the expected, correct answer.**
- Put empty-result examples in the few-shot block, not just claim-bearing ones.
- **Measure it.** Golden-corpus negatives must include plain conversational filler, and the false-positive rate on them is a reported metric, not an afterthought.

```python
class ExtractedClaim(BaseModel):
    proposition_text: str
    stance: Literal["support", "oppose", "mixed", "hedge"]
    hedging_level: float
    is_own_assertion: bool
    exclusion_reason: str | None
    quote_text: str                   # the substring; offsets are computed in code (§1)
    condition: str | None
    prior_stance_reported: Literal["support", "oppose"] | None
    change_marker: ChangeMarker | None
    confidence: float

class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim]      # empty list is the common, correct answer
```

This Pydantic model does double duty: it generates the GBNF grammar that constrains decoding, and it validates the parsed result afterwards.

**Sample greedily.** Locally you control decoding, so set `temperature = 0` and a fixed seed. This does not make extraction perfectly reproducible across hardware or library versions, which is exactly why `extraction_version` is stamped on every row (§9) — but it removes run-to-run variance on one machine, which makes prompt iteration against the golden corpus measurable rather than noisy.

---

## 9. Versioning and re-extraction

`extraction_version` is a tuple of `(model_id, prompt_version, schema_version)` and it is **part of the `claim_id` hash**, refining `design_data_layer.md` §3:

```
claim_id = sha256(utterance_id | proposition_id | stance | extraction_version)[:16]
```

Without it, re-extracting under an improved prompt either silently collides with old rows or produces two claims for the same utterance with no way to tell which is current. With it:

- Every query filters to the **active** extraction version. Old claims remain, inert and auditable.
- Re-extraction is a scoped, resumable job over utterances below the new version.
- An assessment computed under one extraction version is **not comparable** to one computed under another — same rule as `rubric_version` (`design_data_layer.md` §6), same enforcement.

---

## 10. Failure modes

| Failure | Consequence | Mitigation |
|---|---|---|
| **Polarity baked into proposition text** | System silently detects nothing, forever | §2 validator, plus a golden-corpus case that fails if a known reversal goes undetected |
| Over-split propositions | Same, quieter | Bias the merge threshold toward merging; measure split rate on the golden corpus |
| Steelman scored as own assertion | Punishes intellectual honesty — the exact inverse of the product's purpose | §3 exclusion taxonomy, measured false-exclusion rate |
| Sarcasm in a deadpan register | Inverted stance | Not fully solvable. Low `confidence` propagates to the Tension; borderline cases quarantine rather than publish |
| Gate false negative | Real position lost with no trace | Recall-biased threshold; gated-out utterances are **recorded**, so the gate is auditable and re-runnable |
| `quote_span` doesn't resolve | Fabricated evidence | Hard-fail before write. Never a warning |
| Cache invalidated by per-subject interpolation | Silent ~10× cost increase | §7 assertion in the smoke test |
| Model emits a claim for banter | Signal buried in noise | "Empty list is the correct answer" stated in the prompt and covered by golden-corpus negatives |

---

## 11. Open decisions

**Resolved:** Issue 007 → local Gemma for both stages (§6). Issue 005 → `nomic-embed-text-v1.5` at 768 dims for dedup. Issue 008 (Parameter 008) → `T_dedup = 0.86` measured empirically over 1,499 live propositions; ambiguous-band adjudication does not earn its cost (Item P0).

**Revisit only with data:** if golden-corpus precision on N1–N4 misses the bar, run the comparison in §6 and file the result as a new issue. Do not switch extractors on a hunch.
