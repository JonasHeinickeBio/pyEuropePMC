# Quick start

This page walks through a first session with pyEuropePMC: a search, a query built with `QueryBuilder`, paging through many results, downloading and parsing a full-text article, and handling errors. It assumes you have [installed](installation.md) the package.

## Search

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("cancer", pageSize=10)

print(results["hitCount"])
for article in results["resultList"]["result"]:
    print(article.get("title", "No title"))
```

`search()` sends its keyword arguments to the Europe PMC search endpoint. The common ones:

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `pageSize` (or `page_size`) | int | 25 | Records per request, 1–1000 |
| `sort` | str | relevance | A field and a direction, such as `"P_PDATE_D desc"` (newest first) or `"CITED desc"` (most cited first) |
| `resultType` | str | `"lite"` | `"idlist"`, `"lite"` or `"core"`; `core` adds abstracts, MeSH terms and full-text links |
| `cursorMark` | str | `"*"` | Where the next page starts; take it from the response's `nextCursorMark` |
| `synonym` | bool | `False` | Expand the query with synonyms |
| `format` | str | `"json"` | `"json"` returns a dict; `"xml"` and `"dc"` return the response as a string |

Other keyword arguments are sent to the API unchanged. Europe PMC ignores names it does not know, such as `limit` or `offset`, so a misspelt argument has no effect and raises no error.

Filter by source inside the query rather than with an argument, for example `SRC:MED` for PubMed records or `SRC:PPR` for preprints:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("machine learning AND SRC:MED", sort="P_PDATE_D desc", pageSize=20)

for article in results["resultList"]["result"]:
    print(article.get("pubYear"), article.get("title"))
    print("   ", article.get("authorString"), "|", article.get("journalTitle"), "|", article.get("doi"))
```

## Build a query with QueryBuilder

`QueryBuilder` builds query strings from named fields and checks that operators sit between terms. Create a new builder for each query, because `build()` does not reset it.

```python
from pyeuropepmc import QueryBuilder

query = (
    QueryBuilder()
    .keyword("cancer", field="title")
    .and_()
    .keyword("therapy")
    .and_()
    .date_range(start_year=2020, end_year=2023)
    .and_()
    .citation_count(min_count=10)
    .build()
)
print(query)
# TITLE:cancer AND therapy AND (PUB_YEAR:[2020 TO 2023]) AND (CITED:[10 TO *])
```

See the [QueryBuilder API](../api/query-builder.md) for all fields and methods.

## Get every result

One request returns at most 1,000 records. `search_all()` follows `nextCursorMark` from page to page and returns a list of records:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("CRISPR AND PUB_YEAR:2023", page_size=100, max_results=500)

print(len(papers), papers[0]["title"])
```

`search_all()` stops at the first failed request and returns the records it has collected so far, without raising an error. If you need to know that a page failed, page with `search()` yourself:

```python
from pyeuropepmc import SearchClient

papers = []
cursor = "*"
with SearchClient() as client:
    while len(papers) < 300:
        page = client.search("CRISPR AND PUB_YEAR:2023", pageSize=100, cursorMark=cursor)
        records = page["resultList"]["result"]
        papers.extend(records)
        if not records or page.get("nextCursorMark") in (None, cursor):
            break
        cursor = page["nextCursorMark"]

print(len(papers))
```

## Download and parse full text

Articles with a PMCID can have full text; open-access ones usually do. `FullTextClient` downloads it and `FullTextXMLParser` reads the JATS XML:

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

pmcid = "PMC3359999"
with FullTextClient() as client:
    print(client.check_fulltext_availability(pmcid))  # {'pdf': ..., 'xml': ..., 'html': ...}
    xml = client.get_fulltext_content(pmcid)  # JATS XML as a string

parser = FullTextXMLParser(xml)
metadata = parser.extract_metadata()
print(metadata["title"], metadata["doi"])

for table in parser.extract_tables():
    print(table["label"], (table["caption"] or "")[:60])

for section in parser.get_full_text_sections_structured():
    print(section["section_type"], section["title"])

print(parser.to_plaintext()[:300])
```

Each structured section has a `section_type`: `front` for the article title and abstract, `body` for the main text, `back` for back matter, and `appendix`. To save a file instead of reading it into memory, use `client.download_xml_by_pmcid(pmcid, output_path=...)` or `client.download_pdf_by_pmcid(pmcid, output_path=...)`; both return the path of the saved file.

## Handle errors

Every pyEuropePMC exception derives from `PyEuropePMCError` and carries an error code:

```python
from pyeuropepmc import SearchClient
from pyeuropepmc.core.exceptions import PyEuropePMCError

try:
    with SearchClient() as client:
        client.search("cancer", pageSize=5000)
except PyEuropePMCError as err:
    print(err.error_code.value)  # SEARCH002: the page size must be 1-1000
    print(err.is_retryable())  # False
```

`SearchClient` raises `SearchError`. When a request fails, whether from a network error or an HTTP error status, the code is `NET001` and `err.__cause__` holds the underlying `APIClientError`, whose code names the status, such as `HTTP500` or `RATE429`. `ArticleClient` and `FullTextClient` raise `APIClientError` for failed requests. [Error codes](../reference/error-codes.md) lists every code.

## Next steps

- [Examples](../examples/README.md)
- [FAQ](faq.md)
- [Search](../features/search/README.md), [Full-text retrieval](../features/fulltext/README.md) and [XML parsing](../features/parsing/README.md)
