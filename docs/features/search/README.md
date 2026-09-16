# Searching Europe PMC

`SearchClient` queries the Europe PMC REST search service. This page covers query syntax, request parameters, paging through large result sets, the shape of the results and error handling; the [SearchClient API reference](../../api/search-client.md) lists every method and parameter.

## Quick start

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR gene editing", pageSize=10)

print(f"Total matches: {results['hitCount']}")
for paper in results["resultList"]["result"]:
    print(paper["title"], "-", paper.get("citedByCount", 0), "citations")
```

`search()` returns the parsed JSON response as a `dict`. The records are in `results["resultList"]["result"]`; `hitCount` is the total number of matches, not the number of records in this response.

## Query syntax

The query string is sent to Europe PMC unchanged, so the full Europe PMC query language is available: keywords, quoted phrases, `AND`, `OR`, `NOT`, parentheses and fielded searches.

```python
from pyeuropepmc import SearchClient

queries = [
    "malaria",                                  # keyword
    '"machine learning"',                       # exact phrase
    "cancer AND therapy",                       # both terms
    "cancer OR tumour",                         # either term
    "cancer NOT lung",                          # exclude a term
    "(cancer OR tumour) AND (therapy OR treatment)",
    'AUTH:"Smith J" AND TITLE:cancer',          # fielded search
    "PUB_YEAR:[2020 TO 2024]",                  # range
]

with SearchClient() as client:
    for query in queries:
        print(query, "->", client.get_hit_count(query))
```

Frequently used fields:

| Field | Searches | Example |
|---|---|---|
| `TITLE` | Article title | `TITLE:malaria` |
| `ABSTRACT` | Abstract text | `ABSTRACT:"drug resistance"` |
| `AUTH` | Author name | `AUTH:"Smith J"` |
| `AFF` | Author affiliation | `AFF:"university of oxford"` |
| `JOURNAL` | Journal title or abbreviation | `JOURNAL:"Nature"` |
| `PUB_YEAR` | Publication year, single or range | `PUB_YEAR:[2020 TO 2024]` |
| `FIRST_PDATE` | Date of first publication | `FIRST_PDATE:[2020-01-01 TO 2020-06-30]` |
| `EXT_ID` with `SRC` | Record ID within a source, for example a PubMed ID | `EXT_ID:32791984 AND SRC:MED` |
| `PMCID` | PubMed Central ID | `PMCID:PMC3258128` |
| `DOI` | DOI | `DOI:"10.1038/s41586-020-2649-2"` |
| `GRANT_AGENCY` | Funder | `GRANT_AGENCY:wellcome` |
| `OPEN_ACCESS` | Open-access subset | `OPEN_ACCESS:y` |
| `CITED` | Number of citations | `CITED:[100 TO *]` |
| `CITES` | Records that cite an article, given as `ID_source` | `CITES:8521067_med` |
| `SRC` | Data source code | `SRC:PPR` |

Source codes include `MED` (PubMed/MEDLINE), `PMC` (PubMed Central), `PPR` (preprints), `AGR` (Agricola), `CBA` (Chinese Biological Abstracts), `CTX` (CiteXplore), `ETH` (EThOS theses), `HIR` (NHS Evidence), `NBK` (Europe PMC Bookshelf) and `PAT` (biological patents).

The builder's field list and a live list of searchable fields are described in the [QueryBuilder API reference](../../api/query-builder.md#field-names). To assemble query strings in code, use [`QueryBuilder`](../query-builder-load-save-translate.md).

## Search parameters

`search(query, **kwargs)` recognises these keyword arguments. Any other keyword argument is added to the request as a query-string parameter without checks.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `resultType` | `str` | `"lite"` | `"idlist"`, `"lite"` or `"core"`; see [Result types](#result-types) |
| `pageSize` | `int` | `25` | Records per request, 1 to 1000. `page_size` is accepted as well and wins if both are given |
| `cursorMark` | `str` | `"*"` | Paging cursor; `"*"` requests the first page |
| `sort` | `str` | `""` (relevance) | A sortable field and a direction, for example `"CITED desc"` or `"P_PDATE_D asc"` |
| `synonym` | `bool` | `False` | Expand the query with MeSH and UniProt synonyms |
| `format` | `str` | `"json"` | `"json"` returns a `dict`; `"xml"` and `"dc"` (Dublin Core) return the response text as a `str` |
| `email` | `str` | not sent | Contact address passed to Europe PMC |

## Result types

| `resultType` | Record contents |
|---|---|
| `idlist` | `id`, `source` and the PubMed and PubMed Central IDs where they exist |
| `lite` | Key metadata: title, `authorString`, `journalTitle`, `pubYear`, `citedByCount`, identifiers and availability flags such as `isOpenAccess` and `hasPDF` |
| `core` | Full metadata: `abstractText`, `authorList` with affiliations, `journalInfo`, `pubTypeList`, `fullTextUrlList` and, when the record has them, `meshHeadingList`, `keywordList`, `grantsList` and `license` |

Abstracts, MeSH headings and grants are only returned with `resultType="core"`. A `core` record describes the journal in `journalInfo["journal"]["title"]` instead of `journalTitle`.

## Sorting

Omit `sort` to get results in relevance order. Otherwise give a field and `asc` or `desc`:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    by_relevance = client.search("cancer")
    most_cited = client.search("cancer", sort="CITED desc")
    newest_first = client.search("cancer", sort="P_PDATE_D desc")
    oldest_first = client.search("cancer", sort="P_PDATE_D asc")
```

## Paging through results

### Collect many records with search_all

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("malaria vaccine", page_size=100, max_results=500)

print(f"Retrieved {len(papers)} records")
```

`search_all(query, page_size=100, max_results=None, **kwargs)` follows `nextCursorMark` until it has `max_results` records or no more pages remain, and returns a `list` of record dicts. Other keyword arguments, such as `resultType="core"` or `sort`, are sent with every request. With `max_results=None` it fetches every match, which for a broad query means many requests.

`search_all()` does not raise when a request fails: it stops and returns the records collected so far. Compare `len(papers)` with `get_hit_count()` when completeness matters.

### Count matches and list IDs

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    total = client.get_hit_count("malaria vaccine")          # int
    first_ids = client.search_ids_only("malaria vaccine")    # list[str] from one page

print(total, first_ids[:5])
```

`get_hit_count()` makes one request with a page size of 1. `search_ids_only()` requests one `idlist` page (25 IDs unless you pass `pageSize`) and returns an empty list if the request fails.

### Page manually with cursorMark

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    cursor = "*"
    for _ in range(3):  # at most three pages of 100 records
        page = client.search("malaria vaccine", pageSize=100, cursorMark=cursor)
        for paper in page["resultList"]["result"]:
            print(paper["id"], paper["title"])
        next_cursor = page.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor:
            break  # Europe PMC returns the same cursor on the last page
        cursor = next_cursor
```

Pages are reachable only through `nextCursorMark`; there is no page number or offset parameter.

### Very long queries

`search_post(query, **kwargs)` takes the same parameters as `search()` and sends them as a form-encoded POST request, for queries that are too long for a URL.

## Working with results

Keys in a `lite` record:

| Key | Type | Notes |
|---|---|---|
| `id`, `source` | `str` | Record ID and source code; [ArticleClient](../../api/article-client.md) takes both |
| `pmid`, `pmcid`, `doi` | `str` | Present only when the record has them |
| `title` | `str` | |
| `authorString` | `str` | Comma-separated author names |
| `journalTitle` | `str` | `core` records use `journalInfo` instead |
| `pubYear` | `str` | For example `"2024"`; convert it before comparing numbers |
| `firstPublicationDate` | `str` | `YYYY-MM-DD` |
| `citedByCount` | `int` | Citations counted by Europe PMC |
| `isOpenAccess`, `inEPMC`, `inPMC`, `hasPDF` | `str` | `"Y"` or `"N"` |

### Filter records

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search("cancer therapy", pageSize=100)["resultList"]["result"]

recent = [p for p in papers if int(p.get("pubYear") or 0) >= 2020]
highly_cited = [p for p in papers if p.get("citedByCount", 0) > 50]
open_access_in_pmc = [p for p in papers if p.get("pmcid") and p.get("isOpenAccess") == "Y"]

print(len(recent), len(highly_cited), len(open_access_in_pmc))
```

### Read core metadata

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("GRANT_AGENCY:wellcome AND malaria", resultType="core", pageSize=50)

for paper in results["resultList"]["result"]:
    abstract = paper.get("abstractText", "")
    grants = paper.get("grantsList", {}).get("grant", [])
    funders = sorted({grant.get("agency", "unknown") for grant in grants})
    print(paper["title"])
    print("  abstract length:", len(abstract))
    print("  funders:", ", ".join(funders) or "none listed")
```

### Parse into a list of records

`search_and_parse(query, format="json", **kwargs)` runs one search and returns the records as a `list` of dicts, for JSON, XML or Dublin Core responses:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    records = client.search_and_parse("malaria", format="json")
    dublin_core = client.search_and_parse("malaria", format="dc")

print(records[0]["title"])
print(dublin_core[0]["title"], dublin_core[0]["date"])
```

The parsing is done by [EuropePMCParser](../../api/parser.md).

## Caching

Caching is opt-in: responses are not cached unless you pass a `CacheConfig`, and the cache is held in memory unless you also set `enable_l2=True`. With caching enabled, an identical request is answered from the cache:

```python
from pyeuropepmc import CacheConfig, SearchClient

with SearchClient(cache_config=CacheConfig(enabled=True, ttl=3600)) as client:
    client.search("malaria")  # sent to Europe PMC
    client.search("malaria")  # answered from the cache
    print(client.get_cache_stats()["hits"])
```

See [Caching](../caching/README.md) for how to configure it and the [caching reference](../../advanced/caching.md) for cache layers, expiry and invalidation.

## Rate limiting

`SearchClient(rate_limit_delay=1.0)` waits `rate_limit_delay` seconds after every request; the default is 1.0. Europe PMC needs no API key or registration. You can pass `email="you@example.org"` to `search()` so that the Europe PMC team can contact you about service changes.

## Error handling

```python
from pyeuropepmc import EuropePMCError, SearchClient

with SearchClient() as client:
    try:
        results = client.search("malaria", pageSize=100)
    except EuropePMCError as error:
        print(f"Search failed: {error}")
    else:
        if results["hitCount"] == 0:
            print("No results found")
```

`EuropePMCError` is the exported name of `SearchError` from `pyeuropepmc.core.exceptions`. `search()` raises it when:

- the query fails the local check in `SearchClient.validate_query()`: empty, shorter than two characters, an odd number of double quotes, or more than 30% special characters (error code `SEARCH001`);
- `pageSize` is outside 1 to 1000 (`SEARCH002`);
- `format` is not a supported value (`SEARCH004`);
- the request fails, including HTTP error responses (for example `NET001`).

The error code is available as `error.error_code`. All exceptions raised by the package derive from `PyEuropePMCError` in `pyeuropepmc.core.exceptions`. `search_all()` and `search_ids_only()` do not raise on request failures, as described above.

## See also

- [SearchClient API reference](../../api/search-client.md)
- [Query builder](../query-builder-load-save-translate.md)
- [Multi-source search](../multi-source-search.md)
- [Caching](../caching/README.md)
