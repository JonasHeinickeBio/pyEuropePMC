"""
Semantic Scholar API client for academic impact metrics.

Semantic Scholar provides citation counts, influential citations,
abstracts, and venue information.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
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

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper"

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
        self, doi: str | None = None, semantic_scholar_id: str | None = None, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich paper metadata using Semantic Scholar API.

        Parameters
        ----------
        doi : str, optional
            Paper DOI
        semantic_scholar_id : str, optional
            Semantic Scholar paper ID (alternative to DOI)
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
            - authors: List of authors
            - fields_of_study: List of research fields
            - s2_paper_id: Semantic Scholar paper ID
            - external_ids: External identifiers (DOI, PubMed, etc.)

        Raises
        ------
        ValueError
            If neither DOI nor Semantic Scholar ID is provided
        """
        if not doi and not semantic_scholar_id:
            raise ValueError("Either DOI or Semantic Scholar ID is required")

        # Construct endpoint
        if semantic_scholar_id:
            endpoint = semantic_scholar_id
            logger.debug(f"Enriching metadata for S2 ID: {semantic_scholar_id}")
        else:
            endpoint = f"DOI:{doi}"
            logger.debug(f"Enriching metadata for DOI: {doi}")

        # Define fields to retrieve
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
            "referenceCount",
            "openAccessPdf",
        ]

        params = {"fields": ",".join(fields)}

        response = self._make_request(endpoint=endpoint, params=params)
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
        # Extract authors
        authors = []
        for author in response.get("authors", []):
            authors.append(
                {
                    "name": author.get("name"),
                    "author_id": author.get("authorId"),
                }
            )

        # Extract external IDs
        external_ids = response.get("externalIds", {})

        # Extract open access PDF
        oa_pdf = response.get("openAccessPdf")
        oa_pdf_url = oa_pdf.get("url") if oa_pdf else None

        return {
            "source": "semantic_scholar",
            "s2_paper_id": response.get("paperId"),
            "title": response.get("title"),
            "abstract": response.get("abstract"),
            "venue": response.get("venue"),
            "year": response.get("year"),
            "citation_count": response.get("citationCount", 0),
            "influential_citation_count": response.get("influentialCitationCount", 0),
            "reference_count": response.get("referenceCount", 0),
            "authors": authors if authors else None,
            "fields_of_study": response.get("fieldsOfStudy"),
            "external_ids": external_ids if external_ids else None,
            "open_access_pdf_url": oa_pdf_url,
        }
