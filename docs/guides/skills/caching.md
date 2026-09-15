# Caching skill

Cache the API responses of a client so that repeated calls do not send new requests. The full guide is [Caching](../../features/caching/README.md).

```python
from pyeuropepmc import CacheConfig, SearchClient

cache_config = CacheConfig(enabled=True, ttl=3600)  # entries expire after one hour

with SearchClient(cache_config=cache_config) as client:
    client.search("cancer", pageSize=10)
    client.search("cancer", pageSize=10)  # answered from the cache
    stats = client.get_cache_stats()
    print(stats["hits"], stats["misses"])  # 1 1
```

Key tips:
- Caching is off unless you pass `cache_config`. `ArticleClient`, `AnnotationsClient` and `FullTextClient` take the same argument.
- The cache is kept in memory, belongs to one client instance and is emptied when the client closes.
- `ttl` is in seconds (default 86400). There is no never-expire value, and `ttl=0` expires entries immediately.
- `CacheConfig(enable_l2=True)` adds a disk layer in `cache_dir`, but it does not yet keep entries for a later client or run.
- `client.invalidate_search_cache("*:search:*")` removes cached searches (the default pattern matches nothing); `client.clear_cache()` removes everything.
- `FullTextClient` also keeps downloaded files in a separate file cache (`enable_cache=True` by default).
