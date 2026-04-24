#!/usr/bin/env python3
"""
XML Element Type Analyzer for Europe PMC Full Text Articles

This script analyzes XML files from Europe PMC and generates documentation
of all XML element types found, with explanations based on JATS schema.

Usage:
    python analyze_xml_elements.py <xml_file_path> [output_file]

Arguments:
    xml_file_path: Path to the XML file to analyze
    output_file: Optional output file path (default: xml_element_analysis.md)
"""

import os
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser


def collect_element_examples(root) -> dict[str, list[str]]:
    """Collect example text content for each element type."""
    examples = {}

    if root is None:
        return examples

    for elem in root.iter():
        tag = elem.tag
        if tag.startswith("{"):
            tag = tag.split("}", 1)[1]

        # Get text content, limit to first 200 characters
        text = elem.text or ""
        text = text.strip()
        if len(text) > 200:
            text = text[:200] + "..."

        # Collect up to 3 examples per element type
        if tag not in examples:
            examples[tag] = []
        if len(examples[tag]) < 3 and text:
            examples[tag].append(text)

    return examples


def analyze_xml_file(xml_path: str) -> tuple[list[str], dict[str, list[str]]]:
    """Analyze XML file and return sorted list of element types and examples."""
    with open(xml_path, encoding="utf-8") as f:
        xml_content = f.read()

    parser = FullTextXMLParser(xml_content)
    element_types = parser.list_element_types()

    # Collect examples for each element type
    examples = collect_element_examples(parser.root)

    return element_types, examples


def generate_documentation(
    element_types: list[str], source_file: str, examples: dict[str, list[str]]
) -> str:
    """Generate markdown documentation for the element types."""

    # JATS element explanations
    element_explanations = {
        # Document structure
        "article": "Root element containing the entire article",
        "front": "Contains article metadata (title, authors, abstract, etc.)",
        "body": "Contains the main article content (sections, paragraphs)",
        "back": "Contains supplementary material (references, acknowledgments, etc.)",
        # Metadata containers
        "article-meta": "Article-level metadata",
        "journal-meta": "Journal-level metadata",
        "title-group": "Container for article title elements",
        "contrib-group": "Container for author/contributor information",
        # Content elements
        "p": "Paragraph",
        "title": "Section or figure title",
        "sec": "Section container",
        "label": "Label for sections, figures, tables",
        "caption": "Caption for figures/tables",
        # Text formatting
        "bold": "Bold text formatting",
        "italic": "Italic text formatting",
        "sup": "Superscript",
        "sub": "Subscript",
        # References and citations
        "ref": "Individual reference entry",
        "ref-list": "Container for all references",
        "citation-alternatives": "Alternative citation formats",
        "element-citation": "Structured citation with XML elements",
        "mixed-citation": "Formatted citation text",
        "person-group": "Author group in citations",
        "etal": '"et al." indicator',
        "source": "Journal or source title",
        "year": "Publication year",
        "volume": "Journal volume",
        "fpage": "First page",
        "lpage": "Last page",
        "elocation-id": "Electronic location identifier",
        # Figures and tables
        "fig": "Figure container",
        "table-wrap": "Table container",
        "table": "HTML table element",
        "thead": "Table header",
        "tbody": "Table body",
        "tr": "Table row",
        "th": "Table header cell",
        "td": "Table data cell",
        "graphic": "Image reference",
        # Identifiers
        "article-id": "Article identifiers (PMCID, PMID, DOI)",
        "pub-id": "Publication identifier within citations",
        "contrib-id": "Contributor identifier (ORCID, etc.)",
        "institution-id": "Institutional identifier (ROR, etc.)",
        "journal-id": "Journal identifier",
        "award-id": "Funding award identifier",
        # Names and affiliations
        "name": "Person name container",
        "surname": "Family name",
        "given-names": "Given/first names",
        "email": "Email address",
        "aff": "Affiliation information",
        "institution": "Institutional name",
        "institution-wrap": "Institutional affiliation wrapper",
        "address": "Physical address",
        # Publication information
        "pub-date": "Publication date",
        "date": "Generic date element",
        "day": "Day of month",
        "month": "Month",
        "issn": "ISSN identifier",
        "publisher": "Publisher information",
        "publisher-name": "Publisher name",
        "publisher-loc": "Publisher location",
        # Keywords and categories
        "kwd": "Individual keyword",
        "kwd-group": "Keyword group container",
        "article-categories": "Article categorization",
        "subj-group": "Subject category group",
        "subject": "Subject category",
        # Permissions and licensing
        "permissions": "Copyright and licensing information",
        "license": "License details",
        "license-p": "License paragraph",
        "license_ref": "License reference",
        "copyright-statement": "Copyright statement",
        "copyright-year": "Copyright year",
        # Footnotes and notes
        "fn": "Footnote",
        "fn-group": "Footnote group",
        "notes": "General notes section",
        "ack": "Acknowledgments section",
        # Cross-references and links
        "xref": "Cross-reference to figures, tables, sections",
        "ext-link": "External link",
        # Funding
        "funding-group": "Funding information",
        "funding-source": "Funding source",
        "award-group": "Award group",
        "principal-award-recipient": "Principal award recipient",
        # Processing and technical
        "processing-meta": "Processing metadata",
        "restricted-by": "Access restrictions",
        "history": "Publication history",
        "custom-meta": "Custom metadata field",
        "custom-meta-group": "Custom metadata group",
        "meta-name": "Metadata field name",
        "meta-value": "Metadata field value",
    }

    doc = f"""# XML Element Types Analysis
# Generated from: {source_file}
# Total unique elements: {len(element_types)}

This document provides explanations for all XML element types found in the analyzed file.

## Element Types Found

"""

    for tag in element_types:
        explanation = element_explanations.get(tag, "No description available")
        doc += f"- **{tag}**: {explanation}\n"

        # Add examples if available
        if tag in examples and examples[tag]:
            doc += "  - Examples:\n"
            for example in examples[tag]:
                # Escape markdown characters and limit length
                example = example.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                if len(example) > 100:
                    example = example[:100] + "..."
                doc += f"    - `{example}`\n"
        doc += "\n"

    doc += f"""

## Summary

- **Total elements**: {len(element_types)}
- **Source file**: {source_file}
- **Format**: JATS (Journal Article Tag Suite)
- **Context**: Europe PMC full text article

## Notes

- This analysis is based on JATS schema standards
- Some elements may have multiple uses depending on context
- Not all possible JATS elements may be present in this specific article
"""

    return doc


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_xml_elements.py <xml_file_path> [output_file]")
        sys.exit(1)

    xml_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "xml_element_analysis.md"

    if not os.path.exists(xml_path):
        print(f"Error: File '{xml_path}' not found")
        sys.exit(1)

    try:
        element_types, examples = analyze_xml_file(xml_path)
        documentation = generate_documentation(element_types, xml_path, examples)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(documentation)

        print(f"Analysis complete. Found {len(element_types)} unique element types.")
        print(f"Documentation saved to: {output_file}")

    except Exception as e:
        print(f"Error analyzing XML file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
