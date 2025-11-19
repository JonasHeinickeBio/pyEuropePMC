"""
Unpaywall API client for open access information.

Unpaywall provides information about open access availability
and full-text locations for academic papers.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["UnpaywallClient"]


class UnpaywallClient(BaseEnrichmentClient):
    """
    Client for Unpaywall API enrichment.

    Unpaywall provides:
    - Open access status
    - Best OA location for full text
    - License information
    - Repository information

    Note: Unpaywall requires an email parameter for API access.

    Examples
    --------
    >>> client = UnpaywallClient(email="your@email.com")
    >>> oa_info = client.enrich(doi="10.1371/journal.pone.0123456")
    >>> if oa_info and oa_info.get("is_oa"):
    ...     print("Open access available!")
    ...     print(f"URL: {oa_info.get('best_oa_location', {}).get('url')}")
    """

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(
        self,
        email: str,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize Unpaywall client.

        Parameters
        ----------
        email : str
            Email address (required by Unpaywall API)
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration

        Raises
        ------
        ValueError
            If email is not provided
        """
        if not email:
            raise ValueError("Email is required for Unpaywall API")

        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email
        logger.info(f"Unpaywall client initialized with email: {email}")

    def enrich(self, doi: str | None = None, **kwargs: Any) -> dict[str, Any] | None:
        """
        Enrich paper metadata using Unpaywall API.

        Parameters
        ----------
        doi : str
            Paper DOI (required)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Open access information with keys:
            - is_oa: Boolean indicating OA status
            - oa_status: OA status (gold, green, hybrid, bronze, closed)
            - best_oa_location: Best location to access OA version
                - url: URL to full text
                - version: Version (publishedVersion, acceptedVersion, submittedVersion)
                - license: License information
                - repository_type: Repository type
            - oa_locations: List of all OA locations
            - oa_locations_embargoed: Embargoed OA locations

        Raises
        ------
        ValueError
            If DOI is not provided
        """
        if not doi:
            raise ValueError("DOI is required for Unpaywall enrichment")

        logger.debug(f"Checking OA status for DOI: {doi}")

        # Make request with email parameter
        endpoint = f"{doi}"
        params = {"email": self.email}

        response = self._make_request(endpoint=endpoint, params=params)
        if response is None:
            logger.warning(f"No OA data found for DOI: {doi}")
            return None

        try:
            enriched = self._parse_unpaywall_response(response)
            logger.info(
                f"Successfully retrieved OA info for DOI: {doi} "
                f"(OA: {enriched.get('is_oa', False)})"
            )
            return enriched

        except Exception as e:
            logger.error(f"Error parsing Unpaywall response for {doi}: {e}")
            return None

    def _parse_unpaywall_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse Unpaywall API response into normalized metadata.

        Parameters
        ----------
        response : dict
            Unpaywall API response

        Returns
        -------
        dict
            Normalized OA information
        """
        # Extract OA status
        is_oa = response.get("is_oa", False)
        oa_status = response.get("oa_status", "closed")

        # Extract best OA location
        best_oa_location = None
        best_oa_raw = response.get("best_oa_location")
        if best_oa_raw:
            best_oa_location = {
                "url": best_oa_raw.get("url"),
                "url_for_pdf": best_oa_raw.get("url_for_pdf"),
                "url_for_landing_page": best_oa_raw.get("url_for_landing_page"),
                "version": best_oa_raw.get("version"),
                "license": best_oa_raw.get("license"),
                "repository_type": best_oa_raw.get("host_type"),
                "evidence": best_oa_raw.get("evidence"),
            }

        # Extract all OA locations
        oa_locations = []
        for loc in response.get("oa_locations", []):
            oa_locations.append(
                {
                    "url": loc.get("url"),
                    "url_for_pdf": loc.get("url_for_pdf"),
                    "version": loc.get("version"),
                    "license": loc.get("license"),
                    "repository_type": loc.get("host_type"),
                }
            )

        # Extract embargoed locations
        oa_locations_embargoed = []
        for loc in response.get("oa_locations_embargoed", []):
            oa_locations_embargoed.append(
                {
                    "url": loc.get("url"),
                    "version": loc.get("version"),
                    "license": loc.get("license"),
                }
            )

        return {
            "source": "unpaywall",
            "is_oa": is_oa,
            "oa_status": oa_status,
            "best_oa_location": best_oa_location,
            "oa_locations": oa_locations if oa_locations else None,
            "oa_locations_embargoed": oa_locations_embargoed if oa_locations_embargoed else None,
            "first_oa_date": response.get("first_oa_date"),
            "journal_is_oa": response.get("journal_is_oa", False),
            "journal_is_in_doaj": response.get("journal_is_in_doaj", False),
            "publisher": response.get("publisher"),
            "year": response.get("year"),
        }
