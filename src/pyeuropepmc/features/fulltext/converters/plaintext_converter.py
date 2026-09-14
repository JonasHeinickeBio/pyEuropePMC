"""
Plaintext converter for XML to plain text conversion.

This module provides conversion of parsed XML to plain text format.
"""

import logging
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.author_parser import AuthorParser
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser

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

            # Bare <p> directly under <body>, with no <sec> wrapper - the
            # opening paragraphs of many articles, and the whole body for
            # publishers like PLOS.
            #
            # This used to run only when the document had no <sec> at all, to
            # dodge the duplication that has since been fixed (#209). The guard
            # silently dropped those paragraphs from every article that had
            # both: four in PMC12018715, three in PMC12126031. A bare <p> is in
            # no section, so no section can emit it - there is nothing left to
            # duplicate against.
            # `_section_own_elements` rather than `./p`: it stops at <sec> but
            # descends through wrappers, so a <p> inside a <boxed-text> sitting
            # directly under <body> is found too. PMC6453151 lost one that way.
            bare_texts = [
                text
                for para in self._section_own_elements(body_elem, "p")
                if (text := self._text_excluding(para, "list"))
            ]
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

        # Extract paragraphs with formatting. Own paragraphs only - `.//p` here
        # duplicated every subsection's text into its parent as well (#209).
        # <list> is rendered separately below, so it is excluded twice over:
        # `stop_at` keeps a list's own <p> out of this list, and
        # `_text_excluding` drops the list's text from a <p> that wraps one.
        #
        # `table-wrap` is deliberately NOT excluded, even though the renderer
        # below now covers caption, cells and footer. Measured over 19,964
        # body sentences, excluding it saved 35 duplicates and cost 106
        # sentences outright - a table subtree carries more than those three
        # parts. Leaving a table's text in its wrapping paragraph duplicates
        # it; removing it loses it, and duplication is the safer failure.
        # Two different mechanisms, and they are not interchangeable:
        #
        # `stop_at` decides which <p> count as this section's own. A <p> inside
        # a <list-item>, a table cell or a table <caption> is rendered by the
        # list/table renderers below, so it must not be collected here too.
        #
        # `_text_excluding` decides what a collected <p> contributes. It is
        # applied to <list> only. Dropping a <table-wrap> subtree from a <p>
        # that wraps one cost 106 sentences outright over the corpus: a table
        # subtree carries more than the caption, cells and footer the renderer
        # covers, and the rest has nowhere else to go.
        paragraphs = [
            text
            for para in self._section_own_elements(section, "p", stop_at=("list", "table-wrap"))
            if (text := self._text_excluding(para, "list"))
        ]
        for para_text in paragraphs:
            formatted_text = self._process_formatting_in_text(para_text)
            text_parts.append(f"{formatted_text}\n")

        # Extract lists
        lists = self._section_own_elements(section, "list")
        for list_elem in lists:
            list_text = self._process_list_plaintext(list_elem)
            if list_text:
                text_parts.append(f"{list_text}\n")

        # Prefer <table-wrap> over the bare <table> it contains: the caption
        # and <table-wrap-foot> are siblings of <table>, so selecting the inner
        # element put them out of reach. The walk stops at whichever it matches
        # first, so a wrapper is never returned alongside its own table, and a
        # <table> with no wrapper is still found.
        # `stop_at=("p",)`: a table nested inside a paragraph is already
        # carried by that paragraph's own text, so rendering it here as well
        # would emit it twice. Only tables that are siblings of the section's
        # paragraphs need rendering.
        tables = self._section_own_elements(section, "table-wrap", "table", stop_at=("p",))
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

        # Direct children only, and the whole of each item.
        #
        # This took `.//list-item`, which also matched the items of nested
        # lists, and then rendered only `item_text[0]` - the first <p> of each.
        # An item with two paragraphs lost the second; an item holding text
        # directly, with no <p> at all, produced nothing. That loss used to be
        # hidden because the enclosing <p> emitted the list's text as part of
        # its own; now that it no longer does, this has to be complete.
        # `itertext()` already carries any nested list, which is why the search
        # is `./list-item` and not `.//list-item`.
        for i, item in enumerate(list_elem.findall("./list-item"), 1):
            item_text = " ".join("".join(item.itertext()).split())
            if item_text:
                marker = f"{i}. " if list_type == "ordered" else "• "
                text_parts.append(f"{marker}{item_text}")

        return "\n".join(text_parts)

    def _process_table_plaintext(self, table_elem: ET.Element) -> str:
        """Render a <table-wrap> (or a bare <table>) to plain text.

        Caption, rows and footer. The footer carries the table's notes and
        abbreviation keys; neither it nor the caption was rendered before,
        because this was only ever handed the inner <table>.
        """
        text_parts = []

        captions = self._extract_flat_texts(
            table_elem, ".//caption", filter_empty=True, use_full_text=True
        )
        if captions:
            text_parts.append(f"Table: {captions[0]}\n")

        for row in table_elem.findall(".//tr"):
            cells = []
            for cell in row.findall(".//td") + row.findall(".//th"):
                # The whole cell: taking only the first extracted string lost
                # the rest of a cell holding several <p>.
                cells.append(" ".join("".join(cell.itertext()).split()))
            if cells:
                text_parts.append(" | ".join(cells))

        for foot in table_elem.findall(".//table-wrap-foot"):
            foot_text = " ".join("".join(foot.itertext()).split())
            if foot_text:
                text_parts.append(foot_text)

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
