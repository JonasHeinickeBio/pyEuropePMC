"""
Figure parser for extracting figure information from XML.

This module provides specialized parsing for figures.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.utils.figure_assets import own_graphic, parent_figure_map

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
            One dict per figure, with ``id``, ``label``, ``caption`` and, when
            the figure has a graphic of its own, ``graphic_uri``. A figure
            supplement - a ``<fig>`` nested in another - also carries
            ``parent_id`` and ``parent_label``.
        """
        self._require_root()

        try:
            patterns = {"fig": ".//fig"}
            fig_elements = self.extract_elements_by_patterns(patterns, return_type="element")[
                "fig"
            ]
            parents = parent_figure_map(self.root) if self.root is not None else {}
            figures = []
            for fig_elem in fig_elements:
                figure_data = self._extract_single_figure(fig_elem, parents.get(fig_elem))
                figures.append(figure_data)
            logger.debug(f"Extracted {len(figures)} figures from XML: {figures}")
            return figures
        except Exception as e:
            logger.error(f"Error extracting figures: {e}")
            raise

    def _extract_single_figure(
        self, fig_elem: ET.Element, parent: ET.Element | None = None
    ) -> dict[str, Any]:
        """Extract data from a single fig element."""
        figure_data: dict[str, Any] = {}
        figure_data["id"] = fig_elem.get("id")

        # Extract label and caption
        label_patterns = {"label": "label"}
        caption_patterns = {"caption": "caption"}
        figure_data["label"] = self._extract_first_text_from_element(fig_elem, label_patterns)
        figure_data["caption"] = self._extract_first_text_from_element(fig_elem, caption_patterns)

        # The figure's own graphic, not the first one anywhere beneath it: a
        # caption can hold images of an inline formula, and an eLife figure
        # holds its supplements' images. Both came before the figure's own
        # <graphic> in document order, so a `.//graphic` search returned a
        # fragment of an equation as PMC10775981's Fig 3.
        graphic = own_graphic(fig_elem)
        if graphic is not None:
            figure_data["graphic_uri"] = graphic.get(
                "{http://www.w3.org/1999/xlink}href"
            ) or graphic.get("href")

        if parent is not None:
            figure_data["parent_id"] = parent.get("id")
            figure_data["parent_label"] = self._extract_first_text_from_element(
                parent, {"label": "label"}
            )

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
