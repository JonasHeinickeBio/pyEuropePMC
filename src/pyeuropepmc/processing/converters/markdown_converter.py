"""
Markdown converter for XML to markdown conversion.

This module provides conversion of parsed XML to markdown format.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.author_parser import AuthorParser
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.parsers.metadata_parser import MetadataParser

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
            body_results = self.extract_elements_by_patterns(
                {"body": ".//body"}, return_type="element", first_only=True
            )
            if body_results["body"]:
                body_elem = body_results["body"][0]
                for sec in body_elem.iter():
                    if sec.tag == "sec":
                        section_md = self._process_section_markdown(sec, level=2)
                        if section_md:
                            md_parts.append(f"{section_md}\n\n")

            return "".join(md_parts).strip()

        except Exception as e:
            logger.error(f"Error converting to markdown: {e}")
            raise

    def _add_metadata_to_markdown(
        self, metadata: dict[str, Any], md_parts: list[str]
    ) -> None:
        """Add metadata fields to markdown parts."""
        journal = metadata.get("journal")
        if journal:
            # journal is a dict with title, volume, issue
            if isinstance(journal, dict):
                journal_title = journal.get("title", "")
                if journal_title:
                    md_parts.append(f"**Journal:** {journal_title}\n\n")
            else:
                md_parts.append(f"**Journal:** {journal}\n\n")
        if metadata.get("doi"):
            md_parts.append(f"**DOI:** {metadata['doi']}\n\n")

    def _process_section_markdown(self, section: ET.Element, level: int = 2) -> str:
        """Process a section element to markdown."""
        md_parts = []

        # Extract section title
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        if titles:
            md_parts.append(f"{'#' * level} {titles[0]}\n\n")

        # Extract paragraphs
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        for para_text in paragraphs:
            md_parts.append(f"{para_text}\n\n")

        # Process subsections
        for subsec in section.iter():
            if subsec.tag == "sec" and subsec != section:
                subsec_md = self._process_section_markdown(subsec, level=level + 1)
                if subsec_md:
                    md_parts.append(subsec_md)

        return "".join(md_parts)
