"""
XML helper utilities for fulltext parser.

This module provides generic XML extraction and manipulation helper functions.
"""

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

logger = logging.getLogger(__name__)


class XMLHelper:
    """Helper class for generic XML extraction operations."""

    @staticmethod
    def get_text_content(element: ET.Element | None) -> str:
        """
        Get all text content from an element and its descendants.

        Parameters
        ----------
        element : ET.Element or None
            XML element to extract text from

        Returns
        -------
        str
            Combined text content
        """
        if element is None:
            return ""

        # Get text from element and all sub-elements
        text_parts = []
        if element.text:
            text_parts.append(element.text.strip())

        for child in element:
            child_text = XMLHelper.get_text_content(child)
            if child_text:
                text_parts.append(child_text)
            if child.tail:
                text_parts.append(child.tail.strip())

        return " ".join(text_parts).strip()

    @staticmethod
    def extract_flat_texts(
        parent: ET.Element,
        pattern: str,
        filter_empty: bool = True,
        use_full_text: bool = False,
    ) -> list[str]:
        """
        Extract flat text fields from XML.

        For each element matching pattern, extract its text.

        Parameters
        ----------
        parent : ET.Element
            Parent element to search within
        pattern : str
            XPath pattern to find elements
        filter_empty : bool
            If True, filter out empty strings
        use_full_text : bool
            If True, use get_text_content() for deep text extraction

        Returns
        -------
        list[str]
            List of extracted text values
        """
        results = []
        for elem in parent.findall(pattern):
            if use_full_text:
                text = XMLHelper.get_text_content(elem)
            else:
                text = elem.text.strip() if elem.text else ""
            if not filter_empty or text:
                results.append(text)
        return results

    @staticmethod
    def extract_nested_texts(
        parent: ET.Element,
        outer_pattern: str,
        inner_patterns: list[str],
        join: str = " ",
        filter_empty: bool = True,
    ) -> list[str]:
        """
        Extract nested text fields from XML.

        For each element matching outer_pattern, extract/join text from inner_patterns.

        Parameters
        ----------
        parent : ET.Element
            Parent element to search within
        outer_pattern : str
            XPath pattern for outer elements
        inner_patterns : list[str]
            XPath patterns for inner elements to extract
        join : str
            String to join inner texts with
        filter_empty : bool
            If True, filter out empty strings

        Returns
        -------
        list[str]
            List of joined text values
        """
        results = []
        for outer in parent.findall(outer_pattern):
            parts = []
            for ipat in inner_patterns:
                found = outer.find(ipat)
                if found is not None and found.text:
                    parts.append(found.text.strip())
            if filter_empty:
                parts = [p for p in parts if p]
            if parts:
                results.append(join.join(parts))
        return results

    @staticmethod
    def extract_inline_elements(
        element: ET.Element,
        inline_patterns: list[str] | None = None,
        filter_empty: bool = True,
    ) -> list[str]:
        """
        Extract text from inline elements (e.g., superscripts, subscripts).

        Parameters
        ----------
        element : ET.Element
            Parent element to search within
        inline_patterns : list[str], optional
            List of element patterns to extract. Defaults to [".//sup"].
        filter_empty : bool
            Whether to filter out empty strings (default: True)

        Returns
        -------
        list[str]
            List of extracted text values from matching inline elements
        """
        if inline_patterns is None:
            inline_patterns = [".//sup"]

        results = []
        for pattern in inline_patterns:
            texts = XMLHelper.extract_flat_texts(
                element, pattern, filter_empty=filter_empty, use_full_text=False
            )
            results.extend(texts)

        return results

    @staticmethod
    def get_text_without_inline_elements(
        element: ET.Element,
        inline_patterns: list[str] | None = None,
    ) -> str:
        """
        Get text content with specified inline elements removed.

        Parameters
        ----------
        element : ET.Element
            Element to extract text from
        inline_patterns : list[str], optional
            Patterns for inline elements to remove. Defaults to [".//sup"].

        Returns
        -------
        str
            Text content with inline elements removed
        """
        if inline_patterns is None:
            inline_patterns = [".//sup"]

        # Get full text
        full_text = "".join(element.itertext()).strip()

        # Extract inline element texts
        inline_texts = XMLHelper.extract_inline_elements(
            element, inline_patterns, filter_empty=True
        )

        # Remove each inline text using regex
        clean_text = full_text
        for inline_text in inline_texts:
            clean_text = re.sub(rf"{re.escape(inline_text)}", "", clean_text)

        return clean_text.strip()

    @staticmethod
    def extract_with_fallbacks(
        element: ET.Element, patterns: list[str], use_full_text: bool = False
    ) -> str | None:
        """
        Try multiple element patterns in order until one succeeds.

        Parameters
        ----------
        element : ET.Element
            Parent element to search within
        patterns : list[str]
            Ordered list of element names/patterns to try
        use_full_text : bool
            Whether to extract all nested text (default: False)

        Returns
        -------
        str or None
            First match found, or None if no patterns match
        """
        for pattern in patterns:
            results = XMLHelper.extract_flat_texts(
                element, pattern, filter_empty=True, use_full_text=use_full_text
            )
            if results:
                logger.debug(f"Fallback successful: pattern '{pattern}' matched")
                return results[0]
        logger.debug(f"No fallback patterns matched: {patterns}")
        return None

    @staticmethod
    def extract_structured_fields(
        parent: ET.Element,
        field_patterns: dict[str, str],
        first_only: bool = True,
    ) -> dict[str, Any]:
        """
        Extract multiple fields from a parent element as a structured dict.

        Parameters
        ----------
        parent : ET.Element
            Parent element to search within
        field_patterns : dict[str, str]
            Mapping of field names to XPath patterns
        first_only : bool
            If True, return single value; if False, return lists

        Returns
        -------
        dict[str, Any]
            Dictionary with extracted values (or None if not found)
        """
        result: dict[str, Any] = {}
        for key, pattern in field_patterns.items():
            matches = parent.findall(pattern)
            if not first_only:
                result[key] = [XMLHelper.get_text_content(m) for m in matches] if matches else []
            else:
                if matches:
                    text = XMLHelper.get_text_content(matches[0])
                    result[key] = text if text else None
                else:
                    result[key] = None
        return result

    @staticmethod
    def combine_page_range(fpage: str | None, lpage: str | None) -> str | None:
        """
        Combine first and last page into a page range.

        Parameters
        ----------
        fpage : str or None
            First page
        lpage : str or None
            Last page

        Returns
        -------
        str or None
            Page range string (e.g., "100-110") or single page
        """
        if fpage and lpage:
            return f"{fpage}-{lpage}"
        elif fpage:
            return fpage
        return None
