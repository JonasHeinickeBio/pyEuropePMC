# ArticleClient API Reference

The `ArticleClient` provides article-specific operations and metadata retrieval from Europe PMC.

## Class Overview

```python
from pyeuropepmc.clients.article import ArticleClient

class ArticleClient:
    """Client for article-specific operations."""
```

## Constructor

### `ArticleClient(rate_limit_delay=1.0, timeout=30, max_retries=3)`

Create a new ArticleClient instance.

**Parameters:**
- `rate_limit_delay` (float): Delay between requests in seconds (default: 1.0)
- `timeout` (int): Request timeout in seconds (default: 30)
- `max_retries` (int): Maximum number of retry attempts (default: 3)

## Methods

### `get_article_metadata(pmcid, **kwargs)`

Get detailed metadata for a specific article by PMC ID.

**Parameters:**
- `pmcid` (str): PMC ID (e.g., "PMC1234567")
- `format` (str): Output format - "json" or "xml" (default: "json")

**Returns:**
- Dict containing article metadata

**Example:**
```python
from pyeuropepmc.clients.article import ArticleClient

with ArticleClient() as client:
    metadata = client.get_article_metadata("PMC1234567")
    print(f"Title: {metadata.get('title')}")
    print(f"Journal: {metadata.get('journalTitle')}")
```

### `get_article_citations(pmcid, **kwargs)`

Get citation information for an article.

**Parameters:**
- `pmcid` (str): PMC ID
- `pageSize` (int): Number of citations per page (default: 100)
- `offset` (int): Starting offset (default: 0)

**Returns:**
- Dict containing citation data

### `get_article_references(pmcid, **kwargs)`

Get references cited by an article.

**Parameters:**
- `pmcid` (str): PMC ID
- `pageSize` (int): Number of references per page (default: 100)
- `offset` (int): Starting offset (default: 0)

**Returns:**
- Dict containing reference data

## Context Manager Usage

```python
with ArticleClient() as client:
    metadata = client.get_article_metadata("PMC1234567")
    citations = client.get_article_citations("PMC1234567")
```

## Error Handling

Raises `EuropePMCError` for API-related issues:

```python
from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.core.exceptions import EuropePMCError

try:
    with ArticleClient() as client:
        metadata = client.get_article_metadata("PMC1234567")
except EuropePMCError as e:
    print(f"Failed to get article metadata: {e}")
```

## Examples

### Get Article Details

```python
from pyeuropepmc.clients.article import ArticleClient

with ArticleClient() as client:
    # Get basic metadata
    metadata = client.get_article_metadata("PMC3258128")

    print(f"Title: {metadata.get('title')}")
    print(f"Authors: {metadata.get('authorString')}")
    print(f"Abstract: {metadata.get('abstractText', 'No abstract')[:200]}...")

    # Get citation count
    citations = client.get_article_citations("PMC3258128")
    print(f"Citation count: {citations.get('hitCount', 0)}")
```

### Batch Article Processing

```python
pmcids = ["PMC1234567", "PMC2345678", "PMC3456789"]

with ArticleClient() as client:
    for pmcid in pmcids:
        try:
            metadata = client.get_article_metadata(pmcid)
            print(f"Processed {pmcid}: {metadata.get('title', 'No title')[:50]}...")
        except EuropePMCError as e:
            print(f"Failed to process {pmcid}: {e}")
```

## Related Classes

- [`SearchClient`](../search-client.md) - For searching articles
- [`FullTextClient`](../fulltext-client.md) - For downloading full text
- [`EuropePMCParser`](../parser.md) - For parsing responses
