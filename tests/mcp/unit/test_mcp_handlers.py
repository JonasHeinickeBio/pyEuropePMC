"""Unit tests for the pyeuropepmc.mcp.server tool implementations (hermetic).

Each tool is a plain async function (the ``@mcp.tool()`` decorator returns the
original callable unchanged), so these tests call them directly — awaited via
``asyncio.run`` — with the underlying pyeuropepmc clients mocked out through
the module's lazy-singleton caches. Protocol-level concerns (schema
validation, ``isError`` wrapping, tool discovery) live in test_mcp_server.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from pyeuropepmc.mcp import server as srv

ALL_CACHES = [
    srv._client_cache,
    srv._unified_cache,
    srv._citation_walker_cache,
    srv._clinical_trials_cache,
    srv._figure_extractor_cache,
    srv._llm_agent_cache,
    srv._bib_manager_cache,
    srv._bib_converter_cache,
    srv._bib_resolver_cache,
]


@pytest.fixture(autouse=True)
def _reset_singletons():
    for cache in ALL_CACHES:
        cache.reset()
    yield
    for cache in ALL_CACHES:
        cache.reset()


def _run(coro):
    return asyncio.run(coro)


def _fake_ctx() -> MagicMock:
    """A truthy stand-in for mcp.server.fastmcp.Context with an awaitable .info()."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    return ctx


class TestUnifiedSearch:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", False)
        with pytest.raises(ToolError, match="UnifiedSearch not available"):
            _run(srv.unified_search(query="x"))

    def test_success_with_sources(self, monkeypatch):
        unified = MagicMock()
        report = MagicMock(total_input=10, total_output=5, duplicates_removed=5)
        unified.search.return_value = ([{"title": "a"}], report)
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        srv._unified_cache.set(unified)

        result = _run(srv.unified_search(query="cancer", sources=["europepmc"], limit=5))

        unified.search.assert_called_once_with("cancer", sources=["europepmc"], limit=5)
        assert result["dedup"] == {
            "total_input": 10,
            "total_output": 5,
            "duplicates_removed": 5,
        }
        assert result["results"] == [{"title": "a"}]

    def test_success_without_sources(self, monkeypatch):
        unified = MagicMock()
        report = MagicMock(total_input=1, total_output=1, duplicates_removed=0)
        unified.search.return_value = ([], report)
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        srv._unified_cache.set(unified)

        _run(srv.unified_search(query="cancer"))

        unified.search.assert_called_once_with("cancer", sources=None, limit=25)

    def test_search_exception_propagates(self, monkeypatch):
        unified = MagicMock()
        unified.search.side_effect = RuntimeError("boom")
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        srv._unified_cache.set(unified)
        with pytest.raises(RuntimeError, match="boom"):
            _run(srv.unified_search(query="x"))

    def test_reports_progress_via_context(self, monkeypatch):
        unified = MagicMock()
        report = MagicMock(total_input=1, total_output=1, duplicates_removed=0)
        unified.search.return_value = ([], report)
        monkeypatch.setattr(srv, "UNIFIED_AVAILABLE", True)
        srv._unified_cache.set(unified)
        ctx = _fake_ctx()

        _run(srv.unified_search(query="cancer", ctx=ctx))

        assert ctx.info.await_count == 2


class TestSearchPapers:
    def test_success(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        srv._client_cache.set(client)

        result = _run(srv.search_papers(query="x", limit=10, sort="cited", result_type="lite"))

        client.search_all.assert_called_once_with(
            "x", pageSize=10, resultType="lite", sort="cited"
        )
        assert result == [{"title": "a"}]

    def test_no_sort_omits_kwarg(self):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)

        _run(srv.search_papers(query="x"))

        client.search_all.assert_called_once_with("x", pageSize=25, resultType="core")


class TestGetPaperDetails:
    def test_by_pmid(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        srv._client_cache.set(client)

        result = _run(srv.get_paper_details(pmid="123"))

        client.search_all.assert_called_once_with("ext_id:123", pageSize=1)
        assert result == {"title": "a"}

    def test_by_pmcid(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        srv._client_cache.set(client)
        _run(srv.get_paper_details(pmcid="PMC1"))
        client.search_all.assert_called_once_with("ext_id:PMC1", pageSize=1)

    def test_by_doi(self):
        client = MagicMock()
        client.search_all.return_value = [{"title": "a"}]
        srv._client_cache.set(client)
        _run(srv.get_paper_details(doi="10.1/x"))
        client.search_all.assert_called_once_with("doi:10.1/x", pageSize=1)

    def test_no_identifier_raises(self):
        with pytest.raises(ToolError, match="At least one ID"):
            _run(srv.get_paper_details())

    def test_no_results_raises(self):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="No results found"):
            _run(srv.get_paper_details(pmid="1"))


class TestSearchAuthors:
    def test_builds_auth_query(self):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        _run(srv.search_authors(query="Smith"))
        args, kwargs = client.search_all.call_args
        assert args[0] == 'AUTH:"Smith"'
        assert kwargs == {"pageSize": 25}


class TestGetPaperCitations:
    def test_builds_cited_query(self):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "2"}]
        srv._client_cache.set(client)
        result = _run(srv.get_paper_citations(pmid="1", limit=50))
        client.search_all.assert_called_once_with("CITED:1", pageSize=50)
        assert result == [{"pmid": "2"}]


class TestCitationSnowball:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.citation_snowball(identifier="PMID:1"))

    def test_success(self, monkeypatch):
        walker = MagicMock()
        report = MagicMock(total_input=3, total_output=2, duplicates_removed=1)
        walker.snowball.return_value = ([{"title": "a"}, {"title": "b"}], report)
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        srv._citation_walker_cache.set(walker)

        result = _run(srv.citation_snowball(identifier="PMID:1", strategy="both", max_papers=10))

        assert result["paper_count"] == 2
        _, kwargs = walker.snowball.call_args
        assert kwargs["strategy"] == srv.SnowballingStrategy.BOTH
        assert kwargs["max_papers"] == 10

    def test_invalid_strategy_rejected_by_schema(self, monkeypatch):
        """Unlike the old handler (which silently fell back to 'forward'), an
        invalid literal is now a validation error raised before the tool body
        runs at all — see TestToolRegistry.test_calling_tool_validates_input_types
        for the protocol-level version of this."""
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        srv._citation_walker_cache.set(MagicMock())
        with pytest.raises(KeyError):
            _run(srv.citation_snowball(identifier="PMID:1", strategy="bogus"))  # type: ignore[arg-type]

    def test_reports_progress_via_context(self, monkeypatch):
        walker = MagicMock()
        report = MagicMock(total_input=0, total_output=0, duplicates_removed=0)
        walker.snowball.return_value = ([], report)
        monkeypatch.setattr(srv, "CITATION_WALKER_AVAILABLE", True)
        srv._citation_walker_cache.set(walker)
        ctx = _fake_ctx()

        _run(srv.citation_snowball(identifier="PMID:1", ctx=ctx))

        ctx.info.assert_awaited_once()


class TestClinicalTrialSearch:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.clinical_trial_search())

    def _trial(self, status="RECRUITING", interventions="drug X"):
        t = MagicMock()
        t.extra_metadata = {"status": status, "interventions": interventions}
        return t

    def test_search_by_query_only(self, monkeypatch):
        client = MagicMock()
        client.search.return_value = [self._trial()]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        srv._clinical_trials_cache.set(client)

        result = _run(srv.clinical_trial_search(query="cancer"))

        client.search.assert_called_once_with("cancer", limit=25)
        assert result["trial_count"] == 1

    def test_search_by_condition_only(self, monkeypatch):
        client = MagicMock()
        client.search_by_condition.return_value = [self._trial()]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        srv._clinical_trials_cache.set(client)
        _run(srv.clinical_trial_search(condition="diabetes"))
        client.search_by_condition.assert_called_once_with("diabetes", limit=25)

    def test_search_by_intervention_only(self, monkeypatch):
        client = MagicMock()
        client.search_by_intervention.return_value = [self._trial()]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        srv._clinical_trials_cache.set(client)
        _run(srv.clinical_trial_search(intervention="metformin"))
        client.search_by_intervention.assert_called_once_with("metformin", limit=25)

    def test_condition_and_intervention_filters(self, monkeypatch):
        client = MagicMock()
        client.search_by_condition.return_value = [
            self._trial(interventions="metformin therapy"),
            self._trial(interventions="placebo"),
        ]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        srv._clinical_trials_cache.set(client)

        result = _run(srv.clinical_trial_search(condition="diabetes", intervention="metformin"))

        assert result["trial_count"] == 1

    def test_status_filter(self, monkeypatch):
        client = MagicMock()
        client.search.return_value = [
            self._trial(status="RECRUITING"),
            self._trial(status="COMPLETED"),
        ]
        monkeypatch.setattr(srv, "CLINICAL_TRIALS_AVAILABLE", True)
        srv._clinical_trials_cache.set(client)

        result = _run(srv.clinical_trial_search(query="x", status="completed"))

        assert result["trial_count"] == 1


class TestFulltextIndexQuery:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "FTS_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.fulltext_index_query(query="x"))

    def test_success_default_index(self, monkeypatch):
        idx = MagicMock()
        idx.search.return_value = [{"title": "a"}]
        idx.stats.return_value = {"total_documents": 1}
        monkeypatch.setattr(srv, "FTS_AVAILABLE", True)
        monkeypatch.setattr(srv, "FullTextIndex", MagicMock(return_value=idx))

        result = _run(srv.fulltext_index_query(query="cancer"))

        assert result["stats"] == {"total_documents": 1}
        assert result["results"] == [{"title": "a"}]

    def test_success_custom_index_path(self, monkeypatch):
        idx = MagicMock()
        idx.search.return_value = []
        idx.stats.return_value = {}
        mock_cls = MagicMock(return_value=idx)
        monkeypatch.setattr(srv, "FTS_AVAILABLE", True)
        monkeypatch.setattr(srv, "FullTextIndex", mock_cls)

        _run(srv.fulltext_index_query(query="x", index_path="/tmp/my.db"))

        mock_cls.assert_called_once_with(db_path="/tmp/my.db")

    def test_exception_propagates(self, monkeypatch):
        monkeypatch.setattr(srv, "FTS_AVAILABLE", True)
        monkeypatch.setattr(srv, "FullTextIndex", MagicMock(side_effect=RuntimeError("boom")))
        with pytest.raises(RuntimeError, match="boom"):
            _run(srv.fulltext_index_query(query="x"))


class TestPaperFigures:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.paper_figures())

    def test_missing_identifier(self, monkeypatch):
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        with pytest.raises(ToolError, match="One of pmcid, pmid, or doi is required"):
            _run(srv.paper_figures())

    def test_by_pmcid(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = [
            {"label": "Fig 1", "figure_type": "figure"},
            {"label": "Table 1", "figure_type": "table"},
        ]
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        srv._figure_extractor_cache.set(extractor)

        result = _run(srv.paper_figures(pmcid="PMC1"))

        extractor.extract.assert_called_once_with(
            pmcid="PMC1", include_tables=True, include_supplements=True
        )
        assert result["figure_count"] == 2
        assert result["counts_by_type"] == {"figure": 1, "table": 1}

    def test_by_pmid(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = []
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        srv._figure_extractor_cache.set(extractor)
        _run(srv.paper_figures(pmid="123"))
        extractor.extract.assert_called_once_with(
            pmid="123", include_tables=True, include_supplements=True
        )

    def test_by_doi(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = []
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        srv._figure_extractor_cache.set(extractor)
        _run(srv.paper_figures(doi="10.1/x"))
        extractor.extract.assert_called_once_with(
            doi="10.1/x", include_tables=True, include_supplements=True
        )

    def test_tables_and_supplements_can_be_left_out(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract.return_value = []
        monkeypatch.setattr(srv, "FIGURE_EXTRACTOR_AVAILABLE", True)
        srv._figure_extractor_cache.set(extractor)
        _run(srv.paper_figures(pmcid="PMC1", include_tables=False, include_supplements=False))
        extractor.extract.assert_called_once_with(
            pmcid="PMC1", include_tables=False, include_supplements=False
        )


class TestLlmTools:
    @pytest.fixture
    def agent(self, monkeypatch):
        mock_agent = MagicMock()
        monkeypatch.setattr(srv, "LLM_AVAILABLE", True)
        srv._llm_agent_cache.set(mock_agent)
        return mock_agent

    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "LLM_AVAILABLE", False)
        with pytest.raises(ToolError, match="LLM tools not available"):
            _run(srv.analyze_citations(pmid="1"))

    def test_init_failure_wrapped(self, monkeypatch):
        monkeypatch.setattr(srv, "LLM_AVAILABLE", True)
        monkeypatch.setattr(
            srv._llm_agent_cache, "_factory", MagicMock(side_effect=RuntimeError("no key"))
        )
        with pytest.raises(ToolError, match="Failed to initialise LLM client"):
            _run(srv.analyze_citations(pmid="1"))

    def test_analyze_citations_paper_not_found(self, agent):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="not found"):
            _run(srv.analyze_citations(pmid="1"))

    def test_analyze_citations_success(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.analyze_citation_context.return_value = {"summary": "ok"}

        result = _run(srv.analyze_citations(pmid="1"))

        assert result == {"summary": "ok"}

    def test_analyze_citations_agent_returns_falsy(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.analyze_citation_context.return_value = None
        with pytest.raises(ToolError, match="Failed to analyze citations"):
            _run(srv.analyze_citations(pmid="1"))

    def test_compare_citations_missing_paper(self, agent):
        client = MagicMock()
        client.search_all.side_effect = [[{"pmid": "1"}], []]
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="One or both papers not found"):
            _run(srv.compare_citations(pmid1="1", pmid2="2"))

    def test_compare_citations_success(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1"}]
        srv._client_cache.set(client)
        agent.compare_citations.return_value = {"result": "ok"}
        result = _run(srv.compare_citations(pmid1="1", pmid2="2"))
        assert result == {"result": "ok"}

    def test_compare_citations_agent_returns_falsy(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1"}]
        srv._client_cache.set(client)
        agent.compare_citations.return_value = None
        with pytest.raises(ToolError, match="Failed to compare citations"):
            _run(srv.compare_citations(pmid1="1", pmid2="2"))

    def test_summarize_citations_success(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1"}]
        srv._client_cache.set(client)
        agent.summarize_citations.return_value = {"summary": "ok"}
        result = _run(srv.summarize_citations(pmid="1"))
        assert result == {"summary": "ok"}

    def test_summarize_citations_not_found(self, agent):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="not found"):
            _run(srv.summarize_citations(pmid="1"))

    def test_summarize_citations_agent_returns_falsy(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1"}]
        srv._client_cache.set(client)
        agent.summarize_citations.return_value = None
        with pytest.raises(ToolError, match="Failed to summarize citations"):
            _run(srv.summarize_citations(pmid="1"))

    def test_paper_screening(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.screen_papers.return_value = {"included": []}

        result = _run(
            srv.paper_screening(query="x", inclusion_criteria=["a"], exclusion_criteria=["b"])
        )

        assert result == {"included": []}
        agent.screen_papers.assert_called_once()

    def test_paper_screening_agent_returns_falsy(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.screen_papers.return_value = None
        with pytest.raises(ToolError, match="Failed to screen papers"):
            _run(
                srv.paper_screening(query="x", inclusion_criteria=["a"], exclusion_criteria=["b"])
            )

    def test_paper_screening_reports_progress_via_context(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.screen_papers.return_value = {"included": []}
        ctx = _fake_ctx()

        _run(
            srv.paper_screening(
                query="x", inclusion_criteria=["a"], exclusion_criteria=["b"], ctx=ctx
            )
        )

        assert ctx.info.await_count == 2

    def test_research_question_analysis(self, agent):
        agent.analyze_research_question.return_value = {"ok": True}
        result = _run(srv.research_question_analysis(research_question="q"))
        assert result == {"ok": True}

    def test_research_question_analysis_agent_returns_falsy(self, agent):
        agent.analyze_research_question.return_value = None
        with pytest.raises(ToolError, match="Failed to analyze research question"):
            _run(srv.research_question_analysis(research_question="q"))

    def test_preprint_analysis(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.analyze_preprint.return_value = {"ok": True}
        result = _run(srv.preprint_analysis(pmid="1"))
        assert result == {"ok": True}

    def test_preprint_analysis_not_found(self, agent):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="not found"):
            _run(srv.preprint_analysis(pmid="1"))

    def test_preprint_analysis_agent_returns_falsy(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.analyze_preprint.return_value = None
        with pytest.raises(ToolError, match="Failed to analyze preprint"):
            _run(srv.preprint_analysis(pmid="1"))

    def test_literature_review(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.generate_literature_review.return_value = {"ok": True}

        result = _run(srv.literature_review(research_topic="x", key_concepts=["a"]))

        assert result == {"ok": True}
        _, kwargs = agent.generate_literature_review.call_args
        assert kwargs["excluded_topics"] == []

    def test_literature_review_agent_returns_falsy(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.generate_literature_review.return_value = None
        with pytest.raises(ToolError, match="Failed to generate literature review"):
            _run(srv.literature_review(research_topic="x", key_concepts=["a"]))

    def test_literature_review_reports_progress_via_context(self, agent):
        client = MagicMock()
        client.search_all.return_value = [{"pmid": "1", "title": "T"}]
        srv._client_cache.set(client)
        agent.generate_literature_review.return_value = {"ok": True}
        ctx = _fake_ctx()

        _run(srv.literature_review(research_topic="x", key_concepts=["a"], ctx=ctx))

        ctx.info.assert_awaited_once()

    def test_knowledge_graph(self, agent):
        agent.build_knowledge_graph.return_value = {"ok": True}
        result = _run(srv.knowledge_graph(research_domain="x"))
        assert result == {"ok": True}

    def test_knowledge_graph_agent_returns_falsy(self, agent):
        agent.build_knowledge_graph.return_value = None
        with pytest.raises(ToolError, match="Failed to build knowledge graph"):
            _run(srv.knowledge_graph(research_domain="x"))


class TestBibliographyTools:
    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "BIBLIOGRAPHY_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.bib_parse_string(content=""))

    @pytest.fixture
    def bib_mocks(self, monkeypatch):
        mgr = MagicMock()
        converter = MagicMock()
        resolver = MagicMock()
        monkeypatch.setattr(srv, "BIBLIOGRAPHY_AVAILABLE", True)
        monkeypatch.setattr(srv, "BIBTEXPARSER_AVAILABLE", True)
        srv._bib_manager_cache.set(mgr)
        srv._bib_converter_cache.set(converter)
        srv._bib_resolver_cache.set(resolver)
        return mgr, converter, resolver

    def test_bib_parse_string(self, bib_mocks):
        mgr, _, _ = bib_mocks
        entry = MagicMock(citation_key="k1", entry_type="article", fields={"title": "T"})
        lib = MagicMock(entries=[entry])
        lib.__len__.return_value = 1
        mgr.parse_string.return_value = lib

        result = _run(srv.bib_parse_string(content="@article{...}"))

        assert result["entries_count"] == 1
        assert result["keys"] == ["k1"]

    def test_bib_validate(self, bib_mocks):
        mgr, _, _ = bib_mocks
        lib = MagicMock()
        lib.__len__.return_value = 2
        mgr.parse_string.return_value = lib
        mgr.validate.return_value = ["issue1"]

        result = _run(srv.bib_validate(content="x"))

        assert result["issues_count"] == 1

    def test_bib_to_ris(self, bib_mocks):
        mgr, converter, _ = bib_mocks
        entry = MagicMock()
        lib = MagicMock(entries=[entry])
        mgr.parse_string.return_value = lib
        converter.to_ris.return_value = "RIS-TEXT"

        result = _run(srv.bib_to_ris(content="x"))

        assert result == "RIS-TEXT"

    def test_bib_to_csl(self, bib_mocks):
        mgr, converter, _ = bib_mocks
        entry = MagicMock()
        lib = MagicMock(entries=[entry])
        mgr.parse_string.return_value = lib
        converter.to_csl_json.return_value = {"type": "article"}

        result = _run(srv.bib_to_csl(content="x"))

        assert result == [{"type": "article"}]

    def test_bib_tools_need_the_bibliography_extra(self, bib_mocks, monkeypatch):
        """Without bibtexparser the BibTeX tools say which extra to install."""
        monkeypatch.setattr(srv, "BIBTEXPARSER_AVAILABLE", False)
        with pytest.raises(ToolError, match=r"pip install pyeuropepmc\[bibliography\]"):
            _run(srv.bib_parse_string(content="@article{k, title={T}}"))

    def test_ref_tools_work_without_the_bibliography_extra(self, bib_mocks, monkeypatch):
        """Resolving an identifier needs no bibtexparser, so no extra is demanded."""
        _, _, resolver = bib_mocks
        monkeypatch.setattr(srv, "BIBTEXPARSER_AVAILABLE", False)
        ref = MagicMock()
        ref.to_dict.return_value = {"doi": "10.1/x"}
        resolver.resolve_doi.return_value = ref

        assert _run(srv.ref_resolve_doi(doi="10.1/x")) == {"doi": "10.1/x"}

    def test_ref_resolve_doi_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        ref = MagicMock()
        ref.to_dict.return_value = {"doi": "10.1/x"}
        resolver.resolve_doi.return_value = ref

        result = _run(srv.ref_resolve_doi(doi="10.1/x"))

        assert result == {"doi": "10.1/x"}

    def test_ref_resolve_doi_not_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        resolver.resolve_doi.return_value = None
        with pytest.raises(ToolError, match="No metadata found"):
            _run(srv.ref_resolve_doi(doi="10.1/x"))

    def test_ref_resolve_pmid_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        ref = MagicMock()
        ref.to_dict.return_value = {"pmid": "1"}
        resolver.resolve_pmid.return_value = ref

        result = _run(srv.ref_resolve_pmid(pmid="1"))

        assert result == {"pmid": "1"}

    def test_ref_resolve_pmid_not_found(self, bib_mocks):
        _, _, resolver = bib_mocks
        resolver.resolve_pmid.return_value = None
        with pytest.raises(ToolError, match="No metadata found"):
            _run(srv.ref_resolve_pmid(pmid="1"))

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

        result = _run(srv.bib_merge(libraries=["a", "b"]))

        assert result["input_libraries"] == 2
        assert result["merged_entries"] == 1
        assert result["deduplicated"] == 4
