
# API Reference

This section provides detailed documentation for all PyEuropePMC classes and methods.


## Core Classes

### QueryBuilder

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder(validate=True)
```

The advanced fluent API for building complex search queries with type safety and validation.

#### Key Features

- **Fluent API**: Chain methods to build complex queries
- **Type Safety**: Field names validated at compile time
- **Validation**: Optional syntax validation with search-query package
- **Persistence**: Save/load queries in standard JSON format
- **Translation**: Convert between platform syntaxes
- **Evaluation**: Assess search effectiveness metrics

**[Complete QueryBuilder API →](query-builder.md)**

---

### EuropePMC Client

```python
from pyeuropepmc import EuropePMC

client = EuropePMC()
```

The main client class for interacting with the Europe PMC API.

#### Constructor

```python
EuropePMC(
    base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest",
    timeout: int = 30,
    retries: int = 3,
    rate_limit: float = 1.0
)
```

**Parameters:**

- `base_url`: Base URL for the Europe PMC API
- `timeout`: Request timeout in seconds
- `retries`: Number of retry attempts for failed requests
- `rate_limit`: Minimum time between requests in seconds

#### Methods

##### search()

Search for articles in the Europe PMC database.

```python
search(
    query: str,
    source: str = "MED",
    limit: int = 25,
    offset: int = 0,
    sort: str = "relevance",
    format: str = "json",
    **kwargs
) -> List[Article]
```

**Parameters:**

- `query`: Search query string
- `source`: Data source (MED, PMC, AGR, CBA, CTX, ETH, HIR, PAT)
- `limit`: Maximum number of results to return
- `offset`: Number of results to skip
- `sort`: Sort order (relevance, date, cited)
- `format`: Response format (json, xml, dc)


**Returns:** List of Article objects

**Example:**

```python
results = client.search("cancer therapy", limit=10, sort="date", format="json")
```

##### fetch_by_id()

Fetch a specific article by its ID.

```python
fetch_by_id(
    pmid: str = None,
    pmcid: str = None,
    doi: str = None,
    format: str = "json"
) -> Article
```

##### fetch_citations()

Get citations for a specific article.

```python
fetch_citations(
    pmid: str = None,
    pmcid: str = None,
    limit: int = 25,
    offset: int = 0
) -> List[Citation]
```

##### fetch_references()

Get references cited by a specific article.

```python
fetch_references(
    pmid: str = None,
    pmcid: str = None,
    limit: int = 25,
    offset: int = 0
) -> List[Reference]
```


## Data Models

### Article

Represents a scientific article from Europe PMC.

**Attributes:**

- `title`: Article title
- `authors`: List of author names
- `journal`: Journal name
- `pub_year`: Publication year
- `pmid`: PubMed ID
- `pmcid`: PMC ID
- `doi`: DOI
- `abstract`: Article abstract
- `keywords`: List of keywords
- `mesh_terms`: List of MeSH terms

### Citation

Represents a citation to an article.

**Attributes:**

- `pmid`: PubMed ID of citing article
- `title`: Title of citing article
- `authors`: Authors of citing article
- `journal`: Journal of citing article
- `pub_year`: Publication year

### Reference

Represents a reference cited by an article.

**Attributes:**

- `pmid`: PubMed ID of referenced article
- `title`: Title of referenced article
- `authors`: Authors of referenced article
- `journal`: Journal of referenced article
- `pub_year`: Publication year


## Error Handling

### Exception Classes

- `EuropePMCError`: Base exception class
- `APIError`: API-related errors
- `AuthenticationError`: Authentication failures
- `RateLimitError`: Rate limiting exceeded
- `ValidationError`: Input validation errors

### Example Error Handling

```python
from pyeuropepmc import EuropePMC, APIError, RateLimitError

try:
    client = EuropePMC()
    results = client.search("invalid query")
except APIError as e:
    print(f"API Error: {e}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Type Safety & Validation

All public methods use type annotations and validate input parameters. Invalid arguments will raise exceptions with clear error messages.

## Configuration

### Environment Variables

- `EUROPEPMC_API_KEY`: API key for authenticated requests
- `EUROPEPMC_BASE_URL`: Custom base URL
- `EUROPEPMC_TIMEOUT`: Default timeout in seconds
- `EUROPEPMC_RATE_LIMIT`: Default rate limit in seconds

### Configuration File

Create a `.pyeuropepmc.conf` file in your home directory:

```ini
[api]
base_url = https://www.ebi.ac.uk/europepmc/webservices/rest
timeout = 30
retries = 3
rate_limit = 1.0

[logging]
level = INFO
format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
```
