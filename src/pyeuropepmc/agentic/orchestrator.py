"""
Agent orchestrator for multi-agent coordination.

This module provides:
- AgentOrchestrator class for managing multiple agents
- Agent communication protocol
- Task delegation between agents
- Result aggregation and synthesis
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any

from pyeuropepmc.agentic.base import BaseAgent
from pyeuropepmc.agentic.llm_client import LLMClient, create_llm_client
from pyeuropepmc.features.search.base import BaseLiteratureClient

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles that agents can play in the orchestration."""

    PLANNER = "planner"
    WRITER = "writer"
    REVIEWER = "reviewer"
    SYNTHESIZER = "synthesizer"
    ANALYST = "analyst"
    EXPERT = "expert"
    EDITOR = "editor"
    VALIDATOR = "validator"


@dataclass
class AgentConfig:
    """Configuration for an agent in the orchestrator."""

    name: str
    role: AgentRole
    description: str = ""
    llm_client: LLMClient | None = None
    literature_client: BaseLiteratureClient | None = None
    llm_enabled: bool = True
    priority: int = 0
    can_delegate: bool = True
    requirements: list[str] = field(default_factory=list)


@dataclass
class Task:
    """Task to be executed by an agent."""

    id: str
    description: str
    assigned_agent: str | None = None
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    status: str = "pending"  # pending, in_progress, completed, failed
    result: dict[str, Any] | None = None
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCommunication:
    """Message passed between agents."""

    sender: str
    recipient: str | None
    message_type: str  # query, response, request, notification
    content: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: str | None = None


class AgentOrchestrator:
    """
    Orchestrator for multi-agent literature research workflows.

    Inspired by gpt-researcher and AgentLaboratory, this orchestrator:
    - Manages multiple specialized agents
    - Coordinates agent communication
    - Delegates tasks based on agent expertise
    - Aggregates results from multiple agents

    Attributes
    ----------
    agents : dict
        Registered agents by name
    tasks : dict
        Task queue and status
    communication_log : list
        History of agent communications
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        literature_client: BaseLiteratureClient | None = None,
    ):
        """
        Initialize the orchestrator.

        Parameters
        ----------
        llm_client : LLMClient, optional
            LLM client for agent operations. If None, creates new one.
        literature_client : BaseLiteratureClient, optional
            Literature client for paper fetching. If None, creates new one.
        """
        self.llm_client = llm_client or create_llm_client()
        # Only create literature client if not provided (for testing)
        if literature_client is None:
            try:
                from pyeuropepmc.features.search.pmc import PmcClient

                self.literature_client = PmcClient()
            except Exception:
                # For tests, leave as None
                self.literature_client = None
        else:
            self.literature_client = literature_client
        self.agents: dict[str, BaseAgent] = {}
        self.agent_configs: dict[str, AgentConfig] = {}
        self.tasks: dict[str, Task] = {}
        self.communication_log: list[AgentCommunication] = []
        self._task_callbacks: list[Callable[[Task], None]] = []

    def register_agent(
        self,
        agent: BaseAgent,
        name: str,
        role: AgentRole,
        description: str = "",
        priority: int = 0,
        can_delegate: bool = True,
    ) -> None:
        """
        Register an agent with the orchestrator.

        Parameters
        ----------
        agent : BaseAgent
            Agent instance to register
        name : str
            Unique name for the agent
        role : AgentRole
            Role the agent plays
        description : str, optional
            Description of agent's capabilities
        priority : int, optional
            Agent priority (higher = more urgent tasks)
        can_delegate : bool, optional
            Whether agent can receive delegated tasks
        """
        self.agents[name] = agent
        self.agent_configs[name] = AgentConfig(
            name=name,
            role=role,
            description=description,
            priority=priority,
            can_delegate=can_delegate,
        )
        logger.info(f"Registered agent '{name}' with role {role.value}")

    def create_task(
        self,
        task_id: str,
        description: str,
        priority: int = 0,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """
        Create a new task in the queue.

        Parameters
        ----------
        task_id : str
            Unique identifier for the task
        description : str
            Description of what needs to be done
        priority : int, optional
            Task priority (higher = more urgent)
        dependencies : list, optional
            Task IDs that must complete first
        metadata : dict, optional
            Additional task metadata

        Returns
        -------
        Task
            Created task object
        """
        task = Task(
            id=task_id,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self.tasks[task_id] = task
        logger.info(f"Created task '{task_id}': {description[:50]}...")
        return task

    def assign_task(self, task_id: str, agent_name: str) -> bool:
        """
        Assign a task to a specific agent.

        Parameters
        ----------
        task_id : str
            ID of task to assign
        agent_name : str
            Name of agent to assign to

        Returns
        -------
        bool
            True if assignment successful
        """
        if task_id not in self.tasks:
            logger.error(f"Task '{task_id}' not found")
            return False

        if agent_name not in self.agents:
            logger.error(f"Agent '{agent_name}' not registered")
            return False

        self.tasks[task_id].assigned_agent = agent_name
        self.tasks[task_id].status = "in_progress"
        logger.info(f"Assigned task '{task_id}' to agent '{agent_name}'")
        return True

    def execute_task(self, task_id: str) -> dict[str, Any] | None:
        """
        Execute a single task.

        Parameters
        ----------
        task_id : str
            ID of task to execute

        Returns
        -------
        dict or None
            Task result or None if failed
        """
        if task_id not in self.tasks:
            logger.error(f"Task '{task_id}' not found")
            return None

        task = self.tasks[task_id]

        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                logger.error(f"Dependency '{dep_id}' not found for task '{task_id}'")
                task.status = "failed"
                return None

            if self.tasks[dep_id].status != "completed":
                logger.warning(f"Dependency '{dep_id}' not completed for task '{task_id}'")
                task.status = "pending"
                return None

        # Get assigned agent
        agent_name = task.assigned_agent
        if not agent_name or agent_name not in self.agents:
            logger.error(f"No valid agent assigned to task '{task_id}'")
            task.status = "failed"
            return None

        agent = self.agents[agent_name]

        logger.info(f"Executing task '{task_id}' with agent '{agent_name}'")

        try:
            # Execute agent
            result = agent.execute(**task.metadata)

            # Update task
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()

            # Notify callbacks
            for callback in self._task_callbacks:
                try:
                    callback(task)
                except Exception as e:
                    logger.warning(f"Task callback failed: {e}")

            logger.info(f"Completed task '{task_id}'")
            return result

        except Exception as e:
            logger.error(f"Task '{task_id}' failed: {e}")
            task.status = "failed"
            return None

    def execute_workflow(self, task_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Execute a sequence of tasks.

        Parameters
        ----------
        task_ids : list
            Ordered list of task IDs to execute

        Returns
        -------
        dict
            Results from all completed tasks
        """
        results: dict[str, dict[str, Any]] = {}

        for task_id in task_ids:
            result = self.execute_task(task_id)
            if result is not None:
                results[task_id] = result
            else:
                logger.warning(f"Task '{task_id}' failed, skipping subsequent tasks")
                break

        return results

    def register_task_callback(self, callback: Callable[[Task], None]) -> None:
        """
        Register a callback for task completion.

        Parameters
        ----------
        callback : callable
            Function called when task completes
        """
        self._task_callbacks.append(callback)

    def broadcast_message(
        self,
        sender: str,
        message_type: str,
        content: dict[str, Any],
        recipient: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """
        Broadcast a message between agents.

        Parameters
        ----------
        sender : str
            Name of sending agent
        message_type : str
            Type of message (query, response, request, notification)
        content : dict
            Message content
        recipient : str, optional
            Specific recipient or None for broadcast
        task_id : str, optional
            Associated task ID
        """
        message = AgentCommunication(
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            content=content,
            task_id=task_id,
        )
        self.communication_log.append(message)
        logger.debug(f"Message: {sender} -> {recipient}: {message_type}")

    def get_agents_by_role(self, role: AgentRole) -> list[str]:
        """
        Get all agents with a specific role.

        Parameters
        ----------
        role : AgentRole
            Role to filter by

        Returns
        -------
        list
            Names of agents with that role
        """
        return [name for name, config in self.agent_configs.items() if config.role == role]

    def get_completed_tasks(self) -> list[Task]:
        """Get all completed tasks."""
        return [task for task in self.tasks.values() if task.status == "completed"]

    def get_failed_tasks(self) -> list[Task]:
        """Get all failed tasks."""
        return [task for task in self.tasks.values() if task.status == "failed"]

    def clear_tasks(self) -> None:
        """Clear all tasks from the queue."""
        self.tasks.clear()
        logger.info("Cleared all tasks")
