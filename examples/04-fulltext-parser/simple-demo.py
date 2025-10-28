#!/usr/bin/env python3
"""
Simple demonstration of the full text XML parser with local fixture files.

This script shows how to parse an existing XML file and extract various
information from it.
"""

from pathlib import Path
from pyeuropepmc import FullTextXMLParser


def main():
    print("=== Full Text XML Parser Simple Demo ===\n")

    # Use fixture file from tests
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "fulltext_downloads"
    xml_file = fixtures_dir / "PMC3258128.xml"

    if not xml_file.exists():
        print(f"Fixture file not found: {xml_file}")
        print("This demo requires test fixture files to be present.")
        return

    print(f"Reading XML from: {xml_file}\n")

    # Read the XML content
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # Create parser instance and parse the XML
    parser = FullTextXMLParser(xml_content)

    # Extract metadata
    print("1. Metadata:")
    print("-" * 60)
    metadata = parser.extract_metadata()
    print(f"PMC ID:     {metadata['pmcid']}")
    print(f"DOI:        {metadata['doi']}")
    print(f"Title:      {metadata['title']}")
    print(f"Authors:    {', '.join(metadata['authors'][:3])}")
    if len(metadata['authors']) > 3:
        print(f"            ... and {len(metadata['authors']) - 3} more authors")
    print(f"Journal:    {metadata['journal']}")
    print(f"Date:       {metadata['pub_date']}")
    print(f"Volume:     {metadata['volume']}, Issue: {metadata['issue']}")
    if metadata['abstract']:
        abstract_preview = metadata['abstract'][:150]
        print(f"Abstract:   {abstract_preview}...")
    print()

    # Extract tables
    print("2. Tables:")
    print("-" * 60)
    tables = parser.extract_tables()
    print(f"Found {len(tables)} table(s)")
    for i, table in enumerate(tables[:2], 1):
        print(f"\nTable {i}: {table['label']}")
        if table['caption']:
            caption_preview = table['caption'][:80]
            print(f"Caption: {caption_preview}...")
        print(f"Dimensions: {len(table['headers'])} columns × {len(table['rows'])} rows")
        if table['headers']:
            print(f"Headers: {', '.join(table['headers'][:5])}")
    print()

    # Extract sections
    print("3. Body Sections:")
    print("-" * 60)
    sections = parser.get_full_text_sections()
    print(f"Found {len(sections)} section(s)")
    for section in sections[:5]:
        if section['title']:
            content_words = len(section['content'].split())
            print(f"- {section['title']} ({content_words} words)")
    print()

    # Convert to different formats
    print("4. Format Conversions:")
    print("-" * 60)

    # Plaintext
    plaintext = parser.to_plaintext()
    print(f"Plaintext: {len(plaintext)} characters")
    print(f"Preview: {plaintext[:100]}...")
    print()

    # Markdown
    markdown = parser.to_markdown()
    print(f"Markdown: {len(markdown)} characters")
    markdown_lines = markdown.split('\n')
    print(f"First few lines:")
    for line in markdown_lines[:5]:
        if line.strip():
            print(f"  {line[:70]}")
    print()

    # Extract references
    print("5. References:")
    print("-" * 60)
    references = parser.extract_references()
    print(f"Found {len(references)} reference(s)")
    for i, ref in enumerate(references[:3], 1):
        print(f"\n[{ref['label']}] ", end="")
        if ref['authors']:
            print(f"{ref['authors'][:40]}...", end=" ")
        if ref['title']:
            print(f"'{ref['title'][:50]}...'", end=" ")
        if ref['source'] and ref['year']:
            print(f"{ref['source']} ({ref['year']})")
        else:
            print()

    print("\n" + "=" * 60)
    print("Demo complete! The parser can extract:")
    print("✓ Metadata (title, authors, journal info)")
    print("✓ Abstract and full text sections")
    print("✓ Tables with headers and data")
    print("✓ References and citations")
    print("✓ Convert to plaintext or markdown formats")
    print("\nUse these features for:")
    print("- Literature analysis and text mining")
    print("- Data extraction for meta-analysis")
    print("- Content conversion and reuse")
    print("- Citation network analysis")


if __name__ == "__main__":
    main()
