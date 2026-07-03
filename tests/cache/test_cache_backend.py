"""
Unit tests for cache backend functionality.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pyeuropepmc.cache.cache import (
    CACHETOOLS_AVAILABLE,
    DISKCACHE_AVAILABLE,
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
    _normalize_single_value,
    cached,
    normalize_query_params,
)


def _make_backend(temp_dir: str, ttl: int = 60) -> CacheBackend:
    """Helper to create a test backend."""
    config = CacheConfig(enabled=True, cache_dir=Path(temp_dir), ttl=ttl)
    return CacheBackend(config)


class TestCacheConfig:
    """Test CacheConfig class."""

    def test_cache_config_defaults(self):
        """Test CacheConfig with default values."""
        config = CacheConfig()
        assert config.enabled is (True if CACHETOOLS_AVAILABLE else False)
        assert config.ttl == 86400
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
        assert config.get_ttl() == 3600
        assert config.get_ttl(CacheDataType.SEARCH) == 1800
        assert config.get_ttl(CacheDataType.RECORD) == 86400

    def test_cache_config_negative_ttl_raises_error(self):
        """Test negative TTL raises ConfigurationError."""
        with pytest.raises(Exception):
            CacheConfig(ttl=-1)

    def test_cache_config_zero_size_limit_raises_error(self):
        """Test size_limit_mb < 1 raises ConfigurationError."""
        with pytest.raises(Exception):
            CacheConfig(size_limit_mb=0)

    def test_cache_config_invalid_namespace_version_raises_error(self):
        """Test namespace_version < 1 raises ConfigurationError."""
        with pytest.raises(Exception):
            CacheConfig(namespace_version=0)


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
            assert backend.l2_cache is None
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
            assert backend.set("test_key", "test_value")
            assert backend.get("test_key") == "test_value"
            assert backend.delete("test_key")
            assert backend.get("test_key") is None
            assert backend.set("key1", "value1")
            assert backend.set("key2", "value2")
            assert backend.clear()
            assert backend.get("key1") is None
            assert backend.get("key2") is None
            backend.close()

    def test_cache_backend_ttl_expiration(self):
        """Test TTL expiration functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir), ttl=1)
            backend = CacheBackend(config)
            assert backend.set("short_ttl_key", "value")
            assert backend.get("short_ttl_key") == "value"
            time.sleep(1.5)
            assert backend.get("short_ttl_key") is None
            backend.close()

    def test_cache_backend_normalize_key(self):
        """Test key normalization determinism."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            key1 = backend._normalize_key("test_key")
            key2 = backend._normalize_key("test_key")
            assert key1 == key2
            assert isinstance(key1, str)
            backend.close()

    def test_cache_backend_normalize_key_with_data_type(self):
        """Test key normalization includes data type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            search_key = backend._normalize_key("query", data_type=CacheDataType.SEARCH, q="test")
            record_key = backend._normalize_key("query", data_type=CacheDataType.RECORD, q="test")
            assert search_key != record_key
            assert search_key.startswith("search:")
            assert record_key.startswith("record:")
            backend.close()

    def test_cache_backend_normalize_params(self):
        """Test parameter normalization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            params = {"query": "test", "limit": 10, "sort": "relevance"}
            normalized = backend._normalize_params(params)
            assert isinstance(normalized, dict)
            assert "query" in normalized
            assert "limit" in normalized
            assert "sort" in normalized
            backend.close()

    def test_cache_backend_normalize_query_key(self):
        """Test query key normalization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            key = backend.normalize_query_key("cancer research", "search", limit=20)
            assert isinstance(key, str)
            assert "search" in key
            key2 = backend.normalize_query_key("cancer research", "search", limit=20)
            assert key == key2
            backend.close()

    def test_cache_backend_normalize_query_key_whitespace(self):
        """Test query key normalization handles whitespace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            key1 = backend.normalize_query_key("  cancer   research  ")
            key2 = backend.normalize_query_key("cancer research")
            assert key1 == key2
            backend.close()

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

    def test_cache_backend_evict_by_tag(self):
        """Test cache eviction by tag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.set("key1", "value1", tag="tag1")
            backend.set("key2", "value2", tag="tag1")
            backend.set("key3", "value3", tag="tag2")
            evicted = backend.evict("tag1")
            assert evicted >= 1
            assert backend.get("key1") is None
            assert backend.get("key3") == "value3"
            backend.close()

    def test_cache_backend_close(self):
        """Test cache backend closing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.close()
            backend.close()  # Multiple closes safe

    def test_cache_backend_cache_property(self):
        """Test backward compatibility cache property."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            assert backend.cache is backend.l1_cache
            backend.cache = "custom_value"
            assert backend.l1_cache == "custom_value"
            backend.close()

    def test_cache_backend_reset_stats(self):
        """Test resetting cache statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.set("key1", "value1")
            backend.get("key1")
            stats_before = backend.get_stats()
            assert stats_before["overall"]["sets"] >= 1
            backend.reset_stats()
            stats_after = backend.get_stats()
            assert stats_after["overall"]["hits"] == 0
            assert stats_after["overall"]["sets"] == 0
            backend.close()

    def test_cache_backend_get_keys(self):
        """Test getting cache keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.set("key1", "value1")
            backend.set("key2", "value2")
            keys = backend.get_keys()
            assert "key1" in keys
            assert "key2" in keys
            backend.close()

    def test_cache_backend_get_keys_with_pattern(self):
        """Test getting cache keys filtered by pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.set("search:abc", "v1")
            backend.set("search:def", "v2")
            backend.set("record:xyz", "v3")
            matching = backend.get_keys(pattern="search:*")
            assert all("search:" in k for k in matching)
            backend.close()

    def test_cache_backend_get_keys_disabled(self):
        """Test get_keys returns empty when disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        assert backend.get_keys() == []

    def test_cache_backend_compact(self):
        """Test cache compaction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.set("key1", "value1")
            result = backend.compact()
            assert result is True
            backend.close()

    def test_cache_backend_compact_disabled(self):
        """Test compact returns False when disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        assert backend.compact() is False

    def test_cache_backend_warm_cache(self):
        """Test warming cache with pre-computed entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            entries = {"key_a": "value_a", "key_b": "value_b"}
            count = backend.warm_cache(entries, ttl=60, tag="warm")
            assert count == 2
            assert backend.get("key_a") == "value_a"
            assert backend.get("key_b") == "value_b"
            backend.close()

    def test_cache_backend_warm_cache_disabled(self):
        """Test warm_cache returns 0 when disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        assert backend.warm_cache({"key": "val"}) == 0

    def test_cache_backend_warm_cache_partial(self):
        """Test warm_cache with partial success."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir), ttl=60)
            backend = CacheBackend(config)
            entries = {}
            count = backend.warm_cache(entries)
            assert count == 0
            backend.close()

    def test_cache_backend_invalidate_older_than(self):
        """Test invalidate_older_than returns 0 (TTLCache handles it)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend.invalidate_older_than(3600)
            assert result == 0
            backend.close()

    def test_cache_backend_health_disabled(self):
        """Test get_health when cache is disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        health = backend.get_health()
        assert health["status"] == "disabled"
        assert health["enabled"] is False

    def test_cache_backend_health_healthy(self):
        """Test get_health when cache is healthy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            health = backend.get_health()
            assert health["enabled"] is True
            assert health["status"] in ("healthy", "unknown")
            backend.close()

    def test_cache_backend_stats_with_layer(self):
        """Test stats tracking per layer."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.get("miss_key")
            stats = backend.get_stats()
            assert stats["layers"]["l1"]["misses"] >= 1
            backend.close()

    def test_cache_backend_delete_from_l1_only(self):
        """Test delete from L1 only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.set("key1", "value1")
            backend.set("key2", "value2")
            assert backend.delete("key1", layer=CacheLayer.L1) is True
            backend.close()

    def test_cache_backend_normalize_booleans(self):
        """Test _normalize_value handles booleans."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"flag": True, "no_flag": False})
            assert result["flag"] == "true"
            assert result["no_flag"] == "false"
            backend.close()

    def test_cache_backend_normalize_none(self):
        """Test _normalize_value skips None values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"valid": "ok", "empty": None})
            assert "valid" in result
            assert "empty" not in result
            backend.close()

    def test_cache_backend_normalize_lists(self):
        """Test _normalize_value sorts lists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"items": [3, 1, 2]})
            assert result["items"] == (1, 2, 3)
            backend.close()

    def test_cache_backend_normalize_empty_string(self):
        """Test _normalize_value skips empty strings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"name": "  "})
            assert "name" not in result or result.get("name") is None
            backend.close()

    def test_cache_backend_normalize_recursive_dict(self):
        """Test _normalize_value handles recursive dicts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"nested": {"b": 2, "a": 1, "c": None}})
            assert "nested" in result
            backend.close()

    def test_cache_backend_normalize_unsortable_list(self):
        """Test _normalize_value preserves order for unsortable lists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"items": [{"id": 2}, {"id": 1}]})
            assert len(result["items"]) == 2
            backend.close()

    def test_cache_backend_normalize_numeric(self):
        """Test _normalize_value preserves numeric types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            result = backend._normalize_params({"int": 42, "float": 3.14})
            assert result["int"] == 42
            assert result["float"] == 3.14
            backend.close()

    def test_cache_backend_invalidate_pattern(self):
        """Test invalidate_pattern matches and deletes keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("search:abc", "v1")
            backend.set("search:def", "v2")
            backend.set("record:xyz", "v3")
            count = backend.invalidate_pattern("search:*")
            assert count >= 1
            assert backend.get("search:abc") is None
            assert backend.get("record:xyz") == "v3"
            backend.close()

    def test_cache_backend_invalidate_pattern_disabled(self):
        """Test invalidate_pattern returns 0 when disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        assert backend.invalidate_pattern("*") == 0

    def test_cache_backend_invalidate_pattern_no_match(self):
        """Test invalidate_pattern with no matching keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("key1", "v1")
            count = backend.invalidate_pattern("nomatch:*")
            assert count == 0
            backend.close()

    def test_cache_backend_health_unavailable(self):
        """Test get_health when cache is None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            backend.l1_cache = None
            health = backend.get_health()
            assert health["status"] == "unavailable"
            backend.close()

    def test_cache_backend_get_with_layer_l1(self):
        """Test get from L1 layer specifically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("key1", "value1")
            result = backend.get("key1", layer=CacheLayer.L1)
            assert result == "value1"
            backend.close()

    def test_cache_backend_set_with_layer_l1(self):
        """Test set to L1 layer specifically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            result = backend.set("key1", "value1", layer=CacheLayer.L1)
            assert result is True
            assert backend.get("key1") == "value1"
            backend.close()

    def test_cache_backend_delete_not_found(self):
        """Test delete returns False for non-existent key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            assert backend.delete("nonexistent") is False
            backend.close()

    def test_cache_backend_evict_no_tag(self):
        """Test evict with non-existent tag returns 0."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("key1", "v1")
            assert backend.evict("nonexistent_tag") == 0
            backend.close()

    def test_cache_backend_set_tags_tracking(self):
        """Test tag tracking on set."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("k1", "v1", tag="t1")
            assert "t1" in backend._tags
            assert "k1" in backend._tags["t1"]
            backend.close()

    def test_cache_backend_clear_l1_only(self):
        """Test clear L1 layer only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("k1", "v1")
            result = backend.clear(layer=CacheLayer.L1)
            assert result is True
            assert backend.get("k1") is None
            backend.close()

    def test_cache_backend_stats_with_operations(self):
        """Test stats reflect operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("k1", "v1")
            backend.get("k1")
            backend.get("miss")
            stats = backend.get_stats()
            assert stats["overall"]["hits"] >= 1
            assert stats["overall"]["misses"] >= 1
            assert stats["overall"]["sets"] >= 1
            backend.close()

    def test_cache_backend_delete_updates_tags(self):
        """Test delete removes key from tag tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            backend.set("k1", "v1", tag="t1")
            backend.delete("k1")
            assert "k1" not in backend._tags.get("t1", set())
            backend.close()

    def test_cache_backend_evict_disabled(self):
        """Test evict returns 0 when cache disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        assert backend.evict("tag1") == 0

    def test_cache_backend_invalidate_older_than_disabled(self):
        """Test invalidate_older_than returns 0 when disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        assert backend.invalidate_older_than(100) == 0

    def test_cache_backend_get_keys_with_limit(self):
        """Test get_keys with limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            for i in range(10):
                backend.set(f"key{i}", f"v{i}")
            keys = backend.get_keys(limit=3)
            assert len(keys) <= 3
            backend.close()

    def test_cache_backend_warm_cache_with_tag(self):
        """Test warm_cache with tag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            entries = {"k1": "v1", "k2": "v2"}
            count = backend.warm_cache(entries, tag="warm_tag")
            assert count == 2
            assert "k1" in backend._tags.get("warm_tag", set())
            backend.close()

    def test_cache_backend_normalize_allow_none_key(self):
        """Test _normalize_value passes through None for allow_none keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = _make_backend(temp_dir)
            # _normalize_value returns None even with allow_none (falls through to return value)
            result = backend._normalize_value("allow_none_field", None)
            assert result is None
            backend.close()


class TestCacheDataTypes:
    """Test CacheDataType enum."""

    def test_cache_data_types(self):
        """Test all cache data types are defined."""
        assert CacheDataType.SEARCH
        assert CacheDataType.RECORD
        assert CacheDataType.FULLTEXT
        assert CacheDataType.ERROR

    def test_cache_data_type_values(self):
        """Test cache data type string values."""
        assert CacheDataType.SEARCH.value == "search"
        assert CacheDataType.RECORD.value == "record"
        assert CacheDataType.ERROR.value == "error"


class TestCacheLayers:
    """Test CacheLayer enum."""

    def test_cache_layers(self):
        """Test all cache layers are defined."""
        assert CacheLayer.L1
        assert CacheLayer.L2

    def test_cache_layer_values(self):
        """Test cache layer string values."""
        assert CacheLayer.L1.value == "l1"
        assert CacheLayer.L2.value == "l2"


class TestNormalizeQueryParams:
    """Test normalize_query_params standalone function."""

    def test_normalize_query_params_basic(self):
        """Test basic parameter normalization."""
        result = normalize_query_params({"query": "  cancer  ", "pageSize": 10})
        assert result["query"] == "cancer"
        assert result["pageSize"] == 10

    def test_normalize_query_params_none_empty(self):
        """Test None and empty values are removed."""
        result = normalize_query_params({"query": "test", "empty": "", "none": None})
        assert result == {"query": "test"}

    def test_normalize_query_params_numeric_conversion(self):
        """Test string numeric conversion."""
        result = normalize_query_params({"count": "42", "ratio": "3.14"})
        assert result["count"] == 42
        assert result["ratio"] == 3.14

    def test_normalize_query_params_bool_preserved(self):
        """Test booleans are preserved."""
        result = normalize_query_params({"active": True, "verbose": False})
        assert result["active"] is True
        assert result["verbose"] is False

    def test_normalize_query_params_list_sort(self):
        """Test lists are sorted."""
        result = normalize_query_params({"ids": [3, 1, 2]})
        assert result["ids"] == [1, 2, 3]

    def test_normalize_query_params_recursive_dict(self):
        """Test recursive dict normalization."""
        result = normalize_query_params({"filter": {"b": 2, "a": 1}})
        assert result["filter"] == {"a": 1, "b": 2}

    def test_normalize_query_params_empty(self):
        """Test empty dict returns empty dict."""
        assert normalize_query_params({}) == {}

    def test_normalize_query_params_other_types(self):
        """Test other types pass through."""
        result = normalize_query_params({"data": b"bytes"})
        assert result["data"] == b"bytes"


class TestNormalizeSingleValue:
    """Test _normalize_single_value standalone function."""

    def test_normalize_none(self):
        """Test None returns None."""
        assert _normalize_single_value(None) is None

    def test_normalize_string_stripped(self):
        """Test string whitespace stripping."""
        assert _normalize_single_value("  hello  ") == "hello"

    def test_normalize_string_numeric(self):
        """Test string numeric conversion."""
        assert _normalize_single_value("42") == 42
        assert _normalize_single_value("3.14") == 3.14

    def test_normalize_string_empty(self):
        """Test empty string returns None."""
        assert _normalize_single_value("") is None

    def test_normalize_string_whitespace_only(self):
        """Test whitespace-only string returns None."""
        assert _normalize_single_value("   ") is None

    def test_normalize_bool_preserved(self):
        """Test booleans are preserved."""
        assert _normalize_single_value(True) is True
        assert _normalize_single_value(False) is False

    def test_normalize_numeric_preserved(self):
        """Test numbers pass through."""
        assert _normalize_single_value(42) == 42
        assert _normalize_single_value(3.14) == 3.14

    def test_normalize_list_sorted(self):
        """Test lists are sorted with None filtered."""
        assert _normalize_single_value([3, 1, 2]) == [1, 2, 3]

    def test_normalize_list_with_none(self):
        """Test list nulls are filtered."""
        assert _normalize_single_value([1, None, 2]) == [1, 2]

    def test_normalize_dict_recursive(self):
        """Test dicts are recursively normalized with None filtered."""
        result = _normalize_single_value({"b": 2, "a": None, "c": 3})
        assert result == {"b": 2, "c": 3}

    def test_normalize_unsorted_list_preserved(self):
        """Test unsortable list types keep their order."""
        result = _normalize_single_value([{"id": 2}, {"id": 1}])
        assert len(result) == 2


class TestCachedDecorator:
    """Test the @cached decorator."""

    def test_cached_decorator_hit(self):
        """Test cached decorator returns cached result."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            call_count = 0

            @cached(backend, "test_func", ttl=60)
            def my_func(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            result1 = my_func(5)
            assert result1 == 10
            assert call_count == 1
            result2 = my_func(5)
            assert result2 == 10
            assert call_count == 1
            backend.close()

    def test_cached_decorator_with_key_func(self):
        """Test cached decorator with custom key function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            call_count = 0

            def my_key_func(*args, **kwargs):
                return f"custom:{args[0]}"

            @cached(backend, "test_func", ttl=60, key_func=my_key_func)
            def my_func(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            result1 = my_func(5)
            assert result1 == 10
            assert call_count == 1
            result2 = my_func(5)
            assert result2 == 10
            assert call_count == 1
            backend.close()

    def test_cached_decorator_disabled(self):
        """Test cached decorator bypasses cache when disabled."""
        config = CacheConfig(enabled=False)
        backend = CacheBackend(config)
        call_count = 0

        @cached(backend, "test_func", ttl=60)
        def my_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = my_func(5)
        assert result1 == 10
        assert call_count == 1
        result2 = my_func(5)
        assert result2 == 10
        assert call_count == 2
        backend.close()

    def test_cached_decorator_with_tag(self):
        """Test cached decorator with tag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            call_count = 0

            @cached(backend, "test_func", ttl=60, tag="my_tag")
            def my_func(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            my_func(5)
            my_func(5)
            assert call_count == 1
            backend.close()

    def test_cached_decorator_different_args(self):
        """Test cached decorator different args produce different cache keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, cache_dir=Path(temp_dir))
            backend = CacheBackend(config)
            call_count = 0

            @cached(backend, "test_func", ttl=60)
            def my_func(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            my_func(5)
            my_func(10)
            assert call_count == 2
            backend.close()
