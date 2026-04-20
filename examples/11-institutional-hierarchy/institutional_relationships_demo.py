#!/usr/bin/env python3
"""
Institutional Hierarchy and Relationship Mapping Demo

This script demonstrates how to properly map:
1. Department → Organization hierarchies
2. Organization ↔ Authors (affiliations)
3. Papers ↔ Organizations (through authors)
4. Explicit institutional relationships

The example:
- Creates sample author and organization entities with relationships
- Generates RDF with proper institutional hierarchies
- Demonstrates the complete institutional structure in Turtle format
"""

import json
from datetime import datetime
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, DCTERMS

# Import PyEuropePMC components
from pyeuropepmc.models import AuthorEntity, PaperEntity, Organization, Department
from pyeuropepmc.mappers.rdf_mapper import RDFMapper


def create_institutional_hierarchy():
    """Create a sample institutional hierarchy for demonstration."""

    # Create organizations
    mit = Organization(
        display_name="Massachusetts Institute of Technology",
        ror_id="https://ror.org/042nb2s44",
        country="United States",
        country_code="US",
        city="Cambridge",
        latitude=42.3601,
        longitude=-71.0589,
        institution_type="education",
        website="https://www.mit.edu",
        established="1861",
    )

    harvard = Organization(
        display_name="Harvard University",
        ror_id="https://ror.org/03vek6s52",
        country="United States",
        country_code="US",
        city="Cambridge",
        latitude=42.3775,
        longitude=-71.1167,
        institution_type="education",
        website="https://www.harvard.edu",
        established="1636",
    )

    # Create departments
    dept_csail = Department(
        display_name="Computer Science and Artificial Intelligence Laboratory",
        parent_organization=mit,
        country="United States",
        city="Cambridge",
        department_type="Research Laboratory",
    )

    dept_broadinstitute = Department(
        display_name="Broad Institute of Harvard and MIT",
        parent_organization=mit,
        country="United States",
        city="Cambridge",
        department_type="Research Institute",
    )

    # Create authors with institutional affiliations
    author1 = AuthorEntity(
        full_name="John Smith",
        first_name="John",
        last_name="Smith",
        orcid="0000-0001-2345-6789",
        author_institutions=[mit],
        affiliation_text="Computer Science and Artificial Intelligence Laboratory, MIT",
        position="first",
    )

    author2 = AuthorEntity(
        full_name="Jane Doe",
        first_name="Jane",
        last_name="Doe",
        orcid="0000-0001-9876-5432",
        author_institutions=[mit, harvard],
        affiliation_text="Broad Institute of Harvard and MIT",
        position="middle",
    )

    # Create a paper with institutional affiliations
    paper = PaperEntity(
        pmcid="PMC12345678",
        pmid="12345678",
        title="Deep Learning for Genomic Analysis",
        publication_year="2024",
        abstract="This paper presents a novel approach to genomic analysis using deep learning.",
        authors=[author1, author2],
        paper_institutions=[mit, harvard],
    )

    return {
        "organizations": {"mit": mit, "harvard": harvard},
        "departments": {"csail": dept_csail, "broadinstitute": dept_broadinstitute},
        "authors": {"smith": author1, "doe": author2},
        "papers": {"genomics": paper},
    }


def generate_institutional_rdf():
    """Generate RDF with institutional hierarchy relationships."""

    # Create the hierarchy
    entities = create_institutional_hierarchy()

    # Create RDF mapper with named graphs
    mapper = RDFMapper()

    # Prepare entities data for conversion
    entities_data = {
        "genomics-paper": {
            "entity": entities["papers"]["genomics"],
            "related_entities": {"authors": entities["authors"].values()},
        }
    }

    # Convert to RDF
    rdf_graphs = mapper.convert_and_save_entities_to_rdf(
        entities_data,
        output_dir="test_output",
        prefix="institutional_",
        filename_template="test_output/institutional_hierarchy.ttl",
    )

    return rdf_graphs


def print_institutional_relationships():
    """Print and verify institutional relationships in the RDF."""

    # Generate RDF
    graphs = generate_institutional_rdf()

    if not graphs:
        print("No RDF graphs generated!")
        return

    # Get the first graph
    paper_id = list(graphs.keys())[0]
    rdf_graph = graphs[paper_id]

    print(f"\n{'=' * 80}")
    print("INSTITUTIONAL HIERARCHY RDF RELATIONSHIPS")
    print(f"{'=' * 80}\n")

    # Define namespaces for querying
    ORG = Namespace("http://www.w3.org/ns/org#")
    FOAF = Namespace("http://xmlns.com/foaf/0.1/")
    DCTERMS = Namespace("http://purl.org/dc/terms/")
    PYEUROPEPMC = Namespace("https://w3id.org/pyeuropepmc/vocab#")

    print("1. ORGANIZATIONAL HIERARCHY")
    print("-" * 80)
    for s, p, o in rdf_graph.triples((None, ORG.hasUnit, None)):
        print(f"  Organization: {s.split('#')[-1]}")
        print(f"  Has Department: {o.split('#')[-1]}")
        print()

    print("\n2. AUTHOR AFFILIATIONS")
    print("-" * 80)
    for s, p, o in rdf_graph.triples((None, PYEUROPEPMC.affiliatedWith, None)):
        subject_name = s.split("#")[-1]
        object_name = o.split("#")[-1]
        if "author" in str(s):
            print(f"  Author: {subject_name}")
            print(f"  Affiliated With: {object_name}")
            print()

    print("\n3. DEPARTMENT MEMBERSHIP")
    print("-" * 80)
    for s, p, o in rdf_graph.triples((None, PYEUROPEPMC.departmentMember, None)):
        subject_name = s.split("#")[-1]
        object_name = o.split("#")[-1]
        print(f"  Author: {subject_name}")
        print(f"  Department Member: {object_name}")
        print()

    print("\n4. PAPER-ORGANIZATION RELATIONSHIPS")
    print("-" * 80)
    for s, p, o in rdf_graph.triples((None, PYEUROPEPMC.affiliatedWith, None)):
        subject_name = s.split("#")[-1]
        object_name = o.split("#")[-1]
        if "paper" in str(s):
            print(f"  Paper: {subject_name}")
            print(f"  Organization: {object_name}")
            print()

    print("\n5. PAPER DEPARTMENTS")
    print("-" * 80)
    for s, p, o in rdf_graph.triples((None, PYEUROPEPMC.departmentAffiliation, None)):
        subject_name = s.split("#")[-1]
        object_name = o.split("#")[-1]
        print(f"  Paper: {subject_name}")
        print(f"  Department: {object_name}")
        print()

    print(f"\nTotal triples in RDF graph: {len(rdf_graph)}")

    # Print full TTL for inspection
    print(f"\n{'=' * 80}")
    print("COMPLETE RDF IN TURTLE FORMAT")
    print(f"{'=' * 80}\n")
    ttl_path = Path("test_output/institutional_hierarchy.ttl")
    if ttl_path.exists():
        with open(ttl_path) as f:
            print(f.read())
    else:
        print("TTL file not found!")


def validate_namespace_usage():
    """Verify that proper namespaces are used in RDF output."""

    graphs = generate_institutional_rdf()
    if not graphs:
        return

    paper_id = list(graphs.keys())[0]
    rdf_graph = graphs[paper_id]

    print(f"\n{'=' * 80}")
    print("NAMESPACE VALIDATION")
    print(f"{'=' * 80}\n")

    print("Namespaces bound in graph:")
    for prefix, namespace in rdf_graph.namespace_manager.namespaces():
        print(f"  {prefix}: {namespace}")

    print("\nVerifying proper namespace usage...")

    # Check for problematic ns1, ns2, ns3 prefixes
    bad_prefixes = ["ns1", "ns2", "ns3", "ns4", "ns5"]
    ttl_output = rdf_graph.serialize(format="turtle")

    problems_found = False
    for bad_prefix in bad_prefixes:
        if f"@prefix {bad_prefix}" in ttl_output:
            print(f"  ❌ Found problematic prefix: {bad_prefix}")
            problems_found = True

    if not problems_found:
        print("  ✓ No problematic generic prefixes found")

    # Verify expected namespaces
    expected_namespaces = [
        ("dcterms", "http://purl.org/dc/terms/"),
        ("foaf", "http://xmlns.com/foaf/0.1/"),
        ("org", "http://www.w3.org/ns/org#"),
        ("pyeuropepmc", "https://w3id.org/pyeuropepmc/vocab#"),
    ]

    print("\nExpected namespaces:")
    for prefix, uri in expected_namespaces:
        if any(str(ns) == uri for _, ns in rdf_graph.namespace_manager.namespaces()):
            print(f"  ✓ {prefix}: {uri}")
        else:
            print(f"  ❌ Missing: {prefix}: {uri}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("INSTITUTIONAL HIERARCHY AND RELATIONSHIP MAPPING DEMONSTRATION")
    print("=" * 80)

    # Generate and display relationships
    print_institutional_relationships()

    # Validate namespace usage
    validate_namespace_usage()

    print(f"\n{'=' * 80}")
    print("Demo complete! Check test_output/institutional_hierarchy.ttl for full RDF.")
    print("=" * 80 + "\n")
