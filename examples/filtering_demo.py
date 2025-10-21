"""
Example demonstrating the filter_pmc_papers utility for filtering Europe PMC search results.

This example shows how to use advanced filtering to find high-quality papers
based on various criteria including citations, MeSH terms, keywords, and abstract content.
"""

from pyeuropepmc import SearchClient, filter_pmc_papers


def main():
    """Demonstrate filtering capabilities."""
    # Initialize the search client
    client = SearchClient()

    print("=" * 80)
    print("Europe PMC Advanced Filtering Example")
    print("=" * 80)

    # Perform a broad search
    query = "cancer immunotherapy"
    print(f"\n1. Performing broad search: '{query}'")

    # Use resultType="core" to get full metadata including MeSH terms
    response = client.search(query, pageSize=100, resultType="core")

    # Handle response format
    papers = []
    if isinstance(response, dict):
        papers = response.get("resultList", {}).get("result", [])
    print(f"   Found {len(papers)} papers in total")

    # Example 1: Filter for high-quality review papers
    print("\n2. Filtering for high-quality reviews (>10 citations, 2020+, open access)")
    filtered_reviews = filter_pmc_papers(
        papers,
        min_citations=10,
        min_pub_year=2020,
        allowed_types=("Review", "Systematic Review"),
        open_access="Y",
    )

    print(f"   Found {len(filtered_reviews)} high-quality review papers")
    if filtered_reviews:
        print("\n   Top 3 results:")
        for i, paper in enumerate(filtered_reviews[:3], 1):
            print(f"\n   {i}. {paper['title']}")
            print(f"      Year: {paper['pubYear']}, Citations: {paper['citedByCount']}")
            print(f"      Authors: {', '.join(paper['authors'][:3])}")
            if paper["keywords"]:
                print(f"      Keywords: {', '.join(paper['keywords'][:5])}")

    # Example 2: Filter by MeSH terms (partial matching)
    print("\n3. Filtering by MeSH terms (requires 'neoplasms' and 'immunotherapy')")
    filtered_mesh = filter_pmc_papers(
        papers,
        min_citations=5,
        required_mesh={"neoplasm", "immuno"},  # Partial matching
    )

    print(f"   Found {len(filtered_mesh)} papers with required MeSH terms")
    if filtered_mesh:
        sample = filtered_mesh[0]
        print(f"\n   Example paper: {sample['title']}")
        print(f"   MeSH terms: {', '.join(sample['meshHeadings'][:5])}")

    # Example 3: Filter by keywords (partial matching)
    print("\n4. Filtering by keywords (checkpoint inhibitors)")
    filtered_keywords = filter_pmc_papers(
        papers,
        min_citations=5,
        required_keywords={"checkpoint", "inhibitor"},
    )

    print(f"   Found {len(filtered_keywords)} papers with required keywords")
    if filtered_keywords:
        sample = filtered_keywords[0]
        print(f"\n   Example paper: {sample['title']}")
        print(f"   Keywords: {', '.join(sample['keywords'])}")

    # Example 4: Filter by abstract content
    print("\n5. Filtering by abstract content (clinical trial + efficacy + safety)")
    filtered_abstract = filter_pmc_papers(
        papers,
        min_citations=3,
        required_abstract_terms={"clinical trial", "efficacy", "safety"},
    )

    print(f"   Found {len(filtered_abstract)} papers with required abstract terms")
    if filtered_abstract:
        sample = filtered_abstract[0]
        print(f"\n   Example paper: {sample['title']}")
        print(f"   Abstract snippet: {sample['abstractText'][:200]}...")

    # Example 5: Combine multiple filters
    print("\n6. Combining multiple filters for precision")
    print("   (citations>20, year>=2021, reviews, open access, specific keywords)")

    filtered_combined = filter_pmc_papers(
        papers,
        min_citations=20,
        min_pub_year=2021,
        allowed_types=("Review", "Systematic Review"),
        open_access="Y",
        required_keywords={"immuno"},
        required_abstract_terms={"therapy"},
    )

    print(f"   Found {len(filtered_combined)} papers meeting all criteria")
    if filtered_combined:
        print("\n   Top results:")
        for i, paper in enumerate(filtered_combined[:2], 1):
            print(f"\n   {i}. {paper['title']}")
            print(f"      Year: {paper['pubYear']}, Citations: {paper['citedByCount']}")
            print(f"      Type: {paper['pubType']}")
            print(f"      Open Access: {paper['isOpenAccess']}")
            print(f"      PMID: {paper.get('pmid', 'N/A')}, DOI: {paper.get('doi', 'N/A')}")

    # Summary statistics
    print("\n" + "=" * 80)
    print("Summary Statistics")
    print("=" * 80)
    print(f"Total papers found: {len(papers)}")
    print(f"High-quality reviews: {len(filtered_reviews)}")
    print(f"Papers with specific MeSH: {len(filtered_mesh)}")
    print(f"Papers with specific keywords: {len(filtered_keywords)}")
    print(f"Papers with abstract terms: {len(filtered_abstract)}")
    print(f"Papers meeting all criteria: {len(filtered_combined)}")

    print("\n" + "=" * 80)
    print("Filtering Tips:")
    print("=" * 80)
    print("1. Use partial matching for flexibility (e.g., 'immuno' matches 'immunotherapy')")
    print("2. Combine filters to narrow results to high-quality papers")
    print("3. Adjust min_citations based on field (some fields have lower citation rates)")
    print("4. Use resultType='core' to get MeSH terms and full metadata")
    print("5. MeSH terms are more standardized than keywords for biomedical topics")
    print("=" * 80)


if __name__ == "__main__":
    main()
