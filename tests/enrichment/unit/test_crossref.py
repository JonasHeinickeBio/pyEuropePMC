"""Unit tests for CrossRef enrichment client."""

import pytest
from unittest.mock import patch

from pyeuropepmc.enrichment.crossref import CrossRefClient


class TestCrossRefClient:
    """Tests for CrossRefClient."""

    def test_initialization(self):
        """Test basic initialization."""
        client = CrossRefClient()
        assert client.base_url == CrossRefClient.BASE_URL
        assert client.email is None

    def test_initialization_with_email(self):
        """Test initialization with email for polite pool."""
        email = "test@example.com"
        client = CrossRefClient(email=email)
        assert client.email == email
        assert client.session.headers.get("mailto") == email

    @patch.object(CrossRefClient, "_make_request")
    def test_enrich_without_doi_raises(self, mock_request):
        """Test that enrich without DOI raises ValueError."""
        client = CrossRefClient()
        with pytest.raises(ValueError, match="Identifier is required"):
            client.enrich()

    @patch.object(CrossRefClient, "_make_request")
    def test_enrich_success(self, mock_request):
        """Test successful enrichment."""
        # Mock CrossRef API response
        mock_response = {
            "message": {
                "title": ["Test Article"],
                "author": [
                    {"given": "John", "family": "Doe"},
                    {"given": "Jane", "family": "Smith"},
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
                "publisher": "Test Publisher",
            }
        }
        mock_request.return_value = mock_response

        client = CrossRefClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["source"] == "crossref"
        assert result["title"] == "Test Article"
        assert len(result["authors"]) == 2
        assert result["authors"][0] == "John Doe"
        assert result["abstract"] == "Test abstract"
        assert result["journal"] == "Test Journal"
        assert result["publication_date"] == "2021-06-15"
        assert result["citation_count"] == 42
        assert result["references_count"] == 30

    @patch.object(CrossRefClient, "_make_request")
    def test_enrich_no_response(self, mock_request):
        """Test enrichment when API returns None."""
        mock_request.return_value = None

        client = CrossRefClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is None

    @patch.object(CrossRefClient, "_make_request")
    def test_enrich_empty_message(self, mock_request):
        """Test enrichment with empty message."""
        mock_request.return_value = {"message": {}}

        client = CrossRefClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is None

    @patch.object(CrossRefClient, "_make_request")
    def test_enrich_with_license_info(self, mock_request):
        """Test enrichment with license information."""
        mock_response = {
            "message": {
                "title": ["Test Article"],
                "license": [
                    {
                        "URL": "https://creativecommons.org/licenses/by/4.0/",
                        "start": {"date-time": "2021-01-01T00:00:00Z"},
                        "delay-in-days": 0,
                    }
                ],
            }
        }
        mock_request.return_value = mock_response

        client = CrossRefClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["license"] is not None
        assert result["license"]["url"] == "https://creativecommons.org/licenses/by/4.0/"

    @patch.object(CrossRefClient, "_make_request")
    def test_enrich_with_funders(self, mock_request):
        """Test enrichment with funder information."""
        mock_response = {
            "message": {
                "title": ["Test Article"],
                "funder": [
                    {
                        "name": "National Science Foundation",
                        "DOI": "10.13039/100000001",
                        "award": ["1234567"],
                    }
                ],
            }
        }
        mock_request.return_value = mock_response

        client = CrossRefClient()
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["funders"] is not None
        assert len(result["funders"]) == 1
        assert result["funders"][0]["name"] == "National Science Foundation"

    @patch.object(CrossRefClient, "_make_request")
    def test_parse_partial_date(self, mock_request):
        """Test parsing of partial publication dates."""
        # Test year only
        mock_response = {
            "message": {
                "title": ["Test"],
                "published": {"date-parts": [[2021]]},
            }
        }
        mock_request.return_value = mock_response

        client = CrossRefClient()
        result = client.enrich(identifier="10.1234/test")
        assert result["publication_date"] == "2021"

        # Test year and month
        mock_response["message"]["published"]["date-parts"] = [[2021, 6]]
        mock_request.return_value = mock_response
        result = client.enrich(identifier="10.1234/test")
        assert result["publication_date"] == "2021-06"
