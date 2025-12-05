"""
Figure parser for extracting figure information from XML.

This module provides specialized parsing for figures.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class FigureParser(BaseParser):
    """Specialized parser for figure extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the figure parser."""
        super().__init__(root, config)

    def extract_figures(self) -> list[dict[str, Any]]:
        """
        Extract all figures from the full text XML.

        Returns
        -------
        list[dict[str, Any]]
            List of figure dictionaries with id, label, caption, and graphic information
        """
        self._require_root()

        try:
            patterns = {"fig": ".//fig"}
            fig_elements = self.extract_elements_by_patterns(patterns, return_type="element")[
                "fig"
            ]
            figures = []
            for fig_elem in fig_elements:
                figure_data = self._extract_single_figure(fig_elem)
                figures.append(figure_data)
            logger.debug(f"Extracted {len(figures)} figures from XML: {figures}")
            return figures
        except Exception as e:
            logger.error(f"Error extracting figures: {e}")
            raise

    def _extract_single_figure(self, fig_elem: ET.Element) -> dict[str, Any]:
        """Extract data from a single fig element."""
        figure_data: dict[str, Any] = {}
        figure_data["id"] = fig_elem.get("id")

        # Extract label and caption
        label_patterns = {"label": "label"}
        caption_patterns = {"caption": "caption"}
        figure_data["label"] = self._extract_first_text_from_element(fig_elem, label_patterns)
        figure_data["caption"] = self._extract_first_text_from_element(fig_elem, caption_patterns)

        # Extract graphic information
        graphics = fig_elem.findall(".//graphic")
        if graphics:
            graphic = graphics[0]  # Take the first graphic
            figure_data["graphic_uri"] = graphic.get(
                "{http://www.w3.org/1999/xlink}href"
            ) or graphic.get("href")

        return figure_data

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
