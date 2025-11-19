# Data Models Quick Start Guide

Get started with PyEuropePMC's structured data models and RDF conversion in 5 minutes.

## Installation

PyEuropePMC is already installed. The data models are included in the main package.

```bash
# If you need to install from scratch:
pip install pyeuropepmc

# Or with development dependencies:
pip install -e .[dev]
```

## Basic Usage (3 Steps)

### Step 1: Parse XML and Build Entities

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities

# Load your PMC XML file
with open("PMC1234567.xml", "r") as f:
    xml_content = f.read()

# Parse and build entities
parser = FullTextXMLParser(xml_content)
paper, authors, sections, tables, references = build_paper_entities(parser)

# Check what you got
print(f"Paper: {paper.title}")
print(f"Authors: {len(authors)}")
print(f"Sections: {len(sections)}")
```

### Step 2: Validate and Normalize

```python
# Normalize (lowercase DOI, trim whitespace, etc.)
paper.normalize()
for author in authors:
    author.normalize()

# Validate (checks required fields)
paper.validate()
for author in authors:
    author.validate()

print("✓ All entities validated")
```

### Step 3: Export to RDF or JSON

```python
from pyeuropepmc.mappers import RDFMapper
from rdflib import Graph

# Option A: Export to JSON
paper_json = paper.to_dict()
print(paper_json)

# Option B: Export to RDF
mapper = RDFMapper()
g = Graph()

# Add entities to graph
paper.to_rdf(g, mapper=mapper)
for author in authors:
    author.to_rdf(g, mapper=mapper)

# Serialize to Turtle format
ttl = mapper.serialize_graph(g, format="turtle")
print(ttl)

# Or save to file
mapper.serialize_graph(g, format="turtle", destination="output.ttl")
```

## CLI Tool (One Command)

For batch processing, use the CLI tool:

```bash
# Convert XML to Turtle and JSON
python scripts/xml_to_rdf.py input.xml --ttl output.ttl --json output.json -v

# Convert multiple files
for file in *.xml; do
    python scripts/xml_to_rdf.py "$file" --ttl "${file%.xml}.ttl"
done
```

## Query RDF with SPARQL

```python
# After creating an RDF graph (see Step 3 above)

# Query for papers
query = """
PREFIX bibo: <http://purl.org/ontology/bibo/>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?paper ?title ?doi
WHERE {
    ?paper a bibo:AcademicArticle .
    ?paper dct:title ?title .
    OPTIONAL { ?paper bibo:doi ?doi }
}
"""

results = g.query(query)
for row in results:
    print(f"Paper: {row.title}")
    print(f"DOI: {row.doi}")
```

## Available Entities

### PaperEntity
Represents an academic article.

```python
from pyeuropepmc.models import PaperEntity

paper = PaperEntity(
    pmcid="PMC1234567",
    doi="10.1234/example.2024.001",
    title="Example Article",
    journal="Nature",
    keywords=["bioinformatics", "RDF"]
)
```

### AuthorEntity
Represents an author.

```python
from pyeuropepmc.models import AuthorEntity

author = AuthorEntity(
    full_name="Jane Doe",
    first_name="Jane",
    last_name="Doe",
    orcid="0000-0001-2345-6789"
)
```

### SectionEntity
Represents a document section.

```python
from pyeuropepmc.models import SectionEntity

section = SectionEntity(
    title="Introduction",
    content="This is the introduction text..."
)
```

### TableEntity
Represents a table.

```python
from pyeuropepmc.models import TableEntity

table = TableEntity(
    table_label="Table 1",
    caption="Sample data"
)
```

### ReferenceEntity
Represents a citation.

```python
from pyeuropepmc.models import ReferenceEntity

ref = ReferenceEntity(
    title="Referenced Article",
    source="Nature",
    year="2023",
    doi="10.1038/nature12345"
)
```

## Common Operations

### Normalize DOIs

```python
paper = PaperEntity(doi="HTTPS://DOI.ORG/10.1234/TEST")
paper.normalize()
print(paper.doi)  # Output: 10.1234/test
```

### Export to Multiple Formats

```python
from pyeuropepmc.mappers import RDFMapper

mapper = RDFMapper()
# ... build graph g ...

# Turtle
ttl = mapper.serialize_graph(g, format="turtle")

# JSON-LD
jsonld = mapper.serialize_graph(g, format="json-ld")

# RDF/XML
xml = mapper.serialize_graph(g, format="xml")
```

### Custom RDF Configuration

Edit `conf/rdf_map.yml` to customize field mappings:

```yaml
PaperEntity:
  rdf:type: ["bibo:AcademicArticle"]
  fields:
    title: dct:title
    doi: bibo:doi
  multi_value_fields:
    keywords: dct:subject
```

## Examples & Documentation

- **API Reference**: `docs/models.md`
- **Implementation Guide**: `docs/data_models_implementation_summary.md`
- **Demo Notebooks**:
  - `examples/data_models_demo.ipynb` - Basic usage
  - `examples/rdf_conversion_demo.ipynb` - RDF workflow

## Common Patterns

### Pattern 1: XML → JSON

```python
parser = FullTextXMLParser(xml_content)
paper, *_ = build_paper_entities(parser)
paper.normalize()

import json
with open("output.json", "w") as f:
    json.dump(paper.to_dict(), f, indent=2)
```

### Pattern 2: XML → RDF → GraphDB

```python
# Convert
parser = FullTextXMLParser(xml_content)
paper, authors, sections, *_ = build_paper_entities(parser)

mapper = RDFMapper()
g = Graph()
paper.to_rdf(g, mapper=mapper)
for author in authors:
    author.to_rdf(g, mapper=mapper)

# Save
mapper.serialize_graph(g, format="turtle", destination="paper.ttl")

# Load into GraphDB (using their API or CLI)
```

### Pattern 3: Batch Processing

```python
import glob

for xml_file in glob.glob("*.xml"):
    parser = FullTextXMLParser(open(xml_file).read())
    paper, *_ = build_paper_entities(parser)
    paper.normalize()

    # Export
    output = xml_file.replace(".xml", ".ttl")
    mapper.serialize_graph(g, format="turtle", destination=output)
```

## Troubleshooting

### Q: "RDF mapping config not found"
**A:** The mapper looks for `conf/rdf_map.yml` relative to the project root. If needed, specify the path:
```python
mapper = RDFMapper(config_path="/path/to/custom_map.yml")
```

### Q: Validation fails
**A:** Check required fields. For example, PaperEntity needs at least one of: `pmcid`, `doi`, or `title`.

### Q: How to add custom fields?
**A:** Subclass the entity:
```python
from pyeuropepmc.models import PaperEntity

class ExtendedPaperEntity(PaperEntity):
    custom_field: str = ""
```

## Next Steps

1. **Try the demo notebooks** in `examples/`
2. **Read the full documentation** in `docs/models.md`
3. **Customize RDF mappings** in `conf/rdf_map.yml`
4. **Validate with SHACL** using shapes in `shacl/pub.shacl.ttl`
5. **Load into a triple store** (GraphDB, Blazegraph, etc.)

## Support

- **Documentation**: `docs/models.md`
- **Examples**: `examples/` directory
- **Tests**: `tests/models/`, `tests/mappers/`, `tests/builders/`
- **Issues**: [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)

---

**Quick Reference Card**

```python
# Parse
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities
parser = FullTextXMLParser(xml_content)
paper, authors, sections, tables, refs = build_paper_entities(parser)

# Validate
paper.normalize()
paper.validate()

# Export to JSON
paper.to_dict()

# Export to RDF
from pyeuropepmc.mappers import RDFMapper
from rdflib import Graph
mapper = RDFMapper()
g = Graph()
paper.to_rdf(g, mapper=mapper)
ttl = mapper.serialize_graph(g, format="turtle")
```
