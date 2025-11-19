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

## Rate Limits

| API | Free Tier Limit | With Authentication |
|-----|----------------|---------------------|
| CrossRef | No strict limit | Polite pool: faster |
| Unpaywall | 100,000/day | Same |
| Semantic Scholar | 100 req/5 min | With API key: higher |
| OpenAlex | 10 req/sec | Polite pool: stable |

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

See [examples/09-enrichment/](../examples/09-enrichment/) for:
- `basic_enrichment.py` - Simple enrichment example
- `advanced_enrichment.py` - Advanced with caching and all APIs
- `README.md` - Detailed usage guide

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
