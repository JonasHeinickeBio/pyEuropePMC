"""
Reference parser for extracting bibliography information from XML.

This module provides specialized parsing for references and citations.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class ReferenceParser(BaseParser):
    """Specialized parser for reference extraction."""

    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
        raw_xml: str | None = None,
    ):
        """Initialize the reference parser."""
        super().__init__(root, config)
        self.raw_xml = raw_xml

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

    def extract_in_text_citations(self) -> list[dict[str, Any]]:
        """
        Extract in-text citations (xrefs) from the full text XML.

        Parses <xref> elements with ref-type="bibr" and links them to references.

        Returns
        -------
        list[dict[str, Any]]
            List of citation dictionaries with position, text, and linked reference data
        """
        self._require_root()

        try:
            citations = []
            # Find all xref elements with ref-type="bibr"
            xrefs = self.root.findall('.//xref[@ref-type="bibr"]')

            for xref in xrefs:
                citation_data = self._extract_single_citation(xref)
                if citation_data:
                    citations.append(citation_data)

            logger.debug(f"Extracted {len(citations)} in-text citations from XML")
            return citations
        except Exception as e:
            logger.error(f"Error extracting in-text citations: {e}")
            raise

    def _extract_single_citation(self, xref: ET.Element) -> dict[str, str | None] | None:
        """Extract data from a single xref citation element."""
        try:
            rid = xref.get("rid")
            if not rid:
                return None

            citation_text = xref.text or ""
            citation_data = {
                "rid": rid,
                "text": citation_text.strip(),
                "ref_type": xref.get("ref-type", "bibr"),
                "position": self._get_element_position(xref),
            }

            # Link to full references (handle multiple rids)
            rid_list = rid.split()
            references = []
            for single_rid in rid_list:
                full_ref = self._get_reference_by_id(single_rid)
                if full_ref:
                    references.append(full_ref)

            if references:
                citation_data["references"] = references

            return citation_data
        except Exception as e:
            logger.warning(f"Error extracting citation from xref: {e}")
            return None

    def _get_reference_by_id(self, ref_id: str) -> dict[str, str | None] | None:
        """Get full reference data by ID."""
        try:
            refs = self.extract_references()
            for ref in refs:
                if ref.get("id") == ref_id:
                    return ref
            return None
        except Exception:
            return None

    def _get_element_position(self, element: ET.Element) -> str | None:
        """Get approximate position of element in document (e.g., section ID)."""
        # Walk up the tree to find section or paragraph context
        parent = element
        while parent is not None:
            if parent.tag in ["sec", "p"]:
                sec_id = parent.get("id")
                if sec_id:
                    return sec_id
            parent = parent.getparent() if hasattr(parent, "getparent") else None
        return None

    def _extract_single_reference(self, ref: ET.Element) -> dict[str, str | None]:
        """Extract data from a single reference element."""
        ref_data: dict[str, str | None] = {}
        ref_data["id"] = ref.get("id")
        ref_data["label"] = self._extract_with_fallbacks(ref, ["label"])

        # Find citation element
        citation, citation_type_found = self._find_citation_element(ref)

        if citation is not None:
            ref_data["citation_type"] = citation_type_found
            # Extract supplied-pmid from raw XML if available
            supplied_pmid = self._extract_local_supplied_pmid(ref.get("id"))
            self._extract_citation_fields(citation, ref_data, supplied_pmid)

        return ref_data

    def _extract_local_supplied_pmid(self, ref_id: str | None) -> str | None:
        """Extract supplied-pmid processing instruction for a specific ref from raw XML."""
        if not self.raw_xml or not ref_id:
            return None

        import re

        # Find the ref element with this ID in the raw XML and extract supplied-pmid within it
        # Pattern: <ref id="ref_id">...</ref> containing <?supplied-pmid ...?>
        ref_pattern = rf'<ref[^>]+id="{re.escape(ref_id)}"[^>]*>(.*?)</ref>'
        ref_match = re.search(ref_pattern, self.raw_xml, re.DOTALL)

        if ref_match:
            ref_content = ref_match.group(1)
            # Look for supplied-pmid within this ref's content
            pmid_pattern = r"<\?supplied-pmid\s+([^?>]+)\?>"
            pmid_match = re.search(pmid_pattern, ref_content)
            if pmid_match:
                return pmid_match.group(1).strip()

        return None

    def _find_citation_element(self, ref: ET.Element) -> tuple[ET.Element | None, str | None]:
        """Find the citation element within a reference."""
        for citation_type in self.config.citation_types["types"]:
            for elem in ref.iter():
                if elem.tag == citation_type:
                    return elem, citation_type
        return None, None

    def _extract_citation_fields(
        self,
        citation: ET.Element,
        ref_data: dict[str, str | None],
        supplied_pmid: str | None = None,
    ) -> None:
        """Extract fields from a citation element."""
        citation_type = ref_data.get("citation_type")

        # For mixed-citation elements, try text parsing first
        if citation_type == "mixed-citation":
            self._parse_mixed_citation_text(citation, ref_data)
            # Still try structured extraction as fallback for any missing fields
            self._extract_structured_citation_fields(citation, ref_data, supplied_pmid)
        else:
            # For structured citations (element-citation, etc.), use XPath extraction
            self._extract_structured_citation_fields(citation, ref_data, supplied_pmid)

    def _extract_reference_authors(self, citation: ET.Element) -> list[str]:
        """Extract author names from a reference citation element."""
        return XMLHelper.extract_nested_texts(
            citation,
            ".//person-group[@person-group-type='author']/name",
            ["surname", "given-names"],
            join=", ",
        )

    def _extract_authors_from_text(self, text: str) -> tuple[str | None, str]:
        """Extract authors from citation text and return remaining text."""
        import html
        import re

        # First decode HTML entities
        text = html.unescape(text)

        # Pattern 1: Multiple authors separated by " & " or " and "
        # Handles: "Aguiar, R. B. d. & Moraes, J. Z. d."
        # Split at the first occurrence of " & " and take everything before the title
        if " & " in text or " && " in text:
            # Find where the title likely starts (capital word longer than 1 char that's not an initial)
            parts = re.split(r"\s*[\&\&]\s*", text, 1)
            if len(parts) == 2:
                # Look for the complete second author by finding the pattern
                second_author_match = re.search(
                    r"([A-Z][a-z]+,\s*[A-Z]\.(\s*[A-Z]\.)*\s*[a-z]+\.)", parts[1]
                )
                if second_author_match:
                    second_author = second_author_match.group(1).strip()
                    author_part = parts[0].strip() + " & " + second_author
                    # Find where title starts
                    title_start = text.find(second_author) + len(second_author)
                    remaining_text = text[title_start:].strip()
                    if remaining_text.startswith("."):
                        remaining_text = remaining_text[1:].strip()
                    return author_part, remaining_text

        # Pattern 2: Authors with "et al."
        author_pattern_et_al = r"^(.+?et al\.)\s+"
        author_match = re.match(author_pattern_et_al, text, re.IGNORECASE)
        if author_match:
            authors_text = author_match.group(1).strip()
            # Clean up common endings
            authors_text = re.sub(r"\s+et\s+al\.?$", " et al.", authors_text, flags=re.IGNORECASE)
            authors = authors_text.rstrip(".,")
            remaining_text = text[len(author_match.group(0)) :].strip()
            return authors, remaining_text

        # Pattern 3: Single author ending with period (common in citations)
        # Handles: "Aguiar, R. B. d."
        author_pattern_single = r"^([^.]+?\.)\s+"
        author_match = re.match(author_pattern_single, text)
        if author_match:
            authors = author_match.group(1).strip().rstrip(",")
            remaining_text = text[len(author_match.group(0)) :].strip()
            return authors, remaining_text

        # Pattern 4: Multiple authors without clear separator, ending before title
        # Look for pattern where authors end and title begins with capital word
        author_pattern_multiple = r"^(.+?)\s+([A-Z][a-z]+.*)"
        author_match = re.match(author_pattern_multiple, text)
        if author_match:
            potential_authors = author_match.group(1).strip()
            potential_title = author_match.group(2).strip()

            # Check if this looks like authors (contains commas, periods, or common author patterns)
            if (
                "," in potential_authors
                or re.search(r"\b[A-Z]\.\s*[A-Z]\.", potential_authors)  # "R. B."
                or re.search(r"\b[A-Z]\.\s*[a-z]+\.", potential_authors)
            ):  # "R. B. d."
                authors = potential_authors.rstrip(",")
                remaining_text = potential_title
                return authors, remaining_text

        return None, text

    def _extract_title_and_source_from_text(
        self, text: str, ref_data: dict[str, str | None] | None = None
    ) -> tuple[str | None, str | None, str | None, str]:
        """Extract title, source, and year from citation text and return remaining text."""
        import html
        import re

        # Decode HTML entities
        text = html.unescape(text)

        # Pattern 1: Title ending with period, followed by italicized journal
        # Handles: "Title. <italic>Journal</italic>. <bold>10</bold>, 1023 (2019)."
        italic_journal_pattern = r"^(.+?)\.\s*<italic>([^<]+)</italic>\.\s*<bold>(\d+)</bold>,\s*(\d+)\s*\(\s*(\d{4})\s*\)"
        italic_match = re.match(italic_journal_pattern, text, re.IGNORECASE)
        if italic_match:
            title = italic_match.group(1).strip()
            source = italic_match.group(2).strip()
            volume = italic_match.group(3)
            pages = italic_match.group(4)
            year = italic_match.group(5)
            remaining_text = text[italic_match.end() :].strip()

            # Store additional fields if ref_data provided
            if ref_data is not None:
                ref_data["volume"] = volume
                ref_data["pages"] = pages

            return title, source, year, remaining_text

        # Pattern 2: Title ending with period, followed by journal name
        # Handles: "Title. Journal..."
        title_pattern = r"^(.+?)\.\s+([A-Z][^0-9]*?)(?=\.|\d|\s+\d{4}|\s*$)"
        title_match = re.match(title_pattern, text)
        if title_match:
            title = title_match.group(1).strip()
            source = title_match.group(2).strip().rstrip(".")
            remaining_text = text[len(title_match.group(0)) :].strip()
            return title, source, None, remaining_text

        # Pattern 3: Title followed by year in parentheses (fallback)
        # Handles: "Title (2019)"
        title_year_pattern = r"^(.+?)\s*\(\s*(\d{4})\s*\)"
        title_year_match = re.match(title_year_pattern, text)
        if title_year_match:
            title = title_year_match.group(1).strip()
            year = title_year_match.group(2)
            remaining_text = text[len(title_year_match.group(0)) :].strip()
            return title, None, year, remaining_text

        # Pattern 4: Title followed by journal and volume/issue info
        # Handles: "Title. Journal volume, pages (year)"
        complex_pattern = r"^(.+?)\.\s+([^,]+),\s*(\d+),\s*([^,\s]+)\s*\(\s*(\d{4})\s*\)"
        complex_match = re.match(complex_pattern, text)
        if complex_match:
            title = complex_match.group(1).strip()
            source = complex_match.group(2).strip()
            volume = complex_match.group(3)
            pages = complex_match.group(4)
            year = complex_match.group(5)
            remaining_text = text[complex_match.end() :].strip()

            # Store additional fields if ref_data provided
            if ref_data is not None:
                ref_data["volume"] = volume
                ref_data["pages"] = pages

            return title, source, year, remaining_text

        return None, None, None, text

    def _parse_mixed_citation_text(
        self, citation: ET.Element, ref_data: dict[str, str | None]
    ) -> None:
        """Parse text content from mixed-citation elements using regex patterns."""
        import re

        from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

        # Get the text content of the mixed-citation element
        text = XMLHelper.get_text_content(citation)
        if not text.strip():
            return

        # Clean up the text (remove extra whitespace, normalize)
        text = re.sub(r"\s+", " ", text.strip())

        # Extract authors
        authors, text = self._extract_authors_from_text(text)
        if authors:
            ref_data["authors"] = authors

        # Extract title and source
        title, source, year, text = self._extract_title_and_source_from_text(text, ref_data)
        if title:
            ref_data["title"] = title
        if source:
            ref_data["source"] = source
        if year and not ref_data.get("year"):
            ref_data["year"] = year

        # Store raw citation only if parsing failed (key fields missing)
        if not ref_data.get("title") or not ref_data.get("source"):
            ref_data["raw_citation"] = text

        # Extract additional patterns
        self._extract_additional_patterns(text, ref_data)

        logger.debug(f"Parsed mixed-citation text: {text} -> {ref_data}")

    def _extract_additional_patterns(self, text: str, ref_data: dict[str, str | None]) -> None:
        """Extract additional patterns from citation text."""
        import re

        # Pattern 3: Year - look for 4-digit year, often in parentheses or after journal
        year_pattern = r"\b(19|20)\d{2}\b"
        year_match = re.search(year_pattern, text)
        if year_match and not ref_data.get("year"):
            ref_data["year"] = year_match.group(0)

        # Pattern 4: Volume and pages - look for patterns like "12, 345" or "12:345-678"
        vol_page_pattern = r"\b(\d+)\s*[,:]\s*(\d+(?:-\d+)?)\b"
        vol_page_match = re.search(vol_page_pattern, text)
        if vol_page_match:
            ref_data["volume"] = vol_page_match.group(1)
            ref_data["pages"] = vol_page_match.group(2)
        else:
            # Fallback: look for volume(year) pattern
            vol_year_pattern = r"\b(\d+)\s*\(\s*(\d{4})\s*\)"
            vol_year_match = re.search(vol_year_pattern, text)
            if vol_year_match:
                ref_data["volume"] = vol_year_match.group(1)
                if not ref_data.get("year"):
                    ref_data["year"] = vol_year_match.group(2)

        # Pattern 5: DOI - look for doi: or http patterns
        doi_pattern = r"(?:doi:\s*|https?://doi\.org/)([^\s,]+)"
        doi_match = re.search(doi_pattern, text, re.IGNORECASE)
        if doi_match:
            ref_data["doi"] = doi_match.group(1).strip(".,")

        # Pattern 6: PMID - look for PMID: followed by numbers
        pmid_pattern = r"pmid:\s*(\d+)"
        pmid_match = re.search(pmid_pattern, text, re.IGNORECASE)
        if pmid_match:
            ref_data["pmid"] = pmid_match.group(1)

    def _extract_structured_citation_fields(
        self,
        citation: ET.Element,
        ref_data: dict[str, str | None],
        supplied_pmid: str | None = None,
    ) -> None:
        """Extract fields from structured citation elements using XPath patterns."""
        # Authors - only set if not already extracted from text
        if not ref_data.get("authors"):
            authors = self._extract_reference_authors(citation)
            ref_data["authors"] = ", ".join(authors) if authors else None

        # Extract basic fields only if not already set
        self._extract_basic_fields_if_missing(citation, ref_data)

        # Extract identifiers (DOI, PMID, PMCID) only if not already set
        self._extract_identifiers_if_missing(citation, ref_data, supplied_pmid)

    def _extract_basic_fields_if_missing(
        self, citation: ET.Element, ref_data: dict[str, str | None]
    ) -> None:
        """Extract basic citation fields if not already set."""
        if not ref_data.get("title"):
            ref_data["title"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["title"], use_full_text=True
            )
        if not ref_data.get("source"):
            ref_data["source"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["source"]
            )
        if not ref_data.get("year"):
            ref_data["year"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["year"]
            )
        if not ref_data.get("volume"):
            ref_data["volume"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["volume"]
            )
        if not ref_data.get("pages"):
            fpage = self._extract_with_fallbacks(citation, self.config.reference_patterns["fpage"])
            lpage = self._extract_with_fallbacks(citation, self.config.reference_patterns["lpage"])
            ref_data["pages"] = XMLHelper.combine_page_range(fpage, lpage)

    def _extract_identifiers_if_missing(
        self,
        citation: ET.Element,
        ref_data: dict[str, str | None],
        supplied_pmid: str | None = None,
    ) -> None:
        """Extract identifiers (DOI, PMID, PMCID) if not already set."""
        if not ref_data.get("doi"):
            ref_data["doi"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["doi"]
            )
        if not ref_data.get("pmid"):
            ref_data["pmid"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["pmid"]
            )
        if not ref_data.get("pmcid"):
            ref_data["pmcid"] = self._extract_with_fallbacks(
                citation, self.config.reference_patterns["pmcid"]
            )

        # Use supplied_pmid as fallback
        if not ref_data.get("pmid") and supplied_pmid:
            ref_data["pmid"] = supplied_pmid
            ref_data["pmid_source"] = "supplied_pmid"
