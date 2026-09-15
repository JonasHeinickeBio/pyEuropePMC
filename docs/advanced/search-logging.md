# Search logging

`pyeuropepmc.utils.search_logging` records the searches of a literature review in a structured log: the exact query per database, filters, run date, result counts and, optionally, the raw results. It also produces the counts for a PRISMA flow diagram and can zip and sign the files. The review workflow around it is described in [Systematic review tracking](../features/systematic-review-tracking.md).

## Installation

Logging, saving and zipping need only the core package. Signing and key generation need `cryptography`:

```bash
pip install "pyeuropepmc[signing]"
```

All functions below can be imported from `pyeuropepmc.utils.search_logging` or from `pyeuropepmc.utils`.

## Record a search

```python
from pyeuropepmc import SearchClient
from pyeuropepmc.utils.search_logging import prisma_summary, record_query, record_results, start_search

query = "cancer immunotherapy AND PUB_YEAR:2023"
log = start_search("Cancer immunotherapy review", executed_by="A. Smith")

with SearchClient() as client:
    results = client.search(query, pageSize=100)

record_query(
    log,
    database="Europe PMC",
    query=query,
    filters={"publication_year": 2023},
    results_returned=results["hitCount"],
    raw_results=results,
    raw_results_dir="search_results",
    platform="pyeuropepmc SearchClient",
)

# After deduplication and screening
record_results(log, deduplicated_total=950, final_included=42)

log.save("search_log.json")
print(prisma_summary(log)["total_records_identified"])
```

| Function | Returns | What it does |
|---|---|---|
| `start_search(title, executed_by=None)` | `SearchLog` | Creates an empty log; `created_at` and `last_updated` are the current UTC time in ISO 8601. |
| `record_query(log, database, query, ...)` | `None` | Appends a `SearchLogEntry`; parameters below. |
| `record_results(log, deduplicated_total, final_included)` | `None` | Sets the review-level counts on the log. |
| `record_platform(log, platform)` | `None` | Sets `platform` on the last entry. Raises `IndexError` if the log has no entries. |
| `record_export(log, export_path, format)` | `None` | Sets `export_path` on the last entry and `export_format` on the log. Raises `IndexError` if the log has no entries. |
| `record_peer_review(log, peer_reviewed=None)` | `None` | Sets `peer_reviewed` on the log, for example the path of a PRESS checklist. |
| `prisma_summary(log)` | `dict` | Counts for a PRISMA flow diagram; see [PRISMA counts](#prisma-counts). |
| `zip_results(files, zip_path)` | `str` | Writes a ZIP archive with each file stored under its base name. |
| `sign_file(file_path, private_key_path)` | `str` | Writes an RSA signature of the file to `<file_path>.sig` and returns that path. |
| `sign_and_zip_results(files, zip_path, cert_path=None, private_key_path=None)` | `str`, or `(zip_path, signature_path)` when a key is given | Zips the files, then signs the ZIP if `private_key_path` is given. `cert_path` is ignored. |
| `generate_private_key(private_key_path, public_key_path=None, name=None, email=None, info=None, key_size=2048, publish_public=False)` | `(private_key_path, public_key_path or None)` | Writes an unencrypted RSA private key; see [Archive and sign the files](#archive-and-sign-the-files). |

`record_query()` parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `log` | `SearchLog` | required | The log to append to. |
| `database` | `str` | required | Name of the database or source, such as `"Europe PMC"`. |
| `query` | `str` | required | The exact query string. |
| `filters` | `dict` or `None` | `None` | Filters applied outside the query string; stored as `{}` when `None`. |
| `results_returned` | `int` or `None` | `None` | Number of records the query returned. |
| `notes` | `str` or `None` | `None` | Free text. |
| `raw_results` | JSON-serialisable value | `None` | Saved to a JSON file when `raw_results_dir` is also given. |
| `raw_results_dir` | `str`, `Path` or `None` | `None` | Directory for the raw results file, created if needed. |
| `raw_results_filename` | `str` or `None` | `None` | File name. The default is `<database>_results_<UTC timestamp>.json`, with spaces and `/` in the database name replaced by `_`. |
| `platform` | `str` or `None` | `None` | Interface or tool used. |
| `export_path` | `str` or `None` | `None` | Path of an exported results file. |

If the raw results cannot be written, the error is logged and the entry is recorded with `raw_results_path=None`.

## The log

A `SearchLog` has the fields `title`, `executed_by`, `created_at`, `last_updated`, `entries`, `deduplicated_total`, `final_included`, `peer_reviewed` and `export_format`. Each `SearchLogEntry` in `entries` has `database`, `query`, `filters`, `date_run` (UTC, ISO 8601), `results_returned`, `notes`, `raw_results_path`, `platform` and `export_path`.

| Method | Returns | Notes |
|---|---|---|
| `save(path, *, indent=2)` | `Path` | Writes all fields and entries as JSON. |
| `export(path, format="json")` | `Path` | `"json"`, `"csv"` (one row per entry; needs at least one entry) or `"ris"` (one minimal `TY  - SER` record per entry). Other formats raise `ValueError`. Sets `export_format`. |
| `to_dict()` | `dict` | The content of the JSON file. |
| `add_entry(entry)` | `None` | Appends a `SearchLogEntry` and updates `last_updated`. |

## PRISMA counts

`prisma_summary(log)` returns `title`, `executed_by`, `created_at`, `records_by_database`, `total_records_identified`, `deduplicated_total` and `final_included`.

> **Known limitation.** `records_by_database` keeps only the last `results_returned` value of each database name, and `total_records_identified` is the sum of that dict. If you log several queries against the same database, the total is too low. Sum the entries yourself:

```python
from pyeuropepmc.utils.search_logging import prisma_summary, record_query, start_search

log = start_search("Two-query review")
record_query(log, database="Europe PMC", query="cancer AND PUB_YEAR:2023", results_returned=1234)
record_query(log, database="Europe PMC", query="immunotherapy AND PUB_YEAR:2023", results_returned=200)

print(prisma_summary(log)["total_records_identified"])  # 200, not 1434
print(sum(entry.results_returned or 0 for entry in log.entries))  # 1434
```

## Archive and sign the files

This example continues from [Record a search](#record-a-search), which wrote `search_log.json`.

```python
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from pyeuropepmc.utils.search_logging import generate_private_key, sign_and_zip_results

generate_private_key("review_key.pem", name="A. Smith")

zip_path, signature_path = sign_and_zip_results(
    ["search_log.json"],
    "search_archive.zip",
    private_key_path="review_key.pem",
)

# Export the public key for reviewers
private_key = serialization.load_pem_private_key(Path("review_key.pem").read_bytes(), password=None)
Path("review_key.pub.pem").write_bytes(
    private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
)
```

- The private key is written without a password. Keep it out of the archive and out of version control. Its first line is a `# Name: ..., Created: ..., User: ...` comment, which `cryptography` and OpenSSL both accept.
- `zip_results()` and `sign_and_zip_results()` log and skip a file they cannot read, and still write the archive.
- The signature is RSA PKCS #1 v1.5 with SHA-256, computed over the SHA-256 digest of the file rather than over the file itself. Verify it against the digest:

```python
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

public_key = serialization.load_pem_public_key(Path("review_key.pub.pem").read_bytes())
digest = hashlib.sha256(Path("search_archive.zip").read_bytes()).digest()

# verify() raises InvalidSignature if the archive or the signature was changed
public_key.verify(Path("search_archive.zip.sig").read_bytes(), digest, padding.PKCS1v15(), hashes.SHA256())
print("signature valid")
```

With OpenSSL, hash the archive first; `openssl dgst -sha256 -verify` run on the archive itself reports `Verification failure`:

```bash
openssl dgst -sha256 -binary search_archive.zip > search_archive.zip.sha256
openssl dgst -sha256 -verify review_key.pub.pem -signature search_archive.zip.sig search_archive.zip.sha256
```

> **Known limitation.** With `publish_public=True` or `public_key_path=...`, `generate_private_key()` writes a `#` comment line inside the `BEGIN PUBLIC KEY` block, so that file cannot be loaded as PEM (`load_pem_public_key()` raises `ValueError`). Export the public key from the private key as shown above.

## Related pages

- [Systematic review tracking](../features/systematic-review-tracking.md)
- [PRISMA 2020 statement](https://www.prisma-statement.org/)
