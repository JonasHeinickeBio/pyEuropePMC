"""SearchClient.search_all() and search_ids_only() raise when a request fails.

HTTP is mocked at ``requests.Session.get``; the real request path runs.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.core.exceptions import SearchError
from pyeuropepmc.features.literature.search import SearchClient

pytestmark = pytest.mark.unit


def _response(status_code: int = 200, payload: dict | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "OK" if status_code < 400 else "Error"
    response.url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    response._content = json.dumps(payload or {}).encode("utf-8")
    response._content_consumed = True
    return response


def _page(first_id: int, count: int, cursor: str) -> dict:
    return {
        "hitCount": 250,
        "nextCursorMark": cursor,
        "resultList": {"result": [{"id": str(first_id + i)} for i in range(count)]},
    }


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture
def client():
    instance = SearchClient(rate_limit_delay=0)
    yield instance
    instance.close()


class TestSearchAll:
    def test_a_failed_later_page_raises_instead_of_returning_part(self, client):
        responses = iter([_response(200, _page(0, 100, "c2"))])

        def get(self, url, **kwargs):  # noqa: ARG001
            return next(responses, _response(404))

        with patch.object(requests.Session, "get", get), pytest.raises(SearchError):
            client.search_all("malaria", page_size=100)

    def test_a_failed_first_page_raises(self, client):
        with (
            patch.object(
                requests.Session, "get", side_effect=requests.ConnectionError("unreachable")
            ),
            pytest.raises(SearchError),
        ):
            client.search_all("malaria")

    def test_complete_results_are_unchanged(self, client):
        responses = iter(
            [_response(200, _page(0, 100, "c2")), _response(200, _page(100, 50, "c3"))]
        )

        def get(self, url, **kwargs):  # noqa: ARG001
            return next(responses)

        with patch.object(requests.Session, "get", get):
            results = client.search_all("malaria", page_size=100)

        assert len(results) == 150


class TestSearchIdsOnly:
    def test_a_failed_request_raises(self, client):
        with (
            patch.object(requests.Session, "get", return_value=_response(404)),
            pytest.raises(SearchError),
        ):
            client.search_ids_only("malaria")

    def test_ids_are_returned(self, client):
        payload = {"hitCount": 2, "resultList": {"result": [{"id": "1"}, {"id": "2"}]}}
        with patch.object(requests.Session, "get", return_value=_response(200, payload)):
            assert client.search_ids_only("malaria") == ["1", "2"]

    def test_no_matches_is_still_an_empty_list(self, client):
        payload = {"hitCount": 0, "resultList": {"result": []}}
        with patch.object(requests.Session, "get", return_value=_response(200, payload)):
            assert client.search_ids_only("malaria") == []
