"""
Reference parser for extracting bibliography information from XML.

This module provides specialized parsing for references and citations.
"""

import logging
from xml.etree import ElementTree as ET

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class ReferenceParser(BaseParser):
    """Specialized parser for reference extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the reference parser."""
        super().__init__(root, config)

    def extract_references(self) -> list[dict[str, str | None]]:
        """
        Extract references/bibliography from the full text XML.

        Returns
        -------
        list[dict[str, str | None]]
            List of reference dictionaries with extracted metadata
        """
        self._require_root()

        try:
            refs = self.extract_elements_by_patterns({"ref": ".//ref"}, return_type="element")[
                "ref"
            ]
            references = []
            for ref in refs:
                ref_data = self._extract_single_reference(ref)
                references.append(ref_data)
            logger.debug(f"Extracted {len(references)} references from XML: {references}")
            return references
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
            raise

    def _extract_single_reference(self, ref: ET.Element) -> dict[str, str | None]:
        """Extract data from a single reference element."""
        ref_data: dict[str, str | None] = {}
        ref_data["id"] = ref.get("id")
        ref_data["label"] = self._extract_with_fallbacks(ref, ["label"])

        # Find citation element
        citation, citation_type_found = self._find_citation_element(ref)

        if citation is not None:
            ref_data["citation_type"] = citation_type_found
            self._extract_citation_fields(citation, ref_data)

        return ref_data

    def _find_citation_element(
        self, ref: ET.Element
    ) -> tuple[ET.Element | None, str | None]:
        """Find the citation element within a reference."""
        for citation_type in self.config.citation_types:
            for elem in ref.iter():
                if elem.tag == citation_type:
                    return elem, citation_type
        return None, None

    def _extract_citation_fields(
        self, citation: ET.Element, ref_data: dict[str, str | None]
    ) -> None:
        """Extract fields from a citation element."""
        # Authors
        authors = self._extract_reference_authors(citation)
        ref_data["authors"] = ", ".join(authors) if authors else None

        # Extract fields using fallback patterns
        ref_data["title"] = self._extract_with_fallbacks(
            citation, self.config.reference_patterns["title"], use_full_text=True
        )
        ref_data["source"] = self._extract_with_fallbacks(
            citation, self.config.reference_patterns["source"]
        )
        ref_data["year"] = self._extract_with_fallbacks(
            citation, self.config.reference_patterns["year"]
        )
        ref_data["volume"] = self._extract_with_fallbacks(
            citation, self.config.reference_patterns["volume"]
        )

        # Page range
        fpage = self._extract_with_fallbacks(citation, self.config.reference_patterns["fpage"])
        lpage = self._extract_with_fallbacks(citation, self.config.reference_patterns["lpage"])
        ref_data["pages"] = XMLHelper.combine_page_range(fpage, lpage)

        # DOI and PMID
        ref_data["doi"] = self._extract_with_fallbacks(
            citation, self.config.reference_patterns["doi"]
        )
        ref_data["pmid"] = self._extract_with_fallbacks(
            citation, self.config.reference_patterns["pmid"]
        )

    def _extract_reference_authors(self, citation: ET.Element) -> list[str]:
        """Extract author names from a reference citation element."""
        return XMLHelper.extract_nested_texts(
            citation,
            ".//person-group[@person-group-type='author']/name",
            ["given-names", "surname"],
            join=" ",
        )
