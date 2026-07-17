"""
PyEuropePMC - Python toolkit for Europe PMC API

A comprehensive Python library for searching and retrieving scientific literature
from Europe PMC with robust error handling, pagination, and multiple output formats.

Example usage:
    >>> import pyeuropepmc
    >>> client = pyeuropepmc.SearchClient()
    >>> results = client.search("CRISPR gene editing", pageSize=10)
    >>> papers = client.search_and_parse("COVID-19", format="json")
"""

import logging

from .agentic.agents import SmartCitationAnalysis
from .agentic.llm_client import LLMClient, create_llm_client
from .cache.cache import (
    CacheBackend,
    CacheConfig,
    CacheDataType,
    CacheLayer,
    normalize_query_params,
)
from .features.literature.annotations import AnnotationsClient
from .features.literature.article import ArticleClient
from .features.literature.ftp_downloader import FTPDownloader
from .features.fulltext.fulltext_client import FullTextClient, ProgressInfo
from .features.literature.search import SearchClient
from .core.base import BaseAPIClient
from .core.exceptions import (
    APIClientError,
    ClientError,
    EuropePMCError,
    FileError,
    FullTextError,
    ModelError,
    UnpaywallError,
)
from .features.enrich import SemanticScholarClient
from .features.enrich.enricher import EnrichmentConfig, PaperEnricher
from .mappers.converters import convert_annotations_to_rdf
from .pipeline import PaperProcessingPipeline, PipelineConfig
from .features.analytics.analytics import (
    author_statistics,
    citation_statistics,
    detect_duplicates,
    geographic_analysis,
    journal_distribution,
    publication_type_distribution,
    publication_year_distribution,
    quality_metrics,
    remove_duplicates,
    to_dataframe,
)
from .features.fulltext.annotation_parser import (
    AnnotationParser,
    extract_entities,
    extract_relationships,
    extract_sentences,
    parse_annotations,
)
from .features.literature.annotations_to_rdf import (
    annotations_to_entities,
    annotations_to_rdf,
    entity_annotation_to_model,
    relationship_annotation_to_model,
)
from .features.fulltext.fulltext_parser import DocumentSchema, ElementPatterns, FullTextXMLParser
from .features.literature.search_parser import EuropePMCParser
from .features.analytics.visualization import (
    create_summary_dashboard,
    plot_citation_distribution,
    plot_journals,
    plot_publication_types,
    plot_publication_years,
    plot_quality_metrics,
    plot_trend_analysis,
)
from .features.literature.filters import filter_pmc_papers, filter_pmc_papers_or
from .features.literature.pagination import (
    CursorPaginator,
    PaginationCheckpoint,
    PaginationState,
)
from .features.literature.query_builder import QueryBuilder, get_available_fields, validate_field_coverage
from .storage.artifact_store import ArtifactMetadata, ArtifactStore

# UI module — guarded import (Flask is optional)
try:
    from .ui.app import create_app as _create_app

    create_app = _create_app
except ImportError:
    create_app = None  # type: ignore[assignment]
except Exception:
    create_app = None  # type: ignore[assignment]

__version__ = "2.0.0"
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


# Import main classes for convenient access

# Convenience imports for common usage patterns
Client = SearchClient  # Alias for backwards compatibility
Parser = EuropePMCParser  # Alias for convenience

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__url__",
    # Main classes
    "AnnotationsClient",
    "ArticleClient",
    "SearchClient",
    "FullTextClient",
    "FTPDownloader",
    "EuropePMCParser",
    "FullTextXMLParser",
    "AnnotationParser",
    "BaseAPIClient",
    "ProgressInfo",
    "QueryBuilder",
    "get_available_fields",
    "validate_field_coverage",
    # Cache and Storage
    "CacheBackend",
    "CacheConfig",
    "CacheDataType",
    "CacheLayer",
    "normalize_query_params",
    "ArtifactStore",
    "ArtifactMetadata",
    "UnpaywallError",
    "ClientError",
    "FileError",
    "ModelError",
    # Pagination
    "PaginationState",
    "PaginationCheckpoint",
    "CursorPaginator",
    # Parser configuration classes
    "ElementPatterns",
    "DocumentSchema",
    # Exceptions
    "EuropePMCError",
    "FullTextError",
    "APIClientError",
    # Filtering utilities
    "filter_pmc_papers",
    "filter_pmc_papers_or",
    # Annotation parsing utilities
    "parse_annotations",
    "extract_entities",
    "extract_sentences",
    "extract_relationships",
    "annotations_to_entities",
    "annotations_to_rdf",
    "convert_annotations_to_rdf",
    "entity_annotation_to_model",
    "relationship_annotation_to_model",
    # Enrichment utilities
    "PaperEnricher",
    "EnrichmentConfig",
    "SemanticScholarClient",
    # Pipeline utilities
    "PaperProcessingPipeline",
    "PipelineConfig",
    # LLM/Agentic utilities
    "SmartCitationAnalysis",
    "LLMClient",
    "create_llm_client",
    # Analytics utilities
    "to_dataframe",
    "publication_year_distribution",
    "citation_statistics",
    "detect_duplicates",
    "remove_duplicates",
    "quality_metrics",
    "publication_type_distribution",
    "journal_distribution",
    "author_statistics",
    "geographic_analysis",
    # Visualization utilities
    "plot_publication_years",
    "plot_citation_distribution",
    "plot_quality_metrics",
    "plot_publication_types",
    "plot_journals",
    "plot_trend_analysis",
    "create_summary_dashboard",
    # Aliases
    "Client",
    "Parser",
    # Web UI
    "create_app",
]
