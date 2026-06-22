"""
Function-level and block-level profiling using Python stdlib tools.

Provides deterministic profiling via ``cProfile`` and ``pstats`` for
measuring per-function call counts, cumulative time, and per-call overhead
across the full text parser pipeline.

No external dependencies — uses only the Python standard library.

Usage
-----
    >>> from pyeuropepmc.benchmark.profiler import ProfilerContext, profile_text

    >>> with ProfilerContext() as prof:
    ...     parser = FullTextXMLParser(xml_content)
    ...     metas = parser.extract_metadata()
    ...     sections = parser.get_full_text_sections_structured()

    >>> prof.print_stats(sort_by="cumulative", top_n=20)

    >>> # Higher-level convenience
    >>> result = profile_text(xml_content)
    >>> result["by_function"]["FullTextXMLParser.__init__"]["cumulative_s"]
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profiler Context Manager (preferred API)
# ---------------------------------------------------------------------------


class ProfilerContext:
    """
    Context manager wrapping ``cProfile`` with convenient stats access.

    Records all function calls within the context block and provides
    methods to inspect, filter, and sort the results.

    Parameters
    ----------
    builtins : bool, optional
        If True, include built-in function calls (default: False).

    Examples
    --------
    >>> from pyeuropepmc.benchmark.profiler import ProfilerContext
    >>> from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    >>> with ProfilerContext() as prof:
    ...     parser = FullTextXMLParser(xml_content)
    ...     _ = parser.extract_metadata()
    ...     _ = parser.get_full_text_sections_structured()

    >>> # Top 10 functions by cumulative time
    >>> prof.print_stats(sort_by="cumulative", top_n=10)

    >>> # Get raw stats dict
    >>> stats = prof.stats_dict()
    >>> print(stats["by_function"]["FullTextXMLParser.extract_metadata"])
    """

    def __init__(self, builtins: bool = False):
        self._profiler = cProfile.Profile(builtins=builtins)
        self._stats: pstats.Stats | None = None
        self._elapsed: float = 0.0

    def __enter__(self) -> ProfilerContext:
        self._profiler.enable()
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_args: Any) -> None:
        self._profiler.disable()
        self._elapsed = time.perf_counter() - self._start
        self._stats = pstats.Stats(self._profiler)
        self._stats.sort_stats("cumulative")

    # ------------------------------------------------------------------
    # Stats access
    # ------------------------------------------------------------------

    @property
    def elapsed(self) -> float:
        """Wall-clock seconds elapsed inside the context."""
        return self._elapsed

    @property
    def stats(self) -> pstats.Stats | None:
        """Raw ``pstats.Stats`` object (available after context exits)."""
        return self._stats

    def print_stats(
        self,
        sort_by: str = "cumulative",
        top_n: int = 20,
        strip_dirs: bool = True,
    ) -> str:
        """
        Return a formatted string of profiling stats.

        Parameters
        ----------
        sort_by : str, optional
            Sort key: ``"cumulative"``, ``"time"``, ``"calls"``, ``"ncalls"``,
            ``"pcalls"``, ``"filename"``, ``"module"``, ``"name"``, etc.
        top_n : int, optional
            Number of top functions to show (default: 20).
        strip_dirs : bool, optional
            Remove directory paths for readability (default: True).

        Returns
        -------
        str
            Formatted profiling output.
        """
        if self._stats is None:
            return "<no stats available — context was never entered>"

        # Re-create Stats from the raw profile to get a fresh display
        buf = io.StringIO()
        ps = pstats.Stats(self._profiler, stream=buf)
        if strip_dirs:
            ps.strip_dirs()
        ps.sort_stats(sort_by)
        ps.print_stats(top_n)

        output = buf.getvalue()
        print(output.rstrip())
        return output

    def stats_dict(self) -> dict[str, Any]:
        """
        Return profiling results as a structured dictionary.

        Returns
        -------
        dict with keys:
            ``elapsed_s`` — wall-clock seconds in context
            ``by_function`` — dict mapping
                ``{func_name: {ncalls, tottime, cumtime, percall_raw, percall_cum}}``
            ``total_calls`` — total number of function calls
            ``primitive_calls`` — number of primitive (non-recursive) calls
        """
        if self._stats is None:
            return {
                "elapsed_s": self._elapsed,
                "by_function": {},
                "total_calls": 0,
                "primitive_calls": 0,
            }

        out: dict[str, Any] = {
            "elapsed_s": round(self._elapsed, 4),
            "by_function": {},
            "total_calls": self._stats.total_calls,  # type: ignore[attr-defined]
            "primitive_calls": self._stats.prim_calls,  # type: ignore[attr-defined]
        }

        for func, (cc, nc, tt, ct, _callers) in self._stats.stats.items():  # type: ignore[attr-defined]
            filename, lineno, func_name = func
            per_call_raw = tt / nc if nc else 0.0
            per_call_cum = ct / cc if cc else 0.0
            out["by_function"][func_name] = {
                "filename": filename,
                "lineno": lineno,
                "ncalls": cc,
                "tottime_s": round(tt, 6),
                "cumtime_s": round(ct, 6),
                "percall_raw_s": round(per_call_raw, 6),
                "percall_cum_s": round(per_call_cum, 6),
            }

        return out

    def filter_by_module(self, module_prefix: str) -> dict[str, Any]:
        """
        Return stats dict filtered to functions from a specific module.

        Parameters
        ----------
        module_prefix : str
            Module name prefix (e.g. ``"pyeuropepmc"``, ``"xml.etree"``).

        Returns
        -------
        dict with ``by_function`` containing only matching functions.
        """
        full = self.stats_dict()
        filtered = {
            name: data
            for name, data in full["by_function"].items()
            if data["filename"].replace("\\", "/").startswith(module_prefix)
        }
        return {**full, "by_function": filtered}

    def total_time_by_module(self, module_prefix: str) -> float:
        """
        Sum cumulative time across all functions in a module.

        Parameters
        ----------
        module_prefix : str
            Module name prefix.

        Returns
        -------
        float
            Total cumulative seconds.
        """
        filtered = self.filter_by_module(module_prefix)
        return float(
            round(
                sum(f["cumtime_s"] for f in filtered["by_function"].values()),
                4,
            )
        )


# ---------------------------------------------------------------------------
# Convenience: profile_text — one-call profiling for a full XML string
# ---------------------------------------------------------------------------


def profile_text(xml_content: str) -> dict[str, Any]:
    """
    Profile an entire XML parsing pipeline for a single article.

    Parses ``xml_content`` and runs all major extraction methods, collecting
    per-function call counts and cumulative timing via ``cProfile``.

    Parameters
    ----------
    xml_content : str
        JATS/PMC XML content to parse and profile.

    Returns
    -------
    dict with keys:
        ``elapsed_s`` — total wall-clock seconds
        ``by_function`` — per-function call counts and timings
        ``parser_breakdown_s`` — cumulative seconds for each parser method
        ``total_calls`` — total function call count

    Examples
    --------
    >>> from pyeuropepmc.benchmark.profiler import profile_text
    >>> result = profile_text(xml_string)
    >>> result["parser_breakdown_s"]
    {'FullTextXMLParser.__init__': 0.042, 'extract_metadata': 0.015, ...}
    """
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    with ProfilerContext() as prof:
        parser = FullTextXMLParser(xml_content)
        _ = parser.extract_metadata()
        _ = parser.get_full_text_sections()
        _ = parser.get_full_text_sections_structured()
        _ = parser.extract_authors() if hasattr(parser, "extract_authors") else None
        _ = parser.extract_references() if hasattr(parser, "extract_references") else None
        _ = parser.extract_figures() if hasattr(parser, "extract_figures") else None
        _ = parser.extract_tables() if hasattr(parser, "extract_tables") else None

    stats = prof.stats_dict()

    # Extract parser-specific method times
    methods = [
        "FullTextXMLParser.__init__",
        "extract_metadata",
        "get_full_text_sections",
        "get_full_text_sections_structured",
        "extract_authors",
        "extract_references",
        "extract_figures",
        "extract_tables",
        "parse",
    ]
    breakdown: dict[str, float] = {}
    for method in methods:
        if method in stats["by_function"]:
            breakdown[method] = stats["by_function"][method]["cumtime_s"]

    return {
        "elapsed_s": stats["elapsed_s"],
        "by_function": stats["by_function"],
        "parser_breakdown_s": breakdown,
        "total_calls": stats["total_calls"],
        "primitive_calls": stats["primitive_calls"],
    }


# ---------------------------------------------------------------------------
# Micro-benchmark helpers
# ---------------------------------------------------------------------------


def time_function(func: Any, *args: Any, **kwargs: Any) -> dict[str, float]:
    """
    Time a single function call with wall-clock precision.

    Uses ``time.perf_counter`` for wall-clock measurement. Runs the function
    once (not averaged). For micro-benchmarks, use ``timeit`` instead.

    Parameters
    ----------
    func : callable
        Function to time.
    *args, **kwargs
        Arguments passed to the function.

    Returns
    -------
    dict with ``seconds`` (wall-clock) and ``result`` (function return value).
    """
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return {"seconds": round(elapsed, 6), "result": result}


def time_et_parse(xml_content: str) -> dict[str, Any]:
    """
    Time just the ElementTree parse step in isolation.

    Useful for comparing raw XML parse overhead vs full pipeline.

    Parameters
    ----------
    xml_content : str
        XML content to parse.

    Returns
    -------
    dict with ``seconds`` and ``root`` (parsed element).
    """
    return time_function(ET.fromstring, xml_content)
