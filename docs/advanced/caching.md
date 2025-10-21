# Client Caching

PyEuropePMC supports optional response caching across all clients (`SearchClient`, `ArticleClient`, and `FullTextClient`) to improve performance and reduce API load. This feature is **disabled by default** for backward compatibility.

## Quick Start

### Without Caching (Default)

```python
from pyeuropepmc.search import SearchClient
from pyeuropepmc.article import ArticleClient
from pyeuropepmc.fulltext import FullTextClient

# Default behavior - no caching
search_client = SearchClient()
article_client = ArticleClient()
fulltext_client = FullTextClient()
```

### With Caching

```python
from pyeuropepmc.search import SearchClient
from pyeuropepmc.article import ArticleClient
from pyeuropepmc.fulltext import FullTextClient
from pyeuropepmc.cache import CacheConfig

# Enable caching with defaults (24h TTL, 500MB limit)
cache_config = CacheConfig(enabled=True)

# All clients support caching
search_client = SearchClient(cache_config=cache_config)
article_client = ArticleClient(cache_config=cache_config)
fulltext_client = FullTextClient(cache_config=cache_config)

# First request - cache miss
search_results = search_client.search("cancer")

# Second request - cache hit! (much faster)
search_results = search_client.search("cancer")

# Same pattern for ArticleClient
article_details = article_client.get_article_details("MED", "25883711")
article_details = article_client.get_article_details("MED", "25883711")  # Cached

# And FullTextClient
availability = fulltext_client.check_fulltext_availability("3312970")
availability = fulltext_client.check_fulltext_availability("3312970")  # Cached
```

## Cache Configuration

The `CacheConfig` class allows you to customize cache behavior:

```python
from pyeuropepmc.cache import CacheConfig
from pathlib import Path

cache_config = CacheConfig(
    enabled=True,              # Enable/disable caching
    cache_dir=Path("~/.cache/pyeuropepmc"),  # Cache directory
    ttl=3600,                  # Time-to-live in seconds (1 hour)
    size_limit_mb=100,         # Maximum cache size (100 MB)
    eviction_policy="least-recently-used",  # Eviction strategy
)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `False` | Enable/disable caching |
| `cache_dir` | Path | System temp | Directory for cache storage |
| `ttl` | int | 86400 (24h) | Time-to-live for cached entries (seconds) |
| `size_limit_mb` | int | 500 | Maximum cache size (megabytes) |
| `eviction_policy` | str | "least-recently-used" | Cache eviction strategy |

## Client-Specific Features

### SearchClient

SearchClient caches search results and queries:

```python
from pyeuropepmc.search import SearchClient
from pyeuropepmc.cache import CacheConfig

cache_config = CacheConfig(enabled=True, ttl=3600)
client = SearchClient(cache_config=cache_config)

# Both search() and search_post() support caching
results = client.search("malaria", pageSize=100)
results = client.search_post("malaria AND drug resistance")

# Invalidate search-specific cache
client.invalidate_search_cache()
```

### ArticleClient

ArticleClient caches article details, citations, and references:

```python
from pyeuropepmc.article import ArticleClient
from pyeuropepmc.cache import CacheConfig

cache_config = CacheConfig(enabled=True, ttl=7200)  # 2 hours
client = ArticleClient(cache_config=cache_config)

# All article methods support caching
details = client.get_article_details("MED", "25883711")
citations = client.get_citations("MED", "25883711")
references = client.get_references("MED", "25883711")

# Invalidate article-specific cache
count = client.invalidate_article_cache(source="MED", article_id="25883711")
```

### FullTextClient

FullTextClient has **two separate caching systems**:

1. **API Response Cache**: Caches availability checks (controlled by `cache_config`)
2. **File Cache**: Caches downloaded PDF/XML files (controlled by `enable_cache`)

```python
from pyeuropepmc.fulltext import FullTextClient
from pyeuropepmc.cache import CacheConfig

# Configure both caches
cache_config = CacheConfig(enabled=True, ttl=86400)  # 24 hours
client = FullTextClient(
    enable_cache=True,          # File cache for downloads
    cache_config=cache_config   # API response cache
)

# API response cache: availability checks
availability = client.check_fulltext_availability("3312970")

# File cache: downloaded files
pdf_path = client.download_pdf_by_pmcid("3312970", "article.pdf")

# Manage API response cache
client.clear_api_cache()
client.invalidate_fulltext_cache(pmcid="3312970")

# Manage file cache
client.clear_cache(format_type="pdf")  # Clear PDF cache
```

## Cache Management

### Get Cache Statistics

```python
# SearchClient
stats = search_client.get_cache_stats()

# ArticleClient
stats = article_client.get_cache_stats()

# FullTextClient (API response cache)
stats = fulltext_client.get_api_cache_stats()

print(f"Hit rate: {stats.get('hit_rate', 0):.2%}")
print(f"Cache size: {stats.get('size', 0)} bytes")
print(f"Entries: {stats.get('count', 0)}")
```

### Check Cache Health

```python
health = client.get_cache_health()
print(f"Hit rate: {health.get('hit_rate', 0):.2%}")
print(f"Total hits: {health.get('hits', 0)}")
print(f"Total misses: {health.get('misses', 0)}")
```

### Clear Cache

```python
# SearchClient
search_client.clear_cache()
search_client.invalidate_search_cache()

# ArticleClient
article_client.clear_cache()
article_client.invalidate_article_cache(source="MED")

# FullTextClient (API response cache)
fulltext_client.clear_api_cache()
fulltext_client.invalidate_fulltext_cache(pmcid="3312970")
```

## How Caching Works

### Cache Keys

Cache keys are automatically generated from request parameters. The cache system:

- Normalizes parameter order (same query in different parameter order → same cache)
- Normalizes whitespace in queries
- Converts equivalent types (numeric strings → numbers)
- Handles None values intelligently

### Cache Behavior

- **First request**: Cache miss → API call → result cached
- **Subsequent identical requests**: Cache hit → instant response
- **Different parameters**: Separate cache entries
- **Expired entries**: Automatic eviction after TTL

### POST vs GET Searches

POST and GET searches use separate cache keys:

```python
# These are cached separately
result_get = client.search("cancer")
result_post = client.search_post("cancer")
```

## Performance Benefits

With caching enabled:

- **Faster responses**: Cached queries return instantly (no API call)
- **Reduced API load**: Fewer requests to Europe PMC servers
- **Better rate limit compliance**: Repeated queries don't count against limits

### Example Performance Comparison

```python
import time

# Without cache: ~3 seconds for 3 requests
client_no_cache = SearchClient()
start = time.time()
for _ in range(3):
    client_no_cache.search("BRCA1 AND breast cancer", pageSize=25)
print(f"No cache: {time.time() - start:.2f}s")

# With cache: ~1 second for 3 requests (2 from cache)
cache_config = CacheConfig(enabled=True)
client_with_cache = SearchClient(cache_config=cache_config)
start = time.time()
for _ in range(3):
    client_with_cache.search("BRCA1 AND breast cancer", pageSize=25)
print(f"With cache: {time.time() - start:.2f}s")
```

## Best Practices

### 1. Use Context Managers

```python
cache_config = CacheConfig(enabled=True)

with SearchClient(cache_config=cache_config) as client:
    result = client.search("cancer")
    # Cache is automatically closed when exiting
```

### 2. Configure TTL Based on Use Case

```python
# Short-lived cache for frequently updated data
short_ttl = CacheConfig(enabled=True, ttl=300)  # 5 minutes

# Long-lived cache for stable queries
long_ttl = CacheConfig(enabled=True, ttl=86400 * 7)  # 1 week
```

### 3. Monitor Cache Health

```python
health = client.get_cache_health()

if health['status'] == 'warning':
    print("Cache warnings:", health['warnings'])

if health['size_utilization'] > 0.9:
    print("Cache is almost full, consider clearing old entries")
    client.invalidate_search_cache()
```

### 4. Handle Cache Errors Gracefully

Cache errors don't break searches - they're logged and the API request proceeds:

```python
# Even if cache fails, search still works
result = client.search("cancer")
```

## Advanced Usage

### Custom Cache Directory

```python
from pathlib import Path

cache_config = CacheConfig(
    enabled=True,
    cache_dir=Path.home() / ".myapp" / "cache"
)
```

### Per-Query Cache Control

Cache keys are automatically generated based on all search parameters:

```python
# These use different cache entries
result1 = client.search("cancer", pageSize=25, resultType="lite")
result2 = client.search("cancer", pageSize=100, resultType="core")
```

### Pattern-Based Invalidation

```python
# Invalidate all cancer-related searches
client.invalidate_search_cache("search:*cancer*")

# Invalidate all searches
client.invalidate_search_cache("search:*")

# Invalidate all POST searches
client.invalidate_search_cache("search_post:*")
```

## Troubleshooting

### Cache Not Working?

1. **Check if enabled**: `print(client._cache.config.enabled)`
2. **Check dependencies**: Caching requires `diskcache` library
3. **Check permissions**: Ensure write access to cache directory

### Cache Growing Too Large?

```python
# Check cache size
stats = client.get_cache_stats()
print(f"Cache size: {stats['size_mb']} MB / {client._cache.config.size_limit_mb} MB")

# Clear if needed
if stats['size_mb'] > client._cache.config.size_limit_mb * 0.9:
    client.clear_cache()
```

### Low Hit Rate?

```python
stats = client.get_cache_stats()

if stats['hit_rate'] < 0.3:  # Less than 30% hit rate
    print("Consider adjusting cache TTL or query patterns")
```

## Migration Guide

### Existing Code (No Changes Required)

```python
# This still works exactly as before
client = SearchClient()
result = client.search("cancer")
client.close()
```

### Enable Caching (One Line Change)

```python
# Add cache_config parameter
from pyeuropepmc.cache import CacheConfig

client = SearchClient(cache_config=CacheConfig(enabled=True))
result = client.search("cancer")
client.close()
```

## Dependencies

Caching requires the `diskcache` library:

```bash
pip install diskcache
```

If `diskcache` is not installed, caching is automatically disabled with a warning.

## See Also

- [SearchClient API Reference](../api/search-client.md)
- [Cache API Reference](../api/cache.md)
- [Example Script](../../examples/search_client_caching_demo.py)
