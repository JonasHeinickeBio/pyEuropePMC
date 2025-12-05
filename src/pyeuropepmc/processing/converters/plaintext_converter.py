"""
Plaintext converter for XML to plain text conversion.

This module provides conversion of parsed XML to plain text format.
"""

import logging
from xml.etree import ElementTree as ET  # nosec B405

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
            text_parts: list[str] = []

            self._add_title_to_text(text_parts)
            self._add_authors_to_text(text_parts)
            self._add_abstract_to_text(text_parts)
            self._add_body_sections_to_text(text_parts)
            self._add_acknowledgments_to_text(text_parts)
            self._add_appendices_to_text(text_parts)
            self._add_glossary_to_text(text_parts)

            return "".join(text_parts).strip()

        except Exception as e:
            logger.error(f"Error converting to plaintext: {e}")
            raise

    def _add_title_to_text(self, text_parts: list[str]) -> None:
        """Add title to text parts."""
        title_results = self.extract_elements_by_patterns(
            {"title": ".//article-title"}, return_type="text", first_only=True
        )
        if title_results["title"]:
            text_parts.append(f"{title_results['title'][0]}\n\n")

    def _add_authors_to_text(self, text_parts: list[str]) -> None:
        """Add authors to text parts."""
        authors = self.author_parser.extract_authors()
        if authors:
            text_parts.append(f"Authors: {', '.join(authors)}\n\n")

    def _add_abstract_to_text(self, text_parts: list[str]) -> None:
        """Add abstract to text parts."""
        abstract_results = self.extract_elements_by_patterns(
            {"abstract": ".//abstract"}, return_type="text", first_only=True
        )
        if abstract_results["abstract"]:
            text_parts.append(f"Abstract\n{abstract_results['abstract'][0]}\n\n")

    def _add_body_sections_to_text(self, text_parts: list[str]) -> None:
        """Add body sections to text parts."""
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

    def _add_acknowledgments_to_text(self, text_parts: list[str]) -> None:
        """Add acknowledgments to text parts."""
        ack_results = self.extract_elements_by_patterns(
            {"ack": ".//ack"}, return_type="text", first_only=True
        )
        if ack_results["ack"]:
            text_parts.append(f"Acknowledgments\n{ack_results['ack'][0]}\n\n")

    def _add_appendices_to_text(self, text_parts: list[str]) -> None:
        """Add appendices to text parts."""
        app_results = self.extract_elements_by_patterns({"app": ".//app"}, return_type="element")
        for app_elem in app_results["app"]:
            app_text = self._process_appendix_plaintext(app_elem)
            if app_text:
                text_parts.append(f"{app_text}\n\n")

    def _add_glossary_to_text(self, text_parts: list[str]) -> None:
        """Add glossary to text parts."""
        glossary_results = self.extract_elements_by_patterns(
            {"glossary": ".//glossary"}, return_type="text", first_only=True
        )
        if glossary_results["glossary"]:
            text_parts.append(f"Glossary\n{glossary_results['glossary'][0]}\n\n")

    def _process_section_plaintext(self, section: ET.Element) -> str:
        """Process a section element to plain text."""
        text_parts = []

        # Extract section title
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        if titles:
            text_parts.append(f"{titles[0]}\n")

        # Extract paragraphs with formatting
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        for para_text in paragraphs:
            formatted_text = self._process_formatting_in_text(para_text)
            text_parts.append(f"{formatted_text}\n")

        # Extract lists
        lists = section.findall(".//list")
        for list_elem in lists:
            list_text = self._process_list_plaintext(list_elem)
            if list_text:
                text_parts.append(f"{list_text}\n")

        # Extract tables
        tables = section.findall(".//table")
        for table_elem in tables:
            table_text = self._process_table_plaintext(table_elem)
            if table_text:
                text_parts.append(f"{table_text}\n")

        return "\n".join(text_parts)

    def _process_formatting_in_text(self, text: str) -> str:
        """Process formatting elements within text content."""
        # Handle basic formatting - for now, just return the text
        # In a more advanced implementation, we could add markdown-style formatting
        # For example: bold, italic, superscript, subscript, etc.
        return text

    def _process_list_plaintext(self, list_elem: ET.Element) -> str:
        """Process a list element to plain text."""
        text_parts = []
        list_type = list_elem.get("list-type", "bullet")

        for i, item in enumerate(list_elem.findall(".//list-item"), 1):
            item_text = self._extract_flat_texts(
                item, ".//p", filter_empty=True, use_full_text=True
            )
            if item_text:
                if list_type == "ordered":
                    text_parts.append(f"{i}. {item_text[0]}")
                else:
                    text_parts.append(f"• {item_text[0]}")

        return "\n".join(text_parts)

    def _process_table_plaintext(self, table_elem: ET.Element) -> str:
        """Process a table element to plain text."""
        text_parts = []

        # Extract table caption
        captions = self._extract_flat_texts(
            table_elem, ".//caption", filter_empty=True, use_full_text=True
        )
        if captions:
            text_parts.append(f"Table: {captions[0]}\n")

        # Extract table rows
        rows = table_elem.findall(".//tr")
        if rows:
            # Simple table representation
            for row in rows:
                cells = []
                for cell in row.findall(".//td") + row.findall(".//th"):
                    cell_text = self._extract_flat_texts(
                        cell, ".", filter_empty=True, use_full_text=True
                    )
                    cells.append(cell_text[0] if cell_text else "")
                if cells:
                    text_parts.append(" | ".join(cells))

        return "\n".join(text_parts)

    def _process_appendix_plaintext(self, app_elem: ET.Element) -> str:
        """Process an appendix element to plain text."""
        text_parts = []

        # Extract appendix title
        titles = self._extract_flat_texts(
            app_elem, ".//title", filter_empty=True, use_full_text=True
        )
        if titles:
            text_parts.append(f"Appendix: {titles[0]}")
        else:
            text_parts.append("Appendix")

        # Extract appendix content
        content = self._extract_flat_texts(app_elem, ".//p", filter_empty=True, use_full_text=True)
        for para_text in content:
            formatted_text = self._process_formatting_in_text(para_text)
            text_parts.append(f"{formatted_text}")

        return "\n".join(text_parts)
