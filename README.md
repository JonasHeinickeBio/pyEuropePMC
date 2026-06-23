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
- � **Advanced Query Builder** - Fluent API for building complex search queries with type safety
- �📄 **Full-Text Retrieval** - Download PDFs, XML, and HTML content from open access articles
- 🔬 **XML Parsing & Conversion** - Parse full text XML and convert to plaintext, markdown, extract tables and metadata
- 🏷️ **Text-Mining Annotations** - Retrieve and parse entity annotations, sentences, and relationships (genes, diseases, chemicals)
- 📊 **Multiple Output Formats** - JSON, XML, Dublin Core (DC)
- 📦 **Bulk FTP Downloads** - Efficient bulk PDF downloads from Europe PMC FTP servers
- 🔄 **Smart Pagination** - Automatic handling of large result sets
- 🛡️ **Robust Error Handling** - Built-in retry logic and connection management
- 🧑‍💻 **Type Safety** - Extensive use of type annotations and validation
- ⚡ **Rate Limiting** - Respectful API usage with configurable delays
- 🧪 **Extensively Tested** - 200+ tests with 90%+ code coverage
- 📋 **Systematic Review Tracking** - PRISMA-compliant search logging and audit trails
- 📈 **Advanced Analytics** - Publication trends, citation analysis, quality metrics, and duplicate detection
- 📉 **Rich Visualizations** - Interactive plots and dashboards using matplotlib and seaborn
- 🔗 **External API Enrichment** - Enhance metadata with CrossRef, Unpaywall, Semantic Scholar, and OpenAlex

## 📁 Project Structure

The repository is organized as follows:
- `src/pyeuropepmc/` - Main package source code
- `tests/` - Unit and integration tests
- `docs/` - Documentation and guides
- `examples/` - Example scripts and usage demonstrations
- `benchmarks/` - Performance benchmarking scripts and results
- `data/` - Downloads, outputs, and generated data files
- `conf/` - Configuration files for RDF mapping and other settings

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


### Advanced Search with QueryBuilder

```python
from pyeuropepmc import QueryBuilder

# Build complex queries with fluent API
qb = QueryBuilder()
query = (qb
    .keyword("cancer", field="title")
    .and_()
    .keyword("immunotherapy")
    .and_()
    .date_range(start_year=2020, end_year=2023)
    .and_()
    .citation_count(min_count=10)
    .build())

print(f"Generated query: {query}")
# Output: (TITLE:cancer) AND immunotherapy AND (PUB_YEAR:[2020 TO 2023]) AND (CITED:[10 TO *])
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

### Text-Mining Annotations

Retrieve and parse entity annotations, sentences, and relationships from scientific literature:

```python
from pyeuropepmc import AnnotationsClient, parse_annotations

# Initialize annotations client
with AnnotationsClient() as client:
    # Get annotations for specific articles
    annotations = client.get_annotations_by_article_ids(
        article_ids=["PMC3359311"],
        section="abstract"  # or "fulltext", "all"
    )

    # Parse annotations to extract structured data
    parsed = parse_annotations(annotations)

    print(f"Found {len(parsed['entities'])} entities")
    print(f"Found {len(parsed['relationships'])} relationships")

    # Display entities by type
    for entity in parsed['entities'][:5]:
        print(f"{entity['name']} ({entity['type']})")

    # Search for specific entities (e.g., chemicals)
    entity_annotations = client.get_annotations_by_entity(
        entity_id="CHEBI:16236",  # Ethanol
        entity_type="CHEBI",
        page_size=20
    )

    # Filter by annotation provider
    provider_annotations = client.get_annotations_by_provider(
        provider="Europe PMC",
        annotation_type="Disease"
    )
```

**Supported Entity Types:**
- 🧬 Genes and proteins
- 🦠 Diseases and conditions
- 🧪 Chemicals and drugs (CHEBI)
- 🔬 Gene Ontology terms
- 🌱 Organisms and species
- 🔗 Entity relationships

See [examples/10-annotations](examples/10-annotations/) for detailed examples.

### Advanced Analytics and Visualization

Analyze search results with built-in analytics and create visualizations:

```python
from pyeuropepmc import (
    SearchClient,
    to_dataframe,
    citation_statistics,
    quality_metrics,
    remove_duplicates,
    plot_publication_years,
    create_summary_dashboard,
)

# Search and convert to DataFrame
with SearchClient() as client:
    response = client.search("machine learning", pageSize=100)
    papers = response.get("resultList", {}).get("result", [])

# Convert to pandas DataFrame for analysis
df = to_dataframe(papers)

# Remove duplicates
df = remove_duplicates(df, method="title", keep="most_cited")

# Get citation statistics
stats = citation_statistics(df)
print(f"Mean citations: {stats['mean_citations']:.2f}")
print(f"Highly cited (top 10%): {stats['citation_distribution']['90th_percentile']:.0f}")

# Assess quality metrics
metrics = quality_metrics(df)
print(f"Open access: {metrics['open_access_percentage']:.1f}%")
print(f"With PDF: {metrics['with_pdf_percentage']:.1f}%")

# Create visualizations
plot_publication_years(df, save_path="publications_by_year.png")
create_summary_dashboard(df, save_path="analysis_dashboard.png")
```

### External API Enrichment

Enhance paper metadata with data from CrossRef, Unpaywall, Semantic Scholar, and OpenAlex:

**Professional Semantic Scholar Integration** (v0.12.0)

PyEuropePMC now uses the `danielnsilva/semanticscholar` professional library for robust Semantic Scholar API integration:

**Usage with API Key:**

```python
from pyeuropepmc.enrichment.semantic_scholar import SemanticScholarClient

# With API key (recommended for higher rate limits)
client = SemanticScholarClient(api_key="your_api_key_here")

# Get enriched paper data
result = client.enrich(semantic_scholar_id="649def34f8be52c8b66281af98ae884c09aef38b")
print(f"Citations: {result['citation_count']}")  # 439
print(f"Influential: {result['influential_citation_count']}")

# Get recommendations
recommendations = client.get_recommendations_for_paper("649def34f8be52c8b66281af98ae884c09aef38b")
```

**Usage for Bulk Search:**

For search operations that may be rate-limited, use `bulk=True` for faster results:

```python
# Search with bulk retrieval (no relevance ranking, faster)
results = client.search_papers(query="machine learning cancer", bulk=True)

# Or with relevance ranking (default, may be rate-limited)
results = client.search_papers(query="machine learning cancer", bulk=False)
```

**Note:** Search operations may be rate-limited depending on API usage. For reliable results with specific papers, use `client.enrich()` with paper IDs (DOI, S2PaperId, etc.). The `search_papers()` method is best used with `bulk=True` for faster, non-ranked results, or with specific filters to reduce the result set.

**Benefits of Professional Library:**
- ✅ Typed response objects (`Paper`, `Author`, `Venue`)
- ✅ Automatic retries and rate limiting
- ✅ Full API coverage (Graph, Recommendations, Datasets)
- ✅ Async support for concurrent requests
- ✅ Built-in pagination handling
- ✅ Production-ready (461 stars on GitHub)

**Usage:** [examples/09-enrichment/semantic_scholar_demo.py](examples/09-enrichment/semantic_scholar_demo.py)

```python
from pyeuropepmc import PaperEnricher, EnrichmentConfig

# Configure enrichment with multiple APIs
config = EnrichmentConfig(
    enable_crossref=True,
    enable_semantic_scholar=True,
    enable_openalex=True,
    enable_unpaywall=True,
    unpaywall_email="your@email.com"  # Required for Unpaywall
)

# Enrich paper metadata
with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper(doi="10.1371/journal.pone.0308090")

    # Access merged data from all sources
    merged = result["merged"]
    print(f"Title: {merged['title']}")
    print(f"Citations: {merged['citation_count']}")
    print(f"Open Access: {merged['is_oa']}")

    # Access individual source data
    if "crossref" in result["sources"]:
        print(f"Funders: {result['crossref']['funders']}")

    if "semantic_scholar" in result["sources"]:
        print(f"Influential Citations: {result['semantic_scholar']['influential_citation_count']}")
```

**Features:**
- 🔄 Automatic data merging from multiple sources
- 📊 Citation metrics from multiple databases
- 🔓 Open access status and full-text URLs
- 💰 Funding information
- 🏷️ Topic classifications and fields of study
- ⚡ Optional caching for performance
- 📚 Professional Semantic Scholar client (typed responses, async support)

See [examples/09-enrichment](examples/09-enrichment/) for more details.

### Knowledge Graph Structure Options 🕸️

PyEuropePMC supports flexible knowledge graph structures for different use cases:

```python
from pyeuropepmc.mappers import RDFMapper

mapper = RDFMapper()

# Metadata-only KG (for citation networks and bibliometrics)
metadata_graphs = mapper.save_metadata_rdf(
    entities_data,
    output_dir="rdf_output"
)  # Papers + authors + institutions

# Content-only KG (for text analysis and document processing)
content_graphs = mapper.save_content_rdf(
    entities_data,
    output_dir="rdf_output"
)  # Papers + sections + references + tables

# Complete KG (for comprehensive analysis)
complete_graphs = mapper.save_complete_rdf(
    entities_data,
    output_dir="rdf_output"
)  # All entities and relationships

# Use configured default from conf/rdf_map.yml
graphs = mapper.save_rdf(entities_data, output_dir="rdf_output")
```

**Use Cases:**
- **📊 Citation Networks**: Use metadata-only KGs for bibliometric analysis
- **📝 Text Mining**: Use content-only KGs for NLP and information extraction
- **🔬 Full Analysis**: Use complete KGs for comprehensive research workflows

See [examples/kg_structure_demo.py](examples/kg_structure_demo.py) for a complete working example.

### Unified Processing Pipeline 🏗️

The new unified pipeline dramatically simplifies the complex workflow of XML parsing → enrichment → RDF conversion:

```python
from pyeuropepmc import PaperProcessingPipeline, PipelineConfig

# Simple configuration
config = PipelineConfig(
    enable_enrichment=True,      # Enable metadata enrichment
    enable_crossref=True,        # CrossRef API
    enable_semantic_scholar=True, # Semantic Scholar API
    enable_openalex=True,        # OpenAlex API
    enable_ror=True,             # ROR institution data
    crossref_email="your@email.com",  # Required for higher CrossRef rate limits
    output_format="turtle",      # RDF output format
    output_dir="output"          # Where to save RDF files
)

# Create unified pipeline
pipeline = PaperProcessingPipeline(config)

# Process single paper - replaces 8+ separate steps!
result = pipeline.process_paper(
    xml_content=xml_string,
    doi="10.1038/nature11476",
    save_rdf=True
)

print(f"Generated {result['triple_count']} RDF triples")
print(f"Output saved to: {result['output_file']}")

# Process multiple papers in batch
xml_contents = {
    "10.1038/nature11476": xml_content_1,
    "10.1038/nature11477": xml_content_2,
}

batch_results = pipeline.process_papers(xml_contents)
for doi, result in batch_results.items():
    print(f"{doi}: {result['triple_count']} triples")
```

**What it does automatically:**
- ✅ Parses XML and extracts entities (paper, authors, sections, tables, figures, references)
- ✅ Enriches metadata from external APIs (citations, fields of study, etc.)
- ✅ Converts everything to RDF with proper relationships
- ✅ Saves structured output files
- ✅ Handles errors gracefully

**Before vs After:**
```python
# OLD: Complex multi-step workflow (8+ steps)
parser = FullTextXMLParser()
parser.parse(xml_content)
paper, authors, sections, tables, figures, references = build_paper_entities(parser)
enricher = PaperEnricher(config)
enrichment_data = enricher.enrich_paper(doi)
rdf_mapper = RDFMapper()
paper.to_rdf(graph, related_entities=...)
rdf_mapper.serialize_graph(graph, format='turtle')

# NEW: Single pipeline call (3 steps)
config = PipelineConfig(...)
pipeline = PaperProcessingPipeline(config)
result = pipeline.process_paper(xml_content, doi=doi)
```

See [examples/pipeline_demo.py](examples/pipeline_demo.py) for a complete working example.

## 📚 Documentation

**📖 [Read the Full Documentation](https://jonasheinickebio.github.io/pyEuropePMC/)** ← Start Here!

Quick Links:
- 🚀 [Quick Start Guide](https://jonasheinickebio.github.io/pyEuropePMC/getting-started/quickstart.html) - Get started in 5 minutes
- � [Query Builder](https://jonasheinickebio.github.io/pyEuropePMC/features/query-builder-load-save-translate.html) - Advanced query building
- �📚 [API Reference](https://jonasheinickebio.github.io/pyEuropePMC/api/) - Complete API documentation
- 💡 [Examples](https://jonasheinickebio.github.io/pyEuropePMC/examples/) - Code examples and use cases
- ✨ [Features](https://jonasheinickebio.github.io/pyEuropePMC/features/) - Explore all features
- 📊 [XML Coverage Analysis](docs/xml_element_coverage_analysis.md) - Parser coverage and benchmark results

> **Note:** Enable GitHub Pages first! See [Setup Guide](.github/SETUP_GITHUB_PAGES.md) for instructions.

## 📊 Parser Quality Benchmark

The XML full-text parser is continuously evaluated against a curated benchmark of 55 open-access JATS articles from Europe PMC. Results demonstrate high-fidelity extraction across all quality dimensions:

| Metric | Mean | Min | Max | Std Dev |
|--------|------|-----|-----|---------|
| **Composite Score** | **0.9506** | 0.8607 | 0.9908 | 0.0250 |
| Metadata Accuracy | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Text Fidelity | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Element Coverage | 0.9925 | 0.9655 | 1.0000 | 0.0087 |
| Section Accuracy | 0.9339 | 0.7692 | 1.0000 | 0.0518 |
| Inline Recall | 0.8267 | 0.4286 | 0.9732 | 0.1140 |

**Parse speed:** 48.0 articles/s (median 0.021s per article)

### PLOS XML Support

The parser now handles PLOS articles that use bare `<p>` elements directly under `<body>` (without `<sec>` wrappers). This structure was previously ignored, causing near-zero scores on PLOS-only benchmarks.

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| **Composite Score** | **0.4734 (min)** | **0.9778 ± 0.0393** |
| Metadata Accuracy | 0.6000 ± 0.0000 | 1.0000 ± 0.0000 |
| Inline Recall | 0.0000 (min) | 1.0000 ± 0.0000 |
| Text Fidelity | 0.3026 (min) | 1.0000 ± 0.0000 |
| Section Accuracy | 0.5745 ± 0.1812 | 0.9272 ± 0.0870 |
| Element Coverage | 0.9617 ± 0.0118 | 0.9617 ± 0.0118 |

Key fixes:
- **Section parser**: extract text from bare `<p>` elements directly under `<body>`
- **Content blocks**: collect bare `<p>` paragraphs as a synthetic body section
- **Plaintext converter**: include bare `<p>` elements in body text output
- **Metadata matching**: empty-empty fields (e.g., no PMID/PMCID) count as matches
- **Section accuracy**: detect bare `<p>` sections for correct section path tracking

Run the benchmark yourself:

```bash
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 55
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --dataset plos1000
```

See the [Benchmarking Guide](docs/guides/benchmarking.md) for full methodology and profiling tools.

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](docs/development/contributing.md) for details.

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## 🌐 Links

- **📖 Documentation**: [GitHub Pages](https://jonasheinickebio.github.io/pyEuropePMC/) - Full documentation site
- **📦 PyPI Package**: [pyeuropepmc](https://pypi.org/project/pyeuropepmc/) - Install with pip
- **💻 GitHub Repository**: [pyEuropePMC](https://github.com/JonasHeinickeBio/pyEuropePMC) - Source code
- **🐛 Issue Tracker**: [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues) - Report bugs or request features
