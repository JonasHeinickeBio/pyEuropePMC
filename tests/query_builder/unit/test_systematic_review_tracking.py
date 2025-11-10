"""
Tests for systematic review tracking integration in QueryBuilder.
"""

import json
from pathlib import Path
import tempfile

import pytest

from pyeuropepmc import QueryBuilder
from pyeuropepmc.utils.search_logging import start_search


class TestSystematicReviewTracking:
    """Test systematic review tracking integration."""

    def test_log_basic_query(self) -> None:
        """Test logging a basic query to SearchLog."""
        # Create a search log
        log = start_search("Test Review", executed_by="Test User")

        # Build a query
        qb = QueryBuilder()
        query = qb.keyword("cancer").and_().keyword("treatment").build()

        # Log the query
        qb.log_to_search(
            search_log=log,
            database="Europe PMC",
            results_returned=150,
            notes="Initial search",
        )

        # Verify log entry
        assert len(log.entries) == 1
        entry = log.entries[0]
        assert entry.database == "Europe PMC"
        assert entry.query == query
        assert entry.results_returned == 150
        assert entry.notes == "Initial search"

    def test_log_query_with_filters(self) -> None:
        """Test logging a query with filters."""
        log = start_search("Test Review")

        qb = QueryBuilder()
        query = (
            qb.keyword("CRISPR", field="title")
            .and_()
            .date_range(start_year=2020, end_year=2023)
            .build()
        )

        filters = {
            "date_range": "2020-2023",
            "open_access": True,
            "min_citations": 10,
        }

        qb.log_to_search(
            search_log=log,
            filters=filters,
            results_returned=75,
            platform="Europe PMC API v6.9",
        )

        assert len(log.entries) == 1
        entry = log.entries[0]
        assert entry.filters == filters
        assert entry.platform == "Europe PMC API v6.9"

    def test_log_multiple_queries(self) -> None:
        """Test logging multiple queries to the same SearchLog."""
        log = start_search("Multi-Database Review")

        # First query - Europe PMC
        qb1 = QueryBuilder()
        qb1.keyword("cancer").and_().keyword("immunotherapy")
        qb1.log_to_search(log, database="Europe PMC", results_returned=200)

        # Second query - different database simulation
        qb2 = QueryBuilder()
        qb2.keyword("cancer").and_().keyword("checkpoint inhibitor")
        qb2.log_to_search(log, database="PubMed", results_returned=180)

        # Verify both entries
        assert len(log.entries) == 2
        assert log.entries[0].database == "Europe PMC"
        assert log.entries[0].results_returned == 200
        assert log.entries[1].database == "PubMed"
        assert log.entries[1].results_returned == 180

    def test_log_with_raw_results(self) -> None:
        """Test logging with raw results saved to file."""
        log = start_search("Test Review")

        qb = QueryBuilder()
        qb.keyword("cancer")

        # Mock raw results
        raw_results = {
            "resultList": {"result": [{"title": "Paper 1"}, {"title": "Paper 2"}]},
            "hitCount": 2,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            qb.log_to_search(
                search_log=log,
                results_returned=2,
                raw_results=raw_results,
                raw_results_dir=tmpdir,
            )

            # Verify log entry has raw results path
            entry = log.entries[0]
            assert entry.raw_results_path is not None
            assert Path(entry.raw_results_path).exists()

            # Verify raw results file content
            with open(entry.raw_results_path, "r") as f:
                saved_results = json.load(f)
            assert saved_results == raw_results

    def test_log_and_save_workflow(self) -> None:
        """Test complete workflow: build query, log it, save log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log = start_search("Complete Workflow Test", executed_by="Test User")

            # Build and log first query
            qb1 = QueryBuilder()
            qb1.keyword("cancer", field="title").and_().date_range(start_year=2020)
            qb1.log_to_search(
                log,
                filters={"year": "2020+", "field": "title"},
                results_returned=100,
            )

            # Build and log second query
            qb2 = QueryBuilder()
            qb2.keyword("immunotherapy", field="abstract")
            qb2.log_to_search(log, results_returned=50)

            # Save the log
            log_path = Path(tmpdir) / "search_log.json"
            saved_path = log.save(log_path)

            # Verify file exists and contains correct data
            assert saved_path.exists()
            with open(saved_path, "r") as f:
                log_data = json.load(f)

            assert log_data["title"] == "Complete Workflow Test"
            assert log_data["executed_by"] == "Test User"
            assert len(log_data["entries"]) == 2
            assert log_data["entries"][0]["results_returned"] == 100
            assert log_data["entries"][1]["results_returned"] == 50

    def test_log_with_export_path(self) -> None:
        """Test logging with export path."""
        log = start_search("Export Test")

        qb = QueryBuilder()
        qb.keyword("cancer")

        qb.log_to_search(
            log,
            results_returned=100,
            export_path="/path/to/exported_results.csv",
        )

        entry = log.entries[0]
        assert entry.export_path == "/path/to/exported_results.csv"

    def test_log_preserves_query_components(self) -> None:
        """Test that logging captures the exact query built."""
        log = start_search("Query Preservation Test")

        qb = QueryBuilder()
        qb.field("author", "Smith J").and_().field("mesh", "Neoplasms").and_().field(
            "open_access", True
        )

        expected_query = 'AUTH:"Smith J" AND MESH:Neoplasms AND OPEN_ACCESS:y'

        qb.log_to_search(log, results_returned=25)

        entry = log.entries[0]
        assert entry.query == expected_query

    def test_log_empty_filters(self) -> None:
        """Test logging with no filters specified."""
        log = start_search("No Filters Test")

        qb = QueryBuilder()
        qb.keyword("cancer")

        qb.log_to_search(log, results_returned=100)

        entry = log.entries[0]
        assert entry.filters == {}

    def test_log_updates_search_log_timestamp(self) -> None:
        """Test that logging updates the SearchLog's last_updated timestamp."""
        log = start_search("Timestamp Test")
        initial_timestamp = log.last_updated

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        qb = QueryBuilder()
        qb.keyword("cancer")
        qb.log_to_search(log, results_returned=50)

        # Timestamp should be updated
        assert log.last_updated != initial_timestamp

    def test_log_with_complex_query(self) -> None:
        """Test logging a complex multi-part query."""
        log = start_search("Complex Query Test")

        qb = QueryBuilder()
        query = (
            qb.keyword("cancer", field="title")
            .or_()
            .keyword("tumor", field="title")
            .and_()
            .keyword("treatment", field="abstract")
            .and_()
            .date_range(start_year=2018, end_year=2023)
            .and_()
            .citation_count(min_count=5)
            .and_()
            .field("open_access", True)
            .build()
        )

        qb.log_to_search(
            log,
            filters={
                "date_range": "2018-2023",
                "min_citations": 5,
                "open_access": True,
            },
            results_returned=342,
            notes="Comprehensive search with multiple criteria",
        )

        entry = log.entries[0]
        assert "TITLE:" in entry.query
        assert "ABSTRACT:" in entry.query
        assert "PUB_YEAR:" in entry.query  # date_range uses PUB_YEAR not FIRST_PDATE
        assert "CITED:" in entry.query
        assert entry.results_returned == 342


class TestSystematicReviewIntegration:
    """Test integration with full systematic review workflow."""

    def test_prisma_workflow(self) -> None:
        """Test complete PRISMA-compliant workflow."""
        from pyeuropepmc.utils.search_logging import prisma_summary, record_results

        with tempfile.TemporaryDirectory() as tmpdir:
            # Start systematic review
            log = start_search(
                "Cancer Immunotherapy Systematic Review 2024",
                executed_by="Research Team",
            )

            # Search Europe PMC
            qb1 = QueryBuilder()
            qb1.keyword("cancer immunotherapy").and_().date_range(
                start_year=2020, end_year=2024
            )
            qb1.log_to_search(
                log,
                database="Europe PMC",
                results_returned=450,
                filters={"years": "2020-2024"},
            )

            # Search with different criteria (same database)
            qb2 = QueryBuilder()
            qb2.keyword("checkpoint inhibitor").and_().field("open_access", True)
            qb2.log_to_search(
                log, database="Europe PMC", results_returned=230, filters={"OA": True}
            )

            # Record deduplication and final counts
            record_results(log, deduplicated_total=550, final_included=45)

            # Save log
            log_path = Path(tmpdir) / "prisma_search_log.json"
            log.save(log_path)

            # Generate PRISMA summary
            summary = prisma_summary(log)
            assert summary["title"] == "Cancer Immunotherapy Systematic Review 2024"
            # Since both searches are from same database, only last one counts in by_db
            assert summary["total_records_identified"] == 230
            assert summary["deduplicated_total"] == 550
            assert summary["final_included"] == 45

    def test_multi_platform_tracking(self) -> None:
        """Test tracking searches across multiple platforms."""
        log = start_search("Multi-Platform Review")

        # Europe PMC search
        qb_epmc = QueryBuilder()
        qb_epmc.keyword("CRISPR").and_().field("pub_type", "Journal Article")
        qb_epmc.log_to_search(
            log, database="Europe PMC", platform="API v6.9", results_returned=150
        )

        # Web interface search (simulated)
        qb_web = QueryBuilder()
        qb_web.keyword("gene editing")
        qb_web.log_to_search(
            log, database="Europe PMC", platform="Web Interface", results_returned=120
        )

        assert len(log.entries) == 2
        assert log.entries[0].platform == "API v6.9"
        assert log.entries[1].platform == "Web Interface"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
