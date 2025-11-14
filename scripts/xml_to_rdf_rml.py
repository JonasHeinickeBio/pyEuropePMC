#!/usr/bin/env python
"""
CLI script to convert PMC XML files to RDF using RML mappings and SDM-RDFizer.

This script reads a PMC XML file, parses it, extracts entities,
and serializes them to RDF using RML (RDF Mapping Language) mappings
via the SDM-RDFizer tool.
"""

import argparse
import json
from pathlib import Path
import sys

from rdflib import Graph

from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.mappers import RDFIZER_AVAILABLE, RMLRDFizer
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert PMC XML files to RDF using RML mappings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert to RDF using RML
  %(prog)s input.xml --output output.ttl

  # Convert with verbose output
  %(prog)s input.xml --output output.ttl -v

  # Convert and also save intermediate JSON
  %(prog)s input.xml --output output.ttl --json entities.json
        """,
    )

    parser.add_argument("input", type=str, help="Input PMC XML file path")
    parser.add_argument(
        "--output", "-o", type=str, required=True, help="Output RDF file path (Turtle format)"
    )
    parser.add_argument(
        "--json",
        type=str,
        help="Optional: Save intermediate JSON entities to this file",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to RDFizer config file (optional)",
    )
    parser.add_argument(
        "--mappings",
        type=str,
        help="Path to RML mappings file (optional)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    return parser.parse_args()


def load_xml_file(file_path: str) -> str:
    """
    Load XML content from file.

    Parameters
    ----------
    file_path : str
        Path to XML file

    Returns
    -------
    str
        XML content
    """
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def main() -> int:
    """Main entry point for the script."""
    args = parse_args()

    # Check if RDFizer is available
    if not RDFIZER_AVAILABLE:
        print("Error: rdfizer package not installed")
        print("Install it with: pip install rdfizer")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    try:
        # Load and parse XML
        if args.verbose:
            print(f"Loading XML from {args.input}...")
        xml_content = load_xml_file(args.input)

        if args.verbose:
            print("Parsing XML...")
        parser = FullTextXMLParser(xml_content)

        if args.verbose:
            print("Building entities...")
        paper, authors, sections, tables, references = build_paper_entities(parser)

        # Normalize entities
        paper.normalize()
        for author in authors:
            author.normalize()
        for section in sections:
            section.normalize()
        for table in tables:
            table.normalize()
        for ref in references:
            ref.normalize()

        # Save intermediate JSON if requested
        if args.json:
            if args.verbose:
                print(f"Saving JSON entities to {args.json}...")

            json_data = {
                "paper": paper.to_dict(),
                "authors": [a.to_dict() for a in authors],
                "sections": [s.to_dict() for s in sections],
                "tables": [t.to_dict() for t in tables],
                "references": [r.to_dict() for r in references],
            }

            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            if args.verbose:
                print(f"JSON written to {args.json}")

        # Initialize RML RDFizer
        if args.verbose:
            print("Initializing RML RDFizer...")

        rdfizer_kwargs = {}
        if args.config:
            rdfizer_kwargs["config_path"] = args.config
        if args.mappings:
            rdfizer_kwargs["mapping_path"] = args.mappings

        rdfizer = RMLRDFizer(**rdfizer_kwargs)

        # Convert entities to RDF using RML
        if args.verbose:
            print("Converting to RDF using RML mappings...")

        # Create a combined graph
        g = Graph()

        # Convert each entity type separately and merge graphs
        if args.verbose:
            print("  - Converting paper...")
        paper_graph = rdfizer.entities_to_rdf([paper], entity_type="paper")
        g += paper_graph

        if authors and args.verbose:
            print(f"  - Converting {len(authors)} authors...")
        if authors:
            author_graph = rdfizer.entities_to_rdf(authors, entity_type="author")
            g += author_graph

        if sections and args.verbose:
            print(f"  - Converting {len(sections)} sections...")
        if sections:
            section_graph = rdfizer.entities_to_rdf(sections, entity_type="section")
            g += section_graph

        if tables and args.verbose:
            print(f"  - Converting {len(tables)} tables...")
        if tables:
            table_graph = rdfizer.entities_to_rdf(tables, entity_type="table")
            g += table_graph

        if references and args.verbose:
            print(f"  - Converting {len(references)} references...")
        if references:
            ref_graph = rdfizer.entities_to_rdf(references, entity_type="reference")
            g += ref_graph

        # Serialize to output file
        if args.verbose:
            print(f"Writing RDF to {args.output}...")

        g.serialize(destination=args.output, format="turtle")

        if args.verbose:
            print("Conversion complete!")
            print(f"  Paper: {paper.title or paper.pmcid or 'Unknown'}")
            print(f"  Authors: {len(authors)}")
            print(f"  Sections: {len(sections)}")
            print(f"  Tables: {len(tables)}")
            print(f"  References: {len(references)}")
            print(f"  Total RDF triples: {len(g)}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
