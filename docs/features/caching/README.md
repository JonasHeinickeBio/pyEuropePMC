# Caching Features

PyEuropePMC provides **smart automatic caching** to improve performance and reduce API calls.

## Overview

- 🚀 **Automatic caching** - Enabled by default for SearchClient and FullTextClient
- 💾 **Disk-based persistence** - Cache survives program restarts
- ⏰ **TTL support** - Configurable time-to-live for cached data
- 🔄 **Cache invalidation** - Manual and automatic cache clearing
- 📊 **Memory efficient** - Optimized storage for large datasets
- ⚙️ **Configurable** - Customize cache behavior per client

## Quick Start

```python
from pyeuropepmc import SearchClient

# Caching is enabled by default
with SearchClient() as client:
    # First call - hits API, caches response
    results1 = client.search("cancer therapy")

    # Second call - retrieved from cache (instant)
    results2 = client.search("cancer therapy")

    # Different query - hits API, caches new response
    results3 = client.search("machine learning")
```

## How Caching Works

### Automatic Caching

All API requests are automatically cached based on:
- Request URL
- Query parameters
- Request method

```python
from pyeuropepmc import SearchClient, FullTextClient

# SearchClient caching
with SearchClient() as search_client:
    # Cached by query + parameters
    r1 = search_client.search("cancer", pageSize=50)
    r2 = search_client.search("cancer", pageSize=50)  # From cache
    r3 = search_client.search("cancer", pageSize=100)  # Different params - new API call

# FullTextClient caching
with FullTextClient() as fulltext_client:
    # Cached by PMC ID
    xml1 = fulltext_client.get_fulltext_xml("PMC3258128")
    xml2 = fulltext_client.get_fulltext_xml("PMC3258128")  # From cache
```

### Cache Location

Cache files are stored in a platform-specific cache directory:

```python
from pyeuropepmc import SearchClient

client = SearchClient()
print(f"Cache directory: {client.cache_dir}")

# Linux/Unix: ~/.cache/pyeuropepmc/
# macOS: ~/Library/Caches/pyeuropepmc/
# Windows: %LOCALAPPDATA%\pyeuropepmc\Cache\
```

## Configuration

### Disable Caching

```python
from pyeuropepmc import SearchClient

# Disable caching for this client
with SearchClient(use_cache=False) as client:
    results = client.search("cancer")  # Always hits API
```

### Custom Cache Directory

```python
from pyeuropepmc import SearchClient

# Use custom cache location
with SearchClient(cache_dir="./my_cache") as client:
    results = client.search("cancer")
```

### Cache TTL (Time-to-Live)

Configure how long cached data remains valid:

```python
from pyeuropepmc import SearchClient

# Cache valid for 1 hour (3600 seconds)
with SearchClient(cache_ttl=3600) as client:
    results = client.search("cancer")
    # Subsequent calls within 1 hour use cache
    # After 1 hour, fresh data fetched from API

# Cache valid for 1 day (86400 seconds)
with SearchClient(cache_ttl=86400) as client:
    results = client.search("cancer")

# No expiration (cache never expires)
with SearchClient(cache_ttl=None) as client:
    results = client.search("cancer")
```

## Cache Management

### Clear All Cache

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    # Clear entire cache
    client.clear_cache()

    # Next call will hit API
    results = client.search("cancer")
```

### Clear Specific Cache Entry

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    # Make cached request
    results = client.search("cancer")

    # Clear this specific query from cache
    client.clear_cache_entry("cancer")

    # Next call will hit API
    results = client.search("cancer")
```

### Cache Info

```python
from pyeuropepmc import SearchClient
import os

with SearchClient() as client:
    # Get cache directory
    cache_dir = client.cache_dir

    # List cached files
    if os.path.exists(cache_dir):
        cache_files = os.listdir(cache_dir)
        print(f"Cached items: {len(cache_files)}")

        # Get cache size
        total_size = sum(
            os.path.getsize(os.path.join(cache_dir, f))
            for f in cache_files
        )
        print(f"Cache size: {total_size / 1024 / 1024:.2f} MB")
```

## Use Cases

### Use Case 1: Development & Testing

During development, caching speeds up testing:

```python
from pyeuropepmc import SearchClient

# Enable long-term caching during development
with SearchClient(cache_ttl=None) as client:
    # First run: API call
    results = client.search("cancer therapy", pageSize=100)

    # Subsequent runs: instant (from cache)
    # Great for testing data processing without hitting API
    results = client.search("cancer therapy", pageSize=100)
```

### Use Case 2: Repeated Analysis

When analyzing the same dataset multiple times:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    # Run analysis multiple times on same query
    query = "machine learning AND genomics"

    # First analysis
    results = client.search(query, pageSize=200)
    analysis_1 = perform_analysis(results)

    # Modify analysis logic
    results = client.search(query, pageSize=200)  # From cache
    analysis_2 = perform_improved_analysis(results)

    # Compare results without re-fetching data
```

### Use Case 3: Incremental Processing

Process large datasets incrementally:

```python
from pyeuropepmc import SearchClient

with SearchClient(cache_ttl=86400) as client:  # 24 hour cache
    query = "cancer research"

    # Day 1: Process first 500 results
    results = client.search(query, pageSize=100)  # Cached
    process_batch_1(results)

    # Day 2: Continue processing (uses cache if within 24h)
    results = client.search(query, pageSize=100)  # From cache
    process_batch_2(results)
```

### Use Case 4: Collaborative Work

Share cache between team members:

```python
from pyeuropepmc import SearchClient

# Use shared network cache location
shared_cache = "/shared/project/cache"

with SearchClient(cache_dir=shared_cache) as client:
    # Team member A fetches data
    results = client.search("genomics", pageSize=200)

    # Team member B uses cached data (if on same network)
    # No additional API calls needed
```

### Use Case 5: Production with Fresh Data

Ensure production systems get fresh data:

```python
from pyeuropepmc import SearchClient

# Short TTL for production
with SearchClient(cache_ttl=300) as client:  # 5 minute cache
    # Recent data, but still benefits from caching
    # during high-traffic periods
    results = client.search("latest research")
```

## Advanced Caching Patterns

### Pattern 1: Selective Caching

Cache search results but not full-text downloads:

```python
from pyeuropepmc import SearchClient, FullTextClient

# Cache search results
with SearchClient(use_cache=True, cache_ttl=86400) as search_client:
    results = search_client.search("cancer")

# Don't cache downloads (large files)
with FullTextClient(use_cache=False) as fulltext_client:
    xml = fulltext_client.get_fulltext_xml("PMC3258128")
```

### Pattern 2: Conditional Cache Clearing

Clear cache based on conditions:

```python
from pyeuropepmc import SearchClient
from datetime import datetime

with SearchClient() as client:
    # Clear cache on Monday mornings (fresh weekly data)
    if datetime.now().weekday() == 0 and datetime.now().hour < 10:
        client.clear_cache()

    results = client.search("weekly research")
```

### Pattern 3: Fallback to Cache

Try API, fall back to cache on error:

```python
from pyeuropepmc import SearchClient
from pyeuropepmc.exceptions import EuropePMCException

with SearchClient(cache_ttl=None) as client:
    try:
        # Try fresh data
        client.clear_cache_entry("cancer")
        results = client.search("cancer")
    except EuropePMCException:
        # Fall back to cached data if API fails
        print("API failed, using cached data")
        results = client.search("cancer")
```

### Pattern 4: Pre-warming Cache

Pre-populate cache for expected queries:

```python
from pyeuropepmc import SearchClient

# Pre-warm cache with expected queries
common_queries = [
    "cancer therapy",
    "machine learning genomics",
    "CRISPR gene editing",
    "immunotherapy"
]

with SearchClient(cache_ttl=86400) as client:
    print("Pre-warming cache...")
    for query in common_queries:
        client.search(query, pageSize=100)
    print("Cache ready!")
```

### Pattern 5: Cache Migration

Migrate cache to new location:

```python
from pyeuropepmc import SearchClient
import shutil
import os

old_cache = "./old_cache"
new_cache = "./new_cache"

# Copy cache files
if os.path.exists(old_cache):
    os.makedirs(new_cache, exist_ok=True)
    for file in os.listdir(old_cache):
        shutil.copy2(
            os.path.join(old_cache, file),
            os.path.join(new_cache, file)
        )

# Use new cache location
with SearchClient(cache_dir=new_cache) as client:
    results = client.search("cancer")  # Uses migrated cache
```

## Cache Performance Metrics

### Measure Cache Hit Rate

```python
from pyeuropepmc import SearchClient

queries = ["cancer", "therapy", "genomics", "cancer"]  # "cancer" appears twice

cache_hits = 0
api_calls = 0

with SearchClient() as client:
    client.clear_cache()  # Start fresh

    for query in queries:
        # Track if from cache (simplified example)
        results = client.search(query)
        # In real implementation, you'd track actual API calls

hit_rate = cache_hits / len(queries) * 100
print(f"Cache hit rate: {hit_rate:.1f}%")
```

### Measure Performance Improvement

```python
import time
from pyeuropepmc import SearchClient

query = "cancer therapy"

# Without cache
with SearchClient(use_cache=False) as client:
    start = time.time()
    results = client.search(query)
    no_cache_time = time.time() - start

# With cache (second call)
with SearchClient(use_cache=True) as client:
    client.search(query)  # Prime cache
    start = time.time()
    results = client.search(query)
    cache_time = time.time() - start

speedup = no_cache_time / cache_time
print(f"Speedup: {speedup:.1f}x faster with cache")
```

## Best Practices

### 1. Use Caching in Development

```python
# ✅ Keep cache during development
with SearchClient(cache_ttl=None) as client:
    results = client.search("test query")
```

### 2. Set Appropriate TTL for Production

```python
# ✅ Short TTL for real-time data
with SearchClient(cache_ttl=300) as client:  # 5 minutes
    results = client.search("latest research")

# ✅ Longer TTL for historical data
with SearchClient(cache_ttl=86400) as client:  # 24 hours
    results = client.search("historical data")
```

### 3. Clear Cache When Schema Changes

```python
# ✅ Clear cache after library updates
from pyeuropepmc import SearchClient

with SearchClient() as client:
    # After updating pyeuropepmc
    client.clear_cache()
```

### 4. Monitor Cache Size

```python
# ✅ Periodically check cache size
import os
from pyeuropepmc import SearchClient

with SearchClient() as client:
    cache_dir = client.cache_dir
    size_mb = sum(
        os.path.getsize(os.path.join(cache_dir, f))
        for f in os.listdir(cache_dir)
    ) / 1024 / 1024

    if size_mb > 1000:  # If cache > 1GB
        client.clear_cache()
```

### 5. Use Separate Caches for Different Projects

```python
# ✅ Project-specific cache directories
with SearchClient(cache_dir="./project_a/cache") as client:
    results = client.search("project A query")

with SearchClient(cache_dir="./project_b/cache") as client:
    results = client.search("project B query")
```

## Troubleshooting

### Cache Not Working

```python
# Check if caching is enabled
with SearchClient() as client:
    print(f"Cache enabled: {client.use_cache}")
    print(f"Cache directory: {client.cache_dir}")
    print(f"Cache TTL: {client.cache_ttl}")
```

### Clear Stale Cache

```python
# Clear expired cache entries
with SearchClient() as client:
    client.clear_cache()  # Removes all cache
```

### Debug Cache Behavior

```python
import logging
logging.basicConfig(level=logging.DEBUG)

with SearchClient() as client:
    # Will log cache hits/misses
    results = client.search("cancer")
```

## See Also

- **[API Reference: SearchClient](../../api/search-client.md#caching)** - Caching configuration
- **[API Reference: FullTextClient](../../api/fulltext-client.md#caching)** - Full-text caching
- **[Advanced: Performance](../../advanced/performance.md)** - Performance optimization
- **[Examples: Caching](../../examples/basic-examples.md#caching)** - Code examples

---

**Next Steps:**
- Learn about [Search Features](../search/) that benefit from caching
- Explore [Advanced Configuration](../../advanced/configuration.md) for fine-tuning
- Read [Performance Guide](../../advanced/performance.md) for optimization tips
