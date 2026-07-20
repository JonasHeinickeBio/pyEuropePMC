"""Research analytics and visualization.

This slice provides statistical analysis and visualization tools
for literature search results, including publication trends, citation
distributions, author collaboration networks, and geographic analysis.
"""

from pyeuropepmc.features.analytics.analytics import (
    access_distribution,
    author_collaboration_network,
    author_statistics,
    citation_by_access_type,
    citation_statistics,
    detect_duplicates,
    disease_comparison_trends,
    funding_source_analysis,
    geographic_analysis,
    journal_distribution,
    publication_type_distribution,
    publication_year_distribution,
    quality_metrics,
    remove_duplicates,
    to_dataframe,
)
from pyeuropepmc.features.analytics.visualization import (
    create_summary_dashboard,
    plot_access_distribution,
    plot_author_collaboration_network,
    plot_citation_by_access_type,
    plot_citation_distribution,
    plot_disease_comparison_trends,
    plot_fulltext_availability,
    plot_funding_sources,
    plot_journals,
    plot_license_distribution,
    plot_publication_types,
    plot_publication_years,
    plot_quality_metrics,
    plot_trend_analysis,
)

__all__ = [
    "access_distribution",
    "author_collaboration_network",
    "author_statistics",
    "citation_by_access_type",
    "citation_statistics",
    "create_summary_dashboard",
    "detect_duplicates",
    "disease_comparison_trends",
    "funding_source_analysis",
    "geographic_analysis",
    "journal_distribution",
    "plot_access_distribution",
    "plot_author_collaboration_network",
    "plot_citation_by_access_type",
    "plot_citation_distribution",
    "plot_disease_comparison_trends",
    "plot_funding_sources",
    "plot_fulltext_availability",
    "plot_journals",
    "plot_license_distribution",
    "plot_publication_types",
    "plot_publication_years",
    "plot_quality_metrics",
    "plot_trend_analysis",
    "publication_type_distribution",
    "publication_year_distribution",
    "quality_metrics",
    "remove_duplicates",
    "to_dataframe",
]
