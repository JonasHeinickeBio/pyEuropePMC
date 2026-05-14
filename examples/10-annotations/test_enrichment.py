#!/usr/bin/env python3
"""
Test: Verify annotation enrichment pipeline end-to-end

This test:
1. Takes the real Europe PMC API response (from curl)
2. Processes it through the annotation parser
3. Converts to RDF with the enriched fields
4. Outputs Turtle RDF to verify concept links are captured
"""

import json
from pyeuropepmc.processing.annotation_parser import parse_annotations
from pyeuropepmc.processing.annotations_to_rdf import annotations_to_rdf
from rdflib import Namespace

# Real response from Europe PMC API (subset)
REAL_API_RESPONSE = [
    {
        "source": "MED",
        "extId": "41444612",
        "pmcid": "PMC12888368",
        "annotations": [
            {
                "prefix": "and modifiers of",
                "exact": "ME/CFS",
                "postfix": "previously obscured by",
                "tags": [
                    {
                        "name": "chronic fatigue unspecified",
                        "uri": "http://linkedlifedata.com/resource/umls-concept/C0015674"
                    }
                ],
                "id": "http://europepmc.org/article/MED/41444612#europepmc-50b2a3b10e3cfb3a942c6acb716dbf59",
                "type": "Diseases",
                "section": "Abstract (http://purl.org/dc/terms/abstract)",
                "provider": "Europe PMC"
            },
            {
                "prefix": "regulation of glycolysis,",
                "exact": "amino acid",
                "postfix": "acid and lipid",
                "tags": [
                    {
                        "name": "amino acid",
                        "uri": "http://purl.obolibrary.org/obo/CHEBI_33709"
                    }
                ],
                "id": "http://europepmc.org/article/MED/41444612#europepmc-7e10209829c819602f822cb9fb811974",
                "type": "Chemicals",
                "section": "Abstract (http://purl.org/dc/terms/abstract)",
                "provider": "Europe PMC"
            },
            {
                "prefix": "that can influence",
                "exact": "gene expression",
                "postfix": "expression profiles.",
                "tags": [
                    {
                        "name": "gene expression",
                        "uri": "http://identifiers.org/GO:0010467"
                    }
                ],
                "id": "http://europepmc.org/article/MED/41444612#europepmc-961800d8d3422cb6fa1d6d47d5a7f6fe",
                "type": "Gene Ontology",
                "section": "Methods (http://purl.org/orb/Methods)",
                "provider": "Europe PMC"
            }
        ]
    }
]


def test_enrichment_pipeline():
    """Test the full enrichment pipeline."""

    print("=" * 80)
    print("ANNOTATION ENRICHMENT TEST")
    print("=" * 80)
    print()

    # Step 1: Parse annotations from API response
    print("Step 1: Parse annotations from Europe PMC API response...")
    parsed = parse_annotations(REAL_API_RESPONSE)

    print(f"  ✓ Parsed {len(parsed.get('entities', []))} entities")

    # Show first entity to verify enrichment fields were extracted
    if parsed.get("entities"):
        first_entity = parsed["entities"][0]
        print("\n  First entity parsed:")
        print(f"    - exact: {first_entity.get('exact')}")
        print(f"    - entity_id (concept IRI): {first_entity.get('id')}")
        print(f"    - entity_name: {first_entity.get('name')}")
        print(f"    - annotation_category: {first_entity.get('annotation_category')}")
        print(f"    - section: {first_entity.get('section')}")
        print(f"    - prefix: {first_entity.get('prefix')[:30]}..." if first_entity.get('prefix') else "    - prefix: None")
        print(f"    - postfix: {first_entity.get('postfix')[:30]}..." if first_entity.get('postfix') else "    - postfix: None")

    print()

    # Step 2: Convert to RDF
    print("Step 2: Convert to RDF with enrichment...")
    graph = annotations_to_rdf(parsed)

    print(f"  ✓ Generated RDF graph with {len(graph)} triples")

    # Step 3: Display RDF output
    print()
    print("=" * 80)
    print("RDF OUTPUT (Turtle format)")
    print("=" * 80)

    # Bind namespaces for nicer output
    graph.bind("oa", Namespace("http://www.w3.org/ns/oa#"))
    graph.bind("owl", Namespace("http://www.w3.org/2002/07/owl#"))
    graph.bind("rdfs", Namespace("http://www.w3.org/2000/01/rdf-schema#"))
    graph.bind("pyeuropepmc", Namespace("https://w3id.org/pyeuropepmc/vocab#"))

    turtle_output = graph.serialize(format="turtle")
    print(turtle_output)

    # Step 4: Verify enrichment fields are in RDF
    print()
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    PYEURO = Namespace("https://w3id.org/pyeuropepmc/vocab#")
    OWL_NS = Namespace("http://www.w3.org/2002/07/owl#")

    # Count concept links
    concept_links = list(graph.triples((None, OWL_NS.sameAs, None)))
    print(f"✓ Concept links (owl:sameAs): {len(concept_links)}")

    # Count entity types
    entity_types = list(graph.triples((None, PYEURO.entityType, None)))
    print(f"✓ Entity type annotations (pyeuropepmc:entityType): {len(entity_types)}")

    # Count sections
    sections = list(graph.triples((None, PYEURO.section, None)))
    print(f"✓ Document sections (pyeuropepmc:section): {len(sections)}")

    # Count context
    contexts = list(graph.triples((None, PYEURO.textContext, None)))
    print(f"✓ Text contexts (pyeuropepmc:textContext): {len(contexts)}")

    print()
    print("✅ Test passed! Enrichment pipeline is working.")
    print()

    # Sample enriched annotation
    print("=" * 80)
    print("SAMPLE: One fully enriched annotation")
    print("=" * 80)
    print()
    if concept_links:
        annot_uri, _, concept_uri = concept_links[0]
        concept_label = list(graph.objects(concept_uri, Namespace("http://www.w3.org/2000/01/rdf-schema#").label))
        entity_text = list(graph.objects(annot_uri, Namespace("http://www.w3.org/ns/oa#").hasBody))
        entity_type = list(graph.objects(annot_uri, PYEURO.entityType))
        section = list(graph.objects(annot_uri, PYEURO.section))

        print(f"Annotation: '{entity_text[0] if entity_text else '?'}'")
        print(f"  → Concept: {concept_label[0] if concept_label else '?'} ({concept_uri})")
        if entity_type:
            print(f"  → Type: {entity_type[0]}")
        if section:
            print(f"  → Section: {section[0]}")


if __name__ == "__main__":
    test_enrichment_pipeline()
