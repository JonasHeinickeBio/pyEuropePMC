# pyEuropePMC

pyEuropePMC is a Python library for searching Europe PMC, downloading full-text articles and turning their JATS XML into structured data. This page shows the first three things most people do with it and where to read next.

## What it does

- **Search:** query Europe PMC with its search syntax or with `QueryBuilder`, and page through large result sets.
- **Full text:** download XML, PDF and HTML for open-access articles, one at a time or in batches, and bulk PDF packages from the Europe PMC FTP site.
- **Parsing:** extract metadata, sections, tables, figures and references from JATS XML with `FullTextXMLParser`.
- **Multi-source search:** search Europe PMC together with PubMed, arXiv, OpenAlex, Semantic Scholar and other services through `UnifiedSearch`, with duplicates merged.
- **Enrichment:** add metadata from CrossRef, OpenAlex, Semantic Scholar, Unpaywall and other services.
- **Analysis:** publication statistics and plots (with the `analytics` and `visualization` extras) and RDF export for knowledge graphs.
- **Systematic reviews:** search logs that record each query, its filters and its result count.
- **Command line and MCP:** the `pyeuropepmc` command and the `pyeuropepmc-mcp` server for MCP clients.

## Install

```bash
pip install pyeuropepmc
```

pyEuropePMC supports Python 3.10–3.13. The base install covers search, full text, parsing, the command line and the MCP server. Analytics, plots, Excel export, JSON-LD, LLM agents and some enrichment clients need extras, for example `pip install "pyeuropepmc[analytics]"`. See [Installation](getting-started/installation.md) for the full list.

## Search

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR gene editing", pageSize=10)

print(results["hitCount"])
for paper in results["resultList"]["result"]:
    print(paper["title"], paper.get("pubYear"))
```

`search()` returns the Europe PMC response as a dictionary; the records are in `results["resultList"]["result"]`.

## Build a query

```python
from pyeuropepmc import QueryBuilder, SearchClient

query = (
    QueryBuilder()
    .keyword("CRISPR")
    .and_()
    .date_range(start_year=2020, end_year=2024)
    .and_()
    .field("open_access", True)
    .build()
)
print(query)  # CRISPR AND (PUB_YEAR:[2020 TO 2024]) AND OPEN_ACCESS:y

with SearchClient() as client:
    results = client.search(query, pageSize=50)
```

## Download and parse full text

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

with FullTextClient() as client:
    xml = client.get_fulltext_content("PMC3258128")  # JATS XML as a string

parser = FullTextXMLParser(xml)
print(parser.extract_metadata()["title"])
for section in parser.get_full_text_sections_structured()[:3]:
    print(section["section_type"], section["title"])
```

## Where to go next

| Section | What it covers |
|---|---|
| [Getting started](getting-started/README.md) | Installation, a quick start and the FAQ |
| [Examples](examples/README.md) | Short recipes and the example scripts in the repository |
| [Features](features/README.md) | Search, full text, parsing, caching and the other features |
| [API reference](api/README.md) | Classes, methods, exceptions and configuration |
| [Error codes](reference/error-codes.md) | What each error code means and how to fix it |
| [Advanced](advanced/README.md) | Caching internals, search logging and progress callbacks |
| [Development](development/README.md) | Contributing, tests, CI and releases |

If you are upgrading from 1.x, read [Migrating from 1.x to 2.0](migration/v1-to-v2.md) first.

## Links

- [Europe PMC](https://europepmc.org/)
- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [Source code on GitHub](https://github.com/JonasHeinickeBio/pyEuropePMC)
- [Package on PyPI](https://pypi.org/project/pyeuropepmc/)

pyEuropePMC is released under the MIT License.
