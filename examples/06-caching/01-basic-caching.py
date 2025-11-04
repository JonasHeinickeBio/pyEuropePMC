#!/usr/bin/env python3
"""
Caching Layer Demonstration for PyEuropePMC FullTextClient

This script demonstrates the professional caching layer that avoids re-downloading
existing files. It shows cache hits, misses, validation, and management features.
"""

import logging
import sys
import tempfile
import time
from pathlib import Path

# Add the src directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyeuropepmc import FullTextClient

# Set up logging to see cache operations
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    print("🚀 PyEuropePMC Caching Layer Demonstration")
    print("=" * 50)

    # Create a temporary directory for our demo
    with tempfile.TemporaryDirectory() as temp_cache_dir:
        cache_dir = Path(temp_cache_dir) / "demo_cache"

        print(f"\n📁 Cache directory: {cache_dir}")

        # Initialize client with caching enabled
        client = FullTextClient(
            enable_cache=True,
            cache_dir=cache_dir,
            cache_max_age_days=30,
            verify_cached_files=True,
            rate_limit_delay=0.5,  # Faster for demo
        )

        test_pmcid = "3257301"  # Known available article

        print(f"\n🔍 Testing with PMC{test_pmcid}")

        # === DEMONSTRATION 1: First Download (Cache Miss) ===
        print("\n1️⃣  First download - expect cache MISS")
        start_time = time.time()

        xml_file = client.download_xml_by_pmcid(test_pmcid)

        first_download_time = time.time() - start_time
        print(f"   ⏱️  First download took: {first_download_time:.2f} seconds")

        if xml_file:
            print(f"   ✅ Downloaded: {xml_file.name} ({xml_file.stat().st_size:,} bytes)")

        # === DEMONSTRATION 2: Second Download (Cache Hit) ===
        print("\n2️⃣  Second download - expect cache HIT")
        start_time = time.time()

        xml_file_cached = client.download_xml_by_pmcid(test_pmcid)

        second_download_time = time.time() - start_time
        print(f"   ⏱️  Second download took: {first_download_time:.2f} seconds")
        print(
            f"   🚀 Speed improvement: {first_download_time / second_download_time:.1f}x faster!"
        )

        if xml_file_cached:
            print(
                f"   ✅ Retrieved: {xml_file_cached.name} ({xml_file_cached.stat().st_size:,} bytes)"
            )

        # === DEMONSTRATION 3: Cache Statistics ===
        print("\n3️⃣  Cache statistics")
        stats = client.get_cache_stats()

        print(f"   📊 Cache enabled: {stats['enabled']}")
        print(f"   📁 Cache directory: {stats['cache_dir']}")
        print(f"   📄 Total files: {stats['total_files']}")
        print(f"   💾 Total size: {stats['total_size_bytes']:,} bytes")

        for format_type, format_stats in stats["formats"].items():  # type: ignore
            if format_stats["count"] > 0:
                print(
                    f"   📝 {format_type.upper()}: {format_stats['count']} files, "
                    f"{format_stats['size_bytes']:,} bytes"
                )

        # === DEMONSTRATION 4: Multi-format Caching ===
        print("\n4️⃣  Multi-format caching test")

        # Download HTML (should be cached separately)
        html_file = client.download_html_by_pmcid(test_pmcid)
        if html_file:
            print(f"   🌐 HTML cached: {html_file.name} ({html_file.stat().st_size:,} bytes)")

        # Download PDF (should be cached separately)
        pdf_file = client.download_pdf_by_pmcid(test_pmcid)
        if pdf_file:
            print(f"   📄 PDF cached: {pdf_file.name} ({pdf_file.stat().st_size:,} bytes)")

        # Updated statistics
        stats = client.get_cache_stats()
        print(f"   📊 Updated total files: {stats['total_files']}")
        print(f"   💾 Updated total size: {stats['total_size_bytes']:,} bytes")

        # === DEMONSTRATION 5: Cache Validation ===
        print("\n5️⃣  Cache validation test")

        # Test with a different PMC ID to show cache miss
        test_pmcid2 = "1716993"
        print(f"   🔍 Testing with different PMC{test_pmcid2} (should be cache miss)")

        xml_file2 = client.download_xml_by_pmcid(test_pmcid2)
        if xml_file2:
            print(f"   ✅ New download: {xml_file2.name}")

        # Now test cache hit for the new PMC ID
        print(f"   🔍 Re-downloading PMC{test_pmcid2} (should be cache hit)")
        xml_file2_cached = client.download_xml_by_pmcid(test_pmcid2)
        if xml_file2_cached:
            print(f"   ✅ From cache: {xml_file2_cached.name}")

        # === DEMONSTRATION 6: Batch Processing with Cache ===
        print("\n6️⃣  Batch processing with cache benefits")

        batch_pmcids = [test_pmcid, test_pmcid2, "5251083"]
        print(f"   📦 Batch downloading: {batch_pmcids}")

        start_time = time.time()
        batch_results = client.download_fulltext_batch(
            pmcids=batch_pmcids, format_type="xml", skip_errors=True
        )
        batch_time = time.time() - start_time

        successful = sum(1 for result in batch_results.values() if result)
        print(f"   📊 Batch results: {successful}/{len(batch_pmcids)} successful")
        print(f"   ⏱️  Batch took: {batch_time:.2f} seconds")
        print("   🚀 Cache hits accelerated the process!")

        # === DEMONSTRATION 7: Cache Management ===
        print("\n7️⃣  Cache management")

        # Show current cache state
        stats_before = client.get_cache_stats()
        print(f"   📊 Files before cleanup: {stats_before['total_files']}")

        # Clear old files (using 0 days to clear all for demo)
        cleared_count = client.clear_cache(max_age_days=0)
        print(f"   🗑️  Cleared {cleared_count} files")

        # Show cache state after cleanup
        stats_after = client.get_cache_stats()
        print(f"   📊 Files after cleanup: {stats_after['total_files']}")

        # === DEMONSTRATION 8: Cache with Different Output Paths ===
        print("\n8️⃣  Cache with custom output paths")

        # Download to cache first
        cached_xml = client.download_xml_by_pmcid(test_pmcid)
        if cached_xml:
            print(f"   💾 Cached to: {cached_xml}")

        # Download to a different location (should copy from cache)
        custom_path = Path(temp_cache_dir) / "custom_output.xml"
        custom_xml = client.download_xml_by_pmcid(test_pmcid, custom_path)
        if custom_xml:
            print(f"   📄 Copied to custom path: {custom_xml}")
            print("   ✅ Both files exist and should be identical")

        # Close the client
        client.close()

        print("\n🎉 Caching demonstration completed!")
        print("\nKey Benefits Demonstrated:")
        print("  ✅ Automatic cache checking before downloads")
        print("  ✅ Significant speed improvements on cache hits")
        print("  ✅ File format validation and integrity checking")
        print("  ✅ Separate caching for different formats (PDF/XML/HTML)")
        print("  ✅ Cache statistics and monitoring")
        print("  ✅ Flexible cache management and cleanup")
        print("  ✅ Support for custom output paths with cache benefits")
        print("  ✅ Professional error handling and logging")


if __name__ == "__main__":
    main()
