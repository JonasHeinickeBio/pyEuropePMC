# FTPDownloader

`FTPDownloader` downloads open-access PDF bundles from the Europe PMC FTP site, which it reads over HTTPS at `https://europepmc.org/ftp/pdf/`. It finds each article's ZIP file in the site's directory listings, downloads it and extracts the PDFs. It does not download XML; for XML see [FullTextClient](fulltext-client.md).

```python
from pyeuropepmc import FTPDownloader
```

The class is defined in `pyeuropepmc.features.literature.ftp_downloader`.

## Constructor

`FTPDownloader(rate_limit_delay=1.0)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rate_limit_delay` | `float` | `1.0` | Minimum number of seconds between the starts of two requests, also while downloads run in parallel. `0` turns the wait off |

`FTPDownloader` is a context manager; leaving the `with` block, or calling `close()`, closes its HTTP session.

## bulk_download_and_extract

`bulk_download_and_extract(pmcids, output_dir, extract_pdfs=True, keep_zips=False, max_concurrent=3) -> dict[str, dict[str, Any]]`

Finds, downloads and extracts the PDF bundles for a list of articles.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcids` | `list[str]` | required | PMC IDs as digits, without the `PMC` prefix. An ID with the prefix is reported as `not_found` |
| `output_dir` | `str \| Path` | required | Directory for the ZIP files; created if needed |
| `extract_pdfs` | `bool` | `True` | Extract the PDFs into `output_dir/extracted` |
| `keep_zips` | `bool` | `False` | Keep each ZIP file after extracting it. Without extraction the ZIP files are always kept |
| `max_concurrent` | `int` | `3` | Number of articles downloaded and extracted in parallel threads; values below 1 count as 1. The directory search before it runs one listing at a time |

The method calls `query_pmcids_in_ftp()`, then `download_pdf_zip()` and `extract_pdf_from_zip()` for each article found. It returns a dict with one entry per requested PMC ID, in the order given; an ID listed twice is downloaded once:

| `status` | Other keys |
|---|---|
| `"success"` | `zip_path`: the `Path` of the ZIP file, or `None` when it was deleted after extraction (`keep_zips=False`); `pdf_paths` (`list[Path]`), only with `extract_pdfs=True` |
| `"not_found"` | `error`: `"PMC ID not found in FTP"`. Every candidate directory for the article (see `query_pmcids_in_ftp()`) was searched |
| `"error"` | `error`: the message of the `FullTextError` raised while downloading or extracting, or `"Could not search <directory> for PMC<id>: <reason>"` when a candidate directory for the article could not be listed |

```python
from pyeuropepmc import FTPDownloader

with FTPDownloader() as downloader:
    results = downloader.bulk_download_and_extract(["11691200", "99999999"], output_dir="ftp_pdfs")

succeeded = sum(result["status"] == "success" for result in results.values())
print(succeeded, results["99999999"])
```

Output:

```text
1 {'status': 'not_found', 'error': 'PMC ID not found in FTP'}
```

## query_pmcids_in_ftp

`query_pmcids_in_ftp(pmcids, max_directories=100) -> dict[str, dict[str, str | int] | None]`

Looks up which of the given PMC IDs have a ZIP file, without downloading anything. The result maps each PMC ID to its file information (see `get_zip_files_in_directory()`) or to `None`.

The ZIP files sit in directories named `PMCxxxx` followed by digits. For each PMC ID the method derives candidate directories from its last digits: the last three digits and their neighbours (for `11691200`: `PMCxxxx199`, `PMCxxxx200`, `PMCxxxx201`), and, when the last four digits are between 1000 and 1200, those four digits and their neighbours within that range (`PMCxxxx1199`, `PMCxxxx1200`). When no candidate can be derived, it lists all directories. It then reads the listing of each candidate directory, at most `max_directories` of them, and stops early after 10 listings in a row fail.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcids` | `list[str]` | required | PMC IDs as digits |
| `max_directories` | `int` | `100` | Maximum number of directory listings to read |

A directory that does not exist (HTTP 404) counts as searched and empty. Any other failed listing is logged and recorded in `downloader.last_query_failures`, a dict from directory name to the reason, which also names the directories left out when the search stopped early. An article whose directory could not be read is `None` in the result, like an article that does not exist; check `last_query_failures` to tell them apart. `bulk_download_and_extract()` does this for you.

## Lower-level methods

| Method | Returns | Description |
|---|---|---|
| `get_available_directories()` | `list[str]` | Sorted names of the `PMCxxxx…` directories in the root listing |
| `get_zip_files_in_directory(directory)` | `list[dict[str, str \| int]]` | The ZIP files in one directory, as `{"filename": "PMC11691200.zip", "pmcid": "11691200", "size": 295936, "directory": "PMCxxxx1200"}`. `size` is in bytes, computed from the size shown in the listing (for example `289K`) |
| `download_pdf_zip(zip_info, output_dir)` | `Path` | Downloads the ZIP file described by one of those dicts to `output_dir/filename`. Raises `TypeError` if `zip_info` is not a dict with `filename`, `directory`, `pmcid` and `size` |
| `extract_pdf_from_zip(zip_path, extract_dir, keep_zip=True)` | `list[Path]` | Writes every archive member whose name ends in `.pdf` to `extract_dir`, then deletes the ZIP file if `keep_zip=False` |
| `close()` | `None` | Closes the HTTP session |

```python
from pyeuropepmc import FTPDownloader

with FTPDownloader() as downloader:
    zip_info = downloader.query_pmcids_in_ftp(["11691200"])["11691200"]
    if zip_info is not None:
        zip_path = downloader.download_pdf_zip(zip_info, "zips")
        pdf_paths = downloader.extract_pdf_from_zip(zip_path, "pdfs", keep_zip=False)
        print(zip_info["directory"], zip_info["size"], [path.name for path in pdf_paths])
```

Output:

```text
PMCxxxx1200 295936 ['PMC11691200.pdf']
```

## Errors

`get_available_directories()`, `get_zip_files_in_directory()`, `download_pdf_zip()` and `extract_pdf_from_zip()` raise `FullTextError` with code `FULL005` when a request, a download or an extraction fails. `bulk_download_and_extract()` catches `FullTextError` for each article and reports it with status `"error"`. Import the exception with `from pyeuropepmc import FullTextError`.

## Known limitations

- Only the candidate directories derived from the PMC ID are searched; an article stored in another directory is reported as `not_found`.

## See also

- [Full-text retrieval](../features/fulltext/README.md): downloading XML, PDF and HTML with `FullTextClient`
- [FullTextClient](fulltext-client.md)
- [SearchClient](search-client.md): finding PMC IDs to download
