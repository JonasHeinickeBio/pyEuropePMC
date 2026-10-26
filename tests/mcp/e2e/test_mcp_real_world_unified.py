"""Real-world test of ``unified_search`` through the real server, against live providers.

A source named in the call that the server was not configured with must be searched (it used to
be skipped without a word), and a provider that rejects us (Semantic Scholar answers HTTP 403,
DBLP serves a bot-check page) must be reported as an error with its message, not as "no results".
Providers change, so the assertions are invariants, not what a given provider answers today.
"""

from __future__ import annotations

from mcp_wire import is_error, structured, wire
import pytest
from test_mcp_e2e import _server_session

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.e2e]

SOURCES = ["europepmc", "pubmed", "openalex", "clinicaltrials", "hal", "dblp", "semantic_scholar"]


class TestUnifiedSearchAgainstSeveralRealSources:
    async def test_sources_outside_the_configured_set_are_searched_and_failures_say_why(self):
        async with _server_session() as (session, _):
            result = await session.call_tool(
                "unified_search",
                {
                    "query": "long covid fatigue",
                    "sources": SOURCES,
                    "limit": 5,
                    "diagnostics": True,
                },
            )
        assert is_error(result) is False, wire(result)
        data = structured(result)
        rows = data["sources"]
        assert set(rows) == set(SOURCES)
        assert rows["europepmc"]["status"] == "ok"
        # not just the server's default sources (Europe PMC, PubMed, arXiv)
        assert sum(row["status"] == "ok" for row in rows.values()) >= 4, rows
        for name, row in rows.items():
            if row["status"] in {"error", "rate_limited", "unavailable"}:
                assert row["error"]["message"], (name, row)  # a provider that rejects us says so
            if row["status"] == "empty":
                assert row["error"] is None, (name, row)
        for record in data["results"]:
            assert record["source"] in record["matched_sources"]
