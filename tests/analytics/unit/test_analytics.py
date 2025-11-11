"""Tests for analytics module."""

import pandas as pd
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
    author_statistics,
)


@pytest.fixture
def sample_papers():
    """Sample papers for testing."""
    return [
        {
            "id": "1",
            "source": "MED",
            "title": "Cancer Research Paper",
            "authorString": "Smith J, Doe J",
            "journalTitle": "Nature",
            "pubYear": "2020",
            "pubTypeList": {"pubType": ["Journal Article", "Research Article"]},
            "isOpenAccess": "Y",
            "citedByCount": "10",
            "doi": "10.1234/test1",
            "pmid": "12345",
            "pmcid": "PMC12345",
            "abstractText": "This is an abstract about cancer research.",
            "hasPDF": "Y",
            "inPMC": "Y",
            "inEPMC": "Y",
        },
        {
            "id": "2",
            "source": "MED",
            "title": "Another Cancer Paper",
            "authorString": "Jones A",
            "journalTitle": "Science",
            "pubYear": "2021",
            "pubTypeList": {"pubType": ["Review"]},
            "isOpenAccess": "N",
            "citedByCount": "25",
            "doi": "10.1234/test2",
            "pmid": "12346",
            "abstractText": "Review of cancer treatments.",
            "hasPDF": "N",
            "inPMC": "N",
            "inEPMC": "Y",
        },
        {
            "id": "3",
            "source": "MED",
            "title": "Immunotherapy Study",
            "authorString": "Brown B, Green G",
            "journalTitle": "Nature",
            "pubYear": "2021",
            "pubTypeList": {"pubType": ["Clinical Trial"]},
            "isOpenAccess": "Y",
            "citedByCount": "5",
            "doi": "10.1234/test3",
            "pmcid": "PMC12347",
            "abstractText": "Clinical trial on immunotherapy.",
            "hasPDF": "Y",
            "inPMC": "Y",
            "inEPMC": "Y",
        },
        {
            "id": "4",
            "source": "MED",
            "title": "Cancer Research Paper",  # Duplicate title
            "authorString": "White W",
            "journalTitle": "Cell",
            "pubYear": "2022",
            "pubTypeList": {"pubType": ["Journal Article"]},
            "isOpenAccess": "Y",
            "citedByCount": "0",
            "abstractText": "",
            "hasPDF": "N",
            "inPMC": "N",
            "inEPMC": "N",
        },
    ]


class TestToDataFrame:
    """Tests for to_dataframe function."""

    def test_to_dataframe_basic(self, sample_papers):
        """Test basic DataFrame conversion."""
        df = to_dataframe(sample_papers)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 4
        assert "title" in df.columns
        assert "citedByCount" in df.columns
        assert "pubYear" in df.columns

    def test_to_dataframe_empty(self):
        """Test DataFrame conversion with empty list."""
        df = to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_to_dataframe_columns(self, sample_papers):
        """Test that all expected columns are present."""
        df = to_dataframe(sample_papers)
        expected_columns = [
            "id",
            "source",
            "title",
            "authorString",
            "journalTitle",
            "pubYear",
            "pubType",
            "isOpenAccess",
            "citedByCount",
            "doi",
            "pmid",
            "pmcid",
            "abstractText",
            "hasAbstract",
            "hasPDF",
            "inPMC",
            "inEPMC",
        ]
        for col in expected_columns:
            assert col in df.columns

    def test_to_dataframe_types(self, sample_papers):
        """Test data types in DataFrame."""
        df = to_dataframe(sample_papers)
        assert df["citedByCount"].dtype in [int, "int64"]
        assert df["hasAbstract"].dtype == bool
        assert df["hasPDF"].dtype == bool


class TestPublicationYearDistribution:
    """Tests for publication_year_distribution function."""

    def test_year_distribution_list(self, sample_papers):
        """Test year distribution from list."""
        dist = publication_year_distribution(sample_papers)
        assert isinstance(dist, pd.Series)
        assert len(dist) == 3  # 2020, 2021, 2022
        assert dist[2021] == 2  # Two papers in 2021

    def test_year_distribution_dataframe(self, sample_papers):
        """Test year distribution from DataFrame."""
        df = to_dataframe(sample_papers)
        dist = publication_year_distribution(df)
        assert isinstance(dist, pd.Series)
        assert len(dist) == 3

    def test_year_distribution_empty(self):
        """Test year distribution with empty data."""
        dist = publication_year_distribution([])
        assert isinstance(dist, pd.Series)
        assert dist.empty

    def test_year_distribution_sorted(self, sample_papers):
        """Test that distribution is sorted by year."""
        dist = publication_year_distribution(sample_papers)
        assert list(dist.index) == sorted(dist.index)


class TestCitationStatistics:
    """Tests for citation_statistics function."""

    def test_citation_stats_basic(self, sample_papers):
        """Test basic citation statistics."""
        stats = citation_statistics(sample_papers)
        assert isinstance(stats, dict)
        assert stats["total_papers"] == 4
        assert stats["mean_citations"] == 10.0  # (10+25+5+0)/4
        assert stats["median_citations"] == 7.5  # median of [0, 5, 10, 25]
        assert stats["min_citations"] == 0
        assert stats["max_citations"] == 25
        assert stats["total_citations"] == 40
        assert stats["papers_with_citations"] == 3
        assert stats["papers_without_citations"] == 1

    def test_citation_stats_empty(self):
        """Test citation statistics with empty data."""
        stats = citation_statistics([])
        assert stats["total_papers"] == 0
        assert stats["mean_citations"] == 0.0

    def test_citation_stats_dataframe(self, sample_papers):
        """Test citation statistics from DataFrame."""
        df = to_dataframe(sample_papers)
        stats = citation_statistics(df)
        assert stats["total_papers"] == 4

    def test_citation_distribution_keys(self, sample_papers):
        """Test that citation distribution has expected percentiles."""
        stats = citation_statistics(sample_papers)
        dist = stats["citation_distribution"]
        assert "25th_percentile" in dist
        assert "50th_percentile" in dist
        assert "75th_percentile" in dist
        assert "90th_percentile" in dist
        assert "95th_percentile" in dist


class TestDetectDuplicates:
    """Tests for detect_duplicates function."""

    def test_detect_duplicates_title(self, sample_papers):
        """Test duplicate detection by title."""
        duplicates = detect_duplicates(sample_papers, method="title")
        assert isinstance(duplicates, list)
        assert len(duplicates) == 1  # One set of duplicates
        assert len(duplicates[0]) == 2  # Two papers with same title

    def test_detect_duplicates_doi(self, sample_papers):
        """Test duplicate detection by DOI."""
        duplicates = detect_duplicates(sample_papers, method="doi")
        assert isinstance(duplicates, list)
        assert len(duplicates) == 0  # No DOI duplicates

    def test_detect_duplicates_empty(self):
        """Test duplicate detection with empty data."""
        duplicates = detect_duplicates([])
        assert duplicates == []

    def test_detect_duplicates_invalid_method(self, sample_papers):
        """Test duplicate detection with invalid method."""
        with pytest.raises(ValueError):
            detect_duplicates(sample_papers, method="invalid")

    def test_detect_duplicates_dataframe(self, sample_papers):
        """Test duplicate detection from DataFrame."""
        df = to_dataframe(sample_papers)
        duplicates = detect_duplicates(df, method="title")
        assert len(duplicates) == 1


class TestRemoveDuplicates:
    """Tests for remove_duplicates function."""

    def test_remove_duplicates_first(self, sample_papers):
        """Test removing duplicates keeping first."""
        result = remove_duplicates(sample_papers, method="title", keep="first")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3  # 4 - 1 duplicate = 3

    def test_remove_duplicates_last(self, sample_papers):
        """Test removing duplicates keeping last."""
        result = remove_duplicates(sample_papers, method="title", keep="last")
        assert len(result) == 3

    def test_remove_duplicates_most_cited(self, sample_papers):
        """Test removing duplicates keeping most cited."""
        result = remove_duplicates(sample_papers, method="title", keep="most_cited")
        assert len(result) == 3
        # Check that the kept paper is the one with more citations (id=1 has 10, id=4 has 0)
        cancer_papers = result[result["title"].str.lower().str.contains("cancer research")]
        assert len(cancer_papers) == 1
        assert cancer_papers.iloc[0]["citedByCount"] == 10

    def test_remove_duplicates_empty(self):
        """Test removing duplicates with empty data."""
        result = remove_duplicates([])
        assert result.empty

    def test_remove_duplicates_dataframe(self, sample_papers):
        """Test removing duplicates from DataFrame."""
        df = to_dataframe(sample_papers)
        result = remove_duplicates(df, method="title", keep="first")
        assert len(result) == 3


class TestQualityMetrics:
    """Tests for quality_metrics function."""

    def test_quality_metrics_basic(self, sample_papers):
        """Test basic quality metrics."""
        metrics = quality_metrics(sample_papers)
        assert isinstance(metrics, dict)
        assert metrics["total_papers"] == 4
        assert metrics["open_access_count"] == 3
        assert metrics["open_access_percentage"] == 75.0
        assert metrics["with_abstract_count"] == 3
        assert metrics["with_doi_count"] == 3

    def test_quality_metrics_empty(self):
        """Test quality metrics with empty data."""
        metrics = quality_metrics([])
        assert metrics["total_papers"] == 0
        assert metrics["open_access_percentage"] == 0.0

    def test_quality_metrics_dataframe(self, sample_papers):
        """Test quality metrics from DataFrame."""
        df = to_dataframe(sample_papers)
        metrics = quality_metrics(df)
        assert metrics["total_papers"] == 4

    def test_quality_metrics_keys(self, sample_papers):
        """Test that all expected keys are present."""
        metrics = quality_metrics(sample_papers)
        expected_keys = [
            "total_papers",
            "open_access_count",
            "open_access_percentage",
            "with_abstract_count",
            "with_abstract_percentage",
            "with_doi_count",
            "with_doi_percentage",
            "in_pmc_count",
            "in_pmc_percentage",
            "with_pdf_count",
            "with_pdf_percentage",
            "peer_reviewed_estimate",
            "peer_reviewed_percentage",
        ]
        for key in expected_keys:
            assert key in metrics


class TestPublicationTypeDistribution:
    """Tests for publication_type_distribution function."""

    def test_pub_type_distribution(self, sample_papers):
        """Test publication type distribution."""
        dist = publication_type_distribution(sample_papers)
        assert isinstance(dist, pd.Series)
        assert len(dist) > 0
        assert "Journal Article" in dist.index

    def test_pub_type_distribution_empty(self):
        """Test publication type distribution with empty data."""
        dist = publication_type_distribution([])
        assert dist.empty

    def test_pub_type_distribution_sorted(self, sample_papers):
        """Test that distribution is sorted by count."""
        dist = publication_type_distribution(sample_papers)
        # Check that values are in descending order
        assert all(dist.iloc[i] >= dist.iloc[i + 1] for i in range(len(dist) - 1))


class TestJournalDistribution:
    """Tests for journal_distribution function."""

    def test_journal_distribution(self, sample_papers):
        """Test journal distribution."""
        dist = journal_distribution(sample_papers)
        assert isinstance(dist, pd.Series)
        assert len(dist) > 0
        assert "Nature" in dist.index
        assert dist["Nature"] == 2  # Two papers in Nature

    def test_journal_distribution_top_n(self, sample_papers):
        """Test journal distribution with top_n parameter."""
        dist = journal_distribution(sample_papers, top_n=2)
        assert len(dist) <= 2

    def test_journal_distribution_empty(self):
        """Test journal distribution with empty data."""
        dist = journal_distribution([])
        assert dist.empty

    def test_journal_distribution_dataframe(self, sample_papers):
        """Test journal distribution from DataFrame."""
        df = to_dataframe(sample_papers)
        dist = journal_distribution(df)
        assert "Nature" in dist.index


class TestAuthorStatistics:
    """Tests for author_statistics function."""

    def test_author_statistics_basic(self, sample_papers):
        """Test basic author statistics."""
        stats = author_statistics(sample_papers)
        assert isinstance(stats, dict)
        assert stats["total_authors"] == 6  # Smith J, Doe J, Jones A, Brown B, Green G, White W
        assert stats["total_author_mentions"] == 6  # Total author instances
        assert stats["avg_authors_per_paper"] == 1.5  # 6 mentions / 4 papers
        assert stats["max_authors_per_paper"] == 2
        assert stats["min_authors_per_paper"] == 1
        assert stats["single_author_papers"] == 2  # Papers 2 and 4
        assert stats["multi_author_papers"] == 2  # Papers 1 and 3

    def test_author_statistics_empty(self):
        """Test author statistics with empty data."""
        stats = author_statistics([])
        assert stats["total_authors"] == 0
        assert stats["total_author_mentions"] == 0
        assert stats["avg_authors_per_paper"] == 0.0

    def test_author_statistics_top_authors(self, sample_papers):
        """Test top authors extraction."""
        stats = author_statistics(sample_papers, top_n=3)
        top_authors = stats["top_authors"]
        assert isinstance(top_authors, pd.Series)
        assert len(top_authors) <= 3
        # All authors appear once each
        assert all(count == 1 for count in top_authors.values)

    def test_author_statistics_collaboration_patterns(self, sample_papers):
        """Test collaboration pattern analysis."""
        stats = author_statistics(sample_papers)
        patterns = stats["author_collaboration_patterns"]
        assert isinstance(patterns, dict)
        assert patterns["solo_authors"] == 2  # Papers 2 and 4
        assert patterns["two_author_papers"] == 2  # Papers 1 and 3
        assert patterns["three_author_papers"] == 0
        assert patterns["four_or_more_author_papers"] == 0
        assert patterns["avg_collaboration_size"] == 2.0  # (2+2)/2

    def test_author_statistics_dataframe(self, sample_papers):
        """Test author statistics from DataFrame."""
        df = to_dataframe(sample_papers)
        stats = author_statistics(df)
        assert stats["total_authors"] == 6
