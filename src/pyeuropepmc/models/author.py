"""
Author entity model for representing article authors.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyeuropepmc.models.base import BaseEntity

if TYPE_CHECKING:
    from pyeuropepmc.models.institution import InstitutionEntity

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
    semantic_scholar_id : Optional[str]
        Semantic Scholar author ID
    institutions : Optional[list[InstitutionEntity]]
        Institutional affiliations as InstitutionEntity objects
    position : Optional[str]
        Author position/role
    sources : Optional[list[str]]
        Data sources for this author information
    email : Optional[str]
        Email address
    semantic_scholar_author_id : Optional[str]
        Semantic Scholar author ID (alternative field)
    scopus_author_id : Optional[str]
        Scopus author ID
    researcher_id : Optional[str]
        ResearcherID
    orcid_works_count : Optional[int]
        Number of works associated with ORCID
    h_index : Optional[int]
        H-index from various sources
    citation_count : Optional[int]
        Total citation count for author
    paper_count : Optional[int]
        Total number of papers by author
    data_sources : list[str]
        List of data sources that contributed to this entity
    last_updated : Optional[str]
        Timestamp of last data update

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
    semantic_scholar_id: str | None = None
    institutions: list["InstitutionEntity"] | None = None
    position: str | None = None
    sources: list[str] | None = None
    email: str | None = None

    # Additional enrichment fields
    semantic_scholar_author_id: str | None = None
    scopus_author_id: str | None = None
    researcher_id: str | None = None
    orcid_works_count: int | None = None
    h_index: int | None = None
    citation_count: int | None = None
    paper_count: int | None = None

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
        from pyeuropepmc.models.utils import (
            validate_and_normalize_email,
            validate_and_normalize_orcid,
            validate_and_normalize_uri,
            validate_positive_integer,
        )

        if not (self.full_name.strip() or self.name and self.name.strip()):
            raise ValueError("AuthorEntity must have either full_name or name")

        # Validate and normalize identifiers
        if self.orcid:
            self.orcid = validate_and_normalize_orcid(self.orcid)
        if self.email:
            self.email = validate_and_normalize_email(self.email)
        if self.openalex_id:
            self.openalex_id = validate_and_normalize_uri(self.openalex_id)
        if self.semantic_scholar_id:
            self.semantic_scholar_id = validate_and_normalize_uri(self.semantic_scholar_id)

        # Validate positive integer fields
        if self.orcid_works_count is not None:
            self.orcid_works_count = validate_positive_integer(self.orcid_works_count)
        if self.h_index is not None:
            self.h_index = validate_positive_integer(self.h_index)
        if self.citation_count is not None:
            self.citation_count = validate_positive_integer(self.citation_count)
        if self.paper_count is not None:
            self.paper_count = validate_positive_integer(self.paper_count)

        super().validate()

    def normalize(self) -> None:
        """Normalize author data (trim whitespace, validate identifiers)."""
        from pyeuropepmc.models.utils import (
            normalize_string_field,
            validate_and_normalize_email,
            validate_and_normalize_orcid,
            validate_and_normalize_uri,
        )

        self.full_name = normalize_string_field(self.full_name) or ""
        self.first_name = normalize_string_field(self.first_name)
        self.last_name = normalize_string_field(self.last_name)
        self.initials = normalize_string_field(self.initials)
        self.affiliation_text = normalize_string_field(self.affiliation_text)
        self.orcid = validate_and_normalize_orcid(self.orcid)
        self.name = normalize_string_field(self.name)
        self.openalex_id = validate_and_normalize_uri(self.openalex_id)
        self.semantic_scholar_id = validate_and_normalize_uri(self.semantic_scholar_id)
        self.semantic_scholar_author_id = normalize_string_field(self.semantic_scholar_author_id)
        self.scopus_author_id = normalize_string_field(self.scopus_author_id)
        self.researcher_id = normalize_string_field(self.researcher_id)
        self.position = normalize_string_field(self.position)
        if self.email:
            self.email = validate_and_normalize_email(self.email)

        super().normalize()

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
        from pyeuropepmc.models.institution import InstitutionEntity

        # Convert institution dictionaries to InstitutionEntity objects
        institutions_data = author_dict.get("institutions", [])
        institution_entities = []

        for inst_data in institutions_data:
            if isinstance(inst_data, dict):
                # Convert dict to InstitutionEntity
                institution_entities.append(InstitutionEntity.from_enrichment_dict(inst_data))
            elif isinstance(inst_data, InstitutionEntity):
                # Already an InstitutionEntity
                institution_entities.append(inst_data)

        return cls(
            full_name=author_dict.get("name", ""),
            first_name=author_dict.get("given_name"),
            last_name=author_dict.get("family_name"),
            orcid=author_dict.get("orcid"),
            openalex_id=author_dict.get("openalex_id") or author_dict.get("id"),
            semantic_scholar_id=author_dict.get("semantic_scholar_id"),
            semantic_scholar_author_id=author_dict.get("semantic_scholar_author_id"),
            scopus_author_id=author_dict.get("scopus_author_id"),
            researcher_id=author_dict.get("researcher_id"),
            institutions=institution_entities if institution_entities else None,
            position=author_dict.get("position"),
            sources=author_dict.get("sources", []),
            affiliation_text=author_dict.get("affiliation"),
            email=author_dict.get("email"),
            orcid_works_count=author_dict.get("orcid_works_count"),
            h_index=author_dict.get("h_index"),
            citation_count=author_dict.get("citation_count"),
            paper_count=author_dict.get("paper_count"),
            data_sources=author_dict.get("data_sources", []),
            last_updated=author_dict.get("last_updated"),
        )
