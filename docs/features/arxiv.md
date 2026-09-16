# arXiv client

`ArxivClient` searches arXiv preprints through the arXiv API and returns `LiteratureResult` records. The API needs no key or registration.

## Search

```python
from pyeuropepmc.features.search import ArxivClient

with ArxivClient() as client:
    papers = client.search("machine learning", limit=10)

for paper in papers:
    print(paper.source_id, paper.publication_year, paper.title)
```

`search(query, limit=25, sort=None, **kwargs) -> list[LiteratureResult]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | arXiv query, sent unchanged as `search_query` |
| `limit` | `int` | `25` | Maximum records; capped at 2000 |
| `sort` | `str` or `None` | `None` | `"relevance"`, `"date"` (submission date) or `"title"`; `None` leaves the order to arXiv |
| `id_list` | `str` | not sent | Comma-separated arXiv IDs to look up |

Other keyword arguments are ignored without a warning.

## Fields and subject categories

Queries use arXiv's own syntax: prefixes such as `ti:` (title), `au:` (author), `abs:` (abstract), `cat:` (subject category) and `all:`, combined with `AND`, `OR` and `ANDNOT`. To restrict a search to subject categories, put `cat:` terms in the query:

```python
from pyeuropepmc.features.search import ArxivClient

with ArxivClient() as client:
    papers = client.search(
        'all:"quantum computing" AND (cat:cs.AI OR cat:cs.LG)',
        limit=20,
        sort="date",
    )

print(len(papers))
```

There is no `categories` argument: `search("quantum computing", categories="cs.AI")` searches all categories. The syntax is described in the [arXiv API user manual](https://info.arxiv.org/help/api/user-manual.html). Through `UnifiedSearch`, a query without arXiv prefixes is sent as `all:"<query>"`.

## Get a paper

```python
from pyeuropepmc.features.search import ArxivClient

with ArxivClient() as client:
    by_id = client.get_paper("2101.12345")
    by_doi = client.get_paper("10.48550/arXiv.2101.12345")
    by_url = client.get_paper("https://arxiv.org/abs/2101.12345")

print(by_id.title if by_id else "not found")
```

`get_paper(identifier) -> LiteratureResult | None` accepts an arXiv ID, an ID with an `arxiv:` prefix, an abstract URL or an arXiv DOI (`10.48550/arXiv.<id>`).

## Result fields

| Field | Content |
|---|---|
| `source` | `"arxiv"` |
| `source_id` | arXiv ID without the version suffix, for example `2101.12345` |
| `title`, `abstract` | Entry title and summary |
| `authors` | `Author` objects with names in `Last, First` form |
| `publication_year` | Year of the first version |
| `doi` | DOI of the published version, when the authors added one |
| `journal` | Journal reference, when present |

Subject categories are not included in the results.

## Rate limit

`ArxivClient(rate_limit_delay=3.0, timeout=30, cache_config=None)` waits 3 seconds between requests, following arXiv's request to send at most one request every three seconds. `UnifiedSearch` replaces this with its own `rate_limit_delay`, 1.2 seconds by default; use `UnifiedSearch(rate_limit_delay=3.0)` when arXiv is one of the sources.

## See also

- [Multi-source search](multi-source-search.md)
