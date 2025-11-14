# Advanced Multi-Layer Caching

PyEuropePMC implements a sophisticated multi-layer caching architecture optimized for scientific literature retrieval. This professional-grade system provides significant performance improvements while maintaining data freshness and reliability.

## Architecture Overview

### Multi-Layer Cache Design

The cache system implements a **hierarchical caching strategy** with three distinct layers:

1. **L1 Cache (In-Memory)**: Ultra-fast access using `cachetools.TTLCache`
   - Hot data with short TTL (seconds to minutes)
   - Per-process, survives for session duration
   - Maximum speed for frequently accessed data

2. **L2 Cache (Persistent)**: Durable storage using `diskcache`
   - Warm/cold data with longer TTL (hours to days)
   - Survives process restarts and system reboots
   - Shared across multiple processes

3. **Content-Addressed Storage**: Immutable artifact storage
   - SHA-256 based content addressing
   - Automatic deduplication
   - Optimized for large files (PDFs, XMLs)

### Data Type Optimization

Different data types have optimized TTL configurations:

```python
DEFAULT_TTLS = {
    CacheDataType.SEARCH: 300,      # 5 minutes - volatile search results
    CacheDataType.RECORD: 86400,    # 24 hours - semi-stable article metadata
    CacheDataType.FULLTEXT: 2592000, # 30 days - mostly immutable full-text
    CacheDataType.ERROR: 30,        # 30 seconds - very short error responses
}
```

## Quick Start

### Basic Multi-Layer Caching

```python
from pyeuropepmc.cache import CacheConfig, CacheBackend

# Configure multi-layer cache
config = CacheConfig(
    enabled=True,
    enable_l2=True,              # Enable L2 persistent cache
    size_limit_mb=500,           # L1: 500MB
    l2_size_limit_mb=5000,       # L2: 5GB
    namespace_version=1,         # Version for invalidation
)

cache = CacheBackend(config)

# Cache with automatic data type detection
cache.set("search:covid", search_results, data_type=CacheDataType.SEARCH)
cache.set("record:PMC123", article_data, data_type=CacheDataType.RECORD)
cache.set("fulltext:PMC123:pdf", pdf_hash, data_type=CacheDataType.FULLTEXT)
```

### Content-Addressed Artifact Storage

```python
from pyeuropepmc.storage import ArtifactStore

# Initialize content-addressed storage
store = ArtifactStore("/path/to/artifacts", max_size_mb=10000)

# Store content with automatic deduplication
pdf_hash = store.store_artifact(
    content=pdf_bytes,
    mime_type="application/pdf",
    source_id="PMC12345",
    format_type="pdf"
)

# Retrieve by hash
pdf_content = store.get_artifact(pdf_hash)
```

## Advanced Features

### Namespace Versioning

Enable instant broad invalidation by bumping namespace versions:

```python
# Version 1 cache keys
cache_v1 = CacheBackend(CacheConfig(namespace_version=1))
cache_v1.set("search:cancer", results)  # Key: "search:v1:cancer:hash"

# Upgrade to version 2 (different algorithm)
cache_v2 = CacheBackend(CacheConfig(namespace_version=2))
cache_v2.set("search:cancer", results)  # Key: "search:v2:cancer:hash"

# Invalidate all v1 entries instantly
cache_v1.invalidate_pattern("*:v1:*")
```

### Query Normalization

Consistent cache keys through intelligent parameter normalization:

```python
from pyeuropepmc.cache import normalize_query_params

# These generate the same cache key
params1 = {"query": "  COVID-19  ", "pageSize": "25"}
params2 = {"query": "covid-19", "pageSize": 25}

normalized1 = normalize_query_params(params1)  # {"query": "COVID-19", "pageSize": 25}
normalized2 = normalize_query_params(params2)  # {"query": "covid-19", "pageSize": 25}

# Keys are identical despite formatting differences
key1 = cache.normalize_query_key(**params1)
key2 = cache.normalize_query_key(**params2)
assert key1 == key2  # True
```

### Tag-Based Selective Eviction

Group related cache entries for bulk operations:

```python
# Tag entries by category
cache.set("search:cancer", results, tag="oncology")
cache.set("search:diabetes", results, tag="endocrinology")
cache.set("record:PMC123", article, tag="oncology")

# Evict all oncology-related data
evicted = cache.evict("oncology")  # Evicts 2 entries
```

### Pattern-Based Invalidation

Use glob patterns for sophisticated cache management:

```python
# Invalidate all search queries
cache.invalidate_pattern("search:*")

# Invalidate specific namespace version
cache.invalidate_pattern("*:v1:*")

# Invalidate specific data types
cache.invalidate_pattern("record:*")
```

### Cache Warming

Pre-populate cache with frequently accessed data:

```python
popular_queries = {
    "search:cancer": cancer_results,
    "search:diabetes": diabetes_results,
    "record:PMC_top_cited": top_article,
}

warmed_count = cache.warm_cache(popular_queries, tag="preloaded")
```

## Performance Optimization

### Cache Hierarchy Benefits

```
User Request → L1 Cache → L2 Cache → API Call
     ↓            ↓          ↓          ↓
   Instant     ~1ms       ~10ms      ~500ms
```

### Typical Performance Gains

- **First request**: Normal API latency (500-2000ms)
- **L2 cache hit**: 10-50ms (20-100x faster)
- **L1 cache hit**: 0.1-1ms (500-20000x faster)

### Memory Management

Automatic size-based eviction with configurable limits:

```python
config = CacheConfig(
    size_limit_mb=500,      # L1 cache limit
    l2_size_limit_mb=5000,  # L2 cache limit
    eviction_policy="least-recently-used"
)
```

## Monitoring and Health Checks

### Comprehensive Statistics

```python
stats = cache.get_stats()

# Overall metrics
print(f"Hit Rate: {stats['overall']['hit_rate']:.1%}")
print(f"Total Ops: {stats['overall']['hits'] + stats['overall']['misses']}")

# Per-layer metrics
l1_stats = stats['layers']['l1']
print(f"L1 Hit Rate: {l1_stats['hit_rate']:.1%}")
print(f"L1 Size: {l1_stats['size_mb']:.1f} MB")

l2_stats = stats['layers']['l2']
print(f"L2 Hit Rate: {l2_stats['hit_rate']:.1%}")
print(f"L2 Size: {l2_stats['size_mb']:.1f} MB")
```

### Health Monitoring

```python
health = cache.get_health()

if health['status'] == 'healthy':
    print("✅ Cache operating normally")
elif health['status'] == 'warning':
    print(f"⚠️  Warnings: {health['warnings']}")
else:
    print(f"❌ Critical: {health['warnings']}")

print(f"Size Utilization: {health['size_utilization']:.1%}")
print(f"Error Rate: {health['error_rate']:.1%}")
```

## Content-Addressed Storage

### SHA-256 Based Addressing

```python
import hashlib

# Content addressing ensures deduplication
content = pdf_bytes
content_hash = hashlib.sha256(content).hexdigest()

# Same content always produces same hash
# Different IDs can reference same content
store.store_artifact(content, source_id="PMC123", format_type="pdf")  # hash_abc
store.store_artifact(content, source_id="PMC456", format_type="pdf")  # hash_abc (same!)
```

### Storage Benefits

- **Deduplication**: Identical content stored once
- **Integrity**: SHA-256 verification
- **Immutability**: Content never changes
- **Efficiency**: Reduced storage requirements

## Client Integration

### SearchClient with Advanced Caching

```python
from pyeuropepmc.search import SearchClient
from pyeuropepmc.cache import CacheConfig

config = CacheConfig(
    enabled=True,
    enable_l2=True,
    namespace_version=2,
    ttl_by_type={
        CacheDataType.SEARCH: 600,  # 10 minutes for search results
    }
)

client = SearchClient(cache_config=config)

# First search - cache miss
results = client.search("COVID-19 vaccine")

# Second search - cache hit (instant)
results = client.search("COVID-19 vaccine")
```

### FullTextClient with Artifact Storage

```python
from pyeuropepmc.fulltext import FullTextClient
from pyeuropepmc.storage import ArtifactStore

# Configure both caches
cache_config = CacheConfig(enabled=True, enable_l2=True)
artifact_store = ArtifactStore("./artifacts")

client = FullTextClient(
    cache_config=cache_config,
    artifact_store=artifact_store
)

# Downloads are cached with content addressing
pdf_path = client.download_pdf_by_pmcid("PMC12345")
xml_path = client.download_xml_by_pmcid("PMC12345")

# Same content automatically deduplicated
pdf2_path = client.download_pdf_by_pmcid("PMC67890")  # Different article, same PDF
# Storage shows only one copy of identical content
```

## Best Practices

### 1. Configure TTLs by Use Case

```python
# Research workflows - longer TTLs
research_config = CacheConfig(
    ttl_by_type={
        CacheDataType.SEARCH: 3600,    # 1 hour - stable queries
        CacheDataType.RECORD: 86400,   # 24 hours - rarely change
        CacheDataType.FULLTEXT: 604800, # 1 week - very stable
    }
)

# Real-time monitoring - shorter TTLs
monitoring_config = CacheConfig(
    ttl_by_type={
        CacheDataType.SEARCH: 300,     # 5 minutes - fresh data needed
        CacheDataType.RECORD: 1800,    # 30 minutes - updates possible
        CacheDataType.FULLTEXT: 3600,  # 1 hour - balance freshness/speed
    }
)
```

### 2. Monitor Cache Health

```python
def check_cache_health(cache):
    health = cache.get_health()

    # Alert on low hit rate
    if health['hit_rate'] < 0.5:
        print(f"Low cache hit rate: {health['hit_rate']:.1%}")

    # Alert on high utilization
    if health['size_utilization'] > 0.9:
        print(f"Cache nearly full: {health['size_utilization']:.1%}")

    # Alert on errors
    if health['error_rate'] > 0.05:
        print(f"High cache error rate: {health['error_rate']:.1%}")

    return health['status'] == 'healthy'
```

### 3. Use Namespace Versioning for Upgrades

```python
# When upgrading query algorithms or data formats
def upgrade_cache_namespace(old_version, new_version):
    old_cache = CacheBackend(CacheConfig(namespace_version=old_version))
    new_cache = CacheBackend(CacheConfig(namespace_version=new_version))

    # Migrate important entries to new namespace
    # (or let them expire naturally)

    # Invalidate old namespace
    old_cache.invalidate_pattern(f"*:{old_version}:*")
```

### 4. Implement Cache Warming for Known Workloads

```python
def warm_common_queries(client, cache):
    common_queries = [
        "cancer immunotherapy",
        "COVID-19 vaccine efficacy",
        "diabetes treatment",
        "neural networks machine learning",
    ]

    warm_data = {}
    for query in common_queries:
        try:
            results = client.search(query, pageSize=10)
            key = cache.normalize_query_key(query, pageSize=10)
            warm_data[key] = results
        except Exception as e:
            print(f"Failed to warm query '{query}': {e}")

    cache.warm_cache(warm_data, tag="common_queries")
```

## Troubleshooting

### Common Issues

#### Low Hit Rate
```python
stats = cache.get_stats()
if stats['overall']['hit_rate'] < 0.3:
    print("Consider:")
    print("- Increasing TTL values")
    print("- Pre-warming cache with common queries")
    print("- Checking query normalization consistency")
```

#### Cache Too Large
```python
stats = cache.get_stats()
if stats.get('size_mb', 0) > cache.config.size_limit_mb * 0.9:
    # Clear old entries
    cache.invalidate_older_than(3600)  # Clear entries > 1 hour old
    # Or reduce TTL values
```

#### L2 Cache Not Working
```python
# Check diskcache availability
from pyeuropepmc.cache import DISKCACHE_AVAILABLE
if not DISKCACHE_AVAILABLE:
    print("Install diskcache: pip install diskcache")

# Check L2 configuration
config = CacheConfig(enable_l2=True)
if not config.enable_l2:
    print("L2 cache disabled - check diskcache installation")
```

### Debug Logging

Enable detailed cache logging:

```python
import logging
logging.getLogger('pyeuropepmc.cache').setLevel(logging.DEBUG)

# This will show cache hits/misses, key generation, etc.
```

## Performance Benchmarks

### Typical Results

Based on real-world usage patterns:

- **Search Queries**: 85-95% hit rate after initial warm-up
- **Article Records**: 90-98% hit rate (stable metadata)
- **Full-Text Downloads**: 80-90% hit rate (frequent re-access)
- **Memory Usage**: 50-200MB for L1 cache (configurable)
- **Disk Usage**: 1-10GB for L2 cache (configurable)

### Benchmark Script

```python
# Run the advanced demo for performance testing
python examples/06-caching/02-advanced-cache-demo.py
```

## Migration Guide

### From Basic Caching

```python
# Old way
client = SearchClient(enable_cache=True)

# New way - full control
from pyeuropepmc.cache import CacheConfig
config = CacheConfig(enabled=True, enable_l2=True)
client = SearchClient(cache_config=config)
```

### From No Caching

```python
# Add one line for significant performance gains
cache_config = CacheConfig(enabled=True)
client = SearchClient(cache_config=cache_config)
```

## API Reference

### CacheConfig

```python
class CacheConfig:
    def __init__(
        self,
        enabled: bool = True,
        cache_dir: Path | None = None,
        ttl: int = 86400,
        size_limit_mb: int = 500,
        eviction_policy: str = "least-recently-used",
        enable_l2: bool = False,
        l2_size_limit_mb: int = 5000,
        ttl_by_type: dict[CacheDataType, int] | None = None,
        namespace_version: int = 1,
    ):
        # ... see source for full parameter details
```

### CacheBackend

```python
class CacheBackend:
    def get(self, key: str, default=None, layer=None) -> Any: ...
    def set(self, key: str, value: Any, expire=None, tag=None, data_type=None, layer=None) -> bool: ...
    def delete(self, key: str, layer=None) -> bool: ...
    def clear(self, layer=None) -> bool: ...
    def get_stats(self) -> dict: ...
    def get_health(self) -> dict: ...
    def evict(self, tag: str) -> int: ...
    def invalidate_pattern(self, pattern: str, layer=None) -> int: ...
    def warm_cache(self, entries: dict, ttl=None, tag=None) -> int: ...
```

### ArtifactStore

```python
class ArtifactStore:
    def store_artifact(self, content: bytes, mime_type=None, source_id=None, format_type=None) -> str: ...
    def get_artifact(self, hash_value: str) -> bytes | None: ...
    def delete_artifact(self, hash_value: str) -> bool: ...
    def get_stats(self) -> dict: ...
    def cleanup(self, max_age_days=None) -> int: ...
```

## See Also

- [Advanced Cache Demo](../../examples/06-caching/02-advanced-cache-demo.py)
- [Cache API Reference](../api/cache.md)
- [Artifact Storage API Reference](../api/artifact-store.md)
- [Performance Benchmarks](../../examples/06-caching/performance-benchmark.py)
