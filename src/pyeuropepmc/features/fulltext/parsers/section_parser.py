"""
Section parser for extracting body sections from XML.

This module provides specialized parsing for article sections.
"""

import logging
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser

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

            # This article's own <body> only. `.//body` also returns the body
            # of every <sub-article>, so peer-review reports were returned as
            # article sections (#see _own_bodies).
            bodies = self._own_bodies(self.root) if self.root is not None else []
            for body_elem in bodies:
                # Find sections within this specific body element
                secs = body_elem.findall(".//sec")
                for sec in secs:
                    section_data = self._extract_section_structure(sec)
                    if section_data:
                        sections.append(section_data)

                # Body-level content that sits outside any <sec> - the whole
                # body for publishers like PLOS, and the opening paragraphs
                # elsewhere.
                #
                # `_section_own_elements` rather than `./p`: it stops at <sec>
                # but descends through wrappers, so a <p> inside a <boxed-text>
                # placed directly under <body> is found too. PMC6453151 lost
                # one that way.
                bare_ps = self._section_own_elements(body_elem, "p")
                if bare_ps:
                    para_texts: list[str] = []
                    for p in bare_ps:
                        texts = self._extract_flat_texts(
                            p, ".", filter_empty=True, use_full_text=True
                        )
                        if texts:
                            para_texts.extend(texts)
                    para_text = "\n\n".join(para_texts)
                    if para_text:
                        sections.append({"title": "", "content": para_text})

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

        # Acknowledgments. get_full_text_sections() returned <author-notes>
        # but not <ack>, while to_plaintext() did the reverse - each rendering
        # lost different back matter, and to_markdown() lost all of it.
        for elem in self.root.findall(".//ack") if self.root is not None else []:
            content = self._get_text_content(elem)
            if content:
                structures.append(
                    {"title": "Acknowledgments", "content": content, "type": "acknowledgments"}
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
        """Extract section title and content."""
        title = self._extract_flat_texts(section, "title", filter_empty=False, use_full_text=True)
        # Own paragraphs only: `.//p` also swept up every subsection's text,
        # which was then returned again under the subsection itself (#209).
        paragraphs: list[str] = []
        for para in self._section_own_elements(section, "p"):
            paragraphs.extend(
                self._extract_flat_texts(para, ".", filter_empty=True, use_full_text=True)
            )
        return {
            "title": title[0] if title else "",
            "content": "\n\n".join(paragraphs) if paragraphs else "",
        }
