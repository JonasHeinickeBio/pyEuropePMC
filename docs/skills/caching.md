# Caching Skill

Enable caching on clients to reduce API calls and improve performance.

```python
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc import SearchClient

# Configure cache
cache_config = CacheConfig(enabled=True, ttl=3600)  # 1 hour TTL

with SearchClient(cache_config=cache_config) as client:
    results = client.search("cancer", pageSize=10)
    # Second call with same params returns cached result
```

Caching layers:
- **Disk cache**: Store results on disk (default)
- **Memory cache**: Use `diskcache` for fast lookups
- **HTTP cache**: Cache responses with `requests-cache`

Key tips:
- TTL in seconds; use `0` for no expiry
- Normalize query params with `normalize_query_params()`
- Cache applies per-client; create separate clients for different configs
