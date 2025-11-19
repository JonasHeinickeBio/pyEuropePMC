"""Unit tests for Unpaywall enrichment client."""

import pytest
from unittest.mock import patch

from pyeuropepmc.enrichment.unpaywall import UnpaywallClient


class TestUnpaywallClient:
    """Tests for UnpaywallClient."""

    def test_initialization_requires_email(self):
        """Test that initialization requires email."""
        with pytest.raises(ValueError, match="Email is required"):
            UnpaywallClient(email="")

    def test_initialization_with_email(self):
        """Test initialization with email."""
        email = "test@example.com"
        client = UnpaywallClient(email=email)
        assert client.email == email
        assert client.base_url == UnpaywallClient.BASE_URL

    @patch.object(UnpaywallClient, "_make_request")
    def test_enrich_without_doi_raises(self, mock_request):
        """Test that enrich without DOI raises ValueError."""
        client = UnpaywallClient(email="test@example.com")
        with pytest.raises(ValueError, match="DOI is required"):
            client.enrich()

    @patch.object(UnpaywallClient, "_make_request")
    def test_enrich_success_open_access(self, mock_request):
        """Test successful enrichment for open access paper."""
        mock_response = {
            "is_oa": True,
            "oa_status": "gold",
            "best_oa_location": {
                "url": "https://example.com/paper.pdf",
                "url_for_pdf": "https://example.com/paper.pdf",
                "url_for_landing_page": "https://example.com/paper",
                "version": "publishedVersion",
                "license": "cc-by",
                "host_type": "publisher",
                "evidence": "open (via free pdf)",
            },
            "oa_locations": [
                {
                    "url": "https://example.com/paper.pdf",
                    "url_for_pdf": "https://example.com/paper.pdf",
                    "version": "publishedVersion",
                    "license": "cc-by",
                    "host_type": "publisher",
                }
            ],
            "first_oa_date": "2021-01-01",
            "journal_is_oa": True,
            "journal_is_in_doaj": True,
            "publisher": "Test Publisher",
            "year": 2021,
        }
        mock_request.return_value = mock_response

        client = UnpaywallClient(email="test@example.com")
        result = client.enrich(doi="10.1234/test")

        assert result is not None
        assert result["source"] == "unpaywall"
        assert result["is_oa"] is True
        assert result["oa_status"] == "gold"
        assert result["best_oa_location"] is not None
        assert result["best_oa_location"]["url"] == "https://example.com/paper.pdf"
        assert result["journal_is_oa"] is True

    @patch.object(UnpaywallClient, "_make_request")
    def test_enrich_success_closed_access(self, mock_request):
        """Test successful enrichment for closed access paper."""
        mock_response = {
            "is_oa": False,
            "oa_status": "closed",
            "best_oa_location": None,
            "oa_locations": [],
            "first_oa_date": None,
            "journal_is_oa": False,
            "journal_is_in_doaj": False,
            "publisher": "Test Publisher",
            "year": 2021,
        }
        mock_request.return_value = mock_response

        client = UnpaywallClient(email="test@example.com")
        result = client.enrich(doi="10.1234/test")

        assert result is not None
        assert result["is_oa"] is False
        assert result["oa_status"] == "closed"
        assert result["best_oa_location"] is None

    @patch.object(UnpaywallClient, "_make_request")
    def test_enrich_with_embargoed_locations(self, mock_request):
        """Test enrichment with embargoed OA locations."""
        mock_response = {
            "is_oa": False,
            "oa_status": "closed",
            "best_oa_location": None,
            "oa_locations": [],
            "oa_locations_embargoed": [
                {
                    "url": "https://example.com/paper.pdf",
                    "version": "acceptedVersion",
                    "license": "cc-by-nc",
                }
            ],
            "journal_is_oa": False,
            "journal_is_in_doaj": False,
        }
        mock_request.return_value = mock_response

        client = UnpaywallClient(email="test@example.com")
        result = client.enrich(doi="10.1234/test")

        assert result is not None
        assert result["oa_locations_embargoed"] is not None
        assert len(result["oa_locations_embargoed"]) == 1

    @patch.object(UnpaywallClient, "_make_request")
    def test_enrich_no_response(self, mock_request):
        """Test enrichment when API returns None."""
        mock_request.return_value = None

        client = UnpaywallClient(email="test@example.com")
        result = client.enrich(doi="10.1234/test")

        assert result is None

    @patch.object(UnpaywallClient, "_make_request")
    def test_enrich_passes_email_param(self, mock_request):
        """Test that email is passed as parameter."""
        mock_request.return_value = {"is_oa": False, "oa_status": "closed"}

        client = UnpaywallClient(email="test@example.com")
        client.enrich(doi="10.1234/test")

        # Check that email was passed as parameter
        call_args = mock_request.call_args
        assert call_args[1]["params"]["email"] == "test@example.com"
