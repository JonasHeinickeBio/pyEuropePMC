"""
Tests for TaskPlanner.

This module tests:
- Task creation and management
- Task decomposition logic
- Complexity estimation
- Task tree visualization
- Ready task identification
"""

import pytest
from unittest.mock import Mock

from pyeuropepmc.agentic.task_planner import (
    TaskPlanner,
    TaskNode,
    TaskStatus,
)


class TestTaskPlanner:
    """Tests for TaskPlanner class."""

    def test_init_sets_default_parameters(self):
        """Test that TaskPlanner initializes with default parameters."""
        planner = TaskPlanner()

        assert planner.max_depth == 4
        assert planner.max_subtasks_per_node == 5
        assert planner.min_task_complexity == 3
        assert planner.task_count == 0

    def test_create_task_creates_node(self):
        """Test creating a task node."""
        planner = TaskPlanner()
        task = planner.create_task("Test task description")

        assert task.task_id is not None
        assert task.description == "Test task description"
        assert task.parent_id is None
        assert task.depth == 0
        assert task.status == TaskStatus.PENDING
        assert len(task.subtasks) == 0

    def test_create_task_with_parent(self):
        """Test creating a child task."""
        planner = TaskPlanner()
        parent = planner.create_task("Parent task")
        child = planner.create_task("Child task", parent_id=parent.task_id, depth=1)

        assert child.parent_id == parent.task_id
        assert child.depth == 1

    def test_estimate_complexity_short_description(self):
        """Test complexity estimation for short descriptions."""
        planner = TaskPlanner()

        # Simple task should have low complexity
        complexity = planner._estimate_complexity("Find papers about cancer")
        assert complexity >= 0
        assert complexity <= 10

    def test_estimate_complexity_long_description(self):
        """Test complexity estimation for long descriptions."""
        planner = TaskPlanner()

        long_desc = (
            "Investigate the efficacy of CRISPR-Cas9 gene editing in treating "
            "sickle cell disease by analyzing recent clinical trials, comparing "
            "outcomes across different patient populations, and evaluating the "
            "long-term safety and effectiveness of the treatment approach"
        )
        complexity = planner._estimate_complexity(long_desc)
        assert complexity > 3  # Should be decomposable

    def test_estimate_complexity_keywords(self):
        """Test complexity estimation with research keywords."""
        planner = TaskPlanner()

        # Description with multiple research keywords
        desc = (
            "Analyze and compare the impact of exercise on depression and anxiety in adolescents"
        )
        complexity = planner._estimate_complexity(desc)

        # Should have higher complexity due to keywords
        assert complexity >= 2

    def test_generate_subtasks_research_question(self):
        """Test decomposition of research questions."""
        planner = TaskPlanner()

        desc = "Investigate CRISPR efficacy in sickle cell disease"
        subtasks = planner._generate_subtasks(desc)

        assert len(subtasks) > 0
        # Should split into logical subtasks
        assert any("Find" in s for s in subtasks)
        assert any("Analyze" in s for s in subtasks)

    def test_generate_subtasks_step_sequence(self):
        """Test decomposition of step sequences."""
        planner = TaskPlanner()

        desc = "Search first, then screen, finally analyze"
        subtasks = planner._generate_subtasks(desc)

        assert len(subtasks) > 0

    def test_generate_subtasks_systematic_review(self):
        """Test decomposition of systematic review tasks."""
        planner = TaskPlanner()

        desc = "Conduct a systematic review of meta-analysis studies"
        subtasks = planner._generate_subtasks(desc)

        assert len(subtasks) > 0
        # Should include PRISMA-style steps
        assert any("criteria" in s.lower() or "search" in s.lower() for s in subtasks)

    def test_decompose_task_creates_subtasks(self):
        """Test task decomposition creates subtasks."""
        planner = TaskPlanner(max_depth=2, min_task_complexity=1)

        task = planner.create_task(
            "Investigate CRISPR in sickle cell disease by analyzing clinical outcomes and comparing with standard therapy"
        )

        subtask_ids = planner.decompose_task(task)

        assert len(subtask_ids) > 0
        assert len(task.subtasks) > 0
        assert task.status == TaskStatus.DECOMPOSED

    def test_decompose_task_respects_max_depth(self):
        """Test that decomposition respects max depth limit."""
        planner = TaskPlanner(max_depth=2, max_subtasks_per_node=2)

        task = planner.create_task(
            "Investigate CRISPR in sickle cell disease by analyzing clinical outcomes"
        )
        planner.decompose_task(task)

        # Get subtasks
        subtasks = [planner._tasks[tid] for tid in task.subtasks]

        # All subtasks should be at depth 1
        for subtask in subtasks:
            assert subtask.depth == 1

    def test_decompose_task_respects_max_subtasks(self):
        """Test that decomposition respects max subtasks per node."""
        planner = TaskPlanner(max_subtasks_per_node=2)

        # Create a complex task that would normally generate many subtasks
        task = planner.create_task(
            "Compare A, B, C, D, E, F, G in terms of X, Y, Z and evaluate their relationships"
        )

        subtask_ids = planner.decompose_task(task)

        assert len(subtask_ids) <= planner.max_subtasks_per_node

    def test_decompose_task_complexity_threshold(self):
        """Test that low-complexity tasks are not decomposed."""
        planner = TaskPlanner(min_task_complexity=5)

        # Simple task below complexity threshold
        task = planner.create_task("Find papers")

        subtask_ids = planner.decompose_task(task)

        # Should return empty list (no decomposition)
        assert len(subtask_ids) == 0
        assert task.status != TaskStatus.DECOMPOSED

    def test_get_task_tree(self):
        """Test task tree generation."""
        planner = TaskPlanner()

        # Create a tree: A -> B -> C
        root = planner.create_task("Root task")
        child = planner.create_task("Child", parent_id=root.task_id, depth=1)
        grandchild = planner.create_task("Grandchild", parent_id=child.task_id, depth=2)

        root.subtasks.append(child.task_id)
        child.subtasks.append(grandchild.task_id)

        tree = planner.get_task_tree(root.task_id)

        assert "task_id" in tree
        assert "children" in tree
        assert len(tree["children"]) == 1

    def test_get_ready_tasks(self):
        """Test getting ready tasks (no dependencies)."""
        planner = TaskPlanner()

        # Create independent tasks
        task1 = planner.create_task("Task 1")
        task2 = planner.create_task("Task 2")
        # Parent task that's not completed
        parent = planner.create_task("Parent")

        ready = planner.get_ready_tasks()

        # Only tasks without parents should be ready
        ready_ids = [t.task_id for t in ready]
        assert task1.task_id in ready_ids
        assert task2.task_id in ready_ids
        assert parent.task_id in ready_ids

    def test_update_task_status(self):
        """Test updating task status."""
        planner = TaskPlanner()

        task = planner.create_task("Test task")

        result = planner.update_task_status(task.task_id, TaskStatus.COMPLETED, {"data": "result"})

        assert result is True
        assert task.status == TaskStatus.COMPLETED
        assert task.result == {"data": "result"}
        assert task.completed_at is not None

    def test_update_task_status_invalid_task(self):
        """Test updating status of non-existent task."""
        planner = TaskPlanner()

        result = planner.update_task_status("invalid_id", TaskStatus.COMPLETED)

        assert result is False

    def test_reset_clears_tasks(self):
        """Test resetting the planner."""
        planner = TaskPlanner()

        task = planner.create_task("Test task")
        assert planner.task_count == 1

        planner.reset()

        assert planner.task_count == 0

    def test_leaf_tasks(self):
        """Test getting leaf tasks."""
        planner = TaskPlanner()

        root = planner.create_task("Root")
        child1 = planner.create_task("Child 1", parent_id=root.task_id)
        child2 = planner.create_task("Child 2", parent_id=root.task_id)

        root.subtasks.append(child1.task_id)
        root.subtasks.append(child2.task_id)

        leaf_tasks = planner.leaf_tasks

        assert len(leaf_tasks) == 2
        assert child1 in leaf_tasks
        assert child2 in leaf_tasks
        assert root not in leaf_tasks

    def test_task_node_serialization(self):
        """Test TaskNode to_dict and from_dict."""
        node = TaskNode(
            task_id="test-123",
            description="Test task",
            parent_id=None,
            depth=0,
            status=TaskStatus.PENDING,
        )

        # Serialize
        data = node.to_dict()

        assert data["task_id"] == "test-123"
        assert data["status"] == "pending"

        # Deserialize
        new_node = TaskNode.from_dict(data)

        assert new_node.task_id == "test-123"
        assert new_node.description == "Test task"
        assert new_node.status == TaskStatus.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
