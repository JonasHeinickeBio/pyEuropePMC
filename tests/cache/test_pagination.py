"""Tests for pagination module."""

import json
import pytest

from pyeuropepmc.pagination import (
    CursorPaginator,
    PaginationCheckpoint,
    PaginationState,
)


class TestPaginationState:
    """Tests for PaginationState."""
    
    def test_init_default(self):
        """Test default initialization."""
        state = PaginationState(query="COVID-19")
        
        assert state.query == "COVID-19"
        assert state.cursor is None
        assert state.page == 1
        assert state.page_size == 25
        assert state.fetched_count == 0
        assert state.last_doc_id is None
        assert state.total_count is None
        assert state.started_at > 0
        assert state.last_updated > 0
        assert not state.completed
    
    def test_init_with_values(self):
        """Test initialization with custom values."""
        state = PaginationState(
            query="cancer",
            cursor="abc123",
            page=5,
            page_size=100,
            fetched_count=400,
            last_doc_id="PMC123456",
            total_count=1000,
            completed=False,
        )
        
        assert state.query == "cancer"
        assert state.cursor == "abc123"
        assert state.page == 5
        assert state.fetched_count == 400
        assert state.last_doc_id == "PMC123456"
        assert state.total_count == 1000
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        state = PaginationState(query="test", page=2, fetched_count=50)
        data = state.to_dict()
        
        assert isinstance(data, dict)
        assert data["query"] == "test"
        assert data["page"] == 2
        assert data["fetched_count"] == 50
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "query": "test",
            "cursor": "xyz",
            "page": 3,
            "page_size": 50,
            "fetched_count": 100,
            "last_doc_id": "doc1",
            "total_count": 500,
            "started_at": 1234567890.0,
            "last_updated": 1234567900.0,
            "completed": False,
        }
        
        state = PaginationState.from_dict(data)
        
        assert state.query == "test"
        assert state.cursor == "xyz"
        assert state.page == 3
        assert state.fetched_count == 100
    
    def test_json_serialization(self):
        """Test JSON serialization round-trip."""
        state1 = PaginationState(
            query="test", page=2, cursor="abc", fetched_count=50
        )
        
        json_str = state1.to_json()
        state2 = PaginationState.from_json(json_str)
        
        assert state2.query == state1.query
        assert state2.page == state1.page
        assert state2.cursor == state1.cursor
        assert state2.fetched_count == state1.fetched_count
    
    def test_update(self):
        """Test update method."""
        state = PaginationState(query="test")
        
        state.update(
            cursor="new_cursor",
            page=2,
            fetched_count=25,
            last_doc_id="doc1",
            total_count=100,
            completed=False,
        )
        
        assert state.cursor == "new_cursor"
        assert state.page == 2
        assert state.fetched_count == 25
        assert state.last_doc_id == "doc1"
        assert state.total_count == 100
        assert not state.completed
    
    def test_progress_percent(self):
        """Test progress percentage calculation."""
        state = PaginationState(query="test", fetched_count=250, total_count=1000)
        
        assert state.progress_percent() == 25.0
    
    def test_progress_percent_no_total(self):
        """Test progress when total unknown."""
        state = PaginationState(query="test", fetched_count=50)
        
        assert state.progress_percent() == 0.0
    
    def test_progress_percent_complete(self):
        """Test progress when complete."""
        state = PaginationState(query="test", fetched_count=100, total_count=100)
        
        assert state.progress_percent() == 100.0
    
    def test_progress_percent_over_100(self):
        """Test progress capped at 100%."""
        state = PaginationState(query="test", fetched_count=150, total_count=100)
        
        assert state.progress_percent() == 100.0
    
    def test_elapsed_time(self):
        """Test elapsed time calculation."""
        import time
        
        state = PaginationState(query="test")
        time.sleep(0.01)  # Sleep 10ms
        state.last_updated = time.time()
        
        elapsed = state.elapsed_time()
        assert elapsed >= 0.01  # At least 10ms
    
    def test_estimated_remaining_time(self):
        """Test estimated remaining time."""
        import time
        
        state = PaginationState(
            query="test",
            fetched_count=250,
            total_count=1000,
            started_at=time.time() - 10.0,  # Started 10 seconds ago
        )
        state.last_updated = time.time()
        
        remaining = state.estimated_remaining_time()
        assert remaining is not None
        assert remaining > 0
        # Should be roughly 30 seconds (10s for 250 docs, 30s more for 750 remaining)
        assert 20 < remaining < 40
    
    def test_estimated_remaining_time_no_total(self):
        """Test estimated time when total unknown."""
        state = PaginationState(query="test", fetched_count=50)
        
        assert state.estimated_remaining_time() is None


class TestPaginationCheckpoint:
    """Tests for PaginationCheckpoint."""
    
    def test_init(self):
        """Test initialization."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        assert checkpoint.cache is cache
        assert checkpoint.prefix == "pagination:checkpoint"
    
    def test_save_and_load(self):
        """Test save and load checkpoint."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        state = PaginationState(
            query="test query",
            page=5,
            fetched_count=100,
            total_count=500,
        )
        
        # Save
        checkpoint.save(state)
        
        # Load
        loaded = checkpoint.load("test query")
        
        assert loaded is not None
        assert loaded.query == "test query"
        assert loaded.page == 5
        assert loaded.fetched_count == 100
        assert loaded.total_count == 500
    
    def test_load_nonexistent(self):
        """Test loading non-existent checkpoint."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        loaded = checkpoint.load("nonexistent query")
        
        assert loaded is None
    
    def test_delete(self):
        """Test delete checkpoint."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        state = PaginationState(query="test")
        checkpoint.save(state)
        
        # Verify exists
        assert checkpoint.exists("test")
        
        # Delete
        checkpoint.delete("test")
        
        # Verify deleted
        assert not checkpoint.exists("test")
    
    def test_exists(self):
        """Test exists check."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        # Initially doesn't exist
        assert not checkpoint.exists("test")
        
        # Save state
        state = PaginationState(query="test")
        checkpoint.save(state)
        
        # Now exists
        assert checkpoint.exists("test")


class TestCursorPaginator:
    """Tests for CursorPaginator."""
    
    def test_init_new(self):
        """Test initialization without checkpoint."""
        paginator = CursorPaginator(query="test", page_size=50)
        
        state = paginator.get_state()
        assert state.query == "test"
        assert state.page_size == 50
        assert state.page == 1
        assert state.fetched_count == 0
    
    def test_init_with_resume(self):
        """Test initialization with checkpoint resumption."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        # Save existing state
        existing_state = PaginationState(
            query="test", page=3, fetched_count=50
        )
        checkpoint.save(existing_state)
        
        # Create paginator with resume
        paginator = CursorPaginator(
            query="test", checkpoint_manager=checkpoint, resume=True
        )
        
        state = paginator.get_state()
        assert state.page == 3
        assert state.fetched_count == 50
    
    def test_update_progress(self):
        """Test progress update."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        paginator = CursorPaginator(
            query="test", checkpoint_manager=checkpoint
        )
        
        # Simulate fetching results
        results = [{"id": f"doc{i}"} for i in range(25)]
        paginator.update_progress(
            results=results, cursor="next_cursor", total_count=100
        )
        
        state = paginator.get_state()
        assert state.fetched_count == 25
        assert state.cursor == "next_cursor"
        assert state.page == 2
        assert state.last_doc_id == "doc24"
        assert state.total_count == 100
    
    def test_update_progress_completion(self):
        """Test completion detection."""
        paginator = CursorPaginator(query="test")
        
        # Update with empty results and no cursor
        paginator.update_progress(results=[], cursor=None)
        
        state = paginator.get_state()
        assert state.completed
        assert paginator.is_complete()
    
    def test_reset(self):
        """Test reset functionality."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        checkpoint = PaginationCheckpoint(cache)
        
        paginator = CursorPaginator(
            query="test", checkpoint_manager=checkpoint
        )
        
        # Make some progress
        results = [{"id": f"doc{i}"} for i in range(25)]
        paginator.update_progress(results=results)
        
        assert paginator.get_state().fetched_count == 25
        
        # Reset
        paginator.reset()
        
        # State reset
        state = paginator.get_state()
        assert state.page == 1
        assert state.fetched_count == 0
        assert not checkpoint.exists("test")
