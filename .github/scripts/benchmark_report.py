#!/usr/bin/env python3
"""Summarise a modular benchmark run, track history and refresh the README.

Reads ``MODULAR_BENCHMARK_RESULTS.json`` as written by
``tests/benchmark_article_client.py::test_modular_benchmark_system`` and:

* derives headline metrics from the keys that file actually contains,
* compares them against ``.github/benchmark-history.json`` and reports drift,
* appends the run to that history (most recent ``HISTORY_LIMIT`` kept),
* rewrites the "Performance" section of ``README.md``,
* writes a summary to ``$GITHUB_STEP_SUMMARY`` when running in Actions.

Lives outside the workflow YAML so it can be read, linted and run by hand:

    python .github/scripts/benchmark_report.py --results MODULAR_BENCHMARK_RESULTS.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

README_START = "<!-- BENCHMARK-RESULTS:START -->"
README_END = "<!-- BENCHMARK-RESULTS:END -->"
HISTORY_LIMIT = 10
REGRESSION_FACTOR = 1.20  # >20% slower than the previous run
IMPROVEMENT_FACTOR = 0.90  # >10% faster than the previous run


def compute_metrics(results: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw results document to the handful of numbers we track.

    The keys read here (``aggregates.mean``, ``total_requests``, ``errors`` and
    the ``summary`` counters) are the ones the benchmark actually writes. An
    earlier version of this report read ``summary.average_time``,
    ``summary.success_rate`` and ``summary.total_requests``, none of which exist
    - so every metric it published was silently zero.
    """
    means: list[float] = []
    total_requests = 0
    entries = 0
    failed_entries = 0

    for method_results in results.get("results", {}).values():
        for entry in method_results:
            entries += 1
            if entry.get("errors"):
                failed_entries += 1
            total_requests += int(entry.get("total_requests") or 0)
            mean = (entry.get("aggregates") or {}).get("mean")
            if isinstance(mean, (int, float)) and mean > 0:
                means.append(float(mean))

    summary = results.get("summary", {})
    successful = summary.get("successful_runs")
    total_methods = summary.get("total_methods")
    if isinstance(successful, int) and isinstance(total_methods, int) and total_methods:
        success_rate = successful / total_methods * 100
    elif entries:
        success_rate = (entries - failed_entries) / entries * 100
    else:
        success_rate = 0.0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite_name": results.get("suite_name", "unknown"),
        "mean_time": statistics.mean(means) if means else 0.0,
        "p95_time": max(means) if means else 0.0,
        "total_requests": total_requests,
        "success_rate": success_rate,
        "measured_methods": entries,
        "failed_methods": failed_entries,
    }


def compare(current: dict[str, Any], previous: dict[str, Any] | None) -> list[str]:
    """Human-readable comparison lines against the previous run."""
    if not previous:
        return ["No previous run on record - this run becomes the baseline."]

    lines = [
        f"Previous mean time: {previous.get('mean_time', 0):.3f}s "
        f"(success {previous.get('success_rate', 0):.1f}%)"
    ]
    before = previous.get("mean_time") or 0.0
    now = current["mean_time"]
    if not before or not now:
        lines.append("Not enough timing data to compare.")
    elif now > before * REGRESSION_FACTOR:
        lines.append(f"REGRESSION: {((now / before) - 1) * 100:.1f}% slower than the previous run.")
    elif now < before * IMPROVEMENT_FACTOR:
        lines.append(f"Improvement: {(1 - (now / before)) * 100:.1f}% faster than the previous run.")
    else:
        lines.append("Performance stable (within +20% / -10% of the previous run).")
    return lines


def render_readme_section(metrics: dict[str, Any], report: str | None) -> str:
    """The Markdown block injected into README.md."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = [
        "## 📊 Performance",
        "",
        f"> Last updated: {today}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Benchmarked methods** | {metrics['measured_methods']:,} |",
        f"| **Total requests** | {metrics['total_requests']:,} |",
        f"| **Mean call time** | {metrics['mean_time']:.3f}s |",
        f"| **Success rate** | {metrics['success_rate']:.1f}% |",
        "",
    ]
    if report:
        block += [
            "<details>",
            "<summary>📈 View full benchmark report</summary>",
            "",
            report.strip(),
            "",
            "</details>",
            "",
        ]
    return "\n".join(block)


def update_readme(readme_path: Path, section: str) -> bool:
    """Replace the marker-delimited Performance block. Returns True if changed.

    The block is delimited by HTML comments rather than located by matching the
    heading up to "the next ``##``". The embedded benchmark report contains its
    own ``##`` headings, so a heading-based regex stops inside the block: it
    would replace only the first few lines and leave the rest of the previous
    run orphaned in the README, accumulating on every run. Markers also keep the
    hand-written "## 📊 Parser Quality Benchmark" section safe from a near-miss
    heading match.
    """
    if not readme_path.exists():
        return False

    original = readme_path.read_text(encoding="utf-8")
    block = f"{README_START}\n{section.rstrip()}\n{README_END}"

    if README_START in original and README_END in original:
        head, _, rest = original.partition(README_START)
        _, _, tail = rest.partition(README_END)
        updated = head + block + tail
    else:
        contributing = re.compile(r"^## 🤝 Contributing\b", re.MULTILINE)
        if contributing.search(original):
            updated = contributing.sub(block + "\n\n## 🤝 Contributing", original, count=1)
        else:
            updated = original.rstrip() + "\n\n" + block + "\n"

    if updated == original:
        return False
    readme_path.write_text(updated, encoding="utf-8")
    return True


def write_step_summary(lines: list[str]) -> None:
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("MODULAR_BENCHMARK_RESULTS.json"))
    parser.add_argument("--report", type=Path, default=Path("MODULAR_PERFORMANCE_REPORT.md"))
    parser.add_argument("--history", type=Path, default=Path(".github/benchmark-history.json"))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument(
        "--skip-readme",
        action="store_true",
        help="Compute and record metrics without touching README.md.",
    )
    args = parser.parse_args(argv)

    if not args.results.exists():
        # Hard failure on purpose. The previous version exited 0 here, so a
        # benchmark run that collected no tests at all looked like a success.
        print(f"ERROR: {args.results} not found - the benchmark did not produce results.", file=sys.stderr)
        return 1

    results = json.loads(args.results.read_text(encoding="utf-8"))
    metrics = compute_metrics(results)

    history: list[dict[str, Any]] = []
    if args.history.exists():
        try:
            history = json.loads(args.history.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"WARNING: {args.history} is not valid JSON; starting a new history.", file=sys.stderr)
            history = []

    comparison = compare(metrics, history[-1] if history else None)

    summary_lines = [
        "## Benchmark results",
        "",
        f"- Benchmarked methods: **{metrics['measured_methods']}** "
        f"({metrics['failed_methods']} with errors)",
        f"- Mean call time: **{metrics['mean_time']:.3f}s**",
        f"- Slowest method mean: **{metrics['p95_time']:.3f}s**",
        f"- Total requests: **{metrics['total_requests']:,}**",
        f"- Success rate: **{metrics['success_rate']:.1f}%**",
        "",
        "### Comparison",
        "",
        *[f"- {line}" for line in comparison],
        "",
    ]
    print("\n".join(summary_lines))
    write_step_summary(summary_lines)

    history.append(metrics)
    history = history[-HISTORY_LIMIT:]
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print(f"Benchmark history updated ({len(history)} runs stored).")

    if not args.skip_readme:
        report_text = args.report.read_text(encoding="utf-8") if args.report.exists() else None
        if update_readme(args.readme, render_readme_section(metrics, report_text)):
            print(f"{args.readme} performance section updated.")
        else:
            print(f"{args.readme} unchanged.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
