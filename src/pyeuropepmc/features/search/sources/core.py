"""
CORE Aggregator literature client.

CORE (core.ac.uk) is the world's largest aggregator of open-access research
papers, indexing over 250 million papers from thousands of repositories.
This client provides search via the CORE API v3 (requires free API key).

API docs: https://api.core.ac.uk/docs/v3
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["COREClient"]


class COREClient(BaseLiteratureClient):
    """
    Client for the CORE API v3.

    Searches the CORE aggregator of open-access research papers. Requires
    a free API key set via the ``api_key`` parameter or ``CORE_API_KEY``
    environment variable.

    Examples
    --------
    >>> client = COREClient(api_key="your-key-here")
    >>> results = client.search("quantum computing", limit=10)
    >>> for r in results:
    ...     print(r.title, r.doi)
    """

    BASE_URL = "https://api.core.ac.uk/v3"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_delay: float = 1.0,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        import os

        self._api_key = api_key or os.environ.get("CORE_API_KEY", "")
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            **kwargs,
        )
        if self._api_key:
            self.session.headers.update({"Authorization": f"Bearer {self._api_key}"})

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
            "limit": min(limit, 100),
            "offset": 0,
        }
        if sort:
            sort_map = {"relevance": "relevance", "date": "publicationDate"}
            s = sort_map.get(sort)
            if s:
                params["sort"] = s

        # Limit to records with full text available
        if kwargs.get("fulltext_only", False):
            params["fullText"] = "true"

        data = self._make_request(endpoint="search", params=params)
        if not data:
            return []

        # CORE v3 returns results in "results" key
        results_raw = data.get("results", [])
        results: list[LiteratureResult] = []
        for rec in results_raw[:limit]:
            nr = self._normalize_result(rec)
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
        # Identifier can be a CORE ID or DOI
        if identifier.startswith("10."):
            endpoint = f"search/outputs?q={identifier}"
        else:
            endpoint = f"outputs/{identifier}"

        data = self._make_request(endpoint=endpoint)
        if not data:
            return None
        if "results" in data:
            results = data["results"]
            if results:
                return self._normalize_result(results[0])
        return self._normalize_result(data)

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def _normalize_result(self, raw: dict[str, Any]) -> LiteratureResult:
        doi: str | None = raw.get("doi", "") or raw.get("doi", "")
        title: str | None = raw.get("title", "")
        year_raw = raw.get("yearPublished", "") or raw.get("publicationYear", "")
        year: int | None = None
        if year_raw:
            try:
                year = int(str(year_raw)[:4])
            except (ValueError, IndexError):
                pass

        # Authors
        authors_raw = raw.get("authors", [])
        authors = []
        for a in authors_raw:
            if isinstance(a, dict):
                name = a.get("name", "")
                if name:
                    authors.append({"name": name})
            elif isinstance(a, str):
                authors.append({"name": a})
        if not authors:
            authors = None

        # Journal
        journal: str | None = raw.get("journalName", "") or raw.get("publisher", "")

        # Abstract
        abstract: str | None = raw.get("abstract", "") or raw.get("description", "")

        # Citation count
        citations: int = raw.get("citationCount", 0) or raw.get("citationCount", 0) or 0
        try:
            citations = int(citations)
        except (ValueError, TypeError):
            citations = 0

        # Source
        source = "core"
        core_id = str(raw.get("id", raw.get("coreId", "")))

        # Full text URL and download
        fulltext_url: str | None = raw.get("fullTextUrl", "") or raw.get("downloadUrl", "")

        # Extra metadata
        extra = {
            "core_id": core_id,
            "fulltext_url": fulltext_url,
            "language": raw.get("language", {}).get("name")
            if isinstance(raw.get("language"), dict)
            else raw.get("language"),
            "publisher": raw.get("publisher", ""),
            "source_repository": raw.get("repository", {}).get("name")
            if isinstance(raw.get("repository"), dict)
            else None,
            "oa_status": raw.get("oaStatus", ""),
        }

        return LiteratureResult(
            doi=doi,
            title=title,
            authors=authors,
            publication_year=year,
            journal=journal,
            abstract=abstract,
            citation_count=citations,
            source=source,
            source_id=core_id or doi or "",
            extra_metadata=extra,
            pmid=raw.get("pmid") or None,
            pmcid=raw.get("pmcid") or None,
        )
