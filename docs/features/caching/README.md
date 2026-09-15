# Caching

pyEuropePMC can keep API responses so that a repeated request is answered without another HTTP call. This page covers response caching in the clients, which is off until you pass a `CacheConfig`, and the separate file cache that `FullTextClient` keeps for downloads. The cache layer itself is documented in [Caching internals](../../advanced/caching.md).

## Turn on response caching

Pass `cache_config=CacheConfig(...)` when you create the client. Without it, every call goes to the API.

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True, ttl=3600)) as client:
    first = client.search("malaria vaccine", pageSize=25)  # HTTP request
    second = client.search("malaria vaccine", pageSize=25)  # answered from the cache

    stats = client.get_cache_stats()
    print(stats["hits"], stats["misses"])  # 1 1
```

`CacheConfig()` on its own already has `enabled=True`. A client that gets no `cache_config` uses `CacheConfig(enabled=False)`.

## What is cached

| Client | Cached calls | Cache management methods |
|---|---|---|
| `SearchClient` | `search()`, `search_post()`, and each page request of `search_all()` | `get_cache_stats()`, `get_cache_health()`, `clear_cache()`, `invalidate_search_cache(pattern)` |
| `ArticleClient` | `get_article_details()`, `get_citations()` and `get_references()`, except JSONP calls (`callback=`) | `get_cache_stats()`, `get_cache_health()`, `clear_cache()`, `invalidate_article_cache(source, article_id)` |
| `AnnotationsClient` | `get_annotations_by_article_ids()`, `get_annotations_by_entity()`, `get_annotations_by_provider()` | `get_cache_stats()`, `get_cache_health()`, `clear_cache()`, `invalidate_annotations_cache(pattern)` |
| `FullTextClient` | `check_fulltext_availability()` | `get_api_cache_stats()`, `get_api_cache_health()`, `clear_api_cache()`, `invalidate_fulltext_cache(pmcid)` |

Other methods of these clients are not cached. In particular, `FullTextClient.get_fulltext_content()` requests the article every time, and the `download_*` methods use the [download cache](#fulltextclient-download-cache) instead.

These classes also accept `cache_config` and then cache their HTTP responses, but they have no statistics or clearing methods of their own:

- the literature source clients `PubMedClient`, `ArxivClient` and `ClinicalTrialsClient`;
- the enrichment clients `CrossRefClient`, `DataCiteClient`, `OpenAlexClient`, `OrcidClient`, `RorClient`, `SemanticScholarClient` and `UnpaywallClient`, and `EnrichmentConfig`, which passes its `cache_config` to each of them;
- `CitationWalker`.

`UnifiedSearch` has no cache option. `PaperProcessingPipeline` is the one place where caching is on by default: `PipelineConfig(enable_cache=True, cache_size_mb=500)` gives its search, full-text and enrichment clients `CacheConfig(enabled=True, size_limit_mb=500)`.

## Configure the cache

| Parameter | Type | Default | Effect |
|---|---|---|---|
| `enabled` | `bool` | `True` | `False` turns every cache operation into a no-op. |
| `ttl` | `int` | `86400` | Seconds an entry stays valid after it is stored. See [Expiry](#expiry). |
| `size_limit_mb` | `int` | `500` | Capacity of the in-memory layer, as an entry count of `min(size_limit_mb * 1024, 10000)`. Must be 1 or more. |
| `enable_l2` | `bool` | `False` | Adds a disk layer (diskcache) in `cache_dir`. See [Memory and disk layers](#memory-and-disk-layers). |
| `cache_dir` | `Path`, `str` or `None` | `None` | Directory of the disk layer. `None` means `<system temp dir>/pyeuropepmc_cache`. Only used with `enable_l2=True`. |
| `l2_size_limit_mb` | `int` | `5000` | Size limit of the disk layer in megabytes. |

`ttl_by_type` and `eviction_policy` do not change how the clients cache, and `namespace_version` only changes their key strings. All three are described in the [CacheConfig reference](../../advanced/caching.md#cacheconfig-reference).

## Memory and disk layers

Every enabled cache has an in-memory layer (a cachetools `TTLCache`). Each client instance creates its own, so two clients never share entries, even when you pass them the same `CacheConfig` object. Leaving the `with` block, or calling `close()`, empties it.

With `enable_l2=True`, entries are also written to a diskcache database in `cache_dir`. A lookup checks memory first, then disk, and copies a disk hit back into memory.

```python
from pathlib import Path

from pyeuropepmc import CacheConfig, SearchClient

config = CacheConfig(enabled=True, enable_l2=True, cache_dir=Path("pyeuropepmc-cache"))

with SearchClient(cache_config=config) as client:
    client.search("dengue", pageSize=10)
    print(sorted(client.get_cache_stats()["layers"]))  # ['l1', 'l2']
```

> **Known limitation.** The disk layer does not keep entries between client instances or runs yet. Opening it deletes an existing `cache.db` in `cache_dir` (`_initialize_l2_cache()` in `src/pyeuropepmc/cache/cache.py`). A new client, or the same script run again, therefore starts with an empty disk cache, and two clients that are open at the same time on one `cache_dir` do not see each other's entries. Give each client its own `cache_dir`, and do not rely on the disk layer to avoid requests in a later run.

## Expiry

- An entry expires `ttl` seconds after it was stored, in memory and on disk.
- There is no value that never expires: `ttl=None` raises `TypeError`, a negative `ttl` raises `ConfigurationError`, and `ttl=0` expires every entry immediately. For a long-lived development cache, use a large value such as `ttl=30 * 24 * 3600`.
- `CacheConfig(ttl_by_type=...)` does not apply to client entries. It only sets the disk expiry of entries that you store yourself with `CacheBackend.set(..., data_type=...)`.

## How requests are matched

The key of a cached response is built from the request parameters after normalization. Extra whitespace in the query and the `page_size`/`pageSize` spelling do not create a new entry; a change of case does.

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True)) as client:
    client.search("cancer therapy", pageSize=10)
    client.search("cancer   therapy", page_size=10)  # same entry
    client.search("Cancer therapy", pageSize=10)  # new entry
    print(client.get_cache_stats()["entry_count"])  # 2
```

The key formats of every client are listed in [Caching internals](../../advanced/caching.md#cache-keys).

## Inspect the cache

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True)) as client:
    client.search("zika", pageSize=5)
    client.search("zika", pageSize=5)

    stats = client.get_cache_stats()
    print(f"hits={stats['hits']} misses={stats['misses']} hit_rate={stats['hit_rate']:.0%}")
    print(f"entries={stats['entry_count']} of {stats['maxsize']}")  # entries=1 of 10000

    health = client.get_cache_health()
    print(health["status"], health["warnings"])  # healthy []
```

`get_cache_stats()` returns a dict. The keys you will use most:

| Key | Meaning |
|---|---|
| `hits`, `misses` | Lookups answered from the cache, and lookups that found nothing. |
| `hit_rate` | `hits / (hits + misses)`, a fraction between 0 and 1. |
| `entry_count`, `maxsize` | Entries in the in-memory layer, and its capacity. |
| `size_mb` | An estimate of 1 KB per in-memory entry, not measured memory. |
| `layers` | Per-layer statistics: `l1`, plus `l2` when the disk layer is on. |

When caching is disabled, `get_cache_stats()` returns only `namespace_version` and the empty dicts `layers` and `overall`, so `stats["hits"]` raises `KeyError`. `get_cache_health()` works either way: its `status` is `"disabled"`, `"healthy"`, `"warning"` or `"critical"` (`"unavailable"` or `"error"` if the cache could not be read), and `warnings` lists the reasons. All keys are listed in [Statistics and health](../../advanced/caching.md#statistics-and-health).

On `FullTextClient`, use `get_api_cache_stats()` and `get_api_cache_health()`; its `get_cache_stats()` reports the download cache.

## Remove entries

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True)) as client:
    client.search("influenza", pageSize=10)
    client.search_post("influenza", pageSize=10)

    print(client.invalidate_search_cache("*:search:*"))  # 1: the search() entry
    print(client.clear_cache())  # True: the search_post() entry is removed too
```

- `clear_cache()` removes every entry and returns `True` (`False` when caching is disabled).
- `invalidate_search_cache(pattern)` removes the keys that match a glob pattern and returns how many it removed. The query text is hashed into the key, so a pattern selects all `search()` entries (`"*:search:*"`) or all `search_post()` entries (`"*:search_post:*"`), never a single query.
- `ArticleClient.invalidate_article_cache(source="MED", article_id="25883711")` removes the details, citations and references cached for that article. With only `source`, it removes that source's entries; with no arguments, all entries.
- `FullTextClient.invalidate_fulltext_cache("PMC3312970")` removes the availability entry for that ID; with no argument, all entries.

> **Known limitation.** Called without a pattern, `invalidate_search_cache()` uses `"search:*"` and `invalidate_annotations_cache()` uses `"annotations:*"`. The keys of these clients start with `general:` (for example `general:v1:search:6950a79a94574e15`), so the defaults remove nothing. Pass `"*:search:*"`, `"*:search_post:*"` or `"*:annotations_by_*"` instead.

## FullTextClient download cache

`FullTextClient` keeps a copy of every file it downloads and reuses it on the next request for the same ID and format. This file cache is separate from response caching and is on by default.

| Parameter | Type | Default | Effect |
|---|---|---|---|
| `enable_cache` | `bool` | `True` | Keep and reuse downloaded files. |
| `cache_dir` | `str`, `Path` or `None` | `None` | `None` means `<system temp dir>/pyeuropepmc_cache`. Files are stored as `<cache_dir>/<format>/PMC<id>.<format>`. |
| `cache_max_age_days` | `int` | `30` | Files older than this are downloaded again. |
| `verify_cached_files` | `bool` | `True` | Reuse a file only if it starts like its format: `%PDF` for PDF, `<` for XML, an HTML tag for HTML. Empty files are never reused. |

`download_pdf_by_pmcid()`, `download_xml_by_pmcid()`, `download_html_by_pmcid()` and `download_fulltext_batch()` read and fill this cache. A cached file is copied to the `output_path` you ask for.

```python
from pathlib import Path

from pyeuropepmc import FullTextClient

with FullTextClient(cache_dir=Path("fulltext-cache")) as client:
    client.download_xml_by_pmcid("PMC3312970", output_path=Path("xml/PMC3312970.xml"))
    client.download_xml_by_pmcid("PMC3312970", output_path=Path("copy/PMC3312970.xml"))
    print(client.last_xml_source)  # cache

    stats = client.get_cache_stats()
    print(stats["total_files"], stats["formats"]["xml"]["count"])  # 1 1

    print(client.clear_cache(max_age_days=0))  # 1: number of files removed
```

- `get_cache_stats()` returns `enabled`, `cache_dir`, `total_files`, `total_size_bytes` and `formats` (`count` and `size_bytes` per format), or `{"enabled": False}` when `enable_cache=False`.
- `clear_cache(format_type=None, max_age_days=None)` deletes only files older than `max_age_days`, which defaults to `cache_max_age_days`. Without arguments it therefore keeps recent files. Pass `max_age_days=0` to delete them all, and `format_type="pdf"`, `"xml"` or `"html"` to limit it to one format.
- `get_file_cache_health()` reports `status`, whether the directory is writable, whether there is free disk space, and whether the files are within the age limit.

The download cache and the `CacheConfig` disk layer have the same default directory, `<system temp dir>/pyeuropepmc_cache`. If you use both, give them different directories.

## Troubleshooting

**A repeated call still sends a request.** Check `client.get_cache_health()["enabled"]`: it is `False` when no `cache_config` was passed. Entries belong to one client instance, so a new client starts empty; queries that differ in case are different entries; and `ttl=0` expires everything.

**`TypeError: SearchClient.__init__() got an unexpected keyword argument 'use_cache'`.** Older examples passed `use_cache`, `cache_dir`, `cache_ttl` or `enable_cache` to `SearchClient`. Put these settings into `CacheConfig` (`enabled`, `cache_dir`, `ttl`) and pass `cache_config=`.

**`ImportError: cannot import name 'CacheConfig' from 'pyeuropepmc.cache'`.** Import it from `pyeuropepmc`, or from `pyeuropepmc.cache.cache`.

**See what the cache does.** The cache logs every hit, miss and write at DEBUG level:

```python
import logging

from pyeuropepmc import CacheConfig, SearchClient

logging.basicConfig(level=logging.INFO)
logging.getLogger("pyeuropepmc.cache").setLevel(logging.DEBUG)

with SearchClient(cache_config=CacheConfig(enabled=True)) as client:
    client.search("malaria", pageSize=5)
    client.search("malaria", pageSize=5)  # logs "L1 cache hit: general:v1:search:..."
```

## Related pages

- [Caching internals](../../advanced/caching.md): `CacheConfig` and `CacheBackend` reference, cache keys, the disk layer, `ArtifactStore`
- [Caching skill card](../../guides/skills/caching.md)
- [Search](../search/README.md)
- [Full-text retrieval](../fulltext/README.md)
