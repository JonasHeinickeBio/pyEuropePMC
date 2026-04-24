"""
Demo script for schema coverage validation.

This script demonstrates how to use the validate_schema_coverage() method
to analyze XML documents and identify unrecognized element types.
"""
from pathlib import Path

from pyeuropepmc import FullTextXMLParser


def main():
    """Run schema coverage analysis on a sample XML file."""
    # Load sample XML file
    xml_path = Path(__file__).parent.parent / "downloads" / "PMC3258128.xml"

    if not xml_path.exists():
        print(f"❌ Sample XML file not found: {xml_path}")
        print("Please download a sample XML file first.")
        return

    print("=" * 80)
    print("Schema Coverage Validation Demo")
    print("=" * 80)

    # Parse XML
    print(f"\n📄 Loading XML: {xml_path.name}")
    with open(xml_path) as f:
        xml_content = f.read()

    parser = FullTextXMLParser(xml_content)

    # Validate schema coverage
    print("\n🔍 Analyzing schema coverage...")
    coverage = parser.validate_schema_coverage()

    # Display results
    print("\n" + "=" * 80)
    print("COVERAGE SUMMARY")
    print("=" * 80)
    print(f"Total element types:       {coverage['total_elements']}")
    print(f"Recognized elements:       {coverage['recognized_count']}")
    print(f"Unrecognized elements:     {coverage['unrecognized_count']}")
    print(f"Coverage percentage:       {coverage['coverage_percentage']:.1f}%")

    # Show recognized elements
    print("\n" + "=" * 80)
    print("RECOGNIZED ELEMENTS")
    print("=" * 80)
    print(f"Total: {len(coverage['recognized_elements'])}")
    print(", ".join(coverage['recognized_elements'][:20]))
    if len(coverage['recognized_elements']) > 20:
        print(f"... and {len(coverage['recognized_elements']) - 20} more")

    # Show unrecognized elements with frequency
    if coverage['unrecognized_elements']:
        print("\n" + "=" * 80)
        print("UNRECOGNIZED ELEMENTS (with frequency)")
        print("=" * 80)

        # Sort by frequency (most common first)
        unrecognized_with_freq = [
            (elem, coverage['element_frequency'][elem])
            for elem in coverage['unrecognized_elements']
        ]
        unrecognized_with_freq.sort(key=lambda x: x[1], reverse=True)

        for elem, freq in unrecognized_with_freq[:20]:
            print(f"  {elem:40s} {freq:5d} occurrences")

        if len(unrecognized_with_freq) > 20:
            print(f"\n  ... and {len(unrecognized_with_freq) - 20} more unrecognized elements")

        # Recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print("Consider adding patterns for frequently occurring unrecognized elements:")
        for elem, freq in unrecognized_with_freq[:5]:
            if freq >= 5:
                print(f"  • {elem} ({freq} occurrences)")
    else:
        print("\n✅ All elements are recognized by the current configuration!")

    # Element frequency analysis
    print("\n" + "=" * 80)
    print("MOST COMMON ELEMENTS (top 20)")
    print("=" * 80)

    # Sort all elements by frequency
    all_elements_freq = sorted(
        coverage['element_frequency'].items(),
        key=lambda x: x[1],
        reverse=True
    )

    for elem, freq in all_elements_freq[:20]:
        status = "✓" if elem in coverage['recognized_elements'] else "✗"
        print(f"  {status} {elem:40s} {freq:5d} occurrences")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
