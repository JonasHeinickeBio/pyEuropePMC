"""
Unit tests for UnpaywallClient.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, UnpaywallError
from pyeuropepmc.features.enrich.sources.unpaywall_client import UnpaywallClient


@pytest.fixture
def mock_record():
    """Fixture for a typical Unpaywall API response."""
    return {
        "doi": "10.1234/test",
        "is_oa": True,
        "oa_status": "gold",
        "best_oa_location": {
            "url_for_pdf": "https://example.com/article.pdf",
            "url": "https://example.com/article",
            "license": "cc-by-4.0",
            "repository_institution": "Example Repository",
        },
        "oa_locations": [
            {
                "url_for_pdf": "https://example.com/article.pdf",
                "url": "https://example.com/article",
                "type": "publisher",
            },
        ],
    }


@pytest.fixture
def client():
    """Fixture for UnpaywallClient with mocked super().__init__."""
    with patch("pyeuropepmc.features.enrich.sources.unpaywall_client.BaseAPIClient.__init__"):
        client = UnpaywallClient(email="test@example.com")
        yield client


class TestUnpaywallClient:
    """Tests for UnpaywallClient."""

    def test_init_valid_email(self):
        """Test initialization with valid email."""
        with patch("pyeuropepmc.features.enrich.sources.unpaywall_client.BaseAPIClient.__init__"):
            client = UnpaywallClient(email="user@example.com")
        assert client.email == "user@example.com"

    def test_init_empty_email(self):
        """Test initialization with empty email."""
        with (
            patch("pyeuropepmc.features.enrich.sources.unpaywall_client.BaseAPIClient.__init__"),
            pytest.raises(Exception),  # noqa: B017
        ):
            UnpaywallClient(email="")

    def test_init_invalid_email_no_at(self):
        """Test initialization with email missing @."""
        with (
            patch("pyeuropepmc.features.enrich.sources.unpaywall_client.BaseAPIClient.__init__"),
            pytest.raises(Exception),  # noqa: B017
        ):
            UnpaywallClient(email="notanemail")

    def test_lookup_by_doi_empty(self, client):
        """Test lookup with empty DOI."""
        with pytest.raises(Exception):  # noqa: B017
            client.lookup_by_doi("")

    def test_lookup_by_doi_success(self, client, mock_record):
        """Test successful DOI lookup."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_record
        client._get = MagicMock(return_value=mock_response)

        result = client.lookup_by_doi("10.1234/test")
        assert result == mock_record

    def test_lookup_by_doi_not_found(self, client):
        """Test DOI lookup returns None."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        client._get = MagicMock(return_value=mock_response)

        result = client.lookup_by_doi("10.1234/unknown")
        assert result is None

    def test_lookup_by_doi_non_200(self, client):
        """Test DOI lookup returns non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        client._get = MagicMock(return_value=mock_response)

        result = client.lookup_by_doi("10.1234/ratelimited")
        assert result is None

    def test_lookup_by_doi_response_none(self, client):
        """Test DOI lookup when _get returns None."""
        client._get = MagicMock(return_value=None)

        result = client.lookup_by_doi("10.1234/test")
        assert result is None

    def test_lookup_by_doi_http_error_404(self, client):
        """Test DOI lookup when _get reports a 404."""
        # What BaseAPIClient._get raises for an HTTP 404.
        error = APIClientError(ErrorCodes.HTTP404, {"url": "u", "status_code": 404})
        client._get = MagicMock(side_effect=error)

        result = client.lookup_by_doi("10.1234/notfound")
        assert result is None

    def test_lookup_by_doi_http_error_other(self, client):
        """Test DOI lookup with non-404 HTTP error."""
        error = APIClientError(ErrorCodes.HTTP500, {"url": "u", "status_code": 500})
        client._get = MagicMock(side_effect=error)

        with pytest.raises(UnpaywallError) as exc_info:
            client.lookup_by_doi("10.1234/servererror")
        assert exc_info.value.error_code == ErrorCodes.NET001
        assert exc_info.value.__cause__ is error

    def test_lookup_by_doi_request_exception(self, client):
        """Test DOI lookup with network error."""
        # What BaseAPIClient._get raises when the request itself fails.
        error = APIClientError(ErrorCodes.NET001, {"url": "u", "error": "Connection timeout"})
        client._get = MagicMock(side_effect=error)

        with pytest.raises(UnpaywallError) as exc_info:
            client.lookup_by_doi("10.1234/timeout")
        assert "Connection timeout" in exc_info.value.context["message"]

    def test_get_oa_status_found(self, client, mock_record):
        """Test get_oa_status with found DOI."""
        client.lookup_by_doi = MagicMock(return_value=mock_record)
        result = client.get_oa_status("10.1234/test")
        assert result == "gold"

    def test_get_oa_status_not_found(self, client):
        """Test get_oa_status with not found DOI."""
        client.lookup_by_doi = MagicMock(return_value=None)
        result = client.get_oa_status("10.1234/unknown")
        assert result is None

    def test_has_oa_version_true(self, client, mock_record):
        """Test has_oa_version returns True."""
        client.lookup_by_doi = MagicMock(return_value=mock_record)
        result = client.has_oa_version("10.1234/test")
        assert result is True

    def test_has_oa_version_false(self, client):
        """Test has_oa_version returns False."""
        client.lookup_by_doi = MagicMock(return_value={"is_oa": False})
        result = client.has_oa_version("10.1234/closed")
        assert result is False

    def test_has_oa_version_not_found(self, client):
        """Test has_oa_version with not found DOI."""
        client.lookup_by_doi = MagicMock(return_value=None)
        result = client.has_oa_version("10.1234/unknown")
        assert result is False

    def test_get_best_oa_location_found(self, client, mock_record):
        """Test get_best_oa_location with found DOI."""
        client.lookup_by_doi = MagicMock(return_value=mock_record)
        result = client.get_best_oa_location("10.1234/test")
        assert result == mock_record["best_oa_location"]

    def test_get_best_oa_location_not_found(self, client):
        """Test get_best_oa_location with not found DOI."""
        client.lookup_by_doi = MagicMock(return_value=None)
        result = client.get_best_oa_location("10.1234/unknown")
        assert result is None

    def test_get_oa_locations_found(self, client, mock_record):
        """Test get_oa_locations with found DOI."""
        client.lookup_by_doi = MagicMock(return_value=mock_record)
        result = client.get_oa_locations("10.1234/test")
        assert len(result) == 1
        assert result[0]["type"] == "publisher"

    def test_get_oa_locations_not_found(self, client):
        """Test get_oa_locations with not found DOI."""
        client.lookup_by_doi = MagicMock(return_value=None)
        result = client.get_oa_locations("10.1234/unknown")
        assert result == []

    def test_get_oa_locations_none(self, client):
        """Test get_oa_locations when oa_locations is None."""
        client.lookup_by_doi = MagicMock(return_value={"oa_locations": None})
        result = client.get_oa_locations("10.1234/null")
        assert result == []

    def test_get_pdf_url_found(self, client, mock_record):
        """Test get_pdf_url returns url_for_pdf."""
        client.get_best_oa_location = MagicMock(return_value=mock_record["best_oa_location"])
        result = client.get_pdf_url("10.1234/test")
        assert result == "https://example.com/article.pdf"

    def test_get_pdf_url_no_url_for_pdf(self, client):
        """Test get_pdf_url falls back to url containing 'pdf'."""
        client.get_best_oa_location = MagicMock(
            return_value={
                "url_for_pdf": None,
                "url": "https://example.com/pdf/article.html",
            }
        )
        result = client.get_pdf_url("10.1234/test")
        assert result == "https://example.com/pdf/article.html"

    def test_get_pdf_url_fallback_full(self, client):
        """Test get_pdf_url falls back to url containing 'full'."""
        client.get_best_oa_location = MagicMock(
            return_value={
                "url_for_pdf": "",
                "url": "https://example.com/full/article",
            }
        )
        result = client.get_pdf_url("10.1234/test")
        assert result == "https://example.com/full/article"

    def test_get_pdf_url_no_match(self, client):
        """Test get_pdf_url returns None when no PDF URL available."""
        client.get_best_oa_location = MagicMock(
            return_value={
                "url_for_pdf": None,
                "url": "https://example.com/abstract",
            }
        )
        result = client.get_pdf_url("10.1234/test")
        assert result is None

    def test_get_pdf_url_no_location(self, client):
        """Test get_pdf_url with no best OA location."""
        client.get_best_oa_location = MagicMock(return_value=None)
        result = client.get_pdf_url("10.1234/test")
        assert result is None

    def test_get_pdf_url_empty_url_for_pdf(self, client):
        """Test get_pdf_url with empty url_for_pdf string."""
        client.get_best_oa_location = MagicMock(
            return_value={
                "url_for_pdf": "",
                "url": "https://example.com/article",
            }
        )
        # Empty string is falsy, so falls through
        # But url doesn't contain pdf or full, so returns None
        result = client.get_pdf_url("10.1234/test")
        assert result is None

    def test_get_license_found(self, client, mock_record):
        """Test get_license with found DOI."""
        client.get_best_oa_location = MagicMock(return_value=mock_record["best_oa_location"])
        result = client.get_license("10.1234/test")
        assert result == "cc-by-4.0"

    def test_get_license_not_found(self, client):
        """Test get_license with not found DOI."""
        client.get_best_oa_location = MagicMock(return_value=None)
        result = client.get_license("10.1234/unknown")
        assert result is None

    def test_get_repository_found(self, client, mock_record):
        """Test get_repository with found DOI."""
        client.get_best_oa_location = MagicMock(return_value=mock_record["best_oa_location"])
        result = client.get_repository("10.1234/test")
        assert result == "Example Repository"

    def test_get_repository_not_found(self, client):
        """Test get_repository with not found DOI."""
        client.get_best_oa_location = MagicMock(return_value=None)
        result = client.get_repository("10.1234/unknown")
        assert result is None


def _response(status_code: int, body: bytes = b"{}") -> requests.Response:
    """A real ``requests.Response`` with the body already loaded."""
    response = requests.Response()
    response.status_code = status_code
    response.reason = "OK" if status_code < 400 else "Error"
    response.url = "https://api.unpaywall.org/v2/"
    response._content = body
    response._content_consumed = True
    return response


class TestLookupByDoiOverHttp:
    """lookup_by_doi() with the real BaseAPIClient._get and a mocked session."""

    @pytest.fixture
    def http_client(self):
        with patch("time.sleep"):
            instance = UnpaywallClient(email="test@example.com", rate_limit_delay=0)
            yield instance
            instance.close()

    def test_requests_the_doi_under_the_api_base_url(self, http_client, mock_record):
        body = json.dumps(mock_record).encode()
        with patch.object(http_client.session, "get", return_value=_response(200, body)) as get:
            http_client.lookup_by_doi("10.1234/test")

        url = get.call_args.args[0]
        assert url == "https://api.unpaywall.org/v2/10.1234/test"
        assert get.call_args.kwargs["params"] == {"email": "test@example.com"}

    def test_characters_a_path_cannot_carry_are_quoted(self, http_client):
        with patch.object(http_client.session, "get", return_value=_response(200)) as get:
            http_client.lookup_by_doi("10.1002/(SICI)1097-4636#x?y z")

        assert get.call_args.args[0] == (
            "https://api.unpaywall.org/v2/10.1002/(SICI)1097-4636%23x%3Fy%20z"
        )

    def test_200_returns_the_record(self, http_client, mock_record):
        body = json.dumps(mock_record).encode()
        with patch.object(http_client.session, "get", return_value=_response(200, body)):
            assert http_client.lookup_by_doi("10.1234/test") == mock_record

    def test_404_returns_none(self, http_client):
        with patch.object(http_client.session, "get", return_value=_response(404)):
            assert http_client.lookup_by_doi("10.1234/unknown") is None

    def test_500_raises_unpaywall_error(self, http_client):
        with (
            patch.object(http_client.session, "get", return_value=_response(500)),
            pytest.raises(UnpaywallError) as exc_info,
        ):
            http_client.lookup_by_doi("10.1234/test")

        assert exc_info.value.error_code == ErrorCodes.NET001
        assert "HTTP error 500" in exc_info.value.context["message"]

    def test_connection_error_raises_unpaywall_error(self, http_client):
        with (
            patch.object(
                http_client.session, "get", side_effect=requests.ConnectionError("refused")
            ),
            pytest.raises(UnpaywallError) as exc_info,
        ):
            http_client.lookup_by_doi("10.1234/test")

        assert exc_info.value.error_code == ErrorCodes.NET001
        assert "refused" in exc_info.value.context["message"]

    def test_closed_client_error_is_not_disguised(self, http_client):
        http_client.close()
        with pytest.raises(APIClientError) as exc_info:
            http_client.lookup_by_doi("10.1234/test")

        assert exc_info.value.error_code == ErrorCodes.FULL007

    def test_best_oa_location_is_found(self, http_client, mock_record):
        """The FullTextClient fallbacks call this; it could never succeed before."""
        body = json.dumps(mock_record).encode()
        with patch.object(http_client.session, "get", return_value=_response(200, body)):
            location = http_client.get_best_oa_location("10.1234/test")

        assert location == mock_record["best_oa_location"]
