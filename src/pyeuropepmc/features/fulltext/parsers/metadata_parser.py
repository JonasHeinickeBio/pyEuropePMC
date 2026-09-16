"""
Metadata parser for extracting article metadata from XML.

This module provides specialized parsing for article metadata.
"""

import contextlib
import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.author_parser import AuthorParser
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

# <pub-date> selection order. JATS 1.0 spells the attribute `pub-type`; JATS
# 1.1 uses `date-type`. Anything not listed here still qualifies if it carries
# a <year> - see MetadataParser._pub_date_rank.
# NISO Access and Licence Indicators; JATS carries the machine-readable
# licence URL as <ali:license_ref>.
_ALI_NS = "http://www.niso.org/schemas/ali/1.0/"

_PREFERRED_PUB_TYPES = ("ppub", "epub", "collection")
_PREFERRED_DATE_TYPES = ("pub", "collection")

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
            metadata["elocation_id"] = self._extract_elocation_id()
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
        """Extract basic article metadata (pmcid, doi, title, abstract, volume, issue).

        Everything here is read from the article's own <article-meta>. A
        `.//volume` over the whole document also matches every <volume> in
        the reference list, so an article that has no volume of its own took
        a reference's - and so did `issue` (#251).
        """
        scope = self._own_article_meta(self.root)
        return {
            "pmcid": self._extract_with_fallbacks(scope, self.config.article_patterns["pmcid"]),
            "doi": self._extract_with_fallbacks(scope, self.config.article_patterns["doi"]),
            "title": self._extract_with_fallbacks(
                scope, self.config.article_patterns["title"], use_full_text=True
            ),
            "abstract": self._extract_with_fallbacks(
                scope, self.config.article_patterns["abstract"], use_full_text=True
            ),
            "volume": self._extract_with_fallbacks(scope, self.config.article_patterns["volume"]),
            "issue": self._extract_with_fallbacks(scope, self.config.article_patterns["issue"]),
        }

    def _add_article_identifiers(self, metadata: dict[str, Any]) -> None:
        """Add article identifiers to metadata dict.

        Populates both the ``identifiers`` dict (all pub-id types) and
        top-level ``pmid`` field for backward compatibility.
        """
        article_meta_result = self.extract_elements_by_patterns(
            {"article_meta": ".//article-meta"}, return_type="element"
        )

        for article_meta in article_meta_result.get("article_meta", []):
            identifiers = self._extract_all_pub_ids(article_meta, "article-id")
            if identifiers:
                metadata["identifiers"] = identifiers
                # Also expose pmid as a top-level field for consumers
                # that expect metadata["pmid"] (e.g. benchmark ground truth)
                if "pmid" in identifiers and identifiers["pmid"]:
                    metadata["pmid"] = identifiers["pmid"]
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

        article_meta = self._own_article_meta(self.root)

        # If journal title not found in journal-meta, look in article-meta
        # using journal patterns - and only there, for the reason given in
        # _extract_basic_metadata. Over the whole document the `.//source`
        # fallback matches the journal name of the first *reference*.
        if not journal_info.get("title"):
            journal_info["title"] = self._extract_with_fallbacks(
                article_meta, self.config.journal_patterns["title"]
            )

        if not journal_info.get("volume"):
            journal_info["volume"] = self._extract_with_fallbacks(
                article_meta, [".//volume", ".//vol"]
            )
        if not journal_info.get("issue"):
            journal_info["issue"] = self._extract_with_fallbacks(article_meta, [".//issue"])

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
        """Extract page range from the article's own first and last page.

        Read from <article-meta>. Searched over the whole document this took
        the first <fpage>/<lpage> anywhere, and an article paginated with
        <elocation-id> - which has neither - was given the page range of its
        first reference: PMC11671585 reported "1-22" for an article whose
        elocation-id is 354 (#251).
        """
        scope = self._own_article_meta(self.root)
        fpage = self._extract_with_fallbacks(scope, [".//fpage", ".//first-page"])
        lpage = self._extract_with_fallbacks(scope, [".//lpage", ".//last-page"])
        return XMLHelper.combine_page_range(fpage, lpage)

    def _extract_elocation_id(self) -> str | None:
        """Extract the article's <elocation-id>.

        The electronic location identifier that replaces page numbers in
        online-only journals ("e1011761", "RP99323", "354").
        """
        scope = self._own_article_meta(self.root)
        return self._extract_with_fallbacks(scope, [".//elocation-id"])

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

        # Copyright information
        copyright_info = self._extract_copyright()
        if copyright_info:
            metadata["copyright"] = copyright_info

        # History dates (received, accepted, revised)
        history = self._extract_history_dates()
        if history:
            metadata["history"] = history

        # Correspondence information
        corresp = self._extract_corresp()
        if corresp:
            metadata["correspondence"] = corresp

        # Self URI (article landing page)
        self_uri = self._extract_self_uri()
        if self_uri:
            metadata["self_uri"] = self_uri

        # Document structure counts
        counts = self._extract_counts()
        if counts:
            metadata["counts"] = counts

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

    def _extract_copyright(self) -> dict[str, str | None] | None:
        """Extract copyright statement and year from article-meta."""
        assert self.root is not None  # nosec
        copyright_info: dict[str, str | None] = {}

        statement = self._extract_with_fallbacks(self.root, [".//copyright-statement"])
        if statement:
            copyright_info["statement"] = statement

        year = self._extract_with_fallbacks(self.root, [".//copyright-year"])
        if year:
            copyright_info["year"] = year

        return copyright_info if copyright_info else None

    def _extract_history_dates(self) -> list[dict[str, str]] | None:
        """Extract publication history dates (received, accepted, revised)."""
        assert self.root is not None  # nosec
        history_dates: list[dict[str, str]] = []

        # Try <history> first (JATS standard)
        for history_elem in self.root.findall(".//history"):
            for date_elem in history_elem.findall("date"):
                date_type = date_elem.get("date-type", "")
                year = date_elem.findtext("year", "")
                month = date_elem.findtext("month", "")
                day = date_elem.findtext("day", "")
                if year:
                    date_str = year
                    if month:
                        date_str += f"-{month.zfill(2)}"
                    if day:
                        date_str += f"-{day.zfill(2)}"
                    history_dates.append(
                        {
                            "type": date_type,
                            "date": date_str,
                        }
                    )

        # Also try <pub-history> (alternative JATS placement)
        for pub_hist in self.root.findall(".//pub-history"):
            for date_elem in pub_hist.findall("date"):
                date_type = date_elem.get("date-type", "")
                year = date_elem.findtext("year", "")
                month = date_elem.findtext("month", "")
                day = date_elem.findtext("day", "")
                if year:
                    date_str = year
                    if month:
                        date_str += f"-{month.zfill(2)}"
                    if day:
                        date_str += f"-{day.zfill(2)}"
                    history_dates.append(
                        {
                            "type": date_type,
                            "date": date_str,
                        }
                    )

        return history_dates if history_dates else None

    def _extract_corresp(self) -> list[dict[str, str]] | None:
        """Extract correspondence information (email, address)."""
        assert self.root is not None  # nosec
        corresp_entries: list[dict[str, str]] = []

        for corresp_elem in self.root.findall(".//corresp"):
            entry: dict[str, str] = {}
            corresp_id = corresp_elem.get("id", "")
            if corresp_id:
                entry["id"] = corresp_id

            # Extract email
            email_elem = corresp_elem.find("email")
            if email_elem is not None and email_elem.text:
                entry["email"] = email_elem.text.strip()

            # Extract full text
            full_text = "".join(corresp_elem.itertext()).strip()
            if full_text:
                entry["text"] = full_text

            if entry:
                corresp_entries.append(entry)

        return corresp_entries if corresp_entries else None

    def _extract_self_uri(self) -> str | None:
        """Extract the article's self-uri (landing page URL).

        Only the article's own front matter is searched, and a <self-uri>
        that points at an earlier version of the work is skipped. eLife
        lists the preprint and every reviewed preprint before the version of
        record, so the first one in PMC11687933 is the bioRxiv DOI of the
        preprint rather than anything belonging to this article (#251).
        """
        scope = self._own_front(self.root)
        fallback: str | None = None

        for self_uri in scope.findall(".//self-uri"):
            href = self_uri.get(
                "{http://www.w3.org/1999/xlink}href",
                self_uri.get("href", ""),
            )
            if not href:
                continue
            if "preprint" in (self_uri.get("content-type") or "").lower():
                fallback = fallback or href
                continue
            return href

        return fallback

    def _extract_counts(self) -> dict[str, int] | None:
        """Extract document structure counts (pages, figures, tables, equations, words)."""
        assert self.root is not None  # nosec
        counts: dict[str, int] = {}

        # Map JATS count tag names to our output keys
        count_mapping = {
            "page-count": "pages",
            "figure-count": "figures",
            "table-count": "tables",
            "equation-count": "equations",
            "word-count": "words",
        }

        for jats_tag, output_key in count_mapping.items():
            for elem in self.root.findall(f".//{jats_tag}"):
                count_str = elem.get("count", "")
                if count_str:
                    with contextlib.suppress(ValueError, TypeError):
                        counts[output_key] = int(count_str)

        return counts if counts else None

    @staticmethod
    def _pub_date_rank(pub_date: ET.Element) -> int:
        """Order a <pub-date> by how authoritative its type is.

        Lower sorts first. The three ``pub-type`` values keep the precedence
        the previous implementation had; JATS 1.1 ``date-type`` spellings come
        next; anything else - including the untyped form, which was the single
        most common in the sampled corpus - comes last but is still usable.
        """
        pub_type = pub_date.get("pub-type")
        if pub_type in _PREFERRED_PUB_TYPES:
            return _PREFERRED_PUB_TYPES.index(pub_type)

        date_type = pub_date.get("date-type")
        if date_type in _PREFERRED_DATE_TYPES:
            return len(_PREFERRED_PUB_TYPES) + _PREFERRED_DATE_TYPES.index(date_type)

        return len(_PREFERRED_PUB_TYPES) + len(_PREFERRED_DATE_TYPES)

    @staticmethod
    def _format_pub_date(pub_date: ET.Element) -> str | None:
        """Render one <pub-date> as YYYY, YYYY-MM or YYYY-MM-DD.

        A day is only emitted when a month is present: the previous code
        appended each component independently, so a <pub-date> carrying a year
        and a day but no month produced the malformed "2022-14".
        """
        year = (getattr(pub_date.find("year"), "text", None) or "").strip()
        if not year:
            return None

        parts = [year]
        month = (getattr(pub_date.find("month"), "text", None) or "").strip()
        if month:
            parts.append(month.zfill(2))
            day = (getattr(pub_date.find("day"), "text", None) or "").strip()
            if day:
                parts.append(day.zfill(2))
        return "-".join(parts)

    def extract_pub_date(self) -> str | None:
        """Extract publication date from XML."""
        self._require_root()
        root = self.root if self.root is not None else ET.Element("empty")

        # Matching only pub-type ppub/epub/collection missed 566 of 997 papers
        # that had a <pub-date> with a usable <year> (#210). The untyped form
        # alone accounted for 576 elements in the sample, more than any typed
        # one, and JATS 1.1 spells the attribute `date-type`. Rank every
        # candidate instead, and take the best that actually carries a year.
        # `sorted` is stable, so same-rank elements keep document order.
        for pub_date in sorted(root.findall(".//pub-date"), key=self._pub_date_rank):
            date_str = self._format_pub_date(pub_date)
            if date_str:
                logger.debug(f"Extracted pub_date: {date_str}")
                return date_str

        logger.debug("No publication date found.")
        return None

    def extract_keywords(self) -> list[str]:
        """Extract the article's own keywords (flat list of keyword strings).

        Scoped to the article's front matter: a peer-review <sub-article>
        has keywords of its own, and eLife tags its assessment vocabulary
        that way, so PMC11687933's author keywords came back with
        "Compelling" and "Important" appended (#251).
        """
        self._require_root()
        keywords = self._extract_flat_texts(self._own_front(self.root), ".//kwd")
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords

    def extract_keywords_detailed(self) -> list[dict[str, Any]]:
        """Extract keywords with kwd-group type awareness.

        Returns a list of keyword groups, each with:
        - ``type``: The ``kwd-group-type`` attribute (e.g. ``"author"``, ``"mesh"``)
        - ``keywords``: List of keyword strings in that group
        """
        self._require_root()
        root = self._own_front(self.root)
        kwd_groups: list[dict[str, Any]] = []

        for kwd_group in root.findall(".//kwd-group"):
            group_type = kwd_group.get("kwd-group-type", "")
            kwds = self._extract_flat_texts(kwd_group, ".//kwd", filter_empty=True)
            if kwds:
                group: dict[str, Any] = {"keywords": kwds}
                if group_type:
                    group["type"] = group_type
                kwd_groups.append(group)

        # Fallback: if no kwd-group wrapper, extract all kwd elements directly
        if not kwd_groups:
            kwds = self._extract_flat_texts(root, ".//kwd", filter_empty=True)
            if kwds:
                kwd_groups.append({"keywords": kwds})

        return kwd_groups

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
        if not source_texts:
            # Plenty of award-groups name the funder as direct text rather than
            # wrapping it in <institution>. Looking only for the nested form
            # left those groups with no source at all; where the group also had
            # no award-id and no recipient the dictionary came out empty and the
            # group was dropped entirely (#210). itertext() also picks up
            # <named-content content-type="funder-name"> and similar wrappers.
            source_texts = [
                text
                for source in award_group.findall(".//funding-source")
                if (text := " ".join("".join(source.itertext()).split()))
            ]
        if source_texts:
            funding_data["source"] = " ".join(source_texts)

        # Extract FundRef DOI
        for inst_id in award_group.findall(".//institution-id"):
            if inst_id.get("institution-id-type") == "FundRef" and inst_id.text:
                funding_data["fundref_doi"] = inst_id.text.strip()
                break

        # One award-group routinely names several grants - PMC11671585 has a
        # group with four <award-id> - and only the first was kept (#251).
        # `award_id` stays a string so existing consumers are unaffected;
        # `award_ids` carries the whole list.
        award_ids = self._extract_flat_texts(award_group, ".//award-id", filter_empty=True)
        if award_ids:
            funding_data["award_id"] = award_ids[0]
            funding_data["award_ids"] = award_ids

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

            # The canonical machine-readable URL is <ali:license_ref>, which
            # JATS carries alongside the human-readable <license-p>. Only
            # <ext-link> was consulted, so a licence whose URL lives solely in
            # license_ref came back without one.
            for ref in license_elem.findall(f".//{{{_ALI_NS}}}license_ref"):
                url = (ref.text or "").strip()
                if url:
                    license_info["url"] = url
                    break

            if "url" not in license_info:
                for ext_link in license_elem.findall(".//ext-link"):
                    url = ext_link.get("{http://www.w3.org/1999/xlink}href")
                    if url:
                        license_info["url"] = url
                        break

            # use_full_text=True: <license-p> routinely opens with an inline
            # element - "<bold>Open Access</bold>This article is..." - and the
            # default reads only the element's own leading text, which in that
            # case is whitespace and is filtered out as empty. PMC4569634
            # returned {} for a licence that is plainly there.
            text = self._extract_with_fallbacks(license_elem, [".//license-p"], use_full_text=True)
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

        # `.//article` never matches: the root element *is* <article>, and
        # ElementTree's descendant search does not include the element it is
        # called on, so article_type was never set on any document (#251).
        article_elem = self.root if self.root is not None and self.root.tag == "article" else None
        if article_elem is None and self.root is not None:
            article_elem = self.root.find(".//article")
        if article_elem is not None:
            article_type = article_elem.get("article-type")
            if article_type:
                categories["article_type"] = article_type

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
