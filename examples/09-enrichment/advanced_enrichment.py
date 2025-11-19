"""
Advanced example demonstrating enrichment with all APIs and caching.

This example shows how to:
1. Enable all APIs including Unpaywall
2. Use caching for better performance
3. Configure API-specific settings
4. Handle missing or partial data
"""

import os
from pyeuropepmc import PaperEnricher, EnrichmentConfig
from pyeuropepmc.cache.cache import CacheConfig

# Example DOIs to enrich
DOIS = [
    "10.1371/journal.pone.0308090",
    "10.1038/s41586-020-2649-2",  # Nature paper
    "10.1126/science.abc4577",  # Science paper
]


def main():
    """Demonstrate advanced enrichment with caching."""
    print("=" * 80)
    print("Advanced Paper Metadata Enrichment Example")
    print("=" * 80)

    # Get email from environment variable for Unpaywall
    unpaywall_email = os.getenv("UNPAYWALL_EMAIL", "your-email@example.com")
    print(f"\nUsing email for Unpaywall: {unpaywall_email}")

    # Configure caching for better performance
    cache_config = CacheConfig(
        enabled=True,
        ttl=86400,  # Cache for 24 hours
        size_limit_mb=100,
    )

    # Configure enrichment with ALL APIs
    config = EnrichmentConfig(
        enable_crossref=True,
        enable_unpaywall=True,
        enable_semantic_scholar=True,
        enable_openalex=True,
        # API-specific settings
        unpaywall_email=unpaywall_email,
        crossref_email=unpaywall_email,  # Polite pool for CrossRef
        openalex_email=unpaywall_email,  # Polite pool for OpenAlex
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
        # Cache and rate limiting
        cache_config=cache_config,
        rate_limit_delay=1.0,
    )

    # Create enricher
    with PaperEnricher(config) as enricher:
        print(f"\nEnricher initialized with {len(enricher.clients)} clients:")
        for client_name in enricher.clients.keys():
            print(f"  - {client_name}")

        for i, doi in enumerate(DOIS, 1):
            print("\n" + "=" * 80)
            print(f"Paper {i}: {doi}")
            print("=" * 80)

            try:
                # Enrich the paper
                result = enricher.enrich_paper(doi=doi)

                # Check which sources provided data
                sources = result.get("sources", [])
                print(f"\n✓ Successfully enriched from {len(sources)} sources: {', '.join(sources)}")

                # Display key metadata
                merged = result.get("merged", {})

                if "title" in merged:
                    title = merged["title"]
                    print(f"\nTitle: {title[:80]}...")

                if "citation_count" in merged:
                    print(f"Total Citations: {merged['citation_count']}")

                    # Show citation counts from different sources
                    if "citation_counts" in merged:
                        print("  By source:")
                        for cite in merged["citation_counts"]:
                            print(f"    {cite['source']}: {cite['count']}")

                # Open access information
                if "is_oa" in merged:
                    if merged["is_oa"]:
                        print(f"✓ Open Access: {merged.get('oa_status', 'unknown')}")
                        if merged.get("oa_url"):
                            print(f"  Full text: {merged['oa_url']}")
                    else:
                        print("✗ Not Open Access")

                # Additional metrics from Semantic Scholar
                if "influential_citation_count" in merged:
                    print(f"Influential Citations: {merged['influential_citation_count']}")

                # Topics/concepts from OpenAlex
                if "topics" in merged and merged["topics"]:
                    print("\nTop Topics:")
                    for topic in merged["topics"][:3]:
                        if isinstance(topic, dict):
                            name = topic.get("display_name", "Unknown")
                            score = topic.get("score", 0)
                            print(f"  - {name} (relevance: {score:.2f})")

                # Funding information from CrossRef
                if "funders" in merged and merged["funders"]:
                    print(f"\nFunding: {len(merged['funders'])} funder(s)")
                    for funder in merged["funders"][:2]:
                        if isinstance(funder, dict):
                            print(f"  - {funder.get('name', 'Unknown')}")

            except Exception as e:
                print(f"\n✗ Error enriching {doi}: {e}")
                continue

    print("\n" + "=" * 80)
    print("All papers enriched!")
    print("=" * 80)
    print("\nNote: Set environment variables for better results:")
    print("  - UNPAYWALL_EMAIL: Your email for Unpaywall API")
    print("  - SEMANTIC_SCHOLAR_API_KEY: API key for higher rate limits")


if __name__ == "__main__":
    main()
