# RML Mappings Guide

This guide explains how to use RML (RDF Mapping Language) mappings with PyEuropePMC for converting scientific literature data to RDF knowledge graphs.

## What is RML?

RML (RDF Mapping Language) is a W3C community standard for mapping heterogeneous data (CSV, XML, JSON, databases) to RDF. It extends R2RML (the W3C standard for relational database to RDF mapping) to support various data formats.

**Key Benefits:**
- Standards-compliant (W3C community group)
- Widely adopted in semantic web community
- Works with multiple RML processors
- Supports complex mappings (joins, nested data, multiple sources)

## PyEuropePMC RML Integration

PyEuropePMC provides two approaches for RDF conversion:

### 1. Built-in RDFMapper
- Custom YAML-based configuration
- Direct Python API
- Lightweight and simple

### 2. RML with SDM-RDFizer (NEW)
- W3C RML standard compliance
- Powered by SDM-RDFizer (optimized for large datasets)
- Interoperable with other RML tools

## Installation

The RML integration requires the `rdfizer` package:

```bash
pip install rdfizer
```

Or install with PyEuropePMC:

```bash
pip install pyeuropepmc[rml]  # If added to setup
```

## Basic Usage

### Python API

```python
from pyeuropepmc.mappers import RMLRDFizer
from pyeuropepmc.models import PaperEntity

# Initialize RML RDFizer
rdfizer = RMLRDFizer()

# Create entities
paper = PaperEntity(
    pmcid="PMC1234567",
    doi="10.1234/example.2024.001",
    title="Example Paper",
    journal="Nature"
)

# Convert to RDF using RML mappings
g = rdfizer.entities_to_rdf([paper], entity_type="paper")

# Serialize
print(g.serialize(format="turtle"))
```

### CLI Tool

```bash
# Convert PMC XML to RDF using RML
python scripts/xml_to_rdf_rml.py input.xml --output output.ttl -v

# Save intermediate JSON
python scripts/xml_to_rdf_rml.py input.xml \
    --output output.ttl \
    --json entities.json

# Use custom mappings
python scripts/xml_to_rdf_rml.py input.xml \
    --output output.ttl \
    --mappings custom_rml.ttl \
    --config custom_rdfizer.ini
```

## Configuration Files

### RML Mappings (`conf/rml_mappings.ttl`)

Defines how JSON entities map to RDF triples:

```turtle
@prefix rml: <http://semweb.mmlab.be/ns/rml#> .
@prefix rr: <http://www.w3.org/ns/r2rml#> .
@prefix ql: <http://semweb.mmlab.be/ns/ql#> .
@prefix bibo: <http://purl.org/ontology/bibo/> .
@prefix dct: <http://purl.org/dc/terms/> .

<#PaperEntityMap>
    rml:logicalSource [
        rml:source "paper.json" ;
        rml:referenceFormulation ql:JSONPath ;
        rml:iterator "$"
    ] ;
    
    rr:subjectMap [
        rr:template "http://aid-pais.org/data/paper/{pmcid}" ;
        rr:class bibo:AcademicArticle
    ] ;
    
    rr:predicateObjectMap [
        rr:predicate dct:title ;
        rr:objectMap [ rml:reference "title" ]
    ] ;
    
    # Multi-value fields
    rr:predicateObjectMap [
        rr:predicate dct:subject ;
        rr:objectMap [ rml:reference "keywords[*]" ]
    ] .
```

### RDFizer Config (`conf/rdfizer_config.ini`)

Configures the SDM-RDFizer execution:

```ini
[default]
main_directory: .
mapping: conf/rml_mappings.ttl
output_folder: output
output_format: nt
number_of_datasets: 1
large_file: false
ordered: false
all_in_one_file: yes
name: pyeuropepmc_rdf
enrichment: yes
```

## Complete Example

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.mappers import RMLRDFizer

# 1. Parse XML
with open("PMC1234567.xml") as f:
    xml_content = f.read()

parser = FullTextXMLParser(xml_content)

# 2. Build entities
paper, authors, sections, tables, refs = build_paper_entities(parser)

# 3. Normalize
paper.normalize()
for author in authors:
    author.normalize()

# 4. Convert to RDF using RML
rdfizer = RMLRDFizer()

# Create combined graph
from rdflib import Graph
g = Graph()

# Convert each entity type
g += rdfizer.entities_to_rdf([paper], entity_type="paper")
g += rdfizer.entities_to_rdf(authors, entity_type="author")
g += rdfizer.entities_to_rdf(sections, entity_type="section")

# 5. Export
g.serialize("output.ttl", format="turtle")
print(f"Generated {len(g)} RDF triples")
```

## Converting JSON Directly

You can also convert JSON data directly without entity objects:

```python
rdfizer = RMLRDFizer()

# JSON data from any source
json_data = {
    "pmcid": "PMC123",
    "title": "Test Paper",
    "doi": "10.1234/test",
    "journal": "Nature",
    "keywords": ["biology", "medicine"]
}

# Convert to RDF
g = rdfizer.convert_json_to_rdf(json_data, entity_type="paper")

# Query with SPARQL
query = """
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?title WHERE { ?s dct:title ?title }
"""
for row in g.query(query):
    print(row.title)
```

## Customizing RML Mappings

To add custom mappings:

1. **Edit `conf/rml_mappings.ttl`** or create a new file
2. **Add triples map** for your entity type:

```turtle
<#CustomEntityMap>
    rml:logicalSource [
        rml:source "custom.json" ;
        rml:referenceFormulation ql:JSONPath ;
        rml:iterator "$[*]"
    ] ;
    
    rr:subjectMap [
        rr:template "http://example.org/custom/{id}" ;
        rr:class <http://example.org/CustomEntity>
    ] ;
    
    rr:predicateObjectMap [
        rr:predicate <http://example.org/hasProperty> ;
        rr:objectMap [ rml:reference "property" ]
    ] .
```

3. **Update config** to point to your mappings:

```python
rdfizer = RMLRDFizer(
    mapping_path="conf/custom_rml.ttl",
    config_path="conf/custom_rdfizer.ini"
)
```

## Advanced Features

### Joins

RML supports joins across data sources:

```turtle
rr:predicateObjectMap [
    rr:predicate foaf:knows ;
    rr:objectMap [
        rr:parentTriplesMap <#AnotherMap> ;
        rr:joinCondition [
            rr:child "author_id" ;
            rr:parent "id"
        ]
    ]
] .
```

### Named Graphs

Organize triples in named graphs:

```turtle
rr:subjectMap [
    rr:template "http://example.org/paper/{id}" ;
    rr:class bibo:AcademicArticle ;
    rr:graph <http://example.org/graphs/papers>
] .
```

### Language Tags

Add language tags to literals:

```turtle
rr:objectMap [
    rml:reference "title" ;
    rr:language "en"
] .
```

## Performance Considerations

### Large Datasets

For large datasets, enable optimization in `rdfizer_config.ini`:

```ini
large_file: true
ordered: true
```

### Batch Processing

Process multiple files efficiently:

```python
import glob

rdfizer = RMLRDFizer()
g = Graph()

for xml_file in glob.glob("*.xml"):
    parser = FullTextXMLParser(open(xml_file).read())
    paper, *_ = build_paper_entities(parser)
    g += rdfizer.entities_to_rdf([paper], entity_type="paper")

g.serialize("combined_output.ttl", format="turtle")
```

## Comparison: RDFMapper vs RML

| Feature | RDFMapper | RML + RDFizer |
|---------|-----------|---------------|
| **Standard** | Custom YAML | W3C RML |
| **Configuration** | `rdf_map.yml` | `rml_mappings.ttl` |
| **Learning Curve** | Lower | Higher |
| **Flexibility** | Good | Excellent |
| **Interoperability** | PyEuropePMC only | All RML tools |
| **Performance** | Good | Excellent (optimized) |
| **Complex Mappings** | Limited | Full support |

**Recommendation:**
- Use **RDFMapper** for simple cases and quick prototyping
- Use **RML** for production, standards compliance, and complex mappings

## Troubleshooting

### Import Error

```
ImportError: No module named 'rdfizer'
```

**Solution:** Install rdfizer package:
```bash
pip install rdfizer
```

### Config Not Found

```
FileNotFoundError: RDF mapping config not found
```

**Solution:** Specify absolute path:
```python
rdfizer = RMLRDFizer(
    config_path="/absolute/path/to/rdfizer_config.ini",
    mapping_path="/absolute/path/to/rml_mappings.ttl"
)
```

### Empty Graph

If the output graph has 0 triples:
1. Check JSON file was created correctly
2. Verify RML mapping references correct JSON structure
3. Enable verbose logging in RDFizer config
4. Check RDFizer output folder for error logs

## Resources

- **RML Specification**: https://rml.io/specs/rml/
- **SDM-RDFizer**: https://github.com/SDM-TIB/SDM-RDFizer
- **RML Tutorials**: https://rml.io/tutorials/
- **R2RML (base spec)**: https://www.w3.org/TR/r2rml/

## Examples

See the `examples/` directory for:
- `rdf_conversion_demo.ipynb` - Notebook with RDF conversion examples
- Additional RML mapping examples

## Support

For issues with:
- **RML mappings in PyEuropePMC**: Open issue on GitHub
- **SDM-RDFizer**: See https://github.com/SDM-TIB/SDM-RDFizer
- **RML standard**: See https://rml.io/
