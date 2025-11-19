# Paper Metadata Enrichment Examples

This directory contains examples demonstrating how to use the external API enrichment features to enhance paper metadata with information from CrossRef, Unpaywall, Semantic Scholar, and OpenAlex.

## Overview

The enrichment module allows you to:
- Fetch additional metadata from multiple academic APIs
- Get citation counts from various sources
- Check open access availability and locations
- Retrieve funding information
- Access topic classifications and fields of study
- Combine data from multiple sources intelligently

## Examples

### 1. Basic Enrichment (`basic_enrichment.py`)

A simple example showing how to enrich a single paper using default settings.

**Features demonstrated:**
- Basic configuration with CrossRef, Semantic Scholar, and OpenAlex
- Single paper enrichment
- Displaying merged metadata
- Showing individual source data

**Run it:**
```bash
python examples/09-enrichment/basic_enrichment.py
```

### 2. Advanced Enrichment (`advanced_enrichment.py`)

An advanced example showing enrichment with all APIs enabled and caching.

**Features demonstrated:**
- Enabling all APIs including Unpaywall
- Using API-specific configuration (emails, API keys)
- Response caching for performance
- Batch enrichment of multiple papers
- Error handling

**Run it:**
```bash
# Set your email for Unpaywall and other APIs
export UNPAYWALL_EMAIL="your-email@example.com"

# Optionally set Semantic Scholar API key for higher rate limits
export SEMANTIC_SCHOLAR_API_KEY="your-api-key"

python examples/09-enrichment/advanced_enrichment.py
```

## Available APIs

### CrossRef
- **Purpose:** Bibliographic metadata, citations, licensing
- **Authentication:** None required (email optional for polite pool)
- **Data provided:** Title, authors, abstract, journal, dates, citations, funders, licenses

### Unpaywall
- **Purpose:** Open access status and full-text availability
- **Authentication:** Email required
- **Data provided:** OA status, best OA location, license, repository info

### Semantic Scholar
- **Purpose:** Academic impact metrics
- **Authentication:** None required (API key optional for higher limits)
- **Data provided:** Citation count, influential citations, fields of study

### OpenAlex
- **Purpose:** Comprehensive academic metadata graph
- **Authentication:** None required (email optional for polite pool)
- **Data provided:** Citations, topics, author affiliations, institutions, OA status

## Configuration Options

### EnrichmentConfig

```python
from pyeuropepmc import EnrichmentConfig

config = EnrichmentConfig(
    # Enable/disable specific APIs
    enable_crossref=True,
    enable_unpaywall=False,  # Requires email
    enable_semantic_scholar=True,
    enable_openalex=True,
    
    # API-specific settings
    unpaywall_email="your@email.com",  # Required for Unpaywall
    crossref_email="your@email.com",   # Optional, for polite pool
    semantic_scholar_api_key="key",    # Optional, for higher limits
    openalex_email="your@email.com",   # Optional, for polite pool
    
    # Performance settings
    cache_config=CacheConfig(enabled=True, ttl=86400),
    rate_limit_delay=1.0,  # Delay between requests in seconds
)
```

### Using Individual Clients

You can also use individual API clients directly:

```python
from pyeuropepmc.enrichment import CrossRefClient, OpenAlexClient

# CrossRef client
with CrossRefClient(email="your@email.com") as client:
    metadata = client.enrich(doi="10.1234/example")
    print(metadata["title"])

# OpenAlex client
with OpenAlexClient(email="your@email.com") as client:
    metadata = client.enrich(doi="10.1234/example")
    print(metadata["citation_count"])
```

## Data Merging

When multiple sources provide the same information (e.g., citation counts), the enricher intelligently merges the data:

- **Title, Authors, Abstract:** Prefers CrossRef (authoritative for bibliographic data)
- **Citation Count:** Takes maximum across all sources and provides breakdown by source
- **Open Access:** Prefers Unpaywall, falls back to OpenAlex
- **Topics/Fields:** Combines from Semantic Scholar and OpenAlex
- **Funding, License:** From CrossRef

## Best Practices

1. **Use caching** for repeated requests to avoid hitting API rate limits
2. **Provide emails** for polite pools to get better response times
3. **Handle errors gracefully** - APIs may be temporarily unavailable
4. **Respect rate limits** - configure appropriate delays
5. **Start with fewer APIs** and add more as needed

## Rate Limits

- **CrossRef:** No strict limits, polite pool recommended
- **Unpaywall:** 100,000 calls/day for free tier
- **Semantic Scholar:** 100 requests/5 minutes without API key
- **OpenAlex:** 10 requests/second for polite pool, 100,000/day

## Troubleshooting

### "Email is required for Unpaywall"
Set `unpaywall_email` when enabling Unpaywall:
```python
config = EnrichmentConfig(
    enable_unpaywall=True,
    unpaywall_email="your@email.com"
)
```

### "Rate limit exceeded"
Increase `rate_limit_delay`:
```python
config = EnrichmentConfig(rate_limit_delay=2.0)
```

### "No data found"
- Check that the DOI is valid
- Try with a different, well-known DOI to verify connectivity
- Some papers may not be in all databases

## Further Reading

- [CrossRef REST API](https://api.crossref.org/)
- [Unpaywall API Documentation](https://unpaywall.org/products/api)
- [Semantic Scholar API](https://api.semanticscholar.org/)
- [OpenAlex API](https://docs.openalex.org/)
