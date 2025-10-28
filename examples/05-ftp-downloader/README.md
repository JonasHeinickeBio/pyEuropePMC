# FTP Downloader Examples

**Level**: ⭐⭐ Intermediate
**Examples**: 3 files (2 notebooks + 1 script)
**Time**: 20-30 minutes

## Overview

Download full text articles in bulk from Europe PMC's FTP servers. Get PDFs, XML files, and supplementary materials efficiently with progress tracking and error handling.

## 📓 Examples

### 01-basic-download.ipynb
**Introduction to bulk downloads**

Learn download basics:
- Connecting to Europe PMC FTP
- Downloading single articles
- PDF and XML format selection
- Error handling
- File organization

**What you'll build**: A basic article downloader

**Key topics**:
- FTP connection setup
- Format selection (PDF/XML)
- Download verification
- Local file management

### 02-clean-workflow.ipynb
**Organized download workflows**

Production-ready downloads:
- Structured directory organization
- Batch downloading with progress
- Duplicate detection
- Failed download retry
- Metadata tracking

**What you'll build**: A production-ready download system

**Key topics**:
- Directory structure
- Batch operations
- Progress tracking
- Error recovery
- Logging

### bulk-xml-demo.py
**Bulk XML processing script**

Download multiple XML files:
- Batch download from PMC ID list
- Concurrent downloads
- Progress callbacks
- Error aggregation

**What you'll build**: High-volume XML downloader

## 🚀 Quick Start

### Download Single Article
```python
from pyeuropepmc.ftp_downloader import FTPDownloader

downloader = FTPDownloader()

# Download PDF
pdf_path = downloader.download_fulltext("PMC3258128", format="pdf")
print(f"Downloaded: {pdf_path}")

# Download XML
xml_path = downloader.download_fulltext("PMC3258128", format="xml")
print(f"Downloaded: {xml_path}")
```

### Batch Download
```python
# Download multiple articles
pmc_ids = ["PMC3258128", "PMC3359999", "PMC3312970"]

for pmc_id in pmc_ids:
    try:
        path = downloader.download_fulltext(pmc_id, format="pdf")
        print(f"✅ {pmc_id}: {path}")
    except Exception as e:
        print(f"❌ {pmc_id}: {e}")
```

### With Progress Tracking
```python
def progress_callback(pmc_id, status, message):
    print(f"[{status}] {pmc_id}: {message}")

downloader = FTPDownloader(progress_callback=progress_callback)
downloader.download_fulltext("PMC3258128")
```

## 🎯 Key Features

### 1. Multiple Formats
Download different file types:
- **PDF**: Human-readable format
- **XML**: Structured full text (JATS/NLM)
- **Supplementary**: Additional data files

### 2. Bulk Operations
Efficient batch downloads:
- Multiple articles at once
- Progress tracking
- Error handling per article
- Automatic retries

### 3. Smart Organization
Automatic file management:
- Organized directory structure
- Duplicate detection
- Metadata preservation
- Clean file naming

### 4. Error Handling
Robust download system:
- Network error recovery
- Invalid PMC ID detection
- Missing file handling
- Detailed error logging

### 5. Progress Monitoring
Track download status:
- Real-time progress callbacks
- Success/failure counts
- Time estimation
- Detailed logging

## 💡 Common Use Cases

### Download Research Corpus
```python
# Download a collection for analysis
pmc_ids = get_pmc_ids_from_search()  # From search results

downloader = FTPDownloader(output_dir="my_corpus")

for pmc_id in pmc_ids:
    downloader.download_fulltext(pmc_id, format="xml")
```

### PDF Archive Creation
```python
# Create a PDF library
import os

downloader = FTPDownloader(output_dir="pdf_library")

# Download with organization
for pmc_id in article_list:
    pdf_path = downloader.download_fulltext(pmc_id, format="pdf")
    if pdf_path:
        print(f"Added to library: {os.path.basename(pdf_path)}")
```

### XML Corpus for NLP
```python
# Build XML corpus for text mining
downloader = FTPDownloader(output_dir="xml_corpus")

pmc_ids = ["PMC1234567", "PMC2345678", "PMC3456789"]

for pmc_id in pmc_ids:
    xml_path = downloader.download_fulltext(pmc_id, format="xml")
    # Process with FullTextXMLParser...
```

### Failed Download Recovery
```python
# Track and retry failed downloads
failed = []

for pmc_id in large_list:
    try:
        downloader.download_fulltext(pmc_id)
    except Exception as e:
        failed.append((pmc_id, str(e)))

# Retry failed downloads
for pmc_id, error in failed:
    print(f"Retrying {pmc_id} (failed with: {error})")
    # Retry logic...
```

## 📊 PMC ID Format

Supported PMC ID formats:
- `PMC3258128` (with prefix) ✅
- `3258128` (without prefix) ✅
- `PMC123456` (any valid PMC number) ✅

The downloader handles both formats automatically.

## 🔍 Advanced Patterns

### Custom Progress Tracking
```python
class DownloadTracker:
    def __init__(self):
        self.successful = 0
        self.failed = 0

    def callback(self, pmc_id, status, message):
        if status == "success":
            self.successful += 1
        elif status == "error":
            self.failed += 1
        print(f"Progress: {self.successful} OK, {self.failed} failed")

tracker = DownloadTracker()
downloader = FTPDownloader(progress_callback=tracker.callback)
```

### Parallel Downloads
```python
from concurrent.futures import ThreadPoolExecutor

def download_article(pmc_id):
    downloader = FTPDownloader()
    return downloader.download_fulltext(pmc_id)

pmc_ids = ["PMC1234567", "PMC2345678", "PMC3456789"]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = executor.map(download_article, pmc_ids)
```

### Selective Format Download
```python
# Download XML for parsing, PDF for reading
for pmc_id in article_list:
    # Get XML for processing
    xml_path = downloader.download_fulltext(pmc_id, format="xml")

    # Get PDF for manual review
    pdf_path = downloader.download_fulltext(pmc_id, format="pdf")
```

### Integration with Search
```python
from pyeuropepmc.search import SearchClient
from pyeuropepmc.ftp_downloader import FTPDownloader

# Search and download pipeline
with SearchClient() as client:
    results = client.search("machine learning", page_size=10)

downloader = FTPDownloader()

for article in results['resultList']['result']:
    pmcid = article.get('pmcid')
    if pmcid:
        downloader.download_fulltext(pmcid, format="pdf")
```

## 📁 Directory Structure

Default organization:
```
downloads/
├── PMC3258128.pdf
├── PMC3258128.xml
├── PMC3359999.pdf
└── PMC3359999.xml
```

Custom organization:
```
my_corpus/
├── pdf/
│   ├── PMC3258128.pdf
│   └── PMC3359999.pdf
└── xml/
    ├── PMC3258128.xml
    └── PMC3359999.xml
```

## 🆘 Troubleshooting

**Download fails with network error?**
- Check internet connection
- Verify FTP server is accessible
- Try again later (server may be busy)

**"Article not found" error?**
- Verify PMC ID is correct
- Check if article has full text available
- Not all articles are in FTP archive

**Slow download speeds?**
- Europe PMC FTP has rate limits
- Consider downloading during off-peak hours
- Use batch operations efficiently

**PDF missing but XML available?**
- Some articles only have XML
- Check article license and access restrictions
- Try alternative formats

## 📈 Performance Tips

1. **Batch operations**: Group downloads together
2. **Error handling**: Always use try-except
3. **Progress tracking**: Monitor long-running downloads
4. **Respect rate limits**: Don't hammer the FTP server
5. **Local caching**: Check if file exists before downloading

## 🔗 Resources

- [Europe PMC FTP Site](https://europepmc.org/ftp/)
- [PMC Open Access Subset](https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/)
- [Download Guidelines](https://europepmc.org/Help#FTPACCESS)

## 🚀 Next Steps

- **Parse downloads**: Use [04-fulltext-parser](../04-fulltext-parser/) on XML files
- **Organize corpus**: Build structured research libraries
- **Automate**: Create scheduled download scripts
- **Analyze**: Extract and process downloaded content
