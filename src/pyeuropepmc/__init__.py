"""
PyEuropePMC - Python toolkit for Europe PMC API

A comprehensive Python library for searching and retrieving scientific literature
from Europe PMC with robust error handling, pagination, and multiple output formats.

Example usage:
    >>> import pyeuropepmc
    >>> client = pyeuropepmc.SearchClient()
    >>> results = client.search("CRISPR gene editing", pageSize=10)
    >>> papers = client.search_and_parse("COVID-19", format="json")

Import cost
-----------
``import pyeuropepmc`` only pulls in a light core (requests, the cache layer,
exceptions).  Everything else — search/enrichment clients, analytics, RDF
mapping, the agentic/LLM stack, the Flask web UI — is imported lazily on first
attribute access (PEP 562), so optional dependencies are never required just to
``import pyeuropepmc``.  Install what you need with extras, e.g.
``pip install pyeuropepmc[analytics,agentic]``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

# --- Eager: cheap, universally used, no heavy third-party imports -------------
from pyeuropepmc.cache.cache import (
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
    normalize_query_params,
)
from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.exceptions import (
    APIClientError,
    ClientError,
    EuropePMCError,
    FileError,
    FullTextError,
    ModelError,
    UnpaywallError,
)

__version__ = "2.1.2"
__author__ = "Jonas Heinicke"
__email__ = "jonas.heinicke@helmholtz-hzi.de"
__url__ = "https://github.com/JonasHeinickeBio/pyEuropePMC"

logger = logging.getLogger(__name__)


def configure_logging(
    level: int = logging.INFO,
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> None:
    """Configure logging with datetime formatting for all pyeuropepmc modules.

    Parameters
    ----------
    level : int
        Logging level (default: INFO)
    format : str
        Log format string with datetime placeholder (default: includes datetime)
    datefmt : str
        Date/time format string (default: YYYY-MM-DD HH:MM:SS)
    """
    logging.basicConfig(level=level, format=format, datefmt=datefmt)


# --- Lazy: imported on first attribute access (PEP 562) ----------------------
_LAZY: dict[str, str] = {
    # Literature (Europe PMC core)
    "SearchClient": "pyeuropepmc.features.literature.search:SearchClient",
    "ArticleClient": "pyeuropepmc.features.literature.article:ArticleClient",
    "AnnotationsClient": "pyeuropepmc.features.literature.annotations:AnnotationsClient",
    "FTPDownloader": "pyeuropepmc.features.literature.ftp_downloader:FTPDownloader",
    "EuropePMCParser": "pyeuropepmc.features.literature.search_parser:EuropePMCParser",
    "QueryBuilder": "pyeuropepmc.features.literature.query_builder:QueryBuilder",
    "get_available_fields": "pyeuropepmc.features.literature.query_builder:get_available_fields",
    "validate_field_coverage": (
        "pyeuropepmc.features.literature.query_builder:validate_field_coverage"
    ),
    "CursorPaginator": "pyeuropepmc.features.literature.pagination:CursorPaginator",
    "PaginationCheckpoint": "pyeuropepmc.features.literature.pagination:PaginationCheckpoint",
    "PaginationState": "pyeuropepmc.features.literature.pagination:PaginationState",
    "filter_pmc_papers": "pyeuropepmc.features.literature.filters:filter_pmc_papers",
    "filter_pmc_papers_or": "pyeuropepmc.features.literature.filters:filter_pmc_papers_or",
    # Full text
    "FullTextClient": "pyeuropepmc.features.fulltext.fulltext_client:FullTextClient",
    "ProgressInfo": "pyeuropepmc.features.fulltext.fulltext_client:ProgressInfo",
    "FullTextXMLParser": "pyeuropepmc.features.fulltext.fulltext_parser:FullTextXMLParser",
    "DocumentSchema": "pyeuropepmc.features.fulltext.fulltext_parser:DocumentSchema",
    "ElementPatterns": "pyeuropepmc.features.fulltext.fulltext_parser:ElementPatterns",
    "AnnotationParser": "pyeuropepmc.features.fulltext.annotation_parser:AnnotationParser",
    "parse_annotations": "pyeuropepmc.features.fulltext.annotation_parser:parse_annotations",
    "extract_entities": "pyeuropepmc.features.fulltext.annotation_parser:extract_entities",
    "extract_sentences": "pyeuropepmc.features.fulltext.annotation_parser:extract_sentences",
    "extract_relationships": (
        "pyeuropepmc.features.fulltext.annotation_parser:extract_relationships"
    ),
    # Enrichment (needs pyeuropepmc[enrichment] for some sources)
    "SemanticScholarClient": "pyeuropepmc.features.enrich:SemanticScholarClient",
    "PaperEnricher": "pyeuropepmc.features.enrich.enricher:PaperEnricher",
    "EnrichmentConfig": "pyeuropepmc.features.enrich.enricher:EnrichmentConfig",
    # Multi-source search
    "UnifiedSearch": "pyeuropepmc.features.search.unified_search:UnifiedSearch",
    # RDF mapping (needs pyeuropepmc[rdf])
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
    "convert_annotations_to_rdf": "pyeuropepmc.mappers.converters:convert_annotations_to_rdf",
    # Analytics (needs pyeuropepmc[analytics])
    "to_dataframe": "pyeuropepmc.features.analytics.analytics:to_dataframe",
    "publication_year_distribution": (
        "pyeuropepmc.features.analytics.analytics:publication_year_distribution"
    ),
    "citation_statistics": "pyeuropepmc.features.analytics.analytics:citation_statistics",
    "detect_duplicates": "pyeuropepmc.features.analytics.analytics:detect_duplicates",
    "remove_duplicates": "pyeuropepmc.features.analytics.analytics:remove_duplicates",
    "quality_metrics": "pyeuropepmc.features.analytics.analytics:quality_metrics",
    "publication_type_distribution": (
        "pyeuropepmc.features.analytics.analytics:publication_type_distribution"
    ),
    "journal_distribution": "pyeuropepmc.features.analytics.analytics:journal_distribution",
    "author_statistics": "pyeuropepmc.features.analytics.analytics:author_statistics",
    "geographic_analysis": "pyeuropepmc.features.analytics.analytics:geographic_analysis",
    # Visualization (needs pyeuropepmc[visualization])
    "plot_publication_years": (
        "pyeuropepmc.features.analytics.visualization:plot_publication_years"
    ),
    "plot_citation_distribution": (
        "pyeuropepmc.features.analytics.visualization:plot_citation_distribution"
    ),
    "plot_quality_metrics": "pyeuropepmc.features.analytics.visualization:plot_quality_metrics",
    "plot_publication_types": (
        "pyeuropepmc.features.analytics.visualization:plot_publication_types"
    ),
    "plot_journals": "pyeuropepmc.features.analytics.visualization:plot_journals",
    "plot_trend_analysis": "pyeuropepmc.features.analytics.visualization:plot_trend_analysis",
    "create_summary_dashboard": (
        "pyeuropepmc.features.analytics.visualization:create_summary_dashboard"
    ),
    # Pipeline
    "PaperProcessingPipeline": "pyeuropepmc.pipeline:PaperProcessingPipeline",
    "PipelineConfig": "pyeuropepmc.pipeline:PipelineConfig",
    # Storage
    "ArtifactStore": "pyeuropepmc.storage.artifact_store:ArtifactStore",
    "ArtifactMetadata": "pyeuropepmc.storage.artifact_store:ArtifactMetadata",
    # Agentic / LLM (needs pyeuropepmc[agentic])
    "SmartCitationAnalysis": "pyeuropepmc.agentic.agents:SmartCitationAnalysis",
    "LLMClient": "pyeuropepmc.agentic.llm_client:LLMClient",
    "create_llm_client": "pyeuropepmc.agentic.llm_client:create_llm_client",
    # Backwards-compatible aliases
    "Client": "pyeuropepmc.features.literature.search:SearchClient",
    "Parser": "pyeuropepmc.features.literature.search_parser:EuropePMCParser",
}

# Optional: resolves to None when the optional dependency is absent
# (preserves the historical ``create_app = None`` fallback for the Flask UI).
_LAZY_OPTIONAL: dict[str, str] = {
    "create_app": "pyeuropepmc.ui.app:create_app",
}

_EAGER = (
    "__version__",
    "__author__",
    "__url__",
    "configure_logging",
    "BaseAPIClient",
    "CacheBackend",
    "CacheConfig",
    "CacheDataType",
    "CacheLayer",
    "normalize_query_params",
    "APIClientError",
    "ClientError",
    "EuropePMCError",
    "FileError",
    "FullTextError",
    "ModelError",
    "UnpaywallError",
)

_lazy_getattr, __dir__, __all__ = lazy_module(
    __name__, _LAZY, eager=_EAGER, optional=_LAZY_OPTIONAL
)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:  # help IDEs / type checkers without paying import cost at runtime
    from pyeuropepmc.agentic.agents import SmartCitationAnalysis as SmartCitationAnalysis
    from pyeuropepmc.agentic.llm_client import (
        LLMClient as LLMClient,
        create_llm_client as create_llm_client,
    )
    from pyeuropepmc.features.enrich.enricher import (
        EnrichmentConfig as EnrichmentConfig,
        PaperEnricher as PaperEnricher,
    )
    from pyeuropepmc.features.enrich.sources.semantic_scholar import (
        SemanticScholarClient as SemanticScholarClient,
    )
    from pyeuropepmc.features.literature.annotations import AnnotationsClient as AnnotationsClient
    from pyeuropepmc.features.literature.article import ArticleClient as ArticleClient
    from pyeuropepmc.features.literature.ftp_downloader import FTPDownloader as FTPDownloader
    from pyeuropepmc.features.literature.search import SearchClient as SearchClient
    from pyeuropepmc.features.literature.search_parser import EuropePMCParser as EuropePMCParser
    from pyeuropepmc.features.search.unified_search import UnifiedSearch as UnifiedSearch
    from pyeuropepmc.pipeline import (
        PaperProcessingPipeline as PaperProcessingPipeline,
        PipelineConfig as PipelineConfig,
    )
