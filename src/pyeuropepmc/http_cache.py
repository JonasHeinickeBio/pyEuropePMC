"""
HTTP caching with requests-cache for PyEuropePMC.

This module provides protocol-correct HTTP caching with support for:
- ETag and Last-Modified headers
- Conditional GET requests (If-None-Match, If-Modified-Since)
- 304 Not Modified responses
- Cache-Control header handling
- Automatic cache expiration

Uses requests-cache for transparent HTTP caching with SQLite backend.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try to import requests-cache
try:
    import requests_cache
    REQUESTS_CACHE_AVAILABLE = True
except ImportError:
    REQUESTS_CACHE_AVAILABLE = False
    requests_cache = None


class HTTPCacheConfig:
    """
    Configuration for HTTP caching.
    
    Attributes
    ----------
    enabled : bool
        Whether HTTP caching is enabled
    cache_name : str
        Name/path for cache database
    backend : str
        Backend type ('sqlite', 'memory', 'filesystem', 'mongodb', 'redis')
    expire_after : int
        Default expiration in seconds
    allowable_codes : tuple
        HTTP status codes to cache
    allowable_methods : tuple
        HTTP methods to cache
    """
    
    def __init__(
        self,
        enabled: bool = True,
        cache_name: str = "pyeuropepmc_http_cache",
        backend: str = "sqlite",
        expire_after: int = 3600,  # 1 hour default
        allowable_codes: tuple[int, ...] = (200, 203, 300, 301, 304),
        allowable_methods: tuple[str, ...] = ("GET", "HEAD"),
        respect_cache_control: bool = True,
    ):
        """
        Initialize HTTP cache configuration.
        
        Parameters
        ----------
        enabled : bool, optional
            Enable HTTP caching (default: True)
        cache_name : str, optional
            Cache database name/path (default: 'pyeuropepmc_http_cache')
        backend : str, optional
            Cache backend (default: 'sqlite')
        expire_after : int, optional
            Default expiration in seconds (default: 3600 = 1 hour)
        allowable_codes : tuple, optional
            HTTP codes to cache (default: 200, 203, 300, 301, 304)
        allowable_methods : tuple, optional
            HTTP methods to cache (default: GET, HEAD)
        respect_cache_control : bool, optional
            Respect Cache-Control headers (default: True)
        """
        self.enabled = enabled and REQUESTS_CACHE_AVAILABLE
        self.cache_name = cache_name
        self.backend = backend
        self.expire_after = expire_after
        self.allowable_codes = allowable_codes
        self.allowable_methods = allowable_methods
        self.respect_cache_control = respect_cache_control
        
        if self.enabled and not REQUESTS_CACHE_AVAILABLE:
            logger.warning(
                "HTTP cache requested but requests-cache not available. "
                "Install with: pip install requests-cache"
            )
            self.enabled = False


class HTTPCache:
    """
    HTTP caching wrapper using requests-cache.
    
    Provides protocol-correct HTTP caching with automatic handling of:
    - ETags and Last-Modified headers
    - Conditional GET requests
    - 304 Not Modified responses
    - Cache-Control directives
    
    Example
    -------
    >>> from pyeuropepmc.http_cache import HTTPCache, HTTPCacheConfig
    >>> config = HTTPCacheConfig(expire_after=3600)
    >>> http_cache = HTTPCache(config)
    >>> 
    >>> # Create cached session
    >>> session = http_cache.get_session()
    >>> response = session.get("https://api.example.com/data")
    >>> print(f"From cache: {response.from_cache}")
    >>> 
    >>> # Conditional GET (automatically handled)
    >>> response2 = session.get("https://api.example.com/data")
    >>> print(f"Status: {response2.status_code}")  # May be 304
    """
    
    def __init__(self, config: HTTPCacheConfig):
        """
        Initialize HTTP cache.
        
        Parameters
        ----------
        config : HTTPCacheConfig
            Cache configuration
        """
        self.config = config
        self._session = None
        
        if self.config.enabled:
            self._initialize_session()
    
    def _initialize_session(self) -> None:
        """Initialize requests-cache session."""
        if not REQUESTS_CACHE_AVAILABLE:
            logger.warning("requests-cache not available, HTTP caching disabled")
            self.config.enabled = False
            return
        
        try:
            self._session = requests_cache.CachedSession(
                cache_name=self.config.cache_name,
                backend=self.config.backend,
                expire_after=self.config.expire_after,
                allowable_codes=self.config.allowable_codes,
                allowable_methods=self.config.allowable_methods,
                cache_control=self.config.respect_cache_control,
            )
            
            logger.info(
                f"HTTP cache initialized: {self.config.backend} backend, "
                f"expire_after={self.config.expire_after}s"
            )
        except Exception as e:
            logger.error(f"Failed to initialize HTTP cache: {e}")
            self.config.enabled = False
            self._session = None
    
    def get_session(self):
        """
        Get cached HTTP session.
        
        Returns
        -------
        requests_cache.CachedSession or None
            Cached session if available, None otherwise
        
        Examples
        --------
        >>> session = http_cache.get_session()
        >>> response = session.get("https://api.example.com/resource")
        >>> print(f"From cache: {response.from_cache}")
        """
        return self._session if self.config.enabled else None
    
    def is_enabled(self) -> bool:
        """
        Check if HTTP caching is enabled.
        
        Returns
        -------
        bool
            True if caching is enabled and available
        """
        return self.config.enabled and self._session is not None
    
    def clear(self) -> None:
        """Clear all cached HTTP responses."""
        if self._session:
            try:
                self._session.cache.clear()
                logger.info("HTTP cache cleared")
            except Exception as e:
                logger.error(f"Error clearing HTTP cache: {e}")
    
    def delete(self, *urls: str) -> None:
        """
        Delete specific URLs from cache.
        
        Parameters
        ----------
        *urls : str
            URLs to delete from cache
        
        Examples
        --------
        >>> http_cache.delete("https://api.example.com/resource1")
        >>> http_cache.delete(
        ...     "https://api.example.com/resource1",
        ...     "https://api.example.com/resource2"
        ... )
        """
        if self._session:
            try:
                for url in urls:
                    self._session.cache.delete(url=url)
                logger.debug(f"Deleted {len(urls)} URLs from HTTP cache")
            except Exception as e:
                logger.error(f"Error deleting from HTTP cache: {e}")
    
    def get_cache_size(self) -> dict[str, Any]:
        """
        Get HTTP cache statistics.
        
        Returns
        -------
        dict
            Cache statistics including response count and size
        """
        if not self._session:
            return {"enabled": False, "response_count": 0}
        
        try:
            # Get cache stats from backend
            cache = self._session.cache
            
            # Count responses in cache
            response_count = len(list(cache.responses.keys())) if hasattr(cache, 'responses') else 0
            
            return {
                "enabled": True,
                "backend": self.config.backend,
                "response_count": response_count,
                "expire_after": self.config.expire_after,
            }
        except Exception as e:
            logger.warning(f"Error getting HTTP cache stats: {e}")
            return {"enabled": True, "error": str(e)}
    
    def close(self) -> None:
        """Close HTTP cache session."""
        if self._session:
            try:
                self._session.close()
                logger.debug("HTTP cache session closed")
            except Exception as e:
                logger.warning(f"Error closing HTTP cache session: {e}")
            finally:
                self._session = None


def create_cached_session(
    cache_name: str = "pyeuropepmc_http",
    expire_after: int = 3600,
    backend: str = "sqlite",
) -> Any:
    """
    Create a cached HTTP session (convenience function).
    
    Parameters
    ----------
    cache_name : str, optional
        Cache database name (default: 'pyeuropepmc_http')
    expire_after : int, optional
        Default expiration in seconds (default: 3600)
    backend : str, optional
        Cache backend (default: 'sqlite')
    
    Returns
    -------
    requests_cache.CachedSession or requests.Session
        Cached session if available, regular session otherwise
    
    Examples
    --------
    >>> session = create_cached_session(expire_after=7200)
    >>> response = session.get("https://api.example.com/data")
    >>> print(f"From cache: {getattr(response, 'from_cache', False)}")
    """
    if not REQUESTS_CACHE_AVAILABLE:
        import requests
        logger.warning("requests-cache not available, using regular requests session")
        return requests.Session()
    
    try:
        return requests_cache.CachedSession(
            cache_name=cache_name,
            backend=backend,
            expire_after=expire_after,
            allowable_codes=(200, 203, 300, 301, 304),
            allowable_methods=("GET", "HEAD"),
        )
    except Exception as e:
        import requests
        logger.error(f"Failed to create cached session: {e}. Using regular session.")
        return requests.Session()


def conditional_get(session: Any, url: str, etag: str | None = None, last_modified: str | None = None) -> Any:
    """
    Perform conditional GET request with ETag/Last-Modified.
    
    Parameters
    ----------
    session : requests.Session or requests_cache.CachedSession
        HTTP session
    url : str
        URL to request
    etag : str, optional
        ETag value for If-None-Match header
    last_modified : str, optional
        Last-Modified value for If-Modified-Since header
    
    Returns
    -------
    requests.Response
        HTTP response (may be 304 Not Modified)
    
    Examples
    --------
    >>> session = create_cached_session()
    >>> response = conditional_get(
    ...     session,
    ...     "https://api.example.com/data",
    ...     etag='"abc123"',
    ...     last_modified="Wed, 12 Nov 2025 10:00:00 GMT"
    ... )
    >>> if response.status_code == 304:
    ...     print("Not modified, use cached version")
    >>> else:
    ...     print("Updated, new content available")
    """
    headers = {}
    
    if etag:
        headers["If-None-Match"] = etag
    
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    
    return session.get(url, headers=headers)


def is_cached_response(response: Any) -> bool:
    """
    Check if response came from cache.
    
    Parameters
    ----------
    response : requests.Response
        HTTP response
    
    Returns
    -------
    bool
        True if response came from cache
    
    Examples
    --------
    >>> response = session.get("https://api.example.com/data")
    >>> if is_cached_response(response):
    ...     print("Served from cache")
    >>> else:
    ...     print("Fetched from server")
    """
    return getattr(response, "from_cache", False)


def extract_cache_headers(response: Any) -> dict[str, str | None]:
    """
    Extract caching-related headers from response.
    
    Parameters
    ----------
    response : requests.Response
        HTTP response
    
    Returns
    -------
    dict
        Dictionary with ETag, Last-Modified, Cache-Control, Expires
    
    Examples
    --------
    >>> response = session.get("https://api.example.com/data")
    >>> headers = extract_cache_headers(response)
    >>> print(f"ETag: {headers['etag']}")
    >>> print(f"Last-Modified: {headers['last_modified']}")
    """
    return {
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "cache_control": response.headers.get("Cache-Control"),
        "expires": response.headers.get("Expires"),
    }
