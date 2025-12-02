"""
Affiliation parser for extracting affiliation information from XML.

This module provides specialized parsing for author affiliations and institutions.
"""

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.geo_validators import GeoValidator
from pyeuropepmc.processing.utils.text_cleaners import TextCleaner
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class AffiliationParser(BaseParser):
    """Specialized parser for affiliation extraction."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """Initialize the affiliation parser."""
        super().__init__(root, config)

    def extract_affiliations(self) -> list[dict[str, Any]]:
        """
        Extract author affiliations from the full text XML.

        Returns
        -------
        list[dict[str, Any]]
            List of affiliation dictionaries
        """
        self._require_root()

        aff_results = self.extract_elements_by_patterns(
            {"affiliations": ".//aff"}, return_type="element"
        )

        affiliations = []
        for aff_elem in aff_results.get("affiliations", []):
            aff_data = self._extract_single_affiliation(aff_elem)
            affiliations.append(aff_data)

        logger.debug(f"Extracted {len(affiliations)} affiliations")
        return affiliations

    def _extract_single_affiliation(self, aff_elem: ET.Element) -> dict[str, Any]:
        """Extract data from a single affiliation element."""
        aff_data: dict[str, Any] = {}

        # Get ID attribute
        aff_data["id"] = aff_elem.get("id")

        # Get full text for reference
        full_text = "".join(aff_elem.itertext()).strip()
        aff_data["text"] = full_text

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

        return aff_data

    def _parse_mixed_content_affiliation(
        self, aff_elem: ET.Element, aff_data: dict[str, Any]
    ) -> None:
        """Parse mixed content affiliations without structured tags."""
        # Extract superscript markers
        markers = XMLHelper.extract_inline_elements(aff_elem, [".//sup"])
        if markers:
            aff_data["markers"] = ", ".join(markers)
            clean_text = XMLHelper.get_text_without_inline_elements(aff_elem, [".//sup"])
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
            clean_text = "".join(aff_elem.itertext()).strip()
            if clean_text:
                parsed = self._parse_single_institution(clean_text, [], 0)
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
