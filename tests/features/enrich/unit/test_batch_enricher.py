"""Unit tests for batch enricher."""

from unittest.mock import patch

import pytest

from pyeuropepmc.utils.dependencies import is_dependency_available

pytestmark = pytest.mark.skipif(
    not is_dependency_available("semanticscholar"), reason="skipped due to missing semanticscholar"
)

from pyeuropepmc.features.enrich.batch_enricher import BatchEnricher
from pyeuropepmc.features.enrich.config import EnrichmentConfig


class TestBatchEnricher:
    """Tests for BatchEnricher."""

    def test_initialization(self):
        """Test batch enricher initialization."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)
        assert enricher is not None

    def test_enrich_papers_single_paper(self):
        """Test enriching a single paper in batch."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        papers = ["10.1234/test1"]

        with patch.object(enricher.enricher, "enrich_paper") as mock_enrich:
            mock_enrich.return_value = {
                "doi": "10.1234/test1",
                "sources": ["crossref"],
            }

            results = enricher.enrich_papers(papers)

            assert "results" in results
            assert len(results["results"]) == 1
            assert results["results"][0]["identifier"] == "10.1234/test1"

    def test_enrich_papers_multiple_papers(self):
        """Test enriching multiple papers."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        papers = ["10.1234/test1", "10.1234/test2", "10.1234/test3"]

        with patch.object(enricher.enricher, "enrich_paper") as mock_enrich:
            mock_enrich.side_effect = [
                {"doi": "10.1234/test1", "sources": ["crossref"]},
                {"doi": "10.1234/test2", "sources": ["crossref", "semantic_scholar"]},
                {"doi": "10.1234/test3", "sources": []},
            ]

            results = enricher.enrich_papers(papers)

            assert "results" in results
            assert len(results["results"]) == 3

    def test_enrich_papers_empty_list(self):
        """Test enriching empty list."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        results = enricher.enrich_papers([])

        assert results == {"results": [], "stats": {"total": 0, "successful": 0, "failed": 0}}

    def test_enrich_papers_with_error(self):
        """Test enriching papers with some errors."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        papers = ["10.1234/test1", "10.1234/test2"]

        with patch.object(enricher.enricher, "enrich_paper") as mock_enrich:
            mock_enrich.side_effect = [
                {"doi": "10.1234/test1", "sources": ["crossref"]},
                ValueError("API error"),
            ]

            results = enricher.enrich_papers(papers)

            assert "results" in results
            assert len(results["results"]) == 2

    def test_enrich_papers_with_stats(self):
        """Test enriching papers returns statistics."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        papers = ["10.1234/test1", "10.1234/test2"]

        with patch.object(enricher.enricher, "enrich_paper") as mock_enrich:
            mock_enrich.return_value = {"doi": "10.1234/test", "sources": []}

            results = enricher.enrich_papers(papers)

            assert "stats" in results
            assert results["stats"]["total"] == 2

    def test_enrich_papers_with_limit(self):
        """Test enriching papers with limit."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        papers = ["10.1234/test1", "10.1234/test2", "10.1234/test3"]

        results = enricher.enrich_papers(papers, max_workers=2, show_progress=False)

        assert "results" in results
        assert len(results["results"]) == 3

    def test_enrich_papers_with_progress(self):
        """Test enriching papers with progress tracking."""
        config = EnrichmentConfig()
        enricher = BatchEnricher(config)

        papers = ["10.1234/test1", "10.1234/test2"]

        results = enricher.enrich_papers_with_progress(papers, show_progress=False)

        assert isinstance(results, dict)
        assert len(results) == 2
