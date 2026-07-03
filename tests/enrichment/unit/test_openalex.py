"""Unit tests for OpenAlex enrichment client."""

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.enrichment.openalex import OpenAlexClient


class TestOpenAlexClient:
    """Tests for OpenAlexClient."""

    def test_initialization_default(self):
        """Test basic initialization with default params."""
        client = OpenAlexClient()
        assert client.base_url == OpenAlexClient.BASE_URL
        assert client.email is None
        assert client.enable_ror_enrichment is True
        assert client.ror_client is not None

    def test_initialization_with_email(self):
        """Test initialization with email for polite pool."""
        client = OpenAlexClient(email="test@example.com")
        assert client.email == "test@example.com"
        assert "mailto:test@example.com" in client.session.headers["User-Agent"]

    def test_initialization_without_ror_enrichment(self):
        """Test initialization with ROR enrichment disabled."""
        client = OpenAlexClient(enable_ror_enrichment=False)
        assert client.enable_ror_enrichment is False
        assert client.ror_client is None

    def test_initialization_ror_client_created(self):
        """Test RorClient is created when ROR enrichment enabled."""
        client = OpenAlexClient()
        assert client.ror_client is not None
        assert hasattr(client.ror_client, "enrich")

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_with_doi(self, mock_request):
        """Test enrich with DOI via identifier parameter."""
        mock_request.return_value = {"id": "W123", "title": "Test"}
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(identifier="10.1234/test")
        assert result is not None
        assert result["openalex_id"] == "W123"
        mock_request.assert_called_once_with(endpoint="doi:10.1234/test", use_cache=True)

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_with_openalex_id_plain(self, mock_request):
        """Test enrich with plain OpenAlex ID (no URL prefix)."""
        mock_request.return_value = {"id": "W123", "title": "Test"}
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(openalex_id="W123")
        assert result is not None
        assert result["openalex_id"] == "W123"
        mock_request.assert_called_once_with(endpoint="W123", use_cache=True)

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_with_openalex_id_url(self, mock_request):
        """Test enrich with OpenAlex URL (strips https://openalex.org/ prefix)."""
        mock_request.return_value = {"id": "W123", "title": "Test"}
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(openalex_id="https://openalex.org/W123")
        assert result is not None
        assert result["openalex_id"] == "W123"
        mock_request.assert_called_once_with(endpoint="W123", use_cache=True)

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_without_identifier_raises(self, mock_request):
        """Test enrich without identifier or openalex_id raises ValueError."""
        client = OpenAlexClient()
        with pytest.raises(ValueError, match="Either identifier or OpenAlex ID is required"):
            client.enrich()

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_api_returns_none(self, mock_request):
        """Test enrich when _make_request returns None."""
        mock_request.return_value = None
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(identifier="10.1234/test")
        assert result is None

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_parse_exception_returns_none(self, mock_request):
        """Test enrich returns None when _parse_openalex_response raises."""
        mock_request.return_value = {"id": "W123"}
        client = OpenAlexClient(enable_ror_enrichment=False)
        with patch.object(
            client, "_parse_openalex_response", side_effect=ValueError("parse error")
        ):
            result = client.enrich(identifier="10.1234/test")
        assert result is None

    @patch.object(OpenAlexClient, "_make_request")
    def test_parse_response_full(self, mock_request):
        """Test parsing a full OpenAlex response with all fields."""
        mock_response = {
            "id": "W123456789",
            "title": "Test Article",
            "publication_year": 2023,
            "publication_date": "2023-06-15",
            "type": "article",
            "cited_by_count": 42,
            "doi": "https://doi.org/10.1234/test",
            "ids": {"pmid": "12345"},
            "abstract_inverted_index": {"the": [0, 5]},
            "referenced_works_count": 30,
            "related_works": ["W111", "W222"],
            "authorships": [
                {
                    "author": {
                        "id": "A1",
                        "display_name": "John Doe",
                        "orcid": "0000-0001-2345-6789",
                    },
                    "author_position": "first",
                    "institutions": [
                        {
                            "id": "I1",
                            "display_name": "University of Test",
                            "country_code": "US",
                            "type": "education",
                            "ror": "https://ror.org/012345678",
                        }
                    ],
                }
            ],
            "topics": [
                {"id": "T1", "display_name": "Biology", "score": 0.95},
                {"id": "T2", "display_name": "Genetics", "score": 0.80},
            ],
            "primary_location": {
                "source": {
                    "id": "S1",
                    "display_name": "Test Journal",
                    "issn": "1234-5678",
                    "type": "journal",
                    "is_oa": True,
                }
            },
            "open_access": {
                "is_oa": True,
                "oa_status": "gold",
                "oa_url": "https://example.com/oa",
            },
            "biblio": {
                "volume": "10",
                "issue": "3",
                "first_page": "123",
                "last_page": "145",
            },
        }
        mock_request.return_value = mock_response
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["source"] == "openalex"
        assert result["openalex_id"] == "W123456789"
        assert result["title"] == "Test Article"
        assert result["publication_year"] == 2023
        assert result["publication_date"] == "2023-06-15"
        assert result["type"] == "article"
        assert result["citation_count"] == 42
        assert result["cited_by_count"] == 42
        assert result["is_oa"] is True
        assert result["oa_status"] == "gold"
        assert result["oa_url"] == "https://example.com/oa"
        assert result["doi"] == "https://doi.org/10.1234/test"
        assert result["ids"] == {"pmid": "12345"}
        assert result["abstract_inverted_index"] == {"the": [0, 5]}
        assert result["referenced_works_count"] == 30
        assert result["related_works"] == ["W111", "W222"]

        assert len(result["authors"]) == 1
        assert result["authors"][0]["display_name"] == "John Doe"
        assert result["authors"][0]["orcid"] == "0000-0001-2345-6789"
        assert result["authors"][0]["position"] == "first"
        assert len(result["authors"][0]["institutions"]) == 1
        assert result["authors"][0]["institutions"][0]["display_name"] == "University of Test"
        assert result["authors"][0]["institutions"][0]["country"] == "US"

        assert len(result["topics"]) == 2
        assert result["topics"][0]["display_name"] == "Biology"
        assert result["topics"][1]["display_name"] == "Genetics"

        assert result["venue"]["display_name"] == "Test Journal"
        assert result["venue"]["issn"] == "1234-5678"
        assert result["venue"]["type"] == "journal"
        assert result["venue"]["is_oa"] is True

        assert result["biblio"]["volume"] == "10"
        assert result["biblio"]["first_page"] == "123"

    @patch.object(OpenAlexClient, "_make_request")
    def test_parse_response_minimal(self, mock_request):
        """Test parsing a minimal OpenAlex response with only an ID."""
        mock_request.return_value = {"id": "W999"}
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["openalex_id"] == "W999"
        assert result["title"] is None
        assert result["publication_year"] is None
        assert result["authors"] is None
        assert result["topics"] is None
        assert result["institutions"] is None
        assert result["venue"] is None
        assert result["biblio"] is None
        assert result["citation_count"] == 0
        assert result["is_oa"] is False
        assert result["oa_status"] == "closed"

    @patch.object(OpenAlexClient, "_make_request")
    def test_parse_response_no_authorships(self, mock_request):
        """Test parsing response with empty authorships list."""
        mock_request.return_value = {
            "id": "W555",
            "title": "No Authors",
            "authorships": [],
        }
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["authors"] is None
        assert result["institutions"] is None

    @patch.object(OpenAlexClient, "_make_request")
    def test_parse_response_no_primary_location(self, mock_request):
        """Test parsing response without primary_location."""
        mock_request.return_value = {
            "id": "W777",
            "title": "No Venue",
        }
        client = OpenAlexClient(enable_ror_enrichment=False)
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["venue"] is None
        assert result["biblio"] is None

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_institutions_ror_success(self, mock_request):
        """Test institution enrichment with successful ROR lookup."""
        mock_request.return_value = {
            "id": "W1",
            "authorships": [
                {
                    "author": {"id": "A1", "display_name": "John Doe"},
                    "author_position": "first",
                    "institutions": [
                        {
                            "id": "I1",
                            "display_name": "Test University",
                            "country_code": "US",
                            "type": "education",
                            "ror": "https://ror.org/012345678",
                        }
                    ],
                }
            ],
        }
        client = OpenAlexClient(enable_ror_enrichment=True)
        ror_data = {
            "ror_id": "https://ror.org/012345678",
            "display_name": "Enriched University",
            "country": "United States",
        }
        with patch.object(client.ror_client, "enrich", return_value=ror_data):
            result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert len(result["institutions"]) == 1
        assert result["institutions"][0]["display_name"] == "Enriched University"
        assert result["institutions"][0]["country"] == "United States"
        assert result["institutions"][0]["id"] == "I1"
        assert result["institutions"][0]["type"] == "education"

        assert result["authors"][0]["institutions"][0]["display_name"] == "Enriched University"

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_institutions_ror_failure(self, mock_request):
        """Test institution enrichment when ROR returns None."""
        mock_request.return_value = {
            "id": "W1",
            "authorships": [
                {
                    "author": {"id": "A1", "display_name": "John Doe"},
                    "author_position": "first",
                    "institutions": [
                        {
                            "id": "I1",
                            "display_name": "Test University",
                            "country_code": "US",
                            "type": "education",
                            "ror": "https://ror.org/012345678",
                        }
                    ],
                }
            ],
        }
        client = OpenAlexClient(enable_ror_enrichment=True)
        with patch.object(client.ror_client, "enrich", return_value=None):
            result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert len(result["institutions"]) == 1
        assert result["institutions"][0]["display_name"] == "Test University"

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_institutions_ror_invalid_format(self, mock_request):
        """Test invalid ROR IDs (with / but no ror.org) are skipped."""
        mock_request.return_value = {
            "id": "W1",
            "authorships": [
                {
                    "author": {"id": "A1", "display_name": "John Doe"},
                    "author_position": "first",
                    "institutions": [
                        {
                            "id": "I1",
                            "display_name": "Test University",
                            "ror": "https://doi.org/10.1234/rando",
                        }
                    ],
                }
            ],
        }
        client = OpenAlexClient(enable_ror_enrichment=True)
        with patch.object(client.ror_client, "enrich", return_value={"foo": "bar"}) as mock_ror:
            result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert len(result["institutions"]) == 1
        assert result["institutions"][0]["display_name"] == "Test University"
        mock_ror.assert_not_called()

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_institutions_ror_no_ror_id(self, mock_request):
        """Test institution without a ROR ID is not collected for enrichment."""
        mock_request.return_value = {
            "id": "W1",
            "authorships": [
                {
                    "author": {"id": "A1", "display_name": "John Doe"},
                    "author_position": "first",
                    "institutions": [
                        {
                            "id": "I1",
                            "display_name": "Test University",
                            "ror": None,
                        }
                    ],
                }
            ],
        }
        client = OpenAlexClient(enable_ror_enrichment=True)
        with patch.object(client.ror_client, "enrich", return_value={"foo": "bar"}) as mock_ror:
            result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["institutions"] is None
        assert result["authors"][0]["institutions"][0]["display_name"] == "Test University"
        mock_ror.assert_not_called()

    def test_update_authors_ror_matching(self):
        """Test updating authors when ROR IDs match enriched institutions."""
        client = OpenAlexClient(enable_ror_enrichment=False)
        authors = [
            {
                "display_name": "John Doe",
                "institutions": [
                    {
                        "id": "I1",
                        "display_name": "Old Name",
                        "ror_id": "https://ror.org/012345678",
                    }
                ],
            }
        ]
        enriched = [
            {
                "id": "I1",
                "display_name": "New Name",
                "ror_id": "https://ror.org/012345678",
                "country": "US",
            }
        ]
        updated = client._update_authors_with_ror_data(authors, enriched)
        assert len(updated) == 1
        assert len(updated[0]["institutions"]) == 1
        assert updated[0]["institutions"][0]["display_name"] == "New Name"
        assert updated[0]["institutions"][0]["country"] == "US"
        assert updated[0]["institutions"][0]["id"] == "I1"

    def test_update_authors_ror_no_match(self):
        """Test updating authors when ROR IDs do not match."""
        client = OpenAlexClient(enable_ror_enrichment=False)
        authors = [
            {
                "display_name": "John Doe",
                "institutions": [
                    {
                        "id": "I1",
                        "display_name": "Old Name",
                        "ror_id": "https://ror.org/000000000",
                    }
                ],
            }
        ]
        enriched = [
            {
                "id": "I1",
                "display_name": "New Name",
                "ror_id": "https://ror.org/999999999",
            }
        ]
        updated = client._update_authors_with_ror_data(authors, enriched)
        assert len(updated) == 1
        assert len(updated[0]["institutions"]) == 1
        assert updated[0]["institutions"][0]["display_name"] == "Old Name"

    def test_update_authors_no_institutions(self):
        """Test updating authors when author has no institutions."""
        client = OpenAlexClient(enable_ror_enrichment=False)
        authors = [
            {
                "display_name": "John Doe",
                "institutions": None,
            }
        ]
        enriched = [
            {
                "ror_id": "https://ror.org/012345678",
                "display_name": "Test",
            }
        ]
        updated = client._update_authors_with_ror_data(authors, enriched)
        assert len(updated) == 1
        assert updated[0]["institutions"] is None

    def test_update_authors_multiple_authors_mixed(self):
        """Test updating multiple authors with mixed match/no-match."""
        client = OpenAlexClient(enable_ror_enrichment=False)
        authors = [
            {
                "display_name": "Author A",
                "institutions": [
                    {
                        "id": "I1",
                        "display_name": "Old Name",
                        "ror_id": "https://ror.org/AAA",
                    }
                ],
            },
            {
                "display_name": "Author B",
                "institutions": [
                    {
                        "id": "I2",
                        "display_name": "Keep Me",
                        "ror_id": "https://ror.org/BBB",
                    }
                ],
            },
        ]
        enriched = [
            {
                "id": "I1",
                "display_name": "New Name",
                "ror_id": "https://ror.org/AAA",
            }
        ]
        updated = client._update_authors_with_ror_data(authors, enriched)
        assert len(updated) == 2
        assert updated[0]["institutions"][0]["display_name"] == "New Name"
        assert updated[1]["institutions"][0]["display_name"] == "Keep Me"

    @patch.object(OpenAlexClient, "_make_request")
    def test_ror_enrichment_disabled(self, mock_request):
        """Test when ROR enrichment is disabled, no enrichment occurs."""
        mock_request.return_value = {
            "id": "W1",
            "authorships": [
                {
                    "author": {"id": "A1", "display_name": "John Doe"},
                    "author_position": "first",
                    "institutions": [
                        {
                            "id": "I1",
                            "display_name": "Test University",
                            "ror": "https://ror.org/012345678",
                        }
                    ],
                }
            ],
        }
        client = OpenAlexClient(enable_ror_enrichment=False)
        assert client.ror_client is None
        result = client.enrich(identifier="10.1234/test")

        assert result is not None
        assert result["institutions"] is None
        assert result["authors"][0]["institutions"][0]["display_name"] == "Test University"

    @patch.object(OpenAlexClient, "_make_request")
    def test_enrich_with_use_cache_false(self, mock_request):
        """Test enrich with use_cache=False is passed to _make_request."""
        mock_request.return_value = {"id": "W123"}
        client = OpenAlexClient(enable_ror_enrichment=False)
        client.enrich(identifier="10.1234/test", use_cache=False)
        mock_request.assert_called_once_with(endpoint="doi:10.1234/test", use_cache=False)
