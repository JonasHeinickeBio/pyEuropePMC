"""Unit tests for the pyeuropepmc.mcp.server tool handlers (hermetic)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.mcp import server as srv


@pytest.fixture(autouse=True)
def _reset_mcp_singletons():
    srv._SINGLE_CLIENT = None
    srv._SINGLE_UNIFIED = None
    yield
    srv._SINGLE_CLIENT = None
    srv._SINGLE_UNIFIED = None


def _text(response: dict) -> str:
    return response["content"][0]["text"]


class TestUnifiedSearchHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", False)
        result = srv._handle_unified_search({"query": "x"})
        assert "Error" in _text(result)

    def test_get_unified_none(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        monkeypatch.setattr(srv, "_get_unified", lambda: None)
        result = srv._handle_unified_search({"query": "x"})
        assert "Failed to initialise" in _text(result)

    def test_missing_query(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        monkeypatch.setattr(srv, "_get_unified", lambda: MagicMock())
        result = srv._handle_unified_search({})
        assert "query is required" in _text(result)

    def test_success_with_sources(self, monkeypatch):
        unified = MagicMock()
        report = MagicMock(total_input=10, total_output=5, duplicates_removed=5)
        unified.search.return_value = ([{"title": "a"}], report)
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        monkeypatch.setattr(srv, "_get_unified", lambda: unified)
        result = srv._handle_unified_search(
            {"query": "cancer", "sources": ["europepmc"], "limit": 5}
        )
        unified.search.assert_called_once_with("cancer", sources=["europepmc"], limit=5)
        assert "duplicates_removed" in _text(result)

    def test_success_without_sources(self, monkeypatch):
        unified = MagicMock()
        report = MagicMock(total_input=1, total_output=1, duplicates_removed=0)
        unified.search.return_value = ([], report)
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        monkeypatch.setattr(srv, "_get_unified", lambda: unified)
        srv._handle_unified_search({"query": "cancer"})
        unified.search.assert_called_once_with("cancer", limit=25)

    def test_search_exception(self, monkeypatch):
        unified = MagicMock()
        unified.search.side_effect = RuntimeError("boom")
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        monkeypatch.setattr(srv, "_get_unified", lambda: unified)
        result = srv._handle_unified_search({"query": "x"})
        assert "Unified search failed" in _text(result)


class TestCitationSnowballHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", False)
        result = srv._handle_citation_snowball({"identifier": "PMID:1"})
        assert "not available" in _text(result)

    def test_missing_identifier(self, monkeypatch):
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        result = srv._handle_citation_snowball({})
        assert "identifier is required" in _text(result)

    def test_success(self, monkeypatch):
        walker = MagicMock()
        report = MagicMock(total_input=3, total_output=2, duplicates_removed=1)
        walker.snowball.return_value = ([{"title": "a"}, {"title": "b"}], report)
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        monkeypatch.setattr(srv, "CitationWalker", lambda: walker)
        monkeypatch.setattr(
            srv,
            "SnowballingStrategy",
            MagicMock(FORWARD="forward", BACKWARD="backward", BOTH="both"),
        )
        result = srv._handle_citation_snowball(
            {"identifier": "PMID:1", "strategy": "both", "max_papers": 10}
        )
        assert '"paper_count": 2' in _text(result)

    def test_unknown_strategy_defaults_to_forward(self, monkeypatch):
        walker = MagicMock()
        report = MagicMock(total_input=0, total_output=0, duplicates_removed=0)
        walker.snowball.return_value = ([], report)
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        monkeypatch.setattr(srv, "CitationWalker", lambda: walker)
        srv._handle_citation_snowball({"identifier": "PMID:1", "strategy": "bogus"})
        _, kwargs = walker.snowball.call_args
        assert kwargs["strategy"] == srv.SnowballingStrategy.FORWARD

    def test_snowball_exception(self, monkeypatch):
        walker = MagicMock()
        walker.snowball.side_effect = RuntimeError("boom")
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        monkeypatch.setattr(srv, "CitationWalker", lambda: walker)
        result = srv._handle_citation_snowball({"identifier": "PMID:1"})
        assert "Snowball failed" in _text(result)


class TestClinicalTrialSearchHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", False)
        result = srv._handle_clinical_trial_search({})
        assert "not available" in _text(result)

    def _trial(self, status="RECRUITING", interventions="drug X"):
        t = MagicMock()
        t.extra_metadata = {"status": status, "interventions": interventions}
        return t

    def test_search_by_query_only(self, monkeypatch):
        client = MagicMock()
        client.search.return_value = [self._trial()]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        monkeypatch.setattr(srv, "ClinicalTrialsClient", lambda: client)
        result = srv._handle_clinical_trial_search({"query": "cancer"})
        client.search.assert_called_once()
        assert '"trial_count": 1' in _text(result)

    def test_search_by_condition_only(self, monkeypatch):
        client = MagicMock()
        client.search_by_condition.return_value = [self._trial()]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        monkeypatch.setattr(srv, "ClinicalTrialsClient", lambda: client)
        srv._handle_clinical_trial_search({"condition": "diabetes"})
        client.search_by_condition.assert_called_once_with("diabetes", limit=25)

    def test_search_by_intervention_only(self, monkeypatch):
        client = MagicMock()
        client.search_by_intervention.return_value = [self._trial()]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        monkeypatch.setattr(srv, "ClinicalTrialsClient", lambda: client)
        srv._handle_clinical_trial_search({"intervention": "metformin"})
        client.search_by_intervention.assert_called_once_with("metformin", limit=25)

    def test_condition_and_intervention_filters(self, monkeypatch):
        client = MagicMock()
        client.search_by_condition.return_value = [
            self._trial(interventions="metformin therapy"),
            self._trial(interventions="placebo"),
        ]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        monkeypatch.setattr(srv, "ClinicalTrialsClient", lambda: client)
        result = srv._handle_clinical_trial_search(
            {"condition": "diabetes", "intervention": "metformin"}
        )
        assert '"trial_count": 1' in _text(result)

    def test_status_filter(self, monkeypatch):
        client = MagicMock()
        client.search.return_value = [
            self._trial(status="RECRUITING"),
            self._trial(status="COMPLETED"),
        ]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        monkeypatch.setattr(srv, "ClinicalTrialsClient", lambda: client)
        result = srv._handle_clinical_trial_search({"query": "x", "status": "completed"})
        assert '"trial_count": 1' in _text(result)

    def test_exception(self, monkeypatch):
        client = MagicMock()
        client.search.side_effect = RuntimeError("boom")
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        monkeypatch.setattr(srv, "ClinicalTrialsClient", lambda: client)
        result = srv._handle_clinical_trial_search({"query": "x"})
        assert "Clinical trial search failed" in _text(result)


class TestFulltextIndexQueryHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "FTS_AVAILABLE", False)
        result = srv._handle_fulltext_index_query({})
        assert "not available" in _text(result)

    def test_success_default_index(self, monkeypatch):
        idx = MagicMock()
        idx.search.return_value = [{"title": "a"}]
        idx.stats.return_value = {"total_documents": 1}
        monkeypatch.setattr(srv, "FTS_AVAILABLE", True)
        monkeypatch.setattr(srv, "FullTextIndex", MagicMock(return_value=idx))
        result = srv._handle_fulltext_index_query({"query": "cancer"})
        assert "total_documents" in _text(result)

    def test_success_custom_index_path(self, monkeypatch):
        idx = MagicMock()
        idx.search.return_value = []
        idx.stats.return_value = {}
        mock_cls = MagicMock(return_value=idx)
        monkeypatch.setattr(srv, "FTS_AVAILABLE", True)
        monkeypatch.setattr(srv, "FullTextIndex", mock_cls)
        srv._handle_fulltext_index_query({"query": "x", "index_path": "/tmp/my.db"})
        mock_cls.assert_called_once_with(db_path="/tmp/my.db")

    def test_exception(self, monkeypatch):
        monkeypatch.setattr(srv, "FTS_AVAILABLE", True)
        monkeypatch.setattr(srv, "FullTextIndex", MagicMock(side_effect=RuntimeError("boom")))
        result = srv._handle_fulltext_index_query({"query": "x"})
        assert "Full-text index query failed" in _text(result)


class TestPaperFiguresHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", False)
        result = srv._handle_paper_figures({})
        assert "not available" in _text(result)

    def test_missing_identifier(self, monkeypatch):
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        result = srv._handle_paper_figures({})
        assert "One of pmcid, pmid, or doi is required" in _text(result)

    def test_by_pmcid(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = [{"label": "Fig 1"}]
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        monkeypatch.setattr(srv, "FigureExtractor", lambda: extractor)
        result = srv._handle_paper_figures({"pmcid": "PMC1"})
        extractor.extract.assert_called_once_with(pmcid="PMC1")
        assert '"figure_count": 1' in _text(result)

    def test_by_pmid(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = []
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        monkeypatch.setattr(srv, "FigureExtractor", lambda: extractor)
        srv._handle_paper_figures({"pmid": "123"})
        extractor.extract.assert_called_once_with(pmid="123")

    def test_by_doi(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = []
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        monkeypatch.setattr(srv, "FigureExtractor", lambda: extractor)
        srv._handle_paper_figures({"doi": "10.1/x"})
        extractor.extract.assert_called_once_with(doi="10.1/x")

    def test_exception(self, monkeypatch):
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        monkeypatch.setattr(srv, "FigureExtractor", MagicMock(side_effect=RuntimeError("boom")))
        result = srv._handle_paper_figures({"pmcid": "PMC1"})
        assert "Figure extraction failed" in _text(result)


class TestGetPaperDetailsHandler:
    def test_by_pmid(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        result = srv._handle_get_paper_details({"pmid": "123"}, client)
        client.search_all.assert_called_once_with("ext_id:123", pageSize=1)
        assert '"title": "a"' in _text(result)

    def test_by_pmcid(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        srv._handle_get_paper_details({"pmcid": "PMC1"}, client)
        client.search_all.assert_called_once_with("ext_id:PMC1", pageSize=1)

    def test_by_doi(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        srv._handle_get_paper_details({"doi": "10.1/x"}, client)
        client.search_all.assert_called_once_with("doi:10.1/x", pageSize=1)

    def test_no_identifier(self):
        client = MagicMock()
        result = srv._handle_get_paper_details({}, client)
        assert "At least one ID" in _text(result)

    def test_no_results(self):
        client = MagicMock()
        client.search_all.return_value = []
        result = srv._handle_get_paper_details({"pmid": "1"}, client)
        assert "No results found" in _text(result)


class TestFetchPaperSummaryAndBuildPaperDict:
    def test_fetch_paper_summary_found(self):
        client = MagicMock()
        client.search_all.return_value = [
            {
                "pmid": "1",
                "pmcid": "PMC1",
                "doi": "10.1/x",
                "title": "T",
                "authorInfo": [{"author": "Smith J"}],
                "firstPublicationYear": "2020",
                "journalTitle": "J",
                "abstract": "A",
            }
        ]
        summary = srv._fetch_paper_summary("1", client)
        assert summary["title"] == "T"
        assert summary["authors"] == [{"name": "Smith J"}]

    def test_fetch_paper_summary_not_found(self):
        client = MagicMock()
        client.search_all.return_value = []
        assert srv._fetch_paper_summary("1", client) is None

    def test_build_paper_dict(self):
        raw = {
            "pmid": "1",
            "title": "T",
            "authorInfo": [{"author": "Doe A"}],
        }
        d = srv._build_paper_dict(raw)
        assert d["pmid"] == "1"
        assert d["authors"] == [{"name": "Doe A"}]
        assert d["journal"] == ""


class TestBibliographyHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "BIBLIOGRAPHY_AVAILABLE", False)
        result = srv._handle_bibliography_tool("bib_parse_string", {})
        assert "not available" in _text(result)

    @pytest.fixture
    def bib_mocks(self, monkeypatch):
        mgr = MagicMock()
        converter = MagicMock()
        resolver = MagicMock()
        monkeypatch.setattr(srv, "BIBLIOGRAPHY_AVAILABLE", True)
        monkeypatch.setattr(srv, "BibtexManager", lambda: mgr)
        monkeypatch.setattr(srv, "CitationConverter", lambda: converter)
        monkeypatch.setattr(srv, "ReferenceResolver", lambda: resolver)
        return mgr, converter, resolver

    def test_bib_parse_string(self, bib_mocks):
        mgr, _, _ = bib_mocks
        entry = MagicMock(citation_key="k1", entry_type="article", fields={"title": "T"})
        lib = MagicMock(entries=[entry])
        lib.__len__.return_value = 1
        mgr.parse_string.return_value = lib
        result = srv._handle_bibliography_tool("bib_parse_string", {"content": "@article{...}"})
        assert '"entries_count": 1' in _text(result)

    def test_bib_validate(self, bib_mocks):
        mgr, _, _ = bib_mocks
        lib = MagicMock()
        lib.__len__.return_value = 2
        mgr.parse_string.return_value = lib
        mgr.validate.return_value = ["issue1"]
        result = srv._handle_bibliography_tool("bib_validate", {"content": "x"})
        assert '"issues_count": 1' in _text(result)

    def test_bib_to_ris(self, bib_mocks):
        mgr, converter, _ = bib_mocks
        entry = MagicMock()
        lib = MagicMock(entries=[entry])
        mgr.parse_string.return_value = lib
        converter.to_ris.return_value = "RIS-TEXT"
        result = srv._handle_bibliography_tool("bib_to_ris", {"content": "x"})
        assert _text(result) == "RIS-TEXT"

    def test_bib_to_csl(self, bib_mocks):
        mgr, converter, _ = bib_mocks
        entry = MagicMock()
        lib = MagicMock(entries=[entry])
        mgr.parse_string.return_value = lib
        converter.to_csl_json.return_value = {"type": "article"}
        result = srv._handle_bibliography_tool("bib_to_csl", {"content": "x"})
        assert "article" in _text(result)

    def test_ref_resolve_doi_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        ref = MagicMock()
        ref.to_dict.return_value = {"doi": "10.1/x"}
        resolver.resolve_doi.return_value = ref
        result = srv._handle_bibliography_tool("ref_resolve_doi", {"doi": "10.1/x"})
        assert "10.1/x" in _text(result)

    def test_ref_resolve_doi_not_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        resolver.resolve_doi.return_value = None
        result = srv._handle_bibliography_tool("ref_resolve_doi", {"doi": "10.1/x"})
        assert "No metadata found" in _text(result)

    def test_ref_resolve_pmid_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        ref = MagicMock()
        ref.to_dict.return_value = {"pmid": "1"}
        resolver.resolve_pmid.return_value = ref
        result = srv._handle_bibliography_tool("ref_resolve_pmid", {"pmid": "1"})
        assert '"pmid": "1"' in _text(result)

    def test_ref_resolve_pmid_not_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        resolver.resolve_pmid.return_value = None
        result = srv._handle_bibliography_tool("ref_resolve_pmid", {"pmid": "1"})
        assert "No metadata found" in _text(result)

    def test_bib_merge(self, bib_mocks):
        mgr, _, _ = bib_mocks
        lib1 = MagicMock()
        lib1.__len__.return_value = 2
        lib2 = MagicMock()
        lib2.__len__.return_value = 3
        mgr.parse_string.side_effect = [lib1, lib2]
        merged = MagicMock(entries=[MagicMock(citation_key="k1")])
        merged.__len__.return_value = 1
        mgr.merge.return_value = merged
        result = srv._handle_bibliography_tool("bib_merge", {"libraries": ["a", "b"]})
        assert '"input_libraries": 2' in _text(result)
        assert '"merged_entries": 1' in _text(result)

    def test_unknown_tool(self, bib_mocks):
        result = srv._handle_bibliography_tool("bib_unknown", {})
        assert "Unknown bibliography tool" in _text(result)

    def test_exception(self, monkeypatch):
        monkeypatch.setattr(srv, "BIBLIOGRAPHY_AVAILABLE", True)
        monkeypatch.setattr(srv, "BibtexManager", MagicMock(side_effect=RuntimeError("boom")))
        result = srv._handle_bibliography_tool("bib_parse_string", {})
        assert "Bibliography error" in _text(result)


class TestLlmToolHandler:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "LLM_AVAILABLE", False)
        result = srv._handle_llm_tool("analyze_citations", {}, MagicMock())
        assert "not available" in _text(result)

    def test_init_failure(self, monkeypatch):
        monkeypatch.setattr(srv, "LLM_AVAILABLE", True)
        monkeypatch.setattr(srv, "create_llm_client", MagicMock(side_effect=RuntimeError("no key")))
        result = srv._handle_llm_tool("analyze_citations", {}, MagicMock())
        assert "Failed to initialise LLM" in _text(result)

    @pytest.fixture
    def llm_mocks(self, monkeypatch):
        agent = MagicMock()
        monkeypatch.setattr(srv, "LLM_AVAILABLE", True)
        monkeypatch.setattr(srv, "create_llm_client", lambda: MagicMock())
        monkeypatch.setattr(srv, "SmartCitationAnalysis", lambda **kw: agent)
        return agent

    def test_analyze_citations_paper_not_found(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = []
        result = srv._handle_llm_tool("analyze_citations", {"pmid": "1"}, client)
        assert "not found" in _text(result)

    def test_analyze_citations_success(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        llm_mocks.analyze_citation_context.return_value = {"summary": "ok"}
        result = srv._handle_llm_tool("analyze_citations", {"pmid": "1"}, client)
        assert "ok" in _text(result)

    def test_analyze_citations_agent_returns_falsy(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        llm_mocks.analyze_citation_context.return_value = None
        result = srv._handle_llm_tool("analyze_citations", {"pmid": "1"}, client)
        assert "Failed to analyze citations" in _text(result)

    def test_compare_citations_missing_paper(self, llm_mocks):
        client = MagicMock()
        client.search_all.side_effect = [[{"pmid": "1"}], []]
        result = srv._handle_llm_tool(
            "compare_citations", {"pmid1": "1", "pmid2": "2"}, client
        )
        assert "One or both papers not found" in _text(result)

    def test_compare_citations_success(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1"}]
        llm_mocks.compare_citations.return_value = {"result": "ok"}
        result = srv._handle_llm_tool(
            "compare_citations", {"pmid1": "1", "pmid2": "2"}, client
        )
        assert "ok" in _text(result)

    def test_summarize_citations_success(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1"}]
        llm_mocks.summarize_citations.return_value = {"summary": "ok"}
        result = srv._handle_llm_tool("summarize_citations", {"pmid": "1"}, client)
        assert "ok" in _text(result)

    def test_summarize_citations_not_found(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = []
        result = srv._handle_llm_tool("summarize_citations", {"pmid": "1"}, client)
        assert "not found" in _text(result)

    def test_paper_screening(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        llm_mocks.screen_papers.return_value = {"included": []}
        result = srv._handle_llm_tool("paper_screening", {"query": "x"}, client)
        assert "included" in _text(result)

    def test_research_question_analysis(self, llm_mocks):
        llm_mocks.analyze_research_question.return_value = {"ok": True}
        result = srv._handle_llm_tool(
            "research_question_analysis", {"research_question": "q"}, MagicMock()
        )
        assert "ok" in _text(result)

    def test_preprint_analysis(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        llm_mocks.analyze_preprint.return_value = {"ok": True}
        result = srv._handle_llm_tool("preprint_analysis", {"pmid": "1"}, client)
        assert "ok" in _text(result)

    def test_preprint_analysis_not_found(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = []
        result = srv._handle_llm_tool("preprint_analysis", {"pmid": "1"}, client)
        assert "not found" in _text(result)

    def test_literature_review(self, llm_mocks):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        llm_mocks.generate_literature_review.return_value = {"ok": True}
        result = srv._handle_llm_tool(
            "literature_review", {"research_topic": "x"}, client
        )
        assert "ok" in _text(result)

    def test_knowledge_graph(self, llm_mocks):
        llm_mocks.build_knowledge_graph.return_value = {"ok": True}
        result = srv._handle_llm_tool(
            "knowledge_graph", {"research_domain": "x"}, MagicMock()
        )
        assert "ok" in _text(result)

    def test_unknown_tool(self, llm_mocks):
        result = srv._handle_llm_tool("bogus_tool", {}, MagicMock())
        assert "Unknown LLM tool" in _text(result)

    def test_generic_exception(self, llm_mocks):
        client = MagicMock()
        client.search_all.side_effect = RuntimeError("boom")
        result = srv._handle_llm_tool("analyze_citations", {"pmid": "1"}, client)
        assert "LLM tool error" in _text(result)


class TestHandleListTools:
    def test_returns_full_tool_registry(self):
        result = srv.handle_list_tools({})
        assert "tools" in result
        names = {t["name"] for t in result["tools"]}
        assert "unified_search" in names
        assert "bib_merge" in names
        for tool in result["tools"]:
            assert "description" in tool
            assert "inputSchema" in tool


class TestHandleCallToolDispatch:
    def test_dispatch_search_papers(self, monkeypatch):
        client = MagicMock()
        client.search_all.return_value = []
        monkeypatch.setattr(srv, "_get_client", lambda: client)
        result = srv.handle_call_tool({"name": "search_papers", "arguments": {"query": "x"}})
        assert result["content"]

    def test_dispatch_search_authors(self, monkeypatch):
        client = MagicMock()
        client.search_all.return_value = []
        monkeypatch.setattr(srv, "_get_client", lambda: client)
        srv.handle_call_tool({"name": "search_authors", "arguments": {"query": "Smith"}})
        args, kwargs = client.search_all.call_args
        assert 'AUTH:"Smith"' in args[0]

    def test_dispatch_get_paper_citations(self, monkeypatch):
        client = MagicMock()
        client.search_all.return_value = []
        monkeypatch.setattr(srv, "_get_client", lambda: client)
        srv.handle_call_tool({"name": "get_paper_citations", "arguments": {"pmid": "1"}})
        args, kwargs = client.search_all.call_args
        assert args[0] == "CITED:1"

    def test_dispatch_unknown_tool(self, monkeypatch):
        monkeypatch.setattr(srv, "_get_client", lambda: MagicMock())
        result = srv.handle_call_tool({"name": "totally_unknown"})
        assert "Unknown tool" in _text(result)

    def test_dispatch_swallows_exception(self, monkeypatch):
        monkeypatch.setattr(
            srv, "_get_client", MagicMock(side_effect=RuntimeError("client init failed"))
        )
        result = srv.handle_call_tool({"name": "search_papers", "arguments": {}})
        assert "client init failed" in _text(result)

    def test_dispatch_llm_tool_routes_correctly(self, monkeypatch):
        monkeypatch.setattr(srv, "_get_client", lambda: MagicMock())
        monkeypatch.setattr(
            srv, "_handle_llm_tool", lambda name, args, client: srv._ok({"routed": name})
        )
        result = srv.handle_call_tool({"name": "compare_citations", "arguments": {}})
        assert "compare_citations" in _text(result)

    def test_dispatch_bibliography_tool_routes_correctly(self, monkeypatch):
        monkeypatch.setattr(srv, "_get_client", lambda: MagicMock())
        monkeypatch.setattr(
            srv, "_handle_bibliography_tool", lambda name, args: srv._ok({"routed": name})
        )
        result = srv.handle_call_tool({"name": "bib_validate", "arguments": {}})
        assert "bib_validate" in _text(result)
