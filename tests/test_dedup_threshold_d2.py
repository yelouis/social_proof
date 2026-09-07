"""Tests for Item D2 (§13v): Re-measuring Parameter 008 (T_dedup) against the live corpus.

Verifies:
1. Assertion (c): At least one proposition carries claims from two different episodes with opposing stances (candidate set non-empty).
2. Both directions at chosen threshold (T_dedup = 0.84):
   - China open source propositions merge (sim >= 0.84).
   - High speed trains in China does not merge into China open source (sim << 0.84).
3. 1-NN similarity distribution decile bounds and structure.
4. Falsification: T_dedup = 0.999 collapses merges to 0; T_dedup = 0.30 produces absurd merges.
"""

import json
from pathlib import Path

import duckdb

from worker.extract.dedup import DEFAULT_T_DEDUP, get_embedder
from worker.storage import Storage
from worker.tension.detect import TensionDetector


def test_default_t_dedup_is_084() -> None:
    """Parameter 008 single source of truth is 0.84."""
    assert DEFAULT_T_DEDUP == 0.84


def test_assertion_c_cross_episode_opposing_claims_exist() -> None:
    """Assertion (c): At least one proposition carries claims from two different episodes with opposing stances.

    Evaluates live DuckDB corpus under TensionDetector.
    """
    store = Storage("social_proof.duckdb", read_only=True)
    detector = TensionDetector(store)
    report = detector.evaluate_candidate_pairs()

    # The candidate set is non-empty for the first time
    assert report.total_pairs_examined >= 6, (
        f"Expected at least 6 candidate pairs examined, got {report.total_pairs_examined}"
    )
    assert report.candidates_accepted >= 6, (
        f"Expected at least 6 candidate pairs accepted, got {report.candidates_accepted}"
    )

    # Confirm across the database that at least one proposition spans 2+ distinct source_ids with support and oppose
    con = duckdb.connect("social_proof.duckdb", read_only=True)
    query = """
        SELECT
            c.proposition_id,
            COUNT(DISTINCT u.source_id) as ep_count,
            COUNT(DISTINCT c.stance) as stance_count,
            LIST(DISTINCT c.stance) as stances
        FROM claims c
        JOIN utterances u ON c.utterance_id = u.utterance_id
        WHERE c.is_own_assertion AND c.stance IN ('support', 'oppose')
        GROUP BY c.proposition_id
        HAVING ep_count >= 2 AND stance_count >= 2
    """
    rows = con.execute(query).fetchall()
    assert len(rows) >= 1, "Expected at least one proposition with multi-episode opposing stances"
    con.close()


def test_canonical_both_directions_at_chosen_threshold() -> None:
    """Both directions at chosen threshold (T_dedup = 0.84):

    1. The two 'China open source' propositions merge (sim >= 0.84).
    2. 'high speed trains in China are built and operated by private industry' does NOT merge into open source (sim < 0.84).
    """
    embedder = get_embedder()

    # Canonical phrasing from P0 / §13v
    p_china_1 = "China has made a significant push towards open source software"
    p_china_2 = "The leading open source models are from China these days"
    p_trains = "high speed trains in China are built and operated by private industry"

    sim_china_pair = embedder.similarity(p_china_1, p_china_2)
    sim_trains_1 = embedder.similarity(p_china_1, p_trains)
    sim_trains_2 = embedder.similarity(p_china_2, p_trains)

    # Target threshold is 0.84
    assert sim_china_pair >= DEFAULT_T_DEDUP, (
        f"Expected China open source pair ({sim_china_pair:.4f}) to merge at T={DEFAULT_T_DEDUP}"
    )
    assert sim_trains_1 < DEFAULT_T_DEDUP, (
        f"Expected trains vs china_1 ({sim_trains_1:.4f}) NOT to merge at T={DEFAULT_T_DEDUP}"
    )
    assert sim_trains_2 < DEFAULT_T_DEDUP, (
        f"Expected trains vs china_2 ({sim_trains_2:.4f}) NOT to merge at T={DEFAULT_T_DEDUP}"
    )

    # Also test live noun-phrase matters at issue from corpus
    np_china_1 = "societal and official optimism toward open source in china"
    np_china_2 = "societal and official optimism toward artificial intelligence in china compared to western nations"
    np_trains = "high speed trains going 125 motherf***ing hours miles per hour"

    sim_np_china = embedder.similarity(np_china_1, np_china_2)
    sim_np_trains = embedder.similarity(np_china_1, np_trains)

    assert sim_np_china >= DEFAULT_T_DEDUP, (
        f"Expected noun-phrase China pair ({sim_np_china:.4f}) to merge at T={DEFAULT_T_DEDUP}"
    )
    assert sim_np_trains < DEFAULT_T_DEDUP, (
        f"Expected noun-phrase trains ({sim_np_trains:.4f}) NOT to merge at T={DEFAULT_T_DEDUP}"
    )


def test_nearest_neighbour_distribution_deciles() -> None:
    """Verifies that 1-NN similarity distribution has been calculated, recorded, and has structure."""
    fixture_path = Path("fixtures/behaviour/d2_dedup_distribution.json")
    assert fixture_path.exists(), "Distribution fixture fixtures/behaviour/d2_dedup_distribution.json must exist"

    with open(fixture_path) as f:
        data = json.load(f)

    assert data["n"] >= 2100
    assert "deciles" in data
    deciles = data["deciles"]

    # Verify monotonic increasing deciles
    vals = [deciles[f"D{p}"] for p in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]]
    for i in range(len(vals) - 1):
        assert vals[i] <= vals[i + 1]

    # Verify D90 is in expected range ~0.835
    assert 0.82 <= deciles["D90"] <= 0.85
    # Verify D50 (median) is ~0.755
    assert 0.73 <= deciles["D50"] <= 0.78


def test_falsification_t_dedup_extremes() -> None:
    """Falsification test:

    - At T_dedup = 0.999, merges collapse to zero.
    - At T_dedup = 0.30, absurd merges appear (e.g. trains merged with open source).
    """
    embedder = get_embedder()
    p_china_1 = "China has made a significant push towards open source software"
    p_china_2 = "The leading open source models are from China these days"
    p_trains = "high speed trains in China are built and operated by private industry"

    sim_china_pair = embedder.similarity(p_china_1, p_china_2)
    sim_trains = embedder.similarity(p_china_1, p_trains)

    # Extreme 1: T = 0.999 collapses all merges
    t_strict = 0.999
    assert sim_china_pair < t_strict, "At T=0.999 even near-identical China pair must not merge"
    assert sim_trains < t_strict

    # Extreme 2: T = 0.30 produces absurd merges
    t_absurd = 0.30
    assert sim_trains >= t_absurd, "At T=0.30 absurd pair (trains vs open source) falsely merges"
