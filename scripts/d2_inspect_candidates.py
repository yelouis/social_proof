"""Inspect candidate reversal pairs under candidate thresholds (0.86, 0.84, 0.82).

Evaluates whether each candidate pair satisfies TensionDetector's 6 preconditions
and displays the exact proposition text, source episodes, and verbatim quotes.
"""

from typing import Any

import duckdb
import numpy as np

from worker.extract.dedup import get_embedder


def inspect_threshold(t: float) -> None:
    con = duckdb.connect("social_proof.duckdb", read_only=True)
    embedder = get_embedder()

    # 1. Fetch active proposition embeddings
    emb_rows = con.execute("""
        SELECT pe.proposition_id, pe.embedding, p.canonical_text
        FROM proposition_embeddings pe
        JOIN propositions p ON pe.proposition_id = p.proposition_id
        WHERE p.status = 'active'
    """).fetchall()
    embs: dict[str, np.ndarray] = {r[0]: np.array(r[1], dtype=np.float32) for r in emb_rows}
    texts: dict[str, str] = {r[0]: r[2] for r in emb_rows}

    # 2. Fetch claims
    claim_rows = con.execute("""
        SELECT c.claim_id, c.utterance_id, c.proposition_id, c.subject_id, c.stance,
               c.is_own_assertion, c.recorded_at, c.quote_text, u.source_id,
               s.title, u.attribution_confidence, u.negation_uncertain
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        JOIN sources s ON u.source_id = s.source_id
        ORDER BY TRY_CAST(c.recorded_at AS TIMESTAMPTZ), c.utterance_id, c.claim_id
    """).fetchall()

    claims_by_pid: dict[str, list[Any]] = {}
    for r in claim_rows:
        claims_by_pid.setdefault(r[2], []).append(r)

    mapping: dict[str, str] = {}
    active_pids: list[str] = []
    active_vecs: list[np.ndarray] = []

    for row in claim_rows:
        orig_pid = row[2]
        if orig_pid in mapping:
            continue
        if orig_pid not in embs:
            mapping[orig_pid] = orig_pid
            active_pids.append(orig_pid)
            continue
        vec = embs[orig_pid]
        if len(active_vecs) == 0:
            active_pids.append(orig_pid)
            active_vecs.append(vec)
            mapping[orig_pid] = orig_pid
        else:
            mat = np.array(active_vecs)
            sims = np.dot(mat, vec)
            best_idx = int(np.argmax(sims))
            if float(sims[best_idx]) >= t:
                cand_rep = active_pids[best_idx]
                cand_vec = active_vecs[best_idx]
                merge_allowed = True
                pid_claims = claims_by_pid.get(orig_pid, [])
                for c in pid_claims:
                    q_text = (c[7] or "").strip()
                    if q_text:
                        q_vec = np.array(embedder.embed_document(q_text), dtype=np.float32)
                        entail_sim = float(np.dot(q_vec, cand_vec))
                        if entail_sim < 0.70:
                            merge_allowed = False
                            break
                if merge_allowed:
                    mapping[orig_pid] = cand_rep
                else:
                    active_pids.append(orig_pid)
                    active_vecs.append(vec)
                    mapping[orig_pid] = orig_pid
            else:
                active_pids.append(orig_pid)
                active_vecs.append(vec)
                mapping[orig_pid] = orig_pid

    # Group claims by mapped_pid
    claims_by_mapped: dict[str, list[Any]] = {}
    for r in claim_rows:
        mpid = mapping.get(r[2], r[2])
        claims_by_mapped.setdefault(mpid, []).append(r)

    print("\n==================================================")
    print(f"CANDIDATES AT T_dedup = {t:.3f}")
    print(
        f"Total propositions after merge: {len(claims_by_mapped)} (merges: {len([k for k, v in mapping.items() if k != v])})"
    )
    print("==================================================")

    cand_count = 0
    for mpid, cl in claims_by_mapped.items():
        own_cl = [c for c in cl if c[5] and c[4] in ("support", "oppose")]
        by_subj: dict[str, list[Any]] = {}
        for c in own_cl:
            by_subj.setdefault(c[3], []).append(c)

        for subj, scl in by_subj.items():
            supports = [c for c in scl if c[4] == "support"]
            opposes = [c for c in scl if c[4] == "oppose"]
            if not (supports and opposes):
                continue

            for s in supports:
                for o in opposes:
                    if s[8] == o[8]:
                        continue  # same source
                    cand_count += 1
                    rep_text = texts.get(mpid, mpid)
                    s_orig_text = texts.get(s[2], s[2])
                    o_orig_text = texts.get(o[2], o[2])
                    sim_s_rep = float(np.dot(embs[s[2]], embs[mpid]))
                    sim_o_rep = float(np.dot(embs[o[2]], embs[mpid]))

                    print(f"\n--- Candidate #{cand_count} [{subj}] ---")
                    print(f"Cluster Representative: '{rep_text}'")
                    print(f"Support Claim: id={s[0][:10]}, date={s[6]}, episode='{s[9][:40]}'")
                    print(f"  Orig Prop: '{s_orig_text}' (sim to rep: {sim_s_rep:.4f})")
                    print(f'  Quote: "{s[7]}"')
                    print(f"Oppose Claim:  id={o[0][:10]}, date={o[6]}, episode='{o[9][:40]}'")
                    print(f"  Orig Prop: '{o_orig_text}' (sim to rep: {sim_o_rep:.4f})")
                    print(f'  Quote: "{o[7]}"')

    print(f"\nTotal candidate pairs at {t:.3f}: {cand_count}")
    con.close()


def main() -> None:
    for t in [0.86, 0.84, 0.82]:
        inspect_threshold(t)


if __name__ == "__main__":
    main()
