# PyEuropePMC

[![PyPI version](https://img.shields.io/pypi/v/pyeuropepmc.svg)](https://pypi.org/project/pyeuropepmc/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pyeuropepmc)](https://pypi.org/project/pyeuropepmc/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-200%2B%20passed-green.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-90%2B%25-brightgreen.svg)](htmlcov/)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://jonasheinickebio.github.io/pyEuropePMC/)

## 🔄 Build Status

[![CI/CD Pipeline](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/cdci.yml/badge.svg)](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/cdci.yml)
[![Python Compatibility](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/python-compatibility.yml/badge.svg)](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/python-compatibility.yml)
[![Documentation](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/deploy-docs.yml/badge.svg)](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/deploy-docs.yml)
[![CodeQL](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/codeql.yml/badge.svg)](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/JonasHeinickeBio/pyEuropePMC/branch/main/graph/badge.svg)](https://codecov.io/gh/JonasHeinickeBio/pyEuropePMC)


**PyEuropePMC** is a robust Python toolkit for automated search, extraction, and analysis of scientific literature from [Europe PMC](https://europepmc.org/).

## ✨ Key Features


- 🔍 **Comprehensive Search API** - Query Europe PMC with advanced search options
- 📄 **Full-Text Retrieval** - Download PDFs, XML, and HTML content from open access articles
- 🔬 **XML Parsing & Conversion** - Parse full text XML and convert to plaintext, markdown, extract tables and metadata
- 📊 **Multiple Output Formats** - JSON, XML, Dublin Core (DC)
- 📦 **Bulk FTP Downloads** - Efficient bulk PDF downloads from Europe PMC FTP servers
- 🔄 **Smart Pagination** - Automatic handling of large result sets
- 🛡️ **Robust Error Handling** - Built-in retry logic and connection management
- 🧑‍💻 **Type Safety** - Extensive use of type annotations and validation
- ⚡ **Rate Limiting** - Respectful API usage with configurable delays
- 🧪 **Extensively Tested** - 200+ tests with 90%+ code coverage

## 🚀 Quick Start

### Installation

```bash
pip install pyeuropepmc
```

### Basic Usage

```python
from pyeuropepmc.search import SearchClient

# Search for papers
with SearchClient() as client:
    results = client.search("CRISPR gene editing", pageSize=10)

    for paper in results["resultList"]["result"]:
        print(f"Title: {paper['title']}")
        print(f"Authors: {paper.get('authorString', 'N/A')}")
        print("---")
```


### Advanced Search with Parsing

```python
# Search and automatically parse results
papers = client.search_and_parse(
    query="COVID-19 AND vaccine",
    pageSize=50,
    sort="CITED desc"
)

for paper in papers:
    print(f"Citations: {paper.get('citedByCount', 0)}")
    print(f"Title: {paper.get('title', 'N/A')}")
```


### Full-Text Content Retrieval

```python
from pyeuropepmc.fulltext import FullTextClient

# Initialize full-text client
fulltext_client = FullTextClient()

# Download PDF
pdf_path = fulltext_client.download_pdf_by_pmcid("PMC1234567", output_dir="./downloads")

# Download XML
xml_content = fulltext_client.download_xml_by_pmcid("PMC1234567")

# Bulk FTP downloads
from pyeuropepmc.ftp_downloader import FTPDownloader

ftp_downloader = FTPDownloader()
results = ftp_downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678"],
    output_dir="./bulk_downloads"
)
```

### Full-Text XML Parsing

Parse full text XML files and extract structured information:

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

# Download and parse XML
with FullTextClient() as client:
    xml_path = client.download_xml_by_pmcid("PMC3258128")

# Parse the XML
with open(xml_path, 'r') as f:
    parser = FullTextXMLParser(f.read())

# Extract metadata
metadata = parser.extract_metadata()
print(f"Title: {metadata['title']}")
print(f"Authors: {', '.join(metadata['authors'])}")

# Convert to different formats
plaintext = parser.to_plaintext()  # Plain text
markdown = parser.to_markdown()     # Markdown format

# Extract tables
tables = parser.extract_tables()
for table in tables:
    print(f"Table: {table['label']} - {len(table['rows'])} rows")

# Extract references
references = parser.extract_references()
print(f"Found {len(references)} references")
```

## 📚 Documentation

**📖 [Read the Full Documentation](https://jonasheinickebio.github.io/pyEuropePMC/)** ← Start Here!

Quick Links:
- 🚀 [Quick Start Guide](https://jonasheinickebio.github.io/pyEuropePMC/getting-started/quickstart.html) - Get started in 5 minutes
- 📚 [API Reference](https://jonasheinickebio.github.io/pyEuropePMC/api/) - Complete API documentation
- 💡 [Examples](https://jonasheinickebio.github.io/pyEuropePMC/examples/) - Code examples and use cases
- ✨ [Features](https://jonasheinickebio.github.io/pyEuropePMC/features/) - Explore all features

> **Note:** Enable GitHub Pages first! See [Setup Guide](.github/SETUP_GITHUB_PAGES.md) for instructions.

## 📊 Performance

> Benchmarks run weekly on Monday at 02:00 UTC. Last updated: *Pending first run*

| Metric | Value |
|--------|-------|
| **Total Requests** | *Pending* |
| **Average Response Time** | *Pending* |
| **Success Rate** | *Pending* |

*Benchmark results will be automatically updated weekly by GitHub Actions.*

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](docs/development/contributing.md) for details.

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## 🌐 Links

- **📖 Documentation**: [GitHub Pages](https://jonasheinickebio.github.io/pyEuropePMC/) - Full documentation site
- **📦 PyPI Package**: [pyeuropepmc](https://pypi.org/project/pyeuropepmc/) - Install with pip
- **💻 GitHub Repository**: [pyEuropePMC](https://github.com/JonasHeinickeBio/pyEuropePMC) - Source code
- **🐛 Issue Tracker**: [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues) - Report bugs or request features
