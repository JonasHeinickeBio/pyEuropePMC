"""
Demo: Load, Save, and Translate Queries

This example demonstrates the advanced features of QueryBuilder for working
with queries across different platforms and formats.

Features demonstrated:
- Building and saving queries to JSON files
- Loading queries from JSON files
- Translating queries between platforms (PubMed, Web of Science, etc.)
- Round-trip workflow (load, translate, save)

Requirements:
- search-query package: pip install search-query
"""

import tempfile
from pathlib import Path

from pyeuropepmc import QueryBuilder


def demo_save_query():
    """Demonstrate saving a query to a JSON file."""
    print("=" * 70)
    print("Demo 1: Building and Saving a Query")
    print("=" * 70)

    # Build a simple query (avoid Europe PMC-specific syntax for demo)
    qb = QueryBuilder()
    query = qb.keyword("CRISPR", field="title").and_().keyword("treatment")

    print("\nBuilt query:")
    print(f"  {query.build()}")

    # Save to temporary file
    # Note: We skip include_generic=True because QueryBuilder uses Europe PMC
    # syntax which differs from PubMed and may not parse cleanly
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        qb.save(
            tmp_path,
            platform="pubmed",
            authors=[{"name": "Demo User", "ORCID": "0000-0000-0000-0000"}],
            date_info={"search_conducted": "2025-11-06"},
            database=["PubMed", "PMC"],
            record_info={"project": "CRISPR Research Review"},
            include_generic=False,  # Disabled due to Europe PMC vs PubMed syntax differences
        )

        print(f"\n✓ Saved to: {tmp_path}")

        # Read and display contents
        with open(tmp_path) as f:
            import json

            data = json.load(f)
            print("\nSaved file contents:")
            print(f"  Platform: {data['platform']}")
            print(f"  Query: {data['search_string']}")
            print(f"  Authors: {data['authors']}")

    finally:
        # Clean up
        Path(tmp_path).unlink()


def demo_load_query():
    """Demonstrate loading a query from a JSON file."""
    print("\n" + "=" * 70)
    print("Demo 2: Loading a Query from File")
    print("=" * 70)

    # Create a sample query file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        import json

        query_data = {
            "search_string": "cancer AND treatment",
            "platform": "pubmed",
            "version": "1",
            "authors": [{"name": "Jane Smith"}],
            "date": {"search_conducted": "2025-01-01"},
            "database": ["PubMed"],
            "record_info": {},
        }
        json.dump(query_data, tmp)
        tmp_path = tmp.name

    try:
        # Load the query
        qb = QueryBuilder.from_file(tmp_path)

        print(f"\n✓ Loaded from: {tmp_path}")
        print(f"  Query: {qb.build()}")

    finally:
        # Clean up
        Path(tmp_path).unlink()


def demo_load_from_string():
    """Demonstrate loading a query from a string."""
    print("\n" + "=" * 70)
    print("Demo 3: Loading a Query from String")
    print("=" * 70)

    # PubMed syntax - use full field names that search-query recognizes
    pubmed_query = "cancer AND treatment"
    print(f"\nOriginal PubMed query: {pubmed_query}")

    qb = QueryBuilder.from_string(pubmed_query, platform="pubmed")

    print(f"✓ Loaded and parsed successfully")
    print(f"  Rebuilt query: {qb.build()}")


def demo_translate_query():
    """Demonstrate translating a query between platforms."""
    print("\n" + "=" * 70)
    print("Demo 4: Translating Query Between Platforms")
    print("=" * 70)

    # Create a simple PubMed query
    pubmed_query = "cancer AND treatment"
    print(f"\nOriginal PubMed query: {pubmed_query}")

    qb = QueryBuilder.from_string(pubmed_query, platform="pubmed")

    # Translate to Web of Science
    wos_query = qb.translate("wos")
    print(f"\n✓ Translated to Web of Science:")
    print(f"  {wos_query}")

    # You can also translate to other platforms
    try:
        ebsco_query = qb.translate("ebsco")
        print(f"\n✓ Translated to EBSCO:")
        print(f"  {ebsco_query}")
    except Exception as e:
        print(f"\n⚠ EBSCO translation: {e}")


def demo_round_trip_workflow():
    """Demonstrate a complete load-translate-save workflow."""
    print("\n" + "=" * 70)
    print("Demo 5: Round-Trip Workflow (Load → Translate → Save)")
    print("=" * 70)

    # Create initial PubMed query file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp1:
        import json

        query_data = {
            "search_string": "cancer AND treatment",
            "platform": "pubmed",
            "version": "1",
            "authors": [{"name": "Researcher A"}],
            "date": {},
            "record_info": {},
        }
        json.dump(query_data, tmp1)
        tmp_path1 = tmp1.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp2:
        tmp_path2 = tmp2.name

    try:
        # Step 1: Load PubMed query
        print("\n1. Loading PubMed query from file...")
        qb_pubmed = QueryBuilder.from_file(tmp_path1)
        print(f"   Query: {qb_pubmed.build()}")

        # Step 2: Translate to Web of Science
        print("\n2. Translating to Web of Science...")
        wos_query = qb_pubmed.translate("wos")
        print(f"   Translated: {wos_query}")

        # Step 3: Create new QueryBuilder with WoS query
        print("\n3. Creating new QueryBuilder with WoS query...")
        qb_wos = QueryBuilder.from_string(wos_query, platform="wos")

        # Step 4: Save WoS version
        print("\n4. Saving Web of Science version...")
        qb_wos.save(
            tmp_path2,
            platform="wos",
            authors=[{"name": "Researcher A"}],
        )

        # Verify
        with open(tmp_path2) as f:
            data = json.load(f)
            print(f"\n✓ Saved WoS query to: {tmp_path2}")
            print(f"  Platform: {data['platform']}")
            print(f"  Query: {data['search_string']}")

    finally:
        # Clean up
        Path(tmp_path1).unlink()
        Path(tmp_path2).unlink()


def demo_to_query_object():
    """Demonstrate converting to search-query Query objects."""
    print("\n" + "=" * 70)
    print("Demo 6: Converting to Query Objects")
    print("=" * 70)

    # Build a query
    qb = QueryBuilder()
    query = qb.keyword("cancer").and_().keyword("treatment")

    print(f"\nBuilt query: {query.build()}")

    # Convert to Query object
    query_obj = qb.to_query_object()

    print(f"\n✓ Converted to Query object")
    print(f"  Type: {type(query_obj).__name__}")
    print(f"  Has evaluate method: {hasattr(query_obj, 'evaluate')}")
    print(f"  Has to_string method: {hasattr(query_obj, 'to_string')}")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("QueryBuilder Load/Save/Translate Demo")
    print("=" * 70)
    print("\nThis demo shows how to:")
    print("  • Save queries to JSON files with metadata")
    print("  • Load queries from JSON files")
    print("  • Load queries from strings")
    print("  • Translate queries between platforms")
    print("  • Perform round-trip workflows")
    print("  • Convert to Query objects for advanced use")

    try:
        demo_save_query()
        demo_load_query()
        demo_load_from_string()
        demo_translate_query()
        demo_round_trip_workflow()
        demo_to_query_object()

        print("\n" + "=" * 70)
        print("All demos completed successfully!")
        print("=" * 70)

    except ImportError as e:
        print(f"\n❌ Error: {e}")
        print("\nTo use these features, install the search-query package:")
        print("  pip install search-query")


if __name__ == "__main__":
    main()
