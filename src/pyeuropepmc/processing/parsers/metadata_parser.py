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
        """Extract basic article metadata (pmcid, doi, title, abstract, volume, issue)."""
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
            "volume": self._extract_with_fallbacks(root, self.config.article_patterns["volume"]),
            "issue": self._extract_with_fallbacks(root, self.config.article_patterns["issue"]),
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
        assert self.root is not None  # nosec
        journal_info: dict[str, Any] = {}

        journal_meta_result = self.extract_elements_by_patterns(
            {"journal_meta": ".//journal-meta"}, return_type="element"
        )

        for journal_meta in journal_meta_result.get("journal_meta", []):
            # Extract journal title
            journal_info["title"] = self._extract_with_fallbacks(
                journal_meta, [".//journal-title"]
            )

            # Extract volume and issue from journal-meta first
            journal_info["volume"] = self._extract_with_fallbacks(
                journal_meta, [".//volume", ".//vol"]
            )
            journal_info["issue"] = self._extract_with_fallbacks(journal_meta, [".//issue"])

            # Extract ISSNs
            issn_print = self._extract_with_fallbacks(journal_meta, [".//issn[@pub-type='ppub']"])
            if issn_print:
                journal_info["issn_print"] = issn_print

            issn_electronic = self._extract_with_fallbacks(
                journal_meta, [".//issn[@pub-type='epub']"]
            )
            if issn_electronic:
                journal_info["issn_electronic"] = issn_electronic

            # Extract publisher name and location from journal-meta
            publisher_name = self._extract_with_fallbacks(
                journal_meta, [".//publisher/publisher-name", ".//publisher-name"]
            )
            if publisher_name:
                journal_info["publisher"] = publisher_name

            publisher_loc = self._extract_with_fallbacks(
                journal_meta, [".//publisher/publisher-loc", ".//publisher-loc"]
            )
            if publisher_loc:
                journal_info["country"] = publisher_loc

            # Add journal IDs
            self._extract_journal_ids(journal_meta, journal_info)
            break

        # If journal title not found in journal-meta, look in article-meta using journal patterns
        if not journal_info.get("title"):
            journal_info["title"] = self._extract_with_fallbacks(
                self.root, self.config.journal_patterns["title"]
            )

        # If volume/issue not found in journal-meta, look in article-meta
        if not journal_info.get("volume"):
            journal_info["volume"] = self._extract_with_fallbacks(
                self.root, [".//volume", ".//vol"]
            )
        if not journal_info.get("issue"):
            journal_info["issue"] = self._extract_with_fallbacks(self.root, [".//issue"])

        return journal_info

    def _extract_journal_ids(self, journal_meta: ET.Element, journal_info: dict[str, Any]) -> None:
        """Extract journal IDs from journal meta."""
        journal_ids = {}
        for journal_id_elem in journal_meta.findall(".//journal-id"):
            id_type = journal_id_elem.get("journal-id-type")
            if id_type:
                journal_ids[id_type] = journal_id_elem.text

        # Map common journal ID types to our fields
        if "nlm-ta" in journal_ids:
            journal_info["nlm_ta"] = journal_ids["nlm-ta"]
        if "iso-abbrev" in journal_ids:
            journal_info["iso_abbrev"] = journal_ids["iso-abbrev"]
        if "nlmid" in journal_ids:
            journal_info["nlmid"] = journal_ids["nlmid"]

        # Store all journal IDs for completeness
        if journal_ids:
            journal_info["journal_ids"] = journal_ids

    def _extract_issns(self, journal_meta: ET.Element, journal_info: dict[str, Any]) -> None:
        """Extract ISSNs from journal meta."""
        issns = {}
        for issn_elem in journal_meta.findall(".//issn"):
            pub_type = issn_elem.get("pub-type")
            if pub_type:
                issns[pub_type] = issn_elem.text

        # Map to our standard fields
        if "ppub" in issns:
            journal_info["issn_print"] = issns["ppub"]
        if "epub" in issns:
            journal_info["issn_electronic"] = issns["epub"]

        # Store all ISSNs for completeness
        if issns:
            journal_info["issns"] = issns

    def _extract_publisher_info(
        self, journal_meta: ET.Element, journal_info: dict[str, Any]
    ) -> None:
        """Extract publisher information from journal meta."""
        publisher_elem = journal_meta.find(".//publisher")
        if publisher_elem is not None:
            publisher_name = self._extract_with_fallbacks(publisher_elem, [".//publisher-name"])
            if publisher_name:
                journal_info["publisher_name"] = publisher_name

            publisher_loc = self._extract_with_fallbacks(publisher_elem, [".//publisher-loc"])
            if publisher_loc:
                journal_info["publisher_location"] = publisher_loc

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

        # Add extended metadata
        extended = self._extract_extended_metadata()
        if extended:
            metadata["extended_metadata"] = extended

    def _extract_extended_metadata(self) -> dict[str, Any]:
        """Extract extended metadata fields."""
        assert self.root is not None  # nosec
        extended: dict[str, Any] = {}

        # Conference information
        conf_name = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("conf_name", [])
        )
        if conf_name:
            extended["conference_name"] = conf_name

        conf_date = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("conf_date", [])
        )
        if conf_date:
            extended["conference_date"] = conf_date

        conf_loc = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("conf_loc", [])
        )
        if conf_loc:
            extended["conference_location"] = conf_loc

        # Article versioning
        article_version = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("article_version", [])
        )
        if article_version:
            extended["article_version"] = article_version

        # Alternative titles
        alt_title = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("alt_title", [])
        )
        if alt_title:
            extended["alternative_title"] = alt_title

        # Edition information
        edition = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("edition", [])
        )
        if edition:
            extended["edition"] = edition

        # Season information
        season = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("season", [])
        )
        if season:
            extended["season"] = season

        # Series information
        series = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("series", [])
        )
        if series:
            extended["series"] = series

        # Free to read status
        free_to_read = self._extract_with_fallbacks(
            self.root, self.config.extended_metadata_patterns.get("free_to_read", [])
        )
        if free_to_read:
            extended["free_to_read"] = True

        return extended

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

            # Return date if we have at least year
            if date_parts:
                date_str = "-".join(date_parts)
                logger.debug(f"Extracted pub_date: {date_str}")
                return date_str

        logger.debug("No publication date found.")
        return None
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

        # Try the standard award-group approach first
        award_groups_result = self.extract_elements_by_patterns(
            {"award_groups": ".//award-group"}, return_type="element"
        )

        for award_group in award_groups_result.get("award_groups", []):
            funding_data = self._extract_funding_from_group(award_group)
            if funding_data:
                funding_results.append(funding_data)

        # If no award-groups found, try alternative funding extraction
        if not funding_results:
            funding_results = self._extract_funding_from_body()

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

    def _extract_recipient(self, award_group: ET.Element) -> dict[str, Any]:
        """Extract recipient information from award group."""
        recipient_info: dict[str, Any] = {}
        recipients_list = []

        # Extract all principal-award-recipient elements (can be multiple)
        for recipient_elem in award_group.findall(".//principal-award-recipient"):
            surname = self._extract_with_fallbacks(recipient_elem, [".//surname"])
            given_names = self._extract_with_fallbacks(recipient_elem, [".//given-names"])

            if surname or given_names:
                recipient_data = {
                    "surname": surname,
                    "given_names": given_names,
                }
                # Build full name
                if given_names and surname:
                    recipient_data["full_name"] = f"{given_names} {surname}"
                elif surname:
                    recipient_data["full_name"] = surname
                elif given_names:
                    recipient_data["full_name"] = given_names

                recipients_list.append(recipient_data)

        if recipients_list:
            recipient_info["recipients"] = recipients_list
            # For backward compatibility, keep the first recipient as string
            if recipients_list[0].get("full_name"):
                recipient_info["recipient_full"] = recipients_list[0]["full_name"]

        return recipient_info

    def _extract_funding_from_body(self) -> list[dict[str, Any]]:
        """Extract funding information from body sections (alternative to award-group)."""
        funding_results: list[dict[str, Any]] = []

        # Look for sections with title "FUNDING" or similar
        funding_sections = self.extract_elements_by_patterns(
            {"funding_sections": ".//sec"}, return_type="element"
        )

        for section in funding_sections.get("funding_sections", []):
            if self._is_funding_section(section):
                funding_sources = section.findall(".//funding-source")
                if funding_sources:
                    self._process_funding_sources(section, funding_results)

        return funding_results

    def _is_funding_section(self, section: ET.Element) -> bool:
        """Check if a section is a funding section."""
        title_elem = section.find(".//title")
        if title_elem is not None and title_elem.text:
            return "FUNDING" in title_elem.text.upper()
        return False

    def _process_funding_sources(
        self, section: ET.Element, funding_results: list[dict[str, Any]]
    ) -> None:
        """Process funding sources and award IDs from a section."""
        current_source = None
        current_awards: list[str] = []

        # Simple approach: pair consecutive funding-source with following award-ids
        for elem in section.iter():
            if elem.tag == "funding-source":
                self._save_funding_group(current_source, current_awards, funding_results)
                current_source = elem.text.strip() if elem.text else ""
                current_awards = []
            elif elem.tag == "award-id" and elem.text:
                current_awards.append(elem.text.strip())

        # Save last group
        self._save_funding_group(current_source, current_awards, funding_results)

    def _save_funding_group(
        self, source: str | None, awards: list[str], funding_results: list[dict[str, Any]]
    ) -> None:
        """Save a funding source and its awards to results."""
        if source and awards:
            for award in awards:
                funding_data = {"source": source, "award_id": award}
                funding_results.append(funding_data)

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
