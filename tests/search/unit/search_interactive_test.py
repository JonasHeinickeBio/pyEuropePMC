import logging
from unittest.mock import patch

import pytest

from pyeuropepmc.search import SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
def test_interactive_search_unit(search_cancer_json, search_cancer_page2_json) -> None:
    """Test interactive_search basic functionality."""
    client = SearchClient()
    with patch.object(client, "search") as mock_search:
        # Mock search to return first page, then second page
        mock_search.side_effect = [search_cancer_json, search_cancer_page2_json]

        with patch("builtins.input") as mock_input:
            # Simulate user input: view first page, then quit
            mock_input.side_effect = ["", "q"]  # Enter for next page, then quit

            # Should not raise an exception
            client.interactive_search("cancer")

            # Should have called search at least once
            assert mock_search.call_count >= 1

    client.close()


@pytest.mark.unit
def test_interactive_search_string_response() -> None:
    """Test interactive_search handles string response (XML format)."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = "<xml>test response</xml>"

        with patch("builtins.input") as mock_input:
            mock_input.return_value = "q"  # Quit immediately

            # Should handle string response gracefully
            client.interactive_search("test", format="xml")

    client.close()


@pytest.mark.unit
def test_interactive_search_no_hit_count() -> None:
    """Test interactive_search handles response without hitCount."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = {"resultList": {"result": []}}

        with patch("builtins.input") as mock_input:
            mock_input.return_value = "q"  # Quit immediately

            # Should handle missing hitCount gracefully
            client.interactive_search("test")

    client.close()


@pytest.mark.unit
def test_interactive_search_empty_response() -> None:
    """Test interactive_search handles completely empty response."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = {}

        with patch("builtins.input") as mock_input:
            mock_input.return_value = "q"

            # Should handle empty response gracefully
            client.interactive_search("test")

    client.close()


@pytest.mark.unit
def test_interactive_search_with_zero_hits(monkeypatch) -> None:
    """Test interactive_search handles zero hit count."""
    client = SearchClient()

    mock_response = {"hitCount": 0, "resultList": {"result": []}}

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        with patch("builtins.input") as mock_input:
            mock_input.return_value = "q"

            # Should handle zero hits gracefully
            client.interactive_search("nonexistent")

    client.close()


@pytest.mark.unit
def test_interactive_search_fetch_results() -> None:
    """Test interactive_search can fetch additional results."""
    client = SearchClient()

    # Mock responses for multiple pages
    first_response = {
        "hitCount": 100,
        "resultList": {
            "result": [{"id": 1}, {"id": 2}],
            "nextCursorMark": "page2",
        },
    }
    second_response = {
        "hitCount": 100,
        "resultList": {
            "result": [{"id": 3}, {"id": 4}],
            "nextCursorMark": "page3",
        },
    }

    with patch.object(client, "search") as mock_search:
        mock_search.side_effect = [first_response, second_response]

        with patch("builtins.input") as mock_input:
            # View first page, fetch more, then quit
            mock_input.side_effect = ["", "q"]

            client.interactive_search("test")

    client.close()


@pytest.mark.unit
def test_interactive_search_error_handling() -> None:
    """Test interactive_search handles search errors gracefully."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.side_effect = Exception("Network error")

        with patch("builtins.input") as mock_input:
            mock_input.return_value = "q"

            # Should handle search exception gracefully and return empty list
            result = client.interactive_search("test")
            assert result == []  # Should return empty list, not raise exception

    client.close()
