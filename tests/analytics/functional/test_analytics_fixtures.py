"""
Functional tests for analytics module using fixture data.

These tests verify the analytics functionality works correctly with
realistic data structures loaded from test fixtures.
"""

import json
from pathlib import Path

import pytest

from pyeuropepmc.analytics import (
    citation_statistics,
    detect_duplicates,
    journal_distribution,
    publication_type_distribution,
    publication_year_distribution,
    quality_metrics,
    remove_duplicates,
    to_dataframe,
)


class TestAnalyticsWithFixtures:
    """Test analytics functionality using fixture data."""

    @pytest.fixture
    def fixture_data(self):
        """Load test data from fixtures."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "search_cancer.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["resultList"]["result"]

    @pytest.fixture
    def large_fixture_data(self):
        """Load larger test dataset from fixtures."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "search_1000results_cancer.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["resultList"]["result"]

    def test_to_dataframe_with_fixture_data(self, fixture_data):
        """Test converting fixture data to DataFrame."""
        df = to_dataframe(fixture_data)

        assert not df.empty
        assert len(df) == len(fixture_data)
        assert "title" in df.columns
        assert "journalTitle" in df.columns
        assert "pubYear" in df.columns

    def test_publication_year_distribution_with_fixtures(self, fixture_data):
        """Test publication year distribution analysis with fixture data."""
        df = to_dataframe(fixture_data)
        year_dist = publication_year_distribution(df)

        # publication_year_distribution returns a pandas Series
        assert hasattr(year_dist, 'index')  # pandas Series has index
        assert hasattr(year_dist, 'values')  # pandas Series has values
        assert len(year_dist) > 0

        # Check that years are reasonable (not in future, not too old)
        for year in year_dist.index:
            assert isinstance(year, (str, int))
            year_int = int(year) if isinstance(year, str) else year
            assert 1900 <= year_int <= 2030

    def test_journal_distribution_with_fixtures(self, fixture_data):
        """Test journal distribution analysis with fixture data."""
        df = to_dataframe(fixture_data)
        journal_dist = journal_distribution(df)

        # journal_distribution returns a pandas Series
        assert hasattr(journal_dist, 'index')  # pandas Series has index
        assert hasattr(journal_dist, 'values')  # pandas Series has values
        assert len(journal_dist) > 0

        # Check that we have some expected journals
        journal_names = [j.lower() for j in journal_dist.index]
        assert any("cancer" in name or "medicine" in name or "nature" in name for name in journal_names)

    def test_publication_type_distribution_with_fixtures(self, fixture_data):
        """Test publication type distribution with fixture data."""
        df = to_dataframe(fixture_data)
        type_dist = publication_type_distribution(df)

        # publication_type_distribution returns a pandas Series
        assert hasattr(type_dist, 'index')  # pandas Series has index
        assert hasattr(type_dist, 'values')  # pandas Series has values
        # May be empty if fixture data doesn't have pubTypeList
        if len(type_dist) > 0:
            assert all(count > 0 for count in type_dist.values)

    def test_citation_statistics_with_fixtures(self, fixture_data):
        """Test citation statistics with fixture data."""
        df = to_dataframe(fixture_data)
        stats = citation_statistics(df)

        assert isinstance(stats, dict)
        expected_keys = ["total_papers", "mean_citations", "median_citations", "min_citations", "max_citations", "total_citations"]
        for key in expected_keys:
            assert key in stats

    def test_quality_metrics_with_fixtures(self, fixture_data):
        """Test quality metrics calculation with fixture data."""
        df = to_dataframe(fixture_data)
        metrics = quality_metrics(df)

        assert isinstance(metrics, dict)
        assert len(metrics) > 0

        # Check for expected quality metrics
        expected_metrics = ["open_access_percentage", "pmid_coverage", "doi_coverage"]
        for metric in expected_metrics:
            if metric in metrics:
                assert isinstance(metrics[metric], (int, float))
                if "percentage" in metric:
                    assert 0 <= metrics[metric] <= 100

    def test_duplicate_detection_with_fixtures(self, large_fixture_data):
        """Test duplicate detection with larger fixture dataset."""
        df = to_dataframe(large_fixture_data)
        duplicates = detect_duplicates(df)

        assert isinstance(duplicates, list)
        # Duplicates should be a list of indices or paper IDs
        if duplicates:
            assert all(isinstance(d, (int, str)) for d in duplicates)

    def test_duplicate_removal_with_fixtures(self, large_fixture_data):
        """Test duplicate removal with larger fixture dataset."""
        df = to_dataframe(large_fixture_data)
        original_length = len(df)

        cleaned_df = remove_duplicates(df)

        assert isinstance(cleaned_df, type(df))  # Same type as input
        assert len(cleaned_df) <= original_length  # Should not increase length

    def test_analytics_pipeline_with_fixtures(self, fixture_data):
        """Test complete analytics pipeline with fixture data."""
        # Convert to DataFrame
        df = to_dataframe(fixture_data)

        # Run various analyses
        year_dist = publication_year_distribution(df)
        journal_dist = journal_distribution(df)
        type_dist = publication_type_distribution(df)
        citation_stats = citation_statistics(df)
        quality = quality_metrics(df)

        # Verify all results are valid
        assert hasattr(year_dist, 'index') and len(year_dist) > 0
        assert hasattr(journal_dist, 'index') and len(journal_dist) > 0
        assert hasattr(type_dist, 'index') and len(type_dist) > 0
        assert isinstance(citation_stats, dict) and len(citation_stats) > 0
        assert isinstance(quality, dict) and len(quality) > 0
