"""
Markdown converter for XML to markdown conversion.

This module provides conversion of parsed XML to markdown format.
"""

import logging
from typing import Any, ClassVar
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.author_parser import AuthorParser
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.parsers.metadata_parser import MetadataParser
from pyeuropepmc.features.fulltext.utils.flat_blocks import (
    FlatBlock,
    code_fence,
    code_text,
    definition_items,
    escape_markdown,
    float_parts,
    formula_text,
    iter_flat_blocks,
    list_markers,
    markdown_table,
    table_parts,
)

logger = logging.getLogger(__name__)


class MarkdownConverter(BaseParser):
    """Converter for XML to markdown output.

    Every piece of text taken from the document is escaped with
    :func:`escape_markdown`, so a renderer shows it as written. Nothing was:
    "DRB1*0402 ... DQB1*0503" opened an emphasis running to the next asterisk,
    and a literal "<node>" was passed through as an HTML tag.
    """

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the markdown converter."""
        super().__init__(root, config)
        self._author_parser: AuthorParser | None = None
        self._metadata_parser: MetadataParser | None = None

    @property
    def author_parser(self) -> AuthorParser:
        """Get the author parser instance."""
        if self._author_parser is None:
            self._author_parser = AuthorParser(self.root, self.config)
        return self._author_parser

    @property
    def metadata_parser(self) -> MetadataParser:
        """Get the metadata parser instance."""
        if self._metadata_parser is None:
            self._metadata_parser = MetadataParser(self.root, self.config)
        return self._metadata_parser

    def to_markdown(self) -> str:
        """
        Convert the full text XML to Markdown format.

        Returns
        -------
        str
            Markdown representation of the article
        """
        self._require_root()

        try:
            md_parts = []

            # Extract title
            title_results = self.extract_elements_by_patterns(
                {"title": ".//article-title"}, return_type="text", first_only=True
            )
            if title_results["title"]:
                md_parts.append(f"# {escape_markdown(title_results['title'][0])}\n\n")

            # Extract authors
            authors = self.author_parser.extract_authors()
            if authors:
                names = ", ".join(escape_markdown(author) for author in authors)
                md_parts.append(f"**Authors:** {names}\n\n")

            # Extract metadata
            metadata = self.metadata_parser.extract_metadata()
            self._add_metadata_to_markdown(metadata, md_parts)

            # Extract abstract
            abstract_results = self.extract_elements_by_patterns(
                {"abstract": ".//abstract"}, return_type="text", first_only=True
            )
            if abstract_results["abstract"]:
                abstract = escape_markdown(abstract_results["abstract"][0])
                md_parts.append(f"## Abstract\n\n{abstract}\n\n")

            # Extract body sections
            # The article's own body, never a <sub-article>'s. See the same
            # note in plaintext_converter.
            own = self._own_bodies(self.root) if self.root is not None else []
            if own:
                body_elem = own[0]
                # Content directly under <body>, before any <sec>. Markdown
                # never rendered it at all - it only ever walked sections - so
                # an article whose opening paragraphs sit outside a section
                # lost them entirely (four in PMC12018715, three in
                # PMC12126031). It is in no section, so nothing else emits it.
                md_parts.extend(self._blocks_markdown(body_elem))

                # Top-level sections only. `iter()` yielded every descendant
                # <sec> as well, and _process_section_markdown already renders
                # subsections beneath their parent - so each one was emitted
                # twice, at two different heading levels (#209).
                for sec in self._child_sections(body_elem):
                    section_md = self._process_section_markdown(sec, level=2)
                    if section_md:
                        md_parts.append(f"{section_md}\n\n")

            self._add_back_matter_to_markdown(md_parts)

            return "".join(md_parts).strip()

        except Exception as e:
            logger.error(f"Error converting to markdown: {e}")
            raise

    #: Back matter, in the order it is rendered. to_markdown() emitted none of
    #: it: acknowledgments, author notes, appendices and the glossary were all
    #: dropped, though to_plaintext() and get_full_text_sections() each carried
    #: some. The three renderings of one document disagreed about its content.
    BACK_MATTER: ClassVar[tuple[tuple[str, str], ...]] = (
        ("Acknowledgments", ".//ack"),
        ("Author Notes", ".//author-notes"),
        ("Appendix", ".//app"),
        ("Glossary", ".//glossary"),
    )

    def _add_back_matter_to_markdown(self, md_parts: list[str]) -> None:
        """Render acknowledgments, author notes, appendices and glossary."""
        if self.root is None:
            return
        for heading, pattern in self.BACK_MATTER:
            for elem in self.root.findall(pattern):
                if heading == "Appendix":
                    # An appendix is laid out like a section: its tables and
                    # figures as blocks, not run together into one paragraph.
                    appendix = self._process_section_markdown(elem, level=2, prefix="Appendix")
                    if appendix.strip():
                        md_parts.append(f"{appendix}\n\n")
                    continue
                text = self._get_text_content(elem)
                if text.strip():
                    md_parts.append(f"## {heading}\n\n{escape_markdown(text.strip())}\n\n")

    def _add_metadata_to_markdown(self, metadata: dict[str, Any], md_parts: list[str]) -> None:
        """Add metadata fields to markdown parts."""
        journal = metadata.get("journal")
        if journal and isinstance(journal, dict):
            # Journal metadata is always a dict with title, volume, issue
            journal_title = journal.get("title", "")
            if journal_title:
                md_parts.append(f"**Journal:** {escape_markdown(journal_title)}\n\n")
        if metadata.get("doi"):
            md_parts.append(f"**DOI:** {escape_markdown(metadata['doi'])}\n\n")

    def _process_section_markdown(
        self, section: ET.Element, level: int = 2, prefix: str = ""
    ) -> str:
        """Process a section (or appendix) element to markdown."""
        md_parts = []

        # Extract section title
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        heading = ": ".join(escape_markdown(part) for part in (prefix, *titles[:1]) if part)
        if heading:
            md_parts.append(f"{'#' * level} {heading}\n\n")

        # This section's own blocks, in document order - not its subsections'
        # (#209). Only the section's <p> used to be rendered: a table lost its
        # label and every cell outside a <p>, a figure its label and caption
        # title, and a code listing everything.
        md_parts.extend(self._blocks_markdown(section))

        # Process subsections. Direct children only: `iter()` reached every
        # descendant, so a grandchild was rendered once at level+1 under its
        # grandparent and again at level+2 under its own parent.
        for subsec in self._child_sections(section):
            subsec_md = self._process_section_markdown(subsec, level=level + 1)
            if subsec_md:
                md_parts.append(subsec_md)

        return "".join(md_parts)

    def _blocks_markdown(self, container: ET.Element) -> list[str]:
        """The blocks ``container`` owns as Markdown, each ending in a blank line."""
        rendered: list[str] = []
        for block in iter_flat_blocks(container):
            markdown = self._block_markdown(block)
            if markdown:
                rendered.append(f"{markdown}\n\n")
        return rendered

    def _block_markdown(self, block: FlatBlock) -> str:  # noqa: C901
        """One block as Markdown."""
        element = block.element
        if block.kind == "paragraph":
            return escape_markdown(block.text)
        if block.kind == "code":
            code = code_text(element)
            if not code:
                return ""
            fence = code_fence(code)
            language = element.get("language", element.get("lang", ""))
            return f"{fence}{language}\n{code}\n{fence}"
        if block.kind in ("figure", "supplementary"):
            label, text = float_parts(element)
            return self._labelled(label, text)
        if block.kind == "formula":
            return escape_markdown(formula_text(element))
        if block.kind == "list":
            return "\n".join(
                f"{marker}{escape_markdown(item)}"
                for marker, item in list_markers(element, numbered="{}. ", bullet="- ")
            )
        if block.kind == "definition_list":
            return "\n\n".join(
                self._labelled(term, definition) for term, definition in definition_items(element)
            )
        if block.kind == "table":
            parts = table_parts(element)
            pieces = [self._labelled(parts.label, parts.caption)]
            if parts.grid is not None:
                pieces.append(markdown_table(parts.grid))
            pieces.extend(escape_markdown(p) for p in (parts.footer, parts.other))
            return "\n\n".join(piece for piece in pieces if piece)
        return escape_markdown(self._get_text_content(element))

    @staticmethod
    def _labelled(label: str, text: str) -> str:
        """``**label** text``, each escaped; either may be empty."""
        if label:
            return f"**{escape_markdown(label)}** {escape_markdown(text)}".rstrip()
        return escape_markdown(text)
