"""Start the local review site.

Usage:
    .venv/bin/python scripts/serve_site.py

Prints the URL to open, including the bearer token as a query parameter. The
first request sets an `sp_token` cookie, so navigation afterwards needs no token.

The site opens DuckDB read-only (Item A0): if a writing worker already holds
the database, `create_app` raises rather than silently handing the site a
writable cursor. Stop the worker and retry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.api.security import TokenManager
from worker.api.server import run_server
from worker.storage import Storage


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Social Proof review site on loopback.")
    parser.add_argument("--db", default="social_proof.duckdb")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    token = TokenManager().token
    print(f"\n  Review site:  http://127.0.0.1:{args.port}/?token={token}\n")
    print("  Episodes are the front page; click a claim for its Social Proof panel.")
    print("  Ctrl-C to stop.\n")

    run_server(storage=Storage(db_path=args.db, read_only=True), port=args.port, token=token)


if __name__ == "__main__":
    main()
