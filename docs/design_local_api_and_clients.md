# Local API & Clients

**Contract for:** Phase 7, and the boundary every client speaks across.

**The shape:** Social Proof is a local analysis engine with one HTTP contract and several thin clients. The browser extension, the Flutter desktop app, and any future ambient client are all consumers of the same API. This is what makes them one product instead of three.

---

## 1. Why the API is the product

The alternative — a Flutter app that owns the logic, plus an extension that reimplements a slice of it — guarantees two divergent implementations of contradiction rendering, two evidence-integrity paths, and two places for a bug to produce a false accusation. One contract, one enforcement point.

It also makes the deferred ambient client (`master_implementation_plan.md` §9) an integration rather than a rewrite: it would be a third consumer of `GET /subjects/{id}/assessment`, subject to the same sufficiency gate and the same identity rules.

**Consequence for the stack:** Flutter is now one surface among several rather than *the* app. That is a real change from the original decision and it deserves an explicit selection rather than a quiet redefinition — **Issue 002** in `ongoing_errors.md`.

---

## 2. Security — this is the part that is easy to get wrong

A localhost HTTP server is reachable by **any web page the user has open**. Without protection, a random site's JavaScript can `fetch('http://127.0.0.1:8787/subjects')` and read the entire research corpus.

Four controls, all required:

1. **Bind to `127.0.0.1` only.** Never `0.0.0.0`. Binding to all interfaces exposes the corpus to the local network.
2. **Bearer token on every request.** Generated on first run, stored in the OS keychain, provisioned into the extension and the Flutter client at setup. A hostile page cannot read it.
3. **Strict CORS.** Allow only the extension's origin and the Flutter client. Reject `*` unconditionally — including in development, where "temporarily" becomes permanent.
4. **Reject non-token requests without a distinguishing error.** Same response for a bad token and an unknown route, so the API is not a discovery surface.

Additionally: **no write endpoints for clients** (invariant I8). `POST /ingest` enqueues a job for the worker; it does not write to the claim store. Everything else is `GET`.

---

## 3. Endpoints

```
GET  /health                                    → version, corpus stats, worker status

GET  /subjects?q=<name|handle>                  → candidate subjects, resolved by stated identity
GET  /subjects/{id}                             → profile, corpus_stats, available topics

POST /resolve                                   → §4. Page context in, entities + topics out.
                                                  NOTHING STORED.

GET  /subjects/{id}/topics                      → discovered clusters with labels + counts
GET  /subjects/{id}/assessment?topic=<free text>
                                                → Assessment: axis scores or null+reason,
                                                  sufficiency block, tension ids, versions
GET  /subjects/{id}/timeline?topic=<free text>
                                                → dated claims: quote, stance, hedging,
                                                  source, venue, audio locator

GET  /tensions/{id}                             → both claims in full, both quotes, both
                                                  sources, stated distinction if any,
                                                  audio locators for both sides
GET  /claims/{id}                               → claim + utterance + source chain

GET  /compare?a=<id>&b=<id>&topic=<free text>   → head-to-head; 409 if rubric_versions differ

POST /ingest    {subject_id, adapters[], since} → 202 + job_id
GET  /ingest/{job_id}                           → stage, counts, errors
GET  /ingest/{job_id}/stream                    → SSE progress (ingest runs for hours)
```

**Every response that carries a score also carries its versions** — `rubric_version`, `extraction_version`, `embedding_model`. A client rendering a number without them is out of contract (`design_data_layer.md` §6).

---

## 4. `POST /resolve` — selection-triggered, and the news-as-index boundary

**Issue 013 = selection-triggered.** The extension does not scan pages on load. It fires when the user **highlights text**, and the highlighted span *is* the query.

That is a better shape than page-load inference on four counts, and each is worth keeping in mind while implementing:

1. **Explicit intent.** Nothing runs until the user asks. No ambient scanning, no auto-trigger, no toolbar badge counting things they never asked about.
2. **A far more precise query.** "What is this article about" is a guess. "This specific sentence" is a claim the user is actively questioning, and it usually resolves to a **single proposition** rather than a broad topic — so the answer can be *their history on this exact claim* instead of *their views on AI regulation*.

**What `/resolve` is allowed to return** (Issue 027 = A). Proposition matching runs over embeddings, and an embedding's presence is not evidence that the proposition means anything. Two filters are mandatory, and both are structural:

```sql
WHERE p.status = 'active'
  AND EXISTS (SELECT 1 FROM claims c WHERE c.proposition_id = p.proposition_id)
```

- **`status = 'active'`** — never surface a quarantined proposition (`design_evidence_integrity.md` §4).
- **`EXISTS` against `claims`, not `claim_count`** — a proposition nobody is on record as having asserted is not an answer to "what has this person said about this." Use the existence test, **never the denormalized counter**: `claim_count` has already drifted silently across every row in the table once, and a counter that gates a read is a second copy of the truth waiting to disagree with the first. Keep it for reporting; check it in the integrity pass; do not branch on it.

This is not defence in depth over an unlikely case. Before these filters existed, six of the seven propositions `/resolve` could reach had **zero** live claims, and one of them was fabricated.
3. **A much smaller I2 surface.** A bounded span plus bounded context leaves the machine, not the whole article.
4. **It works anywhere.** Nothing about it is news-specific — a forum post, a PDF, a transcript, an email all behave identically.

```
POST /resolve
{
  "selected_text":  "...",      // the highlighted span — this is the query
  "context_before": "...",      // ≤ 500 chars, for pronoun and subject resolution
  "context_after":  "...",      // ≤ 500 chars
  "page_url":       "...",      // provenance only, never a source
  "page_title":     "..."
}
      ↓
{
  "subjects":    [{id, display_name, confidence}],
  "proposition": {id, canonical_text, confidence} | null,   // the precise hit
  "topics":      [{query_string, confidence}]               // the fallback slice
}
```

**Resolution order, and it matters.** Try the precise answer first and fall back only when it is not available:

1. **Proposition** — embed `selected_text`, search the subject's proposition space filtering structurally for `status = 'active'` and `EXISTS (SELECT 1 FROM claims c WHERE c.proposition_id = p.proposition_id)`. Quarantined propositions (e.g. fabrications) and propositions without live claims are unreachable and never returned. Above threshold, return it. This powers the most useful overlay: *here is everything they have said about this exact claim.*
2. **Topic** — if no proposition clears the bar, resolve to a topic slice as in `design_topic_model.md` §3.
3. **Subject only** — if neither resolves, return the subject with `proposition: null, topics: []`. The overlay then says the corpus has nothing on this, which is a useful answer and must not be rendered as an error.

**Context is for disambiguation only.** `context_before` / `context_after` exist so that *"he said it was the only workable path"* can resolve `he`. They are **never** part of the corpus and never part of the quote.

**Contract, enforced by test rather than by discipline:**

- Selected text and context live in a **request-scoped buffer**. Neither is ever written to DuckDB or the artifact store.
- No `Source`, `Utterance`, `Claim`, `Proposition`, or embedding may be derived from them. **In particular: a proposition is *matched*, never *created*, by this endpoint.**
- The response contains **only** identifiers already in the corpus. Resolution can return zero subjects; it can never invent one.
- After any `/resolve` call, the integrity suite asserts no row anywhere has `origin = 'page_context'`.

**Treat the selection and its context as hostile input.** Both are attacker-controlled: a page can contain text engineered to make resolution return the wrong subject, or instructions aimed at the resolving model. Output is constrained to existing corpus ids, and page content is never interpreted as instructions.

---

### The review site's routes (Issue 033)

The local API also serves the review site — four HTML routes rendered per request, not a second service:

```
GET /                     episodes, newest first
GET /episode/{source_id}  claims grouped by person, in timestamp order
GET /claim/{claim_id}     the Social Proof panel (design_ui_direction.md §6b)
GET /person/{subject_id}  one person across all episodes
```

**These routes open DuckDB `read_only=True`.** The site is a reader; the connection should be incapable of writing, not merely disinclined to. If a read-only connection cannot be established (e.g. because another component holds an exclusive writable lock on the file), the application refuses to start (raises `RuntimeError`) rather than falling back to a writable cursor (Item A0). All writes still go through the worker (**I8**), and §2's four controls cover these routes exactly as they cover `/resolve` — the site adds pages, not a second security surface.

**Quarantine exclusions live in the shared query layer, never in a template.** `tensions.status='published'` and `propositions.status='active'` are conditions on the queries every route calls. A renderer that filters is one conditional away from publishing a fabrication, and this project has published three.

---

## 5. Clients

### Browser extension — the only client (Issue 002)

Flutter is deferred, so the extension carries the whole product. It must therefore support **two depths in one surface**, which is what Issue 013's selection asks for.

**Depth 1 — the overlay.** Appears on highlight, anchored near the selection.
- What the corpus holds on *this specific claim*: the resolved proposition, and the two or three most relevant dated quotes.
- The four axis values, or their null reasons — the "trust vectors."
- Compact, dismissible, never modal, never modifying the page.

**Depth 2 — the expanded view.** One click from the overlay, opening in a panel or extension tab rather than a separate app.
- The full timeline for `(subject, topic)`.
- Every axis with its evidence decomposition.
- Tension cards with both quotes and citation deep links.

**Both depths read the same API.** The expanded view is not a second client; it is the same code rendering more of the same payloads.

- Holds the bearer token in extension storage, unreadable by page scripts.
- **Design tokens live in one `tokens.json`** that generates the extension's CSS custom properties — and, when Flutter arrives, its Dart constants. This is the concrete form of the Issue 002 requirement that the design language stay consistent.

### Flutter app — deferred, not cancelled

When it arrives it renders the same payloads from the same endpoints, using constants generated from the same `tokens.json`. See `design_ui_direction.md`.

### Ambient client — deferred, designed for

Would consume the same `assessment` endpoint. Constrained by invariant I10 (stated identity only, never face or voice matching against a stranger) and invariant I5 (the sufficiency gate, which most private individuals will never clear). Not in scope; not designed out.

---

## 6. Failure modes

| Failure | Consequence | Mitigation |
|---|---|---|
| Server bound to `0.0.0.0` | Corpus readable across the local network | §2.1, asserted at startup |
| Missing or wildcard CORS | Any open web page reads the corpus | §2.3, asserted in tests |
| Page text persisted | Invariant I2 violated; agenda enters the corpus | §4, asserted after every `/resolve` in the integrity suite |
| Client renders a score with no version | Cross-version comparison by the user | Versions required in the payload; client test asserts they render |
| Client renders `null` as `0` | Thin records look damning | Rubric contract §5.1; client test asserts null renders as its reason |
| Extension token readable by page scripts | Same as no auth | Extension storage, never `window` or the DOM |
| Long ingest blocks a request | UI hangs | `202` + job id + SSE progress |

---

## 7. Open decisions

**Resolved:** Issue 002 → extension first, Flutter deferred, shared design tokens. Issue 013 → selection-triggered overlay with an expandable full view (§4). Issue 015 → DuckDB is the only store, so §2's four controls are the entire access-control surface.

**Open:** none blocking this contract.
