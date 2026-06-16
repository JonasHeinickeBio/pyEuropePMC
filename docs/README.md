# PyEuropePMC

A comprehensive Python toolkit for searching, retrieving, and analyzing biomedical literature from Europe PMC.

## Overview

PyEuropePMC provides a powerful, type-safe interface to the Europe PMC database, offering advanced search capabilities, full-text content retrieval, XML parsing, and analytics tools for biomedical research.

### Key Capabilities

- **Search & Query** -- Advanced search with boolean operators, field-specific queries, and a fluent Query Builder API supporting 150+ searchable fields
- **Full-Text Retrieval** -- Download PDFs, XML, and HTML content from open-access articles with automatic endpoint fallback
- **XML Parsing** -- Extract structured data from JATS XML articles including metadata, sections, tables, figures, and references
- **Analytics & Visualization** -- Citation analysis, publication trends, quality metrics, and interactive dashboards
- **Systematic Reviews** -- PRISMA-compliant search logging, deduplication, and audit trails
- **Caching** -- Multi-layer caching with memory, disk, and HTTP backends for optimal performance
- **Knowledge Graph** -- RDF/Turtle export with RML mapping support for knowledge graph construction

## Quick Start

### Installation

```bash
pip install pyeuropepmc
```

### Basic Usage

```python
from pyeuropepmc.clients.search import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR gene editing", limit=10)
    for paper in results:
        print(f"{paper['title']} ({paper['pubYear']})")
```

### Query Builder

```python
from pyeuropepmc.query import QueryBuilder

query = (
    QueryBuilder()
    .keyword("CRISPR")
    .and_()
    .date_range("2020-01-01", "2024-12-31")
    .and_()
    .has_full_text()
    .and_()
    .open_access()
)

with SearchClient() as client:
    results = client.search(str(query), limit=50)
```

### Full-Text Download

```python
from pyeuropepmc.clients.fulltext import FullTextClient

with FullTextClient() as client:
    content = client.get_fulltext("PMC7512345")
    if content.xml:
        print(content.xml[:500])
```

## Documentation Structure

| Section | Description |
|---------|-------------|
| [Getting Started](getting-started/README.md) | Installation, quick start, and FAQ |
| [Features](features/README.md) | Search, full-text, parsing, and caching |
| [API Reference](api/README.md) | Complete method documentation |
| [Guides](guides/enrichment.md) | Enrichment and integration guides |
| [Advanced](advanced/README.md) | Caching, performance, and power features |
| [Reference](reference/models.md) | Data models and RDF mapping |
| [Development](development/README.md) | Contributing and development setup |
| [Examples](examples/README.md) | Working code samples |

## Requirements

- Python 3.10+
- Dependencies: `requests`, `pandas`, `lxml`, `tqdm`

## License

MIT License

## Links

- [Europe PMC](https://europepmc.org/) -- The underlying database
- [Europe PMC REST API](https://europepmc.org/RestfulWebService) -- Official API documentation
- [GitHub](https://github.com/JonasHeinickeBio/pyEuropePMC) -- Source code
- [PyPI](https://pypi.org/project/pyeuropepmc/) -- Package distribution
