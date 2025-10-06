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

- Read the [API Reference](api/README.md) for detailed documentation
- Check out [Examples](examples/README.md) for more use cases
- See [Advanced Usage](advanced/README.md) for complex scenarios

## Getting Help

- Check the [FAQ](faq.md)
- Browse [Examples](examples/README.md)
- Visit our [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
