"""Unit tests for base enrichment client."""

import pytest
from unittest.mock import Mock, patch

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient


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
