"""Security controls for the local HTTP API.

Implements design_local_api_and_clients.md §2 and agent_execution_guide.md §22:
1. Bind to 127.0.0.1 loopback ONLY; assert at startup.
2. Bearer token authentication on every request.
3. Strict CORS rejecting wildcard * unconditionally.
4. Uniform error response for bad token and unknown routes.
"""

import os
import re
import secrets
from pathlib import Path
from typing import Any, ClassVar

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


def validate_host(host: str) -> None:
    """Enforces that server binds to 127.0.0.1 loopback only."""
    allowed = ("127.0.0.1", "localhost")
    if host not in allowed:
        raise ValueError(
            f"Security violation: Server must bind to 127.0.0.1 loopback only, got '{host}'. "
            "Binding to 0.0.0.0 or external interfaces exposes the corpus to the local network."
        )


class TokenManager:
    """Manages Bearer token provisioning, persistence, and verification."""

    def __init__(self, token: str | None = None, token_file: str | Path = ".api_token") -> None:
        self.token_file = Path(token_file)
        if token:
            self._token = token
        elif "SOCIAL_PROOF_API_TOKEN" in os.environ:
            self._token = os.environ["SOCIAL_PROOF_API_TOKEN"].strip()
        elif self.token_file.exists():
            self._token = self.token_file.read_text().strip()
        else:
            self._token = secrets.token_urlsafe(32)
            try:
                self.token_file.write_text(self._token)
                self.token_file.chmod(0o600)
            except OSError:
                pass

    @property
    def token(self) -> str:
        return self._token

    def verify(self, auth_header: str | None) -> bool:
        """Verifies Bearer token header."""
        if not auth_header:
            return False
        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return False
        return secrets.compare_digest(parts[1], self._token)


class CORSPolicy:
    """Strict CORS policy rejecting wildcard origins unconditionally."""

    ALLOWED_ORIGIN_REGEXES: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^chrome-extension://[a-z0-9]+$"),
        re.compile(r"^moz-extension://[a-z0-9\-]+$"),
        re.compile(r"^http://127\.0\.0\.1(:\d+)?$"),
        re.compile(r"^http://localhost(:\d+)?$"),
    ]

    @classmethod
    def is_allowed_origin(cls, origin: str | None) -> bool:
        """Verifies origin against allowed client regexes; rejects wildcard unconditionally."""
        if not origin or origin == "*":
            return False
        return any(pat.match(origin) for pat in cls.ALLOWED_ORIGIN_REGEXES)


async def auth_middleware(request: Request, call_next: Any) -> Any:
    """Middleware enforcing Bearer token and strict CORS.

    Emits uniform 404 response on bad token so the API is not a discovery surface.
    """
    # Allow CORS preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)

    token_manager: TokenManager = request.app.state.token_manager
    auth_header = request.headers.get("Authorization")
    query_token = request.query_params.get("token")
    cookie_token = request.cookies.get("sp_token")

    authed = False
    set_cookie = False

    if auth_header and token_manager.verify(auth_header):
        authed = True
    elif query_token and secrets.compare_digest(query_token, token_manager.token):
        authed = True
        set_cookie = True
    elif cookie_token and secrets.compare_digest(cookie_token, token_manager.token):
        authed = True

    if not authed:
        # Uniform 404 response matching unknown routes
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Not Found"},
        )

    # Validate origin if present
    origin = request.headers.get("Origin")
    if origin and not CORSPolicy.is_allowed_origin(origin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Origin not allowed by local CORS policy",
        )

    response = await call_next(request)
    if set_cookie:
        response.set_cookie("sp_token", token_manager.token, httponly=True, samesite="lax")
    if origin and CORSPolicy.is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"

    return response
