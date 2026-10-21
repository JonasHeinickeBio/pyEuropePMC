"""The documentation of the MCP server must name every tool it serves.

The tool table in ``src/pyeuropepmc/mcp/README.md`` and the tool list in the ``server.py``
docstring are written by hand; the tool count appears in the project README and in the
docs overview. A release that adds a tool without touching them fails here instead of
shipping wrong numbers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import re

import pytest

from pyeuropepmc.mcp import server as srv

ROOT = Path(__file__).parents[3]
README = ROOT / "README.md"
MCP_README = ROOT / "src" / "pyeuropepmc" / "mcp" / "README.md"
GUIDE = ROOT / "docs" / "features" / "mcp-server.md"
FEATURES = ROOT / "docs" / "features" / "README.md"
SUMMARY = ROOT / "docs" / "SUMMARY.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tool_names() -> set[str]:
    return {tool.name for tool in asyncio.run(srv.mcp.list_tools())}


def _backticked(text: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9_]+)`", text))


def test_the_mcp_readme_table_lists_every_tool(tool_names):
    assert tool_names - _backticked(_read(MCP_README)) == set()


def test_the_server_docstring_lists_every_tool(tool_names):
    docstring = srv.__doc__ or ""
    missing = {name for name in tool_names if not re.search(rf"\b{name}\b", docstring)}
    assert missing == set()


def test_the_guide_names_only_real_tools(tool_names):
    """A tool that was renamed or removed must not live on in the guide's examples."""
    text = _read(GUIDE)
    called = set(re.findall(r"^\s*([a-z][a-z0-9_]+)\s{2,}\w+=", text, re.MULTILINE))
    assert called, "the guide lost its example calls"
    assert called <= tool_names


def test_the_tool_count_in_the_docs_is_current(tool_names):
    count = len(tool_names)
    assert f"serves {count} tools" in _read(README)
    assert f"({count} tools)" in _read(FEATURES)


def test_the_guide_is_linked_from_the_indexes():
    assert "features/mcp-server.md" in _read(SUMMARY)
    assert "mcp-server.md" in _read(FEATURES)
    assert "docs/features/mcp-server.md" in _read(README)
