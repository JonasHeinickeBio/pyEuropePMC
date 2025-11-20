"""
Base class for external API enrichment clients.

Provides common functionality for all enrichment clients including
rate limiting, error handling, caching, and request management.
"""

import logging
import time
from typing import Any

import backoff
import requests

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
        """
        self.base_url = base_url.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.session = requests.Session()

        # Set default user agent
        if user_agent is None:
            user_agent = "pyeuropepmc/1.12.0 (https://github.com/JonasHeinickeBio/pyEuropePMC)"
        self.session.headers.update({"User-Agent": user_agent})

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

    @backoff.on_exception(
        backoff.expo,
        (requests.ConnectionError, requests.Timeout, requests.HTTPError),
        max_tries=3,
        jitter=None,
        on_backoff=lambda details: logger.warning(
            f"Backing off {details.get('wait', 'unknown')}s after {details['tries']} tries"
        ),
    )
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

        try:
            logger.debug(f"GET request to {url} with params={params}")
            response = self.session.get(
                url, params=params, headers=request_headers, timeout=self.timeout
            )

            # Handle 404 gracefully - return None instead of raising
            if response.status_code == 404:
                logger.info(f"Resource not found at {url}")
                return None

            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Cache successful response
            if use_cache and self._cache.config.enabled:
                self._cache.set(cache_key, data)

            logger.info(f"GET request to {url} succeeded")
            return data  # type: ignore[no-any-return]

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.info(f"Resource not found at {url}")
                return None
            logger.error(f"HTTP error for {url}: {e}")
            raise APIClientError(message=f"HTTP error: {e}") from e
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise APIClientError(message=f"Request failed: {e}") from e
        except ValueError as e:
            logger.error(f"Invalid JSON response from {url}: {e}")
            return None
        finally:
            time.sleep(self.rate_limit_delay)

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
