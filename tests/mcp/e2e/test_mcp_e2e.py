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
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import pytest

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.e2e]


@asynccontextmanager
async def _server_session():
    """Spawn the real server subprocess and yield an initialized (session, InitializeResult)."""
    # stdio_client only forwards a short allow-list of variables by default. Hand over the
    # whole environment so the subprocess imports the same pyeuropepmc as the test
    # (PYTHONPATH, a worktree checkout) rather than whichever install is first on its path.
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "pyeuropepmc.mcp.server"], env=dict(os.environ)
    )
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

    async def test_search_papers_stops_at_limit_for_a_broad_query(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("search_papers", {"query": "CRISPR", "limit": 3})
            assert result.isError is False
            assert len(result.structuredContent["result"]) == 3

    async def test_search_papers_filters_and_count_papers(self):
        async with _server_session() as (session, _init_result):
            args = {"query": "malaria", "date_from": "2023", "date_to": "2023", "source": "MED"}
            found = await session.call_tool("search_papers", {**args, "limit": 2})
            counted = await session.call_tool("count_papers", args)
            assert found.isError is False
            assert counted.isError is False
            assert len(found.structuredContent["result"]) == 2
            assert counted.structuredContent["hit_count"] > 2

    async def test_get_paper_citations_and_references(self):
        async with _server_session() as (session, _init_result):
            cited = await session.call_tool(
                "get_paper_citations", {"pmid": "22745249", "limit": 3}
            )
            refs = await session.call_tool(
                "get_paper_references", {"article_id": "22745249", "limit": 3}
            )
            assert cited.isError is False
            assert len(cited.structuredContent["result"]) == 3
            assert refs.isError is False
            assert refs.structuredContent["hitCount"] > 0

    async def test_invalid_date_filter_is_a_tool_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("search_papers", {"query": "x", "date_from": "soon"})
            assert result.isError is True
            assert "date_from" in result.content[0].text

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


@pytest.mark.network
class TestMCPFullTextAgainstRealEuropePMC:
    # PMC3525259: a small open-access review whose ids, sections and table are stable.
    PMCID = "PMC3525259"

    async def test_outline_then_one_section(self):
        async with _server_session() as (session, _init_result):
            outline = await session.call_tool(
                "get_paper_fulltext", {"pmcid": self.PMCID, "format": "outline"}
            )
            assert outline.isError is False
            titles = outline.structuredContent["sections_available"]
            assert "Conclusions" in titles

            part = await session.call_tool(
                "get_paper_fulltext",
                {"pmid": "16004729", "sections": ["conclusion"], "include_references": True},
            )
            data = part.structuredContent
            assert part.isError is False
            assert data["pmcid"] == self.PMCID
            assert data["content"].startswith("## Conclusions")
            assert data["truncated"] is False
            assert len(data["references"]) == data["reference_count"] > 0

    async def test_sections_format_and_truncation(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_paper_fulltext",
                {"pmcid": self.PMCID, "format": "sections", "max_chars": 3000},
            )
            data = result.structuredContent
            assert result.isError is False
            assert data["truncated"] is True
            assert data["returned_chars"] <= 3000 + 2
            first_block = data["content"][0]["content"][0]
            assert "schema_version" not in first_block

    async def test_paper_without_open_access_fails_fast_with_the_reason(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_paper_fulltext", {"pmcid": "PMC6999107"})
            assert result.isError is True
            assert "not Open Access" in result.content[0].text

    async def test_paper_figures_reuses_the_fetched_text(self):
        async with _server_session() as (session, _init_result):
            await session.call_tool("get_paper_fulltext", {"pmcid": self.PMCID})
            figures = await session.call_tool("paper_figures", {"pmcid": self.PMCID})
            assert figures.isError is False
            assert figures.structuredContent["figure_count"] >= 3


@pytest.mark.network
class TestMCPAnnotationsAgainstRealEuropePMC:
    PMID = "16004729"  # a review with several hundred text-mined mentions

    async def test_paper_annotations_are_grouped_and_capped(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_paper_annotations", {"pmid": self.PMID, "limit": 10}
            )
            data = result.structuredContent
            assert result.isError is False
            assert data["found"] is True
            assert data["annotation_count"] > data["entity_count"] > 10
            assert len(data["entities"]) == 10
            assert data["truncated"] is True
            assert data["entities"][0]["mentions"] >= data["entities"][-1]["mentions"]
            assert len(str(data)) < 20_000

    async def test_filters_and_pmcid_input(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_paper_annotations",
                {"pmcid": "PMC3525259", "annotation_type": "diseases", "section": "abstract"},
            )
            data = result.structuredContent
            assert result.isError is False
            assert data["article"]["id"] == "PMC:PMC3525259"
            assert set(data["by_type"]) <= {"Diseases"}
            assert data["entity_count"] > 0

    async def test_unknown_paper_is_not_an_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_paper_annotations", {"pmid": "99999999999"})
            assert result.isError is False
            assert result.structuredContent["found"] is False

    async def test_entity_search_pages_with_the_cursor(self):
        async with _server_session() as (session, _init_result):
            first = await session.call_tool(
                "find_papers_by_entity", {"entity": "ethanol", "limit": 2}
            )
            page1 = first.structuredContent
            assert first.isError is False
            assert page1["article_count"] == 2
            assert page1["next_cursor"]

            second = await session.call_tool(
                "find_papers_by_entity",
                {"entity": "ethanol", "limit": 2, "cursor": page1["next_cursor"]},
            )
            page2 = second.structuredContent
            assert second.isError is False
            ids1 = {a["id"] for a in page1["articles"]}
            ids2 = {a["id"] for a in page2["articles"]}
            assert ids2 and not ids1 & ids2

    async def test_entity_search_for_an_unknown_entity_is_empty(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("find_papers_by_entity", {"entity": "zzzzzz"})
            assert result.isError is False
            assert result.structuredContent["articles"] == []
            assert result.structuredContent["next_cursor"] is None
