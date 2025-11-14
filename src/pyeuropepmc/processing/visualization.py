"""
Visualization utilities for Europe PMC search results.

This module provides functions for creating visualizations of Europe PMC
search results, including publication trends, citation distributions,
quality metrics, and more.
"""

import logging
from pathlib import Path
from typing import Any

import matplotlib.figure
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .analytics import (
    citation_statistics,
    journal_distribution,
    publication_type_distribution,
    publication_year_distribution,
    quality_metrics,
    to_dataframe,
)

logger = logging.getLogger("pyeuropepmc.visualization")
logger.addHandler(logging.NullHandler())

# Set default style
sns.set_theme(style="whitegrid", palette="muted")


def plot_publication_years(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Publications by Year",
    figsize: tuple[int, int] = (12, 6),
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a bar chart of publications by year.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Publications by Year"
        Title for the plot.
    figsize : tuple[int, int], default=(12, 6)
        Figure size (width, height) in inches.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import plot_publication_years
    >>> fig = plot_publication_years(papers, save_path="pub_years.png")
    """
    year_dist = publication_year_distribution(papers)

    if year_dist.empty:
        logger.warning("No publication year data to plot")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(
            0.5,
            0.5,
            "No publication year data available",
            ha="center",
            va="center",
            fontsize=14,
        )
        return fig

    fig, ax = plt.subplots(figsize=figsize)
    year_dist.plot(kind="bar", ax=ax, color=sns.color_palette("viridis", len(year_dist)))
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Publication Year", fontsize=12)
    ax.set_ylabel("Number of Papers", fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved publication year plot to {save_path}")

    return fig


def plot_citation_distribution(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Citation Distribution",
    figsize: tuple[int, int] = (12, 6),
    log_scale: bool = False,
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a histogram of citation distribution.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Citation Distribution"
        Title for the plot.
    figsize : tuple[int, int], default=(12, 6)
        Figure size (width, height) in inches.
    log_scale : bool, default=False
        Use logarithmic scale for y-axis.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import plot_citation_distribution
    >>> fig = plot_citation_distribution(papers, log_scale=True)
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "citedByCount" not in df.columns:
        logger.warning("No citation data to plot")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No citation data available", ha="center", va="center", fontsize=14)
        return fig

    fig, ax = plt.subplots(figsize=figsize)
    citations = df["citedByCount"].astype(int)

    # Create histogram with automatic binning
    ax.hist(
        citations, bins=30, color=sns.color_palette("viridis")[0], alpha=0.7, edgecolor="black"
    )

    if log_scale:
        ax.set_yscale("log")

    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Number of Citations", fontsize=12)
    ax.set_ylabel("Number of Papers", fontsize=12)

    # Add statistics as text
    stats = citation_statistics(df)
    stats_text = (
        f"Mean: {stats['mean_citations']:.1f}\n"
        f"Median: {stats['median_citations']:.0f}\n"
        f"Max: {stats['max_citations']}"
    )
    ax.text(
        0.95,
        0.95,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="top",
        horizontalalignment="right",
        bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
        fontsize=10,
    )

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved citation distribution plot to {save_path}")

    return fig


def plot_quality_metrics(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Paper Quality Metrics",
    figsize: tuple[int, int] = (10, 6),
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a bar chart of quality metrics.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Paper Quality Metrics"
        Title for the plot.
    figsize : tuple[int, int], default=(10, 6)
        Figure size (width, height) in inches.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import plot_quality_metrics
    >>> fig = plot_quality_metrics(papers)
    """
    metrics = quality_metrics(papers)

    if metrics["total_papers"] == 0:
        logger.warning("No papers to analyze")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No papers to analyze", ha="center", va="center", fontsize=14)
        return fig

    # Prepare data for plotting
    metric_names = [
        "Open Access",
        "With Abstract",
        "With DOI",
        "In PMC",
        "With PDF",
        "Peer Reviewed*",
    ]
    percentages = [
        metrics["open_access_percentage"],
        metrics["with_abstract_percentage"],
        metrics["with_doi_percentage"],
        metrics["in_pmc_percentage"],
        metrics["with_pdf_percentage"],
        metrics["peer_reviewed_percentage"],
    ]

    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh(
        metric_names, percentages, color=sns.color_palette("viridis", len(metric_names))
    )

    ax.set_xlabel("Percentage (%)", fontsize=12)
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlim(0, 100)

    # Add value labels on bars
    for _i, (bar, pct) in enumerate(zip(bars, percentages, strict=False)):
        width = bar.get_width()
        ax.text(
            width + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{pct:.1f}%",
            va="center",
            fontsize=10,
        )

    # Add footnote
    fig.text(
        0.5,
        0.02,
        "*Peer reviewed is estimated based on publication type",
        ha="center",
        fontsize=8,
        style="italic",
    )

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved quality metrics plot to {save_path}")

    return fig


def plot_publication_types(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Publication Type Distribution",
    top_n: int = 10,
    figsize: tuple[int, int] = (10, 6),
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a bar chart of publication types.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Publication Type Distribution"
        Title for the plot.
    top_n : int, default=10
        Number of top publication types to display.
    figsize : tuple[int, int], default=(10, 6)
        Figure size (width, height) in inches.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import plot_publication_types
    >>> fig = plot_publication_types(papers, top_n=15)
    """
    pub_type_dist = publication_type_distribution(papers)

    if pub_type_dist.empty:
        logger.warning("No publication type data to plot")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(
            0.5,
            0.5,
            "No publication type data available",
            ha="center",
            va="center",
            fontsize=14,
        )
        return fig

    # Get top N types
    top_types = pub_type_dist.head(top_n)

    fig, ax = plt.subplots(figsize=figsize)
    top_types.plot(kind="barh", ax=ax, color=sns.color_palette("viridis", len(top_types)))
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Number of Papers", fontsize=12)
    ax.set_ylabel("Publication Type", fontsize=12)
    ax.invert_yaxis()  # Highest at top

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved publication type plot to {save_path}")

    return fig


def plot_journals(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Top Journals",
    top_n: int = 10,
    figsize: tuple[int, int] = (10, 6),
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a bar chart of top journals.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Top Journals"
        Title for the plot.
    top_n : int, default=10
        Number of top journals to display.
    figsize : tuple[int, int], default=(10, 6)
        Figure size (width, height) in inches.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import plot_journals
    >>> fig = plot_journals(papers, top_n=15)
    """
    journal_dist = journal_distribution(papers, top_n=top_n)

    if journal_dist.empty:
        logger.warning("No journal data to plot")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No journal data available", ha="center", va="center", fontsize=14)
        return fig

    fig, ax = plt.subplots(figsize=figsize)
    journal_dist.plot(kind="barh", ax=ax, color=sns.color_palette("viridis", len(journal_dist)))
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Number of Papers", fontsize=12)
    ax.set_ylabel("Journal", fontsize=12)
    ax.invert_yaxis()  # Highest at top

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved journal plot to {save_path}")

    return fig


def plot_trend_analysis(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Publication and Citation Trends",
    figsize: tuple[int, int] = (14, 6),
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a multi-panel plot showing publication and citation trends over time.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Publication and Citation Trends"
        Title for the plot.
    figsize : tuple[int, int], default=(14, 6)
        Figure size (width, height) in inches.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import plot_trend_analysis
    >>> fig = plot_trend_analysis(papers)
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "pubYear" not in df.columns or "citedByCount" not in df.columns:
        logger.warning("Insufficient data for trend analysis")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(
            0.5,
            0.5,
            "Insufficient data for trend analysis",
            ha="center",
            va="center",
            fontsize=14,
        )
        return fig

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    # Publication count by year
    year_dist = publication_year_distribution(df)
    if not year_dist.empty:
        ax1.plot(
            year_dist.index,
            year_dist.values,
            marker="o",
            linewidth=2,
            markersize=6,
            color=sns.color_palette("viridis")[0],
        )
        ax1.fill_between(year_dist.index, year_dist.values, alpha=0.3)
        ax1.set_title("Publications Over Time", fontsize=14, fontweight="bold")
        ax1.set_xlabel("Year", fontsize=12)
        ax1.set_ylabel("Number of Papers", fontsize=12)
        ax1.grid(True, alpha=0.3)

    # Average citations by year
    df_clean = df.dropna(subset=["pubYear"])
    if not df_clean.empty:
        year_citations = (
            df_clean.groupby("pubYear")["citedByCount"]
            .agg(["mean", "median", "count"])
            .reset_index()
        )
        year_citations["pubYear"] = pd.to_numeric(year_citations["pubYear"])

        ax2.plot(
            year_citations["pubYear"],
            year_citations["mean"],
            marker="o",
            linewidth=2,
            markersize=6,
            label="Mean",
            color=sns.color_palette("viridis")[2],
        )
        ax2.plot(
            year_citations["pubYear"],
            year_citations["median"],
            marker="s",
            linewidth=2,
            markersize=6,
            label="Median",
            color=sns.color_palette("viridis")[4],
        )
        ax2.set_title("Citations per Paper Over Time", fontsize=14, fontweight="bold")
        ax2.set_xlabel("Year", fontsize=12)
        ax2.set_ylabel("Citations per Paper", fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved trend analysis plot to {save_path}")

    return fig


def create_summary_dashboard(
    papers: list[dict[str, Any]] | pd.DataFrame,
    title: str = "Literature Analysis Dashboard",
    figsize: tuple[int, int] = (16, 10),
    save_path: str | Path | None = None,
) -> matplotlib.figure.Figure:
    """
    Create a comprehensive dashboard with multiple visualizations.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    title : str, default="Literature Analysis Dashboard"
        Title for the dashboard.
    figsize : tuple[int, int], default=(16, 10)
        Figure size (width, height) in inches.
    save_path : str | Path | None, default=None
        Optional path to save the figure.

    Returns
    -------
    plt.Figure
        The matplotlib figure object.

    Examples
    --------
    >>> from pyeuropepmc.processing.visualization import create_summary_dashboard
    >>> fig = create_summary_dashboard(papers, save_path="dashboard.png")
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty:
        logger.warning("No data to create dashboard")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=14)
        return fig

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Publication year trend
    ax1 = fig.add_subplot(gs[0, :])
    year_dist = publication_year_distribution(df)
    if not year_dist.empty:
        ax1.plot(
            year_dist.index,
            year_dist.values,
            marker="o",
            linewidth=2,
            color=sns.color_palette("viridis")[0],
        )
        ax1.fill_between(year_dist.index, year_dist.values, alpha=0.3)
        ax1.set_title("Publications Over Time", fontweight="bold")
        ax1.set_ylabel("Number of Papers")
        ax1.grid(True, alpha=0.3)

    # Citation distribution
    ax2 = fig.add_subplot(gs[1, 0])
    if "citedByCount" in df.columns:
        citations = df["citedByCount"].astype(int)
        ax2.hist(citations, bins=20, color=sns.color_palette("viridis")[1], alpha=0.7)
        ax2.set_title("Citation Distribution", fontweight="bold")
        ax2.set_xlabel("Citations")
        ax2.set_ylabel("Count")

    # Quality metrics
    ax3 = fig.add_subplot(gs[1, 1])
    metrics = quality_metrics(df)
    metric_names = ["Open Access", "With Abstract", "With DOI"]
    percentages = [
        metrics["open_access_percentage"],
        metrics["with_abstract_percentage"],
        metrics["with_doi_percentage"],
    ]
    ax3.barh(metric_names, percentages, color=sns.color_palette("viridis", 3))
    ax3.set_xlim(0, 100)
    ax3.set_title("Quality Metrics (%)", fontweight="bold")
    ax3.set_xlabel("Percentage")

    # Publication types
    ax4 = fig.add_subplot(gs[1, 2])
    pub_types = publication_type_distribution(df).head(5)
    if not pub_types.empty:
        ax4.barh(range(len(pub_types)), pub_types.values, color=sns.color_palette("viridis", 5))
        ax4.set_yticks(range(len(pub_types)))
        ax4.set_yticklabels(pub_types.index, fontsize=8)
        ax4.set_title("Top Publication Types", fontweight="bold")
        ax4.set_xlabel("Count")
        ax4.invert_yaxis()

    # Top journals
    ax5 = fig.add_subplot(gs[2, :2])
    journals = journal_distribution(df, top_n=8)
    if not journals.empty:
        ax5.barh(range(len(journals)), journals.values, color=sns.color_palette("viridis", 8))
        ax5.set_yticks(range(len(journals)))
        ax5.set_yticklabels(journals.index, fontsize=9)
        ax5.set_title("Top Journals", fontweight="bold")
        ax5.set_xlabel("Number of Papers")
        ax5.invert_yaxis()

    # Summary statistics
    ax6 = fig.add_subplot(gs[2, 2])
    ax6.axis("off")
    stats = citation_statistics(df)
    summary_text = (
        f"Total Papers: {metrics['total_papers']}\n\n"
        f"Citation Statistics:\n"
        f"  Mean: {stats['mean_citations']:.1f}\n"
        f"  Median: {stats['median_citations']:.0f}\n"
        f"  Max: {stats['max_citations']}\n\n"
        f"Open Access: {metrics['open_access_percentage']:.1f}%\n"
        f"With Abstract: {metrics['with_abstract_percentage']:.1f}%"
    )
    ax6.text(
        0.1,
        0.9,
        summary_text,
        transform=ax6.transAxes,
        verticalalignment="top",
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.3},
    )

    fig.suptitle(title, fontsize=18, fontweight="bold")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved dashboard to {save_path}")

    return fig


__all__ = [
    "plot_publication_years",
    "plot_citation_distribution",
    "plot_quality_metrics",
    "plot_publication_types",
    "plot_journals",
    "plot_trend_analysis",
    "create_summary_dashboard",
]
