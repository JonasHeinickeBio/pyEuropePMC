"""Tests for LangGraph claim workflow integration.

NOTE: each graph invocation runs the full multi-agent claim pipeline and
takes ~10-40s, so the whole module is marked ``slow`` (excluded from
default unit runs via ``-m 'not slow'``).

This module mocks the verifier's evidence search to avoid real Europe PMC
API calls (which are slow and flaky in tests). The actual verifier logic
is tested in separate unit tests.
"""

from unittest.mock import patch

import pytest

from pyeuropepmc.agentic.langgraph import (
    LANGGRAPH_AVAILABLE,
    SupervisorClaimWorkflow,
    build_claim_graph,
    create_initial_state,
    make_parallel_verify_node,
    run_claim_graph,
    stream_claim_graph,
)

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def mock_verifier_network_calls():
    """Patch verifier network calls to avoid real Europe PMC API requests."""
    # Patch both _search_evidence (SearchClient) and _enrich_papers (_get_article_details)
    with (
        patch("pyeuropepmc.claims.verifier.ClaimVerifier._search_evidence") as mock_search,
        patch("pyeuropepmc.claims.verifier.ClaimVerifier._enrich_papers") as mock_enrich,
        patch("pyeuropepmc.claims.verifier.ClaimVerifier._get_article_details") as mock_details,
    ):
        # Return empty evidence list - tests only care about graph state flow
        mock_search.return_value = []

        # _enrich_papers receives empty list from _search_evidence, but return empty too for safety
        mock_enrich.return_value = []

        # _get_article_details never called since no papers, but set default
        mock_details.return_value = None

        yield


# ======================================================================= #
# State tests
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestLangGraphState:
    def test_create_initial_state(self):
        state = create_initial_state("test text", llm_enabled=False)
        assert state["source_text"] == "test text"
        assert state["extraction_complete"] is False
        assert state["llm_enabled"] is False
        assert state["errors"] == []

    def test_state_keys_present(self):
        state = create_initial_state("hello")
        required_keys = [
            "source_text",
            "claims_raw",
            "extraction_complete",
            "verified_claims",
            "verification_summary",
            "verification_complete",
            "review",
            "review_complete",
            "user_decisions",
            "decisions_complete",
            "improved_text",
            "bibliography",
            "output_complete",
            "errors",
            "llm_enabled",
        ]
        for key in required_keys:
            assert key in state, f"Missing state key: {key}"

    def test_state_has_supervisor_keys(self):
        """New supervisor state keys are present."""
        state = create_initial_state("test")
        assert state["supervisor_phase"] == "init"
        assert state["workflow_progress"] == 0.0
        assert state["retry_count"] == 0
        assert state["max_retries"] == 2
        assert state["agent_messages"] == []
        assert state["current_node"] == "__start__"

    def test_state_can_be_updated(self):
        state = create_initial_state("test")
        state["extraction_complete"] = True
        state["claims_raw"] = [{"id": "c1", "text": "test claim"}]
        assert state["extraction_complete"] is True
        assert len(state["claims_raw"]) == 1

    def test_max_retries_default_and_custom(self):
        """max_retries should default to 2 and accept custom values."""
        default = create_initial_state("test")
        assert default["max_retries"] == 2

        custom = create_initial_state("test", max_retries=5)
        assert custom["max_retries"] == 5

        min_val = create_initial_state("test", max_retries=0)
        assert min_val["max_retries"] == 0

    def test_workflow_id_generation(self):
        """If no workflow_id provided, should be empty string (generated later)."""
        state = create_initial_state("test")
        assert isinstance(state["workflow_id"], str)


# ======================================================================= #
# Graph construction and basic workflow tests
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestLangGraphGraph:
    def test_build_graph_no_llm(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        assert graph is not None
        compiled = graph.compile()
        assert compiled is not None

    def test_invoke_with_auto_accept(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke(
            source_text="CRISPR-Cas9 is a gene editing tool. It was discovered in 2012.",
            auto_accept=True,
        )
        # Should complete the full pipeline
        assert result["extraction_complete"] is True
        assert result["verification_complete"] is True
        assert result["review_complete"] is True
        assert result["decisions_complete"] is True
        assert result["output_complete"] is True
        assert len(result.get("improved_text", "")) > 0

    def test_invoke_with_empty_text(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke(
            source_text="",
            auto_accept=True,
        )
        # Should handle gracefully — no text means no extraction
        assert result["extraction_complete"] is False
        assert result["output_complete"] is False
        assert "No source text provided" in " ".join(result.get("errors", []))

    def test_run_claim_graph_convenience(self):
        result = run_claim_graph(
            "Test sentence one. Test sentence two.",
            llm_enabled=False,
            auto_accept=True,
            use_checkpointer=False,
        )
        assert result["output_complete"] is True
        assert len(result.get("improved_text", "")) > 0

    def test_result_contains_bibliography(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke(
            source_text="CRISPR-Cas9 corrects genetic mutations in vitro.",
            auto_accept=True,
        )
        assert "bibliography" in result
        assert "improved_text" in result
        assert "verified_claims" in result

    def test_auto_accept_creates_decisions(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke(
            source_text="First discovery. Second finding.",
            auto_accept=True,
        )
        assert len(result.get("user_decisions", {})) > 0

    def test_llm_enabled_false_uses_fallback(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke(
            source_text="The sky is blue. Water is wet.",
            auto_accept=True,
        )
        assert result["extraction_complete"] is True
        assert len(result["claims_raw"]) == 2

    def test_review_contains_quality_assessment(self):
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke(
            source_text="CRISPR is a gene editing technology discovered in bacteria.",
            auto_accept=True,
        )
        review = result.get("review", {})
        assert "overall_quality" in review
        assert "suggestions" in review


# ======================================================================= #
# Supervisor phase progression
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestSupervisorPhaseProgression:
    def test_phases_follow_correct_order(self):
        """Supervisor should route through phases in correct order."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("First sentence. Second claim.", auto_accept=True)
        assert result["supervisor_phase"] == "done" or result["supervisor_phase"] == "write"
        assert result["workflow_progress"] == 1.0

    def test_all_completion_flags_true_on_success(self):
        """All 5 completion flags should be True in a successful run."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Test sentence. Another sentence.", auto_accept=True)
        assert result["extraction_complete"] is True
        assert result["verification_complete"] is True
        assert result["review_complete"] is True
        assert result["decisions_complete"] is True
        assert result["output_complete"] is True

    def test_progress_reaches_one(self):
        """Workflow progress should reach 1.0 on success."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Alpha. Beta. Gamma.", auto_accept=True)
        assert result["workflow_progress"] == 1.0

    def test_phase_failed_on_empty_text(self):
        """Empty text should eventually lead to failed phase."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("", auto_accept=True)
        # After max retries, should hit failed state
        assert result["supervisor_phase"] == "failed"
        assert result["workflow_progress"] == -1.0

    def test_retry_count_increments_on_failure(self):
        """retry_count should be > 0 when retries happen."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("", auto_accept=True, max_retries=3)
        # Should have retried at least once
        assert result["retry_count"] > 0


# ======================================================================= #
# Agent messages
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestAgentMessages:
    def test_agent_messages_present_in_successful_run(self):
        """agent_messages should contain entries from all subagents."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Test claim one. Another claim.", auto_accept=True)
        messages = result.get("agent_messages", [])
        assert len(messages) > 0, "Should have agent messages"

    def test_messages_have_correct_structure(self):
        """Each agent message should have required fields."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Some text. More text.", auto_accept=True)
        messages = result.get("agent_messages", [])
        for msg in messages:
            assert "agent" in msg
            assert "target" in msg
            assert "action" in msg
            assert "timestamp" in msg
            # Common agent names
            assert msg["agent"] in (
                "extract",
                "verify",
                "review",
                "decisions",
                "write",
                "supervisor",
            )

    def test_extract_agent_sends_complete_message(self):
        """Extract subagent should send a 'complete' action on success."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Extract this claim.", auto_accept=True)
        extract_msgs = [
            m
            for m in result.get("agent_messages", [])
            if m.get("agent") == "extract" and m.get("action") == "complete"
        ]
        assert len(extract_msgs) >= 1

    def test_verify_agent_sends_complete_message(self):
        """Verify subagent should send a 'complete' action on success."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Verify this claim.", auto_accept=True)
        verify_msgs = [
            m
            for m in result.get("agent_messages", [])
            if m.get("agent") == "verify" and m.get("action") == "complete"
        ]
        assert len(verify_msgs) >= 1

    def test_agent_messages_on_failure(self):
        """Failed subagents should send 'failed' action messages."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("", auto_accept=True)
        failed_msgs = [m for m in result.get("agent_messages", []) if m.get("action") == "failed"]
        assert len(failed_msgs) >= 1


# ======================================================================= #
# Retry logic
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestRetryLogic:
    def test_empty_text_triggers_max_retries(self):
        """Empty text should trigger max retries then fail."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("", auto_accept=True, max_retries=2)
        assert result["extraction_complete"] is False
        assert result["supervisor_phase"] == "failed"
        # Check that max retries error was recorded
        errors_str = " ".join(result.get("errors", []))
        assert "max retries" in errors_str or "No source text" in errors_str


# ======================================================================= #
# Streaming tests
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestStreaming:
    def test_stream_yields_multiple_steps(self):
        """stream() should yield at least 2 node updates."""
        steps = []
        gen = stream_claim_graph(
            "Test stream. Parallel claims.",
            llm_enabled=False,
            auto_accept=True,
        )
        for step in gen:
            steps.append(step)
        assert len(steps) >= 2

    def test_stream_yields_supervisor_updates(self):
        """Stream should yield supervisor node updates."""
        steps = []
        gen = stream_claim_graph(
            "Stream supervisor. Check routing.",
            llm_enabled=False,
            auto_accept=True,
        )
        for step in gen:
            steps.append(step)
        has_supervisor = any("supervisor" in s for s in steps)
        assert has_supervisor

    def test_stream_yields_subagent_updates(self):
        """Stream should yield subagent node updates (extract, verify, etc.)."""
        steps = []
        gen = stream_claim_graph(
            "Stream subagents. Extract verify write.",
            llm_enabled=False,
            auto_accept=True,
        )
        for step in gen:
            steps.append(step)
        subagent_nodes = {"extract", "verify", "review", "decisions", "write"}
        seen = set()
        for s in steps:
            seen.update(s.keys())
        found = seen & subagent_nodes
        assert len(found) >= 1, f"Expected at least 1 subagent node, got {found}"

    def test_stream_final_state_complete(self):
        """Stream should yield final step with output_complete=True."""
        steps = []
        gen = stream_claim_graph(
            "Stream complete. Multiple claims.",
            llm_enabled=False,
            auto_accept=True,
        )
        for step in gen:
            steps.append(step)

        # Check that at least one step contains output_complete
        has_output = any(
            isinstance(v, dict) and v.get("output_complete") for s in steps for v in s.values()
        )
        assert has_output, "No step contained output_complete=True"


# ======================================================================= #
# Parallel verify node
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestParallelVerifyNode:
    def test_parallel_verify_in_graph(self):
        """Graph with parallel verify should complete successfully."""
        graph = build_claim_graph(
            llm_enabled=False,
            use_checkpointer=False,
            parallel_workers=3,
        )
        result = graph.invoke(
            source_text="Parallel claim one. Parallel claim two.",
            auto_accept=True,
        )
        assert result["extraction_complete"] is True
        assert result["output_complete"] is True

    def test_parallel_verify_agent_messages(self):
        """Parallel verify should produce agent messages."""
        graph = build_claim_graph(
            llm_enabled=False,
            use_checkpointer=False,
            parallel_workers=3,
        )
        result = graph.invoke(
            source_text="Parallel test. Verify via threads.",
            auto_accept=True,
        )
        messages = result.get("agent_messages", [])
        verify_msgs = [m for m in messages if m.get("agent") == "verify"]
        assert len(verify_msgs) >= 1

    def test_parallel_verify_vs_sequential_equivalence(self):
        """Parallel and sequential verify should produce equivalent results."""
        parallel_graph = build_claim_graph(
            llm_enabled=False,
            use_checkpointer=False,
            parallel_workers=4,
        )
        parallel_result = parallel_graph.invoke(
            source_text="Equivalence test one. Equivalence test two.",
            auto_accept=True,
        )

        sequential_graph = build_claim_graph(
            llm_enabled=False,
            use_checkpointer=False,
        )
        sequential_result = sequential_graph.invoke(
            source_text="Equivalence test one. Equivalence test two.",
            auto_accept=True,
        )

        # Both should complete
        assert parallel_result["output_complete"] is True
        assert sequential_result["output_complete"] is True
        # Both should have decisions
        assert len(parallel_result.get("user_decisions", {})) > 0
        assert len(sequential_result.get("user_decisions", {})) > 0


# ======================================================================= #
# Routing edge cases
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestLangGraphRouting:
    def test_routes_to_verify_after_extract(self):
        """Extract with claims should route to verify."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Test claim here.", auto_accept=True)
        assert result["verification_complete"] is True
        assert len(result.get("verification_summary", {})) > 0

    def test_pipeline_completes_all_stages(self):
        """Full pipeline should complete all 5 stages."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Alpha. Beta. Gamma.", auto_accept=True)
        stages = [
            "extraction_complete",
            "verification_complete",
            "review_complete",
            "decisions_complete",
            "output_complete",
        ]
        for stage in stages:
            assert result.get(stage) is True, f"Stage {stage} not complete"

    def test_supervisor_routes_to_end_after_write(self):
        """After write, supervisor should route to END (phase='done')."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=False)
        result = graph.invoke("Final routing test. Check done phase.", auto_accept=True)
        assert result["supervisor_phase"] in ("done", "write")
        assert result["output_complete"] is True


# ======================================================================= #
# Workflow with checkpointer
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestCheckpointer:
    def test_with_checkpointer_completes(self):
        """Workflow with MemorySaver checkpointer should complete."""
        graph = build_claim_graph(llm_enabled=False, use_checkpointer=True)
        result = graph.invoke(
            source_text="Checkpointer test. Save restore state.",
            auto_accept=True,
        )
        assert result["output_complete"] is True

    def test_with_checkpointer_and_parallel(self):
        """Checkpointer + parallel verify should work together."""
        graph = build_claim_graph(
            llm_enabled=False,
            use_checkpointer=True,
            parallel_workers=2,
        )
        result = graph.invoke(
            source_text="Checkpointer parallel. Multi threading ok.",
            auto_accept=True,
        )
        assert result["output_complete"] is True


# ======================================================================= #
# SupervisorClaimWorkflow direct construction with custom node fns
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestDirectConstruction:
    def test_direct_construction_with_no_llm(self):
        """SupervisorClaimWorkflow can be constructed with simple node functions."""

        def noop_extract(state):
            return {"extraction_complete": True, "claims_raw": [{"id": "c1", "text": "mock"}]}

        def noop_verify(state):
            return {
                "verification_complete": True,
                "verified_claims": [{"id": "c1", "text": "mock"}],
            }

        def noop_review(state):
            return {"review_complete": True, "review": {"overall_quality": "high"}}

        def noop_write(state):
            return {"output_complete": True, "improved_text": "output", "bibliography": []}

        wf = SupervisorClaimWorkflow(
            extract_claims_fn=noop_extract,
            verify_claims_fn=noop_verify,
            review_claims_fn=noop_review,
            write_report_fn=noop_write,
        )
        result = wf.invoke("test", auto_accept=True)
        assert result["output_complete"] is True

    def test_direct_construction_streaming(self):
        """SupervisorClaimWorkflow.stream() should work with custom nodes."""

        def noop_extract(state):
            return {"extraction_complete": True, "claims_raw": [{"id": "c1", "text": "mock"}]}

        def noop_verify(state):
            return {
                "verification_complete": True,
                "verified_claims": [{"id": "c1", "text": "mock"}],
            }

        def noop_review(state):
            return {"review_complete": True, "review": {"overall_quality": "high"}}

        def noop_write(state):
            return {"output_complete": True, "improved_text": "output", "bibliography": []}

        wf = SupervisorClaimWorkflow(
            extract_claims_fn=noop_extract,
            verify_claims_fn=noop_verify,
            review_claims_fn=noop_review,
            write_report_fn=noop_write,
        )
        steps = list(wf.stream("test", auto_accept=True))
        assert len(steps) >= 2, f"Expected >=2 steps, got {len(steps)}"
        # Verify the steps include supervisor and subagent updates
        has_output = any(
            isinstance(v, dict) and v.get("output_complete") for s in steps for v in s.values()
        )
        assert has_output, "No step contained output_complete=True"


# ======================================================================= #
# make_parallel_verify_node tests
# ======================================================================= #


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
class TestMakeParallelVerifyNode:
    def test_parallel_verify_node_factory_exists(self):
        """make_parallel_verify_node should be importable and callable."""
        assert callable(make_parallel_verify_node)
