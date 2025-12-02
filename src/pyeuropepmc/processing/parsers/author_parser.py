"""
Author parser for extracting author information from XML.

This module provides specialized parsing for author and contributor data.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.text_cleaners import TextCleaner

logger = logging.getLogger(__name__)


class AuthorParser(BaseParser):
    """Specialized parser for author extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the author parser."""
        super().__init__(root, config)

    def extract_authors(self) -> list[str]:
        """
        Extract list of author names from XML.

        Returns
        -------
        list[str]
            List of author names as strings
        """
        detailed_authors = self.extract_authors_detailed()
        return [
            author.get("full_name", "") for author in detailed_authors if author.get("full_name")
        ]

    def extract_authors_detailed(self) -> list[dict[str, Any]]:
        """
        Extract list of detailed author information from XML.

        Returns
        -------
        list[dict[str, Any]]
            List of author dictionaries with full_name, given_names, surname,
            affiliation_refs, and orcid fields.
        """
        self._require_root()

        # Try each author element pattern in config
        for author_pattern in self.config.author_element_patterns:
            author_elems = self.root.findall(author_pattern) if self.root is not None else []
            if author_elems:
                logger.debug(f"Found {len(author_elems)} authors using pattern: {author_pattern}")
                authors = []
                for elem in author_elems:
                    author_data = self._extract_single_author_detailed(elem)
                    if author_data:
                        authors.append(author_data)

                if authors:
                    logger.debug(f"Extracted authors: {authors}")
                    return authors

        logger.debug("No authors found with any configured pattern")
        return []

    def _extract_single_author_detailed(self, elem: ET.Element) -> dict[str, Any] | None:
        """Extract detailed information for a single author element."""
        author_data: dict[str, Any] = {}

        # Extract name components
        name_elem = self._find_author_name_element(elem)
        given, surname = self._extract_author_name_parts(name_elem)

        # Store individual name components
        author_data["given_names"] = given
        author_data["surname"] = surname

        # Combine name parts for full name
        name_parts = [p for p in [given, surname] if p]
        if not name_parts:
            return None

        author_data["full_name"] = " ".join(name_parts)

        # Extract affiliation references
        author_data["affiliation_refs"] = self._extract_author_affiliation_refs(elem)

        # Extract ORCID if present
        author_data["orcid"] = self._extract_author_orcid(elem)

        return author_data

    def _find_author_name_element(self, elem: ET.Element) -> ET.Element | None:
        """Find the name element within an author element."""
        name_elem = elem.find(".//name")
        if name_elem is None and elem.tag in ["name", "author"]:
            name_elem = elem
        return name_elem

    def _extract_author_name_parts(self, name_elem: ET.Element | None) -> tuple[str, str]:
        """Extract given name and surname from a name element."""
        if name_elem is not None:
            given = (
                self._extract_with_fallbacks(
                    name_elem, self.config.author_field_patterns["given_names"]
                )
                or ""
            )
            surname = (
                self._extract_with_fallbacks(
                    name_elem, self.config.author_field_patterns["surname"]
                )
                or ""
            )
        else:
            given = ""
            surname = ""

        return given, surname

    def _extract_author_affiliation_refs(self, elem: ET.Element) -> list[str]:
        """Extract affiliation reference IDs from an author element."""
        affiliation_refs = []
        xref_elems = elem.findall(".//xref[@ref-type='aff']")
        for xref in xref_elems:
            rid = xref.get("rid")
            if rid:
                affiliation_refs.append(rid)
        return affiliation_refs

    def _extract_author_orcid(self, elem: ET.Element) -> str | None:
        """Extract and clean ORCID identifier from an author element."""
        for pattern in [
            ".//contrib-id[@contrib-id-type='orcid']",
            ".//ext-link[@ext-link-type='orcid']",
            ".//orcid",
        ]:
            orcid_elem = elem.find(pattern)
            if orcid_elem is not None and orcid_elem.text:
                return TextCleaner.clean_orcid(orcid_elem.text)
        return None
