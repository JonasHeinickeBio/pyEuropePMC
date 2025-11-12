"""
Error-specific caching strategies for PyEuropePMC.

This module provides intelligent caching for HTTP errors, including:
- Negative caching for 404 responses
- Transient error caching with jitter (429, 502, 503, 504)
- Error-specific TTL strategies
"""

import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """
    Types of cacheable errors.
    """
    
    NOT_FOUND = 404  # Not found - negative caching
    GONE = 410  # Gone - permanent negative caching
    RATE_LIMIT = 429  # Rate limited - short cache with jitter
    BAD_GATEWAY = 502  # Bad gateway - very short cache
    SERVICE_UNAVAILABLE = 503  # Service unavailable - short cache
    GATEWAY_TIMEOUT = 504  # Gateway timeout - short cache
    
    @classmethod
    def from_status_code(cls, status_code: int) -> Optional["ErrorType"]:
        """
        Get ErrorType from HTTP status code.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            ErrorType if recognized, None otherwise
        """
        try:
            return cls(status_code)
        except ValueError:
            return None


@dataclass
class ErrorTTLConfig:
    """
    TTL configuration for error caching.
    
    Attributes:
        min_ttl: Minimum TTL in seconds
        max_ttl: Maximum TTL in seconds
        use_jitter: Whether to add random jitter
    """
    
    min_ttl: int
    max_ttl: int
    use_jitter: bool = True
    
    def get_ttl(self) -> int:
        """
        Get TTL with optional jitter.
        
        Returns:
            TTL in seconds
        """
        if self.use_jitter and self.max_ttl > self.min_ttl:
            return random.randint(self.min_ttl, self.max_ttl)
        return self.min_ttl


# Default TTL configurations for different error types
DEFAULT_ERROR_TTLS = {
    ErrorType.NOT_FOUND: ErrorTTLConfig(300, 900, use_jitter=True),  # 5-15 minutes
    ErrorType.GONE: ErrorTTLConfig(3600, 7200, use_jitter=False),  # 1-2 hours (permanent)
    ErrorType.RATE_LIMIT: ErrorTTLConfig(30, 60, use_jitter=True),  # 30-60 seconds
    ErrorType.BAD_GATEWAY: ErrorTTLConfig(10, 20, use_jitter=True),  # 10-20 seconds
    ErrorType.SERVICE_UNAVAILABLE: ErrorTTLConfig(20, 40, use_jitter=True),  # 20-40 seconds
    ErrorType.GATEWAY_TIMEOUT: ErrorTTLConfig(15, 30, use_jitter=True),  # 15-30 seconds
}


@dataclass
class CachedError:
    """
    Cached error information.
    
    Attributes:
        status_code: HTTP status code
        message: Error message
        cached_at: Unix timestamp when cached
        retry_after: Optional Retry-After header value (for 429)
    """
    
    status_code: int
    message: str
    cached_at: float
    retry_after: Optional[int] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for caching."""
        return {
            "status_code": self.status_code,
            "message": self.message,
            "cached_at": self.cached_at,
            "retry_after": self.retry_after,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CachedError":
        """Create from cached dictionary."""
        return cls(
            status_code=data["status_code"],
            message=data["message"],
            cached_at=data["cached_at"],
            retry_after=data.get("retry_after"),
        )
    
    def age(self) -> float:
        """
        Get age of cached error in seconds.
        
        Returns:
            Seconds since cached
        """
        return time.time() - self.cached_at


class ErrorCache:
    """
    Cache manager for HTTP errors with intelligent TTL strategies.
    """
    
    def __init__(
        self,
        cache_backend: Any,
        error_ttls: Optional[dict[ErrorType, ErrorTTLConfig]] = None,
        enable_negative_caching: bool = True,
    ):
        """
        Initialize error cache manager.
        
        Args:
            cache_backend: Cache backend (e.g., CacheBackend instance)
            error_ttls: Custom TTL configurations per error type
            enable_negative_caching: Enable caching of 404/410 responses
        """
        self.cache = cache_backend
        self.error_ttls = error_ttls or DEFAULT_ERROR_TTLS
        self.enable_negative_caching = enable_negative_caching
    
    def _make_error_key(self, original_key: str, error_type: ErrorType) -> str:
        """
        Create error-specific cache key.
        
        Args:
            original_key: Original cache key
            error_type: Type of error
            
        Returns:
            Error cache key
        """
        # Prefix with error type to avoid poisoning normal cache entries
        return f"error:{error_type.value}:{original_key}"
    
    def cache_error(
        self,
        key: str,
        status_code: int,
        message: str,
        retry_after: Optional[int] = None,
    ) -> bool:
        """
        Cache an error response.
        
        Args:
            key: Original cache key
            status_code: HTTP status code
            message: Error message
            retry_after: Optional Retry-After header value
            
        Returns:
            True if cached, False if not cacheable
        """
        error_type = ErrorType.from_status_code(status_code)
        
        if not error_type:
            # Unknown error type - don't cache
            return False
        
        # Check if negative caching is disabled for 404/410
        if not self.enable_negative_caching and error_type in (
            ErrorType.NOT_FOUND,
            ErrorType.GONE,
        ):
            return False
        
        # Get TTL configuration
        ttl_config = self.error_ttls.get(error_type)
        if not ttl_config:
            return False
        
        # For rate limits, use Retry-After header if available
        if error_type == ErrorType.RATE_LIMIT and retry_after:
            ttl = min(retry_after, ttl_config.max_ttl)
        else:
            ttl = ttl_config.get_ttl()
        
        # Create error entry
        error = CachedError(
            status_code=status_code,
            message=message,
            cached_at=time.time(),
            retry_after=retry_after,
        )
        
        # Cache with error-specific key
        error_key = self._make_error_key(key, error_type)
        
        try:
            self.cache.set(error_key, error.to_dict(), ttl=ttl)
            logger.debug(
                f"Cached error {status_code} for key={key}, ttl={ttl}s"
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to cache error: {e}")
            return False
    
    def get_cached_error(self, key: str, status_code: int) -> Optional[CachedError]:
        """
        Get cached error if available.
        
        Args:
            key: Original cache key
            status_code: Expected error status code
            
        Returns:
            Cached error if found and valid, None otherwise
        """
        error_type = ErrorType.from_status_code(status_code)
        if not error_type:
            return None
        
        error_key = self._make_error_key(key, error_type)
        
        try:
            data = self.cache.get(error_key)
            if data:
                return CachedError.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to get cached error: {e}")
        
        return None
    
    def is_error_cached(self, key: str, status_code: int) -> bool:
        """
        Check if an error is cached.
        
        Args:
            key: Original cache key
            status_code: Error status code
            
        Returns:
            True if error is cached
        """
        return self.get_cached_error(key, status_code) is not None
    
    def clear_error(self, key: str, status_code: int) -> None:
        """
        Clear cached error.
        
        Args:
            key: Original cache key
            status_code: Error status code
        """
        error_type = ErrorType.from_status_code(status_code)
        if not error_type:
            return
        
        error_key = self._make_error_key(key, error_type)
        
        try:
            self.cache.delete(error_key)
            logger.debug(f"Cleared cached error {status_code} for key={key}")
        except Exception as e:
            logger.warning(f"Failed to clear cached error: {e}")
    
    def clear_all_errors(self, key: str) -> None:
        """
        Clear all cached errors for a key.
        
        Args:
            key: Original cache key
        """
        for error_type in ErrorType:
            self.clear_error(key, error_type.value)
    
    def get_stats(self) -> dict[str, int]:
        """
        Get error caching statistics.
        
        Returns:
            Dictionary with error counts by type
        """
        # Note: This is a simplified implementation
        # In production, you'd track these in separate counters
        stats = {
            "cached_404": 0,
            "cached_410": 0,
            "cached_429": 0,
            "cached_502": 0,
            "cached_503": 0,
            "cached_504": 0,
        }
        
        # This would require scanning cache or maintaining separate counters
        # For now, return empty stats
        return stats


def should_cache_error(status_code: int) -> bool:
    """
    Check if an error status code should be cached.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        True if error should be cached
    """
    return ErrorType.from_status_code(status_code) is not None


def get_default_error_ttl(status_code: int) -> Optional[int]:
    """
    Get default TTL for an error status code.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        TTL in seconds, or None if not cacheable
    """
    error_type = ErrorType.from_status_code(status_code)
    if not error_type:
        return None
    
    ttl_config = DEFAULT_ERROR_TTLS.get(error_type)
    if ttl_config:
        return ttl_config.get_ttl()
    
    return None
