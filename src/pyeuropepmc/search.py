from typing import Any, NoReturn, cast

import requests

from pyeuropepmc.base import BaseAPIClient
from pyeuropepmc.cache import CacheBackend, CacheConfig
from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import EuropePMCError, ParsingError, SearchError
from pyeuropepmc.parser import EuropePMCParser
from pyeuropepmc.utils.helpers import safe_int

logger = BaseAPIClient.logger

__all__ = ["SearchClient", "EuropePMCError"]


class SearchClient(BaseAPIClient):
    """
    Client for searching the Europe PMC publication database.
    This client provides methods to search for publications using various parameters,
    including keywords, phrases, fielded searches, and specific publication identifiers.

    Supports optional response caching to improve performance and reduce API load.
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize the SearchClient with optional rate limiting and caching.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay in seconds between requests to avoid hitting API rate limits (default is 1.0).
        cache_config : CacheConfig, optional
            Configuration for response caching. If None, caching is disabled (default).
            Pass CacheConfig(enabled=True) to enable caching with defaults, or customize
            cache behavior with CacheConfig parameters (cache_dir, ttl, size_limit_mb, etc.).

        Examples
        --------
        >>> # Without caching (backward compatible)
        >>> client = SearchClient()

        >>> # With default caching (24h TTL, 500MB limit)
        >>> from pyeuropepmc.cache import CacheConfig
        >>> client = SearchClient(cache_config=CacheConfig(enabled=True))

        >>> # With custom cache settings
        >>> config = CacheConfig(enabled=True, ttl=3600, size_limit_mb=100)
        >>> client = SearchClient(cache_config=config)
        """
        super().__init__(rate_limit_delay=rate_limit_delay)

        # Initialize cache backend (disabled by default for backward compatibility)
        if cache_config is None:
            cache_config = CacheConfig(enabled=False)

        self._cache = CacheBackend(cache_config)
        cache_status = "enabled" if cache_config.enabled else "disabled"
        logger.info(f"SearchClient initialized with cache {cache_status}")

    def __enter__(self) -> "SearchClient":
        """
        Enter the runtime context related to this object.
        Returns self to allow method chaining.
        """
        return self

    def __repr__(self) -> str:
        return super().__repr__()

    def close(self) -> None:
        """Close the client and release resources including cache."""
        if self._cache:
            self._cache.close()
        return super().close()

    def _extract_search_params(self, query: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Extract and normalize search parameters from kwargs."""
        # Create a copy to avoid mutating the original
        params_dict = kwargs.copy()

        # Handle page_size vs pageSize precedence
        page_size = params_dict.pop("page_size", None)
        if page_size is None:
            page_size = params_dict.pop("pageSize", 25)
        else:
            # Remove pageSize if page_size was provided
            params_dict.pop("pageSize", None)

        # Validate page_size
        if page_size is not None and (page_size < 1 or page_size > 1000):
            context = {"page_size": page_size}
            raise SearchError(ErrorCodes.SEARCH002, context)

        # Build standardized parameters
        params = {
            "query": query,
            "resultType": params_dict.pop("resultType", "lite"),
            "synonym": str(params_dict.pop("synonym", False)).upper(),
            "pageSize": safe_int(page_size, 25),
            "format": params_dict.pop("format", "json"),
            "cursorMark": params_dict.pop("cursorMark", "*"),
            "sort": params_dict.pop("sort", ""),
        }

        # Add any remaining parameters
        params.update(params_dict)
        logger.debug(f"Extracted search params: {params}")
        return params

    def _make_request(
        self, endpoint: str, params: dict[str, Any], method: str = "GET"
    ) -> dict[str, Any] | str:
        """
        Make HTTP request and handle response processing.

        Parameters
        ----------
        endpoint : str
            API endpoint to call
        params : dict
            Request parameters
        method : str
            HTTP method ('GET' or 'POST')

        Returns
        -------
        Union[Dict[str, Any], str]
            Parsed response based on format

        Raises
        ------
        SearchError
            If request fails or response is invalid
        """
        # Validate format parameter
        response_format = params.get("format", "json").lower()
        valid_formats = {"json", "xml", "dc", "lite", "idlist"}
        if response_format not in valid_formats:
            context = {"format": response_format, "valid_formats": list(valid_formats)}
            raise SearchError(ErrorCodes.SEARCH004, context)

        try:
            response = self._make_http_request(endpoint, params, method)
            logger.debug(f"Received {method} response with status code: {response.status_code}")
            if response_format == "json":
                try:
                    json_data = response.json()
                except ValueError as e:
                    # JSON parse error -> wrap as SearchError
                    context = {"method": method.upper(), "endpoint": endpoint, "error": str(e)}
                    raise SearchError(ErrorCodes.SEARCH003, context) from e
                return cast(dict[str, Any], json_data)
            return str(response.text)
        except requests.exceptions.HTTPError as e:
            raise self._handle_http_error(e, method, endpoint) from e
        except requests.exceptions.RequestException as e:
            raise self._handle_request_exception(e, method, endpoint) from e
        except Exception as e:
            context = {"method": method.upper(), "endpoint": endpoint, "error": str(e)}
            logger.error("Unexpected error in request")
            raise SearchError(ErrorCodes.NET001, context) from e

    def _make_http_request(
        self, endpoint: str, params: dict[str, Any], method: str
    ) -> requests.Response:
        """Make the actual HTTP request."""
        response: requests.Response
        if method.upper() == "POST":
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = self._post(endpoint, data=params, headers=headers)
        else:
            response = self._get(endpoint, params)

        if not isinstance(response, requests.Response):
            context = {"method": method.upper(), "endpoint": endpoint}
            raise SearchError(ErrorCodes.NET002, context)
        return response

    def _handle_http_error(
        self, error: requests.exceptions.HTTPError, method: str, endpoint: str
    ) -> NoReturn:
        """Handle HTTP errors and map to appropriate error codes."""
        status_code = getattr(error.response, "status_code", 0) if error.response else 0

        if status_code == 404:
            error_code = ErrorCodes.HTTP404
        elif status_code == 403:
            error_code = ErrorCodes.HTTP403
        elif status_code == 500:
            error_code = ErrorCodes.HTTP500
        else:
            error_code = ErrorCodes.NET001

        context = {
            "method": method.upper(),
            "endpoint": endpoint,
            "status_code": status_code,
            "error": str(error),
        }
        logger.error("HTTP error in request")
        raise SearchError(error_code, context)

    def _handle_request_exception(
        self, error: requests.exceptions.RequestException, method: str, endpoint: str
    ) -> NoReturn:
        """Handle request exceptions and map to appropriate error codes."""
        error_str = str(error).lower()

        if isinstance(error, requests.exceptions.Timeout) or "timeout" in error_str:
            error_code = ErrorCodes.NET002
        elif "connection" in error_str:
            error_code = ErrorCodes.NET001
        else:
            error_code = ErrorCodes.NET001

        context = {"method": method.upper(), "endpoint": endpoint, "error": str(error)}
        logger.error("Request failed")
        raise SearchError(error_code, context)

    def search(self, query: str, **kwargs: Any) -> dict[str, Any] | str:  # noqa: C901
        """
        Search the Europe PMC publication database.

        Parameters
        ----------
        query : str
            User query. Possible options are:
            - a keyword or combination of keywords (e.g. HPV virus).
            - a phrase with enclosing speech marks (e.g. "human malaria").
            - a fielded search (e.g. auth:stoehr).
            - a specific publication (e.g. ext_id:781840 src:med).
        resultType : str
            Response Type. Determines fields returned by XML and JSON formats, but not DC format.
            Possible values:
            - idlist: returns a list of IDs and sources for the given search terms
            - lite: returns key metadata for the given search terms
            - core: returns full metadata for a given publication ID; including abstract,
                full text links, and MeSH terms
        synonym : bool
            Synonym searches are not made by default (default = False).
            Queries can be expanded using MeSH terminology.
        cursorMark : str
            CursorMark for pagination. For the first request, omit or use '*'.
            For following pages, use the returned nextCursorMark.
        pageSize : int
            Number of articles per page. Default is 25. Max is 1000.
        sort : str
            Sort order. Default is relevance. Specify field and order (asc or desc), 'CITED asc'.
        format : str
            Response format. Can be XML, JSON, or DC (Dublin Core).
        callback : str
            For cross-domain JSONP requests. Format must be JSON.
        email : str
            Optional user email for EBI contact about Web Service news.

        Returns
        -------
        dict or str
            Parsed API response as JSON dict, or raw XML/DC string depending on requested format.

        Raises
        ------
        EuropePMCError
            If the query is invalid or the request fails.
        """
        # Validate query
        if not self.validate_query(query):
            context = {"query": query}
            raise SearchError(ErrorCodes.SEARCH001, context)

        try:
            params = self._extract_search_params(query, kwargs)
            cache_key = None

            # Try to get from cache first (with error handling)
            try:
                cache_key = self._cache._normalize_key("search", **params)
                cached_result = self._cache.get(cache_key)

                if cached_result is not None:
                    logger.info(f"Cache hit for search query: {query[:50]}...")
                    # Narrow the cached result's runtime type before returning to avoid
                    # returning an untyped Any (mypy) from this function.
                    if isinstance(cached_result, dict):
                        return cast(dict[str, Any], cached_result)
                    if isinstance(cached_result, str):
                        return cached_result
                    # Unexpected cached type - log and continue to fetch fresh result
                    logger.warning("Cached result has unexpected type; ignoring cache entry")
            except Exception as cache_error:
                # Log cache error but don't fail the search
                logger.warning(f"Cache lookup error (continuing): {cache_error}")

            # Cache miss - make API request
            logger.info(f"Cache miss - performing search with params: {params}")
            result = self._make_request("search", params, method="GET")

            # Cache the result (with error handling)
            if cache_key is not None:
                try:
                    self._cache.set(cache_key, result, tag="search")
                except Exception as cache_error:
                    # Log cache error but don't fail the search
                    logger.warning(f"Cache set error (continuing): {cache_error}")

            return result
        except SearchError:
            # Re-raise SearchError as-is (from validation or other internal errors)
            raise
        except requests.exceptions.RequestException as e:
            # Map request exceptions to appropriate error codes
            error_str = str(e).lower()

            if isinstance(e, requests.exceptions.Timeout) or "timeout" in error_str:
                error_code = ErrorCodes.NET002
            elif "404" in error_str:
                error_code = ErrorCodes.SEARCH006
            elif "429" in error_str:
                error_code = ErrorCodes.RATE429
            else:
                error_code = ErrorCodes.NET001

            context = {"query": query, "error": str(e)}
            logger.error("Search request failed")
            raise SearchError(error_code, context) from e
        except Exception as e:
            context = {"query": query, "error": str(e)}
            logger.error("Unexpected search error")
            raise SearchError(ErrorCodes.SEARCH003, context) from e

    def search_post(self, query: str, **kwargs: Any) -> dict[str, Any] | str:
        """
        Search the Europe PMC publication database using a POST request.

        This endpoint is for complex or very long queries that might exceed URL length limits.
        All parameters are sent as URL-encoded form data in the request body.

        Parameters
        ----------
        query : str
            User query. Possible options are:
            - a keyword or combination of keywords (e.g. HPV virus).
            - a phrase with enclosing speech marks (e.g. "human malaria").
            - a fielded search (e.g. auth:stoehr).
            - a specific publication (e.g. ext_id:781840 src:med).
        resultType : str, optional
            Response Type. Determines fields returned by XML and JSON formats, but not DC format.
            Possible values:
            - idlist: returns a list of IDs and sources for the given search terms
            - lite: returns key metadata for the given search terms
            - core: returns full metadata for a given publication ID; including abstract,
            full text links, and MeSH terms
        synonym : bool, optional
            Synonym searches are not made by default (default = False).
        cursorMark : str, optional
            CursorMark for pagination. For the first request, omit or use '*'.
            For following pages, use the returned nextCursorMark.
        pageSize : int, optional
            Number of articles per page. Default is 25. Max is 1000.
        sort : str, optional
            Sort order. Default is relevance. Specify order (asc or desc), e.g., 'CITED asc'.
        format : str, optional
            Response format. Can be XML, JSON, or DC (Dublin Core).
        callback : str, optional
            For cross-domain JSONP requests. Format must be JSON.
        email : str, optional
            Optional user email for EBI contact about Web Service news.

        Returns
        -------
        dict or str
            Parsed API response as JSON dict, or raw XML/DC string depending on the format.

        Raises
        ------
        EuropePMCError
            If the request fails or the response cannot be parsed.
        """
        try:
            data = self._extract_search_params(query, kwargs)
            # Try to get from cache first (with error handling)
            cache_key = None
            try:
                cache_key = self._cache._normalize_key("search_post", **data)
                cached_result = self._cache.get(cache_key)
                if cached_result is not None:
                    logger.info(f"Cache hit for POST search query: {query[:50]}...")
                    # Validate runtime type of cached value before returning
                    if isinstance(cached_result, dict):
                        return cast(dict[str, Any], cached_result)
                    if isinstance(cached_result, str):
                        return cached_result
                    logger.warning("Cached result has unexpected type; ignoring cache entry")
            except Exception as cache_error:
                logger.warning(f"Cache lookup error (continuing): {cache_error}")
            # Cache miss - make API request
            logger.info(f"Cache miss - performing POST search with data: {data}")
            result = self._make_request("searchPOST", data, method="POST")
            # Cache the result (with error handling)
            if cache_key is not None:
                try:
                    self._cache.set(cache_key, result, tag="search_post")
                except Exception as cache_error:
                    logger.warning(f"Cache set error (continuing): {cache_error}")
            return result
        except SearchError:
            # Re-raise SearchError as-is (from validation or other internal errors)
            raise
        except requests.exceptions.RequestException as e:
            context = {"query": query, "error": str(e)}
            logger.error("POST search request failed")
            raise SearchError(ErrorCodes.NET001, context) from e
        except Exception as e:
            context = {"query": query, "error": str(e)}
            logger.error("Unexpected POST search error")
            raise SearchError(ErrorCodes.SEARCH003, context) from e

    def fetch_all_pages(
        self, query: str, page_size: int = 100, max_results: int | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Fetch all results for a query, handling pagination automatically.
        """
        # Validate inputs
        page_size = max(1, min(page_size, 1000))
        if max_results is not None and max_results <= 0:
            return []

        results: list[dict[str, Any]] = []
        cursor_mark = "*"

        while True:
            # Calculate page size for this request
            current_page_size = page_size
            if max_results is not None:
                remaining = max_results - len(results)
                if remaining <= 0:
                    break
                current_page_size = min(page_size, remaining)

            # Fetch page
            try:
                data = self.search(
                    query, page_size=current_page_size, cursorMark=cursor_mark, **kwargs
                )
            except EuropePMCError:
                break

            # Validate response and extract results using helper
            page_results, next_cursor = self._extract_page_results(data)
            if not page_results:
                break

            # Add results and check for completion
            results.extend(page_results)

            # Stop if next cursor is missing, unchanged, or page wasn't full
            if (
                not next_cursor
                or next_cursor == cursor_mark
                or len(page_results) < current_page_size
            ):
                break

            cursor_mark = next_cursor

        # Trim results if needed
        if max_results is not None and len(results) > max_results:
            results = results[:max_results]

        return results

    def _extract_page_results(self, data: Any) -> tuple[list[dict[str, Any]], str | None]:
        """Validate a single page response and extract the result list and next cursor.

        Returns (page_results, next_cursor) where page_results is empty on invalid response.
        """
        # Use existing lightweight validator first
        if not self._is_valid_page_response(data):
            return [], None

        # At this point data is a dict and resultList key exists
        result_list = data.get("resultList")
        if not isinstance(result_list, dict):
            return [], None

        page_results = result_list.get("result")
        if not isinstance(page_results, list) or not page_results:
            return [], None

        next_cursor = data.get("nextCursorMark")
        if not isinstance(next_cursor, str):
            next_cursor = None

        return page_results, next_cursor

    def _is_valid_page_response(self, data: Any) -> bool:
        """
        Lightweight validation that data is a paged JSON response we can extract results from.
        Returns True for a dict containing a 'resultList' dict with a 'result' list.
        """
        if not isinstance(data, dict):
            return False

        result_list = data.get("resultList")
        if not isinstance(result_list, dict):
            return False

        results = result_list.get("result")
        return isinstance(results, list)

    def interactive_search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """
        Interactive search: Show hit count, prompt user for number of results, fetch and return.
        This method performs an initial search to get the hit count,
        it then prompts the user for how many results they want,
        and then fetches that many results, handling pagination as needed.
        The user can type 'q' or 'quit' to exit without fetching results.
        """
        try:
            # Step 1: Get hit count
            hit_count = self._get_hit_count_for_interactive(query, **kwargs)
            if hit_count == 0:
                return []

            # Step 2: Get user input for number of results
            n = self._prompt_user_for_result_count(hit_count, query)
            if n == 0:
                return []

            # Step 3: Fetch results
            return self._fetch_interactive_results(query, n, **kwargs)

        except (EuropePMCError, Exception) as e:
            logger.error(f"Error during interactive search: {e}")
            return []

    def _get_hit_count_for_interactive(self, query: str, **kwargs: Any) -> int:
        """Get hit count for interactive search and handle early exits."""
        response = self.search(query, page_size=1, **kwargs)

        if isinstance(response, str):
            logger.warning(
                "Received a string response, which is unexpected. "
                "Please check your query or parameters."
            )
            return 0

        if not response or "hitCount" not in response:
            logger.info("No results found or error occurred.")
            return 0

        hit_count = int(response["hitCount"])
        if hit_count == 0:
            logger.info(f"Your query '{query}' returned no results.")
            return 0

        logger.info(f"Your query '{query}' returned {hit_count:,} results.")
        return hit_count

    def _prompt_user_for_result_count(self, hit_count: int, query: str) -> int:
        """Prompt user for number of results to fetch."""
        while True:
            try:
                user_input = (
                    input(
                        f"How many results would you like to retrieve? "
                        f"(max {hit_count}, 'q', 'quit' or 0 to quit): "
                    )
                    .strip()
                    .lower()
                )

                if user_input in ("0", "q", "quit", ""):
                    logger.info("No results will be fetched. Exiting interactive search.")
                    return 0

                n = int(user_input)
                if 1 <= n <= hit_count:
                    return n
                logger.info(f"Please enter a number between 1 and {hit_count}, or '0' to quit.")
            except Exception as e:
                logger.info(f"Please enter a valid integer, or '0' to quit. Error: {e}")
                continue
            except KeyboardInterrupt:
                logger.info("\nOperation cancelled by user.")
                return 0

    def _fetch_interactive_results(
        self, query: str, n: int, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Fetch the requested number of results for interactive search."""
        logger.info(f"Fetching {n} results for '{query}' ...")
        results = self.fetch_all_pages(query, max_results=n, **kwargs)
        logger.info(f"Fetched {len(results)} results.")
        return results

    def search_and_parse(
        self, query: str, format: str = "json", **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Search and parse results from Europe PMC.

        Parameters
        ----------
        query : str
            The search query.
        format : str, optional
            The format of the response. Can be 'json', 'xml', or 'dc' (Dublin Core).
            Default is 'json'.
        **kwargs
            Additional parameters for the search.

        Returns
        -------
        List[Dict[str, Any]]
            Parsed results as a list of dictionaries.

        Raises
        ------
        ValueError
            If format is not supported or response type doesn't match format.
        EuropePMCError
            If search request fails.
        """
        # Validate format early
        supported_formats = {"json", "xml", "dc"}
        if format.lower() not in supported_formats:
            context = {"format": format, "supported_formats": list(supported_formats)}
            raise SearchError(ErrorCodes.SEARCH004, context)

        format = format.lower()

        try:
            raw = self.search(query, format=format, **kwargs)

            # Type checking and parsing
            if format == "json":
                if not isinstance(raw, dict):
                    context = {
                        "expected_type": "dict",
                        "actual_type": type(raw).__name__,
                        "format": format,
                    }
                    raise ParsingError(ErrorCodes.PARSE001, context)
                return EuropePMCParser.parse_json(raw)

            elif format in ("xml", "dc"):
                if not isinstance(raw, str):
                    context = {
                        "expected_type": "str",
                        "actual_type": type(raw).__name__,
                        "format": format,
                    }
                    raise ParsingError(ErrorCodes.PARSE004, context)

                if format == "xml":
                    return EuropePMCParser.parse_xml(raw)
                else:  # format == "dc"
                    return EuropePMCParser.parse_dc(raw)

        except ParsingError:
            # Re-raise ParsingError as-is (for type mismatches and parsing issues)
            raise
        except EuropePMCError:
            # Re-raise EuropePMC errors as-is
            raise
        except Exception as e:
            context = {"format": format, "error": str(e)}
            raise SearchError(ErrorCodes.SEARCH005, context) from e

        # This should never be reached due to the format validation above
        context = {"format": format}
        raise SearchError(ErrorCodes.SEARCH005, context)

    def get_hit_count(self, query: str, **kwargs: Any) -> int:
        """
        Get the total number of results for a query without fetching actual results.

        This is more efficient than search() when you only need the count.

        Parameters
        ----------
        query : str
            The search query.
        **kwargs
            Additional search parameters.

        Returns
        -------
        int
            Total number of results available for the query.

        Raises
        ------
        SearchError
            If the request fails or response is invalid.
        """
        try:
            # Use minimal page size for efficiency
            response = self.search(query, page_size=1, **kwargs)

            if isinstance(response, str):
                context = {"query": query, "response_type": "string"}
                logger.error("Received string response when expecting JSON for hit count.")
                raise SearchError(ErrorCodes.SEARCH003, context)

            if not isinstance(response, dict) or "hitCount" not in response:
                context = {"query": query, "response": str(response)[:100]}
                logger.warning("Missing hitCount in response, returning 0.")
                return 0

            return int(response["hitCount"])

        except SearchError:
            # Re-raise SearchError as-is
            raise
        except Exception as e:
            context = {"query": query, "error": str(e)}
            logger.error("Error getting hit count")
            raise SearchError(ErrorCodes.SEARCH003, context) from e

    def search_ids_only(self, query: str, **kwargs: Any) -> list[str]:
        """
        Search and return only publication IDs (more efficient for large result sets).

        Parameters
        ----------
        query : str
            The search query.
        **kwargs
            Additional search parameters.

        Returns
        -------
        List[str]
            List of publication IDs.
        """
        # Force resultType to idlist for efficiency
        kwargs["resultType"] = "idlist"

        try:
            results = self.search_and_parse(query, **kwargs)
            return [result.get("id", "") for result in results if result.get("id")]
        except Exception as e:
            logger.error(f"Error in search_ids_only: {e}")
            return []

    @staticmethod
    def validate_query(query: str) -> bool:
        """
        Validate a search query for basic correctness.

        Parameters
        ----------
        query : str
            The search query to validate.

        Returns
        -------
        bool
            True if query appears valid, False otherwise.
        """
        if not query or not isinstance(query, str):
            return False

        # Remove extra whitespace
        query = query.strip()

        if not query:
            return False

        # Check for minimum length
        if len(query) < 2:
            return False

        # Check for obvious malformed queries
        # Unmatched quotes - only check if there are quotes
        if '"' in query:
            quote_count = query.count('"')
            if quote_count % 2 != 0:
                logger.warning("Query contains unmatched quotes")
                return False

        # Too many special characters (but allow reasonable scientific notation)
        special_chars = set("!@#$%^&*()+=[]{}|\\:;'<>?,/~`")
        special_count = sum(1 for char in query if char in special_chars)
        if special_count > len(query) * 0.3:  # More than 30% special characters
            logger.warning("Query contains too many special characters")
            return False

        return True

    def export_results(
        self,
        results: list[dict[str, Any]],
        format: str = "dataframe",
        path: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Export search results using the specified format.

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

    # Cache Management Methods

    def clear_cache(self) -> bool:
        """
        Clear all cached search results.

        Returns
        -------
        bool
            True if cache was cleared successfully, False otherwise.

        Examples
        --------
        >>> client = SearchClient(cache_config=CacheConfig(enabled=True))
        >>> client.clear_cache()
        True
        """
        return self._cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics including hits, misses, and size.

        Returns
        -------
        dict
            Dictionary containing cache statistics.

        Examples
        --------
        >>> client = SearchClient(cache_config=CacheConfig(enabled=True))
        >>> stats = client.get_cache_stats()
        >>> print(f"Hit rate: {stats['hit_rate']:.2%}")
        """
        return self._cache.get_stats()

    def get_cache_health(self) -> dict[str, Any]:
        """
        Get cache health status and warnings.

        Returns
        -------
        dict
            Dictionary containing cache health information including status,
            utilization, error rate, and warnings.

        Examples
        --------
        >>> client = SearchClient(cache_config=CacheConfig(enabled=True))
        >>> health = client.get_cache_health()
        >>> if health['status'] != 'healthy':
        ...     print(f"Cache warnings: {health['warnings']}")
        """
        return self._cache.get_health()

    def invalidate_search_cache(self, pattern: str = "search:*") -> int:
        """
        Invalidate cached search results matching a pattern.

        Parameters
        ----------
        pattern : str, optional
            Glob pattern to match cache keys (default: "search:*" for all searches).

        Returns
        -------
        int
            Number of cache entries invalidated.

        Examples
        --------
        >>> # Clear all search caches
        >>> client.invalidate_search_cache("search:*")
        >>> # Clear specific query caches
        >>> client.invalidate_search_cache("search:*cancer*")
        """
        return self._cache.invalidate_pattern(pattern)
