"""
ClinicalTrials.gov API client for searching clinical studies.

ClinicalTrials.gov is a database of privately and publicly funded
clinical studies conducted around the world. This client uses the
v2 API which returns structured JSON results.

The API is free and requires no API key.

References
----------
- ClinicalTrials.gov API v2: https://clinicaltrials.gov/api/v2/
- Study fields: https://clinicaltrials.gov/api/v2/studies
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.literature.normalization import normalize_doi, normalize_paper_title
from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import Author, LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["ClinicalTrialsClient"]

# Maximum results per page (API limit)
_MAX_PAGE_SIZE = 100


class ClinicalTrialsClient(BaseLiteratureClient):
    """
    Client for ClinicalTrials.gov API search.

    ClinicalTrials.gov provides:
    - Interventional and observational clinical studies
    - Eligibility criteria
    - Outcome measures
    - Locations and sponsors
    - Study results and publications

    The API is free and does not require an API key.

    Examples
    --------
    >>> client = ClinicalTrialsClient()
    >>> results = client.search("COVID-19 vaccine", limit=10)
    >>> for study in results:
    ...     print(f"{study.title} ({study.source_id})")
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2"

    def __init__(
        self,
        rate_limit_delay: float = 0.5,
        timeout: int = 30,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize ClinicalTrials.gov client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 0.5).
        timeout : int, optional
            Request timeout in seconds (default: 30).
        cache_config : CacheConfig, optional
            Cache configuration for API responses.
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search clinical studies.

        Parameters
        ----------
        query : str
            Search query (ClinicalTrials.gov query syntax).
            E.g., ``"COVID-19 AND vaccine"``.
        limit : int, optional
            Maximum number of results (default: 25).
        sort : str, optional
            Sort order. Options: ``"relevance"`` (default), ``"last_update"``,
            ``"first_post"``, ``"enrollment"``.
        **kwargs
            Additional parameters. Accepted:
            - ``status`` (str): Recruitment status filter
            - ``phase`` (str): Study phase filter

        Returns
        -------
        list[LiteratureResult]
            List of clinical study results as Pydantic models.
        """
        # Map sort parameter
        sort_map = {
            "relevance": "@relevance",
            "last_update": "@last_update",
            "first_post": "@first_post",
            "enrollment": "@enrollment",
        }
        sort_param = sort_map.get(sort, "@relevance") if sort else "@relevance"

        params: dict[str, Any] = {
            "query.term": query,
            "pageSize": min(limit, _MAX_PAGE_SIZE),
            "sort": sort_param,
            "format": "json",
        }

        # Optional filters
        status = kwargs.get("status")
        if status:
            params["filter.overallStatus"] = status

        phase = kwargs.get("phase")
        if phase:
            params["filter.phase"] = phase

        raw = self._make_request("studies", params=params, use_cache=True)
        if raw is None:
            return []

        return self._parse_response(raw)

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        """
        Get study details by NCT ID.

        Parameters
        ----------
        identifier : str
            NCT ID (e.g. ``"NCT04283461"``).
        **kwargs
            Additional parameters (unused).

        Returns
        -------
        LiteratureResult or None
            Study details as Pydantic model, or None if not found.
        """
        # Normalize NCT ID
        nct_id = identifier.strip().upper()
        if not nct_id.startswith("NCT"):
            nct_id = f"NCT{nct_id}"

        try:
            raw = self._make_request(f"studies/{nct_id}", use_cache=True)
        except APIClientError as e:
            # ClinicalTrials.gov returns 400 for non-existent / invalid NCT IDs
            if e.status_code in (400, 404):
                logger.info("Study %s not found (HTTP %s)", nct_id, e.status_code)
                return None
            raise
        if raw is None:
            return None

        return self._parse_study(raw.get("study", {}) if "study" in raw else raw)

    def search_by_condition(
        self,
        condition: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search studies by medical condition.

        Parameters
        ----------
        condition : str
            Medical condition to search (e.g. ``"Chronic Fatigue Syndrome"``).
        limit : int, optional
            Maximum number of results (default: 25).
        **kwargs
            Additional search parameters.

        Returns
        -------
        list[LiteratureResult]
            List of matching studies.
        """
        return self.search(query=f"AREA[ConditionSearch] {condition}", limit=limit, **kwargs)

    def search_by_intervention(
        self,
        intervention: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        """
        Search studies by intervention/treatment.

        Parameters
        ----------
        intervention : str
            Intervention name (e.g. ``"Rituximab"``).
        limit : int, optional
            Maximum number of results (default: 25).
        **kwargs
            Additional search parameters.

        Returns
        -------
        list[LiteratureResult]
            List of matching studies.
        """
        return self.search(query=f"AREA[InterventionSearch] {intervention}", limit=limit, **kwargs)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_result(self, raw_result: dict[str, Any]) -> LiteratureResult:
        """
        Normalize API response to standard format.

        Parameters
        ----------
        raw_result : dict
            Raw API response data.

        Returns
        -------
        LiteratureResult
            Normalized result as Pydantic model.
        """
        title = normalize_paper_title(raw_result.get("title", ""))
        nct_id = raw_result.get("nct_id", "")

        # Authors (from overall contacts)
        authors_raw = raw_result.get("authors", [])
        authors = None
        if authors_raw:
            author_list = [
                Author(name=a) if isinstance(a, str) else Author(name=a.get("name", ""))
                for a in authors_raw
            ]
            authors = author_list or None

        return LiteratureResult(
            doi=raw_result.get("doi"),
            pmid=raw_result.get("pmid"),
            pmcid=None,
            title=title or None,
            authors=authors,
            publication_year=raw_result.get("year"),
            journal=None,  # ClinicalTrials.gov doesn't have journal field
            abstract=raw_result.get("abstract"),
            citation_count=raw_result.get("citation_count"),
            source="clinicaltrials",
            source_id=nct_id,
            # Extra metadata in source-specific field
            extra_metadata={
                "nct_id": nct_id,
                "overall_status": raw_result.get("overall_status"),
                "phase": raw_result.get("phase"),
                "study_type": raw_result.get("study_type"),
                "conditions": raw_result.get("conditions"),
                "sponsor": raw_result.get("sponsor"),
                "enrollment": raw_result.get("enrollment"),
                "start_date": raw_result.get("start_date"),
                "completion_date": raw_result.get("completion_date"),
            }
            if nct_id
            else None,
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, data: dict[str, Any]) -> list[LiteratureResult]:
        """Parse studies list response into LiteratureResult list."""
        studies = data.get("studies", [])
        results: list[LiteratureResult] = []
        for entry in studies:
            study_data = (
                entry.get("study", {}) if isinstance(entry, dict) and "study" in entry else entry
            )
            parsed = self._parse_study(study_data)
            if parsed:
                results.append(parsed)
        return results

    def _parse_study(self, study: dict[str, Any]) -> LiteratureResult | None:
        """Parse a single study JSON object."""
        protocol = study.get("protocolSection", {})
        if not protocol:
            return None

        id_module = protocol.get("identificationModule", {})
        status_module = protocol.get("statusModule", {})
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        description_module = protocol.get("descriptionModule", {})
        conditions_module = protocol.get("conditionsModule", {})
        design_module = protocol.get("designModule", {})
        arms_module = protocol.get("armsInterventionsModule", {})

        # Core identifiers
        nct_id = id_module.get("nctId", "")
        brief_title = id_module.get("briefTitle", "")
        official_title = id_module.get("officialTitle", "")
        title = official_title or brief_title
        doi = id_module.get("doi", "")

        # Status
        overall_status = status_module.get("overallStatus", "")
        start_date = (
            status_module.get("startDateStruct", {}).get("date")
            if isinstance(status_module.get("startDateStruct"), dict)
            else status_module.get("startDate")
        )
        completion_date = (
            status_module.get("completionDateStruct", {}).get("date")
            if isinstance(status_module.get("completionDateStruct"), dict)
            else status_module.get("completionDate")
        )

        # Year from start date
        year = None
        if start_date:
            # Extract year from various date formats
            start_str = str(start_date)
            if len(start_str) >= 4:
                try:
                    year = int(start_str[:4])
                except ValueError:
                    pass

        # Description (abstract)
        brief_summary = description_module.get("briefSummary", "")
        detailed_desc = description_module.get("detailedDescription", "")
        abstract = detailed_desc or brief_summary

        # Sponsor
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        sponsor_name = lead_sponsor.get("name", "") if isinstance(lead_sponsor, dict) else ""

        # Conditions
        conditions = conditions_module.get("conditions", [])

        # Study type and phase
        study_type = design_module.get("studyType", "")
        phases = design_module.get("phases", [])
        phase_str = ", ".join(phases) if phases else ""

        # Enrollment
        enrollment = design_module.get("enrollmentInfo", {})
        enrollment_count = enrollment.get("count") if isinstance(enrollment, dict) else None

        # Interventions
        interventions = arms_module.get("interventions", [])

        # References (publications linked to this study)
        references_module = protocol.get("referencesModule", {})
        references = references_module.get("references", [])

        # Extract associated PMIDs and DOIs from references
        pmids = []
        dois = []
        for ref in references:
            ref_type = ref.get("type", "")
            if ref_type == "RESULT":
                pmid = ref.get("pmid")
                if pmid:
                    pmids.append(pmid)
                doi = ref.get("doi") or ref.get("referenceDoi")
                if doi:
                    dois.append(doi)

        # Author-like contacts
        contacts = []
        contact_module = protocol.get("contactsLocationsModule", {})
        overall_contacts = contact_module.get("overallOfficials", [])
        for c in overall_contacts:
            if isinstance(c, dict):
                name = c.get("name", "")
                role = c.get("role", "")
                affil = c.get("affiliation", "")
                if name:
                    contacts.append({"name": name, "role": role, "affiliation": affil})

        raw: dict[str, Any] = {
            "title": title,
            "nct_id": nct_id,
            "doi": normalize_doi(doi) if doi else None,
            "pmid": pmids[0] if pmids else None,
            "year": year,
            "abstract": abstract,
            "overall_status": overall_status,
            "phase": phase_str,
            "study_type": study_type,
            "conditions": conditions,
            "sponsor": sponsor_name,
            "enrollment": enrollment_count,
            "start_date": str(start_date) if start_date else None,
            "completion_date": str(completion_date) if completion_date else None,
            "authors": contacts if contacts else None,
            "interventions": interventions,
            "references": references,
        }

        if not title:
            return None

        return self._normalize_result(raw)
