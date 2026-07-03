"""
Additional unit tests for BaseAPIClient to improve test coverage.

This module focuses on testing edge cases, error paths, and less common scenarios
to achieve higher test coverage for the base module.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError

pytestmark = pytest.mark.unit


class TestBaseAPIClientCoverage:
    """Additional test coverage for BaseAPIClient edge cases."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.client = BaseAPIClient()

    def teardown_method(self):
        """Clean up after each test method."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    def test_get_xml_error_context_404(self):
        """Test XML error context for 404 status."""
        context = self.client._get_xml_error_context("fullTextXML", 404)
        assert "XML full text not available" in context
        assert "PMC ID is invalid" in context or "Article is not open access" in context

    def test_get_xml_error_context_403(self):
        """Test XML error context for 403 status."""
        context = self.client._get_xml_error_context("fullTextXML", 403)
        assert "Access denied" in context
        assert "access-restricted" in context

    def test_get_xml_error_context_500(self):
        """Test XML error context for 500 status."""
        context = self.client._get_xml_error_context("fullTextXML", 500)
        assert "Internal server error" in context
        assert "service may be temporarily experiencing issues" in context

    def test_get_xml_error_context_502(self):
        """Test XML error context for 502 status."""
        context = self.client._get_xml_error_context("fullTextXML", 502)
        assert "XML request failed" in context
        assert "status 502" in context

    def test_get_xml_error_context_503(self):
        """Test XML error context for 503 status."""
        context = self.client._get_xml_error_context("fullTextXML", 503)
        assert "XML request failed" in context
        assert "status 503" in context

    def test_get_xml_error_context_unknown(self):
        """Test XML error context for unknown status code."""
        context = self.client._get_xml_error_context("fullTextXML", 418)
        assert "XML request failed" in context
        assert "status 418" in context

    def test_get_pdf_render_error_context_404(self):
        """Test PDF render error context for 404 status."""
        context = self.client._get_pdf_render_error_context(404)
        assert "PDF not available via render endpoint" in context
        assert "Article may not have PDF format" in context

    def test_get_pdf_render_error_context_403(self):
        """Test PDF render error context for 403 status."""
        context = self.client._get_pdf_render_error_context(403)
        assert "PDF access denied via render endpoint" in context
        assert "Article may be under embargo" in context

    def test_get_pdf_render_error_context_500(self):
        """Test PDF render error context for 500 status."""
        context = self.client._get_pdf_render_error_context(500)
        assert "PDF render service experiencing internal errors" in context

    def test_get_pdf_render_error_context_unknown(self):
        """Test PDF render error context for unknown status code."""
        context = self.client._get_pdf_render_error_context(418)
        assert "PDF render request failed with status 418" in context

    def test_get_pdf_backend_error_context_404(self):
        """Test PDF backend error context for 404 status."""
        context = self.client._get_pdf_backend_error_context(404)
        assert "PDF not available via backend service" in context
        assert "ZIP archive fallback" in context

    def test_get_pdf_backend_error_context_403(self):
        """Test PDF backend error context for 403 status."""
        context = self.client._get_pdf_backend_error_context(403)
        assert "PDF access denied via backend service" in context
        assert "access-restricted" in context

    def test_get_pdf_backend_error_context_500(self):
        """Test PDF backend error context for 500 status."""
        context = self.client._get_pdf_backend_error_context(500)
        assert "PDF backend service experiencing internal errors" in context

    def test_get_pdf_backend_error_context_unknown(self):
        """Test PDF backend error context for unknown status code."""
        context = self.client._get_pdf_backend_error_context(418)
        assert "PDF backend request failed with status 418" in context

    def test_get_generic_error_context_404(self):
        """Test generic error context for 404 status."""
        context = self.client._get_generic_error_context(404)
        assert "Resource not found" in context
        assert "endpoint URL may be incorrect" in context

    def test_get_generic_error_context_403(self):
        """Test generic error context for 403 status."""
        context = self.client._get_generic_error_context(403)
        assert "Access forbidden" in context
        assert "access-restricted" in context

    def test_get_generic_error_context_500(self):
        """Test generic error context for 500 status."""
        context = self.client._get_generic_error_context(500)
        assert "Internal server error" in context
        assert "temporarily experiencing issues" in context

    def test_get_generic_error_context_429(self):
        """Test generic error context for 429 status."""
        context = self.client._get_generic_error_context(429)
        assert "Rate limit exceeded" in context
        assert "Too many requests" in context

    def test_get_generic_error_context_502(self):
        """Test generic error context for 502 status."""
        context = self.client._get_generic_error_context(502)
        assert "Bad gateway" in context
        assert "temporarily unavailable" in context

    def test_get_generic_error_context_503(self):
        """Test generic error context for 503 status."""
        context = self.client._get_generic_error_context(503)
        assert "Service unavailable" in context
        assert "maintenance" in context

    def test_get_generic_error_context_unknown(self):
        """Test generic error context for unknown status code."""
        context = self.client._get_generic_error_context(418)
        assert "Request failed with HTTP status 418" in context
        assert "API documentation" in context

    def test_get_error_context_xml_endpoint(self):
        """Test error context for XML endpoint."""
        context = self.client._get_error_context("fullTextXML", 404)
        assert "XML full text not available" in context
        assert "PMC ID is invalid" in context or "Article is not open access" in context

    def test_get_error_context_pdf_render_endpoint(self):
        """Test error context for PDF render endpoint."""
        context = self.client._get_error_context("render.cgi", 403)
        assert "Access forbidden" in context
        assert "access-restricted" in context

    def test_get_error_context_pdf_backend_endpoint(self):
        """Test error context for PDF backend endpoint."""
        context = self.client._get_error_context("pdf-backend", 500)
        assert "Internal server error" in context
        assert "service may be temporarily experiencing issues" in context

    def test_get_error_context_generic_endpoint(self):
        """Test error context for generic endpoint."""
        context = self.client._get_error_context("unknown/endpoint", 429)
        assert "Rate limit exceeded" in context

    def test_get_with_non_200_status_and_context(self):
        """Test _get method with non-200 status code to trigger error context."""
        with patch.object(self.client.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.url = "https://example.com/fullTextXML/123456"
            mock_http_error = requests.HTTPError("Not Found")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 404
            mock_response.raise_for_status.side_effect = mock_http_error
            mock_get.return_value = mock_response

            with pytest.raises(APIClientError) as exc_info:
                self.client._get("https://example.com/fullTextXML/123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.HTTP404

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[HTTP404]" in error_str
            assert "not found" in error_str.lower() or "404" in error_str

    def test_get_with_network_error(self):
        """Test _get method with network error."""
        with patch.object(
            self.client.session, "get", side_effect=requests.RequestException("Network error")
        ):
            with pytest.raises(APIClientError) as exc_info:
                self.client._get("https://example.com/test")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.NET001

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[NET001]" in error_str
            assert "Network connection failed" in error_str

    def test_post_with_non_200_status_and_context(self):
        """Test _post method with non-200 status code to trigger error context."""
        with patch.object(self.client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.url = "https://example.com/search"
            mock_http_error = requests.HTTPError("Forbidden")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 403
            mock_response.raise_for_status.side_effect = mock_http_error
            mock_post.return_value = mock_response

            with pytest.raises(APIClientError) as exc_info:
                self.client._post("https://example.com/search", data={})

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.HTTP403

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[HTTP403]" in error_str
            assert "forbidden" in error_str.lower() or "403" in error_str

    def test_get_with_http_500_error(self):
        """Test _get method with 500 status code."""
        with patch.object(self.client.session, "get") as mock_get:
            mock_http_error = requests.HTTPError("Server Error")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 500
            mock_get.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._get("https://example.com/test")
            assert exc_info.value.error_code == ErrorCodes.HTTP500

    def test_get_with_http_429_error(self):
        """Test _get method with 429 status code."""
        with patch.object(self.client.session, "get") as mock_get:
            mock_http_error = requests.HTTPError("Rate Limited")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 429
            mock_get.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._get("https://example.com/test")
            assert exc_info.value.error_code == ErrorCodes.RATE429

    def test_get_with_http_403_error(self):
        """Test _get method with 403 status code."""
        with patch.object(self.client.session, "get") as mock_get:
            mock_http_error = requests.HTTPError("Forbidden")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 403
            mock_get.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._get("https://example.com/test")
            assert exc_info.value.error_code == ErrorCodes.HTTP403

    def test_get_with_http_unknown_error(self):
        """Test _get method with unknown status code."""
        with patch.object(self.client.session, "get") as mock_get:
            mock_http_error = requests.HTTPError("Unknown")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 418
            mock_get.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._get("https://example.com/test")
            assert exc_info.value.error_code == ErrorCodes.NET001

    def test_get_success_logging(self):
        """Test _get method logs success on 200 response."""
        with patch.object(self.client.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.url = "https://example.com/test"
            mock_get.return_value = mock_response

            response = self.client._get("https://example.com/test")
            assert response.status_code == 200

    def test_post_with_http_500_error(self):
        """Test _post method with 500 status code."""
        with patch.object(self.client.session, "post") as mock_post:
            mock_http_error = requests.HTTPError("Server Error")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 500
            mock_post.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._post("https://example.com/test", data={})
            assert exc_info.value.error_code == ErrorCodes.HTTP500

    def test_post_with_http_429_error(self):
        """Test _post method with 429 status code."""
        with patch.object(self.client.session, "post") as mock_post:
            mock_http_error = requests.HTTPError("Rate Limited")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 429
            mock_post.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._post("https://example.com/test", data={})
            assert exc_info.value.error_code == ErrorCodes.RATE429

    def test_post_with_http_403_error(self):
        """Test _post method with 403 status code."""
        with patch.object(self.client.session, "post") as mock_post:
            mock_http_error = requests.HTTPError("Forbidden")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 403
            mock_post.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._post("https://example.com/test", data={})
            assert exc_info.value.error_code == ErrorCodes.HTTP403

    def test_post_with_http_unknown_error(self):
        """Test _post method with unknown status code."""
        with patch.object(self.client.session, "post") as mock_post:
            mock_http_error = requests.HTTPError("Unknown")
            mock_http_error.response = Mock()
            mock_http_error.response.status_code = 418
            mock_post.return_value.raise_for_status.side_effect = mock_http_error

            with pytest.raises(APIClientError) as exc_info:
                self.client._post("https://example.com/test", data={})
            assert exc_info.value.error_code == ErrorCodes.NET001

    def test_post_with_network_error(self):
        """Test _post method with network error."""
        with patch.object(
            self.client.session, "post", side_effect=requests.RequestException("Network error")
        ):
            with pytest.raises(APIClientError) as exc_info:
                self.client._post("https://example.com/test", data={})
            assert exc_info.value.error_code == ErrorCodes.NET001

    def test_post_success_logging(self):
        """Test _post method logs success on 200 response."""
        with patch.object(self.client.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.url = "https://example.com/test"
            mock_post.return_value = mock_response

            response = self.client._post("https://example.com/test", data={})
            assert response.status_code == 200

    def test_get_error_context_pdf_render(self):
        """Test _get_error_context routes to PDF render."""
        context = self.client._get_error_context("render.cgi?pdf=render", 403)
        assert "PDF access denied" in context

    def test_get_error_context_pdf_backend(self):
        """Test _get_error_context routes to PDF backend."""
        context = self.client._get_error_context("ptpmcrender.fcgi", 404)
        assert "PDF not available via backend" in context

    def test_xml_error_context_non_numeric_status(self):
        """Test _get_xml_error_context with non-numeric status code."""
        from pyeuropepmc.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            self.client._get_xml_error_context("fullTextXML", "abc")

    def test_context_manager(self):
        """Test context manager __enter__ and __exit__."""
        client = BaseAPIClient()
        with client as c:
            assert c is client
            assert not c.is_closed
        assert client.is_closed

    def test_close(self):
        """Test close method."""
        client = BaseAPIClient()
        assert not client.is_closed
        client.close()
        assert client.is_closed
        # Closing again should be safe
        client.close()
        assert client.is_closed

    def test_repr(self):
        """Test __repr__."""
        client = BaseAPIClient()
        rep = repr(client)
        assert "BaseAPIClient" in rep
        assert "active" in rep
        client.close()
        rep2 = repr(client)
        assert "closed" in rep2

    def test_get_with_closed_session(self):
        """Test _get raises error when session is closed."""
        self.client.close()
        with pytest.raises(APIClientError) as exc_info:
            self.client._get("https://example.com/test")
        assert exc_info.value.error_code == ErrorCodes.FULL007

    def test_post_with_closed_session(self):
        """Test _post raises error when session is closed."""
        self.client.close()
        with pytest.raises(APIClientError) as exc_info:
            self.client._post("https://example.com/test", data={})
        assert exc_info.value.error_code == ErrorCodes.FULL007
