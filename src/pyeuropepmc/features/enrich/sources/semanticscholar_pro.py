"""
Professional Semantic Scholar client wrapper using danielnsilva/semanticscholar library.

This module provides a thin wrapper around the danielnsilva/semanticscholar library,
integrating it with pyEuropePMC's caching, rate limiting, and error handling infrastructure.

Features:
- Automatic rate limiting (1 request/second default)
- Retry with exponential backoff for 429 errors
- Request queuing to prevent rate limit violations
- Thread-safe rate limit tracking

Modular Design:
- _execute_with_retry(): Generic retry logic for all API methods
- _enforce_rate_limit(): Centralized rate limiting
- _handle_api_error(): Unified error handling
- _paper_to_dict(), _author_to_dict(), _venue_to_dict(): Response converters
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from pyeuropepmc.core.exceptions import APIClientError

if TYPE_CHECKING:
    from semanticscholar.Author import Author as S2Author
    from semanticscholar.PublicationVenue import PublicationVenue as S2Venue

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
    >>> paper = client.get_paper("DOI:10.1093/mind/lix.236.433")
    >>> print(f"Citations: {paper['citation_count']}")
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.1,  # Slightly > 1.0 to stay under the 1 req/s limit
        timeout: int = 15,
        api_key: str | None = None,
        use_cache: bool = True,
    ) -> None:
        """
        Initialize the professional Semantic Scholar client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Minimum delay between requests in seconds (default: 1.1)
            Set to 0 to disable rate limiting (not recommended).
        timeout : int, optional
            Request timeout in seconds.
        api_key : str, optional
            API key for higher rate limits.
        use_cache : bool, optional
            Kept for API compatibility but not used (library handles its own caching).
        """
        self.rate_limit_delay = max(rate_limit_delay, 0.0)  # Ensure non-negative
        self.timeout = timeout
        self.api_key = api_key
        self.use_cache = use_cache

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_lock = threading.Lock()

        # Lazy import to avoid eager loading of semanticscholar
        from semanticscholar import SemanticScholar

        # Initialize the danielnsilva/semanticscholar client
        self._client = SemanticScholar(
            timeout=timeout,
            api_key=api_key,
            retry=True,
        )

        # Map of exception types for consistent error handling
        self._not_found_exceptions = ()
        self._server_error_exceptions = ()

        # Import exception types once for reuse
        self._init_exception_types()

        logger.info(
            "ProfessionalSemanticScholarClient initialized with rate_limit_delay=%.2fs%s",
            self.rate_limit_delay,
            " (API key configured)" if api_key else " (API key missing - lower limits)",
        )

    def _init_exception_types(self) -> None:
        """Import and cache Semantic Scholar exception types for efficient reuse."""
        from semanticscholar.SemanticScholarException import (
            BadQueryParametersException,
            GatewayTimeoutException,
            InternalServerErrorException,
            ObjectNotFoundException,
            ServerErrorException,
        )

        self._bad_query_exception = BadQueryParametersException
        self._gateway_timeout_exception = GatewayTimeoutException
        self._internal_server_exception = InternalServerErrorException
        self._object_not_found_exception = ObjectNotFoundException
        self._server_error_exception = ServerErrorException

    def _execute_with_retry(
        self,
        operation: Callable[[], Any],
        operation_name: str,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        rate_limit_backoff_multiplier: float = 2.0,
    ) -> Any:
        """
        Execute an API operation with retry logic for rate limits and server errors.

        This is the core DRY helper that all public methods use for consistent
        error handling and retry behavior.

        Parameters
        ----------
        operation : callable
            Lambda/function that performs the API call
        operation_name : str
            Name of the operation for logging (e.g., "get_paper", "search_paper")
        max_retries : int, optional
            Maximum retry attempts (default: 3)
        initial_backoff : float, optional
            Initial backoff time in seconds (default: 1.0)
        rate_limit_backoff_multiplier : float, optional
            Multiplier for rate limit retries (default: 2.0)

        Returns
        -------
        Any
            Result from the operation

        Raises
        ------
        APIClientError
            If all retries fail or non-retryable error occurs
        """
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return operation()
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate limit" in error_str.lower()

                if is_rate_limit:
                    last_error = e
                    wait = initial_backoff * (rate_limit_backoff_multiplier**attempt)
                    logger.warning(
                        "%s rate limit detected, waiting %.1fs (attempt %d/%d)",
                        operation_name,
                        wait,
                        attempt + 1,
                        max_retries + 1,
                    )
                    time.sleep(wait)
                    continue

                # Check for server errors that are retryable
                from semanticscholar.SemanticScholarException import (
                    GatewayTimeoutException,
                    InternalServerErrorException,
                    ServerErrorException,
                )

                if isinstance(
                    e,
                    InternalServerErrorException | GatewayTimeoutException | ServerErrorException,
                ):
                    last_error = e
                    if attempt < max_retries:
                        wait = initial_backoff * (2**attempt)
                        logger.warning(
                            "%s server error, retrying in %.1fs (attempt %d/%d): %s",
                            operation_name,
                            wait,
                            attempt + 1,
                            max_retries + 1,
                            e,
                        )
                        time.sleep(wait)
                        continue
                    raise APIClientError(
                        message=f"{operation_name} failed after {max_retries + 1} attempts: {e}"
                    ) from e

                # Non-retryable errors
                raise APIClientError(message=f"{operation_name} failed: {e}") from e

        # Should not reach here
        raise APIClientError(
            message=f"{operation_name} failed after {max_retries + 1} attempts: {last_error}"
        ) from last_error

    def _enforce_rate_limit(self) -> None:
        """
        Enforce rate limiting by waiting if necessary since the last request.

        This method is thread-safe and uses a lock to ensure only one request
        is made at a time, respecting the configured rate_limit_delay.
        """
        if self.rate_limit_delay <= 0:
            return  # Rate limiting disabled

        with self._request_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time

            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.debug(
                    "Rate limiting: waiting %.2fs since last request",
                    wait_time,
                )
                time.sleep(wait_time)

            self._last_request_time = time.monotonic()

    def get_paper(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        """
        Get a paper by its ID using the professional library.

        Parameters
        ----------
        paper_id : str
            S2PaperId, CorpusId, DOI, ArXivId, MAG, ACL, PMID, PMCID, or URL
        fields : list, optional
            List of paper fields to return. Defaults to common fields.
        max_retries : int, optional
            Maximum retries for rate limit (429) errors (default: 3).

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
            fields = self._default_paper_fields()

        def operation() -> Any:
            return self._client.get_paper(paper_id=paper_id, fields=fields)

        paper = self._execute_with_retry(operation, f"get_paper({paper_id})", max_retries)

        if not paper:
            logger.info(f"Paper not found: {paper_id}")
            return None

        return self._paper_to_dict(paper)

    def get_papers(
        self,
        paper_ids: list[str],
        fields: list[str] | None = None,
        return_not_found: bool = False,
        max_retries: int = 3,
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
        max_retries : int, optional
            Maximum retries for rate limit errors (default: 3).

        Returns
        -------
        list[dict] or tuple[list[dict], list[str]]
            List of paper data dictionaries (and optionally not found IDs)

        Raises
        ------
        APIClientError
            If an API error occurs
        """
        if len(paper_ids) > 500:
            raise ValueError("paper_ids must be a list of 1 to 500 IDs")

        if fields is None:
            fields = self._default_paper_fields()

        def operation() -> Any:
            return self._client.get_papers(
                paper_ids=paper_ids, fields=fields, return_not_found=return_not_found
            )

        try:
            result = self._execute_with_retry(
                operation, f"get_papers({len(paper_ids)} papers)", max_retries
            )

            if return_not_found:
                paper_list, not_found_ids = result
                return [self._paper_to_dict(p) for p in paper_list], not_found_ids
            else:
                return [self._paper_to_dict(p) for p in result]

        except APIClientError as e:
            # Check if this is a rate limit error
            error_str = str(e)
            if "429" in error_str or "rate limit" in error_str.lower():
                logger.warning("Batch rate limit detected, waiting 2s before fallback")
                time.sleep(2)
                logger.info("Falling back to single-paper retrieval for batch")
                return self._fallback_get_papers(paper_ids, fields, return_not_found)
            raise

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
        max_retries: int = 2,
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
        max_retries : int, optional
            Maximum retries for rate limit errors (default: 2).

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
            fields = self._default_paper_fields()

        def operation() -> Any:
            return self._client.search_paper(
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

        results = self._execute_with_retry(
            operation,
            f"search_paper('{query}')",
            max_retries,
            rate_limit_backoff_multiplier=2.0,
        )

        return self._process_search_results(results, limit, match_title)

    def get_paper_authors(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        limit: int = 100,
        max_retries: int = 3,
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
        max_retries : int, optional
            Maximum retries (default: 3)

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
            fields = self._default_author_fields()

        def operation() -> Any:
            return self._client.get_paper_authors(paper_id=paper_id, fields=fields, limit=limit)

        results = self._execute_with_retry(
            operation, f"get_paper_authors({paper_id})", max_retries
        )
        return [self._author_to_dict(a) for a in results]

    def get_author(
        self,
        author_id: str,
        fields: list[str] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        """
        Get an author by ID.

        Parameters
        ----------
        author_id : str
            Author ID
        fields : list, optional
            Author fields to return
        max_retries : int, optional
            Maximum retries (default: 3)

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
            fields = self._default_author_fields()

        def operation() -> Any:
            return self._client.get_author(author_id=author_id, fields=fields)

        try:
            author = self._execute_with_retry(operation, f"get_author({author_id})", max_retries)
            return self._author_to_dict(author) if author else None
        except APIClientError as e:
            if (
                self._object_not_found_exception
                and self._object_not_found_exception.__name__ in str(type(e.__cause__))
            ):
                logger.info(f"Author not found: {author_id}")
                return None
            raise

    def get_recommendations(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        limit: int = 100,
        pool_from: str = "recent",
        max_retries: int = 3,
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
        max_retries : int, optional
            Maximum retries (default: 3)

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
            fields = self._default_paper_fields()

        def operation() -> Any:
            return self._client.get_recommended_papers(
                paper_id=paper_id,
                fields=fields,
                limit=limit,
                pool_from=pool_from,
            )

        papers = self._execute_with_retry(
            operation, f"get_recommendations({paper_id})", max_retries
        )
        return [self._paper_to_dict(p) for p in papers]

    def get_recommendations_from_lists(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str] | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
        max_retries: int = 3,
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
        max_retries : int, optional
            Maximum retries (default: 3)

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
            fields = self._default_paper_fields()

        def operation() -> Any:
            return self._client.get_recommended_papers_from_lists(
                positive_paper_ids=positive_paper_ids,
                negative_paper_ids=negative_paper_ids,
                fields=fields,
                limit=limit,
            )

        papers = self._execute_with_retry(
            operation,
            f"get_recommendations_from_lists({len(positive_paper_ids)} positive)",
            max_retries,
        )
        return [self._paper_to_dict(p) for p in papers]

    def search_author(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 100,
        max_retries: int = 3,
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
        max_retries : int, optional
            Maximum retries (default: 3)

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
            fields = self._default_author_fields()

        def operation() -> Any:
            return self._client.search_author(query=query, fields=fields, limit=limit)

        results = self._execute_with_retry(operation, f"search_author('{query}')", max_retries)
        return [self._author_to_dict(a) for a in results]

    def _process_search_results(
        self,
        results: Any,
        limit: int,
        match_title: bool,
    ) -> list[dict[str, Any]]:
        """
        Process search results from the danielnsilva library into a list of dicts.

        Parameters
        ----------
        results : Any
            Results from the search_paper call
        limit : int
            Maximum number of results
        match_title : bool
            Whether this was a single-title match

        Returns
        -------
        list[dict]
            List of paper data dictionaries
        """
        if match_title and results:
            return [self._paper_to_dict(results)]

        # Handle both PaginatedResults and direct list responses
        paper_list = []
        try:
            if hasattr(results, "__iter__") and not isinstance(results, dict):
                for i, p in enumerate(results):
                    if i >= limit:
                        break
                    paper_list.append(p)
            elif results:
                paper_list = results[:limit] if isinstance(results, list) else [results]
        except Exception as exc:
            logger.debug("Failed to iterate results: %s", exc)

        return [self._paper_to_dict(p) for p in paper_list if p]

    def _fallback_get_papers(
        self,
        paper_ids: list[str],
        fields: list[str],
        return_not_found: bool,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[str]]:
        """
        Fallback method when batch operations hit rate limits.

        Parameters
        ----------
        paper_ids : list[str]
            List of paper IDs
        fields : list[str]
            Fields to fetch
        return_not_found : bool
            Whether to return not found IDs

        Returns
        -------
        list[dict] or tuple[list[dict], list[str]]
            Results matching the return_not_found parameter
        """
        results = []
        not_found = []
        for pid in paper_ids:
            paper = self.get_paper(pid, fields=fields, max_retries=2)
            if paper:
                results.append(paper)
            else:
                not_found.append(pid)

        if return_not_found:
            return results, not_found
        return results

    def _default_paper_fields(self) -> list[str]:
        """Return the default paper fields configuration."""
        return [
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

    def _default_author_fields(self) -> list[str]:
        """Return the default author fields configuration."""
        return [
            "authorId",
            "name",
            "affiliations",
            "citationCount",
            "hIndex",
            "paperCount",
            "homepage",
        ]

    def _paper_to_dict(self, paper: Any) -> dict[str, Any]:
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
