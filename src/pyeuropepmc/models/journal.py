"""
Journal entity model for representing academic journals and publications.
"""

from dataclasses import dataclass
from typing import Any

from pyeuropepmc.models.base import BaseEntity

__all__ = ["JournalEntity"]


@dataclass
class JournalEntity(BaseEntity):
    """
    Entity representing an academic journal with BIBO alignment.

    Attributes
    ----------
    title : str
        Full journal title
    medline_abbreviation : Optional[str]
        Medline abbreviation
    iso_abbreviation : Optional[str]
        ISO abbreviation
    nlmid : Optional[str]
        NLM ID (National Library of Medicine identifier)
    issn : Optional[str]
        ISSN (International Standard Serial Number)
    essn : Optional[str]
        Electronic ISSN
    publisher : Optional[str]
        Publisher name
    country : Optional[str]
        Country of publication
    language : Optional[str]
        Primary language of publication
    journal_issue_id : Optional[int]
        Europe PMC journal issue identifier
    openalex_id : Optional[str]
        OpenAlex journal ID
    wikidata_id : Optional[str]
        Wikidata identifier
    scopus_source_id : Optional[str]
        Scopus source identifier
    subject_areas : Optional[list[str]]
        Subject areas/categories
    impact_factor : Optional[float]
        Journal impact factor
    sjr : Optional[float]
        SCImago Journal Rank
    h_index : Optional[int]
        Journal h-index

    Examples
    --------
    >>> journal = JournalEntity(
    ...     title="Nature",
    ...     issn="0028-0836",
    ...     publisher="Nature Publishing Group"
    ... )
    >>> journal.validate()
    """

    title: str = ""
    medline_abbreviation: str | None = None
    iso_abbreviation: str | None = None
    nlmid: str | None = None
    issn: str | None = None
    essn: str | None = None
    publisher: str | None = None
    country: str | None = None
    language: str | None = None
    journal_issue_id: int | None = None
    openalex_id: str | None = None
    wikidata_id: str | None = None
    scopus_source_id: str | None = None
    subject_areas: list[str] | None = None
    impact_factor: float | None = None
    sjr: float | None = None
    h_index: int | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Journal"]
        if not self.label:
            self.label = self.title or self.medline_abbreviation or self.iso_abbreviation or ""

    def validate(self) -> None:
        """
        Validate journal data.

        Raises
        ------
        ValueError
            If title is not provided or empty
        """
        from pyeuropepmc.models.utils import (
            validate_and_normalize_uri,
            validate_positive_integer,
        )

        if not self.title or not self.title.strip():
            raise ValueError("JournalEntity must have a title")

        # Validate ISSN formats (basic validation)
        if self.issn:
            self.issn = self._validate_issn_format(self.issn)
        if self.essn:
            self.essn = self._validate_issn_format(self.essn)

        # Validate URIs
        if self.openalex_id:
            self.openalex_id = validate_and_normalize_uri(self.openalex_id)
        if self.wikidata_id:
            self.wikidata_id = validate_and_normalize_uri(self.wikidata_id)

        # Validate positive numbers
        if self.journal_issue_id is not None:
            self.journal_issue_id = validate_positive_integer(self.journal_issue_id)
        if self.impact_factor is not None and self.impact_factor >= 0:
            pass  # Already validated as float
        if self.sjr is not None and self.sjr >= 0:
            pass  # Already validated as float
        if self.h_index is not None:
            self.h_index = validate_positive_integer(self.h_index)

        super().validate()

    def _validate_issn_format(self, issn: str) -> str:
        """Validate ISSN format (XXXX-XXXX)."""
        import re

        if not re.match(r"^\d{4}-\d{3}[\dX]$", issn):
            raise ValueError(f"Invalid ISSN format: {issn}")
        return issn

    def normalize(self) -> None:
        """Normalize journal data (trim whitespace, validate identifiers)."""
        from pyeuropepmc.models.utils import (
            normalize_string_field,
            validate_and_normalize_uri,
        )

        self.title = normalize_string_field(self.title) or ""
        self.medline_abbreviation = normalize_string_field(self.medline_abbreviation)
        self.iso_abbreviation = normalize_string_field(self.iso_abbreviation)
        self.nlmid = normalize_string_field(self.nlmid)
        if self.issn:
            self.issn = self._validate_issn_format(self.issn)
        if self.essn:
            self.essn = self._validate_issn_format(self.essn)
        self.publisher = normalize_string_field(self.publisher)
        self.country = normalize_string_field(self.country)
        self.language = normalize_string_field(self.language)
        self.openalex_id = validate_and_normalize_uri(self.openalex_id)
        self.wikidata_id = validate_and_normalize_uri(self.wikidata_id)
        self.scopus_source_id = normalize_string_field(self.scopus_source_id)

        super().normalize()

    @classmethod
    def from_search_result(cls, journal_info: dict[str, Any]) -> "JournalEntity":
        """
        Create a JournalEntity from Europe PMC search result journal info.

        Parameters
        ----------
        journal_info : dict
            Journal information from Europe PMC search result

        Returns
        -------
        JournalEntity
            Journal entity with search result data
        """
        # Handle both nested format (from API) and flat format (from search parser)
        if "journal" in journal_info:
            # Nested format from API
            journal_data = journal_info.get("journal", {})
            title = journal_data.get("title", "")
            medline_abbreviation = journal_data.get("medlineAbbreviation")
            iso_abbreviation = journal_data.get("isoabbreviation")
            nlmid = journal_data.get("nlmid")
            issn = journal_data.get("issn")
            essn = journal_data.get("essn")
            journal_issue_id = journal_info.get("journalIssueId")
        else:
            # Flat format from search parser
            title = journal_info.get("title", "")
            medline_abbreviation = None
            iso_abbreviation = None
            nlmid = None
            issn = journal_info.get("issn")
            essn = None
            journal_issue_id = None

        return cls(
            title=title,
            medline_abbreviation=medline_abbreviation,
            iso_abbreviation=iso_abbreviation,
            nlmid=nlmid,
            issn=issn,
            essn=essn,
            journal_issue_id=journal_issue_id,
        )

    @classmethod
    def from_enrichment_dict(cls, journal_dict: dict[str, Any]) -> "JournalEntity":
        """
        Create a JournalEntity from enrichment journal dictionary.

        Parameters
        ----------
        journal_dict : dict
            Journal dictionary from enrichment result

        Returns
        -------
        JournalEntity
            Journal entity with enrichment data
        """
        return cls(
            title=journal_dict.get("display_name", ""),
            issn=journal_dict.get("issn"),
            openalex_id=journal_dict.get("id"),
            publisher=journal_dict.get("publisher"),
            country=journal_dict.get("country"),
            subject_areas=journal_dict.get("subjects"),
            impact_factor=journal_dict.get("impact_factor"),
            sjr=journal_dict.get("sjr"),
            h_index=journal_dict.get("h_index"),
        )
