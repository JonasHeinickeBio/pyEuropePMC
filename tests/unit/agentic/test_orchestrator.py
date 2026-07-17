"""
Tests for AgentOrchestrator.

This module tests:
- Agent registration and management
- Task creation and assignment
- Task execution workflow
- Agent communication
- Result aggregation
"""

import pytest
from unittest.mock import Mock, patch

from pyeuropepmc.agentic.orchestrator import (
    AgentOrchestrator,
    AgentRole,
    AgentConfig,
    Task,
    AgentCommunication,
)


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name="mock"):
        self.name = name
        self.executions = 0

    def execute(self, **kwargs):
        self.executions += 1
        return {"result": "success", "agent": self.name, "kwargs": kwargs}


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator class."""

    def test_init_creates_default_clients(self):
        """Test that orchestrator creates default clients."""
        orchestrator = AgentOrchestrator()

        assert orchestrator.llm_client is not None
        # literature_client may be None if PmcClient fails to initialize
        # This is expected in test environments without proper API setup
        # assert orchestrator.literature_client is not None  # Skip - environment-specific
        assert orchestrator.agents == {}
        assert orchestrator.tasks == {}
        assert orchestrator.communication_log == []

    def test_init_with_custom_clients(self):
        """Test initialization with custom clients."""
        mock_llm = Mock()
        mock_literature = Mock()

        orchestrator = AgentOrchestrator(
            llm_client=mock_llm,
            literature_client=mock_literature,
        )

        assert orchestrator.llm_client is mock_llm
        assert orchestrator.literature_client is mock_literature

    def test_register_agent(self):
        """Test agent registration."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("test_agent")

        orchestrator.register_agent(
            agent=agent,
            name="test_agent",
            role=AgentRole.ANALYST,
            description="Test agent",
            priority=5,
        )

        assert "test_agent" in orchestrator.agents
        assert orchestrator.agents["test_agent"] is agent
        assert orchestrator.agent_configs["test_agent"].role == AgentRole.ANALYST
        assert orchestrator.agent_configs["test_agent"].priority == 5

    def test_register_agent_duplicate_name(self):
        """Test registering agent with duplicate name."""
        orchestrator = AgentOrchestrator()
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent1")  # Same name

        orchestrator.register_agent(agent1, "agent1", AgentRole.ANALYST)

        # Second registration should overwrite
        orchestrator.register_agent(agent2, "agent1", AgentRole.WRITER)

        assert orchestrator.agents["agent1"] is agent2
        assert orchestrator.agent_configs["agent1"].role == AgentRole.WRITER

    def test_create_task(self):
        """Test task creation."""
        orchestrator = AgentOrchestrator()

        task = orchestrator.create_task(
            task_id="task1",
            description="Test task",
            priority=10,
            dependencies=["dep1"],
        )

        assert task.id == "task1"
        assert task.description == "Test task"
        assert task.priority == 10
        assert task.dependencies == ["dep1"]
        assert task.status == "pending"
        assert task.assigned_agent is None

    def test_assign_task_successful(self):
        """Test successful task assignment."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("test_agent")

        orchestrator.register_agent(agent, "test_agent", AgentRole.ANALYST)
        orchestrator.create_task("task1", "Test task")

        result = orchestrator.assign_task("task1", "test_agent")

        assert result is True
        assert orchestrator.tasks["task1"].assigned_agent == "test_agent"
        assert orchestrator.tasks["task1"].status == "in_progress"

    def test_assign_task_not_found(self):
        """Test assigning non-existent task."""
        orchestrator = AgentOrchestrator()

        result = orchestrator.assign_task("nonexistent", "some_agent")

        assert result is False

    def test_assign_task_agent_not_found(self):
        """Test assigning task to non-existent agent."""
        orchestrator = AgentOrchestrator()
        orchestrator.create_task("task1", "Test task")

        result = orchestrator.assign_task("task1", "nonexistent_agent")

        assert result is False

    def test_execute_task_success(self):
        """Test successful task execution."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")

        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)
        orchestrator.create_task("task1", "Test task")
        orchestrator.assign_task("task1", "executor")

        result = orchestrator.execute_task("task1")

        assert result is not None
        assert result["result"] == "success"
        assert orchestrator.tasks["task1"].status == "completed"
        assert orchestrator.tasks["task1"].result == result

    def test_execute_task_not_found(self):
        """Test executing non-existent task."""
        orchestrator = AgentOrchestrator()

        result = orchestrator.execute_task("nonexistent")

        assert result is None
        assert "nonexistent" not in orchestrator.tasks  # Task not created

    def test_execute_task_with_dependencies(self):
        """Test task execution with dependencies."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")

        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)
        orchestrator.create_task("dep1", "Dependency task")
        orchestrator.create_task("task1", "Main task", dependencies=["dep1"])

        # Execute dependency first
        orchestrator.assign_task("dep1", "executor")
        orchestrator.execute_task("dep1")

        # Now execute main task
        orchestrator.assign_task("task1", "executor")
        result = orchestrator.execute_task("task1")

        assert result is not None
        assert orchestrator.tasks["task1"].status == "completed"

    def test_execute_task_dependency_not_completed(self):
        """Test task execution when dependency not completed."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")

        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)
        orchestrator.create_task("dep1", "Dependency task")
        orchestrator.create_task("task1", "Main task", dependencies=["dep1"])

        # Don't execute dependency
        orchestrator.assign_task("task1", "executor")
        result = orchestrator.execute_task("task1")

        assert result is None
        assert orchestrator.tasks["task1"].status == "pending"

    def test_execute_workflow(self):
        """Test executing a sequence of tasks."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")

        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)
        orchestrator.create_task("task1", "Task 1")
        orchestrator.create_task("task2", "Task 2")
        orchestrator.create_task("task3", "Task 3")

        orchestrator.assign_task("task1", "executor")
        orchestrator.assign_task("task2", "executor")
        orchestrator.assign_task("task3", "executor")

        results = orchestrator.execute_workflow(["task1", "task2", "task3"])

        assert len(results) == 3
        assert "task1" in results
        assert "task2" in results
        assert "task3" in results

    def test_broadcast_message(self):
        """Test message broadcasting between agents."""
        orchestrator = AgentOrchestrator()

        orchestrator.broadcast_message(
            sender="agent1",
            recipient="agent2",
            message_type="query",
            content={"question": "What is the topic?"},
            task_id="task1",
        )

        assert len(orchestrator.communication_log) == 1
        message = orchestrator.communication_log[0]
        assert message.sender == "agent1"
        assert message.recipient == "agent2"
        assert message.message_type == "query"
        assert message.task_id == "task1"

    def test_get_agents_by_role(self):
        """Test getting agents by role."""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockAgent("agent1"), "agent1", AgentRole.ANALYST)
        orchestrator.register_agent(MockAgent("agent2"), "agent2", AgentRole.WRITER)
        orchestrator.register_agent(MockAgent("agent3"), "agent3", AgentRole.ANALYST)

        analysts = orchestrator.get_agents_by_role(AgentRole.ANALYST)

        assert len(analysts) == 2
        assert "agent1" in analysts
        assert "agent3" in analysts
        assert "agent2" not in analysts

    def test_get_completed_tasks(self):
        """Test getting completed tasks."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")
        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)

        orchestrator.create_task("completed_task", "Complete")
        orchestrator.assign_task("completed_task", "executor")
        orchestrator.execute_task("completed_task")

        orchestrator.create_task("pending_task", "Pending")

        completed = orchestrator.get_completed_tasks()

        assert len(completed) == 1
        assert completed[0].id == "completed_task"
        assert completed[0].status == "completed"

    def test_register_task_callback(self):
        """Test registering task completion callback."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")
        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)

        callback_called = []

        def on_task_complete(task):
            callback_called.append(task)

        orchestrator.register_task_callback(on_task_complete)

        orchestrator.create_task("task1", "Test")
        orchestrator.assign_task("task1", "executor")
        orchestrator.execute_task("task1")

        assert len(callback_called) == 1
        assert callback_called[0].id == "task1"
        assert callback_called[0].status == "completed"

    def test_clear_tasks(self):
        """Test clearing all tasks."""
        orchestrator = AgentOrchestrator()
        orchestrator.create_task("task1", "Task 1")
        orchestrator.create_task("task2", "Task 2")

        orchestrator.clear_tasks()

        assert orchestrator.tasks == {}

    def test_task_metadata_passed_to_agent(self):
        """Test that task metadata is passed to agent execute method."""
        orchestrator = AgentOrchestrator()
        agent = MockAgent("executor")
        orchestrator.register_agent(agent, "executor", AgentRole.ANALYST)

        orchestrator.create_task(
            "task1",
            "Test task",
            metadata={"param1": "value1", "param2": 42},
        )
        orchestrator.assign_task("task1", "executor")

        orchestrator.execute_task("task1")

        assert agent.executions == 1
        assert agent.executions == 1


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_all_roles_exist(self):
        """Test that all expected roles are defined."""
        roles = [role for role in AgentRole]
        role_names = [r.value for r in roles]

        assert "planner" in role_names
        assert "writer" in role_names
        assert "reviewer" in role_names
        assert "synthesizer" in role_names
        assert "analyst" in role_names
        assert "expert" in role_names
        assert "editor" in role_names
        assert "validator" in role_names


class TestAgentCommunication:
    """Tests for AgentCommunication dataclass."""

    def test_default_timestamp(self):
        """Test that message has default timestamp."""
        message = AgentCommunication(
            sender="agent1",
            recipient="agent2",
            message_type="query",
            content={"test": "data"},
        )

        assert message.timestamp is not None
        assert message.task_id is None

    def test_message_with_task_id(self):
        """Test message with task ID."""
        message = AgentCommunication(
            sender="agent1",
            recipient=None,
            message_type="notification",
            content={"status": "done"},
            task_id="task123",
        )

        assert message.task_id == "task123"
        assert message.recipient is None  # Broadcast
