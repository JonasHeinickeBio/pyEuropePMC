"""
Annotations to RDF Example

This script demonstrates how to convert Europe PMC annotations
to RDF graphs using the W3C Open Annotation Data Model.
"""

import pyeuropepmc
from pyeuropepmc.cache.cache import CacheConfig

print("=" * 70)
print("Annotations to RDF Conversion Demo")
print("=" * 70)
print()

# Initialize the AnnotationsClient
cache_config = CacheConfig(enabled=True, ttl=3600)
client = pyeuropepmc.AnnotationsClient(cache_config=cache_config)

print("✓ AnnotationsClient initialized")
print()

# Example 1: Fetch and parse annotations
print("Example 1: Fetch annotations for an article")
print("-" * 70)

article_ids = ["PMC3359311"]
print(f"Fetching annotations for: {', '.join(article_ids)}")

try:
    # Fetch annotations from API
    annotations = client.get_annotations_by_article_ids(
        article_ids=article_ids,
        section="abstract",
        format="JSON-LD",
    )
    print(f"✓ Retrieved {annotations.get('totalCount', 0)} annotations")
    print()
except Exception as e:
    print(f"✗ Error fetching annotations: {e}")
    annotations = {"annotations": [], "totalCount": 0}

# Example 2: Parse annotations
print("Example 2: Parse JSON-LD annotations")
print("-" * 70)

from pyeuropepmc import parse_annotations

parsed = parse_annotations(annotations)
print(f"✓ Parsed annotations:")
print(f"  - Entities: {len(parsed['entities'])}")
print(f"  - Relationships: {len(parsed['relationships'])}")
print(f"  - Sentences: {len(parsed['sentences'])}")
print()

# Example 3: Convert to entity models
print("Example 3: Convert to entity models")
print("-" * 70)

from pyeuropepmc import annotations_to_entities

entities = annotations_to_entities(parsed)
print(f"✓ Converted to {len(entities)} entity models")
if entities:
    print("  First entity:")
    first = entities[0]
    print(f"    Type: {first.__class__.__name__}")
    if hasattr(first, "entity_name"):
        print(f"    Name: {first.entity_name}")
    print(f"    Text: {first.exact}")
print()

# Example 4: Convert to RDF graph
print("Example 4: Convert annotations to RDF")
print("-" * 70)

from pyeuropepmc import annotations_to_rdf

try:
    # Convert to RDF graph
    rdf_graph = annotations_to_rdf(parsed)
    
    print(f"✓ Created RDF graph with {len(rdf_graph)} triples")
    print()
    
    # Example 5: Serialize to different formats
    print("Example 5: Serialize RDF to different formats")
    print("-" * 70)
    
    # Turtle format (human-readable)
    turtle = rdf_graph.serialize(format="turtle")
    print("Turtle format (first 500 characters):")
    print(turtle[:500])
    print("...")
    print()
    
    # Save to file
    output_file = "/tmp/annotations.ttl"
    rdf_graph.serialize(destination=output_file, format="turtle")
    print(f"✓ Saved RDF graph to {output_file}")
    print()
    
    # Also save as RDF/XML
    xml_file = "/tmp/annotations.rdf"
    rdf_graph.serialize(destination=xml_file, format="xml")
    print(f"✓ Saved RDF graph to {xml_file}")
    print()
    
except Exception as e:
    print(f"✗ Error converting to RDF: {e}")
    import traceback
    traceback.print_exc()

# Example 6: Query the RDF graph
print("Example 6: Query the RDF graph")
print("-" * 70)

try:
    from rdflib import Namespace
    from rdflib.namespace import RDF
    
    # Define namespaces
    OA = Namespace("http://www.w3.org/ns/oa#")
    
    # Query for all annotations
    print("Querying for annotations:")
    for s, p, o in rdf_graph.triples((None, RDF.type, OA.Annotation)):
        print(f"  Found annotation: {s}")
    print()
    
except Exception as e:
    print(f"✗ Error querying RDF: {e}")

# Close the client
client.close()
print("✓ Client closed")
print()

print("=" * 70)
print("Demo completed!")
print("=" * 70)
print()
print("Summary:")
print("  1. Fetched annotations from Europe PMC Annotations API")
print("  2. Parsed JSON-LD annotations into structured data")
print("  3. Converted to entity models (EntityAnnotation, RelationshipAnnotation)")
print("  4. Converted to RDF graph using W3C Open Annotation Data Model")
print("  5. Serialized to Turtle and RDF/XML formats")
print("  6. Queried the RDF graph using SPARQL")
print()
print("Key Features:")
print("  - Reuses existing RDFMapper infrastructure")
print("  - Follows W3C Open Annotation Data Model")
print("  - Supports multiple RDF serialization formats")
print("  - Can be integrated with existing RDF workflows")
print()
print("For more information:")
print("  - W3C Open Annotation: https://www.w3.org/TR/annotation-model/")
print("  - RDFLib Documentation: https://rdflib.readthedocs.io/")
