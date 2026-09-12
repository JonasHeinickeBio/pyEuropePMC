"""
NIH iCite enrichment client.

iCite (icite.od.nih.gov) is NIH's citation analysis tool that provides
citation metrics including Relative Citation Ratio (RCR), Percentile,
and field-normalized citation impact for PubMed-indexed articles.

API docs: https://icite.od.nih.gov/api
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.features.enrich.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["ICiteClient"]


class ICiteClient(BaseEnrichmentClient):
    """
    Client for the NIH iCite API.

    Provides citation metrics for PubMed papers including RCR (Relative
    Citation Ratio), citation percentile, and field-normalized influence.

    Examples
    --------
    >>> client = ICiteClient()
    >>> metrics = client.enrich(pmid="12345678")
    >>> if metrics:
    ...     print(metrics.get("rcr"), metrics.get("percentile"))
    """

    BASE_URL = "https://icite.od.nih.gov/api"

    def __init__(
        self,
        rate_limit_delay: float = 0.5,
        timeout: int = 15,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            **kwargs,
        )

    def enrich(
        self,
        identifier: str | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Get citation metrics for a paper by PMID.

        Parameters
        ----------
        identifier : str
            PubMed ID (PMID) of the paper.
        use_cache : bool, optional
            Whether to use cache (default: True).

        Returns
        -------
        dict or None
            Citation metrics including:
            - rcr: Relative Citation Ratio
            - percentile: Citation percentile
            - citation_count: Total citations
            - expected_citations: Field-normalized expected citations
            - field_citation_ratio: Actual/expected ratio
            - nih_percentile: NIH-specific percentile
        """
        if not identifier:
            return None

        data = self._make_request(
            endpoint="pubs",
            params={"pmids": str(identifier)},
            use_cache=use_cache,
        )
        if not data:
            return None

        # iCite returns a list under "data" key
        records = data.get("data", [])
        if not records:
            return None

        return self._normalize_result(records[0])

    def enrich_many(
        self,
        pmids: list[str],
        use_cache: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """
        Get citation metrics for multiple papers by PMID (batch).

        Parameters
        ----------
        pmids : list[str]
            List of PubMed IDs.
        use_cache : bool, optional
            Whether to use cache.

        Returns
        -------
        dict[str, dict]
            Mapping of PMID to citation metrics dict.
        """
        if not pmids:
            return {}

        data = self._make_request(
            endpoint="pubs",
            params={"pmids": ",".join(str(p) for p in pmids)},
            use_cache=use_cache,
        )
        if not data:
            return {}

        records = data.get("data", [])
        result: dict[str, dict[str, Any]] = {}
        for rec in records:
            pmid = str(rec.get("pmid", ""))
            if pmid:
                result[pmid] = self._normalize_result(rec)
        return result

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    def _normalize_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        def _f(*keys: str) -> float | None:
            for k in keys:
                if raw.get(k) is not None:
                    return safe_float(raw[k])
            return None

        def _i(*keys: str) -> int | None:
            for k in keys:
                if raw.get(k) is not None:
                    try:
                        return int(raw[k])
                    except (TypeError, ValueError):
                        return None
            return None

        return {
            "pmid": str(raw.get("pmid", "")),
            "rcr": _f("relative_citation_ratio", "rcr"),
            "percentile": _f("nih_percentile", "percentile"),
            "nih_percentile": _f("nih_percentile"),
            "citation_count": _i("citation_count", "citationCount"),
            "citations_per_year": _f("citations_per_year"),
            "expected_citations": _f(
                "expected_citations_per_year", "expected_citations", "expectedCitations"
            ),
            "field_citation_ratio": _f("field_citation_ratio", "fieldCitationRatio"),
            "is_research_article": bool(raw.get("is_research_article", False)),
            "provisional": bool(raw.get("provisional", False)),
            "year": _i("year"),
        }

    # ------------------------------------------------------------------
    # Convenience lookups
    # ------------------------------------------------------------------

    def get_rcr(self, pmid: str) -> float | None:
        """Get the Relative Citation Ratio for a PMID."""
        metrics = self.enrich(identifier=pmid)
        if metrics:
            return metrics.get("rcr")
        return None

    def get_percentile(self, pmid: str) -> float | None:
        """Get the citation percentile for a PMID."""
        metrics = self.enrich(identifier=pmid)
        if metrics:
            return metrics.get("percentile")
        return None

    def get_citation_count(self, pmid: str) -> int | None:
        """Get the total citation count from iCite for a PMID."""
        metrics = self.enrich(identifier=pmid)
        if metrics:
            return metrics.get("citation_count")
        return None


def safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
