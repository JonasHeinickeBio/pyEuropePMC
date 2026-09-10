"""Core literature data access for pyEuropePMC.

This slice provides the fundamental data access layer for Europe PMC,
including search, article retrieval, annotations, FTP downloads, and
search query construction and result parsing.

Names are imported lazily (PEP 562): importing this package — or any single
submodule such as ``pyeuropepmc.features.literature.normalization`` — does not
pull in pandas, rdflib or BeautifulSoup unless the corresponding feature is
actually used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

_LAZY = {
    "OpenAlexLiteratureAdapter": (
        "pyeuropepmc.features.literature.adapters:OpenAlexLiteratureAdapter"
    ),
    "SemanticScholarLiteratureAdapter": (
        "pyeuropepmc.features.literature.adapters:SemanticScholarLiteratureAdapter"
    ),
    "AnnotationsClient": "pyeuropepmc.features.literature.annotations:AnnotationsClient",
    "annotations_to_entities": (
        "pyeuropepmc.features.literature.annotations_to_rdf:annotations_to_entities"
    ),
    "annotations_to_rdf": "pyeuropepmc.features.literature.annotations_to_rdf:annotations_to_rdf",
    "entity_annotation_to_model": (
        "pyeuropepmc.features.literature.annotations_to_rdf:entity_annotation_to_model"
    ),
    "relationship_annotation_to_model": (
        "pyeuropepmc.features.literature.annotations_to_rdf:relationship_annotation_to_model"
    ),
    "ArticleClient": "pyeuropepmc.features.literature.article:ArticleClient",
    "filter_pmc_papers": "pyeuropepmc.features.literature.filters:filter_pmc_papers",
    "filter_pmc_papers_or": "pyeuropepmc.features.literature.filters:filter_pmc_papers_or",
    "FTPDownloader": "pyeuropepmc.features.literature.ftp_downloader:FTPDownloader",
    "is_valid_doi": "pyeuropepmc.features.literature.normalization:is_valid_doi",
    "normalize_abstract": "pyeuropepmc.features.literature.normalization:normalize_abstract",
    "normalize_affiliation": "pyeuropepmc.features.literature.normalization:normalize_affiliation",
    "normalize_author_list": "pyeuropepmc.features.literature.normalization:normalize_author_list",
    "normalize_author_name": "pyeuropepmc.features.literature.normalization:normalize_author_name",
    "normalize_doi": "pyeuropepmc.features.literature.normalization:normalize_doi",
    "normalize_journal_title": (
        "pyeuropepmc.features.literature.normalization:normalize_journal_title"
    ),
    "normalize_mesh_terms": "pyeuropepmc.features.literature.normalization:normalize_mesh_terms",
    "normalize_paper_title": "pyeuropepmc.features.literature.normalization:normalize_paper_title",
    "normalize_to_nfkc": "pyeuropepmc.features.literature.normalization:normalize_to_nfkc",
    "CursorPaginator": "pyeuropepmc.features.literature.pagination:CursorPaginator",
    "PaginationCheckpoint": "pyeuropepmc.features.literature.pagination:PaginationCheckpoint",
    "PaginationState": "pyeuropepmc.features.literature.pagination:PaginationState",
    "QueryBuilder": "pyeuropepmc.features.literature.query_builder:QueryBuilder",
    "QueryBuilderError": "pyeuropepmc.features.literature.query_builder:QueryBuilderError",
    "get_available_fields": "pyeuropepmc.features.literature.query_builder:get_available_fields",
    "get_field_info": "pyeuropepmc.features.literature.query_builder:get_field_info",
    "validate_field_coverage": (
        "pyeuropepmc.features.literature.query_builder:validate_field_coverage"
    ),
    "EuropePMCError": "pyeuropepmc.features.literature.search:EuropePMCError",
    "SearchClient": "pyeuropepmc.features.literature.search:SearchClient",
    "EuropePMCParser": "pyeuropepmc.features.literature.search_parser:EuropePMCParser",
}

_lazy_getattr, __dir__, __all__ = lazy_module(__name__, _LAZY)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:
    from pyeuropepmc.features.literature.adapters import (
        OpenAlexLiteratureAdapter as OpenAlexLiteratureAdapter,
        SemanticScholarLiteratureAdapter as SemanticScholarLiteratureAdapter,
    )
    from pyeuropepmc.features.literature.annotations import AnnotationsClient as AnnotationsClient
    from pyeuropepmc.features.literature.annotations_to_rdf import (
        annotations_to_entities as annotations_to_entities,
        annotations_to_rdf as annotations_to_rdf,
        entity_annotation_to_model as entity_annotation_to_model,
        relationship_annotation_to_model as relationship_annotation_to_model,
    )
    from pyeuropepmc.features.literature.article import ArticleClient as ArticleClient
    from pyeuropepmc.features.literature.filters import (
        filter_pmc_papers as filter_pmc_papers,
        filter_pmc_papers_or as filter_pmc_papers_or,
    )
    from pyeuropepmc.features.literature.ftp_downloader import FTPDownloader as FTPDownloader
    from pyeuropepmc.features.literature.normalization import (
        is_valid_doi as is_valid_doi,
        normalize_abstract as normalize_abstract,
        normalize_affiliation as normalize_affiliation,
        normalize_author_list as normalize_author_list,
        normalize_author_name as normalize_author_name,
        normalize_doi as normalize_doi,
        normalize_journal_title as normalize_journal_title,
        normalize_mesh_terms as normalize_mesh_terms,
        normalize_paper_title as normalize_paper_title,
        normalize_to_nfkc as normalize_to_nfkc,
    )
    from pyeuropepmc.features.literature.pagination import (
        CursorPaginator as CursorPaginator,
        PaginationCheckpoint as PaginationCheckpoint,
        PaginationState as PaginationState,
    )
    from pyeuropepmc.features.literature.query_builder import (
        QueryBuilder as QueryBuilder,
        QueryBuilderError as QueryBuilderError,
        get_available_fields as get_available_fields,
        get_field_info as get_field_info,
        validate_field_coverage as validate_field_coverage,
    )
    from pyeuropepmc.features.literature.search import (
        EuropePMCError as EuropePMCError,
        SearchClient as SearchClient,
    )
    from pyeuropepmc.features.literature.search_parser import EuropePMCParser as EuropePMCParser
