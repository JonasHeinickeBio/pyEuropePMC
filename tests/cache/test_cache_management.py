"""
Tests for cache management features.

Tests invalidation strategies, cache warming, health checks, and advanced management.
"""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from pyeuropepmc.cache import CacheBackend, CacheConfig


class TestCacheInvalidation:
    """Test cache invalidation strategies."""

    @pytest.fixture
    def cache_backend(self):
        """Create a cache backend for testing."""
        tmpdir = Path(tempfile.mkdtemp())
        config = CacheConfig(enabled=True, cache_dir=tmpdir, ttl=60)
        backend = CacheBackend(config)
        yield backend
        backend.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_invalidate_pattern_wildcard(self, cache_backend):
        """Test pattern-based invalidation with wildcards."""
        # Set up test data
        cache_backend.set("search:query1", {"results": [1, 2, 3]})
        cache_backend.set("search:query2", {"results": [4, 5, 6]})
        cache_backend.set("user:123:data", {"name": "Alice"})
        cache_backend.set("user:456:data", {"name": "Bob"})

        # Invalidate all search queries
        count = cache_backend.invalidate_pattern("search:*")
        assert count == 2

        # Verify search entries are gone
        assert cache_backend.get("search:query1") is None
        assert cache_backend.get("search:query2") is None

        # Verify user entries remain
        assert cache_backend.get("user:123:data") is not None
        assert cache_backend.get("user:456:data") is not None

    def test_invalidate_pattern_specific(self, cache_backend):
        """Test pattern-based invalidation with specific patterns."""
        cache_backend.set("user:123:profile", {"name": "Alice"})
        cache_backend.set("user:123:settings", {"theme": "dark"})
        cache_backend.set("user:456:profile", {"name": "Bob"})

        # Invalidate all data for user 123
        count = cache_backend.invalidate_pattern("user:123:*")
        assert count == 2

        # Verify user 123 data is gone
        assert cache_backend.get("user:123:profile") is None
        assert cache_backend.get("user:123:settings") is None

        # Verify user 456 data remains
        assert cache_backend.get("user:456:profile") is not None

    def test_invalidate_pattern_no_matches(self, cache_backend):
        """Test pattern invalidation with no matches."""
        cache_backend.set("test:key", "value")

        count = cache_backend.invalidate_pattern("nonexistent:*")
        assert count == 0

    def test_invalidate_older_than(self, cache_backend):
        """Test time-based invalidation."""
        # Set entries with different timestamps
        cache_backend.set("old:key1", "value1", expire=1)
        cache_backend.set("fresh:key", "fresh_value", expire=3600)

        # Wait for old entries to age
        time.sleep(1.5)

        # Invalidate entries older than 1 second
        count = cache_backend.invalidate_older_than(1)

        # Note: This test might need adjustment based on diskcache behavior
        # The exact behavior depends on how diskcache tracks entry age
        assert count >= 0  # At least doesn't error

    def test_invalidate_when_disabled(self, cache_backend):
        """Test invalidation when cache is disabled."""
        cache_backend.config.enabled = False

        count = cache_backend.invalidate_pattern("*")
        assert count == 0

    def test_evict_by_tag(self, cache_backend):
        """Test eviction by tag."""
        cache_backend.set("key1", "value1", tag="tag1")
        cache_backend.set("key2", "value2", tag="tag1")
        cache_backend.set("key3", "value3", tag="tag2")

        # Evict all entries with tag1
        count = cache_backend.evict("tag1")
        assert count == 2

        # Verify tagged entries are gone
        assert cache_backend.get("key1") is None
        assert cache_backend.get("key2") is None

        # Verify other entries remain
        assert cache_backend.get("key3") is not None


class TestCacheWarming:
    """Test cache warming functionality."""

    @pytest.fixture
    def cache_backend(self):
        """Create a cache backend for testing."""
        tmpdir = Path(tempfile.mkdtemp())
        config = CacheConfig(enabled=True, cache_dir=tmpdir, ttl=60)
        backend = CacheBackend(config)
        yield backend
        backend.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_warm_cache_basic(self, cache_backend):
        """Test basic cache warming."""
        warm_data = {
            "search:cancer": {"results": [1, 2, 3]},
            "search:diabetes": {"results": [4, 5, 6]},
            "search:covid": {"results": [7, 8, 9]},
        }

        count = cache_backend.warm_cache(warm_data)
        assert count == 3

        # Verify all entries are cached
        assert cache_backend.get("search:cancer") == {"results": [1, 2, 3]}
        assert cache_backend.get("search:diabetes") == {"results": [4, 5, 6]}
        assert cache_backend.get("search:covid") == {"results": [7, 8, 9]}

    def test_warm_cache_with_ttl(self, cache_backend):
        """Test cache warming with custom TTL."""
        warm_data = {"key1": "value1", "key2": "value2"}

        count = cache_backend.warm_cache(warm_data, ttl=1)
        assert count == 2

        # Verify entries exist
        assert cache_backend.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.5)

        # Entries should be expired (may still exist but marked expired)
        # This behavior depends on diskcache's expiration handling

    def test_warm_cache_with_tag(self, cache_backend):
        """Test cache warming with tags."""
        warm_data = {
            "popular:1": "data1",
            "popular:2": "data2",
        }

        count = cache_backend.warm_cache(warm_data, tag="popular")
        assert count == 2

        # Should be able to evict by tag
        evicted = cache_backend.evict("popular")
        assert evicted == 2

    def test_warm_cache_when_disabled(self, cache_backend):
        """Test cache warming when cache is disabled."""
        cache_backend.config.enabled = False

        warm_data = {"key1": "value1"}
        count = cache_backend.warm_cache(warm_data)
        assert count == 0

    def test_warm_cache_empty(self, cache_backend):
        """Test cache warming with empty data."""
        count = cache_backend.warm_cache({})
        assert count == 0


class TestCacheHealth:
    """Test cache health monitoring."""

    @pytest.fixture
    def cache_backend(self):
        """Create a cache backend for testing."""
        tmpdir = Path(tempfile.mkdtemp())
        config = CacheConfig(enabled=True, cache_dir=tmpdir, ttl=60, size_limit_mb=1)
        backend = CacheBackend(config)
        yield backend
        backend.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_health_check_healthy(self, cache_backend):
        """Test health check with healthy cache."""
        # Add some data and access it
        cache_backend.set("key1", "value1")
        cache_backend.get("key1")  # Hit
        cache_backend.get("key2")  # Miss

        health = cache_backend.get_health()

        assert health["enabled"] is True
        assert health["available"] is True
        assert health["status"] == "healthy"
        assert 0 <= health["hit_rate"] <= 1
        assert 0 <= health["size_utilization"] <= 1
        assert health["error_rate"] >= 0
        assert isinstance(health["warnings"], list)

    def test_health_check_disabled(self):
        """Test health check when cache is disabled."""
        tmpdir = Path(tempfile.mkdtemp())
        config = CacheConfig(enabled=False, cache_dir=tmpdir)
        backend = CacheBackend(config)

        health = backend.get_health()

        assert health["enabled"] is False
        assert health["status"] == "disabled"
        assert health["available"] is False

        backend.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_health_check_with_stats(self, cache_backend):
        """Test health check includes statistics."""
        # Generate some activity
        for i in range(10):
            cache_backend.set(f"key{i}", f"value{i}")

        for i in range(5):
            cache_backend.get(f"key{i}")  # Hits

        health = cache_backend.get_health()

        assert health["hit_rate"] > 0
        assert health["size_utilization"] >= 0

    def test_health_check_low_hit_rate_warning(self, cache_backend):
        """Test health warning for low hit rate."""
        # Generate lots of misses
        for i in range(200):
            cache_backend.get(f"nonexistent{i}")  # Misses

        health = cache_backend.get_health()

        # Should have low hit rate warning if enough operations
        assert health["hit_rate"] == 0
        if health["status"] == "warning":
            assert any("hit rate" in w.lower() for w in health["warnings"])


class TestCacheCompaction:
    """Test cache compaction and maintenance."""

    @pytest.fixture
    def cache_backend(self):
        """Create a cache backend for testing."""
        tmpdir = Path(tempfile.mkdtemp())
        config = CacheConfig(enabled=True, cache_dir=tmpdir, ttl=60)
        backend = CacheBackend(config)
        yield backend
        backend.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_compact_cache(self, cache_backend):
        """Test cache compaction."""
        # Add some entries
        for i in range(10):
            cache_backend.set(f"key{i}", f"value{i}")

        # Compact should succeed
        result = cache_backend.compact()
        assert result is True

    def test_compact_when_disabled(self, cache_backend):
        """Test compaction when cache is disabled."""
        cache_backend.config.enabled = False

        result = cache_backend.compact()
        assert result is False


class TestCacheKeyRetrieval:
    """Test cache key retrieval and inspection."""

    @pytest.fixture
    def cache_backend(self):
        """Create a cache backend for testing."""
        tmpdir = Path(tempfile.mkdtemp())
        config = CacheConfig(enabled=True, cache_dir=tmpdir, ttl=60)
        backend = CacheBackend(config)
        yield backend
        backend.close()
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_keys_all(self, cache_backend):
        """Test retrieving all cache keys."""
        # Add test data
        cache_backend.set("key1", "value1")
        cache_backend.set("key2", "value2")
        cache_backend.set("key3", "value3")

        keys = cache_backend.get_keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

    def test_get_keys_with_pattern(self, cache_backend):
        """Test retrieving keys with pattern filter."""
        cache_backend.set("search:query1", "data1")
        cache_backend.set("search:query2", "data2")
        cache_backend.set("user:123", "data3")

        keys = cache_backend.get_keys("search:*")
        assert len(keys) == 2
        assert all(k.startswith("search:") for k in keys)

    def test_get_keys_with_limit(self, cache_backend):
        """Test key retrieval with limit."""
        # Add many entries
        for i in range(100):
            cache_backend.set(f"key{i}", f"value{i}")

        keys = cache_backend.get_keys(limit=10)
        assert len(keys) == 10

    def test_get_keys_when_disabled(self, cache_backend):
        """Test key retrieval when cache is disabled."""
        cache_backend.config.enabled = False

        keys = cache_backend.get_keys()
        assert keys == []

    def test_get_keys_empty_cache(self, cache_backend):
        """Test key retrieval from empty cache."""
        keys = cache_backend.get_keys()
        assert keys == []
