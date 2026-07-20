"""
Citation graph walking utility.

Uses the Semantic Scholar API to walk forward (cited-by) and backward
(references) through the citation graph, enabling snowballing literature
reviews. Results can be deduplicated and merged using the standard
LiteratureMerger pipeline.

References
----------
- Semantic Scholar API: https://api.semanticscholar.org/graph/v1
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.features.enrich.merger import (
    DedupConfig,
    DedupMode,
    LiteratureMerger,
    MergeReport,
)
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["CitationWalker", "SnowballingStrategy"]

# Default S2 API base URL
_S2_BASE = "https://api.semanticscholar.org/graph/v1"
# Fields we request from S2
_S2_PAPER_FIELDS = (
    "paperId,externalIds,title,authors,year,journal,abstract,citationCount,"
    "referenceCount,publicationDate,venue"
)
# Max page size for S2 API
_S2_PAGE_SIZE = 100


class SnowballingStrategy:
    """Strategy for citation snowballing direction."""

    FORWARD = "forward"  # Papers that cite the seed paper
    BACKWARD = "backward"  # Papers referenced by the seed paper
    BOTH = "both"  # Both directions


class CitationWalker:
    """
    Citation graph walking utility.

    Walks the Semantic Scholar citation graph to discover related papers
    through forward (cited-by) and backward (references) traversal.

    Uses the free Semantic Scholar API (no key required for basic usage).

    Examples
    --------
    >>> walker = CitationWalker()
    >>> results, report = walker.snowball(
    ...     identifier="DOI:10.1038/s41586-020-2649-2",
    ...     strategy=SnowballingStrategy.BOTH,
    ...     max_papers=50,
    ... )
    >>> print(f"Found {len(results)} papers in citation graph")
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 30,
        cache_config: CacheConfig | None = None,
        api_key: str | None = None,
        skip_dedup: bool = False,
        dedup_mode: DedupMode = DedupMode.BALANCED,
    ) -> None:
        """
        Initialize citation walker.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between API requests (default: 1.0).
        timeout : int, optional
            Request timeout in seconds (default: 30).
        cache_config : CacheConfig, optional
            Cache configuration.
        api_key : str, optional
            Semantic Scholar API key (for higher rate limits).
        skip_dedup : bool, optional
            Skip internal deduplication (default: False).
        dedup_mode : DedupMode, optional
            Dedup mode for merging results (default: BALANCED).
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.api_key = api_key
        self.skip_dedup = skip_dedup
        self.dedup_mode = dedup_mode

        from pyeuropepmc.features.enrich.sources.semantic_scholar import SemanticScholarClient

        self._s2_client = SemanticScholarClient(
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def snowball(
        self,
        identifier: str,
        strategy: str = SnowballingStrategy.FORWARD,
        max_papers: int = 100,
        max_depth: int = 1,
        min_citations: int = 0,
    ) -> tuple[list[LiteratureResult], MergeReport]:
        """
        Perform citation snowballing from a seed paper.

        Parameters
        ----------
        identifier : str
            Seed paper identifier (DOI, PMID, or S2 paperId).
            Use ``"DOI:10.xxxx"`` or ``"PMID:xxxxx"`` prefix for disambiguation.
        strategy : str
            Snowballing direction: ``"forward"`` (cited-by), ``"backward"``
            (references), or ``"both"``.
        max_papers : int, optional
            Maximum total papers to return (default: 100).
        max_depth : int, optional
            Maximum traversal depth. Depth > 1 walks the graph recursively.
            (default: 1, single-hop).
        min_citations : int, optional
            Minimum citation count filter (default: 0 = no filter).

        Returns
        -------
        tuple[list[LiteratureResult], MergeReport]
            List of discovered papers and dedup report.
        """
        # Resolve seed paper
        seed = self._resolve_seed(identifier)
        if not seed:
            logger.warning("Could not resolve seed paper: %s", identifier)
            return [], MergeReport()

        s2_id = seed.get("paperId")
        if not s2_id:
            return [], MergeReport()

        all_papers: dict[str, LiteratureResult] = {}
        # Track visited S2 IDs to prevent cycles
        visited: set[str] = set()

        if strategy in (SnowballingStrategy.FORWARD, SnowballingStrategy.BOTH):
            self._walk(
                s2_id=s2_id,
                direction="citations",
                all_papers=all_papers,
                visited=visited,
                max_papers=max_papers,
                depth=0,
                max_depth=max_depth,
                min_citations=min_citations,
            )

        if strategy in (SnowballingStrategy.BACKWARD, SnowballingStrategy.BOTH):
            self._walk(
                s2_id=s2_id,
                direction="references",
                all_papers=all_papers,
                visited=visited,
                max_papers=max_papers,
                depth=0,
                max_depth=max_depth,
                min_citations=min_citations,
            )

        if not all_papers:
            return [], MergeReport()

        results = list(all_papers.values())

        # Deduplicate
        if not self.skip_dedup and len(results) > 1:
            merger = LiteratureMerger(config=DedupConfig(mode=self.dedup_mode))
            merged, report = merger.merge_results([results])
            return merged, report

        return results, MergeReport(
            total_input=len(results),
            total_output=len(results),
            duplicates_removed=0,
        )

    def get_citations(
        self,
        identifier: str,
        limit: int = 100,
    ) -> list[LiteratureResult]:
        """
        Get papers that cite the given paper (forward citations).

        Parameters
        ----------
        identifier : str
            Paper identifier (DOI, PMID, or S2 paperId).
        limit : int, optional
            Maximum results (default: 100).

        Returns
        -------
        list[LiteratureResult]
            List of citing papers.
        """
        results, _ = self.snowball(
            identifier=identifier,
            strategy=SnowballingStrategy.FORWARD,
            max_papers=limit,
        )
        return results

    def get_references(
        self,
        identifier: str,
        limit: int = 100,
    ) -> list[LiteratureResult]:
        """
        Get papers referenced by the given paper (backward citations).

        Parameters
        ----------
        identifier : str
            Paper identifier (DOI, PMID, or S2 paperId).
        limit : int, optional
            Maximum results (default: 100).

        Returns
        -------
        list[LiteratureResult]
            List of referenced papers.
        """
        results, _ = self.snowball(
            identifier=identifier,
            strategy=SnowballingStrategy.BACKWARD,
            max_papers=limit,
        )
        return results

    # ------------------------------------------------------------------
    # Internal traversal
    # ------------------------------------------------------------------

    def _walk(
        self,
        s2_id: str,
        direction: str,
        all_papers: dict[str, LiteratureResult],
        visited: set[str],
        max_papers: int,
        depth: int,
        max_depth: int,
        min_citations: int,
    ) -> None:
        """Recursive citation graph walker."""
        if depth > max_depth:
            return
        if s2_id in visited:
            return
        if len(all_papers) >= max_papers:
            return

        visited.add(s2_id)

        # Fetch papers in this direction
        papers = self._fetch_direction(s2_id, direction, offset=0, limit=_S2_PAGE_SIZE)

        for paper_data in papers:
            if len(all_papers) >= max_papers:
                break

            paper = self._s2_paper_to_result(paper_data)
            if paper is None:
                continue

            # Citation count filter
            citation_count = paper.citation_count or 0
            if min_citations > 0 and citation_count < min_citations:
                continue

            # Use S2 paperId as dedup key within the walk
            paper_id = paper_data.get("paperId", "")
            if paper_id and paper_id not in all_papers:
                all_papers[paper_id] = paper

            # Recurse to next depth
            if depth + 1 <= max_depth:
                self._walk(
                    s2_id=paper_id,
                    direction=direction,
                    all_papers=all_papers,
                    visited=visited,
                    max_papers=max_papers,
                    depth=depth + 1,
                    max_depth=max_depth,
                    min_citations=min_citations,
                )

    def _fetch_direction(
        self,
        s2_id: str,
        direction: str,
        offset: int = 0,
        limit: int = _S2_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Fetch papers in one direction from the S2 API."""
        url = f"{_S2_BASE}/paper/{s2_id}/{direction}"
        params: dict[str, Any] = {
            "fields": _S2_PAPER_FIELDS,
            "offset": offset,
            "limit": min(limit, _S2_PAGE_SIZE),
        }

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        import requests as _requests

        try:
            resp = _requests.get(url, params=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            time.sleep(self.rate_limit_delay)
            return data.get(direction, [])
        except Exception as e:
            logger.warning("Failed to fetch %s for %s: %s", direction, s2_id, e)
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_seed(self, identifier: str) -> dict[str, Any] | None:
        """Resolve a seed paper identifier to S2 paper data."""
        # Try Semantic Scholar enrichment
        try:
            data = self._s2_client.enrich(identifier)
            if data:
                return data
        except Exception:
            pass

        # Fallback: query S2 API directly
        url = f"{_S2_BASE}/paper/search"
        params = {"query": identifier, "limit": 1, "fields": _S2_PAPER_FIELDS}

        import requests as _requests

        try:
            resp = _requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            matches = data.get("data", [])
            if matches:
                return matches[0]
        except Exception:
            pass

        return None

    def _s2_paper_to_result(self, data: dict[str, Any]) -> LiteratureResult | None:
        """Convert S2 API paper data to LiteratureResult."""
        title = data.get("title")
        if not title:
            return None

        ext_ids = data.get("externalIds", {}) or {}

        authors_raw = data.get("authors") or []
        from pyeuropepmc.models.literature import Author

        authors = None
        if authors_raw:
            author_list = [Author(name=a.get("name", "")) for a in authors_raw if a.get("name")]
            if author_list:
                authors = author_list

        journal_data = data.get("journal")
        journal = None
        if isinstance(journal_data, dict):
            journal = journal_data.get("name")
        elif isinstance(journal_data, str):
            journal = journal_data

        return LiteratureResult(
            doi=ext_ids.get("DOI"),
            pmid=ext_ids.get("PubMed"),
            pmcid=ext_ids.get("PubMedCentral"),
            title=title,
            authors=authors,
            publication_year=data.get("year"),
            journal=journal or data.get("venue"),
            abstract=data.get("abstract"),
            citation_count=data.get("citationCount"),
            source="semanticscholar",
            source_id=data.get("paperId", ""),
        )
