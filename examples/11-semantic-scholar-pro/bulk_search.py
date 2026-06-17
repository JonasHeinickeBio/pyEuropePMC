"""
Bulk Search Example with Professional Semantic Scholar Library

This example demonstrates how to use the professional library's bulk search
feature for efficient large-scale literature mining.
"""

from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient


def main():
    # Initialize client with API key (optional but recommended)
    client = ProfessionalSemanticScholarClient(
        api_key="your-api-key-here",  # Get free API key from https://www.semanticscholar.org/product/api
        rate_limit_delay=1.0
    )

    print("=" * 60)
    print("Bulk Search Example")
    print("=" * 60)

    # Example 1: Bulk search (fast, no relevance ranking, up to 10M results)
    print("\n1. Bulk Search - Fast large-scale search")
    print("-" * 40)

    results = client.search_paper(
        query="cancer immunotherapy",
        bulk=True,  # Use bulk endpoint
        limit=50
    )

    papers = list(results)  # Convert PaginatedResults to list
    print(f"Found {len(papers)} papers")

    for i, paper in enumerate(papers[:5], 1):
        print(f"\n{i}. {paper.get('title', 'N/A')[:60]}...")
        print(f"   Citation count: {paper.get('citation_count', 'N/A')}")
        print(f"   Year: {paper.get('year', 'N/A')}")

    # Example 2: Regular search with relevance ranking
    print("\n\n2. Regular Search - Relevance-ranked results")
    print("-" * 40)

    results = client.search_paper(
        query="cancer immunotherapy",
        bulk=False,  # Use standard search with relevance ranking
        limit=100
    )

    papers = list(results)
    print(f"Found {len(papers)} papers")

    # Example 3: Search with filters
    print("\n\n3. Advanced Search with Filters")
    print("-" * 40)

    results = client.search_paper(
        query="cancer",
        year="2023",  # Restrict to 2023
        publication_types=["journal-article"],
        min_citation_count=10,  # Minimum 10 citations
        limit=50
    )

    papers = list(results)
    print(f"Found {len(papers)} papers (2023, journal articles, >=10 citations)")

    for i, paper in enumerate(papers[:5], 1):
        print(f"\n{i}. {paper.get('title', 'N/A')[:60]}...")
        print(f"   Citation count: {paper.get('citation_count', 'N/A')}")

    # Example 4: Get paper details with typed response
    print("\n\n4. Get Paper with Typed Response")
    print("-" * 40)

    # Get a paper by DOI
    paper = client.get_paper("10.1038/nature12373")

    print(f"Title: {paper.title}")
    print(f"Authors: {len(paper.authors)}")
    print(f"Year: {paper.year}")
    print(f"Citation count: {paper.citation_count}")
    print(f"Fields of study: {paper.fields_of_study}")

    # Example 5: Get author information
    print("\n\n5. Get Author Information")
    print("-" * 40)

    author = client.get_author("1724609")
    print(f"Author: {author.name}")
    print(f"Paper count: {author.paper_count}")
    print(f"H-index: {author.h_index}")
    print(f"i10-index: {author.i10_index}")


if __name__ == "__main__":
    main()
