"""
DOAJ (Directory of Open Access Journals) literature client.

DOAJ is a community-curated online directory that indexes and provides
access to high-quality, open-access, peer-reviewed journals. This client
provides search via the DOAJ API v3 (free, no API key required for search).

API docs: https://doaj.org/api/v3/docs/
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["DOAJClient"]


class DOAJClient(BaseLiteratureClient):
    """
    Client for the DOAJ API v3.

    Searches articles across all journals indexed in the Directory of
    Open Access Journals.

    Examples
    --------
    >>> client = DOAJClient()
    >>> results = client.search("climate change adaptation", limit=10)
    >>> for r in results:
    ...     print(r.title, r.journal)
    """

    BASE_URL = "https://doaj.org/api/v3"

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
            "page": 1,
            "pageSize": min(limit, 100),
        }
        if sort:
            sort_map = {
                "relevance": "",
                "date": "created_date desc",
                "citation": "",
            }
            s = sort_map.get(sort, "")
            if s:
                params["sort"] = s

        data = self._make_request(endpoint=f"search/articles/{query}", params=params)
        if not data:
            return []

        results_raw = data.get("results", [])
        results: list[LiteratureResult] = []
        for rec in results_raw[:limit]:
            nr = self._normalize_result(rec)
            if nr is not None:
                results.append(nr)
        return results

    # ------------------------------------------------------------------
    # Get single article
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        # Identifier is the DOAJ article ID (not a DOI)
        data = self._make_request(endpoint=f"articles/{identifier}")
        if not data:
            return None
        # The single-article endpoint wraps result under "result"
        result = data.get("result", data)
        return self._normalize_result(result)

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def _normalize_result(self, raw: dict[str, Any]) -> LiteratureResult:
        # DOAJ wraps everything under "bibjson"
        bibjson = raw.get("bibjson", raw)
        admin = raw.get("admin", {})

        # DOI
        doi: str | None = bibjson.get("doi", "")
        if not doi and "identifier" in bibjson:
            for id_item in bibjson["identifier"]:
                if id_item.get("type") == "doi":
                    doi = id_item.get("id", "")
                    break

        # PMID
        pmid: str | None = None
        pids = bibjson.get("identifier", [])
        for pid in pids:
            if pid.get("type") == "pissn":
                continue
            if pid.get("type") == "pmid":
                pmid = pid.get("id", "")

        # Title
        title: str | None = bibjson.get("title", "")

        # Authors
        author_list = bibjson.get("author", [])
        authors = []
        for a in author_list:
            name = a.get("name", "")
            if not name:
                name = f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
            authors.append({"name": name})
        if not authors:
            authors = None

        # Publication year
        year: int | None = None
        year_str = bibjson.get("year", "")
        if year_str:
            try:
                year = int(str(year_str)[:4])
            except (ValueError, IndexError):
                pass

        # Journal
        journal: str | None = (
            bibjson.get("journal", {}).get("title")
            if isinstance(bibjson.get("journal"), dict)
            else bibjson.get("journal", "")
        )

        # Abstract
        abstract: str | None = bibjson.get("abstract", "")

        # Keywords
        keywords: list[str] = bibjson.get("keywords", [])

        # Source IDs
        source = "doaj"
        source_id = str(raw.get("id", ""))
        cs = admin.get("carnegie_code", "") if admin else ""

        # Extra metadata
        extra = {
            "doaj_id": source_id,
            "keywords": keywords[:15],
            "publisher": bibjson.get("journal", {}).get("publisher")
            if isinstance(bibjson.get("journal"), dict)
            else None,
            "language": bibjson.get("language", [])[0] if bibjson.get("language") else None,
            "oa_status": "OA",
            "carnegie_code": cs,
            "identifier_type": bibjson.get("type", ""),
        }

        return LiteratureResult(
            doi=doi,
            title=title,
            authors=authors,
            publication_year=year,
            journal=journal,
            abstract=abstract,
            citation_count=0,
            source=source,
            source_id=source_id,
            extra_metadata=extra,
            pmid=pmid,
            pmcid=None,
        )
