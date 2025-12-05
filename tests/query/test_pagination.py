"""
Unit tests for pagination functionality.
"""

from unittest.mock import Mock

import pytest

from pyeuropepmc.query.pagination import (
    CursorPaginator,
    PaginationCheckpoint,
    PaginationState,
)


class TestPaginationState:
    """Test PaginationState class."""

    def test_state_creation(self):
        """Test basic state creation."""
        state = PaginationState(
            query="test query",
            cursor="cursor123",
            page=5,
            page_size=50,
            fetched_count=200,
            last_doc_id="doc123",
            total_count=1000,
        )

        assert state.query == "test query"
        assert state.cursor == "cursor123"
        assert state.page == 5
        assert state.page_size == 50
        assert state.fetched_count == 200
        assert state.last_doc_id == "doc123"
        assert state.total_count == 1000
        assert state.completed is False
        assert state.started_at > 0
        assert state.last_updated > 0

    def test_state_to_dict(self):
        """Test state serialization."""
        state = PaginationState(
            query="test query",
            cursor="cursor123",
            fetched_count=100,
        )

        data = state.to_dict()
        assert data["query"] == "test query"
        assert data["cursor"] == "cursor123"
        assert data["fetched_count"] == 100
        assert "started_at" in data
        assert "last_updated" in data

    def test_state_from_dict(self):
        """Test state deserialization."""
        original = PaginationState(
            query="test query",
            cursor="cursor123",
            fetched_count=100,
        )

        data = original.to_dict()
        restored = PaginationState.from_dict(data)

        assert restored.query == original.query
        assert restored.cursor == original.cursor
        assert restored.fetched_count == original.fetched_count

    def test_state_json_serialization(self):
        """Test JSON serialization."""
        state = PaginationState(query="test query", fetched_count=50)

        json_str = state.to_json()
        restored = PaginationState.from_json(json_str)

        assert restored.query == state.query
        assert restored.fetched_count == state.fetched_count

    def test_state_update(self):
        """Test state updates."""
        state = PaginationState(query="test query")

        state.update(cursor="new_cursor", page=2, fetched_count=25)

        assert state.cursor == "new_cursor"
        assert state.page == 2
        assert state.fetched_count == 25
        assert state.last_updated > state.started_at

    def test_progress_percent(self):
        """Test progress percentage calculation."""
        state = PaginationState(query="test query", fetched_count=50, total_count=200)
        assert state.progress_percent() == 25.0

        # No total count
        state.total_count = None
        assert state.progress_percent() == 0.0

    def test_elapsed_time(self):
        """Test elapsed time calculation."""
        import time

        state = PaginationState(query="test query")
        time.sleep(0.01)  # Small delay
        state.update()  # Update last_updated timestamp

        elapsed = state.elapsed_time()
        assert elapsed > 0

    def test_estimated_remaining_time(self):
        """Test remaining time estimation."""
        state = PaginationState(
            query="test query",
            fetched_count=50,
            total_count=200,
            started_at=1000.0,
            last_updated=1010.0,  # 10 seconds elapsed
        )

        # 50 fetched in 10 seconds, 150 remaining, so ~30 seconds
        estimated = state.estimated_remaining_time()
        assert estimated is not None
        assert 25 <= estimated <= 35  # Allow some variance

        # No total count
        state.total_count = None
        assert state.estimated_remaining_time() is None


class TestPaginationCheckpoint:
    """Test PaginationCheckpoint class."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache backend."""
        cache = Mock()
        cache._normalize_key = Mock(return_value="normalized:key")
        return cache

    @pytest.fixture
    def checkpoint(self, mock_cache):
        """Create a pagination checkpoint manager."""
        return PaginationCheckpoint(mock_cache)

    def test_checkpoint_creation(self, checkpoint):
        """Test checkpoint creation."""
        assert checkpoint.cache is not None
        assert checkpoint.prefix == "pagination:checkpoint"

    def test_key_normalization(self, checkpoint):
        """Test key normalization."""
        key = checkpoint._make_key("test query")
        assert key == "normalized:key"

    def test_save_checkpoint(self, checkpoint, mock_cache):
        """Test saving checkpoint."""
        state = PaginationState(query="test query", fetched_count=100)

        checkpoint.save(state)

        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "normalized:key"
        assert call_args[0][1] == state.to_dict()
        assert call_args[1]["expire"] == 604800  # 7 days

    def test_load_checkpoint(self, checkpoint, mock_cache):
        """Test loading checkpoint."""
        state_dict = {"query": "test query", "fetched_count": 100}
        mock_cache.get.return_value = state_dict

        result = checkpoint.load("test query")

        assert result is not None
        assert result.query == "test query"
        assert result.fetched_count == 100
        mock_cache.get.assert_called_once_with("normalized:key")

    def test_load_checkpoint_not_found(self, checkpoint, mock_cache):
        """Test loading nonexistent checkpoint."""
        mock_cache.get.return_value = None

        result = checkpoint.load("test query")

        assert result is None

    def test_delete_checkpoint(self, checkpoint, mock_cache):
        """Test deleting checkpoint."""
        checkpoint.delete("test query")

        mock_cache.delete.assert_called_once_with("normalized:key")

    def test_exists_checkpoint(self, checkpoint, mock_cache):
        """Test checking checkpoint existence."""
        mock_cache.get.return_value = {"query": "test"}

        result = checkpoint.exists("test query")

        assert result is True
        mock_cache.get.assert_called_once_with("normalized:key")

    def test_exists_checkpoint_not_found(self, checkpoint, mock_cache):
        """Test checking nonexistent checkpoint."""
        mock_cache.get.return_value = None

        result = checkpoint.exists("test query")

        assert result is False


class TestCursorPaginator:
    """Test CursorPaginator class."""

    @pytest.fixture
    def mock_checkpoint(self):
        """Create a mock checkpoint manager."""
        return Mock()

    def test_paginator_creation_no_resume(self, mock_checkpoint):
        """Test paginator creation without resume."""
        paginator = CursorPaginator(
            query="test query",
            page_size=25,
            checkpoint_manager=None,
        )

        assert paginator.query == "test query"
        assert paginator.page_size == 25
        assert paginator.state is not None
        assert paginator.state.query == "test query"
        assert paginator.state.page_size == 25

    def test_paginator_creation_with_resume(self, mock_checkpoint):
        """Test paginator creation with resume."""
        existing_state = PaginationState(query="test query", fetched_count=50)
        mock_checkpoint.load.return_value = existing_state

        paginator = CursorPaginator(
            query="test query",
            page_size=25,
            checkpoint_manager=mock_checkpoint,
            resume=True,
        )

        assert paginator.state == existing_state
        mock_checkpoint.load.assert_called_once_with("test query")

    def test_update_progress(self):
        """Test progress updates."""
        paginator = CursorPaginator(query="test query", checkpoint_manager=None)

        results = [{"id": "doc1"}, {"id": "doc2"}]
        paginator.update_progress(results, cursor="next_cursor", total_count=100)

        state = paginator.get_state()
        assert state.cursor == "next_cursor"
        assert state.page == 2  # Incremented
        assert state.fetched_count == 2
        assert state.last_doc_id == "doc2"
        assert state.total_count == 100
        assert not state.completed

    def test_update_progress_completion(self):
        """Test progress update with completion."""
        paginator = CursorPaginator(query="test query", checkpoint_manager=None)

        # No cursor and no results = completion
        paginator.update_progress([], cursor=None, total_count=50)

        state = paginator.get_state()
        assert state.completed is True

    def test_get_state(self, mock_checkpoint):
        """Test getting current state."""
        paginator = CursorPaginator(query="test query")

        state = paginator.get_state()
        assert isinstance(state, PaginationState)
        assert state.query == "test query"

    def test_is_complete(self, mock_checkpoint):
        """Test completion checking."""
        paginator = CursorPaginator(query="test query")

        assert not paginator.is_complete()

        paginator.state.completed = True
        assert paginator.is_complete()

    def test_reset(self):
        """Test pagination reset."""
        paginator = CursorPaginator(query="test query", checkpoint_manager=None)

        # Modify state
        if paginator.state:
            paginator.state.page = 5
            paginator.state.fetched_count = 100

        paginator.reset()

        state = paginator.get_state()
        assert state.page == 1
        assert state.fetched_count == 0
        assert state.completed is False
