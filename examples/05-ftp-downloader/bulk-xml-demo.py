#!/usr/bin/env python3
"""
Demonstration of Europe PMC bulk XML download functionality.

This script shows how to:
1. Download XML using REST API with bulk FTP fallback
2. Download XML directly from bulk FTP archives
3. Determine archive ranges for different PMC IDs
"""

from pathlib import Path
from pyeuropepmc import FullTextClient, FullTextError


def main():
    print("=== Europe PMC Bulk XML Download Demo ===\n")

    # Create downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    with FullTextClient() as client:
        print("1. Archive Range Determination:")
        print("   (Showing which FTP archive would contain each PMC ID)")
        test_pmcids = [1234567, 345678, 23456, 2345, 123]

        for pmcid in test_pmcids:
            archive_range = client._determine_bulk_archive_range(pmcid)
            if archive_range:
                start_id, end_id = archive_range
                print(f"   PMC{pmcid:>7} -> PMC{start_id}_PMC{end_id}.xml.gz")

        print("\n2. XML Download with Automatic Fallback:")
        print("   (REST API first, then bulk FTP if needed)")

        test_article = "PMC3257301"  # Known open access article
        output_path = downloads_dir / f"{test_article}_fallback.xml"

        try:
            result = client.download_xml_by_pmcid(test_article, output_path)
            if result:
                file_size = result.stat().st_size / 1024
                print(f"   ✓ Downloaded {test_article} ({file_size:.1f} KB)")
                print(f"     Saved to: {result}")
            else:
                print(f"   ✗ Failed to download {test_article}")
        except FullTextError as e:
            print(f"   ✗ Error: {e}")

        print("\n3. Bulk-Only XML Download:")
        print("   (Direct from FTP archives, skipping REST API)")

        output_path_bulk = downloads_dir / f"{test_article}_bulk_only.xml"

        try:
            result = client.download_xml_by_pmcid_bulk(test_article, output_path_bulk)
            if result:
                file_size = result.stat().st_size / 1024
                print(f"   ✓ Downloaded {test_article} from bulk archive ({file_size:.1f} KB)")
                print(f"     Saved to: {result}")

                # Show which archive this would come from
                pmcid_num = int(test_article.replace("PMC", ""))
                archive_range = client._determine_bulk_archive_range(pmcid_num)
                if archive_range:
                    start_id, end_id = archive_range
                    print(f"     Archive: PMC{start_id}_PMC{end_id}.xml.gz")
            else:
                print(f"   ✗ Failed to download {test_article} from bulk archives")
        except FullTextError as e:
            print(f"   ✗ Error: {e}")

    print("\n=== Demo Complete ===")
    print(f"Downloaded files are in: {downloads_dir.absolute()}")


if __name__ == "__main__":
    main()
