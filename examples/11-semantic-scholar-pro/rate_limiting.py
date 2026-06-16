"""
Rate Limiting Example with Professional Semantic Scholar Library

This example demonstrates how to properly configure rate limiting for different
use cases and how to handle rate limit errors gracefully.
"""

import time
from pyeuropepmc.enrichment import ProfessionalSemanticScholarClient


def main():
    print("=" * 60)
    print("Rate Limiting Example")
    print("=" * 60)

    # Example 1: Low volume (hobby projects)
    print("\n\n1. Low Volume Configuration (2.0s delay)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(
        api_key="your-api-key-here",
        rate_limit_delay=2.0  # 2 seconds between requests
    )

    start_time = time.time()
    paper1 = client.get_paper("10.1038/nature12373")
    elapsed1 = time.time() - start_time

    print(f"Single request took: {elapsed1:.2f}s")
    print(f"Rate limit delay: 2.0s")
    print(f"Estimated papers/hour: ~1800")

    # Example 2: Medium volume (research projects)
    print("\n\n2. Medium Volume Configuration (1.0s delay)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(
        api_key="your-api-key-here",
        rate_limit_delay=1.0  # 1 second between requests
    )

    start_time = time.time()
    paper2 = client.get_paper("10.1038/nature12373")
    elapsed2 = time.time() - start_time

    print(f"Single request took: {elapsed2:.2f}s")
    print(f"Rate limit delay: 1.0s")
    print(f"Estimated papers/hour: ~3600")

    # Example 3: High volume (production, with caching)
    print("\n\n3. High Volume Configuration (0.5s delay + caching)")
    print("-" * 40)

    from pyeuropepmc.cache.cache import CacheConfig

    client = ProfessionalSemanticScholarClient(
        api_key="your-api-key-here",
        rate_limit_delay=0.5,  # 0.5 seconds between requests
        cache_config=CacheConfig(enabled=True, ttl=86400)  # Cache for 24 hours
    )

    # First request (cache miss)
    start_time = time.time()
    paper3a = client.get_paper("10.1038/nature12373")
    elapsed3a = time.time() - start_time
    print(f"First request (cache miss): {elapsed3a:.2f}s")

    # Second request (cache hit - instant)
    start_time = time.time()
    paper3b = client.get_paper("10.1038/nature12373")
    elapsed3b = time.time() - start_time
    print(f"Second request (cache hit): {elapsed3b:.4f}s")

    print(f"Rate limit delay: 0.5s")
    print(f"Caching: Enabled (24h TTL)")
    print(f"Estimated papers/hour: ~7200")

    # Example 4: Bulk search (minimize API calls)
    print("\n\n4. Bulk Search (Minimal API Calls)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(
        api_key="your-api-key-here",
        rate_limit_delay=1.0
    )

    # Single bulk search for 500 papers (1 API call)
    start_time = time.time()
    results = client.search_paper("cancer", bulk=True, limit=500)
    papers = list(results)
    elapsed_bulk = time.time() - start_time

    print(f"Bulk search took: {elapsed_bulk:.2f}s")
    print(f"API calls: 1")
    print(f"Papers retrieved: {len(papers)}")
    print(f"Estimated time for 500 papers: {elapsed_bulk:.2f}s")

    # Compare with regular search
    print("\n\nComparison: Bulk vs Regular Search")
    print("-" * 40)
    print(f"Bulk search (1 API call, ~{elapsed_bulk:.2f}s): ✅ Recommended for large datasets")
    print(f"Regular search (100+ API calls, ~100s+): ⚠️ Use for small result sets")


if __name__ == "__main__":
    main()
