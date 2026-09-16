# Getting started

This section takes you from installation to a first search, a downloaded full-text article and parsed XML. Work through the pages in order; each takes a few minutes.

## Before you start

- Python 3.10, 3.11, 3.12 or 3.13
- `pip`, or Poetry if you want to work on pyEuropePMC itself
- No account or API key: the Europe PMC API is open

## Steps

1. [Installation](installation.md): install the package and the extras you need.
2. [Quick start](quickstart.md): search, page through results, download and parse full text, and handle errors.
3. [Examples](../examples/README.md): short recipes for common tasks.
4. [FAQ](faq.md): answers to common questions and problems.

A first search looks like this:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR", pageSize=10)

print(f"Found {results['hitCount']} papers")
```

## Next

- [Features](../features/README.md): what each part of the library does
- [API reference](../api/README.md): classes, methods and exceptions
- [Migrating from 1.x to 2.0](../migration/v1-to-v2.md), if you used an earlier version
- [GitHub issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues), for bugs and questions
