# QueryBuilder - Advanced Query Construction for Europe PMC

The `QueryBuilder` class provides a fluent, type-safe API for constructing complex search queries for Europe PMC. It supports field-specific searches, logical operators, date ranges, citation filters, and validation through the CoLRev search-query package.

## Features

- **Fluent API**: Chain methods for natural query construction
- **Type-Safe**: Full type annotations and IDE autocomplete support
- **Field-Specific Helpers**: Built-in methods for common search fields
- **Logical Operators**: Support for AND, OR, and NOT operations
- **Query Grouping**: Create complex nested queries
- **Validation**: Optional integration with CoLRev search-query for syntax validation
- **Error Handling**: Clear error messages with custom exceptions

## Installation

The query builder is included in PyEuropePMC. For optional query validation support:

```bash
pip install pyeuropepmc[query-builder]
```

Or install the validation package separately:

```bash
pip install search-query
```

## Quick Start

### Basic Query

```python
from pyeuropepmc import QueryBuilder

# Simple keyword search
qb = QueryBuilder(validate=False)
query = qb.keyword("cancer").build()
# Result: "cancer"
```

### Field-Specific Search

```python
# Search in specific fields
qb = QueryBuilder(validate=False)
query = qb.keyword("CRISPR", field="title").build()
# Result: "CRISPR:TITLE"
```

### Using Logical Operators

```python
# AND operator
qb = QueryBuilder(validate=False)
query = (qb
    .keyword("cancer")
    .and_()
    .keyword("treatment")
    .build())
# Result: "cancer AND treatment"

# OR operator
qb = QueryBuilder(validate=False)
query = (qb
    .keyword("cancer")
    .or_()
    .keyword("tumor")
    .build())
# Result: "cancer OR tumor"

# NOT operator
qb = QueryBuilder(validate=False)
query = (qb
    .keyword("cancer")
    .and_()
    .not_()
    .keyword("review")
    .build())
# Result: "cancer AND NOT review"
```

## Advanced Features

### Date Range Filtering

```python
# Year range
qb = QueryBuilder(validate=False)
query = qb.date_range(start_year=2020, end_year=2023).build()
# Result: "(PUB_YEAR:[2020 TO 2023])"

# Open-ended range
query = qb.date_range(start_year=2020).build()
# Result: "(PUB_YEAR:[2020 TO *])"

# Specific dates
query = qb.date_range(
    start_date="2020-01-01",
    end_date="2023-12-31"
).build()
```

### Field-Specific Helpers

```python
# Author search
query = qb.author("Smith J").build()

# Journal search
query = qb.journal("Nature").build()

# MeSH term search
query = qb.mesh_term("Neoplasms").build()

# Citation count filter
query = qb.citation_count(min_count=10, max_count=100).build()

# Open access filter
query = qb.open_access(True).build()

# PDF availability
query = qb.has_pdf(True).build()

# Full text availability
query = qb.has_full_text(True).build()
```

### Identifier Searches

```python
# PMC ID
query = qb.pmcid("PMC1234567").build()

# PubMed ID
query = qb.pmid("12345678").build()

# DOI
query = qb.doi("10.1234/example.2023.001").build()
```

### Query Grouping

```python
# Create a sub-query
disease_terms = (QueryBuilder(validate=False)
    .keyword("cancer")
    .or_()
    .keyword("tumor"))

# Use the sub-query in a larger query
query = (QueryBuilder(validate=False)
    .group(disease_terms)
    .and_()
    .author("Smith J")
    .build())
# Result: "(cancer OR tumor) AND \"Smith J\":AUTH"
```

### Raw Queries

```python
# For complex syntax not directly supported
query = qb.raw("(cancer OR tumor) AND treatment").build()
```

## Real-World Examples

### Recent High-Impact Cancer Research

```python
from pyeuropepmc import QueryBuilder, SearchClient

qb = QueryBuilder(validate=False)
query = (qb
    .keyword("cancer", field="title")
    .and_()
    .date_range(start_year=2020)
    .and_()
    .open_access(True)
    .and_()
    .citation_count(min_count=10)
    .build())

with SearchClient() as client:
    results = client.search(query, pageSize=25)
    print(f"Found {results['hitCount']} papers")
```

### Author-Specific CRISPR Papers in Nature

```python
query = (QueryBuilder(validate=False)
    .author("Smith J")
    .and_()
    .journal("Nature")
    .and_()
    .keyword("CRISPR", field="title")
    .build())
```

### Multiple MeSH Terms with Filters

```python
query = (QueryBuilder(validate=False)
    .mesh_term("Neoplasms")
    .and_()
    .mesh_term("Drug Therapy")
    .and_()
    .date_range(start_year=2018, end_year=2023)
    .and_()
    .has_full_text(True)
    .build())
```

## Query Validation

When the `search-query` package is installed, queries can be validated:

```python
# Enable validation (default if search-query is installed)
qb = QueryBuilder(validate=True)

try:
    query = qb.keyword("cancer").and_().author("Smith J").build()
except QueryBuilderError as e:
    print(f"Query validation failed: {e}")
```

## Supported Europe PMC Fields

The following field types are supported:

- `title` - Article title
- `abstract` - Abstract text
- `auth_man` - Author manuscript
- `author` - Author name
- `journal` - Journal name
- `mesh` - MeSH terms
- `grant_agency` - Grant agency
- `grant_id` - Grant ID
- `pub_type` - Publication type
- `pub_year` - Publication year
- `open_access` - Open access status
- `has_pdf` - PDF availability
- `has_full_text` - Full text availability
- `citation_count` - Citation count
- `pmcid` - PMC ID
- `pmid` - PubMed ID
- `doi` - Digital Object Identifier

## Error Handling

The QueryBuilder includes comprehensive error handling:

```python
from pyeuropepmc.exceptions import QueryBuilderError

try:
    qb = QueryBuilder(validate=False)
    # This will raise an error: can't end with operator
    query = qb.keyword("cancer").and_().build()
except QueryBuilderError as e:
    print(f"Error: {e}")
```

## API Reference

### QueryBuilder

```python
QueryBuilder(validate: bool = True)
```

**Methods:**

- `keyword(term: str, field: FieldType | None = None) -> QueryBuilder`
- `author(author_name: str) -> QueryBuilder`
- `journal(journal_name: str) -> QueryBuilder`
- `mesh_term(mesh: str) -> QueryBuilder`
- `date_range(start_year: int | None = None, end_year: int | None = None, start_date: str | None = None, end_date: str | None = None) -> QueryBuilder`
- `citation_count(min_count: int | None = None, max_count: int | None = None) -> QueryBuilder`
- `open_access(is_open_access: bool = True) -> QueryBuilder`
- `has_pdf(has_pdf: bool = True) -> QueryBuilder`
- `has_full_text(has_text: bool = True) -> QueryBuilder`
- `pmcid(pmcid: str) -> QueryBuilder`
- `pmid(pmid: str | int) -> QueryBuilder`
- `doi(doi: str) -> QueryBuilder`
- `and_() -> QueryBuilder`
- `or_() -> QueryBuilder`
- `not_() -> QueryBuilder`
- `group(builder: QueryBuilder) -> QueryBuilder`
- `raw(query_string: str) -> QueryBuilder`
- `build(validate: bool = True) -> str`

## Integration with CoLRev Search-Query

The QueryBuilder optionally integrates with the [CoLRev search-query](https://colrev-environment.github.io/search-query/) package for:

- Syntax validation
- Query cleaning and normalization
- Cross-platform query translation

When `search-query` is installed, queries are automatically validated before execution.

## Examples

For more examples, see:
- `examples/08-query-builder/query_builder_demo.py` - Comprehensive usage examples
- `tests/query_builder/test_query_builder.py` - Unit test examples

## License

Part of PyEuropePMC - MIT License
