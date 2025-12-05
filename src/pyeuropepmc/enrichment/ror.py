"""
ROR (Research Organization Registry) enrichment client.

This module provides functionality to retrieve detailed institutional information
from the Research Organization Registry API.
"""

import logging
from typing import Any

from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["RorClient"]


class RorClient(BaseEnrichmentClient):
    """
    Client for retrieving institutional data from ROR API.

    ROR provides comprehensive information about research organizations,
    including names, locations, relationships, and external identifiers.
    """

    def __init__(
        self,
        email: str | None = None,
        client_id: str | None = None,
        cache_config: Any | None = None,
        rate_limit_delay: float = 1.0,
    ) -> None:
        """
        Initialize ROR client.

        Parameters
        ----------
        email : str, optional
            Email for polite pool access
        client_id : str, optional
            Client ID for higher rate limits
        cache_config : CacheConfig, optional
            Cache configuration
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        """
        # Set up user agent with email if provided
        user_agent = None
        if email:
            user_agent = (
                f"pyeuropepmc/1.12.0 "
                f"(https://github.com/JonasHeinickeBio/pyEuropePMC; "
                f"mailto:{email})"
            )

        super().__init__(
            base_url="https://api.ror.org/v2",
            rate_limit_delay=rate_limit_delay,
            cache_config=cache_config,
            user_agent=user_agent,
        )

        # Store client_id for headers
        self.client_id = client_id

        logger.info("ROR client initialized")

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Retrieve organization data from ROR.

        Parameters
        ----------
        identifier : str, optional
            ROR identifier (can be full URL, domain+ID, or just ID)
        **kwargs
            Additional parameters (unused for ROR)

        Returns
        -------
        dict or None
            ROR organization data, or None if not found
        """
        if not identifier:
            logger.warning("No ROR ID provided for enrichment")
            return None

        # Normalize ROR ID to just the ID part
        normalized_id = self._normalize_ror_id(identifier)
        if not normalized_id:
            logger.debug(f"Invalid ROR ID format: {identifier}")
            return None

        endpoint = f"/organizations/{normalized_id}"

        try:
            logger.debug(f"Fetching ROR data for: {normalized_id}")
            headers = {}
            if self.client_id:
                headers["Client-Id"] = self.client_id
            data = self._make_request(endpoint, headers=headers, use_cache=use_cache)

            if data:
                logger.info(f"Successfully retrieved ROR data for: {normalized_id}")
                return self._parse_ror_response(data)
            else:
                logger.warning(f"ROR ID not found: {normalized_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching ROR data for {normalized_id}: {e}")
            return None

    def _normalize_ror_id(self, ror_id: str) -> str | None:
        """
        Normalize ROR ID to the standard format.

        Parameters
        ----------
        ror_id : str
            ROR identifier in various formats

        Returns
        -------
        str or None
            Normalized ROR ID (just the ID part), or None if invalid
        """
        if not ror_id:
            return None

        # Remove any URL prefix (handle multiple prefixes)
        while "ror.org/" in ror_id:
            ror_id = ror_id.split("ror.org/", 1)[1]

        # Remove any leading/trailing slashes
        ror_id = ror_id.strip("/")

        # Basic validation: should be alphanumeric with possible hyphens
        if not all(c.isalnum() or c == "-" for c in ror_id):
            return None

        return ror_id

    def _parse_ror_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse ROR API response into standardized format.

        Parameters
        ----------
        data : dict
            Raw ROR API response

        Returns
        -------
        dict
            Parsed and cleaned ROR data
        """
        parsed = {
            "ror_id": data.get("id"),
            "status": data.get("status"),
            "types": data.get("types", []),
            "established": data.get("established"),
        }

        # Names
        self._parse_names(data, parsed)

        # Locations
        self._parse_locations(data, parsed)

        # Links
        self._parse_links(data, parsed)

        # External IDs
        self._parse_external_ids(data, parsed)

        # Relationships and domains
        parsed["relationships"] = data.get("relationships", [])
        parsed["domains"] = data.get("domains", [])

        return parsed

    def _parse_names(self, data: dict[str, Any], parsed: dict[str, Any]) -> None:
        """Parse names from ROR response."""
        names = data.get("names", [])
        if not names:
            return

        parsed["names"] = names

        # Find display name
        for name in names:
            if "ror_display" in name.get("types", []):
                parsed["display_name"] = name.get("value")
                return

        # Fallback to first label
        for name in names:
            if "label" in name.get("types", []):
                parsed["display_name"] = name.get("value")
                break

    def _parse_locations(self, data: dict[str, Any], parsed: dict[str, Any]) -> None:
        """Parse locations from ROR response."""
        locations = data.get("locations", [])
        if not locations:
            return

        parsed["locations"] = locations
        primary_loc = locations[0]
        geonames = primary_loc.get("geonames_details", {})
        if geonames:
            parsed["country"] = geonames.get("country_name")
            parsed["country_code"] = geonames.get("country_code")
            parsed["city"] = geonames.get("name")
            parsed["latitude"] = geonames.get("lat")
            parsed["longitude"] = geonames.get("lng")

    def _parse_links(self, data: dict[str, Any], parsed: dict[str, Any]) -> None:
        """Parse links from ROR response."""
        links = data.get("links", [])
        if not links:
            return

        parsed["links"] = links
        for link in links:
            if link.get("type") == "website":
                parsed["website"] = link.get("value")
                break

    def _parse_external_ids(self, data: dict[str, Any], parsed: dict[str, Any]) -> None:
        """Parse external IDs from ROR response."""
        external_ids = data.get("external_ids", [])
        if not external_ids:
            return

        parsed["external_ids"] = external_ids

        # Extract common IDs
        id_mapping = {
            "fundref": "fundref_id",
            "grid": "grid_id",
            "isni": "isni",
            "wikidata": "wikidata_id",
        }

        for ext_id in external_ids:
            id_type = ext_id.get("type")
            preferred = ext_id.get("preferred")
            if preferred and id_type in id_mapping:
                parsed[id_mapping[id_type]] = preferred
