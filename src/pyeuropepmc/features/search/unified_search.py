"""
Unified multi-source literature search orchestrator.

Federates a single query across multiple literature sources, normalizes
and deduplicates results, and returns a single merged list. Supports
all registered literature clients and adapters.

Examples
    --------
    >>> from pyeuropepmc.features.search import UnifiedSearch
    >>> searcher = UnifiedSearch(sources=["pubmed", "arxiv", "semantic_scholar", "zenodo"])
    >>> results, report = searcher.search("CRISPR cancer therapy", limit=10)
    >>> print(f"Found {len(results)} papers (removed {report.duplicates_removed} dupes)")
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pyeuropepmc.features.enrich.merger import (
    DedupConfig,
    DedupMode,
    LiteratureMerger,
    MergeReport,
)
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["UnifiedSearch"]

# Map of source names to (module_path, class_name)
_SOURCE_REGISTRY: dict[str, tuple[str, str]] = {
    "pubmed": ("pyeuropepmc.features.search.sources.pubmed", "PubMedClient"),
    "arxiv": ("pyeuropepmc.features.search.sources.arxiv", "ArxivClient"),
    "clinicaltrials": ("pyeuropepmc.features.search.sources.clinicaltrials", "ClinicalTrialsClient"),
    "semantic_scholar": ("pyeuropepmc.features.literature.adapters", "SemanticScholarLiteratureAdapter"),
    "openalex": ("pyeuropepmc.features.literature.adapters", "OpenAlexLiteratureAdapter"),
    "zenodo": ("pyeuropepmc.features.search.sources.zenodo", "ZenodoClient"),
    "doaj": ("pyeuropepmc.features.search.sources.doaj", "DOAJClient"),
    "dblp": ("pyeuropepmc.features.search.sources.dblp", "DBLPClient"),
    "hal": ("pyeuropepmc.features.search.sources.hal", "HALClient"),
    "core": ("pyeuropepmc.features.search.sources.core", "COREClient"),
}


def _import_client(source: str) -> Any:
    """Lazy-import a client class by source name."""
    module_path, class_name = _SOURCE_REGISTRY[source]
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


class UnifiedSearch:
    """
    Orchestrator for multi-source literature search.

    Searches across multiple configured sources, normalizes results,
    and deduplicates them using the LiteratureMerger.

    Parameters
    ----------
    sources : list[str] | None
        Source names to search. Default: ``["pubmed", "arxiv", "semantic_scholar"]``.
        Available: ``"pubmed"``, ``"arxiv"``, ``"clinicaltrials"``,
        ``"semantic_scholar"``, ``"openalex"``, ``"zenodo"``, ``"doaj"``,
        ``"dblp"``, ``"hal"``, ``"core"``.
    dedup_mode : DedupMode, optional
        Deduplication mode (default: ``DedupMode.BALANCED``).
    timeout : int, optional
        Per-source timeout in seconds (default: 30).
    max_workers : int, optional
        Maximum parallel workers (default: None = all sources).
    """

    def __init__(
        self,
        sources: list[str] | None = None,
        dedup_mode: DedupMode = DedupMode.BALANCED,
        timeout: int = 30,
        rate_limit_delay: float = 0.5,
    ) -> None:
        if sources is None:
            sources = ["pubmed", "arxiv", "semantic_scholar"]

        # Validate sources
        for s in sources:
            if s not in _SOURCE_REGISTRY:
                raise ValueError(
                    f"Unknown source '{s}'. Available: {list(_SOURCE_REGISTRY.keys())}"
                )

        self.sources = sources
        self.dedup_mode = dedup_mode
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self._clients: dict[str, Any] | None = None

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        sources: list[str] | None = None,
        **kwargs: Any,
    ) -> tuple[list[LiteratureResult], MergeReport]:
        """
        Search across all configured sources.

        Parameters
        ----------
        query : str
            Search query string.
        limit : int, optional
            Maximum results **per source** (default: 25).
            The merged total will be less than ``limit * len(sources)``
            after dedup.
        sort : str, optional
            Sort order (passed to each source).
        sources : list[str], optional
            Override the source set for this search only. If ``None``,
            uses the sources configured on the instance.
        **kwargs
            Additional parameters passed to each source's ``search()``.

        Returns
        -------
        tuple[list[LiteratureResult], MergeReport]
            Merged, deduplicated results and a dedup report.
        """
        clients = self._get_or_init_clients()
        sources = sources or self.sources

        # Search all sources
        all_results: list[list[dict[str, Any]]] = []
        source_times: dict[str, float] = {}

        for source_name in sources:
            client = clients.get(source_name)
            if client is None:
                logger.warning("Source '%s' not initialized, skipping", source_name)
                continue

            try:
                start = time.monotonic()
                results = client.search(query=query, limit=limit, sort=sort, **kwargs)
                elapsed = time.monotonic() - start
                source_times[source_name] = elapsed
                logger.info(
                    "Source '%s' returned %d results in %.2fs",
                    source_name,
                    len(results),
                    elapsed,
                )
                # The merger operates on plain dicts; convert LiteratureResult
                # objects (with nested pydantic models) to dictionaries.
                all_results.append([r.model_dump() for r in results])
            except Exception as e:
                logger.error("Source '%s' failed: %s", source_name, e)
                source_times[source_name] = -1.0

        if not all_results:
            logger.warning("No results from any source")
            return [], MergeReport()

        # Merge and deduplicate
        merger = LiteratureMerger(config=DedupConfig(mode=self.dedup_mode))
        merged_dicts, report = merger.merge_results(all_results)
        report.metadata["source_times"] = source_times
        report.metadata["sources_used"] = sources

        # Restore the public result type (extra fields pass through due to
        # ``extra="allow"`` on LiteratureResult).
        merged = [
            LiteratureResult.model_validate(d)
            for d in merged_dicts
            if d is not None
        ]

        logger.info(
            "UnifiedSearch: %d sources → %d results → %d after dedup (%.1f%% reduction)",
            len(sources),
            sum(len(r) for r in all_results),
            len(merged),
            (1 - len(merged) / max(sum(len(r) for r in all_results), 1)) * 100,
        )

        return merged, report

    def search_all(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> dict[str, list[LiteratureResult]]:
        """
        Search all sources **without** deduplication, returning per-source results.

        Useful for comparing source coverage or for custom merging.

        Parameters
        ----------
        query : str
            Search query string.
        limit : int, optional
            Maximum results per source (default: 25).
        **kwargs
            Additional search parameters.

        Returns
        -------
        dict[str, list[LiteratureResult]]
            Mapping of source name to its raw results.
        """
        clients = self._get_or_init_clients()
        per_source: dict[str, list[LiteratureResult]] = {}

        for source_name in self.sources:
            client = clients.get(source_name)
            if client is None:
                continue
            try:
                results = client.search(query=query, limit=limit, **kwargs)
                per_source[source_name] = list(results)
            except Exception as e:
                logger.error("Source '%s' failed: %s", source_name, e)
                per_source[source_name] = []

        return per_source

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def _get_or_init_clients(self) -> dict[str, Any]:
        """Lazy-initialize all source clients."""
        if self._clients is not None:
            return self._clients

        self._clients = {}
        for source_name in self.sources:
            try:
                client_class = _import_client(source_name)
                self._clients[source_name] = client_class(
                    rate_limit_delay=self.rate_limit_delay,
                    timeout=self.timeout,
                )
            except Exception as e:
                logger.warning("Failed to init client '%s': %s", source_name, e)
                self._clients[source_name] = None

        return self._clients

    def close(self) -> None:
        """Close all initialized clients."""
        if self._clients:
            for client in self._clients.values():
                if client and hasattr(client, "close"):
                    try:
                        client.close()
                    except Exception:
                        pass
            self._clients = None

    @property
    def available_sources(self) -> list[str]:
        """Return list of all registered source names."""
        return list(_SOURCE_REGISTRY.keys())
