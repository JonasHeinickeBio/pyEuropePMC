"""
ArticleClient for Europe PMC Articles RESTful API.

This module provides access to individual article operations including citations,
references, database links, and detailed article information.
"""

import hashlib
import json
import logging
from typing import Any

import requests

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig
from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, ValidationError
from pyeuropepmc.features.literature.search_parser import EuropePMCParser
from pyeuropepmc.utils.helpers import warn_if_empty_hitcount

__all__ = ["ArticleClient"]

# MeSH "check tags" and other headings that nearly every article carries: searching on them
# finds articles that have nothing in common with the one given.
_GENERIC_MESH = frozenset(
    {
        "humans",
        "animals",
        "male",
        "female",
        "adult",
        "aged",
        "aged, 80 and over",
        "middle aged",
        "young adult",
        "adolescent",
        "child",
        "child, preschool",
        "infant",
        "infant, newborn",
        "mice",
        "rats",
        "cells, cultured",
    }
)
_RELATED_BASES = ("auto", "mesh", "keywords")


def _tagged(value: Any) -> list[str]:
    """JSON form of a value JSON cannot hold, which cannot equal a string's JSON form.

    ``b"x"`` and the string ``"b'x'"`` reach Europe PMC as different query strings; they must
    not share a cache entry.
    """
    return [f"<{type(value).__qualname__}>", repr(value)]


def _cache_key(kind: str, source: str, article_id: str, params: dict[str, Any]) -> str | None:
    """
    Cache key for one request: the endpoint plus every parameter that is sent.

    The parameters are serialized in sorted order, so the same request gives the same key
    whatever order the caller passed them in, and any parameter that changes the answer
    (``sort``, ``cursorMark``, ``resultType``, ...) changes the key. A parameter set to
    ``None`` is left out, as ``requests`` does not send it. They are hashed to keep the key
    short. The ``kind:source:article_id:`` prefix stays readable because
    ``ArticleClient.invalidate_article_cache`` matches on it.

    Returns ``None`` when the parameters cannot be serialized (for example a mapping with keys
    of different types, or one that contains itself): the request is then sent without
    touching the cache.
    """
    sent = {k: v for k, v in params.items() if v is not None}
    try:
        canonical = json.dumps(sent, sort_keys=True, separators=(",", ":"), default=_tagged)
    except (TypeError, ValueError):
        return None
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{source}:{article_id}:{digest}"


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

    @staticmethod
    def _text_result(response: requests.Response, format: str) -> dict[str, Any]:
        """
        Wrap a response body that is not JSON.

        XML and Dublin Core responses cannot go through ``response.json()``; like
        JSONP they are returned as text, under ``"xml_response"`` or
        ``"dc_response"``.
        """
        return {f"{format}_response": response.text}

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
            Dict containing article details. With format 'xml' or 'dc' the body
            is returned as text under the key 'xml_response' or 'dc_response'.

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

        # Check cache first (a JSONP callback changes the response's shape: never cached)
        cache_key = _cache_key("article_details", source, article_id, params)
        if params.get("callback") is not None:
            cache_key = None
        if cache_key is not None:
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
            if format != "json":
                result_dict = self._text_result(response, format)
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="article details")
                result_dict = dict(result)

            # Cache the result
            if cache_key is not None:
                try:
                    self._cache.set(cache_key, result_dict, tag="article_details")
                except Exception as e:
                    self.logger.warning(f"Failed to cache article details: {e}")

            return result_dict
        except APIClientError:
            # _get's error already names the failure (HTTP404, RATE429, ...).
            self.logger.error(f"Failed to retrieve article details for {source}:{article_id}")
            raise
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
            Dict containing citation information including count and list of citing papers.
            With format 'xml' the body is returned as text under 'xml_response'.

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
        cache_key = _cache_key("citations", source, article_id, params)
        if cache_key is not None and not callback:
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
                if format != "json":
                    result_dict = self._text_result(response, format)
                else:
                    result = response.json()
                    warn_if_empty_hitcount(result, context="citations")
                    result_dict = dict(result)

                # Cache the result
                if cache_key is not None:
                    try:
                        self._cache.set(cache_key, result_dict, tag="citations")
                    except Exception as e:
                        self.logger.warning(f"Failed to cache citations: {e}")

                return result_dict
        except APIClientError:
            # _get's error already names the failure (HTTP404, RATE429, ...).
            self.logger.error(f"Failed to retrieve citations for {source}:{article_id}")
            raise
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
            Dict containing reference information including count and list of referenced papers.
            With format 'xml' the body is returned as text under 'xml_response'.

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
        cache_key = _cache_key("references", source, article_id, params)
        if cache_key is not None and not callback:
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
                if format != "json":
                    result_dict = self._text_result(response, format)
                else:
                    result = response.json()
                    warn_if_empty_hitcount(result, context="references")
                    result_dict = dict(result)

                # Cache the result
                if cache_key is not None:
                    try:
                        self._cache.set(cache_key, result_dict, tag="references")
                    except Exception as e:
                        self.logger.warning(f"Failed to cache references: {e}")

                return result_dict
        except APIClientError:
            # _get's error already names the failure (HTTP404, RATE429, ...).
            self.logger.error(f"Failed to retrieve references for {source}:{article_id}")
            raise
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

    def get_related_articles(
        self,
        source: str,
        article_id: str,
        basis: str = "auto",
        match: str = "any",
        max_terms: int = 3,
        terms: list[str] | None = None,
        page_size: int = 25,
        cursor_mark: str = "*",
        result_type: str = "lite",
        sort: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Find articles on the same subject as the given article.

        Europe PMC's REST API has no "similar articles" endpoint, so this builds a search from
        what the article is indexed with: its MeSH headings (major topics first, without the
        generic ones such as ``Humans``) or its author keywords. The article itself is left out
        of the results. Pagination and result types are those of ``SearchClient.search()``.

        Args:
            source: Three letter code of the data source (e.g., 'MED', 'PMC')
            article_id: Article ID in that source
            basis: Where the search terms come from: ``"mesh"``, ``"keywords"``, or ``"auto"``
                (MeSH headings, else keywords)
            match: ``"any"`` finds articles that share at least one term, best matches first;
                ``"all"`` only those that carry every term
            max_terms: How many terms to use (1 to 10)
            terms: Search these terms instead of reading them from the article, which saves the
                request for the article. Pass the ``terms`` of a first call to fetch the next
                pages. They are searched as MeSH headings, or as keywords when
                ``basis="keywords"``.
            page_size: Results per page (1-1000)
            cursor_mark: Cursor for the page; ``"*"`` for the first, the ``nextCursorMark`` of
                the previous response afterwards
            result_type: ``"lite"`` (default), ``"core"`` or ``"idlist"``
            sort: Sort order, as for ``SearchClient.search()``; empty means by relevance
            **kwargs: Additional query parameters

        Returns:
            Dict with ``query`` (the search that was run), ``terms``, ``hitCount``,
            ``nextCursorMark`` and ``results`` (the records, as ``search_and_parse()`` returns
            them). When the article has no usable terms, ``terms`` is empty, ``query`` is
            ``None`` and no search is made.

        Raises:
            ValidationError: For an invalid argument
            APIClientError: If a request fails

        Example:
            >>> client = ArticleClient()
            >>> page = client.get_related_articles('MED', '23087375', page_size=10)
            >>> page['terms']
            ['Mutation', 'DNA, Mitochondrial', 'Mitochondria']
            >>> more = client.get_related_articles(
            ...     'MED', '23087375', terms=page['terms'], cursor_mark=page['nextCursorMark']
            ... )
        """
        self._validate_source_and_id(source, article_id)
        self._validate_pagination(1, page_size)
        self._validate_result_type(result_type)
        self._validate_choice("basis", basis, _RELATED_BASES)
        self._validate_choice("match", match, ("any", "all"))
        if not isinstance(max_terms, int) or not 1 <= max_terms <= 10:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name="max_terms",
                actual_value=max_terms,
                message="max_terms must be an integer between 1 and 10",
            )

        if terms is None:
            details = self.get_article_details(source, article_id, result_type="core")
            terms, field = self._related_terms(details.get("result") or {}, basis, max_terms)
        else:
            terms = [t for t in dict.fromkeys(terms) if isinstance(t, str) and t.strip()]
            field = "KW" if basis == "keywords" else "MESH"
        terms = [t.replace('"', " ").strip() for t in terms][:max_terms]

        if not terms:
            self.logger.info(f"No terms to search for articles related to {source}:{article_id}")
            return {
                "query": None,
                "terms": [],
                "hitCount": 0,
                "nextCursorMark": None,
                "results": [],
            }

        # The field is named once and the terms grouped: `MESH:"a" OR MESH:"b"` is evaluated by
        # Europe PMC as `MESH:"b"` alone.
        joiner = " AND " if match == "all" else " OR "
        wanted = joiner.join(f'"{t}"' for t in terms)
        query = f"{field}:({wanted}) AND NOT (EXT_ID:{article_id} AND SRC:{source})"
        params = {
            "query": query,
            "format": "json",
            "resultType": result_type,
            "pageSize": page_size,
            "cursorMark": cursor_mark,
            "sort": sort,
            **kwargs,
        }

        self.logger.info(f"Retrieving articles related to {source}:{article_id}")
        try:
            data = self._get("search", params=params).json()
            warn_if_empty_hitcount(data, context="related articles")
            return {
                "query": query,
                "terms": terms,
                "hitCount": data.get("hitCount", 0),
                "nextCursorMark": data.get("nextCursorMark"),
                "results": EuropePMCParser.parse_json(data) if data.get("hitCount") else [],
            }
        except APIClientError:
            self.logger.error(f"Failed to retrieve articles related to {source}:{article_id}")
            raise
        except Exception as e:
            context = {"source": source, "article_id": article_id, "endpoint": "search"}
            self.logger.error(f"Failed to retrieve articles related to {source}:{article_id}")
            raise APIClientError(ErrorCodes.NET001, context) from e

    @staticmethod
    def _related_terms(
        record: dict[str, Any], basis: str, max_terms: int
    ) -> tuple[list[str], str]:
        """The terms to search for and the field they belong to, read from a core record."""
        mesh = (record.get("meshHeadingList") or {}).get("meshHeading") or []
        specific = [
            m for m in mesh if str(m.get("descriptorName", "")).lower() not in _GENERIC_MESH
        ]
        # Major topics are what the article is mainly about
        specific.sort(key=lambda m: m.get("majorTopic_YN") != "Y")
        mesh_terms = [str(m["descriptorName"]) for m in specific if m.get("descriptorName")]
        keywords = [str(k) for k in (record.get("keywordList") or {}).get("keyword") or []]

        if basis == "keywords" or (basis == "auto" and not mesh_terms):
            return list(dict.fromkeys(keywords))[:max_terms], "KW"
        return list(dict.fromkeys(mesh_terms))[:max_terms], "MESH"

    @staticmethod
    def _validate_choice(name: str, value: str, choices: tuple[str, ...]) -> None:
        """Validate a parameter that takes one of a few values."""
        if value not in choices:
            raise ValidationError(
                ErrorCodes.VALID001,
                field_name=name,
                actual_value=value,
                message=f"{name} must be one of: {', '.join(choices)}",
            )

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
            Dict containing database link information. With format 'xml' the body is
            returned as text under 'xml_response'.

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
            elif format != "json":
                return self._text_result(response, format)
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="database links")
                return dict(result)
        except APIClientError:
            # _get's error already names the failure (HTTP404, RATE429, ...).
            self.logger.error(f"Failed to retrieve database links for {source}:{article_id}")
            raise
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
        except APIClientError:
            # _get's error, or the HTTP404 above: keep the specific code.
            self.logger.error(f"Failed to retrieve supplementary files for {article_id}")
            raise
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
            Dict containing lab links information. With format 'xml' the body is
            returned as text under 'xml_response'.

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
            elif format != "json":
                return self._text_result(response, format)
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="lab links")
                return dict(result)
        except APIClientError:
            # _get's error already names the failure (HTTP404, RATE429, ...).
            self.logger.error(f"Failed to retrieve lab links for {source}:{article_id}")
            raise
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
            Dict containing consolidated data links in Scholix format. With format
            'xml' the body is returned as text under 'xml_response'.

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
            elif format != "json":
                return self._text_result(response, format)
            else:
                result = response.json()
                warn_if_empty_hitcount(result, context="data links")
                return dict(result)
        except APIClientError:
            # _get's error already names the failure (HTTP404, RATE429, ...).
            self.logger.error(f"Failed to retrieve data links for {source}:{article_id}")
            raise
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
        # Close the HTTP session too; without this is_closed stayed False.
        super().close()

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
