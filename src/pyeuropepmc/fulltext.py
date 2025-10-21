"""
Full text client for Europe PMC API.

This module provides functionality to download and access full text content
from Europe PMC, including PDF, XML, and HTML formats.
"""

from collections.abc import Callable
import gzip
from io import BytesIO
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any
from urllib.parse import urljoin
import zipfile

import requests

from pyeuropepmc.base import APIClientError, BaseAPIClient
from pyeuropepmc.cache import CacheBackend, CacheConfig
from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import FullTextError
from pyeuropepmc.utils.helpers import atomic_download, atomic_write

logger = logging.getLogger(__name__)

__all__ = ["FullTextClient", "FullTextError", "ProgressInfo"]


class ProgressInfo:
    """
    Progress information for batch operations.

    Contains comprehensive progress data for tracking batch downloads
    and long-running operations.
    """

    def __init__(
        self,
        total_items: int,
        current_item: int = 0,
        current_pmcid: str | None = None,
        status: str = "starting",
        successful_downloads: int = 0,
        failed_downloads: int = 0,
        cache_hits: int = 0,
        format_type: str = "unknown",
        start_time: float | None = None,
        current_file_size: int = 0,
        total_downloaded_bytes: int = 0,
    ):
        self.total_items = total_items
        self.current_item = current_item
        self.current_pmcid = current_pmcid
        self.status = status
        self.successful_downloads = successful_downloads
        self.failed_downloads = failed_downloads
        self.cache_hits = cache_hits
        self.format_type = format_type
        self.start_time = start_time or time.time()
        self.current_file_size = current_file_size
        self.total_downloaded_bytes = total_downloaded_bytes

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.current_item / self.total_items) * 100

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def estimated_total_time(self) -> float | None:
        """Estimate total time based on current progress."""
        if self.current_item == 0:
            return None
        return (self.elapsed_time / self.current_item) * self.total_items

    @property
    def estimated_remaining_time(self) -> float | None:
        """Estimate remaining time."""
        total_time = self.estimated_total_time
        if total_time is None:
            return None
        return max(0, total_time - self.elapsed_time)

    @property
    def completion_rate(self) -> float:
        """Calculate items completed per second."""
        if self.elapsed_time == 0:
            return 0.0
        return self.current_item / self.elapsed_time

    def to_dict(self) -> dict[str, int | float | str | None]:
        """Convert progress info to dictionary for easy serialization."""
        return {
            "total_items": self.total_items,
            "current_item": self.current_item,
            "current_pmcid": self.current_pmcid,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "successful_downloads": self.successful_downloads,
            "failed_downloads": self.failed_downloads,
            "cache_hits": self.cache_hits,
            "format_type": self.format_type,
            "elapsed_time": self.elapsed_time,
            "estimated_remaining_time": self.estimated_remaining_time,
            "completion_rate": self.completion_rate,
            "current_file_size": self.current_file_size,
            "total_downloaded_bytes": self.total_downloaded_bytes,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"Progress: {self.current_item}/{self.total_items} "
            f"({self.progress_percent:.1f}%) - "
            f"Current: PMC{self.current_pmcid} - "
            f"Status: {self.status}"
        )


class FullTextClient(BaseAPIClient):
    """
    Client for accessing Europe PMC full text content.

    This client provides methods to download and access full text content
    in various formats (PDF, XML, HTML) with proper error handling and
    access permission management.

    Note: Only XML has a direct REST API endpoint. PDF and HTML use different mechanisms:
    - PDF: Uses render endpoint or backend render service
    - HTML: Uses web interface when available
    - XML: Uses REST API endpoint
    """

    # Europe PMC endpoints
    FULLTEXT_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    XML_ENDPOINT = "PMC{pmcid}/fullTextXML"

    # PDF endpoints (no direct API)
    PDF_RENDER_URL = "https://europepmc.org/articles/PMC{pmcid}?pdf=render"
    PDF_BACKEND_URL = (
        "https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmcid}&blobtype=pdf"
    )

    # HTML endpoints (no direct API)
    HTML_ARTICLE_URL_MED = "https://europepmc.org/article/MED/{medid}#free-full-text"
    HTML_ARTICLE_URL_PMC = "https://europepmc.org/article/PMC/{pmcid}#free-full-text"

    # XML bulk download FTP endpoints
    FTP_OA_BASE_URL = "https://europepmc.org/ftp/oa/"
    # Archive naming pattern: PMC{start_id}_{end_id}.xml.gz
    # Archives contain XML files for PMC IDs in the range [start_id, end_id]

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        enable_cache: bool = True,
        cache_dir: str | Path | None = None,
        cache_max_age_days: int = 30,
        verify_cached_files: bool = True,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize the FullTextClient.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay in seconds between requests to avoid hitting API rate limits (default is 1.0).
        enable_cache : bool, optional
            Whether to enable file caching to avoid re-downloading existing files
            (default is True).
        cache_dir : str or Path, optional
            Directory to use for caching downloaded files. If None, uses system temp directory.
        cache_max_age_days : int, optional
            Maximum age in days for cached files before they're considered stale
            (default is 30).
        verify_cached_files : bool, optional
            Whether to verify that cached files are valid and complete (default is True).
        cache_config : CacheConfig, optional
            Configuration for API response caching. If None, response caching is disabled.
            This is separate from file caching which is controlled by enable_cache.
        """
        super().__init__(rate_limit_delay=rate_limit_delay)

        # File cache configuration (for downloaded PDF/XML files)
        self.enable_cache = enable_cache
        self.cache_max_age_days = cache_max_age_days
        self.verify_cached_files = verify_cached_files

        self.cache_dir: Path | None
        if enable_cache:
            if cache_dir is None:
                # Use a subdirectory in the system temp directory
                self.cache_dir = Path(tempfile.gettempdir()) / "pyeuropepmc_cache"
            elif isinstance(cache_dir, Path):
                self.cache_dir = cache_dir
            else:
                self.cache_dir = Path(cache_dir)

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"File cache enabled: {self.cache_dir}")
        else:
            self.cache_dir = None
            self.logger.info("File cache disabled")

        # API response cache (for availability checks and metadata)
        if cache_config is None:
            cache_config = CacheConfig(enabled=False)

        self._cache = CacheBackend(cache_config)
        cache_status = "enabled" if cache_config.enabled else "disabled"
        self.logger.info(f"API response cache {cache_status}")

    def __enter__(self) -> "FullTextClient":
        """Enter the runtime context for the context manager."""
        return self

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        return super().__repr__()

    def _get_cache_path(self, pmcid: str, format_type: str) -> Path | None:
        """
        Get the cache file path for a given PMC ID and format.

        Parameters
        ----------
        pmcid : str
            Normalized PMC ID
        format_type : str
            File format ('pdf', 'xml', 'html')

        Returns
        -------
        Path or None
            Cache file path if caching is enabled, None otherwise
        """
        if not self.enable_cache or not self.cache_dir:
            return None

        # Create format-specific subdirectory
        format_dir = self.cache_dir / format_type
        format_dir.mkdir(exist_ok=True)

        # Generate cache filename
        filename = f"PMC{pmcid}.{format_type}"
        return format_dir / filename

    def _is_cached_file_valid(self, cache_path: Path) -> bool:
        """
        Check if a cached file is valid and not stale.

        Parameters
        ----------
        cache_path : Path
            Path to the cached file

        Returns
        -------
        bool
            True if file is valid and fresh, False otherwise
        """
        if not cache_path.exists():
            return False

        # Check file size (must be non-empty)
        if cache_path.stat().st_size == 0:
            self.logger.warning(f"Cached file is empty: {cache_path}")
            return False

        # Check file age
        file_age_days = (time.time() - cache_path.stat().st_mtime) / (24 * 3600)
        if file_age_days > self.cache_max_age_days:
            self.logger.info(f"Cached file is stale ({file_age_days:.1f} days): {cache_path}")
            return False

        # Additional format-specific validation if enabled
        if self.verify_cached_files:
            return self._verify_file_format(cache_path)

        return True

    def _verify_file_format(self, file_path: Path) -> bool:
        """
        Verify that a cached file has the expected format and is not corrupted.

        Parameters
        ----------
        file_path : Path
            Path to the file to verify

        Returns
        -------
        bool
            True if file appears to be valid, False otherwise
        """
        try:
            suffix = file_path.suffix.lower()

            # Read first few bytes to check file signature
            with open(file_path, "rb") as f:
                header = f.read(10)

            if suffix == ".pdf":
                # PDF files should start with %PDF
                return header.startswith(b"%PDF")
            elif suffix == ".xml":
                # XML files should start with < (possibly with BOM)
                return b"<" in header[:5]
            elif suffix == ".html":
                # HTML files should contain HTML-like content
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read(500).lower()
                    html_tags = ["<html", "<body", "<div", "<p", "doctype"]
                    return any(tag in content for tag in html_tags)

            return True  # Unknown format, assume valid

        except Exception as e:
            self.logger.warning(f"Failed to verify file format: {file_path}: {e}")
            return False

    def _check_cache_for_file(
        self, pmcid: str, format_type: str, output_path: Path | None = None
    ) -> Path | None:
        """
        Check if file exists in cache and copy to output path if needed.

        Parameters
        ----------
        pmcid : str
            Normalized PMC ID
        format_type : str
            File format ('pdf', 'xml', 'html')
        output_path : Path, optional
            Desired output path. If None, returns cache path directly.

        Returns
        -------
        Path or None
            Path to cached file (either cache location or copied to output_path)
        """
        if not self.enable_cache:
            return None

        cache_path = self._get_cache_path(pmcid, format_type)
        if not cache_path or not self._is_cached_file_valid(cache_path):
            return None

        self.logger.info(f"Found valid cached {format_type.upper()} for PMC{pmcid}: {cache_path}")

        # If output_path is specified and different from cache, copy the file
        if output_path and output_path != cache_path:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil

                shutil.copy2(cache_path, output_path)
                self.logger.info(f"Copied cached file to: {output_path}")
                return output_path
            except Exception as e:
                self.logger.warning(f"Failed to copy cached file: {e}")
                return cache_path

        return cache_path

    def _save_to_cache(self, file_path: Path, pmcid: str, format_type: str) -> bool:
        """
        Save a downloaded file to cache.

        Parameters
        ----------
        file_path : Path
            Path to the downloaded file
        pmcid : str
            Normalized PMC ID
        format_type : str
            File format ('pdf', 'xml', 'html')

        Returns
        -------
        bool
            True if successfully cached, False otherwise
        """
        if not self.enable_cache or not file_path.exists():
            return False

        cache_path = self._get_cache_path(pmcid, format_type)
        if not cache_path:
            return False

        try:
            # Don't cache if file is already in cache location
            if file_path.resolve() == cache_path.resolve():
                return True

            # Copy to cache
            import shutil

            shutil.copy2(file_path, cache_path)
            self.logger.info(f"Cached {format_type.upper()} for PMC{pmcid}: {cache_path}")
            return True

        except Exception as e:
            self.logger.warning(f"Failed to cache file: {e}")
            return False

    def clear_cache(self, format_type: str | None = None, max_age_days: int | None = None) -> int:
        """
        Clear cached files based on format and/or age.

        Parameters
        ----------
        format_type : str, optional
            Specific format to clear ('pdf', 'xml', 'html'). If None, clears all formats.
        max_age_days : int, optional
            Clear files older than this many days. If None, uses cache_max_age_days.

        Returns
        -------
        int
            Number of files removed
        """
        if not self.enable_cache or not self.cache_dir:
            return 0

        import time

        max_age = max_age_days if max_age_days is not None else self.cache_max_age_days
        cutoff_time = time.time() - (max_age * 24 * 3600)
        removed_count = 0

        formats_to_clear = [format_type] if format_type else ["pdf", "xml", "html"]

        for fmt in formats_to_clear:
            format_dir = self.cache_dir / fmt
            if not format_dir.exists():
                continue

            for file_path in format_dir.iterdir():
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            removed_count += 1
                            self.logger.debug(f"Removed stale cache file: {file_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove cache file {file_path}: {e}")

        if removed_count > 0:
            self.logger.info(f"Cleared {removed_count} stale cache files")

        return removed_count

    def get_cache_stats(self) -> dict[str, int | str | bool | dict[str, dict[str, int]]]:
        """
        Get statistics about the cache.

        Returns
        -------
        dict
            Cache statistics including file counts and total size
        """
        if not self.enable_cache or not self.cache_dir:
            return {"enabled": False}

        stats: dict[str, int | str | bool | dict[str, dict[str, int]]] = {
            "enabled": True,
            "cache_dir": str(self.cache_dir),
            "total_files": 0,
            "total_size_bytes": 0,
            "formats": {},
        }

        for format_type in ["pdf", "xml", "html"]:
            format_dir = self.cache_dir / format_type
            if format_dir.exists():
                files = list(format_dir.glob(f"*.{format_type}"))
                count = len(files)
                size = sum(f.stat().st_size for f in files if f.is_file())

                # Type casting to ensure mypy understands the types
                formats_dict = stats["formats"]
                if not isinstance(formats_dict, dict):
                    raise TypeError(f"Expected dict for formats, got {type(formats_dict)}")
                formats_dict[format_type] = {"count": count, "size_bytes": size}

                total_files = stats["total_files"]
                if not isinstance(total_files, int):
                    raise TypeError(f"Expected int for total_files, got {type(total_files)}")
                stats["total_files"] = total_files + count

                total_size = stats["total_size_bytes"]
                if not isinstance(total_size, int):
                    raise TypeError(f"Expected int for total_size_bytes, got {type(total_size)}")
                stats["total_size_bytes"] = total_size + size

        return stats

    def get_file_cache_health(self) -> dict[str, Any]:
        """
        Get file cache health status.

        Returns
        -------
        dict
            Health status and metrics for file cache including disk space,
            file age validation, and directory accessibility.

        Example
        -------
        >>> client = FullTextClient(enable_cache=True)
        >>> health = client.get_file_cache_health()
        >>> print(f"Status: {health['status']}")
        """
        health: dict[str, Any] = {
            "enabled": self.enable_cache,
            "status": "unknown",
            "available": False,
            "disk_space_available": True,
            "directory_writable": False,
            "files_within_age_limit": True,
            "warnings": [],
        }

        if not self.enable_cache:
            health["status"] = "disabled"
            return health

        if not self.cache_dir:
            health["status"] = "unavailable"
            health["warnings"].append("Cache directory not set")
            return health

        # Check directory accessibility
        if not self._check_cache_directory_access(health):
            return health

        # Check disk space
        self._check_disk_space(health)

        # Check file ages
        self._check_file_ages(health)

        # Determine overall status
        self._determine_health_status(health)

        return health

    def _check_cache_directory_access(self, health: dict[str, Any]) -> bool:
        """Check if cache directory exists and is writable."""
        if self.cache_dir is None:
            health["status"] = "error"
            health["warnings"].append("Cache directory is not set")
            return False

        try:
            if not self.cache_dir.exists():
                health["status"] = "error"
                health["warnings"].append("Cache directory does not exist")
                return False

            # Check if directory is writable
            test_file = self.cache_dir / ".health_check"
            test_file.write_text("test")
            test_file.unlink()
            health["directory_writable"] = True
            return True
        except (OSError, PermissionError) as e:
            health["status"] = "error"
            health["warnings"].append(f"Cache directory not writable: {e}")
            return False

    def _check_disk_space(self, health: dict[str, Any]) -> None:
        """Check available disk space."""
        if self.cache_dir is None:
            health["warnings"].append("Cache directory is not set")
            return

        try:
            stat = os.statvfs(self.cache_dir)
            free_space_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_space_mb < 100:
                health["disk_space_available"] = False
                health["warnings"].append(f"Low disk space: {free_space_mb:.1f}MB available")
        except (OSError, AttributeError):
            # os.statvfs not available on Windows, skip this check
            pass

    def _check_file_ages(self, health: dict[str, Any]) -> None:
        """Check if cached files are within age limits."""
        if self.cache_dir is None:
            health["warnings"].append("Cache directory is not set")
            return

        max_age_seconds = self.cache_max_age_days * 24 * 60 * 60
        current_time = time.time()
        stale_files = []

        for format_type in ["pdf", "xml", "html"]:
            format_dir = self.cache_dir / format_type
            if format_dir.exists():
                for file_path in format_dir.glob(f"*.{format_type}"):
                    if file_path.is_file():
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age > max_age_seconds:
                            stale_files.append(str(file_path))

        if stale_files:
            health["files_within_age_limit"] = False
            health["warnings"].append(f"Found {len(stale_files)} stale files")

    def _determine_health_status(self, health: dict[str, Any]) -> None:
        """Determine overall health status based on checks."""
        try:
            health["available"] = True
            if not health["warnings"]:
                health["status"] = "healthy"
                return

            if any("not writable" in w or "does not exist" in w for w in health["warnings"]):
                health["status"] = "error"
            elif not health["disk_space_available"]:
                health["status"] = "critical"
            else:
                health["status"] = "warning"
        except Exception as e:
            health["status"] = "error"
            health["warnings"].append(f"Health check failed: {e}")
            self.logger.error(f"File cache health check error: {e}")

    def _validate_pmcid(self, pmcid: str) -> str:
        """
        Validate and normalize PMC ID.

        Parameters
        ----------
        pmcid : str
            PMC ID to validate

        Returns
        -------
        str
            Normalized PMC ID

        Raises
        ------
        FullTextError
            If PMC ID is invalid
        """
        self.logger.debug(f"Validating PMC ID: {pmcid}")
        if not pmcid:
            self.logger.error("PMC ID cannot be empty")
            raise FullTextError(ErrorCodes.FULL001, pmcid=pmcid, operation="validation")

        # Remove PMC prefix if present and normalize
        pmcid = str(pmcid).strip()
        if pmcid.upper().startswith("PMC"):
            pmcid = pmcid[3:]

        # Validate that remaining part is numeric
        if not pmcid.isdigit():
            self.logger.error(f"Invalid PMC ID format: {pmcid}")
            raise FullTextError(ErrorCodes.FULL002, pmcid=pmcid, operation="validation")

        self.logger.debug(f"Normalized PMC ID: {pmcid}")
        return pmcid

    def _get_fulltext_url(self, pmcid: str, format_type: str) -> str:
        """
        Construct full text URL for given PMC ID and format.

        Note: Only XML has a direct REST API endpoint.
        PDF and HTML use different mechanisms and are handled separately.

        Parameters
        ----------
        pmcid : str
            PMC ID (without PMC prefix)
        format_type : str
            Format type ('xml' only for this method)

        Returns
        -------
        str
            Full URL for the requested content

        Raises
        ------
        FullTextError
            If format_type is not 'xml'
        """
        self.logger.debug(f"Constructing fulltext URL for PMC ID: {pmcid}, format: {format_type}")

        if format_type == "xml":
            endpoint = self.XML_ENDPOINT.format(pmcid=pmcid)
            url = urljoin(self.FULLTEXT_BASE_URL, endpoint)
            self.logger.debug(f"Constructed XML URL: {url}")
            return url
        else:
            # PDF and HTML don't use the REST API - they have separate methods
            raise FullTextError(
                ErrorCodes.FULL011,
                context={"format_type": format_type},
                format_type=format_type,
                operation="url_construction",
            )

    def check_fulltext_availability(self, pmcid: str) -> dict[str, bool]:
        """
        Check availability of full text formats for a given PMC ID.

        Note:
        - XML availability is checked via REST API
        - PDF availability is checked via render endpoint
        - HTML availability is checked via web interface (both PMC and MED formats supported)

        Parameters
        ----------
        pmcid : str
            PMC ID to check

        Returns
        -------
        Dict[str, bool]
            Dictionary indicating availability of each format

        Raises
        ------
        FullTextError
            If PMC ID is invalid or check fails
        """
        self.logger.info(f"Checking fulltext availability for PMC ID: {pmcid}")
        normalized_pmcid = self._validate_pmcid(pmcid)

        # Check cache first
        cache_key = f"fulltext_availability:{normalized_pmcid}"
        try:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Cache hit for fulltext availability: PMC{normalized_pmcid}")
                return dict(cached_result)
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}. Proceeding with availability check.")

        availability: dict[str, bool] = {"pdf": False, "xml": False, "html": False}

        # Check XML availability via REST API
        try:
            url = self._get_fulltext_url(normalized_pmcid, "xml")
            self.logger.debug(f"HEAD request to {url}")
            if self.session is None:
                raise FullTextError(ErrorCodes.FULL007, operation="availability_check")
            response = self.session.head(url, timeout=self.DEFAULT_TIMEOUT)
            self.logger.debug(f"HEAD response for {url}: {response.status_code}")
            availability["xml"] = response.status_code == 200
        except requests.RequestException as e:
            self.logger.warning(f"Failed to check XML availability for PMC{normalized_pmcid}: {e}")
            availability["xml"] = False

        # Check PDF availability via render endpoint
        try:
            pdf_url = self.PDF_RENDER_URL.format(pmcid=normalized_pmcid)
            self.logger.debug(f"Checking PDF availability at {pdf_url}")
            if self.session is None:
                raise FullTextError(ErrorCodes.FULL007, operation="availability_check")
            # Use HEAD request first for quick check
            response = self.session.head(pdf_url, timeout=5)
            self.logger.debug(f"HEAD response for {pdf_url}: {response.status_code}")
            availability["pdf"] = (
                response.status_code == 200
                and "application/pdf" in response.headers.get("content-type", "")
            )
        except requests.RequestException as e:
            self.logger.warning(f"Failed to check PDF availability for PMC{normalized_pmcid}: {e}")
            availability["pdf"] = False

        # Check HTML availability via web interface
        try:
            html_url = self.HTML_ARTICLE_URL_PMC.format(pmcid=normalized_pmcid)
            self.logger.debug(f"GET request to check HTML at {html_url}")
            if self.session is None:
                raise FullTextError(ErrorCodes.FULL007, operation="availability_check")
            response = self.session.get(html_url, timeout=5, stream=True)
            self.logger.debug(f"GET response for {html_url}: {response.status_code}")
            availability["html"] = response.status_code == 200
        except requests.RequestException as e:
            self.logger.warning(
                f"Failed to check HTML availability for PMC{normalized_pmcid}: {e}"
            )
            availability["html"] = False

        self.logger.info(f"Availability for PMC{normalized_pmcid}: {availability}")

        # Cache the result
        try:
            self._cache.set(cache_key, availability, tag="fulltext_availability")
        except Exception as e:
            self.logger.warning(f"Failed to cache fulltext availability: {e}")

        return availability

    def _handle_pdf_http_error(self, e: requests.HTTPError, pmcid: str) -> None:
        """Handle HTTP errors during PDF download."""
        self.logger.error(f"HTTP error during PDF download for PMC{pmcid}: {e}")
        if e.response.status_code == 404:
            raise FullTextError(
                ErrorCodes.FULL003,
                context={"status_code": e.response.status_code, "pmcid": pmcid},
                message=f"PDF not found for PMC{pmcid}",
                pmcid=pmcid,
                format_type="pdf",
                operation="download",
            )
        elif e.response.status_code == 403:
            raise FullTextError(
                ErrorCodes.FULL008,
                context={"status_code": e.response.status_code, "pmcid": pmcid},
                message=f"Access denied for PMC{pmcid}",
                pmcid=pmcid,
                format_type="pdf",
                operation="download",
            )
        else:
            raise FullTextError(
                ErrorCodes.FULL005,
                context={"status_code": e.response.status_code, "error": str(e), "pmcid": pmcid},
                message=(
                    f"HTTP error {e.response.status_code} while downloading PDF for PMC{pmcid}"
                ),
                pmcid=pmcid,
                format_type="pdf",
                operation="download",
            )

    def download_pdf_by_pmcid(
        self, pmcid: str, output_path: str | Path | None = None
    ) -> Path | None:
        """
        Download PDF of a paper from Europe PMC using its PMC ID.

        Uses caching to avoid re-downloading existing files. Tries multiple PDF endpoints
        in order and validates downloaded content:
        1. Check cache for existing valid file
        2. Europe PMC render endpoint (?pdf=render)
        3. Backend render service (ptpmcrender.fcgi)
        4. ZIP archive from OA collection

        Parameters
        ----------
        pmcid : str
            PMC ID of the paper (with or without 'PMC' prefix)
        output_path : str or Path, optional
            Path where to save the PDF file

        Returns
        -------
        Path or None
            Path to downloaded PDF file if successful and valid, None if failed

        Raises
        ------
        FullTextError
            If PMC ID is invalid
        """
        normalized_pmcid = self._validate_pmcid(pmcid)
        if output_path is None:
            output_path = Path(f"PMC{normalized_pmcid}.pdf")
        else:
            output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Starting PDF download for PMC{normalized_pmcid}")

        # Check cache first
        cached_file = self._check_cache_for_file(normalized_pmcid, "pdf", output_path)
        if cached_file:
            self.logger.info(f"Using cached PDF for PMC{normalized_pmcid}")
            return cached_file

        # 1. Try the ?pdf=render endpoint
        render_url = self.PDF_RENDER_URL.format(pmcid=normalized_pmcid)
        if self._try_pdf_endpoint(render_url, output_path, "render endpoint"):
            self._save_to_cache(output_path, normalized_pmcid, "pdf")
            return output_path

        # 2. Try the backend render service
        backend_url = self.PDF_BACKEND_URL.format(pmcid=normalized_pmcid)
        if self._try_pdf_endpoint(backend_url, output_path, "backend service"):
            self._save_to_cache(output_path, normalized_pmcid, "pdf")
            return output_path

        # 3. Try the ZIP archive (Europe PMC OA bulk)
        if self._try_pdf_from_zip(normalized_pmcid, output_path):
            self._save_to_cache(output_path, normalized_pmcid, "pdf")
            return output_path

        self.logger.error(f"PDF not available or invalid for PMC{normalized_pmcid}")
        return None

    def download_xml_by_pmcid(
        self, pmcid: str, output_path: str | Path | None = None
    ) -> Path | None:
        """
        Download XML full text of a paper from Europe PMC using its PMC ID.

        Uses caching to avoid re-downloading existing files. This method first checks
        the cache, then tries the REST API endpoint, and if that fails, falls back to
        bulk download from Europe PMC FTP OA archives.

        Parameters
        ----------
        pmcid : str
            PMC ID of the paper (with or without 'PMC' prefix)
        output_path : str or Path, optional
            Path where to save the XML file. If None, saves to current directory
            with filename 'PMC{pmcid}.xml'

        Returns
        -------
        Path or None
            Path to downloaded XML file if successful, None if failed

        Raises
        ------
        FullTextError
            If PMC ID is invalid, XML not available via REST API or bulk FTP,
            or download fails
        """
        self.logger.info(f"Starting XML download for PMC ID: {pmcid}")
        normalized_pmcid = self._validate_pmcid(pmcid)

        # Determine output path
        if output_path is None:
            output_path = Path(f"PMC{normalized_pmcid}.xml")
        else:
            output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check cache first
        cached_file = self._check_cache_for_file(normalized_pmcid, "xml", output_path)
        if cached_file:
            self.logger.info(f"Using cached XML for PMC{normalized_pmcid}")
            return cached_file

        # Try REST API first
        rest_result = self._try_xml_rest_api(normalized_pmcid, output_path)
        if rest_result:
            self._save_to_cache(output_path, normalized_pmcid, "xml")
            return output_path

        # Fall back to bulk download
        bulk_result = self._try_bulk_xml_download(normalized_pmcid, output_path)
        if bulk_result:
            self._save_to_cache(output_path, normalized_pmcid, "xml")
            return output_path

        # All methods failed
        raise FullTextError(
            ErrorCodes.FULL003,
            context={"all_methods_failed": True},
            pmcid=normalized_pmcid,
        )

    def _try_xml_rest_api(self, normalized_pmcid: str, output_path: Path) -> bool:
        """
        Try to download XML using REST API.

        Parameters
        ----------
        normalized_pmcid : str
            Normalized PMC ID
        output_path : Path
            Output file path

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Downloading XML for PMC{normalized_pmcid}")

            # Use the correct endpoint format: PMC{id}/fullTextXML
            endpoint = f"PMC{normalized_pmcid}/fullTextXML"
            response = self._get(endpoint)
            self.logger.debug(f"XML download response headers: {response.headers}")

            # Write XML content to file using atomic write
            with atomic_write(output_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            self.logger.info(f"Successfully downloaded XML to {output_path}")
            return True

        except APIClientError as e:
            self._handle_xml_rest_api_error(e, normalized_pmcid)
            return False
        except requests.RequestException as e:
            self._handle_xml_network_error(e, normalized_pmcid)
            return False
        except OSError as e:
            self._handle_xml_io_error(e, normalized_pmcid)
            return False

    def _handle_xml_rest_api_error(self, e: APIClientError, normalized_pmcid: str) -> None:
        """Handle REST API errors during XML download."""
        error_msg = str(e)
        self.logger.warning(f"REST API failed for PMC{normalized_pmcid}: {error_msg}")

    def _handle_xml_network_error(
        self, e: requests.RequestException, normalized_pmcid: str
    ) -> None:
        """Handle network errors during XML download."""
        error_msg = f"Network error while downloading XML for PMC{normalized_pmcid}: {e}"
        self.logger.warning(error_msg)

    def _handle_xml_io_error(self, e: IOError, normalized_pmcid: str) -> None:
        """Handle I/O errors during XML download."""
        self.logger.error(f"File system error while saving XML for PMC{normalized_pmcid}: {e}")
        raise FullTextError(
            ErrorCodes.FULL009, context={"error_details": str(e)}, pmcid=normalized_pmcid
        )

    def download_xml_by_pmcid_bulk(
        self, pmcid: str, output_path: str | Path | None = None
    ) -> Path | None:
        """
        Download XML full text from Europe PMC FTP OA bulk archives only.

        This method downloads from the Europe PMC FTP OA archives (.xml.gz files)
        without trying the REST API first. Useful when you specifically want to
        use the bulk download method or when the REST API is unavailable.

        Parameters
        ----------
        pmcid : str
            PMC ID of the paper (with or without 'PMC' prefix)
        output_path : str or Path, optional
            Path where to save the XML file. If None, saves to current directory
            with filename 'PMC{pmcid}.xml'

        Returns
        -------
        Path or None
            Path to downloaded XML file if successful, None if failed

        Raises
        ------
        FullTextError
            If PMC ID is invalid or XML not available in bulk archives
        """
        self.logger.info(f"Starting bulk XML download for PMC ID: {pmcid}")
        normalized_pmcid = self._validate_pmcid(pmcid)

        # Determine output path
        if output_path is None:
            output_path = Path(f"PMC{normalized_pmcid}.xml")
        else:
            output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._try_bulk_xml_download(normalized_pmcid, output_path):
            return output_path
        else:
            raise FullTextError(
                ErrorCodes.FULL003,
                context={"details": "Not found in bulk FTP archives"},
                pmcid=normalized_pmcid,
            )

    def get_fulltext_content(self, pmcid: str, format_type: str = "xml") -> str:
        """
        Get full text content as string (for XML/HTML formats).

        Parameters
        ----------
        pmcid : str
            PMC ID of the paper
        format_type : str, optional
            Format type ('xml' or 'html', default is 'xml')

        Returns
        -------
        str
            Full text content as string

        Raises
        ------
        FullTextError
            If PMC ID is invalid, content not available, or retrieval fails
        """
        self.logger.info(f"Retrieving fulltext content for PMC ID: {pmcid}, format: {format_type}")
        if format_type not in ["xml", "html"]:
            raise FullTextError(
                ErrorCodes.FULL004,
                context={"provided_format": format_type},
                format_type=format_type,
            )

        normalized_pmcid = self._validate_pmcid(pmcid)

        try:
            # Use the correct endpoint format: PMC{id}/fullText{FORMAT}
            endpoint = f"PMC{normalized_pmcid}/fullText{format_type.upper()}"
            self.logger.info(f"Retrieving {format_type.upper()} content for PMC{normalized_pmcid}")

            response = self._get(endpoint)
            self.logger.debug(f"Fulltext content response headers: {response.headers}")
            return str(response.text)
        except requests.HTTPError as e:
            self.logger.error(
                f"HTTP error while retrieving {format_type.upper()} for PMC{normalized_pmcid}: {e}"
            )
            if e.response.status_code == 404:
                raise FullTextError(
                    ErrorCodes.FULL003, pmcid=normalized_pmcid, format_type=format_type
                ) from e
            elif e.response.status_code == 403:
                raise FullTextError(ErrorCodes.FULL008, pmcid=normalized_pmcid) from e
            else:
                raise FullTextError(
                    ErrorCodes.FULL005,
                    context={"status_code": e.response.status_code, "error": str(e)},
                    pmcid=normalized_pmcid,
                    format_type=format_type,
                ) from e
        except requests.RequestException as e:
            self.logger.error(
                f"Network error while retrieving {format_type.upper()} for "
                f"PMC{normalized_pmcid}: {e}"
            )
            raise FullTextError(
                ErrorCodes.FULL005,
                context={"error": str(e)},
                pmcid=normalized_pmcid,
                format_type=format_type,
            ) from e

    def _process_batch_download_item(
        self,
        pmcid: str,
        format_type: str,
        output_dir: Path,
        progress: ProgressInfo,
        skip_errors: bool,
    ) -> Path | None:
        """
        Process a single item in batch download with progress tracking.

        Parameters
        ----------
        pmcid : str
            PMC ID to download
        format_type : str
            Format type ('pdf', 'xml', 'html')
        output_dir : Path
            Output directory
        progress : ProgressInfo
            Progress tracking object
        skip_errors : bool
            Whether to skip errors or raise them

        Returns
        -------
        Path or None
            Path to downloaded file or None if failed
        """
        try:
            self.logger.debug(f"Processing batch download for PMC ID: {pmcid}")
            normalized_pmcid = self._validate_pmcid(pmcid)

            # Check cache first to update cache hit statistics
            if self.enable_cache:
                cache_path = self._get_cache_path(normalized_pmcid, format_type)
                if cache_path and self._is_cached_file_valid(cache_path):
                    progress.cache_hits += 1

            # Download the file based on format
            result = self._download_single_by_format(
                pmcid, format_type, output_dir, normalized_pmcid
            )

            # Update progress statistics
            self._update_progress_after_download(result, progress, normalized_pmcid, format_type)

            return result

        except FullTextError as e:
            return self._handle_batch_download_error(e, pmcid, format_type, progress, skip_errors)

    def _download_single_by_format(
        self, pmcid: str, format_type: str, output_dir: Path, normalized_pmcid: str
    ) -> Path | None:
        """Download single file by format type."""
        if format_type == "pdf":
            output_path = output_dir / f"PMC{normalized_pmcid}.pdf"
            return self.download_pdf_by_pmcid(pmcid, output_path)
        elif format_type == "xml":
            output_path = output_dir / f"PMC{normalized_pmcid}.xml"
            return self.download_xml_by_pmcid(pmcid, output_path)
        elif format_type == "html":
            output_path = output_dir / f"PMC{normalized_pmcid}.html"
            return self.download_html_by_pmcid(pmcid, output_path)
        else:
            raise FullTextError(
                ErrorCodes.FULL010,
                context={"provided_format": format_type},
                format_type=format_type,
            )

    def _update_progress_after_download(
        self,
        result: Path | None,
        progress: ProgressInfo,
        normalized_pmcid: str,
        format_type: str,
    ) -> None:
        """Update progress statistics after download."""
        if result:
            progress.successful_downloads += 1
            file_size = result.stat().st_size
            progress.current_file_size = file_size
            progress.total_downloaded_bytes += file_size
            progress.status = f"completed PMC{normalized_pmcid}"

            self.logger.info(
                f"Successfully downloaded {format_type.upper()} for PMC{normalized_pmcid}"
            )
        else:
            progress.failed_downloads += 1
            progress.status = f"failed PMC{normalized_pmcid}"

    def _handle_batch_download_error(
        self,
        error: FullTextError,
        pmcid: str,
        format_type: str,
        progress: ProgressInfo,
        skip_errors: bool,
    ) -> Path | None:
        """Handle errors during batch download."""
        progress.failed_downloads += 1
        progress.status = f"error PMC{pmcid}: {str(error)[:50]}..."

        self.logger.error(f"Failed to download {format_type.upper()} for {pmcid}: {error}")
        if skip_errors:
            return None
        else:
            raise error

    def download_fulltext_batch(
        self,
        pmcids: list[str],
        format_type: str = "pdf",
        output_dir: str | Path | None = None,
        skip_errors: bool = True,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
        progress_update_interval: float = 1.0,
    ) -> dict[str, Path | None]:
        """
        Download full text content for multiple PMC IDs with progress tracking.

        Parameters
        ----------
        pmcids : List[str]
            List of PMC IDs to download
        format_type : str, optional
            Format type ('pdf', 'xml', or 'html', default is 'pdf')
        output_dir : str or Path, optional
            Directory to save files. If None, uses current directory
        skip_errors : bool, optional
            If True, continue downloading other files when one fails (default is True)
        progress_callback : callable, optional
            Function to call with progress updates. Receives ProgressInfo object.
        progress_update_interval : float, optional
            Minimum seconds between progress callback calls (default is 1.0)

        Returns
        -------
        Dict[str, Optional[Path]]
            Dictionary mapping PMC IDs to downloaded file paths (or None if failed)

        Raises
        ------
        FullTextError
            If skip_errors is False and any download fails
        """
        self.logger.info(f"Starting batch download for PMC IDs: {pmcids}, format: {format_type}")
        output_dir = Path.cwd() if output_dir is None else Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize progress tracking
        progress = ProgressInfo(total_items=len(pmcids), format_type=format_type)

        last_callback_time = 0.0
        results = {}

        # Initial progress callback
        if progress_callback:
            progress.status = "initialized"
            progress_callback(progress)
            last_callback_time = time.time()

        for i, pmcid in enumerate(pmcids):
            # Update progress
            progress.current_item = i + 1
            progress.current_pmcid = pmcid
            progress.status = f"downloading PMC{pmcid}"

            # Call progress callback if enough time has passed
            current_time = time.time()
            if progress_callback and current_time - last_callback_time >= progress_update_interval:
                progress_callback(progress)
                last_callback_time = current_time

            # Process individual download
            result = self._process_batch_download_item(
                pmcid, format_type, output_dir, progress, skip_errors
            )
            results[pmcid] = result

        # Final progress callback
        if progress_callback:
            progress.status = "completed"
            progress_callback(progress)

        self.logger.info(
            f"Batch download completed: {progress.successful_downloads} successful, "
            f"{progress.failed_downloads} failed, {progress.cache_hits} cache hits"
        )
        return results

    def get_html_article_url(self, pmcid: str, medid: str | None = None) -> str:
        """
        Get HTML article URL for a given PMC ID or MED ID.

        Parameters
        ----------
        pmcid : str
            PMC ID (with or without 'PMC' prefix)
        medid : str, optional
            MED ID if available (takes precedence over PMC ID)

        Returns
        -------
        str
            URL to the HTML article page
        """
        normalized_pmcid = self._validate_pmcid(pmcid)

        if medid:
            return self.HTML_ARTICLE_URL_MED.format(medid=medid)
        else:
            return self.HTML_ARTICLE_URL_PMC.format(pmcid=normalized_pmcid)

    def download_html_by_pmcid(
        self, pmcid: str, output_path: str | Path | None = None
    ) -> Path | None:
        """
        Download HTML full text of a paper from Europe PMC using its PMC ID.

        Uses caching to avoid re-downloading existing files.

        Parameters
        ----------
        pmcid : str
            PMC ID of the paper (with or without 'PMC' prefix)
        output_path : str or Path, optional
            Path where to save the HTML file

        Returns
        -------
        Path or None
            Path to downloaded HTML file if successful, None if failed

        Raises
        ------
        FullTextError
            If PMC ID is invalid or HTML not available
        """
        normalized_pmcid = self._validate_pmcid(pmcid)

        if output_path is None:
            output_path = Path(f"PMC{normalized_pmcid}.html")
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check cache first
        cached_file = self._check_cache_for_file(normalized_pmcid, "html", output_path)
        if cached_file:
            self.logger.info(f"Using cached HTML for PMC{normalized_pmcid}")
            return cached_file

        try:
            html_url = self.get_html_article_url(normalized_pmcid)
            if self.session is None:
                raise FullTextError(ErrorCodes.FULL007, operation="html_download")

            response = self.session.get(html_url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()

            # Write HTML content to file using atomic write
            with atomic_write(output_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            self.logger.info(f"Successfully downloaded HTML to {output_path}")
            self._save_to_cache(output_path, normalized_pmcid, "html")
            return output_path

        except requests.RequestException as e:
            self.logger.error(f"Failed to download HTML for PMC{normalized_pmcid}: {e}")
            return None
        except OSError as e:
            self.logger.error(
                f"File system error while saving HTML for PMC{normalized_pmcid}: {e}"
            )
            raise FullTextError(
                ErrorCodes.FULL009, context={"error_details": str(e)}, pmcid=normalized_pmcid
            ) from e

    def _validate_pdf_content(self, file_path: Path) -> bool:
        """
        Validate that a downloaded file is a valid PDF.

        Parameters
        ----------
        file_path : Path
            Path to the downloaded file

        Returns
        -------
        bool
            True if file is a valid PDF, False otherwise
        """
        try:
            if not file_path.exists() or file_path.stat().st_size < 100:
                self.logger.warning(f"PDF file too small or doesn't exist: {file_path}")
                return False

            # Check PDF header
            with open(file_path, "rb") as f:
                header = f.read(4)
                if header != b"%PDF":
                    self.logger.warning(f"Invalid PDF header in {file_path}: {header!r}")
                    return False

            # Check file size (PDF should be at least a few KB for valid content)
            file_size = file_path.stat().st_size
            if file_size < 1024:  # Less than 1KB is likely not a valid PDF
                self.logger.warning(
                    f"PDF file suspiciously small ({file_size} bytes): {file_path}"
                )
                return False

            self.logger.debug(f"PDF validation passed for {file_path} ({file_size} bytes)")
            return True

        except Exception as e:
            self.logger.error(f"Error validating PDF {file_path}: {e}")
            return False

    def _try_pdf_endpoint(self, url: str, output_path: Path, endpoint_name: str) -> bool:
        """
        Try downloading PDF from a specific endpoint with validation.

        Parameters
        ----------
        url : str
            URL to download from
        output_path : Path
            Where to save the file
        endpoint_name : str
            Name of the endpoint for logging

        Returns
        -------
        bool
            True if download successful and valid, False otherwise
        """
        try:
            self.logger.debug(f"Trying PDF download from {endpoint_name}: {url}")

            # Use atomic download with validation
            success = atomic_download(
                url=url,
                target_path=output_path,
                session_getter=lambda: requests.Session(),
                validator=self._validate_pdf_content,
                content_type_check="application/pdf",
                timeout=15,
            )

            if success:
                self.logger.info(f"Downloaded valid PDF via {endpoint_name}: {output_path}")
                return True
            else:
                self.logger.warning(f"Downloaded invalid PDF from {endpoint_name}, removed file")
                return False

        except requests.RequestException as e:
            self.logger.error(f"Network error downloading from {endpoint_name}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error downloading from {endpoint_name}: {e}")
            return False

    def _try_pdf_from_zip(self, normalized_pmcid: str, output_path: Path) -> bool:
        """
        Try downloading PDF from ZIP archive with validation.

        Parameters
        ----------
        normalized_pmcid : str
            Normalized PMC ID (without PMC prefix)
        output_path : Path
            Where to save the file

        Returns
        -------
        bool
            True if download successful and valid, False otherwise
        """
        try:
            pmc_int = int(normalized_pmcid)
            zip_dir = f"PMC{pmc_int // 1000 * 1000:07d}"
            zip_url = (
                f"https://europepmc.org/pub/databases/pmc/pdf/OA/"
                f"{zip_dir}/PMC{normalized_pmcid}.zip"
            )

            self.logger.debug(f"Trying PDF download from ZIP archive: {zip_url}")
            zip_response = requests.get(zip_url, stream=True, timeout=15)

            if zip_response.status_code != 200:
                self.logger.debug(f"ZIP archive returned status {zip_response.status_code}")
                return False

            with zipfile.ZipFile(BytesIO(zip_response.content)) as zf:
                pdf_names = [name for name in zf.namelist() if name.lower().endswith(".pdf")]
                if not pdf_names:
                    self.logger.debug(f"No PDF found in ZIP for PMC{normalized_pmcid}")
                    return False

                # Extract PDF content and use atomic write
                pdf_content = zf.read(pdf_names[0])

                # Use atomic write by creating temporary file
                temp_path = output_path.with_suffix(".tmp")
                try:
                    with open(temp_path, "wb") as pdf_file:
                        pdf_file.write(pdf_content)

                    # Validate the downloaded content
                    if self._validate_pdf_content(temp_path):
                        # Move temp file to final location
                        temp_path.rename(output_path)
                        self.logger.info(f"Downloaded valid PDF via OA ZIP: {output_path}")
                        return True
                    else:
                        # Remove invalid file
                        temp_path.unlink(missing_ok=True)
                        self.logger.warning(
                            "Downloaded invalid PDF from ZIP archive, removed file"
                        )
                        return False
                except Exception as e:
                    # Clean up temp file on error
                    temp_path.unlink(missing_ok=True)
                    raise e

        except Exception as e:
            self.logger.error(
                f"Error downloading or extracting ZIP for PMC{normalized_pmcid}: {e}"
            )
            return False

    def _determine_bulk_archive_range(self, pmcid: int) -> tuple[int, int] | None:
        """
        Determine the archive range that would contain the given PMC ID.

        Europe PMC FTP OA archives are organized in ranges like PMC1000000_PMC1099999.xml.gz
        This method estimates the likely archive based on common range patterns.

        Parameters
        ----------
        pmcid : int
            Numeric PMC ID

        Returns
        -------
        tuple[int, int] or None
            (start_id, end_id) for the archive, or None if cannot determine
        """
        # Common range patterns observed in Europe PMC FTP
        # Archives typically use 100k ranges for newer articles
        if pmcid >= 1000000:
            # For PMC IDs >= 1M, use 100k ranges
            start_range = (pmcid // 100000) * 100000
            end_range = start_range + 99999
            return (start_range, end_range)
        elif pmcid >= 100000:
            # For PMC IDs 100k-1M, use 100k ranges
            start_range = (pmcid // 100000) * 100000
            end_range = start_range + 99999
            return (start_range, end_range)
        elif pmcid >= 10000:
            # For PMC IDs 10k-100k, use 10k ranges
            start_range = (pmcid // 10000) * 10000
            end_range = start_range + 9999
            return (start_range, end_range)
        else:
            # For PMC IDs < 10k, use 1k ranges
            start_range = (pmcid // 1000) * 1000
            end_range = start_range + 999
            return (start_range, end_range)

    def _try_bulk_xml_download(self, pmcid: str, output_path: Path) -> bool:
        """
        Try to download XML from Europe PMC FTP OA bulk archives.

        Parameters
        ----------
        pmcid : str
            Numeric PMC ID (without PMC prefix)
        output_path : Path
            Path where to save the XML file

        Returns
        -------
        bool
            True if successfully downloaded and extracted, False otherwise
        """
        try:
            pmcid_int = int(pmcid)
            archive_range = self._determine_bulk_archive_range(pmcid_int)

            if not archive_range:
                self.logger.debug(f"Could not determine archive range for PMC{pmcid}")
                return False

            start_id, end_id = archive_range
            archive_name = f"PMC{start_id}_PMC{end_id}.xml.gz"
            archive_url = urljoin(self.FTP_OA_BASE_URL, archive_name)

            self.logger.debug(f"Trying to download bulk archive: {archive_url}")

            # Download the gzipped archive
            response = requests.get(archive_url, timeout=60, stream=True)
            if response.status_code != 200:
                self.logger.debug(
                    f"Bulk archive not found: {archive_url} (status: {response.status_code})"
                )
                return False

            # Create temporary file for the archive
            with tempfile.NamedTemporaryFile() as temp_file:
                # Download archive content
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                temp_file.flush()

                # Extract the specific XML file from the gzipped archive
                try:
                    with gzip.open(temp_file.name, "rt", encoding="utf-8") as gz_file:
                        xml_content = gz_file.read()

                        # Look for the specific article XML
                        # The content might be a collection of articles or a single article
                        if "<article-meta>" in xml_content and f"PMC{pmcid}" in xml_content:
                            # Save the extracted XML using atomic write
                            with atomic_write(output_path, "w", encoding="utf-8") as f:
                                f.write(xml_content)

                            self.logger.info(
                                f"Successfully downloaded XML from bulk archive: {archive_name}"
                            )
                            return True
                        else:
                            self.logger.debug(
                                f"PMC{pmcid} not found in bulk archive {archive_name}"
                            )
                            return False

                except gzip.BadGzipFile:
                    self.logger.debug(f"Invalid gzip file: {archive_url}")
                    return False

        except (OSError, requests.RequestException, ValueError) as e:
            self.logger.debug(f"Error during bulk XML download for PMC{pmcid}: {e}")
            return False

    def search_and_download_fulltext(
        self,
        query: str,
        format_type: str = "pdf",
        max_results: int = 10,
        output_dir: str | Path | None = None,
        only_available: bool = True,
    ) -> dict[str, Path | None]:
        """
        End-to-end workflow: search papers and download full text content.

        This method combines search functionality with full text download,
        automatically filtering for papers that have the requested format available.

        Parameters
        ----------
        query : str
            Search query for Europe PMC
        format_type : str, optional
            Format to download ('pdf', 'xml', or 'html', default is 'pdf')
        max_results : int, optional
            Maximum number of papers to process (default is 10)
        output_dir : str or Path, optional
            Directory to save files. If None, uses current directory
        only_available : bool, optional
            If True, only process papers where the format is available (default is True)

        Returns
        -------
        Dict[str, Optional[Path]]
            Dictionary mapping PMC IDs to downloaded file paths (or None if failed)

        Raises
        ------
        FullTextError
            If format_type is invalid or search fails
        """
        self._validate_search_download_params(format_type, output_dir)
        output_dir = self._prepare_output_directory(output_dir)

        pmcids = self._search_for_pmcids(query, max_results)
        if not pmcids:
            return {}

        if only_available:
            pmcids = self._filter_available_pmcids(pmcids, format_type)

        return self._download_by_format(pmcids, format_type, output_dir)

    def _validate_search_download_params(
        self, format_type: str, output_dir: str | Path | None
    ) -> None:
        """Validate parameters for search and download."""
        if format_type not in ["pdf", "xml", "html"]:
            raise FullTextError(
                ErrorCodes.FULL004,
                context={"provided_format": format_type},
                format_type=format_type,
            )

    def _prepare_output_directory(self, output_dir: str | Path | None) -> Path:
        """Prepare and create output directory."""
        output_dir = Path.cwd() if output_dir is None else Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _search_for_pmcids(self, query: str, max_results: int) -> list[str]:
        """Search for papers and extract PMC IDs."""
        from pyeuropepmc.search import SearchClient

        self.logger.info(f"Starting search and download for query: '{query}'")

        search_client = SearchClient(rate_limit_delay=self.rate_limit_delay)
        try:
            search_results = search_client.search(query, pageSize=max_results)
            papers = self._extract_papers_from_results(search_results)
            return self._extract_pmcids_from_papers(papers)
        finally:
            search_client.close()

    def _extract_papers_from_results(
        self, search_results: dict[str, Any] | list[dict[str, Any]] | str
    ) -> list[dict[str, Any]]:
        """Extract papers list from search results."""
        if isinstance(search_results, dict) and "resultList" in search_results:
            result_list = search_results["resultList"].get("result", [])
            return result_list if isinstance(result_list, list) else []
        elif isinstance(search_results, list):
            return search_results
        else:
            self.logger.warning("Unexpected search result format")
            return []

    def _extract_pmcids_from_papers(self, papers: list[dict[str, Any]]) -> list[str]:
        """Extract PMC IDs from papers list."""
        pmcids = []
        for paper in papers:
            if isinstance(paper, dict) and "pmcid" in paper:
                pmcid = paper["pmcid"].replace("PMC", "")
                pmcids.append(pmcid)
        return pmcids

    def _filter_available_pmcids(self, pmcids: list[str], format_type: str) -> list[str]:
        """Filter PMC IDs to only include those with available content."""
        available_pmcids = []
        for pmcid in pmcids:
            try:
                availability = self.check_fulltext_availability(pmcid)
                if availability.get(format_type, False):
                    available_pmcids.append(pmcid)
            except Exception as e:
                self.logger.warning(f"Failed to check availability for PMC{pmcid}: {e}")
                continue

        self.logger.info(f"Found {len(available_pmcids)} papers with {format_type} available")
        return available_pmcids

    def _download_by_format(
        self, pmcids: list[str], format_type: str, output_dir: Path
    ) -> dict[str, Path | None]:
        """Download content by format type."""
        if format_type in ["pdf", "xml"]:
            return self.download_fulltext_batch(pmcids, format_type, output_dir)

        # HTML format
        results = {}
        for pmcid in pmcids:
            try:
                output_path = output_dir / f"PMC{pmcid}.html"
                result = self.download_html_by_pmcid(pmcid, output_path)
                results[pmcid] = result
            except Exception as e:
                self.logger.error(f"Failed to download HTML for PMC{pmcid}: {e}")
                results[pmcid] = None
        return results

    # API Response Cache Management Methods

    def get_api_cache_stats(self) -> dict[str, Any]:
        """
        Get API response cache statistics.

        Note: This is for API response caching only. File caching statistics
        are available via get_cache_stats().

        Returns:
            Dict containing API response cache stats (size, eviction stats, etc.)
        """
        try:
            return self._cache.get_stats()
        except Exception as e:
            self.logger.warning(f"Failed to get API cache stats: {e}")
            return {}

    def get_api_cache_health(self) -> dict[str, Any]:
        """
        Get API response cache health status.

        Returns:
            Dict containing cache health metrics (hit rate, miss rate, errors)
        """
        try:
            return self._cache.get_health()
        except Exception as e:
            self.logger.warning(f"Failed to get API cache health: {e}")
            return {}

    def clear_api_cache(self) -> bool:
        """
        Clear all API response cached data.

        Note: This only clears API response cache. Downloaded files in the
        file cache directory are not affected. Use clear_cache() to manage
        file cache.

        Returns:
            True if cache was cleared successfully, False otherwise
        """
        try:
            return self._cache.clear()
        except Exception as e:
            self.logger.warning(f"Failed to clear API cache: {e}")
            return False

    def invalidate_fulltext_cache(self, pmcid: str | None = None) -> int:
        """
        Invalidate cached fulltext availability data matching the pattern.

        Args:
            pmcid: Optional PMC ID filter

        Returns:
            Number of cache entries invalidated
        """
        try:
            if pmcid:
                # Normalize PMCID
                normalized = pmcid.replace("PMC", "")
                pattern = f"*:{normalized}*"
            else:
                pattern = "*"

            return self._cache.invalidate_pattern(pattern)
        except Exception as e:
            self.logger.warning(f"Failed to invalidate fulltext cache: {e}")
            return 0

    def close(self) -> None:
        """
        Close the client and cleanup resources including API response cache.

        Note: This doesn't remove downloaded files from the file cache directory.
        """
        try:
            self._cache.close()
        except Exception as e:
            self.logger.warning(f"Error closing API response cache: {e}")
        super().close()

    def export_results(
        self,
        results: list[dict[str, Any]],
        format: str = "dataframe",
        path: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Export fulltext results using the specified format.

        Args:
            results: List of result dicts to export
            format: Export format ('dataframe', 'csv', 'excel', 'json', 'markdown')
            path: Optional file path for file-based exports
            **kwargs: Additional options for export (e.g., pretty for JSON)

        Returns:
            Exported data (DataFrame, str, bytes, etc.)
        """
        from pyeuropepmc.utils import export

        if format == "dataframe":
            return export.to_dataframe(results)
        elif format == "csv":
            return export.to_csv(results, path)
        elif format == "excel":
            return export.to_excel(results, path)
        elif format == "json":
            return export.to_json(results, path, **kwargs)
        elif format == "markdown":
            return export.to_markdown_table(results)
        else:
            raise ValueError(f"Unsupported export format: {format}")
