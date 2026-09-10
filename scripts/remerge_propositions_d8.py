"""Re-resolution script for Item D8: Re-resolve proposition deduplication at T_dedup = 0.96.

Contracts:
- docs/agent_execution_guide.md §12
- docs/ongoing_errors.md §2 (Parameter 008)
- docs/design_claim_extraction.md §2
"""

import shutil
import time

from worker.extract.dedup import DEFAULT_T_DEDUP, get_embedder
from worker.integrity import run_integrity_corpus
from worker.storage import Storage, compute_proposition_id, normalize_canonical_text
from worker.tension.detect import extract_matter_from_frame


def remerge_d8(db_path: str = "social_proof.duckdb", threshold: float = DEFAULT_T_DEDUP) -> None:
    print(f"=== ITEM D8: Proposition Re-resolution at T_dedup = {threshold:.3f} ===")

    # 1. Backup
    bak_path = f"{db_path}.pre_d8.bak"
    print(f"1. Backing up {db_path} -> {bak_path}...")
    shutil.copy(db_path, bak_path)

    store = Storage(db_path)
    embedder = get_embedder()

    # 2. Fetch all claims
    claims = store.con.execute(
        "SELECT claim_id, position_frame, quote_text, subject_id FROM claims"
    ).fetchall()
    print(f"2. Loaded {len(claims)} claims from database.")

    # 3. Identify raw unmerged propositions from stored position_frames
    raw_props: dict[str, tuple[str, str]] = {}  # pid -> (matter, subject_id)
    for cid, frame, _quote, sid in claims:
        matter = normalize_canonical_text(extract_matter_from_frame(frame))
        pid = compute_proposition_id(matter)
        raw_props[pid] = (matter, sid)
        store.con.execute("UPDATE claims SET proposition_id = ? WHERE claim_id = ?", [pid, cid])

    print(f"3. Reconstructed {len(raw_props)} raw unmerged propositions from claims' frames.")

    # 4. Ensure all raw propositions and embeddings exist in store
    existing_pids = set(
        r[0] for r in store.con.execute("SELECT proposition_id FROM propositions").fetchall()
    )
    existing_embs = set(
        r[0] for r in store.con.execute("SELECT proposition_id FROM proposition_embeddings").fetchall()
    )

    new_embs_count = 0
    for pid, (matter, sid) in raw_props.items():
        if pid not in existing_pids:
            store.con.execute(
                """
                INSERT INTO propositions (proposition_id, canonical_text, subject_ids, claim_count, status, quarantine_reason)
                VALUES (?, ?, ?, 1, 'active', NULL)
                """,
                [pid, matter, [sid]],
            )
        if pid not in existing_embs:
            vec = embedder.embed_document(matter)
            store.con.execute(
                "INSERT INTO proposition_embeddings (proposition_id, embedding) VALUES (?, ?)",
                [pid, vec],
            )
            new_embs_count += 1

    print(f"4. Populated missing raw propositions; generated {new_embs_count} new embeddings.")

    # 5. Snapshot pre-merge tables with the clean unmerged v1.8 distribution
    store.con.execute("DROP TABLE IF EXISTS claims_pre_merge; CREATE TABLE claims_pre_merge AS SELECT * FROM claims;")
    store.con.execute("DROP TABLE IF EXISTS propositions_pre_merge; CREATE TABLE propositions_pre_merge AS SELECT * FROM propositions;")
    store.con.execute("DROP TABLE IF EXISTS proposition_embeddings_pre_merge; CREATE TABLE proposition_embeddings_pre_merge AS SELECT * FROM proposition_embeddings;")

    # 6. Run reresolve_propositions at threshold
    t0 = time.perf_counter()
    print(f"5. Running store.reresolve_propositions(t_dedup={threshold:.3f})...")
    stats = store.reresolve_propositions(
        t_dedup=threshold,
        embedder=embedder,
        from_pre_merge=True,
    )
    el = time.perf_counter() - t0
    print(f"   Re-resolution completed in {el:.2f}s:")
    print(f"     Surviving propositions: {stats['surviving_propositions']}")
    print(f"     Merged away: {stats['merged_away_propositions']}")
    print(f"     Merge histogram: {stats['merge_histogram']}")
    print(f"     Multi-source diff date propositions: {stats['multi_source_diff_date_propositions']}")

    # 7. Clean up claim counts and prune any dead propositions
    store.con.execute("""
        UPDATE propositions
        SET claim_count = (
            SELECT count(*)
            FROM claims
            WHERE claims.proposition_id = propositions.proposition_id
        );
    """)
    store.con.execute("DELETE FROM propositions WHERE claim_count = 0 AND status = 'active';")
    store.con.execute("DELETE FROM proposition_embeddings WHERE proposition_id NOT IN (SELECT proposition_id FROM propositions);")
    store.close()

    # 8. Run integrity pass over updated database
    print("\n6. Running Evidence Integrity Pass over updated database...")
    results = run_integrity_corpus(db_path)
    all_passed = True
    for r in results:
        status_str = f"[{r.status}]"
        print(f"  {r.name:<32} {status_str:<12} (examined: {r.examined_count:<5}) {r.message}")
        if not r.passed:
            all_passed = False

    if not all_passed:
        raise RuntimeError("Integrity pass FAILED on re-resolved database!")
    print("\nSUCCESS: All 16 integrity checks PASSED on live database!")


if __name__ == "__main__":
    remerge_d8()
