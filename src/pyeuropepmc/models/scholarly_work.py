"""
Scholarly work entity base class.

This module provides the ScholarlyWorkEntity base class for entities representing
scholarly publications, including common fields and normalization logic.

Fields migrated from scholarly_work.linkml.yaml:
- abstract: Paper abstract
- citation_count: Number of citations
- source: Source system identifier (pubmed, semanticscholar, openalex, etc.)
- source_id: Original source identifier

LinkML schema: https://github.com/JonasHeinickeBio/pyEuropePMC/schemas/linkml/
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
    journal : Optional[str | Any]
        Journal or publication venue name (xsd:string) or JournalEntity
    abstract : Optional[str]
        Paper abstract (from linkml schema)
    citation_count : Optional[int]
        Number of citations (from linkml schema)
    source : Optional[str]
        Source system identifier (from linkml schema)
    source_id : Optional[str]
        Original source identifier (from linkml schema)
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
    journal: str | Any | None = None
    # Fields from linkml schema
    abstract: str | None = None
    citation_count: int | None = None
    source: str | None = None
    source_id: str | None = None

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
        self.abstract = normalize_string_field(self.abstract)
        self.publication_date = validate_and_normalize_date(self.publication_date)
        self.pmcid = validate_and_normalize_pmcid(self.pmcid)
        self.pmid = validate_and_normalize_pmid(self.pmid)
        self.semantic_scholar_id = normalize_string_field(self.semantic_scholar_id)
        self.source = normalize_string_field(self.source)
        self.source_id = normalize_string_field(self.source_id)
        # Normalize journal only if it's a string (not JournalEntity)
        if isinstance(self.journal, str):
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

        # Validate citation_count if present
        if self.citation_count is not None and self.citation_count < 0:
            raise ValueError("citation_count must be non-negative")

        super().validate()

    @classmethod
    def from_linkml(cls, data: dict[str, Any]) -> "ScholarlyWorkEntity":
        """
        Create a ScholarlyWorkEntity from linkml-style dictionary data.

        Parameters
        ----------
        data : dict[str, Any]
            Dictionary with linkml-style keys (doi, pmid, pmcid, title, authors,
            publication_year, journal, abstract, citation_count, source, source_id)

        Returns
        -------
        ScholarlyWorkEntity
            Entity initialized with linkml data

        Examples
        --------
        >>> work = ScholarlyWorkEntity.from_linkml({
        ...     "title": "Test Paper",
        ...     "doi": "10.1234/test",
        ...     "source": "pubmed",
        ...     "source_id": "12345"
        ... })
        """
        authors_data = data.get("authors", [])
        # Convert author dicts if needed
        if authors_data:
            authors = []
            for author in authors_data:
                if isinstance(author, dict):
                    authors.append(
                        {
                            "name": author.get("name"),
                            "orcid": author.get("orcid"),
                            "affiliation": author.get("affiliation"),
                            "institution": author.get("institution"),
                        }
                    )
                else:
                    authors.append(author)
        else:
            authors = []

        return cls(
            doi=data.get("doi"),
            pmid=data.get("pmid"),
            pmcid=data.get("pmcid"),
            title=data.get("title"),
            authors=authors if authors else None,
            publication_year=data.get("publication_year"),
            journal=data.get("journal"),
            abstract=data.get("abstract"),
            citation_count=data.get("citation_count"),
            source=data.get("source"),
            source_id=data.get("source_id"),
        )
