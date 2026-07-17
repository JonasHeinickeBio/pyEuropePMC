"""
Task planner for recursive task decomposition.

This module provides:
- TaskPlanner class for breaking down complex research tasks
- Task tree visualization
- Dependency resolution
- Progress tracking for decomposition

Inspired by gpt-researcher's task decomposition approach.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any
import uuid

from pyeuropepmc.agentic.base import BaseAgent
from pyeuropepmc.agentic.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task in the decomposition."""

    PENDING = "pending"
    DECOMPOSING = "decomposing"
    DECOMPOSED = "decomposed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskNode:
    """
    Node in the task decomposition tree.

    Represents a single task that may have subtasks.
    """

    task_id: str
    description: str
    parent_id: str | None = None
    depth: int = 0
    status: TaskStatus = TaskStatus.PENDING
    subtasks: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "status": self.status.value,
            "subtasks": self.subtasks,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskNode":
        """Create from dictionary."""
        node = cls(
            task_id=data["task_id"],
            description=data["description"],
            parent_id=data.get("parent_id"),
            depth=data.get("depth", 0),
            status=TaskStatus(data.get("status", "pending")),
            subtasks=data.get("subtasks", []),
            result=data.get("result"),
            metadata=data.get("metadata", {}),
        )
        if data.get("created_at"):
            node.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("completed_at"):
            node.completed_at = datetime.fromisoformat(data["completed_at"])
        return node


class TaskPlanner:
    """
    Planner for recursive task decomposition.

    Takes a high-level research goal and decomposes it into
    a tree of manageable subtasks that can be assigned to agents.

    Key features:
    - Recursive task breakdown based on complexity
    - Dependency management between tasks
    - Depth-limited decomposition to prevent infinite splitting
    - Task tree visualization and analysis

    Examples
    --------
    >>> planner = TaskPlanner()
    >>> root_task = planner.create_task(
    ...     "Investigate the efficacy of CRISPR-Cas9 in treating sickle cell disease",
    ...     max_depth=3
    ... )
    >>> # Decomposition happens automatically during create_task
    >>> # Access the task tree via root_task.task_id
    """

    def __init__(
        self,
        max_depth: int = 4,
        max_subtasks_per_node: int = 5,
        min_task_complexity: int = 3,
    ):
        """
        Initialize the task planner.

        Parameters
        ----------
        max_depth : int, optional
            Maximum depth of task decomposition tree (default: 4)
        max_subtasks_per_node : int, optional
            Maximum number of subtasks per node (default: 5)
        min_task_complexity : int, optional
            Minimum complexity score for decomposition (default: 3)
        """
        self.max_depth = max_depth
        self.max_subtasks_per_node = max_subtasks_per_node
        self.min_task_complexity = min_task_complexity

        self._tasks: dict[str, TaskNode] = {}
        self._task_queue: deque[str] = deque()

    def create_task(
        self,
        description: str,
        parent_id: str | None = None,
        depth: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> TaskNode:
        """
        Create a new task node.

        Parameters
        ----------
        description : str
            Description of the task
        parent_id : str, optional
            ID of parent task (None for root)
        depth : int, optional
            Current depth in the tree (default: 0)
        metadata : dict, optional
            Additional task metadata

        Returns
        -------
        TaskNode
            Created task node
        """
        task_id = str(uuid.uuid4())
        node = TaskNode(
            task_id=task_id,
            description=description,
            parent_id=parent_id,
            depth=depth,
            metadata=metadata or {},
        )
        self._tasks[task_id] = node
        return node

    def decompose_task(
        self,
        task: TaskNode,
        agent: BaseAgent | None = None,
        orchestrator: AgentOrchestrator | None = None,
    ) -> list[str]:
        """
        Decompose a task into subtasks.

        Analyzes the task description and creates subtasks
        based on complexity and structure.

        Parameters
        ----------
        task : TaskNode
            Task to decompose
        agent : BaseAgent, optional
            Agent to use for analysis (optional)
        orchestrator : AgentOrchestrator, optional
            Orchestrator for task execution (optional)

        Returns
        -------
        list[str]
            List of subtask IDs created
        """
        if task.depth >= self.max_depth:
            logger.debug(f"Max depth reached for task {task.task_id}")
            return []

        # Estimate complexity from description length and structure
        complexity = self._estimate_complexity(task.description)

        if complexity < self.min_task_complexity:
            logger.debug(f"Task {task.task_id} complexity too low for decomposition")
            return []

        # Generate subtasks based on task structure
        subtask_descriptions = self._generate_subtasks(task.description)

        if not subtask_descriptions:
            logger.debug(f"No subtasks generated for task {task.task_id}")
            return []

        # Limit number of subtasks
        subtask_descriptions = subtask_descriptions[: self.max_subtasks_per_node]

        subtask_ids: list[str] = []
        for desc in subtask_descriptions:
            subtask = self.create_task(
                description=desc,
                parent_id=task.task_id,
                depth=task.depth + 1,
            )
            task.subtasks.append(subtask.task_id)
            subtask_ids.append(subtask.task_id)

            # Recursively decompose if depth allows
            if task.depth + 1 < self.max_depth:
                self.decompose_task(subtask, agent, orchestrator)

        task.status = TaskStatus.DECOMPOSED
        return subtask_ids

    def _estimate_complexity(self, description: str) -> int:
        """
        Estimate task complexity from description.

        Uses heuristics like description length, sentence count,
        and keyword presence to estimate decomposition needs.

        Parameters
        ----------
        description : str
            Task description

        Returns
        -------
        int
            Complexity score (0-10)
        """
        complexity = 0

        # Length factor
        if len(description) > 100:
            complexity += 2
        if len(description) > 200:
            complexity += 2

        # Sentence count factor
        sentences = description.count(".") + description.count("!") + description.count("?")
        if sentences > 1:
            complexity += 1
        if sentences > 3:
            complexity += 1

        # Keyword factors (research-specific)
        keywords = [
            "analyze",
            "compare",
            "investigate",
            "evaluate",
            "explore",
            "systematic",
            "review",
            "meta-analysis",
            "determine",
            "identify",
            "relationship",
            "impact",
            "effect",
        ]
        desc_lower = description.lower()
        keyword_count = sum(1 for kw in keywords if kw in desc_lower)
        complexity += min(keyword_count, 3)

        # Structural complexity
        if "and" in description.lower() or "or" in description.lower():
            complexity += 1
        if "(" in description or ")" in description:
            complexity += 1

        return min(complexity, 10)

    def _generate_subtasks(self, description: str) -> list[str]:
        """
        Generate subtask descriptions from a task.

        Uses pattern matching and NLP heuristics to identify
        natural decomposition points in the task description.

        Parameters
        ----------
        description : str
            Task description

        Returns
        -------
        list[str]
            List of subtask descriptions
        """
        subtasks = []

        # Pattern 1: Research question format
        # "Investigate X in Y" -> ["Find X", "Analyze Y", "Relate X to Y"]
        if "investigate" in description.lower() or "examine" in description.lower():
            subtasks.extend(self._decompose_research_question(description))

        # Pattern 2: Multi-step process
        # "First do X, then do Y, finally Z" -> ["X", "Y", "Z"]
        if "first" in description.lower() or "then" in description.lower():
            subtasks.extend(self._decompose_step_sequence(description))

        # Pattern 3: Systematic literature review format
        # "Search, Screen, Extract, Analyze" -> individual tasks
        if "systematic" in description.lower() or "review" in description.lower():
            subtasks.extend(self._decompose_review_process(description))

        # Pattern 4: Comparison/contrast format
        if "compare" in description.lower() or "contrast" in description.lower():
            subtasks.extend(self._decompose_comparison(description))

        # Default: single task if no pattern matches
        if not subtasks:
            subtasks = [description]

        return subtasks

    def _decompose_research_question(self, description: str) -> list[str]:
        """Decompose research question into subtasks."""
        subtasks = []

        # Extract key components
        if "in" in description.lower():
            parts = description.lower().split(" in ")
            if len(parts) == 2:
                subtasks.append(f"Find studies about {parts[0]}")
                subtasks.append(f"Analyze {parts[1]} context")
                subtasks.append(f"Relate {parts[0]} to {parts[1]}")

        return subtasks

    def _decompose_step_sequence(self, description: str) -> list[str]:
        """Decompose step-by-step description into subtasks."""
        # Split on common separators
        separators = [", then", ", and", ", finally", "then", "finally"]
        text = description.lower()

        for sep in separators:
            if sep in text:
                parts = text.split(sep)
                return [f"{p.strip().capitalize()}" for p in parts if len(p.strip()) > 5]

        return []

    def _decompose_review_process(self, description: str) -> list[str]:
        """Decompose systematic review into PRISMA-style steps."""
        subtasks = [
            "Define inclusion and exclusion criteria",
            "Search literature databases",
            "Screen titles and abstracts",
            "Review full-text articles",
            "Extract data from selected studies",
            "Assess study quality and risk of bias",
            "Synthesize findings",
        ]

        # Adapt based on description
        if "meta-analysis" in description.lower():
            subtasks.insert(6, "Perform statistical meta-analysis")

        return subtasks[: self.max_subtasks_per_node]

    def _decompose_comparison(self, description: str) -> list[str]:
        """Decompose comparison task into subtasks."""
        subtasks = [
            "Identify item A characteristics",
            "Identify item B characteristics",
            "Compare key features",
            "Evaluate relative strengths",
            "Summarize differences",
        ]

        return subtasks[: self.max_subtasks_per_node]

    def get_task_tree(self, root_id: str) -> dict[str, Any]:
        """
        Get the complete task tree starting from root.

        Parameters
        ----------
        root_id : str
            ID of root task

        Returns
        -------
        dict
            Complete task tree structure
        """
        if root_id not in self._tasks:
            return {"error": f"Task {root_id} not found"}

        root = self._tasks[root_id]
        return self._build_tree(root)

    def _build_tree(self, node: TaskNode) -> dict[str, Any]:
        """Build tree structure recursively."""
        tree = node.to_dict()
        tree["children"] = []

        for subtask_id in node.subtasks:
            if subtask_id in self._tasks:
                child = self._build_tree(self._tasks[subtask_id])
                tree["children"].append(child)

        return tree

    def get_ready_tasks(self) -> list[TaskNode]:
        """
        Get tasks that are ready for execution.

        Ready tasks are those with all dependencies satisfied.

        Returns
        -------
        list[TaskNode]
            List of ready tasks
        """
        ready = []

        for task_id, task in self._tasks.items():
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all parent tasks are completed
            if task.parent_id and task.parent_id in self._tasks:
                parent = self._tasks[task.parent_id]
                if parent.status != TaskStatus.COMPLETED:
                    continue

            ready.append(task)

        return ready

    def update_task_status(
        self, task_id: str, status: TaskStatus, result: dict[str, Any] | None = None
    ) -> bool:
        """
        Update task status and mark as completed if needed.

        Parameters
        ----------
        task_id : str
            Task ID to update
        status : TaskStatus
            New status
        result : dict, optional
            Task result data

        Returns
        -------
        bool
            True if update successful
        """
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.status = status

        if status == TaskStatus.COMPLETED:
            task.result = result
            task.completed_at = datetime.now()

        return True

    def reset(self) -> None:
        """Reset the task planner."""
        self._tasks.clear()
        self._task_queue.clear()

    @property
    def task_count(self) -> int:
        """Total number of tasks in the planner."""
        return len(self._tasks)

    @property
    def leaf_tasks(self) -> list[TaskNode]:
        """Get all leaf tasks (tasks with no subtasks)."""
        return [t for t in self._tasks.values() if not t.subtasks]
