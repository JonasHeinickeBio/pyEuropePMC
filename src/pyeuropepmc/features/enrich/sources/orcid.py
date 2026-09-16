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


def _get(obj: Any, *keys: str) -> Any:
    """Follow *keys* through nested dicts; ``None`` once a level is missing.

    The v3.0 JSON writes an absent value as ``null`` (``"biography": null``,
    ``"end-date": null`` for a current position), so ``d.get(key, {})`` is not
    enough: the key exists and holds ``None``.
    """
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _list(obj: Any, *keys: str) -> list[Any]:
    """Like :func:`_get` for a list value, with ``[]`` for anything else."""
    value = _get(obj, *keys)
    return value if isinstance(value, list) else []


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

        works: list[dict[str, Any]] = []
        for group in _list(data, "group"):
            for summary in _list(group, "work-summary"):
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
        """Parse an ORCID API v3.0 record into a clean dict."""
        profile: dict[str, Any] = {}
        person = _get(data, "person")

        # Name
        given = _get(person, "name", "given-names", "value") or ""
        family = _get(person, "name", "family-name", "value") or ""
        profile["name"] = f"{given} {family}".strip()
        profile["given_name"] = given
        profile["family_name"] = family
        profile["credit_name"] = _get(person, "name", "credit-name", "value")

        # Other names
        profile["other_names"] = [
            n["content"] for n in _list(person, "other-names", "other-name") if _get(n, "content")
        ]

        # Biography
        profile["biography"] = _get(person, "biography", "content")

        # Keywords
        profile["keywords"] = [
            k["content"] for k in _list(person, "keywords", "keyword") if _get(k, "content")
        ]

        # Researcher URLs
        profile["urls"] = {
            (_get(u, "url-name") or ""): _get(u, "url", "value")
            for u in _list(person, "researcher-urls", "researcher-url")
            if _get(u, "url", "value")
        }

        activities = _get(data, "activities-summary")
        profile["employments"] = OrcidClient._parse_affiliations(activities, "employment")
        profile["educations"] = OrcidClient._parse_affiliations(activities, "education")

        # Works summary
        profile["works"] = []
        seen_dois: set[str] = set()
        for group in _list(activities, "works", "group"):
            for summary in _list(group, "work-summary"):
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
    def _parse_affiliations(activities: Any, kind: str) -> list[dict[str, Any]]:
        """Read the employments (*kind* ``"employment"``) or educations of a record.

        API v3.0 groups these entries::

            "employments": {"affiliation-group": [
                {"summaries": [{"employment-summary": {...}}]}
            ]}
        """
        entries: list[dict[str, Any]] = []
        for group in _list(activities, f"{kind}s", "affiliation-group"):
            for item in _list(group, "summaries"):
                summary = _get(item, f"{kind}-summary")
                if not isinstance(summary, dict):
                    continue
                entries.append(
                    {
                        "organization": _get(summary, "organization", "name"),
                        "department": summary.get("department-name"),
                        "role": summary.get("role-title"),
                        "start": _get(summary, "start-date", "year", "value") or "",
                        "end": _get(summary, "end-date", "year", "value") or "",
                    }
                )
        return entries

    @staticmethod
    def _parse_work_summary(summary: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a single work summary entry."""
        title = _get(summary, "title", "title", "value")
        if not title:
            return None

        # Extract DOI from external IDs
        doi = None
        for eid in _list(summary, "external-ids", "external-id"):
            if _get(eid, "external-id-type") == "doi":
                doi = normalize_doi(_get(eid, "external-id-value") or "")
                break

        year = _get(summary, "publication-date", "year", "value")
        try:
            year_int = int(year) if year else None
        except (TypeError, ValueError):
            year_int = None

        # v3.0 wraps the journal title in a value object: {"value": "..."}
        journal_title = summary.get("journal-title")
        if isinstance(journal_title, dict):
            journal_title = journal_title.get("value")

        return {
            "title": title,
            "doi": doi or None,
            "year": year_int,
            "type": summary.get("type"),
            "journal_title": journal_title,
            "visibility": summary.get("visibility"),
            "path": summary.get("path"),
        }
