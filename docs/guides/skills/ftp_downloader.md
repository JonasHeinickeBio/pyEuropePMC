# FTP downloader skill

Download open-access PDF bundles for many articles from the Europe PMC FTP site.

```python
from pyeuropepmc import FTPDownloader

with FTPDownloader() as downloader:
    results = downloader.bulk_download_and_extract(
        pmcids=["11691200", "11861200"],  # digits, without the "PMC" prefix
        output_dir="./downloads",
    )

succeeded = [pmcid for pmcid, result in results.items() if result["status"] == "success"]
print(succeeded)
```

Output:

```text
['11691200', '11861200']
```

Key tips:

- It downloads PDFs only, as ZIP files from `https://europepmc.org/ftp/pdf/`. The PDFs are extracted to `output_dir/extracted/`, and the ZIP files are deleted unless you pass `keep_zips=True`.
- Each result has a `status` of `"success"`, `"not_found"` or `"error"`, plus `zip_path` and `pdf_paths`, or `error`.
- A PMC ID with the `PMC` prefix, or one whose directory listing could not be read, comes back as `"not_found"`.
- There is no progress callback. For XML, or for progress reporting, use `FullTextClient.download_fulltext_batch()` or `download_fulltext_batch_parallel()`.
- To download by DOI, look up the PMC ID first with `SearchClient`.

See the [FTPDownloader reference](../../api/ftp-downloader.md) and [Full-text retrieval](../../features/fulltext/README.md).
