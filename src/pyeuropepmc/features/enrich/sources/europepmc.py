"""
Europe PMC enrichment client.

Europe PMC is the project's home aggregator (MED + PMC + preprints + Agricola
+ patents). As an *enrichment* source it supplies the base record — title,
abstract, authors, journal, publication year, MeSH terms, grant / funding
info, full-text availability, open-access status and Europe PMC's own
``citedByCount`` — that the other enrichment APIs then top up.

It is keyed by any of DOI / PMID / PMCID and resolves the record with a single
targeted Europe PMC query.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["EuropePMCEnrichmentClient"]


class EuropePMCEnrichmentClient:
    """
    Enrichment adapter around the native Europe PMC :class:`SearchClient`.

    Duck-types the enrichment-client interface used by
    :class:`~pyeuropepmc.features.enrich.enricher.PaperEnricher`
    (``enrich(identifier=...)`` + ``close()``).

    Examples
    --------
    >>> client = EuropePMCEnrichmentClient()
    >>> data = client.enrich(identifier="10.1038/s41586-020-2649-2")
    >>> data["citation_count"], data["is_open_access"]
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: Any | None = None,
        **_ignored: Any,
    ) -> None:
        from pyeuropepmc.features.literature.search import SearchClient

        self.timeout = timeout
        try:
            self._client = SearchClient(
                rate_limit_delay=rate_limit_delay, cache_config=cache_config
            )
        except TypeError:  # SearchClient signature drift — fall back to the minimal ctor
            self._client = SearchClient(rate_limit_delay=rate_limit_delay)

    # ------------------------------------------------------------------

    def enrich(
        self,
        identifier: str | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Look up a paper in Europe PMC by DOI / PMID / PMCID.

        Returns a normalized dict (or ``None`` if nothing matched).
        """
        if not identifier:
            return None

        query = self._build_query(identifier.strip())
        try:
            records = self._client.search_and_parse(query, format="json", pageSize=1)
        except Exception:
            logger.warning("Europe PMC enrichment lookup failed for %r", identifier, exc_info=True)
            return None

        if not records:
            return None
        return self._normalize(records[0])

    def get_by_pmid(self, pmid: str) -> dict[str, Any] | None:
        """Convenience alias — look up by PMID."""
        return self.enrich(identifier=pmid)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._client.close()

    # ------------------------------------------------------------------

    @staticmethod
    def _build_query(ident: str) -> str:
        low = ident.lower()
        if low.startswith("10.") or "doi.org/" in low:
            doi = ident.rsplit("/", 1)[-1] if "doi.org/" in low else ident
            return f'DOI:"{doi}"'
        if low.startswith("pmc"):
            return f"PMCID:{ident.upper()}"
        if ident.isdigit():
            return f"EXT_ID:{ident} AND SRC:MED"
        return ident

    @staticmethod
    def _normalize(rec: dict[str, Any]) -> dict[str, Any]:
        def _int(value: Any) -> int | None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        journal = rec.get("journalTitle")
        if not journal:
            journal = (rec.get("journalInfo", {}) or {}).get("journal", {}).get("title")

        mesh_terms: list[str] = []
        for mh in (rec.get("meshHeadingList", {}) or {}).get("meshHeading", []) or []:
            desc = mh.get("descriptorName")
            if desc:
                mesh_terms.append(desc)

        grants: list[dict[str, Any]] = []
        for g in (rec.get("grantsList", {}) or {}).get("grant", []) or []:
            grants.append(
                {
                    "agency": g.get("agency"),
                    "grant_id": g.get("grantId"),
                    "order": g.get("orderIn"),
                }
            )

        full_text_urls: list[str] = []
        for u in (rec.get("fullTextUrlList", {}) or {}).get("fullTextUrl", []) or []:
            url = u.get("url")
            if url:
                full_text_urls.append(url)

        pub_year = _int(str(rec.get("pubYear"))[:4]) if rec.get("pubYear") else None

        return {
            "source": "europepmc",
            "id": rec.get("id"),
            "source_db": rec.get("source"),
            "doi": (rec.get("doi") or "").lower() or None,
            "pmid": rec.get("pmid"),
            "pmcid": rec.get("pmcid"),
            "title": rec.get("title"),
            "abstract": rec.get("abstractText"),
            "author_string": rec.get("authorString"),
            "journal": journal,
            "publication_year": pub_year,
            "publication_type": (rec.get("pubTypeList", {}) or {}).get("pubType"),
            "citation_count": _int(rec.get("citedByCount")),
            "is_open_access": (rec.get("isOpenAccess") == "Y")
            if rec.get("isOpenAccess") is not None
            else None,
            "in_epmc": rec.get("inEPMC") == "Y" if rec.get("inEPMC") is not None else None,
            "in_pmc": rec.get("inPMC") == "Y" if rec.get("inPMC") is not None else None,
            "has_pdf": rec.get("hasPDF") == "Y" if rec.get("hasPDF") is not None else None,
            "has_fulltext_xml": rec.get("hasTextMinedTerms") == "Y"
            if rec.get("hasTextMinedTerms") is not None
            else None,
            "mesh_terms": mesh_terms or None,
            "grants": grants or None,
            "full_text_urls": full_text_urls or None,
        }
