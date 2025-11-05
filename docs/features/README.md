# PyEuropePMC Features

PyEuropePMC provides a comprehensive suite of features for working with scientific literature from Europe PMC.

## 🔍 Core Features

### [Search](search/)
**Query the Europe PMC database with powerful search capabilities**

- Advanced query syntax support
- Boolean operators (AND, OR, NOT)
- Field-specific searches
- Date range filtering
- Citation count sorting
- Pagination for large result sets
- Multiple output formats (JSON, XML, Dublin Core)

**Quick Example:**
```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("cancer AND therapy", pageSize=50, sort="CITED desc")
```

**[Learn More →](search/)**

---

### [Full-Text Retrieval](fulltext/)
**Download complete article content in multiple formats**

- PDF downloads from open access articles
- XML full-text retrieval
- HTML content access
- Bulk FTP downloads for large datasets
- Progress tracking with callbacks
- Automatic retry and error handling

**Quick Example:**
```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    pdf_path = client.download_pdf_by_pmcid("PMC1234567")
    xml_content = client.download_xml_by_pmcid("PMC1234567")
```

**[Learn More →](fulltext/)**

---

### [XML Parsing](parsing/)
**Extract structured data from full-text XML documents**

- **Metadata extraction** - Title, authors, journal, dates, DOI, keywords
- **Table extraction** - Extract tables with headers, captions, and data
- **Reference extraction** - Bibliography with complete citations
- **Format conversion** - Convert to plaintext or Markdown
- **Section extraction** - Get structured body sections
- **Schema coverage validation** - Analyze XML element recognition
- **Flexible configuration** - Customize element patterns

**Quick Example:**
```python
from pyeuropepmc import FullTextXMLParser, ElementPatterns

parser = FullTextXMLParser(xml_content)

# Extract metadata
metadata = parser.extract_metadata()

# Extract tables
tables = parser.extract_tables()

# Convert to markdown
markdown = parser.to_markdown()

# Validate schema coverage
coverage = parser.validate_schema_coverage()
print(f"Coverage: {coverage['coverage_percentage']:.1f}%")
```

**[Learn More →](parsing/)**

---

### [Caching](caching/)
**Smart response caching for improved performance**

- Automatic response caching
- Configurable cache strategies
- TTL (time-to-live) support
- Cache invalidation
- Disk-based persistent cache
- Memory-efficient storage

**Quick Example:**
```python
from pyeuropepmc import SearchClient

# Caching is enabled by default
with SearchClient() as client:
    results = client.search("CRISPR")  # First call - hits API
    results = client.search("CRISPR")  # Second call - from cache
```

**[Learn More →](caching/)**

---

## 🎯 Feature Comparison

| Feature | SearchClient | FullTextClient | FullTextXMLParser | FTPDownloader |
|---------|-------------|---------------|-------------------|---------------|
| **Search Europe PMC** | ✅ | - | - | - |
| **Download PDFs** | - | ✅ | - | ✅ |
| **Download XML** | - | ✅ | - | - |
| **Parse XML** | - | - | ✅ | - |
| **Extract Metadata** | - | - | ✅ | - |
| **Extract Tables** | - | - | ✅ | - |
| **Bulk Downloads** | - | - | - | ✅ |
| **Caching** | ✅ | ✅ | - | - |
| **Progress Tracking** | - | ✅ | - | ✅ |

---

## 🚀 Common Workflows

### Workflow 1: Search → Download → Parse

```python
from pyeuropepmc import SearchClient, FullTextClient, FullTextXMLParser

# Step 1: Search for papers
with SearchClient() as search_client:
    results = search_client.search("machine learning in biology", pageSize=10)
    pmcids = [paper.get('pmcid') for paper in results['resultList']['result']
              if paper.get('pmcid')]

# Step 2: Download XML
with FullTextClient() as fulltext_client:
    for pmcid in pmcids:
        xml_path = fulltext_client.download_xml_by_pmcid(pmcid)

        # Step 3: Parse and extract
        with open(xml_path) as f:
            parser = FullTextXMLParser(f.read())
            metadata = parser.extract_metadata()
            tables = parser.extract_tables()

            print(f"Paper: {metadata['title']}")
            print(f"Tables: {len(tables)}")
```

### Workflow 2: Bulk Download → Batch Process

```python
from pyeuropepmc import FTPDownloader, FullTextXMLParser

# Bulk download PDFs
downloader = FTPDownloader()
results = downloader.bulk_download_and_extract(
    pmcids=["1234567", "2345678", "3456789"],
    output_dir="./papers"
)

# Batch process XML files
for xml_file in results['xml_files']:
    with open(xml_file) as f:
        parser = FullTextXMLParser(f.read())
        # Process each paper...
```

### Workflow 3: Advanced Search → Filter → Extract

```python
from pyeuropepmc import SearchClient, FullTextXMLParser

with SearchClient() as client:
    # Advanced search with filters
    results = client.search(
        query="cancer AND (therapy OR treatment)",
        sort="CITED desc",
        pageSize=100,
        resultType="core"
    )

    # Filter for high-impact papers
    high_impact = [
        paper for paper in results['resultList']['result']
        if paper.get('citedByCount', 0) > 50 and paper.get('pmcid')
    ]

    # Extract detailed information
    for paper in high_impact:
        xml_content = client.get_fulltext_xml(paper['pmcid'])
        parser = FullTextXMLParser(xml_content)
        # Analyze...
```

---

## 📊 Feature Matrix

### Search Features

| Capability | Supported | Notes |
|-----------|-----------|-------|
| Keyword search | ✅ | Full-text search across all fields |
| Boolean operators | ✅ | AND, OR, NOT |
| Field-specific | ✅ | Search specific fields (author, title, etc.) |
| Date filtering | ✅ | Publication date ranges |
| Citation sorting | ✅ | Sort by citation count |
| Pagination | ✅ | Handle large result sets |
| Multiple formats | ✅ | JSON, XML, Dublin Core |

### Full-Text Features

| Capability | Supported | Notes |
|-----------|-----------|-------|
| PDF download | ✅ | Open access articles only |
| XML download | ✅ | JATS/NLM XML format |
| HTML content | ✅ | HTML representation |
| Bulk FTP | ✅ | Efficient for large datasets |
| Progress tracking | ✅ | Real-time progress callbacks |
| Auto-retry | ✅ | Robust error handling |

### Parsing Features

| Capability | Supported | Notes |
|-----------|-----------|-------|
| Metadata extraction | ✅ | Title, authors, journal, dates, etc. |
| Table extraction | ✅ | Structured table data |
| Reference extraction | ✅ | Complete bibliography |
| Plaintext conversion | ✅ | Full article text |
| Markdown conversion | ✅ | Formatted markdown |
| Schema validation | ✅ | Coverage analysis |
| Custom patterns | ✅ | Flexible configuration |
| Multiple XML schemas | ✅ | JATS, NLM, custom |

---

## 🎓 Learning Resources

### By Feature

- **Search** → [Search Documentation](search/)
- **Full-Text** → [Full-Text Documentation](fulltext/)
- **Parsing** → [Parsing Documentation](parsing/)
- **Caching** → [Caching Documentation](caching/)

### By Use Case

- **Literature Review** → [Examples: Literature Review](../examples/use-cases.md#literature-review)
- **Data Mining** → [Examples: Text Mining](../examples/use-cases.md#text-mining)
- **Meta-Analysis** → [Examples: Meta-Analysis](../examples/use-cases.md#meta-analysis)

### By Skill Level

- **Beginner** → [Getting Started](../getting-started/)
- **Intermediate** → [Examples](../examples/)
- **Advanced** → [Advanced Guide](../advanced/)

---

## 💡 Best Practices

### Performance
- Use caching for repeated queries
- Implement bulk operations for large datasets
- Set appropriate page sizes (50-100 for most cases)
- Use FTP downloads for bulk PDF retrieval

### Error Handling
- Always use context managers (`with` statements)
- Implement retry logic for network operations
- Check for PMC ID availability before downloads
- Validate XML before parsing

### Rate Limiting
- Respect Europe PMC API rate limits
- Use delays between bulk operations
- Cache results to minimize API calls
- Consider FTP for large-scale downloads

---

## 🔄 What's Next?

Explore each feature in detail:

1. **[Search Features](search/)** - Master the search API
2. **[Full-Text Retrieval](fulltext/)** - Download article content
3. **[XML Parsing](parsing/)** - Extract structured data
4. **[Caching](caching/)** - Optimize performance

Or jump to:

- **[API Reference](../api/)** for complete API documentation
- **[Examples](../examples/)** for working code
- **[Advanced Guide](../advanced/)** for power user features
