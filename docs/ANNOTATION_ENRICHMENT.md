# Annotation Enrichment Implementation Summary

## Overview

The PyEuropePMC annotation enrichment implementation adds semantic context and external concept links to entity annotations extracted from Europe PMC. This enables deeper semantic analysis and integration with external knowledge bases.

## Enrichment Fields

Each entity annotation now captures these enrichment fields:

### 1. **Entity Context (Text Surr)
- `prefix` - Text appearing before the entity mention
- `postfix` - Text appearing after the entity mention
- **RDF Mapping**: `pyeuropepmc:textPrefix`, `pyeuropepmc:textPostfix`
- **Use Case**: Understand the semantic context of entity mentions

### 2. **Annotation Category**
- `annotation_category` - High-level category from Europe PMC (e.g., "Diseases", "Chemicals", "Gene Ontology")
- **RDF Mapping**: `pyeuropepmc:entityCategory`
- **Use Case**: Classify and filter annotations by type

### 3. **External Knowledge Base Links**
- `entity_id` - IRI linking to external concept (UMLS, ChEBI, GO, etc.)
- **RDF Mapping**: `owl:sameAs` → enables semantic integration with other KGs

### 4. **Standard Fields (Already Supported)**
- `exact` - Exact text of the entity mention
- `entity_name` - Human-readable entity name
- `entity_type` - Entity type from external source
- `section` - Document section (Abstract, Methods, etc.)
- `provider` - Annotation provider (Europe PMC)
- `article_id` - Reference to source article

## RDF Representation

Entity annotations are represented using the W3C Open Annotation Data Model with PyEuropePMC extensions:

```turtle
<http://example.org/annotations/1> a oa:Annotation,
        oa:SpecificResource,
        pyeuropepmc:EntityAnnotation ;
    rdfs:label "chronic fatigue unspecified" ;
    oa:hasBody "ME/CFS" ;
    owl:sameAs <http://linkedlifedata.com/resource/umls-concept/C0015674> ;
    dcterms:creator "Europe PMC" ;
    dcterms:isPartOf "Abstract (http://purl.org/dc/terms/abstract)" ;
    pyeuropepmc:entityCategory "Diseases" ;
    pyeuropepmc:entityId "http://linkedlifedata.com/resource/umls-concept/C0015674"^^xsd:anyURI ;
    pyeuropepmc:textPrefix "and modifiers of" ;
    pyeuropepmc:textPostfix "previously obscured by" ;
    pyeuropepmc:articleId "PMC12888368" ;
    oa:hasTarget "http://europepmc.org/article/MED/41444612"^^xsd:anyURI .
```

## Implementation Details

### 1. Parser Enhancement (`annotation_parser.py`)
The `extract_entities()` function now captures:
```python
entity = {
    "annotation_id": annotation.get("annotation_id"),
    "exact": annotation.get("exact"),  # Entity mention text
    "prefix": annotation.get("prefix"),  # NEW: Context before
    "postfix": annotation.get("postfix"),  # NEW: Context after
    "annotation_category": annotation.get("type"),  # NEW: Diseases, Chemicals, etc.
    "id": tag.get("uri"),  # Concept IRI
    "name": tag.get("name"),  # Entity name
    # ... other fields
}
```

### 2. Model Updates (`models/annotation.py`)
`EntityAnnotation` dataclass now includes:
```python
@dataclass
class EntityAnnotation(AnnotationEntity):
    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    annotation_category: str | None = None  # NEW
    confidence: float | None = None
```

### 3. RDF Configuration (`conf/rdf_map.yml`)
EntityAnnotation mapping includes enrichment fields:
```yaml
EntityAnnotation:
  rdf:type: ["oa:Annotation", "oa:SpecificResource", "pyeuropepmc:EntityAnnotation"]
  fields:
    exact: oa:hasBody
    entity_id: {predicate: "pyeuropepmc:entityId", datatype: "xsd:anyURI"}
    entity_name: rdfs:label
    annotation_category: pyeuropepmc:entityCategory  # NEW
    prefix: pyeuropepmc:textPrefix  # NEW
    postfix: pyeuropepmc:textPostfix  # NEW
    section: dcterms:isPartOf
    provider: dcterms:creator
    confidence: pyeuropepmc:confidence
    article_id: pyeuropepmc:articleId
    article_uri: oa:hasTarget
  alignments:
    entity_id:
      predicate: owl:sameAs  # Link to external KBs
      type: uri
```

### 4. RDF Mapper Enhancement (`mappers/rdf_mapper.py`)
Fixed `_get_entity_mappings()` to properly load entity class configs regardless of naming convention:
```python
def _get_entity_mappings(self, entity: Any) -> list[dict[str, Any]]:
    # Now checks entity's own class first (works with EntityAnnotation)
    # Then checks parent classes for inheritance
    # Removed "endswith('Entity')" restriction for more flexibility
```

### 5. Identifier Handler (`mappers/rdf_utils.py`)
Added `add_entity_annotation_identifiers()` to create owl:sameAs links:
```python
def add_entity_annotation_identifiers(
    g: Graph, subject: URIRef, entity: Any, resolve_predicate
) -> None:
    """Add owl:sameAs links to external concept IRIs."""
    if hasattr(entity, "entity_id") and entity.entity_id:
        g.add((subject, resolve_predicate("owl:sameAs"), URIRef(entity.entity_id)))
```

## Usage Example

```python
from pyeuropepmc import AnnotationsClient
from pyeuropepmc.processing.annotation_parser import parse_annotations
from pyeuropepmc.processing.annotations_to_rdf import annotations_to_rdf

# Fetch annotations
with AnnotationsClient() as client:
    raw_annotations = client.get_annotations_by_article_ids(["PMC3359311"])

# Parse with enrichment
parsed = parse_annotations(raw_annotations)
print(f"Entities: {len(parsed['entities'])}")

# Each entity now has enriched fields
for entity in parsed["entities"]:
    print(f"  Entity: {entity['exact']}")
    print(f"    Context: '{entity['prefix']}..{entity['postfix']}'")
    print(f"    Category: {entity['annotation_category']}")
    print(f"    Concept: {entity['id']}")

# Convert to RDF with semantic links
graph = annotations_to_rdf(parsed)
graph.serialize("annotations.ttl", format="turtle")
```

## Benefits

1. **Semantic Context**: Captures surrounding text for context-aware NLP tasks
2. **Classification**: Enables filtering/grouping by annotation category
3. **Knowledge Integration**: owl:sameAs links enable integration with UMLS, ChEBI, GO, etc.
4. **RDF-Ready**: Direct export to RDF/Turtle for knowledge graph construction
5. **Backward Compatible**: All enrichment fields are optional

## Testing

Comprehensive tests verify:
- Entity annotation parsing with enrichment fields
- RDF conversion with proper predicates
- External concept link generation (owl:sameAs)
- Compatibility with parent class configurations

See `examples/10-annotations/` for test scripts:
- `test_enrichment.py` - Full pipeline test
- `debug_field_mapping.py` - Field mapping verification
- `debug_mapper_config.py` - Configuration loading verification

## Next Steps

1. **Relationship Enhancement** (Optional): Add similar enrichment to relationship annotations
2. **Sentence Context** (Optional): Include full sentence context for entity pairs
3. **Confidence Filtering** (Optional): Add confidence thresholds for filtering
4. **Knowledge Graph Integration** (Optional): Automatic linking to external KGs
