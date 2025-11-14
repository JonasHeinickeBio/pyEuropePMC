"""
Reference entity model for representing bibliographic references.
"""

from dataclasses import dataclass
from typing import Optional

from pyeuropepmc.models.base import BaseEntity

__all__ = ["ReferenceEntity"]


@dataclass
class ReferenceEntity(BaseEntity):
    """
    Entity representing a bibliographic reference with BIBO alignment.

    Attributes
    ----------
    title : Optional[str]
        Reference title
    source : Optional[str]
        Journal/book source
    year : Optional[str]
        Publication year
    volume : Optional[str]
        Journal volume
    pages : Optional[str]
        Page range
    doi : Optional[str]
        Digital Object Identifier
    authors : Optional[str]
        Author list (comma-separated)

    Examples
    --------
    >>> ref = ReferenceEntity(
    ...     title="Sample Article",
    ...     source="Nature",
    ...     year="2021",
    ...     doi="10.1038/nature12345"
    ... )
    >>> ref.validate()
    """

    title: Optional[str] = None
    source: Optional[str] = None
    year: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    authors: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["bibo:Document"]
        if not self.label:
            self.label = self.title or self.doi or "Untitled Reference"

    def validate(self) -> None:
        """Validate reference data."""
        # References can exist with minimal information
        pass

    def normalize(self) -> None:
        """Normalize reference data (DOI lowercase, trim whitespace)."""
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
        if self.source:
            self.source = self.source.strip()
