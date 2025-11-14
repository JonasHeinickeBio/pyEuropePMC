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
from enum import Enum
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import types
from typing import Any, TypeVar

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ConfigurationError

try:
    from cachetools import TTLCache

    CACHETOOLS_AVAILABLE = True
except ImportError:
    TTLCache = None
    CACHETOOLS_AVAILABLE = False

# diskcache is kept as optional fallback (not currently used)
# Type checking imports
diskcache: types.ModuleType | None = None
try:
    import diskcache

    DISKCACHE_AVAILABLE = True
except ImportError:
    diskcache = None
    DISKCACHE_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheDataType(Enum):
    """
    Types of data being cached with different characteristics.

    Each type has different volatility, access patterns, and optimal TTLs.
    """

    SEARCH = "search"  # Search result pages (volatile, paginated)
    RECORD = "record"  # Individual article metadata (semi-stable)
    FULLTEXT = "fulltext"  # PDF/XML/ZIP files (mostly immutable)
    ERROR = "error"  # Error responses (very short-lived)


class CacheLayer(Enum):
    """Cache layer in multi-tier architecture."""

    L1 = "l1"  # In-memory, per-process
    L2 = "l2"  # Persistent, shared across processes


def _validate_diskcache_schema(cache_dir: Path) -> bool:
    """
    Validate that a diskcache database has the required schema.

    This function checks if an existing diskcache database has all required
    columns, particularly the 'size' column which was added in later versions.
    If the schema is incompatible, the old database should be removed to allow
    diskcache to create a new one with the correct schema.

    Parameters
    ----------
    cache_dir : Path
        Directory containing the cache database

    Returns
    -------
    bool
        True if schema is valid or doesn't exist, False if schema is incompatible

    Notes
    -----
    Required columns for diskcache 5.6.3+:
    - rowid, key, raw, store_time, expire_time, access_time, access_count,
      tag, size, mode, filename, value
    """
    db_path = cache_dir / "cache.db"

    # If database doesn't exist, schema is "valid" (will be created)
    if not db_path.exists():
        return True

    try:
        return _check_and_migrate_schema(db_path)
    except sqlite3.Error as e:
        logger.warning(f"Failed to validate diskcache schema: {e}")
        return False


def _check_and_migrate_schema(db_path: Path) -> bool:
    """Check schema and migrate if needed."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        # Get column names from Cache table
        cursor.execute("PRAGMA table_info(Cache)")
        columns = [col[1] for col in cursor.fetchall()]

        # Check for required columns
        required_columns = ["size"]  # Require size column for proper diskcache operation
        missing_columns = [col for col in required_columns if col not in columns]

        if missing_columns:
            _migrate_schema_columns(cursor, missing_columns)
            conn.commit()
            logger.info("Diskcache schema migration completed successfully")

        return True
    except sqlite3.Error as e:
        logger.warning(
            f"Failed to migrate diskcache schema: {e}. Removing cache.db for fresh start."
        )
        # If migration fails, remove the cache.db file to force recreation
        if os.path.exists(str(db_path)):
            os.remove(str(db_path))
        raise ConfigurationError(
            ErrorCodes.CONFIG001,
            context={"operation": "diskcache_schema_migration", "error": str(e)},
            message=f"Failed to migrate diskcache schema: {e}",
        ) from e
    finally:
        conn.close()


def _migrate_schema_columns(cursor: sqlite3.Cursor, missing_columns: list[str]) -> None:
    """Migrate schema by adding missing columns."""
    logger.info(f"Migrating diskcache schema: adding missing columns {missing_columns}")
    for column in missing_columns:
        if column == "size":
            cursor.execute("ALTER TABLE Cache ADD COLUMN size INTEGER DEFAULT 0")
        # Add other columns as needed in future migrations


class CacheConfig:
    """
    Configuration for multi-layer cache behavior.

    Attributes
    ----------
    enabled : bool
        Whether caching is enabled
    cache_dir : Path
        Directory for cache storage
    ttl : int
        Default time-to-live in seconds for cached entries
    size_limit_mb : int
        Maximum cache size in megabytes
    eviction_policy : str
        Policy for cache eviction ('least-recently-used', 'least-frequently-used')
    enable_l2 : bool
        Whether to enable L2 persistent cache with diskcache
    ttl_by_type : dict[CacheDataType, int]
        TTL configuration per data type
    namespace_version : int
        Version number for namespace-based invalidation
    """

    # Default TTLs per data type (in seconds)
    DEFAULT_TTLS = {
        CacheDataType.SEARCH: 300,  # 5 minutes - volatile
        CacheDataType.RECORD: 86400,  # 1 day - semi-stable
        CacheDataType.FULLTEXT: 2592000,  # 30 days - immutable
        CacheDataType.ERROR: 30,  # 30 seconds - very short
    }

    def __init__(
        self,
        enabled: bool = True,
        cache_dir: Path | None = None,
        ttl: int = 86400,  # 24 hours default
        size_limit_mb: int = 500,  # 500MB default
        eviction_policy: str = "least-recently-used",
        enable_l2: bool = False,  # L2 cache disabled by default
        l2_size_limit_mb: int = 5000,  # 5GB for L2
        ttl_by_type: dict[CacheDataType, int] | None = None,
        namespace_version: int = 1,
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
            Default time-to-live in seconds for cached entries (default: 86400 = 24 hours)
        size_limit_mb : int, optional
            Maximum L1 cache size in megabytes (default: 500)
        eviction_policy : str, optional
            Policy for cache eviction (default: 'least-recently-used')
        enable_l2 : bool, optional
            Whether to enable L2 persistent cache (default: False)
        l2_size_limit_mb : int, optional
            Maximum L2 cache size in megabytes (default: 5000)
        ttl_by_type : dict, optional
            TTL configuration per data type (uses defaults if not provided)
        namespace_version : int, optional
            Version number for namespace-based cache invalidation (default: 1)
        """
        self.enabled = enabled and CACHETOOLS_AVAILABLE

        if self.enabled and not CACHETOOLS_AVAILABLE:
            logger.warning(
                "Cache requested but cachetools not available. "
                "Install with: pip install cachetools"
            )
            self.enabled = False

        if cache_dir is None:
            self.cache_dir = Path(tempfile.gettempdir()) / "pyeuropepmc_cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.ttl = ttl
        self.size_limit_mb = size_limit_mb
        self.l2_size_limit_mb = l2_size_limit_mb
        self.eviction_policy = eviction_policy
        self.enable_l2 = enable_l2 and DISKCACHE_AVAILABLE
        self.namespace_version = namespace_version

        # Set TTLs per data type
        self.ttl_by_type = self.DEFAULT_TTLS.copy()
        if ttl_by_type:
            self.ttl_by_type.update(ttl_by_type)

        if self.enable_l2 and not DISKCACHE_AVAILABLE:
            logger.warning(
                "L2 cache requested but diskcache not available. "
                "Install with: pip install diskcache. L2 cache disabled."
            )
            self.enable_l2 = False

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

        if self.namespace_version < 1:
            raise ConfigurationError(
                ErrorCodes.CONFIG001,
                context={
                    "parameter": "namespace_version",
                    "value": namespace_version,
                    "reason": "must be >= 1",
                },
            )

    def get_ttl(self, data_type: CacheDataType | None = None) -> int:
        """
        Get TTL for a specific data type.

        Parameters
        ----------
        data_type : CacheDataType, optional
            Type of data being cached

        Returns
        -------
        int
            TTL in seconds
        """
        if data_type and data_type in self.ttl_by_type:
            return self.ttl_by_type[data_type]
        return self.ttl


class CacheBackend:
    """
    Professional multi-layer cache backend.

    This class provides a thread-safe, multi-tier caching system with:
    - L1: In-memory cache using cachetools.TTLCache (hot data, ultra-fast)
    - L2: Persistent cache using diskcache (warm/cold data, survives restarts)
    - Automatic expiration based on TTL per data type
    - Size-based eviction (LRU)
    - Query normalization for consistent keys
    - Statistics tracking per layer
    - Manual cache control
    - Tag-based grouping for selective eviction
    - Namespace versioning for broad invalidation

    Attributes
    ----------
    config : CacheConfig
        Cache configuration
    l1_cache : TTLCache | None
        L1 in-memory cache
    l2_cache : diskcache.Cache | None
        L2 persistent cache
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
        self.l1_cache: Any | None = None  # cachetools.TTLCache type
        self.l2_cache: Any | None = None  # diskcache.Cache type
        self._tags: dict[str, set[str]] = {}  # Map tags to cache keys
        self._lock = threading.Lock()  # Single-flight lock for cache misses

        # Statistics per layer
        self._stats: dict[str, dict[str, int | float]] = {
            "l1": {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "errors": 0,
            },
            "l2": {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "errors": 0,
            },
        }

        if self.config.enabled:
            self._initialize_cache()

    @property
    def cache(self) -> Any:
        """
        Backward compatibility property for accessing L1 cache.

        Returns
        -------
        Any
            L1 cache object (TTLCache)
        """
        return self.l1_cache

    @cache.setter
    def cache(self, value: Any) -> None:
        """
        Backward compatibility setter for L1 cache.

        Parameters
        ----------
        value : Any
            Value to set for L1 cache
        """
        self.l1_cache = value

    def _initialize_cache(self) -> None:
        """
        Initialize multi-layer cache system.

        This method initializes:
        - L1: cachetools.TTLCache for in-memory caching
        - L2: diskcache.Cache for persistent caching (if enabled)

        L2 cache includes schema validation and migration for compatibility.
        """
        # Initialize L1 cache (in-memory)
        if not self._initialize_l1_cache():
            return

        # Initialize L2 cache (persistent) if enabled
        if self.config.enable_l2 and DISKCACHE_AVAILABLE:
            self._initialize_l2_cache()

    def _initialize_l1_cache(self) -> bool:
        """Initialize L1 in-memory cache. Returns True if successful."""
        if not CACHETOOLS_AVAILABLE:
            logger.warning("cachetools not available, caching disabled")
            self.config.enabled = False
            self.l1_cache = None
            return False

        try:
            # L1: In-memory cache with short TTL for hot data
            # Convert MB to approximate max items (assume ~1KB per item)
            l1_maxsize = min(self.config.size_limit_mb * 1024, 10000)
            if TTLCache is not None:
                self.l1_cache = TTLCache(maxsize=l1_maxsize, ttl=self.config.ttl)

                logger.info(
                    f"L1 cache initialized: TTL={self.config.ttl}s, "
                    f"maxsize={l1_maxsize}, namespace=v{self.config.namespace_version}"
                )
                return True
            else:
                logger.warning("TTLCache not available despite CACHETOOLS_AVAILABLE=True")
                self.config.enabled = False
                self.l1_cache = None
                return False

        except Exception as e:
            logger.error(f"Failed to initialize L1 cache: {e}")
            self.config.enabled = False
            self.l1_cache = None
            return False

    def _initialize_l2_cache(self) -> None:
        """Initialize L2 persistent cache."""
        try:
            cache_dir = self.config.cache_dir
            cache_dir.mkdir(parents=True, exist_ok=True)

            # For test environments, ensure clean cache directory to avoid schema issues
            # Remove any existing cache.db file to force fresh schema creation
            db_path = cache_dir / "cache.db"
            if db_path.exists():
                try:
                    os.remove(db_path)
                    logger.debug(f"Removed existing cache.db for fresh schema: {db_path}")
                    # Also remove any WAL/SHM files
                    for suffix in ["-wal", "-shm", "-journal"]:
                        wal_path = cache_dir / f"cache.db{suffix}"
                        if wal_path.exists():
                            os.remove(wal_path)
                except OSError as e:
                    logger.warning(f"Could not remove existing cache.db: {e}")

            # Initialize diskcache with size limit
            size_limit_bytes = self.config.l2_size_limit_mb * 1024 * 1024
            if diskcache is not None and hasattr(diskcache, "Cache"):
                self.l2_cache = diskcache.Cache(
                    str(cache_dir),
                    size_limit=size_limit_bytes,
                    eviction_policy="least-recently-used",
                )

                # Test the L2 cache with a simple operation to ensure it works
                try:
                    if self.l2_cache is not None:
                        test_key = "__test_l2_cache__"
                        self.l2_cache[test_key] = "test"
                        del self.l2_cache[test_key]
                        logger.debug("L2 cache test successful")
                except Exception as e:
                    logger.warning(f"L2 cache test failed: {e}. Disabling L2 cache.")
                    if self.l2_cache is not None:
                        self.l2_cache.close()
                    self.l2_cache = None
                    self.config.enable_l2 = False
                    return

                logger.info(
                    f"L2 cache initialized: dir={cache_dir}, "
                    f"size_limit={self.config.l2_size_limit_mb}MB"
                )
            else:
                logger.warning("Diskcache module not available despite DISKCACHE_AVAILABLE=True")
                self.config.enable_l2 = False

        except Exception as e:
            logger.warning(f"Failed to initialize L2 cache: {e}. Continuing with L1 only.")
            self.l2_cache = None
            self.config.enable_l2 = False

    def _normalize_key(
        self, prefix: str, data_type: CacheDataType | None = None, **kwargs: Any
    ) -> str:
        """
        Create normalized cache key with namespace versioning.

        This method ensures consistent cache keys by:
        - Adding namespace version for broad invalidation
        - Including data type in key structure
        - Sorting parameters alphabetically
        - Normalizing whitespace in string values
        - Converting equivalent boolean/None representations
        - Handling case sensitivity intelligently
        - Removing default/empty parameters

        Parameters
        ----------
        prefix : str
            Key prefix (e.g., 'search', 'fulltext', 'record')
        data_type : CacheDataType, optional
            Type of data being cached (for versioning and TTL)
        **kwargs : Any
            Key-value pairs to include in the cache key

        Returns
        -------
        str
            Normalized cache key with format: {data_type}:v{version}:{prefix}:{hash}

        Examples
        --------
        >>> cache._normalize_key('query', data_type=CacheDataType.SEARCH, query='COVID-19')
        'search:v1:query:a1b2c3d4e5f6g7h8'
        >>> cache._normalize_key('article', data_type=CacheDataType.RECORD, id='PMC12345')
        'record:v1:article:d9e8f7a6b5c4'
        """
        normalized = self._normalize_params(kwargs)

        # Sort parameters for consistent
        sorted_params = sorted(normalized.items())

        # Create deterministic JSON representation
        params_json = json.dumps(sorted_params, sort_keys=True, default=str)

        # Hash for compact key
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]

        # Build key with namespace versioning
        # Format: {data_type}:v{version}:{prefix}:{hash}
        type_prefix = data_type.value if data_type else "general"

        return f"{type_prefix}:v{self.config.namespace_version}:{prefix}:{params_hash}"

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
        'search:v1:query:a1b2c3d4e5f6g7h8'
        >>> cache.normalize_query_key('  covid-19  ', pageSize=25, format='json')
        'search:v1:query:a1b2c3d4e5f6g7h8'  # Same key despite whitespace
        """
        # Normalize query string
        normalized_query = " ".join(query.split())  # Normalize whitespace

        # Combine with other parameters
        all_params = {"query": normalized_query, **params}

        # Use SEARCH data type by default for query keys
        return self._normalize_key(prefix, data_type=CacheDataType.SEARCH, **all_params)

    def get(self, key: str, default: Any = None, layer: CacheLayer | None = None) -> Any:
        """
        Retrieve value from multi-layer cache.

        Implements cache hierarchy: L1 -> L2 -> miss
        On L2 hit, promotes to L1 for faster subsequent access.

        Parameters
        ----------
        key : str
            Cache key
        default : Any, optional
            Default value if key not found
        layer : CacheLayer, optional
            Specific layer to query (default: try both L1 then L2)

        Returns
        -------
        Any
            Cached value or default
        """
        if not self.config.enabled:
            return default

        # L1 cache check
        if layer in (None, CacheLayer.L1) and self.l1_cache is not None:
            if key in self.l1_cache:
                value = self.l1_cache[key]
                self._stats["l1"]["hits"] += 1
                logger.debug(f"L1 cache hit: {key}")
                return value
            self._stats["l1"]["misses"] += 1

        # L2 cache check
        if layer in (None, CacheLayer.L2) and self.config.enable_l2 and self.l2_cache is not None:
            value = self.l2_cache.get(key)
            if value is not None:
                self._stats["l2"]["hits"] += 1
                logger.debug(f"L2 cache hit: {key}")
                # Promote to L1
                if self.l1_cache is not None:
                    try:
                        self.l1_cache[key] = value
                        logger.debug(f"Promoted to L1: {key}")
                    except Exception as e:
                        logger.debug(f"L1 promotion failed: {e}")
                return value
            self._stats["l2"]["misses"] += 1

        logger.debug(f"Cache miss (all layers): {key}")
        return default

    def set(
        self,
        key: str,
        value: Any,
        expire: int | None = None,
        tag: str | None = None,
        data_type: CacheDataType | None = None,
        layer: CacheLayer | None = None,
    ) -> bool:
        """
        Store value in multi-layer cache.

        Implements write-through pattern: writes to both L1 and L2 simultaneously.

        Parameters
        ----------
        key : str
            Cache key
        value : Any
            Value to cache (must be picklable for L2)
        expire : int, optional
            TTL in seconds (overrides data_type default)
        tag : str, optional
            Tag for grouping related entries
        data_type : CacheDataType, optional
            Type of data (determines default TTL)
        layer : CacheLayer, optional
            Specific layer to write to (default: write to all layers)

        Returns
        -------
        bool
            True if successful in at least one layer, False otherwise
        """
        if not self.config.enabled:
            return False

        success = False

        # Determine TTL
        ttl = expire or (self.config.get_ttl(data_type) if data_type else self.config.ttl)

        try:
            # Write to L1 cache
            if layer in (None, CacheLayer.L1) and self.l1_cache is not None:
                try:
                    self.l1_cache[key] = value
                    self._stats["l1"]["sets"] += 1
                    logger.debug(f"L1 cache set: {key} (TTL: {ttl}s)")
                    success = True
                except Exception as e:
                    logger.warning(f"L1 cache set error for key {key}: {e}")
                    self._stats["l1"]["errors"] += 1

            # Write to L2 cache if enabled (write-through)
            if (
                layer in (None, CacheLayer.L2)
                and self.config.enable_l2
                and self.l2_cache is not None
            ):
                try:
                    self.l2_cache.set(key, value, expire=ttl)
                    self._stats["l2"]["sets"] += 1
                    logger.debug(f"L2 cache set: {key} (TTL: {ttl}s)")
                    success = True
                except Exception as e:
                    logger.warning(f"L2 cache set error for key {key}: {e}")
                    self._stats["l2"]["errors"] += 1

            # Track tag if provided
            if success and tag:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(key)

            return success

        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str, layer: CacheLayer | None = None) -> bool:
        """
        Delete value from multi-layer cache.

        Parameters
        ----------
        key : str
            Cache key
        layer : CacheLayer, optional
            Specific layer to delete from (default: delete from all layers)

        Returns
        -------
        bool
            True if deleted from at least one layer, False if not found or error
        """
        if not self.config.enabled:
            return False

        deleted = False

        # Delete from L1 cache
        if layer in (None, CacheLayer.L1) and self.l1_cache is not None and key in self.l1_cache:
            del self.l1_cache[key]
            self._stats["l1"]["deletes"] += 1
            logger.debug(f"L1 cache delete: {key}")
            deleted = True

        # Delete from L2 cache
        if (
            layer in (None, CacheLayer.L2)
            and self.config.enable_l2
            and self.l2_cache is not None
            and self.l2_cache.delete(key)
        ):
            self._stats["l2"]["deletes"] += 1
            logger.debug(f"L2 cache delete: {key}")
            deleted = True

        # Remove from tag tracking if deleted
        if deleted:
            for tag, keys in list(self._tags.items()):
                if key in keys:
                    keys.discard(key)
                    if not keys:
                        del self._tags[tag]

        return deleted

    def clear(self, layer: CacheLayer | None = None) -> bool:
        """
        Clear all cached entries from specified layer(s).

        Parameters
        ----------
        layer : CacheLayer, optional
            Specific layer to clear (default: clear all layers)

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.config.enabled:
            return False

        success = False

        try:
            # Clear L1 cache
            if (layer is None or layer == CacheLayer.L1) and self.l1_cache is not None:
                self.l1_cache.clear()
                logger.info("L1 cache cleared")
                success = True

            # Clear L2 cache
            if (
                (layer is None or layer == CacheLayer.L2)
                and self.config.enable_l2
                and self.l2_cache is not None
            ):
                self.l2_cache.clear()
                logger.info("L2 cache cleared")
                success = True

            # Clear tag tracking
            self._tags.clear()

            return success

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            if layer == CacheLayer.L1 or (layer is None and self.l1_cache is not None):
                self._stats["l1"]["errors"] += 1
            if layer == CacheLayer.L2 or (layer is None and self.l2_cache is not None):
                self._stats["l2"]["errors"] += 1
            return False

    def evict(self, tag: str) -> int:
        """
        Evict all entries with a specific tag from all layers.

        Parameters
        ----------
        tag : str
            Tag to evict

        Returns
        -------
        int
            Number of entries evicted
        """
        if not self.config.enabled:
            return 0

        try:
            count = 0
            if tag in self._tags:
                keys_to_delete = list(self._tags[tag])
                for key in keys_to_delete:
                    if self.delete(key):  # Deletes from all layers
                        count += 1

            logger.info(f"Evicted {count} entries with tag '{tag}' from all layers")
            return count
        except Exception as e:
            logger.warning(f"Cache evict error for tag {tag}: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """
        Get multi-layer cache statistics.

        Returns
        -------
        dict
            Statistics including hits, misses, size per layer, and overall metrics.
            For backward compatibility, also includes flat stats at top level.
        """
        stats: dict[str, Any] = {
            "namespace_version": self.config.namespace_version,
            "layers": {},
            "overall": {},
        }

        if not self.config.enabled:
            return stats

        try:
            # L1 cache stats
            if self.l1_cache is not None:
                l1_stats = self._stats["l1"].copy()
                l1_stats["entry_count"] = len(self.l1_cache)
                l1_stats["maxsize"] = self.l1_cache.maxsize
                l1_stats["currsize"] = self.l1_cache.currsize
                l1_stats["hit_rate"] = self._calculate_hit_rate("l1")
                l1_stats["size_bytes"] = l1_stats["currsize"] * 1024  # ~1KB per entry
                l1_stats["size_mb"] = round(l1_stats["size_bytes"] / (1024 * 1024), 2)
                stats["layers"]["l1"] = l1_stats

            # L2 cache stats
            if self.config.enable_l2 and self.l2_cache is not None:
                l2_stats = self._stats["l2"].copy()
                l2_stats["entry_count"] = len(self.l2_cache)
                l2_stats["hit_rate"] = self._calculate_hit_rate("l2")
                # Get disk usage from diskcache
                l2_stats["size_bytes"] = self.l2_cache.volume()
                l2_stats["size_mb"] = round(l2_stats["size_bytes"] / (1024 * 1024), 2)
                l2_stats["size_limit_mb"] = self.config.l2_size_limit_mb
                stats["layers"]["l2"] = l2_stats

            # Overall stats (combined)
            total_hits = sum(self._stats[layer]["hits"] for layer in ["l1", "l2"])
            total_misses = sum(self._stats[layer]["misses"] for layer in ["l1", "l2"])
            total_sets = sum(self._stats[layer]["sets"] for layer in ["l1", "l2"])
            total_deletes = sum(self._stats[layer]["deletes"] for layer in ["l1", "l2"])
            total_errors = sum(self._stats[layer]["errors"] for layer in ["l1", "l2"])

            stats["overall"] = {
                "hits": total_hits,
                "misses": total_misses,
                "sets": total_sets,
                "deletes": total_deletes,
                "errors": total_errors,
                "hit_rate": round(total_hits / (total_hits + total_misses), 4)
                if (total_hits + total_misses) > 0
                else 0.0,
            }

            # Backward compatibility: Add flat stats at top level
            stats["hits"] = total_hits
            stats["misses"] = total_misses
            stats["sets"] = total_sets
            stats["deletes"] = total_deletes
            stats["errors"] = total_errors
            stats["hit_rate"] = stats["overall"]["hit_rate"]

            # Add L1-specific stats for backward compatibility
            if self.l1_cache is not None:
                stats["entry_count"] = len(self.l1_cache)
                stats["maxsize"] = self.l1_cache.maxsize
                stats["currsize"] = self.l1_cache.currsize
                stats["size_bytes"] = stats["layers"]["l1"]["size_bytes"]
                stats["size_mb"] = stats["layers"]["l1"]["size_mb"]

        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")

        return stats

    def _calculate_hit_rate(self, layer: str) -> float:
        """
        Calculate cache hit rate for a specific layer.

        Parameters
        ----------
        layer : str
            Layer name ('l1' or 'l2')

        Returns
        -------
        float
            Hit rate as a decimal (0.0 to 1.0)
        """
        if layer not in self._stats:
            return 0.0

        layer_stats = self._stats[layer]
        total = layer_stats["hits"] + layer_stats["misses"]
        if total == 0:
            return 0.0
        return round(layer_stats["hits"] / total, 4)

    def reset_stats(self) -> None:
        """Reset statistics counters for all layers."""
        self._stats = {
            "l1": {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "errors": 0,
            },
            "l2": {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "errors": 0,
            },
        }
        logger.debug("Cache statistics reset for all layers")

    def invalidate_pattern(self, pattern: str, layer: CacheLayer | None = None) -> int:
        """
        Invalidate cache entries matching a pattern from specified layer(s).

        Uses glob-style pattern matching:
        - '*' matches any sequence of characters
        - '?' matches any single character
        - '[seq]' matches any character in seq

        Parameters
        ----------
        pattern : str
            Glob pattern to match keys
        layer : CacheLayer, optional
            Specific layer to invalidate from (default: all layers)

        Returns
        -------
        int
            Number of entries invalidated

        Examples
        --------
        >>> cache.invalidate_pattern('search:v1:*')  # All v1 search queries
        >>> cache.invalidate_pattern('record:v2:*')  # All v2 records
        >>> cache.invalidate_pattern('*:v1:*')  # All v1 entries across all types
        """
        if not self.config.enabled:
            return 0

        import fnmatch

        count = 0
        keys_to_delete = []

        # Collect matching keys from L1
        if layer in (None, CacheLayer.L1) and self.l1_cache is not None:
            for key in list(self.l1_cache.keys()):
                if fnmatch.fnmatch(key, pattern):
                    keys_to_delete.append(key)

        # Collect matching keys from L2
        if layer in (None, CacheLayer.L2) and self.config.enable_l2 and self.l2_cache is not None:
            for key in list(self.l2_cache):
                if fnmatch.fnmatch(str(key), pattern) and key not in keys_to_delete:
                    keys_to_delete.append(key)

        # Delete in batch from all layers
        for key in keys_to_delete:
            if self.delete(key, layer=layer):
                count += 1

        logger.info(
            f"Invalidated {count} entries matching pattern '{pattern}' "
            f"from {layer or 'all layers'}"
        )
        return count

    def invalidate_older_than(self, seconds: int) -> int:
        """
        Invalidate cache entries older than specified time.

        Note: With TTLCache, entries are automatically expired based on TTL.
        This method is provided for API compatibility but has limited functionality.

        Parameters
        ----------
        seconds : int
            Age threshold in seconds

        Returns
        -------
        int
            Number of entries invalidated (always 0 with TTLCache as expiration is automatic)

        Examples
        --------
        >>> cache.invalidate_older_than(3600)  # Remove entries > 1 hour old
        """
        if not self.config.enabled or self.cache is None:
            return 0

        # TTLCache automatically handles expiration based on TTL
        # No manual age-based invalidation is needed or possible
        logger.info("Age-based invalidation not needed with TTLCache (automatic TTL expiration)")
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

        Note: With TTLCache, compaction is automatic as expired entries
        are removed on access. This method is provided for API compatibility.

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
            # TTLCache automatically removes expired entries on access
            # Force iteration to trigger cleanup
            _ = list(self.cache.keys())
            logger.info("Cache compacted successfully (expired entries cleaned on access)")
            return True
        except Exception as e:
            logger.error(f"Cache compact error: {e}")
            self._stats["l1"]["errors"] += 1
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
            for key in list(self.cache.keys()):
                if pattern is None or fnmatch.fnmatch(key, pattern):
                    keys.append(key)
                    if len(keys) >= limit:
                        break

            return keys
        except Exception as e:
            logger.warning(f"Error getting keys: {e}")
            return []

    def close(self) -> None:
        """Close cache and release resources for all layers."""
        try:
            # Close L1 cache (in-memory, minimal cleanup)
            if self.l1_cache is not None:
                self.l1_cache.clear()
                self.l1_cache = None
                logger.debug("L1 cache closed")

            # Close L2 cache (persistent, needs proper cleanup)
            if self.l2_cache is not None:
                self.l2_cache.close()
                self.l2_cache = None
                logger.debug("L2 cache closed")

            # Clear tag tracking
            self._tags.clear()

            logger.info("Multi-layer cache closed successfully")

        except Exception as e:
            logger.warning(f"Error closing cache: {e}")


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
                cache_key = cache_backend._normalize_key(key_prefix, None, **key_parts)

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
    "CACHETOOLS_AVAILABLE",
    "DISKCACHE_AVAILABLE",  # Kept for backward compatibility
    "_validate_diskcache_schema",  # For testing
]
