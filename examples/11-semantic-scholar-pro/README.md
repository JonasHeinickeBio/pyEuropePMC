# Professional Semantic Scholar Integration

This directory contains examples for using the professional `danielnsilva/semanticscholar v0.12.0` library.

## Quick Start

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

# Configure with API key (optional but recommended)
client = ProfessionalSemanticScholarClient(
    api_key="your-api-key",
    rate_limit_delay=1.0
)

# Get a paper with typed response
paper = client.get_paper("10.1038/nature12373")
print(f"Title: {paper.title}")
print(f"Authors: {len(paper.authors)}")

# Bulk search (faster, up to 10M results)
results = client.search_paper("cancer", bulk=True, limit=50)

# Regular search with relevance ranking
results = client.search_paper("machine learning", bulk=False, limit=100)
```

## Examples

### 1. Typed Paper Retrieval

Get a paper with full typed response objects:

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()

# Get paper by DOI
paper = client.get_paper("10.1038/nature12373")

print(f"Title: {paper.title}")
print(f"Authors: {len(paper.authors)}")
print(f"Citation count: {paper.citation_count}")
print(f"Year: {paper.year}")
print(f"Fields of study: {paper.fields_of_study}")

# Access author objects
for author in paper.authors:
    print(f"  - {author.name} ({author.author_id})")
```

### 2. Bulk Search Operations

Search large result sets efficiently:

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()

# Bulk search (fast, no relevance ranking, up to 10M results)
results = client.search_paper("cancer immunotherapy", bulk=True, limit=500)

# Convert to list for iteration
papers = list(results)

print(f"Found {len(papers)} papers")

# Process results
for i, paper in enumerate(papers[:10]):
    print(f"{i+1}. {paper.get('title', 'N/A')}")
    print(f"   Citations: {paper.get('citation_count', 'N/A')}")
```

### 3. Author and Venue Information

Get detailed author and venue data:

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()

# Get author by ID
author = client.get_author("1724609")
print(f"Author: {author.name}")
print(f"Paper count: {author.paper_count}")
print(f"H-index: {author.h_index}")

# Get venue by ID
venue = client.get_venue("12345")
print(f"Venue: {venue.name}")
print(f"Paper count: {venue.paper_count}")
```

### 4. Advanced Search with Filters

Combine multiple filters for precise results:

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()

# Search with filters
results = client.search_paper(
    query="cancer",
    year="2023",
    publication_types=["journal-article"],
    min_citation_count=10,
    limit=100
)

papers = list(results)
print(f"Found {len(papers)} papers")
```

### 5. Enrichment with Multiple APIs

Combine Semantic Scholar with other enrichment sources:

```python
from pyeuropepmc import PaperEnricher, EnrichmentConfig

# Configure enrichment
config = EnrichmentConfig(
    enable_crossref=True,
    enable_semantic_scholar=True,
    enable_openalex=True,
    enable_unpaywall=True,
    rate_limit_delay=1.0
)

with PaperEnricher(config) as enricher:
    # Enrich a paper with multiple sources
    result = enricher.enrich_paper(doi="10.1038/nature12373")

    # Access merged data
    print(f"Title: {result['merged']['title']}")
    print(f"Citation count (max): {result['merged']['citation_count']}")
    print(f"Open access: {result['merged'].get('open_access_status', 'N/A')}")
```

## Migration Guide

### From Old API Wrapper

**Old code:**
```python
from pyeuropepmc.enrichment import SemanticScholarClient

client = SemanticScholarClient()
results = client.search_paper("cancer")
```

**New code:**
```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()
results = client.search_paper("cancer", bulk=False)  # explicit
```

### Benefits of Migration

1. ✅ **Typed responses** - `Paper`, `Author`, `Venue` objects with full IDE support
2. ✅ **Faster search** - Bulk endpoint for 10M+ results
3. ✅ **Better async** - Native async/await support
4. ✅ **Consistent API** - More predictable behavior

## API Reference

### ProfessionalSemanticScholarClient

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_paper(paper_id, fields=None)` | `paper_id` (DOI, S2PaperId, or paper ID) | `Paper` object |
| `search_paper(query, bulk=False, ...)` | `query`, `limit`, `year`, `fields`, etc. | `PaginatedResults` |
| `search_papers(query, bulk=False, ...)` | Same as `search_paper` | `list[dict]` |
| `get_author(author_id, fields=None)` | `author_id` | `Author` object |
| `get_venue(venue_id, fields=None)` | `venue_id` | `Venue` object |

### Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query string |
| `bulk` | bool | Use bulk endpoint (default: `False`) |
| `limit` | int | Maximum results (default: 100) |
| `year` | str | Restrict to publication year |
| `publication_types` | list | Restrict to publication types |
| `min_citation_count` | int | Minimum citation count filter |

## Best Practices

1. **Use API keys** - Higher rate limits (300 req/5 min vs 100 req/5 min)
2. **Use `bulk=True`** for large searches - Minimizes API calls
3. **Enable caching** - Reduces redundant API calls
4. **Handle missing data** - Some fields may be `None`
5. **Check rate limits** - Monitor response headers for rate limit status
