"""Sweep T_dedup thresholds over live claims to analyze merges, multi-episode propositions,
and cross-episode opposing-stance candidate pairs.
"""

from typing import Any

import duckdb
import numpy as np

from worker.extract.dedup import get_embedder


def simulate_dedup(
    con: duckdb.DuckDBPyConnection,
    t_dedup: float,
    t_entail_high: float = 0.70,
    embedder: Any | None = None,
) -> dict[str, Any]:
    # 1. Fetch active proposition embeddings
    emb_rows = con.execute("""
        SELECT pe.proposition_id, pe.embedding
        FROM proposition_embeddings pe
        JOIN propositions p ON pe.proposition_id = p.proposition_id
        WHERE p.status = 'active'
    """).fetchall()
    embs: dict[str, np.ndarray] = {
        r[0]: np.array(r[1], dtype=np.float32) for r in emb_rows
    }

    # 2. Fetch claims
    claim_rows = con.execute("""
        SELECT c.claim_id, c.utterance_id, c.proposition_id, c.subject_id, c.stance,
               c.is_own_assertion, c.recorded_at, c.quote_text, u.source_id
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
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
            if float(sims[best_idx]) >= t_dedup:
                cand_rep = active_pids[best_idx]
                cand_vec = active_vecs[best_idx]
                merge_allowed = True
                if embedder is not None:
                    pid_claims = claims_by_pid.get(orig_pid, [])
                    for c in pid_claims:
                        q_text = (c[7] or "").strip()
                        if q_text:
                            q_vec = np.array(embedder.embed_document(q_text), dtype=np.float32)
                            entail_sim = float(np.dot(q_vec, cand_vec))
                            if entail_sim < t_entail_high:
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

    # Check resulting mapped claims
    mapped_claims = []
    for r in claim_rows:
        cid, uid, pid, sid, stance, is_own, rec_at, quote, src_id = r
        mapped_pid = mapping.get(pid, pid)
        mapped_claims.append({
            "claim_id": cid,
            "utterance_id": uid,
            "orig_pid": pid,
            "mapped_pid": mapped_pid,
            "subject_id": sid,
            "stance": stance,
            "is_own_assertion": is_own,
            "recorded_at": rec_at,
            "quote_text": quote,
            "source_id": src_id,
        })

    # Group claims by mapped_pid
    claims_by_mapped_pid: dict[str, list[dict[str, Any]]] = {}
    for mc in mapped_claims:
        claims_by_mapped_pid.setdefault(mc["mapped_pid"], []).append(mc)

    total_props = len(claims_by_mapped_pid)
    singleton_props = sum(1 for p, cl in claims_by_mapped_pid.items() if len(cl) == 1)
    singleton_rate = singleton_props / total_props if total_props > 0 else 0.0

    # Multi-episode propositions
    multi_episode_props = 0
    for _p, cl in claims_by_mapped_pid.items():
        sources = set(c["source_id"] for c in cl)
        if len(sources) > 1:
            multi_episode_props += 1

    multi_episode_rate = multi_episode_props / total_props if total_props > 0 else 0.0

    # Find candidate reversal pairs:
    # Same subject, same mapped_pid, different stance (support vs oppose),
    # both is_own_assertion=True, different source_id (cross-episode)
    candidates = []
    for pid, cl in claims_by_mapped_pid.items():
        own_cl = [c for c in cl if c["is_own_assertion"] and c["stance"] in ("support", "oppose")]
        if len(own_cl) < 2:
            continue
        # Group by subject
        by_subj: dict[str, list[dict[str, Any]]] = {}
        for c in own_cl:
            by_subj.setdefault(c["subject_id"], []).append(c)
        for subj, subj_claims in by_subj.items():
            supports = [c for c in subj_claims if c["stance"] == "support"]
            opposes = [c for c in subj_claims if c["stance"] == "oppose"]
            if supports and opposes:
                for s in supports:
                    for o in opposes:
                        if s["source_id"] != o["source_id"]:
                            candidates.append((pid, subj, s, o))

    return {
        "t_dedup": t_dedup,
        "total_propositions": total_props,
        "singleton_propositions": singleton_props,
        "singleton_rate": singleton_rate,
        "multi_episode_propositions": multi_episode_props,
        "multi_episode_rate": multi_episode_rate,
        "candidate_pairs_count": len(candidates),
        "candidates": candidates,
        "mapping_merges": len([k for k, v in mapping.items() if k != v]),
    }


def main() -> None:
    con = duckdb.connect("social_proof.duckdb", read_only=True)
    embedder = get_embedder()

    thresholds = [0.999, 0.90, 0.88, 0.86, 0.84, 0.82, 0.80, 0.78, 0.75, 0.30]
    print(f"{'T_dedup':<8} | {'Props':<6} | {'Singletons':<10} | {'Singl%':<7} | {'Multi-Ep':<8} | {'Multi%':<7} | {'Merges':<6} | {'CandPairs':<10}")
    print("-" * 85)

    results = []
    for t in thresholds:
        res = simulate_dedup(con, t_dedup=t, embedder=embedder)
        results.append(res)
        print(
            f"{res['t_dedup']:<8.3f} | {res['total_propositions']:<6} | "
            f"{res['singleton_propositions']:<10} | {res['singleton_rate']*100:<6.1f}% | "
            f"{res['multi_episode_propositions']:<8} | {res['multi_episode_rate']*100:<6.1f}% | "
            f"{res['mapping_merges']:<6} | {res['candidate_pairs_count']:<10}"
        )

    # Let's inspect candidates if any found
    for res in results:
        t = res["t_dedup"]
        cands = res["candidates"]
        if cands and t >= 0.75:
            for pid, subj, s, o in cands[:5]:
                p_row = con.execute("SELECT canonical_text FROM propositions WHERE proposition_id = ?", [pid]).fetchone()
                p_text = str(p_row[0]) if p_row is not None else pid
                print(f"  Subject: {subj}, Prop: '{p_text}'")
                print(f"    Support ({s['source_id'][:10]}): '{s['quote_text'][:80]}'")
                print(f"    Oppose  ({o['source_id'][:10]}): '{o['quote_text'][:80]}'")

    con.close()


if __name__ == "__main__":
    main()
