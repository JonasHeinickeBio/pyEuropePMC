# Advanced Usage

This guide covers advanced features and techniques for using PyEuropePMC effectively.

## Table of Contents

- [Performance Optimization](#performance-optimization)
- [Custom Configurations](#custom-configurations)
- [Batch Processing](#batch-processing)
- [Rate Limiting and Throttling](#rate-limiting-and-throttling)
- [Caching Strategies](#caching-strategies)
- [Advanced Query Techniques](#advanced-query-techniques)
- [Integration with Other Tools](#integration-with-other-tools)

## Performance Optimization

### Concurrent Requests

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pyeuropepmc import EuropePMC

def search_worker(query_batch):
    """Worker function for concurrent searches."""
    client = EuropePMC()
    results = []

    for query in query_batch:
        try:
            batch_results = client.search(query, limit=50)
            results.extend(batch_results)
        except Exception as e:
            print(f"Error with query '{query}': {e}")

    return results

def concurrent_search(queries, max_workers=5):
    """Perform multiple searches concurrently."""
    # Split queries into batches
    batch_size = len(queries) // max_workers
    query_batches = [
        queries[i:i + batch_size]
        for i in range(0, len(queries), batch_size)
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(search_worker, batch): batch
            for batch in query_batches
        }

        all_results = []
        for future in concurrent.futures.as_completed(future_to_batch):
            batch_results = future.result()
            all_results.extend(batch_results)

    return all_results

# Example usage
queries = [
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "neural networks",
    "computer vision"
]

results = concurrent_search(queries, max_workers=3)
print(f"Found {len(results)} total articles")
```

### Memory-Efficient Processing

```python
def process_large_dataset(query, batch_size=100, max_results=10000):
    """Process large datasets without loading everything into memory."""
    client = EuropePMC()
    processed_count = 0

    # Generator function for streaming results
    def result_generator():
        offset = 0
        while offset < max_results:
            try:
                batch = client.search(
                    query,
                    limit=min(batch_size, max_results - offset),
                    offset=offset
                )

                if not batch:
                    break

                for article in batch:
                    yield article

                offset += len(batch)

            except Exception as e:
                print(f"Error at offset {offset}: {e}")
                break

    # Process results one at a time
    for article in result_generator():
        # Process each article individually
        process_article(article)
        processed_count += 1

        if processed_count % 100 == 0:
            print(f"Processed {processed_count} articles")

    return processed_count

def process_article(article):
    """Process a single article."""
    # Example: Extract and save key information
    data = {
        'title': article.title,
        'year': article.pub_year,
        'journal': article.journal,
        'author_count': len(article.authors) if article.authors else 0
    }

    # Save to database, file, or perform analysis
    save_to_database(data)
```

## Custom Configurations

### Configuration Class

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class EuropePMCConfig:
    """Configuration for Europe PMC client."""
    base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    timeout: int = 30
    retries: int = 3
    rate_limit: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    user_agent: str = "PyEuropePMC/1.0"

    @classmethod
    def from_file(cls, config_file: str) -> 'EuropePMCConfig':
        """Load configuration from file."""
        import json

        with open(config_file, 'r') as f:
            config_data = json.load(f)

        return cls(**config_data)

# Usage
config = EuropePMCConfig(
    timeout=60,
    retries=5,
    rate_limit=0.5  # 2 requests per second
)

client = EuropePMC(config=config)
```

### Environment-Based Configuration

```python
import os
from pyeuropepmc import EuropePMC

class ConfiguredEuropePMC(EuropePMC):
    """Europe PMC client with environment-based configuration."""

    def __init__(self):
        super().__init__(
            base_url=os.getenv('EUROPEPMC_BASE_URL', self.default_base_url),
            timeout=int(os.getenv('EUROPEPMC_TIMEOUT', '30')),
            retries=int(os.getenv('EUROPEPMC_RETRIES', '3')),
            rate_limit=float(os.getenv('EUROPEPMC_RATE_LIMIT', '1.0'))
        )

        # Set up logging based on environment
        log_level = os.getenv('EUROPEPMC_LOG_LEVEL', 'INFO')
        self.setup_logging(log_level)
```

## Batch Processing

### Batch Search Operations

```python
class BatchProcessor:
    """Efficient batch processing for Europe PMC operations."""

    def __init__(self, client: EuropePMC, batch_size: int = 50):
        self.client = client
        self.batch_size = batch_size
        self.results_cache = {}

    def batch_search(self, queries: list, deduplicate: bool = True):
        """Process multiple queries in batches."""
        all_results = []

        for i in range(0, len(queries), self.batch_size):
            batch = queries[i:i + self.batch_size]
            batch_results = self._process_batch(batch)
            all_results.extend(batch_results)

            # Optional progress reporting
            print(f"Processed {min(i + self.batch_size, len(queries))}/{len(queries)} queries")

        if deduplicate:
            all_results = self._deduplicate_results(all_results)

        return all_results

    def _process_batch(self, queries: list):
        """Process a single batch of queries."""
        batch_results = []

        for query in queries:
            try:
                if query in self.results_cache:
                    results = self.results_cache[query]
                else:
                    results = self.client.search(query, limit=100)
                    self.results_cache[query] = results

                batch_results.extend(results)

            except Exception as e:
                print(f"Error processing query '{query}': {e}")
                continue

        return batch_results

    def _deduplicate_results(self, results):
        """Remove duplicate articles based on PMID."""
        seen_pmids = set()
        unique_results = []

        for article in results:
            if article.pmid and article.pmid not in seen_pmids:
                seen_pmids.add(article.pmid)
                unique_results.append(article)
            elif not article.pmid:
                # Keep articles without PMID
                unique_results.append(article)

        return unique_results

# Usage
processor = BatchProcessor(client)
queries = ["cancer", "diabetes", "COVID-19", "machine learning"]
results = processor.batch_search(queries)
```

## Rate Limiting and Throttling

### Advanced Rate Limiting

```python
import time
from collections import deque
from threading import Lock

class RateLimiter:
    """Advanced rate limiter with burst handling."""

    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()

    def acquire(self):
        """Acquire permission to make a request."""
        with self.lock:
            now = time.time()

            # Remove old requests outside the time window
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()

            # Check if we can make a request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            # Calculate wait time
            wait_time = self.requests[0] + self.time_window - now
            return wait_time

class ThrottledEuropePMC(EuropePMC):
    """Europe PMC client with advanced throttling."""

    def __init__(self, requests_per_minute: int = 60, **kwargs):
        super().__init__(**kwargs)
        self.rate_limiter = RateLimiter(requests_per_minute, 60)

    def search(self, *args, **kwargs):
        """Search with rate limiting."""
        permission = self.rate_limiter.acquire()

        if permission is not True:
            print(f"Rate limit reached, waiting {permission:.2f} seconds")
            time.sleep(permission)
            # Try again
            self.rate_limiter.acquire()

        return super().search(*args, **kwargs)
```

## Caching Strategies

### Redis-Based Caching

```python
import redis
import json
import hashlib
from typing import Optional

class CachedEuropePMC(EuropePMC):
    """Europe PMC client with Redis caching."""

    def __init__(self, redis_url: str = "redis://localhost:6379",
                 cache_ttl: int = 3600, **kwargs):
        super().__init__(**kwargs)
        self.redis_client = redis.from_url(redis_url)
        self.cache_ttl = cache_ttl

    def _get_cache_key(self, method: str, *args, **kwargs) -> str:
        """Generate cache key for method call."""
        key_data = {
            'method': method,
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def search(self, *args, **kwargs):
        """Search with caching."""
        cache_key = self._get_cache_key('search', *args, **kwargs)

        # Try to get from cache
        cached_result = self.redis_client.get(cache_key)
        if cached_result:
            return json.loads(cached_result)

        # Get fresh data
        results = super().search(*args, **kwargs)

        # Cache the results
        self.redis_client.setex(
            cache_key,
            self.cache_ttl,
            json.dumps([r.to_dict() for r in results])
        )

        return results

# Usage
cached_client = CachedEuropePMC(cache_ttl=7200)  # 2 hours
results = cached_client.search("machine learning")  # Will be cached
```

### File-Based Caching

```python
import os
import pickle
import hashlib
from pathlib import Path

class FileCachedEuropePMC(EuropePMC):
    """Europe PMC client with file-based caching."""

    def __init__(self, cache_dir: str = "./cache", **kwargs):
        super().__init__(**kwargs)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, method: str, *args, **kwargs) -> Path:
        """Get cache file path for method call."""
        key_data = f"{method}_{args}_{kwargs}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.pkl"

    def search(self, *args, **kwargs):
        """Search with file caching."""
        cache_path = self._get_cache_path('search', *args, **kwargs)

        # Check if cache exists and is recent
        if cache_path.exists():
            # Check if cache is fresh (less than 1 hour old)
            if time.time() - cache_path.stat().st_mtime < 3600:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)

        # Get fresh data
        results = super().search(*args, **kwargs)

        # Cache the results
        with open(cache_path, 'wb') as f:
            pickle.dump(results, f)

        return results
```

## Advanced Query Techniques

### Query Builder

```python
class QueryBuilder:
    """Build complex Europe PMC queries programmatically."""

    def __init__(self):
        self.terms = []
        self.filters = []

    def add_term(self, term: str, field: str = None, operator: str = "AND"):
        """Add a search term."""
        if field:
            formatted_term = f"{field}:\"{term}\""
        else:
            formatted_term = f"\"{term}\""

        if self.terms:
            self.terms.append(f" {operator} {formatted_term}")
        else:
            self.terms.append(formatted_term)

        return self

    def add_author(self, author: str, operator: str = "AND"):
        """Add author filter."""
        return self.add_term(author, "AUTH", operator)

    def add_journal(self, journal: str, operator: str = "AND"):
        """Add journal filter."""
        return self.add_term(journal, "JOURNAL", operator)

    def add_year_range(self, start_year: int, end_year: int):
        """Add publication year range."""
        year_filter = f"PUB_YEAR:[{start_year} TO {end_year}]"
        self.filters.append(year_filter)
        return self

    def add_mesh_term(self, mesh_term: str):
        """Add MeSH term filter."""
        mesh_filter = f"MESH:\"{mesh_term}\""
        self.filters.append(mesh_filter)
        return self

    def build(self) -> str:
        """Build the final query string."""
        query_parts = []

        if self.terms:
            query_parts.append("(" + "".join(self.terms) + ")")

        if self.filters:
            query_parts.extend(self.filters)

        return " AND ".join(query_parts)

# Usage
query = (QueryBuilder()
         .add_term("machine learning")
         .add_term("deep learning", operator="OR")
         .add_author("Smith J")
         .add_year_range(2020, 2023)
         .add_mesh_term("Artificial Intelligence")
         .build())

print(f"Generated query: {query}")
results = client.search(query)
```

### Faceted Search

```python
def faceted_search(base_query: str, facets: dict):
    """Perform faceted search with multiple filters."""
    client = EuropePMC()
    facet_results = {}

    for facet_name, facet_values in facets.items():
        facet_results[facet_name] = {}

        for value in facet_values:
            # Build query with facet filter
            if facet_name == "year":
                facet_query = f"{base_query} AND PUB_YEAR:{value}"
            elif facet_name == "journal":
                facet_query = f"{base_query} AND JOURNAL:\"{value}\""
            elif facet_name == "author":
                facet_query = f"{base_query} AND AUTH:\"{value}\""
            else:
                facet_query = f"{base_query} AND {facet_name}:\"{value}\""

            try:
                results = client.search(facet_query, limit=100)
                facet_results[facet_name][value] = len(results)
            except Exception as e:
                print(f"Error with facet {facet_name}={value}: {e}")
                facet_results[facet_name][value] = 0

    return facet_results

# Usage
facets = {
    "year": [2020, 2021, 2022, 2023],
    "journal": ["Nature", "Science", "Cell"],
    "author": ["Smith J", "Johnson A", "Williams R"]
}

results = faceted_search("CRISPR", facets)
print("Faceted search results:")
for facet_name, facet_data in results.items():
    print(f"\n{facet_name.title()}:")
    for value, count in facet_data.items():
        print(f"  {value}: {count} articles")
```

## Integration with Other Tools

### Pandas Integration

```python
import pandas as pd

def results_to_dataframe(results):
    """Convert search results to pandas DataFrame."""
    data = []
    for article in results:
        data.append({
            'title': article.title,
            'authors': '; '.join(article.authors) if article.authors else '',
            'journal': article.journal,
            'year': article.pub_year,
            'pmid': article.pmid,
            'doi': article.doi,
            'abstract_length': len(article.abstract) if article.abstract else 0,
            'author_count': len(article.authors) if article.authors else 0
        })

    return pd.DataFrame(data)

# Usage
results = client.search("bioinformatics", limit=100)
df = results_to_dataframe(results)

# Analyze data
print("Publication years:")
print(df['year'].value_counts().sort_index())

print("\nTop journals:")
print(df['journal'].value_counts().head(10))

print("\nAuthor statistics:")
print(df['author_count'].describe())
```

### NetworkX Integration

```python
import networkx as nx

def build_citation_network(articles):
    """Build citation network using NetworkX."""
    G = nx.DiGraph()

    for article in articles:
        if not article.pmid:
            continue

        # Add article as node
        G.add_node(article.pmid,
                   title=article.title,
                   journal=article.journal,
                   year=article.pub_year)

        # Add citations as edges
        try:
            citations = client.fetch_citations(pmid=article.pmid, limit=50)
            for citation in citations:
                if citation.pmid:
                    G.add_edge(citation.pmid, article.pmid)
        except Exception as e:
            print(f"Error getting citations for {article.pmid}: {e}")

    return G

# Usage
articles = client.search("graph theory", limit=20)
network = build_citation_network(articles)

# Analyze network
print(f"Network has {network.number_of_nodes()} nodes and {network.number_of_edges()} edges")

# Find most cited articles
in_degree = dict(network.in_degree())
most_cited = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:5]

print("Most cited articles:")
for pmid, citation_count in most_cited:
    title = network.nodes[pmid].get('title', 'Unknown')
    print(f"{pmid}: {citation_count} citations - {title[:50]}...")
```

For more advanced techniques and integration examples, see the [development documentation](../development/README.md).
