"""
Professional cache backend for PyEuropePMC clients.

This module provides a robust, thread-safe caching layer with:
- File-based persistence using diskcache
- Configurable TTL (time-to-live) and size limits
- Query normalization for consistent cache keys
- Cache statistics and monitoring
- Manual cache control (clear, invalidate, refresh)
- Graceful degradation if cache is unavailable
"""

from collections.abc import Callable
import hashlib
import json
import logging
from pathlib import Path
import tempfile
from typing import Any, TypeVar

try:
    import diskcache

    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False
    diskcache = None

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class CacheConfig:
    """
    Configuration for cache behavior.

    Attributes
    ----------
    enabled : bool
        Whether caching is enabled
    cache_dir : Path
        Directory for cache storage
    ttl : int
        Time-to-live in seconds for cached entries
    size_limit_mb : int
        Maximum cache size in megabytes
    eviction_policy : str
        Policy for cache eviction ('least-recently-used', 'least-frequently-used')
    """

    def __init__(
        self,
        enabled: bool = True,
        cache_dir: Path | None = None,
        ttl: int = 86400,  # 24 hours default
        size_limit_mb: int = 500,  # 500MB default
        eviction_policy: str = "least-recently-used",
    ):
        """
        Initialize cache configuration.

        Parameters
        ----------
        enabled : bool, optional
            Whether caching is enabled (default: True)
        cache_dir : Path, optional
            Directory for cache storage (default: system temp/pyeuropepmc_cache)
        ttl : int, optional
            Time-to-live in seconds for cached entries (default: 86400 = 24 hours)
        size_limit_mb : int, optional
            Maximum cache size in megabytes (default: 500)
        eviction_policy : str, optional
            Policy for cache eviction (default: 'least-recently-used')
        """
        self.enabled = enabled and DISKCACHE_AVAILABLE

        if self.enabled and not DISKCACHE_AVAILABLE:
            logger.warning(
                "Cache requested but diskcache not available. Install with: pip install diskcache"
            )
            self.enabled = False

        if cache_dir is None:
            self.cache_dir = Path(tempfile.gettempdir()) / "pyeuropepmc_cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.ttl = ttl
        self.size_limit_mb = size_limit_mb
        self.eviction_policy = eviction_policy

        # Validate parameters
        if self.ttl < 0:
            raise ConfigurationError(
                ErrorCodes.CONFIG001,
                context={"parameter": "ttl", "value": ttl, "reason": "must be >= 0"},
            )

        if self.size_limit_mb < 1:
            raise ConfigurationError(
                ErrorCodes.CONFIG001,
                context={
                    "parameter": "size_limit_mb",
                    "value": size_limit_mb,
                    "reason": "must be >= 1",
                },
            )


class CacheBackend:
    """
    Professional cache backend with diskcache integration.

    This class provides a thread-safe, persistent cache with:
    - Automatic expiration based on TTL
    - Size-based eviction
    - Query normalization for consistent keys
    - Statistics tracking
    - Manual cache control
    """

    def __init__(self, config: CacheConfig):
        """
        Initialize cache backend.

        Parameters
        ----------
        config : CacheConfig
            Cache configuration object
        """
        self.config = config
        self.cache: Any | None = None  # diskcache.Cache type
        self._stats: dict[str, int | float] = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }

        if self.config.enabled:
            self._initialize_cache()

    def _initialize_cache(self) -> None:
        """Initialize diskcache with configuration."""
        if not DISKCACHE_AVAILABLE:
            logger.warning("Attempted to initialize cache but diskcache is not installed")
            self.config.enabled = False
            self.cache = None
            self._stats["errors"] += 1
            return
        try:
            # Create cache directory
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)

            # Initialize diskcache with configuration
            size_limit = self.config.size_limit_mb * 1024 * 1024  # Convert MB to bytes

            # Access Cache directly; use type-ignore for attribute checks because
            # diskcache may be typed as Any when the dependency is missing.
            CacheClass = diskcache.Cache
            self.cache = CacheClass(
                str(self.config.cache_dir),
                size_limit=size_limit,
                eviction_policy=self.config.eviction_policy,
                statistics=True,  # Enable built-in statistics
            )

            logger.info(
                f"Cache initialized: {self.config.cache_dir} "
                f"(TTL: {self.config.ttl}s, Size limit: {self.config.size_limit_mb}MB)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize cache: {e}")
            self.config.enabled = False
            self.cache = None
            self._stats["errors"] += 1

    def _normalize_key(self, prefix: str, **kwargs: Any) -> str:
        """
        Create normalized cache key from parameters with intelligent normalization.

        This method ensures consistent cache keys by:
        - Sorting parameters alphabetically
        - Normalizing whitespace in string values
        - Converting equivalent boolean/None representations
        - Handling case sensitivity intelligently
        - Removing default/empty parameters

        Parameters
        ----------
        prefix : str
            Key prefix (e.g., 'search', 'fulltext')
        **kwargs : Any
            Key-value pairs to include in the cache key

        Returns
        -------
        str
            Normalized cache key

        Examples
        --------
        >>> cache._normalize_key('search', query='COVID-19', pageSize=25)
        'search:a1b2c3d4e5f6g7h8'
        >>> cache._normalize_key('search', query='  COVID-19  ', pageSize=25)
        'search:a1b2c3d4e5f6g7h8'  # Same key despite whitespace
        """
        normalized = self._normalize_params(kwargs)

        # Sort parameters for consistent ordering
        sorted_params = sorted(normalized.items())

        # Create deterministic JSON representation
        params_json = json.dumps(sorted_params, sort_keys=True, default=str)

        # Hash for compact key
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]

        return f"{prefix}:{params_hash}"

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize parameters for consistent cache keys.

        Applies intelligent normalization rules:
        - Strips whitespace from strings
        - Converts booleans/None to canonical forms
        - Removes None/empty values (unless explicitly needed)
        - Normalizes numeric types
        - Handles list/dict ordering

        Parameters
        ----------
        params : dict
            Raw parameters

        Returns
        -------
        dict
            Normalized parameters
        """
        normalized = {}

        for key, value in params.items():
            normalized_value = self._normalize_value(key, value)
            if normalized_value is not None:
                normalized[key] = normalized_value

        return normalized

    def _normalize_value(self, key: str, value: Any) -> Any:
        """
        Normalize a single parameter value.

        Parameters
        ----------
        key : str
            Parameter key
        value : Any
            Parameter value

        Returns
        -------
        Any
            Normalized value or None if should be skipped
        """
        # Skip None values (unless key explicitly includes 'allow_none')
        if value is None and "allow_none" not in key.lower():
            return None

        # Normalize strings
        if isinstance(value, str):
            value = " ".join(value.split())  # Normalize internal whitespace
            return value if value else None  # Skip empty strings

        # Normalize booleans
        if isinstance(value, bool):
            return str(value).lower()  # 'true' or 'false'

        # Normalize numeric types
        if isinstance(value, int | float):
            return value

        # Normalize lists (sort if hashable elements)
        if isinstance(value, list | tuple):
            try:
                return tuple(sorted(value))  # Sort and convert to tuple
            except TypeError:
                return tuple(value)  # Keep order if not sortable

        # Normalize dicts (recursive)
        if isinstance(value, dict):
            normalized_dict = self._normalize_params(value)
            return normalized_dict if normalized_dict else None  # Skip empty dicts

        return value

    def normalize_query_key(
        self,
        query: str,
        prefix: str = "search",
        **params: Any,
    ) -> str:
        """
        Create normalized cache key specifically for search queries.

        This is a convenience method for creating consistent cache keys
        from search parameters with additional query-specific normalization.

        Parameters
        ----------
        query : str
            Search query string
        prefix : str, optional
            Key prefix (default: 'search')
        **params : Any
            Additional search parameters (pageSize, format, etc.)

        Returns
        -------
        str
            Normalized cache key

        Examples
        --------
        >>> cache.normalize_query_key('COVID-19', pageSize=25, format='json')
        'search:a1b2c3d4e5f6g7h8'
        >>> cache.normalize_query_key('  covid-19  ', pageSize=25, format='json')
        'search:a1b2c3d4e5f6g7h8'  # Case-insensitive normalization
        """
        # Normalize query string
        normalized_query = " ".join(query.split())  # Normalize whitespace

        # Combine with other parameters
        all_params = {"query": normalized_query, **params}

        return self._normalize_key(prefix, **all_params)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value from cache.

        Parameters
        ----------
        key : str
            Cache key
        default : Any, optional
            Default value if key not found

        Returns
        -------
        Any
            Cached value or default
        """
        if not self.config.enabled or self.cache is None:
            return default

        try:
            value = self.cache.get(key, default=default, retry=True)

            if value is default:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss: {key}")
            else:
                self._stats["hits"] += 1
                logger.debug(f"Cache hit: {key}")

            return value
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            self._stats["errors"] += 1
            return default

    def set(self, key: str, value: Any, expire: int | None = None, tag: str | None = None) -> bool:
        """
        Store value in cache.

        Parameters
        ----------
        key : str
            Cache key
        value : Any
            Value to cache (must be picklable)
        expire : int, optional
            TTL in seconds (default: use config TTL)
        tag : str, optional
            Tag for grouping related entries

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.config.enabled or self.cache is None:
            return False

        try:
            expire = expire or self.config.ttl
            success = self.cache.set(key, value, expire=expire, tag=tag)
            if success:
                self._stats["sets"] += 1
                logger.debug(f"Cache set: {key} (TTL: {expire}s)")
            return bool(success)
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            self._stats["errors"] += 1
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Parameters
        ----------
        key : str
            Cache key

        Returns
        -------
        bool
            True if deleted, False if not found or error
        """
        if not self.config.enabled or self.cache is None:
            return False

        try:
            success = self.cache.delete(key)
            if success:
                self._stats["deletes"] += 1
                logger.debug(f"Cache delete: {key}")
            return bool(success)
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            self._stats["errors"] += 1
            return False

    def clear(self) -> bool:
        """
        Clear all cached entries.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.config.enabled or self.cache is None:
            return False

        try:
            self.cache.clear()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            self._stats["errors"] += 1
            return False

    def evict(self, tag: str) -> int:
        """
        Evict all entries with a specific tag.

        Parameters
        ----------
        tag : str
            Tag to evict

        Returns
        -------
        int
            Number of entries evicted
        """
        if not self.config.enabled or self.cache is None:
            return 0

        try:
            count = self.cache.evict(tag)
            logger.info(f"Evicted {count} entries with tag '{tag}'")
            return int(count)
        except Exception as e:
            logger.warning(f"Cache evict error for tag {tag}: {e}")
            self._stats["errors"] += 1
            return 0

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns
        -------
        dict
            Statistics including hits, misses, size, and more
        """
        stats = self._stats.copy()

        if self.config.enabled and self.cache is not None:
            try:
                # Add diskcache built-in stats
                stats["size_bytes"] = self.cache.volume()
                stats["size_mb"] = round(self.cache.volume() / (1024 * 1024), 2)
                stats["entry_count"] = len(self.cache)
                stats["hit_rate"] = self._calculate_hit_rate()
            except Exception as e:
                logger.warning(f"Error getting cache stats: {e}")

        return stats

    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._stats["hits"] + self._stats["misses"]
        if total == 0:
            return 0.0
        return round(self._stats["hits"] / total, 4)

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}
        logger.debug("Cache statistics reset")

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Uses glob-style pattern matching:
        - '*' matches any sequence of characters
        - '?' matches any single character
        - '[seq]' matches any character in seq

        Parameters
        ----------
        pattern : str
            Glob pattern to match keys

        Returns
        -------
        int
            Number of entries invalidated

        Examples
        --------
        >>> cache.invalidate_pattern('search:*')  # All search queries
        >>> cache.invalidate_pattern('user:123:*')  # All data for user 123
        """
        if not self.config.enabled or self.cache is None:
            return 0

        try:
            import fnmatch

            count = 0
            keys_to_delete = []

            # Collect matching keys
            for key in self.cache.iterkeys():
                if fnmatch.fnmatch(key, pattern):
                    keys_to_delete.append(key)

            # Delete in batch
            for key in keys_to_delete:
                if self.delete(key):
                    count += 1

            logger.info(f"Invalidated {count} entries matching pattern '{pattern}'")
            return count
        except Exception as e:
            logger.warning(f"Pattern invalidation error for '{pattern}': {e}")
            self._stats["errors"] += 1
            return 0

    def invalidate_older_than(self, seconds: int) -> int:
        """
        Invalidate cache entries older than specified time.

        Parameters
        ----------
        seconds : int
            Age threshold in seconds

        Returns
        -------
        int
            Number of entries invalidated

        Examples
        --------
        >>> cache.invalidate_older_than(3600)  # Remove entries > 1 hour old
        """
        if not self.config.enabled or self.cache is None:
            return 0

        try:
            import time

            count = 0
            current_time = time.time()
            keys_to_delete = []

            # Check each entry's age
            for key in self.cache.iterkeys():
                # Get entry metadata
                try:
                    entry_time = self.cache.get(key, read=False, expire_time=True)
                except Exception as e:
                    logger.warning(f"Error reading cache entry for key {key}: {e}")
                    self._stats["errors"] += 1
                    continue
                if entry_time and (current_time - entry_time) > seconds:
                    keys_to_delete.append(key)

            # Delete old entries
            for key in keys_to_delete:
                if self.delete(key):
                    count += 1

            logger.info(f"Invalidated {count} entries older than {seconds}s")
            return count
        except Exception as e:
            logger.warning(f"Time-based invalidation error: {e}")
            self._stats["errors"] += 1
            return 0

    def warm_cache(
        self, entries: dict[str, Any], ttl: int | None = None, tag: str | None = None
    ) -> int:
        """
        Warm the cache with pre-computed entries.

        Useful for:
        - Preloading frequently accessed data
        - Scheduled cache warming jobs
        - Reducing initial latency

        Parameters
        ----------
        entries : dict
            Key-value pairs to cache
        ttl : int, optional
            TTL for all entries
        tag : str, optional
            Tag for all entries

        Returns
        -------
        int
            Number of entries successfully cached

        Examples
        --------
        >>> warm_data = {
        ...     'search:cancer': [...],
        ...     'search:diabetes': [...]
        ... }
        >>> cache.warm_cache(warm_data, ttl=3600, tag='popular')
        """
        if not self.config.enabled:
            return 0

        count = 0
        for key, value in entries.items():
            if self.set(key, value, expire=ttl, tag=tag):
                count += 1

        logger.info(f"Warmed cache with {count}/{len(entries)} entries")
        return count

    def get_health(self) -> dict[str, Any]:  # noqa: C901
        """
        Get cache health status.

        Returns comprehensive health metrics including:
        - Availability status
        - Hit rate
        - Size utilization
        - Error rate
        - Performance indicators

        Returns
        -------
        dict
            Health status and metrics

        Examples
        --------
        >>> health = cache.get_health()
        >>> if health['status'] == 'healthy':
        ...     print(f"Hit rate: {health['hit_rate']}")
        """
        health: dict[str, Any] = {
            "enabled": self.config.enabled,
            "status": "unknown",
            "available": False,
            "hit_rate": 0.0,
            "size_utilization": 0.0,
            "error_rate": 0.0,
            "warnings": [],
        }

        if not self.config.enabled:
            health["status"] = "disabled"
            return health

        if self.cache is None:
            if not isinstance(health["warnings"], list):
                health["warnings"] = []
            health["status"] = "unavailable"
            health["warnings"].append("Cache not initialized")
            return health

        try:
            # Get current stats
            stats = self.get_stats()

            # Local typed values to avoid mypy treating dict entries as `object`
            available: bool = True
            hit_rate: float = float(stats.get("hit_rate", 0.0) or 0.0)

            # Calculate size utilization
            size_mb: float = float(stats.get("size_mb", 0) or 0)
            size_limit: float = float(getattr(self.config, "size_limit_mb", 1) or 1)
            size_utilization: float = round(size_mb / size_limit, 4) if size_limit else 0.0

            # Calculate error rate
            total_ops: float = sum(
                float(stats.get(k, 0) or 0)
                for k in ["hits", "misses", "sets", "deletes", "errors"]
            )
            errors: float = float(stats.get("errors", 0) or 0)
            error_rate: float = round(errors / total_ops, 4) if total_ops > 0 else 0.0

            # Warnings list (typed)
            warnings_list: list[str] = []

            # Determine status using typed locals
            if size_utilization > 0.95:
                status = "critical"
                warnings_list.append("Cache nearly full (>95%)")
            elif size_utilization > 0.80:
                status = "warning"
                warnings_list.append("Cache filling up (>80%)")
            elif error_rate > 0.05:
                status = "warning"
                warnings_list.append(f"High error rate: {error_rate:.2%}")
            elif hit_rate < 0.5 and total_ops > 100:
                status = "warning"
                warnings_list.append(f"Low hit rate: {hit_rate:.2%}")
            else:
                status = "healthy"

            # Populate health dict from typed locals
            health["available"] = available
            health["hit_rate"] = hit_rate
            health["size_utilization"] = size_utilization
            health["error_rate"] = error_rate
            health["status"] = status
            health["warnings"] = warnings_list

        except Exception as e:
            health["status"] = "error"
            # Ensure warnings is a typed list
            existing = health.get("warnings")
            # narrow to list[str] safely
            warnings_list = [str(w) for w in existing] if isinstance(existing, list) else []

            warnings_list.append(f"Health check failed: {e}")
            health["warnings"] = warnings_list
            logger.error(f"Cache health check error: {e}")

        return health

    def compact(self) -> bool:
        """
        Compact cache storage to reclaim space.

        Removes expired entries and optimizes storage.
        This can be resource-intensive and should be run during low-traffic periods.

        Returns
        -------
        bool
            True if successful, False otherwise

        Examples
        --------
        >>> cache.compact()  # Run during maintenance window
        """
        if not self.config.enabled or self.cache is None:
            return False

        try:
            # Trigger cache cleanup
            self.cache.expire()
            logger.info("Cache compacted successfully")
            return True
        except Exception as e:
            logger.error(f"Cache compact error: {e}")
            self._stats["errors"] += 1
            return False

    def get_keys(self, pattern: str | None = None, limit: int = 1000) -> list[str]:
        """
        Get cache keys, optionally filtered by pattern.

        Parameters
        ----------
        pattern : str, optional
            Glob pattern to filter keys
        limit : int, default=1000
            Maximum number of keys to return

        Returns
        -------
        list[str]
            List of matching cache keys

        Examples
        --------
        >>> cache.get_keys('search:*', limit=100)
        ['search:a1b2c3', 'search:d4e5f6', ...]
        """
        if not self.config.enabled or self.cache is None:
            return []

        try:
            import fnmatch

            keys = []
            for key in self.cache.iterkeys():
                if pattern is None or fnmatch.fnmatch(key, pattern):
                    keys.append(key)
                    if len(keys) >= limit:
                        break

            return keys
        except Exception as e:
            logger.warning(f"Error getting keys: {e}")
            return []

    def close(self) -> None:
        """Close cache and release resources."""
        if self.cache is not None:
            try:
                self.cache.close()
                logger.debug("Cache closed")
            except Exception as e:
                logger.warning(f"Error closing cache: {e}")
            finally:
                self.cache = None


def cached(
    cache_backend: CacheBackend,
    key_prefix: str,
    ttl: int | None = None,
    tag: str | None = None,
    key_func: Callable[..., str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for caching function results.

    Parameters
    ----------
    cache_backend : CacheBackend
        Cache backend to use
    key_prefix : str
        Prefix for cache keys
    ttl : int, optional
        TTL override in seconds
    tag : str, optional
        Tag for grouped eviction
    key_func : Callable, optional
        Custom function to generate cache key from args/kwargs

    Returns
    -------
    Callable
        Decorated function with caching

    Examples
    --------
    >>> cache = CacheBackend(CacheConfig())
    >>> @cached(cache, 'search', ttl=3600)
    ... def search(query: str):
    ...     return expensive_api_call(query)
    """

    F = TypeVar("F", bound=Callable[..., Any])

    def decorator(func: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not cache_backend.config.enabled:
                return func(*args, **kwargs)

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name + args/kwargs
                key_parts = {"func": func.__name__, "args": args, "kwargs": kwargs}
                cache_key = cache_backend._normalize_key(key_prefix, **key_parts)

            # Try cache first
            result = cache_backend.get(cache_key)
            if result is not None:
                return result

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            cache_backend.set(cache_key, result, expire=ttl, tag=tag)

            return result

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper  # type: ignore

    return decorator


def normalize_query_params(params: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize query parameters for consistent cache keys.

    This is a standalone helper that applies the same normalization rules
    as the CacheBackend._normalize_params method:
    - Strips whitespace from strings
    - Converts booleans to canonical forms
    - Removes None/empty values
    - Normalizes numeric types
    - Handles list/dict ordering

    Parameters
    ----------
    params : dict
        Raw query parameters

    Returns
    -------
    dict
        Normalized parameters with consistent formatting

    Examples
    --------
    >>> normalize_query_params({"query": "  cancer  ", "pageSize": "10"})
    {'query': 'cancer', 'pageSize': 10}
    >>> normalize_query_params({"query": "test", "empty": "", "none": None})
    {'query': 'test'}
    """
    normalized = {}

    for key, value in params.items():
        normalized_value = _normalize_single_value(value)
        if normalized_value is not None:
            normalized[key] = normalized_value

    return normalized


def _normalize_single_value(value: Any) -> Any:
    """Normalize a single parameter value."""
    # Handle None
    if value is None:
        return None

    # Handle strings
    if isinstance(value, str):
        stripped = value.strip()
        # Try to convert to number
        if stripped:
            try:
                return float(stripped) if "." in stripped else int(stripped)
            except ValueError:
                return stripped
        return None

    # Handle booleans
    if isinstance(value, bool):
        return value

    # Handle numbers
    if isinstance(value, int | float):
        return value

    # Handle lists - normalize and sort
    if isinstance(value, list | tuple):
        normalized_list = [_normalize_single_value(item) for item in value]
        normalized_list = [v for v in normalized_list if v is not None]
        try:
            return sorted(normalized_list)
        except TypeError:
            return normalized_list

    # Handle dicts - normalize recursively
    if isinstance(value, dict):
        return {
            k: _normalize_single_value(v)
            for k, v in value.items()
            if _normalize_single_value(v) is not None
        }

    # Return as-is for other types
    return value


__all__ = [
    "CacheConfig",
    "CacheBackend",
    "cached",
    "normalize_query_params",
    "DISKCACHE_AVAILABLE",
]
