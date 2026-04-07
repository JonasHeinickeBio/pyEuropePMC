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
            sections = []

            # Extract main body sections
            patterns = {"body": ".//body"}
            bodies = self.extract_elements_by_patterns(patterns, return_type="element")["body"]
            for body_elem in bodies:
                # Find sections within this specific body element
                secs = body_elem.findall(".//sec")
                order = 1
                for sec in secs:
                    section_data = self._extract_section_structure(sec)
                    if section_data:
                        section_data["order"] = order
                        sections.append(section_data)
                        order += 1

            # Extract additional content structures
            sections.extend(self._extract_additional_content_structures())

            logger.debug(f"Extracted {len(sections)} sections from XML: {sections}")
            return sections
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            raise

    def _extract_additional_content_structures(self) -> list[dict[str, str]]:
        """Extract additional content structures like acknowledgments, appendices, etc."""
        structures = []

        # Acknowledgments
        ack_patterns = self.config.content_structure_patterns.get("author_notes", [])
        for pattern in ack_patterns:
            elements = self.root.findall(pattern) if self.root else []
            for elem in elements:
                content = self._get_text_content(elem)
                if content:
                    structures.append(
                        {"title": "Author Notes", "content": content, "type": "author_notes"}
                    )

        # Appendices
        app_patterns = self.config.appendix_patterns.get("app", [])
        for pattern in app_patterns:
            elements = self.root.findall(pattern) if self.root else []
            for elem in elements:
                title = self._extract_flat_texts(elem, ".//title", use_full_text=True)
                content = self._get_text_content(elem)
                if content:
                    structures.append(
                        {
                            "title": title[0] if title else "Appendix",
                            "content": content,
                            "type": "appendix",
                        }
                    )

        # Glossary
        glossary_patterns = self.config.content_structure_patterns.get("glossary", [])
        for pattern in glossary_patterns:
            elements = self.root.findall(pattern) if self.root else []
            for elem in elements:
                content = self._get_text_content(elem)
                if content:
                    structures.append(
                        {"title": "Glossary", "content": content, "type": "glossary"}
                    )

        return structures

    def _extract_section_structure(self, section: ET.Element) -> dict[str, str]:
        """
        Extract section title and content.

        Extracts only direct paragraphs (not from nested sections) to avoid duplication.
        """
        title = self._extract_flat_texts(section, "title", filter_empty=False, use_full_text=True)

        # Extract only direct paragraph children, not from nested sections
        # Use iterchildren to get direct children only (not findall which gets all descendants)
        paragraphs = []
        for child in section:
            if child.tag == "p":
                p_text = self._get_text_content(child)
                if p_text:
                    paragraphs.append(p_text)

        section_data = {
            "title": title[0] if title else "",
            "content": "\n\n".join(paragraphs) if paragraphs else "",
        }
        # Add section type classification - first try XML attribute, then title-based
        section_data["type"] = self._classify_section_type(
            section_data["title"], section.get("sec-type")
        )
        return section_data

    def _classify_section_type(self, title: str, xml_sec_type: str | None = None) -> str:
        """
        Classify section type based on XML attribute or title patterns.

        Args:
            title: Section title text
            xml_sec_type: Optional sec-type attribute from XML

        Returns:
            Section type classification
        """
        # Priority 1: Use XML sec-type attribute if available
        if xml_sec_type:
            xml_type_lower = xml_sec_type.lower().strip()
            # Map common XML sec-type values
            type_mapping = {
                "intro": "introduction",
                "materials": "methods",
                "materials-methods": "methods",
                "results-discussion": "discussion",
                "conclusions": "conclusion",
            }
            # Return mapped value or original if it's a known type
            return type_mapping.get(xml_type_lower, xml_type_lower)

        # Priority 2: Classify based on title patterns
        title_lower = title.lower().strip()

        # Common section type patterns
        type_patterns = {
            "abstract": ["abstract", "summary"],
            "introduction": ["introduction", "background"],
            "methods": [
                "methods",
                "materials and methods",
                "methodology",
                "experimental procedures",
            ],
            "results": ["results", "findings", "data analysis"],
            "discussion": ["discussion", "interpretation"],
            "conclusion": ["conclusion", "conclusions"],
            "acknowledgments": ["acknowledgments", "acknowledgement", "thanks"],
            "references": ["references", "bibliography", "literature cited"],
            "supplementary": ["supplementary", "supplemental", "additional data"],
        }

        for section_type, patterns in type_patterns.items():
            if any(pattern in title_lower for pattern in patterns):
                return section_type

        # Default to "section" for unclassified sections
        return "section"
