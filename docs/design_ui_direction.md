# UI Direction — "Show the Receipts"

**Contract for:** Phase 8 onward. The extension is the only client (Issue 002); §2–§5 and §7 describe surfaces it renders in its expanded depth, and that a later Flutter client will render from the same payloads and the same design tokens.

---

## 1. The north star (one sentence)

**The quote is the interface; the score is a footnote on it.**

Every conventional instinct here points the wrong way. A dashboard puts the number in 72pt at the top and buries the evidence behind a chevron. This product must invert that, because the number is the least defensible thing on screen and the quote is the most. If a user remembers one thing from a session, it should be a sentence the subject actually said — with a date next to it.

---

## 2. The timeline is the primary artifact

Not the rubric. The rubric is a summary *of* the timeline.

```
AI REGULATION · 2019–2026 · 84 claims · 11 sources          rubric v1.2

2019 ──●───────────●──────────────────────●─────────── 2026
       │           │                      │
       oppose      oppose                 support ⚠
       ▼           ▼                      ▼
  ┌────────────────────────────────────────────────────┐
  │ Mar 2024 · The Ezra Show · guest · adversarial     │
  │                                                     │
  │ "I've said before that licensing is the wrong      │
  │  tool here, and I still think that."               │
  │                                                     │
  │  ▸ cite 01:42:16   ▸ source   ⚠ in tension with ×1 │
  └────────────────────────────────────────────────────┘
```

Fixed properties:

- **Time is the horizontal axis, always.** Every claim has a date; that is the one thing the product can never be wrong about.
- **Stance is encoded by position or shape, not by colour alone.** Red/green stance coding fails colour-blind readers and reads as approval/disapproval, which is not what stance means.
- **Venue metadata is on the face of the card**, not in a tooltip. "Guest · adversarial" is what makes an audience-divergence pair legible.
- **Every audio-derived claim has a `cite` affordance** — a deep link that opens the original source at the quote's offset (`design_source_acquisition.md` §5.2). Audio is not retained locally (Issue 003 Option C), so this hands off to YouTube, the podcast host, or the institutional transcript rather than playing in-app. It is still the highest-trust element on the card: one click and the reader hears it from the primary source.
- **A claim whose source has no deep-link template renders the affordance as disabled with a reason**, not as a link to the top of a three-hour recording. Sending someone to 00:00 and wishing them luck is worse than admitting the link isn't available.
- **A claim on a `negation_uncertain` utterance carries a visible marker.** The two transcription passes disagreed near a negation, the audio is gone, and it can never be resolved. It appears on the timeline and can never appear in a Tension.

---

## 3. Citation-first rendering (invariant I3)

Non-negotiable, and enforced by widget test rather than by review:

1. **No claim renders without its verbatim quote.** Not a paraphrase, not a summary, not an LLM-written gloss.
2. **No quote renders without its date and a resolvable source link.**
3. **No score renders without its `rubric_version`.**
4. **No score renders without a path to its evidence in one interaction.**

A UI state that violates any of these is a defect of the same class as a wrong number, because it is what turns a citation-backed observation into an unsourced accusation.

---

## 4. Rendering null — the most important screen in the product

`insufficient_corpus`, `no_updates_detected`, and `pattern_not_significant` are **not low scores**, and if they look like low scores the sufficiency gate has failed at the last inch.

> **A null axis must be categorically different in shape, not merely in colour.** A grey bar at zero length reads as zero. An empty slot with a sentence reads as absent.

```
Consistency        ████████████░░░░░░  0.72   19 propositions

Update Integrity   ─── no position changes detected ───
                   Nothing to score. Not a perfect record —
                   an absent one.

Even-handedness    ─── 4 possible double standards, no pattern ───
                   Too few to distinguish from chance.
                   View them anyway →
```

Note the third case: the *evidence is still offered* even though the score is withheld. The system declines to call it a pattern; it does not hide what it found.

**And there is no composite score anywhere in the UI.** No average, no headline number, no letter grade. Adding one rebuilds the trust score the project rejected (`master_implementation_plan.md` §8).

---

## 5. The Tension card

The unit of evidence. Two quotes, side by side, on one shared timeline.

```
┌─ UNACKNOWLEDGED REVERSAL ─────────────────── severity ▓▓░ ─┐
│                                                            │
│  Mar 2021 · own podcast · friendly                        │
│  "Licensing frontier models is the single worst           │
│   proposal in this debate."                    ▸ cite     │
│                                                            │
│  ─────────────── 3 years, 2 months ───────────────         │
│                                                            │
│  May 2024 · Senate testimony · adversarial                │
│  "I support a federal licensing regime for the            │
│   largest training runs."                      ▸ cite     │
│                                                            │
│  No acknowledgement of the change was found in the        │
│  corpus between these dates.                              │
│                                                            │
│  ▸ 41 claims on this proposition   ▸ report a problem     │
└────────────────────────────────────────────────────────────┘
```

- **Type names are descriptive, never accusatory.** "Unacknowledged reversal," not "Caught lying." "Possible double standard," not "Hypocrisy." The card presents; the reader concludes.
- **The gap is labelled in plain language.** Three years is context a bare pair of dates does not convey.
- **The negative finding is stated explicitly** — *"no acknowledgement was found in the corpus"* — because the absence is the actual claim being made, and its scope (this corpus, these dates) belongs on screen.
- **`report a problem` is on every card.** Misattribution and transcription errors will happen; a one-click path from a user who spots one to a quarantined Tension is cheap and load-bearing.
- **A `principle_conflict` card additionally shows the stated distinction verbatim** if one exists — the fairness escape hatch is useless if it is not rendered (`design_principle_extraction.md` §4).

---

## 6. The extension: selection-triggered, two depths

**Issue 013 = selection-triggered.** Nothing appears until the user highlights text. The highlight is the question; the overlay is the answer.

### Depth 1 — the overlay

Anchored near the selection, sized to be read in about five seconds.

```
  +- ON THIS CLAIM ------------------------------+
  |  Dana Reyes . federal licensing of frontier  |
  |  models . 41 claims, 2019-2026               |
  |                                              |
  |  Mar 2021 . own podcast . friendly           |
  |  "...the single worst proposal in this       |
  |   debate."                          > cite   |
  |                                              |
  |  !  1 unacknowledged reversal                |
  |                                              |
  |  Consistency 0.61   .  Specificity 0.38      |
  |  Updates     0.83   .  Even-handed  --       |
  |                                              |
  |  > Full timeline and evidence                |
  +----------------------------------------------+
```

- **Lead with the claim, not the person.** The user highlighted a sentence, not a name. The first line names the resolved proposition, because that is what they asked about.
- **One quote, chosen for contrast** rather than recency — the point is whether the highlighted claim squares with the record.
- **All four axes, always, including nulls.** These are the "trust vectors." An axis rendered as an em-dash with its reason available is more informative than one silently omitted.
- **Never modal, never auto-expanding, never modifying the page.** No highlights injected into the article body, no toolbar badge, no count.
- **Three states that are not errors and must not look like errors:**
  - *Proposition matched* — the layout above.
  - *Topic only* — nothing cleared the proposition threshold; show the topic slice and say which it is.
  - *Nothing in corpus* — "No first-hand record for this person on this topic." A real answer, rendered plainly.

### Depth 2 — the expanded view

One click. Opens in a side panel or extension tab, not a separate application.

Everything in §2-§5: the full timeline on a time axis, all four axes with their evidence decomposition, tension cards with both quotes and citation deep links. **The same components rendering more of the same payloads** — not a second implementation.

### Design tokens

One `tokens.json` (colour, type scale, spacing, radii) generates the extension's CSS custom properties, and later the Flutter client's Dart constants. Hand-copying values into a second client is how two surfaces drift apart, and the Issue 002 selection asked specifically that they not.

---

## 6b. The review site — the same components, no second implementation (Issue 028)

A **local, static** site for reading what the system found: episodes newest-first, each episode's claims grouped by person in timestamp order, and a Social Proof panel on any claim. **Issue 028** settled its four questions — the panel shows *everything* (timeline, four axes, tensions, principles); it is **local only**, with no hosting and therefore no way for a wrong claim about a real person to leave the machine; it is a **static export** of DuckDB to JSON, so there is no server, no write path and no database reachable from a page; and it is **not built until the findings are trustworthy** — specifically, until one tension survives being read by hand.

**It is Depth 2 in a browser tab.** §6's expanded view already specifies this payload, and §157's tokens already style it. Build no second component set.

**Every section renders always, including the empty ones.** `principles` currently holds zero rows and the panel must still show a principles section, reading *"no principle conflicts detected on this topic"* — §4 is the governing screen here, not an edge case. **An honest empty section is a finished feature; a hidden one is not.** The ship gate is that nothing shown is false, never that everything is populated.

**The export is the trust boundary and it enforces rather than assumes.** Quarantined tensions and propositions are excluded by query predicate, never by a template conditional — a renderer that filters is one conditional away from publishing a fabrication, and this project has shipped three. Every exported claim's quote is re-verified verbatim against its utterance at export time rather than trusted from the store.

---

## 7. Head-to-head — exactly two, never N

```
AI REGULATION · A vs B · rubric v1.2

A  2019 ──●──────●───────────────●────────── 2026
                 ╎               ╎
                 ╎ divergence    ╎ divergence
                 ╎               ╎
B  2019 ──●──────●───────────────●────────── 2026
```

- **Two subjects. Always two.** The pair constraint is the entire reason this is legible; N-way is a deliberate non-goal (§8).
- One shared time axis, vertically stacked. **Divergence markers where the two took opposing stances on the same proposition** — which works because propositions are global (`design_topic_model.md` §5).
- **Refuses to render across mismatched `rubric_version`s** and says so, offering recompute. Silently comparing incomparable numbers is worse than declining.

**Secondary comparison view:** a ranked list on **one axis at a time**. One column, one number, sortable, nulls shown as nulls. No radar chart anywhere.

---

## 8. Deliberate non-goals

| Not building | Why |
|---|---|
| Radar / spider charts | Enclosed area is meaningless; axis order changes the shape |
| N-way comparison dashboards | The overwhelm problem. Pairs, or a single-axis list |
| A composite score or letter grade | Rebuilds the rejected trust score |
| Notification badges / contradiction counts on the toolbar | Turns a research tool into an outrage feed |
| Share cards, exportable score images | A screenshot of a number, stripped of its evidence and version, is the exact artefact this design exists to prevent |
| Inline article annotation | Violates news-as-index (I2) |
| Sentiment or tone visualisation | Not measured, not measurable here, and pure vibes |

---

## 9. Tone and visual language

**The reference is a court record or an archive, not a dashboard and not a game.** Sober, dense, typographically serious. Generous whitespace around quotes so they read as documents rather than as data cells. Monospace or a distinctive serif for verbatim text, so a quote is visually unmistakable from interface chrome — the reader should never be uncertain whether they are looking at the subject's words or the app's.

Restraint in colour. Severity earns an accent; everything else is neutral. **No red for "bad."** The product does not have a "bad" — it has "in tension," which is a finding, not a verdict.

---

## 10. Accessibility

- **Contrast checked in an automated test, not by eye.** Body text ≥ 4.5:1, large text and titles ≥ 3.0:1. Assert both — a fix that darkens body text and leaves titles unreadable must still fail.
- **Never colour alone** for stance, severity, or null state. Shape, position, and text carry the same information.
- Full keyboard navigation of timeline and tension cards; quotes selectable and copyable **with their citation attached**.
- Widget tests on animated screens need `accessibleNavigation: true` or they hang — a lesson carried over from the Gaslight project, and it will apply here too.

---

## 11. Motion

Minimal and functional. Timeline scrubbing and card expansion get motion because it aids comprehension of time and hierarchy. Nothing else does. **No reveal animations on findings** — a dramatised contradiction reveal is a tonal disaster for a product whose entire claim is neutrality.

---

## 12. Decisions

**Resolved:** Issue 028 -> local static review site, everything-panel, gated on a hand-verified finding (§6b). Issue 002 -> extension first, Flutter deferred, shared tokens. Issue 013 -> selection-triggered overlay with two depths (SS6). Issue 014 -> no in-app playback; `cite` deep-links to the source at its offset.

**Open:** none blocking this contract.
