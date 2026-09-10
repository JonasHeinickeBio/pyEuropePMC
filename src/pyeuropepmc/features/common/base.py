"""
Common base class for API clients.

Provides shared infrastructure for HTTP session management, retries, caching,
and resource cleanup. This base class is designed to be inherited by specialized
clients for enrichment, search, and other API interactions.

Intended for use with external APIs (CrossRef, OpenAlex, PubMed, etc.).
For Europe PMC internal services, use `pyeuropepmc.core.base.BaseAPIClient` instead.
"""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig

logger = logging.getLogger(__name__)

__all__ = ["BaseHTTPClient", "BaseAPIClient"]


class BaseHTTPClient:
    """
    Common base class for API clients.

    Provides shared functionality including:
    - HTTP session management
    - Retry configuration via HTTPAdapter
    - Response caching
    - Context manager support
    - Resource cleanup

    This is a minimal base class focused on common infrastructure.
    Specialized clients should extend this with their specific functionality.

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
        Initialize the API client.

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

        # Configure retries for common transient errors
        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Initialize cache
        if cache_config is None:
            cache_config = CacheConfig(enabled=False)
        self._cache = CacheBackend(cache_config)

        logger.info(
            "%s initialized with cache %s",
            self.__class__.__name__,
            "enabled" if cache_config.enabled else "disabled",
        )

    def _set_email_header(self, email: str, header: str = "mailto") -> None:
        """
        Add email to headers for polite pool access.

        Many APIs (CrossRef, DataCite, OpenAlex) offer faster response times
        for requests that include an email address for contact purposes.

        Parameters
        ----------
        email : str
            Email address for polite pool
        header : str, optional
            Header name (default: 'mailto' for CrossRef, 'User-Agent' for DataCite/OpenAlex)
        """
        if email:
            if header == "User-Agent":
                # For APIs that include email in User-Agent
                current_ua = str(self.session.headers.get("User-Agent", ""))
                if email not in current_ua:
                    self.session.headers.update(
                        {"User-Agent": f"{current_ua.rstrip('; ')}; mailto:{email}"}
                    )
            else:
                # For APIs with dedicated email header
                self.session.headers.update({header: email})
            logger.info(f"Enabled polite pool with email: {email}")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BaseHTTPClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and clean up resources."""
        self.close()

    def close(self) -> None:
        """Close the client and release resources (idempotent)."""
        if self.session is not None:
            self.session.close()
        if self._cache:
            self._cache.close()


# Backward-compat alias: this class was originally named ``BaseAPIClient`` (it
# clashed with the unrelated ``pyeuropepmc.core.base.BaseAPIClient``).
BaseAPIClient = BaseHTTPClient
