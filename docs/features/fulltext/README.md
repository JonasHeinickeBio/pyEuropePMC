# Full-text retrieval

`FullTextClient` downloads the full text of Europe PMC articles by PMC ID, as XML, PDF or HTML, one at a time or in batches, and keeps a cache of downloaded files. `FTPDownloader` fetches PDF bundles from the Europe PMC FTP site. The reference pages list every parameter: [FullTextClient](../../api/fulltext-client.md) and [FTPDownloader](../../api/ftp-downloader.md).

## Get the XML of an article

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

with FullTextClient() as client:
    xml_content = client.get_fulltext_content("PMC3258128")

parser = FullTextXMLParser(xml_content)
print(parser.extract_metadata()["title"])
```

Output:

```text
Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA
```

`get_fulltext_content(pmcid, format_type="xml")` sends one request to the Europe PMC REST API (`PMC{id}/fullTextXML`) and returns the response body as a string; `format_type="html"` requests `PMC{id}/fullTextHTML`. It neither reads nor fills the file cache, and it tries no other source. [XML parsing](../parsing/README.md) describes what to do with the XML.

Every method accepts a PMC ID with or without the `PMC` prefix, in any letter case: `"PMC3258128"`, `"pmc3258128"` and `"3258128"` are the same article.

## Download files

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    xml_path = client.download_xml_by_pmcid("PMC3258128", output_path="downloads/PMC3258128.xml")
    print(xml_path, client.last_xml_source)

    pdf_path = client.download_pdf_by_pmcid("PMC3258128", output_path="downloads/PMC3258128.pdf")
    print(pdf_path)

    html_path = client.download_html_by_pmcid("PMC3258128", output_path="downloads/PMC3258128.html")
    print(html_path)
```

Output:

```text
downloads/PMC3258128.xml europepmc_rest
downloads/PMC3258128.pdf
downloads/PMC3258128.html
```

Each method returns the `Path` of the saved file. `output_path` is a file path; parent directories are created. Without it, the file is saved in the current directory as `PMC{id}.xml`, `PMC{id}.pdf` or `PMC{id}.html`.

The methods try several sources in turn:

| Method | Sources, in order | If no source succeeds |
|---|---|---|
| `download_xml_by_pmcid()` | The file cache; the Europe PMC REST API; the Europe PMC FTP open-access archives; the Europe PMC `fulltextRepo` endpoint; with `extra_strategies=True` (the default), the NCBI PMC OA web service, NCBI E-utilities efetch, BioC-PMC, DOI content negotiation and the bioRxiv/medRxiv API; Unpaywall | Raises `FullTextError` (`FULL003`) |
| `download_pdf_by_pmcid()` | The file cache; `https://europepmc.org/articles/PMC{id}?pdf=render`; the Europe PMC render service `ptpmcrender.fcgi`; a ZIP file from the open-access PDF collection; Unpaywall | Returns `None` |
| `download_html_by_pmcid()` | The file cache; the article's web page `https://europepmc.org/article/PMC/{id}` | Returns `None` |

- `client.last_xml_source` names the source of the last XML file: `cache`, `europepmc_rest`, `europepmc_ftp_bulk`, `europepmc_fulltext_repo`, `pmc_oa_service`, `ncbi_efetch`, `bioc_pmc`, `doi_negotiation`, `biorxiv` or `unpaywall`.
- The DOI-based sources need the article's DOI. Pass `doi=` to `download_xml_by_pmcid()`, or the client looks it up in Europe PMC.
- The Unpaywall steps run only with a contact e-mail address: `FullTextClient(email="you@example.org")`, or the `UNPAYWALL_EMAIL` or `CROSSREF_EMAIL` environment variable. Without one they are skipped before any request, including the DOI lookup.
- A source that fails counts as having nothing, so the table's last column is the outcome whether the sources answered "not found" or could not be reached.
- A PDF counts as downloaded only if the file starts with `%PDF`.

## Check what is available

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    print(client.check_fulltext_availability("PMC3258128"))
```

Output:

```text
{'pdf': True, 'xml': True, 'html': True}
```

The check sends a HEAD request to the XML endpoint (`xml` is `True` for HTTP 200), a HEAD request to the PDF render URL (`pdf` is `True` for HTTP 200 with a PDF content type), and a GET request to the article's web page (`html` is `True` for HTTP 200). A request that fails counts as `False`. It says nothing about the other XML and PDF sources.

## Download many articles

`download_fulltext_batch()` downloads one article after another and can report progress:

```python
from pyeuropepmc import FullTextClient


def report(progress):
    print(f"{progress.current_item}/{progress.total_items} {progress.status.split()[0]}")


with FullTextClient() as client:
    results = client.download_fulltext_batch(
        ["PMC3258128", "PMC3359999"],
        format_type="xml",
        output_dir="xml_files",
        progress_callback=report,
        progress_update_interval=0,
    )

for pmcid, path in results.items():
    print(pmcid, path)
```

Output:

```text
0/2 initialized
1/2 downloading
2/2 downloading
2/2 completed
PMC3258128 xml_files/PMC3258128.xml
PMC3359999 xml_files/PMC3359999.xml
```

- Files are saved as `output_dir/PMC{id}.{format}`; `output_dir` defaults to the current directory. The result maps each PMC ID, as you passed it, to a `Path` or to `None`.
- With `skip_errors=True` (the default), a `FullTextError` for one article is logged and that article maps to `None`; with `False` the error is raised. Other exceptions stop the batch either way.
- The callback receives a `ProgressInfo` object: once with status `initialized`, before a download when at least `progress_update_interval` seconds (default 1.0) have passed since the last call, and once with status `completed`. See [ProgressInfo](../../api/fulltext-client.md#progressinfo).

`download_fulltext_batch_parallel()` runs the downloads in a thread pool:

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    results = client.download_fulltext_batch_parallel(
        ["PMC3258128", "PMC3359999"],
        format_type="xml",
        output_dir="parallel",
        max_workers=2,
        show_progress=False,
    )
    print({pmcid: str(path) for pmcid, path in sorted(results.items())})
    print(client.download_stats["success_rate"], client.download_stats["global_stats"])
```

Output:

```text
{'PMC3258128': 'parallel/PMC3258128.xml', 'PMC3359999': 'parallel/PMC3359999.xml'}
1.0 {'total_requests': 2, 'total_failures': 0, 'total_successes': 2}
```

- `max_workers` defaults to the number of CPUs, at most 8; larger values are reduced to 8.
- Each worker thread has its own HTTP session and a rate limiter of one request per second. The rate limiter is applied only after the cache lookup, so files served from the cache do not wait.
- `show_progress=True` (the default) shows a tqdm progress bar.
- After the call, `client.download_stats` holds counts, timings and per-worker statistics.
- Failed downloads are not retried, and the result lists the articles in the order their downloads finished.

## Search and download

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    results = client.search_and_download_fulltext(
        "microRNA AND OPEN_ACCESS:y",
        format_type="xml",
        max_results=5,
        output_dir="search_downloads",
    )
print(sorted(results))
```

Output:

```text
['3258128', '3359999']
```

The method searches Europe PMC with `SearchClient` (one page of `max_results` results) and keeps the results that have a PMCID. With `only_available=True` (the default) it then calls `check_fulltext_availability()` for each and keeps those where the requested format is available. It downloads them with `download_fulltext_batch()` for PDF and XML, or `download_html_by_pmcid()` for HTML. The keys of the result are PMC IDs without the `PMC` prefix.

## Caching

`FullTextClient` has two separate caches.

- **File cache for downloads**, specific to `FullTextClient` and on by default. Every downloaded file is copied to `cache_dir/pdf`, `cache_dir/xml` or `cache_dir/html` as `PMC{id}.{format}`. The `download_*_by_pmcid` methods, and the batch methods that use them, look there before sending a request and copy a cached file to `output_path`. The default `cache_dir` is `pyeuropepmc_cache` in the system temporary directory (`tempfile.gettempdir()`). A cached file is used if it is not empty, is younger than `cache_max_age_days` (default 30) and, with `verify_cached_files=True` (the default), starts like a PDF, XML or HTML file. `FullTextClient(enable_cache=False)` turns it off. `get_fulltext_content()` never uses it.
- **API response cache**, opt-in as for the other clients. Pass `cache_config=CacheConfig(enabled=True)` to cache the results of `check_fulltext_availability()`. It is held in memory unless the `CacheConfig` sets `enable_l2=True`, which adds a disk layer; a disk cache is currently wiped when another cache opens the same directory. See the [caching guide](../caching/README.md) and the [caching reference](../../advanced/caching.md).

```python
from pyeuropepmc import FullTextClient

with FullTextClient(cache_dir="fulltext_cache") as client:
    client.download_xml_by_pmcid("PMC3258128", output_path="first/PMC3258128.xml")
    client.download_xml_by_pmcid("PMC3258128", output_path="second/PMC3258128.xml")
    print(client.last_xml_source)

    stats = client.get_cache_stats()
    print(stats["total_files"], stats["formats"]["xml"])
    print(client.clear_cache(format_type="xml", max_age_days=0))
```

Output:

```text
cache
1 {'count': 1, 'size_bytes': 82474}
1
```

`clear_cache(format_type=None, max_age_days=None)` deletes cached files older than `max_age_days` (default: `cache_max_age_days`) and returns how many it deleted; `max_age_days=0` deletes all of them.

## Bulk PDF downloads over FTP

`FTPDownloader` downloads the per-article ZIP files that Europe PMC publishes at `https://europepmc.org/ftp/pdf/` and extracts the PDFs from them. It handles PDFs only; to download XML for many articles, use `download_fulltext_batch_parallel(..., format_type="xml")`.

```python
from pyeuropepmc import FTPDownloader

with FTPDownloader() as downloader:
    results = downloader.bulk_download_and_extract(["11691200", "99999999"], output_dir="ftp_pdfs")

for pmcid, result in results.items():
    print(pmcid, result["status"], result.get("pdf_paths", result.get("error")))
```

Output:

```text
11691200 success [PosixPath('ftp_pdfs/extracted/PMC11691200.pdf')]
99999999 not_found PMC ID not found in FTP
```

Pass PMC IDs as digits without the `PMC` prefix; IDs with the prefix are reported as `not_found`. The [FTPDownloader reference](../../api/ftp-downloader.md) explains the result format and how the downloader finds the files.

## Handle errors

```python
from pyeuropepmc import FullTextClient
from pyeuropepmc.core.exceptions import PyEuropePMCError

with FullTextClient() as client:
    try:
        pdf_path = client.download_pdf_by_pmcid("PMC3258128", output_path="downloads/PMC3258128.pdf")
        print(pdf_path if pdf_path is not None else "No PDF available")
    except PyEuropePMCError as error:
        print(type(error).__name__, error.error_code)
```

| Situation | Result |
|---|---|
| The PMC ID is empty, or is not digits after an optional `PMC` prefix | `FullTextError` (`FULL001` or `FULL002`), from every method |
| `get_fulltext_content()` gets HTTP 404 | `FullTextError` (`FULL003`) |
| `get_fulltext_content()` gets HTTP 403 | `FullTextError` (`FULL008`) |
| `get_fulltext_content()` gets another HTTP error, or the request fails | `FullTextError` (`FULL005`) |
| `get_fulltext_content()` with a `format_type` other than `"xml"` or `"html"` | `FullTextError` (`FULL004`) |
| `download_xml_by_pmcid()` finds no XML | `FullTextError` (`FULL003`) |
| `download_pdf_by_pmcid()` finds no PDF | `None` |
| `download_html_by_pmcid()` gets an HTTP or network error | `None` |
| Saving an XML or HTML file fails | `FullTextError` (`FULL009`) |

`FullTextError`, `APIClientError` and `ParsingError` derive from `PyEuropePMCError` in `pyeuropepmc.core.exceptions`. `FullTextError` and `APIClientError` can also be imported from `pyeuropepmc`. `pyeuropepmc.EuropePMCError` is an alias of `PyEuropePMCError`, so it catches all of them.

## Known limitations

- The `fulltextRepo` step requests `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{id}/fulltextRepo`. That path has not been checked against the live service; the file endpoint the Europe PMC website loads, `https://europepmc.org/api/fulltextRepo`, takes a file name and MIME type rather than only a PMC ID.
- The Unpaywall steps do not find anything yet: `UnpaywallClient` requests the Unpaywall API base URL twice (`https://api.unpaywall.org/v2/https://api.unpaywall.org/v2/{doi}`), so every lookup fails and the step counts the article as not found.
- The FTP archive step guesses the archive name from the PMC ID. From an archive that holds the article it saves only that article.
- `download_html_by_pmcid()` saves the article's Europe PMC web page as served, not a rendering of the article alone.
