from typing import Optional, Dict, Any, List, Union
from .base import BaseAPIClient

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

    def __enter__(self):
        """
        Enter the runtime context related to this object.
        Returns self to allow method chaining.
        """
        return self
    
    def __repr__(self) -> str:
        return super().__repr__()


    def close(self) -> None:
        return super().close()


    def search(self, query: str, **kwargs) -> Union[Dict[str, Any], str]:
        """
        Search the Europe PMC publication database.

        Parameters
        ----------
        query : str
            User query. Possible options are:
            - a keyword or combination of keywords (e.g. HPV virus).
            - a phrase with enclosing speech marks (e.g. "human malaria").
            - a fielded search (e.g. auth:stoehr). Available search fields are listed in the Appendix 1 of the Reference Guide or can be retrieved using the fields module of the API.
            - a specific publication (e.g. ext_id:781840 src:med). Specify ext_id as the article identifier, and src as the source database. List of the data sources can be found on the help pages or in section 3 of the Reference Guide.
        resultType : str
            Response Type. Determines the fields returned by XML and JSON formats, but has no effect on the DC format. Possible values:
            - idlist: returns a list of IDs and sources for the given search terms
            - lite: returns key metadata for the given search terms
            - core: returns full metadata for a given publication ID; including abstract, full text links, and MeSH terms
        synonym : bool
            Synonym searches are not made by default (default = False). Queries can be expanded using MeSH terminology. For example, aspirin's synonym acetylsalicylic acid can be included by setting this to True. Case insensitive.
        cursorMark : str
            CursorMark for pagination. For the first request, omit or use '*'. For following pages, use the returned nextCursorMark.
        pageSize : int
            Number of articles per page. Default is 25. Max is 1000.
        sort : str
            Sort order. Default is relevance. Specify field and order (asc or desc), e.g., 'CITED asc'.
        format : str
            Response format. Can be XML, JSON, or DC (Dublin Core).
        callback : str
            For cross-domain JSONP requests. Format must be JSON.
        email : str
            Optional user email for EBI contact about Web Service news.

        Returns
        -------
        dict or str
            Parsed API response as JSON dict, or raw XML/DC string depending on the requested format.
        """
        params: dict = {
            "query": query,
            "resultType": kwargs.pop("resultType", "lite"),
            "synonym": str(kwargs.pop("synonym", False)).upper(),
            "pageSize": min(max(int(kwargs.pop("pageSize", 25)), 1), 1000),
            "format": kwargs.pop("format", "json"),
        }
        params.update(kwargs)
        try:
            r = self._get("search", params)
            if not r:
                raise EuropePMCError("No response from server")
            response_format = params["format"].lower()
            if response_format == "json":
                return r.json()
            else:
                return r.text
        except Exception as e:
            raise EuropePMCError(f"Error during search: {e}")


    def search_post(self, query: str, **kwargs) -> Union[dict, str]:
        """
        Search the Europe PMC publication database using a POST request.

        This endpoint is suitable for complex or very long queries that might exceed URL length limits.
        All parameters are sent as URL-encoded form data in the request body.

        Parameters
        ----------
        query : str
            User query. Possible options are:
            - a keyword or combination of keywords (e.g. HPV virus).
            - a phrase with enclosing speech marks (e.g. "human malaria").
            - a fielded search (e.g. auth:stoehr). Available search fields are listed in the Appendix 1 of the Reference Guide or can be retrieved using the fields module of the API.
            - a specific publication (e.g. ext_id:781840 src:med). Specify ext_id as the article identifier, and src as the source database. List of the data sources can be found on the help pages or in section 3 of the Reference Guide.
        resultType : str, optional
            Response Type. Determines the fields returned by XML and JSON formats, but has no effect on the DC format. Possible values:
            - idlist: returns a list of IDs and sources for the given search terms
            - lite: returns key metadata for the given search terms
            - core: returns full metadata for a given publication ID; including abstract, full text links, and MeSH terms
        synonym : bool, optional
            Synonym searches are not made by default (default = False). Queries can be expanded using MeSH terminology. For example, aspirin's synonym acetylsalicylic acid can be included by setting this to True. Case insensitive.
        cursorMark : str, optional
            CursorMark for pagination. For the first request, omit or use '*'. For following pages, use the returned nextCursorMark.
        pageSize : int, optional
            Number of articles per page. Default is 25. Max is 1000.
        sort : str, optional
            Sort order. Default is relevance. Specify field and order (asc or desc), e.g., 'CITED asc'.
        format : str, optional
            Response format. Can be XML, JSON, or DC (Dublin Core).
        callback : str, optional
            For cross-domain JSONP requests. Format must be JSON.
        email : str, optional
            Optional user email for EBI contact about Web Service news.

        Returns
        -------
        dict or str
            Parsed API response as JSON dict, or raw XML/DC string depending on the requested format.

        Raises
        ------
        EuropePMCError
            If the request fails or the response cannot be parsed.
        """
        data: dict = {
            "query": query,
            "resultType": kwargs.pop("resultType", "lite"),
            "synonym": str(kwargs.pop("synonym", False)).upper(),
            "pageSize": min(max(int(kwargs.pop("pageSize", 25)), 1), 1000),
            "format": kwargs.pop("format", "json"),
        }
        data.update(kwargs)
        response_format = data["format"].lower()
        try:
            # Ensure Content-Type is set for form data
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            r = self._post("searchPOST", data=data, headers=headers)
            if not r:
                raise EuropePMCError("No response from server")
            if response_format == "json":
                return r.json()
            else:
                return r.text
        except Exception as e:
            raise EuropePMCError(f"Error during POST search: {e}")


    def fetch_all_pages(
        self,
        query: str,
        page_size: int = 100,
        max_results: Optional[int] = None,
        **kwargs
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
        results: List[Dict[str, Any]] = []
        cursor_mark = "*"
        total_fetched = 0

        while True:
            data = self.search(query, pageSize=page_size, cursorMark=cursor_mark, **kwargs)
            if not isinstance(data, dict): # If data is not a dict (e.g., it's a string), stop fetching
                break
            if data.get("hitCount") == 0:
                logger.info(f"No results found for query: {query}")
                return results
            result_list = data.get("resultList", {})
            if not data or not isinstance(result_list, dict) or "result" not in result_list:
                break

            page_results = result_list["result"]
            results.extend(page_results)
            total_fetched += len(page_results)

            if max_results is not None and total_fetched >= max_results:
                return results[:max_results]

            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor

            # If the number of results on this page is less than page_size, we are done
            if len(page_results) < page_size:
                break
        return results
    

    def interactive_search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Interactive search: Show hit count, prompt user for number of results, fetch and return them.
        This method performs an initial search to get the hit count, prompts the user for how many results they want,
        and then fetches that many results, handling pagination as needed.
        The user can type 'q' or 'quit' to exit without fetching results.
        """
        # Step 1: Initial search to get hit count
        response = self.search(query, pageSize=1, **kwargs)

        if isinstance(response, str):
            logger.warning("Received a string response, which is unexpected. Please check your query or parameters.")
            return []
        if not response or "hitCount" not in response:
            logger.info("No results found or error occurred.")
            return []
        hit_count = int(response["hitCount"])
        logger.info(f"Your query '{query}' returned {hit_count:,} results.")

        # Step 2: Prompt user for number of results to fetch, allow quit
        while True:
            user_input = input(f"How many results would you like to retrieve? (max {hit_count}, 'q', 'quit' or 0 to quit): ").strip()
            if user_input in ("0", "q", "quit"):
                logger.info("No results will be fetched. Exiting interactive search.")
                return []
            try:
                n = int(user_input)
                if 1 <= n <= hit_count:
                    break
                logger.info(f"Please enter a number between 1 and {hit_count}, or '0' to quit.")
            except ValueError:
                logger.info("Please enter a valid integer, or '0' to quit.")

        # Step 3: Fetch the requested number of results
        logger.info(f"Fetching {n} results for '{query}' ...")
        results = self.fetch_all_pages(query, max_results=n, **kwargs)
        logger.info(f"Fetched {len(results)} results.")
        return results
    

    """def search_and_parse(self, query: str, format: str = "json", **kwargs) -> List[Dict[str, Any]]:
        raw = self.search(query, format=format, **kwargs)
        if format == "json" and isinstance(raw, dict):
            return self.parse_json(raw)
        elif format == "xml" and isinstance(raw, str):
            return self.parse_xml(raw)
        elif format == "dc" and isinstance(raw, str):
            return self.parse_dc(raw)
        else:
            raise ValueError("Unknown format or parsing error")"""
    


