import logging
from unittest.mock import patch

import pytest

from pyeuropepmc.search import EuropePMCError, SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
def test_get_hit_count_success() -> None:
    """Test get_hit_count returns the correct hit count."""
    client = SearchClient()

    # Mock response with hit count
    mock_response = {"resultList": {"resultType": "lite"}, "hitCount": 42}

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        hit_count = client.get_hit_count("test query")
        assert hit_count == 42
        mock_search.assert_called_once_with("test query", page_size=1)

    client.close()


@pytest.mark.unit
def test_get_hit_count_missing_key() -> None:
    """Test get_hit_count handles missing hitCount key."""
    client = SearchClient()

    # Mock response without hit count
    mock_response = {"resultList": {"resultType": "lite"}}

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        hit_count = client.get_hit_count("test query")
        assert hit_count == 0

    client.close()


@pytest.mark.unit
def test_get_hit_count_exception() -> None:
    """Test get_hit_count handles search exceptions."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.side_effect = Exception("Search failed")

        with pytest.raises(EuropePMCError, match="Error getting hit count"):
            client.get_hit_count("test query")

    client.close()


@pytest.mark.unit
def test_search_ids_only() -> None:
    """Test search_ids_only returns ID list."""
    client = SearchClient()

    mock_response = {
        "resultList": {"resultType": "idlist", "result": [{"id": "12345"}, {"id": "67890"}]}
    }

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        ids = client.search_ids_only("test query", pageSize=10)
        assert ids == ["12345", "67890"]
        mock_search.assert_called_once_with(
            "test query", format="json", resultType="idlist", pageSize=10
        )

    client.close()


@pytest.mark.unit
def test_search_ids_only_empty_results() -> None:
    """Test search_ids_only handles empty results."""
    client = SearchClient()

    mock_response = {"resultList": {"resultType": "idlist", "result": []}}

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = mock_response

        ids = client.search_ids_only("test query")
        assert ids == []

    client.close()


@pytest.mark.unit
def test_search_ids_only_exception() -> None:
    """Test search_ids_only handles exceptions gracefully."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.side_effect = Exception("Search failed")

        ids = client.search_ids_only("test query")
        assert ids == []

    client.close()


@pytest.mark.unit
def test_validate_query_valid() -> None:
    """Test validate_query with valid queries."""
    # Test various valid query formats
    assert SearchClient.validate_query("cancer AND treatment")
    assert SearchClient.validate_query('AUTH:"Smith J"')
    assert SearchClient.validate_query("(cancer OR tumor) AND treatment")
    assert SearchClient.validate_query("simple query")
    assert SearchClient.validate_query("PMID:12345678")


@pytest.mark.unit
def test_validate_query_empty() -> None:
    """Test validate_query with empty/invalid queries."""
    # Test empty and whitespace queries
    assert not SearchClient.validate_query("")
    assert not SearchClient.validate_query("   ")
    assert not SearchClient.validate_query(None)  # type: ignore


@pytest.mark.unit
def test_validate_query_too_short() -> None:
    """Test validate_query with too short queries."""
    assert not SearchClient.validate_query("a")
    assert SearchClient.validate_query("ab")  # 2 chars should be valid


@pytest.mark.unit
def test_validate_query_unmatched_quotes() -> None:
    """Test validate_query with unmatched quotes."""
    assert not SearchClient.validate_query('AUTH:"Smith J')  # Missing closing quote
    assert not SearchClient.validate_query('AUTH:Smith J"')  # Missing opening quote
    assert SearchClient.validate_query('AUTH:"Smith J"')  # Properly matched


@pytest.mark.unit
def test_validate_query_too_many_special_chars() -> None:
    """Test validate_query with excessive special characters."""
    # This should fail due to too many special characters
    excessive_special = "!@#$%^&*()!@#$%^&*()!@#$%^&*()"
    assert not SearchClient.validate_query(excessive_special)

    # This should pass - reasonable amount of special characters
    reasonable = "cancer AND (treatment OR therapy)"
    assert SearchClient.validate_query(reasonable)
