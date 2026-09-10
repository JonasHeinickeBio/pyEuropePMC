"""
Base class for external API literature search clients.

Provides common functionality for all literature search clients including
rate limiting, error handling, caching, search functionality, and result normalization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time
from typing import Any, Literal, overload

import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.error_codes import ErrorCodes, format_error_message
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.common.base import BaseHTTPClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["BaseLiteratureClient"]


class BaseLiteratureClient(BaseHTTPClient, ABC):
    """
    Abstract base class for external API literature search clients.

    Provides common functionality including:
    - HTTP request handling with retries
    - Rate limiting
    - Response caching
    - Error handling and logging
    - Result normalization interface

    Subclasses must implement:
    - search() - perform search queries
    - get_paper() - get details for a single paper by identifier
    - _normalize_result() - normalize API response to standard format

    Attributes
    ----------
    base_url : str
        Base URL for the API
    rate_limit_delay : float
        Delay between requests in seconds
    timeout : int
        Request timeout in seconds
    """

    def __init__(
        self,
        base_url: str,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        user_agent: str | None = None,
        api_key_missing: bool = False,
    ) -> None:
        """
        Initialize the literature client.

        Parameters
        ----------
        base_url : str
            Base URL for the API
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration. If None, caching is disabled.
        user_agent : str, optional
            Custom User-Agent header. If None, uses default.
        api_key_missing : bool, optional
            Whether API key is missing (affects rate limiting behavior).
            If True, uses 3x more conservative rate limiting.
        """
        super().__init__(
            base_url=base_url,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
            user_agent=user_agent,
            api_key_missing=api_key_missing,
        )

    # ------------------------------------------------------------------
    # HTTP request
    # ------------------------------------------------------------------

    @overload
    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = ...,
        headers: dict[str, str] | None = ...,
        use_cache: bool = ...,
        response_format: Literal["json"] = ...,
    ) -> dict[str, Any] | None: ...

    @overload
    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = ...,
        headers: dict[str, str] | None = ...,
        use_cache: bool = ...,
        *,
        response_format: Literal["xml", "text"],
    ) -> str | None: ...

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
        response_format: str = "json",
    ) -> dict[str, Any] | str | None:
        """
        Make HTTP request with retries and caching.

        Parameters
        ----------
        endpoint : str
            API endpoint (will be appended to base_url).
        params : dict, optional
            Query parameters.
        headers : dict, optional
            Additional headers.
        use_cache : bool, optional
            Whether to use caching for this request (default: True).
        response_format : str, optional
            How to decode the response body (default: ``"json"``):

            - ``"json"`` — parse the body and return a ``dict``.
            - ``"xml"`` / ``"text"`` — return ``response.text`` verbatim as a
              ``str`` (no JSON parsing).  Used by sources whose APIs return
              XML/Atom feeds (arXiv, PubMed EFetch).

        Returns
        -------
        dict, str or None
            Parsed response (``dict`` for ``"json"``, ``str`` for
            ``"xml"``/``"text"``), or None if the request fails
            (e.g. 404 — resource not found is handled gracefully).

        Raises
        ------
        APIClientError
            If request fails after all retries (network,
            server error, etc.).
        """
        raw_text = response_format in ("xml", "text")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # ---- Check cache first ----
        cache_key = ""
        if use_cache and self._cache.config.enabled:
            cache_key = f"{url}:{str(params)}:{response_format}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", url)
                return cached  # type: ignore[no-any-return]

        # Prepare headers
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)

        # ---- Retry loop ----
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(
                    "GET %s params=%s attempt=%d/%d", url, params, attempt + 1, max_retries
                )
                response = self.session.get(
                    url, params=params, headers=request_headers, timeout=self.timeout
                )

                # 404 → graceful None (resource may not exist)
                if response.status_code == 404:
                    logger.info("Resource not found at %s", url)
                    return None

                # 429 → rate limited, retry with backoff
                if response.status_code == 429:
                    wait = self._handle_rate_limit(response, attempt, url)
                    time.sleep(min(wait, 60))
                    continue

                response.raise_for_status()

                # Decode body according to the requested format
                data: dict[str, Any] | str = response.text if raw_text else response.json()

                # Cache successful response
                if use_cache and self._cache.config.enabled:
                    self._cache.set(cache_key, data)

                logger.info("GET %s succeeded", url)
                return data

            except requests.HTTPError as e:
                # Retry on 429 inside except (Retry-After header)
                if e.response is not None and e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = int(retry_after)
                            logger.warning("Rate limited — waiting %ds", wait)
                            time.sleep(min(wait, 60))
                            continue
                        except ValueError:
                            pass

                # 404 in except (shouldn't happen, but handle)
                if e.response is not None and e.response.status_code == 404:
                    return None

                # Structured error with ErrorCodes
                status_code = e.response.status_code if e.response is not None else 0
                error_code = self._map_status_to_error_code(status_code)
                msg = format_error_message(
                    error_code,
                    context={"url": url, "endpoint": endpoint, "status_code": str(status_code)},
                )
                raise APIClientError(
                    error_code=error_code,
                    context={"url": url, "endpoint": endpoint},
                    message=msg,
                    endpoint=endpoint,
                    status_code=status_code,
                ) from e

            except requests.ConnectionError as e:
                raise APIClientError(
                    error_code=ErrorCodes.NET001,
                    context={"url": url, "error": str(e)},
                    message=format_error_message(ErrorCodes.NET001),
                    endpoint=endpoint,
                ) from e

            except requests.Timeout as e:
                raise APIClientError(
                    error_code=ErrorCodes.NET002,
                    context={"url": url, "timeout": str(self.timeout)},
                    message=format_error_message(ErrorCodes.NET002),
                    endpoint=endpoint,
                ) from e

            except ValueError as e:
                # JSON decode failure
                logger.error("Invalid JSON response from %s: %s", url, e)
                return None

            time.sleep(self.rate_limit_delay)

        # Exhausted retries
        msg = format_error_message(
            ErrorCodes.RETRY001,
            context={"url": url, "max_retries": str(max_retries)},
        )
        raise APIClientError(
            error_code=ErrorCodes.RETRY001,
            context={"url": url, "max_retries": max_retries},
            message=msg,
            endpoint=endpoint,
        )

    def _handle_rate_limit(
        self,
        response: requests.Response,
        attempt: int,
        url: str,
    ) -> float:
        """Compute wait time for a 429 response with exponential backoff."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        if self.api_key_missing:
            wait = (2**attempt) * max(1.0, self.rate_limit_delay * 3)
            logger.warning(
                "Rate limited (429) at %s. Using conservative backoff: waiting %.1fs", url, wait
            )
        else:
            wait = (2**attempt) * max(1.0, self.rate_limit_delay)
            logger.warning("Rate limited (429) at %s. Backoff: waiting %.1fs", url, wait)
        return wait

    @staticmethod
    def _map_status_to_error_code(status_code: int) -> ErrorCodes:
        """Map HTTP status to an ErrorCodes enum value."""
        mapping = {
            400: ErrorCodes.HTTP400,
            401: ErrorCodes.AUTH401,
            403: ErrorCodes.HTTP403,
            404: ErrorCodes.HTTP404,
            405: ErrorCodes.HTTP405,
            406: ErrorCodes.HTTP406,
            407: ErrorCodes.HTTP407,
            408: ErrorCodes.HTTP408,
            410: ErrorCodes.HTTP410,
            413: ErrorCodes.HTTP413,
            414: ErrorCodes.HTTP414,
            415: ErrorCodes.HTTP415,
            416: ErrorCodes.HTTP416,
            429: ErrorCodes.RATE429,
            500: ErrorCodes.HTTP500,
            501: ErrorCodes.HTTP501,
            502: ErrorCodes.HTTP502,
            503: ErrorCodes.HTTP503,
            504: ErrorCodes.HTTP504,
        }
        return mapping.get(status_code, ErrorCodes.API001)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search literature using the external API.

        Parameters
        ----------
        query : str
            Search query string
        limit : int, optional
            Maximum number of results (default: 25)
        sort : str, optional
            Sort order (e.g., 'date', 'relevance', 'citation')
        **kwargs
            Additional parameters specific to the API

        Returns
        -------
        list[LiteratureResult]
            List of search results as Pydantic models
        """
        raise NotImplementedError("Subclasses must implement search()")

    @abstractmethod
    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get paper details by identifier.

        Parameters
        ----------
        identifier : str
            Paper identifier (DOI, PMID, PMCID, or API-specific ID)
        **kwargs
            Additional parameters specific to the API

        Returns
        -------
        LiteratureResult or None
            Paper details as Pydantic model, or None if not found
        """
        raise NotImplementedError("Subclasses must implement get_paper()")

    def _normalize_result(self, raw_result: dict[str, Any]) -> LiteratureResult:
        """
        Normalize API response to standard format.

        Parameters
        ----------
        raw_result : dict
            Raw API response

        Returns
        -------
        LiteratureResult
            Normalized result as Pydantic model with standard fields:
            - doi: str | None
            - pmid: str | None
            - pmcid: str | None
            - title: str | None
            - authors: list[Author] | None
            - publication_year: int | None
            - journal: str | None
            - abstract: str | None
            - citation_count: int | None
            - source: str
            - source_id: str
        """
        raise NotImplementedError("Subclasses must implement _normalize_result()")

    # ------------------------------------------------------------------
    # Convenience: search / get + normalize (safe for both raw and
    # pre-normalized return values from search() / get_paper())
    # ------------------------------------------------------------------

    def search_and_normalize(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search and normalize results.

        Handles subclasses that already return ``LiteratureResult`` objects
        from ``search()`` (e.g. PubMedClient) as well as those that return
        raw dicts.

        Parameters
        ----------
        query : str
            Search query string
        limit : int, optional
            Maximum number of results (default: 25)
        sort : str, optional
            Sort order
        **kwargs
            Additional parameters

        Returns
        -------
        list[LiteratureResult]
            List of normalized results
        """
        raw_results = self.search(query=query, limit=limit, sort=sort, **kwargs)
        normalized: list[LiteratureResult] = []
        for result in raw_results:
            if isinstance(result, LiteratureResult):
                normalized.append(result)
            else:
                nr = self._normalize_result(result)
                if nr is not None:
                    normalized.append(nr)
        return normalized

    def get_paper_and_normalize(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get paper and normalize.

        Handles subclasses that already return a ``LiteratureResult``
        from ``get_paper()``.

        Parameters
        ----------
        identifier : str
            Paper identifier
        **kwargs
            Additional parameters

        Returns
        -------
        LiteratureResult or None
            Normalized paper details, or None if not found
        """
        raw_result = self.get_paper(identifier=identifier, **kwargs)
        if raw_result is None:
            return None
        if isinstance(raw_result, LiteratureResult):
            return raw_result
        return self._normalize_result(raw_result)
