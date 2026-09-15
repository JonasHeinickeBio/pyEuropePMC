# Features

This page gives an overview of what pyEuropePMC does, with a short example for each main feature and three workflows that combine them. Each section links to the page that covers the feature in detail.

## Search

Query Europe PMC with its search syntax: Boolean operators, fields such as `TITLE:` and `AUTH:`, date ranges, sorting and cursor-based paging for large result sets. Responses come back as JSON dicts, XML or Dublin Core.

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("cancer AND therapy", pageSize=50, sort="CITED desc")

print(results["hitCount"])
```

More: [Search](search/README.md).

## Full-text retrieval

Download XML, PDF and HTML for open-access articles, one at a time or in batches with progress callbacks. `FTPDownloader` fetches PDF packages in bulk from the Europe PMC FTP site.

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    pdf_path = client.download_pdf_by_pmcid("PMC3258128", output_path="PMC3258128.pdf")
    xml_path = client.download_xml_by_pmcid("PMC3258128", output_path="PMC3258128.xml")
    xml_text = client.get_fulltext_content("PMC3258128")

print(pdf_path, xml_path, len(xml_text))
```

The `download_*` methods return the path of the saved file; `get_fulltext_content()` returns the XML as a string. More: [Full-text retrieval](fulltext/README.md).

## XML parsing

`FullTextXMLParser` reads JATS XML and extracts metadata, tables, figures, references and sections, converts the article to plain text or Markdown, and reports which XML elements it recognised.

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

with FullTextClient() as client:
    xml = client.get_fulltext_content("PMC3359999")

parser = FullTextXMLParser(xml)
metadata = parser.extract_metadata()
tables = parser.extract_tables()
markdown = parser.to_markdown()
coverage = parser.validate_schema_coverage()

print(metadata["title"], len(tables))
print(f"Coverage: {coverage['coverage_percentage']:.1f}%")
```

`to_markdown()` does not escape Markdown characters that occur in the article text. More: [XML parsing](parsing/README.md) and [JATS normalization](parsing/jats-normalization.md).

## Query builder

`QueryBuilder` builds query strings from named fields (more than 150 field names), checks operator placement, and saves, loads and translates queries.

```python
from pyeuropepmc import QueryBuilder

query = (
    QueryBuilder()
    .keyword("cancer", field="title")
    .and_()
    .citation_count(min_count=50)
    .and_()
    .date_range(start_year=2020)
    .build()
)
print(query)  # TITLE:cancer AND (CITED:[50 TO *]) AND (PUB_YEAR:[2020 TO <current year>])
```

A `date_range()` without `end_year` ends at the year in which the query is built, so a saved query does not cover later years. `QueryBuilder(validate=True)` runs the search-query package's checks when you call `build()`, but these checks reject `PUB_YEAR` and `CITED` ranges and return other queries in PubMed syntax (for example `cancer[all] AND therapy[all]`), which Europe PMC does not accept; build Europe PMC queries without `validate=True`. More: [Query Builder](query-builder-load-save-translate.md) and the [QueryBuilder API](../api/query-builder.md).

## Systematic review tracking

A search log records each query, its filters and its result count, and saves them as JSON.

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search

log = start_search("Cancer Review", executed_by="Researcher")
qb = QueryBuilder().keyword("cancer").and_().field("open_access", True)
qb.log_to_search(log, filters={"open_access": True}, results_returned=100)
log.save("cancer_review_log.json")
```

More: [Systematic Review Tracking](systematic-review-tracking.md) and [Search logging](../advanced/search-logging.md).

## More features

| Feature | Page |
|---|---|
| Search Europe PMC, PubMed, arXiv, OpenAlex, Semantic Scholar and other services at once | [Multi-source search](multi-source-search.md) |
| Merge duplicate records from several sources | [Deduplication](dedup.md) |
| Follow citations forwards and backwards | [Citation graph walking](citation-walking.md) |
| ClinicalTrials.gov and arXiv clients | [ClinicalTrials.gov](clinical-trials.md) and [arXiv](arxiv.md) |
| ORCID profiles and NIH iCite citation metrics | [ORCID and NIH iCite clients](orcid.md) |
| Add metadata from CrossRef, OpenAlex, Semantic Scholar, Unpaywall and others | [Enrichment](../guides/enrichment.md) |
| Search downloaded full text locally with SQLite FTS5 | [Full-text indexing](fulltext-index.md) |
| Label sentences by rhetorical role | [Rhetorical highlighting](rhetorical-highlighting.md) |
| MeSH terms and PICO questions | [MeSH and PICO](mesh-pico.md) |
| Cache API responses and downloads | [Caching](caching/README.md) |

The `pyeuropepmc` command (`pyeuropepmc --help`) offers the `normalize`, `unified_search`, `claim` and `benchmark` command groups, and `pyeuropepmc-mcp` runs an MCP server for MCP clients.

## Feature comparison

| Capability | SearchClient | FullTextClient | FullTextXMLParser | FTPDownloader | QueryBuilder |
|---|---|---|---|---|---|
| Search Europe PMC | Yes | - | - | - | Builds queries |
| Download PDF | - | Yes | - | Yes, in bulk | - |
| Download XML and HTML | - | Yes | - | - | - |
| Parse XML | - | - | Yes | - | - |
| Batch downloads with progress callbacks | - | Yes | - | - | - |
| Response caching | Yes, when configured | Yes | - | - | - |
| Systematic review logging | - | - | - | - | Yes |

## Workflows

### Build a query, search, and parse the full text

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser, QueryBuilder, SearchClient

query = (
    QueryBuilder()
    .keyword("machine learning", field="title")
    .and_()
    .citation_count(min_count=25)
    .and_()
    .date_range(start_year=2020)
    .build()
)

with SearchClient() as search, FullTextClient() as fulltext:
    results = search.search(query, pageSize=20, sort="CITED desc")
    for paper in results["resultList"]["result"]:
        if paper.get("pmcid") and paper.get("isOpenAccess") == "Y":
            parser = FullTextXMLParser(fulltext.get_fulltext_content(paper["pmcid"]))
            print(parser.extract_metadata()["title"])
```

### Log a systematic review search

```python
from pyeuropepmc import QueryBuilder, SearchClient
from pyeuropepmc.utils.search_logging import start_search

log = start_search("ML in Biology Review", executed_by="Researcher Name")
qb = (
    QueryBuilder()
    .keyword("machine learning")
    .and_()
    .keyword("biology")
    .and_()
    .field("open_access", True)
    .and_()
    .date_range(start_year=2019)
)
query = qb.build()

with SearchClient() as client:
    results = client.search(query, pageSize=100)

qb.log_to_search(
    search_log=log,
    filters={"open_access": True, "date_range": "2019+"},
    results_returned=len(results["resultList"]["result"]),
    notes="Machine learning in biology",
)
log.save("systematic_review_log.json")
```

### Filter highly cited papers and extract their tables

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser, SearchClient

with SearchClient() as search:
    results = search.search("cancer AND (therapy OR treatment)", sort="CITED desc", pageSize=100, resultType="core")

high_impact = [
    paper
    for paper in results["resultList"]["result"]
    if paper.get("citedByCount", 0) > 20 and paper.get("pmcid") and paper.get("isOpenAccess") == "Y"
]

with FullTextClient() as fulltext:
    for paper in high_impact[:5]:
        parser = FullTextXMLParser(fulltext.get_fulltext_content(paper["pmcid"]))
        print(paper["pmcid"], len(parser.extract_tables()), "tables")
```

## Next

- [Getting started](../getting-started/README.md)
- [API reference](../api/README.md)
- [Examples](../examples/README.md)
- [Advanced topics](../advanced/README.md)
