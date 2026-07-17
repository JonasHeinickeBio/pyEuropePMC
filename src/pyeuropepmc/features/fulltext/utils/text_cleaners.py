"""
Text cleaning utilities for fulltext parser.

This module provides text cleaning and normalization functions.
"""

import re


class TextCleaner:
    """Helper class for text cleaning operations."""

    @staticmethod
    def clean_affiliation_text(text: str) -> str:
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
            r"http[s]?://(?:[a-zA-Z0-9$_.+!*'(),@&=-]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
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

    @staticmethod
    def clean_country_name(country: str) -> str:
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

    @staticmethod
    def clean_orcid(orcid: str | None) -> str | None:
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
