"""
Paper entity model for representing academic articles.
"""

from dataclasses import dataclass, field
from typing import Any

from pyeuropepmc.models.scholarly_work import ScholarlyWorkEntity

__all__ = ["PaperEntity"]


@dataclass
class PaperEntity(ScholarlyWorkEntity):
    """
    Entity representing an academic paper with BIBO alignment.

    Attributes
    ----------
    issue : Optional[str]
        Journal issue
    pub_date : Optional[str]
        Publication date (legacy field, use publication_date instead)
    keywords : list[str]
        List of keywords
    abstract : Optional[str]
        Article abstract
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
    external_ids : Optional[dict]
        External identifiers from various sources
    reference_count : Optional[int]
        Number of references cited
    cited_by_count : Optional[int]
        Number of papers citing this work
    publisher : Optional[str]
        Publisher name
    issn : Optional[str]
        ISSN identifier
    publication_type : Optional[str]
        Type of publication
    first_page : Optional[str]
        First page number
    last_page : Optional[str]
        Last page number
    related_works : Optional[list[str]]
        Related work IDs

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

    issue: str | None = None
    pub_date: str | None = None
    keywords: list[str] = field(default_factory=list)
    abstract: str | None = None
    citation_count: int | None = None
    influential_citation_count: int | None = None
    topics: list[dict[str, Any]] | None = None
    fields_of_study: list[str] | None = None
    # Open access and availability
    is_oa: bool | None = None
    oa_status: str | None = None
    oa_url: str | None = None
    has_pdf: bool | None = None
    has_supplementary: bool | None = None
    in_epmc: bool | None = None
    in_pmc: bool | None = None

    # Citation and impact metrics
    cited_by_count: int | None = None
    reference_count: int | None = None

    # Publication metadata
    pub_type: str | None = None
    journal_issn: str | None = None
    page_info: str | None = None
    first_page: str | None = None
    last_page: str | None = None
    publisher: str | None = None
    issn: str | None = None
    publication_type: str | None = None

    # Indexing and availability flags
    has_references: bool | None = None
    has_text_mined_terms: bool | None = None
    has_db_cross_references: bool | None = None
    has_labs_links: bool | None = None
    has_tm_accession_numbers: bool | None = None

    # Dates
    first_index_date: str | None = None
    first_publication_date: str | None = None

    # External identifiers
    semantic_scholar_corpus_id: str | None = None
    openalex_id: str | None = None
    external_ids: dict[str, Any] | None = None
    external_id_conflicts: dict[str, Any] | None = None

    # Additional metadata
    funders: list[dict[str, Any]] | None = None
    license: dict[str, Any] | None = None
    related_works: list[str] | None = None

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
        from pyeuropepmc.models.utils import (
            validate_and_normalize_boolean,
            validate_and_normalize_uri,
            validate_positive_integer,
        )

        if not any([self.pmcid, self.doi, self.title]):
            raise ValueError("PaperEntity must have at least one of: pmcid, doi, title")

        # Validate and normalize citation counts
        if self.citation_count is not None:
            self.citation_count = validate_positive_integer(self.citation_count)
        if self.influential_citation_count is not None:
            self.influential_citation_count = validate_positive_integer(
                self.influential_citation_count
            )
        if self.reference_count is not None:
            self.reference_count = validate_positive_integer(self.reference_count)
        if self.cited_by_count is not None:
            self.cited_by_count = validate_positive_integer(self.cited_by_count)

        # Validate and normalize boolean fields
        if self.is_oa is not None:
            self.is_oa = validate_and_normalize_boolean(self.is_oa)

        # Validate URIs
        if self.oa_url:
            self.oa_url = validate_and_normalize_uri(self.oa_url)

        super().validate()

    def normalize(self) -> None:
        """Normalize paper data (trim whitespace, validate types)."""
        from pyeuropepmc.models.utils import (
            normalize_doi,
            normalize_string_field,
        )

        self.doi = normalize_doi(self.doi)
        self.issue = normalize_string_field(self.issue)
        self.pub_date = normalize_string_field(self.pub_date)
        self.abstract = normalize_string_field(self.abstract)
        self.oa_status = normalize_string_field(self.oa_status)
        self.publisher = normalize_string_field(self.publisher)
        self.issn = normalize_string_field(self.issn)
        self.publication_type = normalize_string_field(self.publication_type)
        self.first_page = normalize_string_field(self.first_page)
        self.last_page = normalize_string_field(self.last_page)
        self.semantic_scholar_corpus_id = normalize_string_field(self.semantic_scholar_corpus_id)
        self.openalex_id = normalize_string_field(self.openalex_id)

        super().normalize()

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
        biblio = merged.get("biblio", {})
        references = merged.get("references", {})
        external_ids = merged.get("external_ids", {})

        # Use merged external IDs to populate main fields if not already set
        final_doi = enrichment_result.get("doi") or external_ids.get("doi")
        final_pmid = enrichment_result.get("pmid") or external_ids.get("pmid")

        return cls(
            doi=final_doi,
            pmcid=enrichment_result.get("pmcid"),
            pmid=final_pmid,
            semantic_scholar_id=enrichment_result.get("semantic_scholar_id"),
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
            volume=biblio.get("volume"),
            pages=biblio.get("pages"),
            issue=biblio.get("issue"),
            publisher=biblio.get("publisher"),
            issn=biblio.get("issn"),
            publication_type=biblio.get("type"),
            first_page=biblio.get("first_page"),
            last_page=biblio.get("last_page"),
            external_ids=external_ids,
            external_id_conflicts=merged.get("external_id_conflicts"),
            # Flattened external IDs
            semantic_scholar_corpus_id=external_ids.get("semantic_scholar_corpus_id"),
            openalex_id=external_ids.get("openalex_id"),
            reference_count=references.get("count"),
            cited_by_count=references.get("cited_by_count"),
            related_works=references.get("related_works"),
        )
