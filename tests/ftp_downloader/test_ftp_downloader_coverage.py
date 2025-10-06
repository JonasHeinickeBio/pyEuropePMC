"""
Additional unit tests for FTP downloader to increase coverage.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import requests
import zipfile
import tempfile

from pyeuropepmc.ftp_downloader import FTPDownloader
from pyeuropepmc.exceptions import FullTextError
from pyeuropepmc.error_codes import ErrorCodes


class TestFTPDownloaderCoverage:
    """Additional test cases to increase FTP downloader coverage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.downloader = FTPDownloader(rate_limit_delay=0.1)

    def test_get_ftp_url_session_none(self):
        """Test _get_ftp_url when session is None."""
        # Mock session to be None
        with patch.object(self.downloader, 'session', None):
            with pytest.raises(FullTextError) as exc_info:
                self.downloader._get_ftp_url("http://example.com")

            assert exc_info.value.error_code == ErrorCodes.FULL005
            # Check context contains the expected error
            assert self.downloader.session is None
            assert exc_info.value.context["error"] == "Session is None"

    def test_get_ftp_url_request_exception(self):
        """Test _get_ftp_url with request exception."""
        with patch.object(self.downloader, 'session') as mock_session:
            mock_session.get.side_effect = requests.RequestException("Network error")

            with pytest.raises(FullTextError) as exc_info:
                self.downloader._get_ftp_url("http://example.com")

            assert exc_info.value.error_code == ErrorCodes.FULL005
            # Check the context contains the expected error
            assert exc_info.value.context["error"] == "Network error"

    def test_get_ftp_url_success_with_stream(self):
        """Test _get_ftp_url successful request with streaming."""
        with patch.object(self.downloader, 'session') as mock_session:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_session.get.return_value = mock_response

            result = self.downloader._get_ftp_url("http://example.com", stream=True)

            assert result == mock_response
            mock_session.get.assert_called_once_with(
                "http://example.com",
            timeout=self.downloader.DEFAULT_TIMEOUT,
            stream=True
        )

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_empty_response(self, mock_get_ftp_url):
        """Test get_available_directories with empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body></body></html>"
        mock_get_ftp_url.return_value = mock_response

        directories = self.downloader.get_available_directories()
        assert directories == []

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_none_response(self, mock_get_ftp_url):
        """Test get_available_directories with None response."""
        mock_get_ftp_url.return_value = None

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_bad_status_code(self, mock_get_ftp_url):
        """Test get_available_directories with bad status code."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get_ftp_url.return_value = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_exception(self, mock_get_ftp_url):
        """Test get_available_directories with exception during parsing."""
        mock_get_ftp_url.side_effect = Exception("Parsing error")

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005
        assert exc_info.value.context["error"] == "Parsing error"

    def test_parse_file_size_empty_string(self):
        """Test _parse_file_size with empty string."""
        assert self.downloader._parse_file_size("") == 0
        assert self.downloader._parse_file_size("-") == 0
        assert self.downloader._parse_file_size("   ") == 0

    def test_parse_file_size_date_patterns(self):
        """Test _parse_file_size ignores date/time patterns."""
        assert self.downloader._parse_file_size("2024-01-15") == 0
        assert self.downloader._parse_file_size("12:34") == 0
        assert self.downloader._parse_file_size("2023") == 0

    def test_parse_file_size_valid_units(self):
        """Test _parse_file_size with valid units."""
        assert self.downloader._parse_file_size("289K") == 289 * 1024
        assert self.downloader._parse_file_size("2.5M") == int(2.5 * 1024 * 1024)
        assert self.downloader._parse_file_size("1G") == 1024 * 1024 * 1024
        assert self.downloader._parse_file_size("1T") == 1024 * 1024 * 1024 * 1024

    def test_parse_file_size_pure_numbers(self):
        """Test _parse_file_size with pure numbers."""
        assert self.downloader._parse_file_size("1000") == 1000
        assert self.downloader._parse_file_size("50000") == 50000
        assert self.downloader._parse_file_size("999999999") == 999999999

        # Too small or too large numbers should return 0
        assert self.downloader._parse_file_size("50") == 0  # Too small
        assert self.downloader._parse_file_size("9999999999") == 0  # Too large

    def test_parse_file_size_invalid_formats(self):
        """Test _parse_file_size with invalid formats."""
        assert self.downloader._parse_file_size("invalid") == 0
        assert self.downloader._parse_file_size("123X") == 0  # Invalid unit
        assert self.downloader._parse_file_size("abc123") == 0

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_zip_files_in_directory_complex_html_structure(self, mock_get_ftp_url):
        """Test get_zip_files_in_directory with complex HTML structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
        <table>
        <tr>
            <td><a href="PMC11691200.zip">PMC11691200.zip</a></td>
            <td>289K</td>
            <td>2024-01-15</td>
        </tr>
        <tr>
            <td></td>
            <td><a href="PMC11691201.zip">PMC11691201.zip</a></td>
            <td>456M</td>
        </tr>
        <tr>
            <td><a href="not_a_pmc.zip">not_a_pmc.zip</a></td>
            <td>100K</td>
        </tr>
        <tr>
            <td><a href="PMC11691202.txt">PMC11691202.txt</a></td>
            <td>50K</td>
        </tr>
        </table>
        </body>
        </html>
        '''
        mock_get_ftp_url.return_value = mock_response

        zip_files = self.downloader.get_zip_files_in_directory("PMCxxxx1200")

        assert len(zip_files) == 2
        assert zip_files[0]["filename"] == "PMC11691200.zip"
        assert zip_files[0]["pmcid"] == "11691200"
        assert zip_files[0]["size"] == 289 * 1024

        assert zip_files[1]["filename"] == "PMC11691201.zip"
        assert zip_files[1]["pmcid"] == "11691201"
        assert zip_files[1]["size"] == 456 * 1024 * 1024

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_zip_files_in_directory_no_size_info(self, mock_get_ftp_url):
        """Test get_zip_files_in_directory when size information is missing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
        <table>
        <tr>
            <td><a href="PMC11691200.zip">PMC11691200.zip</a></td>
            <td>-</td>
            <td></td>
        </tr>
        </table>
        </body>
        </html>
        '''
        mock_get_ftp_url.return_value = mock_response

        zip_files = self.downloader.get_zip_files_in_directory("PMCxxxx1200")

        assert len(zip_files) == 1
        assert zip_files[0]["size"] == 0  # No valid size found

    def test_get_relevant_directories_various_pmcid_lengths(self):
        """Test _get_relevant_directories with various PMC ID lengths."""
        # Test with short PMC IDs
        directories = self.downloader._get_relevant_directories(["123", "456"])
        assert "PMCxxxx123" in directories
        assert "PMCxxxx456" in directories

        # Test with 4-digit PMC IDs in range
        directories = self.downloader._get_relevant_directories(["1100", "1150"])
        assert "PMCxxxx1100" in directories
        assert "PMCxxxx1150" in directories
        assert "PMCxxxx100" in directories  # Last 3 digits
        assert "PMCxxxx150" in directories  # Last 3 digits

        # Test with 4-digit PMC IDs out of range
        directories = self.downloader._get_relevant_directories(["2000", "5000"])
        assert "PMCxxxx000" in directories  # Last 3 digits only

    def test_get_relevant_directories_invalid_pmcids(self):
        """Test _get_relevant_directories with invalid PMC IDs."""
        # Non-numeric PMC IDs should be handled gracefully
        directories = self.downloader._get_relevant_directories(["abc", "xyz"])
        # Should fall back to some default range
        assert len(directories) > 0

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.get_available_directories')
    def test_get_relevant_directories_fallback_to_available(self, mock_get_available):
        """Test _get_relevant_directories fallback to available directories."""
        mock_get_available.return_value = ["PMCxxxx1200", "PMCxxxx1201", "PMCxxxx1202"]

        # Empty PMC IDs list should trigger fallback
        directories = self.downloader._get_relevant_directories([])

        assert directories == set(["PMCxxxx1200", "PMCxxxx1201", "PMCxxxx1202"])
        mock_get_available.assert_called_once()

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.get_available_directories')
    def test_get_relevant_directories_fallback_to_range(self, mock_get_available):
        """Test _get_relevant_directories fallback to known range when API fails."""
        mock_get_available.side_effect = FullTextError(ErrorCodes.FULL005, {})

        directories = self.downloader._get_relevant_directories([])

        # Should create fallback range
        assert len(directories) > 1000  # Should include range 0-1200
        assert "PMCxxxx0" in directories
        assert "PMCxxxx1200" in directories

    def test_download_pdf_zip_invalid_zip_info_type(self):
        """Test download_pdf_zip with invalid zip_info type."""
        with pytest.raises(TypeError) as exc_info:
            # Type: ignore added for intentional type error testing
            self.downloader.download_pdf_zip("not_a_dict", "/tmp")  # type: ignore

        assert "zip_info must be a dictionary" in str(exc_info.value)

    def test_download_pdf_zip_missing_required_keys(self):
        """Test download_pdf_zip with missing required keys."""
        incomplete_zip_info: dict[str, str | int] = {"filename": "test.zip"}

        with pytest.raises(TypeError) as exc_info:
            self.downloader.download_pdf_zip(incomplete_zip_info, "/tmp")

        assert "missing required keys" in str(exc_info.value)

    def test_download_pdf_zip_invalid_key_types(self):
        """Test download_pdf_zip with invalid key types."""
        invalid_zip_info = {
            "filename": 123,  # Should be string
            "directory": "PMCxxxx1200",
            "pmcid": "123456",
            "size": 1000
        }

        with pytest.raises(TypeError) as exc_info:
            self.downloader.download_pdf_zip(invalid_zip_info, "/tmp")

        assert "filename must be string" in str(exc_info.value)

        invalid_zip_info = {
            "filename": "test.zip",
            "directory": 123,  # Should be string
            "pmcid": "123456",
            "size": 1000
        }

        with pytest.raises(TypeError) as exc_info:
            self.downloader.download_pdf_zip(invalid_zip_info, "/tmp")

        assert "directory must be string" in str(exc_info.value)

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_download_pdf_zip_download_failure(self, mock_get_ftp_url):
        """Test download_pdf_zip with download failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get_ftp_url.return_value = mock_response

        zip_info = {
            "filename": "PMC123456.zip",
            "directory": "PMCxxxx1200",
            "pmcid": "123456",
            "size": 1000
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(FullTextError) as exc_info:
                self.downloader.download_pdf_zip(zip_info, temp_dir)

            assert exc_info.value.error_code == ErrorCodes.FULL005

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_pdf_zip_success(self, mock_file, mock_get_ftp_url):
        """Test successful download_pdf_zip."""
        # Mock response with streaming content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'chunk1', b'chunk2', b'chunk3']
        mock_get_ftp_url.return_value = mock_response

        zip_info = {
            "filename": "PMC123456.zip",
            "directory": "PMCxxxx1200",
            "pmcid": "123456",
            "size": 1000
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = self.downloader.download_pdf_zip(zip_info, temp_dir)

            expected_path = Path(temp_dir) / "PMC123456.zip"
            assert result_path == expected_path

            # Verify file was opened for writing
            mock_file.assert_called_once()

            # Verify chunks were written
            handle = mock_file()
            assert handle.write.call_count == 3

    def test_extract_pdf_from_zip_success(self):
        """Test successful PDF extraction from ZIP."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file with PDF content
            zip_path = Path(temp_dir) / "test.zip"
            extract_dir = Path(temp_dir) / "extracted"

            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                zip_file.writestr("document1.pdf", b"PDF content 1")
                zip_file.writestr("document2.pdf", b"PDF content 2")
                zip_file.writestr("readme.txt", b"Not a PDF")

            extracted_files = self.downloader.extract_pdf_from_zip(
                zip_path, extract_dir, keep_zip=True
            )

            assert len(extracted_files) == 2
            assert all(f.suffix == ".pdf" for f in extracted_files)
            assert zip_path.exists()  # ZIP should be kept

    def test_extract_pdf_from_zip_remove_zip(self):
        """Test PDF extraction with ZIP removal."""
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "test.zip"
            extract_dir = Path(temp_dir) / "extracted"

            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                zip_file.writestr("document.pdf", b"PDF content")

            extracted_files = self.downloader.extract_pdf_from_zip(
                zip_path, extract_dir, keep_zip=False
            )

            assert len(extracted_files) == 1
            assert not zip_path.exists()  # ZIP should be removed

    def test_extract_pdf_from_zip_corrupted_zip(self):
        """Test PDF extraction with corrupted ZIP file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create corrupted ZIP file
            zip_path = Path(temp_dir) / "corrupted.zip"
            zip_path.write_bytes(b"This is not a valid ZIP file")

            extract_dir = Path(temp_dir) / "extracted"

            with pytest.raises(FullTextError) as exc_info:
                self.downloader.extract_pdf_from_zip(zip_path, extract_dir)

            assert exc_info.value.error_code == ErrorCodes.FULL005

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.query_pmcids_in_ftp')
    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.download_pdf_zip')
    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.extract_pdf_from_zip')
    def test_bulk_download_and_extract_success(self, mock_extract, mock_download, mock_query):
        """Test successful bulk download and extract."""
        # Mock query results
        mock_query.return_value = {
            "123456": {"filename": "PMC123456.zip", "directory": "PMCxxxx1200", "pmcid": "123456", "size": 1000},
            "789012": None  # Not found
        }

        # Mock download
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "PMC123456.zip"
            pdf_paths = [Path(temp_dir) / "document.pdf"]

            mock_download.return_value = zip_path
            mock_extract.return_value = pdf_paths

            results = self.downloader.bulk_download_and_extract(
                ["123456", "789012"], temp_dir, extract_pdfs=True, keep_zips=False
            )

            # Check results
            assert results["123456"]["status"] == "success"
            assert results["123456"]["zip_path"] == zip_path
            assert results["123456"]["pdf_paths"] == pdf_paths

            assert results["789012"]["status"] == "not_found"
            assert "error" in results["789012"]

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.query_pmcids_in_ftp')
    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.download_pdf_zip')
    def test_bulk_download_and_extract_download_error(self, mock_download, mock_query):
        """Test bulk download with download error."""
        # Mock query results
        mock_query.return_value = {
            "123456": {"filename": "PMC123456.zip", "directory": "PMCxxxx1200", "pmcid": "123456", "size": 1000}
        }

        # Mock download failure
        mock_download.side_effect = FullTextError(ErrorCodes.FULL005, {})

        with tempfile.TemporaryDirectory() as temp_dir:
            results = self.downloader.bulk_download_and_extract(["123456"], temp_dir)

            assert results["123456"]["status"] == "error"
            assert "error" in results["123456"]

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.get_zip_files_in_directory')
    def test_query_pmcids_in_ftp_max_directories_limit(self, mock_get_zip_files):
        """Test query_pmcids_in_ftp with max directories limit."""
        # Mock getting many directories but limit search
        mock_get_zip_files.return_value = []  # No matching files

        with patch.object(self.downloader, '_get_relevant_directories') as mock_get_dirs:
            # Return many directories to test limit
            mock_get_dirs.return_value = set([f"PMCxxxx{i:04d}" for i in range(200)])

            results = self.downloader.query_pmcids_in_ftp(["123456"], max_directories=5)

            assert results["123456"] is None
            # Should have stopped at max directories limit
            assert mock_get_zip_files.call_count <= 5

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.get_zip_files_in_directory')
    def test_query_pmcids_in_ftp_consecutive_failures(self, mock_get_zip_files):
        """Test query_pmcids_in_ftp with consecutive failures."""
        # Make all directory checks fail
        mock_get_zip_files.side_effect = FullTextError(ErrorCodes.FULL005, {})

        with patch.object(self.downloader, '_get_relevant_directories') as mock_get_dirs:
            mock_get_dirs.return_value = set([f"PMCxxxx{i:04d}" for i in range(20)])

            results = self.downloader.query_pmcids_in_ftp(["123456"])

            assert results["123456"] is None
            # Should have stopped due to consecutive failures (max 10)
            assert mock_get_zip_files.call_count <= 10

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader.get_zip_files_in_directory')
    def test_query_pmcids_in_ftp_prioritizes_exact_matches(self, mock_get_zip_files):
        """Test that query_pmcids_in_ftp prioritizes exact directory matches."""
        def side_effect(directory):
            if directory == "PMCxxxx1200":
                return [{
                    "filename": "PMC11691200.zip",
                    "pmcid": "11691200",
                    "size": 1000,
                    "directory": "PMCxxxx1200"
                }]
            elif directory == "PMCxxxx1201":  # Lower priority
                return [{
                    "filename": "PMC11691200.zip",
                    "pmcid": "11691200",
                    "size": 2000,
                    "directory": "PMCxxxx1201"
                }]
            return []

        mock_get_zip_files.side_effect = side_effect

        with patch.object(self.downloader, '_get_relevant_directories') as mock_get_dirs:
            mock_get_dirs.return_value = set(["PMCxxxx1201", "PMCxxxx1200"])  # Out of order

            results = self.downloader.query_pmcids_in_ftp(["11691200"])

            # Should prioritize exact match (PMCxxxx1200 for PMC ID ending in 1200)
            assert results["11691200"] is not None
            assert results["11691200"]["directory"] == "PMCxxxx1200"  # type: ignore
            assert results["11691200"]["size"] == 1000  # type: ignore  # From higher priority directory

    @patch('pyeuropepmc.ftp_downloader.FTPDownloader._get_relevant_directories')
    def test_query_pmcids_in_ftp_directory_error_fallback(self, mock_get_dirs):
        """Test query_pmcids_in_ftp handles directory listing errors gracefully."""
        mock_get_dirs.side_effect = FullTextError(ErrorCodes.FULL005, {})

        results = self.downloader.query_pmcids_in_ftp(["123456"])

        # Should return empty results when directory listing fails
        assert results["123456"] is None
