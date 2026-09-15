"""
Unit tests for ROR client.
"""

from unittest.mock import patch

import pytest

from pyeuropepmc.utils.dependencies import is_dependency_available

pytestmark = pytest.mark.skipif(
    not is_dependency_available("cryptography"),
    reason="skipped due to missing cryptography (enrichment dependency)",
)

from pyeuropepmc.features.enrich.sources.ror import RorClient


class TestRorClient:
    """Tests for RorClient."""

    def test_initialization_default(self):
        """Test RorClient with default params."""
        client = RorClient()
        assert client is not None
        assert client.client_id is None

    def test_initialization_with_email(self):
        """Test RorClient with email."""
        client = RorClient(email="test@example.com")
        assert client is not None

    def test_initialization_with_client_id(self):
        """Test RorClient with client ID."""
        client = RorClient(client_id="my-client-id")
        assert client.client_id == "my-client-id"

    def test_initialization_with_cache_config(self):
        """Test RorClient with cache config."""
        client = RorClient(cache_config=None)
        assert client is not None

    def test_enrich_empty_identifier(self):
        """Test enrich with None identifier."""
        client = RorClient()
        result = client.enrich(identifier=None)
        assert result is None

    def test_enrich_empty_string(self):
        """Test enrich with empty string."""
        client = RorClient()
        result = client.enrich(identifier="")
        assert result is None

    def test_normalize_ror_id_basic(self):
        """Test normalizing a basic ROR ID."""
        client = RorClient()
        result = client._normalize_ror_id("0123456789")
        assert result == "0123456789"

    def test_normalize_ror_id_with_url(self):
        """Test normalizing a full ROR URL."""
        client = RorClient()
        result = client._normalize_ror_id("https://ror.org/0123456789")
        assert result == "0123456789"

    def test_normalize_ror_id_with_trailing_slash(self):
        """Test normalizing ROR URL with trailing slash."""
        client = RorClient()
        result = client._normalize_ror_id("https://ror.org/0123456789/")
        assert result == "0123456789"

    def test_normalize_ror_id_double_prefix(self):
        """Test normalizing ROR ID with double prefix."""
        client = RorClient()
        result = client._normalize_ror_id("ror.org/ror.org/01234")
        assert result == "01234"

    def test_normalize_ror_id_invalid_chars(self):
        """Test normalizing invalid ROR ID."""
        client = RorClient()
        result = client._normalize_ror_id("invalid/id!")
        assert result is None

    def test_normalize_ror_id_empty(self):
        """Test normalizing empty string."""
        client = RorClient()
        result = client._normalize_ror_id("")
        assert result is None

    def test_normalize_ror_id_with_hyphens(self):
        """Test normalizing valid ROR ID with hyphens."""
        client = RorClient()
        result = client._normalize_ror_id("https://ror.org/abc-123-def")
        assert result == "abc-123-def"

    def test_enrich_invalid_identifier_format(self):
        """Test enrich with invalid identifier format."""
        client = RorClient()
        result = client.enrich(identifier="not valid!!")
        assert result is None

    def test_enrich_successful(self):
        """Test successful enrichment."""
        client = RorClient()
        mock_data = {
            "id": "https://ror.org/0123456789",
            "status": "active",
            "types": ["Education"],
            "established": 1900,
            "names": [
                {"types": ["ror_display"], "value": "Test University"},
            ],
            "locations": [
                {
                    "geonames_details": {
                        "country_name": "United States",
                        "country_code": "US",
                        "name": "Boston",
                        "lat": 42.36,
                        "lng": -71.06,
                    }
                }
            ],
            "links": [{"type": "website", "value": "https://test.edu"}],
            "external_ids": [
                {"type": "grid", "preferred": "grid.12345.67"},
                {"type": "wikidata", "preferred": "Q12345"},
            ],
            "relationships": [],
            "domains": [],
        }

        with patch.object(client, "_make_request", return_value=mock_data):
            result = client.enrich(identifier="https://ror.org/0123456789")

        assert result is not None
        assert result["ror_id"] == "https://ror.org/0123456789"
        assert result["status"] == "active"
        assert result["display_name"] == "Test University"
        assert result["country"] == "United States"
        assert result["country_code"] == "US"
        assert result["city"] == "Boston"
        assert result["latitude"] == 42.36
        assert result["longitude"] == -71.06
        assert result["website"] == "https://test.edu"
        assert result["grid_id"] == "grid.12345.67"
        assert result["wikidata_id"] == "Q12345"

    def test_enrich_not_found(self):
        """Test enrich when ROR ID not found."""
        client = RorClient()
        with patch.object(client, "_make_request", return_value=None):
            result = client.enrich(identifier="https://ror.org/0000000000")
        assert result is None

    def test_enrich_exception_handling(self):
        """Test enrich handles exceptions."""
        client = RorClient()
        with patch.object(client, "_make_request", side_effect=ConnectionError("Network error")):
            result = client.enrich(identifier="https://ror.org/0123456789")
        assert result is None

    def test_enrich_with_client_id_header(self):
        """Test enrich with client ID header."""
        client = RorClient(client_id="my-client")

        with patch.object(
            client, "_make_request", return_value={"id": "ror.org/01234", "names": []}
        ):
            client.enrich(identifier="ror.org/01234")

    def test_parse_ror_response_minimal(self):
        """Test parsing minimal ROR response."""
        client = RorClient()
        data = {"id": "https://ror.org/01abc23"}
        result = client._parse_ror_response(data)
        assert result["ror_id"] == "https://ror.org/01abc23"
        # names key NOT set since names list was empty (data.get("names", []) is [])
        assert "names" not in result
        assert result["relationships"] == []
        assert result["domains"] == []

    def test_parse_names_with_ror_display(self):
        """Test parsing names with ror_display type."""
        client = RorClient()
        data = {
            "names": [
                {"types": ["ror_display"], "value": "Display Name"},
                {"types": ["label"], "value": "Label Name"},
            ]
        }
        parsed = {}
        client._parse_names(data, parsed)
        assert parsed["display_name"] == "Display Name"

    def test_parse_names_with_label_fallback(self):
        """Test parsing names with label fallback."""
        client = RorClient()
        data = {
            "names": [
                {"types": ["label"], "value": "Label Name"},
                {"types": ["alias"], "value": "Alias Name"},
            ]
        }
        parsed = {}
        client._parse_names(data, parsed)
        assert parsed["display_name"] == "Label Name"

    def test_parse_names_empty(self):
        """Test parsing empty names."""
        client = RorClient()
        parsed = {}
        client._parse_names({"names": []}, parsed)
        assert "display_name" not in parsed

    def test_parse_locations(self):
        """Test parsing locations."""
        client = RorClient()
        data = {
            "locations": [
                {
                    "geonames_details": {
                        "country_name": "Germany",
                        "country_code": "DE",
                        "name": "Berlin",
                        "lat": 52.52,
                        "lng": 13.40,
                    }
                }
            ]
        }
        parsed = {}
        client._parse_locations(data, parsed)
        assert parsed["country"] == "Germany"
        assert parsed["country_code"] == "DE"
        assert parsed["city"] == "Berlin"
        assert parsed["latitude"] == 52.52
        assert parsed["longitude"] == 13.40

    def test_parse_locations_empty(self):
        """Test parsing empty locations."""
        client = RorClient()
        parsed = {}
        client._parse_locations({"locations": []}, parsed)
        assert "country" not in parsed

    def test_parse_locations_no_geonames(self):
        """Test parsing locations without geonames_details."""
        client = RorClient()
        data = {"locations": [{"geonames_details": {}}]}
        parsed = {}
        client._parse_locations(data, parsed)
        # Should not crash, but nothing is extracted
        assert "country" not in parsed

    def test_parse_links(self):
        """Test parsing links."""
        client = RorClient()
        data = {
            "links": [
                {"type": "website", "value": "https://example.com"},
                {"type": "wikipedia", "value": "https://wikipedia.org/Example"},
            ]
        }
        parsed = {}
        client._parse_links(data, parsed)
        assert parsed["website"] == "https://example.com"

    def test_parse_links_no_website(self):
        """Test parsing links without website type."""
        client = RorClient()
        data = {
            "links": [
                {"type": "wikipedia", "value": "https://wikipedia.org/Example"},
            ]
        }
        parsed = {}
        client._parse_links(data, parsed)
        assert "website" not in parsed

    def test_parse_links_empty(self):
        """Test parsing empty links."""
        client = RorClient()
        parsed = {}
        client._parse_links({"links": []}, parsed)
        assert "website" not in parsed

    def test_parse_external_ids(self):
        """Test parsing external IDs."""
        client = RorClient()
        data = {
            "external_ids": [
                {"type": "fundref", "preferred": "100000001"},
                {"type": "grid", "preferred": "grid.12345.67"},
                {"type": "isni", "preferred": "0000000123456789"},
                {"type": "wikidata", "preferred": "Q12345"},
            ]
        }
        parsed = {}
        client._parse_external_ids(data, parsed)
        assert parsed["fundref_id"] == "100000001"
        assert parsed["grid_id"] == "grid.12345.67"
        assert parsed["isni"] == "0000000123456789"
        assert parsed["wikidata_id"] == "Q12345"

    def test_parse_external_ids_empty(self):
        """Test parsing empty external IDs."""
        client = RorClient()
        parsed = {}
        client._parse_external_ids({"external_ids": []}, parsed)
        assert "fundref_id" not in parsed

    def test_parse_external_ids_unknown_type(self):
        """Test parsing external IDs with unknown type."""
        client = RorClient()
        data = {
            "external_ids": [
                {"type": "unknown_type", "preferred": "some_value"},
            ]
        }
        parsed = {}
        client._parse_external_ids(data, parsed)
        assert len(parsed) == 1  # only external_ids list was set
        assert "external_ids" in parsed
