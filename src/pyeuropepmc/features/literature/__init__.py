"""Core literature data access for pyEuropePMC.

This slice provides the fundamental data access layer for Europe PMC,
including search, article retrieval, annotations, FTP downloads, and
search query construction and result parsing.
"""

from pyeuropepmc.features.literature.adapters import (
    OpenAlexLiteratureAdapter,
    SemanticScholarLiteratureAdapter,
)
from pyeuropepmc.features.literature.annotations import AnnotationsClient
from pyeuropepmc.features.literature.annotations_to_rdf import (
    annotations_to_entities,
    annotations_to_rdf,
    entity_annotation_to_model,
    relationship_annotation_to_model,
)
from pyeuropepmc.features.literature.article import ArticleClient
from pyeuropepmc.features.literature.filters import (
    filter_pmc_papers,
    filter_pmc_papers_or,
)
from pyeuropepmc.features.literature.ftp_downloader import FTPDownloader
from pyeuropepmc.features.literature.normalization import (
    is_valid_doi,
    normalize_abstract,
    normalize_affiliation,
    normalize_author_list,
    normalize_author_name,
    normalize_doi,
    normalize_journal_title,
    normalize_mesh_terms,
    normalize_paper_title,
    normalize_to_nfkc,
)
from pyeuropepmc.features.literature.pagination import (
    CursorPaginator,
    PaginationCheckpoint,
    PaginationState,
)
from pyeuropepmc.features.literature.query_builder import (
    QueryBuilder,
    QueryBuilderError,
    get_available_fields,
    get_field_info,
    validate_field_coverage,
)
from pyeuropepmc.features.literature.search import EuropePMCError, SearchClient
from pyeuropepmc.features.literature.search_parser import EuropePMCParser

__all__ = [
    "AnnotationsClient",
    "ArticleClient",
    "CursorPaginator",
    "EuropePMCError",
    "EuropePMCParser",
    "FTPDownloader",
    "OpenAlexLiteratureAdapter",
    "PaginationCheckpoint",
    "PaginationState",
    "QueryBuilder",
    "QueryBuilderError",
    "SearchClient",
    "SemanticScholarLiteratureAdapter",
    "annotations_to_entities",
    "annotations_to_rdf",
    "entity_annotation_to_model",
    "filter_pmc_papers",
    "filter_pmc_papers_or",
    "get_available_fields",
    "get_field_info",
    "is_valid_doi",
    "normalize_abstract",
    "normalize_affiliation",
    "normalize_author_list",
    "normalize_author_name",
    "normalize_doi",
    "normalize_journal_title",
    "normalize_mesh_terms",
    "normalize_paper_title",
    "normalize_to_nfkc",
    "relationship_annotation_to_model",
    "validate_field_coverage",
]
