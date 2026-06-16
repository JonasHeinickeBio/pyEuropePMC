"""
Integration Example: Combine Professional Semantic Scholar with Other APIs

This example demonstrates how to combine the professional Semantic Scholar library
with other enrichment sources (CrossRef, OpenAlex, Unpaywall) for comprehensive
paper enrichment.
"""

from pyeuropepmc import PaperEnricher, EnrichmentConfig


def main():
    # Configure enrichment with multiple sources
    config = EnrichmentConfig(
        enable_crossref=True,
        enable_unpaywall=True,
        enable_semantic_scholar=True,
        enable_openalex=True,
        rate_limit_delay=1.0,
        unpaywall_email="your@email.com",
        crossref_email="your@email.com",
        openalex_email="your@email.com"
    )

    with PaperEnricher(config) as enricher:
        # Enrich a paper with multiple sources
        paper_doi = "10.1038/nature12373"
        result = enricher.enrich_paper(doi=paper_doi)

        print("=" * 60)
        print(f"Enrichment Results for DOI: {paper_doi}")
        print("=" * 60)

        # Access merged data (priority: CrossRef > OpenAlex)
        print("\nMerged Data (Combined from all sources)")
        print("-" * 40)

        merged = result['merged']
        print(f"Title: {merged.get('title', 'N/A')}")
        print(f"Authors: {merged.get('author_string', 'N/A')[:100]}...")
        print(f"Journal: {merged.get('journal_title', 'N/A')}")
        print(f"Year: {merged.get('pub_year', 'N/A')}")
        print(f"Citation count: {merged.get('citation_count', 'N/A')}")

        # Open access status
        if merged.get('open_access_status'):
            print(f"OA Status: {merged['open_access_status']}")
            print(f"OA URL: {merged.get('oa_url', 'N/A')[:60]}...")

        # Topics/Fields of study
        if merged.get('topics'):
            print(f"Topics: {merged['topics'][:5]}...")
        if merged.get('fields_of_study'):
            print(f"Fields: {merged['fields_of_study'][:5]}...")

        # Source breakdown
        print("\n\nSource Breakdown")
        print("-" * 40)

        for source, data in result.items():
            if source != 'merged':
                print(f"\n{source.upper()}:")
                if data:
                    print(f"  Title: {data.get('title', 'N/A')[:60]}...")
                    print(f"  Citation count: {data.get('citation_count', 'N/A')}")
                else:
                    print("  No data available")

        # Example 2: Enrich multiple papers
        print("\n\n" + "=" * 60)
        print("Batch Enrichment")
        print("=" * 60)

        dois = [
            "10.1038/nature12373",
            "10.1038/nature12374",  # Example DOI
            "10.1038/nature12375",  # Example DOI
        ]

        for i, doi in enumerate(dois, 1):
            print(f"\n{i}. Enriching: {doi}")
            try:
                result = enricher.enrich_paper(doi=doi)
                title = result['merged'].get('title', 'N/A')[:60]
                citations = result['merged'].get('citation_count', 'N/A')
                print(f"   Title: {title}...")
                print(f"   Citations: {citations}")
            except Exception as e:
                print(f"   Error: {e}")


if __name__ == "__main__":
    main()
