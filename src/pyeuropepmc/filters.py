"""
Filtering utilities for Europe PMC search results.

This module provides functions to filter and process Europe PMC API responses
based on quality criteria such as citations, publication year, article type,
MeSH terms, keywords, and abstract content.
"""

import logging
from typing import Any

logger = logging.getLogger("pyeuropepmc.filters")
logger.addHandler(logging.NullHandler())


def filter_pmc_papers(
    papers: list[dict[str, Any]],
    min_citations: int = 0,
    min_pub_year: int = 2000,
    max_pub_year: int | None = None,
    allowed_types: tuple[str, ...] = (
        "Review",
        "Clinical Trial",
        "Journal Article",
        "Case Reports",
        "research-article",
        "Systematic Review",
        "review-article",
        "Editorial",
        "Abstract",
        "Observational Study",
    ),
    open_access: str | None = "Y",
    required_mesh: set[str] | None = None,
    required_keywords: set[str] | None = None,
    required_abstract_terms: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Filter Europe PMC search results based on quality criteria using AND logic.

    This function filters papers based on various criteria including citations,
    publication year, article type, open access status, MeSH terms, keywords,
    and abstract content. All provided criteria must be satisfied (AND logic across
    criteria sets). Within each set (MeSH, keywords, abstract terms), ALL terms must
    be present (AND within set). It supports partial (substring) matching for MeSH
    terms, keywords, and abstract terms.

    Use this for strict multi-criteria filtering. For broader results matching any
    of several criteria, use filter_pmc_papers_or instead.

    Parameters
    ----------
    papers : list[dict[str, Any]]
        List of papers (dicts) from Europe PMC API response.
        Expected to be from response['resultList']['result'].
    min_citations : int, default=0
        Minimum number of citations required.
    min_pub_year : int, default=2000
        Minimum publication year.
    allowed_types : tuple[str, ...], optional
        Allowed study/article types. Default includes common high-quality types.
    open_access : str, default="Y"
        Filter for Open Access papers. Use "Y" for open access only,
        "N" for non-open access, or None to disable this filter.
    required_mesh : set[str] | None, default=None
        Set of required MeSH terms (case-insensitive partial matching).
        ALL terms must be present. If None, no MeSH filtering is applied.
    required_keywords : set[str] | None, default=None
        Set of required keywords (case-insensitive partial matching).
        ALL keywords must be present. If None, no keyword filtering is applied.
    required_abstract_terms : set[str] | None, default=None
        Set of required terms in the abstract (case-insensitive partial matching).
        ALL terms must be present. If None, no abstract filtering is applied.

    Returns
    -------
    list[dict[str, Any]]
        List of filtered papers with selected metadata including:
        - title: Paper title
        - authors: List of author names
        - pubYear: Publication year
        - pubType: Publication type(s)
        - isOpenAccess: Open access status
        - citedByCount: Number of citations
        - keywords: List of keywords (if available)
        - meshHeadings: List of MeSH terms (if available)
        - abstractText: Abstract text (if available)
        - id: Paper ID
        - source: Source database
        - doi: DOI (if available)
        - pmid: PubMed ID (if available)
        - pmcid: PMC ID (if available)

    Examples
    --------
    >>> from pyeuropepmc import SearchClient
    >>> from pyeuropepmc.filters import filter_pmc_papers
    >>>
    >>> client = SearchClient()
    >>> response = client.search("cancer AND therapy", resultType="core")
    >>> papers = response.get("resultList", {}).get("result", [])
    >>>
    >>> # Filter for high-quality review papers
    >>> filtered = filter_pmc_papers(
    ...     papers,
    ...     min_citations=10,
    ...     min_pub_year=2020,
    ...     allowed_types=("Review", "Systematic Review"),
    ...     open_access="Y"
    ... )
    >>>
    >>> # Filter with MeSH terms AND keywords (both must be present)
    >>> filtered = filter_pmc_papers(
    ...     papers,
    ...     min_citations=5,
    ...     required_mesh={"neoplasms", "immunotherapy"},
    ...     required_keywords={"checkpoint", "inhibitor"}
    ... )
    >>>
    >>> # Filter with abstract terms (all terms must be present)
    >>> filtered = filter_pmc_papers(
    ...     papers,
    ...     required_abstract_terms={"efficacy", "safety", "clinical trial"}
    ... )
    """
    filtered_papers = []
    for paper in papers:
        try:
            if not _meets_basic_criteria(
                paper, min_citations, min_pub_year, max_pub_year, allowed_types, open_access
            ):
                continue
            if required_mesh and not _has_required_mesh(paper, required_mesh):
                continue
            if required_keywords and not _has_required_keywords(paper, required_keywords):
                continue
            if required_abstract_terms and not _has_required_abstract_terms(
                paper, required_abstract_terms
            ):
                continue
            filtered_paper = _extract_paper_metadata(paper)
            filtered_papers.append(filtered_paper)
        except Exception as e:
            logger.exception(f"Error filtering paper with id={paper.get('id', None)}: {e}")
    return filtered_papers


def filter_pmc_papers_or(
    papers: list[dict[str, Any]],
    min_citations: int = 0,
    min_pub_year: int = 2000,
    max_pub_year: int | None = None,
    allowed_types: tuple[str, ...] = (
        "Review",
        "Clinical Trial",
        "Journal Article",
        "Case Reports",
        "research-article",
        "Systematic Review",
        "review-article",
        "Editorial",
        "Abstract",
        "Observational Study",
    ),
    open_access: str | None = "Y",
    required_mesh: set[str] | None = None,
    required_keywords: set[str] | None = None,
    required_abstract_terms: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Filter Europe PMC search results using OR logic across criteria sets.

    This function implements true OR logic: a paper passes if it matches ANY of the
    provided criteria sets (MeSH, keywords, or abstract terms). Within each set,
    at least one term must match (OR within set). Basic criteria (citations, year,
    type, open access) are still AND logic.

    Use this for broad inclusion when you want papers matching any of several topics.
    For stricter filtering requiring all criteria, use filter_pmc_papers instead.

    Parameters
    ----------
    papers : list[dict[str, Any]]
        List of papers (dicts) from Europe PMC API response.
    min_citations : int, default=0
        Minimum number of citations required.
    min_pub_year : int, default=2000
        Minimum publication year.
    allowed_types : tuple[str, ...], optional
        Allowed study/article types.
    open_access : str, default="Y"
        Filter for Open Access papers. Use "Y" for open access only,
        "N" for non-open access, or None to disable this filter.
    required_mesh : set[str] | None, default=None
        Set of MeSH terms (case-insensitive partial matching).
        Paper matches if it has at least one of these terms.
    required_keywords : set[str] | None, default=None
        Set of keywords (case-insensitive partial matching).
        Paper matches if it has at least one of these keywords.
    required_abstract_terms : set[str] | None, default=None
        Set of terms (case-insensitive partial matching).
        Paper matches if abstract contains at least one of these terms.

    Returns
    -------
    list[dict[str, Any]]
        List of filtered papers with selected metadata.

    Examples
    --------
    >>> # Papers about immunotherapy OR diabetes (broad inclusion)
    >>> filtered = filter_pmc_papers_or(
    ...     papers,
    ...     required_keywords={"immunotherapy", "diabetes"}
    ... )
    >>>
    >>> # Papers with checkpoint inhibitors (MeSH) OR efficacy (abstract)
    >>> filtered = filter_pmc_papers_or(
    ...     papers,
    ...     required_mesh={"checkpoint inhibitors"},
    ...     required_abstract_terms={"efficacy"}
    ... )
    """
    filtered_papers = []
    for paper in papers:
        try:
            if not _meets_basic_criteria(
                paper, min_citations, min_pub_year, max_pub_year, allowed_types, open_access
            ):
                continue
            # If no content filters are provided, include all papers that meet basic criteria
            if (
                required_mesh is None
                and required_keywords is None
                and required_abstract_terms is None
            ):
                filtered_paper = _extract_paper_metadata(paper)
                filtered_papers.append(filtered_paper)
                continue
            # OR logic: include if matches at least one of the provided criteria sets
            criteria_matched = False
            if required_mesh is not None and _has_any_required_mesh(paper, required_mesh):
                criteria_matched = True
            if required_keywords is not None and _has_any_required_keywords(
                paper, required_keywords
            ):
                criteria_matched = True
            if required_abstract_terms is not None and _has_any_required_abstract_terms(
                paper, required_abstract_terms
            ):
                criteria_matched = True
            if not criteria_matched:
                continue
            filtered_paper = _extract_paper_metadata(paper)
            filtered_papers.append(filtered_paper)
        except Exception as e:
            logger.exception(
                f"Error filtering paper (OR logic) with id={paper.get('id', None)}: {e}"
            )
    return filtered_papers


def _meets_basic_criteria(
    paper: dict[str, Any],
    min_citations: int,
    min_pub_year: int,
    max_pub_year: int | None,
    allowed_types: tuple[str, ...],
    open_access: str | None,
) -> bool:
    """Check if paper meets basic filtering criteria."""
    try:
        citation_count = int(paper.get("citedByCount", 0))
        if citation_count < min_citations:
            return False
        if not _meets_year_criteria(paper, min_pub_year, max_pub_year):
            return False
        if not _meets_type_criteria(paper, allowed_types):
            return False
        return _meets_access_criteria(paper, open_access)
    except Exception as e:
        logger.exception(f"Error in _meets_basic_criteria for paper id={paper.get('id')}: {e}")
        return False


def _meets_year_criteria(
    paper: dict[str, Any], min_pub_year: int, max_pub_year: int | None
) -> bool:
    """Check if paper meets publication year criteria (inclusive min/max).

    If no year data is present, the paper passes this check.
    """
    try:
        pub_year = paper.get("pubYear")
        if not pub_year:
            return True
        year = int(pub_year)
        if year < min_pub_year:
            return False
        return not (max_pub_year is not None and year > max_pub_year)
    except Exception as e:
        logger.exception(f"Error in _meets_year_criteria for paper id={paper.get('id')}: {e}")
        return False


def _meets_type_criteria(paper: dict[str, Any], allowed_types: tuple[str, ...]) -> bool:
    """Check if paper meets publication type criteria."""
    try:
        if not allowed_types:
            return True
        pub_types = []
        pub_type_list = paper.get("pubTypeList", {}).get("pubType", [])
        if isinstance(pub_type_list, str):
            pub_types.append(pub_type_list)
        elif isinstance(pub_type_list, list | tuple | set):
            pub_types.extend(pub_type_list)
        top_pub_type = paper.get("pubType")
        if top_pub_type:
            if isinstance(top_pub_type, str):
                pub_types.append(top_pub_type)
            elif isinstance(top_pub_type, list | tuple | set):
                pub_types.extend(top_pub_type)
        if not pub_types:
            # Only allow through if pubType is missing entirely
            return "pubTypeList" not in paper and "pubType" not in paper
        # If any pub_type is not a string, fail conservatively (matches test expectation)
        if any(not isinstance(pt, str) for pt in pub_types):
            return False
        allowed_lower = set(a.lower() for a in allowed_types)
        return any(isinstance(pt, str) and pt.lower() in allowed_lower for pt in pub_types)
    except Exception as e:
        logger.exception(f"Error in _meets_type_criteria for paper id={paper.get('id')}: {e}")
        return False


def _meets_access_criteria(paper: dict[str, Any], open_access: str | None) -> bool:
    """Check if paper meets open access criteria."""
    try:
        if open_access is None:
            return True
        is_open_access = paper.get("isOpenAccess", "N")
        return bool(is_open_access == open_access)
    except Exception as e:
        logger.exception(f"Error in _meets_access_criteria for paper id={paper.get('id')}: {e}")
        return False


def _has_required_mesh(paper: dict[str, Any], required_mesh: set[str]) -> bool:
    """
    Check if paper has all required MeSH terms (partial matching).

    Uses case-insensitive substring matching.
    """
    try:
        mesh_headings = paper.get("meshHeadingList", {}).get("meshHeading", [])
        if not mesh_headings:
            return False
        paper_mesh_terms = set()
        for heading in mesh_headings:
            if isinstance(heading, dict):
                descriptor = heading.get("descriptorName")
                if descriptor:
                    paper_mesh_terms.add(descriptor.lower())
            elif isinstance(heading, str):
                paper_mesh_terms.add(heading.lower())
        for required_term in required_mesh:
            required_lower = required_term.lower()
            if not any(required_lower in mesh_term for mesh_term in paper_mesh_terms):
                return False
        return True
    except Exception as e:
        logger.exception(f"Error in _has_required_mesh for paper id={paper.get('id')}: {e}")
        return False


def _has_any_required_mesh(paper: dict[str, Any], required_mesh: set[str]) -> bool:
    """
    Check if paper has at least one required MeSH term (partial matching, OR logic).

    Uses case-insensitive substring matching.
    """
    try:
        mesh_headings = paper.get("meshHeadingList", {}).get("meshHeading", [])
        if not mesh_headings:
            return False
        paper_mesh_terms = set()
        for heading in mesh_headings:
            if isinstance(heading, dict):
                descriptor = heading.get("descriptorName")
                if descriptor:
                    paper_mesh_terms.add(descriptor.lower())
            elif isinstance(heading, str):
                paper_mesh_terms.add(heading.lower())
        for required_term in required_mesh:
            required_lower = required_term.lower()
            if any(required_lower in mesh_term for mesh_term in paper_mesh_terms):
                return True
        return False
    except Exception as e:
        logger.exception(f"Error in _has_any_required_mesh for paper id={paper.get('id')}: {e}")
        return False


def _has_required_keywords(paper: dict[str, Any], required_keywords: set[str]) -> bool:
    """
    Check if paper has all required keywords (partial matching).

    Uses case-insensitive substring matching.
    """
    try:
        keyword_list = paper.get("keywordList", {}).get("keyword", [])
        if not keyword_list:
            return False
        paper_keywords = set()
        for keyword in keyword_list:
            if isinstance(keyword, str):
                paper_keywords.add(keyword.lower())
            elif isinstance(keyword, dict):
                kw_text = keyword.get("keyword") or keyword.get("text") or keyword.get("value")
                if kw_text:
                    paper_keywords.add(str(kw_text).lower())
        for required_kw in required_keywords:
            required_lower = required_kw.lower()
            if not any(required_lower in kw for kw in paper_keywords):
                return False
        return True
    except Exception as e:
        logger.exception(f"Error in _has_required_keywords for paper id={paper.get('id')}: {e}")
        return False


def _has_any_required_keywords(paper: dict[str, Any], required_keywords: set[str]) -> bool:
    """
    Check if paper has at least one required keyword (partial matching, OR logic).

    Uses case-insensitive substring matching.
    """
    try:
        keyword_list = paper.get("keywordList", {}).get("keyword", [])
        if not keyword_list:
            return False
        paper_keywords = set()
        for keyword in keyword_list:
            if isinstance(keyword, str):
                paper_keywords.add(keyword.lower())
            elif isinstance(keyword, dict):
                kw_text = keyword.get("keyword") or keyword.get("text") or keyword.get("value")
                if kw_text:
                    paper_keywords.add(str(kw_text).lower())
        for required_kw in required_keywords:
            required_lower = required_kw.lower()
            if any(required_lower in kw for kw in paper_keywords):
                return True
        return False
    except Exception as e:
        logger.exception(
            f"Error in _has_any_required_keywords for paper id={paper.get('id')}: {e}"
        )
        return False


def _has_required_abstract_terms(paper: dict[str, Any], required_abstract_terms: set[str]) -> bool:
    """
    Check if paper abstract contains all required terms (partial matching).

    Uses case-insensitive substring matching.
    """
    try:
        abstract = paper.get("abstractText", "")
        if not abstract:
            return False
        abstract_lower = abstract.lower()
        for required_term in required_abstract_terms:
            if required_term.lower() not in abstract_lower:
                return False
        return True
    except Exception as e:
        logger.exception(
            f"Error in _has_required_abstract_terms for paper id={paper.get('id')}: {e}"
        )
        return False


def _has_any_required_abstract_terms(
    paper: dict[str, Any], required_abstract_terms: set[str]
) -> bool:
    """
    Check if paper abstract contains at least one required term (partial matching, OR logic).

    Uses case-insensitive substring matching.
    """
    try:
        abstract = paper.get("abstractText", "")
        if not abstract:
            return False
        abstract_lower = abstract.lower()
        for required_term in required_abstract_terms:
            if required_term.lower() in abstract_lower:
                return True
        return False
    except Exception as e:
        logger.exception(
            f"Error in _has_any_required_abstract_terms for paper id={paper.get('id')}: {e}"
        )
        return False


def _extract_paper_metadata(paper: dict[str, Any]) -> dict[str, Any]:
    """Extract selected metadata from a paper."""
    try:
        authors = _extract_authors(paper)
        keywords = _extract_keywords(paper)
        mesh_terms = _extract_mesh_terms(paper)
        return {
            "title": paper.get("title", ""),
            "authors": authors,
            "pubYear": paper.get("pubYear"),
            "pubType": paper.get("pubTypeList", {}).get("pubType", []),
            "isOpenAccess": paper.get("isOpenAccess", "N"),
            "citedByCount": int(paper.get("citedByCount", 0)),
            "keywords": keywords,
            "meshHeadings": mesh_terms,
            "abstractText": paper.get("abstractText", ""),
            "id": paper.get("id"),
            "source": paper.get("source"),
            "doi": paper.get("doi"),
            "pmid": paper.get("pmid"),
            "pmcid": paper.get("pmcid"),
        }
    except Exception as e:
        logger.exception(f"Error extracting metadata for paper id={paper.get('id')}: {e}")
        return {}


def _extract_authors(paper: dict[str, Any]) -> list[str]:
    """Extract author names from paper."""
    try:
        authors = []
        author_list = paper.get("authorList", {}).get("author", [])
        for author in author_list:
            if isinstance(author, dict):
                full_name = author.get("fullName") or author.get("lastName", "")
                if full_name:
                    authors.append(full_name)
            elif isinstance(author, str):
                authors.append(author)
        return authors
    except Exception as e:
        logger.exception(f"Error extracting authors for paper id={paper.get('id')}: {e}")
        return []


def _extract_keywords(paper: dict[str, Any]) -> list[str]:
    """Extract keywords from paper."""
    try:
        keywords = []
        keyword_list = paper.get("keywordList", {}).get("keyword", [])
        for keyword in keyword_list:
            if isinstance(keyword, str):
                keywords.append(keyword)
            elif isinstance(keyword, dict):
                kw_text = keyword.get("keyword") or keyword.get("text") or keyword.get("value")
                if kw_text:
                    keywords.append(str(kw_text))
        return keywords
    except Exception as e:
        logger.exception(f"Error extracting keywords for paper id={paper.get('id')}: {e}")
        return []


def _extract_mesh_terms(paper: dict[str, Any]) -> list[str]:
    """Extract MeSH terms from paper."""
    try:
        mesh_terms = []
        mesh_headings = paper.get("meshHeadingList", {}).get("meshHeading", [])
        for heading in mesh_headings:
            if isinstance(heading, dict):
                descriptor = heading.get("descriptorName")
                if descriptor:
                    mesh_terms.append(descriptor)
            elif isinstance(heading, str):
                mesh_terms.append(heading)
        return mesh_terms
    except Exception as e:
        logger.exception(f"Error extracting mesh terms for paper id={paper.get('id')}: {e}")
        return []


__all__ = ["filter_pmc_papers", "filter_pmc_papers_or"]
