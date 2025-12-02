"""
Geographic validation utilities for fulltext parser.

This module provides geographic validation functions for countries,
states/provinces, and postal codes.
"""

from collections.abc import Callable
import re


class GeoValidator:
    """Helper class for geographic validation operations."""

    # US state abbreviations (2-letter codes)
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",  # District of Columbia
    }

    # Canadian province/territory abbreviations
    CANADIAN_PROVINCES = {
        "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
    }

    # Australian state abbreviations
    AUSTRALIAN_STATES = {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}

    # UK country abbreviations (sometimes used as states)
    UK_COUNTRIES = {
        "ENG", "SCO", "WAL", "NIR",  # England, Scotland, Wales, Northern Ireland
    }

    # Known countries and abbreviations
    KNOWN_COUNTRIES = {
        "USA", "US", "UNITED STATES", "UK", "UNITED KINGDOM", "CANADA",
        "CHINA", "JAPAN", "GERMANY", "FRANCE", "ITALY", "SPAIN",
        "AUSTRALIA", "INDIA", "BRAZIL", "MEXICO", "RUSSIA", "SOUTH KOREA",
        "NETHERLANDS", "SWEDEN", "NORWAY", "DENMARK", "FINLAND", "POLAND",
        "BELGIUM", "AUSTRIA", "SWITZERLAND",
    }

    # Country indicators
    COUNTRY_INDICATORS = ["REPUBLIC", "FEDERATION", "KINGDOM", "EMIRATES", "STATES"]

    @staticmethod
    def is_likely_state_province(text: str) -> bool:
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
        text_upper = text.upper().strip()

        return (
            text_upper in GeoValidator.US_STATES
            or text_upper in GeoValidator.CANADIAN_PROVINCES
            or text_upper in GeoValidator.AUSTRALIAN_STATES
            or text_upper in GeoValidator.UK_COUNTRIES
        )

    @staticmethod
    def is_likely_country(text: str, clean_country_fn: Callable[[str], str] | None = None) -> bool:
        """
        Check if text is likely a country name.

        Parameters
        ----------
        text : str
            Text to check
        clean_country_fn : callable, optional
            Function to clean country name

        Returns
        -------
        bool
            True if text looks like a country
        """
        from pyeuropepmc.processing.utils.text_cleaners import TextCleaner

        # Clean the text first
        if clean_country_fn:
            cleaned = clean_country_fn(text).upper()
        else:
            cleaned = TextCleaner.clean_country_name(text).upper()

        # Check if the cleaned text starts with a known country
        for country in GeoValidator.KNOWN_COUNTRIES:
            if cleaned.startswith(country):
                return True

        # Check if it's an ISO code
        if len(cleaned) in (2, 3) and cleaned.isalpha():
            from pyeuropepmc.models.utils import ISO_COUNTRY_CODES

            return cleaned in ISO_COUNTRY_CODES

        # Check if it contains country-like words
        return any(indicator in cleaned for indicator in GeoValidator.COUNTRY_INDICATORS)

    @staticmethod
    def is_postal_code(text: str) -> bool:
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
        if re.match(r"^\w\d\w\d\w\d$", clean_text):
            return True

        # Also check for postal codes within longer strings
        if re.search(r"\b\w\d\w\s*\d\w\d\b", text):
            return True

        # UK postal codes: various patterns like SW1A 1AA, M1 1AA, etc.
        if re.match(r"^\w{1,2}\d{1,2}\w?\s*\d\w{2}$", text.upper()):
            return True

        # Other common postal code patterns (4-6 digits)
        return bool(re.match(r"^\d{4,6}$", clean_text))

    @staticmethod
    def extract_country(components: list[str]) -> str | None:
        """
        Extract country from components, modifying components in place.

        Parameters
        ----------
        components : list[str]
            List of address components

        Returns
        -------
        str or None
            Extracted country name
        """
        from pyeuropepmc.processing.utils.text_cleaners import TextCleaner

        if not components:
            return None

        last_comp = components[-1]
        if GeoValidator.is_likely_country(last_comp):
            country = TextCleaner.clean_country_name(last_comp)
            components.pop()
            return country
        return None

    @staticmethod
    def extract_state_province(components: list[str]) -> str | None:
        """
        Extract state/province from components, modifying components in place.

        Parameters
        ----------
        components : list[str]
            List of address components

        Returns
        -------
        str or None
            Extracted state/province
        """
        if not components:
            return None

        potential_state = components[-1]
        if GeoValidator.is_likely_state_province(potential_state):
            components.pop()
            return potential_state
        return None

    @staticmethod
    def extract_postal_code(components: list[str]) -> str | None:
        """
        Extract postal code from components, modifying components in place.

        Parameters
        ----------
        components : list[str]
            List of address components

        Returns
        -------
        str or None
            Extracted postal code
        """
        if not components:
            return None

        # First, look for standalone postal codes
        postal_candidates = []
        for i, comp in enumerate(components):
            if GeoValidator.is_postal_code(comp):
                postal_candidates.append((i, comp))

        if postal_candidates:
            # Take the last postal code found
            postal_idx, postal_code = postal_candidates[-1]
            components.pop(postal_idx)
            return postal_code

        # If no standalone postal codes, check if any component contains a postal code
        for i, comp in enumerate(components):
            postal_match = re.search(r"\b(\w\d\w\s*\d\w\d|\d{5}(?:-\d{4})?)\b", comp)
            if postal_match:
                postal_code = postal_match.group(1)
                # Remove postal code from the component
                remaining = re.sub(
                    r"\b(?:\w\d\w\s*\d\w\d|\d{5}(?:-\d{4})?)\b", "", comp
                ).strip()
                if remaining:
                    components[i] = remaining
                else:
                    components.pop(i)
                return postal_code

        return None

    @staticmethod
    def extract_city(components: list[str]) -> str | None:
        """
        Extract city from components, modifying components in place.

        Parameters
        ----------
        components : list[str]
            List of address components

        Returns
        -------
        str or None
            Extracted city name
        """
        if not components:
            return None

        # If we have components left, the last one before institution name is likely the city
        if len(components) >= 2:
            city = components.pop()
            return city

        return None
