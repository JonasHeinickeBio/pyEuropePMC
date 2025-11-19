"""
OpenAlex API client for comprehensive academic metadata.

OpenAlex provides unified graph data including works, authors,
venues, institutions, topics, and cited-by information.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["OpenAlexClient"]


class OpenAlexClient(BaseEnrichmentClient):
    """
    Client for OpenAlex API enrichment.

    OpenAlex provides:
    - Comprehensive work metadata
    - Author information and affiliations
    - Venue/journal information
    - Institution data
    - Topics and concepts
    - Citation counts and cited-by information
    - Open access status

    Examples
    --------
    >>> client = OpenAlexClient(email="your@email.com")
    >>> metadata = client.enrich(doi="10.1371/journal.pone.0123456")
    >>> if metadata:
    ...     print(f"Citations: {metadata.get('citation_count')}")
    ...     print(f"Topics: {metadata.get('topics')}")
    """

    BASE_URL = "https://api.openalex.org/works"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        email: str | None = None,
    ) -> None:
        """
        Initialize OpenAlex client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        email : str, optional
            Email for polite pool (gets into polite pool for faster, more consistent response)
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email

        # Add email to user agent for polite pool if provided
        if email:
            user_agent = (
                f"pyeuropepmc/1.12.0 "
                f"(https://github.com/JonasHeinickeBio/pyEuropePMC; "
                f"mailto:{email})"
            )
            self.session.headers.update({"User-Agent": user_agent})
            logger.info(f"OpenAlex polite pool enabled with email: {email}")

    def enrich(
        self, doi: str | None = None, openalex_id: str | None = None, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich paper metadata using OpenAlex API.

        Parameters
        ----------
        doi : str, optional
            Paper DOI
        openalex_id : str, optional
            OpenAlex work ID (alternative to DOI)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Enriched metadata with keys:
            - openalex_id: OpenAlex work ID
            - title: Work title
            - publication_year: Year published
            - publication_date: Full publication date
            - type: Work type
            - citation_count: Citation count
            - cited_by_count: Same as citation_count
            - is_oa: Open access status
            - oa_status: OA status (gold, green, hybrid, bronze, closed)
            - oa_url: URL to OA version
            - authors: List of authors with affiliations
            - institutions: List of institutions
            - topics: List of topics/concepts
            - venue: Venue information
            - biblio: Bibliographic information
            - abstract_inverted_index: Abstract as inverted index

        Raises
        ------
        ValueError
            If neither DOI nor OpenAlex ID is provided
        """
        if not doi and not openalex_id:
            raise ValueError("Either DOI or OpenAlex ID is required")

        # Construct endpoint
        if openalex_id:
            # OpenAlex IDs can be URLs or just IDs
            if openalex_id.startswith("https://openalex.org/"):
                endpoint = openalex_id.split("/")[-1]
            else:
                endpoint = openalex_id
            logger.debug(f"Enriching metadata for OpenAlex ID: {openalex_id}")
        else:
            # Use DOI filter
            endpoint = f"doi:{doi}"
            logger.debug(f"Enriching metadata for DOI: {doi}")

        response = self._make_request(endpoint=endpoint)
        if response is None:
            logger.warning(f"No data found for: {endpoint}")
            return None

        try:
            enriched = self._parse_openalex_response(response)
            logger.info(f"Successfully enriched metadata from OpenAlex: {endpoint}")
            return enriched

        except Exception as e:
            logger.error(f"Error parsing OpenAlex response for {endpoint}: {e}")
            return None

    def _parse_openalex_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse OpenAlex API response into normalized metadata.

        Parameters
        ----------
        response : dict
            OpenAlex API response

        Returns
        -------
        dict
            Normalized metadata
        """
        # Extract authors with affiliations
        authors = []
        for authorship in response.get("authorships", []):
            author_info = authorship.get("author", {})
            institutions = []
            for inst in authorship.get("institutions", []):
                institutions.append(
                    {
                        "id": inst.get("id"),
                        "display_name": inst.get("display_name"),
                        "country_code": inst.get("country_code"),
                        "type": inst.get("type"),
                    }
                )

            authors.append(
                {
                    "id": author_info.get("id"),
                    "display_name": author_info.get("display_name"),
                    "orcid": author_info.get("orcid"),
                    "institutions": institutions if institutions else None,
                    "position": authorship.get("author_position"),
                }
            )

        # Extract topics
        topics = []
        for topic in response.get("topics", []):
            topics.append(
                {
                    "id": topic.get("id"),
                    "display_name": topic.get("display_name"),
                    "score": topic.get("score"),
                }
            )

        # Extract venue information
        venue_info = None
        primary_location = response.get("primary_location", {})
        if primary_location:
            source = primary_location.get("source", {})
            if source:
                venue_info = {
                    "id": source.get("id"),
                    "display_name": source.get("display_name"),
                    "issn": source.get("issn"),
                    "type": source.get("type"),
                    "is_oa": source.get("is_oa"),
                }

        # Extract open access information
        oa_info = response.get("open_access", {})
        is_oa = oa_info.get("is_oa", False)
        oa_status = oa_info.get("oa_status", "closed")
        oa_url = oa_info.get("oa_url")

        # Extract bibliographic information
        biblio = response.get("biblio", {})

        return {
            "source": "openalex",
            "openalex_id": response.get("id"),
            "title": response.get("title"),
            "publication_year": response.get("publication_year"),
            "publication_date": response.get("publication_date"),
            "type": response.get("type"),
            "citation_count": response.get("cited_by_count", 0),
            "cited_by_count": response.get("cited_by_count", 0),
            "is_oa": is_oa,
            "oa_status": oa_status,
            "oa_url": oa_url,
            "authors": authors if authors else None,
            "topics": topics if topics else None,
            "venue": venue_info,
            "biblio": biblio if biblio else None,
            "doi": response.get("doi"),
            "ids": response.get("ids", {}),
            "abstract_inverted_index": response.get("abstract_inverted_index"),
            "referenced_works_count": response.get("referenced_works_count", 0),
            "related_works": response.get("related_works"),
        }
