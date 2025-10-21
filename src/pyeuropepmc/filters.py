"""
Filtering utilities for Europe PMC search results.

This module provides functions to filter and process Europe PMC API responses
based on quality criteria such as citations, publication year, article type,
MeSH terms, keywords, and abstract content.
"""

from typing import Any


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
    Filter Europe PMC search results based on quality criteria.

    This function filters papers based on various criteria including citations,
    publication year, article type, open access status, MeSH terms, keywords,
    and abstract content. It supports partial (substring) matching for MeSH terms,
    keywords, and abstract terms.

    Parameters
    ----------
    papers : list[dict[str, Any]]
        List of papers (dicts) from Europe PMC API response.
        Expected to be from response['resultList']['result'].
    min_citations : int, default=0
        Minimum number of citations required.
    min_pub_year : int, default=2010
        Minimum publication year.
    allowed_types : tuple[str, ...], optional
        Allowed study/article types. Default includes common high-quality types.
    open_access : str, default="Y"
        Filter for Open Access papers. Use "Y" for open access only,
        "N" for non-open access, or None to disable this filter.
    required_mesh : set[str] | None, default=None
        Set of required MeSH terms (case-insensitive partial matching).
        If None, no MeSH filtering is applied.
    required_keywords : set[str] | None, default=None
        Set of required keywords (case-insensitive partial matching).
        If None, no keyword filtering is applied.
    required_abstract_terms : set[str] | None, default=None
        Set of required terms in the abstract (case-insensitive partial matching).
        If None, no abstract filtering is applied.

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
    >>> # Filter with MeSH terms and keywords
    >>> filtered = filter_pmc_papers(
    ...     papers,
    ...     min_citations=5,
    ...     required_mesh={"neoplasms", "immunotherapy"},
    ...     required_keywords={"checkpoint", "inhibitor"}
    ... )
    >>>
    >>> # Filter with abstract terms
    >>> filtered = filter_pmc_papers(
    ...     papers,
    ...     required_abstract_terms={"efficacy", "safety", "clinical trial"}
    ... )
    """
    filtered_papers = []

    for paper in papers:
        # Skip if paper doesn't meet basic criteria
        if not _meets_basic_criteria(
            paper, min_citations, min_pub_year, max_pub_year, allowed_types, open_access
        ):
            continue

        # Skip if paper doesn't meet MeSH requirements
        if required_mesh and not _has_required_mesh(paper, required_mesh):
            continue

        # Skip if paper doesn't meet keyword requirements
        if required_keywords and not _has_required_keywords(paper, required_keywords):
            continue

        # Skip if paper doesn't meet abstract term requirements
        if required_abstract_terms and not _has_required_abstract_terms(
            paper, required_abstract_terms
        ):
            continue

        # Extract and add filtered paper metadata
        filtered_paper = _extract_paper_metadata(paper)
        filtered_papers.append(filtered_paper)

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
    Filter Europe PMC search results using OR logic for MeSH, keywords, and abstract terms.

    This function is similar to filter_pmc_papers, but a paper passes if it matches
    at least one required MeSH term, keyword, or abstract term (if provided).
    Other criteria (citations, year, type, open access) are still AND logic.

    Parameters
    ----------
    papers : list[dict[str, Any]]
        List of papers (dicts) from Europe PMC API response.
    min_citations : int, default=0
        Minimum number of citations required.
    min_pub_year : int, default=2010
        Minimum publication year.
    allowed_types : tuple[str, ...], optional
        Allowed study/article types.
    open_access : str, default="Y"
        Filter for Open Access papers. Use "Y" for open access only,
        "N" for non-open access, or None to disable this filter.
    required_mesh : set[str] | None, default=None
        Set of required MeSH terms (case-insensitive partial matching, OR logic).
    required_keywords : set[str] | None, default=None
        Set of required keywords (case-insensitive partial matching, OR logic).
    required_abstract_terms : set[str] | None, default=None
        Set of required terms in the abstract (case-insensitive partial matching, OR logic).

    Returns
    -------
    list[dict[str, Any]]
        List of filtered papers with selected metadata.
    """
    filtered_papers = []

    for paper in papers:
        if not _meets_basic_criteria(
            paper, min_citations, min_pub_year, max_pub_year, allowed_types, open_access
        ):
            continue

        # OR logic: if any of the required sets is provided, at least one must match
        mesh_ok = True
        if required_mesh is not None:
            mesh_ok = _has_any_required_mesh(paper, required_mesh)
        kw_ok = True
        if required_keywords is not None:
            kw_ok = _has_any_required_keywords(paper, required_keywords)
        abs_ok = True
        if required_abstract_terms is not None:
            abs_ok = _has_any_required_abstract_terms(paper, required_abstract_terms)

        # If any of the provided sets is not None, require at least one to match
        sets_provided = [
            s is not None for s in (required_mesh, required_keywords, required_abstract_terms)
        ]
        if any(sets_provided) and not (mesh_ok or kw_ok or abs_ok):
            continue

        filtered_paper = _extract_paper_metadata(paper)
        filtered_papers.append(filtered_paper)

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
    # Check citation count
    citation_count = int(paper.get("citedByCount", 0))
    if citation_count < min_citations:
        return False

    # Check publication year
    if not _meets_year_criteria(paper, min_pub_year, max_pub_year):
        return False

    # Check publication type
    if not _meets_type_criteria(paper, allowed_types):
        return False

    # Check open access status
    return _meets_access_criteria(paper, open_access)


def _meets_year_criteria(
    paper: dict[str, Any], min_pub_year: int, max_pub_year: int | None
) -> bool:
    """Check if paper meets publication year criteria (inclusive min/max).

    If no year data is present, the paper passes this check.
    """
    pub_year = paper.get("pubYear")
    if not pub_year:
        return True  # No year data, allow through

    try:
        year = int(pub_year)
        if year < min_pub_year:
            return False
        return not (max_pub_year is not None and year > max_pub_year)
    except (ValueError, TypeError):
        return False


def _meets_type_criteria(paper: dict[str, Any], allowed_types: tuple[str, ...]) -> bool:
    """Check if paper meets publication type criteria."""
    pub_type_list = paper.get("pubTypeList", {}).get("pubType", [])

    if not pub_type_list or not allowed_types:
        return True

    # Normalize to iterable of strings
    if isinstance(pub_type_list, str):
        pub_types = [pub_type_list]
    elif isinstance(pub_type_list, list | tuple | set):
        pub_types = list(pub_type_list)
    else:
        # Unknown type, fail conservatively
        return False

    return any(
        any(allowed.lower() in str(pt).lower() for allowed in allowed_types) for pt in pub_types
    )


def _meets_access_criteria(paper: dict[str, Any], open_access: str | None) -> bool:
    """Check if paper meets open access criteria."""
    if open_access is None:
        return True

    is_open_access = paper.get("isOpenAccess", "N")
    return bool(is_open_access == open_access)


def _has_required_mesh(paper: dict[str, Any], required_mesh: set[str]) -> bool:
    """
    Check if paper has all required MeSH terms (partial matching).

    Uses case-insensitive substring matching.
    """
    mesh_headings = paper.get("meshHeadingList", {}).get("meshHeading", [])
    if not mesh_headings:
        return False

    # Extract all MeSH descriptor names (lowercase for comparison)
    paper_mesh_terms = set()
    for heading in mesh_headings:
        if isinstance(heading, dict):
            descriptor = heading.get("descriptorName")
            if descriptor:
                paper_mesh_terms.add(descriptor.lower())
        elif isinstance(heading, str):
            paper_mesh_terms.add(heading.lower())

    # Check if all required MeSH terms are present (partial match)
    for required_term in required_mesh:
        required_lower = required_term.lower()
        # Check if any paper MeSH term contains the required term
        if not any(required_lower in mesh_term for mesh_term in paper_mesh_terms):
            return False

    return True


def _has_any_required_mesh(paper: dict[str, Any], required_mesh: set[str]) -> bool:
    """
    Check if paper has at least one required MeSH term (partial matching, OR logic).

    Uses case-insensitive substring matching.
    """
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


def _has_required_keywords(paper: dict[str, Any], required_keywords: set[str]) -> bool:
    """
    Check if paper has all required keywords (partial matching).

    Uses case-insensitive substring matching.
    """
    keyword_list = paper.get("keywordList", {}).get("keyword", [])
    if not keyword_list:
        return False

    # Extract all keywords (lowercase for comparison)
    paper_keywords = set()
    for keyword in keyword_list:
        if isinstance(keyword, str):
            paper_keywords.add(keyword.lower())
        elif isinstance(keyword, dict):
            # Sometimes keywords are nested in dicts
            kw_text = keyword.get("keyword") or keyword.get("text") or keyword.get("value")
            if kw_text:
                paper_keywords.add(str(kw_text).lower())

    # Check if all required keywords are present (partial match)
    for required_kw in required_keywords:
        required_lower = required_kw.lower()
        # Check if any paper keyword contains the required keyword
        if not any(required_lower in kw for kw in paper_keywords):
            return False

    return True


def _has_any_required_keywords(paper: dict[str, Any], required_keywords: set[str]) -> bool:
    """
    Check if paper has at least one required keyword (partial matching, OR logic).

    Uses case-insensitive substring matching.
    """
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


def _has_required_abstract_terms(paper: dict[str, Any], required_abstract_terms: set[str]) -> bool:
    """
    Check if paper abstract contains all required terms (partial matching).

    Uses case-insensitive substring matching.
    """
    abstract = paper.get("abstractText", "")
    if not abstract:
        return False

    abstract_lower = abstract.lower()

    # Check if all required terms are present in abstract (partial match)
    for required_term in required_abstract_terms:
        if required_term.lower() not in abstract_lower:
            return False

    return True


def _has_any_required_abstract_terms(
    paper: dict[str, Any], required_abstract_terms: set[str]
) -> bool:
    """
    Check if paper abstract contains at least one required term (partial matching, OR logic).

    Uses case-insensitive substring matching.
    """
    abstract = paper.get("abstractText", "")
    if not abstract:
        return False

    abstract_lower = abstract.lower()

    for required_term in required_abstract_terms:
        if required_term.lower() in abstract_lower:
            return True
    return False


def _extract_paper_metadata(paper: dict[str, Any]) -> dict[str, Any]:
    """Extract selected metadata from a paper."""
    authors = _extract_authors(paper)
    keywords = _extract_keywords(paper)
    mesh_terms = _extract_mesh_terms(paper)

    # Build filtered paper dict with selected metadata
    return {
        "title": paper.get("title", ""),
        "authors": authors,
        "pubYear": paper.get("pubYear"),
        # prefer pubTypeList['pubType'] when available
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


def _extract_authors(paper: dict[str, Any]) -> list[str]:
    """Extract author names from paper."""
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


def _extract_keywords(paper: dict[str, Any]) -> list[str]:
    """Extract keywords from paper."""
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


def _extract_mesh_terms(paper: dict[str, Any]) -> list[str]:
    """Extract MeSH terms from paper."""
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


__all__ = ["filter_pmc_papers", "filter_pmc_papers_or"]
