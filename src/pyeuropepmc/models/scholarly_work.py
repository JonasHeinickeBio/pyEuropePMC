"""
Scholarly work entity base class.

This module provides the ScholarlyWorkEntity base class for entities representing
scholarly publications, including common fields and normalization logic.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from pyeuropepmc.models.base import BaseEntity

__all__ = ["ScholarlyWorkEntity"]


@dataclass
class ScholarlyWorkEntity(BaseEntity):
    """
    Base entity for scholarly works (papers, references, etc.).

    Provides common fields and methods for entities representing scholarly publications,
    including DOI normalization and basic bibliographic metadata.

    Attributes
    ----------
    title : Optional[str]
        Work title (xsd:string)
    doi : Optional[str]
        Digital Object Identifier (xsd:anyURI)
    volume : Optional[int | str]
        Publication volume (xsd:int or xsd:string for special cases)
    pages : Optional[str]
        Page range (xsd:string, e.g., "123-456")
    authors : Optional[list[dict[str, Any]] | str]
        Author information (enriched dicts for papers, string for references)
    publication_year : Optional[int]
        Publication year (xsd:gYear, 4-digit year)
    publication_date : Optional[date | str]
        Full publication date (xsd:date or xsd:string for partial dates)
    pmcid : Optional[str]
        PubMed Central ID (xsd:string, format: PMC followed by digits)
    pmid : Optional[str]
        PubMed ID (xsd:string, numeric identifier)
    semantic_scholar_id : Optional[str]
        Semantic Scholar paper ID (xsd:string)
    journal : Optional[str]
        Journal or publication venue name (xsd:string)
    """

    title: str | None = None
    doi: str | None = None
    volume: int | str | None = None
    pages: str | None = None
    authors: list[dict[str, Any]] | str | None = None
    publication_year: int | None = None
    publication_date: date | str | None = None
    pmcid: str | None = None
    pmid: str | None = None
    semantic_scholar_id: str | None = None
    journal: str | None = None

    def normalize(self) -> None:
        """Normalize scholarly work data (DOI lowercase, trim fields)."""
        from pyeuropepmc.models.utils import (
            normalize_doi,
            normalize_string_field,
            validate_and_normalize_date,
            validate_and_normalize_pmcid,
            validate_and_normalize_pmid,
            validate_and_normalize_volume,
        )

        self.doi = normalize_doi(self.doi)
        self.title = normalize_string_field(self.title)
        self.volume = validate_and_normalize_volume(self.volume)
        self.pages = normalize_string_field(self.pages)
        self.publication_date = validate_and_normalize_date(self.publication_date)
        self.pmcid = validate_and_normalize_pmcid(self.pmcid)
        self.pmid = validate_and_normalize_pmid(self.pmid)
        self.semantic_scholar_id = normalize_string_field(self.semantic_scholar_id)
        self.journal = normalize_string_field(self.journal)
        # Note: authors normalization is handled in subclasses due to different types
        super().normalize()

    def validate(self) -> None:
        """Validate scholarly work data."""
        from pyeuropepmc.models.utils import (
            validate_and_normalize_pmcid,
            validate_and_normalize_pmid,
            validate_and_normalize_year,
        )

        # Validate publication_year is a reasonable 4-digit year
        if self.publication_year is not None:
            self.publication_year = validate_and_normalize_year(self.publication_year)

        # Validate DOI format (basic check)
        if self.doi and not self.doi.replace(".", "").replace("/", "").replace("-", "").isalnum():
            # More sophisticated DOI validation could be added here
            pass

        # Validate PMCID format
        if self.pmcid:
            self.pmcid = validate_and_normalize_pmcid(self.pmcid)

        # Validate PMID format
        if self.pmid:
            self.pmid = validate_and_normalize_pmid(self.pmid)

        super().validate()
