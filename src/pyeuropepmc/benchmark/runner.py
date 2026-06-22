"""
Benchmark orchestrator — ties together datasets, metrics, reports, and profiling.

The :class:`BenchmarkRunner` loads a dataset, parses each article, runs all
metrics, optionally profiles function-level timing and memory usage, and
accumulates results into a :class:`BenchmarkReport`.
"""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any

from pyeuropepmc.benchmark.dataset import BenchmarkDataset
from pyeuropepmc.benchmark.memory import MemoryTracker
from pyeuropepmc.benchmark.metrics import compute_all_metrics
from pyeuropepmc.benchmark.profiler import ProfilerContext
from pyeuropepmc.benchmark.report import BenchmarkReport
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Orchestrate benchmark evaluation across datasets.

    Parameters
    ----------
    dataset : BenchmarkDataset or list of BenchmarkDataset
        Dataset(s) to evaluate.
    limit : int, optional
        Limit number of articles processed per dataset (for quick testing).
    config : ElementPatterns, optional
        Custom parser configuration.
    report_title : str, optional
        Title for the generated report.
    skip_errors : bool, default True
        If True, skip articles that fail to parse instead of aborting.

    Examples
    --------
    >>> from pyeuropepmc.benchmark import BenchmarkDataset, BenchmarkRunner

    >>> dataset = BenchmarkDataset("local", local_path="./my_xmls")
    >>> runner = BenchmarkRunner(dataset)
    >>> report = runner.run_all()
    >>> print(report.aggregate_overall())
    """

    def __init__(
        self,
        dataset: BenchmarkDataset | list[BenchmarkDataset],
        limit: int | None = None,
        config: Any = None,
        report_title: str | None = None,
        skip_errors: bool = True,
        profile: bool = False,
        profile_memory: bool = False,
        profile_top_n: int = 20,
    ):
        if isinstance(dataset, BenchmarkDataset):
            self.datasets = [dataset]
        else:
            self.datasets = dataset
        self.limit = limit
        self.config = config
        self.report_title = report_title or "pyEuropePMC Benchmark Report"
        self.skip_errors = skip_errors
        self.profile = profile
        self.profile_memory = profile_memory
        self.profile_top_n = profile_top_n
        self._stats: dict[str, Any] = {
            "total_articles": 0,
            "successful": 0,
            "failed": 0,
            "total_parse_time_s": 0.0,
            "parse_errors": [],
        }

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run_all(self) -> BenchmarkReport:
        """
        Process all articles in all datasets and return a compiled report.

        Returns
        -------
        BenchmarkReport
            Report with per-article and per-dataset aggregations.
        """
        report = BenchmarkReport(title=self.report_title)
        # Record metadata
        import pyeuropepmc

        report.set_metadata(
            parser_version=getattr(pyeuropepmc, "__version__", "unknown"),
            limit=self.limit,
            skip_errors=self.skip_errors,
        )

        for dataset in self.datasets:
            logger.info("Processing dataset: %s", dataset.name)
            ds_articles = 0
            ds_parse_times: list[float] = []

            for article_path in dataset.iter_articles():
                if self.limit is not None and ds_articles >= self.limit:
                    break

                self._stats["total_articles"] += 1
                ds_articles += 1
                article_label = article_path.stem

                logger.debug(
                    "Processing %s (%d/%d)", article_label, ds_articles, self.limit or float("inf")
                )

                result = self._process_single_article(article_path)
                if result is None:
                    continue

                metrics, parse_time, article_meta = result
                ds_parse_times.append(parse_time)
                report.add_article_result(
                    dataset_name=dataset.name,
                    article_label=article_label,
                    metrics=metrics,
                    metadata=article_meta,
                )

            # Per-dataset summary
            ds_agg = report.aggregate_by_dataset().get(dataset.name, {})
            if ds_parse_times:
                ds_agg["parse_time_seconds"] = {
                    "mean": round(sum(ds_parse_times) / len(ds_parse_times), 3),
                    "min": round(min(ds_parse_times), 3),
                    "max": round(max(ds_parse_times), 3),
                }
            ds_agg["article_count"] = ds_articles
            ds_agg["dataset_info"] = dataset.to_dict()
            report.add_dataset_summary(dataset.name, ds_agg)

            logger.info(
                "Dataset %s: %d articles processed (%.1f s/article)",
                dataset.name,
                ds_articles,
                sum(ds_parse_times) / max(len(ds_parse_times), 1),
            )

        # Overall summary
        overall = report.aggregate_overall()
        overall["parse_time"] = {
            "total_s": round(self._stats["total_parse_time_s"], 2),
            "successful": self._stats["successful"],
            "failed": self._stats["failed"],
        }
        report.set_metadata(stats=self._stats)

        logger.info(
            "Benchmark complete: %d/%d successful (%d errors)",
            self._stats["successful"],
            self._stats["total_articles"],
            self._stats["failed"],
        )

        return report

    def _process_single_article(
        self,
        article_path: Path,
    ) -> tuple[dict[str, Any], float, dict[str, Any]] | None:
        """Parse one article and compute all metrics, with optional profiling."""
        try:
            with open(article_path, encoding="utf-8") as f:
                xml_content = f.read()
        except Exception as e:
            logger.error("  Read error for %s: %s", article_path.name, e)
            self._stats["failed"] += 1
            self._stats["parse_errors"].append(
                {"article": article_path.name, "error": f"read: {e}"}
            )
            return None

        # Optional: function-level profiling
        profiling_data: dict[str, Any] = {}
        memory_data: dict[str, Any] = {}

        parse_start = time.perf_counter()

        if self.profile:
            # Full pipeline under cProfile
            with ProfilerContext() as prof:
                try:
                    parser = FullTextXMLParser(xml_content, config=self.config)
                    _ = parser.extract_metadata()
                    _ = parser.get_full_text_sections()
                    _ = parser.get_full_text_sections_structured()
                    _ = parser.extract_authors() if hasattr(parser, "extract_authors") else None
                    _ = (
                        parser.extract_references()
                        if hasattr(parser, "extract_references")
                        else None
                    )
                except Exception as e:
                    logger.error("  Parse error for %s: %s", article_path.name, e)
                    self._stats["failed"] += 1
                    self._stats["parse_errors"].append(
                        {"article": article_path.name, "error": f"parse: {e}"}
                    )
                    return None

            profiling_data = prof.stats_dict()
            parse_time = prof.elapsed

        else:
            # Normal code path without profiling
            try:
                parser = FullTextXMLParser(xml_content, config=self.config)
            except Exception as e:
                elapsed = time.perf_counter() - parse_start
                logger.error("  Parse error for %s: %s", article_path.name, e)
                self._stats["failed"] += 1
                self._stats["total_parse_time_s"] += elapsed
                self._stats["parse_errors"].append(
                    {"article": article_path.name, "error": f"parse: {e}"}
                )
                return None

            parse_time = time.perf_counter() - parse_start

        self._stats["total_parse_time_s"] += parse_time
        self._stats["successful"] += 1

        # Optional: memory profiling for block extraction
        if self.profile_memory:
            try:
                mem_tracker = MemoryTracker()
                mem_tracker.start()
                _ = parser.get_full_text_sections_structured()
                memory_data = mem_tracker.stop()
            except Exception as e:
                logger.warning("  Memory profiling error: %s", e)
                memory_data = {"error": str(e)}

        # Run metrics (unless already done during profiling)
        try:
            if self.profile:
                # parser already has all extraction calls done during profiling
                metrics = compute_all_metrics(parser, xml_content)
            else:
                metrics = compute_all_metrics(parser, xml_content)
        except Exception as e:
            logger.error("  Metrics error for %s: %s", article_path.name, e)
            metrics = {"error": str(e), "composite_score": 0.0, "per_metric": {}}

        # Article metadata
        article_meta: dict[str, Any] = {
            "file_size_bytes": article_path.stat().st_size,
            "parse_time_seconds": round(parse_time, 4),
        }
        if profiling_data:
            article_meta["profiling"] = {
                "elapsed_s": profiling_data["elapsed_s"],
                "total_calls": profiling_data["total_calls"],
                "primitive_calls": profiling_data["primitive_calls"],
                "call_counts": {
                    name: data["ncalls"] for name, data in profiling_data["by_function"].items()
                },
                "cumulative_time_s": {
                    name: data["cumtime_s"] for name, data in profiling_data["by_function"].items()
                },
            }
        if memory_data and "error" not in memory_data:
            article_meta["memory"] = {
                "peak_mib": memory_data["peak_mib"],
                "current_mib": memory_data["current_mib"],
                "allocated_mib": memory_data["allocated_mib"],
                "by_module_kib": memory_data.get("by_module", {}),
            }

        return metrics, parse_time, article_meta

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        """Return current processing statistics."""
        return dict(self._stats)

    def print_profile_summary(self, report: BenchmarkReport) -> None:
        """
        Print a human-readable profiling summary from the report.

        Aggregates function-level call counts and cumulative times across
        all profiled articles.

        Parameters
        ----------
        report : BenchmarkReport
            Report that may contain per-article profiling data.
        """
        has_profiling = any(
            entry.get("metadata", {}).get("profiling") for entry in report.article_results
        )
        has_memory = any(
            entry.get("metadata", {}).get("memory") for entry in report.article_results
        )

        print(f"\n{'=' * 60}")
        print("  Performance Profile Summary")
        print(f"{'=' * 60}")

        if has_profiling:
            call_counts: dict[str, list[int]] = {}
            cum_times: dict[str, list[float]] = {}

            for entry in report.article_results:
                profiling = entry.get("metadata", {}).get("profiling", {})
                for func_name, calls in profiling.get("call_counts", {}).items():
                    call_counts.setdefault(func_name, []).append(calls)
                for func_name, ct in profiling.get("cumulative_time_s", {}).items():
                    cum_times.setdefault(func_name, []).append(ct)

            print("\n  --- Function-Level Profiling ---")
            print(f"  {'Function':40s} {'Calls':>8s} {'Cum. Time (s)':>14s}")
            print(f"  {'-' * 62}")
            for func_name in sorted(cum_times, key=lambda f: max(cum_times[f]), reverse=True)[:15]:
                avg_calls = sum(call_counts.get(func_name, [0])) / max(
                    len(call_counts.get(func_name, [1])), 1
                )
                avg_ct = sum(cum_times[func_name]) / len(cum_times[func_name])
                print(f"  {func_name:40s} {avg_calls:>8.0f} {avg_ct:>14.6f}")

        if has_memory:
            peak_mibs: list[float] = []
            current_mibs: list[float] = []
            modules: dict[str, list[float]] = {}

            for entry in report.article_results:
                mem = entry.get("metadata", {}).get("memory", {})
                if mem.get("peak_mib"):
                    peak_mibs.append(mem["peak_mib"])
                    current_mibs.append(mem.get("current_mib", 0.0))
                    for mod, kib in mem.get("by_module_kib", {}).items():
                        modules.setdefault(mod, []).append(kib)

            if peak_mibs:
                print("\n  --- Memory Profile ---")
                print(f"  Peak memory   : {sum(peak_mibs) / len(peak_mibs):.2f} MiB (avg)")
                print(f"  Current memory: {sum(current_mibs) / len(current_mibs):.2f} MiB (avg)")
                print("  Top modules by allocation:")
                for mod in sorted(modules, key=lambda m: sum(modules[m]), reverse=True)[:5]:
                    avg_kib = sum(modules[mod]) / len(modules[mod])
                    print(f"    {mod:30s} {avg_kib:>8.1f} KiB (avg)")

        if not has_profiling and not has_memory:
            print("\n  No profiling data available.")
            print("  Re-run with profile=True and/or profile_memory=True.")
        print()
