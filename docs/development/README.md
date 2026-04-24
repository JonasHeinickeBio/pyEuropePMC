# Development Guide

This guide covers development practices, contributing guidelines, and project setup for PyEuropePMC contributors.

## Table of Contents

- [Development Setup](#development-setup)
- [Python Version Compatibility](python-version-strategy.md)
- [Project Structure](#project-structure)
- [Contributing Guidelines](#contributing-guidelines)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Release Process](#release-process)
- [Architecture](#architecture)

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Poetry (recommended) or pip

📋 **Note**: See our [Python Version Compatibility Strategy](python-version-strategy.md) for detailed information about supported Python versions and testing procedures.

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC

# Install with Poetry (recommended)
poetry install

# Or with pip
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest
```

### Development Dependencies

```bash
# Core development tools
pytest>=7.0.0
pytest-cov>=4.0.0
pre-commit>=3.0.0
mypy>=1.0.0
ruff>=0.1.0

# Documentation
sphinx>=5.0.0
sphinx-rtd-theme>=1.0.0

# Release tools
bump2version>=1.0.0
twine>=4.0.0
```

## Project Structure

```Markdown
pyEuropePMC/
├── src/pyeuropepmc/          # Main package
│   ├── __init__.py          # Package initialization
│   ├── base.py             # Base API client
│   ├── search.py           # Search functionality
│   ├── search_parser.py    # Response parsing
│   └── utils/
│       └── helpers.py      # Utility functions
├── tests/                   # Test suite
│   ├── base/               # Base client tests
│   ├── search/             # Search tests
│   ├── parser/             # Parser tests
│   ├── utils/              # Utility tests
│   └── fixtures/           # Test data
├── docs/                   # Documentation
├── examples/               # Usage examples
├── .github/                # GitHub workflows
├── pyproject.toml          # Project configuration
└── README.md               # Main documentation
```

### Key Files

- `pyproject.toml`: Project metadata and dependencies
- `.pre-commit-config.yaml`: Code quality hooks
- `pytest.ini`: Test configuration
- `mypy.ini`: Type checking configuration

## Contributing Guidelines

### Code Style

We follow PEP 8 and use automated tools for code formatting and linting:

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/
```

### Commit Convention

We use [Conventional Commits](https://conventionalcommits.org/):

```text
type(scope): description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- test: Test additions/changes
- refactor: Code refactoring
- style: Code style changes
- ci: CI/CD changes
```

Examples:

```text
feat(search): add pagination support
fix(parser): handle missing journal field
docs(api): update search method documentation
test(search): add unit tests for error handling
```

### Pull Request Process

1. **Fork and Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Develop and Test**

   ```bash
   # Make your changes
   # Add tests for new functionality
   pytest
   ```

3. **Quality Checks**

   ```bash
   pre-commit run --all-files
   mypy src/
   ```

4. **Submit PR**
   - Write clear description
   - Reference related issues
   - Ensure CI passes

### Code Review Guidelines

- **Review Checklist:**

  - [ ] Code follows style guidelines
  - [ ] Tests cover new functionality
  - [ ] Documentation is updated
  - [ ] No breaking changes (or properly documented)
  - [ ] Performance implications considered

## Testing

### Test Organization

```text
tests/
├── unit/                   # Unit tests (fast, isolated)
├── functional/             # Integration tests (slower)
├── fixtures/               # Test data and mocks
└── conftest.py             # Shared test configuration
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/pyeuropepmc --cov-report=html

# Run specific test categories
pytest tests/unit/                    # Unit tests only
pytest tests/functional/              # Integration tests only

# Run tests matching pattern
pytest -k "test_search"

# Run tests with verbose output
pytest -v

# Run tests in parallel
pytest -n auto
```

### Writing Tests

#### Unit Test Example

```python
# tests/unit/test_search.py
import pytest
from unittest.mock import Mock, patch
from pyeuropepmc.search import SearchClient

class TestSearchClient:
    def test_search_basic_query(self):
        """Test basic search functionality."""
        client = SearchClient()

        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = {
                'hitCount': 1,
                'resultList': {'result': [{'title': 'Test Article'}]}
            }

            results = client.search("test query")

            assert len(results) == 1
            assert results[0]['title'] == 'Test Article'
            mock_get.assert_called_once()

    def test_search_with_parameters(self):
        """Test search with custom parameters."""
        client = SearchClient()

        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {'hitCount': 0, 'resultList': {'result': []}}

            client.search("query", pageSize=50, format="xml")

            # Verify correct parameters were passed
            args, kwargs = mock_request.call_args
            assert 'pageSize=50' in args[0]
            assert 'format=xml' in args[0]
```

#### Integration Test Example

```python
# tests/functional/test_search_integration.py
import pytest
from pyeuropepmc import SearchClient

class TestSearchIntegration:
    @pytest.mark.integration
    def test_real_api_search(self):
        """Test against real Europe PMC API."""
        client = SearchClient()

        # Use a query likely to return stable results
        results = client.search("src:MED AND FIRST_PDATE:2023", pageSize=5)

        assert isinstance(results, list)
        assert len(results) <= 5

        if results:
            article = results[0]
            assert 'title' in article
            assert 'authorString' in article
```

### Test Fixtures

```python
# tests/conftest.py
import pytest
import json
from pathlib import Path

@pytest.fixture
def sample_search_response():
    """Load sample search response from fixture file."""
    fixture_path = Path(__file__).parent / 'fixtures' / 'search_response.json'
    with open(fixture_path) as f:
        return json.load(f)

@pytest.fixture
def mock_client():
    """Create a mock search client for testing."""
    from unittest.mock import Mock
    client = Mock()
    client.search.return_value = []
    return client
```

## Code Quality

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

### Static Analysis

#### Type Checking with MyPy

```ini
# mypy.ini
[mypy]
python_version = 3.10
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True

[mypy-tests.*]
disallow_untyped_defs = False
```

#### Linting with Ruff

```toml
# pyproject.toml
[tool.ruff]
target-version = "py310"
line-length = 88
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
]

[tool.ruff.per-file-ignores]
"tests/**/*" = ["S101"]  # allow assert in tests
```

### Documentation Standards

#### Docstring Format

We use Google-style docstrings:

```python
def search(self, query: str, pageSize: int = 25, **kwargs) -> List[Dict]:
    """Search Europe PMC database for articles.

    Args:
        query: Search query string following Europe PMC syntax.
        pageSize: Number of results to return per page (1-1000).
        **kwargs: Additional query parameters.

    Returns:
        List of article dictionaries containing metadata.

    Raises:
        APIError: If the API request fails.
        ValidationError: If query parameters are invalid.

    Example:
        >>> client = SearchClient()
        >>> results = client.search("cancer treatment", pageSize=10)
        >>> print(f"Found {len(results)} articles")
    """
```

## Release Process

### Version Management

We use semantic versioning (SemVer):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps

1. **Prepare Release**

   ```bash
   # Update version
   bump2version minor  # or major/patch

   # Update CHANGELOG.md
   # Review and update documentation
   ```

2. **Test Release**

   ```bash
   # Run full test suite
   pytest --cov=src/pyeuropepmc

   # Test with different Python versions
   tox

   # Build package
   python -m build
   ```

3. **Create Release**

   ```bash
   # Tag version
   git tag v1.2.0
   git push origin v1.2.0

   # Upload to PyPI
   twine upload dist/*
   ```

4. **Post-Release**
   - Create GitHub release with changelog
   - Update documentation
   - Announce on relevant channels

### Continuous Integration

GitHub Actions workflow (`.github/workflows/ci.yml`):

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Lint with ruff
      run: ruff check .

    - name: Type check with mypy
      run: mypy src/

    - name: Test with pytest
      run: pytest --cov=src/pyeuropepmc --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Architecture

### Design Principles

1. **Modularity**: Separate concerns into focused modules
2. **Extensibility**: Easy to add new functionality
3. **Reliability**: Robust error handling and retry logic
4. **Performance**: Efficient API usage and response handling
5. **Usability**: Clear, intuitive API design

### Core Components

#### Base Client (`base.py`)

```python
class BaseClient:
    """Base HTTP client with retry logic and error handling."""

    def __init__(self, base_url: str, timeout: int = 30, retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry adapter."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session
```

#### Search Client (`search.py`)

```python
class SearchClient(BaseClient):
    """Client for Europe PMC search operations."""

    def search(self, query: str, **kwargs) -> List[Dict]:
        """Execute search query with parameters."""
        params = self._build_params(query, **kwargs)
        response = self._make_request("search", params)
        return self._parse_response(response)
```

#### Parser (`search_parser.py`)

```python
class ResponseParser:
    """Parse Europe PMC API responses in different formats."""

    @staticmethod
    def parse_json(response: Dict) -> List[Dict]:
        """Parse JSON response format."""

    @staticmethod
    def parse_xml(response: str) -> List[Dict]:
        """Parse XML response format."""
```

### Error Handling Strategy

```python
# Custom exception hierarchy
class EuropePMCError(Exception):
    """Base exception for Europe PMC operations."""

class APIError(EuropePMCError):
    """API request failed."""

class ValidationError(EuropePMCError):
    """Input validation failed."""

class RateLimitError(EuropePMCError):
    """Rate limit exceeded."""
```

### Performance Considerations

- **Connection Pooling**: Reuse HTTP connections
- **Rate Limiting**: Respect API limits
- **Caching**: Optional response caching
- **Pagination**: Efficient handling of large result sets
- **Memory Management**: Stream processing for large datasets

## Getting Help

- **Documentation**: Check the [API documentation](../api/README.md)
- **Issues**: Report bugs on [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
- **Discussions**: Ask questions in [GitHub Discussions](https://github.com/JonasHeinickeBio/pyEuropePMC/discussions)
- **Contributing**: See our [Contributing Guide](CONTRIBUTING.md)
