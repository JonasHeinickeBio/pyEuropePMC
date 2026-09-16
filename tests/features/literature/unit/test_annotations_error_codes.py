"""AnnotationsClient keeps the error code of a failed request.

The session is patched with real ``requests.Response`` objects, so the real
``BaseAPIClient._get`` produces the ``APIClientError``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.literature.annotations import AnnotationsClient

pytestmark = pytest.mark.unit


def _response(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Error"
    response.url = "https://www.ebi.ac.uk/europepmc/annotations_api/"
    response._content = b"{}"
    response._content_consumed = True
    return response


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture
def client():
    instance = AnnotationsClient(rate_limit_delay=0)
    yield instance
    instance.close()


CALLS = [
    ("by_article_ids", lambda c: c.get_annotations_by_article_ids(["PMC3359999"])),
    ("by_entity", lambda c: c.get_annotations_by_entity("malaria", "Disease")),
    ("by_provider", lambda c: c.get_annotations_by_provider("Europe PMC")),
]


@pytest.mark.parametrize(
    ("status_code", "error_code"), [(404, ErrorCodes.HTTP404), (429, ErrorCodes.RATE429)]
)
@pytest.mark.parametrize(("name", "call"), CALLS, ids=[name for name, _ in CALLS])
def test_http_error_keeps_its_code(client, name, call, status_code, error_code):
    with (
        patch.object(client.session, "get", return_value=_response(status_code)),
        pytest.raises(APIClientError) as exc_info,
    ):
        call(client)

    assert exc_info.value.error_code == error_code
    assert exc_info.value.context["status_code"] == status_code


def test_unparseable_response_is_still_wrapped(client):
    """Failures other than the request itself are still reported as NET001."""
    bad = _response(200)
    bad._content = b"not json"
    with (
        patch.object(client.session, "get", return_value=bad),
        pytest.raises(APIClientError) as exc_info,
    ):
        client.get_annotations_by_article_ids(["PMC3359999"])

    assert exc_info.value.error_code == ErrorCodes.NET001
