"""
Unit tests for EnrichmentReporter.
"""

from pyeuropepmc.features.enrich.reporter import EnrichmentReporter


class TestEnrichmentReporter:
    """Tests for EnrichmentReporter."""

    def test_initialization(self):
        """Test reporter initialization."""
        reporter = EnrichmentReporter()
        assert reporter is not None

    def test_generate_report_empty(self):
        """Test generate_report with empty input."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report({})
        assert "No enrichment data available" in result

    def test_generate_report_none(self):
        """Test generate_report with None."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(None)  # type: ignore
        assert "No enrichment data available" in result

    def test_generate_report_basic(self):
        """Test generate_report with basic enrichment result."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(
            {
                "identifier": "10.1234/test",
                "doi": "10.1234/test",
                "sources": ["crossref", "unpaywall"],
            }
        )
        assert "Paper Enrichment Report" in result
        assert "10.1234/test" in result
        assert "crossref" in result
        assert "unpaywall" in result
        assert "No merged metadata" in result

    def test_generate_report_with_merged_metadata(self):
        """Test generate_report with merged metadata."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(
            {
                "identifier": "10.1234/test",
                "doi": "10.1234/test",
                "sources": ["crossref"],
                "merged": {
                    "title": "Test Article Title",
                    "authors": [{"name": "Author 1"}, {"name": "Author 2"}],
                    "journal": {"title": "Test Journal", "name": "Test J"},
                    "publication_date": "2024-01-01",
                    "citation_count": 42,
                    "is_oa": True,
                },
            }
        )
        assert "Test Article Title" in result
        assert "Authors: 2" in result
        assert "Test Journal" in result
        assert "2024-01-01" in result
        assert "Citations: 42" in result
        assert "Open Access" in result

    def test_generate_report_closed_access(self):
        """Test generate_report with closed access."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(
            {
                "sources": ["crossref"],
                "merged": {"is_oa": False},
            }
        )
        assert "Closed Access" in result

    def test_generate_report_publication_year(self):
        """Test generate_report with publication year."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(
            {
                "sources": ["crossref"],
                "merged": {"publication_year": "2023"},
            }
        )
        assert "2023" in result

    def test_generate_report_journal_name_fallback(self):
        """Test journal name fallback when title is missing."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(
            {
                "sources": ["crossref"],
                "merged": {"journal": {"name": "Fallback Journal"}},
            }
        )
        assert "Fallback Journal" in result

    def test_generate_report_title_truncation(self):
        """Test title truncation at 100 chars."""
        reporter = EnrichmentReporter()
        long_title = "A" * 150
        result = reporter.generate_report(
            {
                "sources": [],
                "merged": {"title": long_title},
            }
        )
        assert "..." in result
        assert len(result.split("Title: ")[1].split("\n")[0]) == 103  # 100 + '...'

    def test_generate_report_title_exact_100(self):
        """Test title exactly at 100 chars (no truncation)."""
        reporter = EnrichmentReporter()
        exact_title = "A" * 100
        result = reporter.generate_report(
            {
                "sources": [],
                "merged": {"title": exact_title},
            }
        )
        assert "..." not in result
        assert exact_title in result

    def test_generate_report_no_sources(self):
        """Test generate_report with no sources."""
        reporter = EnrichmentReporter()
        result = reporter.generate_report(
            {
                "identifier": "test",
                "sources": [],
            }
        )
        assert "None" in result

    def test_batch_summary_empty(self):
        """Test batch summary with empty input."""
        reporter = EnrichmentReporter()
        result = reporter.generate_batch_summary({})
        assert "No batch results available" in result

    def test_batch_summary_none(self):
        """Test batch summary with None."""
        reporter = EnrichmentReporter()
        result = reporter.generate_batch_summary(None)  # type: ignore
        assert "No batch results available" in result

    def test_batch_summary_all_successful(self):
        """Test batch summary with all successful."""
        reporter = EnrichmentReporter()
        result = reporter.generate_batch_summary(
            {
                "paper1": {
                    "sources": ["crossref", "unpaywall"],
                    "identifier": "10.1234/1",
                },
                "paper2": {
                    "sources": ["crossref"],
                    "identifier": "10.1234/2",
                },
            }
        )
        assert "Total Papers: 2" in result
        assert "Successful Enrichments: 2" in result
        assert "Failed Enrichments: 0" in result
        assert "100.0%" in result
        assert "Average Sources" in result
        assert "crossref" in result

    def test_batch_summary_mixed_results(self):
        """Test batch summary with mixed results."""
        reporter = EnrichmentReporter()
        result = reporter.generate_batch_summary(
            {
                "paper1": {
                    "sources": ["crossref"],
                    "identifier": "10.1234/1",
                },
                "paper2": {
                    "sources": [],
                    "identifier": "10.1234/2",
                },
                "paper3": "error occurred",
            }
        )
        assert "Total Papers: 3" in result
        assert "Successful Enrichments: 1" in result
        assert "Failed Enrichments: 2" in result
        assert "33.3%" in result

    def test_batch_summary_all_failed(self):
        """Test batch summary with all failed."""
        reporter = EnrichmentReporter()
        result = reporter.generate_batch_summary(
            {
                "paper1": {"sources": [], "identifier": "10.1234/1"},
                "paper2": "error",
            }
        )
        assert "Successful Enrichments: 0" in result
        assert "Failed Enrichments: 2" in result
        assert "0.0%" in result
        # No "Average Sources" since successful_enrichments == 0
        assert "Average Sources" not in result

    def test_batch_summary_source_counts(self):
        """Test batch summary source counting."""
        reporter = EnrichmentReporter()
        result = reporter.generate_batch_summary(
            {
                "paper1": {"sources": ["crossref", "unpaywall"]},
                "paper2": {"sources": ["crossref"]},
                "paper3": {"sources": ["semantic_scholar"]},
            }
        )
        assert "Most Used Source: crossref" in result
        assert "(2 papers)" in result
