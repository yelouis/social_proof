"""Step 2 & Step 4 Verification: 20-utterance sample gate for Item X2 (Issue 034 = B).

Extract from 20 candidate utterances under prompt v1.8.
For each claim, outputs both the position frame and <X>.
Measures Validator 2b (validate_position_bearing) fire rate.
Asserts >= 16 of 20 frames read as sentences a person would write.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import Embedder
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import (
    validate_extracted_claim,
    validate_position_bearing,
)
from worker.storage import Storage


def main() -> None:
    seed = 42
    random.seed(seed)

    store = Storage("social_proof.duckdb", read_only=True)
    utts = store.con.execute("""
        SELECT u.utterance_id, u.source_id, u.subject_id, s.display_name, u.text_verbatim
        FROM utterances u
        JOIN subjects s ON u.subject_id = s.subject_id
        WHERE u.utterance_id IN (SELECT utterance_id FROM claims)
        ORDER BY u.utterance_id
    """).fetchall()

    sample_utts = random.sample(utts, 20)

    print("Initializing LocalGemmaRuntime with live backend (prompt v1.8)...")
    runtime = LocalGemmaRuntime(load_live_backend=True)
    embedder = Embedder()
    print(f"Runtime loaded: {runtime.extraction_version}\n")

    results = []
    val_2b_fires = 0
    total_raw_claims = 0

    print("=" * 80)
    print("STEP 2 SAMPLE: 20 UTTERANCES EXTRACTED UNDER PROMPT v1.8")
    print(f"Seed: {seed}")
    print("=" * 80)

    for i, (uid, _sid, _subj_id, speaker, text) in enumerate(sample_utts, 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue

        context = f"Speaker: {speaker}"
        stats = runtime.generate_constrained(text, context)
        claims = stats.parsed_result.claims

        print(f"\n[{i:2d}/20] ({speaker}) Utterance ID: {uid}")
        print(f'     Verbatim: "{text}"')

        if not claims:
            print("     Result: [NO CLAIMS EMITTED]")
            results.append(
                {
                    "index": i,
                    "uid": uid,
                    "speaker": speaker,
                    "text": text,
                    "claims": [],
                    "has_claims": False,
                }
            )
            continue

        item_claims = []
        for c_idx, ec in enumerate(claims, 1):
            total_raw_claims += 1

            # Normalize frame and prop
            if ec.position_frame:
                frame = ec.position_frame.strip().rstrip(".")
                frame_lower = frame.lower()
                if (
                    "the speaker is for " in frame_lower
                    and "the speaker is against " in frame_lower
                ):
                    ec.stance = "mixed"
                    if not ec.proposition_text:
                        idx = frame_lower.find("the speaker is for ")
                        rest = frame[idx + len("the speaker is for ") :]
                        ec.proposition_text = rest.split(" and ")[0].strip().rstrip(".")
                    ec.position_frame = f"the speaker is FOR {ec.proposition_text} in one respect and the speaker is AGAINST {ec.proposition_text} in another"
                elif frame_lower.startswith("the speaker is for "):
                    ec.stance = "support"
                    ec.proposition_text = frame[len("the speaker is for ") :].strip().rstrip(".")
                    ec.position_frame = f"the speaker is FOR {ec.proposition_text}"
                elif frame_lower.startswith("the speaker is against "):
                    ec.stance = "oppose"
                    ec.proposition_text = (
                        frame[len("the speaker is against ") :].strip().rstrip(".")
                    )
                    ec.position_frame = f"the speaker is AGAINST {ec.proposition_text}"
            elif ec.proposition_text:
                prop = ec.proposition_text.strip().rstrip(".")
                ec.proposition_text = prop
                if ec.stance == "support":
                    ec.position_frame = f"the speaker is FOR {prop}"
                elif ec.stance == "oppose":
                    ec.position_frame = f"the speaker is AGAINST {prop}"
                else:
                    ec.position_frame = f"the speaker is FOR {prop} in one respect and the speaker is AGAINST {prop} in another"

            # Check Validator 2b (validate_position_bearing)
            v2b_res = validate_position_bearing(ec)
            if not v2b_res.is_valid:
                val_2b_fires += 1
                v2b_status = f"FIRED ({v2b_res.rejection_reason})"
            else:
                v2b_status = "CLEARED"

            outcome = validate_extracted_claim(
                claim=ec,
                utterance=utt,
                confidence_floor=0.70,
                embedder=embedder,
            )

            print(f"     Claim #{c_idx}:")
            print(f'       Position Frame : "{ec.position_frame}"')
            print(f'       <X> (Prop Text): "{ec.proposition_text}"')
            print(f"       Stance         : {ec.stance}")
            print(f'       Quote Text     : "{ec.quote_text}"')
            print(f"       Validator 2b   : {v2b_status}")
            print(
                f"       Pipeline Valid : {outcome.is_valid} (status: {outcome.status}, reason: {outcome.rejection_reason})"
            )

            item_claims.append(
                {
                    "frame": ec.position_frame,
                    "x": ec.proposition_text,
                    "stance": ec.stance,
                    "quote": ec.quote_text,
                    "v2b": v2b_status,
                    "valid": outcome.is_valid,
                }
            )

        results.append(
            {
                "index": i,
                "uid": uid,
                "speaker": speaker,
                "text": text,
                "claims": item_claims,
                "has_claims": True,
            }
        )

    store.close()

    print("\n" + "=" * 80)
    print("STEP 2 & STEP 4 SUMMARY")
    print("=" * 80)
    print("Total Utterances Sampled: 20")
    print(f"Utterances with Claims  : {sum(1 for r in results if r['has_claims'])} / 20")
    print(f"Total Raw Claims Emitted: {total_raw_claims}")
    v2b_rate = (val_2b_fires / total_raw_claims * 100) if total_raw_claims > 0 else 0.0
    print(f"Validator 2b Fire Rate  : {val_2b_fires} / {total_raw_claims} ({v2b_rate:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
