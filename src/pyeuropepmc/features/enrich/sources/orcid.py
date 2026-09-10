"""
ORCID API client for author metadata enrichment.

ORCID (Open Researcher and Contributor ID) provides a persistent digital
identifier for researchers. This client allows looking up researcher
profiles, their works, and affiliations.

The public API requires no authentication for public records.

References
----------
- ORCID Public API: https://pub.orcid.org/v3.0/
- ORCID API documentation: https://info.orcid.org/documentation/
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.features.enrich.base import BaseEnrichmentClient
from pyeuropepmc.features.literature.normalization import normalize_doi

logger = logging.getLogger(__name__)

__all__ = ["OrcidClient"]

# Normalize ORCID iD to bare format (0000-0002-1825-0097)
_ORCID_PATTERN = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])")


class OrcidClient(BaseEnrichmentClient):
    """
    Client for ORCID API enrichment.

    Provides researcher profile data, publications lists, and
    affiliation information from the ORCID registry.

    The ORCID Public API (pub.orcid.org) is free and does not require
    authentication for reading public data.

    Examples
    --------
    >>> client = OrcidClient()
    >>> profile = client.enrich(orcid="0000-0002-1825-0097")
    >>> if profile:
    ...     print(f"Name: {profile.get('name')}")
    ...     print(f"Works: {len(profile.get('works', []))}")
    """

    BASE_URL = "https://pub.orcid.org/v3.0"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize ORCID client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0).
        timeout : int, optional
            Request timeout in seconds (default: 15).
        cache_config : CacheConfig, optional
            Cache configuration.
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        # ORCID API expects application/json
        self.session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def enrich(
        self,
        identifier: str | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Enrich metadata by ORCID iD.

        Parameters
        ----------
        identifier : str
            ORCID iD (e.g. ``"0000-0002-1825-0097"``).
            Accepts bare iDs, URLs, and https://orcid.org/ prefixes.
        **kwargs
            Additional parameters (unused).

        Returns
        -------
        dict or None
            Profile data with keys: name, works, affiliations, etc.
        """
        if identifier is None:
            logger.warning("ORCID enrichment requires an identifier")
            return None
        orcid = self._normalize_orcid(identifier)
        if not orcid:
            logger.warning("Invalid ORCID identifier: %s", identifier)
            return None

        return self._get_profile(orcid)

    def get_profile(self, orcid: str) -> dict[str, Any] | None:
        """
        Get full researcher profile by ORCID iD.

        Parameters
        ----------
        orcid : str
            Normalized ORCID iD (e.g. ``"0000-0002-1825-0097"``).

        Returns
        -------
        dict or None
            Researcher profile with personal details, works, and affiliations.
        """
        normalized = self._normalize_orcid(orcid)
        if not normalized:
            return None
        return self._get_profile(normalized)

    def get_works(self, orcid: str) -> list[dict[str, Any]]:
        """
        Get list of works for a researcher.

        Parameters
        ----------
        orcid : str
            Normalized ORCID iD.

        Returns
        -------
        list[dict]
            List of work summaries.
        """
        normalized = self._normalize_orcid(orcid)
        if not normalized:
            return []

        # GET /{orcid}/works
        data = self._make_request(f"{normalized}/works")
        if not data:
            return []

        groups = data.get("group", [])
        works: list[dict[str, Any]] = []
        for group in groups:
            for summary in group.get("work-summary", []):
                work = self._parse_work_summary(summary)
                if work:
                    works.append(work)
        return works

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _get_profile(self, orcid: str) -> dict[str, Any] | None:
        """Fetch and parse a full ORCID profile."""
        # GET /{orcid} (person + activities)
        data = self._make_request(orcid)
        if not data:
            return None

        return self._parse_profile(data)

    @staticmethod
    def _normalize_orcid(identifier: str) -> str | None:
        """
        Normalize ORCID iD to bare format.

        Accepts:
        - ``0000-0002-1825-0097``
        - ``https://orcid.org/0000-0002-1825-0097``
        - ``orcid.org/0000-0002-1825-0097``
        """
        match = _ORCID_PATTERN.search(identifier.strip())
        return match.group(1) if match else None

    @staticmethod
    def _parse_profile(data: dict[str, Any]) -> dict[str, Any]:
        """Parse ORCID profile JSON into a clean dict."""
        profile: dict[str, Any] = {}

        # Name
        name = data.get("person", {}).get("name", {})
        given = (name.get("given-names") or {}).get("value", "")
        family = (name.get("family-name") or {}).get("value", "")
        profile["name"] = f"{given} {family}".strip()
        profile["given_name"] = given
        profile["family_name"] = family
        profile["credit_name"] = (name.get("credit-name") or {}).get("value")

        # Other names
        other_names = data.get("person", {}).get("other-names", {}).get("other-name", [])
        profile["other_names"] = [n.get("content") for n in other_names if n.get("content")]

        # Biography
        bio = data.get("person", {}).get("biography", {})
        profile["biography"] = bio.get("content")

        # Keywords
        keywords = data.get("person", {}).get("keywords", {}).get("keyword", [])
        profile["keywords"] = [k.get("content") for k in keywords if k.get("content")]

        # Researcher URLs
        urls = data.get("person", {}).get("researcher-urls", {}).get("researcher-url", [])
        profile["urls"] = {
            u.get("url-name", ""): u.get("url", {}).get("value", "")
            for u in urls
            if u.get("url", {}).get("value")
        }

        # Employment (summaries)
        emp = (
            data.get("activities-summary", {}).get("employments", {}).get("employment-summary", [])
        )
        profile["employments"] = [
            {
                "organization": e.get("organization", {}).get("name"),
                "department": e.get("department-name"),
                "role": e.get("role-title"),
                "start": f"{e.get('start-date', {}).get('year', {}).get('value', '')}",
                "end": f"{e.get('end-date', {}).get('year', {}).get('value', '')}",
            }
            for e in emp
        ]

        # Education
        edu = data.get("activities-summary", {}).get("educations", {}).get("education-summary", [])
        profile["educations"] = [
            {
                "organization": e.get("organization", {}).get("name"),
                "department": e.get("department-name"),
                "role": e.get("role-title"),
                "start": f"{e.get('start-date', {}).get('year', {}).get('value', '')}",
                "end": f"{e.get('end-date', {}).get('year', {}).get('value', '')}",
            }
            for e in edu
        ]

        # Works summary
        works = data.get("activities-summary", {}).get("works", {}).get("group", [])
        profile["works"] = []
        seen_dois: set[str] = set()
        for group in works:
            for summary in group.get("work-summary", []):
                work = OrcidClient._parse_work_summary(summary)
                if work:
                    doi = work.get("doi", "")
                    if doi:
                        if doi in seen_dois:
                            continue
                        seen_dois.add(doi)
                    profile["works"].append(work)

        return profile

    @staticmethod
    def _parse_work_summary(summary: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a single work summary entry."""
        title_data = summary.get("title", {}).get("title", {})
        title = title_data.get("value") if isinstance(title_data, dict) else None
        if not title:
            return None

        # Extract DOI from external IDs
        doi = None
        ext_ids = summary.get("external-ids", {}).get("external-id", [])
        for eid in ext_ids:
            if eid.get("external-id-type") == "doi":
                doi = normalize_doi(eid.get("external-id-value", ""))
                break

        pub_date = summary.get("publication-date", {})
        year = pub_date.get("year", {}).get("value") if pub_date else None

        return {
            "title": title,
            "doi": doi or None,
            "year": int(year) if year else None,
            "type": summary.get("type"),
            "journal_title": summary.get("journal-title"),
            "visibility": summary.get("visibility"),
            "path": summary.get("path"),
        }
