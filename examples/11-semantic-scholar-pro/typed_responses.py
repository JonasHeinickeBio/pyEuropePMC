"""
Paper and Author Responses with the Semantic Scholar Library Wrapper

This example shows what ProfessionalSemanticScholarClient returns. The client
wraps the danielnsilva/semanticscholar library but converts its typed Paper
and Author objects to plain dicts, so read the values with ``[]`` / ``.get()``.
Keys whose value is missing are left out of the dicts.
"""

from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)


def main():
    # Initialize client (an API key is optional but raises the rate limit)
    client = ProfessionalSemanticScholarClient(
        api_key=None,  # or "your-api-key-here"
        rate_limit_delay=1.0,
    )

    print("=" * 60)
    print("Paper Information")
    print("=" * 60)

    paper = client.get_paper("DOI:10.1038/nature12373")
    if paper is None:
        print("Paper not found")
        return

    external_ids = paper.get("external_ids", {})
    print(f"Title: {paper.get('title')}")
    print(f"DOI: {external_ids.get('DOI')}")
    print(f"Semantic Scholar ID: {paper.get('s2_paper_id')}")
    print(f"Year: {paper.get('year')}")
    print(f"Citation count: {paper.get('citation_count')}")
    print(f"Influential citation count: {paper.get('influential_citation_count')}")
    print(f"Open access PDF: {paper.get('open_access_pdf_url', 'none')}")
    print(f"Fields of study: {paper.get('fields_of_study')}")

    # Authors are dicts with author_id, name and, when known, affiliations
    authors = paper.get("authors", [])
    print(f"\nAuthors ({len(authors)} total):")
    for i, author in enumerate(authors, 1):
        print(f"\n  {i}. {author.get('name')}")
        print(f"     Author ID: {author.get('author_id')}")
        print(f"     Affiliations: {author.get('affiliations', [])}")

    # Venue: a name string, plus journal details when available
    journal = paper.get("journal", {})
    print("\nVenue:")
    print(f"  Name: {paper.get('venue') or journal.get('name')}")
    print(f"  Volume: {journal.get('volume')}")
    print(f"  Pages: {journal.get('pages')}")

    print("\n\n" + "=" * 60)
    print("Author Information")
    print("=" * 60)

    author = client.get_author("1724609")
    if author is None:
        print("Author not found")
        return

    print(f"\nAuthor: {author.get('name')}")
    print(f"Author ID: {author.get('author_id')}")
    print(f"Paper count: {author.get('paper_count')}")
    print(f"Citation count: {author.get('citation_count')}")
    print(f"H-index: {author.get('h_index')}")
    print(f"Homepage: {author.get('homepage')}")


if __name__ == "__main__":
    main()
