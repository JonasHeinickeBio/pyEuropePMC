"""
Table parser for extracting table information from XML.

This module provides specialized parsing for tables.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.utils.table_grid import build_table_grid, find_table

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
            One dict per ``<table-wrap>``:

            ``id``, ``label``, ``caption``, ``footer``
                as in the document; ``None`` where absent.
            ``headers``
                one label per column, combined from every header row (see
                :meth:`TableGrid.header_labels`); ``[]`` without a header row.
            ``header_rows``, ``rows``
                the header rows and the body rows, each as wide as the table.
                A spanning cell's text stands at its top-left position and the
                positions it also covers hold ``""``.
            ``spans``
                ``{row, column, rowspan, colspan}`` for each cell covering more
                than one position; ``row`` counts ``header_rows`` first.
            ``cell_graphics``
                ``{row, column, uri}`` for each image inside a cell. A cell
                holding nothing but an image reads ``[graphic: <uri>]``.
            ``column_groups``
                only when the table has ``<colgroup>`` markup.
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
        table_data["caption"] = self._extract_first_text_from_element(table_wrap, caption_patterns)

        # Every footer, not only the first: notes and abbreviation keys can
        # sit in separate <table-wrap-foot> elements.
        footers = self._extract_flat_texts(
            table_wrap, ".//table-wrap-foot", filter_empty=True, use_full_text=True
        )
        table_data["footer"] = " ".join(footers) if footers else None

        # Extract column group information
        colgroups = self._extract_column_groups(table_wrap)
        if colgroups:
            table_data["column_groups"] = colgroups

        table_elem = find_table(table_wrap)
        if table_elem is not None:
            grid = build_table_grid(table_elem)
            table_data["headers"] = grid.header_labels()
            table_data["header_rows"] = grid.header_rows
            table_data["rows"] = grid.body_rows
            table_data["spans"] = grid.spans()
            table_data["cell_graphics"] = grid.cell_graphics()
        else:
            table_data["headers"] = []
            table_data["header_rows"] = []
            table_data["rows"] = []
            table_data["spans"] = []
            table_data["cell_graphics"] = []

        return table_data

    def _extract_column_groups(self, table_wrap: ET.Element) -> list[dict[str, Any]]:
        """Extract column group information from table."""
        colgroups = []

        # Find colgroup elements
        for colgroup in table_wrap.findall(".//colgroup"):
            colgroup_data: dict[str, Any] = {}
            colgroup_data["columns"] = []

            # Extract span attribute if present
            span = colgroup.get("span")
            if span:
                colgroup_data["span"] = span

            # Extract individual col elements
            for col in colgroup.findall(".//col"):
                col_data = {}
                col_span = col.get("span")
                if col_span:
                    col_data["span"] = col_span

                col_width = col.get("width")
                if col_width:
                    col_data["width"] = col_width

                if col_data:
                    colgroup_data["columns"].append(col_data)

            if colgroup_data["columns"] or "span" in colgroup_data:
                colgroups.append(colgroup_data)

        return colgroups

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
