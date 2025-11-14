import logging
from unittest.mock import MagicMock

import pytest

from pyeuropepmc.clients.search import SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
def test_extract_search_params_handles_snake_and_camel_case() -> None:
    # Arrange: create a mock instance and patch in the method
    mock_instance = MagicMock()

    # Example mixed kwargs
    kwargs = {
        "resultType": "core",
        "synonym": True,
        "page_size": 50,
        "format": "json",
        "cursorMark": "abc123",
        "sort": "CITED desc",
        "extra_param": "foo",
        "pageSize": 999,  # Should be ignored in favor of "page_size"
    }

    # Act: call the method
    params = SearchClient._extract_search_params(mock_instance, "cancer", kwargs.copy())

    # Assert: check normalization and extraction
    assert params["query"] == "cancer"
    assert params["resultType"] == "core"
    assert params["synonym"] == "TRUE"
    assert params["pageSize"] == 50  # "page_size" takes precedence over "pageSize"
    assert params["format"] == "json"
    assert params["cursorMark"] == "abc123"
    assert params["sort"] == "CITED desc"
    assert params["extra_param"] == "foo"
    # Original kwargs should be unchanged (if you want to check that)
    assert "page_size" in kwargs


@pytest.mark.unit
def test_extract_search_params_defaults() -> None:
    mock_instance = MagicMock()

    # No optional params provided
    kwargs = {}

    # Act
    params = SearchClient._extract_search_params(mock_instance, "malaria", kwargs.copy())

    # Assert: check defaults
    assert params["query"] == "malaria"
    assert params["resultType"] == "lite"
    assert params["synonym"] == "FALSE"
    assert params["pageSize"] == 25
    assert params["format"] == "json"
    assert params["cursorMark"] == "*"
    assert params["sort"] == ""
