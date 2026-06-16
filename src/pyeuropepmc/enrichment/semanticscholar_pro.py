"""
Professional Semantic Scholar client wrapper using danielnsilva/semanticscholar library.

This module provides a thin wrapper around the danielnsilva/semanticscholar library,
integrating it with pyEuropePMC's caching, rate limiting, and error handling infrastructure.
"""

import logging
from typing import Any

from semanticscholar import SemanticScholar
from semanticscholar.Author import Author as S2Author
from semanticscholar.Paper import Paper as S2Paper
from semanticscholar.PublicationVenue import PublicationVenue as S2Venue
from semanticscholar.SemanticScholarException import (
    BadQueryParametersException,
    GatewayTimeoutException,
    InternalServerErrorException,
    ObjectNotFoundException,
)

from pyeuropepmc.core.exceptions import APIClientError

logger = logging.getLogger(__name__)

__all__ = ["ProfessionalSemanticScholarClient"]


class ProfessionalSemanticScholarClient:
    """
    Professional Semantic Scholar client using danielnsilva/semanticscholar library.

    This wrapper provides:
    - Typed response objects (Paper, Author, Venue)
    - Automatic retries with exponential backoff
    - Integration with pyEuropePMC's caching and rate limiting
    - Unified error handling

    Parameters
    ----------
    rate_limit_delay : float, optional
        Delay between requests in seconds (default: 1.0)
    timeout : int, optional
        Request timeout in seconds (default: 15)
    api_key : str, optional
        Semantic Scholar API key for higher rate limits
    use_cache : bool, optional
        Whether to use caching (default: True)

    Examples
    --------
    >>> client = ProfessionalSemanticScholarClient(api_key="your_key")
    >>> paper = client.get_paper("10.1093/mind/lix.236.433")
    >>> print(f"Citations: {paper.citationCount}")
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        api_key: str | None = None,
        use_cache: bool = True,
    ) -> None:
        """
        Initialize the professional Semantic Scholar client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Kept for API compatibility but not used (library handles rate limiting).
        timeout : int, optional
            Request timeout in seconds.
        api_key : str, optional
            API key for higher rate limits.
        use_cache : bool, optional
            Kept for API compatibility but not used (library handles its own caching).
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.api_key = api_key
        self.use_cache = use_cache

        # Initialize the danielnsilva/semanticscholar client
        self._client = SemanticScholar(
            timeout=timeout,
            api_key=api_key,
            retry=True,
        )

        # Fix: danielnsilva uses 'x-api-key' header but Semantic Scholar expects
        # 'Authorization: Bearer' - patch the _AsyncSemanticScholar.auth_header
        if api_key:
            self._client._AsyncSemanticScholar.auth_header = {"Authorization": f"Bearer {api_key}"}
            logger.debug("Patched auth_header to use 'Authorization: Bearer' format")

        # Track whether API key is missing for rate limiting decisions
        self.api_key_missing = not bool(api_key)

        debug_msg = (
            f"ProfessionalSemanticScholarClient initialized "
            f"(api_key_missing={self.api_key_missing})"
        )
        logger.debug(debug_msg)

    def get_paper(
        self,
        paper_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a paper by its ID using the professional library.

        Parameters
        ----------
        paper_id : str
            S2PaperId, CorpusId, DOI, ArXivId, MAG, ACL, PMID, PMCID, or URL
        fields : list, optional
            List of paper fields to return. Defaults to common fields.

        Returns
        -------
        dict or None
            Paper data as dictionary, or None if not found

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if fields is None:
            fields = [
                "abstract",
                "authors",
                "authors.affiliations",
                "authors.authorId",
                "authors.name",
                "citationCount",
                "externalIds",
                "fieldsOfStudy",
                "influentialCitationCount",
                "isOpenAccess",
                "journal",
                "openAccessPdf",
                "paperId",
                "publicationDate",
                "publicationTypes",
                "publicationVenue",
                "referenceCount",
                "s2FieldsOfStudy",
                "title",
                "url",
                "venue",
                "year",
            ]

        try:
            paper = self._client.get_paper(paper_id=paper_id, fields=fields)
            return self._paper_to_dict(paper) if paper else None

        except ObjectNotFoundException:
            logger.info(f"Paper not found: {paper_id}")
            return None
        except BadQueryParametersException as e:
            raise APIClientError(
                message=f"Invalid query parameters for paper {paper_id}: {e}"
            ) from e
        except (InternalServerErrorException, GatewayTimeoutException) as e:
            raise APIClientError(
                message=f"Semantic Scholar server error for paper {paper_id}: {e}"
            ) from e
        except Exception as e:
            raise APIClientError(message=f"Failed to retrieve paper {paper_id}: {e}") from e

    def get_papers(
        self,
        paper_ids: list[str],
        fields: list[str] | None = None,
        return_not_found: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[str]]:
        """
        Get multiple papers at once.

        Parameters
        ----------
        paper_ids : list[str]
            List of paper IDs (max 500)
        fields : list, optional
            List of paper fields to return
        return_not_found : bool, optional
            If True, return list of not found IDs as second element

        Returns
        -------
        list[dict] or tuple[list[dict], list[str]]
            List of paper data dictionaries

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if len(paper_ids) > 500:
            raise ValueError("paper_ids must be a list of 1 to 500 IDs")

        if fields is None:
            fields = [
                "paperId",
                "externalIds",
                "title",
                "citationCount",
                "influentialCitationCount",
                "year",
            ]

        try:
            papers = self._client.get_papers(
                paper_ids=paper_ids, fields=fields, return_not_found=return_not_found
            )

            if return_not_found:
                paper_list, not_found_ids = papers
                return [self._paper_to_dict(p) for p in paper_list], not_found_ids
            else:
                return [self._paper_to_dict(p) for p in papers]

        except Exception as e:
            raise APIClientError(message=f"Failed to retrieve papers: {e}") from e

    def search_paper(
        self,
        query: str,
        year: str | None = None,
        publication_types: list[str] | None = None,
        open_access_pdf: bool | None = None,
        venue: list[str] | None = None,
        fields_of_study: list[str] | None = None,
        fields: list[str] | None = None,
        publication_date_or_year: str | None = None,
        min_citation_count: int | None = None,
        limit: int = 100,
        sort: str | None = None,
        match_title: bool = False,
        bulk: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search for papers by keyword.

        Parameters
        ----------
        query : str
            Search query string
        year : str, optional
            Restrict to publication year
        publication_types : list, optional
            Restrict to publication types
        open_access_pdf : bool, optional
            Restrict to open access papers
        venue : list, optional
            Restrict to specific venues
        fields_of_study : list, optional
            Restrict to fields of study
        fields : list, optional
            Paper fields to return
        publication_date_or_year : str, optional
            Restrict to date range (YYYY-MM-DD:YYYY-MM-DD)
        min_citation_count : int, optional
            Minimum citation count filter
        limit : int, optional
            Maximum results (default: 100, max: 100)
        sort : str, optional
            Sort field:order (e.g., citationCount:desc)
        match_title : bool, optional
            Match exact title
        bulk : bool, optional
            Use bulk retrieval (faster, no relevance ranking, up to 10M results)

        Returns
        -------
        list[dict]
            List of matching paper data dictionaries

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if fields is None:
            fields = [
                "paperId",
                "externalIds",
                "title",
                "citationCount",
                "influentialCitationCount",
                "year",
            ]

        try:
            # The danielnsilva library's search_paper returns either:
            # - A single Paper object (if match_title=True)
            # - A PaginatedResults iterator (if match_title=False, default)
            results = self._client.search_paper(
                query=query,
                year=year,
                publication_types=publication_types,
                open_access_pdf=open_access_pdf,
                venue=venue,
                fields_of_study=fields_of_study,
                fields=fields,
                publication_date_or_year=publication_date_or_year,
                min_citation_count=min_citation_count,
                limit=limit,
                sort=sort,
                match_title=match_title,
                bulk=bulk,
            )

            if match_title and results:
                return [self._paper_to_dict(results)]
            else:
                # Handle both PaginatedResults and direct list responses
                # The library may return either depending on parameters
                if hasattr(results, "__iter__") and not isinstance(results, dict):
                    # Try to convert to list, but limit the number of pages
                    paper_list = []
                    try:
                        for i, p in enumerate(results):
                            if i >= limit:
                                break
                            paper_list.append(p)
                    except Exception as exc:
                        # If iteration fails, return empty list
                        logger.debug("Failed to iterate results: %s", exc)
                    return [self._paper_to_dict(p) for p in paper_list if p]
                else:
                    # results might be None or already a list
                    if results:
                        if isinstance(results, list):
                            return [self._paper_to_dict(p) for p in results if p]
                        else:
                            return [self._paper_to_dict(results)]
                    return []

        except Exception as e:
            raise APIClientError(message=f"Paper search failed for query '{query}': {e}") from e

    def get_paper_authors(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get authors for a paper.

        Parameters
        ----------
        paper_id : str
            Paper ID
        fields : list, optional
            Author fields to return
        limit : int, optional
            Maximum authors (default: 100)

        Returns
        -------
        list[dict]
            List of author data dictionaries

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        if fields is None:
            fields = [
                "authorId",
                "name",
                "affiliations",
                "citationCount",
                "hIndex",
                "homepage",
            ]

        try:
            results = self._client.get_paper_authors(paper_id=paper_id, fields=fields, limit=limit)
            return [self._author_to_dict(a) for a in results]

        except Exception as e:
            raise APIClientError(
                message=f"Failed to retrieve authors for paper {paper_id}: {e}"
            ) from e

    def get_author(
        self,
        author_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Get an author by ID.

        Parameters
        ----------
        author_id : str
            Author ID
        fields : list, optional
            Author fields to return

        Returns
        -------
        dict or None
            Author data dictionary, or None if not found

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if fields is None:
            fields = [
                "authorId",
                "name",
                "affiliations",
                "citationCount",
                "hIndex",
                "paperCount",
                "homepage",
            ]

        try:
            author = self._client.get_author(author_id=author_id, fields=fields)
            return self._author_to_dict(author) if author else None

        except ObjectNotFoundException:
            logger.info(f"Author not found: {author_id}")
            return None
        except Exception as e:
            raise APIClientError(message=f"Failed to retrieve author {author_id}: {e}") from e

    def get_recommendations(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        limit: int = 100,
        pool_from: str = "recent",
    ) -> list[dict[str, Any]]:
        """
        Get recommended papers for a given paper.

        Parameters
        ----------
        paper_id : str
            Paper ID to get recommendations for
        fields : list, optional
            Paper fields to return
        limit : int, optional
            Maximum recommendations (default: 100)
        pool_from : str, optional
            Source pool: "recent" or "all-cs"

        Returns
        -------
        list[dict]
            List of recommended paper data dictionaries

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        if pool_from not in ["recent", "all-cs"]:
            raise ValueError('pool_from must be "recent" or "all-cs"')

        if fields is None:
            fields = [
                "paperId",
                "externalIds",
                "title",
                "citationCount",
                "influentialCitationCount",
                "year",
            ]

        try:
            papers = self._client.get_recommended_papers(
                paper_id=paper_id,
                fields=fields,
                limit=limit,
                pool_from=pool_from,
            )
            return [self._paper_to_dict(p) for p in papers]

        except Exception as e:
            raise APIClientError(
                message=f"Failed to get recommendations for paper {paper_id}: {e}"
            ) from e

    def get_recommendations_from_lists(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str] | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get recommended papers based on positive/negative examples.

        Parameters
        ----------
        positive_paper_ids : list[str]
            Paper IDs that recommendations should be related to
        negative_paper_ids : list[str], optional
            Paper IDs that recommendations should NOT be related to
        fields : list, optional
            Paper fields to return
        limit : int, optional
            Maximum recommendations (default: 100)

        Returns
        -------
        list[dict]
            List of recommended paper data dictionaries

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        if fields is None:
            fields = [
                "paperId",
                "externalIds",
                "title",
                "citationCount",
                "influentialCitationCount",
                "year",
            ]

        try:
            papers = self._client.get_recommended_papers_from_lists(
                positive_paper_ids=positive_paper_ids,
                negative_paper_ids=negative_paper_ids,
                fields=fields,
                limit=limit,
            )
            return [self._paper_to_dict(p) for p in papers]

        except Exception as e:
            raise APIClientError(
                message=(
                    "Failed to get recommendations from lists: "
                    f"positive={positive_paper_ids}, negative={negative_paper_ids}: {e}"
                )
            ) from e

    def search_author(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search for authors by name.

        Parameters
        ----------
        query : str
            Author name search query
        fields : list, optional
            Author fields to return
        limit : int, optional
            Maximum results (default: 100)

        Returns
        -------
        list[dict]
            List of matching author data dictionaries

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        if fields is None:
            fields = [
                "authorId",
                "name",
                "affiliations",
                "citationCount",
                "hIndex",
                "paperCount",
            ]

        try:
            results = self._client.search_author(query=query, fields=fields, limit=limit)
            return [self._author_to_dict(a) for a in results]

        except Exception as e:
            raise APIClientError(message=f"Author search failed for query '{query}': {e}") from e

    def _paper_to_dict(self, paper: S2Paper) -> dict[str, Any]:
        """
        Convert S2Paper object to dictionary.

        Parameters
        ----------
        paper : S2Paper
            danielnsilva/semanticscholar Paper object

        Returns
        -------
        dict
            Paper data as dictionary
        """
        if not paper:
            return {}

        # Helper to safely get attribute
        def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
            try:
                return getattr(obj, attr, default)
            except (AttributeError, KeyError):
                return default

        result: dict[str, Any] = {
            "citation_count": safe_get(paper, "citationCount"),
            "influential_citation_count": safe_get(paper, "influentialCitationCount"),
            "abstract": safe_get(paper, "abstract"),
            "authors": [self._author_to_dict(a) for a in safe_get(paper, "authors", []) or []]
            if safe_get(paper, "authors")
            else [],
            "fields_of_study": safe_get(paper, "fieldsOfStudy"),
            "s2_paper_id": safe_get(paper, "paperId"),
            "external_ids": safe_get(paper, "externalIds") or {},
            "open_access_pdf_url": (
                safe_get(paper.openAccessPdf, "get", lambda x: None)("url")
                if safe_get(paper, "openAccessPdf")
                else None
            ),
            "publication_types": safe_get(paper, "publicationTypes"),
            "journal": self._venue_to_dict(safe_get(paper, "journal")),
            "tldr": (
                {"model": safe_get(paper.tldr, "model"), "text": safe_get(paper.tldr, "text")}
                if safe_get(paper, "tldr")
                else None
            ),
            "year": safe_get(paper, "year"),
            "title": safe_get(paper, "title"),
            "venue": safe_get(paper, "venue"),
            "url": safe_get(paper, "url"),
            "publication_date": (
                paper.publicationDate.strftime("%Y-%m-%d")
                if safe_get(paper, "publicationDate")
                else None
            ),
            "corpus_id": safe_get(paper, "corpusId"),
            "reference_count": safe_get(paper, "referenceCount"),
            "is_open_access": safe_get(paper, "isOpenAccess"),
        }

        # Filter out None values for cleaner output
        return {k: v for k, v in result.items() if v is not None}

    def _author_to_dict(self, author: S2Author) -> dict[str, Any]:
        """
        Convert S2Author object to dictionary.

        Parameters
        ----------
        author : S2Author
            danielnsilva/semanticscholar Author object

        Returns
        -------
        dict
            Author data as dictionary
        """
        if not author:
            return {}

        # Helper to safely get attribute
        def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
            try:
                return getattr(obj, attr, default)
            except (AttributeError, KeyError):
                return default

        result: dict[str, Any] = {
            "author_id": safe_get(author, "authorId"),
            "name": safe_get(author, "name"),
            "affiliations": safe_get(author, "affiliations"),
            "citation_count": safe_get(author, "citationCount"),
            "h_index": safe_get(author, "hIndex"),
            "paper_count": safe_get(author, "paperCount"),
            "homepage": safe_get(author, "homepage"),
            "url": safe_get(author, "url"),
        }

        # Filter out None values
        return {k: v for k, v in result.items() if v is not None}

    def _venue_to_dict(self, venue: S2Venue | None) -> dict[str, Any]:
        """
        Convert S2Venue or Journal object to dictionary.

        Parameters
        ----------
        venue : S2Venue or Journal or None
            danielnsilva/semanticscholar Venue object

        Returns
        -------
        dict
            Venue data as dictionary
        """
        if not venue:
            return {}

        # Handle Journal objects (different attributes than PublicationVenue)
        try:
            from semanticscholar.Journal import Journal

            if isinstance(venue, Journal):
                return {
                    "name": venue.name,
                    "volume": getattr(venue, "volume", None),
                    "pages": getattr(venue, "pages", None),
                }
        except ImportError:
            pass

        # Handle PublicationVenue objects
        result: dict[str, Any] = {
            "name": venue.name,
            "type": getattr(venue, "venueType", None),
            "issn": getattr(venue, "issn", None),
            "isbn": getattr(venue, "isbn", None),
            "url": getattr(venue, "url", None),
            "alternate_venues": getattr(venue, "alternateVenues", None),
            "citation_count": getattr(venue, "citationCount", None),
            "paper_count": getattr(venue, "paperCount", None),
            "paper_types": getattr(venue, "paperTypes", None),
            "references": getattr(venue, "references", None),
        }

        # Filter out None values
        return {k: v for k, v in result.items() if v is not None}
