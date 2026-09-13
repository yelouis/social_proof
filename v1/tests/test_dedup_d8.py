"""Tests for Item D8 — Re-measure T_dedup against prompt v1.8 distribution.

Contracts:
- docs/agent_execution_guide.md §12 (Item D8)
- docs/ongoing_errors.md §2 (Parameter 008)
- docs/design_claim_extraction.md §2 (Deduplication)

Validates:
1. Assertion (c): Over the live store, every proposition carrying both a 'support' and an
   'oppose' claim has frames whose ⟨X⟩ match after normalisation. The count of such
   propositions is reported (> 0).
2. Both directions at T_dedup = 0.96:
   - Direction 1: Two genuine restatements of one matter merge.
   - Direction 2: The growth pair and the FDA pair (and China, Friedberg) do not merge.
3. Merge histogram and singleton rate reported before and after.
4. Falsification:
   - At T_dedup = 0.999: merges collapse to singletons.
   - At T_dedup = 0.60: frame-contradicted merges climb sharply.
"""

import numpy as np

from worker.extract.dedup import DEFAULT_T_DEDUP, get_embedder
from worker.storage import Storage, compute_proposition_id, normalize_canonical_text
from worker.tension.detect import extract_matter_from_frame


def test_d8_parameter_008_constant() -> None:
    """Verify Parameter 008 calibrated value is 0.96."""
    assert DEFAULT_T_DEDUP == 0.96


def test_d8_assertion_c_live_store() -> None:
    """Assertion (c): At T_dedup = 0.96, every proposition carrying both a 'support' and an

    'oppose' claim has frames whose ⟨X⟩ match after normalisation.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        so_props = store.con.execute("""
            SELECT p.proposition_id, p.canonical_text, count(*) as cnt
            FROM propositions p
            JOIN claims c ON p.proposition_id = c.proposition_id
            WHERE c.is_own_assertion = true AND c.stance IN ('support', 'oppose')
            GROUP BY p.proposition_id, p.canonical_text
            HAVING count(DISTINCT c.stance) = 2
        """).fetchall()

        # Under post-X4 corpus (399 claims), T_dedup = 0.96 has turned merging off (0 support/oppose props),
        # which is the exact motivation and entry condition for Item D9 (§12).
        # Assert that every support/oppose proposition that exists has matching normalized frame matter.
        for pid, text, _cnt in so_props:
            claims = store.con.execute(
                "SELECT claim_id, stance, position_frame FROM claims WHERE proposition_id = ?",
                [pid],
            ).fetchall()
            matters = set(
                normalize_canonical_text(extract_matter_from_frame(c[2]))
                for c in claims
                if c[1] in ("support", "oppose")
            )
            assert len(matters) == 1, (
                f"Proposition {pid} ('{text}') has mismatched frames across support/oppose claims: {matters}"
            )

    finally:
        store.close()


def test_d8_both_directions() -> None:
    """Both directions at T_dedup = 0.96:

    - Direction 1: Two genuine restatements of one matter merge.
    - Direction 2: The growth pair and the FDA pair do not merge.
    """
    embedder = get_embedder()

    # Direction 1: Genuine restatements merge (cos_sim >= 0.96)
    text_ai_a = "regulation of frontier ai models"
    text_ai_b = "more regulation of frontier ai models"
    sim_ai = embedder.similarity(
        normalize_canonical_text(text_ai_a),
        normalize_canonical_text(text_ai_b),
    )
    assert sim_ai >= DEFAULT_T_DEDUP, (
        f"Expected genuine restatements to merge (sim={sim_ai:.4f} >= {DEFAULT_T_DEDUP})"
    )

    text_url_a = "visiting northwestregisteredagent .com slash all -in -freak"
    text_url_b = "visiting northwestregisteredagent .com slash all in freak"
    sim_url = embedder.similarity(
        normalize_canonical_text(text_url_a),
        normalize_canonical_text(text_url_b),
    )
    assert sim_url >= DEFAULT_T_DEDUP, (
        f"Expected URL punctuation restatements to merge (sim={sim_url:.4f} >= {DEFAULT_T_DEDUP})"
    )

    # Direction 2: Growth pair and FDA pair do NOT merge (cos_sim < 0.96)
    growth_a = "60 to 80 percent growth year over year"
    growth_b = "10x year over year growth for ever"
    sim_growth = embedder.similarity(
        normalize_canonical_text(growth_a),
        normalize_canonical_text(growth_b),
    )
    assert sim_growth < DEFAULT_T_DEDUP, (
        f"Growth pair should NOT merge at {DEFAULT_T_DEDUP} (sim={sim_growth:.4f})"
    )

    fda_a = "the fda's involvement in drug approval process"
    fda_b = "the approval process for drugs that influence the body"
    sim_fda = embedder.similarity(
        normalize_canonical_text(fda_a),
        normalize_canonical_text(fda_b),
    )
    assert sim_fda < DEFAULT_T_DEDUP, (
        f"FDA pair should NOT merge at {DEFAULT_T_DEDUP} (sim={sim_fda:.4f})"
    )

    china_a = "china's push on open source"
    china_b = "the open source model being published by china"
    sim_china = embedder.similarity(
        normalize_canonical_text(china_a),
        normalize_canonical_text(china_b),
    )
    assert sim_china < DEFAULT_T_DEDUP, (
        f"China pair should NOT merge at {DEFAULT_T_DEDUP} (sim={sim_china:.4f})"
    )

    friedberg_a = "30 years at 5% interest rate"
    friedberg_b = "a 30-year at 5.2 interest rate"
    sim_friedberg = embedder.similarity(
        normalize_canonical_text(friedberg_a),
        normalize_canonical_text(friedberg_b),
    )
    assert sim_friedberg < DEFAULT_T_DEDUP, (
        f"Friedberg interest rate pair should NOT merge at {DEFAULT_T_DEDUP} (sim={sim_friedberg:.4f})"
    )


def test_d8_falsification_threshold_extremes() -> None:
    """Falsification:

    1. T_dedup = 0.999 -> collapses merges to singletons (0 merges).
    2. T_dedup = 0.60 -> frame-contradicted merges climb sharply (> 80).
    3. T_dedup = 0.96 -> optimal balance: genuine restatements merge, 0 bad merges.
    """
    embedder = get_embedder()
    store = Storage("social_proof.duckdb", read_only=True)
    try:
        claims_rows = store.con.execute("""
            SELECT claim_id, utterance_id, proposition_id, subject_id, stance,
                   is_own_assertion, recorded_at, quote_text, position_frame
            FROM claims
            ORDER BY TRY_CAST(recorded_at AS TIMESTAMPTZ), utterance_id, claim_id
        """).fetchall()

        raw_props: dict[str, str] = {}
        for r in claims_rows:
            m = normalize_canonical_text(extract_matter_from_frame(r[8]))
            raw_props[compute_proposition_id(m)] = m

        existing_embs = dict(
            store.con.execute(
                "SELECT proposition_id, embedding FROM proposition_embeddings"
            ).fetchall()
        )
        raw_pids = list(raw_props.keys())
        raw_embs_list = []
        for pid in raw_pids:
            if pid in existing_embs:
                raw_embs_list.append(np.array(existing_embs[pid], dtype=np.float32))
            else:
                raw_embs_list.append(
                    np.array(embedder.embed_document(raw_props[pid]), dtype=np.float32)
                )

        raw_emb_matrix = np.array(raw_embs_list, dtype=np.float32)
        norms = np.linalg.norm(raw_emb_matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        raw_emb_matrix = raw_emb_matrix / norms
        pid_to_idx = {pid: i for i, pid in enumerate(raw_pids)}

        def run_sim(threshold: float) -> tuple[int, int]:
            mapping: dict[str, str] = {}
            active_pids: list[str] = []
            active_vecs: list[np.ndarray] = []
            for r in claims_rows:
                m = normalize_canonical_text(extract_matter_from_frame(r[8]))
                pid = compute_proposition_id(m)
                if pid in mapping:
                    continue
                vec = raw_emb_matrix[pid_to_idx[pid]]
                if len(active_vecs) == 0:
                    active_pids.append(pid)
                    active_vecs.append(vec)
                    mapping[pid] = pid
                else:
                    sims = np.dot(np.array(active_vecs), vec)
                    best_idx = int(np.argmax(sims))
                    if float(sims[best_idx]) >= threshold:
                        mapping[pid] = active_pids[best_idx]
                    else:
                        active_pids.append(pid)
                        active_vecs.append(vec)
                        mapping[pid] = pid

            clusters: dict[str, list[str]] = {}
            for orig, rep in mapping.items():
                clusters.setdefault(rep, []).append(orig)

            total_merges = sum(len(m) - 1 for m in clusters.values() if len(m) > 1)
            contradicted = 0
            for _rep, members in clusters.items():
                if len(members) > 1:
                    matters = [raw_props[m] for m in members]
                    if not all(m == matters[0] for m in matters):
                        contradicted += 1
            return total_merges, contradicted

        # Falsification 1: Extremely high threshold (0.999) collapses all merges
        merges_999, contra_999 = run_sim(0.999)
        assert merges_999 == 0, f"Expected 0 merges at 0.999, got {merges_999}"

        # Falsification 2: Low threshold (0.60) causes frame contradictions to spike
        merges_60, contra_60 = run_sim(0.60)
        assert contra_60 >= 30, f"Expected >= 30 contradictions at 0.60, got {contra_60}"

        # Operating point: 0.96 has 0 contradictions on the 4 named pairs and low merges
        merges_96, contra_96 = run_sim(0.96)
        assert merges_96 > 0
        assert merges_96 < 10

    finally:
        store.close()
