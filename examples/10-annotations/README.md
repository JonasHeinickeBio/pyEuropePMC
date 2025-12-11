# Europe PMC Annotations API Examples

This directory contains examples demonstrating how to use PyEuropePMC's **AnnotationsClient** to retrieve and parse text-mining annotations from scientific literature, including conversion to RDF format.

## Overview

The Europe PMC Annotations API provides access to automatically extracted annotations including:
- **Entity annotations**: Mentions of genes, diseases, chemicals, organisms, and other biological entities
- **Sentence annotations**: Contextual text containing entity mentions
- **Relationship annotations**: Associations and interactions between entities (e.g., gene-disease relationships)

All annotations follow the [W3C Open Annotation Data Model](https://www.w3.org/TR/annotation-model/) and are provided in JSON-LD format. PyEuropePMC now supports converting these annotations to RDF graphs for integration with semantic web applications.

## Files

### 1. `annotations_demo.py`
A comprehensive Python script demonstrating:
- Initializing the AnnotationsClient with caching
- Retrieving annotations by article IDs
- Filtering by entity types and providers
- Parsing JSON-LD responses
- Extracting entities, sentences, and relationships
- Cache management

**Run the demo:**
```bash
python annotations_demo.py
```

### 2. `annotations_workflow.ipynb`
An interactive Jupyter notebook tutorial covering:
- Step-by-step annotation retrieval
- Data exploration and visualization
- Advanced use cases like gene-disease association mining
- Best practices for working with annotations

**Open the notebook:**
```bash
jupyter notebook annotations_workflow.ipynb
```

### 3. `annotations_to_rdf_demo.py` ✨ NEW
A demonstration of converting annotations to RDF graphs:
- Fetching and parsing annotations
- Converting to entity models
- Creating RDF graphs using W3C Open Annotation Data Model
- Serializing to Turtle and RDF/XML formats
- Querying RDF graphs

**Run the RDF demo:**
```bash
python annotations_to_rdf_demo.py
```

## Quick Start

### Basic Usage

```python
import pyeuropepmc

# Initialize the client
client = pyeuropepmc.AnnotationsClient()

# Get annotations for specific articles
annotations = client.get_annotations_by_article_ids(
    article_ids=["PMC3359311"],
    section="abstract"
)

# Parse the annotations
from pyeuropepmc.processing.annotation_parser import parse_annotations
parsed = parse_annotations(annotations)

print(f"Found {len(parsed['entities'])} entities")
print(f"Found {len(parsed['relationships'])} relationships")

# Close the client
client.close()
```

### Retrieve Annotations by Entity

```python
# Find all articles mentioning a specific chemical (ethanol)
entity_annotations = client.get_annotations_by_entity(
    entity_id="CHEBI:16236",
    entity_type="CHEBI",
    page_size=20
)
```

### Filter by Provider

```python
# Get annotations from a specific provider
provider_annotations = client.get_annotations_by_provider(
    provider="Europe PMC",
    article_ids=["PMC3359311"],
    annotation_type="Disease"
)
```

### Convert Annotations to RDF

```python
from pyeuropepmc import annotations_to_rdf, parse_annotations

# Fetch and parse annotations
raw = client.get_annotations_by_article_ids(["PMC3359311"])
parsed = parse_annotations(raw)

# Convert to RDF graph following W3C Open Annotation Data Model
rdf_graph = annotations_to_rdf(parsed)

# Serialize to Turtle format
turtle = rdf_graph.serialize(format="turtle")
print(turtle)

# Save to file
rdf_graph.serialize(destination="annotations.ttl", format="turtle")

# Also available in RDF/XML
rdf_graph.serialize(destination="annotations.rdf", format="xml")
```

## Key Features

### 1. Multiple Retrieval Methods
- By article IDs: Fetch all annotations for specific articles
- By entity: Find articles mentioning specific entities
- By provider: Filter annotations by source

### 2. Powerful Parsing
The `AnnotationParser` extracts structured data from JSON-LD:
```python
from pyeuropepmc.processing.annotation_parser import (
    parse_annotations,
    extract_entities,
    extract_sentences,
    extract_relationships
)

# Parse complete response
parsed = parse_annotations(response)

# Or extract specific types
entities = extract_entities(annotations)
relationships = extract_relationships(annotations)
```

### 3. RDF Conversion ✨ NEW
Convert annotations to RDF graphs using the W3C Open Annotation Data Model:
```python
from pyeuropepmc import annotations_to_rdf, annotations_to_entities

# Convert parsed annotations to entity models
entity_models = annotations_to_entities(parsed)

# Convert to RDF graph
rdf_graph = annotations_to_rdf(parsed)

# Serialize to various formats
turtle = rdf_graph.serialize(format="turtle")  # Turtle
rdfxml = rdf_graph.serialize(format="xml")     # RDF/XML
jsonld = rdf_graph.serialize(format="json-ld") # JSON-LD

# Query the RDF graph
from rdflib import Namespace
from rdflib.namespace import RDF

OA = Namespace("http://www.w3.org/ns/oa#")
for s, p, o in rdf_graph.triples((None, RDF.type, OA.Annotation)):
    print(f"Annotation: {s}")
```

**Benefits of RDF conversion:**
- Integration with semantic web applications
- SPARQL queries for complex annotation analysis
- Interoperability with other RDF datasets
- Standard W3C Open Annotation Data Model
- Reuses existing PyEuropePMC RDF infrastructure

### 4. Flexible Filtering
- Filter by section: `abstract`, `fulltext`, or `all`
- Filter by annotation type: `Gene`, `Disease`, `Chemical`, etc.
- Filter by provider: `Europe PMC`, `Pubtator`, etc.

### 4. Built-in Caching
Enable caching for improved performance:
```python
from pyeuropepmc.cache.cache import CacheConfig

cache_config = CacheConfig(enabled=True, ttl=3600)
client = pyeuropepmc.AnnotationsClient(cache_config=cache_config)
```

## Common Entity Types

The Annotations API provides the following entity types:
- **Gene**: Gene mentions (e.g., TP53, BRCA1)
- **Disease**: Disease and condition mentions (e.g., cancer, diabetes)
- **Chemical/CHEBI**: Chemical compounds (e.g., ethanol, aspirin)
- **Organism**: Species mentions (e.g., human, mouse)
- **GO**: Gene Ontology terms
- **Protein**: Protein mentions
- **CellType**: Cell type annotations

## Advanced Use Cases

### Gene-Disease Association Mining

```python
def find_gene_disease_associations(article_ids):
    """Extract gene-disease co-occurrences."""
    annotations = client.get_annotations_by_article_ids(article_ids)
    parsed = parse_annotations(annotations)
    
    genes = [e for e in parsed['entities'] if e['type'] == 'Gene']
    diseases = [e for e in parsed['entities'] if e['type'] == 'Disease']
    
    return genes, diseases
```

### Relationship Extraction

```python
# Extract all relationships from annotations
relationships = extract_relationships(annotations['annotations'])

for rel in relationships:
    print(f"{rel['subject']['name']} {rel['predicate']} {rel['object']['name']}")
```

## API Endpoints

The AnnotationsClient uses these Europe PMC API endpoints:
- `annotationsByArticleIds`: Retrieve annotations for specific articles
- `annotationsByEntity`: Find articles mentioning specific entities
- `annotationsByProvider`: Filter annotations by provider

## Best Practices

1. **Use caching**: Enable caching to reduce API calls and improve performance
2. **Paginate large results**: Use `page` and `page_size` parameters for entity searches
3. **Filter appropriately**: Use section and type filters to get relevant annotations
4. **Close clients**: Always close the client when done using `client.close()` or context managers
5. **Handle errors**: Wrap API calls in try-except blocks for robust error handling

## Resources

- [Europe PMC Annotations API Documentation](https://europepmc.org/AnnotationsApi)
- [W3C Open Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [PyEuropePMC GitHub](https://github.com/JonasHeinickeBio/pyEuropePMC)
- [PyEuropePMC Documentation](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/docs)

## Troubleshooting

### No annotations found
- Verify the article ID is correct (should start with "PMC")
- Check if the article has text-mining annotations available
- Try different sections (abstract vs fulltext)

### API rate limiting
- Enable caching to reduce API calls
- Increase `rate_limit_delay` when initializing the client

### Invalid entity ID
- Ensure entity IDs follow the correct format (e.g., "CHEBI:16236")
- Verify the entity type matches the ID prefix

## Support

For issues, questions, or feature requests, please visit:
https://github.com/JonasHeinickeBio/pyEuropePMC/issues
