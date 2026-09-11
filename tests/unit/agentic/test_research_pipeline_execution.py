"""Additional unit tests for pyeuropepmc.agentic.pipeline.ResearchPipeline.

Covers execute_step/_execute_agent/_execute_tool/run/_aggregate_results/
_finalize_pipeline/_notify_progress and the set_step_input/output
"not found" branches, which are not exercised by the existing
tests/unit/agentic/test_research_pipeline.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyeuropepmc.agentic.pipeline import PipelineStage, PipelineStep, ResearchPipeline


def _pipeline() -> ResearchPipeline:
    return ResearchPipeline(name="test_pipeline")


class TestPipelineStepToDict:
    def test_to_dict_with_all_fields(self):
        step = PipelineStep(
            id="s1",
            name="Step 1",
            agent_name="agent1",
            tool_name=None,
            description="desc",
            input_keys=["a"],
            output_keys=["b"],
        )
        d = step.to_dict()
        assert d["id"] == "s1"
        assert d["agent_name"] == "agent1"
        assert d["created_at"] is not None

    def test_to_dict_none_dates(self):
        step = PipelineStep(id="s1", name="Step 1", created_at=None, completed_at=None)
        d = step.to_dict()
        assert d["created_at"] is None
        assert d["completed_at"] is None


class TestSetStepInputOutputNotFound:
    def test_set_step_input_not_found(self):
        pipeline = _pipeline()
        assert pipeline.set_step_input("missing", ["a"]) is False

    def test_set_step_output_not_found(self):
        pipeline = _pipeline()
        assert pipeline.set_step_output("missing", ["a"]) is False


class TestExecuteStep:
    def test_no_agent_or_tool_falls_back(self):
        pipeline = _pipeline()
        step = PipelineStep(id="s1", name="Step 1")
        result = pipeline.execute_step(step)
        assert result["status"] == "completed"
        assert step.status == "completed"

    def test_agent_execution_updates_global_state(self):
        pipeline = _pipeline()
        agent = MagicMock()
        agent.execute.return_value = {"output_key": "value"}
        pipeline.orchestrator.agents["agent1"] = agent
        step = PipelineStep(
            id="s1", name="Step 1", agent_name="agent1", output_keys=["output_key"]
        )
        result = pipeline.execute_step(step)
        assert result == {"output_key": "value"}
        assert pipeline.state.global_state["output_key"] == "value"
        assert step.status == "completed"

    def test_tool_execution(self):
        pipeline = _pipeline()

        @pipeline.tool_registry.register("mytool")
        def mytool(x: int) -> dict:
            return {"result": x * 2}

        step = PipelineStep(id="s1", name="Step 1", tool_name="mytool", input_keys=["x"])
        pipeline.state.global_state["x"] = 5
        result = pipeline.execute_step(step)
        assert result == {"result": 10}

    def test_agent_exception_is_caught_inside_execute_agent(self):
        # _execute_agent catches the exception itself and returns a "failed"
        # result dict, so execute_step's own try/except never fires and the
        # step is still marked "completed" (only the *result* reports failure).
        pipeline = _pipeline()
        agent = MagicMock()
        agent.execute.side_effect = RuntimeError("boom")
        pipeline.orchestrator.agents["agent1"] = agent
        step = PipelineStep(id="s1", name="Step 1", agent_name="agent1")
        result = pipeline.execute_step(step)
        assert result["status"] == "failed"
        assert step.status == "completed"

    def test_get_step_input_exception_marks_step_failed(self):
        pipeline = _pipeline()
        step = PipelineStep(id="s1", name="Step 1")
        with patch.object(pipeline, "get_step_input", side_effect=RuntimeError("boom")):
            result = pipeline.execute_step(step)
        assert result["status"] == "failed"
        assert step.status == "failed"

    def test_step_callback_invoked(self):
        pipeline = _pipeline()
        calls = []
        pipeline.register_step_callback(lambda s: calls.append(s.id))
        step = PipelineStep(id="s1", name="Step 1")
        pipeline.execute_step(step)
        assert calls == ["s1"]

    def test_step_callback_exception_swallowed(self):
        pipeline = _pipeline()
        pipeline.register_step_callback(lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
        step = PipelineStep(id="s1", name="Step 1")
        result = pipeline.execute_step(step)
        assert result["status"] == "completed"

    def test_output_key_not_in_result_not_stored(self):
        pipeline = _pipeline()
        agent = MagicMock()
        agent.execute.return_value = {"other_key": "value"}
        pipeline.orchestrator.agents["agent1"] = agent
        step = PipelineStep(
            id="s1", name="Step 1", agent_name="agent1", output_keys=["missing_key"]
        )
        pipeline.execute_step(step)
        assert "missing_key" not in pipeline.state.global_state


class TestExecuteAgent:
    def test_agent_not_found_returns_skipped(self):
        pipeline = _pipeline()
        result = pipeline._execute_agent("nonexistent", {})
        assert result["status"] == "skipped"

    def test_agent_exception_returns_failed(self):
        pipeline = _pipeline()
        agent = MagicMock()
        agent.execute.side_effect = RuntimeError("boom")
        pipeline.orchestrator.agents["a1"] = agent
        result = pipeline._execute_agent("a1", {})
        assert result["status"] == "failed"
        assert "boom" in result["error"]

    def test_agent_success(self):
        pipeline = _pipeline()
        agent = MagicMock()
        agent.execute.return_value = {"status": "completed"}
        pipeline.orchestrator.agents["a1"] = agent
        result = pipeline._execute_agent("a1", {"x": 1})
        agent.execute.assert_called_once_with(x=1)
        assert result == {"status": "completed"}


class TestExecuteTool:
    def test_tool_not_found_returns_skipped(self):
        pipeline = _pipeline()
        result = pipeline._execute_tool("nonexistent", {})
        assert result["status"] == "skipped"

    def test_tool_exception_returns_failed(self):
        pipeline = _pipeline()

        @pipeline.tool_registry.register("failing_tool")
        def failing_tool():
            raise RuntimeError("tool boom")

        result = pipeline._execute_tool("failing_tool", {})
        assert result["status"] == "failed"
        assert "tool boom" in result["error"]

    def test_tool_returning_non_dict_wrapped(self):
        pipeline = _pipeline()

        @pipeline.tool_registry.register("plain_tool")
        def plain_tool():
            return "plain result"

        result = pipeline._execute_tool("plain_tool", {})
        assert result == {"result": "plain result"}

    def test_tool_returning_dict_passthrough(self):
        pipeline = _pipeline()

        @pipeline.tool_registry.register("dict_tool")
        def dict_tool():
            return {"a": 1}

        result = pipeline._execute_tool("dict_tool", {})
        assert result == {"a": 1}


class TestRun:
    def test_run_executes_all_stages_and_steps(self):
        pipeline = _pipeline()
        pipeline.add_stage(PipelineStage.EXECUTION)
        agent = MagicMock()
        agent.execute.return_value = {"status": "completed", "out": "v"}
        pipeline.orchestrator.agents["a1"] = agent
        pipeline.add_step(
            "step1",
            agent_name="a1",
            output_keys=["out"],
            metadata={"stage": "execution"},
        )
        result = pipeline.run()
        assert result["status"] == "completed"
        assert pipeline.state.global_state["out"] == "v"

    def test_run_with_initial_state(self):
        pipeline = _pipeline()
        result = pipeline.run(initial_state={"seed": "value"})
        assert pipeline.state.global_state["seed"] == "value"
        assert result["status"] == "completed"

    def test_run_stops_on_failed_step(self):
        pipeline = _pipeline()
        pipeline.add_stage(PipelineStage.EXECUTION)
        agent = MagicMock()
        agent.execute.side_effect = RuntimeError("boom")
        pipeline.orchestrator.agents["a1"] = agent
        pipeline.add_step("step1", agent_name="a1", metadata={"stage": "execution"})
        result = pipeline.run()
        assert result["status"] == "failed"

    def test_run_no_stages_or_steps(self):
        pipeline = _pipeline()
        result = pipeline.run()
        assert result["status"] == "completed"
        assert result["step_results"] == {}

    def test_run_notifies_progress_callbacks(self):
        pipeline = _pipeline()
        pipeline.add_stage(PipelineStage.EXECUTION)
        pipeline.add_step("step1", metadata={"stage": "execution"})
        progress_calls = []
        pipeline.register_progress_callback(lambda p, m: progress_calls.append((p, m)))
        pipeline.run()
        assert len(progress_calls) > 0

    def test_run_exception_during_stage_iteration_returns_failed(self):
        pipeline = _pipeline()
        pipeline.state.stages = None  # will raise TypeError when iterated
        result = pipeline.run()
        assert result["status"] == "failed"


class TestAggregateResults:
    def test_counts_completed_and_failed(self):
        pipeline = _pipeline()
        step1 = PipelineStep(id="s1", name="Step 1", status="completed", result={"a": 1})
        step2 = PipelineStep(id="s2", name="Step 2", status="failed")
        pipeline.state.steps = [step1, step2]
        aggregated = pipeline._aggregate_results()
        assert aggregated["steps_completed"] == 1
        assert aggregated["steps_failed"] == 1
        assert aggregated["step_results"] == {"Step 1": {"a": 1}}

    def test_step_without_result_excluded(self):
        pipeline = _pipeline()
        pipeline.state.steps = [PipelineStep(id="s1", name="Step 1", result=None)]
        aggregated = pipeline._aggregate_results()
        assert aggregated["step_results"] == {}


class TestFinalizePipeline:
    def test_default_empty_final_result(self):
        pipeline = _pipeline()
        result = pipeline._finalize_pipeline()
        assert result["pipeline_name"] == "test_pipeline"
        assert "steps" in result
        assert "global_state" in result

    def test_merges_final_result(self):
        pipeline = _pipeline()
        result = pipeline._finalize_pipeline({"custom": "value"})
        assert result["custom"] == "value"


class TestNotifyProgress:
    def test_calls_all_callbacks(self):
        pipeline = _pipeline()
        calls = []
        pipeline.register_progress_callback(lambda p, m: calls.append((p, m)))
        pipeline._notify_progress(0.5, "halfway")
        assert calls == [(0.5, "halfway")]

    def test_callback_exception_is_swallowed(self):
        pipeline = _pipeline()
        pipeline.register_progress_callback(
            lambda p, m: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        pipeline._notify_progress(1.0, "done")  # should not raise
