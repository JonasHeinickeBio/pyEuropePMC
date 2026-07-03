"""Unit tests for base enrichment client."""

from unittest.mock import Mock, patch

import pytest
import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient
from pyeuropepmc.core.exceptions import APIClientError


class TestBaseEnrichmentClient:
    """Tests for BaseEnrichmentClient."""

    def test_initialization(self):
        """Test basic initialization."""
        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=1.0,
            timeout=15,
        )
        assert client.base_url == "https://api.example.com"
        assert client.rate_limit_delay == 1.0
        assert client.timeout == 15
        assert client.session is not None

    def test_initialization_with_cache(self):
        """Test initialization with caching enabled."""
        cache_config = CacheConfig(enabled=True)
        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            cache_config=cache_config,
        )
        assert client._cache is not None
        assert client._cache.config.enabled is True

    def test_initialization_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base_url."""
        client = BaseEnrichmentClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    def test_custom_user_agent(self):
        """Test custom user agent."""
        custom_ua = "MyApp/1.0"
        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            user_agent=custom_ua,
        )
        assert client.session.headers["User-Agent"] == custom_ua

    def test_context_manager(self):
        """Test context manager protocol."""
        with BaseEnrichmentClient(base_url="https://api.example.com") as client:
            assert client.session is not None
        # After exit, session should be closed (but we can't easily test this)

    @patch("requests.Session.get")
    def test_make_request_success(self, mock_get):
        """Test successful API request."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.1,  # Short delay for tests
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_make_request_404_returns_none(self, mock_get):
        """Test that 404 returns None instead of raising."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.1,
        )

        result = client._make_request("endpoint")
        assert result is None

    @patch("requests.Session.get")
    def test_make_request_with_params(self, mock_get):
        """Test request with parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.1,
        )

        params = {"key": "value"}
        result = client._make_request("endpoint", params=params)
        assert result == {"data": "test"}

        # Check that params were passed correctly
        call_args = mock_get.call_args
        assert call_args[1]["params"] == params

    @patch("requests.Session.get")
    def test_make_request_with_headers(self, mock_get):
        """Test request with custom headers."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.1,
        )

        headers = {"X-Custom": "header"}
        client._make_request("endpoint", headers=headers)

        # Check that headers were included
        call_args = mock_get.call_args
        assert "X-Custom" in call_args[1]["headers"]

    @patch("requests.Session.get")
    def test_make_request_invalid_json(self, mock_get):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.1,
        )

        result = client._make_request("endpoint")
        assert result is None

    def test_enrich_not_implemented(self):
        """Test that enrich raises NotImplementedError."""
        client = BaseEnrichmentClient(base_url="https://api.example.com")
        with pytest.raises(NotImplementedError):
            client.enrich()

    def test_close(self):
        """Test close method."""
        client = BaseEnrichmentClient(base_url="https://api.example.com")
        # Should not raise
        client.close()

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_403_without_api_key(self, mock_get, mock_sleep):
        """Test 403 without API key headers logs warning and raises APIClientError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "403 Forbidden", response=mock_response
        )
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        with pytest.raises(APIClientError):
            client._make_request("endpoint")

        assert mock_get.call_count == 1

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_403_with_auth_retries_without_header(self, mock_get, mock_sleep):
        """Test 403 with Authorization header removes it and retries."""
        mock_response_403 = Mock()
        mock_response_403.status_code = 403

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"key": "value"}

        mock_get.side_effect = [mock_response_403, mock_response_200]

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )
        client.session.headers["Authorization"] = "Bearer token123"

        result = client._make_request("endpoint")

        assert result == {"key": "value"}
        assert mock_get.call_count == 2
        assert "Authorization" not in client.session.headers

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_429_with_retry_after_int(self, mock_get, mock_sleep):
        """Test 429 with integer Retry-After header waits and retries."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "2"}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"key": "value"}

        mock_get.side_effect = [mock_response_429, mock_response_200]

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        assert mock_get.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_429_with_retry_after_float(self, mock_get, mock_sleep):
        """Test 429 with float Retry-After header rounds and waits."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "2.5"}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"key": "value"}

        mock_get.side_effect = [mock_response_429, mock_response_200]

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        assert mock_get.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_429_without_retry_after(self, mock_get, mock_sleep):
        """Test 429 without Retry-After uses exponential backoff."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"key": "value"}

        mock_get.side_effect = [mock_response_429, mock_response_200]

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        assert mock_get.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_429_with_api_key_missing(self, mock_get, mock_sleep):
        """Test 429 with api_key_missing=True uses 3x conservative delay."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"key": "value"}

        mock_get.side_effect = [mock_response_429, mock_response_200]

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
            api_key_missing=True,
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        assert mock_get.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_connection_error(self, mock_get, mock_sleep):
        """Test ConnectionError raises APIClientError."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        with pytest.raises(APIClientError, match="Failed to connect to API"):
            client._make_request("endpoint")

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_timeout(self, mock_get, mock_sleep):
        """Test Timeout raises APIClientError."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        with pytest.raises(APIClientError, match="timed out"):
            client._make_request("endpoint")

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_http_error_raises_api_client_error(self, mock_get, mock_sleep):
        """Test HTTPError with status other than 404/429 raises APIClientError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error", response=mock_response
        )
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        with pytest.raises(APIClientError, match="HTTP 500 error"):
            client._make_request("endpoint")

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_make_request_max_retries_exceeded(self, mock_get, mock_sleep):
        """Test max retries exceeded raises APIClientError."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            rate_limit_delay=0.01,
        )

        with pytest.raises(APIClientError, match="Failed after"):
            client._make_request("endpoint")

        assert mock_get.call_count == 3

    @patch("pyeuropepmc.enrichment.base.CacheBackend")
    @patch("requests.Session.get")
    def test_make_request_cache_hit(self, mock_get, mock_cache):
        """Test cache hit returns cached value without making request."""
        mock_cache_instance = Mock()
        mock_cache_instance.config.enabled = True
        mock_cache_instance.get.return_value = {"cached": "data"}
        mock_cache.return_value = mock_cache_instance

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            cache_config=CacheConfig(enabled=True),
            rate_limit_delay=0.01,
        )

        result = client._make_request("endpoint")
        assert result == {"cached": "data"}
        mock_get.assert_not_called()

    @patch("pyeuropepmc.enrichment.base.CacheBackend")
    @patch("requests.Session.get")
    def test_make_request_cache_set_after_success(self, mock_get, mock_cache):
        """Test successful response is cached."""
        mock_cache_instance = Mock()
        mock_cache_instance.config.enabled = True
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            cache_config=CacheConfig(enabled=True),
            rate_limit_delay=0.01,
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        mock_cache_instance.set.assert_called_once()

    @patch("requests.Session.get")
    def test_make_request_caching_disabled(self, mock_get):
        """Test caching disabled path skips cache."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_get.return_value = mock_response

        client = BaseEnrichmentClient(
            base_url="https://api.example.com",
            cache_config=CacheConfig(enabled=False),
            rate_limit_delay=0.01,
        )

        result = client._make_request("endpoint")
        assert result == {"key": "value"}
        mock_get.assert_called_once()

    def test_exit_closes_session(self):
        """Test __exit__ calls close method."""
        client = BaseEnrichmentClient(base_url="https://api.example.com")
        with patch.object(client, "close") as mock_close:
            client.__exit__(None, None, None)
            mock_close.assert_called_once()
