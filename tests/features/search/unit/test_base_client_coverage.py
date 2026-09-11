"""Additional coverage for BaseLiteratureClient: cache-hit path, custom
headers, the HTTPError-except 429/404 branches, _handle_rate_limit's
Retry-After parse failure, the abstract-method bodies, and the
search_and_normalize / get_paper_and_normalize helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig
from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

from .test_base_client import _ConcreteClient, _response


class TestCacheAndHeaders:
    def test_cache_hit_skips_network(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client._cache = CacheBackend(CacheConfig(enabled=True))
        client.session.get = MagicMock(return_value=_response(200, {"live": True}))

        first = client._make_request("endpoint", use_cache=True)
        assert first == {"live": True}
        assert client.session.get.call_count == 1

        second = client._make_request("endpoint", use_cache=True)
        assert second == {"live": True}
        assert client.session.get.call_count == 1  # served from cache

    def test_custom_headers_merged(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, {"ok": True}))
        client._make_request("endpoint", headers={"X-Custom": "1"}, use_cache=False)
        _, kwargs = client.session.get.call_args
        assert kwargs["headers"]["X-Custom"] == "1"

    def test_response_cached_after_success(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client._cache = CacheBackend(CacheConfig(enabled=True))
        client.session.get = MagicMock(return_value=_response(200, {"a": 1}))
        client._make_request("ep", use_cache=True)
        cache_key = f"{client.base_url}/ep:None:json"
        assert client._cache.get(cache_key) == {"a": 1}


class TestHttpErrorExceptBranches:
    def _http_error(self, status_code, headers=None):
        resp = _response(status_code, headers=headers)
        err = requests.HTTPError(response=resp)
        return err

    @patch("time.sleep")
    def test_429_with_retry_after_in_except_retries(self, mock_sleep):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(
            side_effect=[
                self._http_error(429, headers={"Retry-After": "0"}),
                _response(200, {"ok": True}),
            ]
        )
        assert client._make_request("endpoint", use_cache=False) == {"ok": True}
        assert client.session.get.call_count == 2

    @patch("time.sleep")
    def test_429_with_non_integer_retry_after_falls_through(self, mock_sleep):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(
            side_effect=[self._http_error(429, headers={"Retry-After": "not-a-number"})] * 3
        )
        from pyeuropepmc.core.exceptions import APIClientError

        with pytest.raises(APIClientError):
            client._make_request("endpoint", use_cache=False)

    def test_404_raised_as_http_error_returns_none(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(side_effect=self._http_error(404))
        assert client._make_request("endpoint", use_cache=False) is None


class TestHandleRateLimitRetryAfterParseFailure:
    def test_non_numeric_retry_after_falls_back_to_backoff(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=1.0)
        resp = _response(429, headers={"Retry-After": "not-a-number"})
        wait = client._handle_rate_limit(resp, attempt=0, url="https://x")
        assert wait > 0


class TestAbstractMethodBodies:
    def test_search_not_implemented_via_base_class(self):
        client = _ConcreteClient(base_url="https://x")
        with pytest.raises(NotImplementedError):
            BaseLiteratureClient.search(client, "query")

    def test_get_paper_not_implemented_via_base_class(self):
        client = _ConcreteClient(base_url="https://x")
        with pytest.raises(NotImplementedError):
            BaseLiteratureClient.get_paper(client, "id")

    def test_normalize_result_not_implemented(self):
        client = _ConcreteClient(base_url="https://x")
        with pytest.raises(NotImplementedError):
            client._normalize_result({"title": "x"})


class TestSearchAndNormalize:
    def test_search_and_normalize_with_raw_dicts(self):
        client = _ConcreteClient(base_url="https://x")
        client.search = MagicMock(return_value=[{"title": "raw"}])
        client._normalize_result = MagicMock(
            return_value=LiteratureResult(title="raw", source="pubmed", source_id="1")
        )
        results = client.search_and_normalize(query="q")
        assert len(results) == 1
        assert results[0].title == "raw"

    def test_search_and_normalize_passthrough_literature_results(self):
        client = _ConcreteClient(base_url="https://x")
        already = LiteratureResult(title="already normalized", source="pubmed", source_id="1")
        client.search = MagicMock(return_value=[already])
        client._normalize_result = MagicMock()
        results = client.search_and_normalize(query="q")
        assert results == [already]
        client._normalize_result.assert_not_called()

    def test_get_paper_and_normalize_none(self):
        client = _ConcreteClient(base_url="https://x")
        client.get_paper = MagicMock(return_value=None)
        assert client.get_paper_and_normalize(identifier="1") is None

    def test_get_paper_and_normalize_passthrough(self):
        client = _ConcreteClient(base_url="https://x")
        already = LiteratureResult(title="T", source="pubmed", source_id="1")
        client.get_paper = MagicMock(return_value=already)
        assert client.get_paper_and_normalize(identifier="1") is already

    def test_get_paper_and_normalize_raw_dict(self):
        client = _ConcreteClient(base_url="https://x")
        client.get_paper = MagicMock(return_value={"title": "raw"})
        normalized = LiteratureResult(title="raw", source="pubmed", source_id="1")
        client._normalize_result = MagicMock(return_value=normalized)
        assert client.get_paper_and_normalize(identifier="1") is normalized
