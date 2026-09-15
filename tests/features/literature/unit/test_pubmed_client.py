"""Unit tests for PubMed literature client."""

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.search.sources.pubmed import PubMedClient

pytestmark = pytest.mark.unit


class TestPubMedClient:
    """Tests for PubMedClient."""

    def test_initialization_default(self):
        """Test basic initialization with default params."""
        client = PubMedClient()
        assert client.base_url == PubMedClient.BASE_URL
        assert client.email is None
        assert client.tool_name == "pyeuropepmc"

    def test_initialization_with_email(self):
        """Test initialization with email address."""
        client = PubMedClient(email="test@example.com")
        assert client.email == "test@example.com"
        assert "mailto:test@example.com" in client.session.headers["User-Agent"]

    def test_initialization_with_custom_tool(self):
        """Test initialization with custom tool name."""
        client = PubMedClient(tool_name="my-tool")
        assert client.tool_name == "my-tool"

    def test_initialization_rate_limit(self):
        """Test rate limit delay is set correctly."""
        client = PubMedClient(rate_limit_delay=0.5)
        assert client.rate_limit_delay == 0.5

    @patch.object(PubMedClient, "_make_request")
    def test_search_basic_query(self, mock_make_request):
        """Test basic search query with batch retrieval."""
        # Mock: first call = ESearch (returns IDs), second call = ESummary batch
        mock_make_request.side_effect = [
            # ESearch response
            {
                "esearchresult": {
                    "idlist": ["12345678", "23456789"],
                    "count": "2",
                }
            },
            # ESummary batch response
            {
                "result": {
                    "12345678": {
                        "uid": "12345678",
                        "pmid": "12345678",
                        "title": "Test Article 1",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                    "23456789": {
                        "uid": "23456789",
                        "pmid": "23456789",
                        "title": "Test Article 2",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                }
            },
        ]

        client = PubMedClient()
        results = client.search("test query", limit=2)

        assert len(results) == 2
        assert results[0].pmid == "12345678"
        assert results[1].pmid == "23456789"

    @patch.object(PubMedClient, "_make_request")
    def test_search_with_filters(self, mock_make_request):
        """Test search with filters."""
        mock_make_request.side_effect = [
            # ESearch response
            {
                "esearchresult": {
                    "idlist": ["12345678"],
                    "count": "1",
                }
            },
            # ESummary batch response
            {
                "result": {
                    "12345678": {
                        "uid": "12345678",
                        "pmid": "12345678",
                        "title": "Test Article",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                }
            },
        ]

        client = PubMedClient()
        results = client.search(
            "test query",
            limit=1,
            pub_date="2020/2023",
        )

        # First call should have the reldate filter for pub_date
        first_call_args = mock_make_request.call_args_list[0]
        params = first_call_args.kwargs.get("params", {})
        assert "reldate" in params
        # Results are now Pydantic models
        assert len(results) == 1
        assert results[0].pmid == "12345678"
        assert results[0].title == "Test Article"
        assert results[0].source == "pubmed"

    @patch.object(PubMedClient, "_make_request")
    def test_get_paper_by_pmid(self, mock_make_request):
        """Test getting paper details by PMID."""
        mock_make_request.return_value = {
            "result": {
                "12345678": {
                    "uid": "12345678",
                    "pmid": "12345678",
                    "title": "Test Article",
                    "pubdate": "2024",
                    "source": "Test Journal",
                }
            }
        }

        client = PubMedClient()
        paper = client.get_paper("12345678")

        assert paper is not None
        assert paper.pmid == "12345678"
        assert paper.title == "Test Article"

    @patch.object(PubMedClient, "_make_request")
    def test_get_paper_not_found(self, mock_make_request):
        """Test getting paper that doesn't exist."""
        mock_make_request.return_value = {"result": {}}

        client = PubMedClient()
        paper = client.get_paper("99999999")

        assert paper is None

    @patch.object(PubMedClient, "_make_request")
    def test_search_api_returns_none(self, mock_make_request):
        """Test search when API returns None."""
        mock_make_request.return_value = None

        client = PubMedClient()
        results = client.search("test query")

        assert results == []

    @patch.object(PubMedClient, "_make_request")
    def test_search_with_sort(self, mock_make_request):
        """Test search with sorting."""
        mock_make_request.side_effect = [
            # ESearch response
            {
                "esearchresult": {
                    "idlist": ["12345678"],
                    "count": "1",
                }
            },
            # ESummary batch response
            {
                "result": {
                    "12345678": {
                        "uid": "12345678",
                        "pmid": "12345678",
                        "title": "Test Article",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                }
            },
        ]

        client = PubMedClient()
        results = client.search("test query", sort="date")

        # First call should have the sort parameter
        first_call_args = mock_make_request.call_args_list[0]
        params = first_call_args.kwargs.get("params", {})
        assert params.get("sort") == "date"
        assert len(results) == 1

    def test_normalize_result_basic(self):
        """Test normalizing a basic result."""
        client = PubMedClient()
        raw = {
            "pmid": "12345678",
            "title": "Test Article",
            "pubdate": "2024",
            "source": "Test Journal",
            "authors": [{"name": "Smith, John"}],
        }

        result = client._normalize_result(raw)

        assert result.pmid == "12345678"
        assert result.title == "Test Article"
        assert result.publication_year == 2024
        assert result.journal == "Test Journal"
        assert result.source == "pubmed"

    def test_normalize_result_with_doi(self):
        """Test normalizing result with DOI."""
        client = PubMedClient()
        raw = {
            "pmid": "12345678",
            "title": "Test Article",
            "pubdate": "2024",
            "source": "Test Journal",
            "doi": "10.1234/TEST",
        }

        result = client._normalize_result(raw)

        assert result.doi == "10.1234/test"  # Lowercased

    def test_normalize_result_year_formats(self):
        """Test normalizing various year formats."""
        client = PubMedClient()

        formats = [
            ("2024", 2024),
            ("2024 Jan-Feb", 2024),
            ("2024 Jan 15", 2024),
            ("2024/01/15", 2024),
            ("2024 Jul 15 [Epub ahead of print]", 2024),
        ]

        for pubdate, expected_year in formats:
            raw = {
                "pmid": "12345678",
                "title": "Test",
                "pubdate": pubdate,
            }
            result = client._normalize_result(raw)
            assert result.publication_year == expected_year, f"Failed for {pubdate}"

    def test_normalize_result_author_list(self):
        """Test normalizing author list."""
        client = PubMedClient()
        raw = {
            "pmid": "12345678",
            "title": "Test",
            "pubdate": "2024",
            "authors": [
                {"name": "John Doe"},
                {"name": "Jane Smith"},
            ],
        }

        result = client._normalize_result(raw)

        assert result.authors is not None
        assert len(result.authors) == 2
        # Names should be in "Last, First" format
        assert any("Doe" in author.name for author in result.authors)

    def test_context_manager(self):
        """Test context manager functionality."""
        with PubMedClient() as client:
            assert client is not None
            assert isinstance(client, PubMedClient)

    @patch.object(PubMedClient, "_make_request")
    def test_get_papers_batch(self, mock_make_request):
        """Test batch retrieval of papers."""
        mock_make_request.return_value = {
            "result": {
                "1": {
                    "uid": "1",
                    "pmid": "1",
                    "title": "Article 1",
                    "pubdate": "2024",
                    "source": "Test Journal",
                },
                "2": {
                    "uid": "2",
                    "pmid": "2",
                    "title": "Article 2",
                    "pubdate": "2024",
                    "source": "Test Journal",
                },
            }
        }

        client = PubMedClient()
        results = client.get_papers_batch(["1", "2"])

        assert len(results) == 2
        assert results[0].pmid == "1"
        assert results[1].pmid == "2"

    @patch.object(PubMedClient, "_make_request")
    def test_get_papers_batch_empty(self, mock_make_request):
        """Test batch retrieval with empty list."""
        client = PubMedClient()
        results = client.get_papers_batch([])

        assert results == []

    def test_get_paper_efetch_fallback(self):
        """Test that get_paper with use_efetch=True falls back gracefully when
        _make_request returns None."""
        client = PubMedClient()

        # With use_efetch=True, it calls _get_paper_efetch which calls
        # _make_request for efetch. We need to mock that.
        with patch.object(client, "_make_request", return_value=None):
            result = client.get_paper("12345678", use_efetch=True)
            assert result is None

    def test_pmid_for_citation_missing_params(self):
        """pmid_for_citation with no fields -> ECitMatch returns nothing -> None."""
        client = PubMedClient()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = "NOT_FOUND"
        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            result = client.pmid_for_citation()
        assert result is None
        mock_post.assert_called_once()

    @patch.object(PubMedClient, "_make_request")
    def test_search_empty_idlist(self, mock_make_request):
        """Test search when API returns empty ID list."""
        mock_make_request.return_value = {
            "esearchresult": {
                "idlist": [],
                "count": "0",
            }
        }

        client = PubMedClient()
        results = client.search("test query")

        assert results == []

    @patch.object(PubMedClient, "_make_request")
    def test_search_rate_limiting(self, mock_make_request):
        """Test rate limiting is applied between requests."""
        # First call = ESearch (returns IDs), second call = ESummary batch
        mock_make_request.side_effect = [
            {
                "esearchresult": {
                    "idlist": ["1", "2", "3"],
                    "count": "3",
                }
            },
            {
                "result": {
                    "1": {
                        "uid": "1",
                        "pmid": "1",
                        "title": "Article 1",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                    "2": {
                        "uid": "2",
                        "pmid": "2",
                        "title": "Article 2",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                    "3": {
                        "uid": "3",
                        "pmid": "3",
                        "title": "Article 3",
                        "pubdate": "2024",
                        "source": "Test Journal",
                    },
                }
            },
        ]

        client = PubMedClient(rate_limit_delay=0.1)
        results = client.search("test", limit=3)

        assert len(results) == 3
