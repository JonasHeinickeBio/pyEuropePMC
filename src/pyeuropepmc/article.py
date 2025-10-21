"""
ArticleClient for Europe PMC Articles RESTful API.

This module provides access to individual article operations including citations,
references, database links, and detailed article information.
"""

import logging
from typing import Any

from pyeuropepmc.base import BaseAPIClient
from pyeuropepmc.cache import CacheBackend, CacheConfig
from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import APIClientError, ValidationError
from pyeuropepmc.utils.helpers import warn_if_empty_hitcount

__all__ = ["ArticleClient"]


class ArticleClient(BaseAPIClient):
    """
    Client for individual article operations via Europe PMC Articles RESTful API.

    Provides methods to retrieve:
    - Article details and metadata
    - Citations of a publication
    - References from a publication
    - Database cross-references
    - Supplementary files
    - Lab links and data links

    Supports optional response caching to improve performance.
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize the ArticleClient.

        Args:
            rate_limit_delay: Delay between requests in seconds (default: 1.0)
            cache_config: Optional cache configuration. If None, caching is disabled.
        """
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.logger = logging.getLogger(__name__)

        # Initialize cache (disabled by default for backward compatibility)
        if cache_config is None:
            cache_config = CacheConfig(enabled=False)

        self._cache = CacheBackend(cache_config)
        cache_status = "enabled" if cache_config.enabled else "disabled"
        self.logger.info(f"ArticleClient initialized with cache {cache_status}")

    def get_article_details(
        self,
        source: str,
        article_id: str,
        result_type: str = "core",
        format: str = "json",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve detailed information for a specific article.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier
            result_type: Response type - 'idlist', 'lite', or 'core' (default: 'core')
            format: Response format - 'json', 'xml', or 'dc' (default: 'json')
            **kwargs: Additional query parameters

        Returns:
            Dict containing article details
        from pyeuropepmc.utils.helpers import warn_if_empty_hitcount
        Raises:
            ValidationError: If source or article_id are invalid
            APIClientError: If the API request fails

        Example:
            >>> client = ArticleClient()
            >>> details = client.get_article_details('MED', '25883711')
            >>> print(details['result']['title'])
        """
        self._validate_source_and_id(source, article_id)
        self._validate_result_type(result_type)
        self._validate_format(format)

        endpoint = f"article/{source}/{article_id}"
        params = {"resultType": result_type, "format": format, **kwargs}

        # Check cache first
        cache_key = f"article_details:{source}:{article_id}:{result_type}:{format}"
        try:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Cache hit for article details: {source}:{article_id}")
                return dict(cached_result)
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}. Proceeding with API request.")

        self.logger.info(f"Retrieving article details for {source}:{article_id}")

        try:
            response = self._get(endpoint, params=params)
            result = response.json()
            warn_if_empty_hitcount(result, context="article details")
            result_dict = dict(result)

            # Cache the result
            try:
                self._cache.set(cache_key, result_dict, tag="article_details")
            except Exception as e:
                self.logger.warning(f"Failed to cache article details: {e}")

            return result_dict
        except Exception as e:
            context = {"source": source, "article_id": article_id, "endpoint": endpoint}
            self.logger.error(f"Failed to retrieve article details for {source}:{article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_citations(
        self,
        source: str,
        article_id: str,
        page: int = 1,
        page_size: int = 25,
        format: str = "json",
        callback: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve publications that cite the given article.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier (returned as id element by search module)
            page: Page number for pagination, starting at 1 (default: 1)
            page_size: Number of citations per page (default: 25, max: 1000)
            format: Response format - 'json' or 'xml' (default: 'json')
            callback: JSONP callback function name for cross-domain requests
                (format must be 'json')
            **kwargs: Additional query parameters

        Returns:
            Dict containing citation information including count and list of citing papers

        Raises:
            ValidationError: If parameters are invalid
            APIClientError: If the API request fails

        Example:
            >>> client = ArticleClient()
            >>> citations = client.get_citations('MED', '29867326')
            >>> citation_list = citations.get('citationList', [])
            >>> print(f"Found {len(citation_list)} citations")

            # With JSONP callback
            >>> citations = client.get_citations('MED', '29867326', callback='myCallback')
        """
        self._validate_source_and_id(source, article_id)
        self._validate_pagination(page, page_size)
        self._validate_citations_format(format)
        self._validate_callback(callback, format)

        endpoint = f"{source}/{article_id}/citations"
        params = {"page": page, "pageSize": page_size, "format": format, **kwargs}

        if callback:
            params["callback"] = callback

        # Check cache first (skip caching for JSONP responses)
        cache_key = f"citations:{source}:{article_id}:{page}:{page_size}:{format}"
        if not callback:
            try:
                cached_result = self._cache.get(cache_key)
                if cached_result is not None:
                    self.logger.info(f"Cache hit for citations: {source}:{article_id}")
                    return dict(cached_result)
            except Exception as e:
                self.logger.warning(f"Cache lookup failed: {e}. Proceeding with API request.")

        # Detailed request logging
        full_url = f"{self.BASE_URL}{endpoint}"
        self.logger.info(f"Retrieving citations for {source}:{article_id}")
        self.logger.info(f"Request URL: {full_url}")
        self.logger.info(f"Request params: {params}")

        try:
            response = self._get(endpoint, params=params)
            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(f"Response headers: {dict(response.headers)}")

            # Handle JSONP responses (return raw text) vs JSON responses
            if callback:
                # JSONP response - return raw JavaScript code as text
                return {"jsonp_response": response.text}
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="citations")
                result_dict = dict(result)

                # Cache the result
                try:
                    self._cache.set(cache_key, result_dict, tag="citations")
                except Exception as e:
                    self.logger.warning(f"Failed to cache citations: {e}")

                return result_dict
        except Exception as e:
            context = {
                "source": source,
                "article_id": article_id,
                "endpoint": endpoint,
                "params": params,
            }
            self.logger.error(f"Failed to retrieve citations for {source}:{article_id}")
            self.logger.error(f"Error details: {str(e)}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_references(
        self,
        source: str,
        article_id: str,
        page: int = 1,
        page_size: int = 25,
        format: str = "json",
        callback: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve publications referenced by the given article.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier (returned as id element by search module)
            page: Page number for pagination, starting at 1 (default: 1)
            page_size: Number of references per page (default: 25, max: 1000)
            format: Response format - 'json' or 'xml' (default: 'json')
            callback: JSONP callback function name for cross-domain requests
                (format must be 'json')
            **kwargs: Additional query parameters

        Returns:
            Dict containing reference information including count and list of referenced papers

        Raises:
            ValidationError: If parameters are invalid
            APIClientError: If the API request fails

        Example:
            >>> client = ArticleClient()
            >>> references = client.get_references('MED', '29867326')
            >>> reference_list = references.get('referenceList', [])
            >>> print(f"Found {len(reference_list)} references")

            # With JSONP callback
            >>> references = client.get_references('MED', '29867326', callback='processRefs')
        """
        self._validate_source_and_id(source, article_id)
        self._validate_pagination(page, page_size)
        self._validate_citations_format(format)
        self._validate_callback(callback, format)

        endpoint = f"{source}/{article_id}/references"
        params = {"page": page, "pageSize": page_size, "format": format, **kwargs}

        if callback:
            params["callback"] = callback

        # Check cache first (skip caching for JSONP responses)
        cache_key = f"references:{source}:{article_id}:{page}:{page_size}:{format}"
        if not callback:
            try:
                cached_result = self._cache.get(cache_key)
                if cached_result is not None:
                    self.logger.info(f"Cache hit for references: {source}:{article_id}")
                    return dict(cached_result)
            except Exception as e:
                self.logger.warning(f"Cache lookup failed: {e}. Proceeding with API request.")

        self.logger.info(f"Retrieving references for {source}:{article_id}")

        try:
            response = self._get(endpoint, params=params)

            # Handle JSONP responses (return raw text) vs JSON responses
            if callback:
                # JSONP response - return raw JavaScript code as text
                return {"jsonp_response": response.text}
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="references")
                result_dict = dict(result)

                # Cache the result
                try:
                    self._cache.set(cache_key, result_dict, tag="references")
                except Exception as e:
                    self.logger.warning(f"Failed to cache references: {e}")

                return result_dict
        except Exception as e:
            context = {"source": source, "article_id": article_id, "endpoint": endpoint}
            self.logger.error(f"Failed to retrieve references for {source}:{article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_citation_count(self, source: str, article_id: str, **kwargs: Any) -> int:
        """
        Get the total number of citations for an article using hitCount from the API response.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier
            **kwargs: Additional query parameters

        Returns:
            Total citation count (int)
        """
        resp = self.get_citations(source, article_id, page=1, page_size=1, **kwargs)
        hit_count = resp.get("hitCount", 0)
        try:
            return int(hit_count)
        except Exception:
            return 0

    def get_reference_count(self, source: str, article_id: str, **kwargs: Any) -> int:
        """
        Get the total number of references for an article using hitCount from the API response.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier
            **kwargs: Additional query parameters

        Returns:
            Total reference count (int)
        """
        resp = self.get_references(source, article_id, page=1, page_size=1, **kwargs)
        hit_count = resp.get("hitCount", 0)
        try:
            return int(hit_count)
        except Exception:
            return 0

    def get_database_links(
        self,
        source: str,
        article_id: str,
        page: int = 1,
        page_size: int = 25,
        format: str = "json",
        callback: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve biological database records that cite the given article (cross-references).

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier (returned as id element by search module)
            page: Page number for pagination, starting at 1 (default: 1)
            page_size: Number of results per page (default: 25, max: 1000)
            format: Response format - 'json' or 'xml' (default: 'json')
            callback: JSONP callback function name for cross-domain requests
                (format must be 'json')
            **kwargs: Additional query parameters

        Returns:
            Dict containing database link information

        Raises:
            ValidationError: If parameters are invalid
            APIClientError: If the API request fails

        Example:
            >>> client = ArticleClient()
            >>> db_links = client.get_database_links('MED', '25883711')
            >>> cross_refs = db_links.get('dbCrossReferenceList', {}).get('dbCrossReference', [])
            >>> for link in cross_refs:
            ...     print(f"{link['dbName']}: {link['info1']}")
        """
        self._validate_source_and_id(source, article_id)
        self._validate_pagination(page, page_size)
        self._validate_citations_format(format)
        self._validate_callback(callback, format)

        endpoint = f"{source}/{article_id}/databaseLinks"
        params = {"page": page, "pageSize": page_size, "format": format, **kwargs}

        if callback:
            params["callback"] = callback

        self.logger.info(f"Retrieving database links for {source}:{article_id}")

        try:
            response = self._get(endpoint, params=params)

            # Handle JSONP responses (return raw text) vs JSON responses
            if callback:
                # JSONP response - return raw JavaScript code as text
                return {"jsonp_response": response.text}
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="database links")
                return dict(result)
        except Exception as e:
            context = {"source": source, "article_id": article_id, "endpoint": endpoint}
            self.logger.error(f"Failed to retrieve database links for {source}:{article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_supplementary_files(
        self, article_id: str, include_inline_image: bool = True, **kwargs: Any
    ) -> bytes:
        """
        Retrieve supplementary files for an article (returns ZIP format).

        Note: Only available for Open Access articles with supplementary files.
        All full text publications have external IDs starting 'PMC_'.

        Args:
            article_id: Publication identifier (PMC ID, e.g., 'PMC3258128')
            include_inline_image: Include inline images in ZIP file (default: True)
            **kwargs: Additional query parameters

        Returns:
            bytes: ZIP file content containing supplementary files

        Raises:
            ValidationError: If article_id is invalid
            APIClientError: If the API request fails or files not available

        Example:
            >>> client = ArticleClient()
            >>> zip_content = client.get_supplementary_files('PMC3258128')
            >>> with open('supplementary.zip', 'wb') as f:
            ...     f.write(zip_content)

            # Exclude inline images
            >>> zip_content = client.get_supplementary_files('PMC3258128',
            ...                                             include_inline_image=False)
        """
        if not article_id or not isinstance(article_id, str):
            raise ValidationError(
                ErrorCodes.VALID001, field_name="article_id", actual_value=article_id
            )

        endpoint = f"{article_id}/supplementaryFiles"
        params = {"includeInlineImage": str(include_inline_image).lower(), **kwargs}

        self.logger.info(f"Retrieving supplementary files for {article_id}")

        try:
            response = self._get(endpoint, params=params, stream=True)
            if response.status_code == 404:
                context = {"article_id": article_id, "endpoint": endpoint}
                self.logger.error(f"Supplementary files not found for {article_id}")
                raise APIClientError(ErrorCodes.HTTP404, context)
            response.raise_for_status()
            content = response.content
            return bytes(content) if isinstance(content, bytes | bytearray) else b""
        except Exception as e:
            context = {"article_id": article_id, "endpoint": endpoint}
            self.logger.error(f"Failed to retrieve supplementary files for {article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_lab_links(
        self,
        source: str,
        article_id: str,
        provider_id: str | None = None,
        format: str = "json",
        callback: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve external links provided by 3rd parties for the given article.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier (returned as id element by search module)
            provider_id: Optional specific external content provider ID
            format: Response format - 'json' or 'xml' (default: 'json')
            callback: JSONP callback function name for cross-domain requests
                (format must be 'json')
            **kwargs: Additional query parameters

        Returns:
            Dict containing lab links information

        Raises:
            ValidationError: If parameters are invalid
            APIClientError: If the API request fails

        Example:
            >>> client = ArticleClient()
            >>> lab_links = client.get_lab_links('MED', '25883711')
        """
        self._validate_source_and_id(source, article_id)
        self._validate_citations_format(format)
        self._validate_callback(callback, format)

        endpoint = f"{source}/{article_id}/labsLinks"
        params = {"format": format, **kwargs}

        if provider_id:
            params["providerId"] = provider_id

        if callback:
            params["callback"] = callback

        self.logger.info(f"Retrieving lab links for {source}:{article_id}")

        try:
            response = self._get(endpoint, params=params)

            # Handle JSONP responses (return raw text) vs JSON responses
            if callback:
                # JSONP response - return raw JavaScript code as text
                return {"jsonp_response": response.text}
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="lab links")
                return dict(result)
        except Exception as e:
            context = {"source": source, "article_id": article_id, "endpoint": endpoint}
            self.logger.error(f"Failed to retrieve lab links for {source}:{article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_data_links(
        self,
        source: str,
        article_id: str,
        format: str = "json",
        callback: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve consolidated data-literature links in Scholix format.

        Consolidates databaseLinks, labsLinks and textMinedTerms in one service.

        Args:
            source: Three letter code representing the data source (e.g., 'MED', 'PMC', 'PPR')
            article_id: Publication identifier (returned as id element by search module)
            format: Response format - 'json' or 'xml' (default: 'json')
            callback: JSONP callback function name for cross-domain requests
                (format must be 'json')
            **kwargs: Additional query parameters

        Returns:
            Dict containing consolidated data links in Scholix format

        Raises:
            ValidationError: If parameters are invalid
            APIClientError: If the API request fails

        Example:
            >>> client = ArticleClient()
            >>> data_links = client.get_data_links('MED', '25883711')
        """
        self._validate_source_and_id(source, article_id)
        self._validate_citations_format(format)
        self._validate_callback(callback, format)

        endpoint = f"{source}/{article_id}/datalinks"
        params = {"format": format, **kwargs}

        if callback:
            params["callback"] = callback

        self.logger.info(f"Retrieving data links for {source}:{article_id}")

        try:
            response = self._get(endpoint, params=params)

            # Handle JSONP responses (return raw text) vs JSON responses
            if callback:
                # JSONP response - return raw JavaScript code as text
                return {"jsonp_response": response.text}
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="data links")
                return dict(result)
        except Exception as e:
            context = {"source": source, "article_id": article_id, "endpoint": endpoint}
            self.logger.error(f"Failed to retrieve data links for {source}:{article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    # Validation helper methods

    def _validate_source_and_id(self, source: str, article_id: str) -> None:
        """Validate source and article_id parameters."""
        if not source or not isinstance(source, str) or len(source) != 3:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="source",
                actual_value=source,
                message="Source must be a 3-letter string (e.g., 'MED', 'PMC', 'PPR')",
            )

        if not article_id or not isinstance(article_id, str):
            raise ValidationError(
                ErrorCodes.VALID001, field_name="article_id", actual_value=article_id
            )

    # Cache Management Methods

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict containing cache stats (size, eviction stats, etc.)

        Example:
            >>> client = ArticleClient(cache_config=CacheConfig(enabled=True))
            >>> stats = client.get_cache_stats()
            >>> print(f"Cache size: {stats['size']} bytes")
        """
        try:
            return self._cache.get_stats()
        except Exception as e:
            self.logger.warning(f"Failed to get cache stats: {e}")
            return {}

    def get_cache_health(self) -> dict[str, Any]:
        """
        Get cache health status.

        Returns:
            Dict containing cache health metrics (hit rate, miss rate, errors)

        Example:
            >>> client = ArticleClient(cache_config=CacheConfig(enabled=True))
            >>> health = client.get_cache_health()
            >>> print(f"Cache hit rate: {health['hit_rate']:.2%}")
        """
        try:
            return self._cache.get_health()
        except Exception as e:
            self.logger.warning(f"Failed to get cache health: {e}")
            return {}

    def clear_cache(self) -> bool:
        """
        Clear all cached data.

        Returns:
            True if cache was cleared successfully, False otherwise

        Example:
            >>> client = ArticleClient(cache_config=CacheConfig(enabled=True))
            >>> client.clear_cache()
            True
        """
        try:
            return self._cache.clear()
        except Exception as e:
            self.logger.warning(f"Failed to clear cache: {e}")
            return False

    def invalidate_article_cache(
        self, source: str | None = None, article_id: str | None = None
    ) -> int:
        """
        Invalidate cached article data matching the pattern.

        Args:
            source: Optional source filter (e.g., 'MED', 'PMC')
            article_id: Optional article ID filter

        Returns:
            Number of cache entries invalidated

        Example:
            >>> client = ArticleClient(cache_config=CacheConfig(enabled=True))
            >>> # Clear cache for specific article
            >>> count = client.invalidate_article_cache(source='MED', article_id='12345')
            >>> # Clear cache for all MED articles
            >>> count = client.invalidate_article_cache(source='MED')
            >>> # Clear all article cache
            >>> count = client.invalidate_article_cache()
        """
        try:
            if source and article_id:
                pattern = f"*:{source}:{article_id}:*"
            elif source:
                pattern = f"*:{source}:*"
            else:
                pattern = "*"

            return self._cache.invalidate_pattern(pattern)
        except Exception as e:
            self.logger.warning(f"Failed to invalidate article cache: {e}")
            return 0

    def close(self) -> None:
        """
        Close the client and cleanup resources including cache.

        Example:
            >>> client = ArticleClient(cache_config=CacheConfig(enabled=True))
            >>> # ... use client ...
            >>> client.close()
        """
        try:
            self._cache.close()
        except Exception as e:
            self.logger.warning(f"Error closing cache: {e}")

    # Validation Methods

    def _validate_result_type(self, result_type: str) -> None:
        """Validate result_type parameter."""
        valid_types = {"idlist", "lite", "core"}
        if result_type not in valid_types:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="result_type",
                actual_value=result_type,
                message=f"result_type must be one of: {', '.join(valid_types)}",
            )

    def _validate_format(self, format: str) -> None:
        """Validate format parameter."""
        valid_formats = {"json", "xml", "dc"}
        if format not in valid_formats:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="format",
                actual_value=format,
                message=f"format must be one of: {', '.join(valid_formats)}",
            )

    def _validate_pagination(self, page: int, page_size: int) -> None:
        """Validate pagination parameters."""
        if not isinstance(page, int) or page < 1:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="page",
                actual_value=page,
                message="page must be a positive integer",
            )

        if not isinstance(page_size, int) or page_size < 1 or page_size > 1000:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="page_size",
                actual_value=page_size,
                message="page_size must be an integer between 1 and 1000",
            )

    def _validate_citations_format(self, format: str) -> None:
        """Validate format parameter for citations/references (no DC format)."""
        valid_formats = {"json", "xml"}
        if format not in valid_formats:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="format",
                actual_value=format,
                message=f"format must be one of: {', '.join(valid_formats)}",
            )

    def _validate_callback(self, callback: str | None, format: str) -> None:
        """Validate callback parameter for JSONP requests."""
        if callback is not None:
            if not isinstance(callback, str):
                raise ValidationError(
                    ErrorCodes.VALID001,
                    field_name="callback",
                    actual_value=callback,
                    message="callback must be a string",
                )

            if format != "json":
                raise ValidationError(
                    ErrorCodes.VALID001,
                    field_name="callback",
                    actual_value=callback,
                    message="callback parameter requires format to be 'json'",
                )

    def export_results(
        self,
        results: list[dict[str, Any]],
        format: str = "dataframe",
        path: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Export article results using the specified format.

        Args:
            results: List of result dicts to export
            format: Export format ('dataframe', 'csv', 'excel', 'json', 'markdown')
            path: Optional file path for file-based exports
            **kwargs: Additional options for export (e.g., pretty for JSON)

        Returns:
            Exported data (DataFrame, str, bytes, etc.)
        """
        from pyeuropepmc.utils import export

        if format == "dataframe":
            return export.to_dataframe(results)
        elif format == "csv":
            return export.to_csv(results, path)
        elif format == "excel":
            return export.to_excel(results, path)
        elif format == "json":
            return export.to_json(results, path, **kwargs)
        elif format == "markdown":
            return export.to_markdown_table(results)
        else:
            raise ValueError(f"Unsupported export format: {format}")
