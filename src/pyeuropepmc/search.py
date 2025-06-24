from typing import Any, Dict, List, Optional, Union

import requests

from pyeuropepmc.base import BaseAPIClient
from pyeuropepmc.parser import EuropePMCParser
from pyeuropepmc.utils.helpers import safe_int

logger = BaseAPIClient.logger


class EuropePMCError(Exception):
    """Custom exception for Europe PMC API errors."""

    pass


class SearchClient(BaseAPIClient):
    """
    Client for searching the Europe PMC publication database.
    This client provides methods to search for publications using various parameters,
    including keywords, phrases, fielded searches, and specific publication identifiers.
    """

    def __init__(self, rate_limit_delay: float = 1.0) -> None:
        """
        Initialize the SearchClient with an optional rate limit delay.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay in seconds between requests to avoid hitting API rate limits (default is 1.0).
        """
        super().__init__(rate_limit_delay=rate_limit_delay)

    def __enter__(self) -> "SearchClient":
        """
        Enter the runtime context related to this object.
        Returns self to allow method chaining.
        """
        return self

    def __repr__(self) -> str:
        return super().__repr__()

    def close(self) -> None:
        return super().close()

    def _extract_search_params(self, query: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
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
        self, endpoint: str, params: Dict[str, Any], method: str = "GET"
    ) -> Union[Dict[str, Any], str]:
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
        EuropePMCError
            If request fails or response is invalid
        """
        try:
            if method.upper() == "POST":
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                response = self._post(endpoint, data=params, headers=headers)
            else:
                response = self._get(endpoint, params)

            if not response:
                raise EuropePMCError("No response from server")

            response_format = params.get("format", "json").lower()
            logger.debug(f"Received {method} response with status code: {response.status_code}")

            return response.json() if response_format == "json" else str(response.text)

        except Exception as e:
            logger.error(f"Error during {method} request: {e}")
            raise EuropePMCError(f"Error during {method} request: {e}")

    def search(self, query: str, **kwargs: Any) -> Union[Dict[str, Any], str]:
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
            raise EuropePMCError(f"Invalid query: '{query}'")

        try:
            params = self._extract_search_params(query, kwargs)
            logger.info(f"Performing search with params: {params}")
            return self._make_request("search", params, method="GET")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed during search: {e}")
            raise EuropePMCError(f"Search request failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise EuropePMCError(f"Search failed: {e}") from e

    def search_post(self, query: str, **kwargs: Any) -> Union[Dict[str, Any], str]:
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
            logger.info(f"Performing POST search with data: {data}")
            return self._make_request("searchPOST", data, method="POST")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed during POST search: {e}")
            raise EuropePMCError(f"POST search request failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during POST search: {e}")
            raise EuropePMCError(f"POST search failed: {e}") from e

    def fetch_all_pages(
        self, query: str, page_size: int = 100, max_results: Optional[int] = None, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Fetch all results for a query, handling pagination automatically.

        Parameters
        ----------
        query : str
            The search query.
        page_size : int, optional
            Number of results per page (default 100, max 1000).
        max_results : int, optional
            Maximum number of results to fetch. If None, fetch all available.
        **kwargs
            Additional parameters for the search.

        Returns
        -------
        List[Dict[str, Any]]
            List of result records.
        """
        # Validate inputs
        page_size = max(1, min(page_size, 1000))
        if max_results is not None and max_results <= 0:
            return []

        results: List[Dict[str, Any]] = []
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

            # Validate response and extract results
            if not self._is_valid_page_response(data):
                break

            page_results = data["resultList"]["result"]  # type: ignore
            if not page_results:
                break

            # Add results and check for completion
            results.extend(page_results)  # type: ignore

            # Check if we have more pages
            next_cursor = data.get("nextCursorMark")  # type: ignore
            has_more_pages = (
                next_cursor
                and next_cursor != cursor_mark
                and len(page_results) >= current_page_size
            )
            if not has_more_pages:
                break
            cursor_mark = str(next_cursor)

        # Trim results if needed
        if max_results is not None and len(results) > max_results:
            results = results[:max_results]

        return results

    def _is_valid_page_response(self, data: Any) -> bool:
        """Check if the response is valid for pagination."""
        return (
            isinstance(data, dict)
            and data.get("hitCount", 0) > 0
            and isinstance(data.get("resultList"), dict)
            and "result" in data["resultList"]
        )

    def interactive_search(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
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
            except ValueError:
                logger.info("Please enter a valid integer, or '0' to quit.")
            except KeyboardInterrupt:
                logger.info("\nOperation cancelled by user.")
                return 0

    def _fetch_interactive_results(
        self, query: str, n: int, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch the requested number of results for interactive search."""
        logger.info(f"Fetching {n} results for '{query}' ...")
        results = self.fetch_all_pages(query, max_results=n, **kwargs)
        logger.info(f"Fetched {len(results)} results.")
        return results

    def search_and_parse(
        self, query: str, format: str = "json", **kwargs: Any
    ) -> List[Dict[str, Any]]:
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
            raise ValueError(f"Unsupported format '{format}'. Must be one of: {supported_formats}")

        format = format.lower()

        try:
            raw = self.search(query, format=format, **kwargs)

            # Type checking and parsing
            if format == "json":
                if not isinstance(raw, dict):
                    raise ValueError(f"Expected dict for JSON format, got {type(raw).__name__}")
                return EuropePMCParser.parse_json(raw)

            elif format in ("xml", "dc"):
                if not isinstance(raw, str):
                    raise ValueError(
                        f"Expected str for {format.upper()} format, got {type(raw).__name__}"
                    )

                if format == "xml":
                    return EuropePMCParser.parse_xml(raw)
                else:  # format == "dc"
                    return EuropePMCParser.parse_dc(raw)

        except EuropePMCError:
            # Re-raise EuropePMC errors as-is
            raise
        except Exception as e:
            raise ValueError(f"Parsing error for format '{format}': {e}")

        # This should never be reached due to the format validation above
        raise ValueError(f"Unknown format or parsing error for format '{format}'")

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
        EuropePMCError
            If the request fails.
        """
        try:
            # Use minimal page size for efficiency
            response = self.search(query, page_size=1, **kwargs)

            if isinstance(response, str):
                logger.warning("Received string response when expecting JSON for hit count.")
                return 0

            if not isinstance(response, dict) or "hitCount" not in response:
                logger.warning("Invalid response structure for hit count.")
                return 0

            return int(response["hitCount"])

        except Exception as e:
            logger.error(f"Error getting hit count: {e}")
            raise EuropePMCError(f"Error getting hit count: {e}")

    def search_ids_only(self, query: str, **kwargs: Any) -> List[str]:
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
