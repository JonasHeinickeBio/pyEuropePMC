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
import csv
import io
import json
import os
import re
import sys
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp_wire import hint, is_error, schema_of, structured, wire
import pytest

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.e2e]


@asynccontextmanager
async def _server_session(*, drop_env: tuple[str, ...] = ()):
    """Spawn the real server subprocess and yield an initialized (session, InitializeResult).

    ``drop_env`` names variables the subprocess must not inherit.
    """
    # stdio_client only forwards a short allow-list of variables by default. Hand over the
    # whole environment so the subprocess imports the same pyeuropepmc as the test
    # (PYTHONPATH, a worktree checkout) rather than whichever install is first on its path.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pyeuropepmc.mcp.server"],
        env={k: v for k, v in os.environ.items() if k not in drop_env},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        init_result = await client.initialize()
        yield client, init_result


class TestMCPProtocol:
    async def test_initialize_reports_server_identity(self):
        async with _server_session() as (_session, init_result):
            assert wire(init_result)["serverInfo"]["name"] == "pyeuropepmc-mcp"
            assert wire(init_result)["protocolVersion"]

    async def test_tools_list_is_non_empty_and_well_formed(self):
        async with _server_session() as (session, _init_result):
            result = await session.list_tools()
            assert len(result.tools) >= 20
            for tool in result.tools:
                assert tool.description
                assert schema_of(tool)["type"] == "object"

    async def test_unknown_tool_is_reported_as_a_tool_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("totally_unknown_tool", {})
            assert is_error(result) is True
            assert "Unknown tool" in result.content[0].text

    async def test_missing_required_argument_is_a_validation_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_paper_details", {})
            assert is_error(result) is True
            assert "At least one ID" in result.content[0].text


@pytest.mark.network
class TestMCPToolsAgainstRealEuropePMC:
    async def test_search_papers_returns_structured_results(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("search_papers", {"query": "malaria", "limit": 2})
            assert is_error(result) is False
            assert isinstance(structured(result)["result"], list)

    async def test_search_papers_stops_at_limit_for_a_broad_query(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("search_papers", {"query": "CRISPR", "limit": 3})
            assert is_error(result) is False
            assert len(structured(result)["result"]) == 3

    async def test_search_papers_filters_and_count_papers(self):
        async with _server_session() as (session, _init_result):
            args = {"query": "malaria", "date_from": "2023", "date_to": "2023", "source": "MED"}
            found = await session.call_tool("search_papers", {**args, "limit": 2})
            counted = await session.call_tool("count_papers", args)
            assert is_error(found) is False
            assert is_error(counted) is False
            assert len(structured(found)["result"]) == 2
            assert structured(counted)["hit_count"] > 2

    async def test_analyze_search_year_counts_equal_the_count_papers_total(self):
        async with _server_session() as (session, _init_result):
            args = {"query": "malaria", "date_from": "2019", "date_to": "2021", "source": "MED"}
            counted = await session.call_tool("count_papers", args)
            analysed = await session.call_tool(
                "analyze_search",
                {**args, "metrics": ["by_year", "open_access", "journals"], "limit": 5},
            )
            assert is_error(counted) is False
            assert is_error(analysed) is False
            total = structured(counted)["hit_count"]
            data = structured(analysed)
            assert data["hit_count"] == total
            assert (data["limit"], data["records_read"]) == (5, 5)

            years = data["metrics"]["by_year"]
            assert years["basis"] == "exact"
            assert [y["year"] for y in years["years"]] == [2019, 2020, 2021]
            assert sum(y["count"] for y in years["years"]) + years["undated"] == total
            assert years["undated"] == 0 and years["before"] is None

            oa = data["metrics"]["open_access"]
            assert oa["basis"] == "exact"
            assert oa["open_access"] + oa["not_open_access"] == total

            # five records of thousands: a sample, and it says so
            assert data["metrics"]["journals"]["basis"] == "sample"
            assert f"first 5 of {total}" in data["sample_note"]

    async def test_unified_search_diagnostics_report_every_source(self):
        async with _server_session() as (session, _init_result):
            args = {"query": "malaria vaccine", "sources": ["europepmc", "pubmed"], "limit": 3}
            plain = await session.call_tool("unified_search", args)
            rich = await session.call_tool("unified_search", {**args, "diagnostics": True})
            assert is_error(plain) is False and is_error(rich) is False
            assert set(structured(plain)) == {"results", "dedup"}

            data = structured(rich)
            assert set(data["sources"]) == {"europepmc", "pubmed"}
            for row in data["sources"].values():
                assert row["status"] in {"ok", "rate_limited"}, row
                assert row["query"] and row["seconds"] >= 0
            assert data["sources"]["europepmc"]["status"] == "ok"
            for record in data["results"]:
                assert record["source"] in record["matched_sources"]
                assert set(record["matched_sources"]) <= {"europepmc", "pubmed"}

    async def test_get_paper_citations_and_references(self):
        async with _server_session() as (session, _init_result):
            cited = await session.call_tool(
                "get_paper_citations", {"pmid": "22745249", "limit": 3}
            )
            refs = await session.call_tool(
                "get_paper_references", {"article_id": "22745249", "limit": 3}
            )
            assert is_error(cited) is False
            assert len(structured(cited)["result"]) == 3
            assert is_error(refs) is False
            assert structured(refs)["hitCount"] > 0

    async def test_invalid_date_filter_is_a_tool_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("search_papers", {"query": "x", "date_from": "soon"})
            assert is_error(result) is True
            assert "date_from" in result.content[0].text

    async def test_get_paper_details_round_trip(self):
        async with _server_session() as (session, _init_result):
            search_result = await session.call_tool(
                "search_papers", {"query": "malaria", "limit": 1}
            )
            papers = structured(search_result)["result"]
            if not papers:
                pytest.skip("Europe PMC returned no candidates for this query right now")

            paper_id = papers[0].get("pmid") or papers[0].get("pmcid") or papers[0].get("doi")
            if not paper_id:
                pytest.skip("Candidate paper has no usable identifier")

            details = await session.call_tool("get_paper_details", {"pmid": paper_id})
            assert is_error(details) is False
            assert isinstance(structured(details), dict)


@pytest.mark.network
class TestMCPFullTextAgainstRealEuropePMC:
    # PMC3525259: a small open-access review whose ids, sections and table are stable.
    PMCID = "PMC3525259"

    async def test_outline_then_one_section(self):
        async with _server_session() as (session, _init_result):
            outline = await session.call_tool(
                "get_paper_fulltext", {"pmcid": self.PMCID, "format": "outline"}
            )
            assert is_error(outline) is False
            titles = structured(outline)["sections_available"]
            assert "Conclusions" in titles

            part = await session.call_tool(
                "get_paper_fulltext",
                {"pmid": "16004729", "sections": ["conclusion"], "include_references": True},
            )
            data = structured(part)
            assert is_error(part) is False
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
            data = structured(result)
            assert is_error(result) is False
            assert data["truncated"] is True
            assert data["returned_chars"] <= 3000 + 2
            first_block = data["content"][0]["content"][0]
            assert "schema_version" not in first_block

    async def test_paper_without_open_access_fails_fast_with_the_reason(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_paper_fulltext", {"pmcid": "PMC6999107"})
            assert is_error(result) is True
            assert "not Open Access" in result.content[0].text

    async def test_paper_figures_reuses_the_fetched_text(self):
        async with _server_session() as (session, _init_result):
            await session.call_tool("get_paper_fulltext", {"pmcid": self.PMCID})
            figures = await session.call_tool("paper_figures", {"pmcid": self.PMCID})
            assert is_error(figures) is False
            assert structured(figures)["figure_count"] >= 3


class TestMCPResourcesAndPromptsOverStdio:
    PMCID = "PMC3525259"

    @staticmethod
    def _text(result) -> str:
        return "".join(c.get("text", "") for c in wire(result)["contents"])

    @staticmethod
    def _prompt(result) -> str:
        return "\n".join(m["content"]["text"] for m in wire(result)["messages"])

    async def test_the_paper_templates_are_listed(self):
        async with _server_session() as (session, _init_result):
            templates = wire(await session.list_resource_templates())["resourceTemplates"]
            assert {t["uriTemplate"] for t in templates} == {
                "epmc://paper/{pmcid}",
                "epmc://paper/{pmcid}/references",
                "epmc://paper/{pmcid}/outline",
            }
            assert wire(await session.list_resources())["resources"] == []

    async def test_reading_the_three_resources_matches_the_tool(self):
        async with _server_session() as (session, _init_result):
            tool = structured(await session.call_tool("get_paper_fulltext", {"pmcid": self.PMCID}))
            full = await session.read_resource(f"epmc://paper/{self.PMCID}")
            assert wire(full)["contents"][0]["mimeType"] == "text/markdown"
            text = self._text(full)
            assert text.startswith("# ") and tool["content"] in text
            assert len(text) < 31_000  # the tool's default limit holds for the resource

            outline = json.loads(
                self._text(await session.read_resource(f"epmc://paper/{self.PMCID}/outline"))
            )
            assert "Conclusions" in [s["title"] for s in outline["sections"]]

            refs_result = await session.read_resource(f"epmc://paper/{self.PMCID}/references")
            assert wire(refs_result)["contents"][0]["mimeType"] == "application/json"
            refs = json.loads(self._text(refs_result))
            assert refs["reference_count"] == tool["reference_count"] > 0
            assert refs["returned"] == len(refs["references"]) and refs["truncated"] is False

    async def test_a_paper_without_open_access_fails_with_the_tools_reason(self):
        async with _server_session() as (session, _init_result):
            with pytest.raises(Exception, match="not Open Access"):
                await session.read_resource("epmc://paper/PMC6999107")
            with pytest.raises(Exception, match="pmcid must look like"):
                await session.read_resource("epmc://paper/notanid/outline")

    async def test_the_prompts_render_with_and_without_optional_arguments(self):
        async with _server_session() as (session, _init_result):
            names = {p["name"] for p in wire(await session.list_prompts())["prompts"]}
            assert names == {"literature_review", "critical_appraisal", "citation_trace"}

            plain = self._prompt(
                await session.get_prompt("literature_review", {"topic": "long covid"})
            )
            assert "any year" in plain and "at most 20 papers" in plain
            narrowed = self._prompt(
                await session.get_prompt(
                    "literature_review",
                    {"topic": "long covid", "years": "2021-2024", "max_papers": "8"},
                )
            )
            assert (
                'date_from="2021", date_to="2024"' in narrowed and "at most 8 papers" in narrowed
            )

            appraisal = self._prompt(
                await session.get_prompt("critical_appraisal", {"pmcid": self.PMCID})
            )
            assert f'pmcid="{self.PMCID}"' in appraisal
            forward = self._prompt(
                await session.get_prompt(
                    "citation_trace", {"pmid": "22745249", "direction": "forward"}
                )
            )
            assert "get_paper_citations(" in forward and "get_paper_references(" not in forward

            with pytest.raises(Exception, match="direction must be one of"):
                await session.get_prompt("citation_trace", {"pmid": "1", "direction": "up"})

    async def test_every_tool_a_prompt_names_is_served(self):
        from pyeuropepmc.mcp import _prompts

        async with _server_session() as (session, _init_result):
            schemas = {
                t.name: set(schema_of(t)["properties"]) for t in (await session.list_tools()).tools
            }
            rendered = [
                await session.get_prompt("literature_review", {"topic": "x", "years": "2020"}),
                await session.get_prompt("critical_appraisal", {"pmcid": self.PMCID}),
                await session.get_prompt("citation_trace", {"pmid": "22745249"}),
            ]
            for result in rendered:
                calls = _prompts.tool_calls(self._prompt(result))
                assert calls
                for tool, params in calls:
                    assert tool in schemas and set(params) <= schemas[tool], (tool, params)


class TestMCPHttpAuthentication:
    """The real server on a loopback port with a token: what a network client would see."""

    TOKEN = "e2e-" + "t" * 28
    INITIALIZE = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "auth-test", "version": "0"},
        },
    }
    HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    @staticmethod
    def _free_port() -> int:
        import socket

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @pytest.fixture
    def server(self, tmp_path):
        import subprocess
        import time

        import requests

        port = self._free_port()
        token_file = tmp_path / "tokens"
        token_file.write_text(f"# rotation: old then new\n{self.TOKEN}\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYEUROPEPMC_MCP_AUTH")}
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pyeuropepmc.mcp.server",
                "--transport",
                "streamable-http",
                "--port",
                str(port),
                "--auth-token-file",
                str(token_file),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}/mcp"
        try:
            for _ in range(100):
                try:
                    requests.post(url, json={}, timeout=1)
                    break
                except requests.ConnectionError:
                    assert process.poll() is None, "the server exited"
                    time.sleep(0.2)
            yield url
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_requests_need_the_token(self, server):
        import requests

        none = requests.post(server, json=self.INITIALIZE, headers=self.HEADERS, timeout=10)
        wrong = requests.post(
            server,
            json=self.INITIALIZE,
            headers={**self.HEADERS, "Authorization": "Bearer " + "x" * 32},
            timeout=10,
        )
        assert (none.status_code, wrong.status_code) == (401, 401)
        assert none.headers["WWW-Authenticate"].startswith("Bearer")
        assert none.json()["error"] == "unauthorized"
        assert self.TOKEN not in none.text + wrong.text

        ok = requests.post(
            server,
            json=self.INITIALIZE,
            headers={**self.HEADERS, "Authorization": f"Bearer {self.TOKEN}"},
            timeout=10,
        )
        assert ok.status_code == 200
        assert "pyeuropepmc-mcp" in ok.text

    def test_a_bad_token_configuration_exits_with_a_message(self, tmp_path):
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "pyeuropepmc.mcp.server", "--transport", "streamable-http"],
            env={**os.environ, "PYEUROPEPMC_MCP_AUTH_TOKEN": "short"},
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode != 0
        assert "at least 16 characters" in result.stderr and "short" not in result.stdout


@pytest.mark.network
class TestMCPAnnotationsAgainstRealEuropePMC:
    PMID = "16004729"  # a review with several hundred text-mined mentions

    async def test_paper_annotations_are_grouped_and_capped(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_paper_annotations", {"pmid": self.PMID, "limit": 10}
            )
            data = structured(result)
            assert is_error(result) is False
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
            data = structured(result)
            assert is_error(result) is False
            assert data["article"]["id"] == "PMC:PMC3525259"
            assert set(data["by_type"]) <= {"Diseases"}
            assert data["entity_count"] > 0

    async def test_unknown_paper_is_not_an_error(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_paper_annotations", {"pmid": "99999999999"})
            assert is_error(result) is False
            assert structured(result)["found"] is False

    async def test_entity_search_pages_with_the_cursor(self):
        async with _server_session() as (session, _init_result):
            first = await session.call_tool(
                "find_papers_by_entity", {"entity": "ethanol", "limit": 2}
            )
            page1 = structured(first)
            assert is_error(first) is False
            assert page1["article_count"] == 2
            assert page1["next_cursor"]

            second = await session.call_tool(
                "find_papers_by_entity",
                {"entity": "ethanol", "limit": 2, "cursor": page1["next_cursor"]},
            )
            page2 = structured(second)
            assert is_error(second) is False
            ids1 = {a["id"] for a in page1["articles"]}
            ids2 = {a["id"] for a in page2["articles"]}
            assert ids2 and not ids1 & ids2

    async def test_entity_search_for_an_unknown_entity_is_empty(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("find_papers_by_entity", {"entity": "zzzzzz"})
            assert is_error(result) is False
            assert structured(result)["articles"] == []
            assert structured(result)["next_cursor"] is None


class TestMCPOpenAccess:
    async def test_without_an_email_the_tool_says_which_variable_to_set(self):
        async with _server_session(drop_env=("UNPAYWALL_EMAIL", "CROSSREF_EMAIL")) as (
            session,
            _init_result,
        ):
            result = await session.call_tool(
                "find_open_access", {"doi": "10.1186/1479-7364-2-2-138"}
            )
            assert is_error(result) is True
            assert "UNPAYWALL_EMAIL" in result.content[0].text

    @pytest.mark.network
    @pytest.mark.skipif(
        not (os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("CROSSREF_EMAIL")),
        reason="Unpaywall needs a contact e-mail: set UNPAYWALL_EMAIL to run this test",
    )
    async def test_open_access_paper_and_unknown_doi(self):
        async with _server_session() as (session, _init_result):
            found = await session.call_tool(
                "find_open_access", {"doi": "10.1186/1479-7364-2-2-138"}
            )
            data = structured(found)
            assert is_error(found) is False
            assert data["found"] is True
            assert data["is_oa"] is True
            assert data["best_location"]["url"]
            assert data["europepmc_fulltext"] is True

            by_pmid = await session.call_tool("find_open_access", {"pmid": "26017442"})
            assert structured(by_pmid)["doi"] == "10.1186/1479-7364-2-2-138"

            unknown = await session.call_tool(
                "find_open_access", {"doi": "10.1234/this-doi-does-not-exist-0000"}
            )
            assert is_error(unknown) is False
            assert structured(unknown)["found"] is False


@pytest.mark.network
class TestMCPBatchAgainstRealEuropePMC:
    MIXED = [
        "16004729",
        "PMC5321187",
        "10.1038/s41579-019-0296-0",
        "99999999",
        "not an id",
        "https://doi.org/10.1186/1479-7364-2-2-138",
    ]

    async def test_metadata_batch_keeps_order_and_reports_every_status(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("get_papers_batch", {"ids": self.MIXED})
            data = structured(result)
            assert is_error(result) is False
            assert [r["id"] for r in data["results"]] == self.MIXED
            assert [r["status"] for r in data["results"]] == [
                "ok",
                "ok",
                "ok",
                "not_found",
                "invalid",
                "ok",
            ]
            first, second = data["results"][0]["record"], data["results"][1]["record"]
            assert first["pmcid"] == "PMC3525259"
            assert second["pmid"] == "27534792"
            assert data["results"][5]["record"]["pmid"] == "16004729"

    async def test_a_batch_larger_than_one_chunk(self):
        async with _server_session() as (session, _init_result):
            ids = [str(31636443 + i) for i in range(60)]
            result = await session.call_tool(
                "get_papers_batch", {"ids": ids, "fields": ["pmid", "year"]}
            )
            data = structured(result)
            assert is_error(result) is False
            assert len(data["results"]) == 60
            assert data["by_status"].get("ok", 0) >= 55
            assert [r["record"]["pmid"] for r in data["results"] if r["record"]][:3] == ids[:3]

    async def test_abstracts_on_request(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_papers_batch", {"ids": ["16004729"], "fields": ["title", "abstract"]}
            )
            assert structured(result)["results"][0]["record"]["abstract"]

    async def test_fulltext_batch_reports_papers_without_open_access_and_shares_a_budget(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_papers_fulltext_batch",
                {
                    "ids": ["PMC3525259", "PMC5321187", "PMC6999107", "99999999", "16004729"],
                    "sections": ["conclusion", "results"],
                    "max_chars_per_paper": 2000,
                    "max_total_chars": 3000,
                },
            )
            data = structured(result)
            assert is_error(result) is False
            statuses = [r["status"] for r in data["results"]]
            assert statuses[0] == "ok"
            assert statuses[2] == "not_open_access"
            assert statuses[3] == "not_found"
            assert statuses[4] == "duplicate"
            assert data["total_chars_returned"] <= 3000
            assert data["total_chars_returned"] == sum(
                r.get("returned_chars", 0) for r in data["results"]
            )
            body = data["results"][0]["content"]
            assert body.startswith("##")
            assert len(body.splitlines()) > 1  # a section with text, not a bare heading


@pytest.mark.network
class TestMCPQueryToolsAgainstRealEuropePMC:
    async def test_the_linter_flags_what_europepmc_silently_accepts(self):
        """The premise of validate_query: a broken query returns numbers, not an error."""
        async with _server_session() as (session, _init_result):
            broken = "malaria AND (dengue OR zika"
            fixed = "malaria AND (dengue OR zika)"
            verdict = await session.call_tool("validate_query", {"query": broken})
            assert structured(verdict)["valid"] is False
            assert structured(verdict)["problems"][0]["code"] == "UNMATCHED_PAREN"
            ok = await session.call_tool("validate_query", {"query": fixed})
            assert structured(ok)["valid"] is True

            counts = {}
            for label, query in (("broken", broken), ("fixed", fixed)):
                result = await session.call_tool("count_papers", {"query": query})
                assert is_error(result) is False
                counts[label] = structured(result)["hit_count"]
            assert counts["broken"] != counts["fixed"]  # a different question, no error

    async def test_a_built_query_runs(self):
        async with _server_session() as (session, _init_result):
            built = await session.call_tool(
                "build_query",
                {
                    "all_of": ["heart attack"],
                    "none_of": ["rat"],
                    "date_from": "2020",
                    "date_to": "2021-12-31",
                    "open_access": True,
                    "source": "MED",
                },
            )
            assert is_error(built) is False
            query = structured(built)["query"]
            counted = await session.call_tool("count_papers", {"query": query})
            assert is_error(counted) is False
            assert structured(counted)["hit_count"] > 100

    async def test_evaluate_query_scores_against_known_papers(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "evaluate_query",
                {
                    "query": '"dual-RNA" AND endonuclease',
                    "included_pmids": ["22745249", "16004729"],
                    "excluded_pmids": ["31636443"],
                },
            )
            data = structured(result)
            assert is_error(result) is False
            assert data["included"]["matched"] == 1
            assert data["included"]["missed"] == ["16004729"]
            assert data["included"]["recall"] == 0.5
            assert data["excluded"]["matched"] == 0
            assert data["total_hits"] > 0

    async def test_translate_query_for_pubmed(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "translate_query",
                {"query": "TITLE:crispr AND PUB_YEAR:[2020 TO 2022] AND SRC:MED"},
            )
            assert is_error(result) is False
            assert structured(result)["query"] == "crispr[ti] AND 2020:2022[dp]"
            assert structured(result)["exact"] is True


@pytest.mark.network
class TestMCPStatusAgainstRealEuropePMC:
    async def test_the_status_probe_answers_and_is_kept(self):
        async with _server_session() as (session, _init_result):
            first = await session.call_tool("epmc_status", {})
            data = structured(first)
            assert is_error(first) is False
            # whatever state Europe PMC is in, the answer has this shape
            assert data["status"] in {"ok", "degraded", "down", "unknown"}
            assert set(data["endpoints"]) == {"search", "fulltext", "citations", "annotations"}
            for endpoint in data["endpoints"].values():
                assert endpoint["verdict"] in {"ok", "error", "unreachable", "unexpected"}
                assert endpoint["ms"] >= 0
            assert data["cached"] is False
            assert "ebi.ac.uk" not in str(data)  # no URLs

            second = await session.call_tool("epmc_status", {})
            assert structured(second)["cached"] is True
            assert structured(second)["checked_at"] == data["checked_at"]

    async def test_cache_status_counts_a_cached_search_and_clear_cache_empties_it(self):
        async with _server_session() as (session, _init_result):
            before = await session.call_tool("cache_status", {})
            assert structured(before)["search"] == {"created": False, "entries": 0}

            await session.call_tool("count_papers", {"query": "malaria AND dengue"})
            await session.call_tool("count_papers", {"query": "malaria AND dengue"})
            during = structured(await session.call_tool("cache_status", {}))["search"]
            assert during["created"] is True
            assert during["entries"] >= 1
            assert during["hits"] >= 1  # the second call was served from the cache
            assert "malaria" not in str(during)

            cleared = await session.call_tool("clear_cache", {"scope": "search"})
            assert is_error(cleared) is False
            assert structured(cleared)["results"]["search"]["cleared"] is True
            after = structured(await session.call_tool("cache_status", {}))["search"]
            assert after["entries"] == 0

    async def test_clear_cache_is_declared_as_changing_state(self):
        async with _server_session() as (session, _init_result):
            tools = {t.name: t for t in (await session.list_tools()).tools}
            assert hint(tools["clear_cache"].annotations, "readOnlyHint") is False
            assert hint(tools["epmc_status"].annotations, "readOnlyHint") is True


@pytest.mark.network
class TestMCPExportAgainstRealEuropePMC:
    IDS = ["16004729", "PMC5321187", "10.1038/s41579-019-0296-0", "99999999", "bad id"]

    async def test_bibtex_for_known_papers_keeps_order_and_names_what_is_missing(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "export_papers", {"ids": self.IDS, "format": "bibtex"}
            )
            data = structured(result)
            assert is_error(result) is False
            assert data["exported"] == 3
            assert [e["status"] for e in data["skipped"]] == ["not_found", "invalid"]
            keys = re.findall(r"@article\{(\w+),", data["content"])
            assert keys[0] == "vasiliou2005analysis"
            assert len(set(keys)) == len(keys) == 3
            assert "pmid = {16004729}" in data["content"]

    async def test_every_format_for_a_query_and_the_next_part(self):
        async with _server_session() as (session, _init_result):
            query = "malaria AND TITLE:vaccine"
            first = await session.call_tool(
                "export_papers", {"query": query, "format": "csv", "limit": 3}
            )
            data = structured(first)
            assert is_error(first) is False
            assert data["exported"] == 3
            assert data["total_hits"] > 3
            assert data["next_skip"] == 3
            assert len(list(csv.reader(io.StringIO(data["content"])))) == 4

            second = await session.call_tool(
                "export_papers", {"query": query, "format": "csv", "limit": 3, "skip": 3}
            )
            ids_first = {row[0] for row in csv.reader(io.StringIO(data["content"]))}
            second_rows = csv.reader(io.StringIO(structured(second)["content"]))
            assert not (ids_first - {"id"}) & {row[0] for row in second_rows}

            for fmt in ("ris", "csl-json", "json", "markdown", "bibtex"):
                result = await session.call_tool(
                    "export_papers", {"query": query, "format": fmt, "limit": 2}
                )
                assert is_error(result) is False, fmt
                assert structured(result)["exported"] == 2, fmt

    async def test_a_ris_export_has_start_and_end_pages_and_the_bibtex_reads_back(self):
        async with _server_session() as (session, _init_result):
            ris = await session.call_tool("export_papers", {"ids": ["16004729"], "format": "ris"})
            text = structured(ris)["content"]
            assert "SP  - 138" in text and "EP  - 143" in text
            assert text.rstrip().endswith("ER  -")

            bib = await session.call_tool(
                "export_papers", {"ids": ["33069326"], "format": "bibtex"}
            )
            # the consortium name stays one author despite the "and" in it
            expected = "author = {{GBD 2019 Diseases and Injuries Collaborators}}"
            assert expected in structured(bib)["content"]


@pytest.mark.network
class TestMCPLinksAgainstRealEuropePMC:
    async def test_data_links_of_a_paper_with_text_mined_snps(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_paper_data_links", {"pmid": "32257953", "category": "SNPs", "limit": 5}
            )
            data = structured(result)
            assert is_error(result) is False
            assert data["article"] == {"source": "MED", "id": "32257953"}
            assert data["matching"] >= 10
            assert len(data["links"]) == 5 and data["truncated"] is True
            snp = data["links"][0]
            assert snp["scheme"] == "dbSNP" and snp["id"].startswith("rs")
            assert snp["origin"] == "text_mined" and snp["kind"] == "supporting_data"
            assert snp["url"].startswith("http")

    async def test_a_doi_resolves_to_the_same_links_as_its_pmid(self):
        async with _server_session() as (session, _init_result):
            by_doi = await session.call_tool(
                "get_paper_data_links", {"doi": "10.1038/s41586-021-03583-3"}
            )
            assert is_error(by_doi) is False
            assert structured(by_doi)["article"]["id"] == "34040261"

    async def test_lab_links_with_a_provider_filter(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "get_paper_lab_links", {"pmcid": "PMC3257301", "provider": "genome"}
            )
            data = structured(result)
            assert is_error(result) is False
            assert [p["provider"] for p in data["providers"]] == ["Saccharomyces Genome Database"]
            url = urlparse(data["providers"][0]["links"][0]["url"])
            assert url.scheme == "https" and url.hostname == "www.yeastgenome.org"
            assert len(data["available_providers"]) >= 3

    async def test_a_paper_without_links_and_a_bad_identifier(self):
        async with _server_session() as (session, _init_result):
            none = await session.call_tool("get_paper_data_links", {"pmid": "25883711"})
            assert is_error(none) is False
            assert structured(none)["links"] == []
            bad = await session.call_tool("get_paper_lab_links", {"pmid": "abc"})
            assert is_error(bad) is True


@pytest.mark.network
class TestMCPEnrichAgainstRealSources:
    async def test_a_well_known_paper_has_europe_pmc_and_another_source(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "enrich_paper", {"doi": "10.1038/nature14539", "time_budget": 120}
            )
            data = structured(result)
            assert is_error(result) is False
            assert data["found"] is True
            assert data["article"]["pmid"] == "26017442"
            assert data["article"]["title"].lower().startswith("deep learning")
            status = {name: entry["status"] for name, entry in data["sources"].items()}
            assert status["europepmc"] == "ok"
            assert {status["crossref"], status["icite"]} & {"ok"}
            assert set(status.values()) <= {"ok", "empty", "error", "timeout", "unavailable"}
            assert data["impact"]["citation_count"] > 10_000
            assert len(json.dumps(data)) < 15_000

    async def test_a_retracted_paper_says_so(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "enrich_paper",
                {
                    "pmid": "9500320",
                    "include": ["updates"],
                    "sources": ["crossref"],
                    "time_budget": 60,
                },
            )
            data = structured(result)
            assert is_error(result) is False
            assert set(data) >= {"article", "updates", "sources"}
            assert "impact" not in data
            assert data["updates"]["is_retracted"] is True
            assert {u["from"] for u in data["updates"]["updates"]} >= {"crossref", "europepmc"}
            assert set(data["sources"]) == {"europepmc", "crossref"}

    async def test_a_bad_identifier_is_refused_before_any_request(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("enrich_paper", {"pmid": "abc"})
            assert is_error(result) is True


@pytest.mark.network
class TestMCPPicoAndMeshAgainstRealServices:
    QUESTION = (
        "In adults with type 2 diabetes, does metformin reduce cardiovascular mortality "
        "compared with placebo?"
    )

    async def test_the_generated_query_finds_papers(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("pico_decompose", {"question": self.QUESTION})
            data = structured(result)
            assert is_error(result) is False
            assert data["complete"] is True and data["missing"] == []
            assert data["elements"]["intervention"]["text"] == "metformin"
            assert data["query_check"]["valid"] is True

            counted = await session.call_tool("count_papers", {"query": data["query"]})
            assert structured(counted)["hit_count"] > 1000

    async def test_the_mesh_expanded_query_finds_papers(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "pico_decompose", {"question": self.QUESTION, "mesh": True}
            )
            data = structured(result)
            assert 'MESH:"Diabetes Mellitus, Type 2"' in data["query"]
            counted = await session.call_tool("count_papers", {"query": data["query"]})
            assert structured(counted)["hit_count"] > 1000

    async def test_an_incomplete_question_makes_no_request_and_no_query(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "pico_decompose", {"question": "What is the best programming language?"}
            )
            data = structured(result)
            assert data["complete"] is False and data["query"] == ""
            assert data["missing"] == ["population", "intervention", "outcome"]

    async def test_offline_mesh_fragments_find_papers(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool("mesh_expand", {"terms": ["heart attack", "aspirin"]})
            data = structured(result)
            assert data["source"] == "snapshot" and data["unmatched"] == []
            assert data["query_check"]["valid"] is True
            counted = await session.call_tool("count_papers", {"query": data["query"]})
            assert structured(counted)["hit_count"] > 1000

    async def test_the_nlm_service_covers_a_heading_the_snapshot_lacks(self):
        async with _server_session() as (session, _init_result):
            result = await session.call_tool(
                "mesh_expand", {"terms": ["Sarcoidosis", "heart attack"], "use_api": True}
            )
            data = structured(result)
            assert is_error(result) is False and data["source"] == "nlm"
            sarcoidosis, heart_attack = data["terms"]
            assert sarcoidosis["matched"] is True
            assert sarcoidosis["descriptor"]["ui"] == "D012507"
            assert any(t.startswith("C") for t in sarcoidosis["descriptor"]["tree_numbers"])
            assert heart_attack["descriptor"]["heading"] == "Myocardial Infarction"


@pytest.mark.network
class TestMCPSentenceRolesAgainstARealPaper:
    PMCID = (
        "PMC8658482"  # Efficacy of Exercise on Postneedling Soreness: a randomized trial (CC BY)
    )

    async def test_methods_and_results_are_returned_and_the_roles_filter_works(self):
        async with _server_session() as (session, _init_result):
            everything = await session.call_tool(
                "tag_paper_sentences", {"pmcid": self.PMCID, "max_chars": 200000}
            )
            data = structured(everything)
            assert is_error(everything) is False
            assert data["pmcid"] == self.PMCID and data["method"] == "rules"
            roles = data["roles"]
            assert len(roles["method"]) >= 20 and len(roles["result"]) >= 10
            assert {"background", "conclusion"} <= set(roles)
            assert data["statistics"]["sentences"] > 100 and data["truncated"] is False
            assert all("Materials and Methods" in m["section"] for m in roles["method"][:10])
            assert any("randomized" in m["text"].lower() for m in roles["method"])
            assert any("p <" in r["text"] or "p =" in r["text"] for r in roles["result"])
            # administrative sections and the reference list are not tagged
            joined = " ".join(s["text"] for group in roles.values() for s in group)
            assert "Informed consent was obtained from all subjects" not in joined

            only = await session.call_tool(
                "tag_paper_sentences", {"pmcid": self.PMCID, "roles": ["limitation", "conclusion"]}
            )
            filtered = structured(only)
            assert set(filtered["roles"]) <= {"limitation", "conclusion"} and filtered["roles"]
            assert filtered["statistics"] == data["statistics"]  # counts cover the whole body

            section = await session.call_tool(
                "tag_paper_sentences",
                {"pmcid": self.PMCID, "sections": ["Methods"], "roles": ["method"]},
            )
            assert {
                x["section"].split("/")[0] for x in structured(section)["roles"]["method"]
            } == {"2. Materials and Methods"}

    async def test_truncation_and_a_paper_that_is_not_open_access(self):
        async with _server_session() as (session, _init_result):
            short = await session.call_tool(
                "tag_paper_sentences", {"pmcid": self.PMCID, "max_chars": 1000}
            )
            data = structured(short)
            assert data["truncated"] is True and data["returned_chars"] <= 1000 + 400
            closed = await session.call_tool("tag_paper_sentences", {"pmid": "26017442"})
            assert is_error(closed) is True
