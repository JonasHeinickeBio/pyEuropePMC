"""
Base class for external API enrichment clients.

Provides common functionality for all enrichment clients including
rate limiting, error handling, caching, and request management.
"""

import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig
from pyeuropepmc.core.exceptions import APIClientError

logger = logging.getLogger(__name__)

__all__ = ["BaseEnrichmentClient"]


class BaseEnrichmentClient:
    """
    Base class for external API enrichment clients.

    Provides common functionality including:
    - HTTP request handling with retries
    - Rate limiting
    - Response caching
    - Error handling and logging

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
        Initialize the enrichment client.

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
        self.base_url = base_url.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.api_key_missing = api_key_missing
        self.session = requests.Session()

        # Set default user agent
        if user_agent is None:
            user_agent = "pyeuropepmc/1.12.0 (https://github.com/JonasHeinickeBio/pyEuropePMC)"
        self.session.headers.update({"User-Agent": user_agent})

        # Configure retries for common transient errors (excluding 429 which we handle explicitly)
        # 429 (rate limiting) is handled explicitly in the request methods to provide better
        # error messages and use the Retry-After header properly
        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],  # Transient server errors only
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1,
            raise_on_status=False,  # Don't raise on status codes, let us handle them
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Initialize cache
        if cache_config is None:
            cache_config = CacheConfig(enabled=False)
        self._cache = CacheBackend(cache_config)

        logger.info(
            f"{self.__class__.__name__} initialized with cache "
            f"{'enabled' if cache_config.enabled else 'disabled'}"
        )

    def __enter__(self) -> "BaseEnrichmentClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.close()

    def close(self) -> None:
        """Close the client and release resources."""
        if self.session:
            self.session.close()
        if self._cache:
            self._cache.close()

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any] | None:
        """
        Make HTTP GET request with retries and caching.

        Parameters
        ----------
        endpoint : str
            API endpoint (will be appended to base_url)
        params : dict, optional
            Query parameters
        headers : dict, optional
            Additional headers
        use_cache : bool, optional
            Whether to use caching for this request (default: True)

        Returns
        -------
        dict or None
            Response data as dictionary, or None if request fails

        Raises
        ------
        APIClientError
            If request fails after all retries
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Check cache first
        cache_key = ""
        if use_cache and self._cache.config.enabled:
            cache_key = f"{url}:{str(params)}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {url}")
                return cached  # type: ignore[no-any-return]

        # Prepare headers
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)

        # Retry logic with exponential backoff for 429 and transient errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"GET request to {url} with params={params}, attempt={attempt + 1}")
                response = self.session.get(
                    url, params=params, headers=request_headers, timeout=self.timeout
                )

                # Handle 404 gracefully - return None instead of raising
                if response.status_code == 404:
                    logger.info(f"Resource not found at {url}")
                    return None

                # Handle 403 - may need to retry without API key (for Semantic Scholar)
                if response.status_code == 403:
                    has_auth_header = "Authorization" in request_headers
                    has_x_api_key = "x-api-key" in request_headers

                    if (has_auth_header or has_x_api_key) and attempt == 0:
                        logger.warning(f"API key rejected for {url}; retrying without it")
                        # Remove auth header if present ( Semantic Scholar Bearer)
                        self.session.headers.pop("Authorization", None)
                        request_headers.pop("Authorization", None)
                        # Remove x-api-key if present (other services)
                        self.session.headers.pop("x-api-key", None)
                        request_headers.pop("x-api-key", None)
                        continue
                    else:
                        # No API key to remove or already retried - provide helpful error
                        logger.warning(
                            f"403 Forbidden for {url}. "
                            "This may indicate rate limiting due to lack of API key. "
                            "Consider: (1) Add SEMANTIC_SCHOLAR_API_KEY to environment, "
                            "(2) Increase rate_limit_delay, "
                            "(3) Add delays between requests"
                        )

                # Handle 429 rate limiting explicitly
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    retry_info = ""
                    wait = None

                    if retry_after:
                        try:
                            wait = int(retry_after)
                            retry_info = f" - Server requests waiting {wait}s before retry"
                        except ValueError:
                            try:
                                wait = round(float(retry_after))
                                retry_info = f" - Server requests waiting {wait}s before retry"
                            except ValueError:
                                retry_info = " - Retry-After header present but invalid format"

                    if wait is None:
                        # Use more conservative delay if API key is missing
                        if self.api_key_missing:
                            wait = (2**attempt) * max(1.0, self.rate_limit_delay * 3)
                            retry_info += f". Using exponential backoff: waiting {wait}s (conservative - no API key)"
                        else:
                            wait = (2**attempt) * max(1.0, self.rate_limit_delay)
                            retry_info += f". Using exponential backoff: waiting {wait}s"

                    error_msg = (
                        f"Rate limited (429) at {url}. "
                        f"Too many requests - Semantic Scholar API rate limit exceeded. "
                        f"Consider: (1) Increase rate_limit_delay in client initialization, "
                        f"(2) Add delays between search queries, "
                    )
                    if self.api_key_missing:
                        error_msg += (
                            "(3) Add SEMANTIC_SCHOLAR_API_KEY to environment for higher rate limits "
                            "(free API keys: 25k requests/month vs 100k for registered)"
                        )
                    else:
                        error_msg += "(3) Use API key for higher limits."
                    error_msg += f"{retry_info}"
                    logger.warning(error_msg)

                    # Wait before retrying
                    time.sleep(min(wait, 60))  # Cap at 60 seconds
                    continue

                response.raise_for_status()

                # Parse JSON response
                data = response.json()

                # Cache successful response
                if use_cache and self._cache.config.enabled:
                    self._cache.set(cache_key, data)

                logger.info(f"GET request to {url} succeeded")
                return data  # type: ignore[no-any-return]

            except requests.HTTPError as e:
                # Handle 429 from HTTPError if response is available
                if e.response is not None and e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    retry_info = ""
                    wait = None

                    if retry_after:
                        try:
                            wait = int(retry_after)
                            retry_info = f" - Server requests waiting {wait}s before retry"
                        except ValueError:
                            try:
                                wait = round(float(retry_after))
                                retry_info = f" - Server requests waiting {wait}s before retry"
                            except ValueError:
                                retry_info = " - Retry-After header present but invalid format"

                    if wait is None:
                        # Use more conservative delay if API key is missing
                        if self.api_key_missing:
                            wait = (2**attempt) * max(1.0, self.rate_limit_delay * 3)
                            retry_info += f". Using exponential backoff: waiting {wait}s (conservative - no API key)"
                        else:
                            wait = (2**attempt) * max(1.0, self.rate_limit_delay)
                            retry_info += f". Using exponential backoff: waiting {wait}s"

                    error_msg = (
                        f"Rate limited (429) at {url}. "
                        f"Too many requests - Semantic Scholar API rate limit exceeded. "
                        f"Consider: (1) Increase rate_limit_delay in client initialization, "
                        f"(2) Add delays between search queries, "
                    )
                    if self.api_key_missing:
                        error_msg += (
                            "(3) Add SEMANTIC_SCHOLAR_API_KEY to environment for higher rate limits "
                            "(free API keys: 25k requests/month vs 100k for registered)"
                        )
                    else:
                        error_msg += "(3) Use API key for higher limits."
                    error_msg += f"{retry_info}"
                    logger.warning(error_msg)

                    time.sleep(min(wait, 60))
                    continue

                if e.response is not None and e.response.status_code == 404:
                    logger.info(f"Resource not found at {url}")
                    return None

                status_code = e.response.status_code if e.response else "UNKNOWN"
                logger.error(f"HTTP error for {url}: Status {status_code} - {e}")
                raise APIClientError(message=f"HTTP {status_code} error for API: {e}") from e

            except requests.ConnectionError as e:
                logger.error(f"Connection error for {url}: {e}")
                raise APIClientError(
                    message=(
                        f"Failed to connect to API. "
                        f"Please check your internet connection and try again. "
                        f"Error: {e}"
                    )
                ) from e

            except requests.Timeout as e:
                logger.error(f"Request timeout for {url}: {e}")
                raise APIClientError(
                    message=(
                        f"Request timed out after {self.timeout}s. "
                        f"Consider increasing the timeout parameter. "
                        f"Error: {e}"
                    )
                ) from e

            except ValueError as e:
                logger.error(f"Invalid JSON response from {url}: {e}")
                return None

            # Rate limit delay between attempts
            time.sleep(self.rate_limit_delay)

        logger.error(f"Exceeded max retries ({max_retries}) for {url}")
        raise APIClientError(
            message=(
                f"Failed after {max_retries} attempts. "
                f"Semantic Scholar API may be experiencing issues or rate limiting. "
                f"Please wait before retrying."
            )
        )

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich paper metadata using the external API.

        This method should be implemented by subclasses.

        Parameters
        ----------
        identifier : str, optional
            Paper identifier (DOI, PMCID, or other)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters specific to the API

        Returns
        -------
        dict or None
            Enriched metadata or None if enrichment fails
        """
        raise NotImplementedError("Subclasses must implement enrich()")
