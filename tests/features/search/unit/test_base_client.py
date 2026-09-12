"""Unit tests for BaseLiteratureClient (retries, caching, error mapping)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.search.base import BaseLiteratureClient


class _ConcreteClient(BaseLiteratureClient):
    """Concrete subclass to test the abstract base class."""

    def search(self, query, limit=25, sort=None, **kwargs):
        return []

    def get_paper(self, identifier, **kwargs):
        return None


def _response(status_code: int, json_data=None, headers=None):
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = b"{}"
    if json_data is not None:
        import json

        resp._content = json.dumps(json_data).encode()
    resp.headers.update(headers or {})
    return resp


class TestBaseClientInit:
    def test_init_defaults(self):
        client = _ConcreteClient(base_url="https://example.com/api/")
        assert client.base_url == "https://example.com/api"  # trailing slash stripped
        assert client.timeout == 15
        assert client.api_key_missing is False
        assert "User-Agent" in client.session.headers

    def test_init_custom_user_agent(self):
        client = _ConcreteClient(base_url="https://x", user_agent="custom-agent/1.0")
        assert client.session.headers["User-Agent"] == "custom-agent/1.0"

    def test_context_manager_closes(self):
        client = _ConcreteClient(base_url="https://x")
        with patch.object(client, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()

    def test_close_closes_session_and_cache(self):
        client = _ConcreteClient(base_url="https://x")
        with (
            patch.object(client.session, "close") as mock_session_close,
            patch.object(client._cache, "close") as mock_cache_close,
        ):
            client.close()
            mock_session_close.assert_called_once()
            mock_cache_close.assert_called_once()


class TestMakeRequest:
    def test_success_returns_json(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, {"ok": True}))
        assert client._make_request("endpoint", use_cache=False) == {"ok": True}

    def test_404_returns_none(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(404))
        assert client._make_request("missing", use_cache=False) is None

    @patch("time.sleep")
    def test_429_retries_then_succeeds(self, mock_sleep):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(
            side_effect=[
                _response(429, headers={"Retry-After": "1"}),
                _response(200, {"ok": True}),
            ]
        )
        assert client._make_request("endpoint", use_cache=False) == {"ok": True}
        assert client.session.get.call_count == 2

    @patch("time.sleep")
    def test_http_error_raises_api_client_error(self, mock_sleep):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(500))
        with pytest.raises(APIClientError) as exc_info:
            client._make_request("endpoint", use_cache=False)
        assert exc_info.value.error_code == ErrorCodes.HTTP500
        assert exc_info.value.status_code == 500

    def test_connection_error_raises_net001(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(side_effect=requests.ConnectionError("refused"))
        with pytest.raises(APIClientError) as exc_info:
            client._make_request("endpoint", use_cache=False)
        assert exc_info.value.error_code == ErrorCodes.NET001

    def test_timeout_raises_net002(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        client.session.get = MagicMock(side_effect=requests.Timeout("slow"))
        with pytest.raises(APIClientError) as exc_info:
            client._make_request("endpoint", use_cache=False)
        assert exc_info.value.error_code == ErrorCodes.NET002

    def test_invalid_json_returns_none(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"<not json>"
        client.session.get = MagicMock(return_value=resp)
        assert client._make_request("endpoint", use_cache=False) is None

    @patch("time.sleep")
    def test_retries_exhausted_raises_retry001(self, mock_sleep):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=0)
        # All three attempts get 429 (with Retry-After so they don't raise);
        # the loop exhausts and RETRY001 is raised.
        client.session.get = MagicMock(
            side_effect=[_response(429, headers={"Retry-After": "1"})] * 3
        )
        with pytest.raises(APIClientError) as exc_info:
            client._make_request("endpoint", use_cache=False)
        assert exc_info.value.error_code == ErrorCodes.RETRY001


class TestCache:
    def test_cache_hit_returns_cached(self):
        client = _ConcreteClient(
            base_url="https://x",
            rate_limit_delay=0,
            cache_config=__import__(
                "pyeuropepmc.cache.cache", fromlist=["CacheConfig"]
            ).CacheConfig(enabled=True, ttl=300),
        )
        # Pre-populate the cache backend with the exact key format used by
        # ``_make_request``: f"{url}:{str(params)}:{response_format}"
        cache_key = "https://x/endpoint:{'a': 1}:json"
        client._cache.set(cache_key, {"cached": True})
        client.session.get = MagicMock(return_value=_response(200, {"fresh": True}))
        assert client._make_request("endpoint", {"a": 1}) == {"cached": True}
        client.session.get.assert_not_called()

    def test_cache_disabled_by_default(self):
        client = _ConcreteClient(base_url="https://x")
        assert client._cache.config.enabled is False


class TestRateLimitHelper:
    def test_handle_rate_limit_retry_after(self):
        client = _ConcreteClient(base_url="https://x")
        resp = _response(429, headers={"Retry-After": "5"})
        assert client._handle_rate_limit(resp, attempt=0, url="https://x/e") == 5.0

    def test_handle_rate_limit_backoff(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=1.0)
        resp = _response(429)
        assert client._handle_rate_limit(resp, attempt=2, url="https://x/e") == 4.0

    def test_handle_rate_limit_conservative_without_api_key(self):
        client = _ConcreteClient(base_url="https://x", rate_limit_delay=1.0, api_key_missing=True)
        resp = _response(429)
        assert client._handle_rate_limit(resp, attempt=1, url="https://x/e") == 6.0


class TestStatusMapping:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (400, ErrorCodes.HTTP400),
            (401, ErrorCodes.AUTH401),
            (403, ErrorCodes.HTTP403),
            (404, ErrorCodes.HTTP404),
            (429, ErrorCodes.RATE429),
            (500, ErrorCodes.HTTP500),
            (503, ErrorCodes.HTTP503),
            (999, ErrorCodes.API001),  # unknown → generic
        ],
    )
    def test_map_status_to_error_code(self, status, expected):
        assert BaseLiteratureClient._map_status_to_error_code(status) == expected
