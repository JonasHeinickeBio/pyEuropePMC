"""
Bulk Search Example with the Semantic Scholar Library Wrapper

This example shows ProfessionalSemanticScholarClient.search_paper() with the
bulk endpoint, relevance search and filters. Results are lists of plain dicts;
keys whose value is missing are left out, so read them with ``.get()``.
"""

from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)


def main():
    # Initialize client (an API key is optional but raises the rate limit;
    # get one at https://www.semanticscholar.org/product/api)
    client = ProfessionalSemanticScholarClient(
        api_key=None,  # or "your-api-key-here"
        rate_limit_delay=1.0,
    )

    print("=" * 60)
    print("Bulk Search Example")
    print("=" * 60)

    # Example 1: Bulk search (no relevance ranking, pages of up to 1000 papers)
    print("\n1. Bulk Search - Fast large-scale search")
    print("-" * 40)

    papers = client.search_paper(
        query="cancer immunotherapy",
        bulk=True,  # Use bulk endpoint
        limit=50,
    )
    print(f"Found {len(papers)} papers")

    for i, paper in enumerate(papers[:5], 1):
        print(f"\n{i}. {paper.get('title', 'N/A')[:60]}...")
        print(f"   Citation count: {paper.get('citation_count', 'N/A')}")
        print(f"   Year: {paper.get('year', 'N/A')}")

    # Example 2: Regular search with relevance ranking
    print("\n\n2. Regular Search - Relevance-ranked results")
    print("-" * 40)

    papers = client.search_paper(
        query="cancer immunotherapy",
        bulk=False,  # Use standard search with relevance ranking
        limit=100,
    )
    print(f"Found {len(papers)} papers")

    # Example 3: Search with filters
    print("\n\n3. Advanced Search with Filters")
    print("-" * 40)

    papers = client.search_paper(
        query="cancer",
        year="2023",  # Restrict to 2023
        publication_types=["JournalArticle"],  # Semantic Scholar's type names
        min_citation_count=10,  # Minimum 10 citations
        limit=50,
    )
    print(f"Found {len(papers)} papers (2023, journal articles, >=10 citations)")

    for i, paper in enumerate(papers[:5], 1):
        print(f"\n{i}. {paper.get('title', 'N/A')[:60]}...")
        print(f"   Citation count: {paper.get('citation_count', 'N/A')}")

    # Example 4: Get paper details
    print("\n\n4. Get Paper Details")
    print("-" * 40)

    paper = client.get_paper("DOI:10.1038/nature12373")
    if paper:
        print(f"Title: {paper.get('title')}")
        print(f"Authors: {len(paper.get('authors', []))}")
        print(f"Year: {paper.get('year')}")
        print(f"Citation count: {paper.get('citation_count')}")
        print(f"Fields of study: {paper.get('fields_of_study')}")

    # Example 5: Get author information
    print("\n\n5. Get Author Information")
    print("-" * 40)

    author = client.get_author("1724609")
    if author:
        print(f"Author: {author.get('name')}")
        print(f"Paper count: {author.get('paper_count')}")
        print(f"Citation count: {author.get('citation_count')}")
        print(f"H-index: {author.get('h_index')}")


if __name__ == "__main__":
    main()
