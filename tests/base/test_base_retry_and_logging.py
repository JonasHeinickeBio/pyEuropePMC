"""Unit tests for the retry, rate-limit and logging behaviour of BaseAPIClient.

Every request here is mocked; nothing touches the network (pytest-socket blocks
it anyway).
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.core.base import RETRYABLE_STATUS_CODES, BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    instance = BaseAPIClient(rate_limit_delay=0)
    yield instance
    instance.close()


@pytest.fixture(autouse=True)
def no_sleep():
    """Keep the backoff waits and the rate-limit delay out of the clock."""
    with patch("time.sleep") as mock_sleep:
        yield mock_sleep


def _response(status_code: int) -> MagicMock:
    """A response whose raise_for_status() raises HTTPError for 4xx/5xx."""
    response = MagicMock()
    response.status_code = status_code
    if status_code >= 400:
        error = requests.HTTPError(f"{status_code}")
        error.response = response
        response.raise_for_status.side_effect = error
    else:
        response.raise_for_status.return_value = None
    return response


class TestGetRetries:
    def test_connection_error_is_retried_before_giving_up(self, client):
        with (
            patch.object(
                client.session, "get", side_effect=requests.ConnectionError("refused")
            ) as mock_get,
            pytest.raises(APIClientError) as exc_info,
        ):
            client._get("endpoint")

        assert mock_get.call_count == 5
        assert exc_info.value.error_code == ErrorCodes.NET001

    def test_timeout_is_retried(self, client):
        with (
            patch.object(client.session, "get", side_effect=requests.Timeout("slow")) as mock_get,
            pytest.raises(APIClientError),
        ):
            client._get("endpoint")

        assert mock_get.call_count == 5

    def test_transient_failure_then_success_returns_the_response(self, client):
        ok = _response(200)
        with patch.object(
            client.session,
            "get",
            side_effect=[requests.ConnectionError("refused"), requests.Timeout("slow"), ok],
        ) as mock_get:
            assert client._get("endpoint") is ok

        assert mock_get.call_count == 3

    @pytest.mark.parametrize("status_code", sorted(RETRYABLE_STATUS_CODES))
    def test_retryable_http_status_is_retried(self, client, status_code):
        with (
            patch.object(client.session, "get", return_value=_response(status_code)) as mock_get,
            pytest.raises(APIClientError),
        ):
            client._get("endpoint")

        assert mock_get.call_count == 5

    @pytest.mark.parametrize(
        ("status_code", "error_code"),
        [(404, ErrorCodes.HTTP404), (403, ErrorCodes.HTTP403), (418, ErrorCodes.NET001)],
    )
    def test_permanent_http_status_is_not_retried(self, client, status_code, error_code):
        with (
            patch.object(client.session, "get", return_value=_response(status_code)) as mock_get,
            pytest.raises(APIClientError) as exc_info,
        ):
            client._get("endpoint")

        assert mock_get.call_count == 1
        assert exc_info.value.error_code == error_code

    def test_success_is_not_retried(self, client):
        with patch.object(client.session, "get", return_value=_response(200)) as mock_get:
            client._get("endpoint")

        assert mock_get.call_count == 1

    def test_rate_limit_delay_is_applied_once_per_call(self, no_sleep):
        client = BaseAPIClient(rate_limit_delay=2.5)
        try:
            with patch.object(client.session, "get", return_value=_response(200)):
                client._get("endpoint")
        finally:
            client.close()

        assert no_sleep.call_args_list[-1].args == (2.5,)


class TestPostRetries:
    def test_connection_error_is_retried_before_giving_up(self, client):
        with (
            patch.object(
                client.session, "post", side_effect=requests.ConnectionError("refused")
            ) as mock_post,
            pytest.raises(APIClientError),
        ):
            client._post("endpoint", data={})

        assert mock_post.call_count == 5

    def test_permanent_http_status_is_not_retried(self, client):
        with (
            patch.object(client.session, "post", return_value=_response(404)) as mock_post,
            pytest.raises(APIClientError) as exc_info,
        ):
            client._post("endpoint", data={})

        assert mock_post.call_count == 1
        assert exc_info.value.error_code == ErrorCodes.HTTP404

    def test_retryable_http_status_is_retried(self, client):
        with (
            patch.object(client.session, "post", return_value=_response(503)) as mock_post,
            pytest.raises(APIClientError),
        ):
            client._post("endpoint", data={})

        assert mock_post.call_count == 5


class TestLibraryLogging:
    def test_importing_the_package_does_not_configure_the_root_logger(self):
        """A library must leave the application's logging setup alone."""
        root = logging.getLogger()
        before = list(root.handlers)

        BaseAPIClient(rate_limit_delay=0).close()

        assert root.handlers == before

    def test_package_logger_has_a_null_handler(self):
        """The NullHandler stops the 'no handler could be found' warning."""
        handlers = logging.getLogger("pyeuropepmc").handlers
        assert any(isinstance(handler, logging.NullHandler) for handler in handlers)
