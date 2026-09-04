"""One-shot migration script for Proposition Table Repair (D0 · Issue 027 = Option A).

Enforces:
1. Normalizes proposition IDs via normalize_canonical_text (terminal punctuation stripped).
2. Merges duplicate rows into live survivors without cascade.
3. Updates IDs for orphaned rows.
4. Recomputes claim_count from actual claims table.
5. Quarantines fabricated proposition db3ec63d33cf6f0a.
6. Backfills nomic-embed-text-v1.5 embeddings for all 8 live propositions using embed_document prefix.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.extract.dedup import NomicEmbedder
from worker.storage import Storage


def run_migration(db_path: str = "social_proof.duckdb") -> dict[str, int]:
    p = Path(db_path)
    if not p.exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to {db_path}...")
    store = Storage(str(p))
    try:
        print("Running proposition migration...")
        embedder = NomicEmbedder()
        report = store.migrate_propositions(embedder=embedder)
        print("Migration complete. Report:")
        print(json.dumps(report, indent=2))
        return report
    finally:
        store.con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate propositions table (D0)")
    parser.add_argument("--db", type=str, default="social_proof.duckdb", help="Path to DuckDB database")
    args = parser.parse_args()
    run_migration(args.db)


if __name__ == "__main__":
    main()
