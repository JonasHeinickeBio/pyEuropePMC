# Citation Graph Walking

PyEuropePMC provides citation graph traversal for systematic reviews and literature exploration through the `CitationWalker`.

## Snowballing

Citation snowballing is the process of following citation chains forward (papers that cite a given paper) and backward (references cited by a paper).

```python
from pyeuropepmc.literature import CitationWalker, SnowballingStrategy

walker = CitationWalker()
```

### Forward Snowballing

Find papers that cite a given paper:

```python
# Forward snowballing (cited-by)
results = walker.snowball(
    identifier="32791984",
    strategy=SnowballingStrategy.FORWARD,
    max_papers=200,
)
print(f"Found {len(results)} citing papers")
```

### Backward Snowballing

Find papers referenced by a paper:

```python
# Backward snowballing (references)
results = walker.snowball(
    identifier="32791984",
    strategy=SnowballingStrategy.BACKWARD,
    max_papers=200,
)
print(f"Found {len(results)} references")
```

### Both Directions

```python
# Both forward and backward
results = walker.snowball(
    identifier="32791984",
    strategy=SnowballingStrategy.BOTH,
    max_papers=500,
)
print(f"Found {len(results)} papers in citation graph")
```

## Deep Snowballing (Recursive)

The `max_depth` parameter controls how many levels deep the snowballing goes:

```python
# Two levels deep: find papers that cite, and papers that cite those
results = walker.snowball(
    identifier="32791984",
    strategy=SnowballingStrategy.FORWARD,
    max_depth=2,
    max_papers=500,
)
```

## Filtering

### By Minimum Citations

Filter results to only include highly-cited papers:

```python
results = walker.snowball(
    identifier="32791984",
    strategy=SnowballingStrategy.FORWARD,
    min_citations=10,  # Only papers with 10+ citations
)
```

## Low-Level API

If you don't need recursive traversal:

```python
# Get papers that cite this one
citations = walker.get_citations(identifier="32791984")
for paper in citations:
    print(f"{paper.title} — cited by {paper.citation_count}")

# Get references cited by this paper
references = walker.get_references(identifier="32791984")
for paper in references:
    print(f"{paper.title}")
```

## Deduplication

Results from citation walking are automatically deduplicated:

```python
results = walker.snowball(
    identifier="32791984",
    strategy=SnowballingStrategy.FORWARD,
)
# No duplicate papers — the internal LiteratureMerger handles it
```

## Identifiers

You can use any of these identifier types:

```python
# PMID
walker.snowball(identifier="32791984")

# DOI
walker.snowball(identifier="10.1186/s13643-022-02045-9")

# arXiv ID
walker.snowball(identifier="2101.12345")
```

The CitationWalker uses the Semantic Scholar API under the hood, which cross-references multiple identifier systems.
