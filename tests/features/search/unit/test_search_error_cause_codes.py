"""SearchClient still raises SearchError NET001; only the cause's code is specific."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, SearchError
from pyeuropepmc.features.literature.search import SearchClient

pytestmark = pytest.mark.unit


def _response(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Error"
    response.url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    response._content = b"{}"
    response._content_consumed = True
    return response


@pytest.fixture
def client():
    with patch("time.sleep"):
        instance = SearchClient(rate_limit_delay=0)
        yield instance
        instance.close()


@pytest.mark.parametrize(
    ("status_code", "cause_code"), [(404, ErrorCodes.HTTP404), (503, ErrorCodes.HTTP503)]
)
def test_search_get_failure(client, status_code, cause_code):
    with (
        patch.object(client.session, "get", return_value=_response(status_code)),
        pytest.raises(SearchError) as exc_info,
    ):
        client.search("malaria")

    assert exc_info.value.error_code == ErrorCodes.NET001
    assert isinstance(exc_info.value.__cause__, APIClientError)
    assert exc_info.value.__cause__.error_code == cause_code


@pytest.mark.parametrize(
    ("status_code", "cause_code"), [(404, ErrorCodes.HTTP404), (500, ErrorCodes.HTTP500)]
)
def test_search_post_failure(client, status_code, cause_code):
    with (
        patch.object(client.session, "post", return_value=_response(status_code)),
        pytest.raises(SearchError) as exc_info,
    ):
        client.search_post("malaria")

    assert exc_info.value.error_code == ErrorCodes.NET001
    assert exc_info.value.__cause__.error_code == cause_code
    assert exc_info.value.__cause__.context["status_code"] == status_code
