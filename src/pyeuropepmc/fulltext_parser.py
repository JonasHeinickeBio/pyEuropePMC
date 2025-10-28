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

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import ParsingError

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
            ".//contrib[@contrib-type='author']/name",
            ".//contrib[@contrib-type='author']",
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
        Extract metadata from the full text XML.

        Uses configuration-based fallback patterns for flexible extraction
        across different XML schemas and article types.

        Returns
        -------
        dict
            Dictionary containing extracted metadata including:
            - pmcid: PMC ID
            - doi: DOI
            - title: Article title
            - authors: List of author names
            - journal: Journal name
            - pub_date: Publication date
            - volume: Journal volume
            - issue: Journal issue
            - pages: Page range
            - abstract: Article abstract
            - keywords: List of keywords

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
            # Use flexible extraction with fallback patterns
            metadata: dict[str, Any] = {
                "pmcid": self._extract_with_fallbacks(
                    self.root, self.config.article_patterns["pmcid"]
                ),
                "doi": self._extract_with_fallbacks(
                    self.root, self.config.article_patterns["doi"]
                ),
                "title": self._extract_with_fallbacks(
                    self.root, self.config.article_patterns["title"], use_full_text=True
                ),
                "journal": self._extract_with_fallbacks(
                    self.root, self.config.journal_patterns["title"]
                ),
                "volume": self._extract_with_fallbacks(
                    self.root, self.config.journal_patterns["volume"]
                ),
                "issue": self._extract_with_fallbacks(
                    self.root, self.config.journal_patterns["issue"]
                ),
                "abstract": self._extract_with_fallbacks(
                    self.root, self.config.article_patterns["abstract"], use_full_text=True
                ),
            }

            # Pages: try multiple patterns for first and last page
            fpage = self._extract_with_fallbacks(self.root, [".//fpage", ".//first-page"])
            lpage = self._extract_with_fallbacks(self.root, [".//lpage", ".//last-page"])
            metadata["pages"] = self._combine_page_range(fpage, lpage)

            # Authors, publication date, and keywords (use specialized methods)
            metadata["authors"] = self.extract_authors()
            metadata["pub_date"] = self.extract_pub_date()
            metadata["keywords"] = self.extract_keywords()

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

    def extract_authors(self) -> list[str]:
        """
        Extract list of author names from XML.

        Uses configuration-based fallback patterns to handle different
        author element structures across XML schemas.

        Returns
        -------
        list[str]
            List of author names (given-name + surname)
        """
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

        # Try each author element pattern in config
        for author_pattern in self.config.author_element_patterns:
            # Find all author elements matching this pattern
            author_elems = self.root.findall(author_pattern)
            if author_elems:
                logger.debug(f"Found {len(author_elems)} authors using pattern: {author_pattern}")
                authors = []
                for elem in author_elems:
                    # Extract given name and surname with fallbacks
                    given = (
                        self._extract_with_fallbacks(
                            elem, self.config.author_field_patterns["given_names"]
                        )
                        or ""
                    )
                    surname = (
                        self._extract_with_fallbacks(
                            elem, self.config.author_field_patterns["surname"]
                        )
                        or ""
                    )
                    # Combine name parts
                    name_parts = [p for p in [given, surname] if p]
                    if name_parts:
                        authors.append(" ".join(name_parts))

                if authors:
                    logger.debug(f"Extracted authors: {authors}")
                    return authors

        # No authors found with any pattern
        logger.debug("No authors found with any configured pattern")
        return []

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

        Returns
        -------
        list[dict[str, Any]]
            List of affiliation dictionaries, each containing:
            - id: Affiliation ID attribute
            - institution: Institution name (if structured)
            - city: City (if structured)
            - country: Country (if structured)
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

            # Try structured extraction first
            structured = self._extract_structured_fields(
                aff_elem,
                {
                    "institution": "institution",
                    "city": "addr-line/named-content[@content-type='city']",
                    "country": "country",
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

            # Try to extract components using patterns
            # Pattern: Institution, City PostalCode, Country
            match = re.search(r"([^,]+),\s*([^,]+?)\s+(\d+)(?:,\s*(.+))?", part)
            if match:
                institution = {
                    "marker": markers[i] if i < len(markers) else None,
                    "name": match.group(1).strip(),
                    "city": match.group(2).strip(),
                    "postal_code": match.group(3).strip(),
                    "country": match.group(4).strip() if match.group(4) else None,
                }
            else:
                # Simple fallback - just store the text
                institution = {"marker": markers[i] if i < len(markers) else None, "text": part}

            institutions.append(institution)

        return institutions

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

    def _extract_section_data(self, section: ET.Element) -> dict[str, str]:
        """Extract title and content from a section element using generic helper."""
        return self._extract_section_structure(section)
