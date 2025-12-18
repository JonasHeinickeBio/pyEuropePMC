from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import re
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
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
        "default_prefix": "pyeuropepmc",
        "default_range": "string",
        "description": "LinkML schema defining the data model for PyEuropePMC, a "
        "Python toolkit for searching, retrieving, and analyzing "
        "scientific literature from Europe PMC. This schema provides a "
        "single source of truth for generating JSON Schema, RDF/OWL, "
        "SHACL shapes, and Python dataclasses.",
        "id": "https://w3id.org/pyeuropepmc",
        "imports": ["linkml:types"],
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
        "source_file": "schemas/pyeuropepmc_schema.yaml",
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


class BaseEntity(ConfiguredBaseModel):
    """
    Base entity for all data models with RDF serialization support. All entities inherit from this
        base class, providing common functionality for validation, normalization, and RDF export.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "abstract": True,
            "class_uri": "pyeuropepmc:BaseEntity",
            "from_schema": "https://w3id.org/pyeuropepmc",
        }
    )

    id: str = Field(
        default=...,
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


class ScholarlyWorkEntity(BaseEntity):
    """
    Base entity for scholarly works (papers, references, etc.). Provides common fields and methods
        for entities representing scholarly publications.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "abstract": True,
            "class_uri": "bibo:Document",
            "from_schema": "https://w3id.org/pyeuropepmc",
        }
    )

    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "SectionEntity", "JournalEntity"],
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
    id: str = Field(
        default=...,
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
    @classmethod
    def pattern_doi(cls, v: Any) -> Any:
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$")
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
    @classmethod
    def pattern_pmcid(cls, v: Any) -> Any:
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
    @classmethod
    def pattern_pmid(cls, v: Any) -> Any:
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
    Entity representing an academic paper with BIBO alignment. Contains bibliographic metadata,
    citation information, and relationships to authors, institutions, journals, and other entities.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:AcademicArticle",
            "from_schema": "https://w3id.org/pyeuropepmc",
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
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "bibo:numPages"}
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
                "domain_of": ["PaperEntity", "AuthorEntity", "InstitutionEntity", "JournalEntity"],
                "slot_uri": "datacite:openalex",
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
    authors: list[str] | None = Field(
        default=[],
        description="""Authors of a work""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "papers",
                "slot_uri": "dcterms:creator",
            }
        },
    )
    paper_institutions: list[str] | None = Field(
        default=[],
        description="""Institutions affiliated with a paper""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["PaperEntity"], "slot_uri": "pyeuropepmc:affiliatedWith"}
        },
    )
    journal: str | None = Field(
        default=None,
        description="""Journal a paper is published in""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "journal_papers",
                "slot_uri": "bibo:journal",
            }
        },
    )
    sections: list[str] | None = Field(
        default=[],
        description="""Sections of a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "section_paper",
                "slot_uri": "dcterms:hasPart",
            }
        },
    )
    references: list[str] | None = Field(
        default=[],
        description="""References cited by a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "citing_paper",
                "slot_uri": "cito:cites",
            }
        },
    )
    tables: list[str] | None = Field(
        default=[],
        description="""Tables in a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "table_paper",
                "slot_uri": "dcterms:hasPart",
            }
        },
    )
    figures: list[str] | None = Field(
        default=[],
        description="""Figures in a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "figure_paper",
                "slot_uri": "dcterms:hasPart",
            }
        },
    )
    grants: list[str] | None = Field(
        default=[],
        description="""Grants funding a paper""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity"],
                "inverse": "funded_papers",
                "slot_uri": "foaf:fundedBy",
            }
        },
    )
    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "SectionEntity", "JournalEntity"],
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
    id: str = Field(
        default=...,
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
    @classmethod
    def pattern_issn(cls, v: Any) -> Any:
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

    @field_validator("doi")
    @classmethod
    def pattern_doi(cls, v: Any) -> Any:
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$")
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
    @classmethod
    def pattern_pmcid(cls, v: Any) -> Any:
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
    @classmethod
    def pattern_pmid(cls, v: Any) -> Any:
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
    Entity representing an author with FOAF alignment. Contains personal information, institutional
        affiliations, and identifiers.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "foaf:Person",
            "from_schema": "https://w3id.org/pyeuropepmc",
            "slot_usage": {"full_name": {"name": "full_name", "required": True}},
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
                "domain_of": ["AuthorEntity"],
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
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "InstitutionEntity", "JournalEntity"],
                "slot_uri": "datacite:openalex",
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
    papers: list[str] | None = Field(
        default=[],
        description="""Papers authored by a person""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity"],
                "inverse": "authors",
                "slot_uri": "foaf:made",
            }
        },
    )
    author_institutions: list[str] | None = Field(
        default=[],
        description="""Institutions an author is affiliated with""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["AuthorEntity"],
                "inverse": "members",
                "slot_uri": "pyeuropepmc:affiliatedWith",
            }
        },
    )
    h_index: int | None = Field(
        default=None,
        description="""H-index""",
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
    id: str = Field(
        default=...,
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
    @classmethod
    def pattern_orcid(cls, v: Any) -> Any:
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
    @classmethod
    def pattern_email(cls, v: Any) -> Any:
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


class SectionEntity(BaseEntity):
    """
    Entity representing a document section with BIBO and NIF alignment. Contains section content
        and NIF text offsets for alignment.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:DocumentPart",
            "from_schema": "https://w3id.org/pyeuropepmc",
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
            "slot_usage": {"content": {"name": "content", "required": True}},
        }
    )

    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "SectionEntity", "JournalEntity"],
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
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "nif:beginIndex"}
        },
    )
    end_index: int | None = Field(
        default=None,
        description="""NIF end offset for text alignment""",
        ge=0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["SectionEntity"], "slot_uri": "nif:endIndex"}
        },
    )
    section_paper: str | None = Field(
        default=None,
        description="""Paper this section belongs to""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity"],
                "inverse": "sections",
                "slot_uri": "dcterms:isPartOf",
            }
        },
    )
    subsections: list[str] | None = Field(
        default=[],
        description="""Child sections of a section""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity"],
                "inverse": "parent_section",
                "slot_uri": "dcterms:hasPart",
            }
        },
    )
    parent_section: str | None = Field(
        default=None,
        description="""Parent section""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["SectionEntity"],
                "inverse": "subsections",
                "slot_uri": "dcterms:isPartOf",
            }
        },
    )
    id: str = Field(
        default=...,
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
    Entity representing a table with BIBO alignment. Contains table metadata and structured row
        data.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "bibo:Table", "from_schema": "https://w3id.org/pyeuropepmc"}
    )

    caption: str | None = Field(
        default=None,
        description="""Caption/description""",
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
        description="""Column headers for a table""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["TableEntity"], "slot_uri": "rdfs:label"}
        },
    )
    rows: list[str] | None = Field(
        default=[],
        description="""Rows in a table""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["TableEntity"],
                "inverse": "table",
                "slot_uri": "dcterms:hasPart",
            }
        },
    )
    table_paper: str | None = Field(
        default=None,
        description="""Paper this table belongs to""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["TableEntity"],
                "inverse": "tables",
                "slot_uri": "dcterms:isPartOf",
            }
        },
    )
    id: str = Field(
        default=...,
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
            "from_schema": "https://w3id.org/pyeuropepmc",
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
    table: str | None = Field(
        default=None,
        description="""Table this row belongs to""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["TableRowEntity"],
                "inverse": "rows",
                "slot_uri": "dcterms:isPartOf",
            }
        },
    )
    id: str = Field(
        default=...,
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
    Entity representing a bibliographic reference with BIBO alignment. Contains citation
        information for works referenced by papers.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "bibo:Article", "from_schema": "https://w3id.org/pyeuropepmc"}
    )

    raw_citation: str | None = Field(
        default=None,
        description="""Raw citation text when parsing fails""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["ReferenceEntity"], "slot_uri": "dcterms:description"}
        },
    )
    citing_paper: str | None = Field(
        default=None,
        description="""Paper that cites this reference""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ReferenceEntity"],
                "inverse": "references",
                "slot_uri": "cito:isCitedBy",
            }
        },
    )
    title: str | None = Field(
        default=None,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "SectionEntity", "JournalEntity"],
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
    id: str = Field(
        default=...,
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
    @classmethod
    def pattern_doi(cls, v: Any) -> Any:
        pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$")
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
    @classmethod
    def pattern_pmcid(cls, v: Any) -> Any:
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
    @classmethod
    def pattern_pmid(cls, v: Any) -> Any:
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


class InstitutionEntity(BaseEntity):
    """
    Entity representing an institution with ROR alignment. Contains organizational metadata and
        geographic information.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "org:Organization",
            "from_schema": "https://w3id.org/pyeuropepmc",
            "slot_usage": {"display_name": {"name": "display_name", "required": True}},
        }
    )

    display_name: str = Field(
        default=...,
        description="""Display name of the institution""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "skos:prefLabel"}
        },
    )
    ror_id: str | None = Field(
        default=None,
        description="""ROR identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "pyeuropepmc:rorId"}
        },
    )
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "InstitutionEntity", "JournalEntity"],
                "slot_uri": "datacite:openalex",
            }
        },
    )
    country: str | None = Field(
        default=None,
        description="""Country name""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["InstitutionEntity", "JournalEntity"],
                "slot_uri": "geo:country",
            }
        },
    )
    country_code: str | None = Field(
        default=None,
        description="""ISO country code""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "geo:countryCode"}
        },
    )
    city: str | None = Field(
        default=None,
        description="""City name""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "geo:city"}
        },
    )
    latitude: Decimal | None = Field(
        default=None,
        description="""Geographic latitude""",
        ge=-90.0,
        le=90.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "geo:lat"}
        },
    )
    longitude: Decimal | None = Field(
        default=None,
        description="""Geographic longitude""",
        ge=-180.0,
        le=180.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "geo:long"}
        },
    )
    institution_type: InstitutionType | None = Field(
        default=None,
        description="""Type of institution""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "org:classification"}
        },
    )
    grid_id: str | None = Field(
        default=None,
        description="""GRID identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "pyeuropepmc:gridId"}
        },
    )
    isni: str | None = Field(
        default=None,
        description="""ISNI identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "pyeuropepmc:isni"}
        },
    )
    wikidata_id: str | None = Field(
        default=None,
        description="""Wikidata identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["InstitutionEntity", "JournalEntity"],
                "slot_uri": "owl:sameAs",
            }
        },
    )
    fundref_id: str | None = Field(
        default=None,
        description="""FundRef identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["InstitutionEntity"],
                "slot_uri": "pyeuropepmc:fundrefId",
            }
        },
    )
    website: str | None = Field(
        default=None,
        description="""Institution website URL""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "foaf:homepage"}
        },
    )
    established: int | None = Field(
        default=None,
        description="""Year established""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "dcterms:created"}
        },
    )
    domains: list[str] | None = Field(
        default=[],
        description="""Associated domain names""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["InstitutionEntity"], "slot_uri": "dcterms:subject"}
        },
    )
    members: list[str] | None = Field(
        default=[],
        description="""Members of an institution""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["InstitutionEntity"],
                "inverse": "author_institutions",
                "slot_uri": "org:hasMember",
            }
        },
    )
    id: str = Field(
        default=...,
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

    @field_validator("country_code")
    @classmethod
    def pattern_country_code(cls, v: Any) -> Any:
        pattern = re.compile(r"^[A-Z]{2}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid country_code format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid country_code format: {v}"
            raise ValueError(err_msg)
        return v


class JournalEntity(BaseEntity):
    """
    Entity representing an academic journal with BIBO alignment. Contains journal metadata and
        bibliometric information.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {
            "class_uri": "bibo:Journal",
            "from_schema": "https://w3id.org/pyeuropepmc",
            "slot_usage": {"title": {"name": "title", "required": True}},
        }
    )

    title: str = Field(
        default=...,
        description="""Work or entity title""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["ScholarlyWorkEntity", "SectionEntity", "JournalEntity"],
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
        description="""NLM ID""",
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
                "domain_of": ["InstitutionEntity", "JournalEntity"],
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
    journal_issue_id: int | None = Field(
        default=None,
        description="""Journal issue identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:issue"}
        },
    )
    openalex_id: str | None = Field(
        default=None,
        description="""OpenAlex identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["PaperEntity", "AuthorEntity", "InstitutionEntity", "JournalEntity"],
                "slot_uri": "datacite:openalex",
            }
        },
    )
    wikidata_id: str | None = Field(
        default=None,
        description="""Wikidata identifier""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["InstitutionEntity", "JournalEntity"],
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
        ge=0.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "pyeuropepmc:impactFactor"}
        },
    )
    sjr: Decimal | None = Field(
        default=None,
        description="""SCImago Journal Rank""",
        ge=0.0,
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "pyeuropepmc:sjr"}
        },
    )
    h_index: int | None = Field(
        default=None,
        description="""H-index""",
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
        description="""ISO abbreviation (alternative)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "bibo:isoAbbrev"}
        },
    )
    publisher_id: str | None = Field(
        default=None,
        description="""Publisher-specific identifier""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["JournalEntity"], "slot_uri": "pyeuropepmc:publisherId"}
        },
    )
    journal_papers: list[str] | None = Field(
        default=[],
        description="""Papers published in this journal""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["JournalEntity"],
                "inverse": "journal",
                "slot_uri": "bibo:article",
            }
        },
    )
    id: str = Field(
        default=...,
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
    @classmethod
    def pattern_issn(cls, v: Any) -> Any:
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
    @classmethod
    def pattern_essn(cls, v: Any) -> Any:
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
    Entity representing a research grant or funding award with FRAPO alignment. Contains funding
        information and relationships to recipients.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "frapo:Grant", "from_schema": "https://w3id.org/pyeuropepmc"}
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
        description="""Name of the funding organization""",
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
    recipient: str | None = Field(
        default=None,
        description="""Grant recipient (deprecated, use recipients relationship)""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasRecipient"}
        },
    )
    recipients: list[str] | None = Field(
        default=[],
        description="""Principal investigators/recipients of a grant""",
        json_schema_extra={
            "linkml_meta": {"domain_of": ["GrantEntity"], "slot_uri": "frapo:hasRecipient"}
        },
    )
    funded_papers: list[str] | None = Field(
        default=[],
        description="""Papers funded by a grant""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["GrantEntity"],
                "inverse": "grants",
                "slot_uri": "frapo:funds",
            }
        },
    )
    id: str = Field(
        default=...,
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


class FigureEntity(BaseEntity):
    """
    Entity representing a figure with BIBO alignment. Contains figure metadata and graphic URI.
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"class_uri": "bibo:Image", "from_schema": "https://w3id.org/pyeuropepmc"}
    )

    caption: str | None = Field(
        default=None,
        description="""Caption/description""",
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
    figure_paper: str | None = Field(
        default=None,
        description="""Paper this figure belongs to""",
        json_schema_extra={
            "linkml_meta": {
                "domain_of": ["FigureEntity"],
                "inverse": "figures",
                "slot_uri": "dcterms:isPartOf",
            }
        },
    )
    id: str = Field(
        default=...,
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
SectionEntity.model_rebuild()
TableEntity.model_rebuild()
TableRowEntity.model_rebuild()
ReferenceEntity.model_rebuild()
InstitutionEntity.model_rebuild()
JournalEntity.model_rebuild()
GrantEntity.model_rebuild()
FigureEntity.model_rebuild()
