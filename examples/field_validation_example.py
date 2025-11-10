#!/usr/bin/env python3
"""
Example: Field Validation and Coverage Check

This example demonstrates how to validate that the QueryBuilder's
field definitions are up-to-date with the Europe PMC API.
"""

from pyeuropepmc.query_builder import (
    QueryBuilder,
    get_available_fields,
    validate_field_coverage,
)


def main() -> None:
    """Run field validation examples."""
    print("Europe PMC Query Builder - Field Validation Examples")
    print("=" * 70)

    # Example 1: Get available fields from API
    print("\n1. Fetching available fields from Europe PMC API...")
    try:
        fields = get_available_fields()
        print(f"   ✓ Found {len(fields)} fields")
        print(f"   Sample fields: {', '.join(fields[:10])}...")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Example 2: Validate field coverage
    print("\n2. Validating field coverage...")
    try:
        result = validate_field_coverage(verbose=False)
        print(f"   API Fields: {result['total_api_fields']}")
        print(f"   Defined Fields: {result['total_defined_fields']}")
        print(f"   Coverage: {result['coverage_percent']}%")
        print(f"   Up to date: {'✓' if result['up_to_date'] else '✗'}")

        if not result["up_to_date"]:
            print(f"\n   Missing fields ({len(result['missing_in_code'])}):")
            for field in result["missing_in_code"]:
                print(f"     - {field}")

        if result["extra_in_code"]:
            print(f"\n   Extra fields ({len(result['extra_in_code'])}):")
            print("   (These may be documented but not in API response)")
            for field in result["extra_in_code"][:5]:  # Show first 5
                print(f"     - {field}")
            if len(result["extra_in_code"]) > 5:
                print(f"     ... and {len(result['extra_in_code']) - 5} more")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Example 3: Using field aliases
    print("\n3. Demonstrating field aliases...")
    print("   Europe PMC supports both full and abbreviated field names:")

    qb = QueryBuilder(validate=False)

    # Using full name
    query1 = qb.keyword("Smith", field="author").build()
    print(f"   Full name:  {query1}")

    # Using abbreviated name (AUTH)
    qb2 = QueryBuilder(validate=False)
    query2 = qb2.keyword("Smith", field="auth").build()
    print(f"   Abbrev:     {query2}")

    # More examples
    examples = [
        ("affiliation", "aff"),
        ("language", "lang"),
        ("keyword", "kw"),
        ("chemical", "chem"),
    ]

    print("\n   Other field aliases:")
    for full, abbr in examples:
        print(f"     {full:15} ↔ {abbr}")

    # Example 4: Comprehensive validation (verbose)
    print("\n4. Running comprehensive validation (verbose)...")
    print("-" * 70)
    try:
        validate_field_coverage(verbose=True)
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 70)
    print("Examples complete!")


if __name__ == "__main__":
    main()
