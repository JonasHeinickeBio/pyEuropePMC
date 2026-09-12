"""
FTP Downloader for Europe PMC Open Access PDFs.

This module provides functionality to query, download, and extract
open access PDFs from the Europe PMC FTP server.
"""

import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin
import zipfile

from bs4 import BeautifulSoup, Tag
import requests

from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import FullTextError

logger = logging.getLogger(__name__)


class FTPDownloader(BaseAPIClient):
    """
    Downloader for open access PDFs from Europe PMC FTP server.

    This class provides methods to:
    - Query available PDF directories
    - Download ZIP files containing PDFs
    - Extract and organize downloaded PDFs
    """

    BASE_FTP_URL = "https://europepmc.org/ftp/pdf/"

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the FTP downloader.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests to be respectful to the server (default 1.0).
        """
        super().__init__(rate_limit_delay=rate_limit_delay)

    def _get_ftp_url(self, url: str, stream: bool = False) -> requests.Response:
        """
        Direct GET request for FTP URLs without API base URL prefix.

        Parameters
        ----------
        url : str
            Full URL to request
        stream : bool, optional
            Whether to stream the response (default False)

        Returns
        -------
        requests.Response
            The HTTP response

        Raises
        ------
        FullTextError
            If the request fails
        """
        if self.session is None:
            context = {"url": url, "error": "Session is None"}
            raise FullTextError(ErrorCodes.FULL005, context)

        try:
            logger.debug(f"FTP GET request to {url} with stream={stream}")
            response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT, stream=stream)
            response.raise_for_status()
            logger.info(f"FTP GET request to {url} succeeded with status {response.status_code}")
            return response
        except requests.RequestException as e:
            context = {"url": url, "error": str(e)}
            logger.error(f"FTP GET request to {url} failed: {e}")
            raise FullTextError(ErrorCodes.FULL005, context) from e

    def get_available_directories(self) -> list[str]:
        """
        Get list of available PDF directories from the FTP server.

        Returns
        -------
        List[str]
            List of directory names (e.g., ['PMCxxxx000', 'PMCxxxx001', ...])

        Raises
        ------
        FullTextError
            If unable to fetch or parse the directory listing
        """
        try:
            response = self._get_ftp_url(self.BASE_FTP_URL)
            if not response or response.status_code != 200:
                context = {
                    "url": self.BASE_FTP_URL,
                    "status_code": response.status_code if response else None,
                }
                raise FullTextError(ErrorCodes.FULL005, context)

            soup = BeautifulSoup(response.text, "html.parser")
            directories = []

            # Parse directory listing from HTML
            for link in soup.find_all("a"):
                if isinstance(link, Tag):
                    href = link.get("href", "")
                    if isinstance(href, str) and href.startswith("PMCxxxx") and href.endswith("/"):
                        directories.append(href.rstrip("/"))

            logger.info(f"Found {len(directories)} directories")
            return sorted(directories)

        except Exception as e:
            context = {"url": self.BASE_FTP_URL, "error": str(e)}
            raise FullTextError(ErrorCodes.FULL005, context) from e

    def get_zip_files_in_directory(self, directory: str) -> list[dict[str, str | int]]:
        """
        Get list of ZIP files in a specific directory.

        Parameters
        ----------
        directory : str
            Directory name (e.g., 'PMCxxxx1200')

        Returns
        -------
        List[Dict[str, Union[str, int]]]
            List of dictionaries with zip file information:
            [{'filename': 'PMC11691200.zip', 'size': 289000, 'pmcid': '11691200'}, ...]

        Raises
        ------
        FullTextError
            If unable to fetch or parse the directory listing
        """
        directory_url = urljoin(self.BASE_FTP_URL, f"{directory}/")

        try:
            response = self._get_ftp_url(directory_url)
            if not response or response.status_code != 200:
                context = {
                    "url": directory_url,
                    "status_code": response.status_code if response else None,
                }
                raise FullTextError(ErrorCodes.FULL005, context)

            soup = BeautifulSoup(response.text, "html.parser")
            zip_files = []

            # Parse ZIP file listing from HTML
            for row in soup.find_all("tr"):
                if not isinstance(row, Tag):
                    continue

                zip_info = self._parse_zip_file_row(row, directory)
                if zip_info:
                    zip_files.append(zip_info)

            logger.info(f"Found {len(zip_files)} ZIP files in {directory}")
            return zip_files

        except Exception as e:
            context = {"url": directory_url, "error": str(e)}
            raise FullTextError(ErrorCodes.FULL005, context) from e

    def _parse_zip_file_row(self, row: Tag, directory: str) -> dict[str, str | int] | None:
        """Parse a single table row for ZIP file information."""
        cells = row.find_all("td")
        if len(cells) < 3:
            return None

        filename = self._extract_filename_from_cells(cells)
        if not filename or not filename.endswith(".zip") or not filename.startswith("PMC"):
            return None

        pmcid = self._extract_pmcid_from_filename(filename)
        if not pmcid:
            return None

        size_bytes = self._extract_file_size_from_cells(cells)

        return {
            "filename": filename,
            "pmcid": pmcid,
            "size": size_bytes,
            "directory": directory,
        }

    def _extract_filename_from_cells(self, cells: list[Tag]) -> str | None:
        """Extract filename from table cells, trying different positions."""
        # Try first cell
        filename = self._get_link_href(cells[0])
        if filename:
            return filename

        # Try second cell if first failed
        if len(cells) > 1:
            filename = self._get_link_href(cells[1])
            if filename:
                return filename

        return None

    def _get_link_href(self, cell: Tag) -> str | None:
        """Extract href from the first link in a cell."""
        if not isinstance(cell, Tag):
            return None

        link_element = cell.find("a")
        if not isinstance(link_element, Tag):
            return None

        href = link_element.get("href")
        return href if isinstance(href, str) else None

    def _extract_pmcid_from_filename(self, filename: str) -> str | None:
        """Extract PMC ID from filename like 'PMC11691200.zip'."""
        pmcid_match = re.search(r"PMC(\d+)\.zip", filename)
        return pmcid_match.group(1) if pmcid_match else None

    def _extract_file_size_from_cells(self, cells: list[Tag]) -> int:
        """Extract file size from any of the table cells."""
        for cell in cells:
            if isinstance(cell, Tag):
                size_text = cell.get_text(strip=True)
                if size_text and size_text != "-":
                    parsed_size = self._parse_file_size(size_text)
                    if parsed_size > 0:
                        return parsed_size
        return 0

    def query_pmcids_in_ftp(
        self, pmcids: list[str], max_directories: int = 100
    ) -> dict[str, dict[str, str | int] | None]:
        """
        Query which of the given PMC IDs are available in the FTP server.

        Parameters
        ----------
        pmcids : List[str]
            List of PMC IDs to search for (without PMC prefix)
        max_directories : int, optional
            Maximum number of directories to check before giving up (default: 100)

        Returns
        -------
        Dict[str, Optional[Dict[str, Union[str, int]]]]
            Dictionary mapping PMC ID to file info (or None if not found)

        Example
        -------
        >>> downloader = FTPDownloader()
        >>> result = downloader.query_pmcids_in_ftp(['11691200', '11861200'])
        >>> print(result)
        {'11691200': {'filename': 'PMC11691200.zip', 'directory': 'PMCxxxx1200', ...},
         '11861200': {'filename': 'PMC11861200.zip', 'directory': 'PMCxxxx1200', ...}}
        """
        # Determine which directories to check based on PMC IDs
        try:
            directories_to_check = self._get_relevant_directories(pmcids)
        except FullTextError as e:
            logger.error(f"Failed to get directory list: {e}")
            # Return empty results if we can't get directories
            return {pmcid: None for pmcid in pmcids}

        result = self._initialize_result_dict(pmcids)
        directories_list = self._prepare_directories_list(directories_to_check, pmcids)

        search_stats = self._search_directories_for_pmcids(
            directories_list, pmcids, result, max_directories
        )

        logger.info(
            f"Search completed: found {search_stats['found_count']}/{len(pmcids)} PMC IDs "
            f"in {search_stats['directories_checked']} directories"
        )
        return result

    def _initialize_result_dict(self, pmcids: list[str]) -> dict[str, dict[str, str | int] | None]:
        """Initialize result dictionary with None values for all PMC IDs."""
        return {pmcid: None for pmcid in pmcids}

    def _prepare_directories_list(
        self, directories_to_check: set[str], pmcids: list[str]
    ) -> list[str]:
        """Convert directories set to sorted list prioritizing exact matches."""
        directories_list = list(directories_to_check)
        directories_list.sort(key=lambda d: self._get_directory_priority(d, pmcids))
        return directories_list

    def _get_directory_priority(self, directory: str, pmcids: list[str]) -> int:
        """Get priority score for directory (lower = higher priority)."""
        match = re.search(r"PMCxxxx(\d{4})", directory)
        if not match:
            return 9999  # Low priority for non-standard names

        dir_suffix = match.group(1)

        # Check if any PMC ID would map to this directory
        for pmcid in pmcids:
            if len(pmcid) >= 4 and pmcid[-4:] == dir_suffix:
                return 0  # High priority for exact match

        return 1  # Medium priority for nearby directories

    def _search_directories_for_pmcids(
        self,
        directories_list: list[str],
        pmcids: list[str],
        result: dict[str, dict[str, str | int] | None],
        max_directories: int,
    ) -> dict[str, int]:
        """Search directories for PMC IDs and return search statistics."""
        directories_checked = 0
        consecutive_failures = 0
        max_consecutive_failures = 10
        found_count = 0

        for directory in directories_list:
            if directories_checked >= max_directories:
                logger.warning(
                    f"Reached maximum directory limit ({max_directories}), stopping search"
                )
                break

            success = self._check_directory_for_pmcids(directory, pmcids, result)
            if success:
                consecutive_failures = 0
                found_count = sum(1 for v in result.values() if v is not None)
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Too many consecutive failures ({consecutive_failures}), stopping search"
                    )
                    break

            directories_checked += 1

        return {"found_count": found_count, "directories_checked": directories_checked}

    def _check_directory_for_pmcids(
        self, directory: str, pmcids: list[str], result: dict[str, dict[str, str | int] | None]
    ) -> bool:
        """Check a single directory for PMC IDs. Returns True if successful."""
        try:
            zip_files = self.get_zip_files_in_directory(directory)

            for zip_info in zip_files:
                pmcid = str(zip_info["pmcid"])
                if pmcid in pmcids and result[pmcid] is None:
                    # Only update if we haven't found this PMC ID yet
                    result[pmcid] = zip_info
                    logger.info(f"Found PMC{pmcid} in {directory}")

            return True

        except FullTextError as e:
            logger.warning(f"Failed to check directory {directory}: {e}")
            return False

    def download_pdf_zip(self, zip_info: dict[str, str | int], output_dir: str | Path) -> Path:
        """
        Download a ZIP file containing PDFs.

        Parameters
        ----------
        zip_info : Dict[str, Union[str, int]]
            ZIP file information from get_zip_files_in_directory()
        output_dir : Union[str, Path]
            Directory to save the downloaded ZIP file

        Returns
        -------
        Path
            Path to the downloaded ZIP file

        Raises
        ------
        FullTextError
            If download fails
        TypeError
            If zip_info is not a dictionary or missing required keys
        """
        # INPUT VALIDATION - Prevents "string indices must be integers" error
        if not isinstance(zip_info, dict):
            raise TypeError(f"zip_info must be a dictionary, got {type(zip_info).__name__}")

        required_keys = ["filename", "directory", "pmcid", "size"]
        missing_keys = [key for key in required_keys if key not in zip_info]

        if missing_keys:
            raise TypeError(f"zip_info missing required keys: {missing_keys}")

        # Validate key types
        if not isinstance(zip_info["filename"], str):
            raise TypeError(f"filename must be string, got {type(zip_info['filename'])}")

        if not isinstance(zip_info["directory"], str):
            raise TypeError(f"directory must be string, got {type(zip_info['directory'])}")

        # END INPUT VALIDATION

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = zip_info["filename"]
        directory = zip_info["directory"]

        download_url = urljoin(self.BASE_FTP_URL, f"{directory}/{filename}")
        output_path = output_dir / filename

        try:
            logger.info(f"Downloading {filename} from {download_url}")
            response = self._get_ftp_url(download_url, stream=True)

            if not response or response.status_code != 200:
                context = {
                    "url": download_url,
                    "status_code": response.status_code if response else None,
                }
                raise FullTextError(ErrorCodes.FULL005, context)

            # Download with progress
            downloaded_size = 0

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

            logger.info(f"Downloaded {filename} ({downloaded_size} bytes)")
            return output_path

        except Exception as e:
            context = {"url": download_url, "filename": filename, "error": str(e)}
            raise FullTextError(ErrorCodes.FULL005, context) from e

    def extract_pdf_from_zip(
        self, zip_path: Path, extract_dir: str | Path, keep_zip: bool = True
    ) -> list[Path]:
        """
        Extract PDF files from a downloaded ZIP file.

        Parameters
        ----------
        zip_path : Path
            Path to the ZIP file
        extract_dir : Union[str, Path]
            Directory to extract PDFs to
        keep_zip : bool, optional
            Whether to keep the ZIP file after extraction (default True)

        Returns
        -------
        List[Path]
            List of paths to extracted PDF files

        Raises
        ------
        FullTextError
            If extraction fails
        """
        extract_dir = Path(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        extracted_files = []

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for file_info in zip_ref.infolist():
                    if file_info.filename.endswith(".pdf"):
                        # Extract to extract_dir
                        extracted_path = extract_dir / file_info.filename
                        with (
                            zip_ref.open(file_info) as source,
                            open(extracted_path, "wb") as target,
                        ):
                            target.write(source.read())
                        extracted_files.append(extracted_path)
                        logger.info(f"Extracted {file_info.filename}")

            if not keep_zip:
                zip_path.unlink()
                logger.info(f"Removed ZIP file {zip_path}")

            return extracted_files

        except Exception as e:
            context = {"zip_path": str(zip_path), "error": str(e)}
            raise FullTextError(ErrorCodes.FULL005, context) from e

    def bulk_download_and_extract(
        self,
        pmcids: list[str],
        output_dir: str | Path,
        extract_pdfs: bool = True,
        keep_zips: bool = False,
        max_concurrent: int = 3,
    ) -> dict[str, dict[str, Any]]:
        """
        Bulk download and extract PDFs for multiple PMC IDs.

        Parameters
        ----------
        pmcids : List[str]
            List of PMC IDs to download
        output_dir : Union[str, Path]
            Base output directory
        extract_pdfs : bool, optional
            Whether to extract PDFs from ZIP files (default True)
        keep_zips : bool, optional
            Whether to keep ZIP files after extraction (default False)
        max_concurrent : int, optional
            Maximum concurrent downloads (default 3)

        Returns
        -------
        Dict[str, Dict[str, Union[Path, List[Path], str]]]
            Results for each PMC ID with status, paths, etc.

        Example
        -------
        >>> downloader = FTPDownloader()
        >>> results = downloader.bulk_download_and_extract(['11691200', '11861200'], './downloads')
        >>> print(results)
        {'11691200': {'status': 'success', 'zip_path': Path('...'), 'pdf_paths': [Path('...')]},
         '11861200': {'status': 'not_found', 'error': 'PMC ID not found in FTP'}}
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Query which PMC IDs are available
        logger.info(f"Querying {len(pmcids)} PMC IDs in FTP server")
        available_files = self.query_pmcids_in_ftp(pmcids)

        results: dict[str, dict[str, Any]] = {}

        for pmcid in pmcids:
            zip_info = available_files.get(pmcid)

            if not zip_info:
                results[pmcid] = {"status": "not_found", "error": "PMC ID not found in FTP"}
                continue

            try:
                # Download ZIP file
                zip_path = self.download_pdf_zip(zip_info, output_dir)

                result_data: dict[str, Any] = {"status": "success", "zip_path": zip_path}

                # Extract PDFs if requested
                if extract_pdfs:
                    pdf_paths = self.extract_pdf_from_zip(
                        zip_path, output_dir / "extracted", keep_zip=keep_zips
                    )
                    result_data["pdf_paths"] = pdf_paths

                results[pmcid] = result_data

            except FullTextError as e:
                results[pmcid] = {"status": "error", "error": str(e)}
                logger.error(f"Failed to download PMC{pmcid}: {e}")

        return results

    def _get_relevant_directories(self, pmcids: list[str]) -> set[str]:
        """
        Determine which directories might contain the given PMC IDs.

        Always checks BOTH 3-digit and 4-digit patterns since the directory
        structure is not consistently predictable from PMC ID value alone.
        """
        directories: set[str] = set()

        for pmcid in pmcids:
            self._add_directories_for_pmcid(directories, pmcid)

        # If we couldn't determine any specific directories, fall back to getting all available
        if not directories:
            return self._get_fallback_directories()

        logger.info(f"Searching in targeted directories: {sorted(directories)}")
        return directories

    def _add_directories_for_pmcid(self, directories: set[str], pmcid: str) -> None:
        """Add relevant directories for a single PMC ID."""
        try:
            # Always check BOTH patterns regardless of PMC ID value
            if len(pmcid) >= 3:
                self._add_three_digit_patterns(directories, pmcid)

            if len(pmcid) >= 4:
                self._add_four_digit_patterns(directories, pmcid)

        except ValueError:
            logger.warning(f"PMC ID {pmcid} is not a valid integer: {pmcid}")

    def _add_three_digit_patterns(self, directories: set[str], pmcid: str) -> None:
        """Add 3-digit directory patterns for a PMC ID."""
        last_three = pmcid[-3:]
        last_three_int = int(last_three)

        # Add 3-digit pattern
        directories.add(f"PMCxxxx{last_three_int:03d}")

        # Also check nearby directories (±1) for 3-digit pattern
        for offset in [-1, 1]:
            adjusted = last_three_int + offset
            if 0 <= adjusted <= 999:
                directories.add(f"PMCxxxx{adjusted:03d}")

    def _add_four_digit_patterns(self, directories: set[str], pmcid: str) -> None:
        """Add 4-digit directory patterns for a PMC ID."""
        last_four = pmcid[-4:]
        last_four_int = int(last_four)

        # Add 4-digit pattern if within reasonable range
        if 1000 <= last_four_int <= 1200:
            directories.add(f"PMCxxxx{last_four_int}")

            # Also check nearby directories (±1) for 4-digit pattern
            for offset in [-1, 1]:
                adjusted = last_four_int + offset
                if 1000 <= adjusted <= 1200:
                    directories.add(f"PMCxxxx{adjusted}")

    def _get_fallback_directories(self) -> set[str]:
        """Get fallback directories when specific ones can't be determined."""
        try:
            available_dirs = self.get_available_directories()
            logger.info(
                f"Falling back to all available directories: {len(available_dirs)} directories"
            )
            return set(available_dirs)
        except FullTextError:
            # Final fallback to the known directory range
            logger.info("Falling back to known directory range: PMCxxxx0 to PMCxxxx1200")
            directories: set[str] = set()
            # Add directories for PMC IDs 0-999 (last 3 digits)
            for i in range(1000):
                directories.add(f"PMCxxxx{i}")
            # Add directories for PMC IDs 1000-1200 (last 4 digits)
            for i in range(1000, 1201):
                directories.add(f"PMCxxxx{i}")
            return directories

    def _parse_file_size(self, size_text: str) -> int:
        """
        Parse file size string (e.g., '289K', '2.8M') to bytes.

        Parameters
        ----------
        size_text : str
            Size string from directory listing

        Returns
        -------
        int
            Size in bytes
        """
        if not size_text or size_text == "-":
            return 0

        size_text = size_text.strip().upper()

        # Skip date/time patterns
        if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|\b(19|20)\d{2}\b", size_text):
            return 0

        # Extract number and unit - must end with size unit or be a pure number at end of string
        match = re.match(r"^([0-9.]+)([KMGT])$", size_text)
        if not match:
            # Also accept pure numbers (bytes) but only if they look like reasonable file sizes
            pure_number_match = re.match(r"^([0-9]+)$", size_text)
            if pure_number_match:
                pure_number = int(pure_number_match.group(1))
                # Accept numbers that look like reasonable file sizes (not years like 2024)
                if 100 <= pure_number <= 999999999:  # Between 100 bytes and ~1GB in bytes
                    return pure_number
            return 0

        number = float(match.group(1))
        unit = match.group(2)

        multipliers = {
            "K": 1024,
            "M": 1024 * 1024,
            "G": 1024 * 1024 * 1024,
            "T": 1024 * 1024 * 1024 * 1024,
        }

        return int(number * multipliers.get(unit, 1))
