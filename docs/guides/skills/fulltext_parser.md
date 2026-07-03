# Full-Text Parser Skill

Parse full-text XML files and extract structured content (metadata, sections, tables, figures, references).

## Core Parser

```python
from pyeuropepmc import FullTextXMLParser

# Load and parse XML
parser = FullTextXMLParser(xml_content)

# Extract metadata
metadata = parser.extract_metadata()
print(f"Title: {metadata['title']}")
print(f"Authors: {', '.join(metadata['authors'])}")

# Convert formats
plaintext = parser.to_plaintext()
markdown = parser.to_markdown()

# Extract specific elements
tables = parser.extract_tables()
figures = parser.extract_figures()
references = parser.extract_references()
```

Key tips:
- Supports PMC and publisher XML formats
- Use `ElementPatterns` config to customize parsing rules
- Extract sections with `parser.extract_sections()`
- Access table captions with `table['caption']`

## Extension Modules (10 modules)

```python
from pyeuropepmc.processing.extensions import (
    ContentBlockExtractor,     # Typed content blocks for RAG/LLM
    JATS4RValidator,           # JATS4R compliance validation
    MathMLConverter,           # MathML → LaTeX conversion
    PeerReviewExtractor,       # Peer review extraction
    BatchProcessor,            # Rate-limited batch processing
    ImageFetcher,              # Asset extraction
    ReferenceResolver,         # API-based reference enrichment
    LocalXMLProcessor,         # Local file convenience utilities
    LXMLParser,                # Optional lxml backend
)

# Structured content blocks
sections = ContentBlockExtractor(parser.root).extract_sections()

# JATS4R validation
report = JATS4RValidator(parser.root).validate()
print(f"Compliance: {report.compliance_score:.0%}")

# MathML to LaTeX
latex = MathMLConverter().convert_element(mathml_element)

# Peer review materials
reviews = PeerReviewExtractor(parser.root).extract_all()

# Batch processing
results = BatchProcessor().process(xml_strings)

# Local file convenience
parser = LocalXMLProcessor.parse_file("article.xml")
```

Key tips:
- All extensions are importable from `pyeuropepmc.processing.extensions`
- See **[XML Parser Extensions Reference](../../reference/xml-parser-extensions.md)** for full docs
