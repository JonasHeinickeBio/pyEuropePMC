import logging
from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.clients.search import EuropePMCError, SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
def test_europepmc_error_exception() -> None:
    """Test that EuropePMCError can be raised and caught."""
    with pytest.raises(EuropePMCError):
        raise EuropePMCError(ErrorCodes.SEARCH001)


@pytest.mark.unit
def test_search_handles_empty_response() -> None:
    """Test that search handles empty response gracefully."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.return_value = {}

        result = client.search("test")
        assert result == {}

    client.close()


@pytest.mark.unit
def test_search_handles_request_exception() -> None:
    """Test that search handles request exceptions."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.RequestException("Network error")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "NET001" in error_msg or "Network connection failed" in error_msg

    client.close()


@pytest.mark.unit
def test_search_post_handles_empty_response() -> None:
    """Test that search POST handles empty response gracefully."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.return_value = {}

        result = client.search_post("test")
        assert result == {}

    client.close()


@pytest.mark.unit
def test_search_post_sets_correct_headers() -> None:
    """Test that search POST sets correct headers."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.return_value = {"test": "data"}

        client.search_post("test")

        # Verify _make_request was called with POST method
        mock_make_request.assert_called_once()
        args, kwargs = mock_make_request.call_args
        # Should be called with "searchPOST" endpoint and POST method
        assert args[0] == "searchPOST"

    client.close()


@pytest.mark.unit
def test_search_post_handles_request_exception() -> None:
    """Test that search POST handles request exceptions."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.RequestException("Network error")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search_post("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "NET001" in error_msg or "Network connection failed" in error_msg

    client.close()


@pytest.mark.unit
def test_search_handles_connection_error() -> None:
    """Test that search handles connection errors."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "NET001" in error_msg or "Network connection failed" in error_msg

    client.close()


@pytest.mark.unit
def test_search_post_handles_connection_error() -> None:
    """Test that search POST handles connection errors."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search_post("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "NET001" in error_msg or "Network connection failed" in error_msg

    client.close()


@pytest.mark.unit
def test_search_handles_timeout_error() -> None:
    """Test that search handles timeout errors."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search("test")

        # Check for the new error code message (timeout maps to NET002)
        error_msg = str(exc_info.value)
        assert "NET002" in error_msg or "Request timeout" in error_msg

    client.close()


@pytest.mark.unit
def test_search_post_handles_timeout_error() -> None:
    """Test that search POST handles timeout errors."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search_post("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "NET001" in error_msg or "Network connection failed" in error_msg

    client.close()


@pytest.mark.unit
def test_search_handles_http_error() -> None:
    """Test that search handles HTTP errors."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search("test")

        # Check for the new error code message (404 maps to SEARCH006)
        error_msg = str(exc_info.value)
        assert "SEARCH006" in error_msg or "Search endpoint not found" in error_msg

    client.close()


@pytest.mark.unit
def test_search_post_handles_http_error() -> None:
    """Test that search POST handles HTTP errors."""
    client = SearchClient()
    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.side_effect = requests.exceptions.HTTPError("500 Server Error")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search_post("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "NET001" in error_msg or "Network connection failed" in error_msg

    client.close()


@pytest.mark.unit
def test_search_handles_unexpected_error() -> None:
    """Test that search handles unexpected errors."""
    client = SearchClient()
    with patch.object(client, "_extract_search_params") as mock_extract:
        mock_extract.side_effect = ValueError("Unexpected error")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search("test")

        # Check for the new error code message (unexpected errors map to SEARCH003)
        error_msg = str(exc_info.value)
        assert "SEARCH003" in error_msg or "Query too complex" in error_msg

    client.close()


@pytest.mark.unit
def test_search_post_handles_unexpected_error() -> None:
    """Test that search POST handles unexpected errors."""
    client = SearchClient()
    with patch.object(client, "_extract_search_params") as mock_extract:
        mock_extract.side_effect = ValueError("Unexpected error")

        with pytest.raises(EuropePMCError) as exc_info:
            client.search_post("test")

        # Check for the new error code message
        error_msg = str(exc_info.value)
        assert "SEARCH003" in error_msg or "Query too complex" in error_msg

    client.close()


@pytest.mark.unit
def test_search_successful_execution() -> None:
    """Test that search executes successfully without errors."""
    client = SearchClient()
    expected_result = {"hitCount": 1, "resultList": {"result": [{"id": "123"}]}}

    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.return_value = expected_result

        result = client.search("test")

        assert result == expected_result
        mock_make_request.assert_called_once()

    client.close()


@pytest.mark.unit
def test_search_post_successful_execution() -> None:
    """Test that search POST executes successfully without errors."""
    client = SearchClient()
    expected_result = {"hitCount": 1, "resultList": {"result": [{"id": "123"}]}}

    with patch.object(client, "_make_request") as mock_make_request:
        mock_make_request.return_value = expected_result

        result = client.search_post("test")

        assert result == expected_result
        mock_make_request.assert_called_once()

    client.close()
