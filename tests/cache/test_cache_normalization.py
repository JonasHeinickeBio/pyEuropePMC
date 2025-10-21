"""
Tests for cache query normalization functionality.
"""

import pytest
from pyeuropepmc.cache import CacheBackend, CacheConfig, normalize_query_params


@pytest.fixture
def cache_backend():
    """Create a cache backend for testing."""
    config = CacheConfig(enabled=True, ttl=60)
    backend = CacheBackend(config)
    yield backend
    backend.close()


class TestQueryNormalization:
    """Test query normalization for consistent cache keys."""

    def test_whitespace_normalization(self, cache_backend):
        """Test that whitespace variations produce the same key."""
        key1 = cache_backend.normalize_query_key("COVID-19", pageSize=25)
        key2 = cache_backend.normalize_query_key("  COVID-19  ", pageSize=25)
        key3 = cache_backend.normalize_query_key("COVID-19   ", pageSize=25)
        key4 = cache_backend.normalize_query_key("   COVID-19", pageSize=25)

        assert key1 == key2 == key3 == key4

    def test_internal_whitespace_normalization(self, cache_backend):
        """Test that internal whitespace is normalized."""
        key1 = cache_backend.normalize_query_key("machine  learning", pageSize=25)
        key2 = cache_backend.normalize_query_key("machine learning", pageSize=25)
        key3 = cache_backend.normalize_query_key("machine   learning", pageSize=25)

        assert key1 == key2 == key3

    def test_parameter_order_independence(self, cache_backend):
        """Test that parameter order doesn't affect cache key."""
        key1 = cache_backend._normalize_key(
            "search", query="test", pageSize=25, format="json"
        )
        key2 = cache_backend._normalize_key(
            "search", format="json", query="test", pageSize=25
        )
        key3 = cache_backend._normalize_key(
            "search", pageSize=25, query="test", format="json"
        )

        assert key1 == key2 == key3

    def test_none_parameter_ignored(self, cache_backend):
        """Test that None parameters are ignored."""
        key1 = cache_backend._normalize_key("search", query="test", pageSize=25)
        key2 = cache_backend._normalize_key(
            "search", query="test", pageSize=25, extra=None
        )

        assert key1 == key2

    def test_empty_string_ignored(self, cache_backend):
        """Test that empty strings are ignored."""
        key1 = cache_backend._normalize_key("search", query="test", pageSize=25)
        key2 = cache_backend._normalize_key(
            "search", query="test", pageSize=25, extra=""
        )

        assert key1 == key2

    def test_boolean_normalization(self, cache_backend):
        """Test that booleans are normalized to strings."""
        params = {"enabled": True, "disabled": False}
        normalized = cache_backend._normalize_params(params)

        assert normalized["enabled"] == "true"
        assert normalized["disabled"] == "false"

    def test_list_normalization(self, cache_backend):
        """Test that lists are sorted and converted to tuples."""
        params = {"ids": [3, 1, 2]}
        normalized = cache_backend._normalize_params(params)

        assert normalized["ids"] == (1, 2, 3)

    def test_list_order_independence(self, cache_backend):
        """Test that list order doesn't affect cache key."""
        key1 = cache_backend._normalize_key("search", ids=[1, 2, 3])
        key2 = cache_backend._normalize_key("search", ids=[3, 2, 1])
        key3 = cache_backend._normalize_key("search", ids=[2, 1, 3])

        assert key1 == key2 == key3

    def test_tuple_normalized_like_list(self, cache_backend):
        """Test that tuples are normalized like lists."""
        key1 = cache_backend._normalize_key("search", ids=[1, 2, 3])
        key2 = cache_backend._normalize_key("search", ids=(1, 2, 3))

        assert key1 == key2

    def test_nested_dict_normalization(self, cache_backend):
        """Test that nested dicts are normalized recursively."""
        params = {
            "filter": {"author": "  Smith  ", "year": 2020, "empty": None}
        }
        normalized = cache_backend._normalize_params(params)

        assert "filter" in normalized
        assert normalized["filter"]["author"] == "Smith"
        assert normalized["filter"]["year"] == 2020
        assert "empty" not in normalized["filter"]

    def test_numeric_types_preserved(self, cache_backend):
        """Test that numeric types are preserved."""
        params = {"int_val": 42, "float_val": 3.14}
        normalized = cache_backend._normalize_params(params)

        assert normalized["int_val"] == 42
        assert normalized["float_val"] == 3.14
        assert isinstance(normalized["int_val"], int)
        assert isinstance(normalized["float_val"], float)

    def test_different_queries_different_keys(self, cache_backend):
        """Test that different queries produce different keys."""
        key1 = cache_backend.normalize_query_key("COVID-19", pageSize=25)
        key2 = cache_backend.normalize_query_key("cancer", pageSize=25)
        key3 = cache_backend.normalize_query_key("COVID-19", pageSize=50)

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_prefix_affects_key(self, cache_backend):
        """Test that different prefixes produce different keys."""
        key1 = cache_backend._normalize_key("search", query="test")
        key2 = cache_backend._normalize_key("fulltext", query="test")

        assert key1 != key2

    def test_normalize_query_key_with_multiple_params(self, cache_backend):
        """Test normalize_query_key with multiple parameters."""
        key = cache_backend.normalize_query_key(
            "COVID-19",
            prefix="search",
            pageSize=25,
            format="json",
            sort="date",
        )

        assert key.startswith("search:")
        assert len(key) > len("search:")

    def test_empty_dict_ignored(self, cache_backend):
        """Test that empty dicts are ignored."""
        params = {"query": "test", "filters": {}}
        normalized = cache_backend._normalize_params(params)

        assert "query" in normalized
        assert "filters" not in normalized

    def test_unsortable_list_preserved(self, cache_backend):
        """Test that unsortable lists maintain order as tuple."""
        params = {"mixed": [{"a": 1}, {"b": 2}]}
        normalized = cache_backend._normalize_params(params)

        # Should be converted to tuple but keep order
        assert isinstance(normalized["mixed"], tuple)
        assert len(normalized["mixed"]) == 2

    def test_none_parameters_filtered(self):
        """Test that None parameters are filtered out by default."""
        params = {"query": "test", "none_param": None, "empty_param": ""}
        normalized = normalize_query_params(params)
        assert "query" in normalized
        assert "none_param" not in normalized  # None values are filtered
        assert "empty_param" not in normalized  # Empty strings are filtered


class TestCacheKeyConsistency:
    """Test cache key consistency across different scenarios."""

    def test_real_world_search_query_variations(self, cache_backend):
        """Test real-world search query variations."""
        # All these should produce the same cache key
        variations = [
            {"query": "cancer therapy", "pageSize": 25, "format": "json"},
            {"query": "  cancer therapy  ", "pageSize": 25, "format": "json"},
            {"format": "json", "query": "cancer therapy", "pageSize": 25},
            {"pageSize": 25, "format": "json", "query": "cancer therapy"},
        ]

        keys = [
            cache_backend.normalize_query_key(v.pop("query"), **v)
            for v in variations
        ]

        assert len(set(keys)) == 1, "All variations should produce the same key"

    def test_fulltext_parameter_normalization(self, cache_backend):
        """Test fulltext download parameter normalization."""
        key1 = cache_backend._normalize_key(
            "fulltext", pmcid="PMC123456", format="pdf"
        )
        key2 = cache_backend._normalize_key(
            "fulltext", format="pdf", pmcid="PMC123456"
        )

        assert key1 == key2

    def test_citation_parameter_normalization(self, cache_backend):
        """Test citation parameter normalization."""
        key1 = cache_backend._normalize_key(
            "citations", pmid="12345678", page=1, pageSize=100
        )
        key2 = cache_backend._normalize_key(
            "citations", pageSize=100, pmid="12345678", page=1
        )

        assert key1 == key2


class TestNormalizationEdgeCases:
    """Test edge cases in normalization."""

    def test_unicode_strings(self, cache_backend):
        """Test that unicode strings are handled correctly."""
        key1 = cache_backend.normalize_query_key("Müller", pageSize=25)
        key2 = cache_backend.normalize_query_key("Müller", pageSize=25)

        assert key1 == key2

    def test_special_characters(self, cache_backend):
        """Test special characters in queries."""
        key1 = cache_backend.normalize_query_key("COVID-19 & SARS-CoV-2", pageSize=25)
        key2 = cache_backend.normalize_query_key("COVID-19 & SARS-CoV-2", pageSize=25)

        assert key1 == key2

    def test_very_long_query(self, cache_backend):
        """Test that very long queries are handled."""
        long_query = " ".join(["word"] * 1000)
        key = cache_backend.normalize_query_key(long_query, pageSize=25)

        assert key.startswith("search:")
        # Hash should keep key compact
        assert len(key) < 50

    def test_empty_query(self, cache_backend):
        """Test handling of empty query."""
        key1 = cache_backend.normalize_query_key("", pageSize=25)
        key2 = cache_backend.normalize_query_key("   ", pageSize=25)

        # Empty queries should be normalized to same key
        assert key1 == key2

    def test_only_whitespace_ignored(self, cache_backend):
        """Test that whitespace-only values are ignored."""
        params = {"query": "test", "extra": "   "}
        normalized = cache_backend._normalize_params(params)

        assert "query" in normalized
        assert "extra" not in normalized
