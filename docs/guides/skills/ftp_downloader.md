# FTP Downloader Skill

Bulk download XML/PDF files from Europe PMC FTP servers.

```python
from pyeuropepmc import FTPDownloader

downloader = FTPDownloader()

# Download multiple papers
results = downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678", "3456789"],
    output_dir="./downloads",
    file_type="xml"  # or "pdf"
)

# Download by DOI
downloader.download_by_doi("10.1038/nature11476", output_dir="./downloads")
```

Key tips:
- Use `file_type="xml"` for full-text, `"pdf"` for publisher PDFs
- Progress callback via `progress_callback` parameter
- Rate limiting built-in; respects FTP server limits
- Returns dict with success/failure counts
