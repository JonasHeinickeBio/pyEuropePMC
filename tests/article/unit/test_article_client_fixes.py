"""ArticleClient: closing the session, non-JSON formats and specific error codes.

HTTP is mocked at ``requests.Session.get``; the real ``BaseAPIClient._get`` runs.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.literature.article import ArticleClient

pytestmark = pytest.mark.unit

XML = '<?xml version="1.0" encoding="UTF-8"?><responseWrapper><hitCount>1</hitCount></responseWrapper>'


def _response(status_code: int = 200, text: str = "") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "OK" if status_code < 400 else "Error"
    response.url = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    response._content = text.encode("utf-8")
    response._content_consumed = True
    return response


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture
def client():
    instance = ArticleClient(rate_limit_delay=0)
    yield instance
    instance.close()


# name, call with the given format
FORMAT_METHODS = [
    ("get_article_details", lambda c, f: c.get_article_details("MED", "25883711", format=f)),
    ("get_citations", lambda c, f: c.get_citations("MED", "25883711", format=f)),
    ("get_references", lambda c, f: c.get_references("MED", "25883711", format=f)),
    ("get_database_links", lambda c, f: c.get_database_links("MED", "25883711", format=f)),
    ("get_lab_links", lambda c, f: c.get_lab_links("MED", "25883711", format=f)),
    ("get_data_links", lambda c, f: c.get_data_links("MED", "25883711", format=f)),
]


class TestClose:
    def test_close_closes_the_http_session(self):
        client = ArticleClient(rate_limit_delay=0)
        session = client.session
        with patch.object(session, "close") as session_close:
            client.close()

        session_close.assert_called_once()
        assert client.is_closed

    def test_context_manager_closes_the_session(self):
        with ArticleClient(rate_limit_delay=0) as client:
            assert not client.is_closed
        assert client.is_closed

    def test_requests_after_close_are_refused(self):
        client = ArticleClient(rate_limit_delay=0)
        client.close()
        with pytest.raises(APIClientError) as exc_info:
            client.get_article_details("MED", "25883711")
        assert exc_info.value.error_code == ErrorCodes.FULL007


class TestNonJsonFormats:
    @pytest.mark.parametrize(("name", "call"), FORMAT_METHODS, ids=[n for n, _ in FORMAT_METHODS])
    def test_xml_body_is_returned_as_text(self, client, name, call):
        with patch.object(requests.Session, "get", return_value=_response(200, XML)):
            result = call(client, "xml")

        assert result == {"xml_response": XML}

    def test_dublin_core_article_details(self, client):
        with patch.object(requests.Session, "get", return_value=_response(200, XML)):
            result = client.get_article_details("MED", "25883711", format="dc")

        assert result == {"dc_response": XML}

    def test_xml_details_are_cached_under_their_format(self):
        client = ArticleClient(rate_limit_delay=0, cache_config=CacheConfig(enabled=True))
        try:
            with patch.object(requests.Session, "get", return_value=_response(200, XML)) as get:
                first = client.get_article_details("MED", "25883711", format="xml")
                second = client.get_article_details("MED", "25883711", format="xml")
        finally:
            client.close()

        assert first == second == {"xml_response": XML}
        assert get.call_count == 1

    @pytest.mark.parametrize(("name", "call"), FORMAT_METHODS, ids=[n for n, _ in FORMAT_METHODS])
    def test_json_is_still_parsed(self, client, name, call):
        with patch.object(requests.Session, "get", return_value=_response(200, '{"hitCount": 1}')):
            assert call(client, "json") == {"hitCount": 1}


class TestSpecificErrorCodes:
    @pytest.mark.parametrize(("name", "call"), FORMAT_METHODS, ids=[n for n, _ in FORMAT_METHODS])
    def test_http_404_is_reported_as_http404(self, client, name, call):
        with (
            patch.object(requests.Session, "get", return_value=_response(404)),
            pytest.raises(APIClientError) as exc_info,
        ):
            call(client, "json")

        assert exc_info.value.error_code == ErrorCodes.HTTP404

    def test_http_429_is_reported_as_rate429(self, client):
        with (
            patch.object(requests.Session, "get", return_value=_response(429)),
            pytest.raises(APIClientError) as exc_info,
        ):
            client.get_citations("MED", "25883711")

        assert exc_info.value.error_code == ErrorCodes.RATE429

    def test_supplementary_files_404_is_reported_as_http404(self, client):
        with (
            patch.object(requests.Session, "get", return_value=_response(404)),
            pytest.raises(APIClientError) as exc_info,
        ):
            client.get_supplementary_files("PMC3258128")

        assert exc_info.value.error_code == ErrorCodes.HTTP404

    def test_connection_failure_is_still_net001(self, client):
        with (
            patch.object(requests.Session, "get", side_effect=requests.ConnectionError("down")),
            pytest.raises(APIClientError) as exc_info,
        ):
            client.get_article_details("MED", "25883711")

        assert exc_info.value.error_code == ErrorCodes.NET001
