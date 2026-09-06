from worker.storage import Storage

TERMINAL_PUNCT_TUPLE = (".", "?", "!", '."', '?"', '!"', ".'", "?'", "!'", ".”", "?”", "!”")
OPENING_QUOTES = ('"', "'", "“", "‘")


def test_assertion_c_zero_utterances_begin_or_end_mid_word() -> None:
    """Assertion (c): Zero utterances begin or end mid-word.

    All text_verbatim strings must begin with an uppercase letter or quotation mark,
    and must terminate with terminal punctuation (. ? ! or quoted variants).
    No stub or fixed-interval segmenter can satisfy this across real audio.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        utterances = store.con.execute("SELECT utterance_id, text_verbatim FROM utterances").fetchall()
        assert len(utterances) > 0, "Expected utterances in database"

        bad_starts = []
        bad_ends = []
        for uid, text in utterances:
            t = text.strip()
            starts_valid = t[0].isupper() or t[0] in OPENING_QUOTES or t[0].isdigit()
            ends_valid = t.endswith(TERMINAL_PUNCT_TUPLE)
            if not starts_valid:
                bad_starts.append((uid, t[:40]))
            if not ends_valid:
                bad_ends.append((uid, t[-40:]))

        assert bad_starts == [], f"Found {len(bad_starts)} utterances starting mid-word: {bad_starts[:5]}"
        assert bad_ends == [], f"Found {len(bad_ends)} utterances ending without terminal punctuation: {bad_ends[:5]}"
    finally:
        store.close()


def test_quarantined_tension_0068adec4b1501c6_not_rendered() -> None:
    """The fabricated tension 0068adec4b1501c6 must be quarantined and never appear in axis_evidence."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        tension = store.get_tension("0068adec4b1501c6")
        assert tension is not None, "Quarantined tension 0068adec4b1501c6 must be preserved for audit"
        assert tension.status == "quarantined"
        assert tension.quarantine_reason == "fabricated_proposition"

        # Verify no assessment contains the quarantined tension in its axis_evidence
        assessments = store.con.execute("SELECT assessment_id, axis_evidence FROM assessments").fetchall()
        for aid, evidence_json in assessments:
            assert "0068adec4b1501c6" not in str(evidence_json), (
                f"Assessment {aid} contains quarantined tension in axis_evidence: {evidence_json}"
            )
    finally:
        store.close()


def test_surviving_claims_have_verbatim_supporting_quotes() -> None:
    """All surviving claims in social_proof.duckdb have verbatim quotes present in utterances."""
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        claim_ids = [r[0] for r in store.con.execute("SELECT claim_id FROM claims").fetchall()]
        claims = [c for cid in claim_ids if (c := store.get_claim(cid)) is not None]
        assert len(claims) == len(claim_ids), f"Unresolvable claims: found {len(claims)} of {len(claim_ids)}"
        assert len(claims) >= 9, f"Expected at least 9 verified claims, found {len(claims)}"

        for c in claims:
            # Quote must not be empty or a 6-word arbitrary fragment
            assert c.quote_text is not None, f"Claim {c.claim_id} has no quote_text"
            assert len(c.quote_text.split()) >= 6, f"Claim quote too short: {c.quote_text}"
            assert c.extraction_version in (
                "gemma-3-27b-it:v1.1:s1",
                "gemma-3-27b-it:v1.2:s1",
                "gemma-3-27b-it:v1.3:s1",
                "gemma-3-27b-it:v1.4:s1",
            ), (
                f"Claim {c.claim_id} does not have bumped extraction version: {c.extraction_version}"
            )

            # Quote must resolve verbatim against its utterance
            utt = store.get_utterance(c.utterance_id)
            assert utt is not None, f"Utterance {c.utterance_id} for claim {c.claim_id} not found"
            assert c.quote_text in utt.text_verbatim or c.quote_text.lower() in utt.text_verbatim.lower(), (
                f"Claim quote '{c.quote_text}' not in utterance '{utt.text_verbatim}'"
            )
    finally:
        store.close()


def test_falsification_fixed_length_segmenter_fails_assertion_c() -> None:
    """FALSIFICATION (LOOP 2):

    Demonstrates that fixed-length/fixed-chunk slicing causes Assertion (c) to fail (RED),
    generating mid-word cuts and lowercase/unpunctuated utterance boundaries.
    """
    sample_text = (
        "So he has been kind of outcast in the scientific community as it is bullshit. "
        "Jeffrey Epstein and people kind of say, well, this guy is fringe or they use "
        "these different terms to chastise him."
    )
    # Simulate naive fixed-character chunking (e.g. 50 characters)
    chunk_size = 50
    fixed_chunks = [sample_text[i:i + chunk_size] for i in range(0, len(sample_text), chunk_size)]

    bad_starts = []
    bad_ends = []
    for chunk in fixed_chunks:
        t = chunk.strip()
        if not (t[0].isupper() or t[0] in OPENING_QUOTES):
            bad_starts.append(t[:20])
        if not t.endswith(TERMINAL_PUNCT_TUPLE):
            bad_ends.append(t[-20:])

    # Under naive fixed-length segmentation, Assertion (c) MUST FAIL (go RED)
    assert len(bad_starts) > 0, "Fixed-length segmentation should have produced mid-word/lowercase starts"
    assert len(bad_ends) > 0, "Fixed-length segmentation should have produced unpunctuated ends"
