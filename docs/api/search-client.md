# SearchClient API Reference

The `SearchClient` is the main interface for searching Europe PMC's database of scientific literature.

## Class Overview

```python
from pyeuropepmc.search import SearchClient

class SearchClient:
    """Client for searching Europe PMC REST API."""
```

## Constructor

### `SearchClient(rate_limit_delay=1.0, timeout=30, max_retries=3)`

Create a new SearchClient instance.

**Parameters:**
- `rate_limit_delay` (float): Delay between requests in seconds (default: 1.0)
- `timeout` (int): Request timeout in seconds (default: 30)
- `max_retries` (int): Maximum number of retry attempts (default: 3)

**Example:**
```python
client = SearchClient(rate_limit_delay=2.0, timeout=60)
```

## Methods

### `search(query, **kwargs)`

Search Europe PMC and return results.

**Parameters:**
- `query` (str): Search query string
- `pageSize` (int): Number of results per page (1-1000, default: 100)
- `offset` (int): Starting offset for results (default: 0)
- `format` (str): Output format - "json", "xml", or "dc" (default: "json")
- `resultType` (str): Result detail level - "lite", "core", or "full" (default: "core")
- `sort` (str): Sort field (default: "relevance")
- `source` (str): Data source filter - "MED", "PMC", "PPR", etc.
- `limit` (int): Maximum total results to return (for pagination)

**Returns:**
- Dict containing search results with metadata

**Example:**
```python
results = client.search(
    "CRISPR gene editing",
    pageSize=50,
    format="json",
    sort="CITED desc"
)
```

### `search_and_parse(query, **kwargs)`

Search and automatically parse results into structured data.

**Parameters:**
- Same as `search()` method

**Returns:**
- List of parsed paper dictionaries

**Example:**
```python
papers = client.search_and_parse(
    "COVID-19 vaccine",
    pageSize=25,
    sort="CITED desc"
)

for paper in papers:
    print(f"Citations: {paper.get('citedByCount', 0)}")
    print(f"Title: {paper.get('title')}")
```

### `get_hit_count(query)`

Get the total number of results for a query without retrieving them.

**Parameters:**
- `query` (str): Search query string

**Returns:**
- Integer count of matching results

**Example:**
```python
count = client.get_hit_count("machine learning")
print(f"Found {count} papers")
```

### `fetch_all_pages(query, max_results=None, **kwargs)`

Automatically fetch all pages of results up to a maximum limit.

**Parameters:**
- `query` (str): Search query string
- `max_results` (int): Maximum total results to return (default: None for all)
- Additional parameters passed to `search()`

**Returns:**
- List of all result dictionaries

**Example:**
```python
all_papers = client.fetch_all_pages(
    "cancer immunotherapy",
    max_results=1000,
    pageSize=100
)
```

## Context Manager Usage

The SearchClient supports context manager usage for automatic resource cleanup:

```python
with SearchClient() as client:
    results = client.search("neural networks")
    # Client automatically closed
```

## Error Handling

The SearchClient raises `EuropePMCError` for API-related issues:

```python
from pyeuropepmc.search import SearchClient, EuropePMCError

try:
    with SearchClient() as client:
        results = client.search("invalid query syntax")
except EuropePMCError as e:
    print(f"Search failed: {e}")
```

## Rate Limiting

Built-in rate limiting prevents API abuse:

```python
# Respectful usage (recommended)
client = SearchClient(rate_limit_delay=1.0)

# More conservative
client = SearchClient(rate_limit_delay=2.0)
```

## Examples

### Basic Search

```python
from pyeuropepmc.search import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR", pageSize=10)

    print(f"Total results: {results['hitCount']}")

    for paper in results["resultList"]["result"]:
        print(f"Title: {paper.get('title')}")
        print(f"Authors: {paper.get('authorString')}")
        print(f"Year: {paper.get('pubYear')}")
```

### Advanced Search with Filtering

```python
with SearchClient() as client:
    results = client.search(
        query="cancer immunotherapy",
        source="MED",  # PubMed only
        sort="CITED desc",  # Most cited first
        pageSize=50,
        format="json"
    )
```

### Pagination

```python
# Manual pagination
page1 = client.search("machine learning", pageSize=100, offset=0)
page2 = client.search("machine learning", pageSize=100, offset=100)

# Automatic pagination
all_results = client.fetch_all_pages("machine learning", max_results=500)
```

### Citation Analysis

```python
papers = client.search_and_parse(
    "artificial intelligence",
    pageSize=100,
    sort="CITED desc"
)

# Analyze citation distribution
citations = [p.get('citedByCount', 0) for p in papers]
highly_cited = [p for p in papers if p.get('citedByCount', 0) > 100]
```

## Related Classes

- [`QueryBuilder`](../query-builder.md) - For building complex search queries
- [`FullTextClient`](../fulltext-client.md) - For downloading full-text content
- [`EuropePMCParser`](../parser.md) - For parsing search results
