# Full Text XML Parser

The `FullTextXMLParser` provides comprehensive functionality for parsing and extracting information from Europe PMC full text XML files.

## Features

- **Metadata Extraction**: Extract article metadata including title, authors, journal information, DOI, publication dates, keywords, and abstract
- **Format Conversion**: Convert XML to plaintext or Markdown format for easy reading and processing
- **Table Extraction**: Extract all tables with headers, captions, and data
- **Reference Extraction**: Extract bibliography with complete citation information
- **Section Extraction**: Get structured body sections with titles and content
- **Robust Error Handling**: Proper error handling with informative error messages
- **Parser Extensions**: 10 extension modules for content blocks, MathML, peer review, JATS4R validation, and more

## Installation

The parser is included in the pyeuropepmc package:

```bash
pip install pyeuropepmc
```

## Quick Start

### Basic Usage

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

# Download XML from Europe PMC
with FullTextClient() as client:
    xml_path = client.download_xml_by_pmcid("PMC3258128")

# Read and parse the XML
with open(xml_path, 'r') as f:
    xml_content = f.read()

parser = FullTextXMLParser(xml_content)

# Extract metadata
metadata = parser.extract_metadata()
print(f"Title: {metadata['title']}")
print(f"Authors: {', '.join(metadata['authors'])}")
```

### Parsing from String

```python
from pyeuropepmc import FullTextXMLParser

# Parse XML content directly
xml_content = """<?xml version="1.0"?>
<article>
  <!-- XML content -->
</article>
"""

parser = FullTextXMLParser(xml_content)
metadata = parser.extract_metadata()
```

## Core Functionality

### 1. Metadata Extraction

Extract comprehensive metadata from articles:

```python
metadata = parser.extract_metadata()

# Available fields:
# - pmcid: PMC identifier
# - doi: Digital Object Identifier
# - title: Article title
# - authors: List of author names
# - journal: Journal info dict with 'title', 'volume', 'issue' keys
# - pub_date: Publication date
# - pages: Page range
# - abstract: Article abstract
# - keywords: List of keywords

print(f"PMC ID: {metadata['pmcid']}")
print(f"DOI: {metadata['doi']}")
print(f"Title: {metadata['title']}")
print(f"Authors: {', '.join(metadata['authors'])}")
print(f"Journal: {metadata['journal']['title']} Vol. {metadata['journal'].get('volume', 'N/A')}")
print(f"Date: {metadata['pub_date']}")
```

### 2. Format Conversion

#### Convert to Plaintext

```python
# Convert entire article to plain text
plaintext = parser.to_plaintext()

# Save to file
with open('article.txt', 'w') as f:
    f.write(plaintext)

# Use for text analysis
word_count = len(plaintext.split())
print(f"Article contains {word_count} words")
```

#### Convert to Markdown

```python
# Convert to markdown format
markdown = parser.to_markdown()

# Save to file
with open('article.md', 'w') as f:
    f.write(markdown)

# Preview
print(markdown[:500])
```

### 3. Table Extraction

Extract structured table data:

```python
tables = parser.extract_tables()

for i, table in enumerate(tables, 1):
    print(f"\nTable {i}:")
    print(f"Label: {table['label']}")
    print(f"Caption: {table['caption']}")
    print(f"Headers: {table['headers']}")
    print(f"Dimensions: {len(table['headers'])} x {len(table['rows'])}")

    # Access table data
    for row in table['rows']:
        print(row)
```

Table structure:
```python
{
    'id': 'table-id',
    'label': 'Table 1',
    'caption': 'Table caption text',
    'headers': ['Column 1', 'Column 2', ...],
    'rows': [
        ['Cell 1', 'Cell 2', ...],
        ['Cell 3', 'Cell 4', ...],
    ]
}
```

### 4. Reference Extraction

Extract bibliography and citations:

```python
references = parser.extract_references()

for ref in references:
    print(f"[{ref['label']}] {ref['authors']}")
    print(f"    {ref['title']}")
    print(f"    {ref['source']} ({ref['year']}) {ref['volume']}: {ref['pages']}")
```

Reference structure:
```python
{
    'id': 'ref-id',
    'label': '1',
    'authors': 'Author names',
    'title': 'Article title',
    'source': 'Journal or book name',
    'year': '2021',
    'volume': '10',
    'pages': '100-110'
}
```

### 5. Section Extraction

Get structured body sections:

```python
sections = parser.get_full_text_sections()

for section in sections:
    print(f"\n{section['title']}")
    print("-" * 50)
    print(section['content'][:200])  # Preview first 200 chars

    # Get section word count
    word_count = len(section['content'].split())
    print(f"Word count: {word_count}")
```

## Advanced Usage

### Batch Processing

Process multiple XML files:

```python
from pathlib import Path
from pyeuropepmc import FullTextXMLParser

xml_files = Path('xml_downloads').glob('*.xml')

results = []
for xml_file in xml_files:
    with open(xml_file, 'r') as f:
        parser = FullTextXMLParser(f.read())

    metadata = parser.extract_metadata()
    tables = parser.extract_tables()

    results.append({
        'pmcid': metadata['pmcid'],
        'title': metadata['title'],
        'table_count': len(tables)
    })

# Analyze results
import pandas as pd
df = pd.DataFrame(results)
print(df)
```

### Text Mining Pipeline

Extract and analyze article content:

```python
from pyeuropepmc import FullTextXMLParser

# Parse article
parser = FullTextXMLParser(xml_content)

# Extract abstract for analysis
metadata = parser.extract_metadata()
abstract = metadata['abstract']

# Extract full text sections
sections = parser.get_full_text_sections()

# Find methods section
methods = next((s for s in sections if 'method' in s['title'].lower()), None)
if methods:
    print("Methods:")
    print(methods['content'])

# Extract all text for NLP processing
full_text = parser.to_plaintext()

# Your NLP pipeline here...
```

### Table Data Analysis

Extract and analyze table data:

```python
import pandas as pd
from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(xml_content)
tables = parser.extract_tables()

# Convert first table to pandas DataFrame
if tables:
    table = tables[0]
    df = pd.DataFrame(table['rows'], columns=table['headers'])

    # Analyze the data
    print(df.describe())
    print(df.head())
```

### Citation Analysis

Extract and analyze references:

```python
from pyeuropepmc import FullTextXMLParser
from collections import Counter

parser = FullTextXMLParser(xml_content)
references = parser.extract_references()

# Count references by year
years = [ref['year'] for ref in references if ref['year']]
year_counts = Counter(years)

# Find most cited journals
sources = [ref['source'] for ref in references if ref['source']]
source_counts = Counter(sources)

print("Top 5 cited journals:")
for source, count in source_counts.most_common(5):
    print(f"  {source}: {count}")
```

## Extension Modules

The parser includes 10 extension modules for advanced XML processing. Each module is importable from `pyeuropepmc.processing.extensions`.

### Structured Content Blocks (for RAG/LLM)

```python
from pyeuropepmc.processing.extensions import ContentBlockExtractor

extractor = ContentBlockExtractor(parser.root)
sections = extractor.extract_sections()
for section in sections:
    print(f"Section: {section.title}")
    for block in section.content:
        print(f"  [{block.type.value}] {block.text[:80]}")
```

Or use the built-in method on the parser:

```python
structured = parser.get_full_text_sections_structured()
for section in structured:
    for block in section.content:
        print(f"[{block.type.value}] {block.text[:80]}")
```

### JATS4R Compliance Validation

```python
from pyeuropepmc.processing.extensions import JATS4RValidator

report = JATS4RValidator(parser.root).validate()
print(f"Compliance: {report.compliance_score:.0%}")
for finding in report.findings:
    print(f"  [{finding.severity}] {finding.category}: {finding.message}")
```

### Peer Review Extraction

```python
from pyeuropepmc.processing.extensions import PeerReviewExtractor

review_sets = PeerReviewExtractor(parser.root).extract_all()
for round_set in review_sets:
    print(f"Revision round {round_set.revision_round}:")
    for review in round_set.reviews:
        print(f"  {review.review_type.value} by {review.author}")
```

### MathML → LaTeX Conversion

```python
from pyeuropepmc.processing.extensions import MathMLConverter

converter = MathMLConverter()
for formula_elem in parser.root.findall(".//disp-formula"):
    mathml = formula_elem.find(".//mml:math", converter.namespaces)
    if mathml is not None:
        latex = converter.convert_element(mathml)
        print(f"LaTeX: {latex}")
```

### Batch Processing Multiple Files

```python
from pyeuropepmc.processing.extensions import BatchProcessor

processor = BatchProcessor(rate_per_second=5, on_progress=lambda i,t: print(f"{i}/{t}"))
results = processor.process_files(["doc1.xml", "doc2.xml", "doc3.xml"])
print(f"Processed: {results.total_count} files in {results.total_time:.2f}s")
```

### Local Processing Convenience

```python
from pyeuropepmc.processing.extensions import LocalXMLProcessor

# Parse a file directly
parser = LocalXMLProcessor.parse_file("article.xml")

# Quick Markdown export
LocalXMLProcessor.write_markdown(xml_content, "article.md")

# Batch process a directory
results = LocalXMLProcessor.batch_process_files(["file1.xml", "file2.xml"])
```

### Reference Resolution via API

```python
from pyeuropepmc.processing.extensions import ReferenceResolver

resolver = ReferenceResolver()
refs = resolver.resolve_references(parser)
for ref in refs:
    if ref.resolved:
        print(f"[{ref.label}] {ref.title} — DOI: {ref.doi}")
```

### Asset Extraction

```python
from pyeuropepmc.processing.extensions import ImageFetcher

assets = ImageFetcher(parser.root).extract_assets()
for asset in assets:
    print(f"[{asset.type.value}] {asset.label}: {asset.uri}")
```

### lxml Backend (Optional)

```python
from pyeuropepmc.processing.extensions import LXMLParser, is_lxml_available

if is_lxml_available():
    lxml_root = LXMLParser().parse(xml_content)
    # Or enable directly on the parser
    LXMLParser.enable_for(parser)
```

See the **[XML Parser Extensions Reference](../../reference/xml-parser-extensions.md)** for complete documentation.

## Error Handling

The parser uses robust error handling:

```python
from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.exceptions import ParsingError

try:
    parser = FullTextXMLParser(xml_content)
    metadata = parser.extract_metadata()
except ParsingError as e:
    print(f"Parsing failed: {e}")
    # Handle the error appropriately
```

Common errors:
- Empty or invalid XML content
- Malformed XML structure
- Missing required elements
- Attempting operations before parsing

## Integration with FullTextClient

Combine with the FullTextClient for a complete workflow:

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser

# Download and parse in one workflow
with FullTextClient() as client:
    # Search for articles
    pmcids = ["PMC3258128", "PMC3359999"]

    for pmcid in pmcids:
        # Download XML
        xml_path = client.download_xml_by_pmcid(pmcid)

        # Parse XML
        with open(xml_path, 'r') as f:
            parser = FullTextXMLParser(f.read())

        # Extract and process
        metadata = parser.extract_metadata()
        plaintext = parser.to_plaintext()

        # Save processed output
        output_file = f"{pmcid}_processed.txt"
        with open(output_file, 'w') as f:
            f.write(f"Title: {metadata['title']}\n\n")
            f.write(plaintext)
```

## Performance Considerations

- **Memory**: The parser loads the entire XML into memory. For very large articles, consider streaming approaches.
- **Speed**: Parsing is generally fast (<1 second per article on modern hardware)
- **Caching**: Consider caching parsed results if processing the same articles multiple times

## Examples

See the `examples/` directory for complete working examples:
- `fulltext_parser_demo.py`: Comprehensive demo showing all features
- `fulltext_parser_simple_demo.py`: Simple demo using local XML files

## API Reference

### FullTextXMLParser

```python
class FullTextXMLParser(xml_content: str | None = None)
```

#### Methods

- `parse(xml_content: str) -> ET.Element`: Parse XML content
- `extract_metadata() -> dict`: Extract article metadata
- `to_plaintext() -> str`: Convert to plain text
- `to_markdown() -> str`: Convert to Markdown
- `extract_tables() -> list[dict]`: Extract all tables
- `extract_references() -> list[dict]`: Extract references
- `get_full_text_sections() -> list[dict]`: Extract body sections

## Troubleshooting

### XML Parsing Fails

**Problem**: ParsingError when parsing XML

**Solutions**:
- Verify XML is well-formed
- Check for encoding issues
- Ensure XML follows PMC DTD format

### Missing Metadata Fields

**Problem**: Some metadata fields are None

**Solutions**:
- Not all articles have all fields
- Check if the field exists in the source XML
- Handle None values in your code

### Empty Tables or References

**Problem**: extract_tables() or extract_references() returns empty list

**Solutions**:
- Not all articles have tables or references
- Check the article structure
- Verify XML contains the expected elements

## Contributing

Contributions are welcome! Please see the main repository README for contribution guidelines.

## License

This module is part of pyeuropepmc and is distributed under the MIT License.
