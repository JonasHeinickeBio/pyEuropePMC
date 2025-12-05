"""
AnnotationsClient for Europe PMC Annotations API.

This module provides access to text-mining annotations from Europe PMC,
supporting retrieval of entities, sentences, and relationships in JSON-LD format
according to the W3C Open Annotation Data Model.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig
from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, ValidationError

__all__ = ["AnnotationsClient"]


class AnnotationsClient(BaseAPIClient):
    """
    Client for text-mining annotations via Europe PMC Annotations API.

    Provides methods to retrieve:
    - Annotations by article IDs
    - Annotations by entity types (CHEBI, GO, Disease, etc.)
    - Annotations by provider (Europe PMC, Pubtator, etc.)
    - Entity mentions, sentences, and relationships

    All annotations are returned in JSON-LD format following the
    W3C Open Annotation Data Model.

    Supports optional response caching to improve performance.
    """

    ANNOTATIONS_BASE_URL: str = "https://www.ebi.ac.uk/europepmc/annotations_api/"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize the AnnotationsClient.

        Args:
            rate_limit_delay: Delay between requests in seconds (default: 1.0)
            cache_config: Optional cache configuration. If None, caching is disabled.

        Examples:
            >>> client = AnnotationsClient()
            >>> # With caching enabled
            >>> from pyeuropepmc.cache.cache import CacheConfig
            >>> client = AnnotationsClient(cache_config=CacheConfig(enabled=True))
        """
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.logger = logging.getLogger(__name__)

        # Initialize cache (disabled by default for backward compatibility)
        if cache_config is None:
            cache_config = CacheConfig(enabled=False)

        self._cache = CacheBackend(cache_config)
        cache_status = "enabled" if cache_config.enabled else "disabled"
        self.logger.info(f"AnnotationsClient initialized with cache {cache_status}")

    def __enter__(self) -> "AnnotationsClient":
        """Enter the runtime context related to this object."""
        return self

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        status = "closed" if self.is_closed else "active"
        return (
            f"{self.__class__.__name__}(rate_limit_delay={self.rate_limit_delay}, "
            f"status={status})"
        )

    def close(self) -> None:
        """Close the client and release resources including cache."""
        if self._cache:
            self._cache.close()
        return super().close()

    def get_annotations_by_article_ids(
        self,
        article_ids: list[str],
        section: str = "all",
        provider: str | None = None,
        annotation_type: str | None = None,
        format: str = "JSON-LD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve annotations for specific article IDs.

        Args:
            article_ids: List of article identifiers (e.g., ['PMC1234567', 'PMC2345678'])
            section: Section to retrieve annotations from - 'all', 'abstract', or 'fulltext'
                (default: 'all')
            provider: Filter by annotation provider (e.g., 'Europe PMC', 'Pubtator')
            annotation_type: Filter by annotation type (e.g., 'Gene', 'Disease', 'Chemical')
            format: Response format - 'JSON-LD' (default), 'JSON', or 'XML'
            **kwargs: Additional query parameters

        Returns:
            Dict containing annotations in JSON-LD format

        Raises:
            ValidationError: If article_ids are invalid or empty
            APIClientError: If the API request fails

        Examples:
            >>> client = AnnotationsClient()
            >>> annotations = client.get_annotations_by_article_ids(['PMC1234567'])
            >>> # Filter by entity type
            >>> annotations = client.get_annotations_by_article_ids(
            ...     ['PMC1234567'],
            ...     annotation_type='Gene'
            ... )
        """
        if not article_ids or not isinstance(article_ids, list):
            context = {"article_ids": article_ids}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="article_ids",
                actual_value=article_ids,
            )

        self._validate_section(section)
        if format:
            self._validate_format(format)

        # Build endpoint with article IDs
        article_ids_str = ",".join(str(aid) for aid in article_ids)
        endpoint = "annotationsByArticleIds"

        params: dict[str, Any] = {
            "articleIds": article_ids_str,
            "section": section,
            "format": format,
            **kwargs,
        }

        if provider:
            params["provider"] = provider
        if annotation_type:
            params["type"] = annotation_type

        # Check cache first
        cache_key = self._cache._normalize_key("annotations_by_ids", **params)
        try:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Cache hit for annotations: {article_ids_str[:50]}")
                return dict(cached_result)
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}. Proceeding with API request.")

        self.logger.info(f"Retrieving annotations for article IDs: {article_ids_str[:50]}...")

        try:
            response = self._get_annotations(endpoint, params=params)
            result = response.json()
            result_dict = dict(result)

            # Cache the result
            try:
                self._cache.set(cache_key, result_dict, tag="annotations")
            except Exception as e:
                self.logger.warning(f"Failed to cache annotations: {e}")

            return result_dict
        except Exception as e:
            context = {"article_ids": article_ids_str, "endpoint": endpoint}
            self.logger.error("Failed to retrieve annotations for article IDs")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_annotations_by_entity(
        self,
        entity_id: str,
        entity_type: str,
        provider: str | None = None,
        section: str = "all",
        page: int = 1,
        page_size: int = 25,
        format: str = "JSON-LD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve annotations for a specific entity across all articles.

        Args:
            entity_id: Entity identifier (e.g., 'CHEBI:16236' for ethanol)
            entity_type: Type of entity (e.g., 'CHEBI', 'GO', 'Disease')
            provider: Filter by annotation provider
            section: Section to retrieve annotations from - 'all', 'abstract', or 'fulltext'
            page: Page number for pagination, starting at 1 (default: 1)
            page_size: Number of results per page (default: 25)
            format: Response format - 'JSON-LD' (default), 'JSON', or 'XML'
            **kwargs: Additional query parameters

        Returns:
            Dict containing annotations matching the entity

        Raises:
            ValidationError: If entity_id or entity_type are invalid
            APIClientError: If the API request fails

        Examples:
            >>> client = AnnotationsClient()
            >>> # Get all annotations for a specific chemical (ethanol)
            >>> annotations = client.get_annotations_by_entity(
            ...     entity_id='CHEBI:16236',
            ...     entity_type='CHEBI'
            ... )
        """
        if not entity_id or not isinstance(entity_id, str):
            context = {"entity_id": entity_id}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="entity_id",
                actual_value=entity_id,
            )

        if not entity_type or not isinstance(entity_type, str):
            context = {"entity_type": entity_type}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="entity_type",
                actual_value=entity_type,
            )

        self._validate_section(section)
        self._validate_format(format)
        self._validate_pagination(page, page_size)

        endpoint = "annotationsByEntity"
        params: dict[str, Any] = {
            "entityId": entity_id,
            "entityType": entity_type,
            "section": section,
            "page": page,
            "pageSize": page_size,
            "format": format,
            **kwargs,
        }

        if provider:
            params["provider"] = provider

        # Check cache first
        cache_key = self._cache._normalize_key("annotations_by_entity", **params)
        try:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Cache hit for entity annotations: {entity_id}")
                return dict(cached_result)
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}. Proceeding with API request.")

        self.logger.info(f"Retrieving annotations for entity: {entity_id} ({entity_type})")

        try:
            response = self._get_annotations(endpoint, params=params)
            result = response.json()
            result_dict = dict(result)

            # Cache the result
            try:
                self._cache.set(cache_key, result_dict, tag="annotations")
            except Exception as e:
                self.logger.warning(f"Failed to cache entity annotations: {e}")

            return result_dict
        except Exception as e:
            context = {"entity_id": entity_id, "entity_type": entity_type, "endpoint": endpoint}
            self.logger.error("Failed to retrieve entity annotations")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def get_annotations_by_provider(
        self,
        provider: str,
        article_ids: list[str] | None = None,
        section: str = "all",
        annotation_type: str | None = None,
        format: str = "JSON-LD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Retrieve annotations filtered by provider.

        Args:
            provider: Annotation provider name (e.g., 'Europe PMC', 'Pubtator')
            article_ids: Optional list of article IDs to filter
            section: Section to retrieve annotations from - 'all', 'abstract', or 'fulltext'
            annotation_type: Filter by annotation type (e.g., 'Gene', 'Disease')
            format: Response format - 'JSON-LD' (default), 'JSON', or 'XML'
            **kwargs: Additional query parameters

        Returns:
            Dict containing annotations from the specified provider

        Raises:
            ValidationError: If provider is invalid
            APIClientError: If the API request fails

        Examples:
            >>> client = AnnotationsClient()
            >>> # Get Europe PMC annotations
            >>> annotations = client.get_annotations_by_provider('Europe PMC')
        """
        if not provider or not isinstance(provider, str):
            context = {"provider": provider}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="provider",
                actual_value=provider,
            )

        self._validate_section(section)
        self._validate_format(format)

        endpoint = "annotationsByProvider"
        params: dict[str, Any] = {
            "provider": provider,
            "section": section,
            "format": format,
            **kwargs,
        }

        if article_ids:
            params["articleIds"] = ",".join(str(aid) for aid in article_ids)
        if annotation_type:
            params["type"] = annotation_type

        # Check cache first
        cache_key = self._cache._normalize_key("annotations_by_provider", **params)
        try:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Cache hit for provider annotations: {provider}")
                return dict(cached_result)
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}. Proceeding with API request.")

        self.logger.info(f"Retrieving annotations from provider: {provider}")

        try:
            response = self._get_annotations(endpoint, params=params)
            result = response.json()
            result_dict = dict(result)

            # Cache the result
            try:
                self._cache.set(cache_key, result_dict, tag="annotations")
            except Exception as e:
                self.logger.warning(f"Failed to cache provider annotations: {e}")

            return result_dict
        except Exception as e:
            context = {"provider": provider, "endpoint": endpoint}
            self.logger.error("Failed to retrieve provider annotations")
            raise APIClientError(ErrorCodes.NET001, context) from e

    def _get_annotations(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> Any:
        """
        Make a GET request to the Annotations API.

        This is a wrapper around the base _get method that uses the
        annotations-specific base URL.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters

        Returns:
            Response object from the request
        """
        # Temporarily override BASE_URL for annotations API
        original_base_url = self.BASE_URL
        try:
            self.BASE_URL = self.ANNOTATIONS_BASE_URL
            return self._get(endpoint, params=params)
        finally:
            # Restore original BASE_URL
            self.BASE_URL = original_base_url

    def _validate_section(self, section: str) -> None:
        """Validate section parameter."""
        valid_sections = {"all", "abstract", "fulltext"}
        if section not in valid_sections:
            context = {"section": section, "valid_sections": list(valid_sections)}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="section",
                actual_value=section,
            )

    def _validate_format(self, format: str) -> None:
        """Validate format parameter."""
        valid_formats = {"JSON-LD", "JSON", "XML", "json-ld", "json", "xml"}
        if format not in valid_formats:
            context = {"format": format, "valid_formats": ["JSON-LD", "JSON", "XML"]}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="format",
                actual_value=format,
            )

    def _validate_pagination(self, page: int, page_size: int) -> None:
        """Validate pagination parameters."""
        if page < 1:
            context = {"page": page}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="page",
                actual_value=page,
            )

        if page_size < 1 or page_size > 1000:
            context = {"page_size": page_size}
            raise ValidationError(
                ErrorCodes.VALID001,
                context=context,
                field_name="page_size",
                actual_value=page_size,
            )

    # Cache Management Methods

    def clear_cache(self) -> bool:
        """
        Clear all cached annotations.

        Returns:
            True if cache was cleared successfully, False otherwise.

        Examples:
            >>> client = AnnotationsClient(cache_config=CacheConfig(enabled=True))
            >>> client.clear_cache()
            True
        """
        return self._cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics including hits, misses, and size.

        Returns:
            Dictionary containing cache statistics.

        Examples:
            >>> client = AnnotationsClient(cache_config=CacheConfig(enabled=True))
            >>> stats = client.get_cache_stats()
            >>> print(f"Hit rate: {stats['hit_rate']:.2%}")
        """
        return self._cache.get_stats()

    def get_cache_health(self) -> dict[str, Any]:
        """
        Get cache health status and warnings.

        Returns:
            Dictionary containing cache health information.

        Examples:
            >>> client = AnnotationsClient(cache_config=CacheConfig(enabled=True))
            >>> health = client.get_cache_health()
            >>> if health['status'] != 'healthy':
            ...     print(f"Cache warnings: {health['warnings']}")
        """
        return self._cache.get_health()

    def invalidate_annotations_cache(self, pattern: str = "annotations:*") -> int:
        """
        Invalidate cached annotations matching a pattern.

        Args:
            pattern: Glob pattern to match cache keys (default: "annotations:*")

        Returns:
            Number of cache entries invalidated.

        Examples:
            >>> # Clear all annotation caches
            >>> client.invalidate_annotations_cache("annotations:*")
            >>> # Clear specific entity caches
            >>> client.invalidate_annotations_cache("annotations:*CHEBI*")
        """
        return self._cache.invalidate_pattern(pattern)
