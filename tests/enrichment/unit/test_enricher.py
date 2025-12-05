"""Unit tests for paper enrichment orchestrator."""

import pytest
from unittest.mock import Mock, patch

from pyeuropepmc.enrichment.enricher import EnrichmentConfig, PaperEnricher


class TestEnrichmentConfig:
    """Tests for EnrichmentConfig."""

    def test_default_configuration(self):
        """Test default configuration."""
        config = EnrichmentConfig()
        assert config.enable_crossref is True
        assert config.enable_unpaywall is False
        assert config.enable_semantic_scholar is True
        assert config.enable_openalex is True

    def test_unpaywall_requires_email(self):
        """Test that enabling Unpaywall without email raises ValueError."""
        with pytest.raises(ValueError, match="unpaywall_email is required"):
            EnrichmentConfig(enable_unpaywall=True)

    def test_unpaywall_with_email(self):
        """Test enabling Unpaywall with email."""
        config = EnrichmentConfig(
            enable_unpaywall=True,
            unpaywall_email="test@example.com",
        )
        assert config.enable_unpaywall is True
        assert config.unpaywall_email == "test@example.com"

    def test_custom_rate_limit(self):
        """Test custom rate limit configuration."""
        config = EnrichmentConfig(rate_limit_delay=2.0)
        assert config.rate_limit_delay == 2.0


class TestPaperEnricher:
    """Tests for PaperEnricher."""

    def test_initialization_default_config(self):
        """Test initialization with default configuration."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        # Should have CrossRef, Semantic Scholar, and OpenAlex
        assert "crossref" in enricher.clients
        assert "semantic_scholar" in enricher.clients
        assert "openalex" in enricher.clients
        assert "unpaywall" not in enricher.clients

    def test_initialization_all_clients(self):
        """Test initialization with all clients enabled."""
        config = EnrichmentConfig(
            enable_crossref=True,
            enable_unpaywall=True,
            enable_semantic_scholar=True,
            enable_openalex=True,
            unpaywall_email="test@example.com",
        )
        enricher = PaperEnricher(config)

        assert len(enricher.clients) == 5  # crossref, unpaywall, semantic_scholar, openalex, ror
        assert "crossref" in enricher.clients
        assert "unpaywall" in enricher.clients
        assert "semantic_scholar" in enricher.clients
        assert "openalex" in enricher.clients
        assert "ror" in enricher.clients  # ROR is enabled by default

    def test_context_manager(self):
        """Test context manager protocol."""
        config = EnrichmentConfig()
        with PaperEnricher(config) as enricher:
            assert len(enricher.clients) > 0

    def test_enrich_without_doi_raises(self):
        """Test that enrich without DOI raises ValueError."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        with pytest.raises(ValueError, match="Identifier \\(DOI or PMCID\\) is required"):
            enricher.enrich_paper()

    @patch("pyeuropepmc.enrichment.crossref.CrossRefClient.enrich")
    @patch("pyeuropepmc.enrichment.semantic_scholar.SemanticScholarClient.enrich")
    @patch("pyeuropepmc.enrichment.openalex.OpenAlexClient.enrich")
    def test_enrich_paper_success(self, mock_openalex, mock_semantic, mock_crossref):
        """Test successful paper enrichment."""
        # Mock responses from each client
        mock_crossref.return_value = {
            "source": "crossref",
            "title": "Test Article",
            "citation_count": 42,
        }
        mock_semantic.return_value = {
            "source": "semantic_scholar",
            "citation_count": 40,
            "influential_citation_count": 5,
        }
        mock_openalex.return_value = {
            "source": "openalex",
            "citation_count": 45,
            "is_oa": True,
        }

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        result = enricher.enrich_paper(identifier="10.1234/test")

        assert result is not None
        assert result["doi"] == "10.1234/test"
        assert len(result["sources"]) == 3
        assert "crossref" in result["sources"]
        assert "semantic_scholar" in result["sources"]
        assert "openalex" in result["sources"]
        assert result["crossref"]["title"] == "Test Article"
        assert result["merged"] is not None

    @patch("pyeuropepmc.enrichment.crossref.CrossRefClient.enrich")
    def test_enrich_paper_partial_failure(self, mock_crossref):
        """Test enrichment when some clients fail."""
        # CrossRef succeeds
        mock_crossref.return_value = {
            "source": "crossref",
            "title": "Test Article",
        }

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        # Mock other clients to return None
        with patch.object(enricher.clients["semantic_scholar"], "enrich", return_value=None):
            with patch.object(enricher.clients["openalex"], "enrich", return_value=None):
                result = enricher.enrich_paper(identifier="10.1234/test")

                assert result is not None
                assert len(result["sources"]) == 1
                assert "crossref" in result["sources"]

    def test_enrich_paper_all_failures(self):
        """Test enrichment when all clients fail."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        # Mock all clients to return None
        for client in enricher.clients.values():
            client.enrich = Mock(return_value=None)

        result = enricher.enrich_paper(identifier="10.1234/test")

        assert result is not None
        assert len(result["sources"]) == 0
        assert result["merged"] == {}

    @patch("pyeuropepmc.enrichment.crossref.CrossRefClient.enrich")
    @patch("pyeuropepmc.enrichment.semantic_scholar.SemanticScholarClient.enrich")
    def test_merge_results_citation_count(self, mock_semantic, mock_crossref):
        """Test merging of citation counts from multiple sources."""
        mock_crossref.return_value = {
            "source": "crossref",
            "citation_count": 42,
        }
        mock_semantic.return_value = {
            "source": "semantic_scholar",
            "citation_count": 40,
        }

        config = EnrichmentConfig(enable_openalex=False)
        enricher = PaperEnricher(config)
        result = enricher.enrich_paper(identifier="10.1234/test")

        # Should use the maximum citation count
        assert result["merged"]["citation_count"] == 42
        assert len(result["merged"]["citation_counts"]) == 2

    @patch("pyeuropepmc.enrichment.crossref.CrossRefClient.enrich")
    @patch("pyeuropepmc.enrichment.openalex.OpenAlexClient.enrich")
    def test_merge_results_oa_status(self, mock_openalex, mock_crossref):
        """Test merging of OA status."""
        mock_crossref.return_value = {
            "source": "crossref",
            "title": "Test",
        }
        mock_openalex.return_value = {
            "source": "openalex",
            "is_oa": True,
            "oa_status": "gold",
            "oa_url": "https://example.com/paper.pdf",
        }

        config = EnrichmentConfig(enable_semantic_scholar=False)
        enricher = PaperEnricher(config)
        result = enricher.enrich_paper(identifier="10.1234/test")

        assert result["merged"]["is_oa"] is True
        assert result["merged"]["oa_status"] == "gold"
        assert result["merged"]["oa_url"] == "https://example.com/paper.pdf"

    def test_close(self):
        """Test close method."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        # Should not raise
        enricher.close()
