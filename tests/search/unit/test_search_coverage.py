"""
Additional unit tests for SearchClient to improve test coverage.

This module focuses on testing edge cases, error paths, and less common scenarios
to achieve higher test coverage for the search module.
"""

from unittest.mock import Mock, patch
import pytest
import requests

from pyeuropepmc.clients.search import SearchClient
from pyeuropepmc.core.exceptions import SearchError, APIClientError
from pyeuropepmc.core.error_codes import ErrorCodes


pytestmark = pytest.mark.unit


class TestSearchClientCoverage:
    """Additional test coverage for SearchClient edge cases."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.client = SearchClient()

    def teardown_method(self):
        """Clean up after each test method."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    def test_make_request_with_network_error(self):
        """Test _make_request with network error."""
        with patch.object(
            self.client, "_get", side_effect=requests.RequestException("Network error")
        ):
            with pytest.raises(SearchError) as exc_info:
                self.client._make_request("search", {"query": "cancer", "format": "json"})

            error_message = str(exc_info.value)
            assert "NET001" in error_message or "Network connection failed" in error_message

    def test_make_request_with_http_404_error(self):
        """Test _make_request with 404 HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.HTTPError("Not Found")
        http_error.response = mock_response

        with patch.object(self.client, "_get", side_effect=http_error):
            with pytest.raises(SearchError) as exc_info:
                self.client._make_request("search", {"query": "cancer", "format": "json"})

            error_message = str(exc_info.value)
            assert "HTTP404" in error_message or "Resource not found" in error_message

    def test_make_request_with_http_403_error(self):
        """Test _make_request with 403 HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 403
        http_error = requests.HTTPError("Forbidden")
        http_error.response = mock_response

        with patch.object(self.client, "_get", side_effect=http_error):
            with pytest.raises(SearchError) as exc_info:
                self.client._make_request("search", {"query": "cancer", "format": "json"})

            error_message = str(exc_info.value)
            assert "HTTP403" in error_message or "Access forbidden" in error_message

    def test_make_request_with_http_500_error(self):
        """Test _make_request with 500 HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.HTTPError("Server Error")
        http_error.response = mock_response

        with patch.object(self.client, "_get", side_effect=http_error):
            with pytest.raises(SearchError) as exc_info:
                self.client._make_request("search", {"query": "cancer", "format": "json"})

            error_message = str(exc_info.value)
            assert "HTTP500" in error_message or "Server internal error" in error_message

    def test_make_request_with_api_client_error(self):
        """Test _make_request with APIClientError."""
        with patch.object(self.client, "_get", side_effect=APIClientError(ErrorCodes.NET001)):
            with pytest.raises(SearchError) as exc_info:
                self.client._make_request("search", {"query": "cancer", "format": "json"})

            error_message = str(exc_info.value)
            assert "NET001" in error_message or "Network connection failed" in error_message

    def test_make_request_with_invalid_format(self):
        """Test _make_request with invalid format."""
        with pytest.raises(SearchError) as exc_info:
            self.client._make_request("search", {"query": "cancer", "format": "invalid"})

        error_message = str(exc_info.value)
        assert "SEARCH004" in error_message or "Invalid format parameter" in error_message

    def test_make_request_with_valid_formats(self):
        """Test _make_request with all valid formats."""
        mock_response = Mock(spec=requests.Response)
        mock_response.text = '{"hitCount": 0, "resultList": {"result": []}}'
        mock_response.status_code = 200

        valid_formats = ["json", "xml", "dc", "lite", "idlist"]

        for format_type in valid_formats:
            with patch.object(self.client, "_get", return_value=mock_response):
                # Should not raise an exception
                result = self.client._make_request(
                    "search", {"query": "cancer", "format": format_type}
                )
                assert result is not None

    def test_search_with_page_size_validation(self):
        """Test search with page size validation."""
        with pytest.raises(SearchError) as exc_info:
            self.client.search("cancer", page_size=1001)

        error_message = str(exc_info.value)
        assert (
            "SEARCH002" in error_message or "Page size must be between 1 and 1000" in error_message
        )

    def test_search_with_invalid_page_size_zero(self):
        """Test search with page size of zero."""
        with pytest.raises(SearchError) as exc_info:
            self.client.search("cancer", page_size=0)

        error_message = str(exc_info.value)
        assert (
            "SEARCH002" in error_message or "Page size must be between 1 and 1000" in error_message
        )

    def test_search_with_invalid_page_size_negative(self):
        """Test search with negative page size."""
        with pytest.raises(SearchError) as exc_info:
            self.client.search("cancer", page_size=-5)

        error_message = str(exc_info.value)
        assert (
            "SEARCH002" in error_message or "Page size must be between 1 and 1000" in error_message
        )

    def test_search_all_with_max_results_zero(self):
        """Test search_all with max_results of zero."""
        result = self.client.search_all("cancer", max_results=0)
        assert result == []

    def test_search_all_with_max_results_none(self):
        """Test search_all with max_results of None."""
        # Mock the search method to return properly parsed JSON response
        # Simulate multiple pages by changing the nextCursorMark
        page_responses = [
            {
                "hitCount": 5,
                "resultList": {"result": [{"id": "1"}]},
                "nextCursorMark": "page2",
            },
            {
                "hitCount": 5,
                "resultList": {"result": [{"id": "2"}]},
                "nextCursorMark": "page3",
            },
            {
                "hitCount": 5,
                "resultList": {"result": [{"id": "3"}]},
                "nextCursorMark": "page4",
            },
            {
                "hitCount": 5,
                "resultList": {"result": [{"id": "4"}]},
                "nextCursorMark": "page5",
            },
            {
                "hitCount": 5,
                "resultList": {"result": [{"id": "5"}]},
                "nextCursorMark": "page5",  # Same cursor indicates no more pages
            },
        ]

        with patch.object(self.client, "search", side_effect=page_responses):
            result = self.client.search_all("cancer", max_results=None, page_size=1)
            assert len(result) == 5  # Should fetch all available results

    def test_search_all_with_negative_max_results(self):
        """Test search_all with negative max_results."""
        result = self.client.search_all("cancer", max_results=-5)
        assert result == []

    def test_interactive_search_with_user_input_zero(self):
        """Test interactive_search when user inputs 0."""
        mock_response = {"hitCount": 10, "resultList": {"result": [{"id": "1"}]}}

        with patch.object(self.client, "search", return_value=mock_response), patch(
            "builtins.input", return_value="0"
        ):
            result = self.client.interactive_search("cancer")
            assert result == []  # Should return empty list when user inputs 0

    def test_prompt_user_for_result_count_with_invalid_input(self):
        """Test _prompt_user_for_result_count with invalid input then valid."""
        # Mock multiple inputs: invalid, then valid
        side_effects = ["invalid", "abc", "-1", "10"]

        with patch("builtins.input", side_effect=side_effects):
            result = self.client._prompt_user_for_result_count(100, "cancer")
            assert result == 10

    def test_prompt_user_for_result_count_with_max_exceeded(self):
        """Test _prompt_user_for_result_count with input exceeding max."""
        side_effects = ["1000", "50"]  # First input exceeds max, second is valid

        with patch("builtins.input", side_effect=side_effects):
            result = self.client._prompt_user_for_result_count(100, "cancer")
            assert result == 50

    def test_prompt_user_for_result_count_with_zero_input(self):
        """Test _prompt_user_for_result_count with zero input."""
        with patch("builtins.input", return_value="0"):
            result = self.client._prompt_user_for_result_count(100, "cancer")
            assert result == 0

    def test_prompt_user_for_result_count_with_negative_input(self):
        """Test _prompt_user_for_result_count with negative input then valid."""
        side_effects = ["-5", "25"]

        with patch("builtins.input", side_effect=side_effects):
            result = self.client._prompt_user_for_result_count(100, "cancer")
            assert result == 25

    def test_fetch_interactive_results(self):
        """Test _fetch_interactive_results method."""
        mock_results = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        with patch.object(self.client, "search_all", return_value=mock_results):
            result = self.client._fetch_interactive_results("cancer", 3)
            assert result == mock_results
            assert len(result) == 3

    def test_search_and_parse_with_invalid_format(self):
        """Test search_and_parse with invalid format."""
        with pytest.raises(SearchError) as exc_info:
            self.client.search_and_parse("cancer", format="invalid")

        error_message = str(exc_info.value)
        assert "SEARCH004" in error_message or "Invalid format parameter" in error_message

    def test_search_and_parse_with_empty_results(self):
        """Test search_and_parse with empty search results."""
        # Mock a valid API response with no results
        empty_response = {"hitCount": 0, "resultList": {"result": []}}

        with patch.object(self.client, "search", return_value=empty_response), patch(
            "pyeuropepmc.processing.search_parser.EuropePMCParser.parse_json", return_value=[]
        ):
            result = self.client.search_and_parse("cancer", format="json")
            assert result == []

    def test_search_and_parse_with_parsing_error(self):
        """Test search_and_parse with parsing error."""
        # Mock a valid dict response (not a list) so type checking passes
        mock_results = {"hitCount": 1, "resultList": {"result": [{"id": "1"}]}}

        with (
            patch.object(self.client, "search", return_value=mock_results),
            patch(
                "pyeuropepmc.processing.search_parser.EuropePMCParser.parse_json",
                side_effect=Exception("Parse error"),
            ),
        ):
            with pytest.raises(SearchError) as exc_info:
                self.client.search_and_parse("cancer", format="json")

            error_message = str(exc_info.value)
            assert (
                "SEARCH005" in error_message or "Failed to parse search results" in error_message
            )

    def test_get_hit_count_with_network_error(self):
        """Test get_hit_count with network error."""
        with patch.object(
            self.client, "_make_request", side_effect=SearchError(ErrorCodes.SEARCH001)
        ):
            with pytest.raises(SearchError) as exc_info:
                self.client.get_hit_count("cancer")

            error_message = str(exc_info.value)
            assert "SEARCH001" in error_message or "Invalid search query format" in error_message

    def test_get_hit_count_with_invalid_response(self):
        """Test get_hit_count with invalid JSON response."""
        # Mock search to return a string instead of a dict to trigger the error path
        with patch.object(self.client, "search", return_value="invalid json string"):
            with pytest.raises(SearchError) as exc_info:
                self.client.get_hit_count("cancer")

            error_message = str(exc_info.value)
            assert "SEARCH003" in error_message or "Query too complex" in error_message
