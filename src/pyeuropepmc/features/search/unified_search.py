"""
Unified multi-source literature search orchestrator.

Federates a single query across multiple literature sources, translates the
query into each source's dialect, runs the sources in parallel, then normalizes
and deduplicates the combined results into one merged list.

Sources come from :mod:`pyeuropepmc.features.search.registry`, so the set is
pluggable (third parties can ``register_source``) and dependency-aware
(selecting a source whose optional package is missing raises a helpful error).

Examples
--------
>>> from pyeuropepmc.features.search import UnifiedSearch
>>> searcher = UnifiedSearch(sources=["europepmc", "pubmed", "arxiv"])
>>> results, report = searcher.search("CRISPR cancer therapy", limit=10)
>>> print(f"{len(results)} papers, {report.duplicates_removed} dupes removed")
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
import logging
import time
from typing import Any

from pyeuropepmc.features.enrich.merger import (
    DedupConfig,
    DedupMode,
    LiteratureMerger,
    MergeReport,
)
from pyeuropepmc.features.search.query_translation import translate_query
import pyeuropepmc.features.search.registry as registry
from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = ["UnifiedSearch"]

_DEFAULT_SOURCES = ["europepmc", "pubmed", "arxiv"]


class UnifiedSearch:
    """
    Orchestrator for multi-source literature search.

    Parameters
    ----------
    sources : list[str] | None
        Source names to search (see
        :func:`pyeuropepmc.features.search.registry.available_sources`).
        Default: ``["europepmc", "pubmed", "arxiv"]``.
    dedup_mode : DedupMode, optional
        Deduplication mode (default: ``DedupMode.BALANCED``).
    timeout : int, optional
        Per-source request timeout in seconds (default: 30).
    rate_limit_delay : float, optional
        Delay between requests for each source client (default: 1.2 s, chosen
        for Semantic Scholar's 1 req/s unauthenticated limit).
    max_workers : int | None, optional
        Thread-pool size for the parallel fan-out (default: one per source).
    translate : bool, optional
        Translate the query into each source's dialect (default: ``True``).
    credentials : dict[str, Any] | None, optional
        Per-credential values forwarded to whichever sources accept them, e.g.
        ``{"api_key": "...", "email": "you@example.org"}``.
    api_key : str | None, optional
        Backwards-compatible shortcut for ``credentials={"api_key": ...}``.
    """

    def __init__(
        self,
        sources: list[str] | None = None,
        dedup_mode: DedupMode = DedupMode.BALANCED,
        timeout: int = 30,
        rate_limit_delay: float = 1.2,
        api_key: str | None = None,
        max_workers: int | None = None,
        translate: bool = True,
        credentials: dict[str, Any] | None = None,
    ) -> None:
        sources = sources or list(_DEFAULT_SOURCES)

        known = set(registry.available_sources())
        unknown = [s for s in sources if s not in known]
        if unknown:
            raise ValueError(f"Unknown source(s) {unknown}. Available: {sorted(known)}")

        self.sources = sources
        self.dedup_mode = dedup_mode
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.max_workers = max_workers
        self.translate = translate
        self.credentials: dict[str, Any] = dict(credentials or {})
        if api_key and "api_key" not in self.credentials:
            self.credentials["api_key"] = api_key
        self._clients: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 25,
        sort: str | None = None,
        sources: list[str] | None = None,
        **kwargs: Any,
    ) -> tuple[list[LiteratureResult], MergeReport]:
        """
        Search across all configured sources in parallel and deduplicate.

        Returns
        -------
        tuple[list[LiteratureResult], MergeReport]
            Merged, deduplicated results plus a report.  Per-source timings are
            in ``report.metadata["source_times"]`` and per-source failures in
            ``report.metadata["source_errors"]``.
        """
        clients = self._get_or_init_clients()
        sources = sources or self.sources

        per_source, source_times, source_errors = self._run_sources(
            clients, sources, query, limit, sort, translate=self.translate, **kwargs
        )

        all_results = [
            [r.model_dump() for r in results] for results in per_source.values() if results
        ]
        if not all_results:
            logger.warning("No results from any source (errors: %s)", source_errors)
            report = MergeReport()
            report.metadata["source_times"] = source_times
            report.metadata["source_errors"] = source_errors
            report.metadata["sources_used"] = sources
            return [], report

        merger = LiteratureMerger(config=DedupConfig(mode=self.dedup_mode))
        merged_dicts, report = merger.merge_results(all_results)
        report.metadata["source_times"] = source_times
        report.metadata["source_errors"] = source_errors
        report.metadata["sources_used"] = sources

        merged = [LiteratureResult.model_validate(d) for d in merged_dicts if d is not None]

        total_in = sum(len(r) for r in all_results)
        logger.info(
            "UnifiedSearch: %d/%d sources ok → %d results → %d after dedup (%.1f%% reduction)",
            len(all_results),
            len(sources),
            total_in,
            len(merged),
            (1 - len(merged) / max(total_in, 1)) * 100,
        )
        return merged, report

    def search_all(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> dict[str, list[LiteratureResult]]:
        """Search every source in parallel **without** dedup; return per-source lists."""
        clients = self._get_or_init_clients()
        per_source, _, _ = self._run_sources(
            clients, self.sources, query, limit, None, translate=self.translate, **kwargs
        )
        return per_source

    # ------------------------------------------------------------------
    # Parallel fan-out
    # ------------------------------------------------------------------

    def _run_sources(
        self,
        clients: dict[str, Any],
        sources: list[str],
        query: str,
        limit: int,
        sort: str | None,
        *,
        translate: bool,
        **kwargs: Any,
    ) -> tuple[dict[str, list[LiteratureResult]], dict[str, float], dict[str, str]]:
        active = [(s, clients.get(s)) for s in sources]
        runnable = [(s, c) for s, c in active if c is not None]

        per_source: dict[str, list[LiteratureResult]] = {}
        source_times: dict[str, float] = {}
        source_errors: dict[str, str] = {
            s: "client not initialised" for s, c in active if c is None
        }

        def _one(source_name: str, client: Any) -> list[LiteratureResult]:
            q = translate_query(query, source_name) if translate else query
            if q != query:
                logger.debug("query for %s: %r -> %r", source_name, query, q)
            return list(client.search(query=q, limit=limit, sort=sort, **kwargs))

        if not runnable:
            return per_source, source_times, source_errors

        workers = self.max_workers or len(runnable)
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(_one, s, c): s for s, c in runnable}
            for fut in as_completed(futures):
                source_name = futures[fut]
                elapsed = time.monotonic() - started
                source_times[source_name] = elapsed
                try:
                    results = fut.result()
                    per_source[source_name] = results
                    logger.info(
                        "Source '%s' returned %d results in %.2fs",
                        source_name,
                        len(results),
                        elapsed,
                    )
                except Exception as exc:  # noqa: BLE001 - report, don't abort the batch
                    source_errors[source_name] = f"{type(exc).__name__}: {exc}"
                    logger.error("Source '%s' failed: %s", source_name, exc)

        return per_source, source_times, source_errors

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def _get_or_init_clients(self) -> dict[str, Any]:
        if self._clients is not None:
            return self._clients

        self._clients = {}
        for source_name in self.sources:
            spec = registry.get_source_spec(source_name)
            kwargs: dict[str, Any] = {
                "rate_limit_delay": self.rate_limit_delay,
                "timeout": self.timeout,
            }
            for cred in spec.credential_kwargs:
                if self.credentials.get(cred) is not None:
                    kwargs[cred] = self.credentials[cred]
            try:
                self._clients[source_name] = registry.load_source(source_name, **kwargs)
            except Exception as exc:  # noqa: BLE001 - missing dep / init failure
                logger.warning("Failed to init source '%s': %s", source_name, exc)
                self._clients[source_name] = None

        return self._clients

    def close(self) -> None:
        """Close all initialised clients."""
        if self._clients:
            for client in self._clients.values():
                if client and hasattr(client, "close"):
                    with contextlib.suppress(Exception):
                        client.close()
            self._clients = None

    def __enter__(self) -> UnifiedSearch:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def available_sources(self) -> list[str]:
        """All registered source names (see the registry for capability info)."""
        return registry.available_sources()
