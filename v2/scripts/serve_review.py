"""Social Proof V2 — Review Site Loopback Server.

Implements B5 Step 6 from v2/docs/agent_execution_guide.md §9.
Binds strictly to 127.0.0.1, read-only posture, zero disk writes, zero network calls.

Usage:
    .venv/bin/python v2/scripts/serve_review.py [--port 8787] [--episode EPISODE_ID]
"""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from v2.src.review import (
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_GOLD_DIR,
    DEFAULT_TRANSCRIPT_DIR,
    REFERENCE_EPISODE,
    list_available_episodes,
    load_episode_data,
    render_review_html,
)


class ReviewRequestHandler(BaseHTTPRequestHandler):
    """Read-only HTTP handler serving episode review pages on loopback."""

    server_version = "SocialProofReview/2.0"

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        if path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            payload = {
                "status": "ok",
                "host": "127.0.0.1",
                "read_only": True,
                "default_episode": REFERENCE_EPISODE,
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if path in ("/", "/index.html", "/review"):
            # Determine episode
            episodes = list_available_episodes(DEFAULT_TRANSCRIPT_DIR)
            episode_id = query.get("episode", [None])[0]
            if not episode_id:
                # Default to reference episode if available, else first episode
                available_ids = [e["source_id"] for e in episodes]
                if REFERENCE_EPISODE in available_ids:
                    episode_id = REFERENCE_EPISODE
                elif episodes:
                    episode_id = episodes[0]["source_id"]
                else:
                    self.send_error(HTTPStatus.NOT_FOUND, "No transcript episodes found on disk.")
                    return

            try:
                data = load_episode_data(
                    source_id=episode_id,
                    transcript_dir=DEFAULT_TRANSCRIPT_DIR,
                    gold_dir=DEFAULT_GOLD_DIR,
                    extraction_dir=DEFAULT_EXTRACTION_DIR,
                )
                html_content = render_review_html(data, all_episodes=episodes)
                body = html_content.encode("utf-8")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError as e:
                self.send_error(HTTPStatus.NOT_FOUND, str(e))
            except Exception as e:  # noqa: BLE001
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error rendering review page: {e}")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        """Strictly reject writes with 405 Method Not Allowed."""
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Review site is strictly read-only.")

    def do_PUT(self) -> None:
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Review site is strictly read-only.")

    def do_DELETE(self) -> None:
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Review site is strictly read-only.")

    def log_message(self, format: str, *args: object) -> None:
        # Suppress noise, log concise requests
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}\n")


def create_server(host: str = "127.0.0.1", port: int = 8787, auto_port: bool = False) -> ThreadingHTTPServer:
    """Creates a ThreadingHTTPServer bound strictly to loopback."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"Security invariant: Review site must bind only to loopback (127.0.0.1), got {host}")

    current_port = port
    while True:
        try:
            return ThreadingHTTPServer((host, current_port), ReviewRequestHandler)
        except OSError as e:
            if auto_port and e.errno == 48:  # Address already in use
                current_port += 1
                if current_port > port + 20:
                    raise
                continue
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Social Proof V2 review site on loopback.")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind (default: 8787)")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (must be 127.0.0.1)")
    parser.add_argument("--episode", default=REFERENCE_EPISODE, help="Default episode ID to display")
    args = parser.parse_args()

    # If default port 8787 is in use (e.g. by V1 server), auto-fallback to next port
    server = create_server(host=args.host, port=args.port, auto_port=True)
    actual_port = server.server_port
    url = f"http://{args.host}:{actual_port}/?episode={args.episode}"

    print("\n========================================================")
    print("  Social Proof V2 Review Site (B5)")
    print(f"  URL: {url}")
    print("  Posture: read-only, loopback 127.0.0.1, zero writes")
    print("  Press Ctrl+C to stop.")
    print("========================================================\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping review server...", flush=True)
    finally:
        server.server_close()



if __name__ == "__main__":
    main()
