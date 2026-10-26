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
import re
import threading
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

#: Delay between requests when ``rate_limit_delay`` is not given (chosen for Semantic Scholar's
#: 1 request per second without a key).
DEFAULT_RATE_LIMIT_DELAY = 1.2
#: Sources whose own client waits longer by default, because the provider asks for it (arXiv: one
#: request every 3 seconds). Without an explicit ``rate_limit_delay`` or ``rate_limits`` entry a
#: source is never paced faster than this.
SOURCE_MIN_DELAY: dict[str, float] = {"arxiv": 3.0, "dblp": 3.0, "zenodo": 3.0}


class _Unset:
    """Sentinel so ``primary=None`` (disable) differs from "not passed" (default)."""


_UNSET = _Unset()


#: Canonical sort tokens accepted by :meth:`UnifiedSearch.search`, mapped to the
#: value each source's own ``search()`` expects.  ``None`` means "this source
#: cannot sort that way" — the key is then left out of the call so the source
#: falls back to its default order instead of receiving a value it rejects.
#: A source that is missing from a row, or a ``sort`` value that is not a
#: canonical token, is passed through unchanged, so source-native values such as
#: ``sort="P_PDATE_D desc"`` still work when you search a single source.
_SORT_BY_SOURCE: dict[str, dict[str, str | None]] = {
    "relevance": {
        "europepmc": None,  # Europe PMC's default order is relevance
        "pubmed": "relevance",
        "openalex": "relevance",
        "semantic_scholar": None,
        "clinicaltrials": "relevance",
    },
    "date": {
        "europepmc": "P_PDATE_D desc",
        "pubmed": "pub_date",
        "arxiv": "date",
        "openalex": "date",
        "semantic_scholar": "publicationDate:desc",
        "clinicaltrials": "last_update",
        "core": "date",
        "doaj": "date",
        "hal": "date",
        "zenodo": "date",
        "dblp": None,
    },
    "citations": {
        "europepmc": "CITED desc",
        "pubmed": None,
        "arxiv": None,
        "openalex": "citation_count",
        "semantic_scholar": "citationCount:desc",
        "clinicaltrials": None,
        "core": None,
        "doaj": None,
        "hal": None,
        "zenodo": None,
        "dblp": None,
    },
}

#: Aliases for the canonical tokens above.
_SORT_ALIASES = {"citation_count": "citations", "cited": "citations"}


def _translate_sort(sort: str | None, source: str) -> tuple[bool, str | None]:
    """Map a canonical ``sort`` token to *source*'s dialect.

    Returns ``(send, value)``.  ``send=False`` means the source cannot sort this
    way and ``sort`` should be left off the call entirely.
    """
    if sort is None:
        return False, None
    canonical = _SORT_ALIASES.get(sort.strip().lower(), sort.strip().lower())
    per_source = _SORT_BY_SOURCE.get(canonical)
    if per_source is None or source not in per_source:
        # Not a canonical token (or a source we have no mapping for): the caller
        # knows this source's dialect better than we do.
        return True, sort
    value = per_source[source]
    if value is None:
        logger.debug("Source '%s' cannot sort by %r — using its default order", source, canonical)
        return False, None
    return True, value


_RATE_LIMITED = re.compile(r"rate.?limit|too many requests|\b429\b", re.IGNORECASE)


def _http_status(exc: BaseException) -> int | None:
    """The HTTP status an exception (or one it was raised from) carries, if any."""
    seen = 0
    err: BaseException | None = exc
    while err is not None and seen < 5:
        response = getattr(err, "response", None)
        status = getattr(response, "status_code", None)
        if status is None:
            context = getattr(err, "context", None)
            status = context.get("status_code") if isinstance(context, dict) else None
        if isinstance(status, int):
            return status
        err, seen = err.__cause__ or err.__context__, seen + 1
    return None


def _retry_after(exc: BaseException) -> float | None:
    """Seconds a server asked to wait (``Retry-After``), when the error carries a response."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    value = headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _failure(exc: BaseException) -> dict[str, Any]:
    """Status record of a source that raised: ``rate_limited`` for HTTP 429 or a rate-limit
    message, otherwise ``error``."""
    status = _http_status(exc)
    message = str(exc)
    limited = status == 429 or bool(_RATE_LIMITED.search(message))
    return {
        "status": "rate_limited" if limited else "error",
        "error": {"type": type(exc).__name__, "message": message, "http_status": status},
        "retry_after": _retry_after(exc) if limited else None,
    }


def _record_keys(rec: Any) -> set[str]:
    """Identity keys of a record (DOI, PMID, title prefix), for matching across sources."""
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
        Delay between requests for every source client, replacing each client's
        own default. Left out, it is 1.2 s (Semantic Scholar's 1 req/s
        unauthenticated limit), and a source whose provider asks for more
        (``SOURCE_MIN_DELAY``: arXiv, DBLP and Zenodo, 3 s) keeps that.
    rate_limits : dict[str, float] | None, optional
        Delay in seconds per source; wins over ``rate_limit_delay`` for the
        sources it names, e.g. ``{"arxiv": 5.0, "openalex": 0.2}``.
    source_concurrency : int | dict[str, int], optional
        How many calls to one source may run at the same time, across every
        thread that shares this object (default: 1). One ``search()`` makes one
        call per source, so this matters when several searches run at once, as
        in a server. An ``int`` applies to every source; a dict names sources
        and leaves the others at 1.
    max_workers : int | None, optional
        Thread-pool size for the parallel fan-out, i.e. how many sources one
        ``search()`` queries at once (default: one per source).
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
        rate_limit_delay: float | None = None,
        api_key: str | None = None,
        max_workers: int | None = None,
        translate: bool = True,
        credentials: dict[str, Any] | None = None,
        primary: str | None | _Unset = _UNSET,
        primary_limit_factor: float = 2.0,
        rate_limits: dict[str, float] | None = None,
        source_concurrency: int | dict[str, int] = 1,
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
        self._explicit_delay = rate_limit_delay is not None
        self.rate_limit_delay = (
            DEFAULT_RATE_LIMIT_DELAY if rate_limit_delay is None else rate_limit_delay
        )
        self.rate_limits = self._checked_limits(rate_limits, sources)
        self.max_concurrency = self._checked_concurrency(source_concurrency, sources)
        self._gates = {s: threading.BoundedSemaphore(self.max_concurrency[s]) for s in sources}
        if self.rate_limit_delay < 0:
            raise ValueError(f"rate_limit_delay must not be negative, got {rate_limit_delay}")
        self.max_workers = max_workers
        self.translate = translate
        self.credentials: dict[str, Any] = dict(credentials or {})
        if api_key and "api_key" not in self.credentials:
            self.credentials["api_key"] = api_key
        self._clients: dict[str, Any] | None = None
        self._init_errors: dict[str, str] = {}
        self._init_lock = threading.RLock()

    @staticmethod
    def _checked_limits(
        rate_limits: dict[str, float] | None, sources: list[str]
    ) -> dict[str, float]:
        given = dict(rate_limits or {})
        stray = [s for s in given if s not in sources]
        if stray:
            raise ValueError(f"rate_limits names {stray}, which are not in sources {sources}")
        negative = {s: v for s, v in given.items() if v < 0}
        if negative:
            raise ValueError(f"rate_limits must not be negative, got {negative}")
        return {s: float(v) for s, v in given.items()}

    @staticmethod
    def _checked_concurrency(value: int | dict[str, int], sources: list[str]) -> dict[str, int]:
        if isinstance(value, dict):
            stray = [s for s in value if s not in sources]
            if stray:
                raise ValueError(f"source_concurrency names {stray}, not in sources {sources}")
            chosen = {s: value.get(s, 1) for s in sources}
        else:
            chosen = dict.fromkeys(sources, value)
        bad = {s: v for s, v in chosen.items() if not isinstance(v, int) or v < 1}
        if bad:
            raise ValueError(f"source_concurrency must be a whole number of at least 1, got {bad}")
        return chosen

    def delay_for(self, source: str) -> float:
        """Seconds the client of ``source`` waits between its requests: its ``rate_limits``
        entry, else ``rate_limit_delay`` when that was given, else 1.2 s or the provider's
        minimum (``SOURCE_MIN_DELAY``), whichever is longer."""
        if source in self.rate_limits:
            return self.rate_limits[source]
        if self._explicit_delay:
            return self.rate_limit_delay
        return max(self.rate_limit_delay, SOURCE_MIN_DELAY.get(source, 0.0))

    @property
    def limits(self) -> dict[str, dict[str, float | int]]:
        """The effective limits per source: ``rate_limit_delay`` (seconds between requests) and
        ``max_concurrency`` (simultaneous calls)."""
        return {s: self._limits_of(s) for s in self.sources}

    def _limits_of(self, source: str) -> dict[str, float | int]:
        return {
            "rate_limit_delay": self.delay_for(source),
            "max_concurrency": self.max_concurrency.get(source, 1),
        }

    def _checked_sources(self, sources: list[str] | None) -> list[str]:
        """The sources of one call: those given, which may be any registered source and not only
        the ones this object was built with, else the configured ones."""
        chosen = list(dict.fromkeys(sources)) if sources else self.sources
        known = set(registry.available_sources())
        unknown = [s for s in chosen if s not in known]
        if unknown:
            raise ValueError(f"Unknown source(s) {unknown}. Available: {sorted(known)}")
        return chosen

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
        diagnostics: bool = False,
        **kwargs: Any,
    ) -> tuple[list[LiteratureResult], MergeReport]:
        """
        Search across all configured sources in parallel and deduplicate.

        Parameters
        ----------
        query : str
            The search string, translated into each source's dialect when
            ``translate`` is on.
        limit : int, optional
            Records per source (default: 25); the primary source gets
            ``limit × primary_limit_factor``.
        sort : str, optional
            One of the canonical tokens ``"relevance"``, ``"date"`` or
            ``"citations"`` (alias ``"citation_count"``), translated into each
            source's own sort vocabulary — Europe PMC receives
            ``"P_PDATE_D desc"`` for ``"date"``, PubMed ``"pub_date"``.  A
            source that cannot sort that way keeps its default order.  Any
            other value is passed through unchanged, so a source-native value
            still works when you search that source alone.
        sources : list[str], optional
            Restrict this one call to a subset of the configured sources.
        diagnostics : bool, optional
            Off by default, so the result keeps its shape.  When ``True``,
            ``report.metadata["source_status"]`` holds one record per queried
            source (``status`` is ``ok``, ``empty``, ``error``, ``rate_limited`` or
            ``unavailable``, with the record count, seconds, limit, the query and
            sort sent, and the error when there is one), and every merged record
            gets ``matched_sources``: the sources that returned that paper.

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
        sources = self._checked_sources(sources)
        clients = self._get_or_init_clients(sources)
        limits = self._limits_for(sources, limit)

        status: dict[str, dict[str, Any]] | None = {} if diagnostics else None
        per_source, source_times, source_errors = self._run_sources(
            clients,
            sources,
            query,
            limits,
            sort,
            translate=self.translate,
            status=status,
            **kwargs,
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
                effective_limits={s: self._limits_of(s) for s in sources},
            )
            if status is not None:
                report.metadata["source_status"] = status
            return [], report

        merger = LiteratureMerger(config=self._dedup_config())
        merged_dicts, report = merger.merge_results(all_results)
        report.metadata.update(
            source_times=source_times,
            source_errors=source_errors,
            sources_used=sources,
            source_counts=source_counts,
            effective_limits={s: self._limits_of(s) for s in sources},
        )

        merged = [LiteratureResult.model_validate(d) for d in merged_dicts if d is not None]
        self._annotate_provenance(merged, report, per_source)
        if status is not None:
            report.metadata["source_status"] = status
            self._annotate_matches(merged, per_source, sources)

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

        _keys = _record_keys
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

    @staticmethod
    def _annotate_matches(
        merged: list[LiteratureResult],
        per_source: dict[str, list[LiteratureResult]],
        order: list[str],
    ) -> None:
        """Set ``matched_sources`` on each merged record: every source that returned it, found
        by the DOI, PMID or title the records share, in the order the sources were asked."""
        index: dict[str, set[str]] = {}
        for name, records in per_source.items():
            for rec in records:
                for key in _record_keys(rec):
                    index.setdefault(key, set()).add(name)
        rank = {name: i for i, name in enumerate(order)}
        for rec in merged:
            found = {rec.source}
            for key in _record_keys(rec):
                found |= index.get(key, set())
            rec.matched_sources = sorted(found, key=lambda n: (rank.get(n, len(rank)), n))  # type: ignore[attr-defined]

    def search_all(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> tuple[dict[str, list[LiteratureResult]], dict[str, str]]:
        """Search every source in parallel **without** dedup.

        Returns ``(per_source_results, per_source_errors)``.
        """
        clients = self._get_or_init_clients(self.sources)
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
        status: dict[str, dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> tuple[dict[str, list[LiteratureResult]], dict[str, float], dict[str, str]]:
        """Fan out to the sources. ``status``, when given, is filled with one record per source."""
        active = [(s, clients.get(s)) for s in sources]
        runnable = [(s, c) for s, c in active if c is not None]
        sent: dict[str, dict[str, Any]] = {}
        if status is not None:
            for s, c in active:
                if c is None:
                    message = self._init_errors.get(s, "the client could not be created")
                    status[s] = {
                        "status": "unavailable",
                        "records": 0,
                        "seconds": None,
                        "limit": limits.get(s, 25),
                        "query": None,
                        "sort": None,
                        "error": {"type": "ClientUnavailable", "message": message},
                        "retry_after": None,
                        "rate_limit_delay": self.delay_for(s),
                        "max_concurrency": self.max_concurrency.get(s),
                        "waited_seconds": 0.0,
                    }

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
            send_sort, sort_value = _translate_sort(sort, source_name)
            sent[source_name] = {"query": q, "sort": sort_value if send_sort else None}
            pairs = [("sort", sort_value)] if send_sort else []
            for key, value in (*pairs, *kwargs.items()):
                if accepted is None or key in accepted:
                    call[key] = value
            gate = self._gate(source_name)
            queued = time.monotonic()
            with gate:
                sent[source_name]["waited"] = time.monotonic() - queued
                return self._search_checked(client, call)

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
                    if status is not None:
                        status[source_name] = self._status_row(
                            source_name, limits, sent, elapsed, len(results)
                        )
                    logger.info(
                        "Source '%s' returned %d results in %.2fs",
                        source_name,
                        len(results),
                        elapsed,
                    )
                except Exception as exc:  # noqa: BLE001 - report, don't abort the batch
                    source_errors[source_name] = f"{type(exc).__name__}: {exc}"
                    logger.error("Source '%s' failed: %s", source_name, exc)
                    if status is not None:
                        status[source_name] = self._status_row(
                            source_name, limits, sent, elapsed, 0, exc
                        )

        return per_source, source_times, source_errors

    def _status_row(
        self,
        source: str,
        limits: dict[str, int],
        sent: dict[str, dict[str, Any]],
        elapsed: float,
        records: int,
        exc: BaseException | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "status": "ok" if records else "empty",
            "records": records,
            "seconds": round(elapsed, 3),
            "limit": limits.get(source, 25),
            "query": sent.get(source, {}).get("query"),
            "sort": sent.get(source, {}).get("sort"),
            "error": None,
            "retry_after": None,
            "rate_limit_delay": self.delay_for(source),
            "max_concurrency": self.max_concurrency.get(source),
            "waited_seconds": round(sent.get(source, {}).get("waited", 0.0), 3),
        }
        if exc is not None:
            row.update(_failure(exc))
        return row

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _search_checked(client: Any, call: dict[str, Any]) -> list[LiteratureResult]:
        """Run ``client.search``. An empty answer that the client reached by swallowing an error
        (it records the error in ``last_error``) is raised, so it counts as a failure and is not
        mistaken for "no results"."""
        client.last_error = None
        results = list(client.search(**call))
        error = getattr(client, "last_error", None)
        if error is not None and not results:
            raise error
        return results

    def _gate(self, source: str) -> threading.BoundedSemaphore:
        """The concurrency gate of a source, made on first use for one named only in a call."""
        with self._init_lock:
            if source not in self._gates:
                self._gates[source] = threading.BoundedSemaphore(
                    self.max_concurrency.get(source, 1)
                )
            return self._gates[source]

    def _get_or_init_clients(self, sources: list[str] | None = None) -> dict[str, Any]:
        """The clients of ``sources`` (default: the configured ones), each created on first use.

        A source that cannot be created (a missing optional package, say) is kept as ``None``
        and its reason in ``_init_errors``, so it is reported rather than retried on every call.
        """
        with self._init_lock:
            if self._clients is None:
                self._clients = {}
            for source_name in sources or self.sources:
                if source_name not in self._clients:
                    self._clients[source_name] = self._create_client(source_name)
            return self._clients

    def _create_client(self, source_name: str) -> Any:
        spec = registry.get_source_spec(source_name)
        kwargs: dict[str, Any] = {
            "rate_limit_delay": self.delay_for(source_name),
            "timeout": self.timeout,
        }
        for cred in spec.credential_kwargs:
            if self.credentials.get(cred) is not None:
                kwargs[cred] = self.credentials[cred]
        try:
            return registry.load_source(source_name, **kwargs)
        except Exception as exc:  # noqa: BLE001 - missing dep / init failure
            logger.warning("Failed to init source '%s': %s", source_name, exc)
            self._init_errors[source_name] = f"{type(exc).__name__}: {exc}"
            return None

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
