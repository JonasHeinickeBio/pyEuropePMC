"""Internal invariants of the MCP server are explicit errors, not ``assert`` (stripped under -O).

Each case breaks the invariant on purpose; an ``assert`` would raise ``AssertionError`` (a bare
traceback for the client), the explicit check raises the ``ToolError`` the client is shown.
"""

from __future__ import annotations

import asyncio

import pytest

from pyeuropepmc.mcp import _mesh as mm, server as srv
from pyeuropepmc.mcp.server import ToolError


def _run(coro):
    return asyncio.run(coro)


class TestUnifiedSearch:
    def test_a_missing_client_is_reported_not_asserted(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        monkeypatch.setattr(srv, "_get_unified", lambda: None)
        with pytest.raises(ToolError, match="UnifiedSearch is not available"):
            _run(srv.unified_search(query="cancer"))


class TestMeshSnapshot:
    def test_pico_decompose_without_a_snapshot(self, monkeypatch):
        monkeypatch.setattr(mm, "snapshot", lambda: None)
        with pytest.raises(ToolError, match="MeSH snapshot is not loaded"):
            _run(
                srv.pico_decompose(
                    question="In adults with type 2 diabetes, does metformin reduce mortality?",
                    mesh=True,
                )
            )

    def test_mesh_expand_without_a_snapshot(self, monkeypatch):
        monkeypatch.setattr(mm, "snapshot", lambda: None)
        with pytest.raises(ToolError, match="MeSH snapshot is not loaded"):
            srv._expand_terms(["metformin"], use_api=False, max_entry_terms=5)


class TestUnderOptimizedPython:
    def test_a_missing_client_is_still_reported_under_python_O(self):
        """``python -O`` strips ``assert``; the check must survive it (#196)."""
        import subprocess
        import sys

        code = (
            "import asyncio\n"
            "from pyeuropepmc.mcp import server as srv\n"
            "srv.UNIFIED_AVAILABLE = True\n"
            "srv._get_unified = lambda: None\n"
            "try:\n"
            "    asyncio.run(srv.unified_search(query='cancer'))\n"
            "except srv.ToolError as exc:\n"
            "    print('ToolError:', exc)\n"
        )
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-O", "-c", code], capture_output=True, text=True, timeout=120
        )
        assert "ToolError: UnifiedSearch is not available" in done.stdout, done.stderr
