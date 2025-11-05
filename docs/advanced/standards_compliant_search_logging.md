# Standards-Compliant Search Logging for Systematic Reviews

## Overview

PyEuropePMC provides a robust, standards-compliant search logging utility designed for systematic reviews. This utility ensures full traceability, reproducibility, and auditability of literature search strategies, supporting PRISMA and Cochrane requirements. It enables:

- **Structured logging** of all search queries and parameters
- **Optional persistence** of raw search results for audit trails
- **Cryptographic signing and archiving** of search logs and results
- **Publication-ready output** for inclusion in systematic review appendices

## Key Features

- **PRISMA/Cochrane Compliance**: All search strings, filters, and result counts are logged in a structured, exportable format.
- **Raw Results Provenance**: Optionally persist raw search results to separate files for later verification or re-analysis.
- **Cryptographic Signing**: Digitally sign logs and results to prove integrity and timestamp provenance.
- **Archiving**: Zip logs, results, and signatures for easy sharing and publication.
- **Robust Error Handling**: All operations are logged and wrapped in project-specific exceptions.

## Usage Example

```python
from pyeuropepmc.utils.search_logging import (
    SearchLog, start_search, record_query, record_results, prisma_summary,
    sign_and_zip_results
)

# Start a new search log
log = start_search(review_name="My Systematic Review", reviewer="Alice Smith")

# Record a search query
record_query(log, query="cancer AND PUB_YEAR:2023", database="Europe PMC", filters={"open_access": True})

# Record search results (optionally persist raw results)
results = client.search("cancer AND PUB_YEAR:2023")
record_results(log, query="cancer AND PUB_YEAR:2023", results=results, persist_raw=True, raw_results_path="raw_results.json")

# Generate a PRISMA-compliant summary
summary = prisma_summary(log)
print(summary)

# Sign and archive logs/results
sign_and_zip_results(
    files=["search_log.json", "raw_results.json"],
    cert_path="my_cert.pem",
    key_path="my_key.pem",
    output_zip="search_log_archive.zip"
)
```

## Best Practices

- **Log every search string and filter** used in your review protocol.
- **Persist raw results** for each query to enable later verification.
- **Digitally sign** logs and results before publication or peer review.
- **Archive** all provenance files for reproducibility and compliance.

## Output Formats

- **JSON**: Structured logs and results for programmatic analysis
- **ZIP**: Signed and archived logs/results for publication
- **Text/CSV**: Exportable summaries for appendices

## Compliance Notes

- The logging utility is designed to meet PRISMA 2020 and Cochrane Handbook requirements for search documentation and reproducibility.
- All search parameters, result counts, and timestamps are recorded.
- Cryptographic signing provides tamper-evidence and auditability.

## See Also

- [PRISMA 2020 Statement](https://www.prisma-statement.org/)
- [Cochrane Handbook: Documenting the Search](https://training.cochrane.org/handbook/current/chapter-04#section-4-4)
- [search_logging.py API Reference](../src/pyeuropepmc/utils/search_logging.py)
- [Unit tests for search logging](../../tests/)
