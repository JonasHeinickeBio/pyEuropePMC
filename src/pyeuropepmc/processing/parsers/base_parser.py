"""
Base parser class for specialized parsers.

This module provides the base class that all specialized parsers inherit from.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class BaseParser:
    """Base class for specialized XML parsers."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """
        Initialize the parser.

        Parameters
        ----------
        root : ET.Element, optional
            Root element of the parsed XML
        config : ElementPatterns, optional
            Configuration for element patterns
        """
        self.root = root
        self.config = config or ElementPatterns()
        self._helper = XMLHelper

    def _require_root(self) -> None:
        """Raise an error if no root element is available."""
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

    def _get_text_content(self, element: ET.Element | None) -> str:
        """Get all text content from an element and its descendants."""
        return self._helper.get_text_content(element)

    def _extract_flat_texts(
        self,
        parent: ET.Element,
        pattern: str,
        filter_empty: bool = True,
        use_full_text: bool = False,
    ) -> list[str]:
        """Extract flat text fields from XML."""
        return self._helper.extract_flat_texts(parent, pattern, filter_empty, use_full_text)

    def _extract_with_fallbacks(
        self, element: ET.Element, patterns: list[str], use_full_text: bool = False
    ) -> str | None:
        """Try multiple element patterns in order until one succeeds."""
        return self._helper.extract_with_fallbacks(element, patterns, use_full_text)

    def _extract_structured_fields(
        self,
        parent: ET.Element,
        field_patterns: dict[str, str],
        first_only: bool = True,
    ) -> dict[str, Any]:
        """Extract multiple fields from a parent element as a structured dict."""
        return self._helper.extract_structured_fields(parent, field_patterns, first_only)

    def extract_elements_by_patterns(
        self,
        patterns: dict[str, str],
        return_type: str = "text",
        first_only: bool = False,
        get_attribute: dict[str, str] | None = None,
    ) -> dict[str, list[Any]]:
        """
        Extract elements from the parsed XML that match user-defined tag patterns.

        Parameters
        ----------
        patterns : dict
            Keys are output field names, values are XPath-like patterns
        return_type : str
            'text': return text content; 'element': return Element; 'attribute': return attribute
        first_only : bool
            If True, only return the first match for each pattern
        get_attribute : dict, optional
            If return_type is 'attribute', a dict mapping field name to attribute name

        Returns
        -------
        dict
            Dictionary where each key is from the input dict and value is list of results
        """
        self._require_root()

        results: dict[str, list[Any]] = {}
        for key, pattern in patterns.items():
            matches = self.root.findall(pattern)
            if not matches:
                results[key] = []
                continue
            values: list[Any]
            if return_type == "text":
                values = [self._get_text_content(elem) for elem in matches]
            elif return_type == "element":
                values = matches
            elif return_type == "attribute":
                attr = get_attribute[key] if get_attribute and key in get_attribute else None
                if attr is None:
                    raise ValueError(f"No attribute specified for key '{key}' in get_attribute.")
                values = [elem.get(attr) for elem in matches]
            else:
                raise ValueError(f"Unknown return_type: {return_type}")
            if first_only:
                results[key] = [values[0]] if values else []
            else:
                results[key] = values
        return results
