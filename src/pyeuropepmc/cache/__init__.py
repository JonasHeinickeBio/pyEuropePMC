"""
Caching utilities for PyEuropePMC.

This subpackage provides the multi-layer cache backend used by every client:
an in-memory L1 layer and an optional persistent L2 layer backed by diskcache.
"""

from .cache import (
    CACHETOOLS_AVAILABLE,
    DISKCACHE_AVAILABLE,
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
    cached,
    normalize_query_params,
)

__all__ = [
    "CACHETOOLS_AVAILABLE",
    "DISKCACHE_AVAILABLE",
    "CacheBackend",
    "CacheConfig",
    "CacheDataType",
    "CacheLayer",
    "cached",
    "normalize_query_params",
]
