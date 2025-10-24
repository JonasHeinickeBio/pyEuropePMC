# PyEuropePMC

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-200%2B%20passed-green.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-90%2B%25-brightgreen.svg)](htmlcov/)


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

- **[Complete Documentation](docs/)** - Comprehensive guides and API reference
- **[Quick Start Guide](docs/quickstart.md)** - Get started in minutes
- **[API Reference](docs/api/)** - Detailed API documentation
- **[Examples](docs/examples/)** - Code examples and use cases

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](docs/development/contributing.md) for details.

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## 🌐 Links

- **PyPI Package**: [pyeuropepmc](https://pypi.org/project/pyeuropepmc/)
- **GitHub Repository**: [pyEuropePMC](https://github.com/JonasHeinickeBio/pyEuropePMC)
- **Documentation**: [GitHub Wiki](https://github.com/JonasHeinickeBio/pyEuropePMC/wiki)
- **Issue Tracker**: [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
