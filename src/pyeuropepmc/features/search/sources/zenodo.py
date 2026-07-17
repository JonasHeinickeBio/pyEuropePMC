"""
Zenodo API literature client.

Zenodo (zenodo.org) is a general-purpose open-access repository for research
datasets, software, and publications. This client provides search capabilities
via the Zenodo REST API (free, no API key required).

API docs: https://developers.zenodo.org/
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.features.search.base import BaseLiteratureClient
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["ZenodoClient"]


class ZenodoClient(BaseLiteratureClient):
    """
    Client for the Zenodo REST API.

    Searches datasets, software, and publications across all Zenodo communities.

    Examples
    --------
    >>> client = ZenodoClient()
    >>> results = client.search("machine learning MRI", limit=10)
    >>> for r in results:
    ...     print(r.title, r.doi)
    """

    BASE_URL = "https://zenodo.org/api"

    def __init__(
        self,
        rate_limit_delay: float = 3.0,
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
        params: dict[str, Any] = {"q": query, "size": min(limit, 100), "page": 1}
        sort_map = {"date": "-publication_date", "relevance": "", "citation": ""}
        if sort and sort in sort_map and sort_map[sort]:
            params["sort"] = sort_map[sort]

        # Type filter from kwargs
        type_filter = kwargs.get("type", "")
        if type_filter in (
            "dataset",
            "publication",
            "software",
            "image",
            "video",
            "poster",
            "presentation",
        ):
            params["type"] = type_filter
        community = kwargs.get("community", "")
        if community:
            params["communities"] = community

        data = self._make_request(endpoint="records", params=params)
        if not data or "hits" not in data:
            return []

        hits = data["hits"].get("hits", [])
        results: list[LiteratureResult] = []
        for rec in hits[:limit]:
            nr = self._normalize_result(rec)
            if nr is not None:
                results.append(nr)
        return results

    # ------------------------------------------------------------------
    # Get single record
    # ------------------------------------------------------------------

    def get_paper(
        self,
        identifier: str,
        **kwargs: Any,
    ) -> LiteratureResult | None:
        # Identifier can be Zenodo record ID or DOI
        if identifier.startswith("10."):
            data = self._make_request(endpoint=f"records/doi/{identifier}")
        else:
            # Assume it's a Zenodo record ID (numeric)
            data = self._make_request(endpoint=f"records/{identifier}")
        if not data:
            return None
        return self._normalize_result(data)

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def _normalize_result(self, raw: dict[str, Any]) -> LiteratureResult:
        metadata = raw.get("metadata", raw)

        # DOI
        doi: str | None = None
        if "doi" in metadata:
            doi = metadata["doi"]
        elif "doi" in raw:
            doi = raw["doi"]

        # Title
        title: str | None = metadata.get("title", "")

        # Authors (creators)
        creators = metadata.get("creators", [])
        authors = []
        for c in creators:
            name = c.get("name", "")
            if not name:
                name = f"{c.get('family', '')}, {c.get('given', '')}".strip(", ")
            authors.append({"name": name})
        if not authors:
            authors = None

        # Publication year
        pub_date = metadata.get("publication_date", "")
        year: int | None = None
        if pub_date:
            try:
                year = int(pub_date[:4])
            except (ValueError, IndexError):
                pass

        # Journal / type
        journal_raw = metadata.get("journal_title") or metadata.get("journal", "")
        if isinstance(journal_raw, dict):
            journal_raw = journal_raw.get("title", "") or journal_raw.get("name", "") or ""
        journal: str | None = str(journal_raw) if journal_raw else None
        resource_type = metadata.get("resource_type", {}).get("type", "")
        if not journal:
            journal = f"Zenodo ({resource_type})" if resource_type else "Zenodo"

        # Description (abstract)
        abstract: str | None = metadata.get("description", "")

        # Keywords/subjects
        subjects = metadata.get("subjects", [])

        # Source and source ID
        source = "zenodo"
        rec_id = str(raw.get("id", ""))
        if doi:
            source_id = doi
        else:
            source_id = rec_id

        # Extra metadata
        extra = {
            "zenodo_id": rec_id,
            "resource_type": resource_type,
            "subjects": [s.get("term", "") for s in subjects[:10]] if subjects else [],
            "communities": [c.get("id", "") for c in metadata.get("communities", [])],
            "license": metadata.get("license", {}).get("id")
            if isinstance(metadata.get("license"), dict)
            else metadata.get("license"),
            "version": metadata.get("version", ""),
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
            pmid=None,
            pmcid=None,
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def search_datasets(
        self,
        query: str,
        limit: int = 25,
    ) -> list[LiteratureResult]:
        """Search only Zenodo datasets."""
        return self.search(query, limit=limit, type="dataset")

    def search_publications(
        self,
        query: str,
        limit: int = 25,
    ) -> list[LiteratureResult]:
        """Search only Zenodo publications."""
        return self.search(query, limit=limit, type="publication")

    def search_software(
        self,
        query: str,
        limit: int = 25,
    ) -> list[LiteratureResult]:
        """Search only Zenodo software records."""
        return self.search(query, limit=limit, type="software")
