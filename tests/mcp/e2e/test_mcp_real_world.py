"""Real-world tests of the MCP server: the live Europe PMC and a real client, nothing faked.

The unit tests prove the logic on small fixed records; these check the claims that only a real
service can contradict. Each one came from running the released server against the real thing:

* ``analyze_search`` says a count is ``exact``: it is compared with independent counts;
* Europe PMC holds records dated in 2096: the year window must still end this year;
* the paper resources must give the tool's text and the tool's errors on real articles;
* the bearer token must be enforced on a real HTTP socket, in the way a client sends it.

Providers change, so the assertions are invariants (sums, equalities, ranges), not today's data.
"""

from __future__ import annotations

import datetime
import json
import os
import socket
import subprocess
import sys
import time

from mcp_wire import is_error, structured, wire
import pytest
import requests
from test_mcp_e2e import _server_session

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.e2e]

QUERY = '"chronic fatigue syndrome"'
THIS_YEAR = datetime.date.today().year


async def _call(session, tool: str, args: dict):
    result = await session.call_tool(tool, args)
    assert is_error(result) is False, wire(result)
    return structured(result)


class TestAnalyzeSearchAgainstTheLiveService:
    pytest.importorskip("pandas")

    async def test_every_exact_number_equals_an_independent_count(self):
        window = {"date_from": "2015", "date_to": "2024", "source": "MED"}
        async with _server_session() as (session, _):
            data = await _call(
                session,
                "analyze_search",
                {
                    "query": QUERY,
                    "metrics": ["by_year", "open_access", "citations"],
                    "limit": 50,
                    **window,
                },
            )
            metrics = data["metrics"]
            by_year = metrics["by_year"]
            assert by_year["basis"] == "exact" and by_year["before"] is None
            assert [y["year"] for y in by_year["years"]] == list(range(2015, 2025))
            assert (
                sum(y["count"] for y in by_year["years"]) + by_year["undated"] == data["hit_count"]
            )

            for year in by_year["years"]:  # each year against count_papers
                one = await _call(
                    session,
                    "count_papers",
                    {
                        "query": QUERY,
                        "date_from": str(year["year"]),
                        "date_to": str(year["year"]),
                        "source": "MED",
                    },
                )
                assert one["hit_count"] == year["count"], year

            oa = await _call(
                session, "count_papers", {"query": QUERY, "open_access": True, **window}
            )
            assert metrics["open_access"]["open_access"] == oa["hit_count"]

            thresholds = metrics["citations"]["thresholds"]
            for n in (10, 100):
                cited = await _call(
                    session,
                    "count_papers",
                    {"query": f"({QUERY}) AND CITED:[{n} TO *]", **window},
                )
                assert thresholds["at_least"][str(n)] == cited["hit_count"], n

            assert metrics["citations"]["basis"] == "sample"
            assert f"first 50 of {data['hit_count']}" in data["sample_note"]

    async def test_records_dated_in_the_future_do_not_swallow_the_year_window(self):
        """Live, a search for 'cancer' had records dated 2096 and the 60-year window ended there,
        so 5.6 million records fell into one 'before' bucket."""
        started = time.monotonic()
        async with _server_session() as (session, _):
            data = await _call(
                session, "analyze_search", {"query": "cancer", "metrics": ["by_year"]}
            )
        by_year = data["metrics"]["by_year"]
        years = [y["year"] for y in by_year["years"]]
        assert max(years) <= THIS_YEAR and THIS_YEAR - max(years) <= 1
        assert len(years) >= 50, "the window should cover the years anyone publishes in"
        in_window = sum(y["count"] for y in by_year["years"])
        assert in_window > 0.9 * data["hit_count"], by_year
        after = by_year["after"]
        assert after is None or after["year"] == THIS_YEAR + 1
        parts = (
            in_window
            + (by_year["before"] or {"count": 0})["count"]
            + (after or {"count": 0})["count"]
        )
        assert parts + by_year["undated"] == data["hit_count"]
        assert time.monotonic() - started < 120

    async def test_a_limit_that_covers_the_result_makes_every_metric_exact(self):
        small = 'TITLE:"dual-RNA" AND TITLE:endonuclease'
        async with _server_session() as (session, _):
            data = await _call(session, "analyze_search", {"query": small, "limit": 100})
            assert 0 < data["hit_count"] <= 100 and data["records_read"] == data["hit_count"]
            assert {m["basis"] for m in data["metrics"].values()} == {"exact"}
            records = await _call(
                session, "search_papers", {"query": small, "limit": 100, "result_type": "core"}
            )
            cited = [r.get("citedByCount", 0) for r in records["result"]]
            assert data["metrics"]["citations"]["statistics"]["max_citations"] == max(cited)

    async def test_a_query_with_no_hits_answers_instead_of_failing(self):
        async with _server_session() as (session, _):
            data = await _call(session, "analyze_search", {"query": "zzzqqqxxxnotaword12345"})
            assert data["hit_count"] == 0 and data["records_read"] == 0
            assert data["metrics"]["by_year"]["years"] == []

    async def test_a_default_call_works_without_the_analytics_extra(self):
        """A plain ``uvx pyeuropepmc mcp`` has no pandas; the default call must still answer."""
        async with _server_session(drop_env=()) as (session, _):
            args = {"query": QUERY, "date_from": "2023", "date_to": "2023"}
            data = await _call(session, "analyze_search", {**args, "limit": 5})
            assert data["metrics"]["by_year"]["basis"] == "exact"  # whatever else is installed


class TestPaperResourcesOnRealArticles:
    OPEN = "PMC3525259"  # small open-access review: sections, a table, 37 references
    LONG = "PMC8658482"  # a research article longer than the default limit
    CLOSED = "PMC6999107"  # not open access

    @staticmethod
    def _text(result) -> str:
        return "".join(c.get("text", "") for c in wire(result)["contents"])

    async def test_the_three_resources_agree_with_the_tool(self):
        async with _server_session() as (session, _):
            tool = await _call(session, "get_paper_fulltext", {"pmcid": self.OPEN})
            text = self._text(await session.read_resource(f"epmc://paper/{self.OPEN}"))
            assert text.startswith("# ") and tool["content"] in text

            outline = json.loads(
                self._text(await session.read_resource(f"epmc://paper/{self.OPEN}/outline"))
            )
            assert {s["title"] for s in outline["sections"]} >= {"Introduction", "Conclusions"}
            assert all(s["chars"] > 0 for s in outline["sections"])

            refs = json.loads(
                self._text(await session.read_resource(f"epmc://paper/{self.OPEN}/references"))
            )
            assert refs["reference_count"] == tool["reference_count"] > 20
            assert refs["returned"] == len(refs["references"]) and refs["truncated"] is False
            assert any(r.get("doi") or r.get("pmid") for r in refs["references"])

    async def test_a_long_article_is_cut_like_the_tool_and_says_how_to_get_the_rest(self):
        async with _server_session() as (session, _):
            text = self._text(await session.read_resource(f"epmc://paper/{self.LONG}"))
            tool = await _call(session, "get_paper_fulltext", {"pmcid": self.LONG})
            assert tool["truncated"] is True and len(text) < 31_000
            assert f"Shown {tool['returned_chars']} of {tool['total_chars']} characters" in text
            assert f'get_paper_fulltext(pmcid="{self.LONG}", sections=' in text

    async def test_failures_arrive_with_the_tools_own_reason(self):
        async with _server_session() as (session, _):
            for suffix in ("", "/outline", "/references"):
                with pytest.raises(Exception, match="not Open Access"):
                    await session.read_resource(f"epmc://paper/{self.CLOSED}{suffix}")
            with pytest.raises(Exception, match="No Europe PMC record found"):
                await session.read_resource("epmc://paper/PMC99999999")
            with pytest.raises(Exception, match="pmcid must look like"):
                await session.read_resource("epmc://paper/not-an-id")


class TestTheBearerTokenOnARealSocket:
    TOKEN = "realworld-" + "t" * 30
    INIT = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "real-world", "version": "0"},
        },
    }
    HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    @staticmethod
    def _port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _json(response: requests.Response) -> dict:
        body = response.text
        if "data:" in body:  # server-sent event framing
            body = "".join(line[5:] for line in body.splitlines() if line.startswith("data:"))
        return json.loads(body)

    @pytest.fixture
    def server(self):
        port = self._port()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pyeuropepmc.mcp.server",
                "--transport",
                "streamable-http",
                "--port",
                str(port),
            ],
            env={**os.environ, "PYEUROPEPMC_MCP_AUTH_TOKEN": self.TOKEN},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}/mcp"
        try:
            for _ in range(150):
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

    def test_a_client_with_the_token_can_run_a_real_tool_and_one_without_cannot(self, server):
        auth = {**self.HEADERS, "Authorization": f"Bearer {self.TOKEN}"}
        for headers in (self.HEADERS, {**self.HEADERS, "Authorization": "Bearer " + "x" * 40}):
            denied = requests.post(server, json=self.INIT, headers=headers, timeout=20)
            assert denied.status_code == 401 and "unauthorized" in denied.text

        opened = requests.post(server, json=self.INIT, headers=auth, timeout=60)
        assert opened.status_code == 200
        session_headers = {**auth, "Mcp-Session-Id": opened.headers["Mcp-Session-Id"]}
        requests.post(
            server,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=session_headers,
            timeout=20,
        )
        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "count_papers",
                "arguments": {"query": "malaria", "date_from": "2024", "date_to": "2024"},
            },
        }
        answered = requests.post(server, json=call, headers=session_headers, timeout=60)
        assert answered.status_code == 200
        result = self._json(answered)["result"]
        assert result.get("isError") in (None, False)
        assert json.loads(result["content"][0]["text"])["hit_count"] > 1000

        # the session id alone is not enough: the token is checked on every request
        stolen = {k: v for k, v in session_headers.items() if k != "Authorization"}
        assert requests.post(server, json=call, headers=stolen, timeout=20).status_code == 401
