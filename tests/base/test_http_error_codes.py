"""HTTP statuses are reported with their own error code, for GET and POST.

Requests go through the real ``BaseAPIClient._get``/``_post`` with a patched
session returning real ``requests.Response`` objects. A Mock response would hide
the POST bug this guards against: a real Response for a 4xx/5xx is falsy.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.error_codes import (
    HTTP_STATUS_ERROR_CODES,
    ErrorCodes,
    error_code_for_status,
)
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.search.base import BaseLiteratureClient

pytestmark = pytest.mark.unit

EXPECTED = [
    (400, ErrorCodes.HTTP400),
    (401, ErrorCodes.AUTH401),
    (403, ErrorCodes.HTTP403),
    (404, ErrorCodes.HTTP404),
    (429, ErrorCodes.RATE429),
    (500, ErrorCodes.HTTP500),
    (502, ErrorCodes.HTTP502),
    (503, ErrorCodes.HTTP503),
    (504, ErrorCodes.HTTP504),
]


def _response(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Error"
    response.url = "https://www.ebi.ac.uk/europepmc/webservices/rest/endpoint"
    response._content = b"{}"
    response._content_consumed = True
    return response


@pytest.fixture(autouse=True)
def no_sleep():
    """Skip the rate-limit delay and any retry backoff."""
    with patch("time.sleep"):
        yield


@pytest.fixture
def client():
    instance = BaseAPIClient(rate_limit_delay=0)
    yield instance
    instance.close()


@pytest.mark.parametrize(("status_code", "error_code"), EXPECTED)
def test_get_reports_the_status_code(client, status_code, error_code):
    with (
        patch.object(client.session, "get", return_value=_response(status_code)),
        pytest.raises(APIClientError) as exc_info,
    ):
        client._get("endpoint")

    assert exc_info.value.error_code == error_code
    assert exc_info.value.context["status_code"] == status_code


@pytest.mark.parametrize(("status_code", "error_code"), EXPECTED)
def test_post_reports_the_status_code(client, status_code, error_code):
    with (
        patch.object(client.session, "post", return_value=_response(status_code)),
        pytest.raises(APIClientError) as exc_info,
    ):
        client._post("endpoint", data={"query": "malaria"})

    assert exc_info.value.error_code == error_code
    assert exc_info.value.context["status_code"] == status_code


@pytest.mark.parametrize("method", ["get", "post"])
def test_status_without_a_code_is_net001_with_the_status(client, method):
    call = client._get if method == "get" else lambda e: client._post(e, data={})
    with (
        patch.object(client.session, method, return_value=_response(418)),
        pytest.raises(APIClientError) as exc_info,
    ):
        call("endpoint")

    assert exc_info.value.error_code == ErrorCodes.NET001
    assert exc_info.value.context["status_code"] == 418


@pytest.mark.parametrize("method", ["get", "post"])
def test_network_failure_is_net001(client, method):
    call = client._get if method == "get" else lambda e: client._post(e, data={})
    with (
        patch.object(client.session, method, side_effect=requests.ConnectionError("refused")),
        pytest.raises(APIClientError) as exc_info,
    ):
        call("endpoint")

    assert exc_info.value.error_code == ErrorCodes.NET001


class TestStatusMapping:
    def test_every_mapped_code_has_a_message(self):
        from pyeuropepmc.core.error_codes import ERROR_MESSAGES

        for error_code in HTTP_STATUS_ERROR_CODES.values():
            assert error_code.value in ERROR_MESSAGES

    @pytest.mark.parametrize("status_code", [418, 599, "unknown", None])
    def test_unmapped_status_has_no_code(self, status_code):
        assert error_code_for_status(status_code) is None

    def test_search_clients_keep_their_api001_fallback(self):
        assert BaseLiteratureClient._map_status_to_error_code(503) == ErrorCodes.HTTP503
        assert BaseLiteratureClient._map_status_to_error_code(401) == ErrorCodes.AUTH401
        assert BaseLiteratureClient._map_status_to_error_code(418) == ErrorCodes.API001
