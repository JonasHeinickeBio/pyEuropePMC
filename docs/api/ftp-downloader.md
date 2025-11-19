# FTPDownloader API Reference

The `FTPDownloader` enables bulk downloading of full-text articles from Europe PMC's FTP servers.

## Class Overview

```python
from pyeuropepmc.clients.ftp_downloader import FTPDownloader

class FTPDownloader:
    """Client for bulk downloading via FTP."""
```

## Constructor

### `FTPDownloader(timeout=30, max_retries=3)`

Create a new FTPDownloader instance.

**Parameters:**
- `timeout` (int): Connection timeout in seconds (default: 30)
- `max_retries` (int): Maximum number of retry attempts (default: 3)

## Methods

### `bulk_download_and_extract(pmcids, output_dir, **kwargs)`

Download and extract multiple PMC articles.

**Parameters:**
- `pmcids` (List[str]): List of PMC IDs (without "PMC" prefix)
- `output_dir` (str): Directory to save extracted files
- `progress_callback` (callable): Optional progress callback function
- `max_workers` (int): Maximum concurrent downloads (default: 4)

**Returns:**
- List of successfully downloaded PMC IDs

**Example:**
```python
from pyeuropepmc.clients.ftp_downloader import FTPDownloader

downloader = FTPDownloader()
results = downloader.bulk_download_and_extract(
    pmcids=["3258128", "1234567"],
    output_dir="./downloads",
    max_workers=2
)

print(f"Downloaded {len(results)} articles")
```

### `download_single_article(pmcid, output_dir)`

Download and extract a single article.

**Parameters:**
- `pmcid` (str): PMC ID (without "PMC" prefix)
- `output_dir` (str): Directory to save extracted files

**Returns:**
- Path to extracted directory or None if failed

### `get_ftp_path(pmcid)`

Get the FTP path for a PMC ID.

**Parameters:**
- `pmcid` (str): PMC ID (without "PMC" prefix)

**Returns:**
- FTP path string

## Context Manager Usage

```python
with FTPDownloader() as downloader:
    results = downloader.bulk_download_and_extract(
        pmcids=["3258128", "1234567"],
        output_dir="./downloads"
    )
```

## Error Handling

Raises `FTPDownloadError` for download-related issues:

```python
from pyeuropepmc.clients.ftp_downloader import FTPDownloader
from pyeuropepmc.core.exceptions import FTPDownloadError

try:
    with FTPDownloader() as downloader:
        results = downloader.bulk_download_and_extract(
            pmcids=["3258128"],
            output_dir="./downloads"
        )
except FTPDownloadError as e:
    print(f"Download failed: {e}")
```

## Examples

### Basic Bulk Download

```python
from pyeuropepmc.clients.ftp_downloader import FTPDownloader

# Download multiple articles
downloader = FTPDownloader()
successful = downloader.bulk_download_and_extract(
    pmcids=["3258128", "1234567", "2345678"],
    output_dir="./pmc_articles"
)

print(f"Successfully downloaded {len(successful)} articles")
```

### Progress Tracking

```python
def progress_callback(pmcid, status, current, total):
    print(f"{pmcid}: {status} ({current}/{total})")

downloader = FTPDownloader()
results = downloader.bulk_download_and_extract(
    pmcids=["3258128", "1234567"],
    output_dir="./downloads",
    progress_callback=progress_callback
)
```

### Single Article Download

```python
# Download one article
result = downloader.download_single_article("3258128", "./downloads")
if result:
    print(f"Article extracted to: {result}")
else:
    print("Download failed")
```

## FTP Structure

Europe PMC organizes articles in a hierarchical FTP structure:

```
/pub/pmc/
├── oa_bulk/           # Open access articles
│   ├── oa_comm/       # Commentary articles
│   ├── oa_noncomm/    # Non-commentary articles
│   └── oa_other/      # Other article types
├── incremental/       # Incremental updates
└── articles/          # Individual article files
```

## Performance Considerations

- **Concurrent Downloads**: Use `max_workers` to control parallelism
- **Rate Limiting**: Built-in delays prevent FTP server overload
- **Resume Capability**: Automatically resumes interrupted downloads
- **Disk Space**: Each article may require 1-10 MB of storage

## Related Classes

- [`FullTextClient`](../fulltext-client.md) - For individual article downloads
- [`SearchClient`](../search-client.md) - For finding articles to download
