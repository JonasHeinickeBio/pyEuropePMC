"""
Affiliation parser for extracting affiliation information from XML.

This module provides specialized parsing for author affiliations and institutions.
"""

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.parsers.base_parser import BaseParser
from pyeuropepmc.features.fulltext.utils.geo_validators import GeoValidator
from pyeuropepmc.features.fulltext.utils.text_cleaners import TextCleaner
from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class AffiliationParser(BaseParser):
    """Specialized parser for affiliation extraction."""

    #: Left out of an affiliation's ``text``. <label> is the superscript
    #: marker that links the affiliation to its authors, and <institution-id>
    #: holds machine identifiers - a ROR URL, a GRID code, an ISNI. Neither is
    #: part of the address, and neither is separated from it by whitespace, so
    #: ``itertext`` ran them into the institution name: 18 of the 19
    #: affiliations across the corpus read "3https://ror.org/00a2xv884grid.
    #: 13402.340000 0004 1759 700XCenter of Cryo Electron Microscopy, ..."
    #: (#251).
    _TEXT_EXCLUDED = frozenset({"label", "institution-id"})

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the affiliation parser."""
        super().__init__(root, config)

    def extract_affiliations(self) -> list[dict[str, Any]]:
        """
        Extract the authors' affiliations from the full text XML.

        Only the article's own front matter is searched, and affiliations
        that belong to the editors rather than the authors are left out.
        A `.//aff` over the whole document returned an eLife article's 8
        author affiliations plus the 2 editor ones and the 23 belonging to
        the peer-review <sub-article> elements - 33 in all (#251).

        Returns
        -------
        list[dict[str, Any]]
            List of affiliation dictionaries
        """
        self._require_root()

        front = self._own_front(self.root)
        affiliations = [
            self._extract_single_affiliation(aff_elem)
            for aff_elem in self._author_affiliations(front)
        ]

        logger.debug(f"Extracted {len(affiliations)} affiliations")
        return affiliations

    @staticmethod
    def _is_author_contrib(contrib: ET.Element, group: ET.Element | None) -> bool:
        """Whether a <contrib> is an author rather than an editor or reviewer.

        Both JATS dialects count: ``contrib-type="author"`` on the
        contribution itself, and an untyped <contrib> whose <contrib-group>
        declares the role instead.
        """
        contrib_type = contrib.get("contrib-type")
        if contrib_type:
            return contrib_type == "author"
        group_type = group.get("content-type") if group is not None else None
        return group_type in (None, "author")

    def _author_affiliations(self, front: ET.Element) -> list[ET.Element]:
        """The <aff> elements in ``front`` that belong to the authors.

        An <aff> inside a <contrib-group> belongs to whoever that group
        describes. One at <article-meta> level is linked by ``rid``, so it
        is an editor's only when an editor cites it and no author does. An
        affiliation nobody cites is kept: single-affiliation articles often
        carry no <xref> at all.
        """
        author_rids: set[str] = set()
        other_rids: set[str] = set()
        group_of: dict[int, ET.Element] = {
            id(contrib): group
            for group in front.iter("contrib-group")
            for contrib in group.iter("contrib")
        }

        for contrib in front.iter("contrib"):
            target = (
                author_rids
                if self._is_author_contrib(contrib, group_of.get(id(contrib)))
                else other_rids
            )
            for xref in contrib.findall(".//xref[@ref-type='aff']"):
                rid = xref.get("rid")
                if rid:
                    target.add(rid)

        group_has_author = {
            id(group): any(
                self._is_author_contrib(contrib, group) for contrib in group.iter("contrib")
            )
            for group in front.iter("contrib-group")
        }
        owning_group = {
            id(aff): group for group in front.iter("contrib-group") for aff in group.iter("aff")
        }

        affiliations: list[ET.Element] = []
        for aff in front.iter("aff"):  # document order
            group = owning_group.get(id(aff))
            if group is not None:
                if group_has_author[id(group)]:
                    affiliations.append(aff)
                continue
            aff_id = aff.get("id")
            if aff_id and aff_id in other_rids and aff_id not in author_rids:
                continue
            affiliations.append(aff)

        return affiliations

    def _extract_single_affiliation(self, aff_elem: ET.Element) -> dict[str, Any]:
        """Extract data from a single affiliation element."""
        aff_data: dict[str, Any] = {}

        # Get ID attribute
        aff_data["id"] = aff_elem.get("id")

        # Get full text for reference
        aff_data["text"] = XMLHelper.get_text_content(aff_elem, exclude_tags=self._TEXT_EXCLUDED)

        # Extract institution IDs
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

        if any(structured.values()):
            aff_data.update(structured)
        else:
            self._parse_mixed_content_affiliation(aff_elem, aff_data)

        # Extract institution-wrap with multiple institutions + IDs
        institutions_list = self._extract_institution_wrap(aff_elem)
        if institutions_list:
            aff_data["institutions"] = institutions_list

        return aff_data

    def _extract_institution_wrap(self, aff_elem: ET.Element) -> list[dict[str, str]] | None:
        """Extract multiple institutions and their IDs from <institution-wrap> elements.

        JATS sometimes wraps institutions with persistent identifiers:
        ``<institution-wrap><institution-id ...>ROR</institution-id>...
           <institution>Name</institution></institution-wrap>``

        Returns a list of dicts, each with ``name`` and/or ``id`` keys.
        """
        institutions_list: list[dict[str, str]] = []

        for wrap in aff_elem.findall(".//institution-wrap"):
            # Collect all institution IDs from this wrapper
            ids: dict[str, str] = {}
            for inst_id in wrap.findall("institution-id"):
                id_type = inst_id.get("institution-id-type", "")
                id_value = inst_id.text
                if id_type and id_value:
                    ids[id_type] = id_value.strip()

            # Collect all institution names from this wrapper
            for inst in wrap.findall("institution"):
                entry: dict[str, Any] = {}
                name = "".join(inst.itertext()).strip()
                if name:
                    entry["name"] = name
                if ids:
                    entry["ids"] = dict(ids)
                institutions_list.append(entry)

        return institutions_list if institutions_list else None

    def _parse_mixed_content_affiliation(
        self, aff_elem: ET.Element, aff_data: dict[str, Any]
    ) -> None:
        """Parse mixed content affiliations without structured tags."""
        # Extract superscript markers
        markers = XMLHelper.extract_inline_elements(aff_elem, [".//sup"])
        if markers:
            aff_data["markers"] = ", ".join(markers)
            # Drop the <sup> subtrees rather than deleting every occurrence
            # of their text from the flattened string, which took the "1" out
            # of a street number as readily as out of the marker.
            clean_text = XMLHelper.get_text_content(
                aff_elem, exclude_tags=self._TEXT_EXCLUDED | {"sup"}
            )
            aff_data["institution_text"] = clean_text

            if clean_text:
                parsed_institutions = self._parse_multi_institution_affiliation(
                    clean_text, markers
                )
                if len(parsed_institutions) > 1:
                    aff_data["parsed_institutions"] = parsed_institutions
                elif len(parsed_institutions) == 1:
                    self._apply_parsed_institution(parsed_institutions[0], aff_data)
        else:
            # Reuse the full_text already extracted in the parent method
            full_text = aff_data.get("text", "")
            if full_text:
                parsed = self._parse_single_institution(full_text, [], 0)
                self._apply_parsed_institution(parsed, aff_data)

    def _apply_parsed_institution(
        self, parsed: dict[str, str | None], aff_data: dict[str, Any]
    ) -> None:
        """Apply parsed institution data to affiliation dict."""
        if parsed.get("name"):
            aff_data["institution"] = parsed["name"]
        if parsed.get("city"):
            aff_data["city"] = parsed["city"]
        if parsed.get("postal_code"):
            aff_data["postal_code"] = parsed["postal_code"]
        if parsed.get("country"):
            aff_data["country"] = parsed["country"]

    def _parse_multi_institution_affiliation(
        self, text: str, markers: list[str]
    ) -> list[dict[str, str | None]]:
        """Parse affiliations with multiple institutions separated by 'and'."""
        institutions = []
        parts = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)

        for i, part in enumerate(parts):
            part = part.strip().strip(",").strip()
            if not part:
                continue

            part = TextCleaner.clean_affiliation_text(part)
            institution = self._parse_single_institution(part, markers, i)
            institutions.append(institution)

        return institutions

    def _parse_single_institution(
        self, part: str, markers: list[str], index: int
    ) -> dict[str, str | None]:
        """Parse a single institution from affiliation text."""
        components = [comp.strip() for comp in part.split(",") if comp.strip()]

        if not components:
            return {
                "marker": markers[index] if index < len(markers) else None,
                "text": part,
            }

        remaining_components = components[:]

        # Extract geographic components
        country = GeoValidator.extract_country(remaining_components)
        postal_code = GeoValidator.extract_postal_code(remaining_components)
        state_province = GeoValidator.extract_state_province(remaining_components)
        city = GeoValidator.extract_city(remaining_components)

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

    def _extract_institution_ids(self, element: ET.Element) -> dict[str, str]:
        """Extract institution identifiers (ROR, GRID, ISNI, etc.)."""
        institution_ids = {}
        for inst_id_elem in element.findall(".//institution-id"):
            id_type = inst_id_elem.get("institution-id-type")
            id_value = inst_id_elem.text
            if id_type and id_value:
                institution_ids[id_type] = id_value.strip()
        return institution_ids
