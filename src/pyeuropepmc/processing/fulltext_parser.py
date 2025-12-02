"""
Full text XML parser for Europe PMC articles.

This module provides functionality for parsing full text XML files from Europe PMC
and converting them to different output formats including metadata extraction,
markdown, plaintext, and table extraction.

This is the main orchestrator module that delegates to specialized parsers:
- parsers/author_parser.py: Author and contributor extraction
- parsers/affiliation_parser.py: Affiliation parsing
- parsers/metadata_parser.py: Article metadata extraction
- parsers/reference_parser.py: Bibliography/citation parsing
- parsers/table_parser.py: Table extraction
- parsers/section_parser.py: Section and body text parsing
- converters/plaintext_converter.py: XML to plaintext conversion
- converters/markdown_converter.py: XML to markdown conversion
"""

import logging
from typing import Any
from xml.etree import (
    ElementTree as ET,  # nosec B405 - Only used for type hints, actual parsing uses defusedxml
)

import defusedxml.ElementTree as DefusedET

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError

# Import configuration classes from modular config
from pyeuropepmc.processing.config.document_schema import DocumentSchema
from pyeuropepmc.processing.config.element_patterns import ElementPatterns

# Import specialized parsers
from pyeuropepmc.processing.converters.markdown_converter import MarkdownConverter
from pyeuropepmc.processing.converters.plaintext_converter import PlaintextConverter
from pyeuropepmc.processing.parsers.affiliation_parser import AffiliationParser
from pyeuropepmc.processing.parsers.author_parser import AuthorParser
from pyeuropepmc.processing.parsers.metadata_parser import MetadataParser
from pyeuropepmc.processing.parsers.reference_parser import ReferenceParser
from pyeuropepmc.processing.parsers.section_parser import SectionParser
from pyeuropepmc.processing.parsers.table_parser import TableParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)

__all__ = ["FullTextXMLParser", "ElementPatterns", "DocumentSchema"]


class FullTextXMLParser:
    """
    Orchestrator for parsing Europe PMC full text XML files.

    This class serves as the main entry point and coordinator for XML parsing operations.
    It delegates specialized parsing tasks to dedicated parser modules while maintaining
    a consistent API for users.

    Architecture
    ------------
    The parser uses a lazy-loading pattern where specialized parsers and converters are
    instantiated on-demand through property accessors. This provides:
    - Reduced memory footprint: Only requested components are created
    - Improved performance: No overhead from unused parsers
    - Clean separation: Each parser focuses on a single responsibility

    Delegated Components
    --------------------
    - AuthorParser: Author and contributor extraction
    - AffiliationParser: Institution and affiliation parsing
    - MetadataParser: Article metadata extraction (title, DOI, dates, journal info)
    - ReferenceParser: Bibliography and citation parsing
    - TableParser: Table extraction and structuring
    - SectionParser: Body section and content parsing
    - PlaintextConverter: XML to plaintext conversion
    - MarkdownConverter: XML to markdown conversion

    Parameters
    ----------
    xml_content : str or ET.Element, optional
        XML content string or Element to parse. If provided, parsing begins immediately.
    config : ElementPatterns, optional
        Configuration for element patterns. If None, uses default JATS patterns.

    Examples
    --------
    >>> # Basic usage with automatic parsing
    >>> parser = FullTextXMLParser(xml_content)
    >>> metadata = parser.extract_metadata()
    >>> authors = parser.extract_authors()
    >>>
    >>> # Custom configuration for non-standard XML
    >>> config = ElementPatterns(citation_types=["element-citation", "mixed-citation"])
    >>> parser = FullTextXMLParser(xml_content, config=config)
    >>>
    >>> # Lazy initialization - parsers created only when needed
    >>> parser = FullTextXMLParser()
    >>> parser.parse(xml_content)  # Parse later
    >>> metadata = parser.extract_metadata()  # MetadataParser created here

    Notes
    -----
    - All specialized parsers share the same root element and configuration
    - Parsers are cached after first access for performance
    - Calling parse() with new content resets all cached parsers
    - The class is thread-safe for read operations after initialization
    """

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
        """
        self.xml_content: str | None = None
        self.root: ET.Element | None = None
        self.config = config or ElementPatterns()
        self._schema: DocumentSchema | None = None

        # Lazy-loaded specialized parsers
        self._author_parser: AuthorParser | None = None
        self._affiliation_parser: AffiliationParser | None = None
        self._metadata_parser: MetadataParser | None = None
        self._reference_parser: ReferenceParser | None = None
        self._table_parser: TableParser | None = None
        self._section_parser: SectionParser | None = None
        self._plaintext_converter: PlaintextConverter | None = None
        self._markdown_converter: MarkdownConverter | None = None

        if xml_content is not None:
            self.parse(xml_content)

    def _reset_parsers(self) -> None:
        """Reset all cached parser instances when root changes."""
        self._author_parser = None
        self._affiliation_parser = None
        self._metadata_parser = None
        self._reference_parser = None
        self._table_parser = None
        self._section_parser = None
        self._plaintext_converter = None
        self._markdown_converter = None
        self._schema = None

    @property
    def author_parser(self) -> AuthorParser:
        """Get the author parser instance."""
        if self._author_parser is None:
            self._author_parser = AuthorParser(self.root, self.config)
        return self._author_parser

    @property
    def affiliation_parser(self) -> AffiliationParser:
        """Get the affiliation parser instance."""
        if self._affiliation_parser is None:
            self._affiliation_parser = AffiliationParser(self.root, self.config)
        return self._affiliation_parser

    @property
    def metadata_parser(self) -> MetadataParser:
        """Get the metadata parser instance."""
        if self._metadata_parser is None:
            self._metadata_parser = MetadataParser(self.root, self.config)
        return self._metadata_parser

    @property
    def reference_parser(self) -> ReferenceParser:
        """Get the reference parser instance."""
        if self._reference_parser is None:
            self._reference_parser = ReferenceParser(self.root, self.config)
        return self._reference_parser

    @property
    def table_parser(self) -> TableParser:
        """Get the table parser instance."""
        if self._table_parser is None:
            self._table_parser = TableParser(self.root, self.config)
        return self._table_parser

    @property
    def section_parser(self) -> SectionParser:
        """Get the section parser instance."""
        if self._section_parser is None:
            self._section_parser = SectionParser(self.root, self.config)
        return self._section_parser

    @property
    def plaintext_converter(self) -> PlaintextConverter:
        """Get the plaintext converter instance."""
        if self._plaintext_converter is None:
            self._plaintext_converter = PlaintextConverter(self.root, self.config)
        return self._plaintext_converter

    @property
    def markdown_converter(self) -> MarkdownConverter:
        """Get the markdown converter instance."""
        if self._markdown_converter is None:
            self._markdown_converter = MarkdownConverter(self.root, self.config)
        return self._markdown_converter

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
            self._reset_parsers()
            return self.root
        elif isinstance(xml_content, str):
            if not xml_content.strip():
                raise ParsingError(
                    ErrorCodes.PARSE003, {"message": "XML content cannot be None or empty."}
                )
            try:
                self.xml_content = xml_content
                self.root = DefusedET.fromstring(xml_content)
                self._reset_parsers()
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

    def _require_root(self) -> None:
        """Raise an error if no root element is available."""
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

    # =========================================================================
    # Public API methods - delegate to specialized parsers
    # =========================================================================

    def extract_metadata(self) -> dict[str, Any]:
        """
        Extract comprehensive metadata from the full text XML.

        Returns
        -------
        dict
            Dictionary containing extracted metadata
        """
        self._require_root()
        try:
            return self.metadata_parser.extract_metadata()
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract metadata from XML"},
            ) from e

    def extract_authors(self) -> list[str]:
        """
        Extract list of author names from XML.

        Returns
        -------
        list[str]
            List of author names as strings
        """
        self._require_root()
        return self.author_parser.extract_authors()

    def extract_authors_detailed(self) -> list[dict[str, Any]]:
        """
        Extract list of detailed author information from XML.

        Returns
        -------
        list[dict[str, Any]]
            List of author dictionaries with detailed information
        """
        self._require_root()
        return self.author_parser.extract_authors_detailed()

    def extract_affiliations(self) -> list[dict[str, Any]]:
        """
        Extract author affiliations from the full text XML.

        Returns
        -------
        list[dict[str, Any]]
            List of affiliation dictionaries
        """
        self._require_root()
        return self.affiliation_parser.extract_affiliations()

    def extract_pub_date(self) -> str | None:
        """Extract publication date from XML."""
        self._require_root()
        return self.metadata_parser.extract_pub_date()

    def extract_keywords(self) -> list[str]:
        """Extract keywords from XML."""
        self._require_root()
        return self.metadata_parser.extract_keywords()

    def extract_funding(self) -> list[dict[str, Any]]:
        """Extract funding information from the full text XML."""
        self._require_root()
        return self.metadata_parser.extract_funding()

    def extract_license(self) -> dict[str, str | None]:
        """Extract license information from the full text XML."""
        self._require_root()
        return self.metadata_parser.extract_license()

    def extract_publisher(self) -> dict[str, str | None]:
        """Extract publisher information from the full text XML."""
        self._require_root()
        return self.metadata_parser.extract_publisher()

    def extract_article_categories(self) -> dict[str, Any]:
        """Extract article categories and subjects from the full text XML."""
        self._require_root()
        return self.metadata_parser.extract_article_categories()

    def extract_references(self) -> list[dict[str, str | None]]:
        """
        Extract references/bibliography from the full text XML.

        Returns
        -------
        list[dict[str, str | None]]
            List of reference dictionaries
        """
        self._require_root()
        try:
            return self.reference_parser.extract_references()
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract references from XML"},
            ) from e

    def extract_tables(self) -> list[dict[str, Any]]:
        """
        Extract all tables from the full text XML.

        Returns
        -------
        list[dict[str, Any]]
            List of table dictionaries
        """
        self._require_root()
        try:
            return self.table_parser.extract_tables()
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract tables from XML"},
            ) from e

    def get_full_text_sections(self) -> list[dict[str, str]]:
        """
        Extract all body sections with their titles and content.

        Returns
        -------
        list[dict[str, str]]
            List of section dictionaries
        """
        self._require_root()
        try:
            return self.section_parser.get_full_text_sections()
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract sections from XML"},
            ) from e

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
            return self.plaintext_converter.to_plaintext()
        except Exception as e:
            logger.error(f"Error converting to plaintext: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to convert XML to plaintext"},
            ) from e

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
            return self.markdown_converter.to_markdown()
        except Exception as e:
            logger.error(f"Error converting to markdown: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to convert XML to markdown"},
            ) from e

    # =========================================================================
    # Schema detection and validation
    # =========================================================================

    def detect_schema(self) -> DocumentSchema:
        """
        Analyze document structure and detect schema patterns.

        Returns
        -------
        DocumentSchema
            Detected schema information
        """
        self._require_root()

        if self._schema is not None:
            return self._schema

        schema = DocumentSchema()
        root = self.root

        # Detect table structures
        for table_pattern in self.config.table_patterns["wrapper"]:
            if root is not None and root.find(f".//{table_pattern}") is not None:
                schema.has_tables = True
                schema.table_structure = "jats"
                break

        if not schema.has_tables and root is not None and root.find(".//table") is not None:
            schema.has_tables = True
            schema.table_structure = "html"

        # Detect citation types present
        for citation_type in self.config.citation_types:
            if root is not None and root.find(f".//{citation_type}") is not None:
                schema.citation_types.append(citation_type)

        # Detect figures
        schema.has_figures = root is not None and root.find(".//fig") is not None

        # Detect supplementary materials
        schema.has_supplementary = (
            root is not None and root.find(".//supplementary-material") is not None
        )

        # Detect acknowledgments
        schema.has_acknowledgments = root is not None and root.find(".//ack") is not None

        # Detect funding information
        schema.has_funding = root is not None and root.find(".//funding-group") is not None

        logger.debug(f"Detected schema: {schema}")
        self._schema = schema
        return schema

    def list_element_types(self) -> list[str]:
        """
        List all unique element tag names in the parsed XML document.

        Returns
        -------
        list[str]
            Sorted list of unique element tag names
        """
        self._require_root()

        element_types = set()
        root = self.root
        if root is None:
            return []
        for elem in root.iter():
            tag = elem.tag
            if tag.startswith("{"):
                tag = tag.split("}", 1)[1]
            element_types.add(tag)
        return sorted(element_types)

    def validate_schema_coverage(self) -> dict[str, Any]:
        """
        Validate schema coverage by analyzing recognized vs unrecognized element tags.

        Returns
        -------
        dict[str, Any]
            Dictionary containing coverage analysis results
        """
        self._require_root()

        # Get all element types in the document
        all_elements = set()
        element_frequency: dict[str, int] = {}
        root = self.root
        if root is None:
            return {
                "total_elements": 0,
                "unique_element_types": 0,
                "element_frequency": {},
                "element_types": [],
            }

        for elem in root.iter():
            tag = elem.tag
            if tag.startswith("{"):
                tag = tag.split("}", 1)[1]
            all_elements.add(tag)
            element_frequency[tag] = element_frequency.get(tag, 0) + 1

        # Build set of recognized element patterns from config
        recognized_patterns = self._build_recognized_patterns()

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

    def _build_recognized_patterns(self) -> set[str]:
        """Build set of recognized element patterns from config."""
        recognized_patterns: set[str] = set()

        # Add citation types directly
        recognized_patterns.update(self.config.citation_types)

        # Add patterns from all config pattern lists
        recognized_patterns.update(
            self._extract_elements_from_patterns(self.config.author_element_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.author_field_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.journal_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.article_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.table_patterns, simple=True)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.reference_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_patterns(self.config.inline_element_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.xref_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_dict_patterns(self.config.media_patterns)
        )
        recognized_patterns.update(
            self._extract_elements_from_patterns(self.config.object_id_patterns)
        )

        # Add common structural elements
        recognized_patterns.update(self._get_common_structural_elements())

        return recognized_patterns

    def _extract_element_from_pattern(self, pattern: str) -> set[str]:
        """Extract element names from XPath pattern."""
        elements: set[str] = set()
        pattern = pattern.lstrip("./")
        parts = pattern.split("/")
        for part in parts:
            elem_name = part.split("[")[0].strip()
            if elem_name and not elem_name.startswith("@"):
                elements.add(elem_name)
        return elements

    def _extract_elements_from_patterns(self, patterns: list[str]) -> set[str]:
        """Extract elements from a list of XPath patterns."""
        result: set[str] = set()
        for pattern in patterns:
            result.update(self._extract_element_from_pattern(pattern))
        return result

    def _extract_elements_from_dict_patterns(
        self, patterns_dict: dict[str, list[str]], simple: bool = False
    ) -> set[str]:
        """Extract elements from a dict of pattern lists."""
        result: set[str] = set()
        for patterns_list in patterns_dict.values():
            if isinstance(patterns_list, list):
                if simple:
                    result.update(patterns_list)
                else:
                    result.update(self._extract_elements_from_patterns(patterns_list))
        return result

    @staticmethod
    def _get_common_structural_elements() -> set[str]:
        """Get common structural elements that are implicitly recognized."""
        return {
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
            "addr-line",
            "xref",
            "person-group",
            "etal",
            "media",
            "underline",
            "month",
            "day",
            "object-id",
        }

    # =========================================================================
    # Generic extraction methods (kept for backward compatibility)
    # =========================================================================

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
            Keys are output field names, values are XPath-like patterns
        return_type : str
            'text': return text content; 'element': return Element; 'attribute': return attribute
        first_only : bool
            If True, only return the first match for each pattern
        get_attribute : dict, optional
            If return_type is 'attribute', a dict mapping field name to attribute name

        Returns
        -------
        dict
            Dictionary where each key is from the input dict and value is list of results
        """
        self._require_root()

        results: dict[str, list[Any]] = {}
        for key, pattern in patterns.items():
            matches = self.root.findall(pattern) if self.root is not None else []
            if not matches:
                results[key] = []
                continue
            values: list[Any]
            if return_type == "text":
                values = [XMLHelper.get_text_content(elem) for elem in matches]
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

    # =========================================================================
    # Helper methods (kept for backward compatibility)
    # =========================================================================

    def _get_text_content(self, element: ET.Element | None) -> str:
        """Get all text content from an element and its descendants."""
        return XMLHelper.get_text_content(element)

    def _extract_flat_texts(
        self,
        parent: ET.Element,
        pattern: str,
        filter_empty: bool = True,
        use_full_text: bool = False,
    ) -> list[str]:
        """Extract flat text fields from XML."""
        return XMLHelper.extract_flat_texts(parent, pattern, filter_empty, use_full_text)

    def _extract_nested_texts(
        self,
        parent: ET.Element,
        outer_pattern: str,
        inner_patterns: list[str],
        join: str = " ",
        filter_empty: bool = True,
    ) -> list[str]:
        """Extract nested text fields from XML."""
        return XMLHelper.extract_nested_texts(
            parent, outer_pattern, inner_patterns, join, filter_empty
        )

    def _extract_with_fallbacks(
        self, element: ET.Element, patterns: list[str], use_full_text: bool = False
    ) -> str | None:
        """Try multiple element patterns in order until one succeeds."""
        return XMLHelper.extract_with_fallbacks(element, patterns, use_full_text)

    def _extract_structured_fields(
        self,
        parent: ET.Element,
        field_patterns: dict[str, str],
        first_only: bool = True,
    ) -> dict[str, Any]:
        """Extract multiple fields from a parent element as a structured dict."""
        return XMLHelper.extract_structured_fields(parent, field_patterns, first_only)

    def _combine_page_range(self, fpage: str | None, lpage: str | None) -> str | None:
        """Combine first and last page into a page range."""
        return XMLHelper.combine_page_range(fpage, lpage)

    def _extract_inline_elements(
        self,
        element: ET.Element,
        inline_patterns: list[str] | None = None,
        filter_empty: bool = True,
    ) -> list[str]:
        """Extract text from inline elements."""
        return XMLHelper.extract_inline_elements(element, inline_patterns, filter_empty)

    def _get_text_without_inline_elements(
        self,
        element: ET.Element,
        inline_patterns: list[str] | None = None,
        remove_strategy: str = "regex",
    ) -> str:
        """Get text content with specified inline elements removed."""
        if remove_strategy != "regex":
            raise ValueError(f"Unknown remove_strategy: {remove_strategy}")
        return XMLHelper.get_text_without_inline_elements(element, inline_patterns)

    def _extract_reference_authors(self, citation: ET.Element) -> list[str]:
        """Extract author names from a reference citation element."""
        return XMLHelper.extract_nested_texts(
            citation,
            ".//person-group[@person-group-type='author']/name",
            ["given-names", "surname"],
            join=" ",
        )

    def _extract_section_structure(self, section: ET.Element) -> dict[str, str]:
        """Extract section title and content."""
        title = XMLHelper.extract_flat_texts(
            section, "title", filter_empty=False, use_full_text=True
        )
        paragraphs = XMLHelper.extract_flat_texts(
            section, ".//p", filter_empty=True, use_full_text=True
        )
        return {
            "title": title[0] if title else "",
            "content": "\n\n".join(paragraphs) if paragraphs else "",
        }
