"""
Standardized benchmark reporting, aggregation, and serialization.

Produces per-dataset, per-article, and aggregate metric reports in a
structured JSON format suitable for comparing parser versions and datasets.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BenchmarkReport:
    """
    Accumulate and serialize benchmark metrics across articles and datasets.

    Parameters
    ----------
    title : str, optional
        Report title (e.g. ``"pyEuropePMC v0.2.0 Benchmark"``).

    Examples
    --------
    >>> report = BenchmarkReport(title="v0.2.0 Regression Check")
    >>> report.add_article_result("PMC_sample_1943", "PMC1234567", metrics)
    >>> report.add_dataset_summary("PMC_sample_1943", {"avg_score": 0.92})
    >>> report.save_json("benchmark_results.json")
    """

    def __init__(self, title: str = "pyEuropePMC Benchmark Report"):
        self.title = title
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.article_results: list[dict[str, Any]] = []
        self.dataset_summaries: dict[str, dict[str, Any]] = {}
        self.metadata: dict[str, Any] = {}

    def add_article_result(
        self,
        dataset_name: str,
        article_label: str,
        metrics: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record metric results for a single article.

        Parameters
        ----------
        dataset_name : str
            Dataset this article belongs to.
        article_label : str
            Article identifier (filename, PMCID, etc.).
        metrics : dict
            Output from :func:`compute_all_metrics`.
        metadata : dict, optional
            Extra data (file size, parse time, etc.).
        """
        entry: dict[str, Any] = {
            "dataset": dataset_name,
            "article": article_label,
            "metrics": metrics,
        }
        if metadata:
            entry["metadata"] = metadata
        self.article_results.append(entry)

    def add_dataset_summary(
        self,
        dataset_name: str,
        summary: dict[str, Any],
    ) -> None:
        """
        Record aggregated summary for a dataset.

        Parameters
        ----------
        dataset_name : str
            Dataset identifier.
        summary : dict
            Aggregated metrics (mean, median, std, etc.).
        """
        self.dataset_summaries[dataset_name] = summary

    def set_metadata(self, **kwargs: Any) -> None:
        """Set report-level metadata (parser version, config, etc.)."""
        self.metadata.update(kwargs)

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    def aggregate_by_dataset(self) -> dict[str, dict[str, Any]]:
        """
        Compute aggregate statistics per dataset.

        Returns
        -------
        dict mapping dataset name → {score_name: {mean, median, min, max, std}}
        """
        by_dataset: dict[str, dict[str, list[float]]] = {}

        for entry in self.article_results:
            ds = entry["dataset"]
            if ds not in by_dataset:
                by_dataset[ds] = {}
            metrics = entry.get("metrics", {})
            for metric_key, score in metrics.get("per_metric", {}).items():
                if metric_key not in by_dataset[ds]:
                    by_dataset[ds][metric_key] = []
                by_dataset[ds][metric_key].append(score)

        aggregated: dict[str, dict[str, Any]] = {}
        for ds, metric_values in by_dataset.items():
            ds_agg: dict[str, Any] = {}
            for metric_name, values in metric_values.items():
                ds_agg[metric_name] = _summarize_values(values)
            # Composite from means
            metric_means = [v.get("mean", 0.0) for v in ds_agg.values()]
            ds_agg["composite_score"] = {
                "mean": round(sum(metric_means) / max(len(metric_means), 1), 4),
            }
            ds_agg["article_count"] = len(self._articles_for_dataset(ds))
            aggregated[ds] = ds_agg

        return aggregated

    def aggregate_overall(self) -> dict[str, Any]:
        """
        Compute overall aggregate across all articles.

        Returns
        -------
        dict with metric means and composite.
        """
        all_metric_lists: dict[str, list[float]] = {}

        for entry in self.article_results:
            for metric_key, score in entry.get("metrics", {}).get("per_metric", {}).items():
                if metric_key not in all_metric_lists:
                    all_metric_lists[metric_key] = []
                all_metric_lists[metric_key].append(score)

        overall: dict[str, Any] = {}
        for metric_name, values in all_metric_lists.items():
            overall[metric_name] = _summarize_values(values)

        if overall:
            mean_scores = [v["mean"] for v in overall.values()]
            overall["composite_score"] = {
                "mean": round(sum(mean_scores) / max(len(mean_scores), 1), 4),
            }

        overall["total_articles"] = len(self.article_results)
        return overall

    def _articles_for_dataset(self, dataset_name: str) -> list[dict[str, Any]]:
        """Return all entries for a given dataset."""
        return [e for e in self.article_results if e["dataset"] == dataset_name]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize entire report to a plain dict."""
        return {
            "title": self.title,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "dataset_summaries": self.dataset_summaries,
            "aggregate_by_dataset": self.aggregate_by_dataset(),
            "aggregate_overall": self.aggregate_overall(),
            "article_results": self.article_results,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save_json(self, path: str | Path, indent: int = 2) -> Path:
        """
        Save report to a JSON file.

        Parameters
        ----------
        path : str or Path
            Output file path.
        indent : int
            JSON indentation level.

        Returns
        -------
        Path
            The path the report was saved to.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json(indent=indent))
        logger.info("Benchmark report saved to %s", path)
        return path

    @classmethod
    def load_json(cls, path: str | Path) -> BenchmarkReport:
        """
        Load a report from a JSON file.

        Parameters
        ----------
        path : str or Path
            Path to saved JSON report.

        Returns
        -------
        BenchmarkReport
            Restored report instance.
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        report = cls(title=data.get("title", "Loaded Report"))
        report.created_at = data.get("created_at", report.created_at)
        report.metadata = data.get("metadata", {})
        report.dataset_summaries = data.get("dataset_summaries", {})
        report.article_results = data.get("article_results", [])
        return report

    # ------------------------------------------------------------------
    # Console output
    # ------------------------------------------------------------------

    def print_summary(self, include_articles: bool = False) -> None:
        """Print a human-readable report summary to stdout."""
        overall = self.aggregate_overall()
        by_dataset = self.aggregate_by_dataset()

        print(f"\n{'=' * 60}")
        print(f"  {self.title}")
        print(f"  Generated: {self.created_at}")
        print(f"{'=' * 60}")

        print(f"\n  Overall ({overall.get('total_articles', 0)} articles):")
        for metric_key in (
            "element_coverage",
            "text_fidelity",
            "section_accuracy",
            "inline_recall",
            "metadata_accuracy",
        ):
            values = overall.get(metric_key, {})
            mean = values.get("mean", "N/A")
            print(f"    {metric_key:25s}  mean = {mean}")

        if "composite_score" in overall:
            print(f"    {'composite_score':25s}  mean = {overall['composite_score']['mean']}")

        if by_dataset:
            print("\n  Per dataset:")
            for ds_name, ds_agg in sorted(by_dataset.items()):
                comp = ds_agg.get("composite_score", {})
                count = ds_agg.get("article_count", "?")
                print(
                    f"    {ds_name:25s}  composite = {comp.get('mean', 'N/A'):<8}  "
                    f"({count} articles)"
                )

        if include_articles and self.article_results:
            print("\n  Per article (top 5):")
            for entry in self.article_results[:5]:
                comp = entry.get("metrics", {}).get("composite_score", "N/A")
                print(f"    {entry['article']:30s}  composite = {comp}")


def _summarize_values(values: list[float]) -> dict[str, float]:
    """Compute summary statistics for a list of floats."""
    if not values:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "std": 0.0, "count": 0}

    n = len(values)
    sorted_vals = sorted(values)
    mean = sum(values) / n
    median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]
    variance = sum((v - mean) ** 2 for v in values) / n
    std = variance**0.5

    return {
        "mean": round(mean, 4),
        "median": round(median, 4),
        "min": round(min_val, 4),
        "max": round(max_val, 4),
        "std": round(std, 4),
        "count": n,
    }
