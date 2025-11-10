# QueryBuilder Load/Save/Translate Feature

## Overview

The QueryBuilder now supports loading, saving, and translating queries using the `search-query` package integration. This enables:

- **Import/Export**: Save and load queries in standardized JSON format
- **Platform Translation**: Convert queries between PubMed, Web of Science, EBSCO, etc.
- **Query Objects**: Access to underlying search-query Query objects for advanced manipulation
- **Search Evaluation**: Assess search effectiveness with recall/precision metrics

## Installation

To use these features, install the optional `search-query` package:

```bash
pip install search-query
```

Or install pyEuropePMC with the optional dependency:

```bash
pip install pyeuropepmc[search-query]
```

## New Methods

### Loading Queries

#### `QueryBuilder.from_string(query_string, platform="pubmed", validate=False)`

Load a query from a string by parsing it.

```python
from pyeuropepmc import QueryBuilder

# Load PubMed query
qb = QueryBuilder.from_string("cancer AND treatment", platform="pubmed")
print(qb.build())  # cancer AND treatment

# Load Web of Science query
qb = QueryBuilder.from_string("TI=cancer", platform="wos")
```

#### `QueryBuilder.from_file(file_path, validate=False)`

Load a query from a JSON file in standard format (Haddaway et al. 2022).

```python
from pyeuropepmc import QueryBuilder

# Load from file
qb = QueryBuilder.from_file("my-search.json")
query = qb.build()
```

JSON file format:
```json
{
    "search_string": "cancer AND treatment",
    "platform": "pubmed",
    "version": "1",
    "authors": [{"name": "John Doe", "ORCID": "0000-0000-0000-0001"}],
    "date": {"data_entry": "2025-01-01", "search_conducted": "2025-01-01"},
    "database": ["PubMed", "PMC"],
    "record_info": {}
}
```

### Saving Queries

#### `save(file_path, platform="pubmed", authors=None, record_info=None, date_info=None, database=None, include_generic=False)`

Save the query to a JSON file with metadata.

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder()
query = qb.keyword("cancer").and_().keyword("treatment")

qb.save(
    "my-search.json",
    platform="pubmed",
    authors=[{"name": "Jane Smith", "ORCID": "0000-0000-0000-0002"}],
    date_info={"search_conducted": "2025-11-06"},
    database=["PubMed", "PMC"],
    record_info={"project": "Cancer Research Review"}
)
```

### Translating Queries

#### `translate(target_platform)`

Translate the query to another platform's syntax.

```python
from pyeuropepmc import QueryBuilder

# Start with PubMed query
qb = QueryBuilder.from_string("cancer AND treatment", platform="pubmed")

# Translate to Web of Science
wos_query = qb.translate("wos")
print(wos_query)  # ALL=(cancer AND treatment)

# Translate to generic format
generic_query = qb.translate("generic")
```

Supported platforms:
- `pubmed` - PubMed/MEDLINE
- `wos` - Web of Science
- `ebsco` - EBSCO (partial support)
- `generic` - Platform-independent format

### Query Objects

#### `to_query_object(platform="pubmed")`

Convert to a search-query Query object for advanced manipulation.

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder()
query = qb.keyword("cancer").and_().keyword("treatment")

# Get Query object
query_obj = qb.to_query_object()
print(type(query_obj))  # <class 'search_query.query_and.AndQuery'>

# Access search-query methods
query_str = query_obj.to_string()
```

### Search Evaluation

#### `evaluate(records, platform="pubmed")`

Evaluate search effectiveness against a set of records.

```python
from pyeuropepmc import QueryBuilder

records = {
    "r1": {"title": "Cancer treatment research", "colrev_status": "rev_included"},
    "r2": {"title": "Cancer diagnosis methods", "colrev_status": "rev_included"},
    "r3": {"title": "Unrelated topic", "colrev_status": "rev_excluded"}
}

qb = QueryBuilder.from_string("cancer[title]", platform="pubmed")
results = qb.evaluate(records)

print(f"Recall: {results['recall']:.2f}")
print(f"Precision: {results['precision']:.2f}")
print(f"F1 Score: {results['f1_score']:.2f}")
```

## Workflow Examples

### Round-Trip: Load → Translate → Save

```python
from pyeuropepmc import QueryBuilder

# 1. Load PubMed query
qb_pubmed = QueryBuilder.from_file("pubmed-search.json")

# 2. Translate to Web of Science
wos_query = qb_pubmed.translate("wos")

# 3. Create new QueryBuilder with translated query
qb_wos = QueryBuilder.from_string(wos_query, platform="wos")

# 4. Save WoS version
qb_wos.save("wos-search.json", platform="wos")
```

### Build → Save → Load

```python
from pyeuropepmc import QueryBuilder

# Build query
qb1 = QueryBuilder()
query = qb1.keyword("CRISPR", field="title").and_().keyword("gene editing")

# Save
qb1.save("crispr-search.json", platform="pubmed")

# Load later
qb2 = QueryBuilder.from_file("crispr-search.json")
results = client.search(qb2.build())
```

## Implementation Details

### Architecture

- **Integration Point**: Uses `search-query` package for parsing, validation, and translation
- **Caching**: Parsed Query objects are cached in `_parsed_query` attribute
- **Platform Support**: Works with Europe PMC syntax internally, translates for other platforms
- **Optional Dependency**: All features gracefully fail with ImportError if search-query not installed

### Type Safety

- All methods have full type annotations
- Return types are properly typed (str, dict, Query objects)
- Mypy strict mode compatible

### Error Handling

- Invalid queries raise `QueryBuilderError` with context
- File not found raises standard `FileNotFoundError`
- Platform translation errors include helpful messages

## Tests

### Unit Tests

Located in `tests/query_builder/unit/test_query_load_save_translate.py`:

- **From String**: 7 tests covering various parsing scenarios
- **From File**: 3 tests for JSON file loading
- **Save**: 3 tests for saving with metadata
- **Translate**: 4 tests for platform translation
- **To Query Object**: 3 tests for Query object conversion
- **Evaluate**: 3 tests (currently skipped pending field mapping fixes)
- **Integration**: 2 tests for round-trip workflows
- **Error Handling**: 7 tests for missing package scenarios

Total: 27 passing tests, 3 skipped

### Running Tests

```bash
# Run all load/save/translate tests
pytest tests/query_builder/unit/test_query_load_save_translate.py -v

# Run with coverage
pytest tests/query_builder/unit/test_query_load_save_translate.py --cov=pyeuropepmc.query_builder

# Run only specific test class
pytest tests/query_builder/unit/test_query_load_save_translate.py::TestQueryBuilderFromString -v
```

## Demo Script

A comprehensive demo is available at `examples/08-query-builder/load_save_translate_demo.py`:

```bash
python examples/08-query-builder/load_save_translate_demo.py
```

Demonstrates:
1. Building and saving queries
2. Loading queries from files
3. Loading queries from strings
4. Translating between platforms
5. Round-trip workflows
6. Converting to Query objects

## Limitations

1. **Evaluate Method**: Currently limited due to field mapping differences between Europe PMC and search-query. Tests are skipped pending investigation.

2. **Platform Syntax**: Europe PMC uses its own field syntax (e.g., `TITLE:`, `OPEN_ACCESS:`) which may differ from PubMed standard fields. Translation handles common cases but may encounter issues with Europe PMC-specific fields.

3. **Generic Query**: The `include_generic=True` option in `save()` may fail for Europe PMC-specific syntax that search-query doesn't recognize.

## References

- Haddaway, N. R., Grainger, M. J., & Gray, C. T. (2022). citationchaser: A tool for transparent and efficient forward and backward citation chasing in systematic searching. *Research Synthesis Methods*, 13(4), 533-545. DOI: 10.1002/jrsm.1563

- search-query documentation: https://github.com/CoLRev-Environment/search-query

## Future Enhancements

1. **Evaluate Method**: Implement proper field mapping for evaluation
2. **More Platforms**: Add support for additional database platforms
3. **Query Optimization**: Integrate search-query's query improvement features
4. **Batch Operations**: Support for loading/saving multiple queries at once
5. **Validation Presets**: Pre-configured validation rules for different use cases
