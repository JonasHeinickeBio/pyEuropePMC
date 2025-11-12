"""Tests for error_cache module."""

import time

import pytest

from pyeuropepmc.error_cache import (
    CachedError,
    ErrorCache,
    ErrorTTLConfig,
    ErrorType,
    get_default_error_ttl,
    should_cache_error,
)


class TestErrorType:
    """Tests for ErrorType enum."""
    
    def test_from_status_code_valid(self):
        """Test getting ErrorType from valid status codes."""
        assert ErrorType.from_status_code(404) == ErrorType.NOT_FOUND
        assert ErrorType.from_status_code(410) == ErrorType.GONE
        assert ErrorType.from_status_code(429) == ErrorType.RATE_LIMIT
        assert ErrorType.from_status_code(502) == ErrorType.BAD_GATEWAY
        assert ErrorType.from_status_code(503) == ErrorType.SERVICE_UNAVAILABLE
        assert ErrorType.from_status_code(504) == ErrorType.GATEWAY_TIMEOUT
    
    def test_from_status_code_invalid(self):
        """Test getting ErrorType from invalid status code."""
        assert ErrorType.from_status_code(200) is None
        assert ErrorType.from_status_code(500) is None
        assert ErrorType.from_status_code(999) is None


class TestErrorTTLConfig:
    """Tests for ErrorTTLConfig."""
    
    def test_init(self):
        """Test initialization."""
        config = ErrorTTLConfig(min_ttl=10, max_ttl=20, use_jitter=True)
        
        assert config.min_ttl == 10
        assert config.max_ttl == 20
        assert config.use_jitter is True
    
    def test_get_ttl_with_jitter(self):
        """Test TTL with jitter."""
        config = ErrorTTLConfig(min_ttl=10, max_ttl=20, use_jitter=True)
        
        ttls = [config.get_ttl() for _ in range(100)]
        
        # Should be in range
        assert all(10 <= ttl <= 20 for ttl in ttls)
        # Should have variation (not all the same)
        assert len(set(ttls)) > 1
    
    def test_get_ttl_without_jitter(self):
        """Test TTL without jitter."""
        config = ErrorTTLConfig(min_ttl=10, max_ttl=20, use_jitter=False)
        
        ttls = [config.get_ttl() for _ in range(10)]
        
        # Should always return min_ttl
        assert all(ttl == 10 for ttl in ttls)


class TestCachedError:
    """Tests for CachedError."""
    
    def test_init(self):
        """Test initialization."""
        error = CachedError(
            status_code=404,
            message="Not found",
            cached_at=time.time(),
        )
        
        assert error.status_code == 404
        assert error.message == "Not found"
        assert error.retry_after is None
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        cached_at = time.time()
        error = CachedError(
            status_code=429,
            message="Rate limited",
            cached_at=cached_at,
            retry_after=60,
        )
        
        data = error.to_dict()
        
        assert data["status_code"] == 429
        assert data["message"] == "Rate limited"
        assert data["cached_at"] == cached_at
        assert data["retry_after"] == 60
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "status_code": 503,
            "message": "Service unavailable",
            "cached_at": 1234567890.0,
            "retry_after": 30,
        }
        
        error = CachedError.from_dict(data)
        
        assert error.status_code == 503
        assert error.message == "Service unavailable"
        assert error.cached_at == 1234567890.0
        assert error.retry_after == 30
    
    def test_age(self):
        """Test age calculation."""
        cached_at = time.time() - 5.0  # 5 seconds ago
        error = CachedError(
            status_code=404,
            message="Not found",
            cached_at=cached_at,
        )
        
        age = error.age()
        assert 4.9 < age < 5.1  # Roughly 5 seconds


class TestErrorCache:
    """Tests for ErrorCache."""
    
    def test_init(self):
        """Test initialization."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        assert error_cache.cache is cache
        assert error_cache.enable_negative_caching is True
    
    def test_cache_error_404(self):
        """Test caching 404 error."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        # Cache 404 error
        result = error_cache.cache_error(
            key="test_key",
            status_code=404,
            message="Resource not found",
        )
        
        assert result is True
        
        # Verify cached
        cached_error = error_cache.get_cached_error("test_key", 404)
        assert cached_error is not None
        assert cached_error.status_code == 404
        assert cached_error.message == "Resource not found"
    
    def test_cache_error_429_with_retry_after(self):
        """Test caching 429 with Retry-After header."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        # Cache 429 with retry_after
        result = error_cache.cache_error(
            key="rate_limit_key",
            status_code=429,
            message="Rate limited",
            retry_after=120,
        )
        
        assert result is True
        
        # Verify cached
        cached_error = error_cache.get_cached_error("rate_limit_key", 429)
        assert cached_error is not None
        assert cached_error.status_code == 429
        assert cached_error.retry_after == 120
    
    def test_cache_error_unknown_status(self):
        """Test caching unknown error status."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        # Try to cache unknown status
        result = error_cache.cache_error(
            key="test_key",
            status_code=500,  # Not in ErrorType enum
            message="Internal server error",
        )
        
        assert result is False
    
    def test_negative_caching_disabled(self):
        """Test with negative caching disabled."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache, enable_negative_caching=False)
        
        # Try to cache 404 with negative caching disabled
        result = error_cache.cache_error(
            key="test_key",
            status_code=404,
            message="Not found",
        )
        
        assert result is False
    
    def test_is_error_cached(self):
        """Test checking if error is cached."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        # Initially not cached
        assert not error_cache.is_error_cached("test_key", 404)
        
        # Cache error
        error_cache.cache_error("test_key", 404, "Not found")
        
        # Now cached
        assert error_cache.is_error_cached("test_key", 404)
    
    def test_clear_error(self):
        """Test clearing cached error."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        # Cache error
        error_cache.cache_error("test_key", 404, "Not found")
        assert error_cache.is_error_cached("test_key", 404)
        
        # Clear error
        error_cache.clear_error("test_key", 404)
        
        # No longer cached
        assert not error_cache.is_error_cached("test_key", 404)
    
    def test_clear_all_errors(self):
        """Test clearing all errors for a key."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        # Cache multiple errors
        error_cache.cache_error("test_key", 404, "Not found")
        error_cache.cache_error("test_key", 503, "Service unavailable")
        
        assert error_cache.is_error_cached("test_key", 404)
        assert error_cache.is_error_cached("test_key", 503)
        
        # Clear all
        error_cache.clear_all_errors("test_key")
        
        # All cleared
        assert not error_cache.is_error_cached("test_key", 404)
        assert not error_cache.is_error_cached("test_key", 503)
    
    def test_get_stats(self):
        """Test getting statistics."""
        from pyeuropepmc.cache import CacheBackend, CacheConfig
        
        cache = CacheBackend(CacheConfig(enabled=True))
        error_cache = ErrorCache(cache)
        
        stats = error_cache.get_stats()
        
        assert isinstance(stats, dict)
        assert "cached_404" in stats
        assert "cached_429" in stats


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_should_cache_error(self):
        """Test should_cache_error function."""
        assert should_cache_error(404) is True
        assert should_cache_error(410) is True
        assert should_cache_error(429) is True
        assert should_cache_error(502) is True
        assert should_cache_error(503) is True
        assert should_cache_error(504) is True
        
        assert should_cache_error(200) is False
        assert should_cache_error(500) is False
    
    def test_get_default_error_ttl(self):
        """Test get_default_error_ttl function."""
        # 404 should have TTL
        ttl_404 = get_default_error_ttl(404)
        assert ttl_404 is not None
        assert 300 <= ttl_404 <= 900  # 5-15 minutes
        
        # 429 should have short TTL
        ttl_429 = get_default_error_ttl(429)
        assert ttl_429 is not None
        assert 30 <= ttl_429 <= 60  # 30-60 seconds
        
        # Unknown status should return None
        ttl_unknown = get_default_error_ttl(500)
        assert ttl_unknown is None
