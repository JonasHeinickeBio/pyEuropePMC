#!/usr/bin/env python3
"""
Example script demonstrating PyEuropePMC usage.

This script shows various ways to use PyEuropePMC to search
and retrieve scientific literature from Europe PMC.
"""

import logging
import pprint
from typing import Any, Dict, List, Optional

# Import the main classes
from pyeuropepmc.search import EuropePMCError, SearchClient

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def basic_search_example() -> None:
    """Demonstrate basic search functionality."""
    print("\n=== Basic Search Example ===")

    with SearchClient(rate_limit_delay=0.5) as client:
        try:
            # Simple search
            results: Dict[str, Any] = client.search(
                "CRISPR gene editing", page_size=5, format="json"
            )  # type: ignore

            print(f"Found {results.get('hitCount', 0)} total papers")
            print(f"Retrieved {len(results.get('resultList', {}).get('result', []))} papers")

            # Display first few results
            for i, paper in enumerate(results.get("resultList", {}).get("result", [])[:3]):
                print(f"\n{i + 1}. {paper.get('title', 'No title')}")
                print(f"   Authors: {paper.get('authorString', 'N/A')}")
                print(f"   Journal: {paper.get('journalTitle', 'N/A')}")
                print(f"   Year: {paper.get('pubYear', 'N/A')}")

            # Show raw output of the first result
            if results.get("resultList", {}).get("result", []):
                print("\nRaw output of first result:")
                first_result: Dict[str, Any] = results.get("resultList", {}).get("result", [])[0]
                pprint.pprint(first_result)

        except EuropePMCError as e:
            print(f"Search failed: {e}")


def advanced_search_example() -> None:
    """Demonstrate advanced search with parsing."""
    print("\n=== Advanced Search with Parsing ===")

    with SearchClient() as client:
        try:
            # Search and parse results automatically
            papers: List[Dict[str, Any]] = client.search_and_parse(
                query="COVID-19 AND vaccine",
                format="json",
                pageSize=10,
                sort="CITED desc",  # Most cited first
            )

            print(f"Retrieved {len(papers)} papers")

            # Display top cited papers
            for i, paper in enumerate(papers[:5]):
                citations: int = paper.get("citedByCount", 0)
                print(f"\n{i + 1}. [{citations} citations] {paper.get('title', 'No title')}")
                print(f"   DOI: {paper.get('doi', 'N/A')}")

        except EuropePMCError as e:
            print(f"Advanced search failed: {e}")


def pagination_example() -> None:
    """Demonstrate automatic pagination for large result sets."""
    print("\n=== Pagination Example ===")

    with SearchClient() as client:
        try:
            # Fetch multiple pages automatically
            all_papers: List[Dict[str, Any]] = client.fetch_all_pages(
                query="machine learning bioinformatics",
                page_size=25,
                max_results=100,  # Limit to 100 papers total
            )

            print(f"Retrieved {len(all_papers)} papers across multiple pages")

            # Analyze publication years
            years: Dict[str, int] = {}
            for paper in all_papers:
                year: Optional[str] = paper.get("pubYear")
                if year:
                    years[year] = years.get(year, 0) + 1

            print("\nPublication years distribution:")
            for year in sorted(years.keys(), reverse=True)[:5]:
                print(f"  {year}: {years[year]} papers")

        except EuropePMCError as e:
            print(f"Pagination example failed: {e}")


def search_parameters_example() -> None:
    """Demonstrate various search parameters."""
    print("\n=== Search Parameters Example ===")

    with SearchClient() as client:
        try:
            # Search with specific parameters
            results: Dict[str, Any] = client.search(
                query='AUTHOR:"Smith J" AND JOURNAL:"Nature"',
                resultType="core",  # Get full metadata
                pageSize=5,
                format="json",
            )  # type: ignore

            papers: List[Dict[str, Any]] = results.get("resultList", {}).get("result", [])
            print(f"Found {len(papers)} papers by 'Smith J' in 'Nature'")

            for paper in papers:
                print(f"\n- {paper.get('title', 'No title')}")
                abstract: str = paper.get("abstractText", "N/A")
                print(f"  Abstract: {abstract[:100]}...")

        except EuropePMCError as e:
            print(f"Parameter search failed: {e}")


def get_hit_count_example() -> None:
    """Demonstrate getting hit counts without retrieving results."""
    print("\n=== Hit Count Example ===")

    with SearchClient() as client:
        queries: List[str] = [
            "artificial intelligence",
            "CRISPR",
            "COVID-19",
            "climate change biology",
        ]

        for query in queries:
            try:
                count: int = client.get_hit_count(query)
                print(f"'{query}': {count:,} papers")
            except EuropePMCError as e:
                print(f"Failed to get count for '{query}': {e}")


def error_handling_example() -> None:
    """Demonstrate error handling."""
    print("\n=== Error Handling Example ===")

    with SearchClient() as client:
        # Try various problematic queries
        problematic_queries: List[str] = [
            "",  # Empty query
            "a",  # Too short
            'query with "unmatched quotes',  # Invalid syntax
            "normal query",  # This should work
        ]

        for query in problematic_queries:
            try:
                if client.validate_query(query):
                    results: Dict[str, Any] = client.search(query, pageSize=1)  # type: ignore
                    print(f"✓ '{query}': {results.get('hitCount', 0)} results")
                else:
                    print(f"✗ '{query}': Invalid query")
            except EuropePMCError as e:
                print(f"✗ '{query}': {e}")


def main() -> None:
    """Run all examples."""
    print("PyEuropePMC Examples")
    print("=" * 50)

    try:
        basic_search_example()
        advanced_search_example()
        pagination_example()
        search_parameters_example()
        get_hit_count_example()
        error_handling_example()

    except KeyboardInterrupt:
        print("\nExamples interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    main()
