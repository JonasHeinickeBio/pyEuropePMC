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

__version__ = "1.8.1"
__author__ = "Jonas Heinicke"
__email__ = "jonas.heinicke@helmholtz-hzi.de"
__url__ = "https://github.com/JonasHeinickeBio/pyEuropePMC"

# Import main classes for convenient access
from .analytics import (
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
from .article import ArticleClient
from .artifact_store import ArtifactMetadata, ArtifactStore
from .base import APIClientError, BaseAPIClient
from .filters import filter_pmc_papers, filter_pmc_papers_or
from .ftp_downloader import FTPDownloader
from .fulltext import FullTextClient, FullTextError, ProgressInfo
from .fulltext_parser import DocumentSchema, ElementPatterns, FullTextXMLParser
from .parser import EuropePMCParser
from .query_builder import QueryBuilder
from .search import EuropePMCError, SearchClient
from .visualization import (
    create_summary_dashboard,
    plot_citation_distribution,
    plot_journals,
    plot_publication_types,
    plot_publication_years,
    plot_quality_metrics,
    plot_trend_analysis,
)

# Convenience imports for common usage patterns
Client = SearchClient  # Alias for backwards compatibility
Parser = EuropePMCParser  # Alias for convenience

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__url__",
    # Main classes
    "ArticleClient",
    "SearchClient",
    "FullTextClient",
    "FTPDownloader",
    "EuropePMCParser",
    "FullTextXMLParser",
    "BaseAPIClient",
    "ProgressInfo",
    "QueryBuilder",
    # Cache and Storage
    "ArtifactStore",
    "ArtifactMetadata",
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
]
