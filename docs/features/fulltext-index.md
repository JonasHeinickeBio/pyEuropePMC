# Full-Text Indexing (SQLite FTS5)

Local full-text search of paper collections using SQLite FTS5.

## Basic Usage

```python
from pyeuropepmc.processing import FullTextIndex, IndexEntry

# Create an in-memory index
index = FullTextIndex(":memory:")

# Add a paper
entry = IndexEntry(
    doi="10.1000/example",
    pmid="12345678",
    title="My Research Paper",
    authors="Smith, John; Doe, Jane",
    abstract="This paper discusses biomarkers for chronic fatigue syndrome...",
    year=2025,
    journal="Journal of Medical Research",
)
index.add(entry)
```

## Searching

```python
# Search with FTS5 full-text syntax
results = index.search("biomarkers")
print(f"Found {results['count']} matches")
for hit in results["results"]:
    print(f"  {hit.title} — {hit.snippet}")
```

### Search Syntax

FTS5 supports rich query syntax:

```python
# Phrase search
results = index.search('"chronic fatigue syndrome"')

# Prefix wildcard
results = index.search("biomarker*")

# Boolean
results = index.search("biomarkers AND fatigue")

# Column-specific
results = index.search("title:CRISPR")
```

## Adding Multiple Papers

```python
entries = [
    IndexEntry(doi="10.1000/1", title="Paper 1", abstract="..."),
    IndexEntry(doi="10.1000/2", title="Paper 2", abstract="..."),
]
index.add_many(entries)
```

## Results with Snippets

Search results include highlighted snippets:

```python
results = index.search("chronic fatigue")
for hit in results["results"]:
    print(f"DOI: {hit.doi}")
    print(f"Title: {hit.title}")
    print(f"Score: {hit.rank}")
    print(f"Snippet: {hit.snippet}")  # FTS5 highlighted excerpt
```

## Lookup by Identifier

```python
# By DOI
entry = index.get_by_doi("10.1000/example")

# By PMID
entry = index.get_by_pmid("12345678")
```

## Update and Delete

```python
# Update an existing entry
index.update("10.1000/example", title="Updated Title")

# Delete
index.delete("10.1000/example")

# Clear entire index
index.clear()
```

## Statistics

```python
stats = index.stats()
print(stats)
# {
#     "total_entries": 100,
#     "total_tokens": 50000,
#     "memory_usage": "1.2 MB",
#     "last_updated": "2026-07-17T12:00:00",
# }
```

## Context Manager

```python
# Auto-close on exit
with FullTextIndex(":memory:") as idx:
    idx.add(IndexEntry(doi="10.1000/1", title="Example", abstract="..."))
    results = idx.search("Example")
```

## From LiteratureResult

```python
from pyeuropepmc.models import LiteratureResult

result = LiteratureResult(
    title="My Paper",
    doi="10.1000/example",
    authors=[{"name": "Smith, J"}],
    abstract="A paper about biomarkers",
)

entry = IndexEntry.from_literature_result(result)
index.add(entry)
```

## Disk Persistence

```python
# File-based index persists across sessions
index = FullTextIndex("my_literature_index.db")
index.add(IndexEntry(doi="10.1000/1", title="Paper", abstract="..."))

# Re-open later
index = FullTextIndex("my_literature_index.db")
results = index.search("Paper")  # Previous data still there!
```

## Performance

- FTS5 full-text search is highly optimized — sub-millisecond queries on 10K+ entries
- Index building is linear in the number of entries
- Memory-mapped database files for low memory overhead
- Concurrent readers supported
