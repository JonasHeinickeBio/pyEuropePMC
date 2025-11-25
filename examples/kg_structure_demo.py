#!/usr/bin/env python3
"""
Knowledge Graph Structure Demo

This script demonstrates the different knowledge graph structures supported by PyEuropePMC:
- Complete KG: All entities (metadata + content)
- Metadata KG: Only bibliographic metadata (papers, authors, institutions)
- Content KG: Only document content (sections, references, tables, figures)
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.mappers import RDFMapper


def load_sample_xml():
    """Load a sample PMC XML file for demonstration."""
    # Try to find a test fixture
    fixture_paths = [
        "tests/fixtures/fulltext_downloads/PMC3359999.xml",
        "../tests/fixtures/fulltext_downloads/PMC3359999.xml",
        "PMC3258128.xml",  # From project root
    ]

    for path in fixture_paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    # Fallback: create a minimal XML for demo
    return """<?xml version="1.0"?>
<pmc-articleset>
<article>
    <front>
        <article-meta>
            <title-group><article-title>Test Article</article-title></title-group>
            <contrib-group>
                <contrib><name><surname>Doe</surname><given-names>John</given-names></name></contrib>
            </contrib-group>
            <abstract><p>This is a test abstract.</p></abstract>
        </article-meta>
    </front>
    <body>
        <sec><title>Introduction</title><p>Test content.</p></sec>
    </body>
    <back>
        <ref-list>
            <ref><citation>Test reference.</citation></ref>
        </ref-list>
    </back>
</article>
</pmc-articleset>"""


def main():
    print("PyEuropePMC Knowledge Graph Structure Demo")
    print("=" * 50)

    # Load and parse XML
    print("\n1. Loading and parsing XML...")
    xml_content = load_sample_xml()
    parser = FullTextXMLParser(xml_content)

    # Build entities
    paper, authors, sections, tables, figures, references = build_paper_entities(parser)

    print(f"   Paper: {paper.title}")
    print(f"   Authors: {len(authors)}")
    print(f"   Sections: {len(sections)}")
    print(f"   Tables: {len(tables)}")
    print(f"   Figures: {len(figures)}")
    print(f"   References: {len(references)}")

    # Prepare entities data
    entities_data = {
        paper.doi or paper.pmcid or "test_paper": {
            "entity": paper,
            "related_entities": {
                "authors": authors,
                "sections": sections,
                "tables": tables,
                "references": references,
            }
        }
    }

    # Initialize mapper
    mapper = RDFMapper()

    # Create output directory
    output_dir = "demo_kg_output"
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n2. Creating knowledge graphs in: {output_dir}/")

    # Create metadata-only KG
    print("\n   Creating Metadata-Only KG...")
    metadata_graphs = mapper.save_metadata_rdf(
        entities_data=entities_data,
        output_dir=output_dir,
        extraction_info={"method": "kg_demo", "timestamp": "2024-01-01T00:00:00Z"}
    )
    print(f"   ✓ Metadata KG: {len(metadata_graphs)} graphs")

    # Create content-only KG
    print("   Creating Content-Only KG...")
    content_graphs = mapper.save_content_rdf(
        entities_data=entities_data,
        output_dir=output_dir,
        extraction_info={"method": "kg_demo", "timestamp": "2024-01-01T00:00:00Z"}
    )
    print(f"   ✓ Content KG: {len(content_graphs)} graphs")

    # Create complete KG
    print("   Creating Complete KG...")
    complete_graphs = mapper.save_complete_rdf(
        entities_data=entities_data,
        output_dir=output_dir,
        extraction_info={"method": "kg_demo", "timestamp": "2024-01-01T00:00:00Z"}
    )
    print(f"   ✓ Complete KG: {len(complete_graphs)} graphs")

    # Analyze and compare
    print("\n3. Analyzing KG structures...")

    from rdflib import Graph

    kg_stats = {}
    for kg_type in ["metadata", "content", "complete"]:
        filename = f"{output_dir}/{kg_type}_{list(entities_data.keys())[0]}.ttl"
        if os.path.exists(filename):
            g = Graph()
            g.parse(filename, format="turtle")

            kg_stats[kg_type] = {
                "triples": len(g),
                "entities": len(set(g.subjects()))
            }

    # Display comparison
    print("\n4. Knowledge Graph Comparison:")
    print("-" * 50)
    for kg_type, stats in kg_stats.items():
        print(f"\n{kg_type.upper()} KG:")
        print(f"   Triples: {stats['triples']}")
        print(f"   Unique entities: {stats['entities']}")

    print(f"\n5. Files created in {output_dir}/:")
    for filename in sorted(os.listdir(output_dir)):
        if filename.endswith('.ttl'):
            filepath = os.path.join(output_dir, filename)
            size = os.path.getsize(filepath)
            print(f"   {filename} ({size} bytes)")

    print("\n6. Usage Examples:")
    print("""
# Create metadata-only KG (for citation networks)
mapper.save_metadata_rdf(entities_data, output_dir="rdf_output")

# Create content-only KG (for text analysis)
mapper.save_content_rdf(entities_data, output_dir="rdf_output")

# Create complete KG (for comprehensive analysis)
mapper.save_complete_rdf(entities_data, output_dir="rdf_output")

# Use configured default (from conf/rdf_map.yml)
mapper.save_rdf(entities_data, output_dir="rdf_output")
""")

    print("\nDemo completed successfully! 🎉")


if __name__ == "__main__":
    main()
