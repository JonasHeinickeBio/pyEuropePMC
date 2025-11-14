"""
Pagination state management for PyEuropePMC.

This module provides cursor-based pagination support and checkpointing
for long-running crawls with resume capability.
"""

from dataclasses import asdict, dataclass
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PaginationState:
    """
    State for cursor-based pagination.

    Attributes:
        query: The search query being paginated
        cursor: Current pagination cursor (if supported by API)
        page: Current page number (fallback if no cursor support)
        page_size: Number of results per page
        fetched_count: Total number of documents fetched so far
        last_doc_id: ID of the last document fetched (for resumption)
        total_count: Total number of results (if known)
        started_at: Unix timestamp when pagination started
        last_updated: Unix timestamp of last update
        completed: Whether pagination is complete
    """

    query: str
    cursor: str | None = None
    page: int = 1
    page_size: int = 25
    fetched_count: int = 0
    last_doc_id: str | None = None
    total_count: int | None = None
    started_at: float = 0.0
    last_updated: float = 0.0
    completed: bool = False

    def __post_init__(self) -> None:
        """Initialize timestamps if not set."""
        if self.started_at == 0.0:
            self.started_at = time.time()
        if self.last_updated == 0.0:
            self.last_updated = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaginationState":
        """Create from dictionary."""
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "PaginationState":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def update(
        self,
        cursor: str | None = None,
        page: int | None = None,
        fetched_count: int | None = None,
        last_doc_id: str | None = None,
        total_count: int | None = None,
        completed: bool | None = None,
    ) -> None:
        """
        Update pagination state.

        Args:
            cursor: New cursor value
            page: New page number
            fetched_count: Update fetched count
            last_doc_id: ID of last fetched document
            total_count: Total result count
            completed: Whether pagination is complete
        """
        if cursor is not None:
            self.cursor = cursor
        if page is not None:
            self.page = page
        if fetched_count is not None:
            self.fetched_count = fetched_count
        if last_doc_id is not None:
            self.last_doc_id = last_doc_id
        if total_count is not None:
            self.total_count = total_count
        if completed is not None:
            self.completed = completed

        self.last_updated = time.time()

    def progress_percent(self) -> float:
        """
        Calculate progress percentage.

        Returns:
            Progress as percentage (0-100), or 0 if total unknown
        """
        if self.total_count and self.total_count > 0:
            return min(100.0, (self.fetched_count / self.total_count) * 100)
        return 0.0

    def elapsed_time(self) -> float:
        """
        Calculate elapsed time since start.

        Returns:
            Elapsed seconds
        """
        return self.last_updated - self.started_at

    def estimated_remaining_time(self) -> float | None:
        """
        Estimate remaining time based on current progress.

        Returns:
            Estimated remaining seconds, or None if cannot estimate
        """
        if not self.total_count or self.fetched_count == 0:
            return None

        elapsed = self.elapsed_time()
        if elapsed == 0:
            return None

        rate = self.fetched_count / elapsed  # docs per second
        remaining = self.total_count - self.fetched_count

        if rate > 0:
            return remaining / rate
        return None


class PaginationCheckpoint:
    """
    Checkpoint manager for long-running crawls.

    Enables saving and resuming pagination state using a cache backend.
    """

    def __init__(self, cache_backend: Any, checkpoint_prefix: str = "pagination:checkpoint"):
        """
        Initialize checkpoint manager.

        Args:
            cache_backend: Cache backend (e.g., CacheBackend instance)
            checkpoint_prefix: Prefix for checkpoint keys
        """
        self.cache = cache_backend
        self.prefix = checkpoint_prefix
        self._lock: dict[str, Any] = {}  # Per-key locks for thread safety

    def _make_key(self, query: str) -> str:
        """
        Create checkpoint key for a query.

        Args:
            query: Search query

        Returns:
            Checkpoint cache key
        """
        # Use cache's normalization if available
        if hasattr(self.cache, "_normalize_key"):
            return str(self.cache._normalize_key(self.prefix, query=query))

        # Fallback to simple key
        import hashlib

        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"{self.prefix}:{query_hash}"

    def save(self, state: PaginationState) -> None:
        """
        Save pagination state as checkpoint.

        Args:
            state: Pagination state to save
        """
        key = self._make_key(state.query)

        try:
            # Save with long TTL (7 days) for resumption
            self.cache.set(key, state.to_dict(), expire=604800)
            logger.debug(
                f"Saved pagination checkpoint: query={state.query}, "
                f"fetched={state.fetched_count}, page={state.page}"
            )
        except Exception as e:
            logger.warning(f"Failed to save pagination checkpoint: {e}")

    def load(self, query: str) -> PaginationState | None:
        """
        Load pagination state from checkpoint.

        Args:
            query: Search query

        Returns:
            Pagination state if found, None otherwise
        """
        key = self._make_key(query)

        try:
            data = self.cache.get(key)
            if data:
                state = PaginationState.from_dict(data)
                logger.debug(
                    f"Loaded pagination checkpoint: query={query}, "
                    f"fetched={state.fetched_count}, page={state.page}"
                )
                return state
        except Exception as e:
            logger.warning(f"Failed to load pagination checkpoint: {e}")

        return None

    def delete(self, query: str) -> None:
        """
        Delete pagination checkpoint.

        Args:
            query: Search query
        """
        key = self._make_key(query)

        try:
            self.cache.delete(key)
            logger.debug(f"Deleted pagination checkpoint: query={query}")
        except Exception as e:
            logger.warning(f"Failed to delete pagination checkpoint: {e}")

    def exists(self, query: str) -> bool:
        """
        Check if checkpoint exists for query.

        Args:
            query: Search query

        Returns:
            True if checkpoint exists
        """
        key = self._make_key(query)

        try:
            return self.cache.get(key) is not None
        except Exception:
            return False


class CursorPaginator:
    """
    Cursor-based paginator with checkpoint support.

    Manages pagination state and provides iteration interface.
    """

    def __init__(
        self,
        query: str,
        page_size: int = 25,
        checkpoint_manager: PaginationCheckpoint | None = None,
        resume: bool = True,
    ):
        """
        Initialize cursor paginator.

        Args:
            query: Search query
            page_size: Results per page
            checkpoint_manager: Optional checkpoint manager for resumption
            resume: Whether to resume from checkpoint if available
        """
        self.query = query
        self.page_size = page_size
        self.checkpoint_manager = checkpoint_manager

        # Try to resume from checkpoint
        self.state: PaginationState | None = None
        if resume and checkpoint_manager:
            self.state = checkpoint_manager.load(query)

        # Initialize new state if not resuming
        if not self.state:
            self.state = PaginationState(query=query, page_size=page_size)

    def update_progress(
        self,
        results: list[Any],
        cursor: str | None = None,
        total_count: int | None = None,
    ) -> None:
        """
        Update pagination progress after fetching results.

        Args:
            results: Fetched results
            cursor: Next cursor value
            total_count: Total result count if known
        """
        if not self.state:
            return

        # Update state
        fetched_count = self.state.fetched_count + len(results)
        last_doc_id = results[-1].get("id") if results else None

        self.state.update(
            cursor=cursor,
            page=self.state.page + 1,
            fetched_count=fetched_count,
            last_doc_id=last_doc_id,
            total_count=total_count,
            completed=(cursor is None and len(results) == 0),
        )

        # Save checkpoint
        if self.checkpoint_manager:
            self.checkpoint_manager.save(self.state)

    def get_state(self) -> PaginationState:
        """
        Get current pagination state.

        Returns:
            Current pagination state
        """
        if not self.state:
            self.state = PaginationState(query=self.query, page_size=self.page_size)
        return self.state

    def is_complete(self) -> bool:
        """
        Check if pagination is complete.

        Returns:
            True if pagination finished
        """
        return self.state.completed if self.state else False

    def reset(self) -> None:
        """Reset pagination to start."""
        self.state = PaginationState(query=self.query, page_size=self.page_size)

        if self.checkpoint_manager:
            self.checkpoint_manager.delete(self.query)
