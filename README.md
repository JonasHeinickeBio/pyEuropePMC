# PyEuropePMC

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-174%20passed-green.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-90%2B%25-brightgreen.svg)](htmlcov/)

**PyEuropePMC** is a robust Python toolkit for automated search, extraction, and analysis of scientific literature from [Europe PMC](https://europepmc.org/). Built with production-ready features including comprehensive error handling, rate limiting, and extensive testing.

---

## ✨ Key Features

- 🔍 **Comprehensive Search API** - Query Europe PMC with advanced search options
- 📊 **Multiple Output Formats** - JSON, XML, and Dublin Core support
- 🔄 **Smart Pagination** - Automatic handling of large result sets
- 🛡️ **Robust Error Handling** - Built-in retry logic and connection management
- ⚡ **Rate Limiting** - Respectful API usage with configurable delays
- 🧪 **Extensively Tested** - 174 tests with 90%+ code coverage
- 📋 **Type Safety** - Full type hints for better IDE support
- 🎯 **Production Ready** - Context managers, logging, and proper resource cleanup

---

## 🚀 Quick Start

### Installation

#### From PyPI (recommended)

```bash
pip install pyeuropepmc
```

#### From Source

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC
pip install -e .
```

#### Development Installation

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC
pip install -e ".[dev]"
pre-commit install
```

### Basic Usage

#### Simple Search

```python
from pyeuropepmc.search import SearchClient

# Create client with rate limiting
with SearchClient(rate_limit_delay=1.0) as client:
    # Search for papers
    results = client.search("CRISPR gene editing", pageSize=10)

    # Process results
    for paper in results["resultList"]["result"]:
        print(f"Title: {paper['title']}")
        print(f"Authors: {paper.get('authorString', 'N/A')}")
        print(f"Journal: {paper.get('journalTitle', 'N/A')}")
        print("---")
```

#### Advanced Search with Parsing

```python
from pyeuropepmc.search import SearchClient

with SearchClient() as client:
    # Search and automatically parse results
    papers = client.search_and_parse(
        query="COVID-19 AND vaccine",
        format="json",
        pageSize=50,
        sort="CITED desc"  # Sort by citation count
    )

    # papers is now a list of dictionaries
    for paper in papers:
        print(f"Citations: {paper.get('citedByCount', 0)}")
        print(f"Title: {paper.get('title', 'N/A')}")
```

#### Interactive Search

```python
from pyeuropepmc.search import SearchClient

with SearchClient() as client:
    # Interactive search with user prompts
    results = client.interactive_search("machine learning bioinformatics")
    # User will be prompted for number of results to fetch
    print(f"Retrieved {len(results)} papers")
```

#### Fetch All Results with Pagination

```python
from pyeuropepmc.search import SearchClient

with SearchClient() as client:
    # Automatically handle pagination for large result sets
    all_papers = client.fetch_all_pages(
        query="protein folding",
        page_size=100,
        max_results=1000  # Limit total results
    )
    print(f"Total papers retrieved: {len(all_papers)}")
```

---

## � API Reference

### SearchClient

The main interface for searching Europe PMC.

#### Constructor

```python
SearchClient(rate_limit_delay: float = 1.0)
```

- `rate_limit_delay`: Delay between API requests in seconds

#### Core Methods

##### `search(query: str, **kwargs) -> Union[Dict, str]`

Perform a search query.

**Parameters:**

- `query`: Search terms
- `pageSize`: Results per page (1-1000, default: 25)
- `format`: Response format ("json", "xml", "dc")
- `resultType`: Type of results ("lite", "core", "idlist")
- `synonym`: Enable synonym expansion (bool)
- `cursorMark`: Pagination cursor
- `sort`: Sort order (e.g., "CITED desc")

**Example:**

```python
results = client.search(
    "breast cancer treatment",
    pageSize=50,
    format="json",
    sort="DATE desc"
)
```

##### `search_and_parse(query: str, format: str = "json", **kwargs) -> List[Dict]`

Search and automatically parse results into a list.

##### `fetch_all_pages(query: str, page_size: int = 100, max_results: Optional[int] = None, **kwargs) -> List[Dict]`

Automatically fetch all pages of results.

##### `interactive_search(query: str, **kwargs) -> List[Dict]`

Interactive search with user prompts.

##### `get_hit_count(query: str, **kwargs) -> int`

Get total number of results for a query.

#### Utility Methods

##### `validate_query(query: str) -> bool`

Validate search query format.

##### `search_ids_only(query: str, **kwargs) -> List[str]`

Get only publication IDs.

---

## � Advanced Usage

### Error Handling

```python
from pyeuropepmc.search import SearchClient, EuropePMCError

try:
    with SearchClient() as client:
        results = client.search("invalid query with \" unmatched quotes")
except EuropePMCError as e:
    print(f"Search failed: {e}")
```

### Custom Configuration

```python
from pyeuropepmc.search import SearchClient

# Configure for high-volume usage
client = SearchClient(rate_limit_delay=0.5)  # Faster requests

# Or for respectful usage
client = SearchClient(rate_limit_delay=2.0)  # Slower requests
```

### Working with Different Formats

#### JSON Format (default)

```python
results = client.search("query", format="json")
# Returns: Dict with structure {"hitCount": int, "resultList": {"result": [...]}}
```

#### XML Format

```python
results = client.search("query", format="xml")
# Returns: Raw XML string
```

#### Dublin Core Format

```python
results = client.search("query", format="dc")
# Returns: Dublin Core XML string
```

### Using the Parser Directly

```python
from pyeuropepmc.parser import EuropePMCParser

# Parse JSON response
papers = EuropePMCParser.parse_json(json_response)

# Parse XML response
papers = EuropePMCParser.parse_xml(xml_string)

# Parse Dublin Core XML
papers = EuropePMCParser.parse_dc(dc_xml_string)
```

---

## 🧪 Testing

The project includes comprehensive tests covering all functionality:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/pyeuropepmc --cov-report=html

# Run specific test categories
pytest tests/unit/                    # Unit tests
pytest tests/functional/              # Functional tests
pytest tests/utils/                   # Utility tests
```

### Test Categories

- **Unit Tests**: Mock-based testing of individual components
- **Functional Tests**: Real API integration tests
- **Utility Tests**: Helper function validation (47 tests, 91% coverage)

---

## 📋 Requirements

- **Python**: 3.10+
- **Dependencies**:
  - `requests`: HTTP client with retry logic
  - `backoff`: Exponential backoff for API calls
  - `defusedxml`: Safe XML parsing
  - `typing-extensions`: Enhanced type hints

### Development Dependencies

- `pytest`: Testing framework
- `pytest-cov`: Coverage reporting
- `pre-commit`: Code quality hooks
- `mypy`: Static type checking
- `ruff`: Fast Python linter

---

## 🏗️ Architecture

```markdown
src/pyeuropepmc/
├── __init__.py          # Package initialization
├── base.py             # Base API client with retry logic
├── search.py           # Search client implementation
├── parser.py           # Response parsing utilities
└── utils/
    └── helpers.py      # Utility functions (JSON, validation)

tests/
├── base/               # Base client tests
├── search/             # Search functionality tests
├── parser/             # Parser tests
├── utils/              # Utility tests
├── functional/         # Integration tests
└── fixtures/           # Test data
```

---

## � Search Query Examples

### Basic Queries

```python
# Simple keyword search
"cancer treatment"

# Phrase search
'"machine learning"'

# Author search
'AUTHOR:"Smith J"'

# Journal search
'JOURNAL:"Nature"'
```

### Advanced Queries

```python
# Boolean operators
"(cancer OR tumor) AND treatment"

# Field-specific searches
'TITLE:"COVID-19" AND PUB_YEAR:2023'

# Date ranges
'PUB_YEAR:[2020 TO 2023]'

# MeSH terms
'MESH:"Neoplasms"'
```

### Filtering Results

```python
# Recent papers only
client.search("CRISPR", sort="DATE desc")

# Highly cited papers
client.search("protein folding", sort="CITED desc")

# Open access only
client.search("climate change", format="json",
              query="climate change AND OPEN_ACCESS:y")
```

---

## 🤝 Contributing

We welcome contributions! Please see our [contribution guidelines](CONTRIBUTING.md).

### Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/pyEuropePMC.git`
3. Install development dependencies: `pip install -e ".[dev]"`
4. Install pre-commit hooks: `pre-commit install`
5. Run tests: `pytest`

### Code Quality

- **Type hints**: All functions must have type annotations
- **Testing**: New features require tests (aim for >90% coverage)
- **Documentation**: Update README and docstrings
- **Style**: Code is automatically formatted with `ruff`

---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

## 🙏 Acknowledgments

- [Europe PMC](https://europepmc.org/) for providing the API
- Built with ❤️ by [Jonas Heinicke](https://github.com/JonasHeinickeBio)

---

## 🌐 Links

- **Documentation**: [Full API Docs](docs/)
- **PyPI Package**: [pyeuropepmc](https://pypi.org/project/pyeuropepmc/)
- **GitHub Repository**: [JonasHeinickeBio/pyEuropePMC](https://github.com/JonasHeinickeBio/pyEuropePMC)
- **Europe PMC API**: [Official Documentation](https://europepmc.org/RestfulWebService)
- **Issue Tracker**: [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
