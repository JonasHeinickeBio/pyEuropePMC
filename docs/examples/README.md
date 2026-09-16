# Examples

This page collects short recipes for common tasks and lists the longer scripts and notebooks in the repository's `examples/` folder. Each recipe is self-contained: copy it into a file or a notebook cell and run it.

## Recipes

### Search and read the results

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search('"gene editing" AND SRC:MED', pageSize=25, sort="CITED desc")

for paper in results["resultList"]["result"]:
    print(f"{paper.get('pubYear')}  {paper['title']}  ({paper.get('authorString', '')})")
```

`authorString` is one comma-separated string, not a list.

### Collect every result

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("bioinformatics AND PUB_YEAR:2024", page_size=500, max_results=2000)

print(f"Collected {len(papers)} records")
```

### Count publications per year

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    for year in range(2019, 2025):
        count = client.get_hit_count(f'"deep learning" AND PUB_YEAR:{year}')
        print(year, count)
```

### Build queries with QueryBuilder

Use a new `QueryBuilder` for each query.

```python
from pyeuropepmc import QueryBuilder

by_author = QueryBuilder().field("author", "Smith J").build()
synonyms = QueryBuilder().keyword("machine learning").or_().keyword("artificial intelligence").build()
diseases = QueryBuilder().keyword("cancer").or_().keyword("tumor")
combined = QueryBuilder().group(diseases).and_().field("open_access", True).build()

print(by_author)  # AUTH:"Smith J"
print(synonyms)
print(combined)
```

Saving, loading and translating queries is covered in [Query Builder](../features/query-builder-load-save-translate.md).

### Get citations and references for an article

```python
from pyeuropepmc import ArticleClient

with ArticleClient() as client:
    details = client.get_article_details("MED", "8521067")
    citing = client.get_citations("MED", "8521067", page_size=100)
    cited = client.get_references("MED", "8521067", page_size=100)
    n_citing = client.get_citation_count("MED", "8521067")

print(details["result"]["title"])
print(n_citing, "citing articles")
for item in citing.get("citationList", {}).get("citation", [])[:5]:
    print("cited by:", item.get("title"))
for item in cited.get("referenceList", {}).get("reference", [])[:5]:
    print("cites:", item.get("title"))
```

### Download full text and extract tables

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

with FullTextClient() as client:
    xml = client.get_fulltext_content("PMC3359999")

parser = FullTextXMLParser(xml)
for table in parser.extract_tables():
    print(table["label"], "-", (table["caption"] or "")[:60])
    print("   columns:", table["headers"])
    print("   rows:", len(table["rows"]))

print(len(parser.extract_references()), "references")
```

### Save search results as a table

This recipe needs the `analytics` extra: `pip install "pyeuropepmc[analytics]"`.

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    papers = client.search_all("CRISPR AND PUB_YEAR:2024", page_size=100, max_results=200)
    df = client.export_results(papers, format="dataframe")

print(df.columns.tolist()[:8])
df.to_csv("crispr_2024.csv", index=False)
```

### Retry after a failed request

```python
import time

from pyeuropepmc import SearchClient
from pyeuropepmc.core.exceptions import PyEuropePMCError


def search_with_retries(query, attempts=3):
    with SearchClient() as client:
        for attempt in range(1, attempts + 1):
            try:
                return client.search(query, pageSize=100)
            except PyEuropePMCError as err:
                if not err.is_retryable() or attempt == attempts:
                    raise
                print(f"[{err.error_code.value}] attempt {attempt} failed; retrying")
                time.sleep(2**attempt)


results = search_with_retries("malaria vaccine")
print(results["hitCount"])
```

The client already retries failed requests with backoff before it raises; this loop adds longer waits on top. [Error codes](../reference/error-codes.md) lists which codes are retryable.

## Scripts and notebooks in the repository

The `examples/` folder holds longer scripts and Jupyter notebooks. They are not published with these pages, so the links open GitHub.

| Folder | What it shows |
|---|---|
| [01-getting-started](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/01-getting-started) | A first notebook with basic searches |
| [02-search-client](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/02-search-client) | Search queries, logging and search with caching |
| [03-article-client](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/03-article-client) | Article metadata, citations and references |
| [04-fulltext-parser](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/04-fulltext-parser) | Parsing full-text XML and configuring the parser |
| [05-ftp-downloader](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/05-ftp-downloader) | Bulk and batch downloads |
| [06-caching](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/06-caching) | Caching for one client and for all clients |
| [07-advanced](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/07-advanced) | Caching with progress reporting, and a knowledge-graph readiness demo |
| [07-advanced-analytics](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/07-advanced-analytics) | Publication analytics |
| [07-advanced-filtering](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/07-advanced-filtering) | Filtering search results |
| [07-advanced-parsing](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/07-advanced-parsing) | Advanced parsing, progress callbacks and schema coverage |
| [07-advanced-pipelines](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/07-advanced-pipelines) | End-to-end pipelines, including a Long COVID case study |
| [08-query-builder](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/08-query-builder) | QueryBuilder, field validation, saving and translating queries, and systematic review tracking |
| [09-enrichment](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/09-enrichment) | Metadata enrichment, including RDF output |
| [10-annotations](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/10-annotations) | Europe PMC text-mining annotations and their conversion to RDF |
| [10-rdf-mapping](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/10-rdf-mapping) | Data models, RDF conversion and knowledge-graph structure |
| [10-semantic-scholar](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/10-semantic-scholar) | The Semantic Scholar enrichment client |
| [11-semantic-scholar-pro](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/11-semantic-scholar-pro) | `ProfessionalSemanticScholarClient`, the wrapper around the `semanticscholar` library: paper and author lookups, bulk search and rate limiting |
