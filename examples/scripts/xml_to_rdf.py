#!/usr/bin/env python
"""
CLI script to convert PMC XML files to RDF (Turtle) and JSON.

This script reads a PMC XML file, parses it, extracts entities,
and serializes them to RDF and/or JSON formats.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from rdflib import Graph

from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.mappers import RDFMapper
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert PMC XML files to RDF and JSON formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert to both TTL and JSON
  %(prog)s input.xml --ttl output.ttl --json output.json

  # Convert to TTL only
  %(prog)s input.xml --ttl output.ttl

  # Convert to JSON only
  %(prog)s input.xml --json output.json
        """,
    )

    parser.add_argument("input", type=str, help="Input PMC XML file path")
    parser.add_argument("--ttl", type=str, help="Output Turtle (TTL) file path")
    parser.add_argument("--json", type=str, help="Output JSON file path")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to RDF mapping config YAML (optional)",
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


def entities_to_json(
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
) -> dict[str, Any]:
    """
    Convert entities to JSON-serializable dictionary.

    Parameters
    ----------
    paper : PaperEntity
        Paper entity
    authors : list[AuthorEntity]
        List of author entities
    sections : list[SectionEntity]
        List of section entities
    tables : list[TableEntity]
        List of table entities
    figures : list[FigureEntity]
        List of figure entities
    references : list[ReferenceEntity]
        List of reference entities

    Returns
    -------
    dict
        JSON-serializable dictionary
    """
    return {
        "paper": paper.to_dict(),
        "authors": [a.to_dict() for a in authors],
        "sections": [s.to_dict() for s in sections],
        "tables": [t.to_dict() for t in tables],
        "figures": [f.to_dict() for f in figures],
        "references": [r.to_dict() for r in references],
    }


def validate_arguments(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    if not args.ttl and not args.json:
        print("Error: At least one output format (--ttl or --json) must be specified")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)


def process_entities(
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
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


def generate_ttl_output(
    args: argparse.Namespace,
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
) -> None:
    """Generate RDF/Turtle output."""
    if args.verbose:
        print(f"Generating RDF/Turtle output to {args.ttl}...")

    # Initialize mapper
    mapper = RDFMapper(config_path=args.config)

    # Create RDF graph
    g = Graph()

    # Add paper
    paper.to_rdf(g, mapper=mapper)

    # Add authors
    for author in authors:
        author.to_rdf(g, mapper=mapper)

    # Add sections
    for section in sections:
        section.to_rdf(g, mapper=mapper)

    # Add tables
    for table in tables:
        table.to_rdf(g, mapper=mapper)

    # Add figures
    for figure in figures:
        figure.to_rdf(g, mapper=mapper)

    # Add references
    for reference in references:
        reference.to_rdf(g, mapper=mapper)

    # Serialize to TTL
    mapper.serialize_graph(g, format="turtle", destination=args.ttl)
    if args.verbose:
        print(f"RDF/Turtle written to {args.ttl}")


def generate_json_output(
    args: argparse.Namespace,
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
) -> None:
    """Generate JSON output."""
    if args.verbose:
        print(f"Generating JSON output to {args.json}...")

    json_data = entities_to_json(paper, authors, sections, tables, figures, references)

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    if args.verbose:
        print(f"JSON written to {args.json}")


def print_summary(
    args: argparse.Namespace,
    paper: Any,
    authors: list[Any],
    sections: list[Any],
    tables: list[Any],
    figures: list[Any],
    references: list[Any],
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


def main() -> int:
    """Main entry point for the script."""
    args = parse_args()
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

        if args.verbose:
            print(f"Paper grants: {getattr(paper, 'grants', 'No grants attribute')}")
            if hasattr(paper, "grants") and paper.grants:
                print(f"Number of grants: {len(paper.grants)}")
                for i, grant in enumerate(paper.grants):
                    print(f"Grant {i}: {grant}")

        # Normalize entities
        process_entities(paper, authors, sections, tables, figures, references)

        # Generate outputs
        if args.ttl:
            generate_ttl_output(args, paper, authors, sections, tables, figures, references)

        if args.json:
            generate_json_output(args, paper, authors, sections, tables, figures, references)

        print_summary(args, paper, authors, sections, tables, figures, references)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
