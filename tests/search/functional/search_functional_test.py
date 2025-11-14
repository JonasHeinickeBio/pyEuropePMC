import logging
from typing import Any, Dict

import pytest

from pyeuropepmc.clients.search import SearchClient

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.mark.functional
@pytest.mark.parametrize(
    "query,page_size",
    [
        ("cancer", 5),
        ("cancer", 100),
        ("diabetes", 3),
        ("asthma", 2),
    ],
)
def test_search_json_functional(query: str, page_size: int) -> None:
    """
    Functional test for SearchClient.search:
    - Tests search method with various queries and page sizes.
    - Asserts correctness of results.
    - Only allows 'json' as format.
    """
    format = "json"
    client = SearchClient()
    logger.debug(f"Starting search for '{query}' with pageSize={page_size} and format='{format}'")
    result: Dict[str, Any] = client.search(query, pageSize=page_size, format=format)  # type: ignore
    logger.debug(f"Search result: {result}")
    assert isinstance(result, dict), "search() should return a dict for JSON format"
    assert "resultList" in result, "Missing 'resultList' in response"
    assert "result" in result["resultList"], "Missing 'result' in 'resultList'"
    assert isinstance(result["resultList"]["result"], list), "'result' should be a list"
    assert len(result["resultList"]["result"]) > 0, f"No results returned for '{query}' query"
    assert len(result["resultList"]["result"]) <= page_size, "Returned more results than page_size"

    # Clean up if your client needs it
    if hasattr(client, "close"):
        logger.debug("Closing client connection")
        client.close()


@pytest.mark.functional
@pytest.mark.parametrize(
    "query,page_size",
    [
        ("cancer", 5),
        ("cancer", 100),
        ("diabetes", 3),
        ("asthma", 2),
    ],
)
def test_search_post_json_functional(query: str, page_size: int) -> None:
    """
    Functional test for SearchClient.search_post:
    - Tests search_post method with various queries and page sizes.
    - Asserts correctness of results.
    - Only allows 'json' as format.
    """
    format = "json"
    client = SearchClient()
    logger.debug(
        f"Starting search_post for '{query}' with pageSize={page_size} and format='{format}'"
    )
    result: Dict[str, Any] = client.search_post(query, pageSize=page_size, format=format)  # type: ignore
    logger.debug(f"Search_post result: {result}")
    assert isinstance(result, dict), "search_post() should return a dict for JSON format"
    assert "resultList" in result, "Missing 'resultList' in response"
    assert "result" in result["resultList"], "Missing 'result' in 'resultList'"
    assert isinstance(result["resultList"]["result"], list), "'result' should be a list"
    assert len(result["resultList"]["result"]) > 0, f"No results returned for '{query}' query"
    assert len(result["resultList"]["result"]) <= page_size, "Returned more results than page_size"

    # Clean up if your client needs it
    if hasattr(client, "close"):
        logger.debug("Closing client connection")
        client.close()
