"""
Section parser for extracting body sections from XML.

This module provides specialized parsing for article sections.
"""

import logging
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class SectionParser(BaseParser):
    """Specialized parser for section extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the section parser."""
        super().__init__(root, config)

    def get_full_text_sections(self) -> list[dict[str, str]]:
        """
        Extract all body sections with their titles and content.

        Returns
        -------
        list[dict[str, str]]
            List of section dictionaries with title and content
        """
        self._require_root()

        try:
            patterns = {"body": ".//body"}
            bodies = self.extract_elements_by_patterns(patterns, return_type="element")["body"]
            sections = []
            for body_elem in bodies:
                # Find sections within this specific body element
                secs = body_elem.findall(".//sec")
                for sec in secs:
                    section_data = self._extract_section_structure(sec)
                    if section_data:
                        sections.append(section_data)
            logger.debug(f"Extracted {len(sections)} sections from XML: {sections}")
            return sections
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            raise

    def _extract_section_structure(self, section: ET.Element) -> dict[str, str]:
        """Extract section title and content."""
        title = self._extract_flat_texts(section, "title", filter_empty=False, use_full_text=True)
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        return {
            "title": title[0] if title else "",
            "content": "\n\n".join(paragraphs) if paragraphs else "",
        }
