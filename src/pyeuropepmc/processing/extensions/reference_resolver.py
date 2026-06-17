"""
Reference Resolution via Europe PMC API.

Resolves cited references to their PubMed IDs (PMIDs) by looking up DOIs/PMIDs
via the Europe PMC API, enabling citation network construction.

Based on patterns from pubmed_parser's reference resolution.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import time
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Europe PMC API endpoint for article lookup
EUROPE_PMC_API = "https://www.ebi.ac.uk/europepmc/api/search"


@dataclass
class ResolvedReference:
    """
    A reference enriched with resolved metadata from the API.

    Parameters
    ----------
    source_ref : dict
        The original reference data from the parser.
    resolved_pmid : str, optional
        Resolved PubMed ID.
    resolved_doi : str, optional
        Resolved DOI.
    title : str, optional
        Resolved article title.
    authors : str, optional
        Resolved author string.
    year : str, optional
        Publication year.
    journal : str, optional
        Journal name.
    citations : int, optional
        Citation count from Europe PMC.
    is_open_access : bool, optional
        Whether the article is Open Access.
    """

    source_ref: dict[str, Any] = field(default_factory=dict)
    resolved_pmid: str = ""
    resolved_doi: str = ""
    title: str = ""
    authors: str = ""
    year: str = ""
    journal: str = ""
    citations: int = 0
    is_open_access: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "source_ref": self.source_ref,
            "resolved_pmid": self.resolved_pmid,
            "resolved_doi": self.resolved_doi,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "citations": self.citations,
            "is_open_access": self.is_open_access,
        }


class ReferenceResolver:
    """
    Resolves references by looking up DOIs/PMIDs via the Europe PMC API.

    Parameters
    ----------
    rate_limit : float, optional
        Requests per second (default: 3, respecting NCBI guidelines).
    api_key : str, optional
        Europe PMC API key for higher rate limits.

    Examples
    --------
    >>> resolver = ReferenceResolver()
    >>> references = parser.extract_references()
    >>> resolved = resolver.resolve_batch(references)
    >>> for ref in resolved:
    ...     if ref.resolved_pmid:
    ...         print(f"Resolved: {ref.resolved_pmid}")
    """

    def __init__(
        self,
        rate_limit: float = 3.0,
        api_key: str | None = None,
    ):
        self.rate_limit = max(rate_limit, 0.1)
        self.api_key = api_key
        self._last_request_time = 0.0
        self._stats = {"lookups": 0, "cache_hits": 0, "cache_size": 0}
        self._cache: dict[str, ResolvedReference] = {}

    def resolve_reference(self, ref: dict[str, Any]) -> ResolvedReference | None:
        """
        Resolve a single reference via API lookup.

        Searches by DOI first (most reliable), then PMID, then title+year.

        Parameters
        ----------
        ref : dict
            Reference dict from ``ReferenceParser.extract_references()``.

        Returns
        -------
        ResolvedReference or None
            Resolved data if found, None if lookup failed.
        """
        doi = ref.get("doi", "") or ""
        pmid = ref.get("pmid", "") or ""
        title = ref.get("title", "") or ""

        # Check cache
        cache_key = doi or pmid or title[:50]
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            return self._cache[cache_key]

        # Rate limiting
        self._throttle()

        result: ResolvedReference | None = None

        if doi:
            result = self._lookup_by_doi(doi)
        if result is None and pmid:
            result = self._lookup_by_pmid(pmid)
        if result is None and title:
            result = self._lookup_by_title(title)

        if result is not None:
            result.source_ref = ref
            self._cache[cache_key] = result
            self._stats["cache_size"] = len(self._cache)

        self._stats["lookups"] += 1
        return result

    def resolve_batch(
        self,
        references: list[dict[str, Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ResolvedReference]:
        """
        Resolve a batch of references.

        Parameters
        ----------
        references : list[dict]
            List of reference dicts from the parser.
        progress_callback : callable, optional
            Called with ``(completed, total)`` after each resolution.

        Returns
        -------
        list[ResolvedReference]
            Resolved references (empty entries for unresolved ones).
        """
        results: list[ResolvedReference] = []
        total = len(references)

        for i, ref in enumerate(references):
            resolved = self.resolve_reference(ref)
            if resolved is not None:
                results.append(resolved)
            else:
                # Return basic entry with source ref
                results.append(
                    ResolvedReference(
                        source_ref=ref,
                        resolved_pmid=ref.get("pmid", ""),
                        resolved_doi=ref.get("doi", ""),
                    )
                )

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def _lookup_by_doi(self, doi: str) -> ResolvedReference | None:
        """Look up a reference by DOI."""
        try:
            import json
            import urllib.request

            query = quote(f'DOI:"{doi}"')
            url = f"{EUROPE_PMC_API}?query={query}&format=json&pageSize=1"
            if self.api_key:
                url += f"&apiKey={self.api_key}"

            resp = urllib.request.urlopen(url, timeout=10)  # nosec
            data = json.loads(resp.read().decode())

            return self._parse_api_response(data)
        except Exception as e:
            logger.debug(f"DOI lookup failed for {doi}: {e}")
            return None

    def _lookup_by_pmid(self, pmid: str) -> ResolvedReference | None:
        """Look up a reference by PubMed ID."""
        try:
            import json
            import urllib.request

            query = quote(f'PMID:"{pmid}"')
            url = f"{EUROPE_PMC_API}?query={query}&format=json&pageSize=1"
            if self.api_key:
                url += f"&apiKey={self.api_key}"

            resp = urllib.request.urlopen(url, timeout=10)  # nosec
            data = json.loads(resp.read().decode())

            return self._parse_api_response(data)
        except Exception as e:
            logger.debug(f"PMID lookup failed for {pmid}: {e}")
            return None

    def _lookup_by_title(self, title: str) -> ResolvedReference | None:
        """Look up a reference by title."""
        if len(title) < 20:
            return None  # Title too short for reliable lookup

        try:
            import json
            import urllib.request

            query = quote(f'TITLE:"{title[:100]}"')
            url = f"{EUROPE_PMC_API}?query={query}&format=json&pageSize=3"
            if self.api_key:
                url += f"&apiKey={self.api_key}"

            resp = urllib.request.urlopen(url, timeout=15)  # nosec
            data = json.loads(resp.read().decode())

            results = data.get("resultList", {}).get("result", [])
            if results:
                return self._parse_entry(results[0])
            return None
        except Exception as e:
            logger.debug(f"Title lookup failed: {e}")
            return None

    def _parse_api_response(self, data: dict[str, Any]) -> ResolvedReference | None:
        """Parse the Europe PMC API response for the first result."""
        results = data.get("resultList", {}).get("result", [])
        if results:
            return self._parse_entry(results[0])
        return None

    @staticmethod
    def _parse_entry(entry: dict[str, Any]) -> ResolvedReference:
        """Parse a single API result entry."""
        return ResolvedReference(
            resolved_pmid=entry.get("pmid", "") or "",
            resolved_doi=entry.get("doi", "") or "",
            title=entry.get("title", "") or "",
            authors=entry.get("authorString", "") or "",
            year=entry.get("firstPublicationDate", "")[:4] or "",
            journal=entry.get("journalTitle", "") or "",
            citations=int(entry.get("citedByCount", 0) or 0),
            is_open_access=entry.get("isOpenAccess", False) or False,
        )

    def _throttle(self) -> None:
        """Apply rate limiting."""
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    @property
    def stats(self) -> dict[str, Any]:
        """Get resolver statistics."""
        return {**self._stats}
