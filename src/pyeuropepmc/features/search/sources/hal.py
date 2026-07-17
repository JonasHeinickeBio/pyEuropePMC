"""
HAL Open Archive literature client.

HAL (hal.science) is the French national open-access archive for scholarly
publications across all disciplines. This client provides search via the
HAL REST API (free, no API key required).

API docs: https://api.archives-ouvertes.fr/docs/
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["HALClient"]


class HALClient(BaseLiteratureClient):
    """
    Client for the HAL Open Archive REST API.

    Searches publications across all disciplines in the HAL open archive.

    Examples
    --------
    >>> client = HALClient()
    >>> results = client.search("reinforcement learning", limit=10)
    >>> for r in results:
    ...     print(r.title, r.publication_year)
    """

    BASE_URL = "https://api.archives-ouvertes.fr/search"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        **kwargs: Any,
    ) -> list[LiteratureResult]:
        params: dict[str, Any] = {
            "q": query,
            "rows": min(limit, 100),
            "start": 0,
            "wt": "json",
        }
        if sort:
            sort_map = {"relevance": "score desc", "date": "submittedDate_tdate desc"}
            s = sort_map.get(sort)
            if s:
                params["sort"] = s

        # Domain filter
        domain = kwargs.get("domain", "")
        if domain:
            params["fq"] = f"domain_s:{domain}"

        data = self._make_request(endpoint="", params=params)
        if not data:
            return []

        response = data.get("response", {})
        docs = response.get("docs", [])
        results: list[LiteratureResult] = []
        for doc in docs[:limit]:
            nr = self._normalize_result(doc)
            if nr is not None:
                results.append(nr)
        return results

    # ------------------------------------------------------------------
    # Get single paper
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        params: dict[str, Any] = {"q": f"halId_s:{identifier}", "wt": "json", "rows": 1}
        data = self._make_request(endpoint="", params=params)
        if not data:
            return None
        response = data.get("response", {})
        docs = response.get("docs", [])
        if docs:
            return self._normalize_result(docs[0])
        return None

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def _normalize_result(self, raw: dict[str, Any]) -> LiteratureResult:
        doi: str | None = None
        doi_id = raw.get("doiId_s", "") or raw.get("doiId_s", "")
        if doi_id:
            doi = doi_id
        doi_str = raw.get("doiId_s", "")
        if isinstance(doi_str, str) and doi_str.startswith("10."):
            doi = doi_str

        title: str | None = ""
        # HAL stores titles in multiple languages
        title_en = raw.get("title_s", [])
        title_fr = raw.get("title_s", [])
        if isinstance(title_en, list) and title_en:
            title = title_en[0]
        elif isinstance(title_fr, list) and title_fr:
            title = title_fr[0]
        elif isinstance(raw.get("title_s"), str):
            title = raw["title_s"]

        # Authors
        authors_raw = raw.get("authFullName_s", [])
        if isinstance(authors_raw, str):
            authors_raw = [authors_raw]
        authors = [{"name": a} for a in authors_raw[:20]] if authors_raw else None

        # Year
        year: int | None = None
        y = raw.get("producedDateY_i", "") or raw.get("year", "")
        if y:
            try:
                year = int(y)
            except (ValueError, TypeError):
                pass

        # Journal
        journal: str | None = raw.get("journalTitle_s", "") or raw.get("journal_s", "")

        # Abstract
        abstract: str | None = ""
        abstract_en = raw.get("abstract_s", [])
        abstract_fr = raw.get("abstract_s", [])
        if isinstance(abstract_en, list) and abstract_en:
            abstract = abstract_en[0]
        elif isinstance(abstract_fr, list) and abstract_fr:
            abstract = abstract_fr[0]

        # Source
        source = "hal"
        hal_id: str = raw.get("halId_s", "") or raw.get("halId_s", "")

        # Extra metadata
        extra = {
            "hal_id": hal_id,
            "hal_url": f"https://hal.science/{hal_id}" if hal_id else None,
            "domain": raw.get("domain_s", ""),
            "language": raw.get("language_s", ""),
            "type": raw.get("docType_s", ""),
            "structures": raw.get("structName_s", [])[:5]
            if isinstance(raw.get("structName_s"), list)
            else [],
        }

        # PMID from HAL
        pmid: str | None = None
        for ext_id in (
            raw.get("externalId_s", []) if isinstance(raw.get("externalId_s"), list) else []
        ):
            if "pubmed" in str(ext_id).lower():
                parts = str(ext_id).split(":")
                if len(parts) > 1:
                    pmid = parts[-1].strip()

        return LiteratureResult(
            doi=doi,
            title=title,
            authors=authors,
            publication_year=year,
            journal=journal,
            abstract=abstract,
            citation_count=0,
            source=source,
            source_id=hal_id or doi or "",
            extra_metadata=extra,
            pmid=pmid,
            pmcid=None,
        )
