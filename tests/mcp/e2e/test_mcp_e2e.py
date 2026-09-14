"""End-to-end tests for the pyeuropepmc MCP server.

These spawn the real ``pyeuropepmc.mcp.server`` module as a subprocess over
stdio and drive it with the official MCP client (``mcp.client.stdio`` +
``ClientSession``), instead of hand-rolling JSON-RPC framing — that framing,
capability negotiation, and content/structuredContent shape are the SDK's
concern, not ours to reimplement in a test. A couple of these tests call the
real Europe PMC API, hence ``network``/``e2e``.

Each test opens its own client/subprocess via ``_server_session()`` *inside*
the test body rather than through a pytest fixture: anyio's task groups (used
internally by ``stdio_client``/``ClientSession``) are affine to the asyncio
Task they were entered in, and pytest-asyncio's default per-phase execution
runs a fixture's setup, the test, and its teardown as separate awaits — not
guaranteed to be the same Task. Keeping the whole ``async with`` inside one
test coroutine sidesteps that "exit cancel scope in a different task"
failure entirely.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import pytest

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.e2e]


@asynccontextmanager
async def _server_session():
    """Spawn the real server subprocess and yield an initialized (session, InitializeResult)."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "pyeuropepmc.mcp.server"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        init_result = await client.initialize()
        yield client, init_result


class TestMCPProtocol:
    async def test_initialize_reports_server_identity(self):
        async with _server_session() as (_session, init_result):
            assert init_result.serverInfo.name == "pyeuropepmc-mcp"
            assert init_result.protocolVersion

    async def test_tools_list_is_non_empty_and_well_formed(self):
        async with _server_session() as (session, _init_result):
            result = await session.list_tools()
            assert len(result.tools) >= 20
            for tool in result.tools:
                assert tool.description
                assert tool.inputSchema["type"] == "object"

    async def test_unknown_tool_is_reported_as_a_tool_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("totally_unknown_tool", {})
            assert result.isError is True
            assert "Unknown tool" in result.content[0].text

    async def test_missing_required_argument_is_a_validation_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_paper_details", {})
            assert result.isError is True
            assert "At least one ID" in result.content[0].text


@pytest.mark.network
class TestMCPToolsAgainstRealEuropePMC:
    async def test_search_papers_returns_structured_results(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("search_papers", {"query": "malaria", "limit": 2})
            assert result.isError is False
            assert isinstance(result.structuredContent["result"], list)

    async def test_get_paper_details_round_trip(self):
        async with _server_session() as (session, _init_result):
            search_result = await session.call_tool(
                "search_papers", {"query": "malaria", "limit": 1}
            )
            papers = search_result.structuredContent["result"]
            if not papers:
                pytest.skip("Europe PMC returned no candidates for this query right now")

            paper_id = papers[0].get("pmid") or papers[0].get("pmcid") or papers[0].get("doi")
            if not paper_id:
                pytest.skip("Candidate paper has no usable identifier")

            details = await session.call_tool("get_paper_details", {"pmid": paper_id})
            assert details.isError is False
            assert isinstance(details.structuredContent, dict)
