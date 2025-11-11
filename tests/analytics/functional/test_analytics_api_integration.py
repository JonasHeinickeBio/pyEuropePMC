"""
Functional tests for analytics module using real API calls.

These tests verify the analytics functionality works correctly with
live data from Europe PMC API. Marked as slow tests.
"""

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
from pyeuropepmc.search import SearchClient


@pytest.mark.slow
@pytest.mark.integration
class TestAnalyticsWithRealAPI:
    """Test analytics functionality using real API calls."""

    @pytest.fixture
    def real_search_results(self):
        """Get real search results from Europe PMC API."""
        client = SearchClient()

        # Search for a small, focused query to get consistent results
        response = client.search(
            query="breast cancer AND 2023[DP]",
            limit=50,  # Small limit for faster testing
            result_type="lite"
        )

        # Extract the results list from the response
        if isinstance(response, dict) and "resultList" in response:
            return response["resultList"]["result"]
        return []

    @pytest.fixture
    def real_dataframe(self, real_search_results):
        """Convert real API results to DataFrame."""
        return to_dataframe(real_search_results)

    def test_real_api_data_conversion(self, real_search_results):
        """Test converting real API data to DataFrame."""
        df = to_dataframe(real_search_results)

        assert not df.empty
        assert len(df) > 0
        assert "title" in df.columns
        assert "pmid" in df.columns or "doi" in df.columns

    def test_real_publication_year_distribution(self, real_dataframe):
        """Test publication year distribution with real data."""
        year_dist = publication_year_distribution(real_dataframe)

        # publication_year_distribution returns a pandas Series
        assert hasattr(year_dist, 'index')  # pandas Series has index
        assert hasattr(year_dist, 'values')  # pandas Series has values
        assert len(year_dist) > 0

        # Should have data from 2023 (based on our query)
        years = [int(y) for y in year_dist.index if str(y).isdigit()]
        assert any(year >= 2023 for year in years)

    def test_real_journal_distribution(self, real_dataframe):
        """Test journal distribution with real data."""
        journal_dist = journal_distribution(real_dataframe)

        # journal_distribution returns a pandas Series
        assert hasattr(journal_dist, 'index')  # pandas Series has index
        assert hasattr(journal_dist, 'values')  # pandas Series has values
        assert len(journal_dist) > 0

        # Should have some journals (top 10 by default)
        assert len(journal_dist) <= 10  # top_n=10 by default
        # All values should be positive (may be numpy types)
        assert all(count >= 0 for count in journal_dist.values)

    def test_real_publication_type_distribution(self, real_dataframe):
        """Test publication type distribution with real data."""
        type_dist = publication_type_distribution(real_dataframe)

        # publication_type_distribution returns a pandas Series
        assert hasattr(type_dist, 'index')  # pandas Series has index
        assert hasattr(type_dist, 'values')  # pandas Series has values
        # Real data should have publication types
        assert len(type_dist) > 0
        # All values should be positive (may be numpy types)
        assert all(count >= 0 for count in type_dist.values)

    def test_real_citation_statistics(self, real_dataframe):
        """Test citation statistics with real data."""
        stats = citation_statistics(real_dataframe)

        assert isinstance(stats, dict)
        expected_keys = ["total_papers", "mean_citations", "median_citations", "min_citations", "max_citations", "total_citations"]
        for key in expected_keys:
            assert key in stats
            assert isinstance(stats[key], (int, float))

        # Check citation distribution exists
        assert "citation_distribution" in stats
        assert isinstance(stats["citation_distribution"], dict)

    def test_real_quality_metrics(self, real_dataframe):
        """Test quality metrics with real data."""
        metrics = quality_metrics(real_dataframe)

        assert isinstance(metrics, dict)
        assert len(metrics) > 0

        # Check for expected quality metrics
        expected_metrics = ["open_access_percentage", "in_pmc_percentage", "with_doi_percentage"]
        for metric in expected_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
            if "percentage" in metric:
                assert 0 <= metrics[metric] <= 100

    def test_real_duplicate_detection(self, real_dataframe):
        """Test duplicate detection with real data."""
        duplicates = detect_duplicates(real_dataframe)

        assert isinstance(duplicates, list)
        # Real data might have duplicates
        if duplicates:
            assert all(isinstance(d, (int, str)) for d in duplicates)

    def test_real_duplicate_removal(self, real_dataframe):
        """Test duplicate removal with real data."""
        original_length = len(real_dataframe)

        cleaned_df = remove_duplicates(real_dataframe)

        assert isinstance(cleaned_df, type(real_dataframe))
        assert len(cleaned_df) <= original_length

    def test_real_analytics_pipeline(self, real_dataframe):
        """Test complete analytics pipeline with real data."""
        # Run all analytics functions
        year_dist = publication_year_distribution(real_dataframe)
        journal_dist = journal_distribution(real_dataframe)
        type_dist = publication_type_distribution(real_dataframe)
        citation_stats = citation_statistics(real_dataframe)
        quality = quality_metrics(real_dataframe)

        # Verify all results are valid
        assert hasattr(year_dist, 'index') and len(year_dist) > 0
        assert hasattr(journal_dist, 'index') and len(journal_dist) > 0
        assert hasattr(type_dist, 'index') and len(type_dist) > 0
        assert isinstance(citation_stats, dict) and len(citation_stats) > 0
        assert isinstance(quality, dict) and len(quality) > 0

        # Test that we can generate meaningful insights
        total_papers = len(real_dataframe)
        open_access_pct = quality.get("open_access_percentage", 0)

        assert total_papers > 0
        assert 0 <= open_access_pct <= 100

    def test_real_data_consistency(self, real_search_results, real_dataframe):
        """Test that DataFrame conversion preserves data consistency."""
        # Check that DataFrame has same number of rows as original data
        assert len(real_dataframe) == len(real_search_results)

        # Check that key fields are preserved
        if real_search_results:
            first_result = real_search_results[0]
            first_row = real_dataframe.iloc[0]

            # Check title preservation
            if "title" in first_result:
                assert first_row["title"] == first_result["title"]

            # Check PMID preservation
            if "pmid" in first_result:
                assert str(first_row["pmid"]) == str(first_result["pmid"])

    @pytest.mark.parametrize("limit", [10, 25, 50])
    def test_real_analytics_scalability(self, limit):
        """Test analytics scalability with different data sizes."""
        client = SearchClient()

        # Get different sized datasets
        response = client.search(
            query="diabetes AND 2023[DP]",
            limit=limit,
            result_type="lite"
        )

        # Extract results from response
        if isinstance(response, dict) and "resultList" in response:
            results = response["resultList"]["result"]
        else:
            results = []

        df = to_dataframe(results)

        # Verify results are reasonable for the data size (API may not respect limit exactly)
        assert len(df) > 0  # Should have some results
        # Allow flexibility - API might return more or fewer results than requested
        assert len(df) <= max(limit * 3, 50)  # Be generous with API behavior

        # Run analytics
        year_dist = publication_year_distribution(df)
        journal_dist = journal_distribution(df)
        citation_stats = citation_statistics(df)

        # Verify results are reasonable for the data size
        assert hasattr(year_dist, 'index')
        assert hasattr(journal_dist, 'index')
        assert isinstance(citation_stats, dict)
