# UI Direction — "Show the Receipts"

**Contract for:** Phases 8–10. Covers the Flutter deep-dive client and the extension overlay.

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
  │  ▸ play 01:42:16   ▸ source   ⚠ in tension with ×1 │
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
│   proposal in this debate."                    ▸ play     │
│                                                            │
│  ─────────────── 3 years, 2 months ───────────────         │
│                                                            │
│  May 2024 · Senate testimony · adversarial                │
│  "I support a federal licensing regime for the            │
│   largest training runs."                      ▸ play     │
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

## 6. The extension overlay

The reading-moment surface. Different constraints entirely: the user did not come here for this.

- **Compact, dismissible, corner-anchored.** Never modal, never full-width, never auto-expanding.
- **Never modifies or annotates the article.** No inline highlights, no injected marks in the page body. The article is an index, not a target (invariant I2).
- **Shows at most three Tensions**, most recent first, each with one quote. Everything else is "open full timeline."
- **Renders `insufficient_corpus` as a first-class state**, not as an empty overlay. "We have 6 statements from this person on this topic — not enough to assess" is a useful thing to learn in the reading moment.
- **No badge, no count, no red dot on the toolbar icon.** A persistent "3 contradictions found!" indicator turns a research tool into an outrage feed and will change what the user does with it.

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

## 12. Open decisions

- **Issue 002** — Flutter's role given the API-plus-thin-clients shape.
- **Issue 013** — extension overlay inline on the page vs. popup only.
- **Issue 014** — whether `play the tape` ships in v1; it depends on the audio retention decision (Issue 003).
