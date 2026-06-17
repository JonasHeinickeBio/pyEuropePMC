"""
Typed Response Example with Professional Semantic Scholar Library

This example demonstrates how to use the professional library's typed response
objects for type-safe development with IDE autocomplete.
"""

from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient


def main():
    # Initialize client
    client = ProfessionalSemanticScholarClient(
        api_key="your-api-key-here",
        rate_limit_delay=1.0
    )

    print("=" * 60)
    print("Typed Response Example")
    print("=" * 60)

    # Get a paper with typed response
    paper = client.get_paper("10.1038/nature12373")

    print("\nPaper Information (Typed Response)")
    print("-" * 40)
    print(f"Title: {paper.title}")
    print(f"DOI: {paper.doi}")
    print(f"Year: {paper.year}")
    print(f"Citation count: {paper.citation_count}")
    print(f"Influential citation count: {paper.influential_citation_count}")
    print(f"Open access: {paper.is_open_access}")
    print(f"Fields of study: {paper.fields_of_study}")

    # Access author objects
    print(f"\nAuthors ({len(paper.authors)} total):")
    for i, author in enumerate(paper.authors, 1):
        print(f"\n  {i}. {author.name}")
        print(f"     Author ID: {author.author_id}")
        print(f"     Position: {author.position}")
        print(f"     Affiliation: {author.affiliation}")

    # Access venue information
    if paper.venue:
        print(f"\nVenue:")
        print(f"  Name: {paper.venue.name}")
        print(f"  Type: {paper.venue.venue_type}")
        print(f"  Pages: {paper.venue.pages}")

    # Example 2: Get author with typed response
    print("\n\n" + "=" * 60)
    print("Author Information (Typed Response)")
    print("=" * 60)

    author = client.get_author("1724609")

    print(f"\nAuthor: {author.name}")
    print(f"Author ID: {author.author_id}")
    print(f"Paper count: {author.paper_count}")
    print(f"H-index: {author.h_index}")
    print(f"i10-index: {author.i10_index}")

    # Example 3: Get venue with typed response
    print("\n\n" + "=" * 60)
    print("Venue Information (Typed Response)")
    print("=" * 60)

    # Get a venue (using a known venue ID)
    try:
        venue = client.get_venue("12345")
        print(f"\nVenue: {venue.name}")
        print(f"Venue ID: {venue.venue_id}")
        print(f"Paper count: {venue.paper_count}")
    except Exception as e:
        print(f"\nVenue lookup failed (venue ID may not exist): {e}")


if __name__ == "__main__":
    main()
