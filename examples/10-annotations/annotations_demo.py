"""
Europe PMC Annotations API Demo

This script demonstrates how to use the AnnotationsClient to retrieve and parse
text-mining annotations from Europe PMC.

The Annotations API provides access to entity annotations, sentences, and relationships
extracted from scientific literature through text mining.
"""

import pyeuropepmc

# Initialize the AnnotationsClient
print("=" * 70)
print("Europe PMC Annotations API Demo")
print("=" * 70)
print()

# Create client (with caching for better performance)
from pyeuropepmc.cache.cache import CacheConfig

cache_config = CacheConfig(enabled=True, ttl=3600)  # Cache for 1 hour
client = pyeuropepmc.AnnotationsClient(cache_config=cache_config)

print("✓ AnnotationsClient initialized with caching enabled")
print()

# Example 1: Get annotations for specific article IDs
print("Example 1: Retrieve annotations by article IDs")
print("-" * 70)

article_ids = ["PMC3359311", "PMC3359312"]
print(f"Fetching annotations for articles: {', '.join(article_ids)}")

try:
    annotations = client.get_annotations_by_article_ids(
        article_ids=article_ids,
        section="abstract",  # Only abstract annotations
        format="JSON-LD",
    )
    print(f"✓ Retrieved annotations successfully")
    print(f"  Total annotations: {annotations.get('totalCount', 0)}")
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    print()

# Example 2: Parse the annotations using AnnotationParser
print("Example 2: Parse annotations to extract entities")
print("-" * 70)

try:
    from pyeuropepmc.processing.annotation_parser import parse_annotations

    parsed = parse_annotations(annotations)

    print(f"✓ Annotations parsed successfully")
    print(f"  Entities found: {len(parsed['entities'])}")
    print(f"  Sentences found: {len(parsed['sentences'])}")
    print(f"  Relationships found: {len(parsed['relationships'])}")
    print()

    # Display first few entities
    if parsed["entities"]:
        print("  First 5 entities:")
        for i, entity in enumerate(parsed["entities"][:5], 1):
            print(f"    {i}. {entity['name']} ({entity['type']}) - {entity['exact']}")
        print()
except Exception as e:
    print(f"✗ Error: {e}")
    print()

# Example 3: Get annotations for a specific entity (e.g., a chemical)
print("Example 3: Retrieve annotations for a specific entity")
print("-" * 70)

entity_id = "CHEBI:16236"  # Ethanol
entity_type = "CHEBI"
print(f"Fetching annotations for entity: {entity_id} ({entity_type})")

try:
    entity_annotations = client.get_annotations_by_entity(
        entity_id=entity_id,
        entity_type=entity_type,
        section="all",
        page=1,
        page_size=10,
    )
    print(f"✓ Retrieved entity annotations successfully")
    print(f"  Total annotations: {entity_annotations.get('totalCount', 0)}")
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    print()

# Example 4: Get annotations by provider
print("Example 4: Retrieve annotations by provider")
print("-" * 70)

provider = "Europe PMC"
print(f"Fetching annotations from provider: {provider}")

try:
    provider_annotations = client.get_annotations_by_provider(
        provider=provider,
        article_ids=["PMC3359311"],
        section="abstract",
    )
    print(f"✓ Retrieved provider annotations successfully")
    print(f"  Total annotations: {provider_annotations.get('totalCount', 0)}")
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    print()

# Example 5: Extract specific types of annotations
print("Example 5: Extract entities, sentences, and relationships")
print("-" * 70)

try:
    from pyeuropepmc.processing.annotation_parser import (
        extract_entities,
        extract_sentences,
        extract_relationships,
    )

    # Assume we have annotations from previous examples
    if annotations.get("annotations"):
        annot_list = annotations["annotations"]

        entities = extract_entities(annot_list)
        sentences = extract_sentences(annot_list)
        relationships = extract_relationships(annot_list)

        print(f"✓ Extracted annotations by type:")
        print(f"  Entities: {len(entities)}")
        print(f"  Sentences: {len(sentences)}")
        print(f"  Relationships: {len(relationships)}")
        print()

        # Display entity types
        if entities:
            entity_types = {}
            for entity in entities:
                entity_type = entity.get("type", "Unknown")
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

            print("  Entity types distribution:")
            for etype, count in sorted(
                entity_types.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"    {etype}: {count}")
            print()
except Exception as e:
    print(f"✗ Error: {e}")
    print()

# Example 6: Cache management
print("Example 6: Cache management")
print("-" * 70)

try:
    stats = client.get_cache_stats()
    print(f"✓ Cache statistics:")
    print(f"  Hit rate: {stats.get('hit_rate', 0):.2%}")
    print(f"  Total hits: {stats.get('hits', 0)}")
    print(f"  Total misses: {stats.get('misses', 0)}")
    print()
except Exception as e:
    print(f"✗ Error: {e}")
    print()

# Close the client
client.close()
print("✓ Client closed successfully")
print()

print("=" * 70)
print("Demo completed!")
print("=" * 70)
print()
print("Key Features Demonstrated:")
print("  1. Retrieving annotations by article IDs")
print("  2. Parsing JSON-LD annotations")
print("  3. Extracting entities, sentences, and relationships")
print("  4. Filtering by entity types")
print("  5. Filtering by annotation provider")
print("  6. Cache management for performance")
print()
print("For more information, see:")
print("  - Europe PMC Annotations API: https://europepmc.org/AnnotationsApi")
print("  - W3C Open Annotation Model: https://www.w3.org/TR/annotation-model/")
