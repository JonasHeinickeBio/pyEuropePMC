import logging
import time
from typing import Any, Dict, List

import pytest

from pyeuropepmc.search import SearchClient

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
    "query,page_size,max_results",
    [
        ("cancer", 5, 12),
        ("cancer", 100, 1000),
        ("diabetes", 3, 6),
        ("asthma", 2, 4),
    ],
)
def test_search_all_json(query: str, page_size: int, max_results: int) -> None:
    """
    Functional test for EuropePMCClient:
    - Tests fetch_all_pages method.
    - Asserts correctness of results.
    """
    client = SearchClient()

    logger.debug(
        f"Fetching pages for '{query}' with page_size={page_size} and max_results={max_results}"
    )
    start_time = time.time()
    all_results: List[Dict[str, Any]] = client.fetch_all_pages(
        query, page_size=page_size, max_results=max_results
    )
    elapsed_time = time.time() - start_time
    time_per_item = elapsed_time / max(1, len(all_results))
    logger.debug(f"All results: {all_results}")

    logger.info(
        f"Query '{query}': {len(all_results)} items in {elapsed_time:.3f}s "
        f"({time_per_item:.3f}s/item)"
    )

    assert isinstance(all_results, list), "fetch_all_pages() should return a list"
    assert len(all_results) <= max_results, "fetch_all_pages() returned more than max_results"
    assert all(isinstance(r, dict) for r in all_results), "Each result should be a dict"

    # Clean up if your client needs it
    if hasattr(client, "close"):
        logger.debug("Closing client connection")
        client.close()


@pytest.mark.functional
@pytest.mark.parametrize(
    "user_inputs, expected_results_count",
    [
        (["5"], 5),  # Normal input
        (["fail", "3"], 3),  # Invalid then valid
        (["0"], 0),  # User enters 0 to quit
        (["q"], 0),  # User enters 'q' to quit
        (["quit"], 0),  # User enters 'quit' to quit
        (["-1", "11"], 11),  # Out of range then valid
    ],
)
def test_interactive_search(
    monkeypatch: Any,
    user_inputs: List[str],
    expected_results_count: int,
) -> None:
    """
    Functional test for SearchClient.interactive_search:
    - Simulates user interaction returning predefined number of results.
    - Tests various user inputs to control the number of results.
    - Asserts that results are returned and user interaction is handled.
    """
    query: str = "cancer"
    page_size: int = 10
    format: str = "json"

    client = SearchClient()
    inputs = iter(user_inputs)
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    results: List[Dict[str, Any]] = client.interactive_search(
        query, page_size=page_size, format=format
    )

    assert isinstance(results, list), "interactive_search should return a list"
    assert all(isinstance(r, dict) for r in results), "Each result should be a dict"
    logger.debug(f"Interactive search results: {results}")
    assert len(results) == expected_results_count, (
        f"Expected {expected_results_count} results, got {len(results)}"
    )

    if hasattr(client, "close"):
        client.close()
