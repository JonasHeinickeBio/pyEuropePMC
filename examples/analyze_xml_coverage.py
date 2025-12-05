#!/usr/bin/env python3
"""
XML Element Coverage Analysis for PyEuropePMC

This script analyzes the coverage of XML elements found in the benchmark
against what the XML parser and RDF mapper handle.
"""

from pathlib import Path


def load_benchmark_elements() -> set[str]:
    """Load the unique XML elements found during benchmarking."""
    benchmark_file = Path(__file__).parent / "benchmark_output" / "xml_element_types.txt"

    elements = set()
    with open(benchmark_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("Total:"):
                elements.add(line)

    return elements


def load_parser_config_elements() -> dict[str, set[str]]:
    """Extract elements that the XML parser is configured to handle."""
    # This is a manual extraction based on the element_patterns.py file
    # In a real implementation, this would parse the config dynamically

    parser_elements = {
        "citation_types": {"element-citation", "mixed-citation", "nlm-citation", "citation"},
        "author_elements": {"contrib", "name", "author-group", "author"},
        "author_fields": {
            "surname",
            "given-names",
            "suffix",
            "prefix",
            "role",
            "family",
            "last-name",
            "lname",
            "given-name",
            "given",
            "forename",
            "first-name",
            "fname",
        },
        "journal_fields": {
            "journal-title",
            "source",
            "journal",
            "issn",
            "publisher-name",
            "publisher",
            "publisher-loc",
            "publisher-location",
            "volume",
            "vol",
            "issue",
        },
        "article_fields": {
            "article-title",
            "title",
            "abstract",
            "kwd",
            "keyword",
            "doi",
            "pmid",
            "pmcid",
            "article-id",
        },
        "table_elements": {
            "table-wrap",
            "table-wrapper",
            "tbl-wrap",
            "table",
            "caption",
            "label",
            "thead",
            "th",
            "tbody",
            "tr",
            "td",
        },
        "reference_fields": {
            "article-title",
            "source",
            "journal",
            "publication",
            "year",
            "date",
            "month",
            "day",
            "volume",
            "vol",
            "issue",
            "fpage",
            "first-page",
            "lpage",
            "last-page",
            "pub-id",
            "ext-link",
            "person-group",
            "etal",
        },
        "inline_elements": {"sup", "sub", "italic", "bold", "underline"},
        "xref_elements": {"xref"},
        "media_elements": {"supplementary-material", "media", "graphic", "inline-graphic"},
        "object_ids": {"object-id", "article-id"},
        # Additional elements from specialized parsers
        "section_elements": {
            "sec",
            "title",
            "p",
            "list",
            "list-item",
            "def-list",
            "def-item",
            "boxed-text",
            "disp-quote",
            "verse-group",
            "table-wrap-group",
            "fig",
            "fig-group",
            "supplementary-material",
            "ack",
            "app-group",
            "app",
            "glossary",
            "notes",
            "fn-group",
            "fn",
        },
        "metadata_elements": {
            "front",
            "article-meta",
            "title-group",
            "article-categories",
            "pub-date",
            "permissions",
            "license",
            "license-p",
            "copyright-statement",
            "copyright-year",
            "copyright-holder",
            "self-uri",
            "journal-meta",
            "journal-title-group",
            "issn",
            "publisher",
            "publisher-loc",
            "publisher-name",
            "article-version",
            "custom-meta-group",
            "custom-meta",
            "meta-name",
            "meta-value",
            "processing-meta",
            "history",
            "pub-history",
            "event",
            "event-desc",
        },
        "affiliation_elements": {
            "aff",
            "addr-line",
            "city",
            "state",
            "postal-code",
            "country",
            "institution",
            "institution-wrap",
            "institution-id",
            "email",
            "phone",
            "fax",
            "uri",
        },
        "funding_elements": {
            "funding-group",
            "funding-source",
            "funding-statement",
            "award-group",
            "award-id",
            "principal-award-recipient",
        },
    }

    return parser_elements


def load_rdf_mapped_entities() -> set[str]:
    """Extract entity types that the RDF mapper handles."""
    # These are the high-level entities, not XML elements
    rdf_entities = {
        "ScholarlyWorkEntity",
        "PaperEntity",
        "AuthorEntity",
        "SectionEntity",
        "TableEntity",
        "TableRowEntity",
        "ReferenceEntity",
        "InstitutionEntity",
        "JournalEntity",
        "GrantEntity",
    }

    return rdf_entities


def analyze_coverage():
    """Analyze XML element coverage across components."""
    print("=== PyEuropePMC XML Element Coverage Analysis ===\n")

    # Load data
    benchmark_elements = load_benchmark_elements()
    parser_config = load_parser_config_elements()
    rdf_entities = load_rdf_mapped_entities()

    print(f"Total unique XML elements found in benchmark: {len(benchmark_elements)}")
    print(f"XML parser configuration categories: {len(parser_config)}")
    print(f"RDF mapper entity types: {len(rdf_entities)}")
    print()

    # Flatten parser elements
    all_parser_elements = set()
    for _category, elements in parser_config.items():
        all_parser_elements.update(elements)

    print(f"Total XML elements configured for parsing: {len(all_parser_elements)}")
    print()

    # Coverage analysis
    parser_covered = benchmark_elements.intersection(all_parser_elements)
    parser_uncovered = benchmark_elements - all_parser_elements

    covered_count = len(parser_covered)
    total_count = len(benchmark_elements)
    covered_pct = covered_count / total_count * 100

    uncovered_count = len(parser_uncovered)
    uncovered_pct = uncovered_count / total_count * 100

    print("=== Coverage Analysis ===")
    print(f"Elements covered by XML parser: {covered_count}/{total_count} ({covered_pct:.1f}%)")
    print(f"Elements NOT covered: {uncovered_count}/{total_count} ({uncovered_pct:.1f}%)")
    print()

    # Category breakdown
    print("=== Parser Coverage by Category ===")
    for category, elements in parser_config.items():
        category_covered = benchmark_elements.intersection(elements)
        if category_covered:
            coverage_pct = len(category_covered) / len(elements) * 100
            found = len(category_covered)
            total = len(elements)
            print(f"{category}: {found}/{total} elements found ({coverage_pct:.1f}%)")
            if len(category_covered) < len(elements):
                missing = elements - benchmark_elements
                print(f"  Missing from benchmark: {sorted(missing)}")
    print()

    # Uncovered elements analysis
    print("=== Uncovered Elements Analysis ===")
    print(f"Elements not handled by current parser ({len(parser_uncovered)}):")
    sorted_uncovered = sorted(parser_uncovered)

    # Group by potential categories
    math_patterns = [
        "math",
        "mml",
        "mfenced",
        "mfrac",
        "mi",
        "mn",
        "mo",
        "mover",
        "mrow",
        "mspace",
        "msqrt",
        "mstyle",
        "msub",
        "msubsup",
        "msup",
        "mtable",
        "mtd",
        "mtext",
        "mtr",
        "munder",
        "munderover",
    ]
    math_elements = {e for e in sorted_uncovered if any(x in e for x in math_patterns)}

    format_patterns = [
        "break",
        "hr",
        "strike",
        "string-",
        "styled-",
        "tex-math",
        "word-count",
        "equation-count",
        "figure-count",
        "table-count",
    ]
    formatting_elements = {e for e in sorted_uncovered if any(x in e for x in format_patterns)}

    meta_patterns = [
        "alt-",
        "anonymous",
        "article-version",
        "conf-",
        "edition",
        "elocation-id",
        "event",
        "free_to_read",
        "issue-id",
        "issue-title",
        "journal-id",
        "named-content",
        "on-behalf-of",
        "part-title",
        "restricted-by",
        "season",
        "series",
        "string-name",
        "subj-group",
        "subject",
        "subtitle",
        "version",
    ]
    metadata_elements = {e for e in sorted_uncovered if any(x in e for x in meta_patterns)}

    content_patterns = [
        "ack",
        "app-group",
        "app",
        "back",
        "body",
        "boxed-text",
        "caption",
        "col",
        "colgroup",
        "comment",
        "compound-",
        "custom-meta",
        "def",
        "disp-formula",
        "disp-quote",
        "fig-group",
        "floats-group",
        "glossary",
        "inline-supplementary-material",
        "label",
        "list",
        "list-item",
        "named-content",
        "notes",
        "p",
        "permissions",
        "processing-meta",
        "related-",
        "role",
        "sc",
        "statement",
        "support-group",
    ]
    content_elements = {e for e in sorted_uncovered if any(x in e for x in content_patterns)}

    other_count = (
        len(sorted_uncovered)
        - len(math_elements)
        - len(formatting_elements)
        - len(metadata_elements)
        - len(content_elements)
    )

    print(f"Mathematical notation elements: {len(math_elements)}")
    print(f"Formatting/layout elements: {len(formatting_elements)}")
    print(f"Additional metadata elements: {len(metadata_elements)}")
    print(f"Content structure elements: {len(content_elements)}")
    print(f"Other/miscellaneous elements: {other_count}")
    print()

    # Show some examples
    print("Sample uncovered elements:")
    for elem in sorted(sorted_uncovered)[:20]:  # Show first 20
        print(f"  - {elem}")
    if len(sorted_uncovered) > 20:
        print(f"  ... and {len(sorted_uncovered) - 20} more")
    print()

    # RDF mapping note
    print("=== RDF Mapping Notes ===")
    print("The RDF mapper operates at the entity level, not XML element level.")
    print(f"It handles {len(rdf_entities)} entity types: {sorted(rdf_entities)}")
    print("XML elements are parsed into these entities, which are then mapped to RDF.")
    print("Coverage gaps at XML level may not affect RDF output if elements are not")
    print("needed for the target entity structures.")


if __name__ == "__main__":
    analyze_coverage()
