# XML Parsing Features

The **FullTextXMLParser** provides comprehensive capabilities for extracting structured data from Europe PMC full-text XML documents.

## Overview

- 📋 **Metadata extraction** - Title, authors, journal, dates, DOI, keywords
- 📊 **Table extraction** - Complete table data with headers and captions
- 📚 **Reference extraction** - Bibliography with full citation information
- 📝 **Format conversion** - Convert to plaintext or Markdown
- 🔍 **Section extraction** - Get structured body sections
- ✅ **Schema validation** - Analyze XML element recognition
- ⚙️ **Flexible configuration** - Customize element patterns
- 🎯 **Multi-schema support** - Handle JATS, NLM, and custom XML

## Quick Start

```python
from pyeuropepmc import FullTextXMLParser

# Load XML content
with open("article.xml") as f:
    xml_content = f.read()

parser = FullTextXMLParser(xml_content)

# Extract metadata
metadata = parser.extract_metadata()
print(f"Title: {metadata['title']}")
print(f"Authors: {metadata['authors']}")

# Extract tables
tables = parser.extract_tables()
print(f"Found {len(tables)} tables")

# Convert to markdown
markdown = parser.to_markdown()
```

## Metadata Extraction

Extract comprehensive article metadata:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)
metadata = parser.extract_metadata()

# Available metadata fields
title = metadata['title']                    # Article title
authors = metadata['authors']                # List of author dicts
journal = metadata['journal']                # Journal info dict (title, volume, issue)
pub_date = metadata['publication_date']      # Publication date
doi = metadata['doi']                        # Digital Object Identifier
pmid = metadata['pmid']                      # PubMed ID
pmcid = metadata['pmcid']                    # PMC ID
abstract = metadata['abstract']              # Abstract text
keywords = metadata['keywords']              # List of keywords
affiliations = metadata['affiliations']      # Author affiliations

# Author information
for author in authors:
    print(f"{author['given_names']} {author['surname']}")
    print(f"  Affiliation: {author.get('affiliation', 'N/A')}")
    print(f"  Email: {author.get('email', 'N/A')}")
```

### Metadata Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `title` | str | Article title |
| `authors` | list[dict] | Author information |
| `journal` | dict | Journal info with 'title', 'volume', 'issue' keys |
| `publication_date` | str | Publication date (ISO format) |
| `doi` | str | DOI identifier |
| `pmid` | str | PubMed ID |
| `pmcid` | str | PMC ID |
| `abstract` | str | Abstract text |
| `keywords` | list[str] | Article keywords |
| `affiliations` | list[str] | Author affiliations |
| `article_type` | str | Article type |
| `pages` | str | Page range |
| `copyright` | str | Copyright statement |
| `license` | str | License information |

## Table Extraction

Extract structured table data:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)
tables = parser.extract_tables()

for i, table in enumerate(tables):
    print(f"\nTable {i+1}")
    print(f"Caption: {table['caption']}")
    print(f"Label: {table['label']}")

    # Table headers
    headers = table['headers']
    print(f"Headers: {headers}")

    # Table data
    for row in table['data']:
        print(row)
```

### Table Structure

Each table is returned as a dictionary:

```python
{
    'label': 'Table 1',
    'caption': 'Patient demographics and baseline characteristics',
    'headers': ['Parameter', 'Group A', 'Group B', 'P-value'],
    'data': [
        ['Age (years)', '45.3 ± 12.1', '43.8 ± 11.5', '0.23'],
        ['Gender (M/F)', '12/8', '14/6', '0.51'],
        # ...
    ]
}
```

### Working with Tables

```python
# Convert table to pandas DataFrame
import pandas as pd

for table in tables:
    df = pd.DataFrame(table['data'], columns=table['headers'])
    print(f"\n{table['caption']}")
    print(df)

    # Save to CSV
    df.to_csv(f"table_{table['label']}.csv", index=False)
```

## Reference Extraction

Extract bibliography and citations:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)
references = parser.extract_references()

for i, ref in enumerate(references, 1):
    print(f"\n[{i}] {ref['title']}")
    print(f"    Authors: {ref['authors']}")
    print(f"    Journal: {ref['journal']}")
    print(f"    Year: {ref['year']}")
    print(f"    DOI: {ref.get('doi', 'N/A')}")
    print(f"    PMID: {ref.get('pmid', 'N/A')}")
```

### Reference Structure

```python
{
    'id': 'ref1',
    'title': 'Original research title',
    'authors': 'Smith J, Jones M, Brown L',
    'journal': 'Nature',
    'year': '2020',
    'volume': '123',
    'pages': '45-52',
    'doi': '10.1038/...',
    'pmid': '12345678'
}
```

## Format Conversion

### Convert to Plaintext

Extract clean plaintext from XML:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)

# Get full plaintext
plaintext = parser.to_plaintext()

# Save to file
with open("article.txt", "w", encoding="utf-8") as f:
    f.write(plaintext)
```

### Convert to Markdown

Generate formatted Markdown:

```python
parser = FullTextXMLParser(xml_content)

# Generate markdown
markdown = parser.to_markdown()

# Save to file
with open("article.md", "w", encoding="utf-8") as f:
    f.write(markdown)
```

**Markdown includes:**
- Article title as H1
- Authors and affiliations
- Abstract section
- Body sections with proper headings
- Tables in markdown table format
- References section
- Figures with captions

### Example Markdown Output

```markdown
# Machine Learning in Genomics: A Review

**Authors:** John Smith¹, Jane Doe², Mary Johnson¹

¹ Department of Computer Science, Stanford University
² Department of Biology, MIT

## Abstract

Machine learning has revolutionized genomics research...

## Introduction

The application of computational methods to biological data...

### Background

Recent advances in sequencing technology...

## Methods

### Data Collection

We collected genomic data from...

| Sample ID | Tissue Type | Read Count |
|-----------|-------------|------------|
| S001      | Brain       | 1,234,567  |
| S002      | Liver       | 987,654    |

## References

1. Smith et al. (2020). "Previous work." *Nature*, 123:45-52.
```

## Section Extraction

Extract specific sections from the article:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)

# Extract introduction
intro = parser.extract_section('introduction')

# Extract methods
methods = parser.extract_section('methods')

# Extract all sections
sections = parser.extract_all_sections()

for section in sections:
    print(f"\n{section['title']}")
    print(f"{section['content'][:200]}...")  # First 200 chars
```

## Schema Coverage Validation

Analyze how well the parser recognizes XML elements:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)

# Validate schema coverage
coverage = parser.validate_schema_coverage()

print(f"Overall coverage: {coverage['coverage_percentage']:.1f}%")
print(f"Recognized elements: {coverage['recognized_count']}")
print(f"Unrecognized elements: {coverage['unrecognized_count']}")

# See unrecognized elements
if coverage['unrecognized_elements']:
    print("\nUnrecognized elements:")
    for elem, count in coverage['unrecognized_elements'].items():
        print(f"  {elem}: {count} occurrences")
```

### Coverage Report Structure

```python
{
    'coverage_percentage': 85.5,
    'recognized_count': 342,
    'unrecognized_count': 58,
    'total_elements': 400,
    'recognized_elements': {
        'article-title': 1,
        'contrib': 5,
        'p': 45,
        'table': 3,
        # ...
    },
    'unrecognized_elements': {
        'custom-meta': 12,
        'inline-formula': 8,
        # ...
    }
}
```

## Custom Element Patterns

Customize XML element recognition for specialized XML schemas:

```python
from pyeuropepmc import FullTextXMLParser, ElementPatterns

# Create custom element patterns
custom_patterns = ElementPatterns(
    title_paths=['./front/article-meta/title-group/article-title'],
    author_paths=['./front/article-meta/contrib-group/contrib'],
    abstract_paths=['./front/article-meta/abstract'],
    # Add custom patterns for specialized elements
    custom_patterns={
        'supplementary': './back/app-group/app',
        'data_availability': './back/sec[@sec-type="data-availability"]'
    }
)

# Use custom patterns
parser = FullTextXMLParser(xml_content, element_patterns=custom_patterns)
metadata = parser.extract_metadata()
```

### Available Pattern Groups

```python
ElementPatterns(
    # Metadata patterns
    title_paths=[...],
    author_paths=[...],
    abstract_paths=[...],
    keywords_paths=[...],

    # Content patterns
    body_paths=[...],
    section_paths=[...],
    paragraph_paths=[...],

    # Table patterns
    table_paths=[...],
    table_caption_paths=[...],

    # Reference patterns
    ref_list_paths=[...],
    ref_paths=[...],

    # Custom patterns (dict)
    custom_patterns={}
)
```

## Advanced Examples

### Example 1: Extract All Data

Complete extraction workflow:

```python
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)

# Extract everything
data = {
    'metadata': parser.extract_metadata(),
    'tables': parser.extract_tables(),
    'references': parser.extract_references(),
    'plaintext': parser.to_plaintext(),
    'coverage': parser.validate_schema_coverage()
}

# Save to JSON
import json
with open("article_data.json", "w") as f:
    json.dump(data, f, indent=2)
```

### Example 2: Batch Processing

Process multiple XML files:

```python
import os
from pyeuropepmc import FullTextXMLParser

xml_dir = "./xml_files"
output_dir = "./processed"

for filename in os.listdir(xml_dir):
    if filename.endswith('.xml'):
        # Read XML
        with open(os.path.join(xml_dir, filename)) as f:
            xml_content = f.read()

        # Parse
        parser = FullTextXMLParser(xml_content)

        # Extract and save metadata
        metadata = parser.extract_metadata()
        pmcid = metadata.get('pmcid', filename.replace('.xml', ''))

        # Save markdown
        markdown = parser.to_markdown()
        with open(f"{output_dir}/{pmcid}.md", "w") as f:
            f.write(markdown)

        print(f"Processed: {pmcid}")
```

### Example 3: Table Export to Excel

Export all tables to Excel:

```python
from pyeuropepmc import FullTextXMLParser
import pandas as pd

parser = FullTextXMLParser(xml_content)
tables = parser.extract_tables()

# Create Excel writer
with pd.ExcelWriter('article_tables.xlsx') as writer:
    for i, table in enumerate(tables):
        # Convert to DataFrame
        df = pd.DataFrame(table['data'], columns=table['headers'])

        # Write to Excel sheet
        sheet_name = f"Table_{i+1}"
        df.to_excel(writer, sheet_name=sheet_name, index=False)

        # Add caption as note (requires openpyxl)
        worksheet = writer.sheets[sheet_name]
        worksheet.insert_rows(0)
        worksheet['A1'] = table['caption']
```

### Example 4: Citation Network Analysis

Build citation network from references:

```python
from pyeuropepmc import FullTextXMLParser
import networkx as nx

# Parse multiple papers
papers_data = []
for xml_file in xml_files:
    with open(xml_file) as f:
        parser = FullTextXMLParser(f.read())
        papers_data.append({
            'metadata': parser.extract_metadata(),
            'references': parser.extract_references()
        })

# Build citation graph
G = nx.DiGraph()

for paper in papers_data:
    pmid = paper['metadata']['pmid']
    G.add_node(pmid, title=paper['metadata']['title'])

    for ref in paper['references']:
        if ref.get('pmid'):
            G.add_edge(pmid, ref['pmid'])

# Analyze
print(f"Papers: {G.number_of_nodes()}")
print(f"Citations: {G.number_of_edges()}")

# Find most cited papers
in_degree = dict(G.in_degree())
most_cited = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:10]
```

### Example 5: Schema Coverage Analysis

Analyze parser coverage across multiple files:

```python
from pyeuropepmc import FullTextXMLParser
from collections import defaultdict

all_unrecognized = defaultdict(int)

for xml_file in xml_files:
    with open(xml_file) as f:
        parser = FullTextXMLParser(f.read())
        coverage = parser.validate_schema_coverage()

        # Aggregate unrecognized elements
        for elem, count in coverage['unrecognized_elements'].items():
            all_unrecognized[elem] += count

# Report most common unrecognized elements
print("Most common unrecognized elements across all files:")
sorted_unrecognized = sorted(all_unrecognized.items(), key=lambda x: x[1], reverse=True)
for elem, count in sorted_unrecognized[:20]:
    print(f"  {elem}: {count} occurrences")
```

## Performance Tips

### 1. Reuse Parser Instances

```python
# ❌ Creating new parser for each operation
xml_content = load_xml()
parser1 = FullTextXMLParser(xml_content)
metadata = parser1.extract_metadata()
parser2 = FullTextXMLParser(xml_content)
tables = parser2.extract_tables()

# ✅ Reuse parser instance
parser = FullTextXMLParser(xml_content)
metadata = parser.extract_metadata()
tables = parser.extract_tables()
references = parser.extract_references()
```

### 2. Extract Only Needed Data

```python
# ❌ Extract everything if you only need metadata
parser = FullTextXMLParser(xml_content)
metadata = parser.extract_metadata()
tables = parser.extract_tables()  # Unnecessary
references = parser.extract_references()  # Unnecessary

# ✅ Extract only what you need
parser = FullTextXMLParser(xml_content)
metadata = parser.extract_metadata()
```

### 3. Use Schema Validation Wisely

```python
# Schema validation is computationally expensive
# Only run when needed (e.g., during development)

if debug_mode:
    coverage = parser.validate_schema_coverage()
    if coverage['coverage_percentage'] < 80:
        print("Warning: Low coverage")
```

## Error Handling

```python
from pyeuropepmc import FullTextXMLParser
from xml.etree.ElementTree import ParseError

try:
    parser = FullTextXMLParser(xml_content)
    metadata = parser.extract_metadata()

    if not metadata.get('title'):
        print("Warning: No title found")

except ParseError as e:
    print(f"Invalid XML: {e}")

except Exception as e:
    print(f"Parser error: {e}")
```

## See Also

- **[API Reference: FullTextXMLParser](../../api/xml-parser.md)** - Complete API documentation
- **[API Reference: ElementPatterns](../../api/xml-parser.md#elementpatterns)** - Pattern configuration
- **[Full-Text Retrieval](../fulltext/)** - Download XML files to parse
- **[Examples: Parsing](../../examples/basic-examples.md#parsing)** - More code examples
- **[Advanced: Custom Patterns](../../advanced/custom-patterns.md)** - Advanced pattern customization

---

**Next Steps:**
- Learn [Custom Element Patterns](../../advanced/custom-patterns.md) for specialized XML
- Explore [Schema Coverage](./schema-coverage.md) validation in detail
- Read [Table Extraction](./table-extraction.md) advanced guide
- See [Metadata Extraction](./metadata-extraction.md) complete reference
