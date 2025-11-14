"""
Analytics utilities for Europe PMC search results.

This module provides functions for analyzing and processing Europe PMC search results,
including publication year distribution, citation patterns, duplicate detection,
and quality metrics computation. It also provides utilities to convert results
to pandas DataFrames for further analysis.
"""

from collections import Counter
import logging
from typing import Any, cast

import pandas as pd

logger = logging.getLogger("pyeuropepmc.analytics")
logger.addHandler(logging.NullHandler())


def _extract_journal_title(paper: dict[str, Any]) -> str:
    """Extract journal title from paper data."""
    journal_title = paper.get("journalTitle", "")
    if not journal_title:
        # Try nested structure for core results
        journal_info = paper.get("journalInfo", {})
        if isinstance(journal_info, dict):
            journal = journal_info.get("journal", {})
            if isinstance(journal, dict):
                journal_title = journal.get("title", "")
    return str(journal_title) if journal_title else ""


def _extract_publisher(paper: dict[str, Any]) -> str:
    """Extract publisher information for preprints."""
    book_details = paper.get("bookOrReportDetails", {})
    return book_details.get("publisher", "") if book_details else ""


def _extract_mesh_terms(paper: dict[str, Any]) -> str:
    """Extract and flatten MeSH terms."""
    mesh_terms = []
    mesh_list = paper.get("meshHeadingList", {}).get("meshHeading", [])
    if isinstance(mesh_list, list):
        for mesh in mesh_list:
            if isinstance(mesh, dict) and "descriptorName" in mesh:
                term = mesh["descriptorName"]
                if mesh.get("majorTopic_YN") == "Y":
                    term += "*"  # Mark major topics
                mesh_terms.append(term)
    return "; ".join(mesh_terms) if mesh_terms else ""


def _extract_grants(paper: dict[str, Any]) -> str:
    """Extract and flatten grant information."""
    grants = []
    grant_list = paper.get("grantsList", {}).get("grant", [])
    if isinstance(grant_list, list):
        for grant in grant_list:
            if isinstance(grant, dict) and "agency" in grant:
                grants.append(grant["agency"])
    return "; ".join(grants) if grants else ""


def to_dataframe(papers: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert list of papers to pandas DataFrame.

    Parameters
    ----------
    papers : list[dict[str, Any]]
        List of paper dictionaries from Europe PMC API.

    Returns
    -------
    pd.DataFrame
        DataFrame with paper information.

    Examples
    --------
    >>> from pyeuropepmc.processing.analytics import to_dataframe
    >>> df = to_dataframe(papers)
    >>> print(df.head())
    """
    if not papers:
        return pd.DataFrame()

    df_data = []
    for paper in papers:
        try:
            row = {
                "id": paper.get("id"),
                "source": paper.get("source"),
                "title": paper.get("title", ""),
                "authorString": paper.get("authorString", ""),
                "journalTitle": _extract_journal_title(paper),
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
                "language": paper.get("language", ""),
                "pageInfo": paper.get("pageInfo", ""),
                "affiliation": paper.get("affiliation", ""),
                "meshTerms": _extract_mesh_terms(paper),
                "grants": _extract_grants(paper),
                "publisher": _extract_publisher(paper),
                "firstPublicationDate": paper.get("firstPublicationDate", ""),
                "hasReferences": paper.get("hasReferences", "N") == "Y",
                "hasTextMinedTerms": paper.get("hasTextMinedTerms", "N") == "Y",
                "hasDbCrossReferences": paper.get("hasDbCrossReferences", "N") == "Y",
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
    >>> from pyeuropepmc.processing.analytics import publication_year_distribution
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
    >>> from pyeuropepmc.processing.analytics import citation_statistics
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
    >>> from pyeuropepmc.processing.analytics import detect_duplicates
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
    >>> from pyeuropepmc.processing.analytics import remove_duplicates
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
        # keep should be "first" or "last"
        keep_value = "first" if keep not in ["first", "last"] else keep
        df = df.drop_duplicates(subset=subset_col, keep=cast(Any, keep_value))

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
    >>> from pyeuropepmc.processing.analytics import quality_metrics
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
        "peer_reviewed_percentage": (peer_reviewed_count / total * 100) if total > 0 else 0.0,
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
    >>> from pyeuropepmc.processing.analytics import publication_type_distribution
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
    >>> from pyeuropepmc.processing.analytics import journal_distribution
    >>> dist = journal_distribution(papers, top_n=15)
    >>> print(dist)
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "journalTitle" not in df.columns:
        return pd.Series(dtype=int)

    # Filter out empty, None, or invalid journal titles
    valid_journals = df["journalTitle"].str.strip()
    valid_journals = valid_journals[
        (valid_journals != "")
        & (valid_journals.notna())
        & (valid_journals.str.lower() != "journaltitle")  # Filter out literal "journalTitle"
        & (valid_journals.str.lower() != "journal title")  # Filter out variations
        & (valid_journals.str.len() > 2)  # Filter out very short titles
    ]

    return valid_journals.value_counts().head(top_n)


def author_statistics(
    papers: list[dict[str, Any]] | pd.DataFrame, top_n: int = 10
) -> dict[str, Any]:
    """
    Calculate author statistics from papers.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    top_n : int, default=10
        Number of top authors to return in statistics.

    Returns
    -------
    dict[str, Any]
        Dictionary containing author statistics:
        - total_authors: Total unique authors across all papers
        - total_author_mentions: Total author mentions (including duplicates)
        - avg_authors_per_paper: Average number of authors per paper
        - max_authors_per_paper: Maximum authors on a single paper
        - min_authors_per_paper: Minimum authors on a single paper
        - single_author_papers: Number of single-author papers
        - multi_author_papers: Number of multi-author papers
        - top_authors: Series with top N most prolific authors
        - author_collaboration_patterns: Dict with collaboration statistics

    Examples
    --------
    >>> from pyeuropepmc.processing.analytics import author_statistics
    >>> stats = author_statistics(papers, top_n=15)
    >>> print(f"Total authors: {stats['total_authors']}")
    >>> print(f"Average authors per paper: {stats['avg_authors_per_paper']:.1f}")
    >>> print("Top authors:")
    >>> print(stats['top_authors'])
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty or "authorString" not in df.columns:
        return {
            "total_authors": 0,
            "total_author_mentions": 0,
            "avg_authors_per_paper": 0.0,
            "max_authors_per_paper": 0,
            "min_authors_per_paper": 0,
            "single_author_papers": 0,
            "multi_author_papers": 0,
            "top_authors": pd.Series(dtype=int),
            "author_collaboration_patterns": {},
        }

    # Parse authors from authorString
    all_authors = []
    author_counts_per_paper = []

    for author_str in df["authorString"].dropna():
        if author_str and author_str.strip():
            # Split by comma and clean up
            authors = [author.strip() for author in str(author_str).split(",") if author.strip()]
            all_authors.extend(authors)
            author_counts_per_paper.append(len(authors))
        else:
            author_counts_per_paper.append(0)

    if not all_authors:
        return {
            "total_authors": 0,
            "total_author_mentions": 0,
            "avg_authors_per_paper": 0.0,
            "max_authors_per_paper": 0,
            "min_authors_per_paper": 0,
            "single_author_papers": 0,
            "multi_author_papers": 0,
            "top_authors": pd.Series(dtype=int),
            "author_collaboration_patterns": {},
        }

    # Calculate basic statistics
    total_author_mentions = len(all_authors)
    unique_authors = len(set(all_authors))
    avg_authors_per_paper = total_author_mentions / len(df) if len(df) > 0 else 0.0

    author_counts = pd.Series(author_counts_per_paper)
    max_authors = int(author_counts.max()) if not author_counts.empty else 0
    min_authors = int(author_counts.min()) if not author_counts.empty else 0

    single_author_papers = int((author_counts == 1).sum())
    multi_author_papers = int((author_counts > 1).sum())

    # Top authors
    author_freq = pd.Series(Counter(all_authors)).sort_values(ascending=False)
    top_authors = author_freq.head(top_n)

    # Collaboration patterns
    collaboration_patterns = {
        "solo_authors": int((author_counts == 1).sum()),
        "two_author_papers": int((author_counts == 2).sum()),
        "three_author_papers": int((author_counts == 3).sum()),
        "four_or_more_author_papers": int((author_counts >= 4).sum()),
        "avg_collaboration_size": (
            float(author_counts[author_counts > 1].mean()) if (author_counts > 1).any() else 0.0
        ),
    }

    return {
        "total_authors": unique_authors,
        "total_author_mentions": total_author_mentions,
        "avg_authors_per_paper": round(avg_authors_per_paper, 2),
        "max_authors_per_paper": max_authors,
        "min_authors_per_paper": min_authors,
        "single_author_papers": single_author_papers,
        "multi_author_papers": multi_author_papers,
        "top_authors": top_authors,
        "author_collaboration_patterns": collaboration_patterns,
    }


def geographic_analysis(
    papers: list[dict[str, Any]] | pd.DataFrame, top_n: int = 10
) -> dict[str, Any]:
    """
    Analyze geographic and institutional distributions from paper affiliations.

    Parameters
    ----------
    papers : list[dict[str, Any]] | pd.DataFrame
        List of papers or DataFrame with paper data.
    top_n : int, default=10
        Number of top countries/institutions to return.

    Returns
    -------
    dict[str, Any]
        Dictionary containing geographic and institutional statistics.

    Examples
    --------
    >>> from pyeuropepmc.processing.analytics import geographic_analysis
    >>> geo_stats = geographic_analysis(papers, top_n=15)
    >>> print(f"Top country: {geo_stats['top_countries'].index[0]}")
    """
    df = to_dataframe(papers) if isinstance(papers, list) else papers

    if df.empty:
        return _empty_geographic_result()

    total_papers = len(df)
    papers_with_affiliation = int(df["affiliation"].notna().sum())

    # Parse all affiliations
    parsed_data = _parse_all_affiliations(df["affiliation"].dropna())

    # Calculate distributions
    country_distribution = pd.Series(Counter(parsed_data["countries"])).sort_values(
        ascending=False
    )
    institution_distribution = pd.Series(Counter(parsed_data["institutions"])).sort_values(
        ascending=False
    )

    # Calculate international collaboration rate
    international_collaboration_rate = _calculate_collaboration_rate(
        parsed_data["multi_country_count"], papers_with_affiliation
    )

    return {
        "country_distribution": country_distribution,
        "institution_distribution": institution_distribution,
        "top_countries": country_distribution.head(top_n),
        "top_institutions": institution_distribution.head(top_n),
        "international_collaboration_rate": international_collaboration_rate,
        "papers_with_affiliation": papers_with_affiliation,
        "total_papers": total_papers,
    }


def _empty_geographic_result() -> dict[str, Any]:
    """Return empty result structure for geographic analysis."""
    empty_series = pd.Series(dtype=int)
    return {
        "country_distribution": empty_series,
        "institution_distribution": empty_series,
        "top_countries": empty_series,
        "top_institutions": empty_series,
        "international_collaboration_rate": 0.0,
        "papers_with_affiliation": 0,
        "total_papers": 0,
    }


def _parse_all_affiliations(affiliations: pd.Series) -> dict[str, Any]:
    """Parse affiliation strings to extract countries and institutions."""
    countries = []
    institutions = []
    multi_country_count = 0

    for affiliation_str in affiliations:
        if not affiliation_str or str(affiliation_str).strip() == "":
            continue

        paper_data = _parse_single_affiliation(affiliation_str)
        countries.extend(paper_data["countries"])
        institutions.extend(paper_data["institutions"])

        if len(paper_data["countries"]) > 1:
            multi_country_count += 1

    return {
        "countries": countries,
        "institutions": institutions,
        "multi_country_count": multi_country_count,
    }


def _parse_single_affiliation(affiliation_str: str) -> dict[str, list[str]]:
    """Parse a single affiliation string."""
    affiliations = _split_affiliations(affiliation_str)
    countries = set()
    institutions = []

    for aff in affiliations:
        country = _extract_country_from_affiliation(aff)
        if country:
            countries.add(country)

        institution = _extract_institution_from_affiliation(aff)
        if institution:
            institutions.append(institution)

    return {
        "countries": list(countries),
        "institutions": institutions,
    }


def _split_affiliations(affiliation_str: str) -> list[str]:
    """Split affiliation string into individual affiliations."""
    return [
        aff.strip() for aff in str(affiliation_str).replace("\n", ";").split(";") if aff.strip()
    ]


def _extract_country_from_affiliation(affiliation: str) -> str:
    """Extract country from a single affiliation string."""
    parts = [part.strip() for part in affiliation.split(",")]
    if len(parts) >= 2:
        country = parts[-1]
        return _normalize_country(country)
    return ""


def _extract_institution_from_affiliation(affiliation: str) -> str:
    """Extract institution from a single affiliation string."""
    # Remove email addresses
    affiliation = " ".join(word for word in affiliation.split() if "@" not in word)

    parts = [part.strip() for part in affiliation.split(",")]
    if not parts:
        return ""

    institution = parts[0]
    return _clean_institution_name(institution)


def _clean_institution_name(institution: str) -> str:
    """Clean and normalize institution name."""
    if not institution or len(institution) < 3:
        return ""

    # Remove common prefixes
    prefixes_to_remove = [
        "Department of",
        "Institute of",
        "Center for",
        "Centre for",
        "Laboratory of",
    ]
    for prefix in prefixes_to_remove:
        institution = institution.replace(prefix, "").strip()

    # Skip if it looks like a department only
    if institution.lower().startswith(("dept", "department", "lab")):
        return ""

    return institution


def _calculate_collaboration_rate(multi_country_count: int, total_with_affiliation: int) -> float:
    """Calculate international collaboration rate."""
    if total_with_affiliation == 0:
        return 0.0
    return round((multi_country_count / total_with_affiliation * 100), 2)


def _normalize_country(country: str) -> str:
    """Normalize country names for consistent analysis."""
    if not country:
        return ""

    country = country.strip().title()

    # Common country name mappings
    country_mappings = {
        "Usa": "United States",
        "Us": "United States",
        "U.S.A.": "United States",
        "U.S.": "United States",
        "America": "United States",
        "Uk": "United Kingdom",
        "U.K.": "United Kingdom",
        "England": "United Kingdom",
        "Scotland": "United Kingdom",
        "Wales": "United Kingdom",
        "Northern Ireland": "United Kingdom",
        "Deutschland": "Germany",
        "Italia": "Italy",
        "España": "Spain",
        "France": "France",
        "China": "China",
        "Japan": "Japan",
        "Canada": "Canada",
        "Australia": "Australia",
        "Netherlands": "Netherlands",
        "Sweden": "Sweden",
        "Norway": "Norway",
        "Denmark": "Denmark",
        "Finland": "Finland",
        "Switzerland": "Switzerland",
        "Austria": "Austria",
        "Belgium": "Belgium",
        "Portugal": "Portugal",
        "Ireland": "Ireland",
        "Poland": "Poland",
        "Czech Republic": "Czech Republic",
        "Hungary": "Hungary",
        "Greece": "Greece",
        "Turkey": "Turkey",
        "Israel": "Israel",
        "South Korea": "South Korea",
        "Brazil": "Brazil",
        "India": "India",
        "Russia": "Russia",
        "South Africa": "South Africa",
        "Mexico": "Mexico",
        "Argentina": "Argentina",
        "Chile": "Chile",
    }

    return country_mappings.get(country, country)


__all__ = [
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
]
