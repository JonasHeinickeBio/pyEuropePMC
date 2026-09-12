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
import inspect
import logging
import time
from typing import Any

from pyeuropepmc.features.enrich.merger import (
    SOURCE_PRIORITY,
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
_DEFAULT_PRIMARY = "europepmc"


class _Unset:
    """Sentinel so ``primary=None`` (disable) differs from "not passed" (default)."""


_UNSET = _Unset()


def _accepted_params(func: Any) -> set[str] | None:
    """Names ``func`` accepts as keyword args, or ``None`` if it takes ``**kwargs``."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return None
    names: set[str] = set()
    for p in sig.parameters.values():
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            return None
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            names.add(p.name)
    return names


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
    primary : str | None, optional
        The "spine" source whose records anchor the merge — it is asked for
        more results (see *primary_limit_factor*), always wins field
        tie-breaks, and its record count is reported separately. Defaults to
        ``"europepmc"`` when Europe PMC is among the sources, else ``None``
        (all sources equal). Pass ``primary=None`` explicitly to disable.
    primary_limit_factor : float, optional
        Multiplier applied to ``limit`` for the primary source so the merged
        set stays primary-shaped (default: ``2.0``).
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
        primary: str | None | _Unset = _UNSET,
        primary_limit_factor: float = 2.0,
    ) -> None:
        sources = sources or list(_DEFAULT_SOURCES)

        known = set(registry.available_sources())
        unknown = [s for s in sources if s not in known]
        if unknown:
            raise ValueError(f"Unknown source(s) {unknown}. Available: {sorted(known)}")

        if isinstance(primary, _Unset):
            primary = _DEFAULT_PRIMARY if _DEFAULT_PRIMARY in sources else None
        if primary is not None and primary not in sources:
            raise ValueError(f"primary={primary!r} is not in sources {sources}")

        self.sources = sources
        self.primary = primary
        self.primary_limit_factor = max(1.0, primary_limit_factor)
        self.dedup_mode = dedup_mode
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.max_workers = max_workers
        self.translate = translate
        self.credentials: dict[str, Any] = dict(credentials or {})
        if api_key and "api_key" not in self.credentials:
            self.credentials["api_key"] = api_key
        self._clients: dict[str, Any] | None = None

    def _limits_for(self, sources: list[str], limit: int) -> dict[str, int]:
        """Per-source result cap — the primary source gets ``limit × factor``."""
        boosted = int(round(limit * self.primary_limit_factor))
        return {s: (boosted if s == self.primary else limit) for s in sources}

    def _dedup_config(self) -> DedupConfig:
        """DedupConfig for this run, pinning the primary source above all others."""
        if self.primary is None:
            return DedupConfig(mode=self.dedup_mode)
        priority = dict(SOURCE_PRIORITY)
        priority[self.primary] = max(priority.values()) + 100
        return DedupConfig(mode=self.dedup_mode, source_priority=priority)

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
            Merged, deduplicated results plus a report.  ``report.metadata``
            carries ``source_times``, ``source_errors``, ``sources_used``,
            ``source_counts`` (raw hits per source), and — when a *primary*
            source is set — ``primary_source``, ``primary_records`` (merged
            records anchored on the primary) and ``added_by_source`` (net-new
            records each satellite contributed).
        """
        clients = self._get_or_init_clients()
        sources = sources or self.sources
        limits = self._limits_for(sources, limit)

        per_source, source_times, source_errors = self._run_sources(
            clients, sources, query, limits, sort, translate=self.translate, **kwargs
        )
        source_counts = {s: len(r) for s, r in per_source.items()}

        all_results = [
            [r.model_dump() for r in results] for results in per_source.values() if results
        ]
        if not all_results:
            logger.warning("No results from any source (errors: %s)", source_errors)
            report = MergeReport()
            report.metadata.update(
                source_times=source_times,
                source_errors=source_errors,
                sources_used=sources,
                source_counts=source_counts,
            )
            return [], report

        merger = LiteratureMerger(config=self._dedup_config())
        merged_dicts, report = merger.merge_results(all_results)
        report.metadata.update(
            source_times=source_times,
            source_errors=source_errors,
            sources_used=sources,
            source_counts=source_counts,
        )

        merged = [LiteratureResult.model_validate(d) for d in merged_dicts if d is not None]
        self._annotate_provenance(merged, report, per_source)

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

    def _annotate_provenance(
        self,
        merged: list[LiteratureResult],
        report: MergeReport,
        per_source: dict[str, list[LiteratureResult]],
    ) -> None:
        """Record how much of the merged set is anchored on the primary source."""
        if self.primary is None:
            return

        def _keys(rec: Any) -> set[str]:
            g = getattr(rec, "get", None)
            doi = (g("doi") if g else getattr(rec, "doi", None)) or None
            pmid = (g("pmid") if g else getattr(rec, "pmid", None)) or None
            title = (g("title") if g else getattr(rec, "title", None)) or None
            out = set()
            if doi:
                out.add(f"doi:{str(doi).lower()}")
            if pmid:
                out.add(f"pmid:{pmid}")
            if title:
                out.add(f"title:{str(title).lower().strip()[:80]}")
            return out

        primary_keys: set[str] = set()
        for rec in per_source.get(self.primary, []):
            primary_keys |= _keys(rec)

        primary_records = 0
        added_by_source: dict[str, int] = {}
        for rec in merged:
            if rec.source == self.primary or _keys(rec) & primary_keys:
                primary_records += 1
            else:
                added_by_source[rec.source] = added_by_source.get(rec.source, 0) + 1

        report.metadata["primary_source"] = self.primary
        report.metadata["primary_records"] = primary_records
        report.metadata["added_by_source"] = added_by_source

    def search_all(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> tuple[dict[str, list[LiteratureResult]], dict[str, str]]:
        """Search every source in parallel **without** dedup.

        Returns ``(per_source_results, per_source_errors)``.
        """
        clients = self._get_or_init_clients()
        limits = self._limits_for(self.sources, limit)
        per_source, _, errors = self._run_sources(
            clients, self.sources, query, limits, None, translate=self.translate, **kwargs
        )
        return per_source, errors

    # ------------------------------------------------------------------
    # Parallel fan-out
    # ------------------------------------------------------------------

    def _run_sources(
        self,
        clients: dict[str, Any],
        sources: list[str],
        query: str,
        limits: dict[str, int],
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
            # Only pass search kwargs the client actually accepts, so a source
            # with a narrower signature drops out gracefully instead of raising
            # TypeError (which would look like a source failure).
            call: dict[str, Any] = {"query": q, "limit": limits.get(source_name, 25)}
            accepted = _accepted_params(client.search)
            for key, value in (("sort", sort), *kwargs.items()):
                if accepted is None or key in accepted:
                    call[key] = value
            return list(client.search(**call))

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
