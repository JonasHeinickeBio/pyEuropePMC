import logging
from unittest.mock import patch

import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import SearchError
from pyeuropepmc.features.literature.search import SearchClient

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
    """A non-JSON answer (``format="xml"``) is an error, not "no results"."""
    client = SearchClient()

    with (
        patch.object(client, "search", return_value="<xml>test response</xml>"),
        patch("builtins.input") as mock_input,
        pytest.raises(SearchError) as caught,
    ):
        client.interactive_search("test", format="xml")

    assert caught.value.error_code == ErrorCodes.SEARCH005
    assert "non-JSON format" in str(caught.value.context["error"])
    mock_input.assert_not_called()
    client.close()


@pytest.mark.unit
@pytest.mark.parametrize("response", [{"resultList": {"result": []}}, {}, None, ["x"]])
def test_interactive_search_without_hit_count(response) -> None:
    """A response with no hit count is an error: it cannot tell whether anything matched."""
    client = SearchClient()

    with (
        patch.object(client, "search", return_value=response),
        patch("builtins.input") as mock_input,
        pytest.raises(SearchError) as caught,
    ):
        client.interactive_search("test")

    assert caught.value.error_code == ErrorCodes.SEARCH005
    mock_input.assert_not_called()
    client.close()


@pytest.mark.unit
def test_interactive_search_quit_returns_an_empty_list() -> None:
    """Choosing not to fetch anything is not an error."""
    client = SearchClient()

    with patch.object(client, "search", return_value={"hitCount": 5, "resultList": {}}):
        for answer in ("q", "quit", "0", ""):
            with patch("builtins.input", return_value=answer):
                assert client.interactive_search("test") == []

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
def test_interactive_search_network_error_is_raised() -> None:
    """A failed request reaches the caller instead of looking like a query without matches."""
    client = SearchClient()
    failure = SearchError(ErrorCodes.NET001, {"error": "Network error"})

    with (
        patch.object(client, "search", side_effect=failure),
        patch("builtins.input") as mock_input,
        pytest.raises(SearchError) as caught,
    ):
        client.interactive_search("test")

    assert caught.value is failure
    mock_input.assert_not_called()
    client.close()


@pytest.mark.unit
def test_interactive_search_error_while_fetching_is_raised() -> None:
    """The hit count worked, the download did not: the records already asked for are not
    silently dropped."""
    client = SearchClient()
    failure = SearchError(ErrorCodes.NET002, {"error": "timed out"})

    with (
        patch.object(client, "search", return_value={"hitCount": 50, "resultList": {}}),
        patch.object(client, "search_all", side_effect=failure),
        patch("builtins.input", return_value="10"),
        pytest.raises(SearchError) as caught,
    ):
        client.interactive_search("test")

    assert caught.value is failure
    client.close()


@pytest.mark.unit
def test_interactive_search_zero_hits_is_an_empty_list_without_a_prompt() -> None:
    client = SearchClient()

    with (
        patch.object(client, "search", return_value={"hitCount": 0, "resultList": {}}),
        patch("builtins.input") as mock_input,
    ):
        assert client.interactive_search("nothing like this") == []

    mock_input.assert_not_called()
    client.close()


@pytest.mark.unit
def test_interactive_search_asks_again_after_a_bad_number() -> None:
    client = SearchClient()
    records = [{"id": 1}, {"id": 2}]

    with (
        patch.object(client, "search", return_value={"hitCount": 5, "resultList": {}}),
        patch.object(client, "search_all", return_value=records) as search_all,
        patch("builtins.input", side_effect=["many", "9", "2"]),
    ):
        assert client.interactive_search("test") == records

    assert search_all.call_args.kwargs["max_results"] == 2
    client.close()


@pytest.mark.unit
def test_interactive_search_closed_stdin_raises_instead_of_looping() -> None:
    client = SearchClient()

    with (
        patch.object(client, "search", return_value={"hitCount": 5, "resultList": {}}),
        patch("builtins.input", side_effect=EOFError),
        pytest.raises(EOFError),
    ):
        client.interactive_search("test")

    client.close()
