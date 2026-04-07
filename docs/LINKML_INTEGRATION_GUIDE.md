# LinkML Schema Integration - Parser and RDF Mapper Improvements

## Overview

The PyEuropePMC parsers and RDF mappers have been enhanced to fully utilize the LinkML schema as the single source of truth. This integration provides:

- **Schema-driven validation**: Automatic validation against LinkML constraints
- **Type safety**: Runtime type checking and coercion
- **Consistent mappings**: Field-to-predicate mappings derived from schema
- **Better error handling**: Early detection of data quality issues

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   LinkML Schema (Single Source of Truth)        │
│              schemas/pyeuropepmc_schema.yaml (modular)          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌──────────────────┐        ┌──────────────────┐
│  Code Generation │        │  Runtime         │
│  (gen-pydantic)  │        │  Introspection   │
└────────┬─────────┘        └────────┬─────────┘
         │                           │
         ▼                           ▼
┌──────────────────┐        ┌──────────────────┐
│ Generated Models │        │ LinkML           │
│ (Pydantic)       │        │ Introspector     │
└────────┬─────────┘        └────────┬─────────┘
         │                           │
         └─────────────┬─────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌──────────────────┐        ┌──────────────────┐
│    Parsers       │        │   RDF Mapper     │
│  (XML → Data)    │        │  (Data → RDF)    │
└────────┬─────────┘        └────────┬─────────┘
         │                           │
         └─────────────┬─────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │   Validated      │
              │   RDF Output     │
              └──────────────────┘
```

## Key Improvements

### 1. Schema Validation Module

**Location**: `src/pyeuropepmc/builders/schema_validation.py`

Provides validation utilities that check data against LinkML schema constraints:

```python
from pyeuropepmc.builders.schema_validation import SchemaValidator

validator = SchemaValidator()

# Validate entity data
paper_data = {'title': 'Test', 'pmcid': 'PMC123', 'publication_year': 2024}
is_valid, errors = validator.validate_entity_data('PaperEntity', paper_data)

# Validate individual field
field_mapping = introspector.get_slot_mapping('orcid', 'AuthorEntity')
is_valid, errors = validator.validate_field_value('orcid', '0000-0001-2345-6789', field_mapping)

# Sanitize field value (coerce to correct type)
sanitized = validator.sanitize_field_value('publication_year', '2024', field_mapping)
```

**Features**:
- Pattern validation (DOI, ORCID, PMCID, etc.)
- Range validation (min/max values)
- Type coercion and sanitization
- Required field checking
- Multivalued field handling

### 2. Enhanced Builders

**Location**: `src/pyeuropepmc/builders/from_parser.py`

Builders now include optional schema validation:

```python
from pyeuropepmc.builders.from_parser import build_paper_entities

# Build entities with validation logging
paper, authors, sections, tables, figures, refs = build_paper_entities(parser)

# Validation warnings are logged automatically
# Example: "Schema validation warnings for AuthorEntity (author #1):"
#          "  - Field 'orcid' value 'invalid' does not match pattern..."
```

**Improvements**:
- Automatic validation during entity creation
- Detailed logging of validation issues
- Graceful handling of invalid data
- Type safety through Pydantic models

### 3. RDF Mapper with LinkML Integration

**Location**: `src/pyeuropepmc/mappers/rdf_mapper.py`

RDFMapper now uses LinkML introspection for all mappings:

```python
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models import PaperEntity
from rdflib import Graph

mapper = RDFMapper()

# Validate before mapping
paper = PaperEntity(title="Test", pmcid="PMC123")
is_valid, errors = mapper.validate_entity(paper)

if is_valid:
    g = Graph()
    uri = paper.to_rdf(g, mapper=mapper)
```

**Features**:
- LinkML schema as primary mapping source
- Automatic field-to-predicate resolution
- Entity validation before RDF conversion
- Configurable validation levels (strict/permissive)
- Namespace resolution from schema prefixes

### 4. LinkML Introspection

**Location**: `src/pyeuropepmc/mappers/linkml_introspection.py`

Runtime introspection of LinkML schema:

```python
from pyeuropepmc.mappers.linkml_introspection import LinkMLSchemaIntrospector

introspector = LinkMLSchemaIntrospector()

# Get complete class mapping
paper_mapping = introspector.get_class_mapping('PaperEntity')
print(paper_mapping['class_uri'])  # bibo:AcademicArticle
print(paper_mapping['fields'])      # {field_name: mapping_dict, ...}

# Get individual slot mapping
title_mapping = introspector.get_slot_mapping('title', 'PaperEntity')
print(title_mapping['predicate'])  # dcterms:title
print(title_mapping['datatype'])   # xsd:string
```

**Capabilities**:
- Extract class URIs and ontology alignments
- Get field-to-predicate mappings
- Retrieve validation constraints
- Handle relationships and cardinality
- Support custom annotations

## Configuration

### RDF Configuration

**Location**: `conf/rdf_config.yaml`

Updated to reference LinkML schema:

```yaml
# Schema reference - LinkML is the source of truth
schema:
  path: "schemas/pyeuropepmc_schema.yaml"
  version: "1.0.0"
  use_linkml_introspection: true

# Quality control settings
quality:
  validation:
    enabled: true
    strict_mode: false  # If true, fail on validation errors
    log_warnings: true
```

**Key Settings**:
- `schema.use_linkml_introspection`: Enable schema-based mapping (default: true)
- `quality.validation.enabled`: Enable entity validation (default: true)
- `quality.validation.strict_mode`: Fail on validation errors (default: false)

## Usage Examples

### Example 1: Parse XML with Validation

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders.from_parser import build_paper_entities

# Parse XML
parser = FullTextXMLParser(xml_content)

# Build entities (validation happens automatically)
paper, authors, sections, tables, figures, refs = build_paper_entities(parser)

# Entities are now LinkML-validated Pydantic models
print(f"Paper: {paper.title}")
print(f"Authors: {len(authors)}")
print(f"Validation: Passed")
```

### Example 2: Create RDF with Schema Validation

```python
from pyeuropepmc.models import PaperEntity, AuthorEntity
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from rdflib import Graph

# Create entities
paper = PaperEntity(
    title="Machine Learning in Healthcare",
    pmcid="PMC7654321",
    publication_year=2024
)

author = AuthorEntity(
    full_name="Dr. Jane Smith",
    orcid="0000-0001-2345-6789"
)

# Create RDF mapper with validation
mapper = RDFMapper()

# Validate entities
is_valid, errors = mapper.validate_entity(paper)
if not is_valid:
    print(f"Validation errors: {errors}")

# Create RDF graph
g = Graph()
paper_uri = paper.to_rdf(g, mapper=mapper)

# Export as Turtle
print(g.serialize(format="turtle"))
```

### Example 3: Custom Validation

```python
from pyeuropepmc.builders.schema_validation import SchemaValidator

validator = SchemaValidator()

# Prepare data
author_data = {
    'full_name': 'John Doe',
    'first_name': 'John',
    'last_name': 'Doe',
    'orcid': '0000-0001-2345-6789',
    'email': 'john.doe@university.edu'
}

# Validate before entity creation
is_valid, errors = validator.validate_entity_data('AuthorEntity', author_data)

if is_valid:
    # Safe to create entity
    author = AuthorEntity(**author_data)
else:
    # Handle validation errors
    print(f"Validation failed: {errors}")
```

## Validation Constraints

The LinkML schema defines various constraints that are enforced:

### Pattern Constraints

```yaml
# DOI pattern
doi:
  pattern: "^10\\.\\d{4,9}/[-._;()/:A-Z0-9]+$"

# ORCID pattern
orcid:
  pattern: "^\\d{4}-\\d{4}-\\d{4}-\\d{3}[\\dX]$"

# PMCID pattern
pmcid:
  pattern: "^PMC\\d+$"
```

### Range Constraints

```yaml
# Publication year
publication_year:
  range: integer
  minimum_value: 1000
  maximum_value: 9999

# Confidence scores
confidence:
  range: float
  minimum_value: 0.0
  maximum_value: 1.0
```

### Required Fields

```yaml
# AuthorEntity requires full_name
AuthorEntity:
  slots:
    - full_name
  slot_usage:
    full_name:
      required: true
```

## Error Handling

### Validation Errors

Validation errors are handled gracefully:

```python
# Non-strict mode (default): Log warnings, continue processing
is_valid, errors = mapper.validate_entity(paper)
# Logs: "Schema validation warnings for PaperEntity:"
#       "  - Field 'doi' value '10.123/invalid' does not match pattern..."

# Strict mode: Raise exceptions
mapper.strict_validation = True
is_valid, errors = mapper.validate_entity(paper)
if not is_valid:
    raise ValueError(f"Validation failed: {errors}")
```

### Parser Errors

Parsers handle invalid data gracefully:

```python
try:
    author = _build_author_entity(author_data, affiliations)
    authors.append(author)
except ValueError as e:
    # Skip invalid author data
    logger.warning(f"Skipping invalid author: {e}")
    continue
```

## Testing

Test the complete workflow:

```bash
cd /home/jhe24/AID-PAIS/pyEuropePMC_project

# Test schema validation
python -c "
from pyeuropepmc.builders.schema_validation import SchemaValidator
validator = SchemaValidator()
data = {'title': 'Test', 'pmcid': 'PMC123'}
is_valid, errors = validator.validate_entity_data('PaperEntity', data)
print(f'Validation: {is_valid}, Errors: {len(errors)}')
"

# Test RDF mapper
python -c "
from pyeuropepmc.models import PaperEntity
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from rdflib import Graph

mapper = RDFMapper()
paper = PaperEntity(title='Test', pmcid='PMC123')
is_valid, errors = mapper.validate_entity(paper)
print(f'RDF Mapper Validation: {is_valid}')

g = Graph()
uri = paper.to_rdf(g, mapper=mapper)
print(f'Generated URI: {uri}')
print(f'Triples: {len(g)}')
"
```

## Migration Guide

### For Developers

If you're working with the parsers or RDF mapper:

1. **Use generated models**: Import from `pyeuropepmc.models`, not from archive
2. **Enable validation**: Set `quality.validation.enabled: true` in config
3. **Check validation results**: Use `mapper.validate_entity()` before RDF conversion
4. **Handle errors gracefully**: Catch Pydantic validation errors

### For Users

No changes required! The API remains the same:

```python
# Same API as before
parser = FullTextXMLParser(xml_content)
paper, authors, sections, tables, figures, refs = build_paper_entities(parser)

# Now with automatic validation and LinkML schema compliance
```

## Benefits

1. **Single Source of Truth**: LinkML schema drives everything
2. **Type Safety**: Pydantic validates at runtime
3. **Consistency**: Field mappings always match schema
4. **Quality**: Early detection of data issues
5. **Maintainability**: Schema changes propagate automatically
6. **Interoperability**: Standards-compliant RDF output

## References

- [LinkML Documentation](https://linkml.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [RDFLib Documentation](https://rdflib.readthedocs.io/)
- [PyEuropePMC Schema README](../schemas/README.md)
