"""
Unit tests for FullTextClient functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.fulltext import FullTextClient, FullTextError

pytestmark = pytest.mark.unit


class TestFullTextClient:
    """Test suite for FullTextClient class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.client = FullTextClient()

    def teardown_method(self):
        """Clean up after each test method."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    def _create_test_pdf_content(self) -> bytes:
        """Create valid PDF content for testing."""
        pdf_header = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        return pdf_header + b"x" * 1000

    @pytest.mark.unit
    def test_client_initialization(self):
        """Test FullTextClient initialization."""
        client = FullTextClient(rate_limit_delay=2.0)
        assert client.rate_limit_delay == 2.0
        assert not client.is_closed
        client.close()

    @pytest.mark.unit
    def test_client_context_manager(self):
        """Test FullTextClient as context manager."""
        with FullTextClient() as client:
            assert not client.is_closed
        assert client.is_closed

    @pytest.mark.unit
    def test_client_repr(self):
        """Test string representation of FullTextClient."""
        repr_str = repr(self.client)
        assert "FullTextClient" in repr_str
        assert "rate_limit_delay" in repr_str
        assert "status" in repr_str

    @pytest.mark.unit
    def test_validate_pmcid_valid(self):
        """Test PMC ID validation with valid inputs."""
        # Test numeric PMC ID
        assert self.client._validate_pmcid("123456") == "123456"

        # Test with PMC prefix
        assert self.client._validate_pmcid("PMC123456") == "123456"
        assert self.client._validate_pmcid("pmc123456") == "123456"

        # Test with whitespace
        assert self.client._validate_pmcid("  PMC123456  ") == "123456"

    @pytest.mark.unit
    def test_validate_pmcid_invalid(self):
        """Test PMC ID validation with invalid inputs."""
        with pytest.raises(FullTextError) as exc_info:
            self.client._validate_pmcid("")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL001]" in error_str
        assert "PMC ID cannot be empty" in error_str

        with pytest.raises(FullTextError) as exc_info:
            self.client._validate_pmcid(None)  # type: ignore

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL001

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL001]" in error_str
        assert "PMC ID cannot be empty" in error_str

        with pytest.raises(FullTextError) as exc_info:
            self.client._validate_pmcid("PMCabc123")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL002

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL002]" in error_str
        assert "Invalid PMC ID format" in error_str

        with pytest.raises(FullTextError) as exc_info:
            self.client._validate_pmcid("invalid")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL002

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL002]" in error_str
        assert "Invalid PMC ID format" in error_str

    @pytest.mark.unit
    def test_get_fulltext_url_xml(self):
        """Test URL construction for XML content only."""
        base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
        xml_url = self.client._get_fulltext_url("123456", "xml")
        assert xml_url == f"{base_url}PMC123456/fullTextXML"

    @pytest.mark.unit
    def test_get_fulltext_url_unsupported_formats(self):
        """Test URL construction with unsupported formats (PDF, HTML)."""
        with pytest.raises(FullTextError) as exc_info:
            self.client._get_fulltext_url("123456", "pdf")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL011

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL011]" in error_str
        assert "URL construction not supported" in error_str

        with pytest.raises(FullTextError) as exc_info:
            self.client._get_fulltext_url("123456", "html")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.FULL011

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[FULL011]" in error_str
        assert "URL construction not supported" in error_str

    @pytest.mark.unit
    def test_get_fulltext_url_invalid_format(self):
        """Test URL construction with completely invalid format."""
        with pytest.raises(
            FullTextError, match="URL construction not supported for format 'invalid'"
        ):
            self.client._get_fulltext_url("123456", "invalid")

    @pytest.mark.unit
    def test_check_fulltext_availability_success(self):
        """Test checking full text availability when XML and PDF are available."""

        # Mock successful HEAD requests for XML (REST API) and PDF (render endpoint)
        def mock_request(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if "pdf=render" in url:
                # PDF endpoint needs proper content-type header
                mock_response.headers = {"content-type": "application/pdf"}
            else:
                mock_response.headers = {}
            return mock_response

        with patch.object(self.client.session, "head", side_effect=mock_request):
            with patch.object(self.client.session, "get", side_effect=mock_request):
                availability = self.client.check_fulltext_availability("123456")

        # XML, PDF, and HTML should all be available with mocked 200 responses
        expected = {"pdf": True, "xml": True, "html": True}
        assert availability == expected

    @pytest.mark.unit
    def test_check_fulltext_availability_partial(self):
        """Test checking full text availability when only XML is available."""

        def mock_head(url, **kwargs):
            mock_response = Mock()
            if "fullTextXML" in url:
                mock_response.status_code = 200  # XML available via REST API
                mock_response.headers = {}
            elif "pdf=render" in url:
                mock_response.status_code = 404  # PDF not available via render endpoint
                mock_response.headers = {}
            else:
                mock_response.status_code = 404
                mock_response.headers = {}
            return mock_response

        def mock_get(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 404  # HTML not available
            return mock_response

        with patch.object(self.client.session, "head", side_effect=mock_head):
            with patch.object(self.client.session, "get", side_effect=mock_get):
                availability = self.client.check_fulltext_availability("123456")

        expected = {"pdf": False, "xml": True, "html": False}
        assert availability == expected

    @pytest.mark.unit
    def test_check_fulltext_availability_none_available(self):
        """Test checking full text availability when neither XML nor PDF are available."""

        def mock_head(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 404  # Nothing available
            mock_response.headers = {}
            return mock_response

        def mock_get(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 404  # HTML not available
            return mock_response

        with patch.object(self.client.session, "head", side_effect=mock_head):
            with patch.object(self.client.session, "get", side_effect=mock_get):
                availability = self.client.check_fulltext_availability("123456")

        expected = {"pdf": False, "xml": False, "html": False}
        assert availability == expected

    @pytest.mark.unit
    @patch("requests.get")
    def test_download_pdf_by_pmcid_render_success(self, mock_get):
        """Test PDF download via ?pdf=render endpoint (success)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        # Create valid PDF content with proper header
        pdf_content = self._create_test_pdf_content()
        mock_response.iter_content.return_value = [pdf_content]
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC123456.pdf"
            client = FullTextClient()
            result = client.download_pdf_by_pmcid("123456", output_path)
            assert result == output_path
            assert output_path.exists()
            with open(output_path, "rb") as f:
                content = f.read()
                assert content.startswith(b"%PDF")
                assert len(content) > 1000
            client.close()

    @pytest.mark.unit
    @patch("requests.get")
    def test_download_pdf_by_pmcid_backend_success(self, mock_get):
        """Test PDF download via backend render service (fallback success)."""
        # First call: render endpoint fails
        mock_response_render = Mock()
        mock_response_render.status_code = 404

        # Second call: backend endpoint succeeds
        mock_response_backend = Mock()
        mock_response_backend.status_code = 200
        mock_response_backend.headers = {"content-type": "application/pdf"}
        # Create valid PDF content with proper header
        pdf_content = self._create_test_pdf_content()
        mock_response_backend.iter_content.return_value = [pdf_content]

        mock_get.side_effect = [mock_response_render, mock_response_backend]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC123456.pdf"
            client = FullTextClient()
            result = client.download_pdf_by_pmcid("123456", output_path)
            assert result == output_path
            assert output_path.exists()
            with open(output_path, "rb") as f:
                content = f.read()
                assert content.startswith(b"%PDF")
                assert len(content) > 1000
            client.close()

    @pytest.mark.unit
    @patch("requests.get")
    def test_download_pdf_by_pmcid_zip_success(self, mock_get):
        """Test PDF download via OA ZIP fallback (success)."""
        import zipfile
        from io import BytesIO

        # First call: render endpoint fails
        mock_response_render = Mock()
        mock_response_render.status_code = 404

        # Second call: backend endpoint fails
        mock_response_backend = Mock()
        mock_response_backend.status_code = 404

        # Third call: ZIP endpoint returns a zip with a PDF
        # Create valid PDF content with proper header
        pdf_bytes = self._create_test_pdf_content()
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("PMC123456.pdf", pdf_bytes)
        zip_buffer.seek(0)
        mock_response_zip = Mock()
        mock_response_zip.status_code = 200
        mock_response_zip.content = zip_buffer.read()

        mock_get.side_effect = [mock_response_render, mock_response_backend, mock_response_zip]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC123456.pdf"
            client = FullTextClient()
            result = client.download_pdf_by_pmcid("123456", output_path)
            assert result == output_path
            assert output_path.exists()
            with open(output_path, "rb") as f:
                assert f.read() == pdf_bytes
            client.close()

    @pytest.mark.unit
    @patch("requests.get")
    def test_download_pdf_by_pmcid_all_fail(self, mock_get):
        """Test PDF download returns None if all endpoints fail."""
        # All endpoints return 404
        mock_response_fail = Mock()
        mock_response_fail.status_code = 404
        mock_get.return_value = mock_response_fail

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC99999999.pdf"
            client = FullTextClient()
            result = client.download_pdf_by_pmcid("99999999", output_path)
            assert result is None
            assert not output_path.exists()
            client.close()

    @pytest.mark.unit
    def test_download_pdf_by_pmcid_invalid(self):
        """Test PDF download raises FullTextError for invalid PMCIDs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMCbadid.pdf"
            client = FullTextClient()
            with pytest.raises(FullTextError) as exc_info:
                client.download_pdf_by_pmcid("badid", output_path)

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL002

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL002]" in error_str
            assert "Invalid PMC ID format" in error_str

            client.close()

    @pytest.mark.unit
    @patch("requests.get")
    @patch("gzip.open")
    @patch("tempfile.NamedTemporaryFile")
    def test_bulk_xml_download_success(self, mock_tempfile, mock_gzip_open, mock_requests_get):
        """Test successful bulk XML download from FTP archives."""
        # Mock successful archive download
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests_get.return_value = mock_response

        # Mock temporary file
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test_archive.gz"
        mock_tempfile.return_value.__enter__.return_value = mock_temp_file

        # Mock gzip file content with XML containing our PMC ID
        xml_content = """<?xml version="1.0"?>
        <article>
            <article-meta>
                <article-id pub-id-type="pmc">PMC3257301</article-id>
                <title>Test Article</title>
            </article-meta>
            <body>
                <p>Test content</p>
            </body>
        </article>"""

        mock_gzip_file = Mock()
        mock_gzip_file.read.return_value = xml_content
        mock_gzip_open.return_value.__enter__.return_value = mock_gzip_file

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"

            result = self.client._try_bulk_xml_download("3257301", output_path)

            assert result is True
            assert output_path.exists()
            assert "PMC3257301" in output_path.read_text()

    @pytest.mark.unit
    @patch("requests.get")
    def test_bulk_xml_download_archive_not_found(self, mock_requests_get):
        """Test bulk XML download when archive is not found."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"

            result = self.client._try_bulk_xml_download("3257301", output_path)

            assert result is False
            assert not output_path.exists()

    @pytest.mark.unit
    @patch("requests.get")
    @patch("gzip.open")
    @patch("tempfile.NamedTemporaryFile")
    def test_bulk_xml_download_pmcid_not_in_archive(
        self, mock_tempfile, mock_gzip_open, mock_requests_get
    ):
        """Test bulk XML download when PMC ID is not found in archive."""
        # Mock successful archive download
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"chunk1"]
        mock_requests_get.return_value = mock_response

        # Mock temporary file
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test_archive.gz"
        mock_tempfile.return_value.__enter__.return_value = mock_temp_file

        # Mock gzip file content WITHOUT our PMC ID
        xml_content = """<?xml version="1.0"?>
        <article>
            <article-meta>
                <article-id pub-id-type="pmc">PMC9999999</article-id>
                <title>Different Article</title>
            </article-meta>
        </article>"""

        mock_gzip_file = Mock()
        mock_gzip_file.read.return_value = xml_content
        mock_gzip_open.return_value.__enter__.return_value = mock_gzip_file

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"

            result = self.client._try_bulk_xml_download("3257301", output_path)

            assert result is False
            assert not output_path.exists()

    @pytest.mark.unit
    def test_determine_bulk_archive_range(self):
        """Test determination of archive ranges for different PMC IDs."""
        # Test PMC IDs >= 1M (100k ranges)
        assert self.client._determine_bulk_archive_range(1234567) == (1200000, 1299999)

        # Test PMC IDs 100k-1M (100k ranges)
        assert self.client._determine_bulk_archive_range(345678) == (300000, 399999)

        # Test PMC IDs 10k-100k (10k ranges)
        assert self.client._determine_bulk_archive_range(23456) == (20000, 29999)

        # Test PMC IDs < 10k (1k ranges)
        assert self.client._determine_bulk_archive_range(2345) == (2000, 2999)
        assert self.client._determine_bulk_archive_range(345) == (0, 999)

    @pytest.mark.unit
    @patch("pyeuropepmc.fulltext.FullTextClient._try_bulk_xml_download")
    def test_download_xml_by_pmcid_bulk_success(self, mock_bulk_download):
        """Test dedicated bulk-only XML download method success."""
        mock_bulk_download.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"
            # Create the file since the mock doesn't actually create it
            output_path.write_text("mock xml content")

            result = self.client.download_xml_by_pmcid_bulk("3257301", output_path)

            assert result == output_path
            mock_bulk_download.assert_called_once_with("3257301", output_path)

    @pytest.mark.unit
    @patch("pyeuropepmc.fulltext.FullTextClient._try_bulk_xml_download")
    def test_download_xml_by_pmcid_bulk_failure(self, mock_bulk_download):
        """Test dedicated bulk-only XML download method failure."""
        mock_bulk_download.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"

            with pytest.raises(FullTextError) as exc_info:
                self.client.download_xml_by_pmcid_bulk("3257301", output_path)

            # Check that the exception has the correct error code
            assert exc_info.value.error_code == ErrorCodes.FULL003

            # Check that the error message contains the expected content
            error_str = str(exc_info.value)
            assert "[FULL003]" in error_str
            assert "Content not found" in error_str

    @pytest.mark.unit
    @patch("pyeuropepmc.fulltext.FullTextClient._try_bulk_xml_download")
    @patch("pyeuropepmc.fulltext.FullTextClient._try_xml_rest_api")
    def test_download_xml_by_pmcid_fallback_to_bulk(self, mock_rest_api, mock_bulk_download):
        """Test XML download falls back to bulk when REST API fails."""

        # Disable caching for this test
        original_cache_setting = self.client.enable_cache
        self.client.enable_cache = False

        try:
            # Mock REST API failure
            mock_rest_api.return_value = False

            # Mock successful bulk download
            mock_bulk_download.return_value = True

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / "PMC3257301.xml"
                # Create the file since the mock doesn't actually create it
                output_path.write_text("mock xml content from bulk")

                result = self.client.download_xml_by_pmcid("3257301", output_path)

                assert result == output_path
                mock_bulk_download.assert_called_once_with("3257301", output_path)
        finally:
            # Restore original cache setting
            self.client.enable_cache = original_cache_setting
