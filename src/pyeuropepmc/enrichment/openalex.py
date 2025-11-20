"""
OpenAlex API client for comprehensive academic metadata.

OpenAlex provides unified graph data including works, authors,
venues, institutions, topics, and cited-by information.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient
from pyeuropepmc.enrichment.ror import RorClient

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

    Enhanced with ROR integration for detailed institutional metadata.

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
        enable_ror_enrichment: bool = True,
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
        enable_ror_enrichment : bool, optional
            Whether to enrich institutional data with ROR (default: True)
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email
        self.enable_ror_enrichment = enable_ror_enrichment

        # Initialize ROR client for institutional enrichment
        self.ror_client: RorClient | None
        if enable_ror_enrichment:
            self.ror_client = RorClient(
                email=email,
                cache_config=cache_config,
                rate_limit_delay=rate_limit_delay,
            )
        else:
            self.ror_client = None

        # Add email to user agent for polite pool if provided
        if email:
            user_agent = (
                f"pyeuropepmc/1.12.0 "
                f"(https://github.com/JonasHeinickeBio/pyEuropePMC; "
                f"mailto:{email})"
            )
            self.session.headers.update({"User-Agent": user_agent})
            logger.info(f"OpenAlex polite pool enabled with email: {email}")

        if enable_ror_enrichment:
            logger.info("ROR enrichment enabled for institutional data")

    def enrich(  # type: ignore[override]
        self,
        identifier: str | None = None,
        openalex_id: str | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any] | None:  # noqa: E501
        """
        Enrich paper metadata using OpenAlex API.

        When a DOI is provided as identifier, it first searches OpenAlex for the work,
        then enriches institutional data with ROR information if available.

        Parameters
        ----------
        identifier : str, optional
            Paper DOI (recommended for comprehensive enrichment with ROR)
        openalex_id : str, optional
            OpenAlex work ID (alternative to identifier)
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
            - institutions: List of institutions (enriched with ROR data when available)
            - topics: List of topics/concepts
            - venue: Venue information
            - biblio: Bibliographic information
            - abstract_inverted_index: Abstract as inverted index

        Raises
        ------
        ValueError
            If neither identifier nor OpenAlex ID is provided
        """
        if not identifier and not openalex_id:
            raise ValueError("Either identifier or OpenAlex ID is required")

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
            endpoint = f"doi:{identifier}"
            logger.debug(f"Enriching metadata for identifier: {identifier}")

        response = self._make_request(endpoint=endpoint, use_cache=use_cache)
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
        institutions = []  # Collect unique institutions for potential ROR enrichment

        for authorship in response.get("authorships", []):
            author_info = authorship.get("author", {})
            author_institutions = []

            for inst in authorship.get("institutions", []):
                inst_data = {
                    "id": inst.get("id"),
                    "display_name": inst.get("display_name"),
                    "country": inst.get("country_code"),  # Map to 'country' for consistency
                    "type": inst.get("type"),
                    "ror_id": inst.get("ror"),  # ROR ID if available
                }

                # Collect for ROR enrichment if enabled
                if self.enable_ror_enrichment and inst.get("ror"):
                    institutions.append(inst_data)

                author_institutions.append(inst_data)

            authors.append(
                {
                    "id": author_info.get("id"),
                    "display_name": author_info.get("display_name"),
                    "orcid": author_info.get("orcid"),
                    "institutions": author_institutions if author_institutions else None,
                    "position": authorship.get("author_position"),
                }
            )

        # Enrich institutions with ROR data if enabled
        enriched_institutions = []
        if self.enable_ror_enrichment and self.ror_client and institutions:
            enriched_institutions = self._enrich_institutions_with_ror(institutions)
        else:
            enriched_institutions = institutions

        # Update authors with enriched institutional data
        if enriched_institutions:
            authors = self._update_authors_with_ror_data(authors, enriched_institutions)

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
            "institutions": enriched_institutions if enriched_institutions else None,
            "topics": topics if topics else None,
            "venue": venue_info,
            "biblio": biblio if biblio else None,
            "doi": response.get("doi"),
            "ids": response.get("ids", {}),
            "abstract_inverted_index": response.get("abstract_inverted_index"),
            "referenced_works_count": response.get("referenced_works_count", 0),
            "related_works": response.get("related_works"),
        }

    def _enrich_institutions_with_ror(
        self, institutions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Enrich institution data with ROR information.

        Parameters
        ----------
        institutions : list[dict]
            List of institutions from OpenAlex

        Returns
        -------
        list[dict]
            Institutions enriched with ROR data
        """
        enriched = []

        for inst in institutions:
            ror_id = inst.get("ror_id")
            if ror_id and self.ror_client:
                # Validate ROR ID format to avoid passing invalid IDs like DOIs
                if "/" in ror_id and "ror.org" not in ror_id:
                    logger.debug(f"Skipping invalid ROR ID format: {ror_id}")
                    enriched.append(inst)
                    continue

                logger.debug(f"Enriching institution with ROR: {ror_id}")
                ror_data = self.ror_client.enrich(ror_id)
                if ror_data:
                    # Merge ROR data with OpenAlex institution data
                    enriched_inst = {**inst, **ror_data}
                    enriched.append(enriched_inst)
                else:
                    # Keep original data if ROR enrichment fails
                    enriched.append(inst)
            else:
                # No ROR ID available, keep original data
                enriched.append(inst)

        return enriched

    def _update_authors_with_ror_data(
        self, authors: list[dict[str, Any]], enriched_institutions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Update author institutions with enriched ROR data.

        Parameters
        ----------
        authors : list[dict]
            List of authors with institution data
        enriched_institutions : list[dict]
            Institutions enriched with ROR data

        Returns
        -------
        list[dict]
            Authors with updated institution data
        """
        # Create lookup map for enriched institutions by ROR ID
        inst_lookup = {
            inst.get("ror_id"): inst for inst in enriched_institutions if inst.get("ror_id")
        }

        updated_authors = []
        for author in authors:
            author_insts = author.get("institutions", [])
            if author_insts:
                updated_insts = []
                for inst in author_insts:
                    ror_id = inst.get("ror_id")
                    if ror_id and ror_id in inst_lookup:
                        # Replace with enriched data
                        updated_insts.append(inst_lookup[ror_id])
                    else:
                        # Keep original data
                        updated_insts.append(inst)
                author = {**author, "institutions": updated_insts}
            updated_authors.append(author)

        return updated_authors
