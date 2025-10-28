# Caching Examples

**Level**: ⭐⭐ Intermediate
**Examples**: 2 scripts
**Time**: 15-20 minutes

## Overview

Optimize performance by caching API responses. Learn to implement intelligent caching strategies that dramatically speed up repeated searches and API calls while respecting Europe PMC's resources.

## 🐍 Examples

### 01-basic-caching.py
**Introduction to caching**

Learn caching basics:
- Enabling cache for clients
- Cache hit/miss monitoring
- TTL (Time To Live) configuration
- Cache size management
- Performance measurement

**What you'll build**: A cached search client

**Key topics**:
- Cache configuration
- Performance comparison
- Memory management
- Cache invalidation

### 02-all-clients.py
**Multi-client caching**

Advanced caching patterns:
- SearchClient with cache
- ArticleClient with cache
- Shared cache strategies
- Cache coordination
- Persistence options

**What you'll build**: Complete cached application

**Key topics**:
- Multiple client caching
- Shared cache pools
- Cache strategies
- Performance optimization

## 🚀 Quick Start

### Basic Caching
```python
from pyeuropepmc.search import SearchClient

# Enable caching
with SearchClient(enable_cache=True, cache_ttl=3600) as client:
    # First call: hits API
    results1 = client.search("covid-19")

    # Second call: served from cache (instant!)
    results2 = client.search("covid-19")
```

### Performance Comparison
```python
import time

# Without cache
start = time.time()
with SearchClient() as client:
    for i in range(10):
        client.search("machine learning")
no_cache_time = time.time() - start

# With cache
start = time.time()
with SearchClient(enable_cache=True) as client:
    for i in range(10):
        client.search("machine learning")
cache_time = time.time() - start

print(f"Without cache: {no_cache_time:.2f}s")
print(f"With cache: {cache_time:.2f}s")
print(f"Speedup: {no_cache_time/cache_time:.1f}x")
```

## 🎯 Key Features

### 1. Response Caching
Cache API responses:
- Search results
- Article details
- Citations and references
- Supplementary data

### 2. Configurable TTL
Control cache lifetime:
- Short TTL for frequently updated data
- Long TTL for stable data
- Infinite cache for historical data
- Per-query TTL settings

### 3. Memory Management
Efficient cache usage:
- LRU (Least Recently Used) eviction
- Size limits
- Memory monitoring
- Cache statistics

### 4. Performance Monitoring
Track cache effectiveness:
- Hit rate percentage
- Miss rate tracking
- Response time comparison
- Memory usage

### 5. Flexible Strategies
Different caching approaches:
- In-memory (default)
- File-based persistence
- Distributed caching
- Selective caching

## 💡 Common Use Cases

### Development Workflow
```python
# Fast iteration during development
with SearchClient(enable_cache=True, cache_ttl=86400) as client:
    # Run multiple times without hitting API
    results = client.search("my query")
    # ... develop your code ...
    # Same query uses cache
```

### Batch Processing
```python
# Process same articles multiple times
from pyeuropepmc.article import ArticleClient

client = ArticleClient(enable_cache=True)

article_ids = ["12345", "67890", "11111"]

# First pass
for article_id in article_ids:
    details = client.get_article_details("MED", article_id)
    # Process...

# Second pass (instant from cache)
for article_id in article_ids:
    details = client.get_article_details("MED", article_id)
    # Additional processing...
```

### Interactive Analysis
```python
# Jupyter notebook analysis
client = SearchClient(enable_cache=True, cache_ttl=7200)

# Initial exploration
results = client.search("gene therapy")
# ... analyze ...

# Refine analysis (uses cache)
results = client.search("gene therapy")
# ... more analysis ...
```

### Testing
```python
# Fast test execution
import pytest

@pytest.fixture
def cached_client():
    return SearchClient(enable_cache=True, cache_ttl=3600)

def test_search(cached_client):
    # Tests run quickly with cached responses
    results = cached_client.search("test query")
    assert results['hitCount'] > 0
```

## 📊 Cache Configuration

### TTL Settings

| TTL | Use Case | Example |
|-----|----------|---------|
| 60 seconds | Frequently changing data | Real-time monitoring |
| 1 hour (3600) | Development/testing | Default |
| 1 day (86400) | Stable historical data | Archive processing |
| None | Never expire | Static reference data |

### Cache Size Limits
```python
# Configure cache size
client = SearchClient(
    enable_cache=True,
    cache_maxsize=1000,  # Max 1000 entries
    cache_ttl=3600
)
```

## 🔍 Advanced Patterns

### Custom Cache Key
```python
# Cache with custom parameters
def search_with_cache(query, year_from=None, year_to=None):
    cache_key = f"{query}_{year_from}_{year_to}"
    # Implement custom caching logic
    pass
```

### Selective Caching
```python
# Cache only specific queries
client = SearchClient()

CACHE_QUERIES = ["common query 1", "common query 2"]

def smart_search(query):
    if query in CACHE_QUERIES:
        # Use cached client
        with SearchClient(enable_cache=True) as cached_client:
            return cached_client.search(query)
    else:
        # Direct API call
        return client.search(query)
```

### Cache Warming
```python
# Pre-populate cache
common_queries = ["covid-19", "machine learning", "CRISPR"]

with SearchClient(enable_cache=True) as client:
    # Warm up the cache
    for query in common_queries:
        client.search(query)

    # Now all common queries are cached
```

### Cache Invalidation
```python
# Clear cache when needed
from pyeuropepmc.search import SearchClient

client = SearchClient(enable_cache=True)

# Use cached data
results = client.search("query")

# Clear cache if data is stale
client.clear_cache()  # If method exists

# Or create new client
client = SearchClient(enable_cache=True)
```

### Multi-Level Caching
```python
# Combine in-memory and disk cache
class TwoLevelCache:
    def __init__(self):
        self.memory_cache = {}
        self.disk_cache = {}

    def get(self, key):
        # Check memory first
        if key in self.memory_cache:
            return self.memory_cache[key]
        # Then disk
        if key in self.disk_cache:
            value = self.disk_cache[key]
            self.memory_cache[key] = value
            return value
        return None
```

## 📈 Performance Gains

Typical speedup with caching:

| Operation | No Cache | With Cache | Speedup |
|-----------|----------|------------|---------|
| Single search | 500ms | 1ms | 500x |
| 10 identical searches | 5s | 0.01s | 500x |
| Batch article fetch | 10s | 0.1s | 100x |
| Development iteration | Minutes | Seconds | 10-100x |

## 🆘 Troubleshooting

**Cache not working?**
- Verify `enable_cache=True` is set
- Check cache is not bypassed
- Ensure identical queries (including parameters)

**Memory usage too high?**
- Reduce `cache_maxsize`
- Decrease TTL
- Implement cache eviction
- Monitor memory usage

**Stale data in cache?**
- Reduce TTL
- Clear cache manually
- Use time-based invalidation

**Cache misses expected hits?**
- Check query parameters match exactly
- Verify cache key generation
- Monitor cache statistics

## 💾 Cache Persistence

### Save Cache to Disk
```python
import pickle

# Save cache
with open('search_cache.pkl', 'wb') as f:
    pickle.dump(client.cache, f)

# Load cache
with open('search_cache.pkl', 'rb') as f:
    cache = pickle.load(f)
    client.cache = cache
```

### Cache Statistics
```python
# Monitor cache effectiveness
def print_cache_stats(client):
    hits = client.cache_hits
    misses = client.cache_misses
    total = hits + misses

    if total > 0:
        hit_rate = (hits / total) * 100
        print(f"Cache hit rate: {hit_rate:.1f}%")
        print(f"Hits: {hits}, Misses: {misses}")
```

## 🔗 Resources

- [Caching Best Practices](../../docs/advanced/caching.md)
- [Performance Optimization Guide](../../docs/advanced/performance.md)
- [Client Configuration](../../docs/api/clients.md)

## 🚀 Best Practices

1. **Enable in development**: Fast iteration
2. **Tune TTL**: Balance freshness vs performance
3. **Monitor hit rate**: Aim for >80% hits
4. **Clear periodically**: Prevent stale data
5. **Consider disk cache**: For large datasets
6. **Test without cache**: Ensure correctness

## 🎓 Learning Path

1. **Start**: `01-basic-caching.py` - Learn fundamentals
2. **Advance**: `02-all-clients.py` - Multi-client patterns
3. **Optimize**: Tune for your use case
4. **Monitor**: Track performance gains

## 🚀 Next Steps

- **Measure impact**: Compare with/without cache
- **Tune settings**: Optimize TTL and size
- **Persist cache**: Save to disk for reuse
- **Integrate**: Add to production workflows
