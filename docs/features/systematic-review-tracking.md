# Systematic review search logging

`pyeuropepmc.utils.search_logging` records the search strings, filters, dates and result counts of a literature review in a JSON log, and `QueryBuilder.log_to_search()` adds a built query to that log. This page covers what is recorded, logging queries from Europe PMC and other databases, raw results, exports and the counts for a PRISMA 2020 flow diagram.

## What a log records

A `SearchLog` holds the review-level fields and a list of `SearchLogEntry` objects, one per search.

| `SearchLog` field | Type | Set by |
|---|---|---|
| `title` | `str` | `start_search()` |
| `executed_by` | `str` or `None` | `start_search()` |
| `created_at`, `last_updated` | `str` | Automatically, as ISO 8601 UTC timestamps |
| `entries` | `list[SearchLogEntry]` | `record_query()` or `QueryBuilder.log_to_search()` |
| `deduplicated_total`, `final_included` | `int` or `None` | `record_results()` |
| `peer_reviewed` | `str` or `None` | `record_peer_review()` |
| `export_format` | `str` or `None` | `SearchLog.export()` or `record_export()` |

| `SearchLogEntry` field | Type | Content |
|---|---|---|
| `database` | `str` | Database label, `"Europe PMC"` by default in `log_to_search()` |
| `query` | `str` | The search string exactly as built |
| `filters` | `dict` | Whatever you pass; nothing is added automatically |
| `date_run` | `str` | ISO 8601 UTC timestamp of the call that recorded the entry |
| `results_returned` | `int` or `None` | The count you pass |
| `notes`, `platform`, `export_path` | `str` or `None` | Whatever you pass |
| `raw_results_path` | `str` or `None` | Set when raw results were saved; see [Save raw responses](#save-raw-responses) |

Request parameters such as `pageSize`, `sort`, `resultType` and the cursor are not captured. Put them in `filters` if your methods section needs them.

## Log a QueryBuilder query

```python
from pyeuropepmc import QueryBuilder, SearchClient
from pyeuropepmc.utils.search_logging import start_search

log = start_search("Cancer immunotherapy review", executed_by="Jane Doe")

qb = (
    QueryBuilder()
    .keyword("cancer", field="title")
    .and_()
    .keyword("immunotherapy", field="abstract")
    .and_()
    .date_range(start_year=2020, end_year=2024)
)
query = qb.build()
print(query)  # TITLE:cancer AND ABSTRACT:immunotherapy AND (PUB_YEAR:[2020 TO 2024])

with SearchClient() as client:
    response = client.search(query, pageSize=100, resultType="core")

qb.log_to_search(
    log,
    results_returned=response["hitCount"],
    filters={"pageSize": 100, "resultType": "core"},
    notes="Initial broad search",
    platform="Europe PMC REST API",
)
log.save("review_searches.json")
```

`log_to_search()` stores `qb.build(validate=False)`, the same string sent to Europe PMC.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search_log` | `SearchLog` | required | Log to add the entry to |
| `database` | `str` | `"Europe PMC"` | Database label |
| `filters` | `dict` or `None` | `None` | Stored as given (`{}` when `None`) |
| `results_returned` | `int` or `None` | `None` | Number of results |
| `notes` | `str` or `None` | `None` | Free text |
| `raw_results` | any JSON-serialisable value | `None` | Response to save to a file |
| `raw_results_dir` | `str` or `None` | `None` | Directory for the raw results file; required for saving |
| `platform` | `str` or `None` | `None` | Interface used, for example `"Europe PMC REST API"` |
| `export_path` | `str` or `None` | `None` | Path of an exported result file |

Open-ended date ranges use the year at build time, for example `date_range(start_year=2020)` gives `(PUB_YEAR:[2020 TO 2026])` in 2026, so the logged string records the year actually searched.

## Log queries from other databases

`record_query()` adds an entry for a search string that was not built with `QueryBuilder`:

```python
from pyeuropepmc.utils.search_logging import record_query, start_search

log = start_search("Cancer immunotherapy review")
record_query(
    log,
    database="PubMed",
    query='"neoplasms"[MeSH Terms] AND immunotherapy[tiab]',
    filters={"publication_date": "2020-2024"},
    results_returned=734,
    platform="PubMed web interface",
)

entry = log.entries[0]
print(entry.database, entry.query, entry.date_run)
```

`record_query(log, database, query, filters=None, results_returned=None, notes=None, raw_results=None, raw_results_dir=None, raw_results_filename=None, platform=None, export_path=None)` accepts the same fields as `log_to_search()`, plus `raw_results_filename` to choose the file name. Entries are dataclass objects: read them as attributes, for example `log.entries[0].query`.

## Save raw responses

```python
from pyeuropepmc import QueryBuilder, SearchClient
from pyeuropepmc.utils.search_logging import start_search

log = start_search("Auditable search")
qb = QueryBuilder().keyword("CRISPR").and_().field("open_access", True)

with SearchClient() as client:
    response = client.search(qb.build(), pageSize=100)

qb.log_to_search(
    log,
    results_returned=response["hitCount"],
    raw_results=response,
    raw_results_dir="raw_results",
)
print(log.entries[0].raw_results_path)  # raw_results/Europe_PMC_results_<UTC timestamp>.json
```

The response is written only when both `raw_results` and `raw_results_dir` are given. The default file name is `<database>_results_<YYYYMMDDTHHMMSS>.json`, with spaces and slashes in the database label replaced by underscores. `raw_results` must be JSON-serialisable: if writing fails, the error is logged rather than raised and `raw_results_path` stays `None`.

## Counts for PRISMA 2020

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import prisma_summary, record_results, start_search

log = start_search("Cancer immunotherapy review", executed_by="Jane Doe")
QueryBuilder().keyword("cancer immunotherapy").log_to_search(log, results_returned=1842)
QueryBuilder().keyword("checkpoint inhibitor").log_to_search(log, results_returned=734)
record_results(log, deduplicated_total=2150, final_included=67)

summary = prisma_summary(log)
print(summary["records_by_database"])       # {'Europe PMC': 734}
print(summary["total_records_identified"])  # 734

identified = sum(entry.results_returned or 0 for entry in log.entries)
print(identified)                           # 2576
```

`prisma_summary(log)` returns `title`, `executed_by`, `created_at`, `records_by_database`, `total_records_identified`, `deduplicated_total` and `final_included`.

Known limitation: `records_by_database` keeps only the last `results_returned` for each database label, and `total_records_identified` is the sum of those values. When you log several searches under the same label, as `log_to_search()` does by default, the total is too low. Sum the entries yourself as shown, or give each search its own `database` label.

The counts can be entered in the PRISMA 2020 flow diagram tool at https://estech.shinyapps.io/prisma_flowdiagram/.

## The saved log

`log.save(path, indent=2)` writes the log as JSON and returns the path as a `pathlib.Path`:

```json
{
  "title": "Cancer immunotherapy review",
  "executed_by": "Jane Doe",
  "created_at": "2025-11-06T12:00:00.000000+00:00",
  "last_updated": "2025-11-06T12:15:00.000000+00:00",
  "entries": [
    {
      "database": "Europe PMC",
      "query": "TITLE:cancer AND ABSTRACT:immunotherapy AND (PUB_YEAR:[2020 TO 2024])",
      "filters": {"pageSize": 100, "resultType": "core"},
      "date_run": "2025-11-06T12:15:00.000000+00:00",
      "results_returned": 342,
      "notes": "Initial broad search",
      "raw_results_path": null,
      "platform": "Europe PMC REST API",
      "export_path": null
    }
  ],
  "deduplicated_total": 2150,
  "final_included": 67,
  "peer_reviewed": null,
  "export_format": null
}
```

## Export and provenance

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search, zip_results

log = start_search("Cancer immunotherapy review")
QueryBuilder().keyword("CRISPR").log_to_search(log, results_returned=125)

log.save("searches.json")
log.export("searches.csv", format="csv")
log.export("searches.ris", format="ris")
archive = zip_results(["searches.json", "searches.csv"], "searches.zip")
print(archive)  # searches.zip
```

| Function or method | Description |
|---|---|
| `SearchLog.export(path, format="json")` | `"json"`, `"csv"` (one row per entry, with the entry fields as columns; needs at least one entry) or `"ris"` (one minimal `TY  - SER` record per entry); returns the path |
| `record_peer_review(log, peer_reviewed)` | Store a peer-review status or checklist path, for example a PRESS checklist |
| `record_platform(log, platform)`, `record_export(log, export_path, format)` | Update the most recent entry |
| `zip_results(files, zip_path)` | Put files into a ZIP archive; returns the archive path |
| `sign_file(file_path, private_key_path)` | Sign a file with an RSA private key (PEM); writes `<file>.sig` and returns its path. Needs `pip install "pyeuropepmc[signing]"` |
| `sign_and_zip_results(files, zip_path, private_key_path=None)` | `zip_results()`, then `sign_file()` when a key is given; returns the ZIP path or `(zip_path, signature_path)` |

## Reproducibility

The logged `query` is the exact string that was sent, so the search can be run again. The results can still differ, because the Europe PMC index changes over time and paging, sorting and result-type parameters are not stored unless you add them to `filters`. Save `raw_results` when you need an audit trail of what a search returned on the day.

The log supports PRISMA 2020 reporting of search strings, dates and counts; screening and eligibility decisions are outside its scope.

## See also

- [QueryBuilder API reference](../api/query-builder.md)
- [Query builder](query-builder-load-save-translate.md)
- [Search logging](../advanced/search-logging.md)
- [PRISMA 2020 statement](http://www.prisma-statement.org/)
- [Cochrane Handbook](https://training.cochrane.org/handbook)
