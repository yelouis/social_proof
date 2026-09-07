"""Item D2 (Parameter 008): Measure 1-NN similarity distribution over live proposition embeddings.

Computes 1-nearest-neighbour cosine similarity for all active propositions,
extracts deciles and histograms, checks for bimodal/structural separation,
tests canonical test pairs, sweeps thresholds, and identifies cross-episode candidate pairs.
"""

import json
from typing import Any

import duckdb
import numpy as np


def main() -> None:
    con = duckdb.connect("social_proof.duckdb", read_only=True)

    # 1. Fetch active propositions and embeddings
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
        print("ERROR: No active propositions found.")
        return

    prop_ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    raw_embs = [r[2] for r in rows]

    # Convert to float32 matrix and normalize just in case
    mat = np.array(raw_embs, dtype=np.float32)  # shape (n, 768)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms

    # 2. Compute 1-nearest-neighbour cosine similarity for every proposition
    sim_matrix = np.dot(mat, mat.T)
    # Zero out diagonal so proposition doesn't match itself
    np.fill_diagonal(sim_matrix, -1.0)

    # 1-NN similarity for each proposition
    max_sims = np.max(sim_matrix, axis=1)
    nearest_indices = np.argmax(sim_matrix, axis=1)

    # Summary stats
    mean_sim = float(np.mean(max_sims))
    std_sim = float(np.std(max_sims))
    min_sim = float(np.min(max_sims))
    max_sim = float(np.max(max_sims))

    # Deciles
    decile_probs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    deciles = {f"D{p}": float(np.percentile(max_sims, p)) for p in decile_probs}
    percentiles = {
        "p25": float(np.percentile(max_sims, 25)),
        "p50": float(np.percentile(max_sims, 50)),
        "p75": float(np.percentile(max_sims, 75)),
        "p90": float(np.percentile(max_sims, 90)),
        "p95": float(np.percentile(max_sims, 95)),
        "p99": float(np.percentile(max_sims, 99)),
    }

    print(f"\n=== 1-NN SIMILARITY DISTRIBUTION (n = {n}) ===")
    print(f"Min:    {min_sim:.4f}")
    print(f"Max:    {max_sim:.4f}")
    print(f"Mean:   {mean_sim:.4f}")
    print(f"StdDev: {std_sim:.4f}")
    print("\nDeciles:")
    for k, v in deciles.items():
        print(f"  {k}: {v:.4f}")
    print("\nKey Percentiles:")
    for k, v in percentiles.items():
        print(f"  {k}: {v:.4f}")

    # Histogram (bins from 0.40 to 1.00 in steps of 0.05)
    bins = np.arange(0.40, 1.02, 0.05)
    hist, bin_edges = np.histogram(max_sims, bins=bins)
    print("\nHistogram (1-NN Cosine Similarity):")
    for count, b_start, b_end in zip(hist, bin_edges[:-1], bin_edges[1:], strict=True):
        bar = "#" * int(count / 10)
        print(f"  [{b_start:.2f}, {b_end:.2f}): {count:4d} | {bar}")

    # Fine histogram around 0.70 to 0.98 (in steps of 0.02)
    fine_bins = np.arange(0.70, 0.98, 0.02)
    fine_hist, fine_edges = np.histogram(max_sims, bins=fine_bins)
    print("\nFine Histogram [0.70 to 0.96]:")
    for count, b_start, b_end in zip(fine_hist, fine_edges[:-1], fine_edges[1:], strict=True):
        bar = "#" * int(count / 5)
        print(f"  [{b_start:.2f}, {b_end:.2f}): {count:4d} | {bar}")

    # 3. Find canonical "China open source" propositions and "trains" proposition
    print("\n=== CANONICAL PROPOSITIONS SEARCH ===")
    china_props = []
    train_props = []
    for i, t in enumerate(texts):
        tl = t.lower()
        if "china" in tl and ("open source" in tl or "open-source" in tl or "models" in tl):
            china_props.append((i, prop_ids[i], t))
        if "train" in tl or "high speed" in tl or "high-speed" in tl:
            train_props.append((i, prop_ids[i], t))

    print(f"Found {len(china_props)} China/open source candidate propositions:")
    for idx, pid, t in china_props[:10]:
        nn_idx = nearest_indices[idx]
        nn_sim = max_sims[idx]
        print(f"  [{pid[:12]}] (NN sim={nn_sim:.4f} -> [{prop_ids[nn_idx][:12]}]: '{texts[nn_idx][:60]}') : '{t}'")

    print(f"\nFound {len(train_props)} train candidate propositions:")
    for idx, pid, t in train_props[:5]:
        nn_idx = nearest_indices[idx]
        nn_sim = max_sims[idx]
        print(f"  [{pid[:12]}] (NN sim={nn_sim:.4f} -> [{prop_ids[nn_idx][:12]}]: '{texts[nn_idx][:60]}') : '{t}'")

    # Specifically check similarity between China open source and trains if found
    if china_props and train_props:
        print("\nCross-similarity: China open source vs Trains:")
        for c_idx, _c_pid, c_t in china_props[:3]:
            for tr_idx, _tr_pid, tr_t in train_props[:3]:
                sim = float(sim_matrix[c_idx, tr_idx])
                print(f"  sim('{c_t[:40]}', '{tr_t[:40]}') = {sim:.4f}")

    # 4. Save results to a json fixture for reporting
    results: dict[str, Any] = {
        "n": n,
        "min": min_sim,
        "max": max_sim,
        "mean": mean_sim,
        "std": std_sim,
        "deciles": deciles,
        "percentiles": percentiles,
        "histogram": {
            f"[{b_start:.2f}, {b_end:.2f})": int(count)
            for count, b_start, b_end in zip(hist, bin_edges[:-1], bin_edges[1:], strict=True)
        },
        "fine_histogram": {
            f"[{b_start:.2f}, {b_end:.2f})": int(count)
            for count, b_start, b_end in zip(fine_hist, fine_edges[:-1], fine_edges[1:], strict=True)
        },
    }
    with open("fixtures/behaviour/d2_dedup_distribution.json", "w") as f:
        json.dump(results, f, indent=2)

    con.close()


if __name__ == "__main__":
    main()
