"""
Metadata parser for extracting article metadata from XML.

This module provides specialized parsing for article metadata.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.author_parser import AuthorParser
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class MetadataParser(BaseParser):
    """Specialized parser for metadata extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the metadata parser."""
        super().__init__(root, config)
        self._author_parser: AuthorParser | None = None

    @property
    def author_parser(self) -> AuthorParser:
        """Get the author parser instance."""
        if self._author_parser is None:
            self._author_parser = AuthorParser(self.root, self.config)
        return self._author_parser

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
            metadata = self._extract_basic_metadata()
            self._add_article_identifiers(metadata)
            metadata["journal"] = self._extract_journal_metadata()
            metadata["pages"] = self._extract_page_range()
            metadata["authors"] = self.author_parser.extract_authors()
            metadata["pub_date"] = self.extract_pub_date()
            metadata["keywords"] = self.extract_keywords()
            self._add_optional_metadata(metadata)

            logger.debug(
                f"Extracted metadata for PMC{metadata.get('pmcid', 'Unknown')}: {metadata}"
            )
            return metadata
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            raise

    def _extract_basic_metadata(self) -> dict[str, Any]:
        """Extract basic article metadata (pmcid, doi, title, abstract)."""
        root = self.root if self.root is not None else ET.Element("empty")
        return {
            "pmcid": self._extract_with_fallbacks(root, self.config.article_patterns["pmcid"]),
            "doi": self._extract_with_fallbacks(root, self.config.article_patterns["doi"]),
            "title": self._extract_with_fallbacks(
                root, self.config.article_patterns["title"], use_full_text=True
            ),
            "abstract": self._extract_with_fallbacks(
                root, self.config.article_patterns["abstract"], use_full_text=True
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
        root = self.root if self.root is not None else ET.Element("empty")
        journal_info: dict[str, Any] = {
            "title": self._extract_with_fallbacks(root, self.config.journal_patterns["title"]),
            "volume": self._extract_with_fallbacks(root, self.config.journal_patterns["volume"]),
            "issue": self._extract_with_fallbacks(root, self.config.journal_patterns["issue"]),
        }
        self._add_journal_ids_and_issns(journal_info)
        return journal_info

    def _add_journal_ids_and_issns(self, journal_info: dict[str, Any]) -> None:
        """Add journal IDs and ISSNs to journal info."""
        journal_meta_result = self.extract_elements_by_patterns(
            {"journal_meta": ".//journal-meta"}, return_type="element"
        )

        for journal_meta in journal_meta_result.get("journal_meta", []):
            # Extract nlm-ta
            nlm_ta = self._extract_with_fallbacks(
                journal_meta, [".//journal-id[@journal-id-type='nlm-ta']"]
            )
            if nlm_ta:
                journal_info["nlm_ta"] = nlm_ta

            # Extract iso-abbrev
            iso_abbrev = self._extract_with_fallbacks(
                journal_meta, [".//journal-id[@journal-id-type='iso-abbrev']"]
            )
            if iso_abbrev:
                journal_info["iso_abbrev"] = iso_abbrev

            # Extract ISSNs
            issn_print = self._extract_with_fallbacks(journal_meta, [".//issn[@pub-type='ppub']"])
            if issn_print:
                journal_info["issn_print"] = issn_print

            issn_electronic = self._extract_with_fallbacks(
                journal_meta, [".//issn[@pub-type='epub']"]
            )
            if issn_electronic:
                journal_info["issn_electronic"] = issn_electronic
            break

    def _extract_page_range(self) -> str | None:
        """Extract page range from first and last page."""
        root = self.root if self.root is not None else ET.Element("empty")
        fpage = self._extract_with_fallbacks(root, [".//fpage", ".//first-page"])
        lpage = self._extract_with_fallbacks(root, [".//lpage", ".//last-page"])
        return XMLHelper.combine_page_range(fpage, lpage)

    def _add_optional_metadata(self, metadata: dict[str, Any]) -> None:
        """Add optional metadata fields."""
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

    def extract_pub_date(self) -> str | None:
        """Extract publication date from XML."""
        self._require_root()

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
        self._require_root()
        root = self.root if self.root is not None else ET.Element("empty")
        keywords = self._extract_flat_texts(root, ".//kwd")
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords

    def extract_funding(self) -> list[dict[str, Any]]:
        """Extract funding information from the full text XML."""
        self._require_root()

        funding_results = []
        award_groups_result = self.extract_elements_by_patterns(
            {"award_groups": ".//award-group"}, return_type="element"
        )

        for award_group in award_groups_result.get("award_groups", []):
            funding_data = self._extract_funding_from_group(award_group)
            if funding_data:
                funding_results.append(funding_data)

        logger.debug(f"Extracted {len(funding_results)} funding entries")
        return funding_results

    def _extract_funding_from_group(self, award_group: ET.Element) -> dict[str, Any]:
        """Extract funding data from a single award-group element."""
        funding_data: dict[str, Any] = {}

        source_texts = self._extract_flat_texts(
            award_group, ".//funding-source//institution", filter_empty=True
        )
        if source_texts:
            funding_data["source"] = " ".join(source_texts)

        # Extract FundRef DOI
        for inst_id in award_group.findall(".//institution-id"):
            if inst_id.get("institution-id-type") == "FundRef" and inst_id.text:
                funding_data["fundref_doi"] = inst_id.text.strip()
                break

        award_id = self._extract_with_fallbacks(award_group, [".//award-id"])
        if award_id:
            funding_data["award_id"] = award_id

        recipient_info = self._extract_recipient(award_group)
        if recipient_info:
            funding_data.update(recipient_info)

        return funding_data

    def _extract_recipient(self, award_group: ET.Element) -> dict[str, str]:
        """Extract recipient information from award group."""
        recipient_info = {}
        for recipient_elem in award_group.findall(".//principal-award-recipient"):
            surname = self._extract_with_fallbacks(recipient_elem, [".//surname"])
            given_names = self._extract_with_fallbacks(recipient_elem, [".//given-names"])

            if surname:
                recipient_info["recipient"] = surname
                if given_names:
                    recipient_info["recipient_full"] = f"{given_names} {surname}"
            break
        return recipient_info

    def extract_license(self) -> dict[str, str | None]:
        """Extract license information from the full text XML."""
        self._require_root()

        license_info: dict[str, str | None] = {}
        license_result = self.extract_elements_by_patterns(
            {"licenses": ".//license"}, return_type="element"
        )

        for license_elem in license_result.get("licenses", []):
            license_type = license_elem.get("license-type")
            if license_type:
                license_info["type"] = license_type

            for ext_link in license_elem.findall(".//ext-link"):
                url = ext_link.get("{http://www.w3.org/1999/xlink}href")
                if url:
                    license_info["url"] = url
                break

            text = self._extract_with_fallbacks(license_elem, [".//license-p"])
            if text:
                license_info["text"] = text
            break

        return license_info if license_info else {}

    def extract_publisher(self) -> dict[str, str | None]:
        """Extract publisher information from the full text XML."""
        self._require_root()

        publisher_info: dict[str, str | None] = {}
        publisher_result = self.extract_elements_by_patterns(
            {"publishers": ".//publisher"}, return_type="element"
        )

        for publisher_elem in publisher_result.get("publishers", []):
            name = self._extract_with_fallbacks(publisher_elem, [".//publisher-name"])
            if name:
                publisher_info["name"] = name

            location = self._extract_with_fallbacks(publisher_elem, [".//publisher-loc"])
            if location:
                publisher_info["location"] = location
            break

        return publisher_info

    def extract_article_categories(self) -> dict[str, Any]:
        """Extract article categories and subjects from the full text XML."""
        self._require_root()

        categories: dict[str, Any] = {}

        article_result = self.extract_elements_by_patterns(
            {"articles": ".//article"}, return_type="element"
        )

        for article_elem in article_result.get("articles", []):
            article_type = article_elem.get("article-type")
            if article_type:
                categories["article_type"] = article_type
            break

        subject_groups = []
        subj_groups_result = self.extract_elements_by_patterns(
            {"subj_groups": ".//subj-group"}, return_type="element"
        )

        for subj_group in subj_groups_result.get("subj_groups", []):
            group_type = subj_group.get("subj-group-type")
            subjects = self._extract_flat_texts(subj_group, ".//subject", filter_empty=True)

            if subjects:
                group_data: dict[str, Any] = {"subjects": subjects}
                if group_type:
                    group_data["type"] = group_type
                subject_groups.append(group_data)

        if subject_groups:
            categories["subject_groups"] = subject_groups

        return categories

    def _extract_all_pub_ids(
        self, element: ET.Element, id_tag: str = "article-id"
    ) -> dict[str, str]:
        """Extract all publication IDs from element."""
        pub_ids = {}
        for id_elem in element.findall(f".//{id_tag}"):
            id_type = id_elem.get("pub-id-type")
            id_value = id_elem.text
            if id_type and id_value:
                pub_ids[id_type] = id_value.strip()
        return pub_ids
