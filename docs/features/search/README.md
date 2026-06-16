# Search Features

The **SearchClient** provides powerful querying capabilities for the Europe PMC database, allowing you to find scientific literature using advanced search syntax.

## Overview

- **Full-text search** across millions of papers
- **Advanced query syntax** with Boolean operators
- **Flexible filtering** by date, citation count, and more
- **Pagination** for large result sets
- **Automatic caching** for improved performance
- **Multiple output formats** (JSON, XML, Dublin Core)

## Quick Start

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    # Simple keyword search
    results = client.search("CRISPR gene editing")

    # Advanced search with filters
    results = client.search(
        query="cancer AND therapy",
        sort="CITED desc",
        pageSize=50,
        resultType="core"
    )

    # Process results
    for paper in results['resultList']['result']:
        print(f"{paper['title']} - {paper.get('citedByCount', 0)} citations")
```

## Search Query Syntax

### Basic Search

```python
# Single keyword
results = client.search("cancer")

# Multiple keywords (implicit AND)
results = client.search("cancer therapy")

# Phrase search (exact match)
results = client.search('"machine learning"')
```

### Boolean Operators

```python
# AND - both terms must appear
results = client.search("cancer AND therapy")

# OR - either term must appear
results = client.search("cancer OR tumor")

# NOT - exclude term
results = client.search("cancer NOT lung")

# Complex combinations
results = client.search("(cancer OR tumor) AND (therapy OR treatment) NOT surgery")
```

### Field-Specific Searches

Search specific metadata fields:

```python
# Author search
results = client.search("AUTH:Einstein")

# Title search
results = client.search("TITLE:relativity")

# Journal search
results = client.search("JOURNAL:Nature")

# Affiliation search
results = client.search("AFF:Stanford")

# Date range
results = client.search("PUB_YEAR:[2020 TO 2024]")

# Combine fields
results = client.search("AUTH:Smith AND TITLE:cancer AND PUB_YEAR:2023")
```

### Available Fields

| Field | Description | Example |
|-------|-------------|---------|
| `AUTH` | Author name | `AUTH:Einstein` |
| `TITLE` | Article title | `TITLE:cancer` |
| `JOURNAL` | Journal name | `JOURNAL:Nature` |
| `AFF` | Author affiliation | `AFF:Harvard` |
| `ABSTRACT` | Abstract text | `ABSTRACT:therapy` |
| `PUB_YEAR` | Publication year | `PUB_YEAR:2023` |
| `PMID` | PubMed ID | `PMID:12345678` |
| `PMCID` | PMC ID | `PMCID:PMC1234567` |
| `DOI` | Digital Object Identifier | `DOI:10.1038/...` |
| `GRANT_AGENCY` | Funding agency | `GRANT_AGENCY:NIH` |
| `GRANT_ID` | Grant number | `GRANT_ID:R01CA123456` |

## Filtering and Sorting

### Sort Options

```python
# By relevance (default)
results = client.search("cancer", sort="relevance")

# By citation count (descending)
results = client.search("cancer", sort="CITED desc")

# By publication date (newest first)
results = client.search("cancer", sort="P_PDATE_D desc")

# By publication date (oldest first)
results = client.search("cancer", sort="P_PDATE_D asc")
```

### Pagination

```python
# Set page size
results = client.search("cancer", pageSize=100)

# Get specific page
results = client.search("cancer", pageSize=50, cursorMark="*")

# Iterate through pages
cursor = "*"
while True:
    results = client.search("cancer", pageSize=100, cursorMark=cursor)

    # Process results
    for paper in results['resultList']['result']:
        print(paper['title'])

    # Check if more pages
    next_cursor = results.get('nextCursorMark')
    if not next_cursor or next_cursor == cursor:
        break
    cursor = next_cursor
```

### Result Types

```python
# Core metadata only (faster)
results = client.search("cancer", resultType="core")

# Include ID list
results = client.search("cancer", resultType="idlist")

# Lightweight results
results = client.search("cancer", resultType="lite")
```

## Advanced Examples

### Example 1: Highly Cited Papers

Find highly cited papers on a specific topic:

```python
with SearchClient() as client:
    results = client.search(
        query="CRISPR",
        sort="CITED desc",
        pageSize=20,
        resultType="core"
    )

    high_impact = [
        paper for paper in results['resultList']['result']
        if paper.get('citedByCount', 0) > 100
    ]

    for paper in high_impact:
        print(f"{paper['title']}")
        print(f"Citations: {paper['citedByCount']}")
        print(f"Year: {paper.get('pubYear', 'N/A')}")
        print("---")
```

### Example 2: Recent Papers from Specific Journal

```python
with SearchClient() as client:
    results = client.search(
        query='JOURNAL:"Nature" AND PUB_YEAR:[2023 TO 2024]',
        sort="P_PDATE_D desc",
        pageSize=50
    )

    for paper in results['resultList']['result']:
        print(f"{paper['title']} ({paper.get('pubYear')})")
```

### Example 3: Author Publication History

```python
with SearchClient() as client:
    results = client.search(
        query='AUTH:"Smith J"',
        sort="P_PDATE_D desc",
        pageSize=100
    )

    papers_by_year = {}
    for paper in results['resultList']['result']:
        year = paper.get('pubYear', 'Unknown')
        papers_by_year.setdefault(year, []).append(paper['title'])

    for year in sorted(papers_by_year.keys(), reverse=True):
        print(f"\n{year}: {len(papers_by_year[year])} papers")
```

### Example 4: Multi-Institutional Collaboration

```python
with SearchClient() as client:
    results = client.search(
        query='AFF:Harvard AND AFF:Stanford AND PUB_YEAR:2024',
        pageSize=50
    )

    print(f"Found {results['hitCount']} collaborative papers")
```

### Example 5: Grant-Funded Research

```python
with SearchClient() as client:
    results = client.search(
        query='GRANT_AGENCY:NIH AND cancer AND PUB_YEAR:[2020 TO 2024]',
        pageSize=100
    )

    for paper in results['resultList']['result']:
        grants = paper.get('grantsList', {}).get('grant', [])
        if grants:
            grant_ids = [g.get('grantId') for g in grants]
            print(f"{paper['title']}")
            print(f"Grants: {', '.join(grant_ids)}")
```

## Working with Results

### Result Structure

```python
results = client.search("cancer")

# Result overview
print(f"Total hits: {results['hitCount']}")
print(f"Page size: {results['request']['pageSize']}")

# Access individual papers
for paper in results['resultList']['result']:
    # Essential metadata
    title = paper['title']
    pmid = paper.get('pmid')
    pmcid = paper.get('pmcid')
    doi = paper.get('doi')

    # Publication info
    journal = paper.get('journalTitle')
    pub_year = paper.get('pubYear')
    pub_date = paper.get('firstPublicationDate')

    # Authors
    authors = paper.get('authorString', 'N/A')

    # Citations
    cited_by = paper.get('citedByCount', 0)

    # Abstract (if available)
    abstract = paper.get('abstractText', '')
```

### Filter Results

```python
results = client.search("cancer therapy", pageSize=100)

# Filter by citation count
high_impact = [
    p for p in results['resultList']['result']
    if p.get('citedByCount', 0) > 50
]

# Filter by publication year
recent = [
    p for p in results['resultList']['result']
    if p.get('pubYear', 0) >= 2020
]

# Filter for open access with PMC ID
open_access = [
    p for p in results['resultList']['result']
    if p.get('pmcid') and p.get('isOpenAccess') == 'Y'
]
```

## Large-Scale Search Operations

For processing thousands of papers, use these strategies:

### Bulk Search (Recommended for Semantic Scholar)

When using the Semantic Scholar enrichment client, use `bulk=True` for faster search:

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()

# Bulk search (fast, no relevance ranking, up to 10M results)
results = client.search_paper("cancer", bulk=True, limit=1000)

# Regular search with relevance ranking (slower for large result sets)
results = client.search_paper("cancer", bulk=False, limit=100)
```

### Europe PMC CursorMark Pagination

Efficient pagination for large result sets:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    cursor = "*"
    all_results = []

    # Get 10 pages of 100 results each
    for i in range(10):
        results = client.search("cancer", pageSize=100, cursorMark=cursor)

        # Process results
        all_results.extend(results['resultList']['result'])

        # Get next page
        next_cursor = results.get('nextCursorMark')
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    print(f"Total papers retrieved: {len(all_results)}")
```

### Batch Processing 1000+ Papers

```python
from pyeuropepmc import SearchClient

def process_papers_in_batches(query, batch_size=100, max_batches=10):
    with SearchClient() as client:
        cursor = "*"
        total_processed = 0

        for batch_num in range(max_batches):
            results = client.search(
                query=query,
                pageSize=batch_size,
                cursorMark=cursor,
                resultType="core"
            )

            papers = results['resultList']['result']
            if not papers:
                break

            # Process batch
            for paper in papers:
                # Your processing logic here
                process_paper(paper)
                total_processed += 1

            # Update cursor
            next_cursor = results.get('nextCursorMark')
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        return total_processed

# Usage
count = process_papers_in_batches("cancer immunotherapy")
print(f"Processed {count} papers")
```

### Performance Comparison

| Strategy | API Calls | Time for 1000 papers | Best For |
|----------|-----------|---------------------|----------|
| `pageSize=10` | 100 | ~100s | Testing |
| `pageSize=100` | 10 | ~20s | Default |
| `pageSize=500` | 2 | ~8s | Large datasets |
| `bulk=True` (SemSchol) | ~1 | ~5s | Semantic Scholar |

## Performance Tips

### 1. Use Caching

Caching is enabled by default and significantly speeds up repeated queries:

```python
with SearchClient() as client:
    # First call - hits API
    results1 = client.search("cancer")

    # Second call - from cache (instant)
    results2 = client.search("cancer")
```

### 2. Optimize Page Size

```python
# Too small - many API calls
results = client.search("cancer", pageSize=10)

# Optimal for most use cases
results = client.search("cancer", pageSize=100)

# Too large - slow response
results = client.search("cancer", pageSize=1000)
```

### 3. Use Specific Queries

```python
# Vague - many irrelevant results
results = client.search("cancer")

# Specific - fewer, better results
results = client.search("lung cancer AND immunotherapy AND PUB_YEAR:[2020 TO 2024]")
```

### 4. Request Only Needed Data

```python
# Full metadata (slower)
results = client.search("cancer", resultType="core")

# Minimal metadata (faster)
results = client.search("cancer", resultType="idlist")
```

## Rate Limiting

### SearchClient Rate Limiting

```python
from pyeuropepmc import SearchClient

with SearchClient(rate_limit_delay=1.0) as client:
    results = client.search("cancer")
```

### Europe PMC Rate Limits

| API | Free Tier Limit | With Authentication |
|-----|----------------|---------------------|
| Europe PMC | No strict limit | Register for API key |

### Best Practices
1. Use caching for repeated queries
2. Set appropriate `rate_limit_delay` based on your use case
3. Use larger `pageSize` to reduce total API calls
4. Implement retry logic for transient failures

## Error Handling

```python
from pyeuropepmc import SearchClient
from pyeuropepmc.exceptions import EuropePMCException

with SearchClient() as client:
    try:
        results = client.search("cancer", pageSize=100)

        if results['hitCount'] == 0:
            print("No results found")
        else:
            # Process results
            pass

    except EuropePMCException as e:
        print(f"API error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

## See Also

- **[API Reference: SearchClient](../../api/search-client.md)** - Complete API documentation
- **[Search Examples](../../examples/)** - Code examples in the repository
- **[Caching](../caching/)** - Understanding caching behavior
