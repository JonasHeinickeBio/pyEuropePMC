# Full Text XML Parser Examples

**Level**: ⭐⭐⭐ Advanced
**Examples**: 6 files (4 notebooks + 2 scripts)
**Time**: 45-60 minutes

## Overview

The FullTextXMLParser is a powerful tool for extracting structured data from Europe PMC full text XML documents. Parse metadata, tables, references, convert to different formats, and customize extraction patterns.

## 📓 Examples

### 01-basic-fulltext.ipynb
**Introduction to full text parsing**

Learn the basics:
- Loading XML documents
- Extracting article metadata
- Converting to plaintext
- Converting to markdown
- Basic error handling

**What you'll build**: A simple full text converter

**Key topics**:
- XML parsing fundamentals
- Metadata extraction
- Format conversion
- Text extraction

### 02-parser-configuration.ipynb
**Advanced parser customization**

Master configuration:
- ElementPatterns configuration
- Schema detection
- Custom fallback patterns
- Multiple XML schema support (JATS, NLM)
- Flexible extraction strategies

**What you'll build**: A configurable parser for different XML formats

**Key topics**:
- Configuration system
- Fallback patterns
- Schema detection
- XML schema variations

### 03-modular-parsing.ipynb
**Component-based extraction**

Extract specific components:
- Tables with structure
- References and citations
- Authors and affiliations
- Figures and captions
- Sections and paragraphs

**What you'll build**: Modular extraction pipeline

**Key topics**:
- Selective extraction
- Structured data extraction
- Component isolation
- Data organization

### 04-advanced-features.ipynb
**Power user techniques**

Advanced extraction:
- Complex table structures
- Nested reference parsing
- Author affiliation mapping
- Cross-reference resolution
- Supplementary material handling

**What you'll build**: Complete article data extractor

**Key topics**:
- Complex structures
- Relationship mapping
- Advanced patterns
- Edge case handling

### demo.py & simple-demo.py
**Standalone scripts**

Quick reference scripts:
- `demo.py`: Full-featured demo with all capabilities
- `simple-demo.py`: Minimal example for quick start

## 🚀 Quick Start

### Basic Parsing
```python
from pyeuropepmc.fulltext_parser import FullTextXMLParser

# Load and parse XML
with open('article.xml', 'r') as f:
    xml_content = f.read()

parser = FullTextXMLParser(xml_content)

# Extract metadata
metadata = parser.extract_metadata()
print(f"Title: {metadata['title']}")
print(f"Authors: {', '.join(metadata['authors'])}")

# Convert to plaintext
plaintext = parser.to_plaintext()

# Convert to markdown
markdown = parser.to_markdown()
```

### With Configuration
```python
from pyeuropepmc.fulltext_parser import FullTextXMLParser, ElementPatterns

# Custom configuration
config = ElementPatterns(
    citation_types=["element-citation", "mixed-citation", "nlm-citation"]
)

parser = FullTextXMLParser(xml_content, config=config)
```

## 🎯 Key Features

### 1. Metadata Extraction
Extract comprehensive article metadata:
- Title, abstract, keywords
- Authors with affiliations
- Journal information
- Publication dates
- Identifiers (DOI, PMID, PMCID)

### 2. Table Extraction
Parse structured tables:
- Table headers and data
- Multi-level headers
- Cell spanning
- Table captions and labels
- Footnotes

### 3. Reference Parsing
Extract bibliography:
- Structured citations
- Author lists
- Journal details
- DOI and PubMed IDs
- Citation context

### 4. Format Conversion
Multiple output formats:
- **Plaintext**: Clean, readable text
- **Markdown**: Formatted with headers, lists, emphasis
- **JSON**: Structured data export
- **HTML**: (via markdown conversion)

### 5. Schema Detection
Automatic schema identification:
- JATS (Journal Article Tag Suite)
- NLM (National Library of Medicine) DTD
- Custom Europe PMC schemas
- Mixed schema handling

### 6. Flexible Configuration
Customize extraction patterns:
- Custom element patterns
- Fallback strategies
- Schema-specific handling
- Priority-based extraction

## 💡 Common Use Cases

### Extract All Tables
```python
parser = FullTextXMLParser(xml_content)
tables = parser.extract_tables()

for i, table in enumerate(tables):
    print(f"\n{table['label']}: {table['caption']}")
    print(f"Rows: {len(table['rows'])}")
    print(f"Headers: {table['headers']}")
```

### Get All References
```python
references = parser.extract_references()

for ref in references:
    authors = ', '.join(ref.get('authors', []))
    print(f"{authors}. {ref.get('title', 'N/A')}")
    print(f"  {ref.get('source', '')} {ref.get('year', '')}")
```

### Convert to Markdown File
```python
markdown = parser.to_markdown()

with open('article.md', 'w') as f:
    f.write(markdown)
```

### Detect Document Capabilities
```python
schema = parser.detect_schema()

print(f"Has tables: {schema.has_tables}")
print(f"Has figures: {schema.has_figures}")
print(f"Has supplementary: {schema.has_supplementary}")
print(f"Citation types: {schema.citation_types}")
```

## 📊 Supported XML Schemas

The parser handles multiple XML schemas through flexible configuration:

| Schema | Support | Notes |
|--------|---------|-------|
| JATS 1.x | ✅ Full | Journal Article Tag Suite (primary) |
| NLM 2.x/3.x | ✅ Full | National Library of Medicine DTD |
| PMC Custom | ✅ Full | Europe PMC extensions |
| Mixed | ✅ Partial | Multiple schemas in one document |

## 🔍 Advanced Patterns

### Custom Citation Extraction
```python
config = ElementPatterns(
    citation_types=["element-citation", "mixed-citation", "custom-citation"]
)

parser = FullTextXMLParser(xml_content, config=config)
references = parser.extract_references()
```

### Extract Author Affiliations
```python
metadata = parser.extract_metadata()
affiliations = parser.extract_affiliations()

for affiliation in affiliations:
    print(f"{affiliation.get('id')}: {affiliation.get('institution')}")
```

### Section-by-Section Parsing
```python
sections = parser.get_full_text_sections()

for section in sections:
    print(f"\n{section['title']}")
    print(section['content'][:200] + "...")
```

### Extract Keywords
```python
keywords = parser.extract_keywords()
print(f"Keywords: {', '.join(keywords)}")
```

## 📁 XML File Sources

Get full text XML files from:
1. **Europe PMC FTP**: Bulk download (see [05-ftp-downloader](../05-ftp-downloader/))
2. **Europe PMC API**: Single article download
3. **Local storage**: Your own XML collection

Example download:
```python
from pyeuropepmc.ftp_downloader import FTPDownloader

downloader = FTPDownloader()
xml_file = downloader.download_fulltext("PMC3258128", format="xml")
```

## 🆘 Troubleshooting

**XML parsing fails?**
- Verify XML is well-formed
- Check for namespace issues
- Try with defusedxml security settings

**Missing data in extraction?**
- Check schema detection: `parser.detect_schema()`
- Try custom ElementPatterns configuration
- Verify XML contains the expected elements

**Table extraction incomplete?**
- Tables may use non-standard structure
- Check `table_structure` in schema
- Customize table patterns in config

**References not found?**
- Try different citation types in config
- Check if document has `<ref-list>`
- Some articles may not have structured references

## 📈 Performance Tips

1. **Reuse parsers**: Create once for batch processing
2. **Stream large files**: Don't load entire corpus into memory
3. **Cache parsed results**: Store extracted data for reuse
4. **Selective extraction**: Only extract what you need

## 🔗 Resources

- [JATS Specification](https://jats.nlm.nih.gov/)
- [NLM DTD Documentation](https://dtd.nlm.nih.gov/)
- [Europe PMC XML Guide](https://europepmc.org/ftp/)
- [Parser API Reference](../../docs/api/fulltext-parser.md)

## 🎓 Learning Path

1. **Start**: `01-basic-fulltext.ipynb` - Learn core concepts
2. **Configure**: `02-parser-configuration.ipynb` - Master customization
3. **Extract**: `03-modular-parsing.ipynb` - Component extraction
4. **Advanced**: `04-advanced-features.ipynb` - Power techniques

## 🚀 Next Steps

- **Combine with FTP**: Download + parse workflows
- **Batch processing**: Process multiple articles
- **Data analysis**: Use extracted data for research
- **Export formats**: Convert to your preferred format
