# QueryBuilder Tests

This directory contains tests for the `QueryBuilder` class, organized into unit and functional test suites.

## Test Organization

### Unit Tests (`unit/`)

Unit tests verify the QueryBuilder logic **without making API calls**:

- ✅ Query string construction
- ✅ Field validation
- ✅ Operator chaining (AND, OR, NOT)
- ✅ Date range formatting
- ✅ Citation count validation
- ✅ Special methods (pmcid, source, accession_type, cites)
- ✅ Error handling and validation

**Run unit tests:**
```bash
pytest tests/query_builder/unit/ -v
```

### Functional Tests (`functional/`)

Functional tests validate QueryBuilder **with real Europe PMC API calls**:

- ✅ Each field produces valid queries
- ✅ Field filters reduce result counts
- ✅ Field names appear in request queryString
- ✅ Queries return results (hitCount > 0)
- ✅ Complex queries with multiple fields work
- ✅ Special methods integrate correctly

**Run functional tests:**
```bash
# All functional tests (slow - makes many API calls)
pytest tests/query_builder/functional/ -v -m functional

# Run a specific test
pytest tests/query_builder/functional/test_field_api_integration.py::TestFieldAPIIntegration::test_title_field -v

# Run tests for specific fields
pytest tests/query_builder/functional/ -k "test_title_field or test_author_field" -v
```

**Note:** Functional tests are marked with `@pytest.mark.functional` and `@pytest.mark.slow` for selective execution.

## Test Coverage by Field

The functional test suite validates all major field categories:

### Core Bibliographic
- `TITLE`, `ABSTRACT`, `AUTH` (author), `JOURNAL`, `ISSN`, `PUB_YEAR`, `DOI`, `PMID`, `PMCID`

### Date Fields
- Date ranges (`PUB_YEAR:[X TO Y]`)

### Author & Affiliation
- `AFF` (affiliation), `INVESTIGATOR`

### Article Metadata
- `LANG` (language), `GRANT_AGENCY`, `KEYWORD`, `MESH`, `CHEM` (chemical), `DISEASE`, `GENE_PROTEIN`, `ORGANISM`

### Full Text Availability
- `HAS_ABSTRACT`, `HAS_PDF`, `OPEN_ACCESS`, `IN_PMC`, `IN_EPMC`

### Database Cross-References
- `HAS_UNIPROT`, `HAS_PDB`

### Citations
- `CITED` (citation count), `CITES`

### Collection Metadata
- `SRC` (source), `LICENSE`

### Books
- `HAS_BOOK`, `ISBN`

### Accession
- `ACCESSION_TYPE`

### Section-Level Search
- `INTRO`, `METHODS`, `RESULTS`, `DISCUSS`, `CONCL`, `BODY`

## Test Patterns

### Unit Test Pattern
```python
def test_field_method(self) -> None:
    """Test field() method builds correct query."""
    qb = QueryBuilder()
    query = qb.field("title", "CRISPR").build()
    assert query == "TITLE:CRISPR"
```

### Functional Test Pattern
```python
def test_field_api_integration(self, client: SearchClient) -> None:
    """Test field with real API call."""
    qb = QueryBuilder(validate=False)
    query = qb.field("title", "CRISPR").build(validate=False)
    base_query = "CRISPR"

    # Verifies:
    # 1. Field appears in request
    # 2. Results are returned
    # 3. Field filter reduces results
    self._test_field_reduces_results(client, query, base_query, "TITLE")
```

## Running All Tests

```bash
# Run all QueryBuilder tests (unit + functional)
pytest tests/query_builder/ -v

# Run only unit tests (fast)
pytest tests/query_builder/unit/ -v

# Run only functional tests (slow)
pytest tests/query_builder/functional/ -v -m functional

# Run with coverage
pytest tests/query_builder/ --cov=src/pyeuropepmc/query_builder --cov-report=html
```

## Test Configuration

Functional tests include:
- **Rate limiting**: 500ms delay between tests
- **Validation disabled**: Europe PMC syntax differs from PubMed
- **Small page sizes**: `page_size=5` to minimize API load
- **Pytest markers**: `@pytest.mark.functional` and `@pytest.mark.slow`

## Adding New Tests

### Adding a Unit Test

Add to `unit/test_query_builder.py`:

```python
def test_new_field_method(self) -> None:
    """Test new_field() method."""
    qb = QueryBuilder()
    query = qb.field("new_field", "value").build()
    assert query == "NEW_FIELD:value"
```

### Adding a Functional Test

Add to `functional/test_field_api_integration.py`:

```python
def test_new_field_api_integration(self, client: SearchClient) -> None:
    """Test NEW_FIELD with real API call."""
    qb = QueryBuilder(validate=False)
    query = qb.field("new_field", "value").build(validate=False)
    base_query = "value"

    self._test_field_reduces_results(client, query, base_query, "NEW_FIELD")
```

## CI/CD Integration

In CI pipelines:
- Run **unit tests** on every commit (fast)
- Run **functional tests** on PR merge or nightly (slow)

```yaml
# Example GitHub Actions
- name: Run unit tests
  run: pytest tests/query_builder/unit/ -v

- name: Run functional tests (on schedule only)
  if: github.event_name == 'schedule'
  run: pytest tests/query_builder/functional/ -v -m functional
```
