"""
Paper entity model for representing academic articles.
"""

from dataclasses import dataclass, field
from typing import Any

from pyeuropepmc.models.grant import GrantEntity
from pyeuropepmc.models.journal import JournalEntity
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
    affiliation_text : Optional[str]
        Affiliation text
    citation_count : Optional[int]
        Total citation count from all sources
    influential_citation_count : Optional[int]
        Influential citation count
    topics : Optional[list[dict]]
        Research topics from OpenAlex
    fields_of_study : Optional[list[str]]
        Fields of study from Semantic Scholar
    grants : Optional[list[GrantEntity]]
        Grant/funding information as GrantEntity objects
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
    journal : Optional[JournalEntity]
        Journal entity containing journal metadata
    publisher : Optional[str]
        Publisher name (legacy field, use journal.publisher instead)
    issn : Optional[str]
        ISSN identifier (legacy field, use journal.issn instead)
    publication_type : Optional[str]
        Type of publication
    pub_types : list[str]
        List of publication types from Europe PMC
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
    mesh_terms: list[str | Any] = field(
        default_factory=list
    )  # MeSH terms (str or MeSHHeadingEntity)
    abstract: str | None = None
    affiliation_text: str | None = None
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
    pub_types: list[str] = field(default_factory=list)
    journal_issn: str | None = None
    page_info: str | None = None
    first_page: str | None = None
    last_page: str | None = None
    journal: JournalEntity | None = None
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
    grants: list["GrantEntity"] | None = None
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

        # Validate journal entity if present
        if self.journal and hasattr(self.journal, "validate"):
            self.journal.validate()

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

        # Normalize pub types
        self.pub_types = self._normalize_pub_types(self.pub_types)

        # Normalize journal entity if present
        if self.journal:
            if isinstance(self.journal, str):
                self.journal = normalize_string_field(self.journal)
            else:
                self.journal.normalize()

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
            grants=merged.get("funders"),
            is_oa=merged.get("is_oa"),
            oa_status=merged.get("oa_status"),
            oa_url=merged.get("oa_url"),
            license=merged.get("license"),
            publication_year=merged.get("publication_year"),
            publication_date=merged.get("publication_date"),
            journal=JournalEntity.from_enrichment_dict(
                {
                    "title": merged.get("journal"),
                    "issn": biblio.get("issn"),
                    "publisher": biblio.get("publisher"),
                }
            )
            if merged.get("journal") or biblio.get("issn") or biblio.get("publisher")
            else None,
            volume=biblio.get("volume"),
            pages=biblio.get("pages"),
            issue=biblio.get("issue"),
            publisher=biblio.get("publisher"),  # Keep for backward compatibility
            issn=biblio.get("issn"),  # Keep for backward compatibility
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

    @staticmethod
    def _normalize_pub_types(pub_types: list[str] | None) -> list[str]:
        """
        Normalize publication types to canonical terms.

        Parameters
        ----------
        pub_types : list[str] or None
            Raw publication types from Europe PMC

        Returns
        -------
        list[str]
            Normalized publication types
        """
        if not pub_types:
            return []

        # Mapping of raw terms to canonical terms
        normalization_map = {
            "review-article": "Review Article",
            "research-article": "Research Article",
            "journal-article": "Journal Article",
            "letter": "Letter",
            "editorial": "Editorial",
            "news": "News",
            "commentary": "Commentary",
            "book-review": "Book Review",
            "conference-paper": "Conference Paper",
            "preprint": "Preprint",
            "dataset": "Dataset",
            "software": "Software",
            "other": "Other",
        }

        normalized = []
        for pub_type in pub_types:
            if isinstance(pub_type, str):
                # Convert to lowercase for matching, then apply mapping
                key = pub_type.lower().replace(" ", "-")
                canonical = normalization_map.get(key, pub_type.strip().title())
                normalized.append(canonical)
            else:
                normalized.append(str(pub_type).strip().title())

        return normalized

    @classmethod
    def from_search_result(cls, search_result: dict[str, Any]) -> "PaperEntity":
        """
        Create a PaperEntity from Europe PMC search result.

        Parameters
        ----------
        search_result : dict
            Search result dictionary from Europe PMC API

        Returns
        -------
        PaperEntity
            Paper entity with search result data
        """
        # Extract pub types
        pub_type_list = search_result.get("pubTypeList", {}).get("pubType", [])
        if isinstance(pub_type_list, str):
            pub_type_list = [pub_type_list]
        elif not isinstance(pub_type_list, list):
            pub_type_list = []

        normalized_pub_types = cls._normalize_pub_types(pub_type_list)

        # Extract journal info
        journal_info = search_result.get("journalInfo", {})
        journal = None
        if journal_info:
            journal_title = journal_info.get("journal", {}).get("title")
            if journal_title:
                journal = JournalEntity(
                    title=journal_title,
                    issn=journal_info.get("journal", {}).get("issn"),
                    publisher=journal_info.get("publisher"),
                )

        # Extract author info (simplified)
        author_list = search_result.get("authorList", {}).get("author", [])
        authors = []
        if isinstance(author_list, list):
            from pyeuropepmc.models.author import AuthorEntity

            for author_data in author_list:
                if isinstance(author_data, dict):
                    author = AuthorEntity(
                        full_name=author_data.get("fullName"),
                        first_name=author_data.get("firstName"),
                        last_name=author_data.get("lastName"),
                        orcid=author_data.get("orcid"),
                    )
                    authors.append(author)

        return cls(
            pmcid=search_result.get("pmcid"),
            doi=search_result.get("doi"),
            pmid=search_result.get("pmid"),
            title=search_result.get("title"),
            abstract=search_result.get("abstractText"),
            authors=authors,
            journal=journal,
            pub_types=normalized_pub_types,
            publication_year=search_result.get("pubYear"),
            publication_date=search_result.get("firstPublicationDate"),
            volume=journal_info.get("volume"),
            issue=journal_info.get("issue"),
            page_info=search_result.get("pageInfo"),
            has_pdf=search_result.get("hasPDF") == "Y",
            has_supplementary=search_result.get("hasSupplements") == "Y",
            in_epmc=search_result.get("inEPMC") == "Y",
            in_pmc=search_result.get("inPMC") == "Y",
            cited_by_count=search_result.get("citedByCount"),
            is_oa=search_result.get("isOpenAccess") == "Y",
            oa_status=search_result.get("openAccess"),
            license=search_result.get("license"),
        )
