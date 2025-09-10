from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.base import BaseAPIClient
from pyeuropepmc.exceptions import APIClientError


@pytest.fixture
def client():
    client_instance = BaseAPIClient(rate_limit_delay=1)
    yield client_instance
    client_instance.close()


@pytest.mark.unit
@patch("time.sleep")
def test_get_success(mock_sleep, client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    with patch.object(client.session, "get", return_value=mock_response) as mock_get:
        response = client._get("test_endpoint", params={"q": "test"})
        mock_get.assert_called_once_with(
            client.BASE_URL + "test_endpoint",
            params={"q": "test"},
            timeout=client.DEFAULT_TIMEOUT,
            stream=False,
        )
        assert response == mock_response


@pytest.mark.unit
@patch("time.sleep")
def test_get_failure(mock_sleep, client):
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(client.session, "get", side_effect=APIClientError(ErrorCodes.NET001)):
        with pytest.raises(APIClientError) as exc_info:
            client._get("bad_endpoint")
        assert "Network connection failed" in str(exc_info.value)


@pytest.mark.unit
@patch("time.sleep")
def test_post_success(mock_sleep, client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 201

    with patch.object(client.session, "post", return_value=mock_response) as mock_post:
        response = client._post("test_endpoint", data={"key": "value"}, headers="TestHeader")
        mock_post.assert_called_once_with(
            client.BASE_URL + "test_endpoint",
            data={"key": "value"},
            headers="TestHeader",
            timeout=client.DEFAULT_TIMEOUT,
        )
        assert response == mock_response


@pytest.mark.unit
@patch("time.sleep")
def test_post_failure(mock_sleep, client):
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(client.session, "post", side_effect=APIClientError(ErrorCodes.NET001)):
        with pytest.raises(APIClientError) as exc_info:
            client._post("bad_endpoint", data={"fail": True})
        assert "Network connection failed" in str(exc_info.value)


@pytest.mark.unit
def test_close(client):
    with patch.object(client.session, "close") as mock_close:
        client.close()
        mock_close.assert_called_once()


@pytest.mark.unit
def test_get_request_exception_logs_and_raises(client, caplog):
    with patch.object(
        client.session, "get", side_effect=requests.RequestException("Timeout error")
    ):
        with caplog.at_level("ERROR"):
            with pytest.raises(APIClientError) as exc_info:
                client._get("timeout_endpoint")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code.value == "NET001"

            # Check that the error message contains the network error description
            error_str = str(exc_info.value)
            assert "[NET001]" in error_str
            assert "Network connection failed" in error_str

            # Check that the URL and error details are in the context
            assert "timeout_endpoint" in error_str or exc_info.value.context.get(
                "url", ""
            ).endswith("timeout_endpoint")
            assert "Timeout error" in str(exc_info.value.context.get("error", ""))


@pytest.mark.unit
def test_post_request_exception_logs_and_raises(client, caplog):
    with patch.object(
        client.session, "post", side_effect=requests.RequestException("Timeout error")
    ):
        with caplog.at_level("ERROR"):
            with pytest.raises(APIClientError) as exc_info:
                client._post("timeout_endpoint", data={"foo": "bar"})

            # Check that the exception has the correct error code
            assert exc_info.value.error_code.value == "NET001"

            # Check that the error message contains the network error description
            error_str = str(exc_info.value)
            assert "[NET001]" in error_str
            assert "Network connection failed" in error_str

            # Check that the URL and error details are in the context
            assert "timeout_endpoint" in error_str or exc_info.value.context.get(
                "url", ""
            ).endswith("timeout_endpoint")
            assert "Timeout error" in str(exc_info.value.context.get("error", ""))


# Additional comprehensive unit tests for BaseAPIClient


@pytest.mark.unit
def test_init_default_values():
    """Test BaseAPIClient initialization with default values."""
    client = BaseAPIClient()
    assert client.rate_limit_delay == 1.0
    assert client.session is not None
    assert not client.is_closed
    assert client.session.headers["User-Agent"] is not None
    client.close()


@pytest.mark.unit
def test_init_custom_rate_limit():
    """Test BaseAPIClient initialization with custom rate limit delay."""
    client = BaseAPIClient(rate_limit_delay=2.5)
    assert client.rate_limit_delay == 2.5
    client.close()


@pytest.mark.unit
def test_repr():
    """Test string representation of BaseAPIClient."""
    client = BaseAPIClient(rate_limit_delay=0.5)
    repr_str = repr(client)
    assert "BaseAPIClient" in repr_str
    assert "rate_limit_delay=0.5" in repr_str
    assert "status=active" in repr_str
    client.close()


@pytest.mark.unit
def test_repr_closed():
    """Test string representation of closed BaseAPIClient."""
    client = BaseAPIClient()
    client.close()
    repr_str = repr(client)
    assert "status=closed" in repr_str


@pytest.mark.unit
def test_context_manager():
    """Test BaseAPIClient as context manager."""
    with BaseAPIClient() as client:
        assert not client.is_closed
        assert isinstance(client, BaseAPIClient)
    assert client.is_closed


@pytest.mark.unit
def test_context_manager_exception_handling():
    """Test context manager properly closes on exception."""
    client = None
    try:
        with BaseAPIClient() as c:
            client = c
            assert not client.is_closed
            raise ValueError("Test exception")
            # The following line will not be reached if exception is raised
            assert client.is_closed
    except ValueError:
        pass
    # After the context manager exits, client is still in scope here
    assert client is not None
    assert client.is_closed


@pytest.mark.unit
def test_is_closed_property():
    """Test is_closed property behavior."""
    client = BaseAPIClient()
    assert not client.is_closed

    client.close()
    assert client.is_closed

    # Multiple closes should be safe
    client.close()
    assert client.is_closed


@pytest.mark.unit
def test_close_when_already_closed():
    """Test that closing an already closed client is safe."""
    client = BaseAPIClient()
    client.close()
    assert client.is_closed

    # Should not raise an exception
    client.close()
    assert client.is_closed


@pytest.mark.unit
def test_get_with_closed_session():
    """Test that _get raises error when session is closed."""
    client = BaseAPIClient()
    client.close()

    with pytest.raises(APIClientError) as exc_info:
        client._get("test_endpoint")

    # Check that the exception has the correct error code for session closed
    assert exc_info.value.error_code.value == "FULL007"

    # Check that the error message indicates session closure
    error_str = str(exc_info.value)
    assert "[FULL007]" in error_str
    assert "Session closed" in error_str


@pytest.mark.unit
def test_post_with_closed_session():
    """Test that _post raises error when session is closed."""
    client = BaseAPIClient()
    client.close()

    with pytest.raises(APIClientError) as exc_info:
        client._post("test_endpoint", data={"test": "data"})

    # Check that the exception has the correct error code for session closed
    assert exc_info.value.error_code.value == "FULL007"

    # Check that the error message indicates session closure
    error_str = str(exc_info.value)
    assert "[FULL007]" in error_str
    assert "Session closed" in error_str


@pytest.mark.unit
@patch("time.sleep")
def test_get_with_stream_parameter(mock_sleep):
    """Test _get method with stream parameter."""
    client = BaseAPIClient()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    with patch.object(client.session, "get", return_value=mock_response) as mock_get:
        response = client._get("test_endpoint", params={"q": "test"}, stream=True)
        mock_get.assert_called_once_with(
            client.BASE_URL + "test_endpoint",
            params={"q": "test"},
            timeout=client.DEFAULT_TIMEOUT,
            stream=True,
        )
        assert response == mock_response
    client.close()


@pytest.mark.unit
@patch("time.sleep")
def test_get_logs_debug_and_info(mock_sleep, client, caplog):
    """Test that _get method logs debug and info messages."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    with patch.object(client.session, "get", return_value=mock_response):
        with caplog.at_level("DEBUG"):
            client._get("test_endpoint", params={"q": "test"})

        log_messages = [record.message for record in caplog.records]
        assert any("GET request to" in msg and "with params=" in msg for msg in log_messages)
        assert any(
            "GET request to" in msg and "succeeded with status" in msg for msg in log_messages
        )


@pytest.mark.unit
@patch("time.sleep")
def test_post_logs_debug_and_info(mock_sleep, client, caplog):
    """Test that _post method logs debug and info messages."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 201

    with patch.object(client.session, "post", return_value=mock_response):
        with caplog.at_level("DEBUG"):
            client._post(
                "test_endpoint",
                data={"key": "value"},
                headers={"Content-Type": "application/json"},
            )

        log_messages = [record.message for record in caplog.records]
        assert any("POST request to" in msg and "with data=" in msg for msg in log_messages)
        assert any(
            "POST request to" in msg and "succeeded with status" in msg for msg in log_messages
        )


@pytest.mark.unit
@patch("time.sleep")
def test_get_http_error_handling(mock_sleep, client):
    """Test _get method handles HTTP errors correctly."""
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(client.session, "get") as mock_get:
        mock_response = MagicMock()
        mock_http_error = requests.HTTPError("404 Not Found")
        mock_http_error.response = MagicMock()
        mock_http_error.response.status_code = 404
        mock_response.raise_for_status.side_effect = mock_http_error
        mock_get.return_value = mock_response

        with pytest.raises(APIClientError) as exc_info:
            client._get("not_found_endpoint")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.HTTP404

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[HTTP404]" in error_str
        assert "not found" in error_str.lower()


@pytest.mark.unit
@patch("time.sleep")
def test_post_http_error_handling(mock_sleep, client):
    """Test _post method handles HTTP errors correctly."""
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(client.session, "post") as mock_post:
        mock_response = MagicMock()
        mock_http_error = requests.HTTPError("400 Bad Request")
        mock_http_error.response = MagicMock()
        mock_http_error.response.status_code = 400
        mock_response.raise_for_status.side_effect = mock_http_error
        mock_post.return_value = mock_response

        with pytest.raises(APIClientError) as exc_info:
            client._post("bad_request_endpoint", data={"invalid": "data"})

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.NET001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[NET001]" in error_str
        assert "Network connection failed" in error_str


@pytest.mark.unit
@patch("time.sleep")
def test_get_timeout_handling(mock_sleep, client):
    """Test _get method handles timeout errors."""
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(client.session, "get", side_effect=requests.Timeout("Request timeout")):
        with pytest.raises(APIClientError) as exc_info:
            client._get("timeout_endpoint")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.NET001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[NET001]" in error_str
        assert "Network connection failed" in error_str


@pytest.mark.unit
@patch("time.sleep")
def test_post_timeout_handling(mock_sleep, client):
    """Test _post method handles timeout errors."""
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(client.session, "post", side_effect=requests.Timeout("Request timeout")):
        with pytest.raises(APIClientError) as exc_info:
            client._post("timeout_endpoint", data={"test": "data"})

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.NET001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[NET001]" in error_str
        assert "Network connection failed" in error_str


@pytest.mark.unit
@patch("time.sleep")
def test_get_connection_error_handling(mock_sleep, client):
    """Test _get method handles connection errors."""
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(
        client.session, "get", side_effect=requests.ConnectionError("Connection failed")
    ):
        with pytest.raises(APIClientError) as exc_info:
            client._get("connection_error_endpoint")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.NET001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[NET001]" in error_str
        assert "Network connection failed" in error_str


@pytest.mark.unit
@patch("time.sleep")
def test_post_connection_error_handling(mock_sleep, client):
    """Test _post method handles connection errors."""
    from pyeuropepmc.error_codes import ErrorCodes

    with patch.object(
        client.session, "post", side_effect=requests.ConnectionError("Connection failed")
    ):
        with pytest.raises(APIClientError) as exc_info:
            client._post("connection_error_endpoint", data={"test": "data"})

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.NET001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[NET001]" in error_str
        assert "Network connection failed" in error_str


@pytest.mark.unit
@patch("time.sleep")
def test_rate_limiting_sleep_called(mock_sleep, client):
    """Test that rate limiting sleep is called after requests."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    with patch.object(client.session, "get", return_value=mock_response):
        client._get("test_endpoint")
        mock_sleep.assert_called_once_with(client.rate_limit_delay)


@pytest.mark.unit
@patch("time.sleep")
def test_rate_limiting_sleep_called_on_error(mock_sleep, client):
    """Test that rate limiting sleep is called even when request fails."""
    with patch.object(client.session, "get", side_effect=requests.RequestException("Error")):
        with pytest.raises(APIClientError):
            client._get("error_endpoint")
        mock_sleep.assert_called_once_with(client.rate_limit_delay)


@pytest.mark.unit
def test_user_agent_header_set():
    """Test that User-Agent header is properly set."""
    client = BaseAPIClient()
    assert client.session is not None, "Session should not be None"
    user_agent = client.session.headers.get("User-Agent")
    assert user_agent is not None
    assert isinstance(user_agent, str)
    assert "pyeuropepmc/1.0.0" in user_agent
    assert "https://github.com/JonasHeinickeBio/pyEuropePMC" in user_agent
    assert "jonas.heinicke@helmholtz-hzi.de" in user_agent
    client.close()


@pytest.mark.unit
def test_constants():
    """Test that class constants are set correctly."""
    assert BaseAPIClient.BASE_URL == "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    assert BaseAPIClient.DEFAULT_TIMEOUT == 15
    assert BaseAPIClient.logger is not None


@pytest.mark.unit
def test_api_client_error_exception():
    """Test APIClientError exception can be raised and caught."""
    from pyeuropepmc.error_codes import ErrorCodes

    with pytest.raises(APIClientError):
        raise APIClientError(ErrorCodes.NET001)


# Test backoff functionality (challenging to test directly, but we can test the decorators exist)
@pytest.mark.unit
def test_backoff_decorators_present():
    """Test that backoff decorators are applied to methods."""
    # Check that the methods have backoff attributes
    assert hasattr(BaseAPIClient._get, "__wrapped__")
    assert hasattr(BaseAPIClient._post, "__wrapped__")


@pytest.mark.unit
def test_close_logs_debug_message(caplog):
    """Test that close method logs debug message."""
    client = BaseAPIClient()
    with caplog.at_level("DEBUG"):
        client.close()

    log_messages = [record.message for record in caplog.records]
    assert any("Closing session" in msg for msg in log_messages)


@pytest.mark.unit
def test_session_none_handling():
    """Test handling when session is None."""
    client = BaseAPIClient()
    # Manually set session to None (simulates edge case)
    client.session = None

    assert client.is_closed

    with pytest.raises(APIClientError):
        client._get("test")

    with pytest.raises(APIClientError):
        client._post("test", data={})
