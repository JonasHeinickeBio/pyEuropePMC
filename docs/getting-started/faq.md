# Frequently asked questions

Short answers to common questions about installing and using pyEuropePMC, with runnable examples. For a specific error code, see [Error codes](../reference/error-codes.md).

## General

### What is pyEuropePMC?

A Python library for the Europe PMC REST API. It covers search, article metadata, citations, full-text download and JATS XML parsing, and adds multi-source search, enrichment and analysis tools on top.

### Do I need an API key?

No. The Europe PMC API needs no registration or key. Some optional services used for enrichment and multi-source search accept a key or a contact email, for example through the `SEMANTIC_SCHOLAR_API_KEY`, `CORE_API_KEY` and `UNPAYWALL_EMAIL` environment variables.

### Which Python versions are supported?

Python 3.10, 3.11, 3.12 and 3.13.

## Installation

### How do I install it?

Run `pip install pyeuropepmc`. Optional features need extras; see [Extras](installation.md#extras).

### How do I set up a development environment?

The development tools are a PEP 735 dependency group, not an extra, so installing with extras does not add them. Run `poetry install` in a clone of the repository; see [Development setup](installation.md#development-setup) and the [development guide](../development/README.md#setup).

## Searching

### How do I run a basic search?

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR", pageSize=10)

for paper in results["resultList"]["result"]:
    print(paper["title"])
```

### How do I search for an author?

Use the `AUTH` field:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    by_author = client.search('AUTH:"Smith J"')
    by_author_and_topic = client.search('AUTH:"Smith J" AND cancer')

print(by_author["hitCount"], by_author_and_topic["hitCount"])
```

### How do I get more than 1,000 results?

`search_all()` pages through the results with `cursorMark`. `fetch_all_pages()` does the same thing under another name.

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("machine learning", page_size=1000, max_results=5000)

print(len(papers))
```

There is no `offset` parameter. For manual paging, see [Get every result](quickstart.md#get-every-result), which also explains that `search_all()` returns what it has collected when a request fails.

### How do I sort results?

Pass a field and a direction: `sort="P_PDATE_D desc"` for newest first or `sort="CITED desc"` for most cited first. Without `sort`, results come in relevance order.

### How do I filter by publication year?

```python
from datetime import datetime

from pyeuropepmc import SearchClient

this_year = datetime.now().year
with SearchClient() as client:
    one_year = client.search("cancer AND PUB_YEAR:2023")
    year_range = client.search("cancer AND PUB_YEAR:[2020 TO 2023]")
    recent = client.search(f"cancer AND PUB_YEAR:[{this_year - 5} TO {this_year}]")

print(one_year["hitCount"], year_range["hitCount"], recent["hitCount"])
```

### Can I search several databases at once?

Within Europe PMC, combine sources in the query. Each record says where it comes from in its `source` field:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR AND (SRC:MED OR SRC:PPR)", pageSize=100)

for paper in results["resultList"]["result"]:
    print(paper["source"], paper["title"])
```

To search other services too and merge duplicates, use `UnifiedSearch`. See [Multi-source search](../features/multi-source-search.md).

```python
from pyeuropepmc import UnifiedSearch

searcher = UnifiedSearch(sources=["europepmc", "pubmed", "arxiv"])
papers, report = searcher.search("CRISPR", limit=25)
searcher.close()

print(len(papers), report.metadata["source_errors"])
```

### Which output formats are there?

`format="json"` (the default) returns a dict. `format="xml"` and `format="dc"` (Dublin Core) return the response as a string. `search_and_parse(query, format=...)` returns a list of record dicts for any of the three. RIS and BibTeX are not search formats.

## Rate limits and performance

### Does pyEuropePMC limit its request rate?

Yes. Each client waits `rate_limit_delay` seconds between requests (default 1.0). If you see HTTP 429 responses, increase it, for example `SearchClient(rate_limit_delay=2.0)`. Failed requests are retried with backoff before an error is raised.

### How do I make repeated searches faster?

`SearchClient` caches responses only when you pass it a `CacheConfig`, and keeps the cache in memory by default. See [Caching](../features/caching/README.md) and [Caching internals](../advanced/caching.md).

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True, ttl=3600)) as client:
    first = client.search("CRISPR", pageSize=100)
    again = client.search("CRISPR", pageSize=100)  # answered from the cache
    print(client.get_cache_stats())
```

The default `resultType="lite"` also returns less data per record than `"core"`.

## Results and full text

### What fields does a search result have?

With the default `resultType="lite"`, records have fields such as `id`, `source`, `pmid`, `pmcid`, `doi`, `title`, `authorString`, `journalTitle`, `pubYear`, `isOpenAccess` and `citedByCount`. A field is missing when the record has no value, so read fields with `.get()`. `resultType="core"` adds the abstract, MeSH terms and full-text links (`fullTextUrlList`).

### How do I get the full text of an article?

Use `FullTextClient` with the article's PMCID. Not every article with a PMCID is open access. See [Full-text retrieval](../features/fulltext/README.md).

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    availability = client.check_fulltext_availability("PMC3258128")
    xml = client.get_fulltext_content("PMC3258128")
    pdf_path = client.download_pdf_by_pmcid("PMC3258128", output_path="PMC3258128.pdf")

print(availability, len(xml), pdf_path)
```

### Where do citation counts come from?

`citedByCount` counts the citing articles that Europe PMC has indexed. Counts from other services, such as OpenAlex or Semantic Scholar, differ because they index different literature.

## Troubleshooting

### Why do I get no results?

1. Check the query syntax: balanced quotes and brackets, and operators in capitals (`AND`, `OR`, `NOT`).
2. Check the field names: `AUTH:`, not `AUTHOR:`.
3. Remove filters one at a time.
4. Count matches without fetching records: `client.get_hit_count("your query")`.

### Why does `search()` raise SEARCH001?

The query failed a basic check before any request was sent. It is empty or shorter than two characters, has an odd number of double quotes, or more than 30% of its characters are special characters. `SearchClient.validate_query(query)` returns `False` for such queries.

### How do I handle errors?

Catch `PyEuropePMCError`, the base class of every pyEuropePMC exception:

```python
from pyeuropepmc import SearchClient
from pyeuropepmc.core.exceptions import PyEuropePMCError

try:
    with SearchClient() as client:
        results = client.search("malaria vaccine")
except PyEuropePMCError as err:
    cause = err.__cause__
    underlying = getattr(getattr(cause, "error_code", None), "value", None)
    print(f"[{err.error_code.value}] retryable={err.is_retryable()} underlying={underlying}")
else:
    print(results["hitCount"])
```

The exception classes you are most likely to meet:

| Raised by | Exception | Import |
|---|---|---|
| `SearchClient` | `EuropePMCError`; a failed request has code `NET001` and the `APIClientError` in `__cause__` | `pyeuropepmc` |
| `ArticleClient`, `FullTextClient` requests | `APIClientError` | `pyeuropepmc` |
| `FullTextClient` argument checks | `FullTextError` | `pyeuropepmc` |
| `FullTextXMLParser`, `EuropePMCParser` | `ParsingError` | `pyeuropepmc.core.exceptions` |
| `QueryBuilder` | `QueryBuilderError` | `pyeuropepmc.core.exceptions` |

### Why do I get timeout errors?

`SearchClient` has no timeout argument. Requests to Europe PMC time out after 15 seconds and are retried with backoff before an error is raised. Check your connection, and try a simpler query or a smaller `pageSize`. `UnifiedSearch` takes `timeout=` (default 30 seconds).

## Getting help

- [Examples](../examples/README.md) and the [example scripts in the repository](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples)
- [API reference](../api/README.md)
- [GitHub issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues), for bugs, questions and feature requests
- [Development guide](../development/README.md), for contributing
- Europe PMC's own documentation: the [REST API](https://europepmc.org/RestfulWebService) and [search help](https://europepmc.org/Help)
