"""
Data processing modules for PyEuropePMC.

This module contains all the data processing and analysis functionality
including parsers, analytics, and visualization tools.
"""

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
from .fulltext_parser import DocumentSchema, ElementPatterns, FullTextXMLParser
from .parser import EuropePMCParser
from .visualization import (
    create_summary_dashboard,
    plot_citation_distribution,
    plot_journals,
    plot_publication_types,
    plot_publication_years,
    plot_quality_metrics,
    plot_trend_analysis,
)

__all__ = [
    "author_statistics",
    "citation_statistics",
    "detect_duplicates",
    "geographic_analysis",
    "journal_distribution",
    "publication_type_distribution",
    "publication_year_distribution",
    "quality_metrics",
    "remove_duplicates",
    "to_dataframe",
    "DocumentSchema",
    "ElementPatterns",
    "FullTextXMLParser",
    "EuropePMCParser",
    "create_summary_dashboard",
    "plot_citation_distribution",
    "plot_journals",
    "plot_publication_types",
    "plot_publication_years",
    "plot_quality_metrics",
    "plot_trend_analysis",
]
