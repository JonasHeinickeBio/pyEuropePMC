"""
Plaintext converter for XML to plain text conversion.

This module provides conversion of parsed XML to plain text format.
"""

import logging
from xml.etree import ElementTree as ET

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.author_parser import AuthorParser
from pyeuropepmc.processing.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class PlaintextConverter(BaseParser):
    """Converter for XML to plaintext output."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the plaintext converter."""
        super().__init__(root, config)
        self._author_parser: AuthorParser | None = None

    @property
    def author_parser(self) -> AuthorParser:
        """Get the author parser instance."""
        if self._author_parser is None:
            self._author_parser = AuthorParser(self.root, self.config)
        return self._author_parser

    def to_plaintext(self) -> str:
        """
        Convert the full text XML to plain text.

        Returns
        -------
        str
            Plain text representation of the article
        """
        self._require_root()

        try:
            text_parts = []

            # Extract title
            title_results = self.extract_elements_by_patterns(
                {"title": ".//article-title"}, return_type="text", first_only=True
            )
            if title_results["title"]:
                text_parts.append(f"{title_results['title'][0]}\n\n")

            # Extract authors
            authors = self.author_parser.extract_authors()
            if authors:
                text_parts.append(f"Authors: {', '.join(authors)}\n\n")

            # Extract abstract
            abstract_results = self.extract_elements_by_patterns(
                {"abstract": ".//abstract"}, return_type="text", first_only=True
            )
            if abstract_results["abstract"]:
                text_parts.append(f"Abstract\n{abstract_results['abstract'][0]}\n\n")

            # Extract body sections
            body_results = self.extract_elements_by_patterns(
                {"body": ".//body"}, return_type="element", first_only=True
            )
            if body_results["body"]:
                body_elem = body_results["body"][0]
                for sec in body_elem.iter():
                    if sec.tag == "sec":
                        section_text = self._process_section_plaintext(sec)
                        if section_text:
                            text_parts.append(f"{section_text}\n\n")

            return "".join(text_parts).strip()

        except Exception as e:
            logger.error(f"Error converting to plaintext: {e}")
            raise

    def _process_section_plaintext(self, section: ET.Element) -> str:
        """Process a section element to plain text."""
        text_parts = []

        # Extract section title
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        if titles:
            text_parts.append(f"{titles[0]}\n")

        # Extract paragraphs
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        for para_text in paragraphs:
            text_parts.append(f"{para_text}\n")

        return "\n".join(text_parts)
