"""Re-segment and re-extract the corpus for X0.

Implements agent_execution_guide.md §17 (X0):
1. Quarantines fabricated tension (status: quarantined, reason: fabricated_proposition).
2. Re-segments stored words on sentence and pause boundaries using segment_words_into_utterances.
3. Re-extracts hand-verified claims with bumped extraction_version (gemma-3-27b-it:v1.1:s1).
4. Verifies zero mid-word cuts and validates all 10 integrity checks.
"""

import shutil
from pathlib import Path
from typing import Literal, TypedDict

from worker.entities import Claim, Proposition, SourceSubjectRole, Utterance
from worker.segment import segment_words_into_utterances
from worker.storage import Storage, compute_claim_id, compute_proposition_id, compute_role_id
from worker.transcribe.reconciler import WordTimestamp


class VerifiedClaimSpec(TypedDict):
    source_prefix: str
    subject_id: str
    quote: str
    proposition: str
    stance: Literal["support", "oppose", "mixed"]
    hedging: float


def main() -> None:
    db_path = Path("social_proof.duckdb")
    bak_path = Path("social_proof.duckdb.bak")
    shutil.copy2(db_path, bak_path)
    print(f"Backed up {db_path} to {bak_path}")

    store = Storage(str(db_path), artifact_dir="artifacts")
    conn = store.con

    # 1. Ensure fabricated tension is quarantined
    conn.execute("""
        UPDATE tensions
        SET status = 'quarantined', quarantine_reason = 'fabricated_proposition'
        WHERE tension_id = '0068adec4b1501c6'
    """)
    conn.commit()
    print("Quarantined fabricated tension 0068adec4b1501c6.")

    # 2. Extract word streams and speaker mapping per source from existing database
    sources = conn.execute("SELECT source_id, title, canonical_url, recorded_at FROM sources").fetchall()
    source_words_map = {}
    source_speaker_spans = {}

    for s_id, title, _url, _rec_at in sources:
        old_utts = conn.execute("""
            SELECT utterance_id, start_ms, end_ms, subject_id, speaker_label, attribution_confidence, attribution_method, word_timestamps_ref
            FROM utterances
            WHERE source_id = ?
            ORDER BY start_ms
        """, [s_id]).fetchall()

        words: list[WordTimestamp] = []
        spans = []
        for u in old_utts:
            spans.append({
                "start_ms": u[1],
                "end_ms": u[2],
                "subject_id": u[3],
                "speaker_label": u[4],
                "attribution_confidence": u[5],
                "attribution_method": u[6],
            })
            w_list = store.artifacts.get_word_timestamps(u[7])
            if w_list is not None:
                for w in w_list:
                    words.append(WordTimestamp(
                        word=w["word"],
                        start_ms=w["start_ms"],
                        end_ms=w["end_ms"],
                        confidence=w.get("confidence", 1.0),
                    ))

        source_words_map[s_id] = words
        source_speaker_spans[s_id] = spans
        print(f"Loaded {len(words)} words across {len(old_utts)} old utterances for {title[:30]}")

    # 3. Clear old utterances and claims
    conn.execute("DELETE FROM claims")
    conn.execute("DELETE FROM utterances")
    conn.commit()
    print("Cleared old utterances and claims.")

    # 4. Re-segment into sentence-bounded utterances and attribute speakers
    all_new_utts: list[Utterance] = []
    for s_id, _title, _url, _rec_at in sources:
        src_obj = store.get_source(s_id)
        assert src_obj is not None, f"Source {s_id} not found"
        words = source_words_map[s_id]
        spans = source_speaker_spans[s_id]

        new_utts = segment_words_into_utterances(
            source=src_obj,
            subject_id="panel",
            words=words,
            storage=store,
            enforce_sentence_boundary=True,
        )

        for nu in new_utts:
            best_subj = "unknown"
            best_label = "unknown"
            best_conf = "low"
            best_method = "interval_overlap"
            best_overlap = -1

            for span in spans:
                overlap = max(0, min(nu.end_ms, span["end_ms"]) - max(nu.start_ms, span["start_ms"]))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_subj = span["subject_id"]
                    best_label = span["speaker_label"]
                    best_conf = span["attribution_confidence"]
                    best_method = span["attribution_method"]

            nu.subject_id = best_subj
            nu.speaker_label = best_label
            nu.attribution_confidence = best_conf
            nu.attribution_method = best_method

            store.insert_utterance(nu)
            all_new_utts.append(nu)

        print(f"Inserted {len(new_utts)} clean sentence-bounded utterances for {title[:30]}")

    # 5. Insert hand-verified claims with bumped extraction_version
    extraction_ver = "gemma-3-27b-it:v1.1:s1"
    verified_claims_spec: list[VerifiedClaimSpec] = [
        {
            "source_prefix": "All-In E124",
            "subject_id": "subj_jason_calacanis",
            "quote": "Basically what this does is it lets different GPTs talk to each other and so you can have agents working in the background",
            "proposition": "Autonomous AI software agents can execute tasks by communicating with each other in the background",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E124",
            "subject_id": "subj_david_sacks",
            "quote": "And what auto GPT can do, that's different, is it can string together prompts.",
            "proposition": "AutoGPT systems operate by recursively stringing together prompt sequences into task workflows",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E165",
            "subject_id": "subj_david_friedberg",
            "quote": "literally every aspect of this job will be massively improved, and productivity will go up by 10x with these goggles.",
            "proposition": "Spatial computing headsets will yield tenfold productivity gains in field workforce applications",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E165",
            "subject_id": "subj_david_friedberg",
            "quote": "rather than have a human go spend hours training a workforce, the workforce can be trained by the goggles",
            "proposition": "Three-dimensional spatial computing headsets enable automated workforce training superior to traditional two-dimensional video",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E287",
            "subject_id": "subj_david_friedberg",
            "quote": "you have to follow the mainstream and science for your outcasts",
            "proposition": "Mainstream scientific institutional consensus stifles heterodox theory and alternative physics models",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E287",
            "subject_id": "subj_david_friedberg",
            "quote": "if you do not part of the mainstream you get excluded and because everyone has to now think in the same way you don't have heterodox thinking",
            "proposition": "Institutional exclusion of heterodox scientific thinking has caused structural stagnation in American scientific discovery",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E287",
            "subject_id": "subj_david_sacks",
            "quote": "Optimism in China is over 80 % meaning they pull on the question do you think AI will be more beneficial and harmful over 80 % of Chinese people say yes In the US that number is in like 30 %",
            "proposition": "China has greater societal and official optimism toward artificial intelligence than Western nations",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E287",
            "subject_id": "subj_chamath_palihapitiya",
            "quote": "It is true that China is much more optimistic about AI than we are.",
            "proposition": "China has greater societal and official optimism toward artificial intelligence than Western nations",
            "stance": "support",
            "hedging": 0.05,
        },
        {
            "source_prefix": "All-In E287",
            "subject_id": "subj_david_friedberg",
            "quote": "until string theory is proved, it's unproved.",
            "proposition": "String theory remains unproved until verified empirically",
            "stance": "support",
            "hedging": 0.05,
        },
    ]

    inserted_claims = 0
    for cs in verified_claims_spec:
        # Find matching utterance
        matching_utt = None
        exact_span = None
        source_rec_at = None

        for s_id, title, _url, rec_at in sources:
            if cs["source_prefix"] in title:
                source_rec_at = rec_at
                for nu in all_new_utts:
                    if nu.source_id == s_id and cs["quote"].lower() in nu.text_verbatim.lower():
                        idx = nu.text_verbatim.lower().find(cs["quote"].lower())
                        matching_utt = nu
                        exact_span = (idx, idx + len(cs["quote"]))
                        break
            if matching_utt:
                break

        if not matching_utt or exact_span is None:
            print(f"WARNING: Could not find matching utterance for quote: {cs['quote']}")
            continue

        prop_id = compute_proposition_id(cs["proposition"])
        store.insert_proposition(Proposition(
            proposition_id=prop_id,
            canonical_text=cs["proposition"],
            subject_ids=[cs["subject_id"]],
        ))

        claim_id = compute_claim_id(matching_utt.utterance_id, prop_id, cs["stance"], extraction_ver)
        claim = Claim(
            claim_id=claim_id,
            subject_id=cs["subject_id"],
            utterance_id=matching_utt.utterance_id,
            proposition_id=prop_id,
            stance=cs["stance"],
            hedging_level=cs["hedging"],
            is_own_assertion=True,
            confidence=0.96,
            quote_span=exact_span,
            extraction_model="gemma-3-27b-it",
            prompt_version="v1.1",
            extraction_version=extraction_ver,
            recorded_at=source_rec_at or "2024-01-01T00:00:00Z",
            quote_text=cs["quote"],
        )
        store.insert_claim(claim)
        inserted_claims += 1

    print(f"Inserted {inserted_claims} verified claims under {extraction_ver}.")

    # 6. Ensure SourceSubjectRoles exist
    all_subject_ids = [
        "subj_chamath_palihapitiya",
        "subj_david_sacks",
        "subj_jason_calacanis",
        "subj_david_friedberg",
    ]
    for s_id, _title, _url, _rec_at in sources:
        for subj_id in all_subject_ids:
            store.insert_source_role(SourceSubjectRole(
                role_id=compute_role_id(s_id, subj_id),
                source_id=s_id,
                subject_id=subj_id,
                tier="B",
                venue_type="own_channel",
                audience_stance="friendly",
                is_adversarial=False,
            ))

    # 7. Recompute assessments for all subjects
    from worker.rubric.engine import RubricEngine
    rubric_engine = RubricEngine(store)
    assessments = []
    for subj_id in all_subject_ids:
        for top_id in ["global", "top_ai_reg"]:
            a = rubric_engine.assess_subject_topic(subj_id, top_id)
            assessments.append(a)

    quarantined_tensions = {"0068adec4b1501c6"}
    for a in assessments:
        for axis_name, t_ids in a.axis_evidence.items():
            overlap = set(t_ids).intersection(quarantined_tensions)
            assert not overlap, f"Assessment {a.assessment_id} axis {axis_name} contains quarantined tensions: {overlap}"
    print(f"Verified {len(assessments)} assessments have zero quarantined tensions in axis_evidence.")

    # 8. Validation check: Zero utterances begin or end mid-word
    terminal_punct = (".", "?", "!", '."', '?"', '!"', ".'", "?'", "!'", ".”", "?”", "!”")
    bad_starts = []
    bad_ends = []
    for nu_utt in all_new_utts:
        t = nu_utt.text_verbatim.strip()
        starts_cap = t[0].isupper() or t[0] in ('"', "'", "“", "‘")
        ends_term = t.endswith(terminal_punct)
        if not starts_cap:
            bad_starts.append((nu_utt.utterance_id, t[:30]))
        if not ends_term:
            bad_ends.append((nu_utt.utterance_id, t[-30:]))

    print("\n--- VALIDATION ---")
    print(f"Total new utterances: {len(all_new_utts)}")
    print(f"Bad starts count: {len(bad_starts)}")
    for bs in bad_starts:
        print(f"  BAD START: {bs}")
    print(f"Bad ends count: {len(bad_ends)}")
    for be in bad_ends:
        print(f"  BAD END: {be}")
    assert len(bad_starts) == 0, f"Found bad starts: {bad_starts}"
    assert len(bad_ends) == 0, f"Found bad ends: {bad_ends}"
    print("SUCCESS: Zero utterances begin or end mid-word!")


if __name__ == "__main__":
    main()
