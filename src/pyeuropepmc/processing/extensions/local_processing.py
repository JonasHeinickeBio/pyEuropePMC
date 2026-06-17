"""
Local XML File/Directory Processing Convenience Methods.

Provides helper functions and methods for processing XML files from local storage,
enabling batch processing of PMC article XML files without API calls.

Based on patterns from pmcgrab's ``process_single_local_xml()`` and
``process_local_xml_dir()``.
"""

from __future__ import annotations

from collections.abc import Callable
import contextlib
import logging
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

logger = logging.getLogger(__name__)


def parse_xml_file(
    file_path: str | Path,
    config: ElementPatterns | None = None,
) -> FullTextXMLParser:
    """
    Parse a local XML file and return a configured parser.

    Convenience function for loading and parsing a single XML file.

    Parameters
    ----------
    file_path : str or Path
        Path to the XML file.
    config : ElementPatterns, optional
        Custom element pattern configuration.

    Returns
    -------
    FullTextXMLParser
        Configured parser with the file content loaded.

    Examples
    --------
    >>> parser = parse_xml_file("PMC1234567.xml")
    >>> metadata = parser.extract_metadata()
    >>> sections = parser.get_full_text_sections()

    >>> # With custom config
    >>> parser = parse_xml_file("article.xml", config=custom_config)
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"XML file not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        xml_content = f.read()

    return FullTextXMLParser(xml_content, config=config)


def parse_xml_directory(
    directory: str | Path,
    glob_pattern: str = "*.xml",
    config: ElementPatterns | None = None,
    recursive: bool = True,
) -> dict[str, FullTextXMLParser]:
    """
    Parse all XML files in a directory.

    Parameters
    ----------
    directory : str or Path
        Directory to scan for XML files.
    glob_pattern : str, optional
        File pattern (default: ``"*.xml"``).
    config : ElementPatterns, optional
        Custom element pattern configuration.
    recursive : bool, optional
        If True, scan subdirectories (default: True).

    Returns
    -------
    dict[str, FullTextXMLParser]
        Mapping of file paths to parser instances.

    Examples
    --------
    >>> parsers = parse_xml_directory("./pmc_articles")
    >>> for path, parser in parsers.items():
    ...     print(f"{path}: {parser.extract_metadata().get('title', 'N/A')}")
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")

    # Find XML files
    pattern = f"**/{glob_pattern}" if recursive else glob_pattern
    xml_files = sorted(directory.glob(pattern))

    if not xml_files:
        logger.warning(f"No XML files matching '{glob_pattern}' found in {directory}")
        return {}

    parsers: dict[str, FullTextXMLParser] = {}
    errors: list[tuple[str, str]] = []

    for file_path in xml_files:
        if not file_path.is_file():
            continue

        try:
            parser = parse_xml_file(file_path, config=config)
            parsers[str(file_path)] = parser
        except Exception as e:
            errors.append((str(file_path), str(e)))
            logger.warning(f"Failed to parse {file_path}: {e}")

    if errors:
        logger.info(f"Parsed {len(parsers)}/{len(xml_files)} files ({len(errors)} errors)")

    return parsers


def extract_article_id_from_xml(xml_content: str | ET.Element) -> str | None:
    """
    Extract the article ID (PMCID, PMID, or DOI) from raw XML content.

    Useful for naming files or determining article identity before full parsing.

    Parameters
    ----------
    xml_content : str or ET.Element
        XML content string or parsed element.

    Returns
    -------
    str or None
        The first found article ID (preferring PMCID > DOI > PMID), or None.

    Examples
    --------
    >>> article_id = extract_article_id_from_xml(xml_string)
    >>> print(f"Article: {article_id}")
    """
    if isinstance(xml_content, str):
        try:
            import defusedxml.ElementTree as DefusedET

            root = DefusedET.fromstring(xml_content)
        except Exception:
            return None
    else:
        root = xml_content

    # Try PMCID first (most useful for local filenames)
    for elem in root.findall(".//article-id[@pub-id-type='pmcid']"):
        text = elem.text
        if text:
            return text.strip()  # type: ignore[no-any-return]

    # Then DOI
    for elem in root.findall(".//article-id[@pub-id-type='doi']"):
        text = elem.text
        if text:
            return text.strip()  # type: ignore[no-any-return]

    # Then PMID
    for elem in root.findall(".//article-id[@pub-id-type='pmid']"):
        text = elem.text
        if text:
            return text.strip()  # type: ignore[no-any-return]

    return None


class LocalXMLProcessor:
    """
    High-level processor for local XML files with extract-select functionality.

    Provides a convenient interface for processing local XML files with
    configurable extraction functions.

    Parameters
    ----------
    config : ElementPatterns, optional
        Custom element pattern configuration.

    Examples
    --------
    >>> processor = LocalXMLProcessor()
    >>> result = processor.process_single("article.xml")
    >>> print(result["metadata"]["title"])
    """

    def __init__(self, config: ElementPatterns | None = None):
        self.config = config

    def process_single(
        self,
        file_path: str | Path,
        extract_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Process a single local XML file.

        Parameters
        ----------
        file_path : str or Path
            Path to the XML file.
        extract_fn : callable, optional
            Function that takes a parser and returns extracted data.
            If None, extracts all available data.

        Returns
        -------
        dict
            Extracted data with metadata, sections, references, etc.
        """
        parser = parse_xml_file(file_path, config=self.config)

        if extract_fn is not None:
            return extract_fn(parser)

        return self._extract_all(parser)

    def process_directory(
        self,
        directory: str | Path,
        glob_pattern: str = "*.xml",
        extract_fn: Callable[[FullTextXMLParser], dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Process all XML files in a directory.

        Parameters
        ----------
        directory : str or Path
            Directory to scan.
        glob_pattern : str, optional
            File pattern.
        extract_fn : callable, optional
            Custom extraction function.

        Returns
        -------
        dict[str, dict]
            Mapping of file paths to extracted data.
        """
        parsers = parse_xml_directory(
            directory,
            glob_pattern=glob_pattern,
            config=self.config,
        )

        results: dict[str, dict[str, Any]] = {}
        for path, parser in parsers.items():
            try:
                if extract_fn is not None:
                    results[path] = extract_fn(parser)
                else:
                    results[path] = self._extract_all(parser)
            except Exception as e:
                logger.error(f"Error processing {path}: {e}")
                results[path] = {"error": str(e)}

        return results

    @staticmethod
    def _extract_all(
        parser: FullTextXMLParser,
    ) -> dict[str, Any]:
        """Extract all available data from a parser."""
        data: dict[str, Any] = {
            "source": parser.xml_content[:100] + "..."
            if parser.xml_content and len(parser.xml_content) > 100
            else (parser.xml_content or ""),
        }

        try:
            data["metadata"] = parser.extract_metadata()
        except Exception as e:
            data["metadata"] = {"error": str(e)}

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

        with contextlib.suppress(Exception):
            data["keywords"] = parser.extract_keywords()

        return data
