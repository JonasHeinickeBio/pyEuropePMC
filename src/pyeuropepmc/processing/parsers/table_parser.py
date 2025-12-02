"""
Table parser for extracting table information from XML.

This module provides specialized parsing for tables.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class TableParser(BaseParser):
    """Specialized parser for table extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the table parser."""
        super().__init__(root, config)

    def extract_tables(self) -> list[dict[str, Any]]:
        """
        Extract all tables from the full text XML.

        Returns
        -------
        list[dict[str, Any]]
            List of table dictionaries with id, label, caption, headers, and rows
        """
        self._require_root()

        try:
            patterns = {"table_wrap": ".//table-wrap"}
            table_wraps = self.extract_elements_by_patterns(patterns, return_type="element")[
                "table_wrap"
            ]
            tables = []
            for table_wrap in table_wraps:
                table_data = self._extract_single_table(table_wrap)
                tables.append(table_data)
            logger.debug(f"Extracted {len(tables)} tables from XML: {tables}")
            return tables
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            raise

    def _extract_single_table(self, table_wrap: ET.Element) -> dict[str, Any]:
        """Extract data from a single table-wrap element."""
        table_data: dict[str, Any] = {}
        table_data["id"] = table_wrap.get("id")

        # Extract label and caption
        label_patterns = {"label": "label"}
        caption_patterns = {"caption": "caption"}
        table_data["label"] = self._extract_first_text_from_element(table_wrap, label_patterns)
        table_data["caption"] = self._extract_first_text_from_element(
            table_wrap, caption_patterns
        )

        # Find table element
        table_elem = None
        for elem in table_wrap.iter():
            if elem.tag == "table":
                table_elem = elem
                break

        if table_elem is not None:
            headers, rows = self._parse_table(table_elem)
            table_data["headers"] = headers
            table_data["rows"] = rows
        else:
            table_data["headers"] = []
            table_data["rows"] = []

        return table_data

    def _extract_first_text_from_element(
        self, element: ET.Element, patterns: dict[str, str]
    ) -> str | None:
        """Extract the first text value for a pattern from a given element."""
        for _key, pattern in patterns.items():
            texts = self._extract_flat_texts(
                element, pattern, filter_empty=True, use_full_text=True
            )
            if texts:
                return texts[0]
        return None

    def _parse_table(self, table_elem: ET.Element) -> tuple[list[str], list[list[str]]]:
        """Parse a table element into headers and rows."""
        headers = self._extract_table_headers(table_elem)
        rows = self._extract_table_rows(table_elem)
        return headers, rows

    def _find_element_by_tag(self, parent: ET.Element, tag: str) -> ET.Element | None:
        """Find the first element with a specific tag."""
        for elem in parent.iter():
            if elem.tag == tag:
                return elem
        return None

    def _extract_table_headers(self, table_elem: ET.Element) -> list[str]:
        """Extract headers from table's thead element."""
        thead = self._find_element_by_tag(table_elem, "thead")
        if thead is None:
            return []

        header_row = self._find_element_by_tag(thead, "tr")
        if header_row is None:
            return []

        return self._extract_flat_texts(
            header_row, ".//th", filter_empty=False, use_full_text=True
        )

    def _extract_table_rows(self, table_elem: ET.Element) -> list[list[str]]:
        """Extract rows from table's tbody element."""
        rows: list[list[str]] = []
        tbody = self._find_element_by_tag(table_elem, "tbody")
        if tbody is None:
            return rows

        for tr in tbody.iter():
            if tr.tag == "tr":
                row_data = self._extract_flat_texts(
                    tr, "td", filter_empty=False, use_full_text=True
                )
                if row_data:
                    rows.append(row_data)

        return rows
