"""
Batch/Concurrent Processing for XML Articles.

Provides configurable concurrent processing of multiple articles with
rate limiting to respect API usage guidelines (NCBI 3 req/sec without API key).

Based on patterns from pubmed-stream and pmcgrab.
"""

from __future__ import annotations

from collections.abc import Callable
import concurrent.futures
import contextlib
from dataclasses import dataclass, field
import logging
import threading
import time
from typing import Any

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

logger = logging.getLogger(__name__)

# Default rate limit: 3 requests per second (NCBI default without API key)
DEFAULT_RATE_LIMIT = 3.0

# Default concurrency
DEFAULT_MAX_WORKERS = 4


@dataclass
class ProcessingResult:
    """
    Result of processing a single article.

    Parameters
    ----------
    identifier : str
        Article identifier (PMID, DOI, or file path).
    success : bool
        Whether processing succeeded.
    data : dict or None
        Extracted data on success.
    error : str, optional
        Error message on failure.
    duration : float, optional
        Processing time in seconds.
    """

    identifier: str
    success: bool
    data: dict[str, Any] | None = None
    error: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "identifier": self.identifier,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration": round(self.duration, 3),
        }


@dataclass
class BatchResult:
    """
    Aggregate result of batch processing.

    Parameters
    ----------
    results : list[ProcessingResult]
        Individual article results.
    total_duration : float
        Total processing time in seconds.
    """

    results: list[ProcessingResult] = field(default_factory=list)
    total_duration: float = 0.0

    @property
    def successes(self) -> list[ProcessingResult]:
        """Results that succeeded."""
        return [r for r in self.results if r.success]

    @property
    def failures(self) -> list[ProcessingResult]:
        """Results that failed."""
        return [r for r in self.results if not r.success]

    @property
    def success_rate(self) -> float:
        """Fraction of successful results (0.0 to 1.0)."""
        if not self.results:
            return 0.0
        return len(self.successes) / len(self.results)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "total": len(self.results),
            "successes": len(self.successes),
            "failures": len(self.failures),
            "success_rate": round(self.success_rate, 2),
            "total_duration": round(self.total_duration, 3),
            "results": [r.to_dict() for r in self.results],
        }


class BatchProcessor:
    """
    Process multiple articles concurrently with rate limiting.

    Supports processing from:
    - XML string content
    - Local XML file paths
    - Article identifiers fetched via the Europe PMC API

    Parameters
    ----------
    max_workers : int, optional
        Maximum number of concurrent workers (default: 4).
    rate_limit : float, optional
        Maximum requests per second (default: 3.0).
    progress_callback : callable, optional
        Called with ``(completed, total, identifier)`` after each article.
    error_callback : callable, optional
        Called with ``(identifier, exception)`` on processing errors.

    Examples
    --------
    >>> processor = BatchProcessor(max_workers=8)
    >>> result = processor.process_files(["paper1.xml", "paper2.xml"])
    >>> print(f"Success rate: {result.success_rate:.0%}")
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        progress_callback: Callable[[int, int, str], None] | None = None,
        error_callback: Callable[[str, Exception], None] | None = None,
    ):
        self.max_workers = max_workers
        self.rate_limit = max(rate_limit, 0.1)  # Minimum 0.1 req/sec
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        self._completed = 0
        self._total = 0
        self._lock = threading.Lock()

    def _rate_sleep(self) -> None:
        """Sleep to respect the rate limit (thread-safe)."""
        time.sleep(1.0 / self.rate_limit)

    def _process_file_one(
        self, file_path: str, extraction_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None
    ) -> ProcessingResult:
        """Process a single file with rate limiting (called from thread pool)."""
        self._rate_sleep()
        t0 = time.time()
        try:
            with open(file_path) as f:
                xml_content = f.read()
            parser = FullTextXMLParser(xml_content)
            data = self._extract_data(parser, extraction_fn)
            duration = time.time() - t0
            result = ProcessingResult(
                identifier=file_path, success=True, data=data, duration=duration
            )
        except Exception as e:
            duration = time.time() - t0
            logger.error(f"Error processing {file_path}: {e}")
            result = ProcessingResult(
                identifier=file_path, success=False, error=str(e), duration=duration
            )
            if self.error_callback:
                self.error_callback(file_path, e)

        with self._lock:
            self._completed += 1
            if self.progress_callback:
                self.progress_callback(self._completed, self._total, file_path)
        return result

    def _process_xml_one(
        self,
        identifier: str,
        xml_content: str,
        extraction_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None,
    ) -> ProcessingResult:
        """Process a single XML string with rate limiting (called from thread pool)."""
        self._rate_sleep()
        t0 = time.time()
        try:
            parser = FullTextXMLParser(xml_content)
            data = self._extract_data(parser, extraction_fn)
            duration = time.time() - t0
            result = ProcessingResult(
                identifier=identifier, success=True, data=data, duration=duration
            )
        except Exception as e:
            duration = time.time() - t0
            logger.error(f"Error processing {identifier}: {e}")
            result = ProcessingResult(
                identifier=identifier, success=False, error=str(e), duration=duration
            )
            if self.error_callback:
                self.error_callback(identifier, e)

        with self._lock:
            self._completed += 1
            if self.progress_callback:
                self.progress_callback(self._completed, self._total, identifier)
        return result

    def process_files(
        self,
        file_paths: list[str],
        extraction_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None = None,
    ) -> BatchResult:
        """
        Process multiple local XML files concurrently.

        Parameters
        ----------
        file_paths : list[str]
            Paths to XML files.
        extraction_fn : callable, optional
            Function that takes a parser and returns extracted data.
            If None, extracts all available data.

        Returns
        -------
        BatchResult
            Aggregate results.
        """
        self._total = len(file_paths)
        self._completed = 0

        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_file_one, fp, extraction_fn): fp for fp in file_paths
            }
            results: list[ProcessingResult] = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        total_duration = time.time() - start
        return BatchResult(results=results, total_duration=total_duration)

    def process_xml_strings(
        self,
        items: list[tuple[str, str]],
        extraction_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None = None,
    ) -> BatchResult:
        """
        Process multiple XML strings concurrently.

        Parameters
        ----------
        items : list[tuple[str, str]]
            List of ``(identifier, xml_string)`` tuples.
        extraction_fn : callable, optional
            Function that takes a parser and returns extracted data.

        Returns
        -------
        BatchResult
            Aggregate results.
        """
        self._total = len(items)
        self._completed = 0

        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_xml_one, ident, xml, extraction_fn): ident
                for ident, xml in items
            }
            results: list[ProcessingResult] = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        total_duration = time.time() - start
        return BatchResult(results=results, total_duration=total_duration)

    @staticmethod
    def _extract_data(
        parser: FullTextXMLParser,
        extraction_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Extract data from a parser using the provided function or default."""
        if extraction_fn is not None:
            return extraction_fn(parser)

        # Default: extract everything available
        data: dict[str, Any] = {}

        with contextlib.suppress(Exception):
            data["metadata"] = parser.extract_metadata()

        with contextlib.suppress(Exception):
            data["authors"] = parser.extract_authors()

        with contextlib.suppress(Exception):
            data["sections"] = parser.get_full_text_sections()

        with contextlib.suppress(Exception):
            data["references"] = parser.extract_references()

        with contextlib.suppress(Exception):
            data["figures"] = parser.extract_figures()

        with contextlib.suppress(Exception):
            data["tables"] = parser.extract_tables()

        with contextlib.suppress(Exception):
            data["funding"] = parser.extract_funding()

        return data

    def process_directories(
        self,
        directories: list[str],
        glob_pattern: str = "*.xml",
        extraction_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None = None,
    ) -> BatchResult:
        """
        Process all XML files in one or more directories.

        Parameters
        ----------
        directories : list[str]
            Directory paths to scan for XML files.
        glob_pattern : str, optional
            File glob pattern (default: ``"*.xml"``).
        extraction_fn : callable, optional
            Function to extract data from each parser.

        Returns
        -------
        BatchResult
            Aggregate results.
        """
        import glob as glob_module
        import os

        file_paths: list[str] = []
        for directory in directories:
            pattern = os.path.join(directory, glob_pattern)
            file_paths.extend(glob_module.glob(pattern))

        if not file_paths:
            logger.warning(f"No files matching '{glob_pattern}' found in directories")

        return self.process_files(file_paths, extraction_fn)
