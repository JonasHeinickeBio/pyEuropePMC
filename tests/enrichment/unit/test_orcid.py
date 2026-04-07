"""Unit tests for ORCID enrichment client."""

import pytest
from unittest.mock import patch

from pyeuropepmc.enrichment.orcid import OrcidClient


class TestOrcidClient:
    """Tests for OrcidClient."""

    def test_initialization(self):
        """Test basic initialization."""
        client = OrcidClient()
        assert client.base_url == OrcidClient.BASE_URL

    @patch.object(OrcidClient, "_make_request")
    def test_enrich_without_orcid_raises(self, mock_request):
        """Test that enrich without ORCID iD raises ValueError."""
        client = OrcidClient()
        with pytest.raises(ValueError, match="ORCID iD is required"):
            client.enrich()

    @patch.object(OrcidClient, "_make_request")
    def test_enrich_success(self, mock_request):
        """Test successful enrichment with ORCID data."""
        # Mock ORCID API response
        mock_response = {
            "orcid-identifier": {
                "uri": "https://orcid.org/0000-0002-1825-0097",
                "path": "0000-0002-1825-0097",
                "host": "orcid.org"
            },
            "person": {
                "name": {
                    "given-names": {"value": "John"},
                    "family-name": {"value": "Doe"},
                    "credit-name": {"value": "John A. Doe"}
                },
                "other-names": {
                    "other-name": [
                        {"content": "J. Doe"},
                        {"content": "Johnny Doe"}
                    ]
                },
                "external-identifiers": {
                    "external-identifier": [
                        {
                            "external-id-type": "Scopus Author ID",
                            "external-id-value": "7004210000",
                            "external-id-url": {"value": "http://www.scopus.com/authid/detail.url?authorId=7004210000"}
                        }
                    ]
                }
            },
            "activities-summary": {
                "works": {
                    "group": [
                        {
                            "work-summary": [
                                {
                                    "put-code": 12345,
                                    "title": {"title": {"value": "Test Publication"}},
                                    "external-ids": {
                                        "external-id": [
                                            {"external-id-type": "doi", "external-id-value": "10.1234/test"}
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
                "employments": {
                    "affiliation-group": [
                        {
                            "summaries": [
                                {
                                    "employment-summary": {
                                        "organization": {
                                            "name": "Test University",
                                            "address": {"city": "Test City", "country": "US"}
                                        },
                                        "start-date": {"year": {"value": "2020"}},
                                        "end-date": {"year": {"value": "2023"}}
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        }
        mock_request.return_value = mock_response

        client = OrcidClient()
        result = client.enrich(identifier="0000-0002-1825-0097")

        assert result is not None
        assert result["source"] == "orcid"
        assert result["orcid"] == "0000-0002-1825-0097"
        assert result["name"]["given"] == "John"
        assert result["name"]["family"] == "Doe"
        assert result["name"]["credit"] == "John A. Doe"
        assert len(result["external_ids"]) == 1
        assert result["external_ids"][0]["type"] == "Scopus Author ID"
        assert len(result["works"]) == 1
        assert result["works"][0]["title"] == "Test Publication"
        assert len(result["employment"]) == 1
        assert result["employment"][0]["organization"]["name"] == "Test University"

    @patch.object(OrcidClient, "_make_request")
    def test_enrich_no_response(self, mock_request):
        """Test enrichment when API returns None."""
        mock_request.return_value = None

        client = OrcidClient()
        result = client.enrich(identifier="0000-0002-1825-0097")

        assert result is None

    @patch.object(OrcidClient, "_make_request")
    def test_enrich_empty_person(self, mock_request):
        """Test enrichment with empty person data."""
        mock_request.return_value = {"person": {}}

        client = OrcidClient()
        result = client.enrich(identifier="0000-0002-1825-0097")

        # Should return result with None/empty values, not None
        assert result is not None
        assert result["name"] is None
        assert result["biography"] is None

    @patch.object(OrcidClient, "_make_request")
    def test_enrich_minimal_profile(self, mock_request):
        """Test enrichment with minimal profile data."""
        mock_response = {
            "orcid-identifier": {"path": "0000-0002-1825-0097"},
            "person": {
                "name": {
                    "given-names": {"value": "John"},
                    "family-name": {"value": "Doe"}
                }
            }
        }
        mock_request.return_value = mock_response

        client = OrcidClient()
        result = client.enrich(identifier="0000-0002-1825-0097")

        assert result is not None
        assert result["name"]["given"] == "John"
        assert result["name"]["family"] == "Doe"
        assert result["external_ids"] == []
        assert result["works"] == []
        assert result["employment"] == []
