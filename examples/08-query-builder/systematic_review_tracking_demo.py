"""
Demonstration of systematic review tracking with QueryBuilder.

This example shows how to use QueryBuilder with the search logging system
to maintain PRISMA/Cochrane-compliant records of all searches performed
in a systematic review.
"""

import json
import tempfile
from pathlib import Path

from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import (
    prisma_summary,
    record_results,
    start_search,
)


def demo_basic_tracking():
    """Demo 1: Basic query tracking for systematic reviews."""
    print("=" * 70)
    print("Demo 1: Basic Query Tracking")
    print("=" * 70)

    # Start a new systematic review search log
    log = start_search(
        title="Cancer Immunotherapy Systematic Review 2024",
        executed_by="Jane Doe, Research Team",
    )

    # Build and execute a query
    qb = QueryBuilder()
    query = (
        qb.keyword("cancer", field="title")
        .and_()
        .keyword("immunotherapy", field="abstract")
        .and_()
        .date_range(start_year=2020, end_year=2024)
        .and_()
        .field("open_access", True)
        .build()
    )

    print(f"\nQuery built: {query}")

    # Log the query with metadata
    qb.log_to_search(
        search_log=log,
        database="Europe PMC",
        filters={
            "date_range": "2020-2024",
            "fields": ["title", "abstract"],
            "open_access": True,
        },
        results_returned=342,
        notes="Initial broad search for cancer immunotherapy papers",
        platform="Europe PMC API v6.9",
    )

    print("\n✅ Query logged successfully!")
    print(f"   Database: Europe PMC")
    print(f"   Results: 342 papers")
    print(f"   Date: {log.entries[0].date_run}")
    print()


def demo_multi_query_tracking():
    """Demo 2: Tracking multiple queries in one systematic review."""
    print("=" * 70)
    print("Demo 2: Multi-Query Tracking")
    print("=" * 70)

    log = start_search("Multi-Database Systematic Review", executed_by="Research Team")

    # Query 1: Broad cancer search
    qb1 = QueryBuilder()
    qb1.keyword("cancer", field="title").and_().date_range(start_year=2020)
    qb1.log_to_search(
        log,
        database="Europe PMC",
        results_returned=1250,
        filters={"year": "2020+", "field": "title"},
        notes="Broad cancer search",
    )

    # Query 2: Specific treatment search
    qb2 = QueryBuilder()
    qb2.keyword("checkpoint inhibitor", field="abstract").and_().field("mesh", "Neoplasms")
    qb2.log_to_search(
        log,
        database="Europe PMC",
        results_returned=487,
        filters={"mesh": "Neoplasms"},
        notes="Checkpoint inhibitor specific search",
    )

    # Query 3: Clinical trials
    qb3 = QueryBuilder()
    qb3.keyword("immunotherapy").and_().field("pub_type", "Clinical Trial")
    qb3.log_to_search(
        log,
        database="Europe PMC",
        results_returned=156,
        filters={"pub_type": "Clinical Trial"},
        notes="Clinical trials only",
    )

    print(f"\n✅ Logged {len(log.entries)} queries:")
    for i, entry in enumerate(log.entries, 1):
        print(f"   {i}. {entry.notes}: {entry.results_returned} results")
    print()


def demo_save_and_export():
    """Demo 3: Saving search logs for PRISMA reporting."""
    print("=" * 70)
    print("Demo 3: Save and Export for PRISMA")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        log = start_search("PRISMA Workflow Demo", executed_by="Demo User")

        # Build and log multiple searches
        qb1 = QueryBuilder()
        qb1.keyword("CRISPR").and_().date_range(start_year=2018, end_year=2024)
        qb1.log_to_search(log, results_returned=523)

        qb2 = QueryBuilder()
        qb2.keyword("gene editing").and_().field("open_access", True)
        qb2.log_to_search(log, results_returned=412)

        # Record deduplication and final counts
        record_results(log, deduplicated_total=750, final_included=42)

        # Save the complete search log
        log_path = Path(tmpdir) / "systematic_review_searches.json"
        saved_path = log.save(log_path)

        print(f"\n✅ Search log saved to: {saved_path}")

        # Load and display the saved log
        with open(saved_path, "r") as f:
            saved_data = json.load(f)

        print(f"   Title: {saved_data['title']}")
        print(f"   Executed by: {saved_data['executed_by']}")
        print(f"   Total queries: {len(saved_data['entries'])}")
        print(f"   Deduplicated total: {saved_data['deduplicated_total']}")
        print(f"   Final included: {saved_data['final_included']}")

        # Generate PRISMA summary
        summary = prisma_summary(log)
        print("\n📊 PRISMA Summary:")
        print(f"   Total records identified: {summary['total_records_identified']}")
        print(f"   After deduplication: {summary['deduplicated_total']}")
        print(f"   Final included studies: {summary['final_included']}")
        print()


def demo_with_raw_results():
    """Demo 4: Saving raw results for auditability."""
    print("=" * 70)
    print("Demo 4: Raw Results Tracking")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        log = start_search("Auditable Search", executed_by="Auditor")

        # Simulate API results
        raw_results = {
            "hitCount": 150,
            "resultList": {
                "result": [
                    {"id": "123456", "title": "Cancer research paper 1"},
                    {"id": "789012", "title": "Cancer research paper 2"},
                ]
            },
        }

        qb = QueryBuilder()
        qb.keyword("cancer").and_().field("open_access", True)
        qb.log_to_search(
            log,
            results_returned=150,
            raw_results=raw_results,
            raw_results_dir=tmpdir,
        )

        print(f"\n✅ Query logged with raw results")
        print(f"   Raw results saved to: {log.entries[0].raw_results_path}")

        # Verify raw results file
        if log.entries[0].raw_results_path:
            with open(log.entries[0].raw_results_path, "r") as f:
                saved_results = json.load(f)
            print(f"   Results in file: {saved_results['hitCount']} records")
        print()


def demo_complex_systematic_review():
    """Demo 5: Complete systematic review workflow."""
    print("=" * 70)
    print("Demo 5: Complete Systematic Review Workflow")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize review
        log = start_search(
            "Cancer Immunotherapy & Checkpoint Inhibitors: Systematic Review 2024",
            executed_by="Dr. Smith, Dr. Jones, Dr. Brown",
        )

        print("\n📋 Systematic Review: Cancer Immunotherapy 2024")
        print("-" * 70)

        # Search 1: Broad cancer immunotherapy
        print("\n🔍 Search 1: Broad cancer immunotherapy...")
        qb1 = QueryBuilder()
        qb1.keyword("cancer").and_().keyword("immunotherapy").and_().date_range(
            start_year=2020, end_year=2024
        )
        qb1.log_to_search(
            log,
            database="Europe PMC",
            filters={"years": "2020-2024", "type": "broad"},
            results_returned=1842,
            notes="Broad search: cancer AND immunotherapy",
            platform="API",
        )
        print(f"   ✓ Found 1,842 papers")

        # Search 2: Checkpoint inhibitors
        print("\n🔍 Search 2: Checkpoint inhibitors...")
        qb2 = QueryBuilder()
        qb2.keyword("checkpoint inhibitor").and_().field("mesh", "Neoplasms").and_().field(
            "open_access", True
        )
        qb2.log_to_search(
            log,
            database="Europe PMC",
            filters={"mesh": "Neoplasms", "open_access": True},
            results_returned=734,
            notes="Specific: checkpoint inhibitors with MeSH neoplasms",
            platform="API",
        )
        print(f"   ✓ Found 734 papers")

        # Search 3: Clinical trials
        print("\n🔍 Search 3: Clinical trials...")
        qb3 = QueryBuilder()
        qb3.keyword("PD-1").or_().keyword("PD-L1").and_().field(
            "pub_type", "Clinical Trial"
        )
        qb3.log_to_search(
            log,
            database="Europe PMC",
            filters={"pub_type": "Clinical Trial", "keywords": ["PD-1", "PD-L1"]},
            results_returned=412,
            notes="Clinical trials: PD-1 OR PD-L1",
            platform="API",
        )
        print(f"   ✓ Found 412 papers")

        # Search 4: Recent reviews
        print("\n🔍 Search 4: Recent systematic reviews...")
        qb4 = QueryBuilder()
        qb4.keyword("immunotherapy").and_().field("pub_type", "Systematic Review").and_().date_range(
            start_year=2023, end_year=2024
        )
        qb4.log_to_search(
            log,
            database="Europe PMC",
            filters={"pub_type": "Systematic Review", "years": "2023-2024"},
            results_returned=89,
            notes="Recent systematic reviews 2023-2024",
            platform="API",
        )
        print(f"   ✓ Found 89 papers")

        # Record deduplication and screening results
        print("\n📊 Processing results...")
        record_results(log, deduplicated_total=2150, final_included=67)
        print(f"   ✓ Total records: 3,077 (before deduplication)")
        print(f"   ✓ After deduplication: 2,150")
        print(f"   ✓ After screening: 67 included")

        # Save everything
        log_path = Path(tmpdir) / "cancer_immunotherapy_review_2024.json"
        log.save(log_path)
        print(f"\n💾 Complete search log saved to:")
        print(f"   {log_path}")

        # Generate PRISMA summary for methods section
        print("\n📄 PRISMA Flow Diagram Data:")
        print("-" * 70)
        summary = prisma_summary(log)
        print(f"   Records identified: {summary['total_records_identified']}")
        print(f"   Records after deduplication: {summary['deduplicated_total']}")
        print(f"   Studies included in review: {summary['final_included']}")

        print("\n✅ Systematic review tracking complete!")
        print(
            "   This log can be included in your PRISMA flow diagram and methods section."
        )
        print()


if __name__ == "__main__":
    # Run all demos
    demo_basic_tracking()
    demo_multi_query_tracking()
    demo_save_and_export()
    demo_with_raw_results()
    demo_complex_systematic_review()

    print("=" * 70)
    print("All demos completed successfully!")
    print("=" * 70)
    print(
        "\nThese search logs are PRISMA/Cochrane compliant and can be used in:"
    )
    print("  - Methods sections of systematic reviews")
    print("  - PRISMA flow diagrams")
    print("  - Supplementary materials")
    print("  - Audit trails for reproducibility")
    print()
