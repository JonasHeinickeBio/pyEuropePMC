"""
Author entity model for representing article authors.
"""

from dataclasses import dataclass

from pyeuropepmc.models.base import BaseEntity

__all__ = ["AuthorEntity"]


@dataclass
class AuthorEntity(BaseEntity):
    """
    Entity representing an author with FOAF alignment.

    Attributes
    ----------
    full_name : str
        Full name of the author
    first_name : Optional[str]
        First/given name(s) of the author
    last_name : Optional[str]
        Last/family name of the author
    initials : Optional[str]
        Author's initials
    affiliation_text : Optional[str]
        Affiliation text for the author
    orcid : Optional[str]
        ORCID identifier

    Examples
    --------
    >>> author = AuthorEntity(
    ...     full_name="John Smith",
    ...     first_name="John",
    ...     last_name="Smith",
    ...     orcid="0000-0001-2345-6789"
    ... )
    >>> author.validate()
    """

    full_name: str = ""
    first_name: str | None = None
    last_name: str | None = None
    initials: str | None = None
    affiliation_text: str | None = None
    orcid: str | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["foaf:Person"]
        if not self.label:
            self.label = self.full_name

    def validate(self) -> None:
        """
        Validate author data.

        Raises
        ------
        ValueError
            If full_name is empty
        """
        if not self.full_name:
            raise ValueError("AuthorEntity must have a full_name")

    def normalize(self) -> None:
        """Normalize author data (trim whitespace)."""
        if self.full_name:
            self.full_name = self.full_name.strip()
        if self.first_name:
            self.first_name = self.first_name.strip()
        if self.last_name:
            self.last_name = self.last_name.strip()
        if self.orcid:
            self.orcid = self.orcid.strip()
