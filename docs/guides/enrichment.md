# External API Enrichment

The enrichment module provides integration with external academic APIs to enhance paper metadata with additional information from multiple sources.

## Supported APIs

### CrossRef
- **URL**: https://api.crossref.org/
- **Purpose**: Comprehensive bibliographic metadata
- **Authentication**: None required (email optional for polite pool)
- **Data Provided**:
  - Title, authors, abstract
  - Journal information
  - Publication dates
  - Citation counts
  - License information
  - Funding information
  - References

### Unpaywall
- **URL**: https://api.unpaywall.org/
- **Purpose**: Open access status and full-text availability
- **Authentication**: Email required
- **Data Provided**:
  - Open access status (gold, green, hybrid, bronze, closed)
  - Best OA location for full text
  - License information
  - Repository information
  - Embargoed OA locations

### Semantic Scholar
- **URL**: https://api.semanticscholar.org/
- **Purpose**: Academic impact metrics
- **Authentication**: None required (API key optional for higher limits)
- **Data Provided**:
  - Citation counts
  - Influential citation counts
  - Abstract
  - Venue information
  - Author information
  - Fields of study
  - References and citations

### OpenAlex
- **URL**: https://api.openalex.org/
- **Purpose**: Comprehensive academic metadata graph
- **Authentication**: None required (email optional for polite pool)
- **Data Provided**:
  - Citation counts
  - Topics and concepts
  - Author affiliations
  - Institution data
  - Open access status
  - Referenced works

## Architecture

### BaseEnrichmentClient

Base class providing common functionality:
- HTTP request handling with retries (exponential backoff)
- Rate limiting
- Response caching via existing cache system
- Error handling and logging
- Context manager support

### Individual API Clients

Each API has a dedicated client that extends `BaseEnrichmentClient`:
- `CrossRefClient`
- `UnpaywallClient`
- `SemanticScholarClient`
- `OpenAlexClient`

### Professional Library Integration

PyEuropePMC now uses **danielnsilva/semanticscholar v0.12.0** professional library as the backend for Semantic Scholar API operations. This integration provides:

| Feature | Professional Library | Old API Wrapper |
|---------|---------------------|-----------------|
| **Type Safety** | ✅ Full typed responses (`Paper`, `Author`, `Venue`) | ⚠️ Dict-based |
| **Async Support** | ✅ Native async/await | ❌ Sync only |
| **Bulk Search** | ✅ `/paper/search/bulk` endpoint | ⚠️ paginated |
| **Typed Objects** | ✅ Dataclass models | ❌ Raw dicts |
| **Recommended** | ✅ For new projects | ⚠️ Legacy |

#### When to Use Each Client

**Use `ProfessionalSemanticScholarClient` (Recommended for new projects):**
- ✅ You need typed responses (`Paper`, `Author`, `Venue` objects)
- ✅ You're building async applications
- ✅ You need faster bulk search operations
- ✅ You want type-safe development with IDE autocomplete

**Use `SemanticScholarClient` (Legacy):**
- ⚠️ You're migrating existing code
- ⚠️ You need a simple dict-based interface
- ⚠️ You're using the unified `PaperEnricher` class

### PaperEnricher Orchestrator

High-level interface that:
- Coordinates multiple API clients
- Handles errors gracefully
- Merges data from multiple sources intelligently
- Provides unified interface

## Usage

### Basic Usage

```python
from pyeuropepmc import PaperEnricher, EnrichmentConfig

# Configure enrichment
config = EnrichmentConfig(
    enable_crossref=True,
    enable_semantic_scholar=True,
    enable_openalex=True
)

# Enrich a paper
with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper(doi="10.1371/journal.pone.0308090")

    # Access merged data
    print(result["merged"]["title"])
    print(result["merged"]["citation_count"])
```

### Advanced Configuration

```python
from pyeuropepmc import PaperEnricher, EnrichmentConfig
from pyeuropepmc.cache.cache import CacheConfig

# Configure with all options
config = EnrichmentConfig(
    # Enable/disable APIs
    enable_crossref=True,
    enable_unpaywall=True,
    enable_semantic_scholar=True,
    enable_openalex=True,

    # API-specific settings
    unpaywall_email="your@email.com",
    crossref_email="your@email.com",
    semantic_scholar_api_key="your-api-key",
    openalex_email="your@email.com",

    # Performance settings
    cache_config=CacheConfig(enabled=True, ttl=86400),
    rate_limit_delay=1.0
)

with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper(doi="10.1234/example")
```

### Using Individual Clients

```python
from pyeuropepmc.enrichment import CrossRefClient, OpenAlexClient

# Use CrossRef directly
with CrossRefClient(email="your@email.com") as client:
    data = client.enrich(doi="10.1234/example")
    print(data["citation_count"])

# Use OpenAlex directly
with OpenAlexClient(email="your@email.com") as client:
    data = client.enrich(doi="10.1234/example")
    print(data["topics"])
```

### Semantic Scholar Recommendations API

`SemanticScholarClient` also supports Semantic Scholar Recommendations API v1:

```python
from pyeuropepmc.enrichment import SemanticScholarClient

with SemanticScholarClient(api_key="your-api-key") as client:
    # GET /recommendations/v1/papers/forpaper/{paper_id}
    recs_for_one = client.get_recommendations_for_paper(
        paper_id="649def34f8be52c8b66281af98ae884c09aef38b",
        limit=500,
    )

    # POST /recommendations/v1/papers/
    recs_for_many = client.get_recommendations_for_papers(
        positive_paper_ids=["649def34f8be52c8b66281af98ae884c09aef38b"],
        negative_paper_ids=["ArXiv:1805.02262"],
        limit=500,
    )
```

### Using the Professional Library Directly

For advanced use cases, you can use `ProfessionalSemanticScholarClient` directly:

```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

# Configure with API key (optional but recommended for higher rate limits)
client = ProfessionalSemanticScholarClient(
    api_key="your-api-key",
    rate_limit_delay=1.0  # 1 second delay between requests
)

# Typed responses with Paper objects
paper = client.get_paper("10.1038/nature12373")
print(f"Title: {paper.title}")
print(f"Authors: {len(paper.authors)}")
print(f"Citations: {paper.citation_count}")

# Bulk search (faster, no relevance ranking, up to 10M results)
results = client.search_paper("cancer", bulk=True, limit=50)

# Regular search with relevance ranking
results = client.search_paper("machine learning", bulk=False, limit=100)

# Get author information
author = client.get_author("1724609")
print(f"Author: {author.name}")
print(f"Paper count: {author.paper_count}")

# Get venue information
venue = client.get_venue("12345")
print(f"Venue: {venue.name}")
print(f"Paper count: {venue.paper_count}")
```

### Migrating from Old Library to Professional Library

**Old Code:**
```python
from pyeuropepmc.enrichment import SemanticScholarClient

client = SemanticScholarClient()
results = client.search_paper("cancer")
```

**New Code:**
```python
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient()
results = client.search_paper("cancer", bulk=False)  # explicit
```

**Migration Benefits:**
1. ✅ Typed responses (`Paper`, `Author`, `Venue`) instead of dicts
2. ✅ Bulk search endpoint for faster operations
3. ✅ Better async support
4. ✅ More consistent API

**Backward Compatibility:**
- `SemanticScholarClient` still works and wraps the professional library
- Existing code continues to function without changes
- Use `PaperEnricher` for unified multi-API enrichment

## Data Merging Strategy

When multiple sources provide the same information, `PaperEnricher` uses the following priority:

### Bibliographic Data
- **Title, Authors, Abstract**: CrossRef (most authoritative)
- **Journal/Venue**: CrossRef, then OpenAlex
- **Publication Date**: CrossRef, then OpenAlex

### Metrics
- **Citation Count**: Maximum across all sources
  - Provides breakdown by source
- **Influential Citations**: Semantic Scholar

### Open Access
- **OA Status**: Unpaywall (primary), OpenAlex (fallback)
- **OA URL**: Best available location

### Additional Metadata
- **Topics**: OpenAlex
- **Fields of Study**: Semantic Scholar
- **License**: CrossRef
- **Funding**: CrossRef

## Error Handling

The enrichment module provides robust error handling:

### Graceful Degradation
- If one API fails, others continue
- Returns partial results when available
- Logs errors without raising exceptions

### Retry Logic
- Automatic retries with exponential backoff
- Configurable retry attempts
- Respects HTTP status codes (404 returns None instead of raising)

### Validation
- Input validation (requires DOI for most operations)
- Configuration validation (e.g., email required for Unpaywall)
- Type checking via mypy

## Performance

### Caching
- Reuses existing PyEuropePMC cache system
- Configurable TTL per data type
- Reduces redundant API calls
- L1 (in-memory) and L2 (persistent) cache layers

### Rate Limiting
- Configurable delay between requests
- Per-API rate limiting
- Respects API quotas

### Best Practices
1. Enable caching for repeated queries
2. Provide emails for polite pools (faster response)
3. Use API keys where available (higher limits)
4. Start with fewer APIs and add as needed
5. Handle missing data gracefully

## Authentication & API Keys

### Recommended: Environment Variables

The simplest and most secure way to configure API keys is using environment variables:

```bash
# Linux/Mac (add to ~/.bashrc or ~/.zshrc)
export SEMANTIC_SCHOLAR_API_KEY="your-api-key-here"
export UNPAYWALL_EMAIL="your@email.com"
export CROSSREF_EMAIL="your@email.com"
export OPENALEX_EMAIL="your@email.com"

# Windows (PowerShell)
$env:SEMANTIC_SCHOLAR_API_KEY="your-api-key-here"
$env:UNPAYWALL_EMAIL="your@email.com"
```

### Programmatic Configuration

```python
from pyeuropepmc.enrichment import EnrichmentConfig, ProfessionalSemanticScholarClient

# Configure with all options
config = EnrichmentConfig(
    # Enable/disable APIs
    enable_crossref=True,
    enable_unpaywall=True,
    enable_semantic_scholar=True,
    enable_openalex=True,

    # API-specific settings
    unpaywall_email="your@email.com",
    crossref_email="your@email.com",
    semantic_scholar_api_key="your-api-key",
    openalex_email="your@email.com",

    # Performance settings
    rate_limit_delay=1.0
)

with ProfessionalSemanticScholarClient(
    api_key=config.semantic_scholar_api_key,
    rate_limit_delay=config.rate_limit_delay
) as client:
    paper = client.get_paper("10.1038/nature12373")
```

### Authentication Priority

1. **Environment variables** (highest priority)
2. **Programmatic configuration**
3. **Default (no authentication)** - Limited to free tier

## Rate Limits

| API | Free Tier Limit | With Authentication | Recommended Delay |
|-----|----------------|---------------------|-------------------|
| CrossRef | No strict limit | Polite pool | 1.0-2.0s |
| Unpaywall | 100,000/day | Same | 0.5-1.0s |
| Semantic Scholar | 100 req/5 min | 300 req/5 min | 1.5-3.0s |
| OpenAlex | 10 req/sec | 100 req/day | 0.2-0.5s |

### Rate Limiting Recommendations

| Use Case | Delay | Notes |
|----------|-------|-------|
| Hobby projects | 2.0s | Conservative, respectful usage |
| Research projects | 1.0s | Balanced for moderate workloads |
| Production with caching | 0.5s | Use caching to reduce requests |
| Bulk operations | N/A | Use `bulk=True` to minimize API calls |

### Best Practices
1. Enable caching for repeated queries
2. Use `bulk=True` for search operations (minimizes API calls)
3. Provide emails for polite pools (faster response)
4. Use API keys where available (higher limits)
5. Monitor response headers for rate limit status
6. Handle 429 (rate limit) responses with exponential backoff

## Testing

The enrichment module includes comprehensive tests:

- **43 unit tests** covering all functionality
- **Mocked API responses** for fast, reliable testing
- **Error scenario testing** for robustness
- **Type checking** with mypy strict mode
- **Code quality** via ruff linting

Run tests:
```bash
pytest tests/enrichment/
```

## Examples

See [examples/09-enrichment/](../../examples/09-enrichment/) for:
- `basic_enrichment.py` - Simple enrichment example
- `advanced_enrichment.py` - Advanced with caching and all APIs
- `enrichment_demo.ipynb` - Interactive Jupyter notebook demo
- `README.md` - Detailed usage guide

### Enrichment Demo Notebook

The `enrichment_demo.ipynb` notebook provides an interactive demonstration of enrichment capabilities with detailed data analysis:

#### Basic Enrichment Example
- Simple configuration with CrossRef, Semantic Scholar, and OpenAlex
- Displays merged metadata in organized sections:
  - Title and authors
  - Citation metrics
  - Open access status

#### Advanced Enrichment Example
- Full configuration with all APIs enabled
- Caching and rate limiting
- Multiple DOI processing
- Error handling

#### Detailed Data Analysis
The notebook includes comprehensive data exploration sections:

##### Available Fields per Service
Lists all top-level fields available from each service and shows data types for each field. This helps understand the complete data structure returned by each API.

##### Service Comparison Summary
A clean comparison table showing what each service provides:

| Service | Fields | Title | Authors | Citations | Abstract | OA | Topics | License | Funding |
|---------|--------|-------|---------|-----------|----------|----|--------|---------|---------|
| **CROSSREF** | 16 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | None |
| **SEMANTIC_SCHOLAR** | 13 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **OPENALEX** | 20 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |

This comparison helps users understand the strengths of each API and plan their enrichment strategy accordingly.

## API Documentation

For detailed API documentation, see:
- [CrossRef REST API](https://api.crossref.org/)
- [Unpaywall API](https://unpaywall.org/products/api)
- [Semantic Scholar API](https://api.semanticscholar.org/)
- [OpenAlex API](https://docs.openalex.org/)

## Future Enhancements

Potential future additions:
- ORCID API integration
- ROR (Research Organization Registry) support
- OpenCitations for citation network data
- DataCite for additional DOI metadata
- Batch enrichment optimization
- Citation network analysis
