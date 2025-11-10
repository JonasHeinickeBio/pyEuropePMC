# Systematic Review Tracking with QueryBuilder

## Overview

The QueryBuilder now integrates with PyEuropePMC's systematic review tracking system to maintain PRISMA/Cochrane-compliant records of all searches performed. This enables researchers to:

- Track all search queries with **exact syntax and parameters used in API calls**
- Record filters, platforms, and search dates automatically
- Save raw results for auditability
- Generate PRISMA flow diagram data
- Export comprehensive search logs for methods sections

## Key Principle: Exact API Query Logging

**For full reproducibility, systematic review tracking logs the exact query string sent to the Europe PMC API.** This ensures that:

- The logged query can be directly copied and pasted into API calls
- Search results can be exactly replicated
- All query parameters, operators, and field specifications are preserved
- Raw API responses can be saved for complete audit trails

### What Gets Logged

When you call `qb.log_to_search()`, the system captures:

1. **Exact API Query String**: The result of `qb.build()` - the literal string sent to Europe PMC
2. **Query Components**: Individual parts that make up the query (keywords, fields, operators)
3. **Search Parameters**: Page size, result limits, sort order
4. **API Response**: Raw JSON response for complete auditability
5. **Metadata**: Timestamps, platform versions, researcher information

**Note**: Date ranges without an end year use the current year. For example, `date_range(start_year=2020)` becomes `(PUB_YEAR:[2020 TO 2025])` in 2025.

### Example Logged Query

```python
qb = QueryBuilder()
qb.keyword("cancer").and_().field("open_access", True).and_().citation_count(min_count=10)
query = qb.build()
# query = "cancer AND OPEN_ACCESS:y AND CITED:[10 TO *]"

# This exact string gets logged and can be reused:
# client.search("cancer AND OPEN_ACCESS:y AND CITED:[10 TO *]")
```

## Installation

The systematic review tracking features are built into PyEuropePMC and require no additional dependencies:

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search, prisma_summary
```

## Quick Start

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search

# 1. Start a systematic review search log
log = start_search(
    title="Cancer Immunotherapy Review 2024",
    executed_by="Jane Doe, Research Team"
)

# 2. Build and execute a query
qb = QueryBuilder()
query = (qb
    .keyword("cancer", field="title")
    .and_()
    .keyword("immunotherapy", field="abstract")
    .and_()
    .date_range(start_year=2020, end_year=2024)
    .build())

# The query variable now contains: "TITLE:cancer AND ABSTRACT:immunotherapy AND (PUB_YEAR:[2020 TO 2024])"
# This is the EXACT string sent to the Europe PMC API

# 3. Log the query with metadata
qb.log_to_search(
    search_log=log,
    filters={
        "date_range": "2020-2024",
        "fields": ["title", "abstract"],
        "open_access": True
    },
    results_returned=342,
    notes="Initial broad search",
    platform="Europe PMC API v6.9"
)

# 4. Save the search log
log.save("systematic_review_searches.json")
```

## API Reference

### `QueryBuilder.log_to_search()`

Log a query to a SearchLog for systematic review tracking.

**Parameters:**
- `search_log` (SearchLog): The SearchLog instance to record this query in
- `database` (str, optional): Database name (default: "Europe PMC")
- `filters` (dict, optional): Additional filters applied
- `results_returned` (int, optional): Number of results returned
- `notes` (str, optional): Additional notes about this search
- `raw_results` (Any, optional): Raw API response to save
- `raw_results_dir` (str, optional): Directory to save raw results
- `platform` (str, optional): Search platform used (e.g., "API v6.9")
- `export_path` (str, optional): Path to exported results file

**Example:**
```python
qb.log_to_search(
    search_log=log,
    database="Europe PMC",
    filters={"year": "2020+", "open_access": True},
    results_returned=150,
    notes="Search for open access papers since 2020",
    platform="API v6.9"
)
```

## Workflow Examples

### Basic Search Tracking

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search

# Start a new review
log = start_search("My Systematic Review", executed_by="Research Team")

# Build and log a query
qb = QueryBuilder()
qb.keyword("CRISPR").and_().field("open_access", True)
qb.log_to_search(log, results_returned=125)

# Save the log
log.save("searches.json")
```

### Multi-Query Tracking

```python
log = start_search("Multi-Database Review")

# Query 1: Broad search
qb1 = QueryBuilder()
qb1.keyword("cancer").and_().date_range(start_year=2020)
qb1.log_to_search(log, results_returned=1250, notes="Broad cancer search")

# Query 2: Specific search
qb2 = QueryBuilder()
qb2.keyword("checkpoint inhibitor").and_().field("mesh", "Neoplasms")
qb2.log_to_search(log, results_returned=487, notes="Checkpoint inhibitors")

# Query 3: Clinical trials
qb3 = QueryBuilder()
qb3.keyword("immunotherapy").and_().field("pub_type", "Clinical Trial")
qb3.log_to_search(log, results_returned=156, notes="Clinical trials only")

print(f"Logged {len(log.entries)} queries")
```

### Complete PRISMA Workflow

```python
from pyeuropepmc.utils.search_logging import (
    start_search,
    record_results,
    prisma_summary
)

# Initialize review
log = start_search(
    "Cancer Immunotherapy Systematic Review 2024",
    executed_by="Dr. Smith, Dr. Jones"
)

# Perform multiple searches
qb1 = QueryBuilder()
qb1.keyword("cancer immunotherapy").and_().date_range(2020, 2024)
qb1.log_to_search(log, results_returned=1842, filters={"years": "2020-2024"})

qb2 = QueryBuilder()
qb2.keyword("checkpoint inhibitor").and_().field("mesh", "Neoplasms")
qb2.log_to_search(log, results_returned=734, filters={"mesh": "Neoplasms"})

# Record deduplication and screening results
record_results(log, deduplicated_total=2150, final_included=67)

# Save complete log
log.save("cancer_immunotherapy_review.json")

# Generate PRISMA summary for methods section
summary = prisma_summary(log)
print(f"Total records identified: {summary['total_records_identified']}")
print(f"After deduplication: {summary['deduplicated_total']}")
print(f"Studies included: {summary['final_included']}")
```

### Saving Raw Results for Auditability

```python
log = start_search("Auditable Search")

# Simulate API response
raw_results = {
    "hitCount": 150,
    "resultList": {"result": [...]},
}

qb = QueryBuilder()
qb.keyword("cancer").and_().field("open_access", True)

# Save raw results to file
qb.log_to_search(
    log,
    results_returned=150,
    raw_results=raw_results,
    raw_results_dir="./raw_results"
)

# The raw results file path is stored in the log
print(f"Raw results saved to: {log.entries[0].raw_results_path}")
```

## Search Log Structure

The saved JSON file contains the **exact API query string** that was sent to Europe PMC:

```json
{
  "title": "Cancer Immunotherapy Review 2024",
  "executed_by": "Jane Doe, Research Team",
  "created_at": "2024-11-06T12:00:00",
  "last_updated": "2024-11-06T14:30:00",
  "entries": [
    {
      "database": "Europe PMC",
      "query": "TITLE:cancer AND ABSTRACT:immunotherapy AND (PUB_YEAR:[2020 TO 2024])",
      "filters": {
        "date_range": "2020-2024",
        "fields": ["title", "abstract"]
      },
      "date_run": "2024-11-06T12:15:00",
      "results_returned": 342,
      "notes": "Initial broad search",
      "platform": "Europe PMC API v6.9",
      "raw_results_path": "./raw_results/Europe_PMC_results_20241106.json"
    }
  ],
  "deduplicated_total": 2150,
  "final_included": 67
}
```

**Important**: The `"query"` field contains the exact string that was passed to the Europe PMC search API. This ensures complete reproducibility - you can copy this query string directly into a new API call and get identical results.

## PRISMA Compliance

The search logs are fully compliant with PRISMA 2020 guidelines and can be used for:

1. **Methods Section**: Complete documentation of search strategies
2. **PRISMA Flow Diagram**: Exact numbers for each stage
3. **Supplementary Materials**: Detailed search strategies
4. **Audit Trails**: Full reproducibility with raw results

### Generating PRISMA Flow Diagrams

The exported search log data can be used with the official PRISMA flow diagram tool:
https://estech.shinyapps.io/prisma_flowdiagram/

```python
from pyeuropepmc.utils.search_logging import prisma_summary

summary = prisma_summary(log)
# Use summary data in PRISMA flow diagram tool
```

## Integration with Search Clients

```python
from pyeuropepmc import QueryBuilder, SearchClient
from pyeuropepmc.utils.search_logging import start_search

# Initialize
log = start_search("My Review")
client = SearchClient()

# Build query
qb = QueryBuilder()
query = qb.keyword("CRISPR").and_().date_range(start_year=2020).build()

# query now contains: "CRISPR AND (PUB_YEAR:[2020 TO 2025])"
# This exact string is sent to the API

# Execute search
response = client.search(query, pageSize=100)
results_count = response.get("hitCount", 0)

# Log the search - captures the exact API query used
qb.log_to_search(
    log,
    results_returned=results_count,
    raw_results=response,
    raw_results_dir="./search_results",
    filters={"page_size": 100}
)

# The log entry will contain:
# "query": "CRISPR AND (PUB_YEAR:[2020 TO 2025])"

# Save log
log.save("review_searches.json")
```

**Reproducibility Guarantee**: The logged query string can be directly reused:

```python
# Later, to replicate the exact same search:
logged_query = log.entries[0]["query"]  # "CRISPR AND (PUB_YEAR:[2020 TO 2025])"
new_response = client.search(logged_query, pageSize=100)
# Results will be identical to the original search
```

## Best Practices

1. **Log Exact API Queries**: Always use `qb.log_to_search()` after building queries to capture the precise API call
2. **Save Raw Results**: Store complete API responses for full auditability
3. **Document Parameters**: Record all search parameters (pageSize, sort, etc.) used with the query
4. **Version Tracking**: Note API versions and platform details for reproducibility
5. **Regular Saves**: Save the log after each search session
6. **Peer Review**: Include the complete search log in protocol review
7. **Test Reproducibility**: Verify that logged queries produce identical results when rerun

### Reproducibility Checklist

- ✅ Query string matches exact API call
- ✅ All search parameters documented
- ✅ Raw API response saved
- ✅ Timestamps and versions recorded
- ✅ Query can be directly copied and reused

## Example: Complete Systematic Review

```python
from pyeuropepmc import QueryBuilder, SearchClient
from pyeuropepmc.utils.search_logging import (
    start_search,
    record_results,
    prisma_summary
)

# 1. Initialize review
log = start_search(
    "CRISPR Gene Editing Systematic Review 2024",
    executed_by="Smith J, Doe J, Brown M"
)

client = SearchClient()

# 2. Perform multiple searches
searches = [
    ("CRISPR", {"type": "broad"}),
    ("gene editing AND clinical", {"type": "clinical"}),
    ("CRISPR AND therapy", {"type": "therapeutic"}),
]

for search_term, filters in searches:
    qb = QueryBuilder()
    qb.keyword(search_term).and_().date_range(2020, 2024)
    query = qb.build()

    # Execute search
    response = client.search(query)
    count = response.get("hitCount", 0)

    # Log search
    qb.log_to_search(
        log,
        results_returned=count,
        filters=filters,
        raw_results=response,
        raw_results_dir="./raw_results",
        notes=f"Search: {search_term}"
    )

# 3. Record processing results
record_results(log, deduplicated_total=1523, final_included=78)

# 4. Save everything
log.save("crispr_review_searches.json")

# 5. Generate PRISMA data
summary = prisma_summary(log)
print(f"\nPRISMA Summary:")
print(f"  Records identified: {summary['total_records_identified']}")
print(f"  After deduplication: {summary['deduplicated_total']}")
print(f"  Studies included: {summary['final_included']}")
```

## See Also

- [Search Logging Utilities](../advanced/search-logging.md)
- [QueryBuilder Load/Save/Translate](./query-builder-load-save-translate.md)
- [PRISMA 2020 Guidelines](http://www.prisma-statement.org/)
- [Cochrane Handbook](https://training.cochrane.org/handbook)
