"""
SearchClient Caching Demo
=========================

This demo shows how to use the SearchClient with optional caching
to improve performance and reduce API load.
"""

from pyeuropepmc.search import SearchClient
from pyeuropepmc.cache import CacheConfig


def demo_without_cache():
    """Basic usage without caching (default behavior)."""
    print("=" * 60)
    print("Demo 1: SearchClient WITHOUT caching (default)")
    print("=" * 60)

    # Default behavior - no caching
    client = SearchClient()

    # Each search makes a fresh API request
    result1 = client.search("cancer", pageSize=5)
    result2 = client.search("cancer", pageSize=5)  # Makes another API request

    print(f"First result count: {result1.get('hitCount', 0)}")
    print(f"Second result count: {result2.get('hitCount', 0)}")
    print("Note: Both searches hit the API (no caching)")

    client.close()
    print()


def demo_with_default_cache():
    """Usage with default cache settings (24h TTL, 500MB limit)."""
    print("=" * 60)
    print("Demo 2: SearchClient WITH default caching")
    print("=" * 60)

    # Enable caching with defaults
    cache_config = CacheConfig(enabled=True)
    client = SearchClient(cache_config=cache_config)

    # First search - cache miss
    print("First search (cache miss)...")
    result1 = client.search("diabetes", pageSize=5)

    # Second search - cache hit!
    print("Second search (cache hit)...")
    result2 = client.search("diabetes", pageSize=5)

    # Get cache statistics
    stats = client.get_cache_stats()
    print(f"\nCache Statistics:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit rate: {stats['hit_rate']:.2%}")
    print(f"  Cache size: {stats['size_mb']:.2f} MB")
    print(f"  Entries: {stats['entry_count']}")

    client.close()
    print()


def demo_with_custom_cache():
    """Usage with custom cache settings."""
    print("=" * 60)
    print("Demo 3: SearchClient WITH custom cache settings")
    print("=" * 60)

    # Custom cache configuration
    cache_config = CacheConfig(
        enabled=True,
        ttl=3600,  # 1 hour TTL
        size_limit_mb=100,  # 100 MB limit
    )
    client = SearchClient(cache_config=cache_config)

    # Perform some searches
    queries = ["malaria", "tuberculosis", "influenza"]

    for query in queries:
        result = client.search(query, pageSize=5)
        print(f"Search '{query}': {result.get('hitCount', 0)} results")

    # Check cache health
    health = client.get_cache_health()
    print(f"\nCache Health:")
    print(f"  Status: {health['status']}")
    print(f"  Size utilization: {health['size_utilization']:.2%}")
    print(f"  Warnings: {health['warnings'] if health['warnings'] else 'None'}")

    client.close()
    print()


def demo_cache_management():
    """Demonstrate cache management features."""
    print("=" * 60)
    print("Demo 4: Cache Management")
    print("=" * 60)

    cache_config = CacheConfig(enabled=True)
    client = SearchClient(cache_config=cache_config)

    # Perform several searches
    print("Performing multiple searches...")
    for query in ["cancer", "diabetes", "covid"]:
        client.search(query, pageSize=5)

    stats = client.get_cache_stats()
    print(f"Cache has {stats['entry_count']} entries")

    # Invalidate specific pattern
    print("\nInvalidating 'cancer' searches...")
    count = client.invalidate_search_cache("search:*cancer*")
    print(f"Invalidated {count} entries")

    # Clear entire cache
    print("\nClearing all cache...")
    client.clear_cache()

    stats = client.get_cache_stats()
    print(f"Cache now has {stats['entry_count']} entries")

    client.close()
    print()


def demo_context_manager():
    """Demonstrate using SearchClient as a context manager with caching."""
    print("=" * 60)
    print("Demo 5: Context Manager with Caching")
    print("=" * 60)

    cache_config = CacheConfig(enabled=True)

    # Using context manager ensures proper cleanup
    with SearchClient(cache_config=cache_config) as client:
        # Perform searches
        result = client.search("pneumonia", pageSize=10)
        print(f"Found {result.get('hitCount', 0)} results")

        # Cache is automatically closed when exiting context

    print("Client and cache closed automatically")
    print()


def demo_performance_comparison():
    """Compare performance with and without caching."""
    import time

    print("=" * 60)
    print("Demo 6: Performance Comparison")
    print("=" * 60)

    query = "BRCA1 AND breast cancer"

    # Without cache
    print("Without cache:")
    client_no_cache = SearchClient()

    start = time.time()
    for _ in range(3):
        client_no_cache.search(query, pageSize=25)
    elapsed_no_cache = time.time() - start

    print(f"  3 searches took {elapsed_no_cache:.2f}s (all hit API)")
    client_no_cache.close()

    # With cache
    print("\nWith cache:")
    cache_config = CacheConfig(enabled=True)
    client_with_cache = SearchClient(cache_config=cache_config)

    start = time.time()
    for i in range(3):
        client_with_cache.search(query, pageSize=25)
    elapsed_with_cache = time.time() - start

    print(f"  3 searches took {elapsed_with_cache:.2f}s (1 API call, 2 from cache)")

    speedup = elapsed_no_cache / elapsed_with_cache if elapsed_with_cache > 0 else float('inf')
    print(f"  Speedup: {speedup:.2f}x faster")

    client_with_cache.close()
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SearchClient Caching Demonstration")
    print("=" * 60 + "\n")

    try:
        demo_without_cache()
        demo_with_default_cache()
        demo_with_custom_cache()
        demo_cache_management()
        demo_context_manager()
        demo_performance_comparison()

        print("=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()
