"""
Pydantic models for normalized literature search results.

This module provides typed models for literature search results that normalize
data from multiple sources (PubMed, Semantic Scholar, OpenAlex, etc.) into
a consistent format for downstream processing.
"""

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

if TYPE_CHECKING:
    from pyeuropepmc.models.paper import PaperEntity

#: Source names the package itself produces.  ``LiteratureResult.source`` is not
#: limited to these: a source registered with
#: :func:`pyeuropepmc.features.search.registry.register_source` reports its own name.
BUILTIN_SOURCES: frozenset[str] = frozenset(
    {
        "europepmc",
        "pubmed",
        "semanticscholar",
        "openalex",
        "crossref",
        "unpaywall",
        "arxiv",
        "clinicaltrials",
        "zenodo",
        "doaj",
        "dblp",
        "hal",
        "core",
        "icite",
    }
)

#: A source name: lower-case letters and digits, optionally joined by ``_ . -``.
_SOURCE_NAME = re.compile(r"^[a-z0-9]+(?:[_.-][a-z0-9]+)*$")


class Author(BaseModel):
    """
    Normalized author information.

    Attributes
    ----------
    name : str
        Author name in "Last, First" format
    orcid : Optional[str]
        ORCID identifier
    affiliation : Optional[str]
        Affiliation/institution name
    institution : Optional[str]
        Institution name (alternative to affiliation)
    position : Optional[str]
        Author position/role
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Author name in 'Last, First' format")
    orcid: str | None = Field(None, description="ORCID identifier")
    affiliation: str | None = Field(None, description="Affiliation/institution name")
    institution: str | None = Field(None, description="Institution name")
    position: str | None = Field(None, description="Author position/role")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty."""
        if not v or not v.strip():
            raise ValueError("Author name cannot be empty")
        return v.strip()

    @field_validator("orcid")
    @classmethod
    def validate_orcid(cls, v: str | None) -> str | None:
        """Validate ORCID format."""
        if v is None:
            return None
        # Accept both bare IDs and full URLs (e.g. https://orcid.org/0000-...)
        if v.startswith(("http://", "https://")):
            v = v.rstrip("/").rsplit("/", 1)[-1]
        # Basic ORCID format check
        if not v.replace("-", "").replace(" ", "").isalnum():
            raise ValueError(f"Invalid ORCID format: {v}")
        return v


class LiteratureResult(BaseModel):
    """
    Normalized literature search result.

    This model represents a paper/article from any literature source with
    standardized fields for downstream processing and LLM analysis.

    Attributes
    ----------
    doi : Optional[str]
        Digital Object Identifier (normalized lowercase)
    pmid : Optional[str]
        PubMed ID
    pmcid : Optional[str]
        PubMed Central ID
    title : Optional[str]
        Paper title (normalized)
    authors : Optional[list[Author]]
        List of authors
    publication_year : Optional[int]
        Year of publication
    journal : Optional[str]
        Journal name (normalized)
    abstract : Optional[str]
        Paper abstract
    citation_count : Optional[int]
        Number of citations
    source : str
        Source system (pubmed, semanticscholar, openalex, etc.).  Any
        lower-case identifier is accepted so registered third-party sources can
        use their own name; the value is stripped and lower-cased.
    source_id : str
        Original source identifier
    """

    model_config = ConfigDict(extra="allow")

    doi: str | None = Field(None, description="Digital Object Identifier (normalized lowercase)")
    pmid: str | None = Field(None, description="PubMed ID")
    pmcid: str | None = Field(None, description="PubMed Central ID")
    title: str | None = Field(None, description="Paper title (normalized)")
    authors: list[Author] | None = Field(None, description="List of authors")
    publication_year: int | None = Field(None, description="Year of publication")
    journal: str | None = Field(None, description="Journal name (normalized)")
    abstract: str | None = Field(None, description="Paper abstract")
    citation_count: int | None = Field(None, description="Number of citations")
    source: str = Field(..., description="Source system identifier")
    source_id: str = Field(..., description="Original source identifier")
    extra_metadata: dict[str, Any] | None = Field(
        None, description="Source-specific extra metadata"
    )

    # Source-specific extra fields
    semantic_scholar_data: dict[str, Any] | None = Field(
        None, description="Raw Semantic Scholar data"
    )
    openalex_data: dict[str, Any] | None = Field(None, description="Raw OpenAlex data")
    pubmed_data: dict[str, Any] | None = Field(None, description="Raw PubMed data")

    @field_validator("doi")
    @classmethod
    def normalize_doi(cls, v: str | None) -> str | None:
        """Normalize DOI to lowercase."""
        if v is None:
            return None
        # Remove DOI prefix if present
        v = v.replace("https://doi.org/", "").replace("http://doi.org/", "")
        return v.lower().strip()

    @field_validator("title")
    @classmethod
    def normalize_title(cls, v: str | None) -> str | None:
        """Normalize title."""
        if v is None:
            return None
        return v.strip()

    @field_validator("journal")
    @classmethod
    def normalize_journal(cls, v: str | None) -> str | None:
        """Normalize journal name."""
        if v is None:
            return None
        return v.strip()

    @field_validator("abstract")
    @classmethod
    def normalize_abstract(cls, v: str | None) -> str | None:
        """Normalize abstract."""
        if v is None:
            return None
        return v.strip()

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v: Any) -> Any:
        """Normalize the source name and check that it is a plain identifier.

        The set of sources is open — the search registry is pluggable — so this
        only rejects values that cannot be a source name, such as an empty
        string or one containing spaces.
        """
        if not isinstance(v, str):
            return v  # let pydantic's str validation report the type error
        name = v.strip().lower()
        if not _SOURCE_NAME.match(name):
            raise ValueError(
                f"Invalid source: {v!r}. Use a lower-case identifier such as "
                f"'pubmed' or 'my_repo' (built-in: {sorted(BUILTIN_SOURCES)})"
            )
        return name

    @field_serializer("publication_year")
    def serialize_year(self, year: int | None) -> int | None:
        """Serialize year as integer."""
        return year

    def to_paper_entity(self) -> "PaperEntity":
        """
        Convert to PaperEntity for use with existing enrichment pipeline.

        Returns
        -------
        PaperEntity
            PaperEntity with data from this result
        """
        from pyeuropepmc.models.journal import JournalEntity
        from pyeuropepmc.models.paper import PaperEntity

        # Build authors list
        authors_list = []
        if self.authors:
            for author in self.authors:
                author_dict: dict[str, Any] = {"name": author.name}
                if author.orcid:
                    author_dict["orcid"] = author.orcid
                if author.affiliation:
                    author_dict["affiliation"] = author.affiliation
                if author.institution:
                    author_dict["institution"] = author.institution
                authors_list.append(author_dict)

        return PaperEntity(
            doi=self.doi,
            pmid=self.pmid,
            pmcid=self.pmcid,
            title=self.title,
            authors=authors_list if authors_list else None,
            publication_year=self.publication_year,
            journal=JournalEntity(title=self.journal) if self.journal else None,
            abstract=self.abstract,
            citation_count=self.citation_count,
            openalex_id=self.source_id if self.source == "openalex" else None,
            semantic_scholar_id=self.source_id if self.source == "semanticscholar" else None,
        )

    def merge(self, other: "LiteratureResult") -> "LiteratureResult":
        """
        Merge two results, preferring non-None values from self.

        Parameters
        ----------
        other : LiteratureResult
            Another result to merge with

        Returns
        -------
        LiteratureResult
            Merged result with combined data
        """
        data = self.model_dump(exclude_unset=True, exclude_defaults=True)
        other_data = other.model_dump(exclude_unset=True, exclude_defaults=True)

        # Merge, preferring self values
        for key, value in other_data.items():
            if key not in data or data[key] is None:
                data[key] = value

        return LiteratureResult(**data)


class LiteratureSearchResponse(BaseModel):
    """
    Response from a literature search operation.

    Attributes
    ----------
    results : list[LiteratureResult]
        List of search results
    total_results : Optional[int]
        Total number of results available (if pagination supported)
    page : Optional[int]
        Current page number
    page_size : Optional[int]
        Number of results per page
    query : Optional[str]
        Original search query
    """

    model_config = ConfigDict(extra="allow")

    results: list[LiteratureResult] = Field(..., description="List of search results")
    total_results: int | None = Field(None, description="Total number of results available")
    page: int | None = Field(None, description="Current page number")
    page_size: int | None = Field(None, description="Number of results per page")
    query: str | None = Field(None, description="Original search query")

    def __iter__(self) -> Any:
        """Iterate over results."""
        return iter(self.results)

    def __len__(self) -> int:
        """Return number of results."""
        return len(self.results)

    def __getitem__(self, index: int) -> LiteratureResult:
        """Get result by index."""
        return self.results[index]


# Type alias for normalized work
NormalizedWork = LiteratureResult
