# FullTextClient

`FullTextClient` retrieves the full text of Europe PMC articles by PMC ID as XML, PDF or HTML, singly or in batches, with a file cache. This page lists its parameters, methods and return values; [Full-text retrieval](../features/fulltext/README.md) shows them in use.

```python
from pyeuropepmc import FullTextClient
```

The class is defined in `pyeuropepmc.features.fulltext.fulltext_client`, together with `ProgressInfo`, `DownloadReport` and `RateLimiter`.

## Constructor

`FullTextClient(rate_limit_delay=1.0, enable_cache=True, cache_dir=None, cache_max_age_days=30, verify_cached_files=True, cache_config=None, email=None)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `rate_limit_delay` | `float` | `1.0` | Seconds to wait after each request to the Europe PMC REST API: `get_fulltext_content()` and the REST steps of `download_xml_by_pmcid()`. Other requests are not delayed |
| `enable_cache` | `bool` | `True` | Keep a copy of each downloaded file and reuse it |
| `cache_dir` | `str \| Path \| None` | `None` | File cache directory, created on construction; `None` means `pyeuropepmc_cache` in `tempfile.gettempdir()` |
| `cache_max_age_days` | `int` | `30` | Cached files older than this are not used |
| `verify_cached_files` | `bool` | `True` | Use a cached file only if it starts like its format: `%PDF` for PDF, `<` for XML, an HTML tag for HTML |
| `cache_config` | `CacheConfig \| None` | `None` | API response cache for availability checks; `None` disables it |
| `email` | `str \| None` | `None` | Contact address for Unpaywall; when `None`, the `UNPAYWALL_EMAIL` and then the `CROSSREF_EMAIL` environment variable is used. Without an address the Unpaywall steps are skipped |

The client is a context manager. `close()` closes the HTTP session and the API response cache; cached files stay on disk.

PMC IDs are accepted with or without the `PMC` prefix, in any letter case. An empty ID raises `FullTextError` with code `FULL001`, and an ID that is not digits after the optional prefix raises `FULL002`.

## Retrieve content as a string

### get_fulltext_content

`get_fulltext_content(pmcid, format_type="xml") -> str`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcid` | `str` | required | PMC ID |
| `format_type` | `str` | `"xml"` | `"xml"` requests `PMC{id}/fullTextXML`, `"html"` requests `PMC{id}/fullTextHTML` from `https://www.ebi.ac.uk/europepmc/webservices/rest/` |

Sends one request and returns the response body. It does not use the file cache and tries no other source. Errors are raised as `FullTextError`, with the `APIClientError` from the request as `__cause__`: HTTP 404 gives `FULL003`, HTTP 403 gives `FULL008`, and any other HTTP error or a failed request gives `FULL005`. Another `format_type` raises `FullTextError` (`FULL004`); calling it after `close()` raises `APIClientError` (`FULL007`).

## Download single files

The three download methods save to `output_path`, a file path whose parent directories are created. Without it they write `PMC{id}.xml`, `PMC{id}.pdf` or `PMC{id}.html` in the current directory. They look in the file cache first and copy a valid cached file to `output_path`; after a network download they copy the file into the cache. `rate_limiter`, a `RateLimiter`, is applied after the cache lookup and before the network steps.

### download_xml_by_pmcid

`download_xml_by_pmcid(pmcid, output_path=None, rate_limiter=None, doi=None, extra_strategies=True) -> Path`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcid` | `str` | required | PMC ID |
| `output_path` | `str \| Path \| None` | `None` | Target file |
| `rate_limiter` | `RateLimiter \| None` | `None` | Rate limiter for the network steps |
| `doi` | `str \| None` | `None` | DOI for the DOI-based steps, including Unpaywall; looked up in Europe PMC when needed and not given |
| `extra_strategies` | `bool` | `True` | Try the non-Europe-PMC sources before Unpaywall |

Steps, in order; the name of the successful step is stored in `client.last_xml_source`:

| Step | `last_xml_source` |
|---|---|
| File cache | `cache` |
| Europe PMC REST API, `PMC{id}/fullTextXML` | `europepmc_rest` |
| Europe PMC FTP open-access archive (see `download_xml_by_pmcid_bulk()`) | `europepmc_ftp_bulk` |
| Europe PMC `fulltextRepo` endpoint | `europepmc_fulltext_repo` |
| With `extra_strategies=True`: NCBI PMC OA web service, NCBI E-utilities efetch, BioC-PMC (BioC XML, not JATS), DOI content negotiation, bioRxiv/medRxiv API | `pmc_oa_service`, `ncbi_efetch`, `bioc_pmc`, `doi_negotiation`, `biorxiv` |
| Unpaywall, only with an e-mail address; only a link that serves XML is used | `unpaywall` |

Returns the `Path` of the saved file. If no step succeeds it raises `FullTextError` (`FULL003`); it does not return `None`. A step that fails, including the Europe PMC request that looks up the DOI, counts as that step finding nothing. Without an e-mail address the Unpaywall step is skipped before any request is made. A file system error while saving from the REST API raises `FullTextError` (`FULL009`).

### download_xml_by_pmcid_bulk

`download_xml_by_pmcid_bulk(pmcid, output_path=None) -> Path`

Runs only the FTP archive step, without the file cache. The archive name is derived from the PMC ID: `https://europepmc.org/ftp/oa/PMC{start}_PMC{end}.xml.gz`, with ranges of 100,000 IDs for IDs from 100,000 up (PMC3258128 is in `PMC3200000_PMC3299999.xml.gz`), 10,000 for IDs from 10,000 and 1,000 below. The archive is downloaded to a temporary file and read as a stream, one article at a time. The `<article>` whose own `<front>/<article-meta>` has an `<article-id>` of type `pmcid`, `pmc` or `pmcid-ver` equal to the PMC ID, with or without the `PMC` prefix, is written to `output_path` as a standalone XML document; the other articles in the archive are not saved. The saved document has no DOCTYPE, and namespace prefixes are renamed (`xlink:href` becomes, for example, `ns0:href`, bound to the same namespace). If no article matches, `FullTextError` (`FULL003`) is raised.

### download_pdf_by_pmcid

`download_pdf_by_pmcid(pmcid, output_path=None, rate_limiter=None, doi=None, max_bytes=None, open_access=None) -> Path | None`

Tries the file cache, `https://europepmc.org/articles/PMC{id}?pdf=render`, `https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{id}&blobtype=pdf`, the PDF of the newest version in NCBI's PMC Open Access Subset on AWS open data (`https://pmc-oa-opendata.s3.amazonaws.com/PMC{id}.{version}/PMC{id}.{version}.pdf`), the ZIP file `https://ftp.ebi.ac.uk/pub/databases/pmc/pdf/OA/PMCxxxx{batch}/PMC{id}.zip` (`batch` is the PMC ID divided by 10,000, rounded up, in three digits or more: PMC3525259 is in `PMCxxxx353`), and Unpaywall (only with an e-mail address). The first two are behind a browser check (HTTP 403) for scripted clients since November 2026 and are not worked around. `doi` is passed to the Unpaywall step; without it the DOI is looked up from Europe PMC. `max_bytes` refuses a PDF, or ZIP, over that size from its declared size or while it downloads, in every step, and leaves no partial file. A downloaded file counts only if it starts with `%PDF` and is at least 1,024 bytes long. `open_access=False` skips the two steps that only hold open-access articles (see `download_pdf_with_provenance`). Returns the `Path`, or `None` when no step succeeds, including when the request that looks up the DOI for Unpaywall fails. [Downloading PDFs](../features/pdf-download.md) explains the sources, the checks and the measured coverage.

### download_pdf_with_provenance

`download_pdf_with_provenance(pmcid, output_path=None, rate_limiter=None, doi=None, max_bytes=None, open_access=None) -> PdfResult | None`

The same steps as `download_pdf_by_pmcid`, which returns only the path. The `PdfResult` (`features/fulltext/pdf_result.py`, frozen) has `path`, `source`, `url`, `license`, `md5_verified` and `from_cache`:

- `source` is the step that supplied the file: `cache`, `europepmc_render`, `europepmc_backend`, `pmc_open_data`, `europepmc_ftp_zip` or `unpaywall`. `url` is where the bytes came from.
- `license` is what that step reported, normalized by `normalize_license` to one lowercase spelling (`CC BY-NC-ND`, `cc by-nc-nd`, `CCBYNCND` all become `cc-by-nc-nd`; `CC0` becomes `cc0`). It is `None` when the step did not say, which is not the same as "not open". The PMC bucket reads it from the article's `PMC<id>.<v>.json` (`license_code`); Unpaywall gives it per location.
- `md5_verified` is `True` when the bucket's published MD5 for the PDF matched the downloaded file. A file that does not match is discarded and the next version or step is tried.
- With the file cache on, the origin of every cached PDF is recorded in `<cache_dir>/pdf-provenance/PMC<id>.json`, with the file's SHA-256. A later cache hit returns that origin with `from_cache=True`; if the record is missing or names a different file, `source` is just `cache`.
- `open_access=False` (Europe PMC's `isOpenAccess` is `N`) skips `pmc_open_data` and `europepmc_ftp_zip`, which only hold open-access articles. After a response from a host carries Cloudflare's `cf-mitigated: challenge` header, that host's PDF steps are skipped for `CHALLENGE_COOLDOWN_SECONDS` (600).

### download_pdf_by_doi

`download_pdf_by_doi(doi, output_path, max_bytes=None, skip=()) -> PdfResult | None`

For a paper that is not in PubMed Central. Asks, in order, arXiv (for `10.48550/arXiv.*` DOIs), Unpaywall (needs the client's e-mail), OpenAlex (`best_oa_location` and `locations`) and Semantic Scholar (`openAccessPdf`) for links, and saves the first that serves a PDF; returns a `PdfResult` with the source's name (`arxiv`, `unpaywall`, `openalex`, `semantic_scholar`), the link and the licence that source reported for it, or `None`. A link counts only if it is http(s), has no credentials and every address its host resolves to is public (no loopback, private or link-local range); redirects are followed by hand, at most five, and each target is checked the same way. A body of type HTML, over `max_bytes`, under 1,024 bytes or not starting with `%PDF` is refused and no file is left. `skip` names sources not to ask. The address can change between the check and the connection, so this narrows the risk of a hostile record pointing at an internal service rather than removing it.

### download_html_by_pmcid

`download_html_by_pmcid(pmcid, output_path=None, rate_limiter=None) -> Path | None`

Tries the file cache, then downloads the article's web page, `https://europepmc.org/article/PMC/{id}#free-full-text`. Returns the `Path`, or `None` on an HTTP or network error; a file system error raises `FullTextError` (`FULL009`).

### get_html_article_url

`get_html_article_url(pmcid, medid=None) -> str` returns `https://europepmc.org/article/MED/{medid}#free-full-text` when `medid` is given, otherwise `https://europepmc.org/article/PMC/{id}#free-full-text`.

### check_fulltext_availability

`check_fulltext_availability(pmcid) -> dict[str, bool]` returns `{"pdf": bool, "xml": bool, "html": bool}`:

| Key | `True` when |
|---|---|
| `xml` | A HEAD request to `PMC{id}/fullTextXML` returns HTTP 200 |
| `pdf` | A HEAD request to the PDF render URL returns HTTP 200 with a content type containing `application/pdf` |
| `html` | A GET request to the article's web page returns HTTP 200 |

A failed request counts as `False`. With `cache_config` enabled, results are cached under the key `fulltext_availability:{id}`.

## Batch downloads

### download_fulltext_batch

`download_fulltext_batch(pmcids, format_type="pdf", output_dir=None, skip_errors=True, progress_callback=None, progress_update_interval=1.0) -> dict[str, Path | None]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcids` | `list[str]` | required | PMC IDs |
| `format_type` | `str` | `"pdf"` | `"pdf"`, `"xml"` or `"html"` |
| `output_dir` | `str \| Path \| None` | `None` | Target directory, created if needed; `None` means the current directory |
| `skip_errors` | `bool` | `True` | Map an article that raises `FullTextError` to `None` instead of raising |
| `progress_callback` | `Callable[[ProgressInfo], None] \| None` | `None` | Called at the start (status `initialized`), before downloads, and at the end (status `completed`) |
| `progress_update_interval` | `float` | `1.0` | Minimum seconds between the calls made before downloads |

Downloads one article after another with the `download_*_by_pmcid` method for the format, saving `output_dir/PMC{id}.{format}`. Returns a dict from each PMC ID, as passed, to the saved `Path` or `None`. Exceptions other than `FullTextError` are always raised.

### download_fulltext_batch_parallel

`download_fulltext_batch_parallel(pmcids, format_type="pdf", output_dir=None, skip_errors=True, max_workers=None, show_progress=True, verbose=False) -> dict[str, Path | None]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcids` | `list[str]` | required | PMC IDs |
| `format_type` | `str` | `"pdf"` | `"pdf"`, `"xml"` or `"html"` |
| `output_dir` | `str \| Path \| None` | `None` | Target directory; `None` means the current directory |
| `skip_errors` | `bool` | `True` | Continue after a failed article |
| `max_workers` | `int \| None` | `None` | Threads; `None` means the CPU count, capped at 8; other values are limited to 1–8 |
| `show_progress` | `bool` | `True` | Show a tqdm progress bar |
| `verbose` | `bool` | `False` | Extra debug logging |

Each worker thread uses its own HTTP session and a `RateLimiter` of one request per second, applied after the cache lookup. Failed downloads are not retried. The result has the same form as `download_fulltext_batch()`. Afterwards, `client.download_stats` is a dict with `total_items`, `format_type`, `max_workers`, `start_time`, `end_time`, `total_time_seconds`, `avg_speed`, `success_rate`, `worker_stats` (per worker: `requests`, `failures`, `successes`, `time_spent`) and `global_stats` (`total_requests`, `total_failures`, `total_successes`).

### search_and_download_fulltext

`search_and_download_fulltext(query, format_type="pdf", max_results=10, output_dir=None, only_available=True) -> dict[str, Path | None]`

Searches Europe PMC with `SearchClient` for one page of `max_results` results and takes the PMC IDs of the results that have one. With `only_available=True` it keeps only the IDs for which `check_fulltext_availability()` reports the format. It then downloads with `download_fulltext_batch()` (PDF, XML) or `download_html_by_pmcid()` (HTML). The result's keys are PMC IDs without the `PMC` prefix. An invalid `format_type` raises `FullTextError` (`FULL004`).

### ProgressInfo

Passed to the `download_fulltext_batch()` callback.

| Attribute | Type | Description |
|---|---|---|
| `total_items`, `current_item` | `int` | Number of articles, and the 1-based number of the current one (0 at the start) |
| `current_pmcid` | `str \| None` | ID of the current article |
| `status` | `str` | `initialized`, `downloading PMC…`, `completed PMC…`, `failed PMC…`, `error PMC…` or `completed` |
| `successful_downloads`, `failed_downloads`, `cache_hits` | `int` | Running counts |
| `format_type` | `str` | Requested format |
| `start_time` | `float \| None` | Start time as a Unix timestamp |
| `current_file_size`, `total_downloaded_bytes` | `int` | Bytes |
| `progress_percent` | `float` | Property: `current_item / total_items * 100` |
| `elapsed_time`, `estimated_total_time`, `estimated_remaining_time` | `float`, `float \| None`, `float \| None` | Properties, in seconds |
| `completion_rate` | `float` | Property: items per second |
| `to_dict()` | `dict` | All of the above |

## Download diagnostics

`analyze_download(pmcid, output_dir=None, run_all_strategies=False) -> DownloadReport` records each download attempt for one article.

- With `run_all_strategies=False`, it follows the XML fallback chain.
- With `True`, a second client without file cache runs six attempts and saves their files in `output_dir` (default: the current directory): the full XML download, the PDF download, the FTP archive step, the `fulltextRepo` endpoint, a Europe PMC search for the article, and the XML download once more.
- With `output_dir`, the report is also saved as `output_dir/PMC{id}_analysis.json`.

`DownloadReport(pmcid)` has `add_attempt(...)`, `add_fallback(...)`, `set_detailed_analysis(analysis)`, `to_dict()`, `to_json(indent=2)` and `save(output_path) -> Path`.

## PDF results and helpers

### PdfResult

`PdfResult` is a frozen dataclass in `pyeuropepmc.features.fulltext.pdf_result`, returned by `download_pdf_with_provenance()` and `download_pdf_by_doi()`.

| Attribute | Type | Meaning |
|---|---|---|
| `path` | `Path` | The saved file. |
| `source` | `str` | The step or service that supplied it. |
| `url` | `str` or `None` | Where the bytes came from; `None` for a cache hit with no recorded origin. |
| `license` | `str` or `None` | What the source reported, normalized; `None` when it did not say. |
| `md5_verified` | `bool` | `True` when the MD5 published by the PMC open-data bucket matched. Default `False`. |
| `from_cache` | `bool` | `True` when the file cache supplied the file. Default `False`. |

### normalize_license

`normalize_license(value) -> str | None`, in the same module, turns the spellings that the sources use into one lowercase form: `CC BY-NC-ND`, `cc by-nc-nd` and `CCBYNCND` become `cc-by-nc-nd`, a version is kept (`cc by 4.0` becomes `cc-by-4.0`), `CC0` becomes `cc0`, and any other text is lowercased with spaces turned into hyphens. Blank or non-text values give `None`.

### oa_pdf

`pyeuropepmc.features.fulltext.oa_pdf` holds the DOI route behind `download_pdf_by_doi()`:

| Name | Description |
|---|---|
| `download_pdf_by_doi(doi, output_path, email=None, max_bytes=None, skip=())` | The function the client method calls. `email` is passed by the client; without it Unpaywall is skipped. |
| `fetch_pdf(url, output_path, max_bytes=None) -> bool` | Fetches one link under the rules in `download_pdf_by_doi` and leaves no file when it fails. |
| `is_public_url(url) -> bool` | `True` for an `http` or `https` URL without credentials whose host resolves only to globally routable addresses. |
| `SOURCES` | The source names in the order they are asked: `arxiv`, `unpaywall`, `openalex`, `semantic_scholar`. |
| `Link` | A `NamedTuple` of `url` and `license`, what each source returns for a candidate. |

## Caching

The file cache, on by default, stores downloads as `cache_dir/{pdf,xml,html}/PMC{id}.{format}`. For PDFs, `cache_dir/pdf-provenance/PMC{id}.json` records where the cached file came from, with its SHA-256. The API response cache is opt-in: `cache_config=CacheConfig(enabled=True)` caches availability results, in memory unless `enable_l2=True` adds a disk layer. See the [caching guide](../features/caching/README.md) and the [caching reference](../advanced/caching.md) for `CacheConfig`.

| Method | Returns | Description |
|---|---|---|
| `get_cache_stats()` | `dict` | `{"enabled": False}` without a file cache; otherwise `enabled`, `cache_dir`, `total_files`, `total_size_bytes` and `formats` (per format: `count`, `size_bytes`) |
| `clear_cache(format_type=None, max_age_days=None)` | `int` | Deletes cached files of one format, or all formats, that are older than `max_age_days` (default: `cache_max_age_days`); `0` deletes all. Returns the number deleted |
| `get_file_cache_health()` | `dict` | `enabled`, `status` (`healthy`, `warning`, `critical`, `error`, `disabled` or `unavailable`), `available`, `disk_space_available` (at least 100 MB free), `directory_writable`, `files_within_age_limit`, `warnings` |
| `get_api_cache_stats()`, `get_api_cache_health()` | `dict` | Statistics and health of the API response cache |
| `clear_api_cache()` | `bool` | Clears the API response cache |
| `invalidate_fulltext_cache(pmcid=None)` | `int` | Removes cached availability results for one PMC ID, or all; returns the number removed |

## Export

`export_results(results, format="dataframe", path=None, **kwargs)` converts a list of result dicts with `pyeuropepmc.utils.export`: `"dataframe"` returns a pandas `DataFrame` (pandas must be installed), `"csv"` a CSV string, `"excel"` bytes, `"json"` a JSON string (`pretty=True` indents it), and `"markdown"` a Markdown table. `path` writes the CSV, Excel or JSON output to a file. Any other format raises `ValueError`.

```python
from pyeuropepmc import FullTextClient

with FullTextClient(enable_cache=False) as client:
    print(client.export_results([{"pmcid": "PMC3258128", "format": "xml"}], format="json"))
```

Output:

```text
[{"pmcid": "PMC3258128", "format": "xml"}]
```

## RateLimiter

`RateLimiter(worker_id, max_requests_per_second=1.0)` has `wait_if_needed()`, which sleeps until another request is allowed, `check_and_record()`, and `get_stats()`. Pass one as `rate_limiter` to the `download_*_by_pmcid` methods to throttle your own loops.

## Errors

| Error | Raised by |
|---|---|
| `FullTextError` `FULL001`, `FULL002` | Every method, for an empty or malformed PMC ID |
| `FullTextError` `FULL003` | `download_xml_by_pmcid()` and `download_xml_by_pmcid_bulk()` when nothing is found; `get_fulltext_content()` on HTTP 404 |
| `FullTextError` `FULL004` | `get_fulltext_content()` and `search_and_download_fulltext()` with an unsupported format |
| `FullTextError` `FULL005` | `get_fulltext_content()` on an HTTP error other than 403 and 404, or a failed request |
| `FullTextError` `FULL008` | `get_fulltext_content()` on HTTP 403 |
| `FullTextError` `FULL009` | Saving an XML or HTML file fails |
| `APIClientError` `FULL007` | `get_fulltext_content()` after `close()` |

Both derive from `PyEuropePMCError` in `pyeuropepmc.core.exceptions` and can be imported from `pyeuropepmc`.

## Known limitations

- The `fulltextRepo` step requests `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{id}/fulltextRepo`. That path has not been checked against the live service; the file endpoint the Europe PMC website loads, `https://europepmc.org/api/fulltextRepo`, takes a file name and MIME type rather than only a PMC ID.
- On 6 November 2026 `europepmc.org` answered scripted clients with a Cloudflare browser check (HTTP 403) on article pages, the PDF render and backend endpoints, `/ftp/pdf/`, `/ftp/oa/` and `/api/fulltextRepo`. The REST API on `www.ebi.ac.uk` was not affected. Nothing here tries to pass the check; the PDF chain uses other sources, and the XML chain falls through to the REST API. `FTPDownloader` and the `europepmc_ftp_bulk` XML step depend on the blocked hosts.
- The HTML download is the Europe PMC web page as served, not an article-only document.

## See also

- [Full-text retrieval](../features/fulltext/README.md)
- [Downloading PDFs](../features/pdf-download.md)
- [FTPDownloader](ftp-downloader.md)
- [FullTextXMLParser](xml-parser.md)
