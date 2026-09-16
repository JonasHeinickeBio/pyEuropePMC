# SearchClient API reference

`SearchClient` wraps the Europe PMC REST `search` and `searchPOST` endpoints. For query syntax and worked examples see [Searching Europe PMC](../features/search/README.md).

```python
from pyeuropepmc import SearchClient
```

The class is defined in `pyeuropepmc.features.literature.search`. `pyeuropepmc.Client` is an alias for it.

## Constructor

`SearchClient(rate_limit_delay=1.0, cache_config=None)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rate_limit_delay` | `float` | `1.0` | Seconds to wait after each request |
| `cache_config` | `CacheConfig` or `None` | `None` | Response cache settings; `None` disables caching. See [Caching](#caching) |

Requests time out after 15 seconds. The client can be used as a context manager; otherwise call `close()` when you are done.

```python
from pyeuropepmc import SearchClient

with SearchClient(rate_limit_delay=2.0) as client:
    results = client.search("malaria")
```

## Methods

| Method | Returns | Summary |
|---|---|---|
| [`search(query, **kwargs)`](#search) | `dict` or `str` | One page of results |
| [`search_post(query, **kwargs)`](#search_post) | `dict` or `str` | One page of results, sent as a POST request |
| [`search_all(query, page_size=100, max_results=None, **kwargs)`](#search_all) | `list[dict]` | Records from as many pages as needed |
| [`search_and_parse(query, format="json", **kwargs)`](#search_and_parse) | `list[dict]` | One page, parsed into records |
| [`search_ids_only(query, **kwargs)`](#search_ids_only) | `list[str]` | Record IDs from one page |
| [`get_hit_count(query, **kwargs)`](#get_hit_count) | `int` | Total number of matches |
| [`validate_query(query)`](#validate_query) | `bool` | Static method: the local query check |
| [`interactive_search(query, **kwargs)`](#interactive_search) | `list[dict]` | Asks on standard input how many records to fetch |
| [`export_results(results, format="dataframe", path=None, **kwargs)`](#export_results) | depends on `format` | Convert records to a DataFrame, CSV, Excel, JSON or Markdown |
| `fetch_all_pages(query, page_size=100, max_results=None, **kwargs)` | `list[dict]` | Deprecated alias of `search_all()`; emits `DeprecationWarning` |
| [`get_cache_stats()`, `get_cache_health()`, `clear_cache()`, `invalidate_search_cache(pattern="search:*")`](#caching) | | Cache management |
| `close()` | `None` | Release the HTTP session and the cache |

### search

`search(query, **kwargs) -> dict | str`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Europe PMC query string |
| `resultType` | `str` | `"lite"` | `"idlist"`, `"lite"` or `"core"` |
| `pageSize` or `page_size` | `int` | `25` | Records per page, 1 to 1000; `page_size` wins if both are given |
| `cursorMark` | `str` | `"*"` | Cursor from the previous response's `nextCursorMark`; `"*"` for the first page |
| `sort` | `str` | `""` | Empty for relevance order, otherwise a field and direction such as `"CITED desc"` |
| `synonym` | `bool` | `False` | Expand the query with MeSH and UniProt synonyms |
| `format` | `str` | `"json"` | `"json"`, `"xml"` or `"dc"` |
| `email` | `str` | not sent | Contact address passed to Europe PMC |

Other keyword arguments are forwarded as query-string parameters without checks.

**Returns:** for `format="json"`, the parsed response: a `dict` with `version`, `hitCount`, `nextCursorMark`, `request` (the parameters Europe PMC applied) and `resultList`, whose `result` list holds the records. For `"xml"` and `"dc"`, the response body as a `str`.

**Raises:** `SearchError` (exported as `pyeuropepmc.EuropePMCError`); see [Errors](#errors).

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search(
        'TITLE:"gene editing" AND PUB_YEAR:[2020 TO 2024]',
        resultType="core",
        pageSize=50,
        sort="CITED desc",
    )

print(results["hitCount"], len(results["resultList"]["result"]))
```

### search_post

`search_post(query, **kwargs) -> dict | str`

Takes the same parameters as `search()` and sends them form-encoded to the `searchPOST` endpoint. Use it for queries too long for a URL. Unlike `search()`, it does not run `validate_query()` first.

### search_all

`search_all(query, page_size=100, max_results=None, **kwargs) -> list[dict]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Europe PMC query string |
| `page_size` | `int` | `100` | Records per request; values outside 1 to 1000 are clamped |
| `max_results` | `int` or `None` | `None` | Stop after this many records; `None` fetches every match |
| `**kwargs` | | | Sent with every request, for example `resultType` or `sort` |

Follows `nextCursorMark` from page to page. It stops when `max_results` is reached, a page is empty or shorter than requested, or the cursor is missing or unchanged. It returns an empty list when `max_results` is 0 or negative.

A failed request ends the loop without an exception; the records collected so far are returned.

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("malaria vaccine", max_results=250, resultType="core")

print(len(papers))
```

### search_and_parse

`search_and_parse(query, format="json", **kwargs) -> list[dict]`

Runs one `search()` and parses the response with [EuropePMCParser](parser.md):

| `format` | Parser | Records |
|---|---|---|
| `"json"` | `parse_json` | The result dicts as returned by Europe PMC |
| `"xml"` | `parse_xml` | Each `<result>` element's child tags and text; nested elements are not expanded |
| `"dc"` | `parse_dc` | Dublin Core elements such as `title`, `creator`, `date`, `identifier`; repeated elements become lists |

**Raises:** `SearchError` with code `SEARCH004` for any other format, `ParsingError` if the response cannot be parsed, and the errors of `search()`.

### search_ids_only

`search_ids_only(query, **kwargs) -> list[str]`

Requests one page with `resultType="idlist"` and returns the `id` values. The page size is 25 unless you pass `pageSize`. Returns an empty list instead of raising when the request fails.

### get_hit_count

`get_hit_count(query, **kwargs) -> int`

Makes one request with a page size of 1 and returns `hitCount` as an `int`, or 0 if the response has none. Raises `SearchError` when the request fails.

### validate_query

`SearchClient.validate_query(query) -> bool`

The local check that `search()` applies before sending a request. It returns `False` for a query that is not a string, is empty or shorter than two characters after stripping, contains an odd number of double quotes, or consists of more than 30% of the characters ``!@#$%^&*()+=[]{}|\:;'<>?,/~` ``. It does not check field names or Boolean syntax.

### interactive_search

`interactive_search(query, **kwargs) -> list[dict]`

Prints the number of matches, asks on standard input how many records to fetch (`0`, `q` or `quit` cancels), then calls `search_all()`. Errors are logged and an empty list is returned.

### export_results

`export_results(results, format="dataframe", path=None, **kwargs)`

Converts a list of record dicts, such as the output of `search_all()`.

| `format` | Returns | Notes |
|---|---|---|
| `"dataframe"` | `pandas.DataFrame` | Needs pandas |
| `"csv"` | `str` | Also written to `path` if given; needs pandas |
| `"excel"` | `bytes` | Also written to `path` if given; needs pandas and xlsxwriter |
| `"json"` | `str` | Also written to `path` if given; pass `pretty=True` for indentation |
| `"markdown"` | `str` | Needs pandas and tabulate; returns `""` if conversion fails |

Other values raise `ValueError`. pandas, tabulate and xlsxwriter are installed with `pip install "pyeuropepmc[export]"`.

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("malaria vaccine", max_results=50)
    json_text = client.export_results(papers, format="json", path="papers.json", pretty=True)
```

## Caching

Caching is off by default. Pass a `CacheConfig` to enable it:

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True, ttl=3600)) as client:
    client.search("malaria")
    client.search("malaria")  # served from the cache
    stats = client.get_cache_stats()
    print(stats["hits"], stats["misses"], stats["hit_rate"])
    removed = client.invalidate_search_cache("search:*")
```

| Method | Returns | Description |
|---|---|---|
| `get_cache_stats()` | `dict` | Counters including `hits`, `misses`, `hit_rate`, `sets`, `entry_count` and `size_mb` |
| `get_cache_health()` | `dict` | `status`, `enabled`, `available`, `hit_rate`, `error_rate`, `size_utilization`, `warnings` |
| `clear_cache()` | `bool` | Remove every cached entry |
| `invalidate_search_cache(pattern="search:*")` | `int` | Remove entries whose key matches the glob pattern; returns the number removed |

`search()` and `search_post()` results are cached under separate keys. Cache errors are logged and never make a search fail. The cache is held in memory unless `CacheConfig(enable_l2=True)` is set. See the [Caching](../features/caching/README.md) guide and the [caching reference](../advanced/caching.md) for layers, time-to-live settings and storage location.

## Errors

`search()`, `search_post()`, `search_and_parse()` and `get_hit_count()` raise `SearchError`, which `pyeuropepmc` exports as `EuropePMCError`. The error code is available as `error.error_code`:

| Code | Cause |
|---|---|
| `SEARCH001` | The query failed `validate_query()` |
| `SEARCH002` | Page size outside 1 to 1000 |
| `SEARCH003` | The response was not valid JSON, or an unexpected error occurred |
| `SEARCH004` | Unsupported `format` |
| `NET001` | The request failed, including HTTP error responses |

```python
from pyeuropepmc import EuropePMCError, SearchClient

with SearchClient() as client:
    try:
        client.search("cancer", pageSize=5000)
    except EuropePMCError as error:
        print(error.error_code, error)
```

`SearchError`, `ParsingError` and the other package exceptions are defined in `pyeuropepmc.core.exceptions` and derive from `PyEuropePMCError`.

## Related pages

- [QueryBuilder](query-builder.md) builds query strings
- [ArticleClient](article-client.md) reads citations, references and links for one article
- [FullTextClient](fulltext-client.md) downloads full text
- [EuropePMCParser](parser.md) parses search responses
