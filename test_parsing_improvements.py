#!/usr/bin/env python3
"""Test script for improved affiliation parsing."""

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser


def test_postal_code_detection():
    """Test postal code detection."""
    parser = FullTextXMLParser()

    test_codes = [
        "94305",
        "BC V5Z 1L3",
        "02138",
        "SW1A 1AA",
        "12345-6789",
        "M1 1AA",
        "Toronto",  # Should not be postal
        "Canada",  # Should not be postal
    ]

    print("Testing postal code detection:")
    for code in test_codes:
        result = parser._is_postal_code(code)
        print(f"  '{code}' -> {result}")


def test_country_detection():
    """Test country detection."""
    parser = FullTextXMLParser()

    test_countries = [
        "Canada",
        "Canada.",
        "USA",
        "USA. Contact: email",
        "UK",
        "United States",
        "Toronto",  # Should not be country
        "94305",  # Should not be country
    ]

    print("\nTesting country detection:")
    for country in test_countries:
        result = parser._is_likely_country(country)
        print(f"  '{country}' -> {result}")


def test_parsing_improvements():
    """Test the improved affiliation parsing logic."""
    parser = FullTextXMLParser()

    # Test cases with problematic data
    test_cases = [
        # Case 1: Country with trailing dot
        ("University of Toronto, Toronto, Canada.", ["1"]),
        # Case 2: Postal code mistaken for city
        ("Vancouver General Hospital, BC V5Z 1L3, Canada", ["1"]),
        # Case 3: Email mixed with geographic data
        ("Harvard University, Cambridge, MA 02138, USA. Contact: john@example.com", ["1"]),
        # Case 4: Multiple institutions
        (
            "University of Toronto, Toronto, Canada and McGill University, Montreal, Canada",
            ["1", "2"],
        ),
        # Case 5: Complex case with postal code
        ("Stanford University, Stanford, CA 94305, USA", ["1"]),
    ]

    print("\nTesting parsing:")
    for text, markers in test_cases:
        print(f"\nTesting: {text}")
        result = parser._parse_multi_institution_affiliation(text, markers)
        for inst in result:
            print(f"  Marker: {inst.get('marker')}")
            print(f"  Name: {inst.get('name')}")
            print(f"  City: {inst.get('city')}")
            print(f"  State: {inst.get('state_province')}")
            print(f"  Postal: {inst.get('postal_code')}")
            print(f"  Country: {inst.get('country')}")
            if "text" in inst:
                print(f"  Raw text: {inst['text']}")


if __name__ == "__main__":
    test_postal_code_detection()
    test_country_detection()
    test_parsing_improvements()
