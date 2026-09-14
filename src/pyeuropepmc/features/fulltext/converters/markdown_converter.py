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

logger = logging.getLogger(__name__)


class MarkdownConverter(BaseParser):
    """Converter for XML to markdown output."""

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
                md_parts.append(f"# {title_results['title'][0]}\n\n")

            # Extract authors
            authors = self.author_parser.extract_authors()
            if authors:
                md_parts.append(f"**Authors:** {', '.join(authors)}\n\n")

            # Extract metadata
            metadata = self.metadata_parser.extract_metadata()
            self._add_metadata_to_markdown(metadata, md_parts)

            # Extract abstract
            abstract_results = self.extract_elements_by_patterns(
                {"abstract": ".//abstract"}, return_type="text", first_only=True
            )
            if abstract_results["abstract"]:
                md_parts.append(f"## Abstract\n\n{abstract_results['abstract'][0]}\n\n")

            # Extract body sections
            # The article's own body, never a <sub-article>'s. See the same
            # note in plaintext_converter.
            own = self._own_bodies(self.root) if self.root is not None else []
            if own:
                body_elem = own[0]
                # Top-level sections only. `iter()` yielded every descendant
                # <sec> as well, and _process_section_markdown already renders
                # subsections beneath their parent - so each one was emitted
                # twice, at two different heading levels (#209).
                # Bare <p> directly under <body>, before any <sec>. Markdown
                # never rendered these at all - it only ever walked sections -
                # so an article whose opening paragraphs sit outside a section
                # lost them entirely (four in PMC12018715, three in
                # PMC12126031). They are in no section, so nothing else emits
                # them.
                bare_texts = [
                    text
                    for para in body_elem.findall("./p")
                    for text in self._extract_flat_texts(
                        para, ".", filter_empty=True, use_full_text=True
                    )
                ]
                for text in bare_texts:
                    md_parts.append(f"{text}\n\n")

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
                text = self._get_text_content(elem)
                if text.strip():
                    md_parts.append(f"## {heading}\n\n{text.strip()}\n\n")

    def _add_metadata_to_markdown(self, metadata: dict[str, Any], md_parts: list[str]) -> None:
        """Add metadata fields to markdown parts."""
        journal = metadata.get("journal")
        if journal and isinstance(journal, dict):
            # Journal metadata is always a dict with title, volume, issue
            journal_title = journal.get("title", "")
            if journal_title:
                md_parts.append(f"**Journal:** {journal_title}\n\n")
        if metadata.get("doi"):
            md_parts.append(f"**DOI:** {metadata['doi']}\n\n")

    def _process_section_markdown(self, section: ET.Element, level: int = 2) -> str:
        """Process a section element to markdown."""
        md_parts = []

        # Extract section title
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        if titles:
            md_parts.append(f"{'#' * level} {titles[0]}\n\n")

        # Extract paragraphs - this section's own, not its subsections' (#209)
        # No stop_at=("list",) here, unlike the plaintext converter: markdown
        # has no separate list rendering, so a <p> inside a <list-item> reaches
        # the output only through this walk. Excluding it would lose the text.
        for para in self._section_own_elements(section, "p"):
            for para_text in self._extract_flat_texts(
                para, ".", filter_empty=True, use_full_text=True
            ):
                md_parts.append(f"{para_text}\n\n")

        # Process subsections. Direct children only: `iter()` reached every
        # descendant, so a grandchild was rendered once at level+1 under its
        # grandparent and again at level+2 under its own parent.
        for subsec in self._child_sections(section):
            subsec_md = self._process_section_markdown(subsec, level=level + 1)
            if subsec_md:
                md_parts.append(subsec_md)

        return "".join(md_parts)
