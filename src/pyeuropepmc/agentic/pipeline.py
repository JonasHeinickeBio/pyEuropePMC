"""
Research pipeline for workflow chaining.

This module provides:
- ResearchPipeline class for chaining agents and tools
- Workflow state management
- Pipeline visualization and tracking
- Results aggregation and synthesis

Inspired by gpt-researcher's workflow approach.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any
import uuid

from pyeuropepmc.agentic.orchestrator import AgentOrchestrator
from pyeuropepmc.agentic.registry import ToolRegistry
from pyeuropepmc.agentic.task_planner import TaskPlanner

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Stages of a research pipeline."""

    INITIALIZE = "initialize"
    PLANNING = "planning"
    EXECUTION = "execution"
    SYNTHESIS = "synthesis"
    REVIEW = "review"
    FINALIZE = "finalize"


@dataclass
class PipelineStep:
    """Single step in a research pipeline."""

    id: str
    name: str
    agent_name: str | None = None
    tool_name: str | None = None
    description: str = ""
    input_keys: list[str] = field(default_factory=list)
    output_keys: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert step to a serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name,
            "description": self.description,
            "input_keys": self.input_keys,
            "output_keys": self.output_keys,
            "status": self.status,
            "result": self.result,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class PipelineState:
    """Complete state of a research pipeline."""

    pipeline_id: str
    name: str
    description: str
    stages: list[PipelineStage]
    steps: list[PipelineStep]
    global_state: dict[str, Any] = field(default_factory=dict)
    current_stage: PipelineStage = PipelineStage.INITIALIZE
    current_step: int = 0
    status: str = "pending"  # pending, running, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchPipeline:
    """
    Pipeline for chaining research agents and tools.

    Coordinates multiple agents and tools into a cohesive workflow:
    - Define research steps with input/output specifications
    - Chain agents with proper data flow
    - Track pipeline progress and state
    - Support dynamic step addition and modification

    Inspired by gpt-researcher's workflow approach.

    Attributes
    ----------
    state : PipelineState
        Current pipeline state
    task_planner : TaskPlanner
        Task decomposition for complex steps
    orchestrator : AgentOrchestrator
        Agent coordination
    tool_registry : ToolRegistry
        Tool execution
    """

    def __init__(
        self,
        name: str = "research_pipeline",
        description: str = "",
    ):
        """
        Initialize research pipeline.

        Parameters
        ----------
        name : str, optional
            Pipeline name (default: "research_pipeline")
        description : str, optional
            Pipeline description
        """
        self.name = name
        self.description = description
        self.pipeline_id = str(uuid.uuid4())

        # Pipeline state
        self.state = PipelineState(
            pipeline_id=self.pipeline_id,
            name=name,
            description=description,
            stages=[],
            steps=[],
            status="pending",
        )

        # Dependencies
        self.task_planner = TaskPlanner()
        self.orchestrator = AgentOrchestrator()
        self.tool_registry = ToolRegistry()

        # Callbacks
        self._progress_callbacks: list = []
        self._step_callbacks: list = []

    def add_stage(self, stage: PipelineStage) -> "ResearchPipeline":
        """
        Add a stage to the pipeline.

        Parameters
        ----------
        stage : PipelineStage
            Stage to add

        Returns
        -------
        ResearchPipeline
            Self for method chaining
        """
        if stage not in self.state.stages:
            self.state.stages.append(stage)
        return self

    def add_step(
        self,
        name: str,
        agent_name: str | None = None,
        tool_name: str | None = None,
        description: str = "",
        input_keys: list[str] | None = None,
        output_keys: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ResearchPipeline":
        """
        Add a step to the pipeline.

        Parameters
        ----------
        name : str
            Step name
        agent_name : str, optional
            Name of agent to execute this step
        tool_name : str, optional
            Name of tool to execute this step
        description : str, optional
            Step description
        input_keys : list[str], optional
            Keys to extract from global state for input
        output_keys : list[str], optional
            Keys to store in global state from result
        metadata : dict, optional
            Additional step metadata

        Returns
        -------
        ResearchPipeline
            Self for method chaining
        """
        if input_keys is None:
            input_keys = []
        if output_keys is None:
            output_keys = []
        if metadata is None:
            metadata = {}

        step = PipelineStep(
            id=str(uuid.uuid4()),
            name=name,
            agent_name=agent_name,
            tool_name=tool_name,
            description=description,
            input_keys=input_keys,
            output_keys=output_keys,
            metadata=metadata,
        )

        self.state.steps.append(step)
        return self

    def set_step_agent(self, step_id: str, agent_name: str) -> bool:
        """
        Assign an agent to a step.

        Parameters
        ----------
        step_id : str
            Step ID
        agent_name : str
            Agent name

        Returns
        -------
        bool
            True if successful
        """
        for step in self.state.steps:
            if step.id == step_id:
                step.agent_name = agent_name
                return True
        return False

    def set_step_tool(self, step_id: str, tool_name: str) -> bool:
        """
        Assign a tool to a step.

        Parameters
        ----------
        step_id : str
            Step ID
        tool_name : str
            Tool name

        Returns
        -------
        bool
            True if successful
        """
        for step in self.state.steps:
            if step.id == step_id:
                step.tool_name = tool_name
                return True
        return False

    def set_step_input(self, step_id: str, input_keys: list[str]) -> bool:
        """
        Set input keys for a step.

        Parameters
        ----------
        step_id : str
            Step ID
        input_keys : list[str]
            Input keys

        Returns
        -------
        bool
            True if successful
        """
        for step in self.state.steps:
            if step.id == step_id:
                step.input_keys = input_keys
                return True
        return False

    def set_step_output(self, step_id: str, output_keys: list[str]) -> bool:
        """
        Set output keys for a step.

        Parameters
        ----------
        step_id : str
            Step ID
        output_keys : list[str]
            Output keys

        Returns
        -------
        bool
            True if successful
        """
        for step in self.state.steps:
            if step.id == step_id:
                step.output_keys = output_keys
                return True
        return False

    def get_step_input(self, step: PipelineStep) -> dict[str, Any]:
        """
        Get input data for a step from global state.

        Parameters
        ----------
        step : PipelineStep
            Step to get input for

        Returns
        -------
        dict[str, Any]
            Input data dictionary
        """
        input_data = {}
        for key in step.input_keys:
            if key in self.state.global_state:
                input_data[key] = self.state.global_state[key]
        return input_data

    def execute_step(self, step: PipelineStep) -> dict[str, Any]:
        """
        Execute a single step.

        Parameters
        ----------
        step : PipelineStep
            Step to execute

        Returns
        -------
        dict[str, Any]
            Step result
        """
        step.status = "running"
        step.completed_at = datetime.now()

        try:
            # Get input data
            input_data = self.get_step_input(step)

            # Execute based on type
            if step.agent_name:
                result = self._execute_agent(step.agent_name, input_data)
            elif step.tool_name:
                result = self._execute_tool(step.tool_name, input_data)
            else:
                # Fallback to empty execution
                result = {"status": "completed", "message": "No agent or tool specified"}

            step.status = "completed"
            step.result = result

            # Update global state
            if step.output_keys and result:
                for key in step.output_keys:
                    if key in result:
                        self.state.global_state[key] = result[key]

            # Notify step callbacks
            for callback in self._step_callbacks:
                try:
                    callback(step)
                except Exception as e:
                    logger.warning(f"Step callback error: {e}")

            return result

        except Exception as e:
            step.status = "failed"
            logger.error(f"Step {step.name} failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _execute_agent(self, agent_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute an agent.

        Parameters
        ----------
        agent_name : str
            Agent name
        input_data : dict[str, Any]
            Input data

        Returns
        -------
        dict[str, Any]
            Agent result
        """
        if agent_name not in self.orchestrator.agents:
            logger.warning(f"Agent '{agent_name}' not found, skipping")
            return {"status": "skipped", "message": f"Agent '{agent_name}' not found"}

        agent = self.orchestrator.agents[agent_name]

        try:
            result = agent.execute(**input_data)
            return result
        except Exception as e:
            logger.error(f"Agent '{agent_name}' execution failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _execute_tool(self, tool_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool.

        Parameters
        ----------
        tool_name : str
            Tool name
        input_data : dict[str, Any]
            Input data

        Returns
        -------
        dict[str, Any]
            Tool result (passed through — status managed by pipeline step)
        """
        if tool_name not in self.tool_registry.tools:
            logger.warning(f"Tool '{tool_name}' not found, skipping")
            return {"status": "skipped", "message": f"Tool '{tool_name}' not found"}

        tool_info = self.tool_registry.tools[tool_name]

        try:
            result = tool_info.func(**input_data)
            # If result is already a dict, return as-is so output_keys work
            if isinstance(result, dict):
                return result
            return {"result": result}
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            return {"status": "failed", "error": str(e)}

    def run(self, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Run the entire pipeline.

        Parameters
        ----------
        initial_state : dict[str, Any], optional
            Initial state data

        Returns
        -------
        dict[str, Any]
            Final pipeline result
        """
        self.state.status = "running"
        self.state.created_at = datetime.now()

        if initial_state:
            self.state.global_state.update(initial_state)

        try:
            # Execute each stage
            for stage in self.state.stages:
                self.state.current_stage = stage
                self._notify_progress(0.0, f"Starting stage: {stage.value}")

                # Execute steps in this stage
                stage_steps = [
                    s for s in self.state.steps if s.metadata.get("stage") == stage.value
                ]
                total_steps = len(stage_steps)

                for i, step in enumerate(stage_steps):
                    self.state.current_step = i
                    self._notify_progress(
                        i / total_steps if total_steps > 0 else 0, f"Executing step: {step.name}"
                    )
                    result = self.execute_step(step)

                    if result.get("status") == "failed":
                        self.state.status = "failed"
                        return self._finalize_pipeline()

                self._notify_progress(1.0, f"Completed stage: {stage.value}")

            # Final synthesis
            self.state.current_stage = PipelineStage.FINALIZE
            self._notify_progress(0.5, "Synthesizing results")

            # Aggregate results
            final_result = self._aggregate_results()

            self.state.status = "completed"
            self.state.completed_at = datetime.now()

            return self._finalize_pipeline(final_result)

        except Exception as e:
            self.state.status = "failed"
            logger.error(f"Pipeline failed: {e}")
            return self._finalize_pipeline({"status": "failed", "error": str(e)})

    def _aggregate_results(self) -> dict[str, Any]:
        """
        Aggregate results from all steps.

        Returns
        -------
        dict[str, Any]
            Aggregated results
        """
        aggregated = {
            "status": "completed",
            "steps_completed": sum(1 for s in self.state.steps if s.status == "completed"),
            "steps_failed": sum(1 for s in self.state.steps if s.status == "failed"),
            "step_results": {},
        }

        for step in self.state.steps:
            if step.result:
                aggregated["step_results"][step.name] = step.result

        return aggregated

    def _finalize_pipeline(self, final_result: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Finalize pipeline and return results.

        Parameters
        ----------
        final_result : dict[str, Any], optional
            Final result to include

        Returns
        -------
        dict[str, Any]
            Pipeline results
        """
        if final_result is None:
            final_result = {}

        return {
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.name,
            "status": self.state.status,
            "steps": [s.to_dict() for s in self.state.steps],  # type: ignore
            "global_state": self.state.global_state,
            **final_result,
        }

    def register_progress_callback(self, callback):
        """
        Register a progress callback.

        Parameters
        ----------
        callback : callable
            Function signature: callback(progress: float, message: str)
        """
        self._progress_callbacks.append(callback)

    def register_step_callback(self, callback):
        """
        Register a step callback.

        Parameters
        ----------
        callback : callable
            Function signature: callback(step: PipelineStep)
        """
        self._step_callbacks.append(callback)

    def _notify_progress(self, progress: float, message: str):
        """
        Notify progress callbacks.

        Parameters
        ----------
        progress : float
            Progress value (0.0 to 1.0)
        message : str
            Progress message
        """
        for callback in self._progress_callbacks:
            try:
                callback(progress, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def get_step_tree(self) -> str:
        """
        Get a string representation of the pipeline steps.

        Returns
        -------
        str
            Step tree visualization
        """
        lines = [f"Pipeline: {self.name}"]
        lines.append(f"  ID: {self.pipeline_id}")
        lines.append(f"  Status: {self.state.status}")
        lines.append("")

        current_stage = None
        for step in self.state.steps:
            stage = step.metadata.get("stage", "general")
            if stage != current_stage:
                current_stage = stage
                lines.append(f"[{stage.upper()}]")

            status_icon = (
                "○" if step.status == "pending" else "●" if step.status == "completed" else "✗"
            )
            lines.append(f"  {status_icon} {step.name}: {step.description[:50]}...")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert pipeline to dictionary.

        Returns
        -------
        dict[str, Any]
            Pipeline as dictionary
        """
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "state": self.state.__dict__,
            "orchestrator_agents": list(self.orchestrator.agents.keys()),
            "tool_registry_tools": list(self.tool_registry.tools.keys()),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPipeline":
        """
        Create pipeline from dictionary.

        Parameters
        ----------
        data : dict[str, Any]
            Pipeline data

        Returns
        -------
        ResearchPipeline
            Created pipeline
        """
        pipeline = cls(
            name=data.get("name", "research_pipeline"),
            description=data.get("description", ""),
        )

        # Note: This is a basic reconstruction. Full state restoration
        # would require recreating agents and tools.
        return pipeline
