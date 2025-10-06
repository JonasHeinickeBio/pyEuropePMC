"""
Additional unit tests for FullTextClient to improve test coverage.
"""

import gzip
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import APIClientError, FullTextError
from pyeuropepmc.fulltext import FullTextClient

pytestmark = pytest.mark.unit


class TestFullTextClientCoverage:
    """Additional test coverage for FullTextClient edge cases."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.client = FullTextClient()

    def teardown_method(self):
        """Clean up after each test method."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    def test_check_availability_session_closed(self):
        """Test availability check when session is closed."""
        self.client.close()

        with pytest.raises(FullTextError) as exc_info:
            self.client.check_fulltext_availability("123456")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL007

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL007]" in error_str
        assert "Session closed" in error_str

    def test_check_availability_xml_session_closed_during_check(self):
        """Test XML availability check when session becomes None."""
        # Mock the session to be None during XML check
        with patch.object(self.client, "session", None):
            with pytest.raises(FullTextError) as exc_info:
                self.client.check_fulltext_availability("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL007

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL007]" in error_str
            assert "Session closed" in error_str

    def test_check_availability_pdf_session_closed_during_check(self):
        """Test PDF availability check when session becomes None during PDF check."""
        # Mock successful XML check but None session for PDF check
        with patch.object(self.client.session, "head") as mock_head:
            mock_head.return_value.status_code = 200

            # Set session to None after XML check
            original_session = self.client.session

            def side_effect(*args, **kwargs):
                if "fullTextXML" in args[0]:
                    return Mock(status_code=200)
                else:
                    # PDF check - set session to None
                    self.client.session = None
                    raise FullTextError(ErrorCodes.FULL007)

            mock_head.side_effect = side_effect

            with pytest.raises(FullTextError) as exc_info:
                self.client.check_fulltext_availability("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL007

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL007]" in error_str
            assert "Session closed" in error_str

            # Restore session for cleanup
            self.client.session = original_session

    def test_check_availability_html_session_closed_during_check(self):
        """Test HTML availability check when session becomes None during HTML check."""
        # Mock successful XML and PDF checks but None session for HTML check
        with (
            patch.object(self.client.session, "head") as mock_head,
            patch.object(self.client.session, "get") as mock_get,
        ):
            mock_head.return_value.status_code = 200
            mock_head.return_value.headers = {"content-type": "application/pdf"}

            # Set session to None during HTML check
            original_session = self.client.session

            def side_effect(*args, **kwargs):
                # HTML check - set session to None
                self.client.session = None
                raise FullTextError(ErrorCodes.FULL007)

            mock_get.side_effect = side_effect

            with pytest.raises(FullTextError) as exc_info:
                self.client.check_fulltext_availability("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL007

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL007]" in error_str
            assert "Session closed" in error_str

            # Restore session for cleanup
            self.client.session = original_session

    def test_handle_pdf_http_error_404(self):
        """Test PDF HTTP error handling for 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_error = requests.HTTPError("Not Found")
        mock_error.response = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.client._handle_pdf_http_error(mock_error, "123456")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL003

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL003]" in error_str
        assert "PDF not found for PMC123456" in error_str

    def test_handle_pdf_http_error_403(self):
        """Test PDF HTTP error handling for 403."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_error = requests.HTTPError("Forbidden")
        mock_error.response = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.client._handle_pdf_http_error(mock_error, "123456")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL008

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL008]" in error_str
        assert "Access denied for PMC123456" in error_str

    def test_handle_pdf_http_error_500(self):
        """Test PDF HTTP error handling for 500."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_error = requests.HTTPError("Server Error")
        mock_error.response = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.client._handle_pdf_http_error(mock_error, "123456")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL005

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL005]" in error_str
        assert "HTTP error 500 while downloading PDF for PMC123456" in error_str

    def test_validate_pdf_content_nonexistent_file(self):
        """Test PDF validation with nonexistent file."""
        nonexistent_path = Path("/tmp/nonexistent_file.pdf")
        result = self.client._validate_pdf_content(nonexistent_path)
        assert result is False

    def test_validate_pdf_content_empty_file(self):
        """Test PDF validation with empty file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            result = self.client._validate_pdf_content(temp_path)
            assert result is False
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validate_pdf_content_small_file(self):
        """Test PDF validation with very small file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(b"tiny")
            temp_path = Path(temp_file.name)

        try:
            result = self.client._validate_pdf_content(temp_path)
            assert result is False
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validate_pdf_content_invalid_header(self):
        """Test PDF validation with invalid header."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(b"NOT_PDF_HEADER" + b"x" * 2000)
            temp_path = Path(temp_file.name)

        try:
            result = self.client._validate_pdf_content(temp_path)
            assert result is False
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validate_pdf_content_valid_pdf(self):
        """Test PDF validation with valid PDF."""
        pdf_content = b"%PDF-1.4\n" + b"x" * 2000
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_path = Path(temp_file.name)

        try:
            result = self.client._validate_pdf_content(temp_path)
            assert result is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validate_pdf_content_exception_handling(self):
        """Test PDF validation exception handling."""
        # Mock file operations to raise exception
        with patch("builtins.open", side_effect=IOError("File error")):
            temp_path = Path("/tmp/test.pdf")
            result = self.client._validate_pdf_content(temp_path)
            assert result is False

    def test_try_pdf_endpoint_non_200_status(self):
        """Test PDF endpoint with non-200 status."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = self.client._try_pdf_endpoint(
                "http://example.com/test.pdf", Path("/tmp/test.pdf"), "test endpoint"
            )
            assert result is False

    def test_try_pdf_endpoint_wrong_content_type(self):
        """Test PDF endpoint with wrong content type."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_get.return_value = mock_response

            result = self.client._try_pdf_endpoint(
                "http://example.com/test.pdf", Path("/tmp/test.pdf"), "test endpoint"
            )
            assert result is False

    def test_try_pdf_endpoint_network_error(self):
        """Test PDF endpoint with network error."""
        with patch("requests.get", side_effect=requests.RequestException("Network error")):
            result = self.client._try_pdf_endpoint(
                "http://example.com/test.pdf", Path("/tmp/test.pdf"), "test endpoint"
            )
            assert result is False

    def test_try_pdf_endpoint_invalid_pdf_content(self):
        """Test PDF endpoint with invalid PDF content."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.iter_content.return_value = [b"INVALID_PDF_CONTENT"]
            mock_get.return_value = mock_response

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.pdf"
                result = self.client._try_pdf_endpoint(
                    "http://example.com/test.pdf", output_path, "test endpoint"
                )
                assert result is False
                # Check that temp file was cleaned up
                assert not output_path.with_suffix(".tmp").exists()

    def test_try_pdf_endpoint_general_exception(self):
        """Test PDF endpoint with general exception."""
        with patch("requests.get", side_effect=Exception("Unexpected error")):
            result = self.client._try_pdf_endpoint(
                "http://example.com/test.pdf", Path("/tmp/test.pdf"), "test endpoint"
            )
            assert result is False

    def test_try_pdf_from_zip_non_200_status(self):
        """Test ZIP PDF download with non-200 status."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = self.client._try_pdf_from_zip("123456", Path("/tmp/test.pdf"))
            assert result is False

    def test_try_pdf_from_zip_no_pdf_in_zip(self):
        """Test ZIP PDF download with no PDF in ZIP."""
        # Create a ZIP with no PDF files
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("readme.txt", "No PDF here")

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = zip_buffer.getvalue()
            mock_get.return_value = mock_response

            result = self.client._try_pdf_from_zip("123456", Path("/tmp/test.pdf"))
            assert result is False

    def test_try_pdf_from_zip_invalid_pdf_content(self):
        """Test ZIP PDF download with invalid PDF content."""
        # Create a ZIP with invalid PDF content
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test.pdf", "INVALID_PDF_CONTENT")

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = zip_buffer.getvalue()
            mock_get.return_value = mock_response

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.pdf"
                result = self.client._try_pdf_from_zip("123456", output_path)
                assert result is False

    def test_try_pdf_from_zip_exception(self):
        """Test ZIP PDF download with exception."""
        with patch("requests.get", side_effect=Exception("Network error")):
            result = self.client._try_pdf_from_zip("123456", Path("/tmp/test.pdf"))
            assert result is False

    def test_determine_bulk_archive_range_large_pmcid(self):
        """Test bulk archive range determination for large PMC IDs."""
        result = self.client._determine_bulk_archive_range(1234567)
        assert result == (1200000, 1299999)

    def test_determine_bulk_archive_range_medium_pmcid(self):
        """Test bulk archive range determination for medium PMC IDs."""
        result = self.client._determine_bulk_archive_range(567890)
        assert result == (500000, 599999)

    def test_determine_bulk_archive_range_small_pmcid(self):
        """Test bulk archive range determination for small PMC IDs."""
        result = self.client._determine_bulk_archive_range(12345)
        assert result == (10000, 19999)

    def test_determine_bulk_archive_range_very_small_pmcid(self):
        """Test bulk archive range determination for very small PMC IDs."""
        result = self.client._determine_bulk_archive_range(567)
        assert result == (0, 999)

    def test_try_bulk_xml_download_no_archive_range(self):
        """Test bulk XML download when archive range cannot be determined."""
        # Mock to return None for archive range
        with patch.object(self.client, "_determine_bulk_archive_range", return_value=None):
            result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
            assert result is False

    def test_try_bulk_xml_download_archive_not_found(self):
        """Test bulk XML download when archive is not found."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
            assert result is False

    def test_try_bulk_xml_download_invalid_gzip(self):
        """Test bulk XML download with invalid gzip file."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b"NOT_GZIP_CONTENT"]
            mock_get.return_value = mock_response

            result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
            assert result is False

    def test_try_bulk_xml_download_pmcid_not_in_content(self):
        """Test bulk XML download when PMC ID not found in content."""
        # Create valid gzip content without the target PMC ID
        xml_content = "<article><article-meta>PMC999999</article-meta></article>"
        gzip_buffer = BytesIO()
        with gzip.open(gzip_buffer, "wt", encoding="utf-8") as f:
            f.write(xml_content)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [gzip_buffer.getvalue()]
            mock_get.return_value = mock_response

            result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
            assert result is False

    def test_try_bulk_xml_download_success(self):
        """Test successful bulk XML download."""
        # Create valid gzip content with the target PMC ID
        xml_content = (
            "<article><article-meta>PMC123456</article-meta>"
            "<abstract>Test content</abstract></article>"
        )
        gzip_buffer = BytesIO()
        with gzip.open(gzip_buffer, "wt", encoding="utf-8") as f:
            f.write(xml_content)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [gzip_buffer.getvalue()]
            mock_get.return_value = mock_response

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.xml"
                result = self.client._try_bulk_xml_download("123456", output_path)
                assert result is True
                assert output_path.exists()

                # Verify content was saved correctly
                with open(output_path, "r", encoding="utf-8") as f:
                    saved_content = f.read()
                    assert "PMC123456" in saved_content
                    assert "article-meta" in saved_content

    def test_try_bulk_xml_download_network_error(self):
        """Test bulk XML download with network error."""
        with patch("requests.get", side_effect=requests.RequestException("Network error")):
            result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
            assert result is False

    def test_try_bulk_xml_download_io_error(self):
        """Test bulk XML download with IO error."""
        xml_content = "<article><article-meta>PMC123456</article-meta></article>"
        gzip_buffer = BytesIO()
        with gzip.open(gzip_buffer, "wt", encoding="utf-8") as f:
            f.write(xml_content)

        with (
            patch("requests.get") as mock_get,
            patch("builtins.open", side_effect=IOError("File error")),
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [gzip_buffer.getvalue()]
            mock_get.return_value = mock_response

            result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
            assert result is False

    def test_get_fulltext_content_invalid_format(self):
        """Test get fulltext content with invalid format."""
        with pytest.raises(FullTextError) as exc_info:
            self.client.get_fulltext_content("123456", "pdf")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL004

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL004]" in error_str
        assert "Invalid format type" in error_str

    def test_get_fulltext_content_http_404_error(self):
        """Test get fulltext content with 404 HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.HTTPError("Not Found")
        http_error.response = mock_response

        with patch.object(self.client, "_get", side_effect=http_error):
            with pytest.raises(FullTextError) as exc_info:
                self.client.get_fulltext_content("123456", "xml")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL003

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL003]" in error_str
            assert "Content not found for PMC ID 123456" in error_str

    def test_get_fulltext_content_http_403_error(self):
        """Test get fulltext content with 403 HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 403
        http_error = requests.HTTPError("Forbidden")
        http_error.response = mock_response

        with patch.object(self.client, "_get", side_effect=http_error):
            with pytest.raises(FullTextError) as exc_info:
                self.client.get_fulltext_content("123456", "xml")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL008

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL008]" in error_str
            assert "Access denied for content" in error_str

    def test_get_fulltext_content_http_500_error(self):
        """Test get fulltext content with 500 HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.HTTPError("Server Error")
        http_error.response = mock_response

        with patch.object(self.client, "_get", side_effect=http_error):
            with pytest.raises(FullTextError) as exc_info:
                self.client.get_fulltext_content("123456", "xml")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL005

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL005]" in error_str
            assert "Download failed or content corrupted" in error_str

    def test_get_fulltext_content_network_error(self):
        """Test get fulltext content with network error."""
        with patch.object(
            self.client, "_get", side_effect=requests.RequestException("Network error")
        ):
            with pytest.raises(FullTextError) as exc_info:
                self.client.get_fulltext_content("123456", "xml")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL005

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL005]" in error_str
            assert "Download failed or content corrupted" in error_str

    def test_download_fulltext_batch_invalid_format(self):
        """Test batch download with invalid format and skip_errors=False."""
        with pytest.raises(FullTextError) as exc_info:
            self.client.download_fulltext_batch(
                ["123456"], format_type="invalid", skip_errors=False
            )

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL010

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL010]" in error_str
        assert "Unsupported format for batch download" in error_str

    def test_download_fulltext_batch_skip_errors_false(self):
        """Test batch download with skip_errors=False and error occurs."""
        with patch.object(
            self.client, "download_pdf_by_pmcid", side_effect=FullTextError(ErrorCodes.FULL005)
        ):
            with pytest.raises(FullTextError) as exc_info:
                self.client.download_fulltext_batch(
                    ["123456"], format_type="pdf", skip_errors=False
                )

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL005

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL005]" in error_str
            assert "Download failed or content corrupted" in error_str

    def test_download_xml_by_pmcid_bulk_success(self):
        """Test successful bulk XML download via dedicated method."""
        with patch.object(self.client, "_try_bulk_xml_download", return_value=True):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.xml"
                result = self.client.download_xml_by_pmcid_bulk("123456", output_path)
                assert result == output_path

    def test_download_xml_by_pmcid_bulk_failure(self):
        """Test bulk XML download failure via dedicated method."""
        with patch.object(self.client, "_try_bulk_xml_download", return_value=False):
            with pytest.raises(FullTextError) as exc_info:
                self.client.download_xml_by_pmcid_bulk("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL003

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL003]" in error_str
            assert "Content not found for PMC ID 123456" in error_str

    def test_get_html_article_url_with_medid(self):
        """Test HTML article URL generation with MED ID."""
        url = self.client.get_html_article_url("123456", medid="987654")
        expected = "https://europepmc.org/article/MED/987654#free-full-text"
        assert url == expected

    def test_get_html_article_url_without_medid(self):
        """Test HTML article URL generation without MED ID."""
        url = self.client.get_html_article_url("123456")
        expected = "https://europepmc.org/article/PMC/123456#free-full-text"
        assert url == expected

    def test_download_xml_io_error(self):
        """Test XML download with IO error during file write."""
        mock_response = Mock()
        mock_response.text = "<xml>content</xml>"

        # Mock atomic_write to raise IOError - need to patch the context manager
        def mock_atomic_write(*args, **kwargs):
            raise IOError("File write error")

        with (
            patch.object(self.client, "_get", return_value=mock_response),
            patch("pyeuropepmc.fulltext.atomic_write", side_effect=mock_atomic_write),
        ):
            with pytest.raises(FullTextError) as exc_info:
                self.client.download_xml_by_pmcid("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL009

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL009]" in error_str
            assert "File operation failed" in error_str

    def test_download_xml_api_fallback_to_bulk_success(self):
        """Test XML download falling back to bulk download after API failure."""
        # Mock API failure followed by successful bulk download
        with (
            patch.object(self.client, "_get", side_effect=APIClientError(ErrorCodes.HTTP404)),
            patch.object(self.client, "_try_bulk_xml_download", return_value=True),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.xml"
                result = self.client.download_xml_by_pmcid("123456", output_path)
                assert result == output_path

    def test_download_xml_api_403_fallback_to_bulk_success(self):
        """Test XML download falling back to bulk download after 403 error."""
        # Mock 403 error followed by successful bulk download
        with (
            patch.object(self.client, "_get", side_effect=APIClientError(ErrorCodes.HTTP403)),
            patch.object(self.client, "_try_bulk_xml_download", return_value=True),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.xml"
                result = self.client.download_xml_by_pmcid("123456", output_path)
                assert result == output_path

    def test_download_xml_api_other_error_fallback_to_bulk_success(self):
        """Test XML download falling back to bulk download after other API error."""
        # Mock other API error followed by successful bulk download
        with (
            patch.object(self.client, "_get", side_effect=APIClientError(ErrorCodes.HTTP500)),
            patch.object(self.client, "_try_bulk_xml_download", return_value=True),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.xml"
                result = self.client.download_xml_by_pmcid("123456", output_path)
                assert result == output_path

    def test_download_xml_network_error_fallback_to_bulk_success(self):
        """Test XML download falling back to bulk download after network error."""
        # Mock network error followed by successful bulk download
        with (
            patch.object(
                self.client, "_get", side_effect=requests.RequestException("Network error")
            ),
            patch.object(self.client, "_try_bulk_xml_download", return_value=True),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "test.xml"
                result = self.client.download_xml_by_pmcid("123456", output_path)
                assert result == output_path

    def test_check_availability_request_exceptions(self):
        """Test availability check with RequestException for each format type."""
        # Test XML request exception
        with patch.object(
            self.client.session, "head", side_effect=requests.RequestException("XML error")
        ):
            availability = self.client.check_fulltext_availability("123456")
            assert availability["xml"] is False

        # Test PDF request exception
        def mock_head_pdf_error(*args, **kwargs):
            if "fullTextXML" in args[0]:
                return Mock(status_code=200)
            else:
                raise requests.RequestException("PDF error")

        with (
            patch.object(self.client.session, "head", side_effect=mock_head_pdf_error),
            patch.object(self.client.session, "get") as mock_get,
        ):
            mock_get.return_value.status_code = 200
            availability = self.client.check_fulltext_availability("123456")
            assert availability["pdf"] is False
            assert availability["xml"] is True
            assert availability["html"] is True

        # Test HTML request exception
        def mock_requests_html_error(*args, **kwargs):
            if "fullTextXML" in args[0]:
                mock_resp = Mock()
                mock_resp.status_code = 200
                return mock_resp
            else:  # PDF check
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.headers = {"content-type": "application/pdf"}
                return mock_resp

        with (
            patch.object(self.client.session, "head", side_effect=mock_requests_html_error),
            patch.object(
                self.client.session, "get", side_effect=requests.RequestException("HTML error")
            ),
        ):
            availability = self.client.check_fulltext_availability("123456")
            assert availability["html"] is False
            assert availability["xml"] is True
            assert availability["pdf"] is True

    def test_download_pdf_by_pmcid_default_output_path(self):
        """Test PDF download with default output path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change working directory to temp dir
            import os

            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # Mock _try_pdf_endpoint to actually create the file and return True
                def mock_try_pdf(*args, **kwargs):
                    # Create the file that would be created
                    output_path = args[1] if len(args) > 1 else kwargs.get("output_path")
                    if output_path:
                        Path(output_path).touch()
                    return True

                with patch.object(self.client, "_try_pdf_endpoint", side_effect=mock_try_pdf):
                    result = self.client.download_pdf_by_pmcid("123456")
                    expected_path = Path(temp_dir) / "PMC123456.pdf"

                    # Ensure result is not None
                    assert result is not None
                    # Convert both to absolute paths for comparison
                    assert result.resolve() == expected_path.resolve()
                    assert result.exists()
            finally:
                os.chdir(original_cwd)

    def test_download_xml_bulk_download_fallback_failure(self):
        """Test XML download API failure followed by bulk download failure."""
        with (
            patch.object(self.client, "_get", side_effect=APIClientError(ErrorCodes.HTTP403)),
            patch.object(self.client, "_try_bulk_xml_download", return_value=False),
        ):
            with pytest.raises(FullTextError) as exc_info:
                self.client.download_xml_by_pmcid("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL003

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL003]" in error_str

    def test_download_xml_other_api_error_bulk_failure(self):
        """Test XML download with other API error and bulk download failure."""
        with (
            patch.object(self.client, "_get", side_effect=APIClientError(ErrorCodes.HTTP500)),
            patch.object(self.client, "_try_bulk_xml_download", return_value=False),
        ):
            with pytest.raises(FullTextError) as exc_info:
                self.client.download_xml_by_pmcid("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL003

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL003]" in error_str

    def test_download_xml_network_error_bulk_failure(self):
        """Test XML download with network error and bulk download failure."""
        with (
            patch.object(
                self.client, "_get", side_effect=requests.RequestException("Network error")
            ),
            patch.object(self.client, "_try_bulk_xml_download", return_value=False),
        ):
            with pytest.raises(FullTextError) as exc_info:
                self.client.download_xml_by_pmcid("123456")

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL003

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL003]" in error_str

    def test_validate_pdf_content_small_file_under_1kb(self):
        """Test PDF validation with file under 1KB."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            # Write valid PDF header but keep file small
            temp_file.write(b"%PDF-1.4\n" + b"x" * 500)  # Less than 1KB
            temp_path = Path(temp_file.name)

        try:
            result = self.client._validate_pdf_content(temp_path)
            assert result is False
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validate_pdf_content_success_large_file(self):
        """Test PDF validation with large valid file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            # Write valid PDF header with large content
            temp_file.write(b"%PDF-1.4\n" + b"x" * 2000)  # Over 1KB
            temp_path = Path(temp_file.name)

        try:
            result = self.client._validate_pdf_content(temp_path)
            assert result is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_try_bulk_xml_download_value_error(self):
        """Test bulk XML download with ValueError during processing."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b"valid content"]
            mock_get.return_value = mock_response

            # Mock int() to raise ValueError
            with patch("builtins.int", side_effect=ValueError("Invalid integer")):
                result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
                assert result is False

    def test_try_bulk_xml_download_final_return_false(self):
        """Test bulk XML download reaching final return False."""
        # This tests the final return False line that's not covered
        with patch.object(self.client, "_determine_bulk_archive_range", return_value=(0, 999)):
            with patch("requests.get") as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.iter_content.return_value = [b"valid content"]
                mock_get.return_value = mock_response

                # Mock gzip.open to not find the PMC ID
                xml_content = "<article><article-meta>PMC999999</article-meta></article>"

                with patch("gzip.open") as mock_gzip:
                    mock_gzip.return_value.__enter__.return_value.read.return_value = xml_content

                    result = self.client._try_bulk_xml_download("123456", Path("/tmp/test.xml"))
                    assert result is False

    def test_progress_info_initialization(self):
        """Test ProgressInfo initialization with all parameters."""
        from pyeuropepmc.fulltext import ProgressInfo
        import time

        start_time = time.time()
        progress = ProgressInfo(
            total_items=100,
            current_item=25,
            current_pmcid="123456",
            status="downloading",
            successful_downloads=20,
            failed_downloads=3,
            cache_hits=2,
            format_type="pdf",
            start_time=start_time,
            current_file_size=1024,
            total_downloaded_bytes=50000
        )

        assert progress.total_items == 100
        assert progress.current_item == 25
        assert progress.current_pmcid == "123456"
        assert progress.status == "downloading"

    def test_progress_info_default_initialization(self):
        """Test ProgressInfo initialization with minimal parameters."""
        from pyeuropepmc.fulltext import ProgressInfo

        progress = ProgressInfo(total_items=50)

        assert progress.total_items == 50
        assert progress.current_item == 0
        assert progress.current_pmcid is None
        assert progress.status == "starting"

    def test_progress_percent_calculation(self):
        """Test progress percentage calculation."""
        from pyeuropepmc.fulltext import ProgressInfo

        progress = ProgressInfo(total_items=100, current_item=25)
        assert progress.progress_percent == 25.0

        progress = ProgressInfo(total_items=0, current_item=5)
        assert progress.progress_percent == 0.0

    def test_estimated_times_calculation(self):
        """Test estimated time calculations."""
        from pyeuropepmc.fulltext import ProgressInfo
        import time

        start_time = time.time() - 10  # 10 seconds ago
        progress = ProgressInfo(total_items=100, current_item=25, start_time=start_time)

        # Should have estimates when progress > 0
        assert progress.estimated_total_time is not None
        assert progress.estimated_remaining_time is not None

        # No estimates when no progress
        progress_no_work = ProgressInfo(total_items=100, current_item=0, start_time=start_time)
        assert progress_no_work.estimated_total_time is None
        assert progress_no_work.estimated_remaining_time is None

    def test_completion_rate_calculation(self):
        """Test completion rate calculation."""
        from pyeuropepmc.fulltext import ProgressInfo
        from unittest.mock import patch
        import time

        # Test with actual elapsed time
        start_time = time.time() - 10  # 10 seconds ago
        progress = ProgressInfo(total_items=100, current_item=25, start_time=start_time)

        rate = progress.completion_rate
        # Rate should be approximately 2.5 items/second (25 items in ~10 seconds)
        # Allow some tolerance for timing variations
        assert 2.0 < rate < 4.0

        # Test zero elapsed time by mocking time.time to return start_time
        with patch('time.time') as mock_time:
            fixed_time = 1000.0
            mock_time.return_value = fixed_time
            progress_new = ProgressInfo(total_items=100, current_item=25, start_time=fixed_time)
            assert progress_new.completion_rate == 0.0

    def test_progress_to_dict_conversion(self):
        """Test conversion to dictionary."""
        from pyeuropepmc.fulltext import ProgressInfo

        progress = ProgressInfo(
            total_items=100,
            current_item=25,
            current_pmcid="123456",
            status="downloading"
        )

        result_dict = progress.to_dict()

        required_keys = [
            "total_items", "current_item", "current_pmcid", "status",
            "progress_percent", "successful_downloads", "failed_downloads",
            "cache_hits", "format_type", "elapsed_time", "estimated_remaining_time",
            "completion_rate", "current_file_size", "total_downloaded_bytes"
        ]

        assert all(key in result_dict for key in required_keys)
        assert result_dict["total_items"] == 100

    def test_progress_string_representation(self):
        """Test string representation."""
        from pyeuropepmc.fulltext import ProgressInfo

        progress = ProgressInfo(
            total_items=100,
            current_item=25,
            current_pmcid="123456",
            status="downloading"
        )

        string_repr = str(progress)
        assert "25/100" in string_repr
        assert "25.0%" in string_repr
        assert "PMC123456" in string_repr
        assert "downloading" in string_repr

    def test_fulltext_client_cache_initialization_variations(self):
        """Test FullTextClient cache initialization with different settings."""
        # Test with custom cache directory
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "custom_cache"

            client = FullTextClient(
                enable_cache=True,
                cache_dir=cache_dir,
                cache_max_age_days=7,
                verify_cached_files=False
            )

            assert client.enable_cache is True
            assert client.cache_dir == cache_dir
            assert client.cache_max_age_days == 7
            assert client.verify_cached_files is False
            assert cache_dir.exists()

            client.close()

        # Test with cache disabled
        client = FullTextClient(enable_cache=False)
        assert client.enable_cache is False
        assert client.cache_dir is None
        client.close()

        # Test with default cache directory
        client = FullTextClient(enable_cache=True, cache_dir=None)
        assert client.enable_cache is True
        assert client.cache_dir is not None
        assert "pyeuropepmc_cache" in str(client.cache_dir)
        client.close()

    def test_cache_path_operations(self):
        """Test cache path operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FullTextClient(enable_cache=True, cache_dir=temp_dir)

            # Test get_cache_path
            cache_path = client._get_cache_path("123456", "pdf")
            assert cache_path is not None
            assert cache_path.name == "PMC123456.pdf"
            assert "pdf" in str(cache_path.parent)

            client.close()

        # Test with cache disabled
        client = FullTextClient(enable_cache=False)
        cache_path = client._get_cache_path("123456", "pdf")
        assert cache_path is None
        client.close()

    def test_cached_file_validation_edge_cases(self):
        """Test cached file validation edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FullTextClient(enable_cache=True, cache_dir=temp_dir)

            # Nonexistent file
            nonexistent_path = Path(temp_dir) / "nonexistent.pdf"
            assert not client._is_cached_file_valid(nonexistent_path)

            # Empty file
            empty_file = Path(temp_dir) / "empty.pdf"
            empty_file.touch()
            assert not client._is_cached_file_valid(empty_file)

            # Stale file
            client.cache_max_age_days = 1
            stale_file = Path(temp_dir) / "stale.pdf"
            stale_file.write_bytes(b"content")

            # Make file old
            import time, os
            old_time = time.time() - (2 * 24 * 3600)  # 2 days ago
            os.utime(stale_file, (old_time, old_time))
            assert not client._is_cached_file_valid(stale_file)

            client.close()

    def test_file_format_verification(self):
        """Test file format verification for different types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FullTextClient(enable_cache=True, cache_dir=temp_dir)

            # Valid PDF
            pdf_file = Path(temp_dir) / "valid.pdf"
            pdf_file.write_bytes(b"%PDF-1.4\nrest of pdf content")
            assert client._verify_file_format(pdf_file)

            # Invalid PDF
            invalid_pdf = Path(temp_dir) / "invalid.pdf"
            invalid_pdf.write_bytes(b"Not a PDF file")
            assert not client._verify_file_format(invalid_pdf)

            # Valid XML
            xml_file = Path(temp_dir) / "valid.xml"
            xml_file.write_bytes(b"<?xml version='1.0'?><root></root>")
            assert client._verify_file_format(xml_file)

            # XML with BOM
            xml_bom = Path(temp_dir) / "bom.xml"
            xml_bom.write_bytes(b"\xef\xbb\xbf<root></root>")
            assert client._verify_file_format(xml_bom)

            # Valid HTML
            html_file = Path(temp_dir) / "valid.html"
            html_file.write_text("<!DOCTYPE html><html><body><p>Content</p></body></html>")
            assert client._verify_file_format(html_file)

            # Minimal HTML
            minimal_html = Path(temp_dir) / "minimal.html"
            minimal_html.write_text("<div>Some content</div>")
            assert client._verify_file_format(minimal_html)

            # Unknown extension (should return True)
            unknown_file = Path(temp_dir) / "unknown.xyz"
            unknown_file.write_bytes(b"Unknown content")
            assert client._verify_file_format(unknown_file)

            client.close()

    def test_cache_file_operations(self):
        """Test cache file check and save operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FullTextClient(enable_cache=True, cache_dir=temp_dir)

            # Test cache disabled scenario
            client_no_cache = FullTextClient(enable_cache=False)
            result = client_no_cache._check_cache_for_file("123456", "pdf")
            assert result is None
            client_no_cache.close()

            # Test with valid cache file
            cache_path = client._get_cache_path("123456", "pdf")
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(b"%PDF-1.4\nPDF content")

                result = client._check_cache_for_file("123456", "pdf")
                assert result == cache_path

                # Test with output path
                output_path = Path(temp_dir) / "output" / "document.pdf"
                result = client._check_cache_for_file("123456", "pdf", output_path)
                assert result == output_path
                assert output_path.exists()

            client.close()

    def test_url_generation_methods(self):
        """Test URL generation methods."""
        # Test fulltext URL generation (existing method)
        xml_url = self.client._get_fulltext_url("123456", "xml")
        expected_xml = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML"
        assert xml_url == expected_xml

        # Test HTML article URL (existing method)
        html_url_with_med = self.client.get_html_article_url("123456", "789012")
        assert "MED/789012" in html_url_with_med

        html_url_without_med = self.client.get_html_article_url("123456")
        assert "PMC/123456" in html_url_without_med
