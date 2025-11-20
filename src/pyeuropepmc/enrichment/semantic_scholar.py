"""
Semantic Scholar API client for academic impact metrics.

Semantic Scholar provides citation counts, influential citations,
abstracts, and venue information.
"""

import logging
import time
from typing import Any

import requests

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["SemanticScholarClient"]


class SemanticScholarClient(BaseEnrichmentClient):
    """
    Client for Semantic Scholar API enrichment.

    Semantic Scholar provides:
    - Citation counts
    - Influential citation counts
    - Abstract
    - Venue information
    - Author information
    - Fields of study
    - References and citations

    Examples
    --------
    >>> client = SemanticScholarClient()
    >>> metrics = client.enrich(doi="10.1371/journal.pone.0123456")
    >>> if metrics:
    ...     print(f"Citations: {metrics.get('citation_count')}")
    ...     print(f"Influential citations: {metrics.get('influential_citation_count')}")
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Initialize Semantic Scholar client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        api_key : str, optional
            API key for higher rate limits (recommended but not required)
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.api_key = api_key

        # Add API key to headers if provided
        if api_key:
            self.session.headers.update({"x-api-key": api_key})
            logger.info("Semantic Scholar API key configured")

    def enrich(
        self,
        identifier: str | None = None,
        use_cache: bool = True,
        semantic_scholar_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Enrich paper metadata using Semantic Scholar API.

        Parameters
        ----------
        identifier : str, optional
            Paper DOI
        use_cache : bool, optional
            Whether to use cached results (default: True)
        semantic_scholar_id : str, optional
            Semantic Scholar paper ID (alternative to identifier)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Enriched metadata with keys:
            - citation_count: Total citation count
            - influential_citation_count: Influential citation count
            - abstract: Paper abstract
            - venue: Publication venue
            - year: Publication year
            - authors: List of authors with enhanced information:
                - name: Author name
                - author_id: Semantic Scholar author ID
                - url: Link to author's Semantic Scholar profile
                - affiliations: Author affiliations (if available)
                - homepage: Author's homepage (if available)
            - fields_of_study: List of research fields
            - s2_paper_id: Semantic Scholar paper ID
            - external_ids: External identifiers (DOI, PubMed, etc.)
            - open_access_pdf_url: URL to open access PDF (if available)
            - publication_types: List of publication types
            - journal: Journal information
            - tldr: TL;DR summary (if available)

        Raises
        ------
        ValueError
            If neither identifier nor Semantic Scholar ID is provided
        """
        if not identifier and not semantic_scholar_id:
            raise ValueError("Either identifier or Semantic Scholar ID is required")

        # Construct endpoint
        if semantic_scholar_id:
            endpoint = f"paper/{semantic_scholar_id}"
            logger.debug(f"Enriching metadata for S2 ID: {semantic_scholar_id}")
        else:
            endpoint = f"paper/{identifier}"
            logger.debug(f"Enriching metadata for identifier: {identifier}")

        # Define comprehensive fields to retrieve
        fields = [
            "title",
            "abstract",
            "venue",
            "year",
            "citationCount",
            "influentialCitationCount",
            "authors",
            "fieldsOfStudy",
            "externalIds",
            "paperId",
            "corpusId",
            "referenceCount",
            "openAccessPdf",
            "publicationTypes",
            "publicationDate",
            "journal",
            "tldr",
            "s2FieldsOfStudy",
        ]

        params = {"fields": ",".join(fields)}

        response = self._make_request(endpoint=endpoint, params=params, use_cache=use_cache)
        if response is None:
            logger.warning(f"No data found for: {endpoint}")
            return None

        try:
            enriched = self._parse_semantic_scholar_response(response)
            logger.info(f"Successfully enriched metadata from Semantic Scholar: {endpoint}")
            return enriched

        except Exception as e:
            logger.error(f"Error parsing Semantic Scholar response for {endpoint}: {e}")
            return None

    def _make_post_request(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any] | list[Any] | None:
        """
        Make HTTP POST request with retries and caching.

        Parameters
        ----------
        endpoint : str
            API endpoint (will be appended to base_url)
        json_data : dict, optional
            JSON data to send in request body
        params : dict, optional
            Query parameters
        headers : dict, optional
            Additional headers
        use_cache : bool, optional
            Whether to use caching for this request (default: True)

        Returns
        -------
        dict, list, or None
            Response data, or None if request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Check cache first (for idempotent requests)
        cache_key = ""
        if use_cache and self._cache.config.enabled:
            cache_key = f"POST:{url}:{str(params)}:{str(json_data)}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for POST {url}")
                return cached  # type: ignore[no-any-return]

        # Prepare headers
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)

        try:
            logger.debug(f"POST request to {url} with params={params}")
            response = self.session.post(
                url, json=json_data, params=params, headers=request_headers, timeout=self.timeout
            )

            # Handle 404 gracefully - return None instead of raising
            if response.status_code == 404:
                logger.info(f"Resource not found at {url}")
                return None

            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Cache successful response (for idempotent requests)
            if use_cache and self._cache.config.enabled:
                self._cache.set(cache_key, data)

            logger.info(f"POST request to {url} succeeded")
            return data  # type: ignore[no-any-return]

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.info(f"Resource not found at {url}")
                return None
            logger.error(f"HTTP error for POST {url}: {e}")
            raise APIClientError(message=f"HTTP error: {e}") from e
        except requests.RequestException as e:
            logger.error(f"POST request failed for {url}: {e}")
            raise APIClientError(message=f"Request failed: {e}") from e
        except ValueError as e:
            logger.error(f"Invalid JSON response from POST {url}: {e}")
            return None
        finally:
            time.sleep(self.rate_limit_delay)

    def _parse_semantic_scholar_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse Semantic Scholar API response into normalized metadata.

        Parameters
        ----------
        response : dict
            Semantic Scholar API response

        Returns
        -------
        dict
            Normalized metadata
        """
        # Extract authors with enhanced information
        authors = []
        for author in response.get("authors", []):
            author_data = {
                "name": author.get("name"),
                "author_id": author.get("authorId"),
            }

            # Add Semantic Scholar author URL if authorId is available
            if author.get("authorId"):
                author_data["url"] = f"https://www.semanticscholar.org/author/{author['authorId']}"

            # Add any additional author fields that might be present
            if author.get("url"):
                author_data["url"] = author["url"]
            if author.get("affiliations"):
                author_data["affiliations"] = author["affiliations"]
            if author.get("homepage"):
                author_data["homepage"] = author["homepage"]

            authors.append(author_data)

        # Extract external IDs
        external_ids = response.get("externalIds", {})

        # Extract open access PDF
        oa_pdf = response.get("openAccessPdf")
        oa_pdf_url = oa_pdf.get("url") if oa_pdf else None

        # Extract journal information
        journal = response.get("journal")
        journal_info = None
        if journal:
            journal_info = {
                "name": journal.get("name"),
                "volume": journal.get("volume"),
                "pages": journal.get("pages"),
            }

        # Extract TL;DR summary
        tldr = response.get("tldr")
        tldr_text = tldr.get("text") if tldr else None

        return {
            "source": "semantic_scholar",
            "s2_paper_id": response.get("paperId"),
            "corpus_id": response.get("corpusId"),
            "title": response.get("title"),
            "abstract": response.get("abstract"),
            "venue": response.get("venue"),
            "year": response.get("year"),
            "publication_date": response.get("publicationDate"),
            "citation_count": response.get("citationCount", 0),
            "influential_citation_count": response.get("influentialCitationCount", 0),
            "reference_count": response.get("referenceCount", 0),
            "authors": authors if authors else None,
            "fields_of_study": response.get("fieldsOfStudy"),
            "s2_fields_of_study": response.get("s2FieldsOfStudy"),
            "publication_types": response.get("publicationTypes"),
            "journal": journal_info,
            "external_ids": external_ids if external_ids else None,
            "open_access_pdf_url": oa_pdf_url,
            "tldr": tldr_text,
        }

    def enrich_batch(
        self, identifiers: list[str], use_cache: bool = True, **kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        """
        Enrich multiple papers at once using the batch API.

        Parameters
        ----------
        identifiers : list[str]
            List of paper identifiers (DOIs, Semantic Scholar IDs, etc.)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict[str, dict | None]
            Dictionary mapping identifiers to enrichment results
        """
        if not identifiers:
            return {}

        # Limit batch size to API constraints (500 papers max)
        batch_size = 500
        results = {}

        for i in range(0, len(identifiers), batch_size):
            batch = identifiers[i : i + batch_size]

            # Define comprehensive fields for batch request
            fields = [
                "title",
                "abstract",
                "venue",
                "year",
                "citationCount",
                "influentialCitationCount",
                "authors",
                "fieldsOfStudy",
                "externalIds",
                "paperId",
                "corpusId",
                "referenceCount",
                "openAccessPdf",
                "publicationTypes",
                "publicationDate",
                "journal",
                "tldr",
            ]

            params = {"fields": ",".join(fields)}
            json_data = {"ids": batch}

            response = self._make_post_request(
                endpoint="paper/batch", params=params, json_data=json_data, use_cache=use_cache
            )

            if response and isinstance(response, list):
                for item in response:
                    if isinstance(item, dict):
                        paper_id = item.get("paperId")
                        if paper_id and isinstance(paper_id, str):
                            parsed = self._parse_semantic_scholar_response(item)
                            results[paper_id] = parsed
                        else:
                            # If no paperId, try to match by external IDs
                            external_ids = item.get("externalIds", {})
                            doi = external_ids.get("DOI")
                            if doi and isinstance(doi, str):
                                parsed = self._parse_semantic_scholar_response(item)
                                results[doi] = parsed
            else:
                logger.warning(f"Batch request failed for batch starting at index {i}")

        return results

    def enrich_author(
        self, author_id: str, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich author information using Semantic Scholar API.

        Parameters
        ----------
        author_id : str
            Semantic Scholar author ID
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Author metadata with keys:
            - author_id: Semantic Scholar author ID
            - name: Author name
            - url: Author profile URL
            - affiliations: List of affiliations
            - homepage: Author homepage
            - paper_count: Total number of papers
            - citation_count: Total citation count
            - h_index: H-index
            - external_ids: External identifiers
        """
        fields = [
            "name",
            "url",
            "affiliations",
            "homepage",
            "paperCount",
            "citationCount",
            "hIndex",
            "externalIds",
        ]

        params = {"fields": ",".join(fields)}
        response = self._make_request(
            endpoint=f"author/{author_id}", params=params, use_cache=use_cache
        )

        if response is None:
            logger.warning(f"No data found for author: {author_id}")
            return None

        try:
            return {
                "source": "semantic_scholar",
                "author_id": response.get("authorId"),
                "name": response.get("name"),
                "url": response.get("url"),
                "affiliations": response.get("affiliations"),
                "homepage": response.get("homepage"),
                "paper_count": response.get("paperCount"),
                "citation_count": response.get("citationCount"),
                "h_index": response.get("hIndex"),
                "external_ids": response.get("externalIds"),
            }
        except Exception as e:
            logger.error(f"Error parsing author response for {author_id}: {e}")
            return None

    def search_papers(
        self, query: str, limit: int = 100, use_cache: bool = True, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Search for papers using Semantic Scholar's relevance search.

        Parameters
        ----------
        query : str
            Search query
        limit : int, optional
            Maximum number of results (default: 100, max: 1000)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional search parameters (year, venue, fieldsOfStudy, etc.)

        Returns
        -------
        list[dict]
            List of paper metadata dictionaries
        """
        params = {
            "query": query,
            "limit": min(limit, 1000),  # API limit
            "fields": (
                "title,abstract,venue,year,citationCount,"
                "influentialCitationCount,authors,fieldsOfStudy,"
                "externalIds,paperId"
            ),
        }

        # Add optional filters
        valid_keys = [
            "year",
            "venue",
            "fieldsOfStudy",
            "minCitationCount",
            "publicationDateOrYear",
        ]
        for key, value in kwargs.items():
            if key in valid_keys:
                params[key] = value

        response = self._make_request(endpoint="paper/search", params=params, use_cache=use_cache)

        if response is None:
            logger.warning(f"No search results for query: {query}")
            return []

        try:
            data = response.get("data", [])
            results = []
            for item in data:
                if isinstance(item, dict):
                    parsed = self._parse_semantic_scholar_response(item)
                    results.append(parsed)
            return results
        except Exception as e:
            logger.error(f"Error parsing search response for query '{query}': {e}")
            return []
