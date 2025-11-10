# QueryBuilder API Reference

The `QueryBuilder` class provides a fluent API for constructing complex Europe PMC search queries with type safety and validation.

## Class Overview

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder(validate=False)  # Optional validation
```

## Constructor

```python
QueryBuilder(validate: bool = False) -> QueryBuilder
```

**Parameters:**
- `validate` (bool, optional): Whether to validate queries using search-query package. Defaults to False.

## Core Methods

### keyword()

Add a keyword search term.

```python
keyword(term: str, field: FieldType | None = None) -> QueryBuilder
```

**Parameters:**
- `term` (str): Search term
- `field` (FieldType, optional): Field to search in

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.keyword("cancer").keyword("therapy", field="title")
```

### field()

Generic field search with optional value transformation.

```python
field(
    field_name: FieldType,
    value: str | int | bool,
    escape: bool = True,
    transform: Callable[[str | int | bool], str | int | bool] | None = None
) -> QueryBuilder
```

**Parameters:**
- `field_name` (FieldType): Field to search (e.g., "author", "title")
- `value` (str | int | bool): Search value
- `escape` (bool, optional): Whether to escape special characters. Defaults to True.
- `transform` (Callable, optional): Function to transform value before formatting

**Returns:** QueryBuilder (for method chaining)

**Examples:**
```python
# Basic field search
qb.field("author", "Smith J")

# With transformation
qb.field("pmcid", "1234567", transform=lambda x: f"PMC{x}" if not str(x).startswith("PMC") else str(x))
```

### date_range()

Add publication date constraints.

```python
date_range(
    start_year: int | None = None,
    end_year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None
) -> QueryBuilder
```

**Parameters:**
- `start_year` (int, optional): Start year (inclusive)
- `end_year` (int, optional): End year (inclusive)
- `start_date` (str, optional): Start date in YYYY-MM-DD format
- `end_date` (str, optional): End date in YYYY-MM-DD format

**Returns:** QueryBuilder (for method chaining)

**Examples:**
```python
# Year range
qb.date_range(start_year=2020, end_year=2023)

# Date range
qb.date_range(start_date="2020-01-01", end_date="2023-12-31")
```

### citation_count()

Add citation count filters.

```python
citation_count(min_count: int | None = None, max_count: int | None = None) -> QueryBuilder
```

**Parameters:**
- `min_count` (int, optional): Minimum citation count (inclusive)
- `max_count` (int, optional): Maximum citation count (inclusive)

**Returns:** QueryBuilder (for method chaining)

**Examples:**
```python
# Papers with at least 10 citations
qb.citation_count(min_count=10)

# Papers with 5-50 citations
qb.citation_count(min_count=5, max_count=50)
```

### pmcid()

Search by PMC ID.

```python
pmcid(pmcid: str) -> QueryBuilder
```

**Parameters:**
- `pmcid` (str): PMC ID (with or without "PMC" prefix)

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.pmcid("PMC1234567")  # Also accepts "1234567"
```

### source()

Search by data source.

```python
source(source: str) -> QueryBuilder
```

**Parameters:**
- `source` (str): Data source code (e.g., "MED", "PMC", "AGR")

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.source("MED")
```

### accession_type()

Search by accession type.

```python
accession_type(accession_type: str) -> QueryBuilder
```

**Parameters:**
- `accession_type` (str): Accession type (automatically lowercased)

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.accession_type("pdb")  # Automatically lowercased
```

### cites()

Search for papers that cite a specific article.

```python
cites(article_id: str, source: str = "med") -> QueryBuilder
```

**Parameters:**
- `article_id` (str): Article ID to find citations for
- `source` (str, optional): Data source. Defaults to "med".

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.cites("8521067", source="med")
```

## Logical Operators

### and_()

Add AND operator between query parts.

```python
and_() -> QueryBuilder
```

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.keyword("cancer").and_().keyword("therapy")
```

### or_()

Add OR operator between query parts.

```python
or_() -> QueryBuilder
```

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.keyword("cancer").or_().keyword("tumor")
```

### not_()

Add NOT operator before the next query part.

```python
not_() -> QueryBuilder
```

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.keyword("cancer").and_().not_().keyword("review")
```

## Advanced Methods

### group()

Add a grouped sub-query.

```python
group(builder: QueryBuilder) -> QueryBuilder
```

**Parameters:**
- `builder` (QueryBuilder): Sub-query to group

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
sub_query = QueryBuilder().keyword("cancer").or_().keyword("tumor")
qb.group(sub_query).and_().keyword("therapy")
```

### raw()

Add raw query string.

```python
raw(query_string: str) -> QueryBuilder
```

**Parameters:**
- `query_string` (str): Raw query string

**Returns:** QueryBuilder (for method chaining)

**Example:**
```python
qb.raw("(cancer OR tumor) AND therapy")
```

## Build & Validation

### build()

Build and return the final query string.

```python
build(validate: bool = True) -> str
```

**Parameters:**
- `validate` (bool, optional): Whether to validate the query. Defaults to True.

**Returns:** str - The constructed query string

**Example:**
```python
query = qb.keyword("cancer").and_().keyword("therapy").build()
print(query)  # "cancer AND therapy"
```

## Persistence Methods

### save()

Save query to JSON file in standard format.

```python
save(
    file_path: str,
    platform: str = "pubmed",
    authors: list[dict[str, str]] | None = None,
    record_info: dict[str, Any] | None = None,
    date_info: dict[str, str] | None = None,
    database: list[str] | None = None,
    include_generic: bool = False
) -> None
```

**Parameters:**
- `file_path` (str): Path to save JSON file
- `platform` (str, optional): Query platform. Defaults to "pubmed".
- `authors` (list[dict[str, str]], optional): Author information
- `record_info` (dict, optional): Additional record metadata
- `date_info` (dict, optional): Date information
- `database` (list[str], optional): Database information
- `include_generic` (bool, optional): Include generic query representation

### Class Methods

#### from_string()

Load query from string.

```python
@classmethod
from_string(
    query_string: str,
    platform: str = "pubmed",
    validate: bool = False
) -> QueryBuilder
```

**Parameters:**
- `query_string` (str): Query string to parse
- `platform` (str, optional): Platform syntax. Defaults to "pubmed".
- `validate` (bool, optional): Whether to validate. Defaults to False.

**Returns:** QueryBuilder instance

#### from_file()

Load query from JSON file.

```python
@classmethod
from_file(file_path: str, validate: bool = False) -> QueryBuilder
```

**Parameters:**
- `file_path` (str): Path to JSON file
- `validate` (bool, optional): Whether to validate. Defaults to False.

**Returns:** QueryBuilder instance

## Translation & Evaluation

### translate()

Translate query to another platform's syntax.

```python
translate(target_platform: str) -> str
```

**Parameters:**
- `target_platform` (str): Target platform ("pubmed", "wos", "ebsco", "generic")

**Returns:** str - Query in target platform syntax

**Example:**
```python
qb = QueryBuilder.from_string('("cancer"[Title])', platform="pubmed")
wos_query = qb.translate("wos")  # TI="cancer"
```

### to_query_object()

Convert to search-query Query object.

```python
to_query_object(platform: str = "pubmed") -> Any
```

**Parameters:**
- `platform` (str, optional): Platform for parsing. Defaults to "pubmed".

**Returns:** Query object from search-query package

### evaluate()

Evaluate search effectiveness against records.

```python
evaluate(records: dict[str, dict[str, str]], platform: str = "pubmed") -> dict[str, float]
```

**Parameters:**
- `records` (dict): Records with IDs as keys, containing 'title' and 'colrev_status'
- `platform` (str, optional): Platform for evaluation. Defaults to "pubmed".

**Returns:** dict with 'recall', 'precision', and 'f1_score'

## Systematic Review Integration

### log_to_search()

Log query to SearchLog for systematic review tracking.

```python
log_to_search(
    search_log: Any,
    database: str = "Europe PMC",
    filters: dict[str, Any] | None = None,
    results_returned: int | None = None,
    notes: str | None = None,
    raw_results: Any = None,
    raw_results_dir: str | None = None,
    platform: str | None = None,
    export_path: str | None = None
) -> None
```

**Parameters:**
- `search_log` (SearchLog): SearchLog instance to record query
- `database` (str, optional): Database name. Defaults to "Europe PMC".
- `filters` (dict, optional): Applied filters
- `results_returned` (int, optional): Number of results returned
- `notes` (str, optional): Additional notes
- `raw_results` (Any, optional): Raw API response
- `raw_results_dir` (str, optional): Directory for raw results
- `platform` (str, optional): Search platform used
- `export_path` (str, optional): Path to exported results

## Field Types

The `FieldType` literal type includes all 150+ searchable fields:

**Core Fields:** `title`, `abstract`, `author`, `journal`, `doi`, `pmid`, `pmcid`

**Date Fields:** `pub_year`, `first_pdate`, `e_pdate`, `update_date`

**Author Fields:** `affiliation`, `authorid`, `auth_first`, `auth_last`

**Content Fields:** `keyword`, `mesh`, `chemical`, `disease`, `gene_protein`

**Citation Fields:** `citation_count`, `cites`, `cited`, `reffed_by`

**Full-Text Fields:** `has_pdf`, `has_fulltext`, `open_access`, `in_pmc`

**And many more...** See [Field Metadata](field-metadata-structure.md) for complete list.

## Error Handling

QueryBuilder uses specific error codes:

- `QUERY001`: Empty or invalid query parameters
- `QUERY002`: Invalid date/year/citation values
- `QUERY003`: Incorrect operator usage
- `QUERY004`: Query parsing/validation failures
- `CONFIG003`: Missing search-query dependency

## Examples

### Basic Query Building

```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder()

# Simple keyword search
query1 = qb.keyword("machine learning").build()
# "machine learning"

# Field-specific search
query2 = qb.field("author", "Smith J").build()
# "AUTH:Smith J"

# Complex query with operators
query3 = (qb
    .keyword("cancer", field="title")
    .and_()
    .keyword("therapy")
    .and_()
    .date_range(start_year=2020)
    .build())
# "(TITLE:cancer) AND therapy AND (PUB_YEAR:[2020 TO *])"
```

### Advanced Query Patterns

```python
# Citation-based filtering
query = (qb
    .keyword("CRISPR")
    .and_()
    .citation_count(min_count=50)
    .build())

# Multi-field search with OR logic
query = (qb
    .field("title", "machine learning")
    .or_()
    .field("abstract", "machine learning")
    .and_()
    .field("pub_year", 2023)
    .build())

# Complex nested query
sub_query = QueryBuilder().keyword("cancer").or_().keyword("tumor")
main_query = (qb
    .group(sub_query)
    .and_()
    .field("journal", "Nature")
    .build())
```

### Systematic Review Workflow

```python
from pyeuropepmc.utils.search_logging import start_search

# Start systematic review log
log = start_search("CRISPR Review", executed_by="Researcher Name")

# Build and execute query
qb = QueryBuilder()
query = (qb
    .keyword("CRISPR")
    .and_()
    .keyword("gene editing")
    .and_()
    .date_range(start_year=2018)
    .build())

# Log the search
qb.log_to_search(
    search_log=log,
    filters={"date_range": "2018+", "keywords": ["CRISPR", "gene editing"]},
    results_returned=150,
    notes="Initial broad search for CRISPR literature"
)

# Save the log
log.save("systematic_review_searches.json")
```

### Query Persistence

```python
# Save query
qb.save("my_search.json",
        authors=[{"name": "John Doe", "ORCID": "0000-0000-0000-0001"}],
        date_info={"data_entry": "2025-11-07", "search_conducted": "2025-11-07"})

# Load query
loaded_qb = QueryBuilder.from_file("my_search.json")
translated = loaded_qb.translate("wos")  # Translate to Web of Science syntax
```

See Also:
- [Query Builder Features](../features/query-builder-load-save-translate.md)
- [Systematic Review Tracking](../features/systematic-review-tracking.md)
- [Field Metadata](field-metadata-structure.md)</content>
<parameter name="filePath">/home/jhe24/AID-PAIS/pyEuropePMC_project/docs/api/query-builder.md
