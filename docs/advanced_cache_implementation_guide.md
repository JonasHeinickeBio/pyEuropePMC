# Advanced Cache Architecture Implementation Guide

## Status: Phase 1 & 2 Complete ✅

This document tracks the implementation of the advanced multi-layer caching architecture for PyEuropePMC.

## Completed Features

### Phase 1: Enhanced L1 Cache ✅

**Namespace Versioning**
- Keys now include version: `{type}:v{version}:{prefix}:{hash}`
- Instant broad invalidation by bumping `namespace_version` in config
- Example: `search:v1:query:abc123` vs `search:v2:query:abc123`

**Data Type-Specific TTLs**
```python
DEFAULT_TTLS = {
    CacheDataType.SEARCH: 300,      # 5 minutes - volatile
    CacheDataType.RECORD: 86400,    # 1 day - semi-stable
    CacheDataType.FULLTEXT: 2592000, # 30 days - immutable
    CacheDataType.ERROR: 30,        # 30 seconds - very short
}
```

**Enhanced Statistics**
- Per-layer statistics (L1 and L2 separate)
- Overall combined metrics
- Hit rate calculation per layer

### Phase 2: L2 Persistent Cache ✅

**Multi-Layer Architecture**
- L1: `cachetools.TTLCache` (in-memory, hot data, ultra-fast)
- L2: `diskcache.Cache` (persistent, warm/cold data, survives restarts)

**Write-Through Pattern**
- Writes go to both L1 and L2 simultaneously
- Ensures consistency across layers
- Configurable per-layer writes via `layer` parameter

**L1/L2 Hierarchy**
```python
def get(key):
    # Try L1 first (fastest)
    if key in l1_cache:
        return l1_cache[key]  # L1 hit

    # Try L2 if L1 missed
    if key in l2_cache:
        value = l2_cache[key]
        l1_cache[key] = value  # Promote to L1
        return value  # L2 hit with promotion

    return None  # Cache miss
```

**Schema Migration**
- Automatic detection of old diskcache schemas
- Safe migration by removing incompatible databases
- Allows diskcache to recreate with correct schema

## Implementation Roadmap

### Phase 3: Content-Addressed Artifact Storage 📋

**Goal**: Efficient storage and deduplication of large files (PDF, XML, ZIP)

**Key Components**:

1. **SHA-256 Content Addressing**
   ```python
   class ArtifactStore:
       def store(self, content: bytes, metadata: dict) -> str:
           """Store content and return hash."""
           hash_value = hashlib.sha256(content).hexdigest()
           path = self._get_path(hash_value)  # artifacts/{hash[:2]}/{hash}
           if not path.exists():
               path.write_bytes(content)
           return hash_value

       def retrieve(self, hash_value: str) -> bytes:
           """Retrieve content by hash."""
           path = self._get_path(hash_value)
           return path.read_bytes()
   ```

2. **Index Mapping: ID → Hash → Path**
   ```python
   # Cache index entries
   index_key = f"ft:index:v1:{source}:{doc_id}:{format}"
   index_value = {
       "hash": "abc123...",
       "size": 1024000,
       "mime_type": "application/pdf",
       "etag": "abc123",
       "last_modified": "2025-11-12T10:00:00Z"
   }
   cache.set(index_key, index_value, data_type=CacheDataType.FULLTEXT)
   ```

3. **Deduplication**
   - Same content stored only once
   - Multiple IDs can reference same hash
   - Saves significant disk space

4. **Disk Watchdog**
   ```python
   class DiskWatchdog:
       def check_and_cull(self, high_water_mb: int):
           """Monitor disk usage and cull old artifacts."""
           usage = get_disk_usage()
           if usage > high_water_mb:
               self._cull_lru_artifacts(target_mb=high_water_mb * 0.9)
   ```

**Files to Create**:
- `src/pyeuropepmc/artifact_store.py` - Artifact storage implementation
- `tests/cache/test_artifact_store.py` - Tests for artifact storage

### Phase 4: HTTP Caching with requests-cache 📋

**Goal**: Protocol-correct HTTP caching with ETag/Last-Modified support

**Key Components**:

1. **requests-cache Integration**
   ```python
   import requests_cache

   session = requests_cache.CachedSession(
       cache_name='pyeuropepmc_http',
       backend='sqlite',
       expire_after=3600,
       allowable_codes=(200, 304),
   )
   ```

2. **Conditional GET Support**
   ```python
   def fetch_with_cache(url: str, etag: str = None):
       headers = {}
       if etag:
           headers['If-None-Match'] = etag

       response = session.get(url, headers=headers)

       if response.status_code == 304:
           # Not modified, extend TTL
           return cached_content

       return response.content
   ```

3. **ETag and Last-Modified Headers**
   - Store headers with content
   - Use for conditional GET requests
   - Handle 304 Not Modified responses

**Files to Create**:
- `src/pyeuropepmc/http_cache.py` - HTTP caching wrapper
- `tests/cache/test_http_cache.py` - Tests for HTTP caching

### Phase 5: Advanced Features 📋

**Cursor-Based Pagination**
```python
class PaginationState:
    """Track pagination progress."""
    cursor: str | None
    fetched_count: int
    last_doc_id: str
    completed: bool

# Cache pagination state
state_key = f"search:progress:v1:{norm_query}"
cache.set(state_key, state, data_type=CacheDataType.SEARCH)
```

**Checkpointing for Long Crawls**
```python
def crawl_with_checkpoints(query: str, checkpoint_interval: int = 100):
    checkpoint_key = f"crawl:checkpoint:v1:{query_hash}"
    checkpoint = cache.get(checkpoint_key) or {"page": 1, "count": 0}

    for page in range(checkpoint["page"], max_pages):
        results = fetch_page(query, page)
        process_results(results)

        checkpoint["page"] = page + 1
        checkpoint["count"] += len(results)
        cache.set(checkpoint_key, checkpoint, ttl=86400)
```

**Negative Caching**
```python
def cache_404_response(key: str):
    """Cache 404 responses briefly to avoid repeated requests."""
    error_key = f"error:404:v1:{key}"
    cache.set(error_key, {"status": 404}, data_type=CacheDataType.ERROR)  # 30s TTL
```

**Error-Specific Caching**
```python
ERROR_TTL_MAP = {
    429: (30, 60),   # Rate limit: 30-60s with jitter
    502: (10, 20),   # Bad gateway: 10-20s
    503: (20, 40),   # Service unavailable: 20-40s
    504: (15, 30),   # Gateway timeout: 15-30s
}

def cache_error(status_code: int, key: str, response: dict):
    min_ttl, max_ttl = ERROR_TTL_MAP.get(status_code, (30, 60))
    ttl = random.randint(min_ttl, max_ttl)  # Jitter

    error_key = f"error:{status_code}:v1:{key}"
    cache.set(error_key, response, expire=ttl)
```

**Files to Create**:
- `src/pyeuropepmc/pagination.py` - Pagination state management
- `src/pyeuropepmc/error_cache.py` - Error caching strategies
- `tests/cache/test_pagination.py` - Pagination tests
- `tests/cache/test_error_cache.py` - Error caching tests

### Phase 6: Monitoring and Observability 📋

**Telemetry**
```python
class CacheMetrics:
    """Comprehensive cache metrics."""

    def get_metrics(self) -> dict:
        return {
            "l1": {
                "hit_rate": self.l1_hit_rate,
                "miss_rate": self.l1_miss_rate,
                "latency_p50": self.l1_latency_p50,
                "latency_p99": self.l1_latency_p99,
                "size_mb": self.l1_size_mb,
                "eviction_count": self.l1_evictions,
            },
            "l2": {
                "hit_rate": self.l2_hit_rate,
                "miss_rate": self.l2_miss_rate,
                "latency_p50": self.l2_latency_p50,
                "latency_p99": self.l2_latency_p99,
                "size_mb": self.l2_size_mb,
                "disk_usage_percent": self.l2_disk_usage,
            },
            "overall": {
                "total_hit_rate": self.total_hit_rate,
                "avg_latency": self.avg_latency,
                "error_rate": self.error_rate,
            }
        }
```

**Health Checks**
```python
def get_cache_health() -> dict:
    """Comprehensive health status."""
    metrics = cache.get_stats()

    warnings = []
    if metrics["l2"]["disk_usage_percent"] > 90:
        warnings.append("L2 disk usage critical (>90%)")
    if metrics["l2"]["hit_rate"] < 0.3:
        warnings.append("L2 hit rate low (<30%)")
    if metrics["overall"]["error_rate"] > 0.05:
        warnings.append("High error rate (>5%)")

    status = "critical" if any("critical" in w for w in warnings) else \
             "warning" if warnings else "healthy"

    return {
        "status": status,
        "warnings": warnings,
        "metrics": metrics
    }
```

**Logging**
```python
# Structured logging for cache operations
logger.info(
    "Cache operation completed",
    extra={
        "operation": "set",
        "layer": "l2",
        "key_type": "search",
        "ttl": 300,
        "size_bytes": 1024,
        "namespace_version": 1
    }
)
```

**Files to Create**:
- `src/pyeuropepmc/cache_metrics.py` - Metrics collection
- `src/pyeuropepmc/cache_health.py` - Health monitoring
- `tests/cache/test_metrics.py` - Metrics tests

## Migration Guide for Existing Users

### Backward Compatibility

The enhanced cache is **100% backward compatible** with existing code:

```python
# Old code still works
from pyeuropepmc.cache import CacheBackend, CacheConfig

config = CacheConfig(enabled=True, ttl=3600)
cache = CacheBackend(config)

cache.set("key", "value")
result = cache.get("key")
```

### Opting Into New Features

```python
# Enable multi-layer caching
config = CacheConfig(
    enabled=True,
    enable_l2=True,  # NEW: Enable L2 persistent cache
    namespace_version=1,  # NEW: For invalidation
    ttl_by_type={  # NEW: Per-type TTLs
        CacheDataType.SEARCH: 300,
        CacheDataType.RECORD: 86400,
    }
)

cache = CacheBackend(config)

# Use data types for automatic TTL selection
cache.set(
    key,
    value,
    data_type=CacheDataType.SEARCH  # NEW: Automatic 300s TTL
)
```

### Invalidation Strategies

**Pattern-Based** (existing):
```python
cache.invalidate_pattern("search:*")  # Clear all search queries
```

**Namespace Version Bump** (new):
```python
# Change config from v1 to v2
config_v2 = CacheConfig(namespace_version=2)
cache_v2 = CacheBackend(config_v2)
# All v1 keys are now effectively invalidated
```

## Performance Characteristics

### Expected Hit Rates

- **L1 (hot data)**: 70-90% for frequently accessed queries
- **L2 (warm data)**: 40-60% for less frequent but still common queries
- **Overall**: 80-95% combined hit rate

### Latency Targets

- **L1 hit**: < 1ms (in-memory dictionary lookup)
- **L2 hit**: < 10ms (local disk read with SQLite)
- **L2 → L1 promotion**: < 2ms (additional in-memory write)
- **Cache miss**: 50-500ms (depends on API response time)

### Storage Efficiency

- **L1**: 500MB (5,000-10,000 entries)
- **L2**: 5GB (50,000-100,000 entries)
- **Artifacts**: Limited by disk (deduplicated, content-addressed)

## Testing Strategy

### Unit Tests
- Per-component testing (L1, L2, artifact store, HTTP cache)
- Edge cases (empty cache, full cache, concurrent access)
- Error conditions (disk full, permission errors, corrupted data)

### Integration Tests
- L1/L2 coordination
- Cache promotion and demotion
- Namespace version changes
- Pattern invalidation across layers

### Performance Tests
- Benchmark hit rates with realistic workloads
- Measure latency distributions (p50, p95, p99)
- Test under high concurrency
- Stress test with large datasets

### End-to-End Tests
- Full workflow: search → cache → retrieve → validate
- Multi-process scenarios
- Cache persistence across restarts
- Artifact deduplication

## Documentation Requirements

### User Documentation
- [x] Cache architecture overview
- [ ] Configuration guide
- [ ] Best practices for each data type
- [ ] Performance tuning guide
- [ ] Troubleshooting guide

### Developer Documentation
- [x] API reference (in docstrings)
- [x] Architecture decision records
- [ ] Extension guide (adding new data types)
- [ ] Contribution guidelines

### Examples
- [x] Basic usage examples (in docstrings)
- [ ] Advanced patterns (pagination, checkpointing)
- [ ] Integration examples (with search, fulltext modules)
- [ ] Performance optimization examples

## Next Steps

1. **Phase 3 (Content-Addressed Storage)**: Implement artifact store for large files
2. **Phase 4 (HTTP Caching)**: Integrate requests-cache for protocol-correct caching
3. **Phase 5 (Advanced Features)**: Add pagination, checkpointing, negative caching
4. **Phase 6 (Monitoring)**: Build comprehensive telemetry and health monitoring
5. **Documentation**: Complete user and developer documentation
6. **Performance Testing**: Benchmark and optimize based on real workloads

## References

- [cachetools documentation](https://cachetools.readthedocs.io/)
- [diskcache documentation](http://www.grantjenks.com/docs/diskcache/)
- [requests-cache documentation](https://requests-cache.readthedocs.io/)
- [HTTP Caching RFC 7234](https://tools.ietf.org/html/rfc7234)
- [Content Addressing](https://en.wikipedia.org/wiki/Content-addressable_storage)
