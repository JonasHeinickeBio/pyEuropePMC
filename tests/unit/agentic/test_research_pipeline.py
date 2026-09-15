"""
Tests for ResearchPipeline.

This module tests:
- Pipeline initialization and configuration
- Step management and execution
- Agent/tool assignment
- State tracking and progression
- Result aggregation
"""

from unittest.mock import Mock

from pyeuropepmc.agentic.pipeline import (
    PipelineStage,
    PipelineState,
    PipelineStep,
    ResearchPipeline,
)


class TestResearchPipeline:
    """Tests for ResearchPipeline class."""

    def test_init_sets_default_parameters(self):
        """Test that ResearchPipeline initializes with default parameters."""
        pipeline = ResearchPipeline()

        assert pipeline.name == "research_pipeline"
        assert pipeline.description == ""
        assert pipeline.pipeline_id is not None
        assert pipeline.state.status == "pending"
        assert len(pipeline.state.stages) == 0
        assert len(pipeline.state.steps) == 0

    def test_init_with_custom_parameters(self):
        """Test that ResearchPipeline initializes with custom parameters."""
        pipeline = ResearchPipeline(
            name="test_pipeline",
            description="Test research pipeline",
        )

        assert pipeline.name == "test_pipeline"
        assert pipeline.description == "Test research pipeline"

    def test_add_stage(self):
        """Test adding a stage to the pipeline."""
        pipeline = ResearchPipeline()

        pipeline.add_stage(PipelineStage.INITIALIZE)
        pipeline.add_stage(PipelineStage.PLANNING)

        assert PipelineStage.INITIALIZE in pipeline.state.stages
        assert PipelineStage.PLANNING in pipeline.state.stages
        assert len(pipeline.state.stages) == 2

    def test_add_stage_duplicate(self):
        """Test that adding duplicate stages is handled."""
        pipeline = ResearchPipeline()

        pipeline.add_stage(PipelineStage.INITIALIZE)
        pipeline.add_stage(PipelineStage.INITIALIZE)

        # Should only appear once
        assert pipeline.state.stages.count(PipelineStage.INITIALIZE) == 1

    def test_add_step(self):
        """Test adding a step to the pipeline."""
        pipeline = ResearchPipeline()

        pipeline.add_step(
            name="search_papers",
            description="Search for relevant papers",
            input_keys=["query"],
            output_keys=["papers"],
        )

        assert len(pipeline.state.steps) == 1
        step = pipeline.state.steps[0]
        assert step.name == "search_papers"
        assert step.description == "Search for relevant papers"
        assert step.input_keys == ["query"]
        assert step.output_keys == ["papers"]

    def test_add_step_with_agent(self):
        """Test adding a step with an agent assignment."""
        pipeline = ResearchPipeline()

        pipeline.add_step(
            name="analyze_papers",
            agent_name="reviewer",
            description="Analyze papers",
        )

        step = pipeline.state.steps[0]
        assert step.agent_name == "reviewer"
        assert step.tool_name is None

    def test_add_step_with_tool(self):
        """Test adding a step with a tool assignment."""
        pipeline = ResearchPipeline()

        pipeline.add_step(
            name="extract_data",
            tool_name="text_extractor",
            description="Extract data from papers",
        )

        step = pipeline.state.steps[0]
        assert step.tool_name == "text_extractor"
        assert step.agent_name is None

    def test_set_step_agent(self):
        """Test setting agent for a step."""
        pipeline = ResearchPipeline()

        pipeline.add_step(name="search")
        step_id = pipeline.state.steps[0].id

        result = pipeline.set_step_agent(step_id, "planner")

        assert result is True
        assert pipeline.state.steps[0].agent_name == "planner"

    def test_set_step_agent_not_found(self):
        """Test setting agent for non-existent step."""
        pipeline = ResearchPipeline()

        result = pipeline.set_step_agent("nonexistent_id", "planner")

        assert result is False

    def test_set_step_tool(self):
        """Test setting tool for a step."""
        pipeline = ResearchPipeline()

        pipeline.add_step(name="extract")
        step_id = pipeline.state.steps[0].id

        result = pipeline.set_step_tool(step_id, "extractor")

        assert result is True
        assert pipeline.state.steps[0].tool_name == "extractor"

    def test_set_step_tool_not_found(self):
        """Test setting tool for non-existent step."""
        pipeline = ResearchPipeline()

        result = pipeline.set_step_tool("nonexistent_id", "extractor")

        assert result is False

    def test_set_step_input(self):
        """Test setting input keys for a step."""
        pipeline = ResearchPipeline()

        pipeline.add_step(name="analyze")
        step_id = pipeline.state.steps[0].id

        result = pipeline.set_step_input(step_id, ["paper", "query"])

        assert result is True
        assert pipeline.state.steps[0].input_keys == ["paper", "query"]

    def test_set_step_output(self):
        """Test setting output keys for a step."""
        pipeline = ResearchPipeline()

        pipeline.add_step(name="analyze")
        step_id = pipeline.state.steps[0].id

        result = pipeline.set_step_output(step_id, ["results"])

        assert result is True
        assert pipeline.state.steps[0].output_keys == ["results"]

    def test_add_step_output(self):
        """Test adding output keys for a step."""
        pipeline = ResearchPipeline()

        pipeline.add_step(name="analyze")
        step_id = pipeline.state.steps[0].id

        result = pipeline.set_step_output(step_id, ["results", "summary"])

        assert result is True
        assert pipeline.state.steps[0].output_keys == ["results", "summary"]

    def test_get_step_input(self):
        """Test getting step input from global state."""
        pipeline = ResearchPipeline()

        pipeline.add_step(
            name="analyze",
            input_keys=["query", "limit"],
        )

        pipeline.state.global_state["query"] = "cancer treatment"
        pipeline.state.global_state["limit"] = 10
        pipeline.state.global_state["extra"] = "should not be included"

        step = pipeline.state.steps[0]
        input_data = pipeline.get_step_input(step)

        assert "query" in input_data
        assert input_data["query"] == "cancer treatment"
        assert "limit" in input_data
        assert input_data["limit"] == 10
        assert "extra" not in input_data

    def test_get_step_input_empty(self):
        """Test getting step input when keys not in global state."""
        pipeline = ResearchPipeline()

        pipeline.add_step(name="analyze", input_keys=["missing_key"])

        step = pipeline.state.steps[0]
        input_data = pipeline.get_step_input(step)

        assert input_data == {}

    def test_register_progress_callback(self):
        """Test registering progress callback."""
        pipeline = ResearchPipeline()
        callback = Mock()

        pipeline.register_progress_callback(callback)

        assert len(pipeline._progress_callbacks) == 1
        assert pipeline._progress_callbacks[0] == callback

    def test_register_step_callback(self):
        """Test registering step callback."""
        pipeline = ResearchPipeline()
        callback = Mock()

        pipeline.register_step_callback(callback)

        assert len(pipeline._step_callbacks) == 1
        assert pipeline._step_callbacks[0] == callback

    def test_get_step_tree(self):
        """Test getting step tree visualization."""
        pipeline = ResearchPipeline()
        pipeline.add_step(name="step1", description="First step")
        pipeline.add_step(name="step2", description="Second step")

        tree = pipeline.get_step_tree()

        assert "Pipeline: research_pipeline" in tree
        assert "step1" in tree
        assert "First step" in tree
        assert "step2" in tree
        assert "Second step" in tree

    def test_to_dict(self):
        """Test converting pipeline to dictionary."""
        pipeline = ResearchPipeline(
            name="test_pipeline",
            description="Test description",
        )
        pipeline.add_stage(PipelineStage.INITIALIZE)
        pipeline.add_step(name="step1")

        data = pipeline.to_dict()

        assert data["name"] == "test_pipeline"
        assert data["description"] == "Test description"
        assert data["pipeline_id"] == pipeline.pipeline_id
        assert "orchestrator_agents" in data
        assert "tool_registry_tools" in data

    def test_from_dict(self):
        """Test creating pipeline from dictionary."""
        data = {
            "name": "restored_pipeline",
            "description": "Restored pipeline",
        }

        pipeline = ResearchPipeline.from_dict(data)

        assert pipeline.name == "restored_pipeline"
        assert pipeline.description == "Restored pipeline"

    def test_method_chaining(self):
        """Test that methods return self for chaining."""
        pipeline = ResearchPipeline()

        result = pipeline.add_stage(PipelineStage.INITIALIZE).add_step(
            name="test",
            description="Test step",
        )

        assert result is pipeline
        assert len(pipeline.state.stages) == 1
        assert len(pipeline.state.steps) == 1


class TestResearchPipelineIntegration:
    """Integration tests for ResearchPipeline."""

    def test_complex_workflow(self):
        """Test a complex multi-step workflow."""
        pipeline = ResearchPipeline(
            name="complex_workflow",
            description="Multiple stages and steps",
        )

        # Build a realistic workflow
        pipeline.add_stage(PipelineStage.PLANNING)
        pipeline.add_step(
            name="define_research_question",
            description="Define the research question",
            output_keys=["research_question"],
        ).add_step(
            name="search_papers",
            description="Search for papers",
            input_keys=["research_question"],
            output_keys=["papers"],
        )

        pipeline.add_stage(PipelineStage.EXECUTION)
        pipeline.add_step(
            name="screen_papers",
            description="Screen papers for relevance",
            input_keys=["papers"],
            output_keys=["relevant_papers"],
        ).add_step(
            name="extract_data",
            description="Extract data from papers",
            input_keys=["relevant_papers"],
            output_keys=["extracted_data"],
        )

        pipeline.add_stage(PipelineStage.SYNTHESIS)
        pipeline.add_step(
            name="synthesize_findings",
            description="Synthesize findings",
            input_keys=["extracted_data"],
            output_keys=["synthesis"],
        )

        # Verify structure
        assert len(pipeline.state.stages) == 3
        assert len(pipeline.state.steps) == 5

        # Check step inputs/outputs
        search_step = next(s for s in pipeline.state.steps if s.name == "search_papers")
        assert search_step.input_keys == ["research_question"]

        screen_step = next(s for s in pipeline.state.steps if s.name == "screen_papers")
        assert screen_step.input_keys == ["papers"]

        synthesis_step = next(s for s in pipeline.state.steps if s.name == "synthesize_findings")
        assert synthesis_step.input_keys == ["extracted_data"]


class TestPipelineStep:
    """Tests for PipelineStep class."""

    def test_init(self):
        """Test PipelineStep initialization."""
        step = PipelineStep(
            id="step1",
            name="test_step",
            description="Test step",
        )

        assert step.id == "step1"
        assert step.name == "test_step"
        assert step.description == "Test step"
        assert step.status == "pending"
        assert step.agent_name is None
        assert step.tool_name is None

    def test_input_output_defaults(self):
        """Test that input/output keys default to empty lists."""
        step = PipelineStep(id="step1", name="test")

        assert step.input_keys == []
        assert step.output_keys == []


class TestPipelineState:
    """Tests for PipelineState class."""

    def test_init(self):
        """Test PipelineState initialization."""
        state = PipelineState(
            pipeline_id="pipeline1",
            name="test_pipeline",
            description="Test pipeline",
            stages=[],
            steps=[],
        )

        assert state.pipeline_id == "pipeline1"
        assert state.name == "test_pipeline"
        assert state.description == "Test pipeline"
        assert state.stages == []
        assert state.steps == []
        assert state.status == "pending"
