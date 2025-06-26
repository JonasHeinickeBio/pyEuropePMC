# Frequently Asked Questions

## General Questions

### What is PyEuropePMC?

PyEuropePMC is a Python library for searching and retrieving scientific literature from the Europe PMC database. It provides a simple, robust interface to access millions of research articles, preprints, and other scholarly content.

### Who should use PyEuropePMC?

- **Researchers** conducting literature reviews
- **Data scientists** analyzing scientific publications
- **Bioinformaticians** building literature-based workflows
- **Developers** integrating publication data into applications
- **Students** learning about bibliometric analysis

## Installation & Setup

### How do I install PyEuropePMC?

```bash
pip install pyeuropepmc
```

For development:

```bash
pip install -e ".[dev]"
```

### What Python versions are supported?

Python 3.10 and newer versions are supported.

### Do I need an API key?

No, Europe PMC provides open access to their search API without requiring registration or API keys.

## Usage Questions

### How do I perform a basic search?

```python
from pyeuropepmc.search import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR", pageSize=10)
    for paper in results["resultList"]["result"]:
        print(paper["title"])
```

### How can I search for specific authors?

```python
# Search by author
results = client.search('AUTH:"Smith J"')

# Search by author and topic
results = client.search('AUTH:"Smith J" AND cancer')
```

### How do I handle large result sets?

Use the pagination features:

```python
# Automatic pagination
all_results = client.fetch_all_pages("machine learning", max_results=1000)

# Manual pagination
page1 = client.search("query", pageSize=100, offset=0)
page2 = client.search("query", pageSize=100, offset=100)
```

### What output formats are available?

- **JSON** (default): Structured data, easy to process
- **XML**: Full metadata, Europe PMC native format
- **Dublin Core**: Standardized metadata format

```python
json_results = client.search("query", format="json")
xml_results = client.search("query", format="xml")
dc_results = client.search("query", format="dc")
```

### How do I filter by publication date?

```python
# Specific year
results = client.search("cancer AND PUB_YEAR:2023")

# Date range
results = client.search("cancer AND PUB_YEAR:[2020 TO 2023]")

# Recent articles (last 5 years)
from datetime import datetime
current_year = datetime.now().year
results = client.search(f"cancer AND PUB_YEAR:[{current_year-5} TO {current_year}]")
```

## Advanced Usage

### How do I implement rate limiting?

```python
# Built-in rate limiting
client = SearchClient(rate_limit_delay=2.0)  # 2 seconds between requests

# Custom throttling
import time
for query in queries:
    results = client.search(query)
    time.sleep(1)  # Additional delay
```

### Can I search multiple databases simultaneously?

```python
# Search specific sources
results_pubmed = client.search("query", source="MED")
results_pmc = client.search("query", source="PMC")
results_preprints = client.search("query", source="PPR")

# Combine results
all_results = results_pubmed + results_pmc + results_preprints
```

### How do I handle errors and retries?

```python
from pyeuropepmc.search import SearchClient, EuropePMCError

try:
    with SearchClient() as client:
        results = client.search("complex query")
except EuropePMCError as e:
    print(f"Search failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

The client includes built-in retry logic for network errors.

## Performance & Limits

### Are there API rate limits?

Europe PMC doesn't publish specific rate limits, but we recommend:

- Maximum 1-2 requests per second
- Use built-in rate limiting: `SearchClient(rate_limit_delay=1.0)`
- Implement exponential backoff for errors

### How many results can I retrieve?

- Single request: Up to 1,000 results
- Total: No hard limit, but be respectful of the service
- Use pagination for large datasets

### How can I optimize performance?

```python
# Use appropriate page sizes
results = client.search("query", pageSize=100)  # vs. pageSize=10

# Request only needed fields
results = client.search("query", resultType="lite")  # vs. "core"

# Use caching for repeated queries
# (implement your own caching layer)
```

## Data & Results

### What information is included in search results?

Standard fields include:

- Title, authors, journal
- Publication date, DOI, PMID
- Abstract (when available)
- Citation counts
- Full-text availability

### How do I access full-text articles?

```python
for paper in results["resultList"]["result"]:
    # Check if full text is available
    if paper.get("isOpenAccess") == "Y":
        print(f"Open access: {paper.get('fullTextUrlList')}")

    # PMC articles may have full text
    if paper.get("pmcid"):
        print(f"PMC ID: {paper['pmcid']}")
```

### How accurate are citation counts?

Citation counts are updated regularly but may not be real-time. They include:

- Citations from Europe PMC corpus
- May not include all citation sources
- Updated periodically (not real-time)

## Troubleshooting

### Why am I getting no results?

1. **Check query syntax**: Ensure proper quoting and operators
2. **Verify field names**: Use `AUTH:` not `AUTHOR:`
3. **Check spelling**: Try variations and synonyms
4. **Broaden search**: Remove restrictive filters

```python
# Debug: Check hit count
hit_count = client.get_hit_count("your query")
print(f"Total matches: {hit_count}")
```

### Why am I getting timeout errors?

```python
# Increase timeout
client = SearchClient(timeout=60)  # Default is 30 seconds

# Check network connectivity
# Try simpler queries first
```

### Why are some fields missing?

Not all articles have complete metadata:

- Older articles may lack abstracts
- Some journals don't provide author ORCIDs
- Citation counts vary by article age and source

Use safe access:

```python
title = paper.get("title", "No title available")
authors = paper.get("authorString", "No authors listed")
```

## Getting Help

### Where can I find more examples?

- [Examples documentation](examples/README.md)
- [GitHub examples directory](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples)
- [API reference](api/README.md)

### How do I report bugs or request features?

- **GitHub Issues**: [Report bugs or request features](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
- **Discussions**: [Ask questions](https://github.com/JonasHeinickeBio/pyEuropePMC/discussions)

### How can I contribute to the project?

See our [Contributing Guide](development/README.md#contributing-guidelines) for:

- Code contributions
- Documentation improvements
- Bug reports
- Feature suggestions

### Where is the official Europe PMC documentation?

- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [Search syntax guide](https://europepmc.org/Help#search)
- [API documentation](https://europepmc.org/docs/)

## Best Practices

### Query Construction

```python
# Good: Specific, well-structured queries
query = 'TITLE:"machine learning" AND PUB_YEAR:[2020 TO 2023]'

# Avoid: Too broad or ambiguous
query = "data"  # Too broad, millions of results
```

### Resource Management

```python
# Good: Use context managers
with SearchClient() as client:
    results = client.search("query")

# Good: Implement proper error handling
try:
    results = client.search("query")
except EuropePMCError as e:
    logger.error(f"Search failed: {e}")
```

### Data Processing

```python
# Good: Process results efficiently
def extract_key_info(results):
    return [
        {
            "title": paper.get("title"),
            "year": paper.get("pubYear"),
            "citations": paper.get("citedByCount", 0)
        }
        for paper in results["resultList"]["result"]
    ]
```
