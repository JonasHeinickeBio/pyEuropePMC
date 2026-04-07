from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
import re
import sys
from typing import Any, ClassVar, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

metamodel_version = "None"
version = "1.0.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_name=True,
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        use_enum_values=True,
        strict=False,
    )

    @model_serializer(mode="wrap", when_used="unless-none")
    def treat_empty_lists_as_none(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        if info.exclude_none:
            _instance = self.model_copy()
            for field, field_info in type(_instance).model_fields.items():
                if getattr(_instance, field) == [] and not (field_info.is_required()):
                    setattr(_instance, field, None)
        else:
            _instance = self
        return handler(_instance, info)


class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key: str):
        return getattr(self.root, key)

    def __getitem__(self, key: str):
        return self.root[key]

    def __setitem__(self, key: str, value):
        self.root[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta(
    {
        "default_prefix": "https://w3id.org/pyeuropepmc/",
        "description": "LinkML schema defining the data model for PyEuropePMC, a "
        "Python toolkit for searching, retrieving, and analyzing "
        "scientific literature from Europe PMC. This schema provides a "
        "single source of truth for generating JSON Schema, RDF/OWL, "
        "SHACL shapes, and Python dataclasses.",
        "id": "https://w3id.org/pyeuropepmc",
        "imports": [
            "base",
            "enums",
            "slots",
            "entities/base",
            "entities/paper",
            "entities/author",
            "entities/organization",
            "entities/journal",
            "entities/grant",
            "entities/section",
            "entities/table",
            "entities/reference",
            "entities/figure",
            "entities/affiliation",
        ],
        "license": "MIT",
        "name": "pyeuropepmc",
        "prefixes": {
            "bibo": {
                "prefix_prefix": "bibo",
                "prefix_reference": "http://purl.org/ontology/bibo/",
            },
            "cito": {"prefix_prefix": "cito", "prefix_reference": "http://purl.org/spar/cito/"},
            "datacite": {
                "prefix_prefix": "datacite",
                "prefix_reference": "http://purl.org/spar/datacite/",
            },
            "dcterms": {
                "prefix_prefix": "dcterms",
                "prefix_reference": "http://purl.org/dc/terms/",
            },
            "foaf": {"prefix_prefix": "foaf", "prefix_reference": "http://xmlns.com/foaf/0.1/"},
            "frapo": {
                "prefix_prefix": "frapo",
                "prefix_reference": "http://purl.org/cerif/frapo/",
            },
            "geo": {
                "prefix_prefix": "geo",
                "prefix_reference": "http://www.w3.org/2003/01/geo/wgs84_pos#",
            },
            "linkml": {"prefix_prefix": "linkml", "prefix_reference": "https://w3id.org/linkml/"},
            "mesh": {"prefix_prefix": "mesh", "prefix_reference": "http://id.nlm.nih.gov/mesh/"},
            "meshv": {
                "prefix_prefix": "meshv",
                "prefix_reference": "http://id.nlm.nih.gov/mesh/vocab#",
            },
            "nif": {
                "prefix_prefix": "nif",
                "prefix_reference": "http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#",
            },
            "obo": {"prefix_prefix": "obo", "prefix_reference": "http://purl.obolibrary.org/obo/"},
            "org": {"prefix_prefix": "org", "prefix_reference": "http://www.w3.org/ns/org#"},
            "owl": {"prefix_prefix": "owl", "prefix_reference": "http://www.w3.org/2002/07/owl#"},
            "prov": {"prefix_prefix": "prov", "prefix_reference": "http://www.w3.org/ns/prov#"},
            "pyeuropepmc": {
                "prefix_prefix": "pyeuropepmc",
                "prefix_reference": "https://w3id.org/pyeuropepmc/vocab#",
            },
            "pyeuropepmcdata": {
                "prefix_prefix": "pyeuropepmcdata",
                "prefix_reference": "https://w3id.org/pyeuropepmc/data#",
            },
            "rdf": {
                "prefix_prefix": "rdf",
                "prefix_reference": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            },
            "rdfs": {
                "prefix_prefix": "rdfs",
                "prefix_reference": "http://www.w3.org/2000/01/rdf-schema#",
            },
            "ror": {"prefix_prefix": "ror", "prefix_reference": "https://ror.org/vocab#"},
            "skos": {
                "prefix_prefix": "skos",
                "prefix_reference": "http://www.w3.org/2004/02/skos/core#",
            },
            "xsd": {
                "prefix_prefix": "xsd",
                "prefix_reference": "http://www.w3.org/2001/XMLSchema#",
            },
        },
        "source_file": "/home/jhe24/AID-PAIS/pyEuropePMC_project/schemas/pyeuropepmc_schema.yaml",
        "title": "PyEuropePMC Data Model Schema",
    }
)


class OpenAccessStatus(str, Enum):
    """
    Open access status of a publication
    """

    open = "open"
    """
    Fully open access
    """
    closed = "closed"
    """
    Not open access
    """
    hybrid = "hybrid"
    """
    Hybrid open access
    """
    green = "green"
    """
    Green open access (preprint/postprint)
    """
    gold = "gold"
    """
    Gold open access
    """
    bronze = "bronze"
    """
    Bronze open access
    """
    unknown = "unknown"
    """
    Unknown open access status
    """


class PublicationType(str, Enum):
    """
    Type of scholarly publication
    """

    journal_article = "journal_article"
    """
    Journal article
    """
    review = "review"
    """
    Review article
    """
    preprint = "preprint"
    """
    Preprint
    """
    book_chapter = "book_chapter"
    """
    Book chapter
    """
    conference_paper = "conference_paper"
    """
    Conference paper
    """
    dataset = "dataset"
    """
    Dataset
    """
    thesis = "thesis"
    """
    Thesis or dissertation
    """
    other = "other"
    """
    Other publication type
    """


class InstitutionType(str, Enum):
    """
    Type of research institution
    """

    education = "education"
    """
    Educational institution
    """
    healthcare = "healthcare"
    """
    Healthcare institution
    """
    company = "company"
    """
    Company or corporation
    """
    government = "government"
    """
    Government organization
    """
    nonprofit = "nonprofit"
    """
    Nonprofit organization
    """
    facility = "facility"
    """
    Research facility
    """
    funder = "funder"
    """
    Funding organization
    """
    other = "other"
    """
    Other institution type
    """


class AuthorPosition(str, Enum):
    """
    Position of author in author list
    """

    first = "first"
    """
    First author
    """
    middle = "middle"
    """
    Middle author
    """
    last = "last"
    """
    Last/corresponding author
    """
    corresponding = "corresponding"
    """
    Corresponding author (may overlap with first/last)
    """


class AuthorRole(str, Enum):
    """
    Specific roles or contributions of authors
    """

    conceptualization = "conceptualization"
    """
    Ideas, formulation of research goals
    """
    methodology = "methodology"
    """
    Development of methodology
    """
    software = "software"
    """
    Programming, software development
    """
    validation = "validation"
    """
    Verification of methods/analyses
    """
    formal_analysis = "formal_analysis"
    """
    Application of statistical techniques
    """
    investigation = "investigation"
    """
    Conducting research, data collection
    """
    resources = "resources"
    """
    Provision of study materials/reagents
    """
    data_curation = "data_curation"
    """
    Management of data activities
    """
    writing_original_draft = "writing_original_draft"
    """
    Preparation of original draft
    """
    writing_review_editing = "writing_review_editing"
    """
    Review and editing of manuscript
    """
    visualization = "visualization"
    """
    Preparation of figures/tables
    """
    supervision = "supervision"
    """
    Oversight and leadership
    """
    project_administration = "project_administration"
    """
    Management and coordination
    """
    funding_acquisition = "funding_acquisition"
    """
    Acquisition of funding
    """


class SectionType(str, Enum):
    """
    Type of document section
    """

    abstract = "abstract"
    """
    Abstract section
    """
    introduction = "introduction"
    """
    Introduction section
    """
    methods = "methods"
    """
    Methods/Materials section
    """
    results = "results"
    """
    Results section
    """
    discussion = "discussion"
    """
    Discussion section
    """
    conclusion = "conclusion"
    """
    Conclusion section
    """
    acknowledgments = "acknowledgments"
    """
    Acknowledgments section
    """
    references = "references"
    """
    References/Bibliography section
    """
    supplementary = "supplementary"
    """
    Supplementary materials
    """
    appendix = "appendix"
    """
    Appendix section
    """
    other = "other"
    """
    Other section type
    """


class CitationType(str, Enum):
    """
    Type of citation relationship
    """

    cites = "cites"
    """
    General citation
    """
    cites_as_evidence = "cites_as_evidence"
    """
    Cites as evidence/support
    """
    cites_as_background = "cites_as_background"
    """
    Cites for background information
    """
    cites_as_related = "cites_as_related"
    """
    Cites related work
    """
    cites_as_method = "cites_as_method"
    """
    Cites methodological work
    """
    cites_for_information = "cites_for_information"
    """
    Cites for specific information
    """
    shares_authors = "shares_authors"
    """
    Shares authors with cited work
    """
    agrees_with = "agrees_with"
    """
    Agrees with cited work
    """
    disagrees_with = "disagrees_with"
    """
    Disagrees with cited work
    """
    cites_as_metadata = "cites_as_metadata"
    """
    Citation in metadata/references section
    """
    cites_as_data = "cites_as_data"
    """
    Cites data source
    """


class BaseEntity(ConfiguredBaseModel):
    """
    Base entity for all data models with RDF serialization support. All entities inherit from this base class, providing common functionality for validation, normalization, and RDF export.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "abstract": True,
            "class_uri": "pyeuropepmc:BaseEntity",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/base",
        }
    )

    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @model_validator(mode="after")
    def set_defaults(self):
        """Set default types and label after initialization."""
        if not self.types:
            if self.__class__.__name__ == "Organization":
                self.types = ["org:Organization"]
            elif self.__class__.__name__ == "Department":
                self.types = ["org:OrganizationalUnit"]
            elif self.__class__.__name__ == "AuthorEntity":
                self.types = ["foaf:Person"]
            elif self.__class__.__name__ == "FigureEntity":
                self.types = ["bibo:Image"]
            elif self.__class__.__name__ == "PaperEntity":
                self.types = ["bibo:AcademicArticle"]
            elif self.__class__.__name__ == "ReferenceEntity":
                self.types = ["bibo:Document"]
            elif self.__class__.__name__ == "SectionEntity":
                self.types = ["bibo:DocumentPart", "nif:Context"]
            elif self.__class__.__name__ == "TableEntity":
                self.types = ["bibo:Table"]
            elif self.__class__.__name__ == "TableRowEntity":
                self.types = ["bibo:Row"]

        if not self.label:
            if hasattr(self, "display_name") and self.display_name:
                self.label = self.display_name
            elif hasattr(self, "full_name") and self.full_name:
                self.label = self.full_name
            elif hasattr(self, "title") and self.title:
                self.label = self.title
            elif hasattr(self, "figure_label") and self.figure_label:
                self.label = self.figure_label
            elif hasattr(self, "table_label") and self.table_label:
                self.label = self.table_label
            elif hasattr(self, "doi") and self.doi:
                self.label = self.doi
            elif hasattr(self, "pmcid") and self.pmcid:
                self.label = self.pmcid
            elif self.__class__.__name__ == "TableRowEntity" and hasattr(self, "cells"):
                self.label = f"Row with {len(self.cells)} cells"
            else:
                # Set default labels for untitled items
                if self.__class__.__name__ == "FigureEntity":
                    self.label = "Untitled Figure"
                elif self.__class__.__name__ == "ReferenceEntity":
                    self.label = "Untitled Reference"
                elif (
                    self.__class__.__name__ == "SectionEntity"
                    and hasattr(self, "title")
                    and not self.title
                ):
                    self.label = "Untitled Section"
                elif self.__class__.__name__ == "TableEntity":
                    self.label = "Untitled Table"

        return self


class ScholarlyWorkEntity(BaseEntity):
    """
    Base entity for scholarly works (papers, references, etc.). Provides common fields and methods for entities representing scholarly publications.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "abstract": True,
            "class_uri": "bibo:Document",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/base",
        }
    )

    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "JournalEntity", "SectionEntity"],
                "slot_uri": "dcterms:title",
            }
        },
    )
    doi: str | None = Field(
        default=None,
        description="""Digital Object Identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:doi"}
        },
    )
    volume: str | None = Field(
        default=None,
        description="""Publication volume""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:volume"}
        },
    )
    pages: str | None = Field(
        default=None,
        description="""Page range (e.g., \"123-456\")""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:pages"}
        },
    )
    publication_year: int | None = Field(
        default=None,
        description="""Publication year (4-digit)""",
        ge=1000,
        le=9999,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "dcterms:issued"}
        },
    )
    publication_date: date | None = Field(
        default=None,
        description="""Full publication date""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "dcterms:date"}
        },
    )
    pmcid: str | None = Field(
        default=None,
        description="""PubMed Central ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "pyeuropepmc:pmcid"}
        },
    )
    pmid: str | None = Field(
        default=None,
        description="""PubMed ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "pyeuropepmc:pmid"}
        },
    )
    semantic_scholar_id: str | None = Field(
        default=None,
        description="""Semantic Scholar paper ID""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:semanticScholarId",
            }
        },
    )
    authors: list[AuthorEntity] | None = Field(
        default=[],
        description="""Authors of a work""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "PaperEntity"],
                "slot_uri": "dcterms:creator",
            }
        },
    )
    journal: JournalEntity | None = Field(
        default=None,
        description="""Journal of a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "PaperEntity"],
                "slot_uri": "bibo:journal",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @field_validator("doi")
    def pattern_doi(cls, v):
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid doi format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid doi format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("pmcid")
    def pattern_pmcid(cls, v):
        pattern = re.compile(r"^PMC\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmcid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmcid format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("pmid")
    def pattern_pmid(cls, v):
        pattern = re.compile(r"^\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmid format: {v}"
            raise ValueError(err_msg)
        return v


class PaperEntity(ScholarlyWorkEntity):
    """
    Entity representing an academic paper with BIBO alignment. Contains bibliographic metadata, citation information, and relationships to authors, institutions, journals, and other entities.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:AcademicArticle",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/paper",
            "rules": [
                {
                    "description": "PaperEntity must have at least one of: pmcid, doi, or title",
                    "postconditions": {
                        "slot_conditions": {
                            "title": {"name": "title", "value_presence": "PRESENT"}
                        }
                    },
                    "preconditions": {
                        "slot_conditions": {
                            "doi": {"name": "doi", "value_presence": "ABSENT"},
                            "pmcid": {"name": "pmcid", "value_presence": "ABSENT"},
                        }
                    },
                }
            ],
            "slot_usage": {
                "doi": {"name": "doi", "required": False},
                "pmcid": {"name": "pmcid", "required": False},
                "quality_score": {
                    "description": "Overall quality score for "
                    "paper data completeness and "
                    "accuracy",
                    "maximum_value": 1.0,
                    "minimum_value": 0.0,
                    "name": "quality_score",
                    "range": "float",
                    "required": False,
                },
                "title": {"name": "title", "required": False},
            },
        }
    )

    issue: str | None = Field(
        default=None,
        description="""Journal issue number""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:issue"}
        },
    )
    pub_date: date | None = Field(
        default=None,
        description="""Publication date (legacy field)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:issued"}
        },
    )
    keywords: list[str] | None = Field(
        default=[],
        description="""List of keywords""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:subject"}
        },
    )
    abstract: str | None = Field(
        default=None,
        description="""Article abstract""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:abstract"}
        },
    )
    affiliation_text: str | None = Field(
        default=None,
        description="""Affiliation text""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "AffiliationEntity"],
                "slot_uri": "pyeuropepmc:affiliationText",
            }
        },
    )
    citation_count: int | None = Field(
        default=None,
        description="""Total citation count""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:citationCount",
            }
        },
    )
    influential_citation_count: int | None = Field(
        default=None,
        description="""Influential citation count""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:influentialCitationCount",
            }
        },
    )
    is_oa: bool | None = Field(
        default=None,
        description="""Open access status flag""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:accessRights"}
        },
    )
    oa_status: OpenAccessStatus | None = Field(
        default=None,
        description="""Open access status details""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:accessRights"}
        },
    )
    oa_url: str | None = Field(
        default=None,
        description="""Open access URL""",
        json_schema_extra={"linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:uri"}},
    )
    reference_count: int | None = Field(
        default=None,
        description="""Number of references cited""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:referenceCount"}
        },
    )
    cited_by_count: int | None = Field(
        default=None,
        description="""Number of papers citing this work""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:citationCount"}
        },
    )
    publisher: str | None = Field(
        default=None,
        description="""Publisher name""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "JournalEntity"],
                "slot_uri": "dcterms:publisher",
            }
        },
    )
    issn: str | None = Field(
        default=None,
        description="""ISSN identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity", "JournalEntity"], "slot_uri": "bibo:issn"}
        },
    )
    publication_type: PublicationType | None = Field(
        default=None,
        description="""Type of publication""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:DocumentType"}
        },
    )
    first_page: str | None = Field(
        default=None,
        description="""First page number""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:pageStart"}
        },
    )
    last_page: str | None = Field(
        default=None,
        description="""Last page number""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:pageEnd"}
        },
    )
    semantic_scholar_corpus_id: str | None = Field(
        default=None,
        description="""Semantic Scholar corpus ID""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:semanticScholarCorpusId",
            }
        },
    )
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "Organization", "JournalEntity"],
                "slot_uri": "pyeuropepmc:openAlexId",
            }
        },
    )
    license_url: str | None = Field(
        default=None,
        description="""License URL""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:license"}
        },
    )
    license_text: str | None = Field(
        default=None,
        description="""License description text""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:rights"}
        },
    )
    fields_of_study: list[str] | None = Field(
        default=[],
        description="""Fields of study""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:subject"}
        },
    )
    related_works: list[str] | None = Field(
        default=[],
        description="""Related work IDs""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:related"}
        },
    )
    pub_types: list[str] | None = Field(
        default=[],
        description="""List of publication types from Europe PMC""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:DocumentType"}
        },
    )
    mesh_terms: list[str] | None = Field(
        default=[],
        description="""MeSH terms associated with the paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "meshv:hasDescriptor"}
        },
    )
    topics: list[str] | None = Field(
        default=[],
        description="""Research topics from OpenAlex""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:subject"}
        },
    )
    has_pdf: bool | None = Field(
        default=None,
        description="""Whether the paper has a PDF available""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:hasPdf"}
        },
    )
    has_supplementary: bool | None = Field(
        default=None,
        description="""Whether the paper has supplementary materials""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:hasSupplementary",
            }
        },
    )
    in_epmc: bool | None = Field(
        default=None,
        description="""Whether the paper is in Europe PMC""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:inEpmc"}
        },
    )
    in_pmc: bool | None = Field(
        default=None,
        description="""Whether the paper is in PubMed Central""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:inPmc"}
        },
    )
    journal_issn: str | None = Field(
        default=None,
        description="""Journal ISSN identifier""",
        json_schema_extra={"linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:issn"}},
    )
    page_info: str | None = Field(
        default=None,
        description="""Page information string""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:pages"}
        },
    )
    has_references: bool | None = Field(
        default=None,
        description="""Whether the paper has references""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:hasReferences"}
        },
    )
    has_text_mined_terms: bool | None = Field(
        default=None,
        description="""Whether the paper has text-mined terms""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:hasTextMinedTerms",
            }
        },
    )
    has_db_cross_references: bool | None = Field(
        default=None,
        description="""Whether the paper has database cross-references""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:hasDbCrossReferences",
            }
        },
    )
    has_labs_links: bool | None = Field(
        default=None,
        description="""Whether the paper has labs links""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:hasLabsLinks"}
        },
    )
    has_tm_accession_numbers: bool | None = Field(
        default=None,
        description="""Whether the paper has text-mined accession numbers""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:hasTmAccessionNumbers",
            }
        },
    )
    first_index_date: date | None = Field(
        default=None,
        description="""First index date""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:firstIndexDate"}
        },
    )
    first_publication_date: date | None = Field(
        default=None,
        description="""First publication date""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:firstPublicationDate",
            }
        },
    )
    external_id_conflicts: str | None = Field(
        default=None,
        description="""Conflicts in external identifiers""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:externalIdConflicts",
            }
        },
    )
    pii: str | None = Field(
        default=None,
        description="""Publisher Item Identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:pii"}
        },
    )
    publisher_id: str | None = Field(
        default=None,
        description="""Publisher identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "JournalEntity"],
                "slot_uri": "pyeuropepmc:publisherId",
            }
        },
    )
    license: str | None = Field(
        default=None,
        description="""License information""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:license"}
        },
    )
    authors: list[AuthorEntity] | None = Field(
        default=[],
        description="""Authors of a work""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "PaperEntity"],
                "slot_uri": "dcterms:creator",
            }
        },
    )
    paper_institutions: list[Organization] | None = Field(
        default=[],
        description="""Institutions affiliated with a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:affiliatedWith"}
        },
    )
    affiliations: list[AffiliationEntity] | None = Field(
        default=[],
        description="""Author affiliations with institutions""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:hasAffiliation",
            }
        },
    )
    journal: JournalEntity | None = Field(
        default=None,
        description="""Journal of a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "PaperEntity"],
                "slot_uri": "bibo:journal",
            }
        },
    )
    sections: list[SectionEntity] | None = Field(
        default=[],
        description="""Sections of a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:hasPart"}
        },
    )
    references: list[ReferenceEntity] | None = Field(
        default=[],
        description="""References cited by a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "cito:cites"}
        },
    )
    tables: list[TableEntity] | None = Field(
        default=[],
        description="""Tables in a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:hasPart"}
        },
    )
    figures: list[FigureEntity] | None = Field(
        default=[],
        description="""Figures in a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:hasPart"}
        },
    )
    grants: list[GrantEntity] | None = Field(
        default=[],
        description="""Grants funding a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "foaf:fundedBy"}
        },
    )
    quality_score: float | None = Field(
        default=None,
        description="""Overall quality score for paper data completeness and accuracy""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:qualityScore",
            }
        },
    )
    s2_paper_id: str | None = Field(
        default=None,
        description="""Semantic Scholar paper ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:s2PaperId"}
        },
    )
    corpus_id: str | None = Field(
        default=None,
        description="""Semantic Scholar corpus ID (alternative field)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:corpusId"}
        },
    )
    s2_fields_of_study: list[str] | None = Field(
        default=[],
        description="""Semantic Scholar fields of study""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:subject"}
        },
    )
    publication_types: list[str] | None = Field(
        default=[],
        description="""Publication types from Semantic Scholar""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:DocumentType"}
        },
    )
    tldr: str | None = Field(
        default=None,
        description="""TLDR summary from Semantic Scholar""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "dcterms:abstract"}
        },
    )
    open_access_pdf_url: str | None = Field(
        default=None,
        description="""Open access PDF URL""",
        json_schema_extra={"linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:uri"}},
    )
    referenced_works_count: int | None = Field(
        default=None,
        description="""Number of referenced works""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:referencedWorksCount",
            }
        },
    )
    references_count: int | None = Field(
        default=None,
        description="""Number of references""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "slot_uri": "pyeuropepmc:referencesCount",
            }
        },
    )
    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "JournalEntity", "SectionEntity"],
                "slot_uri": "dcterms:title",
            }
        },
    )
    doi: str | None = Field(
        default=None,
        description="""Digital Object Identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:doi"}
        },
    )
    volume: str | None = Field(
        default=None,
        description="""Publication volume""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:volume"}
        },
    )
    pages: str | None = Field(
        default=None,
        description="""Page range (e.g., \"123-456\")""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:pages"}
        },
    )
    publication_year: int | None = Field(
        default=None,
        description="""Publication year (4-digit)""",
        ge=1000,
        le=9999,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "dcterms:issued"}
        },
    )
    publication_date: date | None = Field(
        default=None,
        description="""Full publication date""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "dcterms:date"}
        },
    )
    pmcid: str | None = Field(
        default=None,
        description="""PubMed Central ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "pyeuropepmc:pmcid"}
        },
    )
    pmid: str | None = Field(
        default=None,
        description="""PubMed ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "pyeuropepmc:pmid"}
        },
    )
    semantic_scholar_id: str | None = Field(
        default=None,
        description="""Semantic Scholar paper ID""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:semanticScholarId",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @field_validator("issn")
    def pattern_issn(cls, v):
        pattern = re.compile(r"^\d{4}-\d{3}[\dX]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid issn format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid issn format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("journal_issn")
    def pattern_journal_issn(cls, v):
        pattern = re.compile(r"^\d{4}-\d{3}[\dX]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid journal_issn format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid journal_issn format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("doi")
    def pattern_doi(cls, v):
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid doi format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid doi format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("pmcid")
    def pattern_pmcid(cls, v):
        pattern = re.compile(r"^PMC\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmcid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmcid format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("pmid")
    def pattern_pmid(cls, v):
        pattern = re.compile(r"^\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmid format: {v}"
            raise ValueError(err_msg)
        return v


class AuthorEntity(BaseEntity):
    """
    Entity representing an author with FOAF alignment. Contains personal information, institutional affiliations, and identifiers.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "foaf:Person",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/author",
            "slot_usage": {
                "full_name": {"name": "full_name", "required": True},
                "quality_score": {
                    "description": "Confidence score for author data completeness and accuracy",
                    "maximum_value": 1.0,
                    "minimum_value": 0.0,
                    "name": "quality_score",
                    "range": "float",
                    "required": False,
                },
                "roles": {
                    "description": "Specific roles or contributions of the author",
                    "multivalued": True,
                    "name": "roles",
                    "range": "AuthorRole",
                    "required": False,
                },
            },
        }
    )

    full_name: str = Field(
        default=...,
        description="""Full name of the author""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:name"}
        },
    )
    first_name: str | None = Field(
        default=None,
        description="""First/given name of the author""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:givenName"}
        },
    )
    last_name: str | None = Field(
        default=None,
        description="""Last/family name of the author""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:familyName"}
        },
    )
    initials: str | None = Field(
        default=None,
        description="""Author's initials""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:initials"}
        },
    )
    affiliation_text: str | None = Field(
        default=None,
        description="""Affiliation text""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "AffiliationEntity"],
                "slot_uri": "pyeuropepmc:affiliationText",
            }
        },
    )
    orcid: str | None = Field(
        default=None,
        description="""ORCID identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "datacite:orcid"}
        },
    )
    name: str | None = Field(
        default=None,
        description="""Display name (for enrichment compatibility)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:name"}
        },
    )
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "Organization", "JournalEntity"],
                "slot_uri": "pyeuropepmc:openAlexId",
            }
        },
    )
    semantic_scholar_id: str | None = Field(
        default=None,
        description="""Semantic Scholar paper ID""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:semanticScholarId",
            }
        },
    )
    semantic_scholar_author_id: str | None = Field(
        default=None,
        description="""Semantic Scholar author ID (alternative field)""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity"],
                "slot_uri": "pyeuropepmc:semanticScholarAuthorId",
            }
        },
    )
    scopus_author_id: str | None = Field(
        default=None,
        description="""Scopus author ID""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity"],
                "slot_uri": "pyeuropepmc:scopusAuthorId",
            }
        },
    )
    researcher_id: str | None = Field(
        default=None,
        description="""ResearcherID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "pyeuropepmc:researcherId"}
        },
    )
    position: AuthorPosition | None = Field(
        default=None,
        description="""Author position/role""",
        json_schema_extra={"linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "org:role"}},
    )
    sources: list[str] | None = Field(
        default=[],
        description="""Data sources for author information""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    email: str | None = Field(
        default=None,
        description="""Email address""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:mbox"}
        },
    )
    papers: list[PaperEntity] | None = Field(
        default=[],
        description="""Papers authored by an author""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "foaf:made"}
        },
    )
    author_institutions: list[Organization] | None = Field(
        default=[],
        description="""Institutions affiliated with an author""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity"],
                "slot_uri": "pyeuropepmc:affiliatedWith",
            }
        },
    )
    affiliations: list[AffiliationEntity] | None = Field(
        default=[],
        description="""Author affiliations with institutions""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:hasAffiliation",
            }
        },
    )
    institutions: list[Organization] | None = Field(
        default=[],
        description="""Institutional affiliations as InstitutionEntity objects""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "org:memberOf"}
        },
    )
    h_index: int | None = Field(
        default=None,
        description="""Journal h-index""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity", "JournalEntity"],
                "slot_uri": "pyeuropepmc:hIndex",
            }
        },
    )
    citation_count: int | None = Field(
        default=None,
        description="""Total citation count""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:citationCount",
            }
        },
    )
    orcid_works_count: int | None = Field(
        default=None,
        description="""Number of works associated with ORCID""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity"],
                "slot_uri": "pyeuropepmc:orcidWorksCount",
            }
        },
    )
    paper_count: int | None = Field(
        default=None,
        description="""Total number of papers by author""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "pyeuropepmc:paperCount"}
        },
    )
    roles: list[AuthorRole] | None = Field(
        default=[],
        description="""Specific roles or contributions of the author""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AuthorEntity"], "slot_uri": "pyeuropepmc:authorRoles"}
        },
    )
    quality_score: float | None = Field(
        default=None,
        description="""Confidence score for author data completeness and accuracy""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:qualityScore",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @field_validator("orcid")
    def pattern_orcid(cls, v):
        pattern = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid orcid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid orcid format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("email")
    def pattern_email(cls, v):
        pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid email format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid email format: {v}"
            raise ValueError(err_msg)
        return v


class Organization(BaseEntity):
    """
    Entity representing an organization with ROR alignment. Contains organizational metadata and geographic information.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "org:Organization",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/organization",
            "slot_usage": {"display_name": {"name": "display_name", "required": True}},
        }
    )

    display_name: str = Field(
        default=...,
        description="""Display name of the institution""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "skos:prefLabel",
            }
        },
    )
    ror_id: str | None = Field(
        default=None,
        description="""ROR (Research Organization Registry) identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization"], "slot_uri": "pyeuropepmc:rorId"}
        },
    )
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "Organization", "JournalEntity"],
                "slot_uri": "pyeuropepmc:openAlexId",
            }
        },
    )
    country: str | None = Field(
        default=None,
        description="""Country name""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department", "JournalEntity"],
                "slot_uri": "geo:country",
            }
        },
    )
    country_code: str | None = Field(
        default=None,
        description="""ISO country code""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "geo:countryCode",
            }
        },
    )
    city: str | None = Field(
        default=None,
        description="""City name""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "geo:city"}
        },
    )
    latitude: Decimal | None = Field(
        default=None,
        description="""Geographic latitude""",
        ge=-90.0,
        le=90.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "geo:lat"}
        },
    )
    longitude: Decimal | None = Field(
        default=None,
        description="""Geographic longitude""",
        ge=-180.0,
        le=180.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "geo:long"}
        },
    )
    institution_type: InstitutionType | None = Field(
        default=None,
        description="""Type of institution""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization"], "slot_uri": "org:classification"}
        },
    )
    grid_id: str | None = Field(
        default=None,
        description="""GRID identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "pyeuropepmc:gridId",
            }
        },
    )
    isni: str | None = Field(
        default=None,
        description="""ISNI identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "pyeuropepmc:isni",
            }
        },
    )
    wikidata_id: str | None = Field(
        default=None,
        description="""Wikidata identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department", "JournalEntity"],
                "slot_uri": "owl:sameAs",
            }
        },
    )
    fundref_id: str | None = Field(
        default=None,
        description="""FundRef identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization"], "slot_uri": "pyeuropepmc:fundrefId"}
        },
    )
    website: str | None = Field(
        default=None,
        description="""Institution website URL""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "foaf:homepage",
            }
        },
    )
    established: int | None = Field(
        default=None,
        description="""Year established""",
        ge=1000,
        le=9999,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "dcterms:created",
            }
        },
    )
    domains: list[str] | None = Field(
        default=[],
        description="""Institution domains""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "dcterms:subject",
            }
        },
    )
    relationships: list[str] | None = Field(
        default=[],
        description="""Related institutions""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "org:relationship",
            }
        },
    )
    institution_members: list[AuthorEntity] | None = Field(
        default=[],
        description="""Members of an institution""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization"], "slot_uri": "org:hasMember"}
        },
    )
    status: str | None = Field(
        default=None,
        description="""Institution status""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "pyeuropepmc:status",
            }
        },
    )
    names: list[str] | None = Field(
        default=[],
        description="""Alternative institution names""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "skos:altLabel",
            }
        },
    )
    locations: list[str] | None = Field(
        default=[],
        description="""Institution locations""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "org:siteAddress",
            }
        },
    )
    links: list[str] | None = Field(
        default=[],
        description="""Institution links""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "foaf:page"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class Department(BaseEntity):
    """
    Entity representing a department or sub-organization within an organization. Contains organizational metadata and geographic information.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "org:OrganizationalUnit",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/organization",
            "slot_usage": {
                "display_name": {"name": "display_name", "required": True},
                "parent_organization": {
                    "name": "parent_organization",
                    "range": "Organization",
                    "required": True,
                },
            },
        }
    )

    display_name: str = Field(
        default=...,
        description="""Display name of the institution""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "skos:prefLabel",
            }
        },
    )
    parent_organization: Organization = Field(
        default=...,
        description="""URI of the parent organization this unit belongs to""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Department"], "slot_uri": "org:memberOf"}
        },
    )
    country: str | None = Field(
        default=None,
        description="""Country name""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department", "JournalEntity"],
                "slot_uri": "geo:country",
            }
        },
    )
    country_code: str | None = Field(
        default=None,
        description="""ISO country code""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "geo:countryCode",
            }
        },
    )
    city: str | None = Field(
        default=None,
        description="""City name""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "geo:city"}
        },
    )
    latitude: Decimal | None = Field(
        default=None,
        description="""Geographic latitude""",
        ge=-90.0,
        le=90.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "geo:lat"}
        },
    )
    longitude: Decimal | None = Field(
        default=None,
        description="""Geographic longitude""",
        ge=-180.0,
        le=180.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "geo:long"}
        },
    )
    department_type: str | None = Field(
        default=None,
        description="""Type of department""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Department"], "slot_uri": "org:classification"}
        },
    )
    grid_id: str | None = Field(
        default=None,
        description="""GRID identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "pyeuropepmc:gridId",
            }
        },
    )
    isni: str | None = Field(
        default=None,
        description="""ISNI identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "pyeuropepmc:isni",
            }
        },
    )
    wikidata_id: str | None = Field(
        default=None,
        description="""Wikidata identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department", "JournalEntity"],
                "slot_uri": "owl:sameAs",
            }
        },
    )
    website: str | None = Field(
        default=None,
        description="""Institution website URL""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "foaf:homepage",
            }
        },
    )
    established: int | None = Field(
        default=None,
        description="""Year established""",
        ge=1000,
        le=9999,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "dcterms:created",
            }
        },
    )
    domains: list[str] | None = Field(
        default=[],
        description="""Institution domains""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "dcterms:subject",
            }
        },
    )
    relationships: list[str] | None = Field(
        default=[],
        description="""Related institutions""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "org:relationship",
            }
        },
    )
    status: str | None = Field(
        default=None,
        description="""Institution status""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "pyeuropepmc:status",
            }
        },
    )
    names: list[str] | None = Field(
        default=[],
        description="""Alternative institution names""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "skos:altLabel",
            }
        },
    )
    locations: list[str] | None = Field(
        default=[],
        description="""Institution locations""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department"],
                "slot_uri": "org:siteAddress",
            }
        },
    )
    links: list[str] | None = Field(
        default=[],
        description="""Institution links""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["Organization", "Department"], "slot_uri": "foaf:page"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class JournalEntity(BaseEntity):
    """
    Entity representing an academic journal with BIBO alignment. Contains journal metadata and bibliometric information.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:Journal",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/journal",
            "slot_usage": {"title": {"name": "title", "required": True}},
        }
    )

    title: str = Field(
        default=...,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "JournalEntity", "SectionEntity"],
                "slot_uri": "dcterms:title",
            }
        },
    )
    medline_abbreviation: str | None = Field(
        default=None,
        description="""Medline abbreviation""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:shortTitle"}
        },
    )
    iso_abbreviation: str | None = Field(
        default=None,
        description="""ISO abbreviation""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:shortTitle"}
        },
    )
    nlmid: str | None = Field(
        default=None,
        description="""NLM ID (National Library of Medicine identifier)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:nlmid"}
        },
    )
    issn: str | None = Field(
        default=None,
        description="""ISSN identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity", "JournalEntity"], "slot_uri": "bibo:issn"}
        },
    )
    essn: str | None = Field(
        default=None,
        description="""Electronic ISSN""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:eissn"}
        },
    )
    publisher: str | None = Field(
        default=None,
        description="""Publisher name""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "JournalEntity"],
                "slot_uri": "dcterms:publisher",
            }
        },
    )
    country: str | None = Field(
        default=None,
        description="""Country name""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department", "JournalEntity"],
                "slot_uri": "geo:country",
            }
        },
    )
    language: str | None = Field(
        default=None,
        description="""Primary language of publication""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "dcterms:language"}
        },
    )
    journal_issue_id: str | None = Field(
        default=None,
        description="""Europe PMC journal issue identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:issue"}
        },
    )
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "Organization", "JournalEntity"],
                "slot_uri": "pyeuropepmc:openAlexId",
            }
        },
    )
    wikidata_id: str | None = Field(
        default=None,
        description="""Wikidata identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["Organization", "Department", "JournalEntity"],
                "slot_uri": "owl:sameAs",
            }
        },
    )
    scopus_source_id: str | None = Field(
        default=None,
        description="""Scopus source identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["JournalEntity"],
                "slot_uri": "pyeuropepmc:scopusSourceId",
            }
        },
    )
    subject_areas: list[str] | None = Field(
        default=[],
        description="""Subject areas/categories""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "dcterms:subject"}
        },
    )
    impact_factor: Decimal | None = Field(
        default=None,
        description="""Journal impact factor""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "pyeuropepmc:impactFactor"}
        },
    )
    sjr: Decimal | None = Field(
        default=None,
        description="""SCImago Journal Rank""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "pyeuropepmc:sjr"}
        },
    )
    h_index: int | None = Field(
        default=None,
        description="""Journal h-index""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity", "JournalEntity"],
                "slot_uri": "pyeuropepmc:hIndex",
            }
        },
    )
    nlm_ta: str | None = Field(
        default=None,
        description="""NLM Title Abbreviation""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:nlmTA"}
        },
    )
    iso_abbrev: str | None = Field(
        default=None,
        description="""ISO abbreviation (alternative field)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:isoAbbrev"}
        },
    )
    publisher_id: str | None = Field(
        default=None,
        description="""Publisher identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "JournalEntity"],
                "slot_uri": "pyeuropepmc:publisherId",
            }
        },
    )
    journal_ids: str | None = Field(
        default=None,
        description="""All journal identifiers by type""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "pyeuropepmc:journalIds"}
        },
    )
    journal_papers: list[PaperEntity] | None = Field(
        default=[],
        description="""Papers published in a journal""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:article"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @field_validator("issn")
    def pattern_issn(cls, v):
        pattern = re.compile(r"^\d{4}-\d{3}[\dX]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid issn format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid issn format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("essn")
    def pattern_essn(cls, v):
        pattern = re.compile(r"^\d{4}-\d{3}[\dX]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid essn format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid essn format: {v}"
            raise ValueError(err_msg)
        return v


class GrantEntity(BaseEntity):
    """
    Entity representing a research grant or funding award with FRAPO alignment. Contains funding information and relationships to recipients.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "frapo:Grant", "from_schema": "https://w3id.org/pyeuropepmc/entities/grant"}
    )

    fundref_doi: str | None = Field(
        default=None,
        description="""FundRef DOI for the funding organization""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "datacite:doi"}
        },
    )
    funding_source: str | None = Field(
        default=None,
        description="""Name of the funding organization/source""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasFundingAgency"}
        },
    )
    award_id: str | None = Field(
        default=None,
        description="""Grant or award identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "datacite:identifier"}
        },
    )
    grant_id: str | None = Field(
        default=None,
        description="""Grant identifier from funding agency""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasGrantNumber"}
        },
    )
    agency: str | None = Field(
        default=None,
        description="""Funding agency name""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasFundingAgency"}
        },
    )
    order_in: int | None = Field(
        default=None,
        description="""Order/position of grant in the list""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "pyeuropepmc:orderIn"}
        },
    )
    recipient: str | None = Field(
        default=None,
        description="""DEPRECATED: Use recipients instead. Grant recipient name.""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasRecipient"}
        },
    )
    recipients: list[AuthorEntity] | None = Field(
        default=[],
        description="""Recipients of a grant""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasRecipient"}
        },
    )
    funded_papers: list[PaperEntity] | None = Field(
        default=[],
        description="""Papers funded by a grant""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:funds"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @field_validator("fundref_doi")
    def pattern_fundref_doi(cls, v):
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid fundref_doi format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid fundref_doi format: {v}"
            raise ValueError(err_msg)
        return v


class SectionEntity(BaseEntity):
    """
    Entity representing a document section with BIBO and NIF alignment. Contains section content and NIF text offsets for alignment.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:DocumentPart",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/section",
            "rules": [
                {
                    "description": "begin_index must be less than end_index",
                    "postconditions": {
                        "slot_conditions": {
                            "begin_index": {"maximum_value": 999999999, "name": "begin_index"},
                            "end_index": {"minimum_value": 0, "name": "end_index"},
                        }
                    },
                    "preconditions": {
                        "slot_conditions": {
                            "begin_index": {"name": "begin_index", "value_presence": "PRESENT"},
                            "end_index": {"name": "end_index", "value_presence": "PRESENT"},
                        }
                    },
                }
            ],
            "slot_usage": {
                "citation_contexts": {
                    "description": "Detailed citation contexts within this section",
                    "multivalued": True,
                    "name": "citation_contexts",
                    "range": "CitationContextEntity",
                    "required": False,
                },
                "content": {"name": "content", "required": True},
                "section_type": {
                    "description": "Type/category of the section",
                    "name": "section_type",
                    "range": "SectionType",
                    "required": False,
                },
            },
        }
    )

    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "JournalEntity", "SectionEntity"],
                "slot_uri": "dcterms:title",
            }
        },
    )
    content: str = Field(
        default=...,
        description="""Section text content""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "nif:isString"}
        },
    )
    begin_index: int | None = Field(
        default=None,
        description="""NIF begin offset for text alignment""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity", "CitationContextEntity"],
                "slot_uri": "nif:beginIndex",
            }
        },
    )
    end_index: int | None = Field(
        default=None,
        description="""NIF end offset for text alignment""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity", "CitationContextEntity"],
                "slot_uri": "nif:endIndex",
            }
        },
    )
    section_paper: PaperEntity | None = Field(
        default=None,
        description="""Paper containing a section""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "dcterms:isPartOf"}
        },
    )
    subsections: list[SectionEntity] | None = Field(
        default=[],
        description="""Subsections of a section""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "dcterms:hasPart"}
        },
    )
    parent_section: SectionEntity | None = Field(
        default=None,
        description="""Parent section of a subsection""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "dcterms:isPartOf"}
        },
    )
    citations: list[CitationContextEntity] | None = Field(
        default=[],
        description="""Citations within a section""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "cito:cites"}
        },
    )
    section_type: SectionType | None = Field(
        default=None,
        description="""Type/category of the section""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "dcterms:type"}
        },
    )
    order: int | None = Field(
        default=None,
        description="""Document order of the section (1-based)""",
        ge=1,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "pyeuropepmc:sectionOrder"}
        },
    )
    citation_contexts: list[CitationContextEntity] | None = Field(
        default=[],
        description="""Detailed citation contexts within this section""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity"],
                "slot_uri": "pyeuropepmc:citationContext",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class CitationContextEntity(BaseEntity):
    """
    Entity representing the context of a citation within a section. Contains citation type, position, and surrounding text.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "cito:Citation",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/section",
            "slot_usage": {
                "begin_index": {"minimum_value": 0, "name": "begin_index", "required": True},
                "citation_type": {
                    "name": "citation_type",
                    "range": "CitationType",
                    "required": True,
                },
                "confidence_score": {
                    "description": "Confidence score for citation type classification",
                    "maximum_value": 1.0,
                    "minimum_value": 0.0,
                    "name": "confidence_score",
                    "range": "float",
                    "required": False,
                },
                "context_text": {
                    "description": "Surrounding text context of the citation",
                    "name": "context_text",
                    "required": False,
                },
                "end_index": {"minimum_value": 0, "name": "end_index", "required": True},
            },
        }
    )

    citation_type: CitationType = Field(
        default=...,
        description="""Type of citation relationship""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["CitationContextEntity"],
                "slot_uri": "cito:citationType",
            }
        },
    )
    begin_index: int = Field(
        default=...,
        description="""NIF begin offset for text alignment""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity", "CitationContextEntity"],
                "slot_uri": "nif:beginIndex",
            }
        },
    )
    end_index: int = Field(
        default=...,
        description="""NIF end offset for text alignment""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity", "CitationContextEntity"],
                "slot_uri": "nif:endIndex",
            }
        },
    )
    context_text: str | None = Field(
        default=None,
        description="""Surrounding text context of the citation""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["CitationContextEntity"],
                "slot_uri": "pyeuropepmc:contextText",
            }
        },
    )
    cited_paper: PaperEntity | None = Field(
        default=None,
        description="""Paper being cited""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["CitationContextEntity"], "slot_uri": "cito:isCitedBy"}
        },
    )
    citing_section: SectionEntity | None = Field(
        default=None,
        description="""Section containing the citation""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["CitationContextEntity"], "slot_uri": "cito:cites"}
        },
    )
    confidence_score: float | None = Field(
        default=None,
        description="""Confidence score for citation type classification""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["CitationContextEntity"],
                "slot_uri": "pyeuropepmc:confidenceScore",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class TableEntity(BaseEntity):
    """
    Entity representing a table with BIBO alignment. Contains table metadata and structured row data.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "bibo:Table", "from_schema": "https://w3id.org/pyeuropepmc/entities/table"}
    )

    caption: str | None = Field(
        default=None,
        description="""Caption or description""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["TableEntity", "FigureEntity"],
                "slot_uri": "dcterms:description",
            }
        },
    )
    table_label: str | None = Field(
        default=None,
        description="""Table label (e.g., \"Table 1\")""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableEntity"], "slot_uri": "rdfs:label"}
        },
    )
    headers: list[str] | None = Field(
        default=[],
        description="""Column headers for the table""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableEntity"], "slot_uri": "rdfs:label"}
        },
    )
    rows: list[TableRowEntity] | None = Field(
        default=[],
        description="""Rows in a table""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableEntity"], "slot_uri": "dcterms:hasPart"}
        },
    )
    table_paper: PaperEntity | None = Field(
        default=None,
        description="""Paper containing a table""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableEntity"], "slot_uri": "dcterms:isPartOf"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class TableRowEntity(BaseEntity):
    """
    Entity representing a table row.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:Row",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/table",
            "slot_usage": {"cells": {"minimum_cardinality": 1, "name": "cells", "required": True}},
        }
    )

    cells: list[str] = Field(
        default=...,
        description="""Cell values for a table row""",
        min_length=1,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableRowEntity"], "slot_uri": "rdfs:member"}
        },
    )
    row_table: TableEntity | None = Field(
        default=None,
        description="""Table containing a row""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableRowEntity"], "slot_uri": "dcterms:isPartOf"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class ReferenceEntity(ScholarlyWorkEntity):
    """
    Entity representing a bibliographic reference with BIBO alignment. Contains citation information for works referenced by papers.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:Article",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/reference",
        }
    )

    author_list: str | None = Field(
        default=None,
        description="""Author list (comma-separated)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ReferenceEntity"], "slot_uri": "bibo:authorList"}
        },
    )
    raw_citation: str | None = Field(
        default=None,
        description="""Raw citation text when parsing fails""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ReferenceEntity"], "slot_uri": "dcterms:description"}
        },
    )
    citing_paper: PaperEntity | None = Field(
        default=None,
        description="""Paper that cites this reference""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ReferenceEntity"], "slot_uri": "cito:isCitedBy"}
        },
    )
    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "JournalEntity", "SectionEntity"],
                "slot_uri": "dcterms:title",
            }
        },
    )
    doi: str | None = Field(
        default=None,
        description="""Digital Object Identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:doi"}
        },
    )
    volume: str | None = Field(
        default=None,
        description="""Publication volume""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:volume"}
        },
    )
    pages: str | None = Field(
        default=None,
        description="""Page range (e.g., \"123-456\")""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "bibo:pages"}
        },
    )
    publication_year: int | None = Field(
        default=None,
        description="""Publication year (4-digit)""",
        ge=1000,
        le=9999,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "dcterms:issued"}
        },
    )
    publication_date: date | None = Field(
        default=None,
        description="""Full publication date""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "dcterms:date"}
        },
    )
    pmcid: str | None = Field(
        default=None,
        description="""PubMed Central ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "pyeuropepmc:pmcid"}
        },
    )
    pmid: str | None = Field(
        default=None,
        description="""PubMed ID""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ScholarlyWorkEntity"], "slot_uri": "pyeuropepmc:pmid"}
        },
    )
    semantic_scholar_id: str | None = Field(
        default=None,
        description="""Semantic Scholar paper ID""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "AuthorEntity"],
                "slot_uri": "pyeuropepmc:semanticScholarId",
            }
        },
    )
    authors: list[AuthorEntity] | None = Field(
        default=[],
        description="""Authors of a work""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "PaperEntity"],
                "slot_uri": "dcterms:creator",
            }
        },
    )
    journal: JournalEntity | None = Field(
        default=None,
        description="""Journal of a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "PaperEntity"],
                "slot_uri": "bibo:journal",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )

    @field_validator("doi")
    def pattern_doi(cls, v):
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid doi format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid doi format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("pmcid")
    def pattern_pmcid(cls, v):
        pattern = re.compile(r"^PMC\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmcid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmcid format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator("pmid")
    def pattern_pmid(cls, v):
        pattern = re.compile(r"^\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmid format: {v}"
            raise ValueError(err_msg)
        return v


class FigureEntity(BaseEntity):
    """
    Entity representing a figure with BIBO alignment. Contains figure metadata and graphic URI.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "bibo:Image", "from_schema": "https://w3id.org/pyeuropepmc/entities/figure"}
    )

    caption: str | None = Field(
        default=None,
        description="""Caption or description""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["TableEntity", "FigureEntity"],
                "slot_uri": "dcterms:description",
            }
        },
    )
    figure_label: str | None = Field(
        default=None,
        description="""Figure label (e.g., \"Figure 1\")""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["FigureEntity"], "slot_uri": "rdfs:label"}
        },
    )
    graphic_uri: str | None = Field(
        default=None,
        description="""URI to the figure graphic/image file""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["FigureEntity"], "slot_uri": "foaf:depiction"}
        },
    )
    figure_paper: FigureEntity | None = Field(
        default=None,
        description="""Paper containing a figure""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["FigureEntity"], "slot_uri": "dcterms:isPartOf"}
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


class AffiliationEntity(BaseEntity):
    """
    Entity representing an author's affiliation with an institution. Contains the relationship between authors and institutions with affiliation text.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "org:Membership",
            "from_schema": "https://w3id.org/pyeuropepmc/entities/affiliation",
        }
    )

    affiliation_text: str | None = Field(
        default=None,
        description="""Affiliation text""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "AffiliationEntity"],
                "slot_uri": "pyeuropepmc:affiliationText",
            }
        },
    )
    affiliated_author: AuthorEntity | None = Field(
        default=None,
        description="""Author affiliated with this institution""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AffiliationEntity"],
                "slot_uri": "pyeuropepmc:hasAffiliation",
            }
        },
    )
    affiliated_institution: Organization | None = Field(
        default=None,
        description="""Institution the author is affiliated with""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["AffiliationEntity"], "slot_uri": "org:memberOf"}
        },
    )
    affiliation_order: int | None = Field(
        default=None,
        description="""Order of affiliation in author's list""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AffiliationEntity"],
                "slot_uri": "pyeuropepmc:affiliationOrder",
            }
        },
    )
    id: str | None = Field(
        default=None,
        description="""Local identifier (slug/uuid) for the entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:identifier"}
        },
    )
    label: str | None = Field(
        default=None,
        description="""Human-readable label for the entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdfs:label"}},
    )
    source_uri: str | None = Field(
        default=None,
        description="""Source URI for provenance tracking""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    confidence: float | None = Field(
        default=None,
        description="""Confidence score for extracted information (0.0 to 1.0)""",
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "pyeuropepmc:confidence"}
        },
    )
    types: list[str] | None = Field(
        default=[],
        description="""RDF types (CURIEs/URIs) for this entity""",
        json_schema_extra={"linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "rdf:type"}},
    )
    data_sources: list[str] | None = Field(
        default=[],
        description="""List of data sources that contributed to this entity""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "prov:hadPrimarySource"}
        },
    )
    last_updated: datetime | None = Field(
        default=None,
        description="""Timestamp of last data update (ISO 8601)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["BaseEntity"], "slot_uri": "dcterms:modified"}
        },
    )


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
BaseEntity.model_rebuild()
ScholarlyWorkEntity.model_rebuild()
PaperEntity.model_rebuild()
AuthorEntity.model_rebuild()
Organization.model_rebuild()
Department.model_rebuild()
JournalEntity.model_rebuild()
GrantEntity.model_rebuild()
SectionEntity.model_rebuild()
CitationContextEntity.model_rebuild()
TableEntity.model_rebuild()
TableRowEntity.model_rebuild()
ReferenceEntity.model_rebuild()
FigureEntity.model_rebuild()
AffiliationEntity.model_rebuild()


# Custom methods for Organization class
def _add_organization_custom_methods():
    """Add custom methods to Organization class."""
    from typing import Any

    @classmethod
    def from_enrichment_dict(cls, inst_dict: dict[str, Any]) -> Organization:
        """
        Create an Organization from enrichment institution dictionary.

        Parameters
        ----------
        inst_dict : dict
            Institution dictionary from enrichment result

        Returns
        -------
        Organization
            Organization entity with enrichment data
        """
        # Handle relationships - extract labels from dicts
        relationships_data = inst_dict.get("relationships", [])
        if relationships_data and isinstance(relationships_data[0], dict):
            relationships_list = [r.get("label", "") for r in relationships_data]
        else:
            relationships_list = relationships_data

        # Extract individual identifiers from external_ids
        grid_id = None
        isni = None
        wikidata_id = None
        fundref_id = None

        external_ids = inst_dict.get("external_ids", [])
        if external_ids:
            for ext_id in external_ids:
                if isinstance(ext_id, dict):
                    id_type = ext_id.get("type")
                    id_value = ext_id.get("preferred") or (
                        ext_id.get("all", [None])[0] if ext_id.get("all") else None
                    )

                    if id_type == "grid" and id_value:
                        grid_id = id_value
                    elif id_type == "isni" and id_value:
                        isni = id_value
                    elif id_type == "wikidata" and id_value:
                        wikidata_id = id_value
                    elif id_type == "fundref" and id_value:
                        fundref_id = id_value

        return cls(
            display_name=inst_dict.get("display_name", ""),
            ror_id=inst_dict.get("ror_id"),
            openalex_id=inst_dict.get("openalex_id") or inst_dict.get("id"),
            country=inst_dict.get("country"),
            country_code=inst_dict.get("country_code"),
            city=inst_dict.get("city"),
            latitude=inst_dict.get("latitude"),
            longitude=inst_dict.get("longitude"),
            institution_type=inst_dict.get("type"),
            grid_id=grid_id,
            isni=isni,
            wikidata_id=wikidata_id,
            fundref_id=fundref_id,
            website=inst_dict.get("website"),
            established=inst_dict.get("established"),
            domains=inst_dict.get("domains", []),
            relationships=relationships_list,
            # Additional ROR fields
            status=inst_dict.get("status"),
            types=inst_dict.get("types", []),
            names=inst_dict.get("names", []),
            locations=inst_dict.get("locations", []),
            links=inst_dict.get("links", []),
        )

    # Add the method to the Organization class
    Organization.from_enrichment_dict = from_enrichment_dict


_add_organization_custom_methods()


# Custom methods for BaseEntity class
def _add_base_entity_custom_methods():
    """Add custom methods to BaseEntity class."""
    from typing import Any, Dict
    from urllib.parse import quote
    import uuid

    def mint_uri(self, prefix: str) -> str:
        """
        Mint a URI for this entity.

        Parameters
        ----------
        prefix : str
            URI prefix/path

        Returns
        -------
        str
            The minted URI
        """
        if self.id:
            return f"http://example.org/data/{quote(prefix)}/{quote(self.id)}"
        else:
            # Generate UUID if no ID
            entity_id = str(uuid.uuid4())
            return f"http://example.org/data/{quote(prefix)}/{quote(entity_id)}"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert entity to dictionary representation.

        Returns
        -------
        Dict[str, Any]
            Dictionary representation of the entity
        """
        return self.model_dump()

    def validate(self) -> None:
        """
        Validate the entity.

        Raises
        ------
        ValueError
            If validation fails
        """
        # Basic validation - can be overridden by subclasses
        pass

    def normalize(self) -> None:
        """
        Normalize the entity (trim whitespace, etc.).

        This is a base implementation that can be overridden.
        """
        # Base implementation - subclasses should override
        pass

    # Add methods to BaseEntity
    BaseEntity.mint_uri = mint_uri
    BaseEntity.to_dict = to_dict
    BaseEntity.validate = validate
    BaseEntity.normalize = normalize

    # Import and assign the to_rdf method
    from .rdf_methods import to_rdf

    BaseEntity.to_rdf = to_rdf


_add_base_entity_custom_methods()


# Custom methods for other entities
def _add_entity_custom_methods():
    """Add custom methods to other entity classes."""

    # AuthorEntity normalize
    def author_normalize(self) -> None:
        """Normalize AuthorEntity by trimming whitespace."""
        if self.full_name:
            self.full_name = self.full_name.strip()
        if self.first_name:
            self.first_name = self.first_name.strip()
        if self.last_name:
            self.last_name = self.last_name.strip()
        if self.affiliation_text:
            self.affiliation_text = self.affiliation_text.strip()

    def author_validate(self) -> None:
        """Validate AuthorEntity."""
        if not self.full_name or not self.full_name.strip():
            raise ValueError("AuthorEntity must have either full_name or name")

    # FigureEntity normalize
    def figure_normalize(self) -> None:
        """Normalize FigureEntity by trimming whitespace."""
        if self.caption:
            self.caption = self.caption.strip()
        if self.figure_label:
            self.figure_label = self.figure_label.strip()
        if self.graphic_uri:
            self.graphic_uri = self.graphic_uri.strip()

    # PaperEntity normalize
    def paper_normalize(self) -> None:
        """Normalize PaperEntity by trimming whitespace."""
        if self.title:
            self.title = self.title.strip()
        if self.doi:
            self.doi = self.doi.strip().lower()
        if self.pmcid:
            self.pmcid = self.pmcid.strip().upper()

    def paper_validate(self) -> None:
        """Validate PaperEntity."""
        if not any([self.pmcid, self.doi, self.title]):
            raise ValueError(
                "PaperEntity must have at least one identifier (pmcid, doi, or title)"
            )

    # ReferenceEntity normalize
    def reference_normalize(self) -> None:
        """Normalize ReferenceEntity by trimming whitespace."""
        if self.title:
            self.title = self.title.strip()
        if self.doi:
            self.doi = self.doi.strip().lower()
        if self.journal:
            self.journal = self.journal.strip()
        if self.authors and isinstance(self.authors, str):
            self.authors = self.authors.strip()

    # SectionEntity normalize
    def section_normalize(self) -> None:
        """Normalize SectionEntity by trimming whitespace."""
        if self.title:
            self.title = self.title.strip()
        if self.content:
            self.content = self.content.strip()

    def section_validate(self) -> None:
        """Validate SectionEntity."""
        if not self.content or not self.content.strip():
            raise ValueError("SectionEntity must have content")

    # TableEntity normalize
    def table_normalize(self) -> None:
        """Normalize TableEntity by trimming whitespace."""
        if self.table_label:
            self.table_label = self.table_label.strip()
        if self.caption:
            self.caption = self.caption.strip()
        if self.headers:
            self.headers = [h.strip() if h else h for h in self.headers]

    def table_validate(self) -> None:
        """Validate TableEntity."""
        if self.rows:
            row_lengths = [len(row.cells) for row in self.rows if row.cells]
            if self.headers and len(self.headers) != row_lengths[0] if row_lengths else 0:
                raise ValueError("TableEntity headers must match number of columns in rows")
            if len(set(row_lengths)) > 1:
                raise ValueError("TableEntity must have the same number of columns in all rows")

    # TableRowEntity normalize
    def table_row_normalize(self) -> None:
        """Normalize TableRowEntity by trimming whitespace."""
        if self.cells:
            self.cells = [cell.strip() if cell else cell for cell in self.cells]

    def table_row_validate(self) -> None:
        """Validate TableRowEntity."""
        if not self.cells:
            raise ValueError("TableRowEntity must have cells")

    # Organization normalize
    def organization_normalize(self) -> None:
        """Normalize Organization by trimming whitespace."""
        if self.display_name:
            self.display_name = self.display_name.strip()
        if self.ror_id:
            self.ror_id = self.ror_id.strip()
        if self.city:
            self.city = self.city.strip()

    def organization_validate(self) -> None:
        """Validate Organization."""
        if not self.display_name or not self.display_name.strip():
            raise ValueError("Organization must have display_name")

    # Department normalize
    def department_normalize(self) -> None:
        """Normalize Department by trimming whitespace."""
        if self.display_name:
            self.display_name = self.display_name.strip()

    def department_validate(self) -> None:
        """Validate Department."""
        if not self.display_name or not self.display_name.strip():
            raise ValueError("Department must have display_name")

    # Add post-init methods to set types and labels
    # Add methods to classes (without post_init since we use validator now)
    AuthorEntity.normalize = author_normalize
    AuthorEntity.validate = author_validate

    FigureEntity.normalize = figure_normalize

    PaperEntity.normalize = paper_normalize
    PaperEntity.validate = paper_validate

    ReferenceEntity.normalize = reference_normalize

    SectionEntity.normalize = section_normalize
    SectionEntity.validate = section_validate

    TableEntity.normalize = table_normalize
    TableEntity.validate = table_validate

    TableRowEntity.normalize = table_row_normalize
    TableRowEntity.validate = table_row_validate

    Organization.normalize = organization_normalize
    Organization.validate = organization_validate

    Department.normalize = department_normalize
    Department.validate = department_validate


_add_entity_custom_methods()
