"""
Memory profiling for XML parsing pipelines using ``tracemalloc``.

Provides context managers and convenience functions to track peak memory,
per-snapshot allocations, and per-function memory impact during parsing.

Uses only the Python standard library (``tracemalloc`` since 3.4).

Usage
-----
    >>> from pyeuropepmc.benchmark.memory import MemoryTracker

    >>> tracker = MemoryTracker()
    >>> tracker.start()
    >>> parser = FullTextXMLParser(xml_content)
    >>> _ = parser.get_full_text_sections_structured()
    >>> snapshot = tracker.stop()

    >>> print(snapshot["peak_mib"])
    >>> print(snapshot["allocated_mib"])
    >>> print(snapshot["top_allocations"])
"""

from __future__ import annotations

import logging
import tracemalloc
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Memory Tracker
# ---------------------------------------------------------------------------


class MemoryTracker:
    """
    Track peak memory and allocation patterns using ``tracemalloc``.

    Provides ``start()`` / ``stop()`` / ``snapshot()`` API for measuring
    memory usage of specific code blocks.

    Uses snapshot comparison (``compare_to``) to measure allocations that
    occurred only within the tracked block, not cumulative across the
    entire process lifetime.

    Parameters
    ----------
    nframe : int, optional
        Number of stack frames to trace (default: 3). Higher values give
        more precise location info but use more memory.

    Examples
    --------
    >>> from pyeuropepmc.benchmark.memory import MemoryTracker
    >>> from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    >>> tracker = MemoryTracker()
    >>> tracker.start()
    >>> parser = FullTextXMLParser(xml_content)
    >>> _ = parser.get_full_text_sections_structured()
    >>> snapshot = tracker.stop()

    >>> print(f"Peak: {snapshot['peak_mib']:.2f} MiB")
    >>> for alloc in snapshot["top_allocations"][:5]:
    ...     print(f"  {alloc['size_kib']:>8.1f} KiB  {alloc['trace']}")
    """

    def __init__(self, nframe: int = 3):
        self._nframe = nframe
        self._snapshot1: tracemalloc.Snapshot | None = None
        self._snapshot2: tracemalloc.Snapshot | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start memory tracing. Call before the code block to profile."""
        if not tracemalloc.is_tracing():
            tracemalloc.start(self._nframe)
        self._snapshot1 = tracemalloc.take_snapshot()
        self._running = True

    def stop(self) -> dict[str, Any]:
        """
        Stop tracing and return memory snapshot.

        Returns
        -------
        dict with keys:
            ``peak_mib`` — peak memory in MiB
            ``current_mib`` — current memory in MiB
            ``allocated_mib`` — total allocated since start in MiB
            ``freed_mib`` — total freed since start in MiB
            ``top_allocations`` — list of ``{size_kib, count, trace}`` dicts
            ``by_module`` — dict mapping ``{module: total_kib}``
        """
        if not self._running:
            return {
                "peak_mib": 0.0,
                "current_mib": 0.0,
                "allocated_mib": 0.0,
                "freed_mib": 0.0,
                "top_allocations": [],
                "by_module": {},
            }

        self._snapshot2 = tracemalloc.take_snapshot()
        self._running = False

        # Get current/peak from get_traced_memory (cumulative since start)
        current_peak: tuple[int, int] = (0, 0)
        if hasattr(tracemalloc, "get_traced_memory"):
            current_peak = tracemalloc.get_traced_memory()

        # Compute diff between snapshots to measure allocations within this block
        stats = (
            self._snapshot2.compare_to(self._snapshot1, "lineno")
            if self._snapshot1 is not None
            else []
        )

        top_allocs: list[dict[str, Any]] = []
        module_sizes: dict[str, float] = {}

        for stat in stats[:30]:
            size_kib = stat.size_diff / 1024
            count = stat.count_diff
            frame = stat.traceback[0]
            func_name = getattr(frame, "function", getattr(frame, "func_name", ""))
            trace_str = f"{frame.filename}:{frame.lineno} in {func_name}"

            top_allocs.append(
                {
                    "size_kib": round(size_kib, 1),
                    "count": count,
                    "filename": frame.filename,
                    "lineno": frame.lineno,
                    "function": func_name,
                    "trace": trace_str,
                }
            )

            # Aggregate by module (only positive allocations)
            module = _module_from_filename(frame.filename)
            module_sizes[module] = module_sizes.get(module, 0.0) + max(size_kib, 0.0)

        current_bytes, peak_bytes = current_peak

        result: dict[str, Any] = {
            "peak_mib": round(peak_bytes / (1024 * 1024), 4),
            "current_mib": round(current_bytes / (1024 * 1024), 4),
            "allocated_mib": round(peak_bytes / (1024 * 1024), 4),
            "top_allocations": top_allocs,
            "by_module": {
                mod: round(kib, 1)
                for mod, kib in sorted(module_sizes.items(), key=lambda x: -x[1])
            },
        }

        tracemalloc.stop()
        return result

    def snapshot(self) -> dict[str, Any]:
        """
        Take an intermediate snapshot without stopping the tracker.

        Useful for before/after comparisons within a running trace.

        Returns
        -------
        dict with ``current_mib``, ``peak_mib``, ``top_allocations``.
        """
        if not tracemalloc.is_tracing():
            return {"current_mib": 0.0, "peak_mib": 0.0, "top_allocations": []}

        current, peak = tracemalloc.get_traced_memory()

        return {
            "current_mib": round(current / (1024 * 1024), 4),
            "peak_mib": round(peak / (1024 * 1024), 4),
        }

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> MemoryTracker:
        self.start()
        return self

    def __exit__(self, *exc_args: Any) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def profile_memory(xml_content: str) -> dict[str, Any]:
    """
    Profile memory usage of a full XML parsing pipeline.

    Parses ``xml_content`` and runs all major extraction methods while
    tracking memory allocations via ``tracemalloc``.

    Parameters
    ----------
    xml_content : str
        JATS/PMC XML content.

    Returns
    -------
    dict with keys: ``peak_mib``, ``current_mib``, ``allocated_mib``,
    ``freed_mib``, ``top_allocations``, ``by_module``.

    Examples
    --------
    >>> from pyeuropepmc.benchmark.memory import profile_memory
    >>> mem = profile_memory(xml_string)
    >>> print(f"Peak memory: {mem['peak_mib']:.2f} MiB")
    >>> print(f"Top modules: {list(mem['by_module'].keys())[:5]}")
    """
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    tracker = MemoryTracker()
    tracker.start()
    parser = FullTextXMLParser(xml_content)
    _ = parser.extract_metadata()
    _ = parser.get_full_text_sections()
    _ = parser.get_full_text_sections_structured()
    _ = parser.extract_authors() if hasattr(parser, "extract_authors") else None
    _ = parser.extract_references() if hasattr(parser, "extract_references") else None
    return tracker.stop()


def profile_memory_blocks(xml_content: str) -> dict[str, Any]:
    """
    Profile memory usage of the content blocks extraction specifically.

    Focuses on the ``get_full_text_sections_structured()`` call which
    builds ``ContentBlock`` objects from the parsed XML tree.

    Parameters
    ----------
    xml_content : str
        JATS/PMC XML content.

    Returns
    -------
    dict with memory snapshot after block extraction.
    """
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    parser = FullTextXMLParser(xml_content)

    tracker = MemoryTracker()
    tracker.start()
    _ = parser.get_full_text_sections_structured()
    return tracker.stop()


def profile_memory_fulltext(xml_content: str) -> dict[str, float]:
    """
    Measure memory for full-text flat sections with minimal allocation tracking.

    Lighter-weight than :func:`profile_memory` — uses tracemalloc snapshots
    but with fewer frames and no top-allocations detail.

    Parameters
    ----------
    xml_content : str
        JATS/PMC XML content.

    Returns
    -------
    dict with ``peak_mib``, ``current_mib``.
    """
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    parser = FullTextXMLParser(xml_content)

    tracker = MemoryTracker(nframe=1)
    tracker.start()
    _ = parser.get_full_text_sections()
    result = tracker.stop()
    return {
        "peak_mib": result["peak_mib"],
        "current_mib": result["current_mib"],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _module_from_filename(filename: str) -> str:
    """Extract a short module name from a file path."""
    # Normalize path separators
    fname = filename.replace("\\", "/")

    # Try site-packages
    if "site-packages/" in fname:
        parts = fname.split("site-packages/")[-1].split("/")
        return parts[0] if parts else fname

    # Try src/
    if "src/" in fname:
        parts = fname.split("src/")[-1].split("/")
        return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]

    # Python stdlib
    if fname.startswith("/usr/lib/python") or "python3." in fname:
        return "stdlib"

    return fname.split("/")[-1] if "/" in fname else fname
