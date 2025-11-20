"""
Paper entity model for representing academic articles.
"""

from dataclasses import dataclass, field
from typing import Any

from pyeuropepmc.models.base import BaseEntity
from pyeuropepmc.models.utils import normalize_doi

__all__ = ["PaperEntity"]


@dataclass
class PaperEntity(BaseEntity):
    """
    Entity representing an academic paper with BIBO alignment.

    Attributes
    ----------
    pmcid : Optional[str]
        PubMed Central ID
    doi : Optional[str]
        Digital Object Identifier
    title : Optional[str]
        Article title
    journal : Optional[str]
        Journal name
    volume : Optional[str]
        Journal volume
    issue : Optional[str]
        Journal issue
    pages : Optional[str]
        Page range
    pub_date : Optional[str]
        Publication date
    keywords : list[str]
        List of keywords
    abstract : Optional[str]
        Article abstract
    authors : Optional[list[dict]]
        List of author dictionaries with enrichment data
    citation_count : Optional[int]
        Total citation count from all sources
    influential_citation_count : Optional[int]
        Influential citation count
    topics : Optional[list[dict]]
        Research topics from OpenAlex
    fields_of_study : Optional[list[str]]
        Fields of study from Semantic Scholar
    funders : Optional[list[dict]]
        Funding information
    is_oa : Optional[bool]
        Open access status
    oa_status : Optional[str]
        Open access status details
    oa_url : Optional[str]
        Open access URL
    license : Optional[dict]
        License information
    publication_year : Optional[int]
        Publication year
    publication_date : Optional[str]
        Full publication date

    Examples
    --------
    >>> paper = PaperEntity(
    ...     pmcid="PMC1234567",
    ...     doi="10.1234/test.2021.001",
    ...     title="Test Article"
    ... )
    >>> paper.normalize()
    >>> paper.validate()
    """

    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    pub_date: str | None = None
    keywords: list[str] = field(default_factory=list)
    abstract: str | None = None
    authors: list[dict[str, Any]] | None = None
    citation_count: int | None = None
    influential_citation_count: int | None = None
    topics: list[dict[str, Any]] | None = None
    fields_of_study: list[str] | None = None
    funders: list[dict[str, Any]] | None = None
    is_oa: bool | None = None
    oa_status: str | None = None
    oa_url: str | None = None
    license: dict[str, Any] | None = None
    publication_year: int | None = None
    publication_date: str | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:AcademicArticle"]
        if not self.label:
            self.label = self.title or self.doi or self.pmcid or ""

    def validate(self) -> None:
        """
        Validate paper data.

        Raises
        ------
        ValueError
            If neither PMCID, DOI, nor title is provided
        """
        if not any([self.pmcid, self.doi, self.title]):
            raise ValueError("PaperEntity must have at least one of: pmcid, doi, title")

    def normalize(self) -> None:
        """Normalize paper data (DOI lowercase, trim whitespace)."""
        self.doi = normalize_doi(self.doi)
        if self.title:
            self.title = self.title.strip()
        if self.pmcid:
            self.pmcid = self.pmcid.strip()
        if self.journal:
            self.journal = self.journal.strip()
        if self.abstract:
            self.abstract = self.abstract.strip()
        if self.oa_url:
            self.oa_url = self.oa_url.strip()
        if self.publication_date:
            self.publication_date = self.publication_date.strip()

    @classmethod
    def from_enrichment_result(cls, enrichment_result: dict[str, Any]) -> "PaperEntity":
        """
        Create a PaperEntity from enrichment result.

        Parameters
        ----------
        enrichment_result : dict
            Enrichment result dictionary

        Returns
        -------
        PaperEntity
            Paper entity with enrichment data
        """
        merged = enrichment_result.get("merged", {})
        return cls(
            doi=enrichment_result.get("doi"),
            title=merged.get("title"),
            abstract=merged.get("abstract"),
            authors=merged.get("authors"),
            citation_count=merged.get("citation_count"),
            influential_citation_count=merged.get("influential_citation_count"),
            topics=merged.get("topics"),
            fields_of_study=merged.get("fields_of_study"),
            funders=merged.get("funders"),
            is_oa=merged.get("is_oa"),
            oa_status=merged.get("oa_status"),
            oa_url=merged.get("oa_url"),
            license=merged.get("license"),
            publication_year=merged.get("publication_year"),
            publication_date=merged.get("publication_date"),
            journal=merged.get("journal"),
        )
