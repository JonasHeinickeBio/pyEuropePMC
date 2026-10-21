"""Time the ``enrich_paper`` MCP tool against the live services.

Every source alone, all sources together, and all sources with ROR details, for a few
papers, several times each, one call at a time. Prints a table of medians and ranges.

    python benchmarks/benchmark_enrich_paper.py            # 3 papers x 3 repeats, ~5 minutes
    python benchmarks/benchmark_enrich_paper.py --repeats 5 --budget 60

Needs network access and no credentials. The numbers depend on the machine, the network
and the day: Europe PMC, Crossref, OpenAlex, Semantic Scholar, iCite and ROR are public
services. The results in ``docs/features/mcp-server.md`` come from this script.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
import logging
import statistics
import time
from typing import Any

PAPERS: dict[str, dict[str, str]] = {
    "retracted-1998 (PMID 9500320, 24 authors)": {"pmid": "9500320"},
    "deep-learning-2015 (DOI, 3 authors)": {"doi": "10.1038/nature14539"},
    "yeast-2012 (PMC3257301, open access)": {"pmcid": "PMC3257301"},
}

#: label, kind ("library": PaperEnricher directly, "tool": the MCP tool), arguments
CONFIGS: list[tuple[str, str, dict[str, Any]]] = [
    ("europepmc only", "library", {"only_sources": ["europepmc"]}),
    ("+ crossref", "tool", {"sources": ["crossref"]}),
    ("+ openalex", "tool", {"sources": ["openalex"]}),
    ("+ semantic_scholar", "tool", {"sources": ["semantic_scholar"]}),
    ("+ icite", "tool", {"sources": ["icite"]}),
    ("all sources", "tool", {}),
    ("all sources + ROR details", "tool", {"ror_details": True}),
]


def _spread(values: list[float]) -> str:
    return f"{statistics.median(values):.1f} ({min(values):.1f}-{max(values):.1f})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--budget", type=float, default=120, help="time_budget per call")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)

    from pyeuropepmc.mcp import server as srv

    walls: dict[str, list[float]] = defaultdict(list)
    sizes: dict[str, list[float]] = defaultdict(list)
    own: dict[str, list[float]] = defaultdict(list)
    problems: dict[str, int] = defaultdict(int)

    for ident in PAPERS.values():
        for label, kind, extra in CONFIGS:
            for _ in range(args.repeats):
                started = time.perf_counter()
                if kind == "tool":
                    result = asyncio.run(
                        srv.enrich_paper(**ident, time_budget=args.budget, **extra)
                    )
                    report, size = result["sources"], len(str(result))
                else:
                    enricher = srv._enricher_cache.get()
                    value = next(iter(ident.values()))
                    result = enricher.enrich_paper(value, time_budget=args.budget, **extra)
                    report, size = result["source_status"], len(str(result.get("merged")))
                walls[label].append(time.perf_counter() - started)
                sizes[label].append(size)
                for name, entry in report.items():
                    if entry.get("seconds") is not None and entry["status"] in ("ok", "empty"):
                        own[name].append(entry["seconds"])
                    elif entry["status"] in ("error", "timeout"):
                        problems[f"{label}: {name} {entry['status']}"] += 1

    print(f"{'configuration':28} {'call, seconds: median (min-max)':34} bytes")
    for label, _, _ in CONFIGS:
        print(f"{label:28} {_spread(walls[label]):34} {statistics.median(sizes[label]):.0f}")
    print("\nTime of each source inside the calls above (seconds, median (min-max)):")
    for name in sorted(own):
        print(f"  {name:18} {_spread(own[name])}")
    if problems:
        print("\nSources that failed or timed out:")
        for key, count in sorted(problems.items()):
            print(f"  {count}x {key}")


if __name__ == "__main__":
    main()
