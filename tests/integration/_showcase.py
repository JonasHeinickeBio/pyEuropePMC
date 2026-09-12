"""Shared helpers for the 50-example real-world showcase tests.

These tests hit live APIs, so they only run under ``--run-integration``. Each
one exercises 50 real inputs, collects metrics, prints a table to stdout
(use ``-s`` to see it live) and writes a Markdown + JSON report under
``tests/integration/showcase_reports/`` (git-ignored).
"""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
import statistics
import time
from typing import Any

REPORT_DIR = Path(__file__).parent / "showcase_reports"


class Timer:
    """Context-manager stopwatch."""

    def __enter__(self) -> Timer:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed = time.perf_counter() - self._t0


def pct(part: float, whole: float) -> float:
    return 100.0 * part / whole if whole else 0.0


def _fmt_hist(hist: dict[str, int], total: int) -> list[str]:
    rows = []
    for key, count in sorted(hist.items(), key=lambda kv: -kv[1]):
        bar = "█" * round(30 * count / max(total, 1))
        rows.append(f"  {key:<24} {count:>4}  {pct(count, total):5.1f}%  {bar}")
    return rows


def write_report(
    name: str,
    *,
    headline: dict[str, Any],
    per_item: list[dict[str, Any]],
    sections: dict[str, list[str]] | None = None,
) -> str:
    """Persist + return a Markdown report; also prints it."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [f"# Showcase — {name}", ""]
    lines.append("## Headline")
    for k, v in headline.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    for title, body in (sections or {}).items():
        lines.append(f"## {title}")
        lines.extend(body)
        lines.append("")
    lines.append("## Per-item")
    if per_item:
        cols = list(per_item[0].keys())
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for row in per_item:
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    text = "\n".join(lines)

    (REPORT_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    (REPORT_DIR / f"{name}.json").write_text(
        json.dumps({"headline": headline, "per_item": per_item}, indent=2, default=str),
        encoding="utf-8",
    )
    print("\n" + text)
    return text


def summary_stats(values: Iterable[float]) -> dict[str, float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": len(vals),
        "mean": round(statistics.mean(vals), 3),
        "median": round(statistics.median(vals), 3),
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
    }
