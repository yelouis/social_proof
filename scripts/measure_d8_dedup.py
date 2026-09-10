"""Measurement script for Item D8: Re-measuring T_dedup against prompt v1.8 distribution.

Step 1:
- Compute 1-NN cosine similarity distribution across all 1,465 propositions.
- Report deciles and distribution shape.

Step 2:
- Use stored position_frame <X> as objective ground truth.
- Evaluate merge endorsement vs contradiction across thresholds [0.80 ... 0.98].
- Specifically check the 4 named pairs from §12:
  1. Sacks growth: '60 to 80 percent growth year over year' vs '10x year over year growth for ever'
  2. FDA: 'the fda involvement in drug approval process' vs 'the approval process for drugs that influence the body'
  3. China open source: 'china push on open source' vs 'the open source model being published by china'
  4. Friedberg interest rate: '30 years at 5 interest rate' vs 'a 30 year at 5 2 interest rate'
"""

from collections import defaultdict
from typing import Any

import duckdb
import numpy as np

from worker.extract.dedup import get_embedder
from worker.storage import compute_proposition_id, normalize_canonical_text
from worker.tension.detect import extract_matter_from_frame


def compute_step1_distribution(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    print("============================================================")
    print("STEP 1: 1-NN SIMILARITY DISTRIBUTION ACROSS PROPOSITIONS")
    print("============================================================")
    rows = con.execute("""
        SELECT p.proposition_id, p.canonical_text, pe.embedding
        FROM propositions p
        JOIN proposition_embeddings pe ON p.proposition_id = pe.proposition_id
        WHERE p.status = 'active'
        ORDER BY p.proposition_id
    """).fetchall()

    n = len(rows)
    print(f"Total active propositions with embeddings: {n}")
    if n == 0:
        raise ValueError("No active proposition embeddings found!")

    pids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    emb_matrix = np.array([r[2] for r in rows], dtype=np.float32)

    # Normalize vectors just to be certain
    norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    emb_matrix = emb_matrix / norms

    # Compute cosine similarity matrix
    # emb_matrix is (N, 768) -> dot product is (N, N)
    sim_matrix = np.dot(emb_matrix, emb_matrix.T)

    # Set self-similarity diagonal to -1 so it's not chosen as 1-NN
    np.fill_diagonal(sim_matrix, -1.0)

    # 1-NN similarity for each proposition
    one_nn_sims = np.max(sim_matrix, axis=1)

    # Compute deciles
    percentiles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    decile_values = np.percentile(one_nn_sims, percentiles)

    print("\n1-NN Similarity Distribution Deciles:")
    for p, v in zip(percentiles, decile_values, strict=True):
        label = "Min (0%)" if p == 0 else ("Max (100%)" if p == 100 else f"D{p//10} ({p}%)")
        print(f"  {label:<12}: {v:.4f}")

    mean_val = float(np.mean(one_nn_sims))
    std_val = float(np.std(one_nn_sims))
    median_val = float(np.median(one_nn_sims))
    print(f"\nSummary: Mean = {mean_val:.4f}, Std = {std_val:.4f}, Median = {median_val:.4f}")

    # Histogram buckets
    bins = np.linspace(0.50, 1.0, 11)
    hist, bin_edges = np.histogram(one_nn_sims, bins=bins)
    print("\n1-NN Histogram:")
    for i in range(len(hist)):
        bar = "#" * int(hist[i] / n * 80)
        print(f"  [{bin_edges[i]:.2f}, {bin_edges[i+1]:.2f}): {hist[i]:4d} ({hist[i]/n*100:4.1f}%) {bar}")

    return {
        "n": n,
        "pids": pids,
        "texts": texts,
        "emb_matrix": emb_matrix,
        "one_nn_sims": one_nn_sims,
        "deciles": dict(zip(percentiles, decile_values, strict=True)),
        "mean": mean_val,
        "std": std_val,
    }


def compute_step2_frame_evaluation(con: duckdb.DuckDBPyConnection) -> None:
    print("\n============================================================")
    print("STEP 2: EVALUATING MERGES AGAINST STORED FRAMES GROUND TRUTH")
    print("============================================================")

    # 1. Fetch claims with position_frame
    claims_rows = con.execute("""
        SELECT claim_id, utterance_id, proposition_id, subject_id, stance,
               is_own_assertion, recorded_at, quote_text, position_frame
        FROM claims
        ORDER BY TRY_CAST(recorded_at AS TIMESTAMPTZ), utterance_id, claim_id
    """).fetchall()

    print(f"Total claims: {len(claims_rows)}")

    # Extract raw matter and unmerged proposition_id for each claim
    raw_props: dict[str, str] = {}  # raw_pid -> normalized matter
    claims_by_raw_pid: dict[str, list[Any]] = defaultdict(list)

    for r in claims_rows:
        frame = r[8]
        matter = extract_matter_from_frame(frame)
        norm_matter = normalize_canonical_text(matter)
        raw_pid = compute_proposition_id(norm_matter)
        raw_props[raw_pid] = norm_matter
        claims_by_raw_pid[raw_pid].append(r)

    print(f"Total raw unmerged propositions from frames: {len(raw_props)}")

    # Get embedder
    embedder = get_embedder()
    print("Embedding raw propositions...")
    # Cache raw embeddings
    raw_pids = list(raw_props.keys())
    raw_texts = [raw_props[pid] for pid in raw_pids]

    # Check if we can reuse existing embeddings from proposition_embeddings table
    existing_embs = dict(con.execute("SELECT proposition_id, embedding FROM proposition_embeddings").fetchall())

    raw_embs_list: list[np.ndarray] = []
    missing_texts: list[str] = []
    missing_indices: list[int] = []

    for i, pid in enumerate(raw_pids):
        if pid in existing_embs:
            raw_embs_list.append(np.array(existing_embs[pid], dtype=np.float32))
        else:
            raw_embs_list.append(np.zeros(768, dtype=np.float32))
            missing_texts.append(raw_texts[i])
            missing_indices.append(i)

    if missing_texts:
        print(f"Computing embeddings for {len(missing_texts)} propositions not in table...")
        for idx, text in zip(missing_indices, missing_texts, strict=True):
            vec = np.array(embedder.embed_document(text), dtype=np.float32)
            raw_embs_list[idx] = vec

    raw_emb_matrix = np.array(raw_embs_list, dtype=np.float32)
    norms = np.linalg.norm(raw_emb_matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    raw_emb_matrix = raw_emb_matrix / norms
    pid_to_idx = {pid: i for i, pid in enumerate(raw_pids)}

    # Four known pairs to check:
    named_pairs = [
        (
            "Sacks growth",
            "60 to 80 percent growth year over year",
            "10x year over year growth for ever",
        ),
        (
            "FDA drug approval",
            "the fda's involvement in drug approval process",
            "the approval process for drugs that influence the body",
        ),
        (
            "China open source",
            "china's push on open source",
            "the open source model being published by china",
        ),
        (
            "Friedberg interest rate",
            "30 years at 5% interest rate",
            "a 30-year at 5.2 interest rate",
        ),
    ]

    print("\nPairwise similarity of 4 named defect pairs:")
    for name, text_a, text_b in named_pairs:
        v_a = embedder.embed_document(normalize_canonical_text(text_a))
        v_b = embedder.embed_document(normalize_canonical_text(text_b))
        cos_sim = float(np.dot(v_a, v_b) / (np.linalg.norm(v_a) * np.linalg.norm(v_b)))
        print(f"  {name:<25}: cos_sim = {cos_sim:.4f}")
        print(f"    A: '{text_a}'")
        print(f"    B: '{text_b}'")

    # Sweep candidate thresholds
    thresholds = [0.80, 0.82, 0.84, 0.85, 0.86, 0.87, 0.88, 0.89, 0.90, 0.92, 0.95, 0.98, 0.999]
    print("\n" + "=" * 105)
    print(f"{'T_dedup':<8} | {'Props':<6} | {'Merges':<6} | {'Endorsed':<8} | {'Contradicted':<12} | {'SO_Props':<8} | {'SO_Clean':<8} | {'Named Bad Merges':<20}")
    print("=" * 105)

    for t in thresholds:
        # Simulate greedy chronological clustering from raw unmerged propositions
        mapping: dict[str, str] = {}
        active_pids: list[str] = []
        active_vecs: list[np.ndarray] = []

        for row in claims_rows:
            frame = row[8]
            norm_matter = normalize_canonical_text(extract_matter_from_frame(frame))
            raw_pid = compute_proposition_id(norm_matter)

            if raw_pid in mapping:
                continue

            vec = raw_emb_matrix[pid_to_idx[raw_pid]]

            if len(active_vecs) == 0:
                active_pids.append(raw_pid)
                active_vecs.append(vec)
                mapping[raw_pid] = raw_pid
            else:
                mat = np.array(active_vecs)
                sims = np.dot(mat, vec)
                best_idx = int(np.argmax(sims))
                best_sim = float(sims[best_idx])

                if best_sim >= t:
                    cand_rep = active_pids[best_idx]
                    cand_vec = active_vecs[best_idx]
                    # Entailment check against candidate proposition representative
                    merge_allowed = True
                    for c in claims_by_raw_pid[raw_pid]:
                        q_text = (c[7] or "").strip()
                        if q_text:
                            q_vec = np.array(embedder.embed_document(q_text), dtype=np.float32)
                            entail_sim = float(np.dot(q_vec, cand_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(cand_vec)))
                            if entail_sim < 0.70:
                                merge_allowed = False
                                break
                    if merge_allowed:
                        mapping[raw_pid] = cand_rep
                    else:
                        active_pids.append(raw_pid)
                        active_vecs.append(vec)
                        mapping[raw_pid] = raw_pid
                else:
                    active_pids.append(raw_pid)
                    active_vecs.append(vec)
                    mapping[raw_pid] = raw_pid

        # Evaluate resulting clusters against frames ground truth
        # Group raw propositions by cluster rep
        clusters: dict[str, list[str]] = defaultdict(list)
        for orig_pid, rep_pid in mapping.items():
            clusters[rep_pid].append(orig_pid)

        total_props = len(clusters)
        merges = sum(len(members) - 1 for members in clusters.values() if len(members) > 1)

        # For multi-member clusters, check if frames agree
        endorsed_clusters = 0
        contradicted_clusters = 0

        for _rep_pid, members in clusters.items():
            if len(members) <= 1:
                continue
            # Compare all pairs of matters in cluster
            matters = [raw_props[m] for m in members]
            all_identical = all(m == matters[0] for m in matters)
            if all_identical:
                endorsed_clusters += 1
            else:
                contradicted_clusters += 1

        # Check Support/Oppose propositions:
        # Group claims by rep_pid
        claims_by_rep: dict[str, list[Any]] = defaultdict(list)
        for c in claims_rows:
            norm_m = normalize_canonical_text(extract_matter_from_frame(c[8]))
            raw_p = compute_proposition_id(norm_m)
            rep_p = mapping[raw_p]
            claims_by_rep[rep_p].append(c)

        so_props = 0
        so_clean = 0
        for _rep_p, c_list in claims_by_rep.items():
            stances = set(c[4] for c in c_list if c[5])  # own assertions
            if "support" in stances and "oppose" in stances:
                so_props += 1
                # Check if all frames in this SO proposition have identical <X>
                so_matters = set(normalize_canonical_text(extract_matter_from_frame(c[8])) for c in c_list if c[5] and c[4] in ("support", "oppose"))
                if len(so_matters) == 1:
                    so_clean += 1

        # Check named bad merges
        bad_merged = []
        for name, text_a, text_b in named_pairs:
            pid_a = compute_proposition_id(normalize_canonical_text(text_a))
            pid_b = compute_proposition_id(normalize_canonical_text(text_b))
            if pid_a in mapping and pid_b in mapping:
                if mapping[pid_a] == mapping[pid_b]:
                    bad_merged.append(name)

        bad_str = ", ".join(bad_merged) if bad_merged else "none (all clean!)"
        print(f"{t:<8.3f} | {total_props:<6} | {merges:<6} | {endorsed_clusters:<8} | {contradicted_clusters:<12} | {so_props:<8} | {so_clean:<8} | {bad_str}")


def main() -> None:
    con = duckdb.connect("social_proof.duckdb", read_only=True)
    try:
        compute_step1_distribution(con)
        compute_step2_frame_evaluation(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
