# ArticleClient API reference

`ArticleClient` reads the resources Europe PMC keeps for a single article: its metadata, the records that cite it, its reference list, database cross-references, lab and data links, and supplementary files.

```python
from pyeuropepmc import ArticleClient
```

The class is defined in `pyeuropepmc.features.literature.article`.

## Identifying an article

Every method except `get_supplementary_files()` takes a `source` and an `article_id`, the `source` and `id` values of a search result:

| `source` | Records | Example `article_id` |
|---|---|---|
| `MED` | PubMed/MEDLINE | `"39709209"` |
| `PMC` | PubMed Central | `"PMC3258128"` |
| `PPR` | Preprints | `"PPR123456"` |
| `AGR`, `CBA`, `CTX`, `ETH`, `HIR`, `NBK`, `PAT` | Agricola, Chinese Biological Abstracts, CiteXplore, EThOS theses, NHS Evidence, Europe PMC Bookshelf, biological patents | |

The client only checks that `source` is a three-letter string and that `article_id` is a non-empty string.

## Constructor

`ArticleClient(rate_limit_delay=1.0, cache_config=None)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rate_limit_delay` | `float` | `1.0` | Seconds to wait after each request |
| `cache_config` | `CacheConfig` or `None` | `None` | Response cache settings; `None` disables caching |

The client can be used as a context manager; otherwise call `close()`.

## Methods

| Method | Endpoint | Returns |
|---|---|---|
| `get_article_details(source, article_id, result_type="core", format="json", **kwargs)` | `article/{source}/{id}` | `dict` |
| `get_citations(source, article_id, page=1, page_size=25, format="json", callback=None, **kwargs)` | `{source}/{id}/citations` | `dict` |
| `get_references(source, article_id, page=1, page_size=25, format="json", callback=None, **kwargs)` | `{source}/{id}/references` | `dict` |
| `get_citation_count(source, article_id, **kwargs)` | `{source}/{id}/citations` | `int` |
| `get_reference_count(source, article_id, **kwargs)` | `{source}/{id}/references` | `int` |
| `get_database_links(source, article_id, page=1, page_size=25, format="json", callback=None, **kwargs)` | `{source}/{id}/databaseLinks` | `dict` |
| `get_lab_links(source, article_id, provider_id=None, format="json", callback=None, **kwargs)` | `{source}/{id}/labsLinks` | `dict` |
| `get_data_links(source, article_id, format="json", callback=None, **kwargs)` | `{source}/{id}/datalinks` | `dict` |
| `get_supplementary_files(article_id, include_inline_image=True, **kwargs)` | `{id}/supplementaryFiles` | `bytes` |
| `export_results(results, format="dataframe", path=None, **kwargs)` | | Same as [`SearchClient.export_results()`](search-client.md#export_results) |
| `get_cache_stats()`, `get_cache_health()`, `clear_cache()`, `invalidate_article_cache(source=None, article_id=None)` | | Cache management |
| `close()` | | Release the HTTP session and the cache |

Extra keyword arguments are added to the request as query-string parameters.

### Common parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | `int` | `1` | Page number, starting at 1 |
| `page_size` | `int` | `25` | Records per page, 1 to 1000 |
| `format` | `str` | `"json"` | Use `"json"`. The response body is always parsed as JSON, so another format makes the request fail with `APIClientError` |
| `callback` | `str` or `None` | `None` | JSONP function name; the method then returns `{"jsonp_response": <text>}` and skips the cache. Requires `format="json"` |

### get_article_details

Returns `{"version", "hitCount", "request", "result"}`, where `result` is the article record. `result_type` is `"idlist"`, `"lite"` or `"core"` (default); `core` records carry the abstract, author list, MeSH headings and grants, as described under [Result types](../features/search/README.md#result-types).

### get_citations and get_references

`get_citations()` returns `{"version", "hitCount", "request", "citationList": {"citation": [...]}}`. `get_references()` returns the same outer keys with `"referenceList": {"reference": [...]}`. `hitCount` is the total across all pages. Each item describes one publication, with keys such as `id`, `source`, `citationType`, `title`, `authorString`, `journalAbbreviation`, `pubYear`, `volume`, `issue` and `pageInfo`; citation items also carry `citedByCount`, and reference items `citedOrder` and `match`.

`get_citation_count()` and `get_reference_count()` request one record and return `hitCount` as an `int` (0 if it cannot be read).

When a response has `hitCount` 0, the client emits a `UserWarning`.

### get_database_links, get_lab_links and get_data_links

`get_database_links()` returns the biological database records that cite the article under `dbCrossReferenceList`. `get_lab_links()` returns external links added by third-party providers; pass `provider_id` to restrict it to one provider. `get_data_links()` returns the article's data-literature links in Scholix format.

### get_supplementary_files

Downloads the supplementary material of an open-access article as a ZIP archive and returns its bytes. `article_id` is the PMC ID, for example `"PMC3258128"`. `include_inline_image=False` leaves inline images out of the archive. A missing archive raises `APIClientError`.

## Examples

### Details, citations and references

```python
from pyeuropepmc import ArticleClient

with ArticleClient() as client:
    details = client.get_article_details("MED", "39709209")
    print(details["result"]["title"])

    citations = client.get_citations("MED", "39709209", page_size=100)
    print(f"Cited by {citations['hitCount']} records")
    for item in citations.get("citationList", {}).get("citation", []):
        print(f"  {item['source']}:{item['id']} {item.get('title')}")

    references = client.get_references("MED", "39709209")
    for item in references.get("referenceList", {}).get("reference", []):
        print(f"  {item.get('title')}")
```

### Collect every citing record

```python
from pyeuropepmc import ArticleClient

citing = []
with ArticleClient() as client:
    total = client.get_citation_count("MED", "39709209")
    page = 1
    while len(citing) < total:
        response = client.get_citations("MED", "39709209", page=page, page_size=1000)
        batch = response.get("citationList", {}).get("citation", [])
        if not batch:
            break
        citing.extend(batch)
        page += 1

print(f"{len(citing)} of {total} citing records")
```

### Save supplementary files

```python
from pathlib import Path

from pyeuropepmc import ArticleClient

with ArticleClient() as client:
    archive = client.get_supplementary_files("PMC3258128")

Path("PMC3258128_supplementary.zip").write_bytes(archive)
```

## Caching

With `cache_config=CacheConfig(enabled=True)`, the responses of `get_article_details()`, `get_citations()` and `get_references()` are cached. Database, lab and data links and supplementary files are always fetched. `invalidate_article_cache(source=None, article_id=None)` removes cached entries for one article, for one source, or all entries when called without arguments, and returns the number removed. See [Caching](../features/caching/README.md).

```python
from pyeuropepmc import ArticleClient, CacheConfig

with ArticleClient(cache_config=CacheConfig(enabled=True)) as client:
    client.get_citations("MED", "39709209")
    client.get_citations("MED", "39709209")  # served from the cache
    removed = client.invalidate_article_cache(source="MED", article_id="39709209")
```

## Errors

| Exception | Raised when |
|---|---|
| `ValidationError` | An argument is invalid: `source` not three letters, empty `article_id`, `page` below 1, `page_size` outside 1 to 1000, an unknown `result_type` or `format`, or `callback` with a non-JSON format |
| `APIClientError` | The request fails or the response is not JSON |

`APIClientError` is exported by `pyeuropepmc`; `ValidationError` is imported from `pyeuropepmc.core.exceptions`. Both derive from `PyEuropePMCError`.

```python
from pyeuropepmc import APIClientError, ArticleClient
from pyeuropepmc.core.exceptions import ValidationError

with ArticleClient() as client:
    try:
        client.get_citations("MEDLINE", "39709209")
    except ValidationError as error:
        print(f"Invalid argument: {error}")
    except APIClientError as error:
        print(f"Request failed: {error}")
```

## Related pages

- [SearchClient](search-client.md) finds articles and their `source` and `id`
- [FullTextClient](fulltext-client.md) downloads full-text XML and PDF
