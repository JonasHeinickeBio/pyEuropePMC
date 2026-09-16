"""
Plaintext converter for XML to plain text conversion.

This module provides conversion of parsed XML to plain text format.
"""

import logging
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.author_parser import AuthorParser
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.utils.flat_blocks import (
    FlatBlock,
    iter_flat_blocks,
    plain_text,
    table_plain_text,
)

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
            self._add_author_notes_to_text(text_parts)
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
        # `first_only=True` over `.//body` happened to pick the article's own
        # body because it comes first in document order. Say so explicitly:
        # a <sub-article> body must never be rendered as the article's text.
        own = self._own_bodies(self.root) if self.root is not None else []
        if own:
            body_elem = own[0]
            for sec in body_elem.iter():
                if sec.tag == "sec":
                    section_text = self._process_section_plaintext(sec)
                    if section_text:
                        text_parts.append(f"{section_text}\n\n")

            # Content directly under <body>, with no <sec> wrapper - the
            # opening paragraphs of many articles, and the whole body for
            # publishers like PLOS.
            #
            # This used to run only when the document had no <sec> at all, to
            # dodge the duplication that has since been fixed (#209). The guard
            # silently dropped those paragraphs from every article that had
            # both: four in PMC12018715, three in PMC12126031. Content in no
            # section is emitted by no section, so nothing duplicates it. The
            # walk stops at <sec> but descends through wrappers, so a <p>
            # inside a <boxed-text> directly under <body> is found too
            # (PMC6453151).
            bare_texts = self._blocks_plaintext(body_elem)
            if bare_texts:
                text_parts.append("\n".join(bare_texts) + "\n\n")

    def _add_acknowledgments_to_text(self, text_parts: list[str]) -> None:
        """Add acknowledgments to text parts."""
        ack_results = self.extract_elements_by_patterns(
            {"ack": ".//ack"}, return_type="text", first_only=True
        )
        if ack_results["ack"]:
            text_parts.append(f"Acknowledgments\n{ack_results['ack'][0]}\n\n")

    def _add_author_notes_to_text(self, text_parts: list[str]) -> None:
        """Add author notes - correspondence, contributions, competing interests.

        get_full_text_sections() has always returned these; to_plaintext() did
        not, so the two renderings of the same document disagreed about what
        the back matter contained.
        """
        notes = self.extract_elements_by_patterns(
            {"notes": ".//author-notes"}, return_type="text", first_only=True
        )
        if notes["notes"]:
            text_parts.append(f"Author Notes\n{notes['notes'][0]}\n\n")

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

        # The section's own blocks - not its subsections', which are rendered
        # as sections in their own right (#209) - in document order.
        #
        # This collected the section's <p> elements, then its lists, then its
        # tables, which moved every list and table after the paragraphs around
        # it, and rendered nothing else: a figure placed directly in a section
        # lost its label and caption title, a table its label, a code listing
        # everything. It also had to choose, for a table inside a paragraph,
        # between rendering the table's text twice and losing part of it.
        # `iter_flat_blocks` gives every element to exactly one block instead.
        text_parts.extend(f"{text}\n" for text in self._blocks_plaintext(section))

        return "\n".join(text_parts)

    def _blocks_plaintext(self, container: ET.Element) -> list[str]:
        """The blocks ``container`` owns, each as plain text, in document order."""
        texts: list[str] = []
        for block in iter_flat_blocks(container):
            text = plain_text(block)
            if block.kind == "paragraph":
                text = self._process_formatting_in_text(text)
            if text:
                texts.append(text)
        return texts

    def _process_formatting_in_text(self, text: str) -> str:
        """Process formatting elements within text content."""
        # Handle basic formatting - for now, just return the text
        # In a more advanced implementation, we could add markdown-style formatting
        # For example: bold, italic, superscript, subscript, etc.
        return text

    def _process_list_plaintext(self, list_elem: ET.Element) -> str:
        """Process a list element to plain text.

        Direct children only, and the whole of each item: `.//list-item` also
        matched the items of nested lists, and taking the first <p> of each
        lost the rest of an item with two paragraphs.
        """
        return plain_text(FlatBlock("list", list_elem))

    def _process_table_plaintext(self, table_elem: ET.Element) -> str:
        """Render a <table-wrap> (or a bare <table>) to plain text.

        Label and caption, one line per row laid out with its spans, then the
        footer. Only the caption, the cells and the footer were rendered before:
        a table's label reached no rendering at all.
        """
        return table_plain_text(table_elem)

    def _process_appendix_plaintext(self, app_elem: ET.Element) -> str:
        """Process an appendix element to plain text.

        Its blocks, like a section's, and then its own sections. Only the
        appendix's <p> were rendered, so an appendix that is a table came out
        as its title alone.
        """
        text_parts = []

        titles = self._extract_flat_texts(app_elem, "title", filter_empty=True, use_full_text=True)
        text_parts.append(f"Appendix: {titles[0]}" if titles else "Appendix")
        text_parts.extend(self._blocks_plaintext(app_elem))
        for sec in app_elem.iter():
            if sec.tag == "sec":
                section_text = self._process_section_plaintext(sec)
                if section_text:
                    text_parts.append(section_text)

        return "\n".join(text_parts)
