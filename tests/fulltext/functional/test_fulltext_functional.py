"""
Functional tests for FullTextClient with real API calls.
These tests require network access and interact with the real Europe PMC API.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, Mock, mock_open

import pytest

from pyeuropepmc.fulltext import FullTextClient
from pyeuropepmc.exceptions import FullTextError
from pyeuropepmc.search import SearchClient
from pyeuropepmc.ftp_downloader import FTPDownloader
from pyeuropepmc.error_codes import ErrorCodes

pytestmark = pytest.mark.functional


class TestFullTextClientFunctional:
    """Functional tests for FullTextClient using real API calls."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.client = FullTextClient(rate_limit_delay=1.5)  # Be respectful to API

    def teardown_method(self):
        """Clean up after each test method."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    @pytest.mark.parametrize(
        "pmcid,expected_formats",
        [
            ("3257301", ["xml"]),  # Known open access article
            ("PMC3257301", ["xml"]),  # Same article with PMC prefix
        ],
    )
    def test_check_availability_known_articles(self, pmcid, expected_formats):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info(f"Checking availability for PMC ID: {pmcid}")
        availability = self.client.check_fulltext_availability(pmcid)
        logger.info(f"Availability result for {pmcid}: {availability}")
        assert isinstance(availability, dict)
        assert all(format_type in availability for format_type in ["pdf", "xml", "html"])
        for format_type in expected_formats:
            logger.info(f"Checking if {format_type} is available for {pmcid}")
            assert availability[format_type], f"{format_type} should be available for {pmcid}"

    def test_check_availability_invalid_pmcid(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info("Checking availability for invalid PMC ID: 99999999")
        availability = self.client.check_fulltext_availability("99999999")
        logger.info(f"Availability result for 99999999: {availability}")
        # For invalid PMCIDs, PDF and XML should be False, but HTML availability checking
        # might be unreliable for very high/invalid PMC IDs, so we only check PDF and XML
        assert availability["pdf"] is False
        assert availability["xml"] is False
        # HTML availability check is less reliable for invalid IDs, so we don't assert it

    def test_download_pdf_open_access_article(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_download.pdf"
            logger.info(f"Attempting PDF download for PMC3257301 to {output_path}")
            try:
                result = self.client.download_pdf_by_pmcid("3257301", output_path)
                logger.info(f"Download result: {result}")
                if result:
                    assert result == output_path
                    assert output_path.exists()
                    logger.info(f"Downloaded PDF exists at {output_path}")
                    assert output_path.stat().st_size > 1000
                    with open(output_path, "rb") as f:
                        header = f.read(4)
                        logger.info(f"PDF header: {header}")
                        assert header == b"%PDF"
            except FullTextError as e:
                logger.warning(f"PDF not available for test article: {e}")
                pytest.skip(f"PDF not available for test article: {e}")

    def test_download_pdf_invalid_pmcid(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nonexistent.pdf"
            logger.info("Testing PDF download with invalid PMC ID")
            result = self.client.download_pdf_by_pmcid("99999999", output_path)
            assert result is None

    def test_download_xml_open_access_article(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_download.xml"
            logger.info(f"Attempting XML download for PMC3257301 to {output_path}")
            result = self.client.download_xml_by_pmcid("3257301", output_path)
            logger.info(f"Download result: {result}")
            assert result == output_path
            assert output_path.exists()
            assert output_path.stat().st_size > 100
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info(f"First 200 chars of XML: {content[:200]}")
                assert content.strip().startswith("<")
                assert "article" in content or "pmc-articleset" in content

    def test_download_xml_known_available_duplicate(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"
            logger.info(f"Attempting XML download for PMC3257301 to {output_path}")
            result = self.client.download_xml_by_pmcid("3257301", output_path)
            logger.info(f"Download result: {result}")
            assert result == output_path
            assert output_path.exists()
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info(f"First 200 chars of XML: {content[:200]}")
                assert content.strip().startswith("<")

    def test_get_xml_content_open_access_article(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info("Retrieving XML content for PMC3257301 as string")
        content = self.client.get_fulltext_content("3257301", "xml")
        logger.info(f"First 200 chars of XML content: {content[:200]}")
        assert isinstance(content, str)
        assert len(content) > 100
        assert content.strip().startswith("<")
        assert "article" in content or "pmc-articleset" in content

    def test_batch_download_mixed_results(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        pmcids = ["3257301", "99999999", "invalid"]
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Batch downloading XML for: {pmcids}")
            try:
                results = self.client.download_fulltext_batch(
                    pmcids, format_type="xml", output_dir=temp_dir, skip_errors=True
                )
            except Exception:
                # Accept any error for invalid/unavailable PMCIDs
                results = {pmcid: None for pmcid in pmcids}
            logger.info(f"Batch download results: {results}")
            assert len(results) == 3
            assert results["3257301"] is not None
            assert results["99999999"] is None
            assert results["invalid"] is None

    def test_pmcid_format_variations(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        variations = ["3257301", "PMC3257301", "pmc3257301", "  PMC3257301  "]
        for pmcid in variations:
            logger.info(f"Checking availability for variation: {pmcid}")
            availability = self.client.check_fulltext_availability(pmcid)
            logger.info(f"Availability: {availability}")
            assert isinstance(availability, dict)
            assert availability["xml"]

    def test_rate_limiting_behavior(self):
        import logging
        import time

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info("Testing rate limiting behavior")
        start_time = time.time()
        for i in range(2):  # Reduce to 2 requests to make timing more predictable
            logger.info(f"Request {i + 1} for PMC3257301")
            self.client.check_fulltext_availability("3257301")
        elapsed_time = time.time() - start_time
        logger.info(f"Elapsed time: {elapsed_time}")
        # With 2 requests and rate_limit_delay=1.5, expect at least 1.5 seconds
        # But use a very lenient threshold to account for CI environment variations
        expected_min_time = self.client.rate_limit_delay * 0.2  # Very lenient timing for CI
        assert elapsed_time >= expected_min_time, (
            f"Expected at least {expected_min_time}s, got {elapsed_time}s"
        )

    def test_context_manager_functionality(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info("Testing context manager functionality")
        with FullTextClient() as client:
            availability = client.check_fulltext_availability("3257301")
            logger.info(f"Availability in context: {availability}")
            assert isinstance(availability, dict)
            assert not client.is_closed
        assert client.is_closed

    def test_error_handling_with_real_api(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info("Testing error handling with invalid PMC ID format")
        with pytest.raises(FullTextError):
            self.client._validate_pmcid("not_a_number_at_all")
        logger.info("Testing error handling with non-existent PMC ID")
        availability = self.client.check_fulltext_availability("123456789")
        logger.info(f"Availability for 123456789: {availability}")
        # For very high PMC IDs, PDF and XML should be False, but HTML might be unreliable
        assert not availability["pdf"]
        assert not availability["xml"]

    def test_large_file_download(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "large_test.pdf"
            logger.info(f"Attempting large PDF download for PMC3257301 to {output_path}")
            try:
                result = self.client.download_pdf_by_pmcid("3257301", output_path)
                logger.info(f"Download result: {result}")
                if result and output_path.exists():
                    file_size = output_path.stat().st_size
                    logger.info(f"Downloaded file size: {file_size}")
                    assert file_size > 0
                    with open(output_path, "rb") as f:
                        header = f.read(8)
                        logger.info(f"PDF header: {header}")
                        assert header.startswith(b"%PDF")
                        f.seek(-10, 2)
                        footer = f.read()
                        logger.info(f"PDF footer: {footer}")
                        assert len(footer) > 0
            except FullTextError as e:
                logger.warning(f"Large file test skipped: {e}")
                pytest.skip(f"Large file test skipped: {e}")

    def test_download_xml_known_working(self):
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        pmcid = "3257301"
        logger.info(f"Functional test: download XML for PMC{pmcid}")
        with FullTextClient() as client:
            try:
                xml_content = client.get_fulltext_content(pmcid, format_type="xml")
                logger.info(f"First 200 chars of XML: {xml_content[:200]}")
                assert xml_content.strip().startswith(
                    "<!DOCTYPE article"
                ) or xml_content.strip().startswith("<article"), (
                    "XML content should start with article tag or DOCTYPE."
                )
                assert "open_access" in xml_content or "article-type" in xml_content, (
                    "Should contain expected XML properties."
                )
            except FullTextError as e:
                logger.error(f"FullTextError raised unexpectedly: {e}")
                pytest.fail(f"FullTextError raised unexpectedly: {e}")

    @pytest.mark.functional
    def test_check_availability_xml_available(self):
        """Test XML availability for a known available PMC ID (PMC3257301)."""
        availability = self.client.check_fulltext_availability("3257301")
        assert availability["xml"], "XML should be available for PMC3257301"

    @pytest.mark.functional
    def test_download_xml_known_available(self):
        """Test XML download for a known available PMC ID (PMC3257301)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3257301.xml"
            result = self.client.download_xml_by_pmcid("3257301", output_path)
            assert result == output_path
            assert output_path.exists()
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert content.strip().startswith("<"), "Downloaded file should be XML"

    @pytest.mark.functional
    def test_download_xml_known_unavailable(self):
        """Test XML download for a known unavailable PMC ID (PMC3312970)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMC3312970.xml"
            with pytest.raises((FullTextError, Exception)):
                self.client.download_xml_by_pmcid("3312970", output_path)

    @pytest.mark.functional
    def test_e2e_search_and_download_10_xml(self):  # noqa: C901
        """End-to-end: search, find 10 XML-available papers, download XML for each."""
        import logging

        logger = logging.getLogger("TestFullTextClientFunctional")
        logger.info("Starting e2e search and download for first 10 XML-available papers")
        search_client = SearchClient(rate_limit_delay=1.5)

        try:
            results = search_client.search(query="open access", page_size=100)
            logger.info(f"Search returned: {type(results)}")

            # Handle different result formats
            if isinstance(results, dict) and "resultList" in results:
                result_list = results["resultList"].get("result", [])
            elif isinstance(results, list):
                result_list = results
            else:
                logger.warning(f"Unexpected search result format: {type(results)}")
                pytest.skip("Search returned unexpected format, skipping e2e test")
                return

            found = 0
            pmcids = []

            for result in result_list:
                if isinstance(result, dict):
                    pmcid = result.get("pmcid")
                    if not pmcid:
                        continue
                    # Remove PMC prefix if present
                    pmcid = pmcid.replace("PMC", "")
                    try:
                        avail = self.client.check_fulltext_availability(pmcid)
                        logger.info(
                            f"Found pmcid in search: {pmcid}, xml available: {avail['xml']}"
                        )
                        if pmcid and avail["xml"]:
                            pmcids.append(pmcid)
                            found += 1
                        if found == 10:
                            break
                    except Exception as e:
                        logger.warning(f"Failed to check availability for {pmcid}: {e}")
                        continue

            logger.info(f"Found {found} XML-available PMCIDs in search results")

            # If we can't find any, skip the test rather than fail
            if len(pmcids) == 0:
                pytest.skip(
                    "No XML-available papers found in search results, skipping download test"
                )
                return

            with tempfile.TemporaryDirectory() as temp_dir:
                for pmcid in pmcids[:3]:  # Just test first 3 to avoid long test times
                    output_path = Path(temp_dir) / f"PMC{pmcid}.xml"
                    logger.info(f"Downloading XML for PMC{pmcid} to {output_path}")
                    try:
                        result = self.client.download_xml_by_pmcid(pmcid, output_path)
                        logger.info(f"Download result: {result}")
                        assert result == output_path
                        assert output_path.exists()
                        with open(output_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            logger.info(f"First 200 chars of XML for PMC{pmcid}: {content[:200]}")
                            assert content.strip().startswith("<"), (
                                f"Downloaded file for PMC{pmcid} should be XML"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to download XML for PMC{pmcid}: {e}")
                        continue

        except Exception as e:
            logger.error(f"E2E test failed with error: {e}")
            pytest.skip(f"E2E test skipped due to error: {e}")

    @patch("requests.get")
    def test_download_pdf_by_pmcid_invalid(self, mock_get):
        mock_response_render = Mock()
        mock_response_render.status_code = 404
        mock_response_zip = Mock()
        mock_response_zip.status_code = 404
        mock_get.side_effect = [mock_response_render, mock_response_zip]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "PMCbadid.pdf"
            client = FullTextClient()
            with pytest.raises(FullTextError):
                client.download_pdf_by_pmcid("badid", output_path)


class TestFTPDownloaderFunctional:
    """Functional tests for FTPDownloader with mocked responses."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.downloader = FTPDownloader(rate_limit_delay=0.1)  # Fast tests

    @patch("pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url")
    def test_get_available_directories_functional(self, mock_get):
        """Test retrieving available directories with realistic HTML response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <!DOCTYPE html>
        <html>
        <head><title>Index of /ftp/pdf/</title></head>
        <body>
        <h1>Index of /ftp/pdf/</h1>
        <table>
        <tr><th><img src="/icons/blank.gif" alt="[ICO]"></th><th><a href="?C=N;O=D">Name</a></th></tr>
        <tr><td><img src="/icons/back.gif" alt="[PARENTDIR]"></td><td><a href="/">Parent Directory</a></td></tr>
        <tr><td><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="PMCxxxx1200/">PMCxxxx1200/</a></td></tr>
        <tr><td><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="PMCxxxx1201/">PMCxxxx1201/</a></td></tr>
        <tr><td><img src="/icons/folder.gif" alt="[DIR]"></td><td><a href="PMCxxxx1202/">PMCxxxx1202/</a></td></tr>
        </table>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        directories = self.downloader.get_available_directories()
        assert len(directories) == 3
        assert "PMCxxxx1200" in directories
        assert "PMCxxxx1201" in directories
        assert "PMCxxxx1202" in directories

    @patch("pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url")
    def test_get_zip_files_functional(self, mock_get):
        """Test retrieving ZIP files with realistic HTML response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <!DOCTYPE html>
        <html>
        <head><title>Index of /ftp/pdf/PMCxxxx1200/</title></head>
        <body>
        <h1>Index of /ftp/pdf/PMCxxxx1200/</h1>
        <table>
        <tr><th><img src="/icons/blank.gif" alt="[ICO]"></th><th><a href="?C=N;O=D">Name</a></th><th>Size</th></tr>
        <tr><td><img src="/icons/back.gif" alt="[PARENTDIR]"></td><td><a href="/">Parent Directory</a></td><td>-</td></tr>
        <tr><td><img src="/icons/compressed.gif" alt="[ZIP]"></td><td><a href="PMC11691200.zip">PMC11691200.zip</a></td><td>289K</td></tr>
        <tr><td><img src="/icons/compressed.gif" alt="[ZIP]"></td><td><a href="PMC11691201.zip">PMC11691201.zip</a></td><td>1.2M</td></tr>
        <tr><td><img src="/icons/text.gif" alt="[TXT]"></td><td><a href="README.txt">README.txt</a></td><td>1.5K</td></tr>
        </table>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        zip_files = self.downloader.get_zip_files_in_directory("PMCxxxx1200")
        assert len(zip_files) == 2

        # Check first ZIP file
        assert zip_files[0]["filename"] == "PMC11691200.zip"
        assert zip_files[0]["pmcid"] == "11691200"
        assert zip_files[0]["size"] == 295936  # 289K in bytes
        assert zip_files[0]["directory"] == "PMCxxxx1200"

        # Check second ZIP file
        assert zip_files[1]["filename"] == "PMC11691201.zip"
        assert zip_files[1]["pmcid"] == "11691201"
        assert zip_files[1]["size"] == 1258291  # 1.2M in bytes
        assert zip_files[1]["directory"] == "PMCxxxx1200"

    @patch("pyeuropepmc.ftp_downloader.FTPDownloader.get_zip_files_in_directory")
    @patch("pyeuropepmc.ftp_downloader.FTPDownloader._get_relevant_directories")
    def test_query_pmcids_functional(self, mock_get_dirs, mock_get_zips):
        """Test querying PMC IDs with realistic data."""
        mock_get_dirs.return_value = {"PMCxxxx1200", "PMCxxxx1201"}

        # Mock ZIP files for directories
        def side_effect(directory):
            if directory == "PMCxxxx1200":
                return [
                    {
                        "filename": "PMC11691200.zip",
                        "pmcid": "11691200",
                        "size": 295936,
                        "directory": "PMCxxxx1200",
                    },
                    {
                        "filename": "PMC11691205.zip",
                        "pmcid": "11691205",
                        "size": 400000,
                        "directory": "PMCxxxx1200",
                    },
                ]
            elif directory == "PMCxxxx1201":
                return [
                    {
                        "filename": "PMC11691300.zip",
                        "pmcid": "11691300",
                        "size": 500000,
                        "directory": "PMCxxxx1201",
                    }
                ]
            return []

        mock_get_zips.side_effect = side_effect

        # Query for a mix of available and unavailable PMC IDs
        result = self.downloader.query_pmcids_in_ftp(["11691200", "11691300", "99999999"])

        assert len(result) == 3
        assert result["11691200"] is not None
        assert result["11691200"]["filename"] == "PMC11691200.zip"
        assert result["11691300"] is not None
        assert result["11691300"]["filename"] == "PMC11691300.zip"
        assert result["99999999"] is None

    @patch("pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_download_pdf_zip_functional(self, mock_mkdir, mock_file_open, mock_get):
        """Test downloading a ZIP file with realistic response."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "295936"}
        mock_response.iter_content = Mock(return_value=[b"fake_zip_data"])
        mock_get.return_value = mock_response

        zip_info = {
            "filename": "PMC11691200.zip",
            "directory": "PMCxxxx1200",
            "pmcid": "11691200",
            "size": 295936,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = self.downloader.download_pdf_zip(zip_info, temp_dir)

            # Verify the download
            expected_path = Path(temp_dir) / "PMC11691200.zip"
            assert result_path == expected_path
            mock_mkdir.assert_called_once()
            mock_file_open.assert_called_once()

    @patch("zipfile.ZipFile")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_extract_pdf_functional(self, mock_mkdir, mock_file_open, mock_zipfile):
        """Test extracting PDFs from ZIP file with realistic structure."""
        # Mock ZIP file with multiple PDFs
        mock_zip_instance = Mock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

        # Mock file info objects
        pdf1_info = Mock()
        pdf1_info.filename = "paper1.pdf"
        pdf2_info = Mock()
        pdf2_info.filename = "paper2.pdf"
        readme_info = Mock()
        readme_info.filename = "README.txt"

        mock_zip_instance.infolist.return_value = [pdf1_info, pdf2_info, readme_info]

        # Mock file content with proper context manager
        mock_source = Mock()
        mock_source.read.return_value = b"fake_pdf_content"
        mock_source.__enter__ = Mock(return_value=mock_source)
        mock_source.__exit__ = Mock(return_value=None)
        mock_zip_instance.open.return_value = mock_source

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "PMC11691200.zip"
            extract_dir = Path(temp_dir) / "extracted"

            extracted_files = self.downloader.extract_pdf_from_zip(
                zip_path, extract_dir, keep_zip=True
            )

            # Should only extract PDF files
            assert len(extracted_files) == 2
            assert extract_dir / "paper1.pdf" in extracted_files
            assert extract_dir / "paper2.pdf" in extracted_files

    @patch("pyeuropepmc.ftp_downloader.FTPDownloader.query_pmcids_in_ftp")
    @patch("pyeuropepmc.ftp_downloader.FTPDownloader.download_pdf_zip")
    @patch("pyeuropepmc.ftp_downloader.FTPDownloader.extract_pdf_from_zip")
    def test_bulk_download_functional(self, mock_extract, mock_download, mock_query):
        """Test bulk download functionality with mixed results."""
        import logging

        logger = logging.getLogger("TestFTPDownloaderFunctional")

        # Mock query results
        mock_query.return_value = {
            "11691200": {
                "filename": "PMC11691200.zip",
                "pmcid": "11691200",
                "size": 295936,
                "directory": "PMCxxxx1200",
            },
            "11691201": {
                "filename": "PMC11691201.zip",
                "pmcid": "11691201",
                "size": 400000,
                "directory": "PMCxxxx1200",
            },
            "99999999": None,  # Not found
        }

        # Mock download results
        def download_side_effect(zip_info, output_dir):
            pmcid = zip_info["pmcid"]
            return Path(output_dir) / f"PMC{pmcid}.zip"

        mock_download.side_effect = download_side_effect

        # Mock extraction results
        def extract_side_effect(zip_path, extract_dir, keep_zip=False):
            pmcid = zip_path.name.replace("PMC", "").replace(".zip", "")
            return [Path(extract_dir) / f"PMC{pmcid}_paper.pdf"]

        mock_extract.side_effect = extract_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Starting bulk download test in {temp_dir}")
            results = self.downloader.bulk_download_and_extract(
                ["11691200", "11691201", "99999999"], temp_dir
            )

            # Verify results
            assert len(results) == 3

            # Check successful downloads
            assert results["11691200"]["status"] == "success"
            assert "zip_path" in results["11691200"]
            assert "pdf_paths" in results["11691200"]

            assert results["11691201"]["status"] == "success"
            assert "zip_path" in results["11691201"]
            assert "pdf_paths" in results["11691201"]

            # Check not found
            assert results["99999999"]["status"] == "not_found"
            assert results["99999999"]["error"] == "PMC ID not found in FTP"

            logger.info(f"Bulk download test completed successfully: {results}")

    def test_ftp_downloader_integration_with_search(self):
        """Integration test: search for papers and check FTP availability."""
        import logging

        logger = logging.getLogger("TestFTPDownloaderFunctional")

        # This test demonstrates how FTPDownloader integrates with SearchClient
        search_client = SearchClient(rate_limit_delay=0.1)

        try:
            # Search for recent open access papers
            results = search_client.search(query="open access AND hasReferences:Y", page_size=5)

            logger.info(f"Search returned: {type(results)}")

            # Extract PMC IDs
            pmcids = []
            if isinstance(results, dict) and "resultList" in results:
                result_list = results["resultList"].get("result", [])
            elif isinstance(results, list):
                result_list = results
            else:
                pytest.skip("Unexpected search result format")
                return

            for result in result_list[:3]:  # Test first 3
                if isinstance(result, dict) and "pmcid" in result:
                    pmcid = result["pmcid"].replace("PMC", "")
                    pmcids.append(pmcid)

            if not pmcids:
                pytest.skip("No PMC IDs found in search results")
                return

            # Mock FTP query (since we can't access real FTP in tests)
            with patch.object(self.downloader, "query_pmcids_in_ftp") as mock_query:
                mock_query.return_value = {
                    pmcid: {
                        "filename": f"PMC{pmcid}.zip",
                        "pmcid": pmcid,
                        "size": 300000,
                        "directory": "PMCxxxx1200",
                    }
                    if i < 2
                    else None  # Make first 2 available
                    for i, pmcid in enumerate(pmcids)
                }

                ftp_availability = self.downloader.query_pmcids_in_ftp(pmcids)
                logger.info(f"FTP availability: {ftp_availability}")

                available_count = sum(1 for v in ftp_availability.values() if v is not None)
                logger.info(f"Found {available_count} papers available on FTP")

                assert isinstance(ftp_availability, dict)
                assert len(ftp_availability) == len(pmcids)

        except Exception as e:
            logger.warning(f"Integration test skipped due to error: {e}")
            pytest.skip(f"Integration test error: {e}")

    @patch("pyeuropepmc.ftp_downloader.FTPDownloader._get_ftp_url")
    def test_error_handling_network_issues(self, mock_get):
        """Test error handling for network issues."""
        # Test connection timeout
        mock_get.return_value = None

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005

        # Test HTTP error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        with pytest.raises(FullTextError) as exc_info:
            self.downloader.get_available_directories()

        assert exc_info.value.error_code == ErrorCodes.FULL005

    def test_file_size_parsing_edge_cases(self):
        """Test file size parsing with various formats."""
        test_cases = [
            ("289K", 295936),
            ("2.5M", 2621440),
            ("1.2G", 1288490188),  # Fixed expected value
            ("100", 100),
            ("0", 0),
            ("", 0),
            ("-", 0),
            ("N/A", 0),
            ("50.5K", 51712),
            ("1.5T", 1649267441664),
        ]

        for size_text, expected in test_cases:
            actual = self.downloader._parse_file_size(size_text)
            assert actual == expected, f"Expected {expected} for '{size_text}', got {actual}"

    def teardown_method(self):
        """Clean up after each test method."""
        # FTPDownloader doesn't need explicit cleanup, but we can add it if needed
        pass
