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

## 4. `POST /resolve` — the news-as-index boundary

The one endpoint that accepts untrusted content, and therefore the one that enforces invariant I2 in code.

```
POST /resolve
{ "page_text": "...", "page_url": "...", "page_title": "..." }
      ↓
{ "subjects": [{id, display_name, confidence}],
  "topics":   [{query_string, confidence}] }
```

**Contract, enforced by test rather than by discipline:**

- `page_text` lives in a **request-scoped buffer**. It is never written to Firestore, DuckDB, or the artifact store.
- No `Source`, `Utterance`, `Claim`, `Proposition`, or embedding may be derived from it.
- The response contains **only** identifiers already in the corpus. Resolution can return zero subjects; it can never invent one.
- After any `/resolve` call, the integrity suite asserts that no row anywhere has `origin = 'page_context'` (`e2e_verification_journeys.md`).

**Treat page text as hostile input.** It is attacker-controlled: a page can contain text engineered to make resolution return the wrong subject, or instructions aimed at the resolving model. Resolution output is constrained to existing corpus ids, and page content is never interpreted as instructions.

---

## 5. Clients

### Browser extension (Phase 8) — the primary surface

The reason the product exists at the reading moment rather than the researching moment.

- Content script extracts page text → `POST /resolve` → renders a compact, dismissible overlay.
- Overlay shows: subject, resolved topic, the three axis values (or their null reasons), and the two or three most recent Tensions with quotes.
- "Open full timeline" hands off to the Flutter client.
- **Non-blocking and opt-in per page.** It never modifies the page, never auto-expands, and never editorialises the article it is sitting on.
- Holds the bearer token in extension storage, unreadable by page scripts.

### Flutter macOS app (Phase 9) — the deep-dive surface

Full timelines, evidence browsing, corpus management, the ingest queue, head-to-head. Reads the API over localhost like any other client. See `design_ui_direction.md`.

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

- **Issue 002** — Flutter as one client among several vs. the primary app vs. dropping it for a web client.
- **Issue 013** — whether the extension ships the overlay inline on the page or in the extension popup only.
