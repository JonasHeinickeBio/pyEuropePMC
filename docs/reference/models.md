# Data Models & RDF Mapping

PyEuropePMC provides structured data models for representing scientific literature with built-in RDF serialization capabilities. This enables semantic integration with knowledge graphs and ontologies.

## Overview

The data models layer wraps the outputs of `FullTextXMLParser` in typed entities that can be:

- **Validated** - Ensures data quality and completeness
- **Normalized** - Standardizes formats (e.g., lowercase DOIs)
- **Exported to JSON** - For easy integration with web APIs
- **Exported to RDF** - Aligned to ontologies (BIBO, FOAF, DCT, PROV, etc.)
- **Validated with SHACL** - Ensures semantic correctness

## Architecture

### Entity Hierarchy

All entities inherit from `BaseEntity`:

```
BaseEntity
├── PaperEntity        (bibo:AcademicArticle)
├── AuthorEntity       (foaf:Person)
├── SectionEntity      (bibo:DocumentPart, nif:Context)
├── TableEntity        (bibo:Table)
├── TableRowEntity     (bibo:Row)
└── ReferenceEntity    (bibo:Document)
```

### Components

1. **Models** (`src/pyeuropepmc/models/`) - Typed entity classes
2. **Mappers** (`src/pyeuropepmc/mappers/`) - RDF serialization logic
3. **Builders** (`src/pyeuropepmc/builders/`) - Conversion from parser outputs
4. **Config** (`conf/rdf_map.yml`) - Ontology mapping definitions
5. **SHACL** (`shacl/pub.shacl.ttl`) - Validation shapes

## Entity Models

### BaseEntity

The base class for all entities provides common functionality:

```python
from pyeuropepmc.models import BaseEntity

entity = BaseEntity(
    id="unique-id",
    label="Human-readable label",
    source_uri="urn:pmc:1234567",
    confidence=0.95,
    types=["bibo:Document"]
)

# Mint URI
uri = entity.mint_uri("entity")  # http://example.org/data/entity/unique-id

# Convert to dictionary
data = entity.to_dict()

# Validate (override in subclasses)
entity.validate()

# Normalize (override in subclasses)
entity.normalize()

# Convert to RDF
from rdflib import Graph
from pyeuropepmc.mappers import RDFMapper

g = Graph()
mapper = RDFMapper()
subject = entity.to_rdf(g, mapper=mapper)
```

### PaperEntity

Represents an academic paper with BIBO alignment:

```python
from pyeuropepmc.models import PaperEntity

paper = PaperEntity(
    pmcid="PMC1234567",
    doi="10.1234/example.2024.001",
    title="Example Scientific Article",
    journal="Nature",
    volume="580",
    issue="7805",
    pages="123-127",
    pub_date="2024-01-15",
    keywords=["bioinformatics", "RDF"]
)

# Normalize DOI (lowercase, remove URL prefix)
paper.normalize()

# Validate (requires pmcid, doi, or title)
paper.validate()
```

**RDF Mapping:**
- `rdf:type` → `bibo:AcademicArticle`
- `pmcid` → `dct:identifier`
- `doi` → `bibo:doi`
- `title` → `dct:title`
- `journal` → `bibo:journal`
- `volume` → `bibo:volume`
- `issue` → `bibo:issue`
- `pages` → `bibo:pages`
- `pub_date` → `dct:issued`
- `keywords` → `dct:subject` (multi-value)

### AuthorEntity

Represents an author with FOAF alignment:

```python
from pyeuropepmc.models import AuthorEntity

author = AuthorEntity(
    full_name="Jane Doe",
    first_name="Jane",
    last_name="Doe",
    initials="J.D.",
    orcid="0000-0001-2345-6789",
    affiliation_text="University of Example"
)

author.validate()  # Requires full_name
author.normalize()  # Trims whitespace
```

**RDF Mapping:**
- `rdf:type` → `foaf:Person`
- `full_name` → `foaf:name`
- `first_name` → `foaf:givenName`
- `last_name` → `foaf:familyName`
- `initials` → `bibo:shortTitle`
- `orcid` → `bibo:identifier`
- `affiliation_text` → `dct:publisher`

### SectionEntity

Represents a document section with BIBO and NIF alignment:

```python
from pyeuropepmc.models import SectionEntity

section = SectionEntity(
    title="Introduction",
    content="This is the introduction text...",
    begin_index=0,    # Optional: NIF offset
    end_index=100     # Optional: NIF offset
)

section.validate()  # Requires content
```

**RDF Mapping:**
- `rdf:type` → `bibo:DocumentPart`, `nif:Context`
- `title` → `dct:title`
- `content` → `nif:isString`
- `begin_index` → `nif:beginIndex`
- `end_index` → `nif:endIndex`

### TableEntity

Represents a table:

```python
from pyeuropepmc.models import TableEntity

table = TableEntity(
    table_label="Table 1",
    caption="Sample data table"
)
```

**RDF Mapping:**
- `rdf:type` → `bibo:Table`
- `caption` → `dct:description`
- `table_label` → `rdfs:label`

### TableRowEntity

Represents a table row:

```python
from pyeuropepmc.models import TableRowEntity

row = TableRowEntity(
    headers=["Column 1", "Column 2"],
    cells=["Value 1", "Value 2"]
)
```

**RDF Mapping:**
- `rdf:type` → `bibo:Row`
- `headers` → `ex:hasHeader` (multi-value)
- `cells` → `ex:hasCell` (multi-value)

### ReferenceEntity

Represents a bibliographic reference:

```python
from pyeuropepmc.models import ReferenceEntity

ref = ReferenceEntity(
    title="Referenced Article",
    source="Nature",
    year="2023",
    volume="600",
    pages="123-127",
    doi="10.1038/nature12345",
    authors="Smith J, Doe J"
)
```

**RDF Mapping:**
- `rdf:type` → `bibo:Document`
- `title` → `dct:title`
- `source` → `dct:isPartOf`
- `year` → `dct:issued`
- `volume` → `bibo:volume`
- `pages` → `bibo:pages`
- `doi` → `bibo:doi`
- `authors` → `dct:creator`

## Builder Layer

The builder layer converts `FullTextXMLParser` outputs to entities:

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities

# Parse XML
parser = FullTextXMLParser(xml_content)

# Build entities
paper, authors, sections, tables, references = build_paper_entities(parser)

# Normalize all entities
paper.normalize()
for author in authors:
    author.normalize()
for section in sections:
    section.normalize()

# Validate all entities
paper.validate()
for author in authors:
    author.validate()
```

## RDF Mapping

### Configuration

RDF mappings are defined in `conf/rdf_map.yml`:

```yaml
_@prefix:
  dct: "http://purl.org/dc/terms/"
  bibo: "http://purl.org/ontology/bibo/"
  foaf: "http://xmlns.com/foaf/0.1/"
  # ...

PaperEntity:
  rdf:type: ["bibo:AcademicArticle"]
  fields:
    pmcid: dct:identifier
    doi: bibo:doi
    title: dct:title
  multi_value_fields:
    keywords: dct:subject
```

### RDFMapper

The `RDFMapper` class handles RDF serialization:

```python
from rdflib import Graph
from pyeuropepmc.mappers import RDFMapper

# Initialize mapper (loads conf/rdf_map.yml)
mapper = RDFMapper()

# Create graph
g = Graph()

# Add entity to graph
paper = PaperEntity(title="Example", doi="10.1234/test")
paper_uri = paper.to_rdf(g, mapper=mapper)

# Serialize to various formats
ttl = mapper.serialize_graph(g, format="turtle")
jsonld = mapper.serialize_graph(g, format="json-ld")
xml = mapper.serialize_graph(g, format="xml")

# Save to file
mapper.serialize_graph(g, format="turtle", destination="output.ttl")
```

### RML Mappings (W3C Standard)

PyEuropePMC also supports RML (RDF Mapping Language), a W3C community standard for mapping heterogeneous data to RDF. RML is particularly useful for:

- **Standards Compliance**: RML is a widely adopted standard
- **Tool Interoperability**: Works with various RML processors
- **Complex Mappings**: Supports joins, nested data, and multiple sources

#### Using RML with SDM-RDFizer

The `RMLRDFizer` wrapper integrates the SDM-RDFizer tool:

```python
from rdflib import Graph
from pyeuropepmc.mappers import RMLRDFizer
from pyeuropepmc.models import PaperEntity

# Initialize RML RDFizer
rdfizer = RMLRDFizer()

# Convert entities to RDF using RML mappings
paper = PaperEntity(pmcid="PMC123", title="Test Paper")
g = rdfizer.entities_to_rdf([paper], entity_type="paper")

# Serialize
ttl = g.serialize(format="turtle")
```

#### RML Configuration

RML mappings are defined in `conf/rml_mappings.ttl` using Turtle syntax:

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
        rr:template "http://example.org/data/paper/{pmcid}" ;
        rr:class bibo:AcademicArticle
    ] ;

    rr:predicateObjectMap [
        rr:predicate dct:title ;
        rr:objectMap [ rml:reference "title" ]
    ] .
```

The RDFizer configuration is in `conf/rdfizer_config.ini`.

#### Direct JSON to RDF

Convert JSON data directly without entity objects:

```python
rdfizer = RMLRDFizer()

json_data = {
    "pmcid": "PMC123",
    "title": "Test Paper",
    "doi": "10.1234/test"
}

g = rdfizer.convert_json_to_rdf(json_data, entity_type="paper")
```

## CLI Tools

### Standard RDF Mapper

Convert PMC XML files to RDF and JSON using the built-in RDFMapper:

```bash
# Convert to both Turtle and JSON
python scripts/xml_to_rdf.py input.xml --ttl output.ttl --json output.json -v

# Convert to Turtle only
python scripts/xml_to_rdf.py input.xml --ttl output.ttl

# Use custom RDF mapping config
python scripts/xml_to_rdf.py input.xml --ttl output.ttl --config custom_map.yml
```

### RML-based Conversion

Convert PMC XML files to RDF using RML mappings and SDM-RDFizer:

```bash
# Convert using RML mappings
python scripts/xml_to_rdf_rml.py input.xml --output output.ttl -v

# Save intermediate JSON entities
python scripts/xml_to_rdf_rml.py input.xml --output output.ttl --json entities.json

# Use custom RML mappings and config
python scripts/xml_to_rdf_rml.py input.xml --output output.ttl \
    --mappings custom_rml.ttl --config custom_rdfizer.ini
```

**Example Output (Turtle):**

```turtle
@prefix bibo: <http://purl.org/ontology/bibo/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

<http://example.org/data/paperentity/PMC1234567> a bibo:AcademicArticle ;
    dct:title "Example Article" ;
    dct:identifier "PMC1234567" ;
    bibo:doi "10.1234/example.2024.001" ;
    dct:issued "2024-01-15" .

<http://example.org/data/authorentity/uuid-123> a foaf:Person ;
    foaf:name "Jane Doe" ;
    foaf:givenName "Jane" ;
    foaf:familyName "Doe" .
```

## SHACL Validation

Validate RDF output using SHACL shapes in `shacl/pub.shacl.ttl`:

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix bibo: <http://purl.org/ontology/bibo/> .
@prefix dct: <http://purl.org/dc/terms/> .

bibo:AcademicArticleShape a sh:NodeShape ;
    sh:targetClass bibo:AcademicArticle ;
    sh:property [
        sh:path dct:title ;
        sh:minCount 0 ;
        sh:maxCount 1 ;
    ] .
```

Validate with a SHACL validator:

```python
from pyshacl import validate

# Load data and shapes
data_graph = Graph()
data_graph.parse("output.ttl", format="turtle")

shapes_graph = Graph()
shapes_graph.parse("shacl/pub.shacl.ttl", format="turtle")

# Validate
conforms, results_graph, results_text = validate(
    data_graph,
    shacl_graph=shapes_graph,
    inference="rdfs"
)

print(f"Conforms: {conforms}")
if not conforms:
    print(results_text)
```

## Example: Complete Pipeline

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.mappers import RDFMapper
from rdflib import Graph

# 1. Parse XML
with open("PMC1234567.xml", "r") as f:
    xml_content = f.read()

parser = FullTextXMLParser(xml_content)

# 2. Build entities
paper, authors, sections, tables, references = build_paper_entities(parser)

# 3. Normalize and validate
paper.normalize()
paper.validate()

for author in authors:
    author.normalize()
    author.validate()

# 4. Convert to RDF
mapper = RDFMapper()
g = Graph()

paper_uri = paper.to_rdf(g, mapper=mapper)

for author in authors:
    author.to_rdf(g, mapper=mapper)

for section in sections:
    section.to_rdf(g, mapper=mapper)

# 5. Export
ttl = mapper.serialize_graph(g, format="turtle")
print(ttl)

# Save to file
mapper.serialize_graph(g, format="turtle", destination="output.ttl")
```

## Ontology Alignment

The data models are aligned to established ontologies:

- **BIBO** (Bibliographic Ontology) - Academic articles, journals, volumes
- **FOAF** (Friend of a Friend) - People, names, affiliations
- **DCT** (Dublin Core Terms) - Titles, identifiers, dates
- **PROV** (Provenance) - Provenance tracking (wasDerivedFrom)
- **NIF** (NLP Interchange Format) - Text content, offsets
- **AID-PAIS** - Custom ontology for domain-specific concepts

## Next Steps

1. **Extend models** - Add more entity types (e.g., Organization, Funding)
2. **Enhanced provenance** - Track extraction confidence, methods
3. **NIF offsets** - Add sentence/token boundary detection
4. **Relation extraction** - Model subject-predicate-object statements
5. **GraphDB integration** - Load RDF into triple stores
6. **SPARQL queries** - Query the semantic knowledge graph

## References

- [BIBO Ontology](http://purl.org/ontology/bibo/)
- [FOAF Ontology](http://xmlns.com/foaf/spec/)
- [Dublin Core Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
- [PROV Ontology](https://www.w3.org/TR/prov-o/)
- [NIF Ontology](http://persistence.uni-leipzig.org/nlp2rdf/)
- [SHACL Specification](https://www.w3.org/TR/shacl/)
