"""
Full text XML parser for Europe PMC articles.

This module provides functionality for parsing full text XML files from Europe PMC
and converting them to different output formats including metadata extraction,
markdown, plaintext, and table extraction.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any
from xml.etree import (
    ElementTree as ET,  # nosec B405 - Only used for type hints, actual parsing uses defusedxml
)

import defusedxml.ElementTree as DefusedET

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError

logger = logging.getLogger(__name__)

__all__ = ["FullTextXMLParser", "ElementPatterns", "DocumentSchema"]


@dataclass
class ElementPatterns:
    """
    Configuration for XML element patterns with fallbacks.

    This class defines flexible patterns for extracting various elements from
    different XML schema variations (JATS, NLM, custom).

    Examples
    --------
    >>> # Use default patterns
    >>> config = ElementPatterns()
    >>>
    >>> # Customize citation patterns
    >>> config = ElementPatterns(
    ...     citation_types=["element-citation", "mixed-citation", "nlm-citation"]
    ... )
    """

    # Bibliographic citation patterns (ordered by preference)
    citation_types: list[str] = field(
        default_factory=lambda: ["element-citation", "mixed-citation", "nlm-citation", "citation"]
    )

    # Author element patterns (XPath to author containers)
    author_element_patterns: list[str] = field(
        default_factory=lambda: [
            ".//contrib[@contrib-type='author']",  # Full contrib element
            ".//contrib[@contrib-type='author']/name",  # Name element (fallback)
            ".//author-group/author",
            ".//author",
            ".//name",
        ]
    )

    # Author name field patterns with fallbacks
    author_field_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "surname": [".//surname", ".//family", ".//last-name", ".//lname"],
            "given_names": [
                ".//given-names",
                ".//given-name",
                ".//given",
                ".//forename",
                ".//first-name",
                ".//fname",
            ],
            "suffix": [".//suffix"],
            "prefix": [".//prefix"],
            "role": [".//role"],
        }
    )

    # Journal metadata patterns
    journal_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "title": [".//journal-title", ".//source", ".//journal"],
            "issn": [".//issn"],
            "publisher": [".//publisher-name", ".//publisher"],
            "publisher_loc": [".//publisher-loc", ".//publisher-location"],
            "volume": [".//volume", ".//vol"],
            "issue": [".//issue"],
        }
    )

    # Article metadata patterns
    article_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "title": [".//article-title", ".//title"],
            "abstract": [".//abstract"],
            "keywords": [".//kwd", ".//keyword"],
            "doi": [".//article-id[@pub-id-type='doi']", ".//doi"],
            "pmid": [".//article-id[@pub-id-type='pmid']", ".//pmid"],
            "pmcid": [".//article-id[@pub-id-type='pmcid']", ".//pmcid"],
        }
    )

    # Table structure patterns
    table_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "wrapper": ["table-wrap", "table-wrapper", "tbl-wrap"],
            "table": ["table"],
            "caption": ["caption", "title", "table-title"],
            "label": ["label"],
            "header": ["thead", "th"],
            "body": ["tbody"],
            "row": ["tr"],
            "cell": ["td", "th"],
        }
    )

    # Reference/citation field patterns
    reference_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "title": [".//article-title", ".//source", ".//title"],
            "source": [".//source", ".//journal", ".//publication"],
            "year": [".//year", ".//date"],
            "month": [".//month"],
            "day": [".//day"],
            "volume": [".//volume", ".//vol"],
            "issue": [".//issue"],
            "fpage": [".//fpage", ".//first-page"],
            "lpage": [".//lpage", ".//last-page"],
            "doi": [
                ".//pub-id[@pub-id-type='doi']",
                ".//doi",
                ".//ext-link[@ext-link-type='doi']",
            ],
            "pmid": [
                ".//pub-id[@pub-id-type='pmid']",
                ".//pmid",
            ],
            "person_group": [".//person-group"],
            "etal": [".//etal"],
        }
    )

    # Inline element patterns (elements to extract or filter out)
    inline_element_patterns: list[str] = field(
        default_factory=lambda: [".//sup", ".//sub", ".//italic", ".//bold", ".//underline"]
    )

    # Cross-reference patterns (for linking to figures, tables, citations)
    xref_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "bibr": [".//xref[@ref-type='bibr']"],  # Bibliography references
            "fig": [".//xref[@ref-type='fig']"],  # Figure references
            "table": [".//xref[@ref-type='table']"],  # Table references
            "supplementary": [".//xref[@ref-type='supplementary-material']"],
        }
    )

    # Media and supplementary material patterns
    media_patterns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "supplementary": [".//supplementary-material", ".//media"],
            "graphic": [".//graphic"],
            "inline_graphic": [".//inline-graphic"],
        }
    )

    # Object identifier patterns
    object_id_patterns: list[str] = field(
        default_factory=lambda: [".//object-id", ".//article-id"]
    )


@dataclass
class DocumentSchema:
    """
    Detected document schema information.

    This class stores information about the XML document structure to enable
    adaptive parsing strategies.

    Attributes
    ----------
    has_tables : bool
        Whether document contains tables
    has_figures : bool
        Whether document contains figures
    has_supplementary : bool
        Whether document contains supplementary materials
    citation_types : list[str]
        Types of citation elements found
    table_structure : str
        Table structure type: "jats", "html", "cals"
    has_acknowledgments : bool
        Whether document has acknowledgments section
    has_funding : bool
        Whether document has funding information
    """

    has_tables: bool = False
    has_figures: bool = False
    has_supplementary: bool = False
    has_acknowledgments: bool = False
    has_funding: bool = False
    citation_types: list[str] = field(default_factory=list)
    table_structure: str = "jats"  # "jats", "html", "cals"


class FullTextXMLParser:
    """Parser for Europe PMC full text XML files with flexible configuration support."""

    # XML namespaces commonly used in PMC articles
    NAMESPACES = {
        "xlink": "http://www.w3.org/1999/xlink",
        "mml": "http://www.w3.org/1998/Math/MathML",
    }

    def __init__(
        self, xml_content: str | ET.Element | None = None, config: ElementPatterns | None = None
    ):
        """
        Initialize the parser with optional XML content or Element and configuration.

        Parameters
        ----------
        xml_content : str or ET.Element, optional
            XML content string or Element to parse
        config : ElementPatterns, optional
            Configuration for element patterns. If None, uses default patterns.

        Examples
        --------
        >>> # Use default configuration
        >>> parser = FullTextXMLParser()
        >>>
        >>> # Use custom configuration
        >>> config = ElementPatterns(citation_types=["element-citation", "mixed-citation"])
        >>> parser = FullTextXMLParser(config=config)
        """
        self.xml_content: str | None = None
        self.root: ET.Element | None = None
        self.config = config or ElementPatterns()
        self._schema: DocumentSchema | None = None
        if xml_content is not None:
            self.parse(xml_content)

    def parse(self, xml_content: str | ET.Element) -> ET.Element:
        """
        Parse XML content (string or Element) and store the root element.

        Parameters
        ----------
        xml_content : str or ET.Element
            XML content string or Element to parse

        Returns
        -------
        ET.Element
            Root element of the parsed XML

        Raises
        ------
        ParsingError
            If XML parsing fails
        """
        if xml_content is None:
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "XML content cannot be None or empty."}
            )

        if isinstance(xml_content, ET.Element):
            self.root = xml_content
            self.xml_content = None
            return self.root
        elif isinstance(xml_content, str):
            if not xml_content.strip():
                raise ParsingError(
                    ErrorCodes.PARSE003, {"message": "XML content cannot be None or empty."}
                )
            try:
                self.xml_content = xml_content
                self.root = DefusedET.fromstring(xml_content)
                return self.root
            except ET.ParseError as e:
                error_msg = f"XML parsing error: {e}. The XML appears malformed."
                logger.error(error_msg)
                raise ParsingError(
                    ErrorCodes.PARSE002, {"error": str(e), "format": "XML", "message": error_msg}
                ) from e
            except Exception as e:
                error_msg = f"Unexpected XML parsing error: {e}"
                logger.error(error_msg)
                raise ParsingError(
                    ErrorCodes.PARSE003, {"error": str(e), "format": "XML", "message": error_msg}
                ) from e
        else:
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "xml_content must be a string or Element."}
            )

    def list_element_types(self) -> list[str]:
        """
        List all unique element tag names in the parsed XML document.

        Returns
        -------
        list of str
            Sorted list of unique element tag names found in the document.

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        element_types = set()
        for elem in self.root.iter():
            # Remove namespace if present
            tag = elem.tag
            if tag.startswith("{"):
                tag = tag.split("}", 1)[1]
            element_types.add(tag)
        return sorted(element_types)

    def validate_schema_coverage(self) -> dict[str, Any]:  # noqa: C901
        """
        Validate schema coverage by analyzing recognized vs unrecognized element tags.

        This method compares all element tags in the document against the patterns
        defined in the ElementPatterns configuration to identify coverage gaps.

        Returns
        -------
        dict[str, Any]
            Dictionary containing:
            - total_elements: Total number of unique element types in document
            - recognized_elements: List of element types covered by config patterns
            - unrecognized_elements: List of element types not covered by config
            - coverage_percentage: Percentage of elements recognized (0-100)
            - unrecognized_count: Count of unrecognized element types
            - element_frequency: Dict mapping each element to its occurrence count

        Raises
        ------
        ParsingError
            If no XML has been parsed

        Examples
        --------
        >>> parser = FullTextXMLParser(xml_content)
        >>> coverage = parser.validate_schema_coverage()
        >>> print(f"Coverage: {coverage['coverage_percentage']:.1f}%")
        >>> print(f"Unrecognized: {coverage['unrecognized_elements']}")
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        # Get all element types in the document
        all_elements = set()
        element_frequency: dict[str, int] = {}

        for elem in self.root.iter():
            # Remove namespace if present
            tag = elem.tag
            if tag.startswith("{"):
                tag = tag.split("}", 1)[1]
            all_elements.add(tag)
            element_frequency[tag] = element_frequency.get(tag, 0) + 1

        # Build set of recognized element patterns from config
        recognized_patterns = set()

        # Extract element names from XPath patterns in config
        def extract_element_from_pattern(pattern: str) -> set[str]:
            """Extract element names from XPath pattern."""
            elements = set()
            # Remove leading .// or /
            pattern = pattern.lstrip("./")
            # Split by / to get path components
            parts = pattern.split("/")
            for part in parts:
                # Remove predicates [...] and get element name
                elem_name = part.split("[")[0].strip()
                if elem_name and not elem_name.startswith("@"):
                    elements.add(elem_name)
            return elements

        # Process citation types
        for citation_type in self.config.citation_types:
            recognized_patterns.add(citation_type)

        # Process author patterns
        for pattern in self.config.author_element_patterns:
            recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process author field patterns
        for patterns_list in self.config.author_field_patterns.values():
            for pattern in patterns_list:
                recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process journal patterns
        for patterns_list in self.config.journal_patterns.values():
            for pattern in patterns_list:
                recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process article patterns
        for patterns_list in self.config.article_patterns.values():
            for pattern in patterns_list:
                recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process table patterns
        for patterns_list in self.config.table_patterns.values():
            if isinstance(patterns_list, list):
                for pattern in patterns_list:
                    recognized_patterns.add(pattern)

        # Process reference patterns
        for patterns_list in self.config.reference_patterns.values():
            for pattern in patterns_list:
                recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process inline element patterns
        for pattern in self.config.inline_element_patterns:
            recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process xref patterns
        for patterns_list in self.config.xref_patterns.values():
            for pattern in patterns_list:
                recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process media patterns
        for patterns_list in self.config.media_patterns.values():
            for pattern in patterns_list:
                recognized_patterns.update(extract_element_from_pattern(pattern))

        # Process object_id patterns
        for pattern in self.config.object_id_patterns:
            recognized_patterns.update(extract_element_from_pattern(pattern))

        # Add common structural elements that are implicitly recognized
        common_structural = {
            "article",
            "front",
            "body",
            "back",
            "sec",
            "p",
            "title",
            "ref-list",
            "ref",
            "fig",
            "graphic",
            "label",
            "caption",
            "supplementary-material",
            "ack",
            "funding-group",
            "aff",
            "name",
            "contrib",
            "contrib-group",
            "author-notes",
            "pub-date",
            "addr-line",  # Address lines in affiliations
            "xref",  # Cross-references
            "person-group",  # Author groups in references
            "etal",  # Et al. indicator
            "media",  # Media elements
            "underline",  # Inline formatting
            "month",  # Date component
            "day",  # Date component
            "object-id",  # Object identifiers
        }
        recognized_patterns.update(common_structural)

        # Calculate recognized vs unrecognized
        recognized_elements = sorted(all_elements & recognized_patterns)
        unrecognized_elements = sorted(all_elements - recognized_patterns)

        # Calculate coverage percentage
        total = len(all_elements)
        recognized_count = len(recognized_elements)
        coverage_pct = (recognized_count / total * 100) if total > 0 else 0

        result = {
            "total_elements": total,
            "recognized_elements": recognized_elements,
            "unrecognized_elements": unrecognized_elements,
            "recognized_count": recognized_count,
            "unrecognized_count": len(unrecognized_elements),
            "coverage_percentage": coverage_pct,
            "element_frequency": element_frequency,
        }

        logger.info(
            f"Schema coverage: {coverage_pct:.1f}% "
            f"({recognized_count}/{total} elements recognized)"
        )
        if unrecognized_elements:
            logger.debug(f"Unrecognized elements: {unrecognized_elements}")

        return result

    def extract_elements_by_patterns(
        self,
        patterns: dict[str, str],
        return_type: str = "text",
        first_only: bool = False,
        get_attribute: dict[str, str] | None = None,
    ) -> dict[str, list[Any]]:
        """
        Extract elements from the parsed XML that match user-defined tag patterns.

        Parameters
        ----------
        patterns : dict
            Keys are output field names, values are XPath-like patterns (relative to root).
        return_type : str, optional
            'text' (default): return text content; 'element': return Element; 'attribute':
            return attribute value (see get_attribute).
        first_only : bool, optional
            If True, only return the first match for each pattern
            (as a single-item list or empty list).
        get_attribute : dict, optional
            If return_type is 'attribute', a dict mapping field name to attribute name to extract.

        Returns
        -------
        dict
            Dictionary where each key is from the input dict and the value is a list of results
            (text, attribute, or element) for all matching elements.

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        results: dict[str, list[Any]] = {}
        for key, pattern in patterns.items():
            matches = self.root.findall(pattern)
            if not matches:
                results[key] = []
                continue
            values: list[Any]
            if return_type == "text":
                values = [self._get_text_content(elem) for elem in matches]
            elif return_type == "element":
                values = matches
            elif return_type == "attribute":
                attr = get_attribute[key] if get_attribute and key in get_attribute else None
                if attr is None:
                    raise ValueError(f"No attribute specified for key '{key}' in get_attribute.")
                values = [elem.get(attr) for elem in matches]
            else:
                raise ValueError(f"Unknown return_type: {return_type}")
            if first_only:
                results[key] = [values[0]] if values else []
            else:
                results[key] = values
        return results

    def _extract_nested_texts(
        self,
        parent: ET.Element,
        outer_pattern: str,
        inner_patterns: list[str],
        join: str = " ",
        filter_empty: bool = True,
    ) -> list[str]:
        """
        Generic helper to extract nested text fields from XML.
        For each element matching outer_pattern, extract/join text from inner_patterns.
        """
        results = []
        for outer in parent.findall(outer_pattern):
            parts = []
            for ipat in inner_patterns:
                found = outer.find(ipat)
                if found is not None and found.text:
                    parts.append(found.text.strip())
            if filter_empty:
                parts = [p for p in parts if p]
            if parts:
                results.append(join.join(parts))
        return results

    def _extract_flat_texts(
        self,
        parent: ET.Element,
        pattern: str,
        filter_empty: bool = True,
        use_full_text: bool = False,
    ) -> list[str]:
        """
        Generic helper to extract flat text fields from XML.
        For each element matching pattern, extract its text.

        Parameters
        ----------
        parent : ET.Element
            Parent element to search within
        pattern : str
            XPath pattern to find elements
        filter_empty : bool
            If True, filter out empty strings
        use_full_text : bool
            If True, use _get_text_content() for deep text extraction
        """
        results = []
        for elem in parent.findall(pattern):
            if use_full_text:
                text = self._get_text_content(elem)
            else:
                text = elem.text.strip() if elem.text else ""
            if not filter_empty or text:
                results.append(text)
        return results

    def _extract_reference_authors(self, citation: ET.Element) -> list[str]:
        """
        Generic helper to extract author names from a reference citation element.
        """
        return self._extract_nested_texts(
            citation,
            ".//person-group[@person-group-type='author']/name",
            ["given-names", "surname"],
            join=" ",
        )

    def _combine_page_range(self, fpage: str | None, lpage: str | None) -> str | None:
        """
        Generic helper to combine first and last page into a page range.
        """
        if fpage and lpage:
            return f"{fpage}-{lpage}"
        elif fpage:
            return fpage
        return None

    def _extract_structured_fields(
        self,
        parent: ET.Element,
        field_patterns: dict[str, str],
        first_only: bool = True,
    ) -> dict[str, Any]:
        """
        Generic helper to extract multiple fields from a parent element as a structured dict.
        Returns dict with extracted values (or None if not found).
        """
        result: dict[str, Any] = {}
        for key, pattern in field_patterns.items():
            matches = parent.findall(pattern)
            if not first_only:
                # For first_only=False, return lists
                result[key] = [self._get_text_content(m) for m in matches] if matches else []
            else:
                # For first_only=True, return single value or None
                if matches:
                    text = self._get_text_content(matches[0])
                    result[key] = text if text else None
                else:
                    result[key] = None
        return result

    def _extract_with_fallbacks(
        self, element: ET.Element, patterns: list[str], use_full_text: bool = False
    ) -> str | None:
        """
        Try multiple element patterns in order until one succeeds.

        This method enables flexible extraction by trying multiple element names/patterns
        in order of preference, returning the first successful match.

        Parameters
        ----------
        element : ET.Element
            Parent element to search within
        patterns : list[str]
            Ordered list of element names/patterns to try
        use_full_text : bool, optional
            Whether to extract all nested text (default: False)

        Returns
        -------
        str or None
            First match found, or None if no patterns match

        Examples
        --------
        >>> # Try both "given-names" and "given"
        >>> name = parser._extract_with_fallbacks(
        ...     author_elem,
        ...     ["given-names", "given", "forename"]
        ... )
        """
        for pattern in patterns:
            results = self._extract_flat_texts(
                element, pattern, filter_empty=True, use_full_text=use_full_text
            )
            if results:
                logger.debug(f"Fallback successful: pattern '{pattern}' matched")
                return results[0]
        logger.debug(f"No fallback patterns matched: {patterns}")
        return None

    def detect_schema(self) -> DocumentSchema:
        """
        Analyze document structure and detect schema patterns.

        This method inspects the XML structure to identify document capabilities
        and variations, enabling adaptive parsing strategies.

        Returns
        -------
        DocumentSchema
            Detected schema information

        Raises
        ------
        ParsingError
            If no XML has been parsed

        Examples
        --------
        >>> parser = FullTextXMLParser(xml_content)
        >>> schema = parser.detect_schema()
        >>> if schema.has_tables:
        ...     tables = parser.extract_tables()
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        if self._schema is not None:
            return self._schema

        schema = DocumentSchema()

        # Detect table structures
        for table_pattern in self.config.table_patterns["wrapper"]:
            if self.root.find(f".//{table_pattern}") is not None:
                schema.has_tables = True
                schema.table_structure = "jats"
                break

        if not schema.has_tables and self.root.find(".//table") is not None:
            schema.has_tables = True
            schema.table_structure = "html"

        # Detect citation types present
        for citation_type in self.config.citation_types:
            if self.root.find(f".//{citation_type}") is not None:
                schema.citation_types.append(citation_type)

        # Detect figures
        schema.has_figures = self.root.find(".//fig") is not None

        # Detect supplementary materials
        schema.has_supplementary = self.root.find(".//supplementary-material") is not None

        # Detect acknowledgments
        schema.has_acknowledgments = self.root.find(".//ack") is not None

        # Detect funding information
        schema.has_funding = self.root.find(".//funding-group") is not None

        logger.debug(f"Detected schema: {schema}")
        self._schema = schema
        return schema

    def _extract_section_structure(self, section: ET.Element) -> dict[str, str]:
        """
        Generic helper to extract section title and content.
        """
        title = self._extract_flat_texts(section, "title", filter_empty=False, use_full_text=True)
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        return {
            "title": title[0] if title else "",
            "content": "\n\n".join(paragraphs) if paragraphs else "",
        }

    def extract_metadata(self) -> dict[str, Any]:
        """
        Extract comprehensive metadata from the full text XML.

        Uses configuration-based fallback patterns for flexible extraction
        across different XML schemas and article types.

        Returns
        -------
        dict
            Dictionary containing extracted metadata including:
            - pmcid: PMC ID
            - doi: DOI
            - identifiers: Dict of all article IDs (pmcid, pmid, doi, publisher-id, etc.)
            - title: Article title
            - authors: List of author names
            - journal: Dict with title, volume, issue, IDs (nlm-ta, iso-abbrev), ISSNs
            - pub_date: Publication date
            - pages: Page range
            - abstract: Article abstract
            - keywords: List of keywords
            - funding: List of funding information (if available)
            - license: License information (if available)
            - publisher: Publisher name and location (if available)
            - categories: Article categories and subjects (if available)

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        try:
            # Extract basic metadata
            metadata = self._extract_basic_metadata()

            # Extract article identifiers
            self._add_article_identifiers(metadata)

            # Extract journal information
            metadata["journal"] = self._extract_journal_metadata()

            # Extract page range
            metadata["pages"] = self._extract_page_range()

            # Extract standard metadata using specialized methods
            metadata["authors"] = self.extract_authors()
            metadata["pub_date"] = self.extract_pub_date()
            metadata["keywords"] = self.extract_keywords()

            # Extract optional metadata fields
            self._add_optional_metadata(metadata)

            logger.debug(
                f"Extracted metadata for PMC{metadata.get('pmcid', 'Unknown')}: {metadata}"
            )
            return metadata
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract metadata from XML"},
            ) from e

    def _extract_basic_metadata(self) -> dict[str, Any]:
        """Extract basic article metadata (pmcid, doi, title, abstract)."""
        return {
            "pmcid": self._extract_with_fallbacks(
                self.root, self.config.article_patterns["pmcid"]
            ),
            "doi": self._extract_with_fallbacks(self.root, self.config.article_patterns["doi"]),
            "title": self._extract_with_fallbacks(
                self.root, self.config.article_patterns["title"], use_full_text=True
            ),
            "abstract": self._extract_with_fallbacks(
                self.root, self.config.article_patterns["abstract"], use_full_text=True
            ),
        }

    def _add_article_identifiers(self, metadata: dict[str, Any]) -> None:
        """Add article identifiers to metadata dict."""
        article_meta_result = self.extract_elements_by_patterns(
            {"article_meta": ".//article-meta"}, return_type="element"
        )

        for article_meta in article_meta_result.get("article_meta", []):
            identifiers = self._extract_all_pub_ids(article_meta, "article-id")
            if identifiers:
                metadata["identifiers"] = identifiers
            break

    def _extract_journal_metadata(self) -> dict[str, Any]:
        """Extract journal information including IDs and ISSNs."""
        journal_info: dict[str, Any] = {
            "title": self._extract_with_fallbacks(
                self.root, self.config.journal_patterns["title"]
            ),
            "volume": self._extract_with_fallbacks(
                self.root, self.config.journal_patterns["volume"]
            ),
            "issue": self._extract_with_fallbacks(
                self.root, self.config.journal_patterns["issue"]
            ),
        }

        # Extract journal IDs and ISSNs using helper
        self._add_journal_ids_and_issns(journal_info)

        return journal_info

    def _add_journal_ids_and_issns(self, journal_info: dict[str, Any]) -> None:
        """Add journal IDs (nlm-ta, iso-abbrev) and ISSNs to journal info."""
        journal_meta_result = self.extract_elements_by_patterns(
            {"journal_meta": ".//journal-meta"}, return_type="element"
        )

        for journal_meta in journal_meta_result.get("journal_meta", []):
            # Extract journal IDs using helper
            temp_parser = FullTextXMLParser()
            temp_parser.root = journal_meta
            nlm_ta_result = temp_parser.extract_elements_by_patterns(
                {"nlm_ta": ".//journal-id[@journal-id-type='nlm-ta']"}, return_type="text"
            )
            if nlm_ta_result.get("nlm_ta"):
                journal_info["nlm_ta"] = nlm_ta_result["nlm_ta"][0]

            iso_abbrev_result = temp_parser.extract_elements_by_patterns(
                {"iso_abbrev": ".//journal-id[@journal-id-type='iso-abbrev']"},
                return_type="text",
            )
            if iso_abbrev_result.get("iso_abbrev"):
                journal_info["iso_abbrev"] = iso_abbrev_result["iso_abbrev"][0]

            # Extract ISSNs using helper
            issn_print_result = temp_parser.extract_elements_by_patterns(
                {"issn_print": ".//issn[@pub-type='ppub']"}, return_type="text"
            )
            if issn_print_result.get("issn_print"):
                journal_info["issn_print"] = issn_print_result["issn_print"][0]

            issn_epub_result = temp_parser.extract_elements_by_patterns(
                {"issn_electronic": ".//issn[@pub-type='epub']"}, return_type="text"
            )
            if issn_epub_result.get("issn_electronic"):
                journal_info["issn_electronic"] = issn_epub_result["issn_electronic"][0]
            break

    def _extract_page_range(self) -> str | None:
        """Extract page range from first and last page."""
        fpage = self._extract_with_fallbacks(self.root, [".//fpage", ".//first-page"])
        lpage = self._extract_with_fallbacks(self.root, [".//lpage", ".//last-page"])
        return self._combine_page_range(fpage, lpage)

    def _add_optional_metadata(self, metadata: dict[str, Any]) -> None:
        """Add optional metadata fields (funding, license, publisher, categories)."""
        funding = self.extract_funding()
        if funding:
            metadata["funding"] = funding

        license_info = self.extract_license()
        if license_info:
            metadata["license"] = license_info

        publisher_info = self.extract_publisher()
        if publisher_info:
            metadata["publisher"] = publisher_info

        categories = self.extract_article_categories()
        if categories:
            metadata["categories"] = categories

    def extract_authors(self) -> list[str]:
        """
        Extract list of author names from XML.

        Uses configuration-based fallback patterns to handle different
        author element structures across XML schemas.

        Returns
        -------
        list[str]
            List of author names as strings (backward compatibility)
        """
        detailed_authors = self.extract_authors_detailed()
        return [
            author.get("full_name", "") for author in detailed_authors if author.get("full_name")
        ]

    def extract_authors_detailed(self) -> list[dict[str, Any]]:
        """
        Extract list of author information from XML.

        Uses configuration-based fallback patterns to handle different
        author element structures across XML schemas.

        Returns
        -------
        list[dict[str, Any]]
            List of author dictionaries, each containing:
            - full_name: Full author name (given-name + surname)
            - given_names: Given/first names
            - surname: Family/last name
            - affiliation_refs: List of affiliation IDs referenced by this author
            - orcid: ORCID identifier if present
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML has been parsed. Call parse() first."},
            )

        # Try each author element pattern in config
        for author_pattern in self.config.author_element_patterns:
            author_elems = self.root.findall(author_pattern)
            if author_elems:
                logger.debug(f"Found {len(author_elems)} authors using pattern: {author_pattern}")
                authors = []
                for elem in author_elems:
                    author_data = self._extract_single_author_detailed(elem)
                    if author_data:
                        authors.append(author_data)

                if authors:
                    logger.debug(f"Extracted authors: {authors}")
                    return authors

        # No authors found with any pattern
        logger.debug("No authors found with any configured pattern")
        return []

    def _extract_single_author_detailed(self, elem: ET.Element) -> dict[str, Any] | None:
        """Extract detailed information for a single author element."""
        author_data: dict[str, Any] = {}

        # Extract name components
        name_elem = self._find_author_name_element(elem)
        given, surname = self._extract_author_name_parts(name_elem)

        # Store individual name components
        author_data["given_names"] = given
        author_data["surname"] = surname

        # Combine name parts for full name
        name_parts = [p for p in [given, surname] if p]
        if not name_parts:
            return None  # Skip authors with no name

        author_data["full_name"] = " ".join(name_parts)

        # Extract affiliation references
        author_data["affiliation_refs"] = self._extract_author_affiliation_refs(elem)

        # Extract ORCID if present
        author_data["orcid"] = self._extract_author_orcid(elem)

        return author_data

    def _find_author_name_element(self, elem: ET.Element) -> ET.Element | None:
        """Find the name element within an author element."""
        # First try to find name element within this author element
        name_elem = elem.find(".//name")
        if name_elem is None and elem.tag in ["name", "author"]:
            # elem is already the name element
            name_elem = elem
        return name_elem

    def _extract_author_name_parts(self, name_elem: ET.Element | None) -> tuple[str, str]:
        """Extract given name and surname from a name element."""
        if name_elem is not None:
            given = (
                self._extract_with_fallbacks(
                    name_elem, self.config.author_field_patterns["given_names"]
                )
                or ""
            )
            surname = (
                self._extract_with_fallbacks(
                    name_elem, self.config.author_field_patterns["surname"]
                )
                or ""
            )
        else:
            given = ""
            surname = ""

        return given, surname

    def _extract_author_affiliation_refs(self, elem: ET.Element) -> list[str]:
        """Extract affiliation reference IDs from an author element."""
        affiliation_refs = []
        xref_elems = elem.findall(".//xref[@ref-type='aff']")
        for xref in xref_elems:
            rid = xref.get("rid")
            if rid:
                affiliation_refs.append(rid)
        return affiliation_refs

    def _extract_author_orcid(self, elem: ET.Element) -> str | None:
        """Extract and clean ORCID identifier from an author element."""
        # Try multiple patterns for ORCID
        for pattern in [
            ".//contrib-id[@contrib-id-type='orcid']",
            ".//ext-link[@ext-link-type='orcid']",
            ".//orcid",
        ]:
            orcid_elem = elem.find(pattern)
            if orcid_elem is not None and orcid_elem.text:
                return self._clean_orcid(orcid_elem.text)
        return None

    def extract_pub_date(self) -> str | None:
        """Extract publication date from XML."""
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )
        for pub_type in ["ppub", "epub", "collection"]:
            patterns = {
                "year": f".//pub-date[@pub-type='{pub_type}']/year",
                "month": f".//pub-date[@pub-type='{pub_type}']/month",
                "day": f".//pub-date[@pub-type='{pub_type}']/day",
            }
            parts = self.extract_elements_by_patterns(patterns, first_only=True)
            date_parts = []
            if parts["year"] and parts["year"][0]:
                date_parts.append(parts["year"][0])
            if parts["month"] and parts["month"][0]:
                date_parts.append(parts["month"][0].zfill(2))
            if parts["day"] and parts["day"][0]:
                date_parts.append(parts["day"][0].zfill(2))
            if date_parts:
                date_str = "-".join(date_parts)
                logger.debug(f"Extracted pub_date: {date_str}")
                return date_str
        logger.debug("No publication date found.")
        return None

    def extract_keywords(self) -> list[str]:
        """Extract keywords from XML."""
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )
        keywords = self._extract_flat_texts(self.root, ".//kwd")
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords

    def extract_affiliations(self) -> list[dict[str, Any]]:
        """
        Extract author affiliations from the full text XML.

        Handles both structured affiliations (with institution/city/country tags)
        and mixed-content affiliations (with superscript markers and multiple institutions).
        Now also extracts institution IDs (ROR, GRID, ISNI).

        Returns
        -------
        list[dict[str, Any]]
            List of affiliation dictionaries, each containing:
            - id: Affiliation ID attribute
            - institution: Institution name (if structured)
            - city: City (if structured)
            - country: Country (if structured)
            - institution_ids: Dict of institution identifiers (ROR, GRID, ISNI, etc.)
            - text: Full text of affiliation
            - markers: Superscript markers (e.g., "1, 2")
            - institution_text: Clean institution text without markers
            - parsed_institutions: List of parsed institutions (if multiple in one element)

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        aff_results = self.extract_elements_by_patterns(
            {"affiliations": ".//aff"}, return_type="element"
        )

        affiliations = []
        for aff_elem in aff_results.get("affiliations", []):
            aff_data: dict[str, Any] = {}

            # Get ID attribute
            aff_data["id"] = aff_elem.get("id")

            # Get full text for reference
            full_text = "".join(aff_elem.itertext()).strip()
            aff_data["text"] = full_text

            # Extract institution IDs (ROR, GRID, ISNI, etc.)
            institution_ids = self._extract_institution_ids(aff_elem)
            if institution_ids:
                aff_data["institution_ids"] = institution_ids

            # Try structured extraction first
            structured = self._extract_structured_fields(
                aff_elem,
                {
                    "institution": ".//institution",
                    "city": ".//city",
                    "country": ".//country",
                },
            )

            # Check if we got structured data
            if any(structured.values()):
                # Use structured data
                aff_data.update(structured)
            else:
                # Fallback: Parse mixed content manually
                # Extract superscript markers (affiliation numbers) using generic helper
                markers = self._extract_inline_elements(aff_elem, [".//sup"])
                if markers:
                    aff_data["markers"] = ", ".join(markers)

                    # Get text without superscripts using generic helper
                    clean_text = self._get_text_without_inline_elements(aff_elem, [".//sup"])
                    aff_data["institution_text"] = clean_text

                    # Try to parse multiple institutions separated by "and"
                    if clean_text:  # Only parse if we have text
                        parsed_institutions = self._parse_multi_institution_affiliation(
                            clean_text, markers
                        )
                        if len(parsed_institutions) > 1:
                            aff_data["parsed_institutions"] = parsed_institutions
                        elif len(parsed_institutions) == 1:
                            # Single institution - extract fields from parsed data
                            inst = parsed_institutions[0]
                            if inst.get("name"):
                                aff_data["institution"] = inst["name"]
                            if inst.get("city"):
                                aff_data["city"] = inst["city"]
                            if inst.get("postal_code"):
                                aff_data["postal_code"] = inst["postal_code"]
                            if inst.get("country"):
                                aff_data["country"] = inst["country"]
                else:
                    # No markers - try to parse the text directly
                    clean_text = "".join(aff_elem.itertext()).strip()
                    if clean_text:
                        # Try to parse as single institution
                        parsed = self._parse_single_institution(clean_text, [], 0)
                        if parsed.get("name") or parsed.get("city") or parsed.get("country"):
                            if parsed.get("name"):
                                aff_data["institution"] = parsed["name"]
                            if parsed.get("city"):
                                aff_data["city"] = parsed["city"]
                            if parsed.get("postal_code"):
                                aff_data["postal_code"] = parsed["postal_code"]
                            if parsed.get("country"):
                                aff_data["country"] = parsed["country"]

            affiliations.append(aff_data)

        logger.debug(f"Extracted {len(affiliations)} affiliations")
        return affiliations

    def _parse_multi_institution_affiliation(
        self, text: str, markers: list[str]
    ) -> list[dict[str, str | None]]:
        """
        Parse affiliations with multiple institutions separated by 'and'.

        Parameters
        ----------
        text : str
            Clean affiliation text without superscript markers
        markers : list[str]
            List of superscript markers (e.g., ['1', '2'])

        Returns
        -------
        list[dict[str, str | None]]
            List of parsed institutions with fields:
            - marker: Corresponding superscript marker
            - name: Institution name
            - city: City
            - postal_code: Postal/ZIP code
            - country: Country
            - text: Raw text if parsing failed
        """
        institutions = []

        # Split by common separators like "and"
        parts = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)

        for i, part in enumerate(parts):
            part = part.strip().strip(",").strip()
            if not part:
                continue

            # Clean the part by removing emails and other non-geographic data
            part = self._clean_affiliation_text(part)

            # Try to extract components using improved patterns
            institution = self._parse_single_institution(part, markers, i)
            institutions.append(institution)

        return institutions

    def _clean_affiliation_text(self, text: str) -> str:
        """
        Clean affiliation text by removing emails and other non-geographic data.

        Parameters
        ----------
        text : str
            Raw affiliation text

        Returns
        -------
        str
            Cleaned text with non-geographic data removed
        """
        # Remove email addresses
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "", text)

        # Remove URLs
        text = re.sub(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            "",
            text,
        )

        # Remove phone numbers (basic pattern)
        text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "", text)

        # Remove common contact prefixes and trailing text after country
        text = re.sub(
            r"\.?\s*(?:Contact|Email|Tel|Phone|Fax)[:.]?\s*.*$", "", text, flags=re.IGNORECASE
        )

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def _parse_single_institution(
        self, part: str, markers: list[str], index: int
    ) -> dict[str, str | None]:
        """
        Parse a single institution from affiliation text.

        Parameters
        ----------
        part : str
            Single institution text to parse
        markers : list[str]
            List of superscript markers
        index : int
            Index of this institution in the markers list

        Returns
        -------
        dict[str, str | None]
            Parsed institution data
        """
        # Split by commas to get components
        components = [comp.strip() for comp in part.split(",") if comp.strip()]

        if not components:
            return {
                "marker": markers[index] if index < len(markers) else None,
                "text": part,
            }

        # Initialize variables
        country = None
        state_province = None
        postal_code = None
        city = None
        remaining_components = components[:]

        # Extract country (last component if it matches)
        country = self._extract_country(remaining_components)

        # Extract postal code first (can be before or after state)
        postal_code = self._extract_postal_code(remaining_components)

        # Extract state/province
        state_province = self._extract_state_province(remaining_components)

        # Extract city (what's left before the institution name)
        city = self._extract_city(remaining_components)

        # Everything else is the institution name
        name = ", ".join(remaining_components)

        return {
            "marker": markers[index] if index < len(markers) else None,
            "name": name if name else None,
            "city": city,
            "state_province": state_province,
            "postal_code": postal_code,
            "country": country,
        }

    def _is_likely_state_province(self, text: str) -> bool:
        """
        Check if text is likely a state or province abbreviation.

        Parameters
        ----------
        text : str
            Text to check

        Returns
        -------
        bool
            True if likely a state/province
        """
        # US state abbreviations (2-letter codes)
        us_states = {
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
            "DC",  # District of Columbia
        }

        # Canadian province/territory abbreviations
        canadian_provinces = {
            "AB",
            "BC",
            "MB",
            "NB",
            "NL",
            "NS",
            "NT",
            "NU",
            "ON",
            "PE",
            "QC",
            "SK",
            "YT",
        }

        # Australian state abbreviations
        australian_states = {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}

        # UK country abbreviations (sometimes used as states)
        uk_countries = {
            "ENG",
            "SCO",
            "WAL",
            "NIR",  # England, Scotland, Wales, Northern Ireland
        }

        text_upper = text.upper().strip()

        return (
            text_upper in us_states
            or text_upper in canadian_provinces
            or text_upper in australian_states
            or text_upper in uk_countries
        )

    def _is_likely_country(self, text: str) -> bool:
        """
        Check if text is likely a country name.

        Parameters
        ----------
        text : str
            Text to check

        Returns
        -------
        bool
            True if text looks like a country
        """
        # Clean the text first
        cleaned = self._clean_country_name(text).upper()

        # Check against known countries and abbreviations
        known_countries = {
            "USA",
            "US",
            "UNITED STATES",
            "UK",
            "UNITED KINGDOM",
            "CANADA",
            "CHINA",
            "JAPAN",
            "GERMANY",
            "FRANCE",
            "ITALY",
            "SPAIN",
            "AUSTRALIA",
            "INDIA",
            "BRAZIL",
            "MEXICO",
            "RUSSIA",
            "SOUTH KOREA",
            "NETHERLANDS",
            "SWEDEN",
            "NORWAY",
            "DENMARK",
            "FINLAND",
            "POLAND",
            "BELGIUM",
            "AUSTRIA",
            "SWITZERLAND",
        }

        # Check if the cleaned text starts with a known country
        for country in known_countries:
            if cleaned.startswith(country):
                return True

        # Check if it's an ISO code
        if len(cleaned) in (2, 3) and cleaned.isalpha():
            # Import here to avoid circular imports
            from pyeuropepmc.models.utils import ISO_COUNTRY_CODES

            return cleaned in ISO_COUNTRY_CODES

        # Check if it contains country-like words
        country_indicators = ["REPUBLIC", "FEDERATION", "KINGDOM", "EMIRATES", "STATES"]
        return any(indicator in cleaned for indicator in country_indicators)

    def _extract_country(self, components: list[str]) -> str | None:
        """Extract country from components, modifying components in place."""
        if not components:
            return None

        last_comp = components[-1]
        if self._is_likely_country(last_comp):
            country = self._clean_country_name(last_comp)
            components.pop()
            return country
        return None

    def _extract_state_province(self, components: list[str]) -> str | None:
        """Extract state/province from components, modifying components in place."""
        if not components:
            return None

        potential_state = components[-1]
        if self._is_likely_state_province(potential_state):
            components.pop()
            return potential_state
        return None

    def _extract_postal_code(self, components: list[str]) -> str | None:
        """Extract postal code from components, modifying components in place."""
        if not components:
            return None

        # First, look for standalone postal codes
        postal_candidates = []
        for i, comp in enumerate(components):
            if self._is_postal_code(comp):
                postal_candidates.append((i, comp))

        if postal_candidates:
            # Take the last postal code found
            postal_idx, postal_code = postal_candidates[-1]
            components.pop(postal_idx)
            return postal_code

        # If no standalone postal codes, check if any component contains a postal code
        # that needs to be split out
        for i, comp in enumerate(components):
            postal_match = re.search(r"\b(\w\d\w\s*\d\w\d|\d{5}(?:-\d{4})?)\b", comp)
            if postal_match:
                postal_code = postal_match.group(1)
                # Remove postal code from the component
                remaining = re.sub(r"\b(?:\w\d\w\s*\d\w\d|\d{5}(?:-\d{4})?)\b", "", comp).strip()
                if remaining:
                    # Replace the component with the cleaned version
                    components[i] = remaining
                else:
                    # Remove the component entirely if it was just the postal code
                    components.pop(i)
                return postal_code

        return None

    def _extract_city(self, components: list[str]) -> str | None:
        """Extract city from components, modifying components in place."""
        if not components:
            return None

        # If we have components left, the last one before the institution name is likely the city
        # But only if we have more than one component (institution name + city)
        if len(components) >= 2:
            city = components.pop()
            return city

        return None

    def _clean_country_name(self, country: str) -> str:
        """
        Clean country name by removing trailing punctuation and normalizing.

        Parameters
        ----------
        country : str
            Raw country name

        Returns
        -------
        str
            Cleaned country name
        """
        if not country:
            return country

        # Remove trailing dots and other punctuation
        country = re.sub(r"[.,;:!?]+$", "", country).strip()

        return country

    def _is_postal_code(self, text: str) -> bool:
        """
        Check if text looks like a postal code.

        Parameters
        ----------
        text : str
            Text to check

        Returns
        -------
        bool
            True if text matches postal code patterns
        """
        # Remove spaces for checking
        clean_text = text.replace(" ", "").upper()

        # US ZIP codes: 5 digits or 5+4
        if re.match(r"^\d{5}(-\d{4})?$", clean_text):
            return True

        # Canadian postal codes: ANA NAN pattern (with or without space)
        # e.g., "A1B 2C3" -> "A1B2C3" or "A1B2C3"
        if re.match(r"^\w\d\w\d\w\d$", clean_text):
            return True

        # Also check for postal codes within longer strings (e.g., "V5Z 1L3" in "BC V5Z 1L3")
        # Look for the pattern within the text
        if re.search(r"\b\w\d\w\s*\d\w\d\b", text):
            return True

        # UK postal codes: various patterns like SW1A 1AA, M1 1AA, etc.
        if re.match(r"^\w{1,2}\d{1,2}\w?\s*\d\w{2}$", text.upper()):
            return True

        # Other common postal code patterns (4-6 digits)
        if re.match(r"^\d{4,6}$", clean_text):
            return True

        # European postal codes (5 digits for many countries)
        return bool(re.match(r"^\d{4,6}$", clean_text))

    def _get_text_content(self, element: ET.Element | None) -> str:
        """
        Get all text content from an element and its descendants.

        Parameters
        ----------
        element : ET.Element or None
            XML element to extract text from

        Returns
        -------
        str
            Combined text content
        """
        if element is None:
            return ""

        # Get text from element and all sub-elements
        text_parts = []
        if element.text:
            text_parts.append(element.text.strip())

        for child in element:
            child_text = self._get_text_content(child)
            if child_text:
                text_parts.append(child_text)
            if child.tail:
                text_parts.append(child.tail.strip())

        return " ".join(text_parts).strip()

    def _extract_inline_elements(
        self,
        element: ET.Element,
        inline_patterns: list[str] | None = None,
        filter_empty: bool = True,
    ) -> list[str]:
        """
        Extract text from inline elements (e.g., superscripts, subscripts).

        This is a generic helper for extracting content from inline markup elements
        like <sup>, <sub>, <italic>, <bold>, etc.

        Parameters
        ----------
        element : ET.Element
            Parent element to search within
        inline_patterns : list[str], optional
            List of element patterns to extract (e.g., [".//sup", ".//sub"]).
            Defaults to [".//sup"] for backward compatibility.
        filter_empty : bool, optional
            Whether to filter out empty strings (default: True)

        Returns
        -------
        list[str]
            List of extracted text values from matching inline elements

        Examples
        --------
        >>> # Extract superscripts
        >>> markers = parser._extract_inline_elements(element, [".//sup"])
        >>>
        >>> # Extract both superscripts and subscripts
        >>> inline_text = parser._extract_inline_elements(
        ...     element, [".//sup", ".//sub"]
        ... )
        """
        if inline_patterns is None:
            inline_patterns = [".//sup"]

        results = []
        for pattern in inline_patterns:
            texts = self._extract_flat_texts(
                element, pattern, filter_empty=filter_empty, use_full_text=False
            )
            results.extend(texts)

        return results

    def _get_text_without_inline_elements(
        self,
        element: ET.Element,
        inline_patterns: list[str] | None = None,
        remove_strategy: str = "regex",
    ) -> str:
        """
        Get text content with specified inline elements removed.

        This generic helper extracts text while filtering out inline markup
        elements like superscripts, subscripts, etc.

        Parameters
        ----------
        element : ET.Element
            Element to extract text from
        inline_patterns : list[str], optional
            Patterns for inline elements to remove (e.g., [".//sup", ".//sub"]).
            Defaults to [".//sup"].
        remove_strategy : str, optional
            Strategy for removal:
            - "regex": Remove using regex pattern matching (default)
            - "skip": Skip inline elements during traversal (not yet implemented)

        Returns
        -------
        str
            Text content with inline elements removed

        Examples
        --------
        >>> # Remove superscripts from affiliation text
        >>> clean_text = parser._get_text_without_inline_elements(
        ...     aff_elem, [".//sup"]
        ... )
        >>>
        >>> # Remove both superscripts and subscripts
        >>> clean_text = parser._get_text_without_inline_elements(
        ...     element, [".//sup", ".//sub"]
        ... )
        """
        if inline_patterns is None:
            inline_patterns = [".//sup"]

        # Get full text
        full_text = "".join(element.itertext()).strip()

        if remove_strategy == "regex":
            # Extract inline element texts
            inline_texts = self._extract_inline_elements(
                element, inline_patterns, filter_empty=True
            )

            # Remove each inline text using regex
            clean_text = full_text
            for inline_text in inline_texts:
                clean_text = re.sub(rf"{re.escape(inline_text)}", "", clean_text)

            return clean_text.strip()
        else:
            raise ValueError(f"Unknown remove_strategy: {remove_strategy}")

    def to_plaintext(self) -> str:
        """
        Convert the full text XML to plain text.

        Returns
        -------
        str
            Plain text representation of the article

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        try:
            text_parts = []

            # Extract title using generic helper
            title_results = self.extract_elements_by_patterns(
                {"title": ".//article-title"}, return_type="text", first_only=True
            )
            if title_results["title"]:
                text_parts.append(f"{title_results['title'][0]}\n\n")

            # Extract authors
            authors = self.extract_authors()
            if authors:
                text_parts.append(f"Authors: {', '.join(authors)}\n\n")

            # Extract abstract using generic helper
            abstract_results = self.extract_elements_by_patterns(
                {"abstract": ".//abstract"}, return_type="text", first_only=True
            )
            if abstract_results["abstract"]:
                text_parts.append(f"Abstract\n{abstract_results['abstract'][0]}\n\n")

            # Extract body sections using generic helper
            body_results = self.extract_elements_by_patterns(
                {"body": ".//body"}, return_type="element", first_only=True
            )
            if body_results["body"]:
                body_elem = body_results["body"][0]
                # Get all section elements within body
                for sec in body_elem.iter():
                    if sec.tag == "sec":
                        section_text = self._process_section_plaintext(sec)
                        if section_text:
                            text_parts.append(f"{section_text}\n\n")

            return "".join(text_parts).strip()

        except Exception as e:
            logger.error(f"Error converting to plaintext: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to convert XML to plaintext"},
            ) from e

    def _process_section_plaintext(self, section: ET.Element) -> str:
        """Process a section element to plain text using generic helpers."""
        text_parts = []

        # Extract section title using generic helper
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        if titles:
            text_parts.append(f"{titles[0]}\n")

        # Extract paragraphs using generic helper
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        for para_text in paragraphs:
            text_parts.append(f"{para_text}\n")

        return "\n".join(text_parts)

    def to_markdown(self) -> str:  # noqa: C901
        """
        Convert the full text XML to Markdown format.

        Returns
        -------
        str
            Markdown representation of the article

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        try:
            md_parts = []

            # Extract title using generic helper
            title_results = self.extract_elements_by_patterns(
                {"title": ".//article-title"}, return_type="text", first_only=True
            )
            if title_results["title"]:
                md_parts.append(f"# {title_results['title'][0]}\n\n")

            # Extract authors
            authors = self.extract_authors()
            if authors:
                md_parts.append(f"**Authors:** {', '.join(authors)}\n\n")

            # Extract metadata
            metadata = self.extract_metadata()
            if metadata.get("journal"):
                md_parts.append(f"**Journal:** {metadata['journal']}\n\n")
            if metadata.get("doi"):
                md_parts.append(f"**DOI:** {metadata['doi']}\n\n")

            # Extract abstract using generic helper
            abstract_results = self.extract_elements_by_patterns(
                {"abstract": ".//abstract"}, return_type="text", first_only=True
            )
            if abstract_results["abstract"]:
                md_parts.append(f"## Abstract\n\n{abstract_results['abstract'][0]}\n\n")

            # Extract body sections using generic helper
            body_results = self.extract_elements_by_patterns(
                {"body": ".//body"}, return_type="element", first_only=True
            )
            if body_results["body"]:
                body_elem = body_results["body"][0]
                # Get all section elements within body
                for sec in body_elem.iter():
                    if sec.tag == "sec":
                        section_md = self._process_section_markdown(sec, level=2)
                        if section_md:
                            md_parts.append(f"{section_md}\n\n")

            return "".join(md_parts).strip()

        except Exception as e:
            logger.error(f"Error converting to markdown: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to convert XML to markdown"},
            ) from e

    def _process_section_markdown(self, section: ET.Element, level: int = 2) -> str:
        """Process a section element to markdown using generic helpers."""
        md_parts = []

        # Extract section title using generic helper
        titles = self._extract_flat_texts(section, "title", filter_empty=True, use_full_text=True)
        if titles:
            md_parts.append(f"{'#' * level} {titles[0]}\n\n")

        # Extract paragraphs using generic helper
        paragraphs = self._extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        for para_text in paragraphs:
            md_parts.append(f"{para_text}\n\n")

        # Process subsections - get direct child sec elements
        for subsec in section.iter():
            if subsec.tag == "sec" and subsec != section:
                # Only process direct children or nested sections
                subsec_md = self._process_section_markdown(subsec, level=level + 1)
                if subsec_md:
                    md_parts.append(subsec_md)

        return "".join(md_parts)

    def extract_tables(self) -> list[dict[str, Any]]:
        """
        Extract all tables from the full text XML using modular, reusable logic.

        Returns
        -------
        list of dict
            List of dictionaries, each containing:
            - id: Table ID
            - label: Table label (e.g., "Table 1")
            - caption: Table caption
            - headers: List of column headers
            - rows: List of rows, where each row is a list of cell values

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        try:
            patterns = {"table_wrap": ".//table-wrap"}
            table_wraps = self.extract_elements_by_patterns(patterns, return_type="element")[
                "table_wrap"
            ]
            tables = []
            for table_wrap in table_wraps:
                table_data: dict[str, Any] = {}
                # Extract table ID (attribute)
                table_data["id"] = table_wrap.get("id")
                # Extract label and caption using patterns
                label_patterns = {"label": "label"}
                caption_patterns = {"caption": "caption"}
                label = self._extract_first_text_from_element(table_wrap, label_patterns)
                caption = self._extract_first_text_from_element(table_wrap, caption_patterns)
                table_data["label"] = label
                table_data["caption"] = caption
                # Extract table element - find first table tag
                table_elems = []
                for elem in table_wrap.iter():
                    if elem.tag == "table":
                        table_elems.append(elem)
                        break
                if table_elems:
                    headers, rows = self._parse_table_modular(table_elems[0])
                    table_data["headers"] = headers
                    table_data["rows"] = rows
                else:
                    table_data["headers"] = []
                    table_data["rows"] = []
                tables.append(table_data)
            logger.debug(f"Extracted {len(tables)} tables from XML: {tables}")
            return tables
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract tables from XML"},
            ) from e

    def _extract_first_text_from_element(
        self, element: ET.Element, patterns: dict[str, str]
    ) -> str | None:
        """
        Helper to extract the first text value for a pattern from a given element.
        Uses generic helpers instead of findall.
        """
        for _key, pattern in patterns.items():
            # Use generic helper to extract text
            texts = self._extract_flat_texts(
                element, pattern, filter_empty=True, use_full_text=True
            )
            if texts:
                return texts[0]
        return None

    def _parse_table_modular(self, table_elem: ET.Element) -> tuple[list[str], list[list[str]]]:  # noqa: C901
        """
        Modular table parser using generic helpers for headers and rows.
        """
        headers: list[str] = []
        rows: list[list[str]] = []

        # Extract headers from thead using generic helper
        # Find thead element
        thead = None
        for elem in table_elem.iter():
            if elem.tag == "thead":
                thead = elem
                break

        if thead is not None:
            # Find header row
            header_row = None
            for elem in thead.iter():
                if elem.tag == "tr":
                    header_row = elem
                    break
            if header_row is not None:
                headers = self._extract_flat_texts(
                    header_row, ".//th", filter_empty=False, use_full_text=True
                )

        # Extract rows from tbody using generic helper
        # Find tbody element
        tbody = None
        for elem in table_elem.iter():
            if elem.tag == "tbody":
                tbody = elem
                break

        if tbody is not None:
            # Find all tr elements in tbody
            for tr in tbody.iter():
                if tr.tag == "tr":
                    row_data = self._extract_flat_texts(
                        tr, "td", filter_empty=False, use_full_text=True
                    )
                    if row_data:
                        rows.append(row_data)

        return headers, rows

    def _parse_table(self, table_elem: ET.Element) -> tuple[list[str], list[list[str]]]:  # noqa: C901
        """
        Parse a table element into headers and rows using generic helpers.

        Parameters
        ----------
        table_elem : ET.Element
            Table element to parse

        Returns
        -------
        tuple
            (headers, rows) where headers is a list of strings and
            rows is a list of lists of strings
        """
        headers: list[str] = []
        rows: list[list[str]] = []

        # Extract headers from thead
        thead = None
        for elem in table_elem.iter():
            if elem.tag == "thead":
                thead = elem
                break

        if thead is not None:
            # Find header row
            header_row = None
            for elem in thead.iter():
                if elem.tag == "tr":
                    header_row = elem
                    break
            if header_row is not None:
                # Extract th elements using generic helper
                headers = self._extract_flat_texts(
                    header_row, ".//th", filter_empty=False, use_full_text=True
                )

        # Extract rows from tbody
        tbody = None
        for elem in table_elem.iter():
            if elem.tag == "tbody":
                tbody = elem
                break

        if tbody is not None:
            # Find all tr elements
            for tr in tbody.iter():
                if tr.tag == "tr":
                    # Extract td elements using generic helper
                    row_data = self._extract_flat_texts(
                        tr, "td", filter_empty=False, use_full_text=True
                    )
                    if row_data:
                        rows.append(row_data)

        # If no thead, try to get headers from first row
        if not headers and rows:
            # Check if we should treat first row as header (heuristic)
            # For now, just return empty headers
            pass

        return headers, rows

    def extract_references(self) -> list[dict[str, str | None]]:
        """
        Extract references/bibliography from the full text XML using modular helpers.

        Now supports multiple citation types through flexible fallback patterns.

        Returns
        -------
        list[dict[str, str | None]]
            List of reference dictionaries with extracted metadata

        Raises
        ------
        ParsingError
            If no XML has been parsed or extraction fails
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )
        try:
            refs = self.extract_elements_by_patterns({"ref": ".//ref"}, return_type="element")[
                "ref"
            ]
            references = []
            for ref in refs:
                ref_data: dict[str, str | None] = {}
                ref_data["id"] = ref.get("id")

                # Extract label with fallback
                label = self._extract_with_fallbacks(ref, ["label"])
                ref_data["label"] = label

                # Find citation element using configured citation types
                citation = None
                citation_type_found = None
                for citation_type in self.config.citation_types:
                    for elem in ref.iter():
                        if elem.tag == citation_type:
                            citation = elem
                            citation_type_found = citation_type
                            break
                    if citation is not None:
                        break

                if citation is not None:
                    ref_data["citation_type"] = citation_type_found

                    # Authors (use generic helper)
                    authors = self._extract_reference_authors(citation)
                    ref_data["authors"] = ", ".join(authors) if authors else None

                    # Extract fields using fallback patterns from config
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

                    # Extract page numbers with fallbacks
                    fpage = self._extract_with_fallbacks(
                        citation, self.config.reference_patterns["fpage"]
                    )
                    lpage = self._extract_with_fallbacks(
                        citation, self.config.reference_patterns["lpage"]
                    )
                    ref_data["pages"] = self._combine_page_range(fpage, lpage)

                    # Extract DOI with fallback
                    ref_data["doi"] = self._extract_with_fallbacks(
                        citation, self.config.reference_patterns["doi"]
                    )

                    # Extract PMID with fallback
                    ref_data["pmid"] = self._extract_with_fallbacks(
                        citation, self.config.reference_patterns["pmid"]
                    )

                references.append(ref_data)
            logger.debug(f"Extracted {len(references)} references from XML: {references}")
            return references
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract references from XML"},
            ) from e

    def get_full_text_sections(self) -> list[dict[str, str]]:
        """
        Extract all body sections with their titles and content.

        Returns
        -------
        list of dict
            List of section dictionaries containing:
            - title: Section title
            - content: Section text content

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        try:
            patterns = {"body": ".//body"}
            bodies = self.extract_elements_by_patterns(patterns, return_type="element")["body"]
            sections = []
            for _body_elem in bodies:
                sec_patterns = {"sec": ".//sec"}
                secs = self.extract_elements_by_patterns(sec_patterns, return_type="element")[
                    "sec"
                ]
                for sec in secs:
                    section_data = self._extract_section_data(sec)
                    if section_data:
                        sections.append(section_data)
            logger.debug(f"Extracted {len(sections)} sections from XML: {sections}")
            return sections
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract sections from XML"},
            ) from e

    def _extract_institution_ids(self, element: ET.Element) -> dict[str, str]:
        """
        Extract institution identifiers (ROR, GRID, ISNI, etc.) from element.

        Parameters
        ----------
        element : ET.Element
            The XML element to extract institution IDs from

        Returns
        -------
        dict[str, str]
            Dictionary mapping ID type to ID value
        """
        institution_ids = {}
        # Use extract_elements_by_patterns helper
        temp_parser = FullTextXMLParser()
        temp_parser.root = element
        id_elems_result = temp_parser.extract_elements_by_patterns(
            {"institution_ids": ".//institution-id"}, return_type="element"
        )

        for inst_id_elem in id_elems_result.get("institution_ids", []):
            id_type = inst_id_elem.get("institution-id-type")
            id_value = inst_id_elem.text
            if id_type and id_value:
                institution_ids[id_type] = id_value.strip()
        return institution_ids

    def _extract_all_pub_ids(
        self, element: ET.Element, id_tag: str = "article-id"
    ) -> dict[str, str]:
        """
        Extract all publication IDs from element.

        Parameters
        ----------
        element : ET.Element
            The XML element to extract IDs from
        id_tag : str
            The tag name for ID elements (default: "article-id")

        Returns
        -------
        dict[str, str]
            Dictionary mapping ID type to ID value (pmcid, pmid, doi, publisher-id, etc.)
        """
        pub_ids = {}
        # Use extract_elements_by_patterns helper
        temp_parser = FullTextXMLParser()
        temp_parser.root = element
        id_elems_result = temp_parser.extract_elements_by_patterns(
            {"pub_ids": f".//{id_tag}"}, return_type="element"
        )

        for id_elem in id_elems_result.get("pub_ids", []):
            id_type = id_elem.get("pub-id-type")
            id_value = id_elem.text
            if id_type and id_value:
                pub_ids[id_type] = id_value.strip()
        return pub_ids

    def _clean_orcid(self, orcid: str | None) -> str | None:
        """
        Clean ORCID ID by removing URL prefix.

        Parameters
        ----------
        orcid : str | None
            ORCID URL or ID

        Returns
        -------
        str | None
            Clean ORCID ID (e.g., "0000-0003-3442-7216")
        """
        if not orcid:
            return None
        # Remove common URL prefixes
        orcid = orcid.strip()
        for prefix in ["http://orcid.org/", "https://orcid.org/", "orcid.org/"]:
            if orcid.startswith(prefix):
                return orcid[len(prefix) :]
        return orcid

    def extract_funding(self) -> list[dict[str, Any]]:
        """
        Extract funding information from the full text XML.

        Returns
        -------
        list[dict[str, Any]]
            List of funding dictionaries, each containing:
            - source: Funding source name
            - fundref_doi: FundRef DOI (if available)
            - award_id: Award/grant ID
            - recipient: Award recipient name
            - recipient_full: Full recipient name (given + surname)

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        funding_results = []
        # Use extract_elements_by_patterns helper
        award_groups_result = self.extract_elements_by_patterns(
            {"award_groups": ".//award-group"}, return_type="element"
        )

        for award_group in award_groups_result.get("award_groups", []):
            funding_data = self._extract_funding_from_group(award_group)
            if funding_data:  # Only add if we extracted something
                funding_results.append(funding_data)

        logger.debug(f"Extracted {len(funding_results)} funding entries")
        return funding_results

    def _extract_funding_from_group(self, award_group: ET.Element) -> dict[str, Any]:
        """Extract funding data from a single award-group element."""
        funding_data: dict[str, Any] = {}

        # Extract funding source using _extract_flat_texts helper
        source_texts = self._extract_flat_texts(
            award_group, ".//funding-source//institution", filter_empty=True
        )
        if source_texts:
            funding_data["source"] = " ".join(source_texts)

        # Extract FundRef DOI using extract_elements_by_patterns
        temp_parser = FullTextXMLParser()
        temp_parser.root = award_group
        inst_ids_result = temp_parser.extract_elements_by_patterns(
            {"institution_ids": ".//institution-id"}, return_type="element"
        )

        for inst_id in inst_ids_result.get("institution_ids", []):
            if inst_id.get("institution-id-type") == "FundRef" and inst_id.text:
                funding_data["fundref_doi"] = inst_id.text.strip()
                break

        # Extract award ID using _extract_with_fallbacks helper
        award_id = self._extract_with_fallbacks(award_group, [".//award-id"])
        if award_id:
            funding_data["award_id"] = award_id

        # Extract recipient
        recipient_info = self._extract_recipient(award_group)
        if recipient_info:
            funding_data.update(recipient_info)

        return funding_data

    def _extract_recipient(self, award_group: ET.Element) -> dict[str, str]:
        """Extract recipient information from award group."""
        recipient_info = {}
        # Use extract_elements_by_patterns helper
        temp_parser = FullTextXMLParser()
        temp_parser.root = award_group
        recipients_result = temp_parser.extract_elements_by_patterns(
            {"recipients": ".//principal-award-recipient"}, return_type="element"
        )

        for recipient_elem in recipients_result.get("recipients", []):
            # Use _extract_with_fallbacks for name parts
            surname = self._extract_with_fallbacks(recipient_elem, [".//surname"])
            given_names = self._extract_with_fallbacks(recipient_elem, [".//given-names"])

            if surname:
                recipient_info["recipient"] = surname
                if given_names:
                    recipient_info["recipient_full"] = f"{given_names} {surname}"
            break
        return recipient_info

    def extract_license(self) -> dict[str, str | None]:
        """
        Extract license information from the full text XML.

        Returns
        -------
        dict[str, str | None]
            Dictionary containing:
            - type: License type attribute
            - url: License URL (from ext-link)
            - text: License text content

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        license_info: dict[str, str | None] = {}
        # Use extract_elements_by_patterns helper
        license_result = self.extract_elements_by_patterns(
            {"licenses": ".//license"}, return_type="element"
        )

        for license_elem in license_result.get("licenses", []):
            # Extract license type
            license_type = license_elem.get("license-type")
            if license_type:
                license_info["type"] = license_type

            # Extract license URL using extract_elements_by_patterns
            temp_parser = FullTextXMLParser()
            temp_parser.root = license_elem
            ext_links_result = temp_parser.extract_elements_by_patterns(
                {"ext_links": ".//ext-link"}, return_type="element"
            )

            for ext_link in ext_links_result.get("ext_links", []):
                url = ext_link.get("{http://www.w3.org/1999/xlink}href")
                if url:
                    license_info["url"] = url
                break

            # Extract license text using _extract_with_fallbacks helper
            text = self._extract_with_fallbacks(license_elem, [".//license-p"])
            if text:
                license_info["text"] = text
            break

        return license_info if license_info else {}

    def extract_publisher(self) -> dict[str, str | None]:
        """
        Extract publisher information from the full text XML.

        Returns
        -------
        dict[str, str | None]
            Dictionary containing:
            - name: Publisher name
            - location: Publisher location

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        publisher_info: dict[str, str | None] = {}
        # Use extract_elements_by_patterns helper
        publisher_result = self.extract_elements_by_patterns(
            {"publishers": ".//publisher"}, return_type="element"
        )

        for publisher_elem in publisher_result.get("publishers", []):
            # Extract publisher name using helper
            name = self._extract_with_fallbacks(publisher_elem, [".//publisher-name"])
            if name:
                publisher_info["name"] = name

            # Extract publisher location using helper
            location = self._extract_with_fallbacks(publisher_elem, [".//publisher-loc"])
            if location:
                publisher_info["location"] = location
            break

        return publisher_info

    def extract_article_categories(self) -> dict[str, Any]:
        """
        Extract article categories and subjects from the full text XML.

        Returns
        -------
        dict[str, Any]
            Dictionary containing:
            - article_type: Article type attribute from root element
            - subject_groups: List of subject group dicts with type and subjects

        Raises
        ------
        ParsingError
            If no XML has been parsed
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        categories: dict[str, Any] = {}

        # Get article type from root element using extract_elements_by_patterns
        article_result = self.extract_elements_by_patterns(
            {"articles": ".//article"}, return_type="element"
        )

        for article_elem in article_result.get("articles", []):
            article_type = article_elem.get("article-type")
            if article_type:
                categories["article_type"] = article_type
            break

        # Extract subject groups using extract_elements_by_patterns
        subject_groups = []
        subj_groups_result = self.extract_elements_by_patterns(
            {"subj_groups": ".//subj-group"}, return_type="element"
        )

        for subj_group in subj_groups_result.get("subj_groups", []):
            group_type = subj_group.get("subj-group-type")
            # Use _extract_flat_texts helper instead of manual list comprehension
            subjects = self._extract_flat_texts(subj_group, ".//subject", filter_empty=True)

            if subjects:
                group_data: dict[str, Any] = {"subjects": subjects}
                if group_type:
                    group_data["type"] = group_type
                subject_groups.append(group_data)

        if subject_groups:
            categories["subject_groups"] = subject_groups

        return categories

    def _extract_section_data(self, section: ET.Element) -> dict[str, str]:
        """Extract title and content from a section element using generic helper."""
        return self._extract_section_structure(section)
