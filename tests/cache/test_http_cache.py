"""
Tests for HTTP caching with requests-cache.

These tests verify protocol-correct HTTP caching including
ETag, Last-Modified, conditional GET, and 304 Not Modified responses.
"""

import pytest

from pyeuropepmc.http_cache import (
    HTTPCache,
    HTTPCacheConfig,
    REQUESTS_CACHE_AVAILABLE,
    create_cached_session,
    conditional_get,
    is_cached_response,
    extract_cache_headers,
)


class TestHTTPCacheConfig:
    """Test HTTP cache configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = HTTPCacheConfig()
        
        # If requests-cache available, should be enabled
        assert config.enabled == REQUESTS_CACHE_AVAILABLE
        assert config.cache_name == "pyeuropepmc_http_cache"
        assert config.backend == "sqlite"
        assert config.expire_after == 3600
        assert 200 in config.allowable_codes
        assert 304 in config.allowable_codes
        assert "GET" in config.allowable_methods

    def test_custom_config(self):
        """Test custom configuration."""
        config = HTTPCacheConfig(
            enabled=True,
            cache_name="custom_cache",
            expire_after=7200,
            backend="memory",
        )
        
        assert config.cache_name == "custom_cache"
        assert config.expire_after == 7200
        assert config.backend == "memory"

    def test_disabled_config(self):
        """Test explicitly disabled configuration."""
        config = HTTPCacheConfig(enabled=False)
        
        assert config.enabled is False


@pytest.mark.skipif(not REQUESTS_CACHE_AVAILABLE, reason="requests-cache not available")
class TestHTTPCacheWithLibrary:
    """Test HTTP cache when requests-cache is available."""

    def test_cache_initialization(self, tmp_path):
        """Test cache initialization."""
        config = HTTPCacheConfig(
            cache_name=str(tmp_path / "test_cache"),
            backend="sqlite",
        )
        cache = HTTPCache(config)
        
        assert cache.is_enabled()
        assert cache.get_session() is not None

    def test_get_session(self, tmp_path):
        """Test getting cached session."""
        config = HTTPCacheConfig(cache_name=str(tmp_path / "test"))
        cache = HTTPCache(config)
        
        session = cache.get_session()
        assert session is not None
        assert hasattr(session, "cache")

    def test_cache_clear(self, tmp_path):
        """Test clearing cache."""
        config = HTTPCacheConfig(cache_name=str(tmp_path / "test"))
        cache = HTTPCache(config)
        
        # Should not raise
        cache.clear()

    def test_cache_delete_urls(self, tmp_path):
        """Test deleting specific URLs."""
        config = HTTPCacheConfig(cache_name=str(tmp_path / "test"))
        cache = HTTPCache(config)
        
        # Should not raise
        cache.delete("https://example.com/resource1")
        cache.delete(
            "https://example.com/resource1",
            "https://example.com/resource2",
        )

    def test_get_cache_size(self, tmp_path):
        """Test getting cache statistics."""
        config = HTTPCacheConfig(cache_name=str(tmp_path / "test"))
        cache = HTTPCache(config)
        
        stats = cache.get_cache_size()
        
        assert stats["enabled"] is True
        assert "backend" in stats
        assert "response_count" in stats

    def test_cache_close(self, tmp_path):
        """Test closing cache."""
        config = HTTPCacheConfig(cache_name=str(tmp_path / "test"))
        cache = HTTPCache(config)
        
        # Should not raise
        cache.close()

    def test_create_cached_session_helper(self, tmp_path):
        """Test convenience function for creating cached session."""
        session = create_cached_session(
            cache_name=str(tmp_path / "test"),
            expire_after=1800,
        )
        
        assert session is not None
        assert hasattr(session, "cache")

    def test_memory_backend(self):
        """Test using memory backend."""
        config = HTTPCacheConfig(
            cache_name="memory_test",
            backend="memory",
        )
        cache = HTTPCache(config)
        
        assert cache.is_enabled()
        assert cache.get_session() is not None


class TestHTTPCacheWithoutLibrary:
    """Test HTTP cache behavior when requests-cache is NOT available."""

    def test_cache_disabled_without_library(self, monkeypatch):
        """Test that cache is disabled when library not available."""
        # Simulate missing requests-cache
        import pyeuropepmc.http_cache as http_cache_module
        monkeypatch.setattr(http_cache_module, "REQUESTS_CACHE_AVAILABLE", False)
        
        config = HTTPCacheConfig(enabled=True)
        
        # Should be disabled due to missing library
        assert config.enabled is False

    def test_create_session_fallback(self, monkeypatch):
        """Test that create_cached_session falls back to regular session."""
        # Simulate missing requests-cache
        import pyeuropepmc.http_cache as http_cache_module
        monkeypatch.setattr(http_cache_module, "REQUESTS_CACHE_AVAILABLE", False)
        
        session = create_cached_session()
        
        # Should return a session (might be regular requests.Session)
        assert session is not None


class TestHTTPCacheEdgeCases:
    """Test edge cases and error handling."""

    def test_disabled_cache_operations(self):
        """Test operations on disabled cache."""
        config = HTTPCacheConfig(enabled=False)
        cache = HTTPCache(config)
        
        assert not cache.is_enabled()
        assert cache.get_session() is None
        
        # Operations should not raise
        cache.clear()
        cache.delete("https://example.com")
        cache.close()
        
        stats = cache.get_cache_size()
        assert stats["enabled"] is False

    @pytest.mark.skipif(not REQUESTS_CACHE_AVAILABLE, reason="requests-cache not available")
    def test_expire_after_values(self, tmp_path):
        """Test different expire_after values."""
        # Very short expiration
        config1 = HTTPCacheConfig(
            cache_name=str(tmp_path / "short"),
            expire_after=1,
        )
        cache1 = HTTPCache(config1)
        assert cache1.is_enabled()
        
        # Very long expiration
        config2 = HTTPCacheConfig(
            cache_name=str(tmp_path / "long"),
            expire_after=86400 * 365,  # 1 year
        )
        cache2 = HTTPCache(config2)
        assert cache2.is_enabled()

    @pytest.mark.skipif(not REQUESTS_CACHE_AVAILABLE, reason="requests-cache not available")
    def test_allowable_codes(self, tmp_path):
        """Test custom allowable codes."""
        config = HTTPCacheConfig(
            cache_name=str(tmp_path / "test"),
            allowable_codes=(200, 404),  # Also cache 404s
        )
        cache = HTTPCache(config)
        
        assert cache.is_enabled()
        assert 404 in cache.config.allowable_codes


class TestConditionalGET:
    """Test conditional GET functionality."""

    def test_conditional_get_with_etag(self):
        """Test conditional GET with ETag."""
        # Create mock session
        class MockSession:
            def get(self, url, headers=None):
                class MockResponse:
                    status_code = 304
                    headers = {"ETag": '"abc123"'}
                return MockResponse()
        
        session = MockSession()
        response = conditional_get(
            session,
            "https://example.com/data",
            etag='"abc123"'
        )
        
        assert response.status_code == 304

    def test_conditional_get_with_last_modified(self):
        """Test conditional GET with Last-Modified."""
        class MockSession:
            def get(self, url, headers=None):
                class MockResponse:
                    status_code = 304
                    headers = {"Last-Modified": "Wed, 12 Nov 2025 10:00:00 GMT"}
                return MockResponse()
        
        session = MockSession()
        response = conditional_get(
            session,
            "https://example.com/data",
            last_modified="Wed, 12 Nov 2025 10:00:00 GMT"
        )
        
        assert response.status_code == 304

    def test_conditional_get_with_both_headers(self):
        """Test conditional GET with both ETag and Last-Modified."""
        class MockSession:
            def get(self, url, headers=None):
                assert "If-None-Match" in headers
                assert "If-Modified-Since" in headers
                class MockResponse:
                    status_code = 304
                    headers = {}
                return MockResponse()
        
        session = MockSession()
        response = conditional_get(
            session,
            "https://example.com/data",
            etag='"abc123"',
            last_modified="Wed, 12 Nov 2025 10:00:00 GMT"
        )
        
        assert response.status_code == 304


class TestCacheHelpers:
    """Test helper functions."""

    def test_is_cached_response_true(self):
        """Test detecting cached response."""
        class MockResponse:
            from_cache = True
        
        response = MockResponse()
        assert is_cached_response(response) is True

    def test_is_cached_response_false(self):
        """Test detecting non-cached response."""
        class MockResponse:
            from_cache = False
        
        response = MockResponse()
        assert is_cached_response(response) is False

    def test_is_cached_response_missing_attribute(self):
        """Test response without from_cache attribute."""
        class MockResponse:
            pass
        
        response = MockResponse()
        assert is_cached_response(response) is False

    def test_extract_cache_headers(self):
        """Test extracting cache headers."""
        class MockResponse:
            headers = {
                "ETag": '"abc123"',
                "Last-Modified": "Wed, 12 Nov 2025 10:00:00 GMT",
                "Cache-Control": "max-age=3600",
                "Expires": "Wed, 12 Nov 2025 11:00:00 GMT",
            }
        
        response = MockResponse()
        headers = extract_cache_headers(response)
        
        assert headers["etag"] == '"abc123"'
        assert headers["last_modified"] == "Wed, 12 Nov 2025 10:00:00 GMT"
        assert headers["cache_control"] == "max-age=3600"
        assert headers["expires"] == "Wed, 12 Nov 2025 11:00:00 GMT"

    def test_extract_cache_headers_missing(self):
        """Test extracting headers when some are missing."""
        class MockResponse:
            headers = {"ETag": '"abc123"'}
        
        response = MockResponse()
        headers = extract_cache_headers(response)
        
        assert headers["etag"] == '"abc123"'
        assert headers["last_modified"] is None
        assert headers["cache_control"] is None
        assert headers["expires"] is None


class TestHTTPCacheIntegration:
    """Test HTTP cache integration scenarios."""

    @pytest.mark.skipif(not REQUESTS_CACHE_AVAILABLE, reason="requests-cache not available")
    def test_basic_workflow(self, tmp_path):
        """Test basic HTTP cache workflow."""
        config = HTTPCacheConfig(
            cache_name=str(tmp_path / "workflow"),
            expire_after=3600,
        )
        cache = HTTPCache(config)
        
        # Get session
        session = cache.get_session()
        assert session is not None
        
        # Check stats
        stats = cache.get_cache_size()
        assert stats["enabled"]
        
        # Clear cache
        cache.clear()
        
        # Close
        cache.close()

    @pytest.mark.skipif(not REQUESTS_CACHE_AVAILABLE, reason="requests-cache not available")
    def test_multiple_sessions(self, tmp_path):
        """Test creating multiple cached sessions."""
        config1 = HTTPCacheConfig(cache_name=str(tmp_path / "cache1"))
        config2 = HTTPCacheConfig(cache_name=str(tmp_path / "cache2"))
        
        cache1 = HTTPCache(config1)
        cache2 = HTTPCache(config2)
        
        session1 = cache1.get_session()
        session2 = cache2.get_session()
        
        assert session1 is not None
        assert session2 is not None
        assert session1 != session2  # Different sessions
