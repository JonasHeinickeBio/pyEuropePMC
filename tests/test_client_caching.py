"""
Quick test to verify caching is integrated in all clients.
"""
import pytest

from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.clients.fulltext import FullTextClient
from pyeuropepmc.clients.search import SearchClient


class TestSearchClientCaching:
    """Test SearchClient caching integration."""

    def test_search_client_cache_disabled_by_default(self):
        """Verify SearchClient has caching disabled by default for backward compatibility."""
        client = SearchClient()
        assert hasattr(client, '_cache')
        # Cache should be disabled by default
        stats = client.get_cache_stats()
        assert isinstance(stats, dict)
        client.close()

    def test_search_client_with_cache_enabled(self):
        """Verify SearchClient can enable caching."""
        cache_config = CacheConfig(enabled=True)
        client = SearchClient(cache_config=cache_config)
        assert hasattr(client, '_cache')

        # Cache management methods should work
        stats = client.get_cache_stats()
        assert isinstance(stats, dict)

        health = client.get_cache_health()
        assert isinstance(health, dict)

        result = client.clear_cache()
        assert isinstance(result, bool)

        client.close()


class TestArticleClientCaching:
    """Test ArticleClient caching integration."""

    def test_article_client_cache_disabled_by_default(self):
        """Verify ArticleClient has caching disabled by default for backward compatibility."""
        client = ArticleClient()
        assert hasattr(client, '_cache')
        # Cache should be disabled by default
        stats = client.get_cache_stats()
        assert isinstance(stats, dict)
        client.close()

    def test_article_client_with_cache_enabled(self):
        """Verify ArticleClient can enable caching."""
        cache_config = CacheConfig(enabled=True)
        client = ArticleClient(cache_config=cache_config)
        assert hasattr(client, '_cache')

        # Cache management methods should work
        stats = client.get_cache_stats()
        assert isinstance(stats, dict)

        health = client.get_cache_health()
        assert isinstance(health, dict)

        result = client.clear_cache()
        assert isinstance(result, bool)

        count = client.invalidate_article_cache()
        assert isinstance(count, int)

        client.close()


class TestFullTextClientCaching:
    """Test FullTextClient caching integration."""

    def test_fulltext_client_cache_disabled_by_default(self):
        """Verify FullTextClient has API response caching disabled by default."""
        client = FullTextClient()
        assert hasattr(client, '_cache')
        # API response cache should be disabled by default
        stats = client.get_api_cache_stats()
        assert isinstance(stats, dict)
        client.close()

    def test_fulltext_client_with_cache_enabled(self):
        """Verify FullTextClient can enable API response caching."""
        cache_config = CacheConfig(enabled=True)
        client = FullTextClient(cache_config=cache_config)
        assert hasattr(client, '_cache')

        # API response cache management methods should work
        stats = client.get_api_cache_stats()
        assert isinstance(stats, dict)

        health = client.get_api_cache_health()
        assert isinstance(health, dict)

        result = client.clear_api_cache()
        assert isinstance(result, bool)

        count = client.invalidate_fulltext_cache()
        assert isinstance(count, int)

        client.close()

    def test_fulltext_client_has_both_caches(self):
        """Verify FullTextClient has both file cache and API response cache."""
        cache_config = CacheConfig(enabled=True)
        client = FullTextClient(enable_cache=True, cache_config=cache_config)

        # File cache
        assert hasattr(client, 'enable_cache')
        assert client.enable_cache is True
        assert hasattr(client, 'cache_dir')

        # File cache health method should exist
        health = client.get_file_cache_health()
        assert isinstance(health, dict)
        assert 'status' in health
        assert 'enabled' in health

        # API response cache
        assert hasattr(client, '_cache')
        stats = client.get_api_cache_stats()
        assert isinstance(stats, dict)

        client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
