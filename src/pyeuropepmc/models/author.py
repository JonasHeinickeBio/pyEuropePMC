"""
Author entity model for representing article authors.
"""

from dataclasses import dataclass
from typing import Any

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
    name : Optional[str]
        Display name (for enrichment compatibility)
    openalex_id : Optional[str]
        OpenAlex author ID
    institutions : Optional[list[dict]]
        Institutional affiliations with details
    position : Optional[str]
        Author position/role
    sources : Optional[list[str]]
        Data sources for this author information

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
    name: str | None = None
    openalex_id: str | None = None
    institutions: list[dict[str, Any]] | None = None
    position: str | None = None
    sources: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["foaf:Person"]
        if not self.label:
            self.label = self.full_name or self.name or ""

    def validate(self) -> None:
        """
        Validate author data.

        Raises
        ------
        ValueError
            If neither full_name nor name is provided or empty
        """
        if not (self.full_name.strip() or self.name and self.name.strip()):
            raise ValueError("AuthorEntity must have either full_name or name")

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
        if self.name:
            self.name = self.name.strip()
        if self.openalex_id:
            self.openalex_id = self.openalex_id.strip()
        if self.affiliation_text:
            self.affiliation_text = self.affiliation_text.strip()

    @classmethod
    def from_enrichment_dict(cls, author_dict: dict[str, Any]) -> "AuthorEntity":
        """
        Create an AuthorEntity from enrichment author dictionary.

        Parameters
        ----------
        author_dict : dict
            Author dictionary from enrichment result

        Returns
        -------
        AuthorEntity
            Author entity with enrichment data
        """
        return cls(
            full_name=author_dict.get("name", ""),
            name=author_dict.get("name"),
            first_name=author_dict.get("given_name"),
            last_name=author_dict.get("family_name"),
            orcid=author_dict.get("orcid"),
            openalex_id=author_dict.get("openalex_id"),
            institutions=author_dict.get("institutions"),
            position=author_dict.get("position"),
            sources=author_dict.get("sources"),
            affiliation_text=(
                ", ".join(author_dict.get("affiliations", []))
                if author_dict.get("affiliations")
                else None
            ),
        )
