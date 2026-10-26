"""``unified_search(diagnostics=True)`` over a real UnifiedSearch with fake source clients."""

from __future__ import annotations

import asyncio
import json

from mcp_wire import schema_of
import pytest
import requests

from pyeuropepmc.features.search import UnifiedSearch
from pyeuropepmc.mcp import server as srv
from pyeuropepmc.models.literature import LiteratureResult


def _run(coro):
    return asyncio.run(coro)


class _Source:
    def __init__(self, records=(), error=None):
        self.records, self.error = list(records), error

    def search(self, query, limit=25, sort=None):
        if self.error:
            raise self.error
        return list(self.records)


def _paper(source, ident):
    return LiteratureResult(source=source, source_id=ident, doi="10.1/x", title="One paper")


@pytest.fixture(autouse=True)
def _searcher(monkeypatch):
    response = requests.Response()
    response.status_code = 429
    searcher = UnifiedSearch(sources=["europepmc", "pubmed", "arxiv", "openalex"])
    searcher._clients = {
        "europepmc": _Source([_paper("europepmc", "1")]),
        "pubmed": _Source([_paper("pubmed", "2")]),
        "arxiv": _Source(),
        "openalex": _Source(error=requests.HTTPError("429", response=response)),
    }
    monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
    srv._unified_cache.reset()
    srv._unified_cache.set(searcher)
    yield
    srv._unified_cache.reset()


def test_diagnostics_adds_the_status_of_every_source_and_matched_sources():
    result = _run(srv.unified_search(query="fatigue", diagnostics=True))
    assert {n: row["status"] for n, row in result["sources"].items()} == {
        "europepmc": "ok",
        "pubmed": "ok",
        "arxiv": "empty",
        "openalex": "rate_limited",
    }
    assert result["sources"]["openalex"]["error"]["http_status"] == 429
    assert result["results"][0]["matched_sources"] == ["europepmc", "pubmed"]
    json.dumps(result)  # plain JSON all the way


def test_without_it_the_response_has_the_old_shape():
    result = _run(srv.unified_search(query="fatigue"))
    assert set(result) == {"results", "dedup"}
    assert "matched_sources" not in result["results"][0]


def test_the_option_is_in_the_tool_schema_and_off_by_default():
    tool = next(t for t in _run(srv.mcp.list_tools()) if t.name == "unified_search")
    prop = schema_of(tool)["properties"]["diagnostics"]
    assert prop["default"] is False and "matched_sources" in prop["description"]
