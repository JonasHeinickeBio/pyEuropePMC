"""
Unit tests for FTP downloader functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from pyeuropepmc.clients.ftp_downloader import FTPDownloader
from pyeuropepmc.core.exceptions import FullTextError
from pyeuropepmc.core.error_codes import ErrorCodes


class TestFTPDownloader:
    """Test cases for FTPDownloader class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.downloader = FTPDownloader()

    def test_init(self):
        """Test FTPDownloader initialization."""
        downloader = FTPDownloader(rate_limit_delay=2.0)
        assert downloader.rate_limit_delay == 2.0
        assert downloader.BASE_FTP_URL == "https://europepmc.org/ftp/pdf/"

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_success(self, mock_get_ftp_url):
        """Test successful retrieval of available directories."""
        # Mock HTML response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
        <a href="PMCxxxx1200/">PMCxxxx1200/</a>
        <a href="PMCxxxx1201/">PMCxxxx1201/</a>
        <a href="PMCxxxx1202/">PMCxxxx1202/</a>
        <a href="other.txt">other.txt</a>
        </body>
        </html>
        '''
        mock_get_ftp_url.return_value = mock_response

        directories = self.downloader.get_available_directories()

        assert directories == ['PMCxxxx1200', 'PMCxxxx1201', 'PMCxxxx1202']
        mock_get_ftp_url.assert_called_once_with(self.downloader.BASE_FTP_URL)

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_http_error(self, mock_get_ftp_url):
        """Test directory retrieval with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get_ftp_url.return_value = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005
        assert "url" in exc_info.value.context

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_available_directories_no_response(self, mock_get_ftp_url):
        """Test directory retrieval with no response."""
        mock_get_ftp_url.return_value = None

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_zip_files_in_directory_success(self, mock_get_ftp_url):
        """Test successful retrieval of ZIP files in directory."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
        <table>
        <tr>
            <td><a href="PMC11691200.zip">PMC11691200.zip</a></td>
            <td>2024-01-01 12:00</td>
            <td>289K</td>
        </tr>
        <tr>
            <td><a href="PMC11691201.zip">PMC11691201.zip</a></td>
            <td>2024-01-01 12:01</td>
            <td>2.5M</td>
        </tr>
        <tr>
            <td><a href="README.txt">README.txt</a></td>
            <td>2024-01-01 10:00</td>
            <td>1K</td>
        </tr>
        </table>
        </body>
        </html>
        '''
        mock_get_ftp_url.return_value = mock_response

        zip_files = self.downloader.get_zip_files_in_directory('PMCxxxx1200')

        expected = [
            {
                'filename': 'PMC11691200.zip',
                'pmcid': '11691200',
                'size': 295936,  # 289K in bytes
                'directory': 'PMCxxxx1200'
            },
            {
                'filename': 'PMC11691201.zip',
                'pmcid': '11691201',
                'size': 2621440,  # 2.5M in bytes
                'directory': 'PMCxxxx1200'
            }
        ]

        assert zip_files == expected

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_get_zip_files_in_directory_http_error(self, mock_get_ftp_url):
        """Test ZIP file retrieval with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get_ftp_url.return_value = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_zip_files_in_directory('PMCxxxx1200')

        assert exc_info.value.error_code == ErrorCodes.FULL005

    def test_parse_file_size(self):
        """Test file size parsing."""
        assert self.downloader._parse_file_size('289K') == 295936
        assert self.downloader._parse_file_size('2.5M') == 2621440
        assert self.downloader._parse_file_size('1.2G') == 1288490188  # Updated expected value
        assert self.downloader._parse_file_size('100') == 100
        assert self.downloader._parse_file_size('') == 0
        assert self.downloader._parse_file_size('-') == 0
        assert self.downloader._parse_file_size('invalid') == 0

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.get_zip_files_in_directory')
    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_relevant_directories')
    def test_query_pmcids_in_ftp_success(self, mock_get_dirs, mock_get_zips):
        """Test successful querying of PMC IDs in FTP."""
        mock_get_dirs.return_value = {'PMCxxxx1200', 'PMCxxxx1201'}

        # Mock ZIP files for first directory
        mock_get_zips.side_effect = [
            [
                {
                    'filename': 'PMC11691200.zip',
                    'pmcid': '11691200',
                    'size': 295936,
                    'directory': 'PMCxxxx1200'
                }
            ],
            [
                {
                    'filename': 'PMC11691300.zip',
                    'pmcid': '11691300',
                    'size': 400000,
                    'directory': 'PMCxxxx1201'
                }
            ]
        ]

        result = self.downloader.query_pmcids_in_ftp(['11691200', '11691300', '99999999'])

        expected = {
            '11691200': {
                'filename': 'PMC11691200.zip',
                'pmcid': '11691200',
                'size': 295936,
                'directory': 'PMCxxxx1200'
            },
            '11691300': {
                'filename': 'PMC11691300.zip',
                'pmcid': '11691300',
                'size': 400000,
                'directory': 'PMCxxxx1201'
            },
            '99999999': None
        }

        assert result == expected

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_download_pdf_zip_success(self, mock_mkdir, mock_file_open, mock_get_ftp_url):
        """Test successful PDF ZIP download."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '295936'}
        mock_response.iter_content = Mock(return_value=[b'chunk1', b'chunk2'])
        mock_get_ftp_url.return_value = mock_response

        zip_info = {
            'filename': 'PMC11691200.zip',
            'directory': 'PMCxxxx1200',
            'pmcid': '11691200',
            'size': 295936
        }

        output_path = self.downloader.download_pdf_zip(zip_info, '/tmp/downloads')

        assert output_path == Path('/tmp/downloads/PMC11691200.zip')
        mock_mkdir.assert_called_once()
        mock_file_open.assert_called_once()

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_download_pdf_zip_http_error(self, mock_get_ftp_url):
        """Test PDF ZIP download with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get_ftp_url.return_value = mock_response

        zip_info = {
            'filename': 'PMC11691200.zip',
            'directory': 'PMCxxxx1200',
            'pmcid': '11691200',
            'size': 295936
        }

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.download_pdf_zip(zip_info, '/tmp/downloads')

        assert exc_info.value.error_code == ErrorCodes.FULL005

    @patch('zipfile.ZipFile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_extract_pdf_from_zip_success(self, mock_mkdir, mock_file_open, mock_zipfile):
        """Test successful PDF extraction from ZIP."""
        # Mock ZIP file
        mock_zip_instance = Mock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

        # Mock file info
        mock_file_info = Mock()
        mock_file_info.filename = 'paper1.pdf'
        mock_zip_instance.infolist.return_value = [mock_file_info]

        # Mock file content with context manager
        mock_source = Mock()
        mock_source.read.return_value = b'PDF content'
        mock_source.__enter__ = Mock(return_value=mock_source)
        mock_source.__exit__ = Mock(return_value=None)
        mock_zip_instance.open.return_value = mock_source

        zip_path = Path('/tmp/PMC11691200.zip')
        extracted_files = self.downloader.extract_pdf_from_zip(
            zip_path, '/tmp/extracted', keep_zip=True
        )

        assert extracted_files == [Path('/tmp/extracted/paper1.pdf')]
        mock_mkdir.assert_called_once()

    @patch('zipfile.ZipFile')
    @patch('pathlib.Path.unlink')
    def test_extract_pdf_from_zip_remove_zip(self, mock_unlink, mock_zipfile):
        """Test PDF extraction with ZIP removal."""
        # Mock ZIP file
        mock_zip_instance = Mock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance
        mock_zip_instance.infolist.return_value = []  # No PDF files

        zip_path = Path('/tmp/PMC11691200.zip')
        extracted_files = self.downloader.extract_pdf_from_zip(
            zip_path, '/tmp/extracted', keep_zip=False
        )

        assert extracted_files == []
        mock_unlink.assert_called_once()

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.query_pmcids_in_ftp')
    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.download_pdf_zip')
    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.extract_pdf_from_zip')
    def test_bulk_download_and_extract_success(self, mock_extract, mock_download, mock_query):
        """Test successful bulk download and extraction."""
        # Mock query results
        mock_query.return_value = {
            '11691200': {
                'filename': 'PMC11691200.zip',
                'pmcid': '11691200',
                'size': 295936,
                'directory': 'PMCxxxx1200'
            },
            '11691201': None  # Not found
        }

        # Mock download
        mock_download.return_value = Path('/tmp/PMC11691200.zip')

        # Mock extraction
        mock_extract.return_value = [Path('/tmp/extracted/paper1.pdf')]

        results = self.downloader.bulk_download_and_extract(
            ['11691200', '11691201'], '/tmp/downloads'
        )

        expected = {
            '11691200': {
                'status': 'success',
                'zip_path': Path('/tmp/PMC11691200.zip'),
                'pdf_paths': [Path('/tmp/extracted/paper1.pdf')]
            },
            '11691201': {
                'status': 'not_found',
                'error': 'PMC ID not found in FTP'
            }
        }

        assert results == expected

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.query_pmcids_in_ftp')
    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.download_pdf_zip')
    def test_bulk_download_and_extract_download_error(self, mock_download, mock_query):
        """Test bulk download with download error."""
        # Mock query results
        mock_query.return_value = {
            '11691200': {
                'filename': 'PMC11691200.zip',
                'pmcid': '11691200',
                'size': 295936,
                'directory': 'PMCxxxx1200'
            }
        }

        # Mock download error
        mock_download.side_effect = FullTextError(ErrorCodes.FULL005, {})

        results = self.downloader.bulk_download_and_extract(['11691200'], '/tmp/downloads')

        assert results['11691200']['status'] == 'error'
        assert 'error' in results['11691200']

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.get_available_directories')
    def test_get_relevant_directories_success(self, mock_get_dirs):
        """Test getting relevant directories."""
        # The method should return specific directories based on PMC IDs, not all available
        directories = self.downloader._get_relevant_directories(['11691200', '11691300'])
         # For PMC ID 11691200, it should check:
        # - PMCxxxx200 (last 3 digits)
        # - PMCxxxx199, PMCxxxx201 (±1 from last 3 digits)
        # - PMCxxxx1200 (last 4 digits, exactly at boundary)
        # - PMCxxxx1199 (1200-1, still in range)
        # - No PMCxxxx1201 (1200+1 = 1201 > 1200, outside range)
        # For PMC ID 11691300, it should check:
        # - PMCxxxx300 (last 3 digits)
        # - PMCxxxx299, PMCxxxx301 (±1 from last 3 digits)
        # - No 4-digit pattern (1300 > 1200, outside valid range)

        expected_dirs = {
            'PMCxxxx200', 'PMCxxxx199', 'PMCxxxx201',  # from 11691200
            'PMCxxxx1200', 'PMCxxxx1199',  # from 11691200 (no 1201 since 1201 > 1200)
            'PMCxxxx300', 'PMCxxxx299', 'PMCxxxx301'  # from 11691300
        }

        assert directories == expected_dirs
        # Should not call get_available_directories since we found specific directories
        mock_get_dirs.assert_not_called()

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader.get_available_directories')
    def test_get_relevant_directories_fallback(self, mock_get_dirs):
        """Test getting relevant directories with fallback."""
        mock_get_dirs.side_effect = FullTextError(ErrorCodes.FULL005, {})

        # Use an invalid PMC ID that would result in no directories
        directories = self.downloader._get_relevant_directories(['invalid'])

        # Should return fallback directories (PMCxxxx0 to PMCxxxx1200)
        assert len(directories) == 1201  # 0-999 (1000) + 1000-1200 (201) = 1201
        assert 'PMCxxxx0' in directories
        assert 'PMCxxxx1200' in directories


@pytest.mark.parametrize("size_text,expected", [
    ("289K", 295936),
    ("2.5M", 2621440),
    ("1.2G", 1288490188),  # Updated expected value
    ("100", 100),
    ("", 0),
    ("-", 0),
    ("invalid", 0),
    ("50.5K", 51712),
])
def test_parse_file_size_parametrized(size_text, expected):
    """Parametrized test for file size parsing."""
    downloader = FTPDownloader()
    assert downloader._parse_file_size(size_text) == expected


class TestFTPDownloaderIntegration:
    """Integration tests for FTPDownloader with more realistic scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.downloader = FTPDownloader()

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_realistic_directory_listing(self, mock_get):
        """Test with realistic directory listing HTML."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <!DOCTYPE html>
        <html>
        <head><title>Index of /ftp/pdf/</title></head>
        <body>
        <h1>Index of /ftp/pdf/</h1>
        <table>
        <tr><th valign="top"><img src="/icons/blank.gif" alt="[ICO]"></th><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th><th><a href="?C=D;O=A">Description</a></th></tr>
        <tr><th colspan="5"><hr></th></tr>
        <tr><td valign="top"><img src="/icons/back.gif" alt="[PARENTDIR]"></td><td><a href="/">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>
        <tr><td valign="top"><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="PMCxxxx1200/">PMCxxxx1200/</a></td><td align="right">2024-01-01 12:00  </td><td align="right">  - </td><td>&nbsp;</td></tr>
        <tr><td valign="top"><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="PMCxxxx1201/">PMCxxxx1201/</a></td><td align="right">2024-01-01 12:01  </td><td align="right">  - </td><td>&nbsp;</td></tr>
        <tr><th colspan="5"><hr></th></tr>
        </table>
        </body>
        </html>
        '''
        mock_get.return_value = mock_response

        directories = self.downloader.get_available_directories()

        assert directories == ['PMCxxxx1200', 'PMCxxxx1201']

    @patch('pyeuropepmc.clients.ftp_downloader.FTPDownloader._get_ftp_url')
    def test_realistic_zip_file_listing(self, mock_get):
        """Test with realistic ZIP file listing HTML."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <!DOCTYPE html>
        <html>
        <head><title>Index of /ftp/pdf/PMCxxxx1200/</title></head>
        <body>
        <h1>Index of /ftp/pdf/PMCxxxx1200/</h1>
        <table>
        <tr><th><a href="?C=N;O=D">Name</a></th><th><a href="?C=M;O=A">Last modified</a></th><th><a href="?C=S;O=A">Size</a></th></tr>
        <tr><td><a href="/">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td></tr>
        <tr><td><a href="PMC11691200.zip">PMC11691200.zip</a></td><td align="right">2024-01-01 12:00  </td><td align="right">289K</td></tr>
        <tr><td><a href="PMC11691201.zip">PMC11691201.zip</a></td><td align="right">2024-01-01 12:01  </td><td align="right">1.2M</td></tr>
        <tr><td><a href="README.txt">README.txt</a></td><td align="right">2024-01-01 10:00  </td><td align="right">1.5K</td></tr>
        </table>
        </body>
        </html>
        '''
        mock_get.return_value = mock_response

        zip_files = self.downloader.get_zip_files_in_directory('PMCxxxx1200')

        expected = [
            {
                'filename': 'PMC11691200.zip',
                'pmcid': '11691200',
                'size': 295936,  # 289K
                'directory': 'PMCxxxx1200'
            },
            {
                'filename': 'PMC11691201.zip',
                'pmcid': '11691201',
                'size': 1258291,  # 1.2M
                'directory': 'PMCxxxx1200'
            }
        ]

        assert zip_files == expected
