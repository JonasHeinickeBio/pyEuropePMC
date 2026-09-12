"""Research analytics and visualization.

This slice provides statistical analysis and visualization tools
for literature search results, including publication trends, citation
distributions, author collaboration networks, and geographic analysis.

Names are imported lazily (PEP 562).  The statistics helpers need
``pyeuropepmc[analytics]`` (pandas); the ``plot_*`` helpers additionally need
``pyeuropepmc[visualization]`` (matplotlib, seaborn).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

_ANALYTICS = "pyeuropepmc.features.analytics.analytics"
_VIZ = "pyeuropepmc.features.analytics.visualization"

_LAZY = {
    name: f"{_ANALYTICS}:{name}"
    for name in (
        "access_distribution",
        "author_collaboration_network",
        "author_statistics",
        "citation_by_access_type",
        "citation_statistics",
        "detect_duplicates",
        "disease_comparison_trends",
        "funding_source_analysis",
        "geographic_analysis",
        "journal_distribution",
        "publication_type_distribution",
        "publication_year_distribution",
        "quality_metrics",
        "remove_duplicates",
        "to_dataframe",
    )
}
_LAZY.update(
    {
        name: f"{_VIZ}:{name}"
        for name in (
            "create_summary_dashboard",
            "plot_access_distribution",
            "plot_author_collaboration_network",
            "plot_citation_by_access_type",
            "plot_citation_distribution",
            "plot_disease_comparison_trends",
            "plot_fulltext_availability",
            "plot_funding_sources",
            "plot_journals",
            "plot_license_distribution",
            "plot_publication_types",
            "plot_publication_years",
            "plot_quality_metrics",
            "plot_trend_analysis",
        )
    }
)

_lazy_getattr, __dir__, __all__ = lazy_module(__name__, _LAZY)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:
    from pyeuropepmc.features.analytics.analytics import (
        access_distribution as access_distribution,
        author_collaboration_network as author_collaboration_network,
        author_statistics as author_statistics,
        citation_by_access_type as citation_by_access_type,
        citation_statistics as citation_statistics,
        detect_duplicates as detect_duplicates,
        disease_comparison_trends as disease_comparison_trends,
        funding_source_analysis as funding_source_analysis,
        geographic_analysis as geographic_analysis,
        journal_distribution as journal_distribution,
        publication_type_distribution as publication_type_distribution,
        publication_year_distribution as publication_year_distribution,
        quality_metrics as quality_metrics,
        remove_duplicates as remove_duplicates,
        to_dataframe as to_dataframe,
    )
    from pyeuropepmc.features.analytics.visualization import (
        create_summary_dashboard as create_summary_dashboard,
        plot_access_distribution as plot_access_distribution,
        plot_author_collaboration_network as plot_author_collaboration_network,
        plot_citation_by_access_type as plot_citation_by_access_type,
        plot_citation_distribution as plot_citation_distribution,
        plot_disease_comparison_trends as plot_disease_comparison_trends,
        plot_fulltext_availability as plot_fulltext_availability,
        plot_funding_sources as plot_funding_sources,
        plot_journals as plot_journals,
        plot_license_distribution as plot_license_distribution,
        plot_publication_types as plot_publication_types,
        plot_publication_years as plot_publication_years,
        plot_quality_metrics as plot_quality_metrics,
        plot_trend_analysis as plot_trend_analysis,
    )
