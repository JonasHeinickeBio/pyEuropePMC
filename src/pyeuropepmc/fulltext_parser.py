"""
Full text XML parser for Europe PMC articles.

This module provides functionality for parsing full text XML files from Europe PMC
and converting them to different output formats including metadata extraction,
markdown, plaintext, and table extraction.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import ParsingError

logger = logging.getLogger(__name__)

__all__ = ["FullTextXMLParser"]


class FullTextXMLParser:
    """Parser for Europe PMC full text XML files."""

    # XML namespaces commonly used in PMC articles
    NAMESPACES = {
        "xlink": "http://www.w3.org/1999/xlink",
        "mml": "http://www.w3.org/1998/Math/MathML",
    }

    def __init__(self, xml_content: str | None = None):
        """
        Initialize the parser with optional XML content.

        Parameters
        ----------
        xml_content : str, optional
            XML content string to parse
        """
        self.xml_content = xml_content
        self.root: ET.Element | None = None
        if xml_content:
            self.parse(xml_content)

    def parse(self, xml_content: str) -> ET.Element:
        """
        Parse XML content and store the root element.

        Parameters
        ----------
        xml_content : str
            XML content string to parse

        Returns
        -------
        ET.Element
            Root element of the parsed XML

        Raises
        ------
        ParsingError
            If XML parsing fails
        """
        if not xml_content or not isinstance(xml_content, str) or not xml_content.strip():
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

    def extract_metadata(self) -> dict[str, Any]:
        """
        Extract metadata from the full text XML.

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

        metadata: dict[str, Any] = {}

        try:
            # Extract PMCID
            pmcid_elem = self.root.find(".//article-id[@pub-id-type='pmcid']")
            metadata["pmcid"] = pmcid_elem.text if pmcid_elem is not None else None

            # Extract DOI
            doi_elem = self.root.find(".//article-id[@pub-id-type='doi']")
            metadata["doi"] = doi_elem.text if doi_elem is not None else None

            # Extract title
            title_elem = self.root.find(".//article-title")
            metadata["title"] = (
                self._get_text_content(title_elem) if title_elem is not None else None
            )

            # Extract authors
            metadata["authors"] = self._extract_authors()

            # Extract journal information
            journal_elem = self.root.find(".//journal-title")
            metadata["journal"] = journal_elem.text if journal_elem is not None else None

            # Extract publication date
            metadata["pub_date"] = self._extract_pub_date()

            # Extract volume and issue
            volume_elem = self.root.find(".//volume")
            metadata["volume"] = volume_elem.text if volume_elem is not None else None

            issue_elem = self.root.find(".//issue")
            metadata["issue"] = issue_elem.text if issue_elem is not None else None

            # Extract pages
            fpage_elem = self.root.find(".//fpage")
            lpage_elem = self.root.find(".//lpage")
            if fpage_elem is not None and lpage_elem is not None:
                metadata["pages"] = f"{fpage_elem.text}-{lpage_elem.text}"
            elif fpage_elem is not None:
                metadata["pages"] = fpage_elem.text
            else:
                metadata["pages"] = None

            # Extract abstract
            abstract_elem = self.root.find(".//abstract")
            metadata["abstract"] = (
                self._get_text_content(abstract_elem) if abstract_elem is not None else None
            )

            # Extract keywords
            metadata["keywords"] = self._extract_keywords()

            logger.debug(f"Extracted metadata for PMC{metadata.get('pmcid', 'Unknown')}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract metadata from XML"},
            ) from e

    def _extract_authors(self) -> list[str]:
        """Extract list of author names from XML."""
        if self.root is None:
            return []

        authors = []
        for contrib in self.root.findall(".//contrib[@contrib-type='author']"):
            name_elem = contrib.find(".//name")
            if name_elem is not None:
                surname = name_elem.find("surname")
                given_names = name_elem.find("given-names")

                if surname is not None:
                    author_name = surname.text or ""
                    if given_names is not None and given_names.text:
                        author_name = f"{given_names.text} {author_name}"
                    authors.append(author_name)

        return authors

    def _extract_pub_date(self) -> str | None:
        """Extract publication date from XML."""
        if self.root is None:
            return None

        # Try different publication date types
        for pub_type in ["ppub", "epub", "collection"]:
            pub_date = self.root.find(f".//pub-date[@pub-type='{pub_type}']")
            if pub_date is not None:
                year = pub_date.find("year")
                month = pub_date.find("month")
                day = pub_date.find("day")

                date_parts = []
                if year is not None and year.text:
                    date_parts.append(year.text)
                if month is not None and month.text:
                    date_parts.append(month.text.zfill(2))
                if day is not None and day.text:
                    date_parts.append(day.text.zfill(2))

                if date_parts:
                    return "-".join(date_parts)

        return None

    def _extract_keywords(self) -> list[str]:
        """Extract keywords from XML."""
        if self.root is None:
            return []

        keywords = []
        for kwd_elem in self.root.findall(".//kwd"):
            if kwd_elem.text:
                keywords.append(kwd_elem.text)

        return keywords

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

            # Extract title
            title_elem = self.root.find(".//article-title")
            if title_elem is not None:
                title = self._get_text_content(title_elem)
                text_parts.append(f"{title}\n\n")

            # Extract authors
            authors = self._extract_authors()
            if authors:
                text_parts.append(f"Authors: {', '.join(authors)}\n\n")

            # Extract abstract
            abstract_elem = self.root.find(".//abstract")
            if abstract_elem is not None:
                abstract = self._get_text_content(abstract_elem)
                text_parts.append(f"Abstract\n{abstract}\n\n")

            # Extract body sections
            body_elem = self.root.find(".//body")
            if body_elem is not None:
                for sec in body_elem.findall(".//sec"):
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
        """Process a section element to plain text."""
        text_parts = []

        # Extract section title
        title_elem = section.find("title")
        if title_elem is not None:
            title = self._get_text_content(title_elem)
            if title:
                text_parts.append(f"{title}\n")

        # Extract paragraphs
        for p in section.findall(".//p"):
            para_text = self._get_text_content(p)
            if para_text:
                text_parts.append(f"{para_text}\n")

        return "\n".join(text_parts)

    def to_markdown(self) -> str:
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

            # Extract title
            title_elem = self.root.find(".//article-title")
            if title_elem is not None:
                title = self._get_text_content(title_elem)
                md_parts.append(f"# {title}\n\n")

            # Extract authors
            authors = self._extract_authors()
            if authors:
                md_parts.append(f"**Authors:** {', '.join(authors)}\n\n")

            # Extract metadata
            metadata = self.extract_metadata()
            if metadata.get("journal"):
                md_parts.append(f"**Journal:** {metadata['journal']}\n\n")
            if metadata.get("doi"):
                md_parts.append(f"**DOI:** {metadata['doi']}\n\n")

            # Extract abstract
            abstract_elem = self.root.find(".//abstract")
            if abstract_elem is not None:
                abstract = self._get_text_content(abstract_elem)
                md_parts.append(f"## Abstract\n\n{abstract}\n\n")

            # Extract body sections
            body_elem = self.root.find(".//body")
            if body_elem is not None:
                for sec in body_elem.findall(".//sec"):
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
        """Process a section element to markdown."""
        md_parts = []

        # Extract section title
        title_elem = section.find("title")
        if title_elem is not None:
            title = self._get_text_content(title_elem)
            if title:
                md_parts.append(f"{'#' * level} {title}\n\n")

        # Extract paragraphs
        for p in section.findall(".//p"):
            para_text = self._get_text_content(p)
            if para_text:
                md_parts.append(f"{para_text}\n\n")

        # Process subsections
        for subsec in section.findall("./sec"):
            subsec_md = self._process_section_markdown(subsec, level=level + 1)
            if subsec_md:
                md_parts.append(subsec_md)

        return "".join(md_parts)

    def extract_tables(self) -> list[dict[str, Any]]:
        """
        Extract all tables from the full text XML.

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
            tables = []

            for table_wrap in self.root.findall(".//table-wrap"):
                table_data: dict[str, Any] = {}

                # Extract table ID
                table_id = table_wrap.get("id")
                table_data["id"] = table_id

                # Extract label
                label_elem = table_wrap.find("label")
                table_data["label"] = label_elem.text if label_elem is not None else None

                # Extract caption
                caption_elem = table_wrap.find("caption")
                table_data["caption"] = (
                    self._get_text_content(caption_elem) if caption_elem is not None else None
                )

                # Extract table content
                table_elem = table_wrap.find(".//table")
                if table_elem is not None:
                    headers, rows = self._parse_table(table_elem)
                    table_data["headers"] = headers
                    table_data["rows"] = rows
                else:
                    table_data["headers"] = []
                    table_data["rows"] = []

                tables.append(table_data)

            logger.debug(f"Extracted {len(tables)} tables from XML")
            return tables

        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract tables from XML"},
            ) from e

    def _parse_table(self, table_elem: ET.Element) -> tuple[list[str], list[list[str]]]:
        """
        Parse a table element into headers and rows.

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
        thead = table_elem.find("thead")
        if thead is not None:
            header_row = thead.find(".//tr")
            if header_row is not None:
                for th in header_row.findall(".//th"):
                    headers.append(self._get_text_content(th))

        # Extract rows from tbody
        tbody = table_elem.find("tbody")
        if tbody is not None:
            for tr in tbody.findall("tr"):
                row_data = []
                for td in tr.findall("td"):
                    row_data.append(self._get_text_content(td))
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
        Extract references/bibliography from the full text XML.

        Returns
        -------
        list of dict
            List of reference dictionaries containing:
            - id: Reference ID
            - label: Reference label (e.g., "1", "2")
            - authors: Author names
            - title: Article title
            - source: Journal or book name
            - year: Publication year
            - volume: Journal volume
            - pages: Page range

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
            references = []

            for ref in self.root.findall(".//ref"):
                ref_data: dict[str, str | None] = {}

                # Extract reference ID
                ref_data["id"] = ref.get("id")

                # Extract label
                label_elem = ref.find("label")
                ref_data["label"] = label_elem.text if label_elem is not None else None

                # Extract citation information
                citation = ref.find(".//element-citation")
                if citation is None:
                    citation = ref.find(".//mixed-citation")
                if citation is not None:
                    # Extract authors
                    authors = []
                    person_group = ".//person-group[@person-group-type='author']//name"
                    for person in citation.findall(person_group):
                        surname = person.find("surname")
                        given_names = person.find("given-names")
                        if surname is not None:
                            author = surname.text or ""
                            if given_names is not None and given_names.text:
                                author = f"{given_names.text} {author}"
                            authors.append(author)
                    ref_data["authors"] = ", ".join(authors) if authors else None

                    # Extract title
                    title_elem = citation.find("article-title")
                    ref_data["title"] = (
                        self._get_text_content(title_elem) if title_elem is not None else None
                    )

                    # Extract source
                    source_elem = citation.find("source")
                    ref_data["source"] = source_elem.text if source_elem is not None else None

                    # Extract year
                    year_elem = citation.find("year")
                    ref_data["year"] = year_elem.text if year_elem is not None else None

                    # Extract volume
                    volume_elem = citation.find("volume")
                    ref_data["volume"] = volume_elem.text if volume_elem is not None else None

                    # Extract pages
                    fpage = citation.find("fpage")
                    lpage = citation.find("lpage")
                    if fpage is not None and lpage is not None:
                        ref_data["pages"] = f"{fpage.text}-{lpage.text}"
                    elif fpage is not None:
                        ref_data["pages"] = fpage.text
                    else:
                        ref_data["pages"] = None

                references.append(ref_data)

            logger.debug(f"Extracted {len(references)} references from XML")
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
            sections = []

            body_elem = self.root.find(".//body")
            if body_elem is not None:
                for sec in body_elem.findall(".//sec"):
                    section_data = self._extract_section_data(sec)
                    if section_data:
                        sections.append(section_data)

            logger.debug(f"Extracted {len(sections)} sections from XML")
            return sections

        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"error": str(e), "message": "Failed to extract sections from XML"},
            ) from e

    def _extract_section_data(self, section: ET.Element) -> dict[str, str]:
        """Extract title and content from a section element."""
        section_data: dict[str, str] = {}

        # Extract section title
        title_elem = section.find("title")
        section_data["title"] = (
            self._get_text_content(title_elem) if title_elem is not None else ""
        )

        # Extract section content (paragraphs)
        content_parts = []
        for p in section.findall(".//p"):
            para_text = self._get_text_content(p)
            if para_text:
                content_parts.append(para_text)

        section_data["content"] = "\n\n".join(content_parts)

        return section_data
