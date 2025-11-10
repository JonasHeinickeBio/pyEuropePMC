# Quick Start Guide

This guide will get you up and running with PyEuropePMC in minutes.

## Installation

```bash
pip install pyeuropepmc
```

## Basic Usage

### Simple Search

```python
from pyeuropepmc import EuropePMC

# Initialize the client
client = EuropePMC()

# Search for articles about cancer
results = client.search(query="cancer", limit=10)

# Print article titles
for article in results:
    print(article.title)
```

### Advanced Search with QueryBuilder

```python
from pyeuropepmc import QueryBuilder

# Build complex queries with type safety
qb = QueryBuilder()

# Simple query
query = qb.keyword("machine learning").build()
print(f"Query: {query}")  # "machine learning"

# Complex query with multiple conditions
complex_query = (qb
    .keyword("cancer", field="title")
    .and_()
    .keyword("therapy")
    .and_()
    .date_range(start_year=2020, end_year=2023)
    .and_()
    .citation_count(min_count=10)
    .build())

print(f"Complex query: {complex_query}")
# "(TITLE:cancer) AND therapy AND (PUB_YEAR:[2020 TO 2023]) AND (CITED:[10 TO *])"
```

### Advanced Search

```python
# Search with filters
results = client.search(
    query="machine learning",
    source="MED",
    sort="date",
    limit=20,
    format="json"
)

# Access article metadata
for article in results:
    print(f"Title: {article.title}")
    print(f"Authors: {', '.join(article.authors)}")
    print(f"DOI: {article.doi}")
    print(f"Publication Year: {article.pub_year}")
    print("---")
```

## Supported Formats

- JSON
- XML
- Dublin Core


### Using Context Manager

```python
with EuropePMC() as client:
    results = client.search("CRISPR", limit=5)
    for article in results:
        print(article.title)
```

## Next Steps

- Read the [API Reference](../api/) for detailed documentation
- Learn about [Query Builder](../features/query-builder-load-save-translate.md) for advanced query construction
- Check out [Examples](../examples/) for more use cases
- See [Advanced Usage](../advanced/) for complex scenarios

## Getting Help

- Check the [FAQ](faq.md)
- Browse [Examples](examples/README.md)
- Visit our [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
