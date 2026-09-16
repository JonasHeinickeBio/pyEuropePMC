# Caching internals

This page is the reference for the cache layer behind the clients: `CacheConfig`, `CacheBackend`, how cache keys are built, the disk layer and its schema helpers, the `cached` decorator and the standalone `ArtifactStore`. To turn caching on in a client, see [Caching](../features/caching/README.md).

## Imports

```python
from pyeuropepmc import CacheBackend, CacheConfig, CacheDataType, CacheLayer, normalize_query_params
from pyeuropepmc import ArtifactMetadata, ArtifactStore  # also importable from pyeuropepmc.storage
from pyeuropepmc.cache.cache import CACHETOOLS_AVAILABLE, DISKCACHE_AVAILABLE, cached
```

`src/pyeuropepmc/cache/` has no `__init__.py`, so `from pyeuropepmc.cache import CacheConfig` raises `ImportError`. `cachetools` and `diskcache` are core dependencies, so both availability flags are normally `True`.

## Architecture

A `CacheBackend` has up to two layers:

| Layer | Implementation | Bound | Expiry |
|---|---|---|---|
| L1 | `cachetools.TTLCache` in the memory of one `CacheBackend` | Entry count, `min(size_limit_mb * 1024, 10000)` | `CacheConfig.ttl`, the same for every entry |
| L2 (`enable_l2=True`) | `diskcache.Cache` in `cache_dir` | `l2_size_limit_mb`, least-recently-used eviction | Per entry: `expire`, otherwise the `ttl_by_type` value of `data_type`, otherwise `ttl` |

- `get()` checks L1, then L2, and copies an L2 hit into L1.
- `set()` writes to both layers unless `layer=` names one.
- Every client creates its own `CacheBackend` from the `CacheConfig` you pass, so clients never share a backend.
- If a layer cannot be created, the backend logs a warning, sets `enabled` or `enable_l2` to `False` on the `CacheConfig` object you passed, and continues without that layer.

## CacheConfig reference

`CacheConfig(enabled=True, cache_dir=None, ttl=86400, size_limit_mb=500, eviction_policy="least-recently-used", enable_l2=False, l2_size_limit_mb=5000, ttl_by_type=None, namespace_version=1)`

| Parameter | Type | Default | Effect |
|---|---|---|---|
| `enabled` | `bool` | `True` | With `False` (also forced if `cachetools` is missing), `get()` returns the default, `set()` returns `False` and the other methods do nothing. |
| `cache_dir` | `Path`, `str` or `None` | `None` | L2 directory. `None` means `Path(tempfile.gettempdir()) / "pyeuropepmc_cache"`; a `str` is converted to `Path`. Unused without L2. |
| `ttl` | `int` | `86400` | Lifetime of every L1 entry and the default L2 expiry, in seconds. A negative value raises `ConfigurationError`, `None` raises `TypeError`, and `0` expires entries immediately. |
| `size_limit_mb` | `int` | `500` | L1 capacity as an entry count, `min(size_limit_mb * 1024, 10000)`: 1 gives 1024 entries, 10 or more gives 10000. Values below 1 raise `ConfigurationError`. |
| `eviction_policy` | `str` | `"least-recently-used"` | Stored but not used; L2 always uses least-recently-used eviction. |
| `enable_l2` | `bool` | `False` | Create the L2 disk layer. Forced to `False` if `diskcache` is missing or the disk cache cannot be opened. |
| `l2_size_limit_mb` | `int` | `5000` | L2 size limit, passed to diskcache in bytes. |
| `ttl_by_type` | `dict[CacheDataType, int]` or `None` | `None` | Merged over `CacheConfig.DEFAULT_TTLS`. Used by `set(..., data_type=...)` for the L2 expiry only. |
| `namespace_version` | `int` | `1` | Version written into hashed keys (`v1`). Values below 1 raise `ConfigurationError`. |

`config.get_ttl(data_type=None) -> int` returns the `ttl_by_type` value for `data_type`, or `ttl` when no data type is given.

`CacheDataType` members and `CacheConfig.DEFAULT_TTLS`:

| Member | Value | Default TTL |
|---|---|---|
| `CacheDataType.SEARCH` | `"search"` | 300 s |
| `CacheDataType.RECORD` | `"record"` | 86400 s |
| `CacheDataType.FULLTEXT` | `"fulltext"` | 2592000 s (30 days) |
| `CacheDataType.ERROR` | `"error"` | 30 s |

No client passes a `data_type`, so these values only matter for your own `set()` calls with `enable_l2=True`. `CacheLayer.L1` (`"l1"`) and `CacheLayer.L2` (`"l2"`) select a layer in `get()`, `set()`, `delete()`, `clear()` and `invalidate_pattern()`.

```python
from pathlib import Path

from pyeuropepmc import CacheBackend, CacheConfig, CacheDataType, CacheLayer

config = CacheConfig(
    enabled=True,
    enable_l2=True,
    cache_dir=Path("cache-l2"),
    ttl=3600,
    ttl_by_type={CacheDataType.SEARCH: 600},
)
cache = CacheBackend(config)

cache.set("record:PMC3312970", {"title": "Example"}, data_type=CacheDataType.RECORD)
cache.set("search:malaria", ["PMC1", "PMC2"], data_type=CacheDataType.SEARCH)  # 600 s on disk, 3600 s in memory

print(cache.get("record:PMC3312970"))  # {'title': 'Example'}
print(cache.get("search:malaria", layer=CacheLayer.L2))  # ['PMC1', 'PMC2']
print(cache.get("missing", default="n/a"))  # n/a
cache.close()
```

## CacheBackend reference

`CacheBackend(config: CacheConfig)`. The attributes `config`, `l1_cache` and `l2_cache` expose the configuration and the two stores; `cache` is an alias of `l1_cache`.

| Method | Returns | Notes |
|---|---|---|
| `get(key, default=None, layer=None)` | Cached value or `default` | L1 first, then L2; an L2 hit is copied to L1. |
| `set(key, value, expire=None, tag=None, data_type=None, layer=None)` | `bool` | `True` if at least one layer stored the value. `expire` and `data_type` only set the L2 expiry, and `expire=0` counts as not given. L2 values must be picklable. |
| `delete(key, layer=None)` | `bool` | `True` if the key was removed from at least one layer. |
| `clear(layer=None)` | `bool` | Removes all entries and all tag records. |
| `evict(tag)` | `int` | Deletes the keys this backend stored with `tag`. Tags are kept in memory and forgotten on `close()`. |
| `invalidate_pattern(pattern, layer=None)` | `int` | Deletes keys that match an `fnmatch` pattern (`*`, `?`, `[seq]`). |
| `warm_cache(entries, ttl=None, tag=None)` | `int` | Calls `set(key, value, expire=ttl, tag=tag)` for each item of a dict and returns how many succeeded. |
| `get_keys(pattern=None, limit=1000)` | `list[str]` | L1 keys only. |
| `normalize_query_key(query, prefix="search", **params)` | `str` | See [Cache keys](#cache-keys). |
| `get_stats()` | `dict` | See [Statistics and health](#statistics-and-health). |
| `get_health()` | `dict` | See [Statistics and health](#statistics-and-health). |
| `reset_stats()` | `None` | Sets all counters to zero. |
| `invalidate_older_than(seconds)` | `int` | Always returns `0`; expiry is left to the TTLs. |
| `compact()` | `bool` | Walks the L1 keys so that expired entries are dropped. Does not touch L2. |
| `close()` | `None` | Empties L1, closes L2 and forgets tags. |

```python
from pyeuropepmc import CacheBackend, CacheConfig

cache = CacheBackend(CacheConfig(enabled=True))

cache.set("search:cancer", {"hitCount": 10}, tag="oncology")
cache.set("record:PMC3312970", {"title": "Example"}, tag="oncology")
cache.set("search:diabetes", {"hitCount": 4}, tag="endocrinology")

print(cache.evict("oncology"))  # 2
print(cache.invalidate_pattern("search:*"))  # 1
print(cache.warm_cache({"search:zika": {"hitCount": 3}}, tag="preloaded"))  # 1
print(cache.get_keys())  # ['search:zika']
cache.close()
```

## Cache keys

`set()` stores the key you give it unchanged. Hashed keys come from `normalize_query_key()` and from the clients:

```python
from pyeuropepmc import CacheBackend, CacheConfig

cache = CacheBackend(CacheConfig(enabled=True))

key = cache.normalize_query_key("covid-19 vaccine", pageSize=25)
print(key)  # search:v1:search:63bbc7e22d791885
print(cache.normalize_query_key("  covid-19   vaccine ", pageSize=25) == key)  # True: whitespace is collapsed
print(cache.normalize_query_key("COVID-19 vaccine", pageSize=25) == key)  # False: case is kept
print(cache.normalize_query_key("covid-19 vaccine", pageSize="25") == key)  # False: "25" is not 25
```

A hashed key has the form `{type}:v{namespace_version}:{prefix}:{hash}`. `type` is `search` for `normalize_query_key()` and `general` for the keys that clients build. `hash` is the first 16 hexadecimal characters of the SHA-256 of the parameters, which are first normalized (`None`, empty strings and empty dicts dropped, whitespace in strings collapsed, booleans turned into `"true"` or `"false"`, lists sorted into tuples, dicts normalized recursively), then sorted and JSON-encoded.

Keys used by the clients:

| Client call | Key | Tag |
|---|---|---|
| `SearchClient.search()` | `general:v{n}:search:{hash}` | `search` |
| `SearchClient.search_post()` | `general:v{n}:search_post:{hash}` | `search_post` |
| `AnnotationsClient.get_annotations_by_article_ids()`, `get_annotations_by_entity()`, `get_annotations_by_provider()` | `general:v{n}:annotations_by_ids:{hash}`, `general:v{n}:annotations_by_entity:{hash}`, `general:v{n}:annotations_by_provider:{hash}` | `annotations` |
| `ArticleClient.get_article_details()` | `article_details:{source}:{article_id}:{result_type}:{format}` | `article_details` |
| `ArticleClient.get_citations()`, `get_references()` | `citations:{source}:{article_id}:{page}:{page_size}:{format}`, `references:{source}:{article_id}:{page}:{page_size}:{format}` | `citations`, `references` |
| `FullTextClient.check_fulltext_availability()` | `fulltext_availability:{digits}` (the PMC ID without its prefix) | `fulltext_availability` |
| Enrichment clients | `{url}:{params}` | none |
| `PubMedClient`, `ArxivClient`, `ClinicalTrialsClient` | `{url}:{params}:{response_format}` | none |

Patterns used by the client invalidation methods:

| Method | Pattern | Matches the client's keys |
|---|---|---|
| `SearchClient.invalidate_search_cache(pattern="search:*")` | The pattern you pass | Not with the default; use `"*:search:*"` or `"*:search_post:*"` |
| `AnnotationsClient.invalidate_annotations_cache(pattern="annotations:*")` | The pattern you pass | Not with the default; use `"*:annotations_by_*"` |
| `ArticleClient.invalidate_article_cache(source=None, article_id=None)` | `*:{source}:{article_id}:*`, `*:{source}:*`, or `*` with no arguments | Yes |
| `FullTextClient.invalidate_fulltext_cache(pmcid=None)` | `*:{digits}*`, or `*` with no argument | Yes; also longer IDs that start with the same digits |

`namespace_version` only changes hashed keys. A backend with `namespace_version=2` computes `search:v2:search:63bbc7e22d791885` for the query above, so it no longer finds the `v1` entry; remove old entries with `invalidate_pattern("*:v1:*")`. Keys stored unchanged through `set()`, such as `"search:cancer"`, contain no version and are not affected.

`normalize_query_params()` is a standalone helper with different rules: it strips surrounding whitespace without collapsing inner whitespace, converts numeric strings to `int` or `float`, keeps booleans and case, sorts lists and drops `None` and empty strings. The clients do not use it to build keys.

```python
from pyeuropepmc import normalize_query_params

params = {"query": "  COVID-19  ", "pageSize": "25", "sort": None, "email": "", "ids": ["b", "a"], "year": "2020"}
print(normalize_query_params(params))
# {'query': 'COVID-19', 'pageSize': 25, 'ids': ['a', 'b'], 'year': 2020}
```

## Statistics and health

`get_stats()` on an enabled backend returns:

| Key | Content |
|---|---|
| `hits`, `misses`, `sets`, `deletes`, `errors` | Counters summed over both layers. |
| `hit_rate` | `hits / (hits + misses)`, a fraction rounded to 4 decimal places. |
| `entry_count`, `maxsize`, `currsize` | L1 entries and capacity. |
| `size_bytes`, `size_mb` | L1 size estimated as 1 KB per entry. |
| `namespace_version` | From `CacheConfig`. |
| `layers` | `l1` with `hits`, `misses`, `sets`, `deletes`, `errors`, `entry_count`, `maxsize`, `currsize`, `hit_rate`, `size_bytes`, `size_mb`; and with L2, `l2` with `hits`, `misses`, `sets`, `deletes`, `errors`, `entry_count`, `hit_rate`, `size_bytes` (measured on disk), `size_mb`, `size_limit_mb`. |
| `overall` | `hits`, `misses`, `sets`, `deletes`, `errors` and `hit_rate` over both layers. |

A disabled backend returns only `{"namespace_version": ..., "layers": {}, "overall": {}}`. With L2 enabled, a lookup that misses L1 is counted in both layers (an L1 miss plus an L2 hit or miss), so `hits + misses` can be larger than the number of lookups.

`get_health()` returns `enabled`, `status`, `available`, `hit_rate`, `size_utilization`, `error_rate` and `warnings`. `status` is `"disabled"` when caching is off, `"unavailable"` when L1 was not created and `"error"` when the statistics could not be computed. Otherwise the first matching rule applies:

| Condition | `status` |
|---|---|
| `size_utilization > 0.95` | `"critical"` |
| `size_utilization > 0.80` | `"warning"` |
| `error_rate > 0.05` | `"warning"` |
| `hit_rate < 0.5` with more than 100 operations | `"warning"` |
| none of the above | `"healthy"` |

`size_utilization` is `size_mb / size_limit_mb`, based on the 1 KB estimate; with the default `size_limit_mb=500`, a full L1 layer reports about 0.02. `error_rate` is `errors` divided by the sum of all counters.

## Disk layer (L2)

When `enable_l2=True`, the backend creates `cache_dir`, opens `diskcache.Cache(str(cache_dir), size_limit=l2_size_limit_mb * 1024 * 1024, eviction_policy="least-recently-used")` and writes and deletes a test key. If any step fails, it logs a warning and continues with L1 only.

> **Known limitation.** Before it opens the disk cache, `_initialize_l2_cache()` deletes `cache.db` and any `cache.db-wal`, `cache.db-shm` and `cache.db-journal` files in `cache_dir` (`src/pyeuropepmc/cache/cache.py`, lines 447-460; the code comment says this is meant for test environments). With the current code:
>
> - a value written by one process is `None` in the next process that opens the same directory;
> - two backends or clients that are open on the same directory at the same time do not see each other's entries;
> - values that diskcache stored as separate `.val` files (large values) remain in `cache_dir` after the database is deleted.
>
> Treat L2 as storage for the lifetime of one backend, and give each backend its own `cache_dir`.

```python
from pathlib import Path

from pyeuropepmc import CacheBackend, CacheConfig
from pyeuropepmc.cache.cache import DISKCACHE_AVAILABLE

config = CacheConfig(enabled=True, enable_l2=True, cache_dir=Path("cache-check"))
backend = CacheBackend(config)
print(DISKCACHE_AVAILABLE, config.enable_l2, backend.l2_cache is not None)  # True True True
backend.close()
```

If the second or third value is `False`, the log contains the reason (`L2 cache test failed` or `Failed to initialize L2 cache`).

### Schema helpers

Databases created by older diskcache versions can lack the `size` column that diskcache 5.6.3 and later expects, which fails with `sqlite3.OperationalError: table Cache has no column named size`. The module `pyeuropepmc.cache.cache` has two private helpers for this case:

| Function | Behaviour |
|---|---|
| `_validate_diskcache_schema(cache_dir: Path) -> bool` | Returns `True` if `cache_dir / "cache.db"` does not exist; otherwise calls `_check_and_migrate_schema()`. Returns `False` if SQLite cannot open the file. |
| `_check_and_migrate_schema(db_path: Path) -> bool` | Reads `PRAGMA table_info(Cache)`. If `size` is missing, runs `ALTER TABLE Cache ADD COLUMN size INTEGER DEFAULT 0` and returns `True`. If SQLite raises an error (for example on a corrupt file), deletes `cache.db` and raises `ConfigurationError` with code `CONFIG001`. |

`CacheBackend` does not call these helpers; it deletes `cache.db` instead, as described above. Use them when you open a `diskcache.Cache` yourself on an older directory, or delete the directory. Their tests are in `tests/cache/test_cache_l2_and_health.py`.

## The cached decorator

```python
from pyeuropepmc import CacheBackend, CacheConfig
from pyeuropepmc.cache.cache import cached

cache = CacheBackend(CacheConfig(enabled=True))
calls = []


@cached(cache, "square", ttl=60)
def square(x):
    calls.append(x)
    return x * x


print(square(4), square(4), len(calls))  # 16 16 1
```

`cached(cache_backend, key_prefix, ttl=None, tag=None, key_func=None)` builds the key from `key_prefix`, the function name and the arguments (`general:v1:square:{hash}`), unless you pass `key_func(*args, **kwargs) -> str`. A result of `None` is never cached, and `ttl` only sets the L2 expiry, like `set(expire=...)`.

## ArtifactStore

`ArtifactStore` is a standalone content-addressed store for large files such as PDF, XML and ZIP downloads. No client uses it; `FullTextClient` keeps its downloads in its own [download cache](../features/caching/README.md#fulltextclient-download-cache).

| Parameter | Type | Default | Effect |
|---|---|---|---|
| `base_dir` | `Path` or `str` | required | Root directory; `artifacts/` and `index/` are created inside it. |
| `size_limit_mb` | `int` | `10000` | When new content would push the stored bytes over this limit, index entries are removed, least recently accessed first, until usage would fall to 80% of the limit; content that no entry references is then deleted. |
| `min_free_space_mb` | `int` | `1000` | Stored but not checked. |

| Method | Returns | Notes |
|---|---|---|
| `store(artifact_id, content, mime_type=None, etag=None, last_modified=None)` | `ArtifactMetadata` | Writes the bytes once per SHA-256 hash and points `artifact_id` at them. Storing an existing ID replaces its index entry. |
| `retrieve(artifact_id)` | `(bytes, ArtifactMetadata)` or `None` | Also updates `last_accessed`. |
| `exists(artifact_id)` | `bool` | Checks the index entry only. |
| `get_metadata(artifact_id)` | `ArtifactMetadata` or `None` | Does not read the content. |
| `delete(artifact_id)` | `bool` | Removes the index entry; the content stays until `compact()`. |
| `compact()` | `dict` | Deletes content that no index entry references. Returns `orphans_removed`, `artifacts_remaining`, `index_entries` and `used_mb`. |
| `get_disk_usage()` | `dict` | `used_bytes`, `used_mb`, `limit_bytes`, `limit_mb`, `used_percent`, `artifact_count`, `index_count`, `fs_available_bytes`, `fs_available_mb`, `fs_total_bytes`, `fs_total_mb`. |
| `clear()` | `None` | Deletes all content and index entries. |

`ArtifactMetadata` has the attributes `hash_value`, `size`, `mime_type`, `etag`, `last_modified`, `stored_at` and `last_accessed`. `to_dict()` writes `hash_value` under the key `hash`, and `ArtifactMetadata.from_dict()` reads that format back.

```text
base_dir/
    artifacts/<first two hex characters>/<sha256>
    index/<artifact_id with ":" and "/" replaced by "_">.json
```

Because of that replacement, IDs that differ only in `:`, `/` or `_` share one index file.

```python
from pathlib import Path

from pyeuropepmc import ArtifactStore

store = ArtifactStore(Path("artifacts"), size_limit_mb=1000)

pdf = b"%PDF-1.7 example"
first = store.store("pmc:PMC3312970:pdf", pdf, mime_type="application/pdf")
second = store.store("doi:10.1000/example:pdf", pdf, mime_type="application/pdf")
print(first.hash_value == second.hash_value)  # True: the bytes are stored once

content, metadata = store.retrieve("pmc:PMC3312970:pdf")
print(len(content), metadata.mime_type)  # 16 application/pdf

store.delete("pmc:PMC3312970:pdf")
store.delete("doi:10.1000/example:pdf")
print(store.compact()["orphans_removed"])  # 1
```

## Logging

The cache logs to `pyeuropepmc.cache.cache`: layer initialisation, `clear()`, `evict()`, `invalidate_pattern()` and `close()` at INFO level, and every hit, miss, write and delete, with its key, at DEBUG level. `ArtifactStore` logs to `pyeuropepmc.storage.artifact_store`.

## Known limitations

These are issues in the current code; the sections above describe the actual behaviour.

- The disk layer deletes `cache.db` when it starts, so it does not persist ([Disk layer](#disk-layer-l2)).
- `SearchClient.invalidate_search_cache()` and `AnnotationsClient.invalidate_annotations_cache()` default to patterns that match none of their keys ([Cache keys](#cache-keys)).
- L1 uses one TTL for every entry; `set(expire=...)`, `data_type` and `ttl_by_type` only change the L2 expiry.
- `CacheConfig(eviction_policy=...)` and `ArtifactStore(min_free_space_mb=...)` are stored but not used.
- `invalidate_older_than()` always returns `0`, and `get_keys()` and `compact()` only look at L1.
