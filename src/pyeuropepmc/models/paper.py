"""
Paper entity model for representing academic articles.
"""

from dataclasses import dataclass, field
from typing import Optional

from pyeuropepmc.models.base import BaseEntity

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

    pmcid: Optional[str] = None
    doi: Optional[str] = None
    title: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    pub_date: Optional[str] = None
    keywords: list[str] = field(default_factory=list)

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
        if self.doi:
            # Normalize DOI: lowercase and remove URL prefix
            self.doi = (
                self.doi.lower()
                .replace("https://doi.org/", "")
                .replace("http://dx.doi.org/", "")
                .strip()
            )
        if self.title:
            self.title = self.title.strip()
        if self.pmcid:
            self.pmcid = self.pmcid.strip()
        if self.journal:
            self.journal = self.journal.strip()
