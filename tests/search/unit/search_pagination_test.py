import logging
from unittest.mock import patch

import pytest

from pyeuropepmc.search import SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
def test_fetch_all_pages() -> None:
    """Test fetch_all_pages retrieves all pages correctly."""
    client = SearchClient()
    with patch.object(client, "search") as mock_search:
        # Create proper mock responses that match the expected structure
        # Use page_size=10 so that 10 results = full page
        first_page = {
            "hitCount": 200,
            "nextCursorMark": "page2_cursor",
            "resultList": {"result": [{"id": i, "title": f"Paper {i}"} for i in range(10)]},
        }
        second_page = {
            "hitCount": 200,
            # No nextCursorMark to stop pagination
            "resultList": {"result": [{"id": i, "title": f"Paper {i}"} for i in range(10, 20)]},
        }

        mock_search.side_effect = [first_page, second_page]

        results = client.fetch_all_pages("cancer", page_size=10, max_results=None)

        # Should have combined results from both pages
        assert isinstance(results, list)
        assert len(results) == 20  # 10 from each page
        # Should have called search twice (once for each page)
        assert mock_search.call_count == 2

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_empty_results() -> None:
    """Test fetch_all_pages handles empty results correctly."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        # Mock empty response
        mock_search.return_value = {"resultList": {"result": []}}

        results = client.fetch_all_pages("nonexistent")
        assert results == []

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_malformed_response() -> None:
    """Test fetch_all_pages handles malformed response."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        # Mock malformed response (missing resultList)
        mock_search.return_value = {"error": "something went wrong"}

        results = client.fetch_all_pages("test")
        assert results == []

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_string_response() -> None:
    """Test fetch_all_pages handles string response (XML format)."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        # Mock string response (XML format) - but fetch_all_pages expects dict format
        # This test should actually fail gracefully and return empty list
        mock_search.return_value = "<xml>test</xml>"

        results = client.fetch_all_pages("test", format="xml")
        # String responses don't match the expected dict structure, so should return empty
        assert results == []

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_with_max_results() -> None:
    """Test fetch_all_pages with max_results limit."""
    client = SearchClient()

    # Create mock data with many results
    mock_results = [{"id": i, "title": f"Paper {i}"} for i in range(100)]
    mock_response = {
        "hitCount": 1000,
        "nextCursorMark": "next_page",
        "resultList": {
            "result": mock_results,
        },
    }

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        # Test with max_results smaller than available results
        results = client.fetch_all_pages("test", max_results=50)

        # Should only return the first 50 results
        assert len(results) == 50
        assert results[0]["id"] == 0
        assert results[49]["id"] == 49

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_no_next_cursor() -> None:
    """Test fetch_all_pages stops when no nextCursorMark."""
    client = SearchClient()

    mock_response = {
        "hitCount": 2,
        "resultList": {
            "result": [{"id": 1}, {"id": 2}],
            # No nextCursorMark - should stop pagination
        },
    }

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        results = client.fetch_all_pages("test")

        # Should call search only once (no next page)
        assert mock_search.call_count == 1
        assert len(results) == 2

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_repeated_cursor() -> None:
    """Test fetch_all_pages handles repeated cursor (infinite loop protection)."""
    client = SearchClient()

    # First response with nextCursorMark
    first_response = {
        "hitCount": 200,
        "nextCursorMark": "same_cursor",
        "resultList": {
            "result": [{"id": i} for i in range(100)]  # Full page (100 results)
        },
    }
    # Second response with same cursor (should stop due to repeated cursor)
    second_response = {
        "hitCount": 200,
        "nextCursorMark": "same_cursor",  # Same cursor - triggers infinite loop protection
        "resultList": {
            "result": [{"id": i} for i in range(100, 200)]  # Another full page
        },
    }

    with patch.object(client, "search") as mock_search:
        mock_search.side_effect = [first_response, second_response]

        results = client.fetch_all_pages("test", page_size=100)

        # Should call search twice, but stop after detecting repeated cursor
        assert mock_search.call_count == 2
        assert len(results) == 200  # Should have results from both calls

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_partial_last_page() -> None:
    """Test fetch_all_pages with partial results on last page."""
    client = SearchClient()

    # Mock responses: first page full, second page partial
    first_page = {
        "hitCount": 30,
        "nextCursorMark": "page2",
        "resultList": {
            "result": [{"id": i} for i in range(25)],  # Full page
        },
    }
    second_page = {
        "hitCount": 30,
        "resultList": {
            "result": [{"id": i} for i in range(25, 30)],  # Partial page (5 < 25)
            # No nextCursorMark - last page
        },
    }

    with patch.object(client, "search") as mock_search:
        mock_search.side_effect = [first_page, second_page]

        # Use page_size that matches the first page
        results = client.fetch_all_pages("test", page_size=25)

        # Should have all results from both pages
        assert len(results) == 30
        assert results[0]["id"] == 0
        assert results[29]["id"] == 29

    client.close()


@pytest.mark.unit
def test_fetch_all_pages_single_page() -> None:
    """Test fetch_all_pages with single page of results."""
    client = SearchClient()

    single_page_response = {
        "hitCount": 3,
        "resultList": {
            "result": [{"id": 1}, {"id": 2}, {"id": 3}],
            # No nextCursorMark - only one page
        },
    }

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = single_page_response

        results = client.fetch_all_pages("test")

        # Should call search only once
        assert mock_search.call_count == 1
        assert len(results) == 3
        assert results == [{"id": 1}, {"id": 2}, {"id": 3}]

    client.close()
