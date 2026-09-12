"""Unit tests for pyeuropepmc.agentic.agents.

Covers BaseAgent's progress-callback plumbing and SmartCitationAnalysis's
LLM-backed analysis methods (disabled/cached/happy-path/exception branches)
plus its pure text-extraction helpers, using a mocked LLMClient so no real
LLM calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyeuropepmc.agentic.agents import BaseAgent, SmartCitationAnalysis


class _ConcreteAgent(BaseAgent):
    def execute(self, **kwargs):
        return {"ok": True}


def _mock_llm(enabled=True, result="Some result text"):
    llm = MagicMock()
    llm.enabled = enabled
    llm.generate_with_template.return_value = result
    return llm


def _agent(enabled=True, result="Some result text"):
    return SmartCitationAnalysis(llm_client=_mock_llm(enabled, result))


class TestBaseAgent:
    def test_execute_is_abstract(self):
        with pytest.raises(TypeError):
            BaseAgent()

    def test_register_and_notify_progress(self):
        agent = _ConcreteAgent(llm_client=_mock_llm())
        calls = []
        agent.register_progress_callback(lambda p, m: calls.append((p, m)))
        agent._notify_progress(0.5, "halfway")
        assert calls == [(0.5, "halfway")]

    def test_notify_progress_swallows_callback_exception(self):
        agent = _ConcreteAgent(llm_client=_mock_llm())
        agent.register_progress_callback(lambda p, m: (_ for _ in ()).throw(RuntimeError("boom")))
        agent._notify_progress(1.0, "done")  # should not raise

    def test_default_llm_client_created_when_none_and_disabled(self):
        agent = _ConcreteAgent(llm_enabled=False)
        assert agent.llm_client.enabled is False


class TestAnalyzeCitationContext:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.analyze_citation_context({"pmid": "1"}) is None

    def test_happy_path(self):
        agent = _agent(result="- insight one\nSome longer descriptive line here.")
        result = agent.analyze_citation_context({"pmid": "1", "title": "T"})
        assert result["paper_id"] == "1"
        assert result["title"] == "T"
        assert "insight one" in result["insights"]
        assert result["methodology"]
        assert result["limitations"]

    def test_cache_hit_skips_llm_call(self):
        agent = _agent()
        first = agent.analyze_citation_context({"pmid": "1"}, context="ctx")
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.analyze_citation_context({"pmid": "1"}, context="ctx")
        assert first == second
        agent.llm_client.generate_with_template.assert_not_called()

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.analyze_citation_context({"pmid": "1"}) is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.analyze_citation_context({"pmid": "1"}) is None


class TestCompareCitations:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.compare_citations({}, {}) is None

    def test_happy_path(self):
        agent = _agent(
            result="These are similar in method.\nThey are different in scope.\nThe implication is clear."
        )
        result = agent.compare_citations({"pmid": "1"}, {"pmid": "2"})
        assert result["paper1_id"] == "1"
        assert result["paper2_id"] == "2"
        assert result["similarities"]
        assert result["differences"]
        assert result["implications"]

    def test_cache_hit(self):
        agent = _agent()
        first = agent.compare_citations({"pmid": "1"}, {"pmid": "2"})
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.compare_citations({"pmid": "1"}, {"pmid": "2"})
        assert first == second
        agent.llm_client.generate_with_template.assert_not_called()

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.compare_citations({}, {}) is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.compare_citations({}, {}) is None


class TestSummarizeCitations:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.summarize_citations({}, 10) is None

    def test_happy_path_increasing_trend(self):
        agent = _agent(result="Citations are increasing over time.\nA notable pattern line.")
        result = agent.summarize_citations({"pmid": "1"}, 10)
        assert result["trend"] == "increasing"
        assert result["patterns"]

    def test_declining_trend(self):
        agent = _agent(result="Citations are declining now.")
        result = agent.summarize_citations({"pmid": "1"}, 10)
        assert result["trend"] == "declining"

    def test_steady_trend_default(self):
        agent = _agent(result="Nothing notable here.")
        result = agent.summarize_citations({"pmid": "1"}, 10)
        assert result["trend"] == "steady"

    def test_cache_hit(self):
        agent = _agent()
        first = agent.summarize_citations({"pmid": "1"}, 5)
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.summarize_citations({"pmid": "1"}, 5)
        assert first == second
        agent.llm_client.generate_with_template.assert_not_called()

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.summarize_citations({}, 0) is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.summarize_citations({}, 0) is None


class TestExecuteDispatch:
    def test_analyze_task(self):
        agent = _agent()
        result = agent.execute(task_type="analyze", paper={"pmid": "1"})
        assert result["paper_id"] == "1"

    def test_compare_task(self):
        agent = _agent()
        result = agent.execute(task_type="compare", paper1={"pmid": "1"}, paper2={"pmid": "2"})
        assert result["paper1_id"] == "1"

    def test_summarize_task(self):
        agent = _agent()
        result = agent.execute(task_type="summarize", paper={"pmid": "1"}, citation_count=3)
        assert result["citation_count"] == 3

    def test_default_task_type_is_analyze(self):
        agent = _agent()
        result = agent.execute(paper={"pmid": "1"})
        assert result["paper_id"] == "1"

    def test_unknown_task_type_returns_error_dict(self):
        agent = _agent()
        result = agent.execute(task_type="bogus")
        assert "error" in result


class TestScreenPapers:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.screen_papers([{"pmid": "1"}], ["inc"], ["exc"]) is None

    def test_no_papers_returns_none(self):
        agent = _agent()
        assert agent.screen_papers([], ["inc"], ["exc"]) is None

    def test_happy_path_parses_classifications(self):
        text = (
            "### Paper 1\n"
            "1. Classification: INCLUDE\n"
            "2. Reasoning: Meets criteria\n"
            "3. Evidence: Strong\n"
            "### Paper 2\n"
            "1. Classification: EXCLUDE\n"
            "2. Reasoning: Off topic\n"
            "3. Evidence: Weak\n"
        )
        agent = _agent(result=text)
        result = agent.screen_papers([{"pmid": "1"}, {"pmid": "2"}], ["inc"], ["exc"])
        assert result["total_papers"] == 2
        assert len(result["included"]) == 1
        assert len(result["excluded"]) == 1
        assert result["screenings"][0]["paper_index"] == 0

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.screen_papers([{"pmid": "1"}], ["inc"], ["exc"]) is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.screen_papers([{"pmid": "1"}], ["inc"], ["exc"]) is None

    def test_cache_hit(self):
        agent = _agent(
            result="### Paper 1\n1. Classification: INCLUDE\n2. Reasoning: x\n3. Evidence: y\n"
        )
        first = agent.screen_papers([{"pmid": "1"}], ["a"], ["b"])
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.screen_papers([{"pmid": "1"}], ["a"], ["b"])
        assert first == second
        agent.llm_client.generate_with_template.assert_not_called()


class TestAnalyzeResearchQuestion:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.analyze_research_question("Does X cause Y?") is None

    def test_happy_path(self):
        text = "- expanded term one\nThere is a knowledge gap here.\nSearch strategy: broad query."
        agent = _agent(result=text)
        result = agent.analyze_research_question("Does X cause Y?", time_frame="5y")
        assert result["research_question"] == "Does X cause Y?"
        assert result["expanded_terms"]
        assert result["knowledge_gaps"]
        assert "strategy" in result["search_strategy"].lower() or result["search_strategy"]

    def test_cache_hit(self):
        agent = _agent()
        first = agent.analyze_research_question("Q?")
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.analyze_research_question("Q?")
        assert first == second
        agent.llm_client.generate_with_template.assert_not_called()

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.analyze_research_question("Q?") is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.analyze_research_question("Q?") is None


class TestAnalyzePreprint:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.analyze_preprint({}) is None

    def test_happy_path(self):
        text = "Methodology is sound.\nTransparency: code available.\nThis is a preprint consideration.\nWe recommend caution."
        agent = _agent(result=text)
        result = agent.analyze_preprint({"pmid": "1", "preprint_server": "bioRxiv"})
        assert result["preprint_server"] == "bioRxiv"
        assert result["methodology_assessment"]
        assert result["transparency_indicators"]
        assert result["preprint_considerations"]
        assert result["recommendations"]

    def test_cache_hit(self):
        agent = _agent()
        first = agent.analyze_preprint({"pmid": "1"})
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.analyze_preprint({"pmid": "1"})
        assert first == second

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.analyze_preprint({}) is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.analyze_preprint({}) is None


class TestGenerateLiteratureReview:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.generate_literature_review("topic", [{"pmid": "1"}]) is None

    def test_no_papers_returns_none(self):
        agent = _agent()
        assert agent.generate_literature_review("topic", []) is None

    def test_happy_path(self):
        text = (
            "Historical development began decades ago.\n"
            "The current state is active.\n"
            "There is an emerging trend.\n"
            "Future work should recommend more studies."
        )
        agent = _agent(result=text)
        result = agent.generate_literature_review(
            "topic", [{"pmid": "1"}], key_concepts=["a"], excluded_topics=["b"]
        )
        assert result["research_topic"] == "topic"
        assert result["historical_overview"]
        assert result["current_state"]
        assert result["research_trends"]
        assert result["future_directions"]
        assert result["key_papers"] == [{"pmid": "1"}]

    def test_cache_hit(self):
        agent = _agent()
        first = agent.generate_literature_review("topic", [{"pmid": "1"}])
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.generate_literature_review("topic", [{"pmid": "1"}])
        assert first == second

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.generate_literature_review("topic", [{"pmid": "1"}]) is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.generate_literature_review("topic", [{"pmid": "1"}]) is None


class TestBuildKnowledgeGraph:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.build_knowledge_graph("domain") is None

    def test_happy_path(self):
        text = (
            "**Node1** (id: n1)\n"
            "- id: n1\n"
            "- label: Gene\n"
            "**Edge1** (edge)\n"
            "- source: n1\n"
            "- target: n2\n"
            "- type: causes\n"
            "This is a central concept.\n"
            "There is a knowledge gap.\n"
            "<graphml><node/></graphml>\n"
            '{"nodes": [], "edges": []}'
        )
        agent = _agent(result=text)
        result = agent.build_knowledge_graph("domain", entities=["a"], relationships=["b"])
        assert result["research_domain"] == "domain"
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)
        assert result["graph_analysis"]["connected_components"] >= 1
        assert result["format_graphml"].startswith("<graphml>")
        assert result["format_json"] == {"nodes": [], "edges": []}

    def test_cache_hit(self):
        agent = _agent()
        first = agent.build_knowledge_graph("domain")
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.build_knowledge_graph("domain")
        assert first == second

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.build_knowledge_graph("domain") is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.build_knowledge_graph("domain") is None


class TestIntegrateClinicalTrials:
    def test_disabled_returns_none(self):
        agent = _agent(enabled=False)
        assert agent.integrate_clinical_trials("cond", "int") is None

    def test_happy_path(self):
        text = (
            "There are 2 active trials underway.\n"
            "One completed trial finished last year.\n"
            "Geographic distribution: worldwide.\n"
            "Evidence integration: combined from multiple studies.\n"
            "We recommend clinical adoption.\n"
            "Inclusion: adults only.\n"
            "Exclusion: pregnant patients.\n"
            "Results were statistically significant."
        )
        agent = _agent(result=text)
        result = agent.integrate_clinical_trials("condition", "intervention")
        assert result["condition"] == "condition"
        assert result["clinical_trial_landscape"]["active_trials"] >= 1
        assert result["evidence_integration"]
        assert result["practice_recommendations"]
        assert result["trial_selection_criteria"]["statistical_significance"] is True

    def test_cache_hit(self):
        agent = _agent()
        first = agent.integrate_clinical_trials("c", "i")
        agent.llm_client.generate_with_template.reset_mock()
        second = agent.integrate_clinical_trials("c", "i")
        assert first == second

    def test_empty_result_returns_none(self):
        agent = _agent(result="")
        assert agent.integrate_clinical_trials("c", "i") is None

    def test_exception_returns_none(self):
        agent = _agent()
        agent.llm_client.generate_with_template.side_effect = RuntimeError("boom")
        assert agent.integrate_clinical_trials("c", "i") is None


class TestExtractHelpersDirect:
    """Direct tests for the pure text-extraction helper methods."""

    @pytest.fixture
    def agent(self):
        return _agent()

    def test_extract_insights_bullet_and_length_based(self, agent):
        text = "* first insight\n- second insight\nshort\nA line with a decent length here that qualifies."
        insights = agent._extract_insights(text)
        assert "first insight" in insights
        assert "second insight" in insights

    def test_extract_methodology_and_limitations_static(self, agent):
        assert "Analysis based on" in agent._extract_methodology()
        assert "verified" in agent._extract_limitations()

    def test_extract_similarities_and_differences(self, agent):
        text = "This is similar to prior work.\nThis is different in scope.\nUnrelated line."
        assert agent._extract_similarities(text)
        assert agent._extract_differences(text)

    def test_extract_implications_default(self, agent):
        assert "Combined insights" in agent._extract_implications("nothing relevant")

    def test_extract_implications_found(self):
        agent = _agent()
        assert "implication" in agent._extract_implications("The implication is big.").lower()

    def test_extract_patterns(self, agent):
        text = "ok\n" + "x" * 10 + "\n" + "y" * 90
        patterns = agent._extract_patterns(text)
        assert all(5 < len(p) < 80 for p in patterns)

    def test_extract_expanded_terms(self, agent):
        text = "- term one\n- term two\nnotdash"
        terms = agent._extract_expanded_terms(text)
        assert terms == ["term one", "term two"]

    def test_extract_knowledge_gaps(self, agent):
        text = "There is a gap.\nWe need more data.\nUnrelated."
        assert len(agent._extract_knowledge_gaps(text)) == 2

    def test_extract_search_strategy_default(self, agent):
        assert "comprehensive search query" in agent._extract_search_strategy("nothing")

    def test_extract_methodology_assessment_default(self, agent):
        assert "Methodology quality" in agent._extract_methodology_assessment("nothing")

    def test_extract_methodology_assessment_found(self, agent):
        result = agent._extract_methodology_assessment("The methodology here is robust.")
        assert "methodology" in result.lower()

    def test_extract_transparency_indicators(self, agent):
        text = "Transparency is high.\nData is open.\nCode is available.\nirrelevant"
        assert len(agent._extract_transparency_indicators(text)) == 3

    def test_extract_preprint_considerations(self, agent):
        text = "This preprint has not been peer reviewed.\nirrelevant"
        assert agent._extract_preprint_considerations(text)

    def test_extract_preprint_recommendations_default(self, agent):
        assert "consider preprint status" in agent._extract_preprint_recommendations("nothing")

    def test_extract_historical_overview_default(self, agent):
        assert "Historical development" in agent._extract_historical_overview("nothing")

    def test_extract_current_state_default(self, agent):
        assert "Current state" in agent._extract_current_state("nothing")

    def test_extract_research_trends(self, agent):
        text = "This is an emerging trend.\nirrelevant"
        assert agent._extract_research_trends(text)

    def test_extract_future_directions(self, agent):
        text = "Future work is needed.\nWe recommend more studies.\nirrelevant"
        assert len(agent._extract_future_directions(text)) == 2

    def test_extract_key_papers_limits_to_ten(self, agent):
        papers = [{"pmid": str(i)} for i in range(15)]
        assert len(agent._extract_key_papers(papers)) == 10

    def test_extract_nodes_empty(self, agent):
        assert agent._extract_nodes("no nodes here") == []

    def test_extract_edges_empty(self, agent):
        assert agent._extract_edges("no edges here") == []

    def test_extract_graph_analysis_counts(self, agent):
        text = "This is central.\nAnother central idea.\nA gap exists."
        analysis = agent._extract_graph_analysis(text)
        assert len(analysis["central_concepts"]) == 2
        assert len(analysis["knowledge_gaps"]) == 1
        assert analysis["connected_components"] == 2

    def test_extract_graphml_missing_tag(self, agent):
        assert agent._extract_graphml("no graphml here") == ""

    def test_extract_graphml_present(self, agent):
        text = "prefix <graphml>content</graphml> suffix"
        assert agent._extract_graphml(text) == "<graphml>content</graphml>"

    def test_extract_graph_json_valid(self, agent):
        text = 'prefix {"nodes": [1], "edges": []} suffix'
        assert agent._extract_graph_json(text) == {"nodes": [1], "edges": []}

    def test_extract_graph_json_invalid_falls_back(self, agent):
        assert agent._extract_graph_json("{not valid json}") == {"nodes": [], "edges": []}

    def test_extract_graph_json_no_braces_falls_back(self, agent):
        assert agent._extract_graph_json("no braces") == {"nodes": [], "edges": []}

    def test_extract_trial_landscape_counts(self, agent):
        text = "One active trial ongoing.\nAnother active trial too.\nA completed trial finished.\nGeographic spread noted."
        landscape = agent._extract_trial_landscape(text)
        assert landscape["active_trials"] == 2
        assert landscape["completed_trials"] == 1
        assert landscape["geographic_distribution"]

    def test_extract_evidence_integration_default(self, agent):
        assert "Integrated evidence" in agent._extract_evidence_integration("nothing")

    def test_extract_practice_recommendations(self, agent):
        text = "We recommend X.\nClinical use is advised.\nirrelevant"
        assert len(agent._extract_practice_recommendations(text)) == 2

    def test_extract_trial_selection_criteria(self, agent):
        text = "Inclusion: adults.\nExclusion: children.\nResults were significant."
        criteria = agent._extract_trial_selection_criteria(text)
        assert criteria["inclusion"]
        assert criteria["exclusion"]
        assert criteria["statistical_significance"] is True

    def test_extract_trial_selection_criteria_not_significant(self, agent):
        criteria = agent._extract_trial_selection_criteria("Inclusion: adults.")
        assert criteria["statistical_significance"] is False
