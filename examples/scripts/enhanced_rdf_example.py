#!/usr/bin/env python3
"""
Enhanced RDF Generation Example

This script demonstrates the enhanced RDF generation capabilities
added to the existing PyEuropePMC codebase, including:

- Named graphs for better organization
- Citation networks using CiTO ontology
- Author collaboration networks using VIVO ontology
- Institutional hierarchies using ORG ontology
- Quality metrics and temporal information
- Data source attribution and provenance tracking

Usage:
    python enhanced_rdf_example.py
"""

from pyeuropepmc.mappers.converters import convert_enhanced_to_rdf


def main():
    """Demonstrate enhanced RDF generation."""

    print("PyEuropePMC Enhanced RDF Generation Example")
    print("=" * 50)

    # Sample data - in real usage, this would come from Europe PMC API
    sample_search_results = {
        "resultList": {
            "result": [
                {
                    "doi": "10.1038/nature12345",
                    "title": "Advances in Cancer Immunotherapy",
                    "pmcid": "PMC123456",
                    "pmid": "12345678",
                    "authorString": "Smith J, Johnson A, Brown R",
                    "journalTitle": "Nature",
                    "pubYear": "2023",
                    "citedByCount": 25,
                },
                {
                    "doi": "10.1038/nature12346",
                    "title": "Novel Therapeutic Approaches",
                    "pmcid": "PMC123457",
                    "pmid": "12345679",
                    "authorString": "Johnson A, Davis M, Wilson K",
                    "journalTitle": "Nature Medicine",
                    "pubYear": "2023",
                    "citedByCount": 15,
                },
            ]
        }
    }

    print("Converting sample data to enhanced RDF...")

    try:
        # Generate enhanced RDF with all features enabled
        main_graph, named_graphs = convert_enhanced_to_rdf(
            search_results=sample_search_results,
            enable_citation_networks=True,
            enable_collaboration_networks=True,
            enable_institutional_hierarchies=True,
            enable_quality_metrics=True,
            enable_shacl_validation=False,  # Disable for simplicity
        )

        print("✓ Enhanced RDF generation successful!")
        print(f"  Total triples: {len(main_graph)}")
        print(f"  Named graphs: {list(named_graphs.keys())}")

        # Show breakdown by named graph
        print("\nNamed Graph Breakdown:")
        for name, graph in named_graphs.items():
            print(f"  {name}: {len(graph)} triples")

        # Show some sample triples
        print("\nSample Triples from Main Graph:")
        for i, (s, p, o) in enumerate(main_graph):
            if i >= 5:
                break
            print(f"  {s} {p} {o}")

        # Check for enhanced features
        features = {
            "Quality Metrics": any("qualityScore" in str(p) for s, p, o in main_graph),
            "Data Source Attribution": any("dataSource" in str(p) for s, p, o in main_graph),
            "Temporal Information": any("lastUpdated" in str(p) for s, p, o in main_graph),
            "Provenance Tracking": any("generatedAtTime" in str(p) for s, p, o in main_graph),
        }

        print("\nEnhanced Features Present:")
        for feature, present in features.items():
            status = "✓" if present else "✗"
            print(f"  {status} {feature}")

        # Save to file
        output_file = "enhanced_rdf_output.ttl"
        main_graph.serialize(destination=output_file, format="turtle")
        print(f"\n✓ RDF saved to: {output_file}")

        print("\n" + "=" * 50)
        print("Enhanced RDF generation complete!")
        print("The generated RDF includes:")
        print("• Named graphs for organized data management")
        print("• Quality metrics for data reliability assessment")
        print("• Data source attribution for provenance tracking")
        print("• Temporal information for versioning")
        print("• Semantic relationships using biomedical ontologies")
        print("=" * 50)

    except Exception as e:
        print(f"✗ Error during RDF generation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
