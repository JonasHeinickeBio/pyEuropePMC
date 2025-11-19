"""
CrossRef API client for enriching paper metadata.

CrossRef provides comprehensive bibliographic metadata, citations,
and licensing information for academic papers.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["CrossRefClient"]


class CrossRefClient(BaseEnrichmentClient):
    """
    Client for CrossRef API enrichment.

    CrossRef provides metadata including:
    - Title, authors, abstract
    - Journal information
    - Publication dates
    - Citation counts
    - License information
    - References and citations
    - Funding information

    Examples
    --------
    >>> client = CrossRefClient()
    >>> metadata = client.enrich(doi="10.1371/journal.pone.0123456")
    >>> if metadata:
    ...     print(metadata.get("title"))
    ...     print(metadata.get("citation_count"))
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        email: str | None = None,
    ) -> None:
        """
        Initialize CrossRef client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        email : str, optional
            Email for polite pool (gets faster response times)
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email

        # Add email to headers for polite pool if provided
        if email:
            self.session.headers.update({"mailto": email})
            logger.info(f"CrossRef polite pool enabled with email: {email}")

    def enrich(self, doi: str | None = None, **kwargs: Any) -> dict[str, Any] | None:
        """
        Enrich paper metadata using CrossRef API.

        Parameters
        ----------
        doi : str
            Paper DOI (required)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Enriched metadata with keys:
            - title: Paper title
            - authors: List of author names
            - abstract: Paper abstract
            - journal: Journal name
            - publication_date: Publication date
            - citation_count: Citation count
            - references_count: Number of references
            - license: License information
            - funder: Funding information
            - is_referenced_by_count: Times cited

        Raises
        ------
        ValueError
            If DOI is not provided
        """
        if not doi:
            raise ValueError("DOI is required for CrossRef enrichment")

        logger.debug(f"Enriching metadata for DOI: {doi}")

        # Make request to CrossRef API
        response = self._make_request(endpoint=doi)
        if response is None:
            logger.warning(f"No data found for DOI: {doi}")
            return None

        # Extract metadata from response
        try:
            message = response.get("message", {})
            if not message:
                logger.warning(f"Empty response from CrossRef for DOI: {doi}")
                return None

            # Parse and normalize metadata
            enriched = self._parse_crossref_response(message)
            logger.info(f"Successfully enriched metadata for DOI: {doi}")
            return enriched

        except Exception as e:
            logger.error(f"Error parsing CrossRef response for {doi}: {e}")
            return None

    def _parse_crossref_response(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Parse CrossRef API response into normalized metadata.

        Parameters
        ----------
        message : dict
            CrossRef API message object

        Returns
        -------
        dict
            Normalized metadata
        """
        # Extract title
        title_list = message.get("title", [])
        title = title_list[0] if title_list else None

        # Extract authors
        authors = []
        for author in message.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)

        # Extract abstract
        abstract = message.get("abstract")

        # Extract journal/container title
        container_title = message.get("container-title", [])
        journal = container_title[0] if container_title else None

        # Extract publication date
        pub_date_parts = message.get("published", {}).get("date-parts", [[]])
        pub_date = None
        if pub_date_parts and pub_date_parts[0]:
            date_parts = pub_date_parts[0]
            if len(date_parts) >= 3:
                pub_date = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
            elif len(date_parts) >= 2:
                pub_date = f"{date_parts[0]}-{date_parts[1]:02d}"
            elif len(date_parts) >= 1:
                pub_date = str(date_parts[0])

        # Extract citation metrics
        citation_count = message.get("is-referenced-by-count", 0)
        references_count = message.get("references-count", 0)

        # Extract license information
        licenses = message.get("license", [])
        license_info = None
        if licenses:
            license_info = {
                "url": licenses[0].get("URL"),
                "start": licenses[0].get("start", {}).get("date-time"),
                "delay_in_days": licenses[0].get("delay-in-days"),
            }

        # Extract funder information
        funders = []
        for funder in message.get("funder", []):
            funders.append(
                {
                    "name": funder.get("name"),
                    "doi": funder.get("DOI"),
                    "award": funder.get("award", []),
                }
            )

        return {
            "source": "crossref",
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "journal": journal,
            "publication_date": pub_date,
            "citation_count": citation_count,
            "references_count": references_count,
            "license": license_info,
            "funders": funders if funders else None,
            "type": message.get("type"),
            "issn": message.get("ISSN"),
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "page": message.get("page"),
            "publisher": message.get("publisher"),
        }
