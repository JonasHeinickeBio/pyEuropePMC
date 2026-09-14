"""Test configuration specific to the MCP test suite.

Every test under here drives async code — ``asyncio.run(...)`` directly in
the unit tests, ``async def test_...`` via pytest-asyncio in the e2e tests.
Creating *any* new event loop on Windows makes CPython call
``socket.socketpair()`` for the loop's internal self-pipe/wakeup mechanism;
Windows has no native ``socketpair()``, so the standard library falls back
to a real (loopback-only) TCP socket pair (``socket._fallback_socketpair``
in CPython's ``Lib/socket.py``). That happens while the event loop is being
constructed, before any test body runs — it isn't something a test can
avoid by not touching the network itself. Linux's default event loop uses a
plain OS pipe for the same purpose and never needs a socket, which is why
this is Windows-only.

Under this project's default ``--disable-socket`` (pytest-socket), a bare
``socket.socket()`` call is blocked outright — regardless of destination —
which raises ``SocketBlockedError`` while asyncio is still setting up,
before the test even starts. ``pytest.mark.allow_hosts`` switches
pytest-socket to its narrower mode instead: socket *construction* is
allowed, and only ``.connect()`` calls to hosts outside the allowlist are
blocked, so an accidental real network call in these tests still fails
loudly — it just no longer blocks the loopback connection asyncio's own
plumbing needs to exist at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Allow loopback-only sockets for tests collected under this directory.

    ``pytest_collection_modifyitems`` receives the *entire* session's items
    regardless of which conftest.py defines it — a nested conftest doesn't
    scope the hook to its own directory automatically — so this filters to
    only the items actually under ``tests/mcp/``.
    """
    marker = pytest.mark.allow_hosts(["127.0.0.1", "::1"])
    for item in items:
        try:
            item.path.relative_to(_THIS_DIR)
        except ValueError:
            continue
        item.add_marker(marker)
