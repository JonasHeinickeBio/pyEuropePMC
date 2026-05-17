# Full-Text Retrieval

The **FullTextClient** and **FTPDownloader** provide comprehensive capabilities for downloading complete article content from Europe PMC.

## Overview

- 📄 **PDF downloads** from open access articles
- 📋 **XML full-text** in JATS/NLM format
- 🌐 **HTML content** retrieval
- 📦 **Bulk FTP downloads** for large datasets
- 📊 **Progress tracking** with callbacks
- 🔄 **Automatic retry** and error handling
- 💾 **Smart caching** for repeated requests
- ⚡ **Parallel batch downloads** with rate limiting and statistics
- 🎯 **Efficient cache usage** - rate limiter only invoked for network requests, not cached hits

## Quick Start

### FullTextClient (Individual Downloads)

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    # Download PDF
    pdf_path = client.download_pdf_by_pmcid("PMC3258128")

    # Download XML
    xml_path = client.download_xml_by_pmcid("PMC3258128")

    # Get XML content directly
    xml_content = client.get_fulltext_xml("PMC3258128")
```

### FTPDownloader (Bulk Downloads)

```python
from pyeuropepmc import FTPDownloader

downloader = FTPDownloader()

# Bulk download with progress tracking
results = downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678", "3456789"],
    output_dir="./papers",
    file_format="pdf"
)

print(f"Downloaded: {len(results['pdf_files'])} PDFs")
print(f"Failed: {len(results['failed'])} items")
```

## FullTextClient Features

### PDF Downloads

Download PDFs from open access articles:

```python
with FullTextClient() as client:
    # Download single PDF
    pdf_path = client.download_pdf_by_pmcid(
        pmcid="PMC3258128",
        output_dir="./downloads"
    )
    print(f"PDF saved to: {pdf_path}")

    # Check if PDF is available before downloading
    metadata = client.get_metadata("PMC3258128")
    if metadata.get('isOpenAccess'):
        pdf_path = client.download_pdf_by_pmcid("PMC3258128")
```

**Note:** Only open access articles have PDFs available. Check `isOpenAccess` flag first.

### XML Downloads

Download full-text XML in JATS/NLM format:

```python
with FullTextClient() as client:
    # Download XML to file
    xml_path = client.download_xml_by_pmcid(
        pmcid="PMC3258128",
        output_dir="./xml_files"
    )

    # Get XML content as string
    xml_content = client.get_fulltext_xml("PMC3258128")

    # Parse immediately
    from pyeuropepmc import FullTextXMLParser
    parser = FullTextXMLParser(xml_content)
    metadata = parser.extract_metadata()
```

### HTML Content

Retrieve HTML representation:

```python
with FullTextClient() as client:
    html_content = client.get_fulltext_html("PMC3258128")

    # Save to file
    with open("article.html", "w", encoding="utf-8") as f:
        f.write(html_content)
```

### Progress Tracking

Monitor download progress with callbacks:

```python
def progress_callback(current, total, message):
    percentage = (current / total) * 100
    print(f"Progress: {percentage:.1f}% - {message}")

with FullTextClient() as client:
    pdf_path = client.download_pdf_by_pmcid(
        pmcid="PMC3258128",
        progress_callback=progress_callback
    )
```

## FTPDownloader Features

The **FTPDownloader** is optimized for bulk operations and large-scale downloads.

### Bulk PDF Downloads

Download multiple PDFs efficiently:

```python
from pyeuropepmc import FTPDownloader

downloader = FTPDownloader()

# List of PMC IDs
pmcids = ["1234567", "2345678", "3456789", "4567890"]

# Bulk download
results = downloader.bulk_download_and_extract(
    pmcids=pmcids,
    output_dir="./papers",
    file_format="pdf"
)

# Process results
print(f"Successful: {len(results['pdf_files'])}")
print(f"Failed: {len(results['failed'])}")

for pdf_file in results['pdf_files']:
    print(f"Downloaded: {pdf_file}")

for failed_pmcid in results['failed']:
    print(f"Failed: PMC{failed_pmcid}")
```

### Bulk XML Downloads

Download XML files in bulk:

```python
results = downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678"],
    output_dir="./xml_collection",
    file_format="xml"
)

# Access downloaded XML files
for xml_file in results['xml_files']:
    with open(xml_file) as f:
        xml_content = f.read()
        # Process XML...
```

### Mixed Format Downloads

Download both PDFs and XML files:

```python
results = downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678"],
    output_dir="./papers",
    file_format="both"  # Download both PDF and XML
)

print(f"PDFs: {len(results['pdf_files'])}")
print(f"XMLs: {len(results['xml_files'])}")
```

### Progress Tracking for Bulk Downloads

```python
def bulk_progress(current, total, message):
    print(f"[{current}/{total}] {message}")

results = downloader.bulk_download_and_extract(
    pmcids=pmcids,
    output_dir="./papers",
    file_format="pdf",
    progress_callback=bulk_progress
)
```

## Advanced Examples

### Example 1: Search + Download Pipeline

Combine search with full-text downloads:

```python
from pyeuropepmc import SearchClient, FullTextClient

# Step 1: Search for papers
with SearchClient() as search_client:
    results = search_client.search(
        query="machine learning AND biology",
        pageSize=20
    )

    # Extract PMC IDs from open access papers
    pmcids = [
        paper['pmcid'].replace('PMC', '')
        for paper in results['resultList']['result']
        if paper.get('pmcid') and paper.get('isOpenAccess') == 'Y'
    ]

# Step 2: Download full-text PDFs
with FullTextClient() as fulltext_client:
    for pmcid in pmcids:
        try:
            pdf_path = fulltext_client.download_pdf_by_pmcid(f"PMC{pmcid}")
            print(f"Downloaded: {pdf_path}")
        except Exception as e:
            print(f"Failed PMC{pmcid}: {e}")
```

### Example 2: Bulk Download with Error Recovery

```python
from pyeuropepmc import FTPDownloader

downloader = FTPDownloader()

# First attempt
results = downloader.bulk_download_and_extract(
    pmcids=large_pmcid_list,
    output_dir="./papers",
    file_format="pdf"
)

# Retry failed downloads
if results['failed']:
    print(f"Retrying {len(results['failed'])} failed downloads...")
    retry_results = downloader.bulk_download_and_extract(
        pmcids=results['failed'],
        output_dir="./papers",
        file_format="pdf"
    )

    # Combine results
    all_successful = results['pdf_files'] + retry_results['pdf_files']
    still_failed = retry_results['failed']

    print(f"Total successful: {len(all_successful)}")
    print(f"Still failed: {len(still_failed)}")
```

### Example 3: Parallel Batch Download with Rate Limiting

Download multiple files in parallel with automatic rate limiting and progress tracking:

```python
from pyeuropepmc import FullTextClient

client = FullTextClient()

# Parallel batch download with 4 workers
pmcids = ["PMC1234567", "PMC2345678", "PMC3456789", "PMC4567890"]

results = client.download_fulltext_batch_parallel(
    pmcids=pmcids,
    format_type="pdf",
    output_dir="./downloads",
    max_workers=4,
    show_progress=True
)

# Check results
for pmcid, path in results.items():
    if path:
        print(f"✓ {pmcid}: {path}")
    else:
        print(f"✗ {pmcid}: Failed")

# View download statistics
print(f"Total requests: {client.download_stats['global_stats']['total_requests']}")
print(f"Success rate: {client.download_stats['success_rate']:.1%}")
```

**Note:** The rate limiter is only invoked for network requests, not for cached files, making parallel downloads more efficient.

### Example 3: Download + Parse Workflow

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

with FullTextClient() as client:
    pmcids = ["PMC3258128", "PMC4567890"]

    for pmcid in pmcids:
        # Download XML
        xml_content = client.get_fulltext_xml(pmcid)

        # Parse immediately
        parser = FullTextXMLParser(xml_content)

        # Extract data
        metadata = parser.extract_metadata()
        tables = parser.extract_tables()
        references = parser.extract_references()

        print(f"\n{metadata['title']}")
        print(f"Tables: {len(tables)}")
        print(f"References: {len(references)}")
```

### Example 4: Batch Processing with Progress

```python
from pyeuropepmc import FTPDownloader, FullTextXMLParser
import os

# Download bulk XML files
downloader = FTPDownloader()
results = downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678", "3456789"],
    output_dir="./xml_files",
    file_format="xml"
)

# Process each downloaded XML
all_metadata = []
for xml_file in results['xml_files']:
    with open(xml_file) as f:
        parser = FullTextXMLParser(f.read())
        metadata = parser.extract_metadata()
        all_metadata.append(metadata)
        print(f"Processed: {metadata['title']}")

# Save summary
import json
with open("metadata_summary.json", "w") as f:
    json.dump(all_metadata, f, indent=2)
```

### Example 5: Selective Download by File Size

```python
from pyeuropepmc import FullTextClient
import os

with FullTextClient() as client:
    pmcids = ["PMC3258128", "PMC4567890", "PMC5678901"]

    for pmcid in pmcids:
        # Download to temporary location first
        pdf_path = client.download_pdf_by_pmcid(pmcid, output_dir="./temp")

        # Check file size
        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)

        if file_size_mb > 10:
            print(f"{pmcid}: Too large ({file_size_mb:.1f} MB), skipping")
            os.remove(pdf_path)
        else:
            # Move to final location
            final_path = f"./papers/{pmcid}.pdf"
            os.rename(pdf_path, final_path)
            print(f"{pmcid}: Downloaded ({file_size_mb:.1f} MB)")
```

## Performance Optimization

### 1. Parallel Batch Downloads with Rate Limiting

Use parallel downloads for multiple files with automatic rate limiting:

```python
from pyeuropepmc import FullTextClient

client = FullTextClient()

# Download 10 files in parallel with 4 workers
pmcids = [f"PMC{1234560+i}" for i in range(10)]

results = client.download_fulltext_batch_parallel(
    pmcids=pmcids,
    format_type="pdf",
    max_workers=4,
    show_progress=True
)

print(f"Downloaded: {sum(1 for p in results.values() if p)} files")
```

**Key features:**
- Automatic rate limiting per worker (1 request/second)
- Cache-aware: rate limiter only invoked for network requests
- Progress tracking with detailed worker statistics
- Automatic error handling and retry logic

### 2. Use FTP for Bulk Downloads

For downloading many articles, FTP is much faster:

```python
# ❌ Slow: Individual downloads
with FullTextClient() as client:
    for pmcid in many_pmcids:
        client.download_pdf_by_pmcid(pmcid)

# ✅ Fast: Bulk FTP download
downloader = FTPDownloader()
results = downloader.bulk_download_and_extract(
    pmcids=many_pmcids,
    output_dir="./papers"
)
```

### 3. Enable Caching

Caching is enabled by default for FullTextClient:

```python
with FullTextClient() as client:
    # First call - downloads from API
    xml1 = client.get_fulltext_xml("PMC3258128")

    # Second call - retrieved from cache (instant)
    xml2 = client.get_fulltext_xml("PMC3258128")
```

### 4. Batch Processing

Process files in batches to manage memory:

```python
from pyeuropepmc import FTPDownloader

downloader = FTPDownloader()

# Split into batches
batch_size = 100
for i in range(0, len(all_pmcids), batch_size):
    batch = all_pmcids[i:i+batch_size]

    results = downloader.bulk_download_and_extract(
        pmcids=batch,
        output_dir=f"./batch_{i//batch_size}",
        file_format="xml"
    )

    # Process batch
    # Clean up if needed
```

## Error Handling

```python
from pyeuropepmc import FullTextClient
from pyeuropepmc.exceptions import EuropePMCException

with FullTextClient() as client:
    try:
        # Try to download PDF
        pdf_path = client.download_pdf_by_pmcid("PMC1234567")

    except EuropePMCException as e:
        if "not found" in str(e).lower():
            print("Article not available")
        elif "not open access" in str(e).lower():
            print("Article is not open access")
        else:
            print(f"API error: {e}")

    except IOError as e:
        print(f"File system error: {e}")

    except Exception as e:
        print(f"Unexpected error: {e}")
```

## File Organization

### Recommended Directory Structure

```
project/
├── downloads/
│   ├── pdfs/
│   │   ├── PMC1234567.pdf
│   │   ├── PMC2345678.pdf
│   │   └── PMC3456789.pdf
│   ├── xml/
│   │   ├── PMC1234567.xml
│   │   ├── PMC2345678.xml
│   │   └── PMC3456789.xml
│   └── html/
│       └── ...
└── processed/
    └── metadata.json
```

### Organizing Downloads

```python
import os
from pyeuropepmc import FullTextClient

# Create organized structure
base_dir = "./downloads"
os.makedirs(f"{base_dir}/pdfs", exist_ok=True)
os.makedirs(f"{base_dir}/xml", exist_ok=True)

with FullTextClient() as client:
    pmcid = "PMC3258128"

    # Download to organized locations
    pdf = client.download_pdf_by_pmcid(pmcid, output_dir=f"{base_dir}/pdfs")
    xml = client.download_xml_by_pmcid(pmcid, output_dir=f"{base_dir}/xml")
```

## See Also

- **[API Reference: FullTextClient](../../api/fulltext-client.md)** - Complete API documentation
- **[API Reference: FTPDownloader](../../api/ftp-downloader.md)** - FTP downloader API
- **[XML Parsing](../parsing/)** - Parse downloaded XML files
- **[Examples: Full-Text](../../examples/basic-examples.md#fulltext)** - More code examples
- **[Advanced: Progress Callbacks](../../advanced/configuration.md#progress-tracking)** - Custom progress tracking

---

**Next Steps:**
- Learn [XML Parsing](../parsing/) to extract data from downloaded files
- Explore [Caching](../caching/) to understand caching behavior
- Read [Advanced Examples](../../examples/advanced-examples.md) for complex workflows
