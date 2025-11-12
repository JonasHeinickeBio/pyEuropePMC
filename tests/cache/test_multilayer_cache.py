"""
Tests for multi-layer cache architecture.

These tests verify the L1/L2 cache coordination, namespace versioning,
data type-specific TTLs, and other advanced caching features.
"""

import tempfile
from pathlib import Path

import pytest

from pyeuropepmc.cache import (
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
    DISKCACHE_AVAILABLE,
)


class TestCacheDataTypes:
    """Test cache configuration per data type."""

    def test_default_ttls_per_type(self):
        """Test that default TTLs are set correctly per data type."""
        config = CacheConfig()
        
        # Test default TTLs
        assert config.get_ttl(CacheDataType.SEARCH) == 300  # 5 minutes
        assert config.get_ttl(CacheDataType.RECORD) == 86400  # 1 day
        assert config.get_ttl(CacheDataType.FULLTEXT) == 2592000  # 30 days
        assert config.get_ttl(CacheDataType.ERROR) == 30  # 30 seconds

    def test_custom_ttls_per_type(self):
        """Test custom TTL configuration per data type."""
        custom_ttls = {
            CacheDataType.SEARCH: 600,  # 10 minutes
            CacheDataType.RECORD: 3600,  # 1 hour
        }
        config = CacheConfig(ttl_by_type=custom_ttls)
        
        assert config.get_ttl(CacheDataType.SEARCH) == 600
        assert config.get_ttl(CacheDataType.RECORD) == 3600
        # Others should keep defaults
        assert config.get_ttl(CacheDataType.FULLTEXT) == 2592000

    def test_fallback_to_default_ttl(self):
        """Test fallback to default TTL when type not specified."""
        config = CacheConfig(ttl=7200)  # 2 hours default
        
        # No data type specified
        assert config.get_ttl(None) == 7200
        assert config.get_ttl() == 7200


class TestNamespaceVersioning:
    """Test namespace versioning for cache invalidation."""

    def test_namespace_version_in_key(self):
        """Test that namespace version is included in cache keys."""
        config = CacheConfig(namespace_version=1)
        backend = CacheBackend(config)
        
        key = backend._normalize_key(
            "query",
            data_type=CacheDataType.SEARCH,
            q="test"
        )
        
        assert ":v1:" in key
        assert key.startswith("search:v1:")

    def test_different_versions_different_keys(self):
        """Test that different namespace versions produce different keys."""
        config_v1 = CacheConfig(namespace_version=1)
        backend_v1 = CacheBackend(config_v1)
        
        config_v2 = CacheConfig(namespace_version=2)
        backend_v2 = CacheBackend(config_v2)
        
        key_v1 = backend_v1._normalize_key(
            "query",
            data_type=CacheDataType.SEARCH,
            q="test"
        )
        key_v2 = backend_v2._normalize_key(
            "query",
            data_type=CacheDataType.SEARCH,
            q="test"
        )
        
        assert key_v1 != key_v2
        assert ":v1:" in key_v1
        assert ":v2:" in key_v2

    def test_namespace_version_validation(self):
        """Test that namespace version must be >= 1."""
        with pytest.raises(Exception):  # ConfigurationError
            CacheConfig(namespace_version=0)
        
        with pytest.raises(Exception):
            CacheConfig(namespace_version=-1)


class TestL1Cache:
    """Test L1 in-memory cache layer."""

    def test_l1_cache_initialization(self):
        """Test L1 cache is initialized correctly."""
        config = CacheConfig(enabled=True)
        backend = CacheBackend(config)
        
        assert backend.l1_cache is not None
        assert backend.config.enabled

    def test_l1_get_set(self):
        """Test basic L1 cache get/set operations."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        key = backend._normalize_key("test", data_type=CacheDataType.SEARCH, id=123)
        value = {"data": "test_value"}
        
        # Set and get
        assert backend.set(key, value, layer=CacheLayer.L1)
        assert backend.get(key, layer=CacheLayer.L1) == value

    def test_l1_cache_miss(self):
        """Test L1 cache miss returns default."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        key = "nonexistent:key"
        assert backend.get(key, default="default_value", layer=CacheLayer.L1) == "default_value"

    def test_l1_delete(self):
        """Test L1 cache delete."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        key = backend._normalize_key("test", data_type=CacheDataType.SEARCH)
        backend.set(key, "value", layer=CacheLayer.L1)
        
        assert backend.get(key, layer=CacheLayer.L1) == "value"
        assert backend.delete(key, layer=CacheLayer.L1)
        assert backend.get(key, layer=CacheLayer.L1) is None


@pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
class TestL2Cache:
    """Test L2 persistent cache layer."""

    def test_l2_cache_initialization(self):
        """Test L2 cache can be initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                enabled=True,
                enable_l2=True,
                cache_dir=Path(tmpdir)
            )
            backend = CacheBackend(config)
            
            assert backend.l2_cache is not None
            assert backend.config.enable_l2

    def test_l2_get_set(self):
        """Test basic L2 cache get/set operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                enabled=True,
                enable_l2=True,
                cache_dir=Path(tmpdir)
            )
            backend = CacheBackend(config)
            
            key = backend._normalize_key("test", data_type=CacheDataType.RECORD, id=456)
            value = {"data": "test_value_l2"}
            
            # Set and get from L2
            assert backend.set(key, value, layer=CacheLayer.L2)
            assert backend.get(key, layer=CacheLayer.L2) == value

    def test_l2_persistence(self):
        """Test that L2 cache persists across backend instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            
            # First backend - write data
            config1 = CacheConfig(enable_l2=True, cache_dir=cache_dir)
            backend1 = CacheBackend(config1)
            
            key = backend1._normalize_key("persist", data_type=CacheDataType.RECORD)
            value = {"persistent": "data"}
            backend1.set(key, value, layer=CacheLayer.L2)
            backend1.close()
            
            # Second backend - read data
            config2 = CacheConfig(enable_l2=True, cache_dir=cache_dir)
            backend2 = CacheBackend(config2)
            
            # Data should persist
            assert backend2.get(key, layer=CacheLayer.L2) == value
            backend2.close()


@pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
class TestMultiLayerCoordination:
    """Test L1/L2 cache coordination."""

    def test_write_through_both_layers(self):
        """Test write-through to both L1 and L2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                enabled=True,
                enable_l2=True,
                cache_dir=Path(tmpdir)
            )
            backend = CacheBackend(config)
            
            key = backend._normalize_key("multi", data_type=CacheDataType.SEARCH)
            value = {"data": "multilayer"}
            
            # Set without specifying layer (writes to both)
            backend.set(key, value)
            
            # Should be in both layers
            assert backend.get(key, layer=CacheLayer.L1) == value
            assert backend.get(key, layer=CacheLayer.L2) == value

    def test_l1_l2_hierarchy(self):
        """Test that L1 is checked before L2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                enabled=True,
                enable_l2=True,
                cache_dir=Path(tmpdir)
            )
            backend = CacheBackend(config)
            
            key = backend._normalize_key("hierarchy", data_type=CacheDataType.RECORD)
            
            # Store in L2 only
            backend.set(key, "l2_value", layer=CacheLayer.L2)
            
            # Get without layer should check L1 first, then L2
            result = backend.get(key)
            assert result == "l2_value"
            
            # Now should be promoted to L1
            assert backend.get(key, layer=CacheLayer.L1) == "l2_value"

    def test_l2_promotion_to_l1(self):
        """Test that L2 hits promote values to L1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                enabled=True,
                enable_l2=True,
                cache_dir=Path(tmpdir)
            )
            backend = CacheBackend(config)
            
            key = backend._normalize_key("promote", data_type=CacheDataType.FULLTEXT)
            value = {"data": "promote_me"}
            
            # Store in L2 only
            backend.set(key, value, layer=CacheLayer.L2)
            assert backend.get(key, layer=CacheLayer.L1) is None  # Not in L1 yet
            
            # Access via hierarchy (triggers promotion)
            result = backend.get(key)
            assert result == value
            
            # Should now be in L1
            assert backend.get(key, layer=CacheLayer.L1) == value


class TestCacheStatistics:
    """Test multi-layer cache statistics."""

    def test_l1_statistics_tracking(self):
        """Test L1 statistics are tracked correctly."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        key = backend._normalize_key("stats", data_type=CacheDataType.SEARCH)
        
        # Initial stats
        stats = backend.get_stats()
        assert stats["layers"]["l1"]["hits"] == 0
        assert stats["layers"]["l1"]["misses"] == 0
        assert stats["layers"]["l1"]["sets"] == 0
        
        # Set a value
        backend.set(key, "value", layer=CacheLayer.L1)
        stats = backend.get_stats()
        assert stats["layers"]["l1"]["sets"] == 1
        
        # Hit
        backend.get(key, layer=CacheLayer.L1)
        stats = backend.get_stats()
        assert stats["layers"]["l1"]["hits"] == 1
        
        # Miss
        backend.get("nonexistent", layer=CacheLayer.L1)
        stats = backend.get_stats()
        assert stats["layers"]["l1"]["misses"] == 1

    @pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
    def test_l2_statistics_tracking(self):
        """Test L2 statistics are tracked correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                enable_l2=True,
                cache_dir=Path(tmpdir)
            )
            backend = CacheBackend(config)
            
            key = backend._normalize_key("stats_l2", data_type=CacheDataType.RECORD)
            
            # Set a value
            backend.set(key, "value", layer=CacheLayer.L2)
            stats = backend.get_stats()
            assert stats["layers"]["l2"]["sets"] == 1
            
            # Hit
            backend.get(key, layer=CacheLayer.L2)
            stats = backend.get_stats()
            assert stats["layers"]["l2"]["hits"] == 1

    def test_overall_statistics(self):
        """Test overall statistics combine both layers."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        key = backend._normalize_key("overall", data_type=CacheDataType.SEARCH)
        
        # Operations
        backend.set(key, "value")
        backend.get(key)
        backend.get("miss")
        
        stats = backend.get_stats()
        overall = stats["overall"]
        
        assert overall["sets"] >= 1
        assert overall["hits"] >= 1
        assert overall["misses"] >= 1
        assert "hit_rate" in overall


class TestCacheInvalidation:
    """Test cache invalidation features."""

    def test_invalidate_by_pattern(self):
        """Test invalidation by pattern."""
        config = CacheConfig(namespace_version=1)
        backend = CacheBackend(config)
        
        # Add some entries
        key1 = backend._normalize_key("query1", data_type=CacheDataType.SEARCH, q="test1")
        key2 = backend._normalize_key("query2", data_type=CacheDataType.SEARCH, q="test2")
        key3 = backend._normalize_key("article", data_type=CacheDataType.RECORD, id=123)
        
        backend.set(key1, "value1")
        backend.set(key2, "value2")
        backend.set(key3, "value3")
        
        # Invalidate all search entries
        count = backend.invalidate_pattern("search:v1:*")
        assert count == 2
        
        # Search entries should be gone
        assert backend.get(key1) is None
        assert backend.get(key2) is None
        
        # Record should still exist
        assert backend.get(key3) == "value3"

    def test_namespace_version_invalidation(self):
        """Test broad invalidation via namespace version bump."""
        # V1 cache
        config_v1 = CacheConfig(namespace_version=1)
        backend_v1 = CacheBackend(config_v1)
        
        key_v1 = backend_v1._normalize_key("data", data_type=CacheDataType.SEARCH, id=1)
        backend_v1.set(key_v1, "v1_value")
        assert backend_v1.get(key_v1) == "v1_value"
        
        # V2 cache (simulates version bump)
        config_v2 = CacheConfig(namespace_version=2)
        backend_v2 = CacheBackend(config_v2)
        
        # V1 key won't be found in V2 namespace
        assert backend_v2.get(key_v1) is None
        
        # V2 key is different
        key_v2 = backend_v2._normalize_key("data", data_type=CacheDataType.SEARCH, id=1)
        assert key_v1 != key_v2


class TestDataTypeKeying:
    """Test cache keys include data type."""

    def test_keys_include_data_type(self):
        """Test that cache keys include data type prefix."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        search_key = backend._normalize_key("query", data_type=CacheDataType.SEARCH)
        record_key = backend._normalize_key("query", data_type=CacheDataType.RECORD)
        fulltext_key = backend._normalize_key("query", data_type=CacheDataType.FULLTEXT)
        
        assert search_key.startswith("search:")
        assert record_key.startswith("record:")
        assert fulltext_key.startswith("fulltext:")

    def test_same_params_different_types_different_keys(self):
        """Test that same params with different types produce different keys."""
        config = CacheConfig()
        backend = CacheBackend(config)
        
        # Same parameters, different data types
        key1 = backend._normalize_key("doc", data_type=CacheDataType.SEARCH, id=123)
        key2 = backend._normalize_key("doc", data_type=CacheDataType.RECORD, id=123)
        
        assert key1 != key2
        assert "search:" in key1
        assert "record:" in key2
