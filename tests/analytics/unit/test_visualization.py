"""Tests for visualization module."""

from pathlib import Path
import tempfile

import matplotlib
import matplotlib.pyplot as plt
import pytest

from pyeuropepmc.processing.analytics import to_dataframe
from pyeuropepmc.processing.visualization import (
    create_summary_dashboard,
    plot_access_distribution,
    plot_author_collaboration_network,
    plot_citation_by_access_type,
    plot_citation_distribution,
    plot_disease_comparison_trends,
    plot_fulltext_availability,
    plot_funding_sources,
    plot_journals,
    plot_license_distribution,
    plot_publication_types,
    plot_publication_years,
    plot_quality_metrics,
    plot_trend_analysis,
)

# Use non-interactive backend for testing
matplotlib.use("Agg")


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
            "pubTypeList": {"pubType": ["Journal Article"]},
            "isOpenAccess": "Y",
            "citedByCount": "10",
            "doi": "10.1234/test1",
            "pmid": "12345",
            "abstractText": "This is an abstract.",
        },
        {
            "id": "2",
            "source": "MED",
            "title": "Another Paper",
            "authorString": "Jones A",
            "journalTitle": "Science",
            "pubYear": "2021",
            "pubTypeList": {"pubType": ["Review"]},
            "isOpenAccess": "N",
            "citedByCount": "25",
            "doi": "10.1234/test2",
            "abstractText": "Review paper.",
        },
        {
            "id": "3",
            "source": "MED",
            "title": "Third Paper",
            "authorString": "Brown B",
            "journalTitle": "Nature",
            "pubYear": "2021",
            "pubTypeList": {"pubType": ["Clinical Trial"]},
            "isOpenAccess": "Y",
            "citedByCount": "5",
        },
    ]


class TestPlotPublicationYears:
    """Tests for plot_publication_years function."""

    def test_plot_basic(self, sample_papers):
        """Test basic plotting."""
        fig = plot_publication_years(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_publication_years([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, sample_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_plot.png"
            fig = plot_publication_years(sample_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)

    def test_plot_custom_title(self, sample_papers):
        """Test plotting with custom title."""
        fig = plot_publication_years(sample_papers, title="Custom Title")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_dataframe(self, sample_papers):
        """Test plotting from DataFrame."""
        df = to_dataframe(sample_papers)
        fig = plot_publication_years(df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestPlotCitationDistribution:
    """Tests for plot_citation_distribution function."""

    def test_plot_basic(self, sample_papers):
        """Test basic plotting."""
        fig = plot_citation_distribution(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_log_scale(self, sample_papers):
        """Test plotting with log scale."""
        fig = plot_citation_distribution(sample_papers, log_scale=True)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_citation_distribution([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, sample_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "citation_dist.png"
            fig = plot_citation_distribution(sample_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)


class TestPlotQualityMetrics:
    """Tests for plot_quality_metrics function."""

    def test_plot_basic(self, sample_papers):
        """Test basic plotting."""
        fig = plot_quality_metrics(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_quality_metrics([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, sample_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "quality_metrics.png"
            fig = plot_quality_metrics(sample_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)


class TestPlotPublicationTypes:
    """Tests for plot_publication_types function."""

    def test_plot_basic(self, sample_papers):
        """Test basic plotting."""
        fig = plot_publication_types(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_top_n(self, sample_papers):
        """Test plotting with top_n parameter."""
        fig = plot_publication_types(sample_papers, top_n=5)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_publication_types([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestPlotJournals:
    """Tests for plot_journals function."""

    def test_plot_basic(self, sample_papers):
        """Test basic plotting."""
        fig = plot_journals(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_top_n(self, sample_papers):
        """Test plotting with top_n parameter."""
        fig = plot_journals(sample_papers, top_n=5)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_journals([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestPlotTrendAnalysis:
    """Tests for plot_trend_analysis function."""

    def test_plot_basic(self, sample_papers):
        """Test basic plotting."""
        fig = plot_trend_analysis(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_trend_analysis([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, sample_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "trend_analysis.png"
            fig = plot_trend_analysis(sample_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)


class TestCreateSummaryDashboard:
    """Tests for create_summary_dashboard function."""

    def test_dashboard_basic(self, sample_papers):
        """Test basic dashboard creation."""
        fig = create_summary_dashboard(sample_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_dashboard_empty(self):
        """Test dashboard with empty data."""
        fig = create_summary_dashboard([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_dashboard_save(self, sample_papers):
        """Test saving dashboard to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "dashboard.png"
            fig = create_summary_dashboard(sample_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)

    def test_dashboard_dataframe(self, sample_papers):
        """Test dashboard from DataFrame."""
        df = to_dataframe(sample_papers)
        fig = create_summary_dashboard(df)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


@pytest.fixture
def extended_papers():
    """Extended sample papers for new visualization tests."""
    return [
        {
            "id": "1", "source": "MED", "title": "Cancer Research on ME/CFS",
            "authorString": "Smith J, Doe J", "pubYear": "2020",
            "isOpenAccess": "Y", "citedByCount": "10", "hasPDF": "Y",
            "inPMC": "Y", "inEPMC": "Y", "license": "CC-BY",
            "abstractText": "This study examines ME/CFS.",
            "grantsList": {"grant": [{"agency": "NIH"}, {"agency": "Wellcome"}]},
        },
        {
            "id": "2", "source": "MED", "title": "Paper on long COVID",
            "authorString": "Jones A", "pubYear": "2021",
            "isOpenAccess": "N", "citedByCount": "25", "hasPDF": "N",
            "inPMC": "N", "inEPMC": "N", "license": "Publisher",
            "abstractText": "Long COVID post-acute sequelae.",
            "grantsList": {"grant": [{"agency": "NIH"}]},
        },
        {
            "id": "3", "source": "MED", "title": "Immunotherapy for chronic fatigue",
            "authorString": "Brown B, Green G", "pubYear": "2022",
            "isOpenAccess": "Y", "citedByCount": "5", "hasPDF": "Y",
            "inPMC": "Y", "inEPMC": "Y", "license": "CC0",
            "abstractText": "Clinical trial on CFS.",
            "grantsList": {"grant": [{"agency": "MRC"}]},
        },
        {
            "id": "4", "source": "MED", "title": "ME prevalence study",
            "authorString": "White W, Black K", "pubYear": "2023",
            "isOpenAccess": "Y", "citedByCount": "15", "hasPDF": "Y",
            "inPMC": "N", "inEPMC": "Y", "license": "CC-BY-NC",
            "abstractText": "ME/CFS prevalence.",
            "grantsList": {"grant": [{"agency": "NIH"}, {"agency": "MRC"}]},
        },
    ]


class TestPlotAccessDistribution:
    """Tests for plot_access_distribution function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        fig = plot_access_distribution(extended_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_access_distribution([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "access_dist.png"
            fig = plot_access_distribution(extended_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)

    def test_plot_custom_title(self, extended_papers):
        """Test plotting with custom title."""
        fig = plot_access_distribution(extended_papers, title="Custom Title")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestPlotLicenseDistribution:
    """Tests for plot_license_distribution function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        fig = plot_license_distribution(extended_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_top_n(self, extended_papers):
        """Test plotting with top_n parameter."""
        fig = plot_license_distribution(extended_papers, top_n=3)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_license_distribution([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "license_dist.png"
            fig = plot_license_distribution(extended_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)


class TestPlotFulltextAvailability:
    """Tests for plot_fulltext_availability function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        fig = plot_fulltext_availability(extended_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_fulltext_availability([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "fulltext_avail.png"
            fig = plot_fulltext_availability(extended_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)


class TestPlotCitationByAccessType:
    """Tests for plot_citation_by_access_type function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        fig = plot_citation_by_access_type(extended_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_citation_by_access_type([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "citation_by_access.png"
            fig = plot_citation_by_access_type(extended_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)


class TestPlotDiseaseComparisonTrends:
    """Tests for plot_disease_comparison_trends function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        disease_terms = {
            "ME/CFS": ["ME/CFS", "chronic fatigue"],
            "Long-COVID": ["long COVID"],
        }
        fig = plot_disease_comparison_trends(extended_papers, disease_terms)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        disease_terms = {"A": ["term1"], "B": ["term2"]}
        fig = plot_disease_comparison_trends([], disease_terms)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        disease_terms = {"ME/CFS": ["ME/CFS"], "Long-COVID": ["long COVID"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "disease_trends.png"
            fig = plot_disease_comparison_trends(
                extended_papers, disease_terms, save_path=save_path
            )
            assert save_path.exists()
            plt.close(fig)


class TestPlotAuthorCollaborationNetwork:
    """Tests for plot_author_collaboration_network function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        fig = plot_author_collaboration_network(extended_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_top_n(self, extended_papers):
        """Test plotting with top_n parameter."""
        fig = plot_author_collaboration_network(extended_papers, top_n=5)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_author_collaboration_network([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "author_network.png"
            fig = plot_author_collaboration_network(
                extended_papers, save_path=save_path
            )
            assert save_path.exists()
            plt.close(fig)


class TestPlotFundingSources:
    """Tests for plot_funding_sources function."""

    def test_plot_basic(self, extended_papers):
        """Test basic plotting."""
        fig = plot_funding_sources(extended_papers)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_top_n(self, extended_papers):
        """Test plotting with top_n parameter."""
        fig = plot_funding_sources(extended_papers, top_n=3)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_empty(self):
        """Test plotting with empty data."""
        fig = plot_funding_sources([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_save(self, extended_papers):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "funding_sources.png"
            fig = plot_funding_sources(extended_papers, save_path=save_path)
            assert save_path.exists()
            plt.close(fig)
