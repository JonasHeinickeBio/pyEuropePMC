#!/usr/bin/env python3
"""
Demonstration of the full text XML parser functionality.

This script shows how to:
1. Download full text XML from Europe PMC
2. Parse XML and extract metadata
3. Convert XML to different formats (plaintext, markdown)
4. Extract tables and references
5. Extract full text sections
"""

from pathlib import Path
from pyeuropepmc import FullTextClient, FullTextXMLParser


def main():
    print("=== Europe PMC Full Text XML Parser Demo ===\n")

    # Create downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    # Initialize the full text client
    with FullTextClient() as client:
        # Example PMC ID - a well-known open access article
        pmcid = "PMC3258128"

        print(f"1. Downloading XML for {pmcid}...")
        xml_path = client.download_xml_by_pmcid(pmcid, downloads_dir / f"{pmcid}.xml")

        if xml_path:
            print(f"   ✓ Downloaded to: {xml_path}\n")

            # Read the XML content
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Create parser instance
            parser = FullTextXMLParser(xml_content)

            # 2. Extract metadata
            print("2. Extracting Metadata:")
            metadata = parser.extract_metadata()
            print(f"   Title: {metadata['title']}")
            print(f"   Authors: {', '.join(metadata['authors'][:3])}")
            if len(metadata['authors']) > 3:
                print(f"            ... and {len(metadata['authors']) - 3} more")
            print(f"   Journal: {metadata['journal']}")
            print(f"   DOI: {metadata['doi']}")
            print(f"   Publication Date: {metadata['pub_date']}")
            print(f"   Volume: {metadata['volume']}, Issue: {metadata['issue']}")
            print(f"   Pages: {metadata['pages']}")
            if metadata['keywords']:
                print(f"   Keywords: {', '.join(metadata['keywords'])}")
            print()

            # 3. Convert to plaintext
            print("3. Converting to Plaintext:")
            plaintext = parser.to_plaintext()
            plaintext_path = downloads_dir / f"{pmcid}_plaintext.txt"
            with open(plaintext_path, 'w', encoding='utf-8') as f:
                f.write(plaintext)
            print(f"   ✓ Saved plaintext to: {plaintext_path}")
            print(f"   Preview (first 200 chars):")
            print(f"   {plaintext[:200]}...\n")

            # 4. Convert to markdown
            print("4. Converting to Markdown:")
            markdown = parser.to_markdown()
            markdown_path = downloads_dir / f"{pmcid}.md"
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            print(f"   ✓ Saved markdown to: {markdown_path}")
            print(f"   Preview (first 200 chars):")
            print(f"   {markdown[:200]}...\n")

            # 5. Extract tables
            print("5. Extracting Tables:")
            tables = parser.extract_tables()
            print(f"   Found {len(tables)} table(s)")
            for i, table in enumerate(tables[:3], 1):  # Show first 3 tables
                print(f"\n   Table {i}:")
                print(f"   - Label: {table['label']}")
                print(f"   - Caption: {table['caption'][:80] if table['caption'] else 'N/A'}...")
                print(f"   - Columns: {len(table['headers'])}")
                print(f"   - Rows: {len(table['rows'])}")
                if table['headers']:
                    print(f"   - Headers: {', '.join(table['headers'][:3])}")
            print()

            # 6. Extract references
            print("6. Extracting References:")
            references = parser.extract_references()
            print(f"   Found {len(references)} reference(s)")
            for i, ref in enumerate(references[:5], 1):  # Show first 5 references
                print(f"\n   Reference {i}:")
                print(f"   - Authors: {ref['authors'][:50] if ref['authors'] else 'N/A'}...")
                print(f"   - Title: {ref['title'][:60] if ref['title'] else 'N/A'}...")
                print(f"   - Source: {ref['source']} ({ref['year']})")
            print()

            # 7. Extract full text sections
            print("7. Extracting Full Text Sections:")
            sections = parser.get_full_text_sections()
            print(f"   Found {len(sections)} section(s)")
            for i, section in enumerate(sections[:3], 1):  # Show first 3 sections
                print(f"\n   Section {i}: {section['title']}")
                content_preview = section['content'][:100] if section['content'] else ''
                print(f"   Content: {content_preview}...")
            print()

            # 8. Demonstrate use case: Extract abstract for further processing
            print("8. Use Case - Extract Abstract for Analysis:")
            abstract = metadata['abstract']
            if abstract:
                word_count = len(abstract.split())
                print(f"   Abstract word count: {word_count}")
                print(f"   First sentence: {abstract.split('.')[0]}.")
            print()

        else:
            print(f"   ✗ Failed to download XML for {pmcid}")

    print("=== Demo Complete ===")
    print(f"All files saved to: {downloads_dir.absolute()}")
    print("\nYou can now use the parser to:")
    print("- Extract structured data for analysis")
    print("- Convert articles to different formats for reuse")
    print("- Extract tables for data mining")
    print("- Process references for citation analysis")
    print("- Extract sections for text mining and NLP tasks")


if __name__ == "__main__":
    main()
