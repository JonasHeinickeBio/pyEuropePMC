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
from typing import Any

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


def validate_arguments(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)


def check_rdfizer_availability() -> None:
    """Check if RDFizer is available."""
    if not RDFIZER_AVAILABLE:
        print("Error: rdfizer package not installed")
        print("Install it with: pip install rdfizer")
        sys.exit(1)


def process_entities(
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
    journals: list[Any],
    grants: list[Any],
) -> None:
    """Normalize all entities."""
    paper.normalize()
    for author in authors:
        author.normalize()
    for section in sections:
        section.normalize()
    for table in tables:
        table.normalize()
    for figure in figures:
        figure.normalize()
    for ref in references:
        ref.normalize()
    for journal in journals:
        journal.normalize()
    for grant in grants:
        grant.normalize()


def save_json_entities(
    args: argparse.Namespace,
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
    journals: list[Any],
    grants: list[Any],
) -> None:
    """Save intermediate JSON entities if requested."""
    if args.json:
        if args.verbose:
            print(f"Saving JSON entities to {args.json}...")

        json_data = {
            "paper": paper.to_dict(),
            "authors": [a.to_dict() for a in authors],
            "sections": [s.to_dict() for s in sections],
            "tables": [t.to_dict() for t in tables],
            "figures": [f.to_dict() for f in figures],
            "references": [r.to_dict() for r in references],
            "journals": [j.to_dict() for j in journals],
            "grants": [g.to_dict() for g in grants],
        }

        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        if args.verbose:
            print(f"JSON written to {args.json}")


def convert_single_entity_type(
    rdfizer: RMLRDFizer, entities: list[Any], entity_type: str, verbose: bool
) -> Graph:
    """Convert a single entity type to RDF."""
    if not entities:
        return Graph()

    if verbose:
        print(f"  - Converting {len(entities)} {entity_type}s...")

    return rdfizer.entities_to_rdf(entities, entity_type=entity_type)


def convert_entities_to_rdf(
    args: argparse.Namespace,
    rdfizer: RMLRDFizer,
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
    journals: list[Any],
    grants: list[Any],
) -> Graph:
    """Convert entities to RDF using RML mappings."""
    if args.verbose:
        print("Converting to RDF using RML mappings...")

    # Create a combined graph
    g = Graph()

    # Convert each entity type separately and merge graphs
    g += convert_single_entity_type(rdfizer, [paper], "paper", args.verbose)
    g += convert_single_entity_type(rdfizer, authors, "author", args.verbose)
    g += convert_single_entity_type(rdfizer, sections, "section", args.verbose)
    g += convert_single_entity_type(rdfizer, tables, "table", args.verbose)
    g += convert_single_entity_type(rdfizer, figures, "figure", args.verbose)
    g += convert_single_entity_type(rdfizer, references, "reference", args.verbose)
    g += convert_single_entity_type(rdfizer, journals, "journal", args.verbose)
    g += convert_single_entity_type(rdfizer, grants, "grant", args.verbose)

    return g


def print_summary(
    args: argparse.Namespace,
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
    journals: list[Any],
    grants: list[Any],
    g: Graph,
) -> None:
    """Print conversion summary if verbose."""
    if args.verbose:
        print("Conversion complete!")
        print(f"  Paper: {paper.title or paper.pmcid or 'Unknown'}")
        print(f"  Authors: {len(authors)}")
        print(f"  Sections: {len(sections)}")
        print(f"  Tables: {len(tables)}")
        print(f"  Figures: {len(figures)}")
        print(f"  References: {len(references)}")
        print(f"  Journals: {len(journals)}")
        print(f"  Grants: {len(grants)}")
        print(f"  Total RDF triples: {len(g)}")


def initialize_rdfizer(args: argparse.Namespace) -> RMLRDFizer:
    """Initialize RML RDFizer with configuration."""
    if args.verbose:
        print("Initializing RML RDFizer...")

    rdfizer_kwargs = {}
    if args.config:
        rdfizer_kwargs["config_path"] = args.config
    if args.mappings:
        rdfizer_kwargs["mapping_path"] = args.mappings

    return RMLRDFizer(**rdfizer_kwargs)


def serialize_and_save_rdf(args: argparse.Namespace, g: Graph) -> None:
    """Serialize and save RDF to output file."""
    if args.verbose:
        print(f"Writing RDF to {args.output}...")

    g.serialize(destination=args.output, format="turtle")


def main() -> int:
    """Main entry point for the script."""
    args = parse_args()
    check_rdfizer_availability()
    validate_arguments(args)

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
        paper, authors, sections, tables, figures, references = build_paper_entities(parser)

        # Extract journal entities
        journals = []
        if paper.journal:
            journals = [paper.journal]

        # Extract grant entities
        grants = paper.grants or []

        # Normalize entities
        process_entities(paper, authors, sections, tables, figures, references, journals, grants)

        # Save intermediate JSON if requested
        save_json_entities(
            args, paper, authors, sections, tables, figures, references, journals, grants
        )

        # Initialize RML RDFizer
        rdfizer = initialize_rdfizer(args)

        # Convert entities to RDF using RML
        g = convert_entities_to_rdf(
            args, rdfizer, paper, authors, sections, tables, figures, references, journals, grants
        )

        # Serialize to output file
        serialize_and_save_rdf(args, g)

        print_summary(
            args, paper, authors, sections, tables, figures, references, journals, grants, g
        )

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
