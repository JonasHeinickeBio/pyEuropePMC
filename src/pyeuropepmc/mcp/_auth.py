"""Bearer-token authentication for the MCP server's HTTP transports.

Opt-in: with no token configured the HTTP transports behave as before, and stdio never
checks anything (the client owns the process). With one or more tokens every HTTP request
must carry ``Authorization: Bearer <token>``; anything else is answered with HTTP 401 before
the MCP server sees it. The check is a plain ASGI middleware, so it works the same under
MCP SDK 1.x and 2.x and for both the streamable-HTTP and the SSE transport.

Tokens come from the environment (``PYEUROPEPMC_MCP_AUTH_TOKEN``, comma separated) or a file
(``--auth-token-file`` or ``PYEUROPEPMC_MCP_AUTH_TOKEN_FILE``, one per line), never from a
command-line value, which every user of the machine can read in the process list. Several
tokens at once allow rotation: add the new one, move clients over, remove the old one.

Pure apart from reading the token file.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
import hashlib
import hmac
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
from typing import Any

logger = logging.getLogger("pyeuropepmc.mcp")

ENV_TOKEN = "PYEUROPEPMC_MCP_AUTH_TOKEN"  # nosec B105 - the name of a variable, not a secret
ENV_TOKEN_FILE = "PYEUROPEPMC_MCP_AUTH_TOKEN_FILE"  # nosec B105 - a variable name
#: A shorter token is refused: 16 characters is the least that cannot be guessed online.
MIN_TOKEN_CHARS = 16
REALM = "pyeuropepmc-mcp"

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_TOKEN = re.compile(r"^[\x21-\x7e]+$")  # printable ASCII, no spaces: safe in a header


class AuthConfigError(ValueError):
    """The token configuration is unusable; the message says what to change."""


def generate_token() -> str:
    """A new random token (256 bits, URL-safe)."""
    return secrets.token_urlsafe(32)


def _check(token: str, source: str) -> str:
    if len(token) < MIN_TOKEN_CHARS:
        raise AuthConfigError(
            f"{source}: a token must have at least {MIN_TOKEN_CHARS} characters "
            "(pyeuropepmc-mcp --generate-token makes one)"
        )
    if not _TOKEN.match(token):
        raise AuthConfigError(f"{source}: a token must be printable ASCII without spaces")
    return token


def _from_file(path: str) -> list[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise AuthConfigError(f"cannot read the token file {path!r}: {exc.strerror}") from exc
    lines = [ln.strip() for ln in text.splitlines()]
    return [_check(ln, f"token file {path!r}") for ln in lines if ln and not ln.startswith("#")]


def load_tokens(file: str = "", environ: MutableMapping[str, str] | None = None) -> list[str]:
    """The accepted tokens: from the token file (the argument, else the environment) and from
    ``PYEUROPEPMC_MCP_AUTH_TOKEN``. Empty when authentication is not configured; raises
    :class:`AuthConfigError` for a token file that cannot be read or a token that is too weak,
    and for a variable that is set but holds no token (a typo must not open the server)."""
    env = os.environ if environ is None else environ
    tokens: list[str] = []
    path = file or env.get(ENV_TOKEN_FILE, "")
    if path:
        found = _from_file(path)
        if not found:
            raise AuthConfigError(f"the token file {path!r} holds no token")
        tokens += found
    raw = env.get(ENV_TOKEN)
    if raw is not None:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if not parts:
            raise AuthConfigError(f"{ENV_TOKEN} is set but empty")
        tokens += [_check(p, ENV_TOKEN) for p in parts]
    return list(dict.fromkeys(tokens))


def is_loopback(host: str) -> bool:
    """Whether a bind address is reachable from this machine only."""
    name = host.strip("[]").lower()
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


class BearerAuthMiddleware:
    """ASGI middleware that lets a request through only with a valid bearer token.

    Every token is compared (in constant time, on SHA-256 digests so that the length of a token
    does not leak either), whether or not an earlier one matched. Lifespan events pass
    unchanged; WebSocket connections, which MCP does not use, are refused.
    """

    def __init__(self, app: ASGIApp, tokens: list[str]) -> None:
        if not tokens:
            raise AuthConfigError("BearerAuthMiddleware needs at least one token")
        self.app = app
        self._digests = [_digest(t) for t in tokens]

    def _authorised(self, scope: Scope) -> bool:
        presented = ""
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                scheme, _, credentials = value.decode("latin-1").partition(" ")
                if scheme.lower() == "bearer":
                    presented = credentials.strip()
                break
        digest = _digest(presented)
        matched = False
        for known in self._digests:
            matched |= hmac.compare_digest(digest, known)
        return matched and bool(presented)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan" or (scope["type"] == "http" and self._authorised(scope)):
            await self.app(scope, receive, send)
        elif scope["type"] == "http":
            logger.warning(
                "refused %s %s: missing or invalid bearer token",
                scope.get("method", "?"),
                scope.get("path", "?"),
            )
            await _unauthorised(send)
        else:
            await send({"type": "websocket.close", "code": 1008})


async def _unauthorised(send: Send) -> None:
    body = json.dumps({"error": "unauthorized", "detail": "a valid bearer token is required"})
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", f'Bearer realm="{REALM}"'.encode()),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body.encode()})
