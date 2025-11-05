"""
Demonstration of caching capabilities across all pyEuropePMC clients.

This example shows how to use caching with SearchClient, ArticleClient,
and FullTextClient to improve performance and reduce API load.
"""
import time
from pyeuropepmc.search import SearchClient
from pyeuropepmc.article import ArticleClient
from pyeuropepmc.fulltext import FullTextClient
from pyeuropepmc.cache import CacheConfig


def demo_search_client_caching():
    """Demonstrate SearchClient caching."""
    print("\n" + "=" * 60)
    print("SearchClient Caching Demo")
    print("=" * 60)

    # Configure cache with 1 hour TTL and 100MB size limit
    cache_config = CacheConfig(
        enabled=True,
        ttl=3600,  # 1 hour
        size_limit_mb=100,
    )

    client = SearchClient(cache_config=cache_config)

    try:
        query = "malaria AND drug resistance"

        # First search - should hit API
        print(f"\n1. First search for: '{query}'")
        start = time.time()
        results = client.search(query, pageSize=10)
        elapsed1 = time.time() - start
        print(f"   Time: {elapsed1:.3f}s")
        print(f"   Results: {results.get('hitCount', 0)} total hits")

        # Second search - should use cache
        print(f"\n2. Second search (cached): '{query}'")
        start = time.time()
        results = client.search(query, pageSize=10)
        elapsed2 = time.time() - start
        print(f"   Time: {elapsed2:.3f}s")
        print(f"   Speedup: {elapsed1/elapsed2:.1f}x faster")

        # Check cache health
        health = client.get_cache_health()
        print(f"\n3. Cache health:")
        print(f"   Hit rate: {health.get('hit_rate', 0):.2%}")
        print(f"   Total hits: {health.get('hits', 0)}")
        print(f"   Total misses: {health.get('misses', 0)}")

        # Get cache stats
        stats = client.get_cache_stats()
        print(f"\n4. Cache statistics:")
        print(f"   Size: {stats.get('size', 0)} bytes")
        print(f"   Items: {stats.get('count', 0)}")

    finally:
        client.close()


def demo_article_client_caching():
    """Demonstrate ArticleClient caching."""
    print("\n" + "=" * 60)
    print("ArticleClient Caching Demo")
    print("=" * 60)

    # Configure cache
    cache_config = CacheConfig(enabled=True, ttl=7200)  # 2 hours
    client = ArticleClient(cache_config=cache_config)

    try:
        source = "MED"
        article_id = "25883711"

        # First request - should hit API
        print(f"\n1. First request for article {source}:{article_id}")
        start = time.time()
        details = client.get_article_details(source, article_id)
        elapsed1 = time.time() - start
        print(f"   Time: {elapsed1:.3f}s")
        print(f"   Title: {details.get('result', {}).get('title', 'N/A')[:60]}...")

        # Second request - should use cache
        print(f"\n2. Second request (cached)")
        start = time.time()
        details = client.get_article_details(source, article_id)
        elapsed2 = time.time() - start
        print(f"   Time: {elapsed2:.3f}s")
        print(f"   Speedup: {elapsed1/elapsed2:.1f}x faster")

        # Get citations (will cache)
        print(f"\n3. Getting citations for {source}:{article_id}")
        start = time.time()
        citations = client.get_citations(source, article_id)
        elapsed3 = time.time() - start
        print(f"   Time: {elapsed3:.3f}s")
        print(f"   Citations found: {citations.get('hitCount', 0)}")

        # Check cache health
        health = client.get_cache_health()
        print(f"\n4. Cache health:")
        print(f"   Hit rate: {health.get('hit_rate', 0):.2%}")
        print(f"   Total operations: {health.get('hits', 0) + health.get('misses', 0)}")

        # Invalidate cache for specific article
        print(f"\n5. Invalidating cache for {source}:{article_id}")
        count = client.invalidate_article_cache(source=source, article_id=article_id)
        print(f"   Invalidated {count} cache entries")

    finally:
        client.close()


def demo_fulltext_client_caching():
    """Demonstrate FullTextClient caching."""
    print("\n" + "=" * 60)
    print("FullTextClient Caching Demo")
    print("=" * 60)

    # Configure API response cache
    cache_config = CacheConfig(enabled=True, ttl=86400)  # 24 hours

    # FullTextClient has both file cache and API response cache
    client = FullTextClient(
        enable_cache=True,  # File cache for downloads
        cache_config=cache_config  # API response cache
    )

    try:
        pmcid = "3312970"

        # First availability check - should hit API
        print(f"\n1. First availability check for PMC{pmcid}")
        start = time.time()
        availability = client.check_fulltext_availability(pmcid)
        elapsed1 = time.time() - start
        print(f"   Time: {elapsed1:.3f}s")
        print(f"   PDF available: {availability.get('pdf', False)}")
        print(f"   XML available: {availability.get('xml', False)}")
        print(f"   HTML available: {availability.get('html', False)}")

        # Second check - should use cache
        print(f"\n2. Second availability check (cached)")
        start = time.time()
        availability = client.check_fulltext_availability(pmcid)
        elapsed2 = time.time() - start
        print(f"   Time: {elapsed2:.3f}s")
        print(f"   Speedup: {elapsed1/elapsed2:.1f}x faster")

        # Check API response cache health
        health = client.get_api_cache_health()
        print(f"\n3. API response cache health:")
        print(f"   Hit rate: {health.get('hit_rate', 0):.2%}")
        print(f"   Total hits: {health.get('hits', 0)}")
        print(f"   Total misses: {health.get('misses', 0)}")

        # Note: File cache is separate
        print(f"\n4. File cache info:")
        print(f"   Enabled: {client.enable_cache}")
        print(f"   Directory: {client.cache_dir}")

    finally:
        client.close()


def demo_cache_management():
    """Demonstrate cache management across clients."""
    print("\n" + "=" * 60)
    print("Cache Management Demo")
    print("=" * 60)

    cache_config = CacheConfig(enabled=True)

    # Initialize all clients with caching
    search_client = SearchClient(cache_config=cache_config)
    article_client = ArticleClient(cache_config=cache_config)
    fulltext_client = FullTextClient(cache_config=cache_config)

    try:
        # Perform some operations to populate caches
        print("\n1. Populating caches with sample requests...")
        search_client.search("cancer", pageSize=5)
        article_client.get_article_details("MED", "25883711")
        fulltext_client.check_fulltext_availability("3312970")

        # Check cache stats for each client
        print("\n2. Cache statistics:")

        search_stats = search_client.get_cache_stats()
        print(f"\n   SearchClient cache:")
        print(f"   - Items: {search_stats.get('count', 0)}")
        print(f"   - Size: {search_stats.get('size', 0)} bytes")

        article_stats = article_client.get_cache_stats()
        print(f"\n   ArticleClient cache:")
        print(f"   - Items: {article_stats.get('count', 0)}")
        print(f"   - Size: {article_stats.get('size', 0)} bytes")

        fulltext_stats = fulltext_client.get_api_cache_stats()
        print(f"\n   FullTextClient API cache:")
        print(f"   - Items: {fulltext_stats.get('count', 0)}")
        print(f"   - Size: {fulltext_stats.get('size', 0)} bytes")

        # Clear all caches
        print("\n3. Clearing all caches...")
        search_client.clear_cache()
        article_client.clear_cache()
        fulltext_client.clear_api_cache()
        print("   All caches cleared!")

    finally:
        search_client.close()
        article_client.close()
        fulltext_client.close()


def main():
    """Run all caching demos."""
    print("\n" + "=" * 60)
    print("pyEuropePMC Caching Demonstration")
    print("=" * 60)
    print("\nThis demo shows caching capabilities across all clients:")
    print("- SearchClient: Cache search results")
    print("- ArticleClient: Cache article details, citations, references")
    print("- FullTextClient: Cache availability checks + file downloads")

    try:
        demo_search_client_caching()
        demo_article_client_caching()
        demo_fulltext_client_caching()
        demo_cache_management()

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print("\nKey takeaways:")
        print("✓ Caching is disabled by default (backward compatible)")
        print("✓ Enable with CacheConfig(enabled=True)")
        print("✓ Configure TTL, size limits, eviction policy")
        print("✓ Monitor with get_cache_stats() and get_cache_health()")
        print("✓ Manage with clear_cache() and invalidate_* methods")
        print("✓ Typical speedup: 100-1000x for cached responses")

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
