"""Unit tests for DOI Content Negotiation enrichment client."""

import pytest
from unittest.mock import patch

from pyeuropepmc.enrichment.doi_content_negotiation import DoiContentNegotiationClient


class TestDoiContentNegotiationClient:
    """Tests for DoiContentNegotiationClient."""

    def test_initialization(self):
        """Test basic initialization."""
        client = DoiContentNegotiationClient()
        assert client.base_url == DoiContentNegotiationClient.BASE_URL

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_without_doi_raises(self, mock_request):
        """Test that enrich without DOI raises ValueError."""
        client = DoiContentNegotiationClient()
        with pytest.raises(ValueError, match="DOI is required"):
            client.enrich()

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_crossref_success(self, mock_request):
        """Test successful enrichment with CrossRef data."""
        # Mock DOI agency response first, then CrossRef metadata response
        mock_request.side_effect = [
            {"agency": "crossref"},  # Agency response
            {  # CrossRef metadata response (wrapped in message)
                "message": {
                    "DOI": "10.1234/test",
                    "title": ["Test Article"],
                    "author": [
                        {"given": "John", "family": "Doe", "name": "John Doe"},
                        {"given": "Jane", "family": "Smith", "name": "Jane Smith"}
                    ],
                    "abstract": "Test abstract",
                    "container-title": ["Test Journal"],
                    "published": {"date-parts": [[2021, 6, 15]]},
                    "is-referenced-by-count": 42,
                    "references-count": 30,
                    "type": "journal-article",
                    "ISSN": ["1234-5678"],
                    "volume": "10",
                    "issue": "3",
                    "page": "123-145",
                    "publisher": "Test Publisher"
                }
            }
        ]

        client = DoiContentNegotiationClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["source"] == "doi_content_negotiation"
        assert result["doi"] == "10.1234/test"
        assert result["agency"] == "crossref"
        assert result["title"] == "Test Article"
        assert len(result["authors"]) == 2
        assert result["authors"][0]["name"] == "John Doe"
        assert result["abstract"] == "Test abstract"
        assert result["journal"] == ["Test Journal"]
        assert result["citation_count"] == 42

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_datacite_success(self, mock_request):
        """Test successful enrichment with DataCite data."""
        # Mock DOI agency response first, then DataCite metadata response
        mock_request.side_effect = [
            {"agency": "datacite"},  # Agency response
            {  # DataCite metadata response
                "data": {
                    "id": "10.5281/test",
                    "type": "dois",
                    "attributes": {
                        "doi": "10.5281/test",
                        "titles": [{"title": "Test Dataset"}],
                        "creators": [
                            {"givenName": "John", "familyName": "Doe", "name": "John Doe"},
                            {"name": "Jane Smith"}
                        ],
                        "descriptions": [{"description": "Test description"}],
                        "container": {"title": "Test Repository"},
                        "dates": [{"date": "2021-06-15", "dateType": "Issued"}],
                        "citationCount": 25,
                        "referenceCount": 15,
                        "types": {"resourceTypeGeneral": "Dataset"},
                        "publisher": "Test Publisher"
                    }
                }
            }
        ]

        client = DoiContentNegotiationClient()
        result = client.enrich(identifier="10.5281/test")

        assert result is not None
        assert result["source"] == "doi_content_negotiation"
        assert result["doi"] == "10.5281/test"
        assert result["agency"] == "datacite"
        assert result["title"] == "Test Dataset"
        assert len(result["authors"]) == 2
        assert result["authors"][0]["name"] == "John Doe"
        assert result["abstract"] == "Test description"
        assert result["journal"] == "Test Repository"
        assert result["citation_count"] == 25

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_no_response(self, mock_request):
        """Test enrichment when API returns None."""
        mock_request.return_value = None

        client = DoiContentNegotiationClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is None

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_empty_crossref(self, mock_request):
        """Test enrichment with empty CrossRef response."""
        mock_request.return_value = {}

        client = DoiContentNegotiationClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is None

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_empty_datacite(self, mock_request):
        """Test enrichment with empty DataCite response."""
        # Mock DOI agency response first, then empty DataCite response
        mock_request.side_effect = [
            {"agency": "datacite"},  # Agency response
            {"data": {}}  # Empty DataCite response
        ]

        client = DoiContentNegotiationClient()
        result = client.enrich(identifier="10.5281/test")

        # Should return result with None/empty values, not None
        assert result is not None
        assert result["title"] is None
        assert result["authors"] == []

    @patch.object(DoiContentNegotiationClient, "_make_request")
    def test_enrich_crossref_minimal(self, mock_request):
        """Test enrichment with minimal CrossRef data."""
        # Mock DOI agency response first, then CrossRef metadata response
        mock_request.side_effect = [
            {"agency": "crossref"},  # Agency response
            {  # Minimal CrossRef metadata response
                "message": {
                    "DOI": "10.1234/test",
                    "title": ["Minimal Article"]
                }
            }
        ]

        client = DoiContentNegotiationClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["title"] == "Minimal Article"
        assert result["authors"] == []
        assert result["abstract"] is None
