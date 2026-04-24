"""
Demonstration of RDF generation from enriched paper metadata.

This script shows how to:
1. Load enrichment data from saved JSON files
2. Create entity models from enriched data
3. Generate RDF triples with semantic mappings
4. Serialize RDF to Turtle format
"""

import json
from pathlib import Path

from rdflib import Graph

from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models import AuthorEntity, InstitutionEntity, PaperEntity


def load_enrichment_result(doi: str) -> dict:
    """Load enrichment result from saved JSON file."""
    # Sanitize DOI for filename
    safe_doi = doi.replace("/", "_").replace(".", "_")

    # Look for merged enrichment result
    enrichment_dir = Path(__file__).parent.parent / "enrichment_responses"
    merged_file = enrichment_dir / f"merged_{safe_doi}.json"

    if not merged_file.exists():
        raise FileNotFoundError(f"Enrichment file not found: {merged_file}")

    with open(merged_file) as f:
        return json.load(f)


def create_paper_from_enrichment(enrichment_result: dict) -> PaperEntity:
    """Create PaperEntity from enrichment result."""
    return PaperEntity.from_enrichment_result(enrichment_result)


def create_authors_from_enrichment(enrichment_result: dict) -> list[AuthorEntity]:
    """Create AuthorEntity instances from enrichment result."""
    merged = enrichment_result.get("merged", {})
    authors_data = merged.get("authors", [])

    authors = []
    for author_dict in authors_data:
        author = AuthorEntity.from_enrichment_dict(author_dict)
        authors.append(author)

    return authors


def create_institutions_from_authors(authors: list[AuthorEntity]) -> list[InstitutionEntity]:
    """Extract and create InstitutionEntity instances from author affiliations."""
    institutions = []
    seen_ids = set()

    for author in authors:
        if not author.institutions:
            continue

        for inst_dict in author.institutions:
            # Use ROR ID or OpenAlex ID as unique identifier
            inst_id = inst_dict.get("ror_id") or inst_dict.get("id")
            if inst_id and inst_id not in seen_ids:
                seen_ids.add(inst_id)
                institution = InstitutionEntity.from_enrichment_dict(inst_dict)
                institutions.append(institution)

    return institutions


def generate_enriched_rdf(doi: str, output_file: str | None = None) -> str:
    """
    Generate RDF from enriched paper data.

    Parameters
    ----------
    doi : str
        DOI of the paper
    output_file : str, optional
        Path to save RDF output

    Returns
    -------
    str
        RDF in Turtle format
    """
    print(f"Loading enrichment data for {doi}...")
    enrichment = load_enrichment_result(doi)

    print(f"Sources: {enrichment.get('sources', [])}")

    # Create entities
    print("\nCreating entities...")
    paper = create_paper_from_enrichment(enrichment)
    authors = create_authors_from_enrichment(enrichment)
    institutions = create_institutions_from_authors(authors)

    print(f"  Paper: {paper.title}")
    print(f"  Authors: {len(authors)}")
    print(f"  Institutions: {len(institutions)}")

    # Create RDF graph
    print("\nGenerating RDF...")
    mapper = RDFMapper()
    g = Graph()

    # Add paper
    paper_uri = paper.to_rdf(g, mapper=mapper)
    print(f"  Paper URI: {paper_uri}")

    # Add authors and their relationships to paper
    author_entities = []
    for author in authors:
        author_uri = author.to_rdf(g, mapper=mapper)
        author_entities.append(author)

    # Add authors relationship to paper
    if author_entities:
        mapper.map_relationships(g, paper_uri, paper, {"authors": author_entities})

    # Add institutions and their relationships to authors
    inst_map = {}  # Map ROR/OpenAlex ID to InstitutionEntity
    for institution in institutions:
        # Add institution to graph
        institution.to_rdf(g, mapper=mapper)
        inst_id = institution.ror_id or institution.openalex_id
        if inst_id:
            inst_map[inst_id] = institution

    # Link authors to institutions
    for author in authors:
        if not author.institutions:
            continue

        author_uri = mapper._generate_entity_uri(author)
        author_insts = []
        for inst_dict in author.institutions:
            inst_id = inst_dict.get("ror_id") or inst_dict.get("id")
            if inst_id and inst_id in inst_map:
                author_insts.append(inst_map[inst_id])

        if author_insts:
            mapper.map_relationships(g, author_uri, author, {"institutions": author_insts})

    print(f"\nRDF graph created with {len(g)} triples")

    # Serialize to Turtle
    ttl = mapper.serialize_graph(g, format="turtle", destination=output_file)

    if output_file:
        print(f"RDF saved to: {output_file}")

    return ttl if not output_file else ""


def main():
    """Main demo function."""
    # Example DOI from enrichment_responses
    doi = "10.1371/journal.pone.0308090"

    print("=" * 80)
    print("Enriched RDF Generation Demo")
    print("=" * 80)

    try:
        # Generate RDF and print to console
        ttl = generate_enriched_rdf(doi)

        print("\n" + "=" * 80)
        print("Generated RDF (first 2000 characters):")
        print("=" * 80)
        print(ttl[:2000])
        print("\n... (truncated)")

        # Optionally save to file
        output_file = "/tmp/enriched_paper.ttl"
        generate_enriched_rdf(doi, output_file=output_file)

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nTo run this demo, first enrich a paper:")
        print("  python examples/09-enrichment/basic_enrichment.py")


if __name__ == "__main__":
    main()
