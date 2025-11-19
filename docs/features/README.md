# PyEuropePMC Features

<div align="center">

**✨ Explore what PyEuropePMC can do** - Comprehensive feature overview and workflows

[🔍 Search](search/) • [📄 Full-Text](fulltext/) • [🔬 Parsing](parsing/) • [⬅️ Back to Docs](../README.md)

</div>

---

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

### [🔧 Query Builder](query-builder-load-save-translate.md)
**Advanced fluent API for building complex search queries with type safety**

- Type-safe field specifications (150+ searchable fields)
- Fluent method chaining with boolean logic (AND/OR/NOT)
- Citation count and date range filtering
- Query validation using CoLRev search-query package
- Cross-platform query translation (PubMed, Web of Science, etc.)
- Load/save queries in standard JSON format
- Query evaluation with recall/precision metrics
- Systematic review integration with PRISMA compliance

**Quick Example:**
```python
from pyeuropepmc import QueryBuilder

qb = QueryBuilder()
query = (qb
    .keyword("cancer", field="title")
    .and_()
    .citation_count(min_count=50)
    .and_()
    .date_range(start_year=2020)
    .build())
# Result: "(TITLE:cancer) AND (CITED:[50 TO *]) AND (PUB_YEAR:[2020 TO *])"
```

**[Learn More →](query-builder-load-save-translate.md)**

---

### [📋 Systematic Review Tracking](systematic-review-tracking.md)
**PRISMA/Cochrane-compliant search logging and audit trails**

- Complete systematic review workflow support
- Search log integration with `log_to_search()` method
- Raw results saving for reproducibility
- PRISMA flow diagram data generation
- Audit trails for research transparency

**Quick Example:**
```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search

log = start_search("Cancer Review", executed_by="Researcher")
qb = QueryBuilder().keyword("cancer").and_().field("open_access", True)
qb.log_to_search(log, filters={"open_access": True}, results_returned=100)
```

**[Learn More →](systematic-review-tracking.md)**

---

## 📊 Feature Comparison

| Feature | SearchClient | FullTextClient | FullTextXMLParser | FTPDownloader | QueryBuilder |
|---------|-------------|---------------|-------------------|---------------|--------------|
| **Search Europe PMC** | ✅ | - | - | - | ✅ |
| **Build Complex Queries** | - | - | - | - | ✅ |
| **Type-Safe Fields** | - | - | - | - | ✅ |
| **Query Validation** | - | - | - | - | ✅ |
| **Query Translation** | - | - | - | - | ✅ |
| **Download PDFs** | - | ✅ | - | ✅ | - |
| **Download XML** | - | ✅ | - | - | - |
| **Parse XML** | - | - | ✅ | - | - |
| **Extract Metadata** | - | - | ✅ | - | - |
| **Extract Tables** | - | - | ✅ | - | - |
| **Bulk Downloads** | - | - | - | ✅ | - |
| **Systematic Review Logging** | - | - | - | - | ✅ |
| **Caching** | ✅ | ✅ | - | - | - |
| **Progress Tracking** | - | ✅ | - | ✅ |

---

## 🚀 Common Workflows

### Workflow 1: Advanced Query → Search → Parse

```python
from pyeuropepmc import QueryBuilder, SearchClient, FullTextXMLParser

# Step 1: Build complex query with QueryBuilder
qb = QueryBuilder()
query = (qb
    .keyword("machine learning", field="title")
    .and_()
    .citation_count(min_count=25)
    .and_()
    .date_range(start_year=2020)
    .build())

# Step 2: Search with the query
with SearchClient() as client:
    results = client.search(query, pageSize=20, sort="CITED desc")

    # Step 3: Process results
    for paper in results['resultList']['result']:
        if paper.get('pmcid'):
            # Download and parse XML
            xml_content = client.get_fulltext_xml(paper['pmcid'])
            parser = FullTextXMLParser(xml_content)
            metadata = parser.extract_metadata()
            print(f"High-impact paper: {metadata['title']}")
```

### Workflow 2: Systematic Review with Audit Trail

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search

# Start systematic review
log = start_search("ML in Biology Review", executed_by="Researcher Name")

# Build comprehensive search strategy
qb = QueryBuilder()
comprehensive_query = (qb
    .keyword("machine learning")
    .and_()
    .keyword("biology")
    .and_()
    .field("open_access", True)
    .and_()
    .date_range(start_year=2019)
    .build())

# Execute and log search
with SearchClient() as client:
    results = client.search(comprehensive_query, pageSize=100)

    # Log for systematic review compliance
    qb.log_to_search(
        search_log=log,
        filters={"open_access": True, "date_range": "2019+"},
        results_returned=len(results['resultList']['result']),
        notes="Comprehensive ML in biology search"
    )

# Save review log
log.save("systematic_review_log.json")
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

- **[📚 API Reference](../api/)** for complete API documentation
- **[🎯 Examples](../examples/)** for working code
- **[⚙️ Advanced Guide](../advanced/)** for power user features

---

## 📚 Related Sections

| Section | Why Visit? |
|---------|------------|
| **[🚀 Getting Started](../getting-started/)** | Installation and basics |
| **[📚 API Reference](../api/)** | Complete method documentation |
| **[🎯 Examples](../examples/)** | Working code samples |
| **[⚙️ Advanced](../advanced/)** | Power user features |

---

<div align="center">

**[⬆ Back to Top](#pyeuropepmc-features)** • [⬅️ Back to Main Docs](../README.md)

</div>
