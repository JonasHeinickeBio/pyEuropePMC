#!/usr/bin/env python3
"""
Institutional Hierarchy and Relationship Mapping - IMPROVED DATA MODEL

This example shows:
1. Explicit Department ↔ Organization hierarchies
2. Author ↔ Organization institutional affiliations
3. Paper ↔ Organization relationships through authors
4. Proper RDF namespace usage

Key Improvements:
- Uses org: and pyeuropepmc: namespaces for relationships
- Generates institutional hierarchies with clear parent-child relationships
- Links papers to their affiliated organizations
- Avoids generic "ns1", "ns2" prefixes
"""

from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, DCTERMS, FOAF

def demonstrate_improvements():
    """Demonstrate the improved institutional hierarchy RDF generation."""

    # Define namespaces
    ORG = Namespace("http://www.w3.org/ns/org#")
    BIBO = Namespace("http://purl.org/ontology/bibo/")
    PYEUROPEPMC = Namespace("https://w3id.org/pyeuropepmc/vocab#")
    DATA = Namespace("https://w3id.org/pyeuropepmc/data#")

    # Create RDF graph
    g = Graph()

    # Bind namespaces  (IMPROVEMENT: Explicit namespace binding)
    g.bind("org", ORG)
    g.bind("bibo", BIBO)
    g.bind("foaf", FOAF)
    g.bind("dcterms", DCTERMS)
    g.bind("pyeuropepmc", PYEUROPEPMC)
    g.bind("data", DATA)

    print("\n" + "="*80)
    print("IMPROVED INSTITUTIONAL HIERARCHY MAPPING")
    print("="*80 + "\n")

    # ===== ORGANIZATIONS =====
    print("1. ORGANIZATIONS")
    print("-" * 80)

    mit_uri = DATA["organization/mit"]
    g.add((mit_uri, RDF.type, ORG.Organization))
    g.add((mit_uri, RDFS.label, Literal("Massachusetts Institute of Technology")))
    g.add((mit_uri, DCTERMS.created, Literal("1861")))
    g.add((mit_uri, PYEUROPEPMC.rorId, Literal("https://ror.org/042nb2s44")))
    print(f"  ✓ Organization: {mit_uri.split('#')[-1]}")

    harvard_uri = DATA["organization/harvard"]
    g.add((harvard_uri, RDF.type, ORG.Organization))
    g.add((harvard_uri, RDFS.label, Literal("Harvard University")))
    g.add((harvard_uri, DCTERMS.created, Literal("1636")))
    g.add((harvard_uri, PYEUROPEPMC.rorId, Literal("https://ror.org/03vek6s52")))
    print(f"  ✓ Organization: {harvard_uri.split('#')[-1]}")

    # ===== DEPARTMENTS =====
    print("\n2. DEPARTMENTS (IMPROVED: Explicit hierarchy)")
    print("-" * 80)

    csail_uri = DATA["department/csail"]
    g.add((csail_uri, RDF.type, ORG.OrganizationalUnit))
    g.add((csail_uri, RDFS.label, Literal("Computer Science and AI Laboratory")))
    g.add((csail_uri, ORG.unitOf, mit_uri))  # IMPROVEMENT: Explicit unitOf relationship
    g.add((mit_uri, ORG.hasUnit, csail_uri))  # IMPROVEMENT: Inverse relationship
    print(f"  ✓ Department: {csail_uri.split('#')[-1]}")
    print(f"    - unitOf: {mit_uri.split('#')[-1]}")

    broadinst_uri = DATA["department/broadinstitute"]
    g.add((broadinst_uri, RDF.type, ORG.OrganizationalUnit))
    g.add((broadinst_uri, RDFS.label, Literal("Broad Institute")))
    g.add((broadinst_uri, ORG.unitOf, mit_uri))  # IMPROVEMENT: Explicit unitOf relationship
    g.add((mit_uri, ORG.hasUnit, broadinst_uri))  # IMPROVEMENT: Inverse relationship
    print(f"  ✓ Department: {broadinst_uri.split('#')[-1]}")
    print(f"    - unitOf: {mit_uri.split('#')[-1]}")

    # ===== AUTHORS =====
    print("\n3. AUTHORS WITH INSTITUTIONAL AFFILIATIONS (IMPROVED: Explicit)")
    print("-" * 80)

    smith_uri = DATA["author/john-smith"]
    g.add((smith_uri, RDF.type, FOAF.Person))
    g.add((smith_uri, FOAF.name, Literal("John Smith")))
    g.add((smith_uri, PYEUROPEPMC.affiliatedWith, mit_uri))  # IMPROVEMENT: Explicit affiliation
    g.add((mit_uri, PYEUROPEPMC.hasAffiliate, smith_uri))  # IMPROVEMENT: Inverse
    print(f"  ✓ Author: {smith_uri.split('#')[-1]}")
    print(f"    - affiliatedWith: {mit_uri.split('#')[-1]}")

    doe_uri = DATA["author/jane-doe"]
    g.add((doe_uri, RDF.type, FOAF.Person))
    g.add((doe_uri, FOAF.name, Literal("Jane Doe")))
    g.add((doe_uri, PYEUROPEPMC.affiliatedWith, mit_uri))  # IMPROVEMENT: Affiliation 1
    g.add((mit_uri, PYEUROPEPMC.hasAffiliate, doe_uri))  # IMPROVEMENT: Inverse 1
    g.add((doe_uri, PYEUROPEPMC.affiliatedWith, harvard_uri))  # IMPROVEMENT: Affiliation 2
    g.add((harvard_uri, PYEUROPEPMC.hasAffiliate, doe_uri))  # IMPROVEMENT: Inverse 2
    print(f"  ✓ Author: {doe_uri.split('#')[-1]}")
    print(f"    - affiliatedWith: {mit_uri.split('#')[-1]}")
    print(f"    - affiliatedWith: {harvard_uri.split('#')[-1]}")

    # ===== PAPERS =====
    print("\n4. PAPERS WITH INSTITUTIONAL AFFILIATION THROUGH AUTHORS")
    print("-" * 80)

    paper_uri = DATA["paper/genomics-2024"]
    g.add((paper_uri, RDF.type, BIBO.AcademicArticle))
    g.add((paper_uri, DCTERMS.title, Literal("Deep Learning for Genomic Analysis")))
    g.add((paper_uri, DCTERMS.creator, smith_uri))  # Link to author
    g.add((paper_uri, DCTERMS.creator, doe_uri))   # Link to author

    # IMPROVEMENT: Direct paper ↔ organization relationships
    g.add((paper_uri, PYEUROPEPMC.affiliatedWith, mit_uri))
    g.add((mit_uri, PYEUROPEPMC.hasPublication, paper_uri))
    g.add((paper_uri, PYEUROPEPMC.affiliatedWith, harvard_uri))
    g.add((harvard_uri, PYEUROPEPMC.hasPublication, paper_uri))

    print(f"  ✓ Paper: {paper_uri.split('#')[-1]}")
    print(f"    - Authors: John Smith, Jane Doe")
    print(f"    - affiliatedWith: {mit_uri.split('#')[-1]}")
    print(f"    - affiliatedWith: {harvard_uri.split('#')[-1]}")

    # ===== GENERATE AND DISPLAY RDF =====
    print("\n" + "="*80)
    print("GENERATED RDF (Turtle Format)")
    print("="*80 + "\n")

    ttl_output = g.serialize(format="turtle")
    print(ttl_output)

    # ===== VALIDATION =====
    print("\n" + "="*80)
    print("NAMESPACE VALIDATION")
    print("="*80 + "\n")

    # Check for problematic ns prefixes
    bad_prefixes = ['ns1', 'ns2', 'ns3']
    problems = False
    for prefix in bad_prefixes:
        if f"@prefix {prefix}" in ttl_output:
            print(f"  ❌ Found problematic prefix: {prefix}")
            problems = True

    if not problems:
        print("  ✓ No generic ns1/ns2/ns3 prefixes found")

    # Verify expected namespaces
    print("\nExpected namespaces present:")
    expected = ["@prefix org:", "@prefix foaf:", "@prefix dcterms:", "@prefix pyeuropepmc:"]
    for prefix in expected:
        if prefix in ttl_output:
            print(f"  ✓ {prefix}")
        else:
            print(f"  ❌ Missing: {prefix}")

    # ===== RELATIONSHIP COUNT =====
    print("\n" + "="*80)
    print("RELATIONSHIP SUMMARY")
    print("="*80 + "\n")
    print(f"Total triples: {len(g)}")
    print(f"Organization hierarchy links: 4 (MIT, Harvard + 2 departments)")
    print(f"Author affiliations: 3")
    print(f"Paper-Organization links: 4")

    # Save to file
    output_file = "test_output/institutional_improved.ttl"
    try:
        with open(output_file, "w") as f:
            f.write(ttl_output)
        print(f"\n✓ RDF saved to: {output_file}")
    except Exception as e:
        print(f"\n❌ Error saving RDF: {e}")

    return g


if __name__ == "__main__":
    g = demonstrate_improvements()
    print("\n" + "="*80)
    print("DEMONSTRATION COMPLETE")
    print("="*80 + "\n")
    print("KEY IMPROVEMENTS SHOWN:")
    print("  1. ✓ Explicit Department ↔ Organization hierarchies (org:unitOf / org:hasUnit)")
    print("  2. ✓ Author ↔ Organization affiliations (pyeuropepmc:affiliatedWith)")
    print("  3. ✓ Paper ↔ Organization relationships (pyeuropepmc:affiliatedWith)")
    print("  4. ✓ Proper namespace usage (no generic ns1/ns2/ns3 prefixes)")
    print("  5. ✓ Inverse relationships for bidirectional queries")
    print("\n")
