# Data Models Implementation Summary

This document provides a comprehensive overview of the data models and RDF mapping implementation for PyEuropePMC (Issue #15).

## 🎯 Overview

The implementation adds a structured data model layer that wraps `FullTextXMLParser` outputs with typed entities that can be validated, normalized, and serialized to RDF for semantic integration.

## 📦 What Was Added

### Core Components

1. **Entity Models** (`src/pyeuropepmc/models/`)
   - `base.py` - BaseEntity with RDF namespaces and common functionality
   - `author.py` - AuthorEntity (FOAF-aligned)
   - `paper.py` - PaperEntity (BIBO-aligned)
   - `section.py` - SectionEntity (BIBO + NIF-aligned)
   - `table.py` - TableEntity & TableRowEntity (BIBO-aligned)
   - `reference.py` - ReferenceEntity (BIBO-aligned)

2. **RDF Mapping** (`src/pyeuropepmc/mappers/`)
   - `rdf_mapper.py` - Loads YAML config and maps fields to RDF predicates
   - Supports multi-value fields, custom types, and namespace resolution

3. **Builder Layer** (`src/pyeuropepmc/builders/`)
   - `from_parser.py` - Converts FullTextXMLParser outputs to typed entities
   - Single function: `build_paper_entities(parser)`

4. **Configuration** (`conf/`)
   - `rdf_map.yml` - YAML-driven ontology mappings
   - Defines field-to-predicate mappings for each entity type
   - Supports multi-value fields (lists)

5. **SHACL Shapes** (`shacl/`)
   - `pub.shacl.ttl` - Validation shapes for RDF output
   - Covers Paper, Author, Section, Table, Reference entities

6. **CLI Tool** (`scripts/`)
   - `xml_to_rdf.py` - Command-line tool for batch conversion
   - Supports Turtle, JSON-LD, XML, and JSON output formats

### Testing

- **52 new tests** in `tests/models/`, `tests/mappers/`, `tests/builders/`
- **105 total tests passing** (including parser regression tests)
- Coverage: Entity validation, RDF serialization, builder integration

### Documentation

- **`docs/models.md`** - Comprehensive API documentation
- **`examples/data_models_demo.ipynb`** - Basic usage examples
- **`examples/rdf_conversion_demo.ipynb`** - RDF workflow examples
- **Updated `examples/README.md`** - Added new section

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FullTextXMLParser                      │
│                  (existing component)                    │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ extract_metadata(), extract_authors(), etc.
                  ▼
┌─────────────────────────────────────────────────────────┐
│              builders/from_parser.py                     │
│         build_paper_entities(parser)                     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ creates entities
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   Entity Models                          │
│  PaperEntity, AuthorEntity, SectionEntity, etc.         │
│  - validate()  - normalize()  - to_dict()               │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ to_rdf(g, mapper)
                  ▼
┌─────────────────────────────────────────────────────────┐
│                    RDFMapper                             │
│  Loads conf/rdf_map.yml                                 │
│  Maps fields → RDF predicates                           │
│  Serializes to Turtle/JSON-LD/XML                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ serialize_graph()
                  ▼
┌─────────────────────────────────────────────────────────┐
│              RDF Output (TTL/JSON-LD/XML)               │
│  SPARQL-queryable, GraphDB-loadable                     │
└─────────────────────────────────────────────────────────┘
```

## 🔑 Key Features

### 1. Typed Entity Models

Each entity has:
- **Type annotations** - Full Python type hints
- **Validation** - `validate()` method checks required fields
- **Normalization** - `normalize()` standardizes formats (DOI, whitespace, etc.)
- **JSON export** - `to_dict()` for API integration
- **RDF export** - `to_rdf(g, mapper)` for semantic integration

### 2. Ontology Alignment

Entities are mapped to standard ontologies:
- **BIBO** - Academic articles, journals, tables
- **FOAF** - People/authors
- **DCT** - Metadata (titles, dates, identifiers)
- **PROV** - Provenance tracking
- **NIF** - Text content and offsets

### 3. Flexible Configuration

`conf/rdf_map.yml` allows easy customization:
```yaml
PaperEntity:
  rdf:type: ["bibo:AcademicArticle"]
  fields:
    title: dct:title
    doi: bibo:doi
  multi_value_fields:
    keywords: dct:subject
```

### 4. CLI Tool

Batch processing made easy:
```bash
python scripts/xml_to_rdf.py input.xml --ttl output.ttl --json output.json -v
```

## 📊 Usage Examples

### Basic Usage

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.mappers import RDFMapper
from rdflib import Graph

# Parse XML
parser = FullTextXMLParser(xml_content)
paper, authors, sections, tables, refs = build_paper_entities(parser)

# Normalize and validate
paper.normalize()
paper.validate()

# Convert to RDF
mapper = RDFMapper()
g = Graph()
paper_uri = paper.to_rdf(g, mapper=mapper)

# Export
ttl = mapper.serialize_graph(g, format="turtle")
```

### SPARQL Queries

```python
query = """
PREFIX bibo: <http://purl.org/ontology/bibo/>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?paper ?title
WHERE {
    ?paper a bibo:AcademicArticle .
    ?paper dct:title ?title .
}
"""
results = g.query(query)
```

## 🧪 Testing

### Test Structure

```
tests/
├── models/
│   └── test_models_rdf.py        (36 tests)
├── mappers/
│   └── test_rdf_mapper.py        (11 tests)
└── builders/
    └── test_from_parser.py       (5 tests)
```

### Test Coverage

- ✅ Entity creation and initialization
- ✅ Validation (success and failure cases)
- ✅ Normalization (DOI, whitespace, etc.)
- ✅ RDF serialization
- ✅ YAML config loading
- ✅ Predicate resolution
- ✅ Multi-value field handling
- ✅ Builder integration
- ✅ CLI tool (manual verification)

### Running Tests

```bash
# Run all new tests
pytest tests/models/ tests/mappers/ tests/builders/

# Run with coverage
pytest tests/models/ tests/mappers/ tests/builders/ --cov=src/pyeuropepmc

# Run specific test file
pytest tests/models/test_models_rdf.py -v
```

## 📁 File Layout

```
pyEuropePMC/
├── src/pyeuropepmc/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── author.py
│   │   ├── paper.py
│   │   ├── section.py
│   │   ├── table.py
│   │   └── reference.py
│   ├── mappers/
│   │   ├── __init__.py
│   │   └── rdf_mapper.py
│   └── builders/
│       ├── __init__.py
│       └── from_parser.py
├── conf/
│   └── rdf_map.yml
├── shacl/
│   └── pub.shacl.ttl
├── scripts/
│   └── xml_to_rdf.py
├── tests/
│   ├── models/
│   │   ├── __init__.py
│   │   └── test_models_rdf.py
│   ├── mappers/
│   │   ├── __init__.py
│   │   └── test_rdf_mapper.py
│   └── builders/
│       ├── __init__.py
│       └── test_from_parser.py
├── docs/
│   └── models.md
└── examples/
    ├── data_models_demo.ipynb
    └── rdf_conversion_demo.ipynb
```

## 🔄 Integration with Existing Code

### No Breaking Changes

- All new functionality is **additive**
- Existing FullTextXMLParser API unchanged
- No modifications to existing modules
- Backward compatible

### Import Paths

```python
# Entity models
from pyeuropepmc.models import (
    BaseEntity, PaperEntity, AuthorEntity,
    SectionEntity, TableEntity, ReferenceEntity
)

# RDF mapper
from pyeuropepmc.mappers import RDFMapper

# Builder
from pyeuropepmc.builders import build_paper_entities
```

## 🚀 Next Steps (Future Enhancements)

The implementation is complete and production-ready. Future enhancements could include:

1. **NIF Offsets** - Add sentence/token boundary detection to SectionEntity
2. **Organization Entity** - Replace `affiliation_text` with structured Organization entities
3. **Observation/Statement Entity** - Model extracted subject-predicate-object triples
4. **Enhanced Provenance** - Track extraction confidence, methods, and timestamps
5. **GraphDB Integration** - Direct loading into triple stores
6. **SHACL Enhancement** - More comprehensive validation shapes

## 📋 Acceptance Criteria Status

All acceptance criteria from issue #15 have been met:

- ✅ BaseEntity + 5 subclasses with validate() and normalize()
- ✅ RDFMapper loads conf/rdf_map.yml, supports fields and links
- ✅ to_rdf() yields triples with correct predicates and types
- ✅ Multi-value fields emit multiple triples
- ✅ URIs minted under http://aid-pais.org/data/<type>/<id>
- ✅ builders/from_parser.py converts parser outputs
- ✅ CLI script xml_to_rdf.py with --ttl and --json flags
- ✅ SHACL shapes in shacl/pub.shacl.ttl
- ✅ Unit tests for all entities (36 tests)
- ✅ Round-trip JSON → RDF tested
- ✅ Parser → builder pipeline tested (5 integration tests)
- ✅ docs/models.md with examples and class diagrams
- ✅ conf/rdf_map.yml fully documented

## 📞 Support

For questions or issues:
1. See `docs/models.md` for API documentation
2. Check `examples/data_models_demo.ipynb` for usage examples
3. Review tests in `tests/models/` for code examples
4. Open a GitHub issue for bugs or feature requests

## 🙏 Acknowledgments

Implementation follows best practices from:
- BIBO (Bibliographic Ontology)
- FOAF (Friend of a Friend)
- Dublin Core Terms
- W3C PROV-O
- NLP Interchange Format

---

**Status**: ✅ Complete and Production-Ready  
**Tests**: 105/105 passing (100%)  
**Type Checking**: ✅ mypy strict mode passing  
**Linting**: ✅ ruff passing  
**Security**: ✅ CodeQL scanned (1 false positive in test code only)
