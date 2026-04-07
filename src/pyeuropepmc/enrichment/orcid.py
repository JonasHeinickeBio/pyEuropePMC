"""
ORCID API client for author disambiguation and profile enrichment.

ORCID provides comprehensive researcher profiles including publications,
affiliations, funding, peer review activities, and unique researcher identifiers.
"""

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["OrcidClient"]


class OrcidClient(BaseEnrichmentClient):
    """
    Client for ORCID API author disambiguation and profile enrichment.

    ORCID provides comprehensive researcher information including:
    - Personal and professional information
    - Publication history with DOIs
    - Affiliation history (education, employment)
    - Funding information
    - Peer review activities
    - External identifiers (Scopus, Web of Science, etc.)
    - Researcher URLs and social media

    Examples
    --------
    >>> client = OrcidClient()
    >>> profile = client.enrich(orcid_id="0000-0003-3442-7216")
    >>> if profile:
    ...     print(f"Name: {profile.get('name')}")
    ...     print(f"Affiliation: {profile.get('current_affiliation')}")
    ...     print(f"Publications: {len(profile.get('works', []))}")
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
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich author information using ORCID API.

        Parameters
        ----------
        identifier : str
            ORCID iD (required, format: XXXX-XXXX-XXXX-XXXX)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Author profile with keys:
            - orcid: ORCID iD
            - name: Full name information
            - biography: Researcher biography
            - current_affiliation: Current institutional affiliation
            - education: Education history
            - employment: Employment history
            - works: Publication list with DOIs
            - funding: Funding/grant information
            - peer_reviews: Peer review activities
            - external_ids: External identifier mappings
            - last_modified: Profile last modification date
            - source: Source identifier ("orcid")

        Raises
        ------
        ValueError
            If identifier is not provided or invalid ORCID format
        """
        if not identifier:
            raise ValueError("ORCID iD is required for ORCID enrichment")

        # Validate ORCID format
        if not self._is_valid_orcid(identifier):
            raise ValueError(
                f"Invalid ORCID format: {identifier}. Expected format: XXXX-XXXX-XXXX-XXXX"
            )

        logger.debug(f"Enriching author profile for ORCID: {identifier}")

        # Make request to ORCID API
        response = self._make_request(
            endpoint=identifier, headers={"Accept": "application/json"}, use_cache=use_cache
        )

        if response is None or not isinstance(response, dict):
            logger.warning(
                f"Invalid or no data found for ORCID: {identifier} (response type: {type(response)})"
            )
            return None

        # Parse and normalize profile data
        try:
            profile = self._parse_orcid_response(response)
            logger.info(f"Successfully enriched author profile for ORCID: {identifier}")
            return profile

        except Exception as e:
            logger.error(f"Error parsing ORCID response for {identifier}: {e}")
            # Add detailed debugging
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def _is_valid_orcid(self, orcid: str) -> bool:
        """
        Validate ORCID iD format.

        Parameters
        ----------
        orcid : str
            ORCID iD to validate

        Returns
        -------
        bool
            True if valid ORCID format
        """
        import re

        # ORCID format: XXXX-XXXX-XXXX-XXXX where X is digit
        pattern = r"^\d{4}-\d{4}-\d{4}-\d{4}$"
        return bool(re.match(pattern, orcid))

    def _parse_orcid_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse ORCID API response into normalized author profile.

        Parameters
        ----------
        response : dict
            ORCID API response

        Returns
        -------
        dict
            Normalized author profile
        """
        # Extract basic profile information
        person = response.get("person")
        if person is None or not isinstance(person, dict):
            logger.warning("Invalid ORCID response: missing or invalid 'person' field")
            return {}

        orcid_id = response.get("orcid-identifier", {}).get("path")
        name = self._extract_name(person)
        biography = None
        biography_data = person.get("biography")
        if biography_data and isinstance(biography_data, dict):
            biography = biography_data.get("content")

        # Extract external identifiers
        external_ids = self._extract_external_ids(person)

        # Extract affiliations
        activities_summary = response.get("activities-summary", {})
        if not activities_summary or not isinstance(activities_summary, dict):
            activities_summary = {}

        education = self._extract_affiliations(activities_summary, "educations")
        employment = self._extract_affiliations(activities_summary, "employments")

        # Determine current affiliation (most recent employment)
        current_affiliation = None
        if employment:
            # Sort by end date (most recent first), find one without end date or with latest end date
            sorted_employment = sorted(
                employment,
                key=lambda x: x.get("end_date", {}).get("year", {}).get("value", "9999")
                if x.get("end_date") and isinstance(x.get("end_date"), dict)
                else "9999",
                reverse=True,
            )
            current_affiliation = (
                sorted_employment[0].get("organization", {}).get("name")
                if sorted_employment[0].get("organization")
                else None
            )

        # Extract works (publications)
        works = self._extract_works(activities_summary)

        # Extract funding
        funding = self._extract_funding(activities_summary)

        # Extract peer reviews
        peer_reviews = self._extract_peer_reviews(activities_summary)

        # Extract last modified date
        last_modified = response.get("last-modified-date", {}).get("value")

        return {
            "source": "orcid",
            "orcid": orcid_id,
            "name": name,
            "biography": biography,
            "current_affiliation": current_affiliation,
            "education": education,
            "employment": employment,
            "works": works,
            "funding": funding,
            "peer_reviews": peer_reviews,
            "external_ids": external_ids,
            "last_modified": last_modified,
            "work_count": len(works) if works else 0,
            "education_count": len(education) if education else 0,
            "employment_count": len(employment) if employment else 0,
        }

    def _extract_name(self, person: dict[str, Any]) -> dict[str, Any] | None:
        """Extract name information from person object."""
        name_data = person.get("name", {})
        if not name_data:
            return None

        return {
            "given": name_data.get("given-names", {}).get("value")
            if name_data.get("given-names") and isinstance(name_data.get("given-names"), dict)
            else None,
            "family": name_data.get("family-name", {}).get("value")
            if name_data.get("family-name") and isinstance(name_data.get("family-name"), dict)
            else None,
            "credit": name_data.get("credit-name", {}).get("value")
            if name_data.get("credit-name") and isinstance(name_data.get("credit-name"), dict)
            else None,
            "full": f"{(name_data.get('given-names', {}).get('value') if name_data.get('given-names') and isinstance(name_data.get('given-names'), dict) else '')} {(name_data.get('family-name', {}).get('value') if name_data.get('family-name') and isinstance(name_data.get('family-name'), dict) else '')}".strip(),
        }

    def _extract_external_ids(self, person: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract external identifiers from person object."""
        external_ids = []
        for ext_id in person.get("external-identifiers", {}).get("external-identifier", []):
            # Safely extract URL
            url = None
            url_data = ext_id.get("external-id-url")
            if url_data and isinstance(url_data, dict):
                url = url_data.get("value")

            external_ids.append(
                {
                    "type": ext_id.get("external-id-type"),
                    "value": ext_id.get("external-id-value"),
                    "url": url,
                    "relationship": ext_id.get("external-id-relationship"),
                }
            )
        return external_ids

    def _extract_affiliations(
        self, activities: dict[str, Any], affiliation_type: str
    ) -> list[dict[str, Any]]:
        """Extract affiliations (education or employment) from activities."""
        affiliations = []
        affiliation_group = activities.get(affiliation_type, {}).get("affiliation-group", [])

        for group in affiliation_group:
            for affiliation in group.get("summaries", []):
                summary = affiliation.get(
                    f"{affiliation_type[:-1]}-summary", {}
                )  # Remove 's' and add '-summary'

                affiliations.append(
                    {
                        "organization": summary.get("organization", {}),
                        "department": summary.get("department-name"),
                        "role": summary.get("role-title"),
                        "start_date": summary.get("start-date"),
                        "end_date": summary.get("end-date"),
                        "put_code": summary.get("put-code"),
                    }
                )

        return affiliations

    def _extract_works(self, activities: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract works/publications from activities."""
        works = []
        work_groups = activities.get("works", {}).get("group", [])

        for group in work_groups:
            for work_summary in group.get("work-summary", []):
                # Extract DOI and other identifiers
                external_ids = work_summary.get("external-ids", {}).get("external-id", [])
                doi = None
                for ext_id in external_ids:
                    if ext_id.get("external-id-type") == "doi":
                        doi = ext_id.get("external-id-normalized", {}).get("value") or ext_id.get(
                            "external-id-value"
                        )
                        break

                # Safely extract title
                title_data = work_summary.get("title")
                title = None
                if title_data and isinstance(title_data, dict):
                    title_obj = title_data.get("title")
                    if title_obj and isinstance(title_obj, dict):
                        title = title_obj.get("value")

                # Safely extract journal title
                journal_title = None
                journal_data = work_summary.get("journal-title")
                if journal_data and isinstance(journal_data, dict):
                    journal_title = journal_data.get("value")

                works.append(
                    {
                        "title": title,
                        "doi": doi,
                        "type": work_summary.get("type"),
                        "publication_date": work_summary.get("publication-date"),
                        "journal_title": journal_title,
                        "put_code": work_summary.get("put-code"),
                    }
                )

        return works

    def _extract_funding(self, activities: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract funding information from activities."""
        funding = []
        funding_groups = activities.get("fundings", {}).get("group", [])

        for group in funding_groups:
            for funding_summary in group.get("funding-summary", []):
                # Safely extract title
                title_data = funding_summary.get("title")
                title = None
                if title_data and isinstance(title_data, dict):
                    title_obj = title_data.get("title")
                    if title_obj and isinstance(title_obj, dict):
                        title = title_obj.get("value")

                funding.append(
                    {
                        "title": title,
                        "organization": funding_summary.get("organization", {}).get("name")
                        if funding_summary.get("organization")
                        else None,
                        "type": funding_summary.get("type"),
                        "start_date": funding_summary.get("start-date"),
                        "end_date": funding_summary.get("end-date"),
                        "put_code": funding_summary.get("put-code"),
                    }
                )

        return funding

    def _extract_peer_reviews(self, activities: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract peer review activities from activities."""
        peer_reviews = []
        peer_review_groups = activities.get("peer-reviews", {}).get("group", [])

        for group in peer_review_groups:
            for peer_review_summary in group.get("peer-review-summary", []):
                peer_reviews.append(
                    {
                        "reviewer_role": peer_review_summary.get("reviewer-role"),
                        "completion_date": peer_review_summary.get("completion-date"),
                        "review_type": peer_review_summary.get("review-type"),
                        "convening_organization": peer_review_summary.get(
                            "convening-organization", {}
                        ).get("name"),
                        "put_code": peer_review_summary.get("put-code"),
                    }
                )

        return peer_reviews
