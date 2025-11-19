"""
Unit tests for cache backend functionality.
"""

import tempfile
import time
from pathlib import Path

import pytest

from pyeuropepmc.cache.cache import (
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
    CACHETOOLS_AVAILABLE,
)


class TestCacheConfig:
    """Test CacheConfig class."""

    def test_cache_config_defaults(self):
        """Test CacheConfig with default values."""
        config = CacheConfig()
        assert config.enabled is True  # Default is True if CACHETOOLS_AVAILABLE
        assert config.ttl == 86400  # 24 hours default
        assert config.size_limit_mb == 500
        assert config.cache_dir is not None
        assert isinstance(config.cache_dir, Path)
        assert config.ttl_by_type is not None
        assert isinstance(config.ttl_by_type, dict)

    def test_cache_config_custom_values(self):
        """Test CacheConfig with custom values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(
                enabled=True,
                ttl=7200,
                size_limit_mb=250,
                cache_dir=Path(temp_dir),
                ttl_by_type={CacheDataType.SEARCH: 1800},
            )
            assert config.enabled is True
            assert config.ttl == 7200
            assert config.size_limit_mb == 250
            assert config.cache_dir == Path(temp_dir)
            assert config.ttl_by_type[CacheDataType.SEARCH] == 1800

    def test_cache_config_get_ttl_for_data_type(self):
        """Test getting TTL for specific data types."""
        config = CacheConfig(ttl=3600, ttl_by_type={CacheDataType.SEARCH: 1800})

        # Default TTL
        assert config.get_ttl() == 3600

        # Specific data type TTL
        assert config.get_ttl(CacheDataType.SEARCH) == 1800

        # Fallback to default for unspecified data types
        assert config.get_ttl(CacheDataType.RECORD) == 86400


@pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
class TestCacheBackend:
    """Test CacheBackend class."""

    def test_cache_backend_initialization_disabled(self):
        """Test CacheBackend initialization with caching disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)

        assert backend.config == config
        assert backend.l1_cache is None
        assert backend.l2_cache is None

    def test_cache_backend_initialization_enabled(self):
        """Test CacheBackend initialization with caching enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            assert backend.config == config
            assert backend.l1_cache is not None
            assert backend.l2_cache is None  # L2 disabled by default

            backend.close()

    def test_cache_backend_get_disabled(self):
        """Test get method when caching is disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)

        result = backend.get("test_key")
        assert result is None

    def test_cache_backend_set_disabled(self):
        """Test set method when caching is disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)

        result = backend.set("test_key", "test_value")
        assert result is False

    def test_cache_backend_delete_disabled(self):
        """Test delete method when caching is disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)

        result = backend.delete("test_key")
        assert result is False

    def test_cache_backend_clear_disabled(self):
        """Test clear method when caching is disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)

        result = backend.clear()
        assert result is False

    def test_cache_backend_basic_operations(self):
        """Test basic cache operations (get, set, delete, clear)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir), ttl=60)
            backend = CacheBackend(config)

            # Test set and get
            assert backend.set("test_key", "test_value")
            assert backend.get("test_key") == "test_value"

            # Test delete
            assert backend.delete("test_key")
            assert backend.get("test_key") is None

            # Test clear
            assert backend.set("key1", "value1")
            assert backend.set("key2", "value2")
            assert backend.clear()
            assert backend.get("key1") is None
            assert backend.get("key2") is None

            backend.close()

    @pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
    def test_cache_backend_ttl_expiration(self):
        """Test TTL expiration functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir), ttl=1)  # 1 second TTL
            backend = CacheBackend(config)

            # Set a value
            assert backend.set("short_ttl_key", "value")
            assert backend.get("short_ttl_key") == "value"

            # Wait for expiration
            time.sleep(2)

            # Value should be expired
            assert backend.get("short_ttl_key") is None

            backend.close()

    @pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
    def test_cache_backend_normalize_key(self):
        """Test key normalization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            # Test key normalization
            key1 = backend._normalize_key("test_key")
            key2 = backend._normalize_key("test_key")  # Should be same
            assert key1 == key2
            assert isinstance(key1, str)

            backend.close()

    @pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
    def test_cache_backend_normalize_params(self):
        """Test parameter normalization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            params = {"query": "test", "limit": 10, "sort": "relevance"}
            normalized = backend._normalize_params(params)

            # Should be sorted and consistent
            assert isinstance(normalized, dict)
            assert "query" in normalized
            assert "limit" in normalized
            assert "sort" in normalized

            backend.close()

    @pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
    def test_cache_backend_normalize_query_key(self):
        """Test query key normalization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            params = {"query": "cancer research", "limit": 20}
            key = backend.normalize_query_key("cancer research", "search", limit=20)

            assert isinstance(key, str)
            assert "search" in key

            # Same params should generate same key
            key2 = backend.normalize_query_key("cancer research", "search", limit=20)
            assert key == key2

            backend.close()

    @pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
    def test_cache_backend_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            stats = backend.get_stats()
            assert isinstance(stats, dict)
            assert "layers" in stats
            assert "overall" in stats

            backend.close()

    @pytest.mark.skipif(not CACHETOOLS_AVAILABLE, reason="cachetools not available")
    def test_cache_backend_evict_by_tag(self):
        """Test cache eviction by tag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            # Set values with tags
            backend.set("key1", "value1", tag="tag1")
            backend.set("key2", "value2", tag="tag1")
            backend.set("key3", "value3", tag="tag2")

            # Evict by tag
            evicted = backend.evict("tag1")
            assert evicted >= 1  # At least key1 should be evicted

            # key1 should be gone, key3 should remain
            assert backend.get("key1") is None
            assert backend.get("key3") == "value3"

            backend.close()

    def test_cache_backend_close(self):
        """Test cache backend closing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)

            # Should not raise exception
            backend.close()

            # Multiple closes should be safe
            backend.close()


class TestCacheDataTypes:
    """Test CacheDataType enum."""

    def test_cache_data_types(self):
        """Test all cache data types are defined."""
        assert CacheDataType.SEARCH
        assert CacheDataType.RECORD
        assert CacheDataType.FULLTEXT
        assert CacheDataType.ERROR


class TestCacheLayers:
    """Test CacheLayer enum."""

    def test_cache_layers(self):
        """Test all cache layers are defined."""
        assert CacheLayer.L1
        assert CacheLayer.L2
