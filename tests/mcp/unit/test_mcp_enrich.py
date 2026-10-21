"""Unit tests for the ``enrich_paper`` MCP tool and its shaping helpers.

``tests/fixtures/enrich`` holds real ``PaperEnricher`` results (Wakefield et al. 1998, a
retracted paper with funders absent and a retraction notice, and LeCun et al. 2015 with
Semantic Scholar failing), with the large raw OpenAlex and Semantic Scholar bodies removed.
The enricher's clients are fakes; nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
import threading
from typing import Any
from unittest.mock import MagicMock

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from pyeuropepmc.features.enrich import EnrichmentConfig, PaperEnricher
from pyeuropepmc.mcp import _enrich as en, server as srv

FIXTURES = Path(__file__).parents[2] / "fixtures" / "enrich"
RETRACTED = json.loads((FIXTURES / "results_pmid_9500320.json").read_text(encoding="utf-8"))
LECUN = json.loads((FIXTURES / "results_nature14539.json").read_text(encoding="utf-8"))
SOURCES = ("crossref", "openalex", "semantic_scholar", "icite")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset():
    srv._enricher_cache.reset()
    yield
    srv._enricher_cache.reset()


def _mock_enricher(results: dict[str, Any], clients=SOURCES + ("europepmc",)) -> MagicMock:
    enricher = MagicMock()
    enricher.clients = {name: object() for name in clients}
    enricher.enrich_paper.return_value = copy.deepcopy(results)
    srv._enricher_cache.set(enricher)
    return enricher


class TestValidateChoice:
    def test_default_is_everything(self):
        assert en.validate_choice(None, en.GROUPS, "field group") == en.GROUPS
        assert en.validate_choice([], en.GROUPS, "field group") == en.GROUPS

    def test_order_follows_the_valid_list_and_names_are_forgiving(self):
        assert en.validate_choice([" Updates", "impact"], en.GROUPS, "g") == ("impact", "updates")
        assert en.validate_choice(["semantic-scholar"], en.SOURCES, "s") == ("semantic_scholar",)

    def test_unknown_name_lists_the_valid_ones(self):
        with pytest.raises(ValueError, match=r"unknown source \['bing'\].*crossref"):
            en.validate_choice(["bing", "crossref"], en.SOURCES, "source")


class TestShape:
    def test_a_retracted_paper(self):
        record = en.shape(RETRACTED)
        assert record["article"]["pmid"] == "9500320"
        assert record["article"]["doi"] == "10.1016/s0140-6736(97)11096-0"
        assert "Retracted Publication" in record["article"]["publication_type"]
        assert record["updates"]["is_retracted"] is True
        notices = {(u["from"], u["type"]) for u in record["updates"]["updates"]}
        assert ("crossref", "retraction") in notices
        assert ("europepmc", "Retraction in") in notices
        assert record["impact"]["citation_count"] > 1000
        assert {c["source"] for c in record["impact"]["citation_counts"]} >= {"europepmc", "icite"}
        assert record["impact"]["relative_citation_ratio"] > 1
        assert record["oa"]["is_oa"] in (True, False)

    def test_authors_carry_institutions(self):
        authors = en.shape(RETRACTED)["affiliations"]["authors"]
        assert authors[0]["name"]
        assert any(a["institutions"] for a in authors)
        institution = next(i for a in authors for i in a["institutions"])
        assert set(institution) == {"name", "country", "ror"}

    def test_include_keeps_only_the_asked_groups(self):
        record = en.shape(LECUN, ("impact", "oa"))
        assert set(record) == {"article", "impact", "oa"}

    def test_a_paper_without_funding_has_empty_lists(self):
        assert en.shape(LECUN, ("funding",))["funding"] == {"funders": [], "grants": []}

    @pytest.mark.parametrize("results", [LECUN, RETRACTED])
    def test_the_whole_record_is_compact(self, results):
        assert len(json.dumps(en.shape(results))) < 15_000

    def test_long_lists_are_cut_and_say_so(self):
        merged = {
            "authors": [{"name": f"A{i}", "affiliations": ["x"] * 9} for i in range(100)],
            "funding": [{"name": f"F{i}", "award": ["a"] * 20} for i in range(50)],
            "updates": [{"type": "correction"}] * 50,
            "topics": [{"display_name": f"T{i}", "score": 1} for i in range(20)],
            "full_text_urls": [f"https://x/{i}" for i in range(20)],
        }
        record = en.shape({"merged": merged})
        assert record["affiliations"]["author_count"] == 100
        assert len(record["affiliations"]["authors"]) == en.MAX_AUTHORS
        assert record["affiliations"]["authors_truncated"] is True
        assert len(record["affiliations"]["authors"][0]["affiliations"]) == en.MAX_PER_AUTHOR
        assert len(record["funding"]["funders"]) == en.MAX_FUNDING
        assert len(record["funding"]["funders"][0]["awards"]) == en.MAX_AWARDS
        assert len(record["updates"]["updates"]) == en.MAX_UPDATES
        assert record["updates"]["updates_truncated"] is True
        assert len(record["impact"]["topics"]) == en.MAX_TOPICS
        assert len(record["oa"]["full_text_urls"]) == en.MAX_URLS

    @pytest.mark.parametrize("merged", [{}, {"authors": None, "funding": "x", "updates": [1]}])
    def test_odd_or_empty_records_do_not_raise(self, merged):
        record = en.shape({"merged": merged})
        assert set(record) == {"article", *en.GROUPS}


class TestSourceReport:
    def test_statuses_pass_through_and_missing_sources_are_unavailable(self):
        results = {
            "source_status": {
                "europepmc": {"status": "ok", "seconds": 1.0},
                "crossref": {"status": "error", "error": "X: boom"},
                "openalex": {"status": "timeout", "seconds": 30.0},
            }
        }
        report = en.source_report(
            results, ("crossref", "openalex", "unpaywall"), {"europepmc", "crossref", "openalex"}
        )
        assert report["crossref"] == {"status": "error", "error": "X: boom"}
        assert report["openalex"]["status"] == "timeout"
        assert report["unpaywall"]["status"] == "unavailable"
        assert "UNPAYWALL_EMAIL" in report["unpaywall"]["reason"]
        assert en.completeness(report) is False

    def test_complete_means_every_source_answered(self):
        results = {"source_status": {"europepmc": {"status": "ok"}, "icite": {"status": "empty"}}}
        assert en.completeness(en.source_report(results, ("icite",), {"europepmc", "icite"}))


class TestEnrichPaperTool:
    def test_full_result(self):
        enricher = _mock_enricher(RETRACTED)
        result = _run(srv.enrich_paper(pmid="9500320"))
        assert result["found"] is True and result["complete"] is True
        assert set(result) >= {"article", *en.GROUPS, "sources", "time_budget_seconds"}
        assert set(result["sources"]) == {"europepmc", *SOURCES}
        assert result["updates"]["is_retracted"] is True
        args, kwargs = enricher.enrich_paper.call_args
        assert args == ("9500320",)
        assert kwargs["only_sources"] == ("europepmc", *SOURCES)
        assert kwargs["time_budget"] == 30

    def test_partial_result_names_the_failed_source(self):
        _mock_enricher(LECUN)
        result = _run(srv.enrich_paper(doi="https://doi.org/10.1038/nature14539"))
        assert result["found"] is True and result["complete"] is False
        assert result["sources"]["semantic_scholar"]["status"] == "error"
        assert "not found" in result["sources"]["semantic_scholar"]["error"]
        assert result["sources"]["crossref"]["status"] == "ok"
        assert result["impact"]["citation_count"]

    def test_timeout_is_reported_not_raised(self):
        results = copy.deepcopy(RETRACTED)
        results["source_status"]["openalex"] = {"status": "timeout", "seconds": 30.0}
        _mock_enricher(results)
        result = _run(srv.enrich_paper(pmid="9500320", time_budget=30))
        assert result["sources"]["openalex"] == {"status": "timeout", "seconds": 30.0}
        assert result["complete"] is False and result["found"] is True

    def test_all_sources_failing_is_an_answer_not_an_error(self):
        failed = {
            "identifier": "1",
            "doi": None,
            "pmid": "1",
            "sources": [],
            "merged": {},
            "source_status": {
                name: {"status": "error", "error": "ConnectionError: down"}
                for name in ("europepmc", *SOURCES)
            },
        }
        _mock_enricher(failed)
        result = _run(srv.enrich_paper(pmid="1"))
        assert result["found"] is False and result["complete"] is False
        assert all(s["status"] == "error" for s in result["sources"].values())
        assert result["impact"]["citation_count"] is None

    def test_include_and_sources_filter(self):
        enricher = _mock_enricher(RETRACTED)
        result = _run(
            srv.enrich_paper(pmid="9500320", include=["updates"], sources=["crossref", "icite"])
        )
        assert set(result) >= {"article", "updates"}
        assert not {"impact", "funding", "affiliations", "oa"} & set(result)
        assert enricher.enrich_paper.call_args.kwargs["only_sources"] == (
            "europepmc",
            "crossref",
            "icite",
        )
        assert set(result["sources"]) == {"europepmc", "crossref", "icite"}

    def test_a_source_the_server_cannot_start_is_unavailable(self):
        _mock_enricher(RETRACTED, clients=("europepmc", "crossref", "openalex", "icite"))
        result = _run(srv.enrich_paper(pmid="9500320"))
        assert result["sources"]["semantic_scholar"]["status"] == "unavailable"
        assert "semanticscholar" in result["sources"]["semantic_scholar"]["reason"]

    def test_unpaywall_is_a_default_only_with_an_email(self):
        enricher = _mock_enricher(RETRACTED, clients=("europepmc", *SOURCES, "unpaywall"))
        _run(srv.enrich_paper(pmid="9500320"))
        assert "unpaywall" in enricher.enrich_paper.call_args.kwargs["only_sources"]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"pmid": "abc"},
            {"pmcid": "xyz"},
            {"doi": "not a doi"},
            {"pmid": "1", "include": ["wealth"]},
            {"pmid": "1", "sources": ["bing"]},
        ],
    )
    def test_bad_input_never_reaches_the_enricher(self, kwargs):
        enricher = _mock_enricher(RETRACTED)
        with pytest.raises(ToolError):
            _run(srv.enrich_paper(**kwargs))
        enricher.enrich_paper.assert_not_called()

    def test_identifier_forms(self):
        enricher = _mock_enricher(RETRACTED)
        _run(srv.enrich_paper(pmcid="pmc1234567"))
        _run(srv.enrich_paper(doi="doi:10.1038/NATURE14539"))
        calls = [c.args[0] for c in enricher.enrich_paper.call_args_list]
        assert calls == ["PMC1234567", "10.1038/NATURE14539"]


class FakeSource:
    def __init__(self, data=None, wait: threading.Event | None = None, error=None):
        self.data, self.wait, self.error = data, wait, error

    def enrich(self, identifier, **kwargs):
        if self.wait is not None:
            self.wait.wait(timeout=10)
        if self.error:
            raise self.error
        return self.data

    def close(self):
        pass


def _real_enricher(**clients) -> PaperEnricher:
    enricher = PaperEnricher(EnrichmentConfig(enable_ror=False))
    enricher.close()
    enricher.clients = dict(clients)
    enricher._resolve_ids = lambda ident: {"doi": "10.1/x", "pmid": "9", "pmcid": None}
    return enricher


class TestWithARealEnricher:
    """The tool and the library together, with fake source clients."""

    def test_nothing_is_written_and_no_directory_is_passed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        enricher = _real_enricher(
            europepmc=FakeSource(RETRACTED["europepmc"]),
            crossref=FakeSource(RETRACTED["crossref"]),
        )
        spy = MagicMock(wraps=enricher.enrich_paper)
        enricher.enrich_paper = spy  # type: ignore[method-assign]
        srv._enricher_cache.set(enricher)
        result = _run(srv.enrich_paper(pmid="9500320", sources=["crossref"]))
        assert result["updates"]["is_retracted"] is True
        assert list(tmp_path.iterdir()) == []
        assert spy.call_args.kwargs["save_responses"] is False
        assert "save_dir" not in spy.call_args.kwargs

    def test_a_hanging_source_is_cut_off_at_the_budget(self):
        release = threading.Event()
        enricher = _real_enricher(
            europepmc=FakeSource(RETRACTED["europepmc"]),
            crossref=FakeSource(RETRACTED["crossref"]),
            openalex=FakeSource({"source": "openalex"}, wait=release),
            icite=FakeSource(error=RuntimeError("HTTP 429")),
        )
        srv._enricher_cache.set(enricher)
        try:
            result = _run(srv.enrich_paper(pmid="9500320", time_budget=2))
        finally:
            release.set()
        assert result["sources"]["crossref"]["status"] == "ok"
        assert result["sources"]["openalex"]["status"] == "timeout"
        assert result["sources"]["icite"] == {"status": "error", "error": "RuntimeError: HTTP 429"}
        assert result["found"] is True and result["complete"] is False


class TestMakeEnricher:
    def test_configured_from_the_environment(self, monkeypatch):
        for name in ("UNPAYWALL_EMAIL", "CROSSREF_EMAIL", "OPENALEX_EMAIL"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "k")
        enricher = srv._make_enricher()
        try:
            assert "unpaywall" not in enricher.clients
            assert "ror" not in enricher.clients
            assert enricher.config.semantic_scholar_api_key == "k"
        finally:
            enricher.close()

    def test_unpaywall_turns_on_with_an_email(self, monkeypatch):
        monkeypatch.setenv("UNPAYWALL_EMAIL", "someone@example.org")
        enricher = srv._make_enricher()
        try:
            assert "unpaywall" in enricher.clients
        finally:
            enricher.close()


def test_the_tool_is_read_only():
    tools = {t.name: t for t in _run(srv.mcp.list_tools())}
    tool = tools["enrich_paper"]
    assert tool.annotations.readOnlyHint is True
    assert not tool.annotations.destructiveHint
    assert tool.inputSchema["properties"]["time_budget"]["maximum"] == 120
