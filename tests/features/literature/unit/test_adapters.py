"""Unit tests for literature adapters (Semantic Scholar, OpenAlex)."""

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.literature.adapters import (
    OpenAlexLiteratureAdapter,
    SemanticScholarLiteratureAdapter,
)
from pyeuropepmc.models.literature import LiteratureResult

pytestmark = pytest.mark.unit

# ===========================================================================
# SemanticScholarLiteratureAdapter
# ===========================================================================

class TestSemanticScholarAdapter:
    def test_init_default(self):
        """Should create enrichment client by default."""
        pytest.importorskip("semanticscholar")
        adapter = SemanticScholarLiteratureAdapter()
        assert adapter.enrichment_client is not None

    @patch("pyeuropepmc.features.literature.adapters.SemanticScholarClient")
    def test_get_paper_returns_model(self, mock_client_cls):
        """get_paper should return a LiteratureResult, not a dict."""
        mock_client = MagicMock()
        mock_client.enrich.return_value = {
            "paperId": "abc123",
            "title": "Test Paper",
            "year": 2023,
            "venue": "Nature",
            "authors": [{"name": "Smith, John", "lastName": "Smith", "firstName": "John"}],
            "doi": "10.1234/test",
            "abstract": "An abstract.",
            "citationCount": 42,
            "externalIds": {"PubMed": "12345678"},
        }
        mock_client_cls.return_value = mock_client

        adapter = SemanticScholarLiteratureAdapter(enrichment_client=mock_client)
        result = adapter.get_paper("abc123")

        assert result is not None
        assert isinstance(result, LiteratureResult)
        assert result.title == "Test Paper"
        assert result.doi == "10.1234/test"
        assert result.pmid == "12345678"
        assert result.source == "semanticscholar"
        assert result.publication_year == 2023

    @patch("pyeuropepmc.features.literature.adapters.SemanticScholarClient")
    def test_get_paper_not_found(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.enrich.return_value = None
        mock_client_cls.return_value = mock_client

        adapter = SemanticScholarLiteratureAdapter(enrichment_client=mock_client)
        result = adapter.get_paper("nonexistent")
        assert result is None

    @patch("requests.Session.get")
    @patch("pyeuropepmc.features.literature.adapters.SemanticScholarClient")
    def test_search_returns_models(self, mock_client_cls, mock_get):
        """search should return list of LiteratureResult, not dicts."""
        mock_get.return_value.json.return_value = {
            "data": [
                {
                    "paperId": "1",
                    "title": "Paper One",
                    "year": 2023,
                    "authors": [{"name": "Doe, John", "lastName": "Doe", "firstName": "John"}],
                },
                {
                    "paperId": "2",
                    "title": "Paper Two",
                    "year": 2022,
                    "authors": [{"name": "Smith, Jane", "lastName": "Smith", "firstName": "Jane"}],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        adapter = SemanticScholarLiteratureAdapter()
        results = adapter.search("test query", limit=2)

        assert len(results) == 2
        for r in results:
            assert isinstance(r, LiteratureResult)
        assert results[0].title == "Paper One"
        assert results[1].title == "Paper Two"

    @patch("requests.Session.get")
    @patch("pyeuropepmc.features.literature.adapters.SemanticScholarClient")
    def test_search_empty(self, mock_client_cls, mock_get):
        mock_get.return_value.json.return_value = {"data": []}
        mock_get.return_value.raise_for_status.return_value = None

        adapter = SemanticScholarLiteratureAdapter()
        results = adapter.search("nonexistent")
        assert results == []

    @patch("requests.Session.get")
    @patch("pyeuropepmc.features.literature.adapters.SemanticScholarClient")
    def test_search_http_error(self, mock_client_cls, mock_get):
        from requests.exceptions import HTTPError

        mock_get.return_value.raise_for_status.side_effect = HTTPError("API error")

        adapter = SemanticScholarLiteratureAdapter()
        results = adapter.search("error query")
        assert results == []


# ===========================================================================
# OpenAlexLiteratureAdapter
# ===========================================================================

class TestOpenAlexAdapter:
    def test_init_default(self):
        adapter = OpenAlexLiteratureAdapter()
        assert adapter.enrichment_client is not None

    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient")
    def test_get_paper_returns_model(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.enrich.return_value = {
            "id": "https://openalex.org/W123",
            "title": "Test Paper",
            "publication_year": 2023,
            "doi": "https://doi.org/10.1234/test",
            "primary_location": {
                "source": {"display_name": "Nature"}
            },
            "authorships": [
                {
                    "author": {"display_name": "John Doe", "orcid": "0000-0002-1825-0097"},
                    "institutions": [{"display_name": "University of X"}],
                }
            ],
            "cited_by_count": 10,
            "abstract_inverted_index": {"We": [0], "found": [1], "X": [2]},
            "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345678"},
        }
        mock_client_cls.return_value = mock_client

        adapter = OpenAlexLiteratureAdapter(enrichment_client=mock_client)
        result = adapter.get_paper("W123")

        assert result is not None
        assert isinstance(result, LiteratureResult)
        assert result.title == "Test Paper"
        assert result.doi == "10.1234/test"
        assert result.pmid == "12345678"
        assert result.publication_year == 2023
        assert result.source == "openalex"
        assert result.authors is not None
        assert len(result.authors) == 1
        assert result.authors[0].name == "Doe, John"

    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient")
    def test_get_paper_not_found(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.enrich.return_value = None
        mock_client_cls.return_value = mock_client

        adapter = OpenAlexLiteratureAdapter(enrichment_client=mock_client)
        result = adapter.get_paper("nonexistent")
        assert result is None

    @patch("requests.Session.get")
    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient")
    def test_search_returns_models(self, mock_client_cls, mock_get):
        mock_get.return_value.json.return_value = {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "Paper One",
                    "publication_year": 2023,
                    "authorships": [{"author": {"display_name": "Doe, John"}}],
                },
                {
                    "id": "https://openalex.org/W2",
                    "title": "Paper Two",
                    "publication_year": 2022,
                    "authorships": [{"author": {"display_name": "Smith, Jane"}}],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        adapter = OpenAlexLiteratureAdapter()
        results = adapter.search("test query", limit=2)

        assert len(results) == 2
        for r in results:
            assert isinstance(r, LiteratureResult)
        assert results[0].title == "Paper One"
        assert results[1].title == "Paper Two"

    @patch("requests.Session.get")
    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient")
    def test_search_empty(self, mock_client_cls, mock_get):
        mock_get.return_value.json.return_value = {"results": []}
        mock_get.return_value.raise_for_status.return_value = None

        adapter = OpenAlexLiteratureAdapter()
        results = adapter.search("nonexistent")
        assert results == []

    @patch("requests.Session.get")
    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient")
    def test_search_http_error(self, mock_client_cls, mock_get):
        from requests.exceptions import HTTPError

        mock_get.return_value.raise_for_status.side_effect = HTTPError("API error")

        adapter = OpenAlexLiteratureAdapter()
        results = adapter.search("error query")
        assert results == []

    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient")
    def test_get_paper_without_pmid(self, mock_client_cls):
        """Papers without PMID should still work."""
        mock_client = MagicMock()
        mock_client.enrich.return_value = {
            "id": "https://openalex.org/W123",
            "title": "Test Paper",
            "publication_year": 2023,
            "doi": "https://doi.org/10.1234/test",
            "primary_location": {"source": {"display_name": "Nature"}},
            "authorships": [{"author": {"display_name": "Doe, John"}}],
            "cited_by_count": 10,
        }
        mock_client_cls.return_value = mock_client

        adapter = OpenAlexLiteratureAdapter(enrichment_client=mock_client)
        result = adapter.get_paper("W123")

        assert result is not None
        assert result.pmid is None
        assert result.pmcid is None
