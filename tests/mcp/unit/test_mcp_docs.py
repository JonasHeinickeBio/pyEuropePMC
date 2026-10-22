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
    prompts = {p.name for p in asyncio.run(srv.mcp.list_prompts())}
    assert called <= tool_names | prompts


def test_the_tool_count_in_the_docs_is_current(tool_names):
    count = len(tool_names)
    assert f"serves {count} tools" in _read(README)
    assert f"({count} tools)" in _read(FEATURES)


def test_the_guide_is_linked_from_the_indexes():
    assert "features/mcp-server.md" in _read(SUMMARY)
    assert "mcp-server.md" in _read(FEATURES)
    assert "docs/features/mcp-server.md" in _read(README)


def test_the_docs_name_every_resource_and_prompt():
    templates = asyncio.run(srv.mcp.list_resource_templates())
    uris = [getattr(t, "uriTemplate", None) or t.uri_template for t in templates]
    prompts = [p.name for p in asyncio.run(srv.mcp.list_prompts())]
    assert uris and prompts
    docstring = srv.__doc__ or ""
    assert all(u in docstring for u in uris)
    assert all(p in docstring for p in prompts)
    for doc in (MCP_README, GUIDE):
        text = _read(doc)
        for uri in uris:  # the guide writes a real id (PMC3525259) where the template has {pmcid}
            shape = re.escape(uri).replace(r"\{pmcid\}", r"(?:\{pmcid\}|PMC\d+)")
            assert re.search(shape + r"(?![\w/])", text), f"{doc.name} lacks {uri}"
        for name in prompts:
            assert re.search(rf"`{name}`|^{name}\s", text, re.MULTILINE), (
                f"{doc.name} lacks {name}"
            )
