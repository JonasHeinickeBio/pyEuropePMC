# Citation graph walking

This page covers two ways to follow citations from a known article: Europe PMC's citation and reference lists, and `CitationWalker`, which is designed to snowball through the Semantic Scholar citation graph.

> **Known limitation:** `CitationWalker` currently returns no papers when it queries the live Semantic Scholar API. Its seed lookup returns a record without the `paperId` key the walker reads, and it reads citation and reference pages from `citations` and `references` keys, while the Semantic Scholar Graph API returns them under `data` as `citingPaper` and `citedPaper` entries. Use the Europe PMC route below until this is fixed.

## Citations and references from Europe PMC

[`ArticleClient`](../api/article-client.md) returns the records that cite an article (forward) and the article's reference list (backward) for records indexed by Europe PMC:

```python
from pyeuropepmc import ArticleClient

with ArticleClient() as client:
    citing = client.get_citations("MED", "32791984", page_size=100)
    references = client.get_references("MED", "32791984", page_size=100)

print(f"Cited by {citing['hitCount']} records")
for item in citing.get("citationList", {}).get("citation", []):
    print("  cited by:", item["source"], item["id"], item.get("title"))
for item in references.get("referenceList", {}).get("reference", []):
    print("  cites:", item.get("source"), item.get("id"), item.get("title"))
```

A two-hop forward snowball collects the records that cite the seed, then the records that cite each of those:

```python
from pyeuropepmc import ArticleClient


def citing_records(client, source, article_id):
    response = client.get_citations(source, article_id, page_size=1000)
    return response.get("citationList", {}).get("citation", [])


found = {}
with ArticleClient() as client:
    first_hop = citing_records(client, "MED", "32791984")
    for record in first_hop:
        found[(record["source"], record["id"])] = record
    for record in first_hop[:10]:  # limit the second hop to ten records
        for citing in citing_records(client, record["source"], record["id"]):
            found.setdefault((citing["source"], citing["id"]), citing)

print(f"{len(found)} records within two citation steps")
```

A page holds at most 1000 records; see [ArticleClient](../api/article-client.md#collect-every-citing-record) for paging. To filter citing records, search with the `CITES:` field:

```python
from pyeuropepmc import QueryBuilder, SearchClient

query = QueryBuilder().cites("32791984", source="med").and_().date_range(2022, 2024).build()
print(query)  # CITES:32791984_med AND (PUB_YEAR:[2022 TO 2024])

with SearchClient() as client:
    recent_citing = client.search_all(query, max_results=200)

print(len(recent_citing))
```

## CitationWalker

```python
from pyeuropepmc.features.citations.walker import CitationWalker, SnowballingStrategy
```

`CitationWalker(rate_limit_delay=1.0, timeout=30, cache_config=None, api_key=None, skip_dedup=False, dedup_mode=DedupMode.BALANCED)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rate_limit_delay` | `float` | `1.0` | Seconds to wait after each Semantic Scholar request |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `cache_config` | `CacheConfig` or `None` | `None` | Cache for the seed lookup |
| `api_key` | `str` or `None` | `None` | Semantic Scholar API key |
| `skip_dedup` | `bool` | `False` | Return the collected papers without deduplication |
| `dedup_mode` | `DedupMode` | `DedupMode.BALANCED` | Mode for the internal [LiteratureMerger](dedup.md) |

### snowball

`snowball(identifier, strategy="forward", max_papers=100, max_depth=1, min_citations=0) -> tuple[list[LiteratureResult], MergeReport]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `identifier` | `str` | required | Semantic Scholar paper ID, or a prefixed identifier such as `"DOI:10.1038/s41586-020-2649-2"`, `"PMID:32791984"` or `"ARXIV:2101.12345"` |
| `strategy` | `str` | `"forward"` | `SnowballingStrategy.FORWARD` (citing papers), `BACKWARD` (references) or `BOTH` |
| `max_papers` | `int` | `100` | Stop after collecting this many papers |
| `max_depth` | `int` | `1` | Recursion depth as implemented: `0` follows one step, the default `1` follows two, and each increment adds one more |
| `min_citations` | `int` | `0` | Papers with fewer citations are dropped and not followed further |

The identifier is passed to Semantic Scholar unchanged; if the lookup fails, the walker uses the first result of a keyword search for the string. The method returns a tuple, so unpack it. Unless `skip_dedup=True`, the papers are deduplicated with `LiteratureMerger` and `report` is its [MergeReport](dedup.md#mergereport). Papers are `LiteratureResult` records with `source="semanticscholar"`.

```python
from pyeuropepmc.features.citations.walker import CitationWalker, SnowballingStrategy

walker = CitationWalker()
papers, report = walker.snowball(
    "DOI:10.1038/s41586-020-2649-2",
    strategy=SnowballingStrategy.BOTH,
    max_papers=50,
)
print(len(papers), report.summary())
```

`get_citations(identifier, limit=100)` and `get_references(identifier, limit=100)` return the paper list of a forward or backward `snowball()` with the default depth.

## See also

- [ArticleClient API reference](../api/article-client.md)
- [Deduplication](dedup.md)
