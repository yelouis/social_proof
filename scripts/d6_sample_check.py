"""Step 2 Verify: Sample 20 candidate utterances and apply the position test to every proposition produced.

At least 16 of 20 must pass the position test.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import Embedder
from worker.extract.runtime import LocalGemmaRuntime
from worker.extract.validators import validate_extracted_claim
from worker.storage import Storage


def main() -> None:
    store = Storage("social_proof.duckdb", read_only=True)
    # Get utterances that produced claims in live corpus
    utts_raw = store.con.execute("""
        SELECT u.utterance_id, u.source_id, u.subject_id, s.display_name, u.start_ms, u.text_verbatim
        FROM utterances u
        JOIN subjects s ON u.subject_id = s.subject_id
        WHERE u.utterance_id IN (SELECT utterance_id FROM claims)
        ORDER BY u.utterance_id
    """).fetchall()

    random.seed(123)
    sample_rows = random.sample(utts_raw, 20)

    runtime = LocalGemmaRuntime(load_live_backend=True)
    embedder = Embedder()
    print(f"Loaded {runtime.extraction_version}")

    propositions_tested = []

    for i, (uid, _sid, _subj_id, speaker, _start_ms, text) in enumerate(sample_rows, 1):
        utt = store.get_utterance(uid)
        if not utt:
            continue
        context = f"Speaker: {speaker}"
        stats = runtime.generate_constrained(text, context)
        claims = stats.parsed_result.claims

        print(f'\n[{i:2d}/20] ({speaker}) "{text[:75]}..."')
        valid_props = []
        for ec in claims:
            outcome = validate_extracted_claim(
                claim=ec,
                utterance=utt,
                confidence_floor=0.70,
                embedder=embedder,
            )
            if outcome.is_valid and ec.is_own_assertion:
                valid_props.append(ec.proposition_text)
            else:
                reason = outcome.rejection_reason or (
                    ec.exclusion_reason if not ec.is_own_assertion else "unknown"
                )
                print(f'   [REJECTED by validator: {reason}] "{ec.proposition_text}"')

        for p in valid_props:
            print(f'   -> Valid Proposition: "{p}"')
            propositions_tested.append((uid, speaker, p, text))

    print("\n" + "=" * 70)
    print(f"VALID PROPOSITIONS PRODUCED ACROSS 20 UTTERANCES: {len(propositions_tested)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
