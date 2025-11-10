"""
Analytics utilities for Europe PMC search results.

This module provides functions for analyzing and processing Europe PMC search results,
including publication year distribution, citation patterns, duplicate detection,
and quality metrics computation. It also provides utilities to convert results
to pandas DataFrames for further analysis.
"""

from collections import Counter
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger("pyeuropepmc.analytics")
logger.addHandler(logging.NullHandler())


def to_dataframe(papers: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert a list of papers to a pandas DataFrame.

    Parameters
    ----------
    papers : list[dict[str, Any]]
        List of papers from Europe PMC API response or filtered results.

    Returns
    -------
    pd.DataFrame
        DataFrame with paper metadata including title, authors, pubYear,
        citedByCount, isOpenAccess, doi, pmid, pmcid, etc.

    Examples
    --------
    >>> from pyeuropepmc import SearchClient
    >>> from pyeuropepmc.analytics import to_dataframe
    >>>
    >>> client = SearchClient()
    >>> response = client.search("cancer", pageSize=10)
    >>> papers = response.get("resultList", {}).get("result", [])
    >>> df = to_dataframe(papers)
    >>> print(df.columns)
    """
    if not papers:
        return pd.DataFrame()

    # Extract common fields
    df_data = []
    for paper in papers:
        try:
            row = {
                "id": paper.get("id"),
                "source": paper.get("source"),
                "title": paper.get("title", ""),
                "authorString": paper.get("authorString", ""),
                "journalTitle": paper.get("journalTitle", ""),
                "pubYear": paper.get("pubYear"),
                "pubType": _flatten_pub_type(paper),
                "isOpenAccess": paper.get("isOpenAccess", "N"),
                "citedByCount": int(paper.get("citedByCount", 0)),
                "doi": paper.get("doi"),
                "pmid": paper.get("pmid"),
                "pmcid": paper.get("pmcid"),
                "abstractText": paper.get("abstractText", ""),
                "hasAbstract": bool(paper.get("abstractText", "").strip()),
                "hasPDF": paper.get("hasPDF", "N") == "Y",
                "inPMC": paper.get("inPMC", "N") == "Y",
                "inEPMC": paper.get("inEPMC", "N") == "Y",
            }
            df_data.append(row)
        except Exception as e:
            logger.exception(f"Error converting paper id={paper.get('id')} to DataFrame: {e}")

    return pd.DataFrame(df_data)


def _flatten_pub_type(paper: dict[str, Any]) -> str:
    """Flatten publication type from various possible structures."""
    try:
        pub_types = []
        pub_type_list = paper.get("pubTypeList", {}).get("pubType", [])
        if isinstance(pub_type_list, str):
            pub_types.append(pub_type_list)
        elif isinstance(pub_type_list, list):
            pub_types.extend(str(pt) for pt in pub_type_list)

        top_pub_type = paper.get("pubType")
        if top_pub_type:
            if isinstance(top_pub_type, str):
                pub_types.append(top_pub_type)
            elif isinstance(top_pub_type, list):
                pub_types.extend(str(pt) for pt in top_pub_type)

        return "; ".join(pub_types) if pub_types else ""
    except Exception:
        return ""


def publication_year_distribution(
    papers: list[dict[str, Any]] | pd.DataFrame,
) -> pd.Series:
    """
    Calculate publication year distribution from papers.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.

    Returns
    -------
    pd.Series
        Series with year as index and count as values, sorted by year.

    Examples
    --------
    >>> from pyeuropepmc.analytics import publication_year_distribution
    >>> dist = publication_year_distribution(papers)
    >>> print(dist)
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "pubYear" not in df.columns:
        return pd.Series(dtype=int)

    # Convert pubYear to numeric, dropping NaN values
    year_series = pd.to_numeric(df["pubYear"], errors="coerce").dropna()
    return year_series.value_counts().sort_index()


def citation_statistics(
    papers: list[dict[str, Any]] | pd.DataFrame,
) -> dict[str, Any]:
    """
    Calculate citation statistics for papers.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.

    Returns
    -------
    dict[str, Any]
        Dictionary containing citation statistics:
        - total_papers: Total number of papers
        - mean_citations: Mean number of citations
        - median_citations: Median number of citations
        - std_citations: Standard deviation of citations
        - min_citations: Minimum citations
        - max_citations: Maximum citations
        - total_citations: Total citations across all papers
        - papers_with_citations: Number of papers with at least one citation
        - papers_without_citations: Number of papers with zero citations
        - citation_distribution: Distribution of citations by percentile

    Examples
    --------
    >>> from pyeuropepmc.analytics import citation_statistics
    >>> stats = citation_statistics(papers)
    >>> print(f"Mean citations: {stats['mean_citations']:.2f}")
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "citedByCount" not in df.columns:
        return {
            "total_papers": 0,
            "mean_citations": 0.0,
            "median_citations": 0.0,
            "std_citations": 0.0,
            "min_citations": 0,
            "max_citations": 0,
            "total_citations": 0,
            "papers_with_citations": 0,
            "papers_without_citations": 0,
            "citation_distribution": {},
        }

    citations = df["citedByCount"].astype(int)

    return {
        "total_papers": len(citations),
        "mean_citations": float(citations.mean()),
        "median_citations": float(citations.median()),
        "std_citations": float(citations.std()),
        "min_citations": int(citations.min()),
        "max_citations": int(citations.max()),
        "total_citations": int(citations.sum()),
        "papers_with_citations": int((citations > 0).sum()),
        "papers_without_citations": int((citations == 0).sum()),
        "citation_distribution": {
            "25th_percentile": float(citations.quantile(0.25)),
            "50th_percentile": float(citations.quantile(0.50)),
            "75th_percentile": float(citations.quantile(0.75)),
            "90th_percentile": float(citations.quantile(0.90)),
            "95th_percentile": float(citations.quantile(0.95)),
        },
    }


def detect_duplicates(
    papers: list[dict[str, Any]] | pd.DataFrame,
    method: str = "title",
) -> list[list[int]]:
    """
    Detect duplicate papers based on various criteria.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    method : str, default="title"
        Method to detect duplicates. Options:
        - "title": Exact title match (case-insensitive)
        - "doi": Exact DOI match
        - "pmid": Exact PMID match
        - "pmcid": Exact PMCID match

    Returns
    -------
    list[list[int]]
        List of lists, where each inner list contains indices of duplicate papers.

    Examples
    --------
    >>> from pyeuropepmc.analytics import detect_duplicates
    >>> duplicates = detect_duplicates(papers, method="title")
    >>> print(f"Found {len(duplicates)} sets of duplicates")
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty:
        return []

    # Map method to column name
    column_map = {
        "title": "title",
        "doi": "doi",
        "pmid": "pmid",
        "pmcid": "pmcid",
    }

    if method not in column_map:
        raise ValueError(f"Invalid method '{method}'. Choose from: {list(column_map.keys())}")

    column = column_map[method]
    if column not in df.columns:
        return []

    # For title, normalize to lowercase for comparison
    if method == "title":
        df_copy = df.copy()
        df_copy["_normalized"] = df_copy[column].str.lower().str.strip()
        column = "_normalized"
    else:
        df_copy = df

    # Find duplicates
    duplicates_list = []
    seen_groups = set()

    for value in df_copy[column].dropna().unique():
        if not value or pd.isna(value):
            continue

        indices = df_copy[df_copy[column] == value].index.tolist()
        if len(indices) > 1:
            indices_tuple = tuple(sorted(indices))
            if indices_tuple not in seen_groups:
                seen_groups.add(indices_tuple)
                duplicates_list.append(indices)

    return duplicates_list


def remove_duplicates(
    papers: list[dict[str, Any]] | pd.DataFrame,
    method: str = "title",
    keep: str = "first",
) -> pd.DataFrame:
    """
    Remove duplicate papers.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    method : str, default="title"
        Method to detect duplicates. Options: "title", "doi", "pmid", "pmcid"
    keep : str, default="first"
        Which duplicate to keep:
        - "first": Keep first occurrence
        - "last": Keep last occurrence
        - "most_cited": Keep the one with most citations

    Returns
    -------
    pd.DataFrame
        DataFrame with duplicates removed.

    Examples
    --------
    >>> from pyeuropepmc.analytics import remove_duplicates
    >>> unique_papers = remove_duplicates(papers, method="title", keep="most_cited")
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers.copy()

    if df.empty:
        return df

    column_map = {
        "title": "title",
        "doi": "doi",
        "pmid": "pmid",
        "pmcid": "pmcid",
    }

    if method not in column_map:
        raise ValueError(f"Invalid method '{method}'. Choose from: {list(column_map.keys())}")

    column = column_map[method]
    if column not in df.columns:
        return df

    # For title, normalize to lowercase for comparison
    if method == "title":
        df["_normalized"] = df[column].str.lower().str.strip()
        subset_col = "_normalized"
    else:
        subset_col = column

    if keep == "most_cited":
        # Sort by citations descending, then keep first (most cited)
        df = df.sort_values("citedByCount", ascending=False)
        df = df.drop_duplicates(subset=subset_col, keep="first")
        df = df.sort_index()
    else:
        df = df.drop_duplicates(subset=subset_col, keep=keep)

    # Clean up temporary column
    if method == "title" and "_normalized" in df.columns:
        df = df.drop(columns=["_normalized"])

    return df


def quality_metrics(papers: list[dict[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    """
    Calculate quality metrics for papers.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.

    Returns
    -------
    dict[str, Any]
        Dictionary containing quality metrics:
        - total_papers: Total number of papers
        - open_access_count: Number of open access papers
        - open_access_percentage: Percentage of open access papers
        - with_abstract_count: Number of papers with abstracts
        - with_abstract_percentage: Percentage with abstracts
        - with_doi_count: Number of papers with DOI
        - with_doi_percentage: Percentage with DOI
        - in_pmc_count: Number of papers in PMC
        - in_pmc_percentage: Percentage in PMC
        - with_pdf_count: Number of papers with PDF available
        - with_pdf_percentage: Percentage with PDF
        - peer_reviewed_estimate: Estimated peer-reviewed papers (based on pub type)

    Examples
    --------
    >>> from pyeuropepmc.analytics import quality_metrics
    >>> metrics = quality_metrics(papers)
    >>> print(f"Open access: {metrics['open_access_percentage']:.1f}%")
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty:
        return {
            "total_papers": 0,
            "open_access_count": 0,
            "open_access_percentage": 0.0,
            "with_abstract_count": 0,
            "with_abstract_percentage": 0.0,
            "with_doi_count": 0,
            "with_doi_percentage": 0.0,
            "in_pmc_count": 0,
            "in_pmc_percentage": 0.0,
            "with_pdf_count": 0,
            "with_pdf_percentage": 0.0,
            "peer_reviewed_estimate": 0,
            "peer_reviewed_percentage": 0.0,
        }

    total = len(df)

    # Open access
    open_access_count = int((df["isOpenAccess"] == "Y").sum())

    # Abstract
    with_abstract_count = int(df.get("hasAbstract", pd.Series([False] * total)).sum())

    # DOI
    with_doi_count = int(df["doi"].notna().sum())

    # In PMC
    in_pmc_count = int(df.get("inPMC", pd.Series([False] * total)).sum())

    # With PDF
    with_pdf_count = int(df.get("hasPDF", pd.Series([False] * total)).sum())

    # Estimate peer-reviewed based on publication type
    peer_reviewed_types = [
        "journal article",
        "research article",
        "review",
        "systematic review",
        "clinical trial",
        "case reports",
    ]
    peer_reviewed_count = 0
    if "pubType" in df.columns:
        for pub_type_str in df["pubType"]:
            if pd.notna(pub_type_str):
                pub_type_lower = str(pub_type_str).lower()
                if any(prt in pub_type_lower for prt in peer_reviewed_types):
                    peer_reviewed_count += 1

    return {
        "total_papers": total,
        "open_access_count": open_access_count,
        "open_access_percentage": (open_access_count / total * 100) if total > 0 else 0.0,
        "with_abstract_count": with_abstract_count,
        "with_abstract_percentage": (with_abstract_count / total * 100) if total > 0 else 0.0,
        "with_doi_count": with_doi_count,
        "with_doi_percentage": (with_doi_count / total * 100) if total > 0 else 0.0,
        "in_pmc_count": in_pmc_count,
        "in_pmc_percentage": (in_pmc_count / total * 100) if total > 0 else 0.0,
        "with_pdf_count": with_pdf_count,
        "with_pdf_percentage": (with_pdf_count / total * 100) if total > 0 else 0.0,
        "peer_reviewed_estimate": peer_reviewed_count,
        "peer_reviewed_percentage": (peer_reviewed_count / total * 100)
        if total > 0
        else 0.0,
    }


def publication_type_distribution(
    papers: list[dict[str, Any]] | pd.DataFrame,
) -> pd.Series:
    """
    Calculate publication type distribution.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.

    Returns
    -------
    pd.Series
        Series with publication type as index and count as values.

    Examples
    --------
    >>> from pyeuropepmc.analytics import publication_type_distribution
    >>> dist = publication_type_distribution(papers)
    >>> print(dist.head())
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "pubType" not in df.columns:
        return pd.Series(dtype=int)

    # Split multiple types and count them
    all_types = []
    for pub_type_str in df["pubType"].dropna():
        if pub_type_str:
            types = [t.strip() for t in str(pub_type_str).split(";")]
            all_types.extend(types)

    return pd.Series(Counter(all_types)).sort_values(ascending=False)


def journal_distribution(
    papers: list[dict[str, Any]] | pd.DataFrame, top_n: int = 10
) -> pd.Series:
    """
    Calculate journal distribution (top N journals).

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    top_n : int, default=10
        Number of top journals to return.

    Returns
    -------
    pd.Series
        Series with journal name as index and count as values.

    Examples
    --------
    >>> from pyeuropepmc.analytics import journal_distribution
    >>> dist = journal_distribution(papers, top_n=15)
    >>> print(dist)
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "journalTitle" not in df.columns:
        return pd.Series(dtype=int)

    return df["journalTitle"].value_counts().head(top_n)


__all__ = [
    "to_dataframe",
    "publication_year_distribution",
    "citation_statistics",
    "detect_duplicates",
    "remove_duplicates",
    "quality_metrics",
    "publication_type_distribution",
    "journal_distribution",
]
