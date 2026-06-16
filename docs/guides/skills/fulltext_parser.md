# Full-Text Parser Skill

Parse full-text XML files and extract structured content (metadata, sections, tables, figures, references).

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
