#!/usr/bin/env python3
"""
Example demonstrating the simplified unified pipeline workflow.

This script shows how the new PaperProcessingPipeline simplifies the
complex multi-step process of XML parsing → enrichment → RDF conversion
into a single, easy-to-use interface.
"""

import pyeuropepmc


def main():
    """Demonstrate the unified pipeline workflow."""

    print("=== PyEuropePMC Unified Pipeline Demo ===\n")

    # Configuration - much simpler than before!
    config = pyeuropepmc.PipelineConfig(
        enable_enrichment=True,  # Enable metadata enrichment
        enable_crossref=True,
        enable_semantic_scholar=True,
        enable_openalex=True,
        enable_ror=True,
        crossref_email="your.email@example.com",  # Replace with your email
        output_format="turtle",
        output_dir="output"
    )

    # Create pipeline - single object handles everything
    pipeline = pyeuropepmc.PaperProcessingPipeline(config)

    print("Pipeline configured and ready!\n")

    # Example XML content (in practice, you'd load from file or API)
    xml_content = """<?xml version='1.0' encoding='UTF-8'?>
<article xmlns:mml='http://www.w3.org/1998/Math/MathML' xmlns:xlink='http://www.w3.org/1999/xlink' article-type='research-article'>
  <front>
    <article-meta>
      <article-id pub-id-type='pmcid'>PMC3258128</article-id>
      <article-id pub-id-type='doi'>10.1038/nature11476</article-id>
      <title-group>
        <article-title>Long COVID: major findings, mechanisms and recommendations</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type='author'>
          <name><surname>Davis</surname><given-names>HE</given-names></name>
          <aff>Department of Surgery and Cancer, Imperial College London</aff>
        </contrib>
        <contrib contrib-type='author'>
          <name><surname>McCorkell</surname><given-names>L</given-names></name>
          <aff>Patient-Led Research Collaborative</aff>
        </contrib>
      </contrib-group>
      <pub-date pub-type='epub'>
        <year>2023</year>
        <month>02</month>
        <day>15</day>
      </pub-date>
      <abstract>
        <p>Long COVID is a debilitating illness of unknown cause.</p>
      </abstract>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>Long COVID refers to persistent symptoms following SARS-CoV-2 infection.</p>
    </sec>
    <sec>
      <title>Methods</title>
      <p>We conducted a comprehensive review of the literature.</p>
    </sec>
  </body>
</article>"""

    print("Processing paper with unified pipeline...")

    # Single method call replaces the complex multi-step workflow!
    result = pipeline.process_paper(
        xml_content=xml_content,
        doi="10.1038/nature11476",
        pmcid="PMC3258128",
        save_rdf=True,
        filename_prefix="demo_"
    )

    print("✅ Processing complete!\n")

    # Show results
    print("Results:")
    print(f"  - Paper title: {result['entities']['paper'].title}")
    print(f"  - Authors: {len(result['entities']['authors'])}")
    print(f"  - Sections: {len(result['entities']['sections'])}")
    print(f"  - RDF triples generated: {result['triple_count']}")
    print(f"  - Output file: {result['output_file']}")

    if result['enrichment_data']:
        print("  - Enrichment sources:", result['enrichment_data'].get('sources', []))
        if 'citation_count' in result['enrichment_data']:
            print(f"  - Citation count: {result['enrichment_data']['citation_count']}")

    print(f"\nRDF file saved to: {result['output_file']}")

    # Demonstrate batch processing
    print("\n=== Batch Processing Demo ===")

    xml_contents = {
        "10.1038/nature11476": xml_content,  # Same paper
        "10.1038/test123": xml_content.replace("nature11476", "test123")  # Mock second paper
    }

    print("Processing multiple papers...")
    batch_results = pipeline.process_papers(xml_contents, save_rdf=True)

    for identifier, result in batch_results.items():
        if 'error' in result:
            print(f"❌ {identifier}: {result['error']}")
        else:
            print(f"✅ {identifier}: {result['triple_count']} triples")

    print("\n=== Comparison: Old vs New Workflow ===")
    print("OLD WORKFLOW (complex, error-prone):")
    print("  1. parser = FullTextXMLParser()")
    print("  2. parser.parse(xml_content)")
    print("  3. paper, authors, sections, tables, figures, references = build_paper_entities(parser)")
    print("  4. enricher = PaperEnricher(config)")
    print("  5. enrichment_data = enricher.enrich_paper(doi)")
    print("  6. rdf_mapper = RDFMapper()")
    print("  7. paper.to_rdf(graph, related_entities=...)")
    print("  8. rdf_mapper.serialize_graph(graph, format='turtle')")
    print("  → 8+ separate steps, lots of manual coordination")

    print("\nNEW WORKFLOW (simple, unified):")
    print("  1. config = PipelineConfig(...)")
    print("  2. pipeline = PaperProcessingPipeline(config)")
    print("  3. result = pipeline.process_paper(xml_content, doi=doi)")
    print("  → 3 steps, everything handled automatically!")

    print("\n🎉 The unified pipeline dramatically simplifies the workflow!")


if __name__ == "__main__":
    main()
