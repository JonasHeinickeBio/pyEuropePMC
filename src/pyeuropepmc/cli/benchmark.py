"""
Benchmark CLI subcommand group.

Commands
--------
- ``list-datasets`` — Show known GROBID benchmark datasets.
- ``dataset-info`` — Show metadata for a specific dataset.
- ``download`` — Download a dataset to local cache.
- ``run`` — Run the full benchmark suite on a dataset.
- ``run-file`` — Run all metrics on a single XML file.
- ``profile`` — Function-level profiling of a single file.
- ``profile-memory`` — Memory profiling of a single file.
- ``report`` — Display or save an existing benchmark report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from pyeuropepmc.benchmark import (
    DATASETS,
    BenchmarkDataset,
    BenchmarkReport,
    BenchmarkRunner,
    compute_all_metrics,
    dataset_info,
    profile_memory,
    profile_text,
)
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

benchmark_app = typer.Typer(
    name="benchmark",
    help="Benchmark XML parser quality and performance across GROBID datasets",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Dataset commands
# ---------------------------------------------------------------------------


@benchmark_app.command(name="list-datasets")
def list_datasets(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full descriptions"),
) -> None:
    """List all known benchmark datasets with metadata."""
    print(f"\n{'Known Benchmark Datasets':^60}")
    print(f"{'=' * 60}")
    print(f"  {'Name':25s} {'Articles':>8s} {'Size':>8s}")
    print(f"  {'-' * 43}")
    for name, info in sorted(DATASETS.items()):
        size_str = f"{info.size_gb:.1f} GB" if info.size_gb > 0 else "N/A"
        print(f"  {name:25s} {info.article_count:>8d} {size_str:>8s}")
        if verbose:
            print(f"  {'':25s} {info.description}")
    print()


@benchmark_app.command(name="dataset-info")
def dataset_info_cmd(
    name: str = typer.Argument(..., help="Dataset name (e.g. PMC_sample_1943)"),
) -> None:
    """Show metadata for a specific dataset."""
    info = dataset_info(name)
    if info is None:
        print(f"Unknown dataset: {name!r}")
        print("Use 'pyeuropepmc benchmark list-datasets' to see available options.")
        raise typer.Exit(code=1)

    print(f"\nDataset: {info.name}")
    print(f"{'=' * 40}")
    print(f"  Description  : {info.description}")
    print(f"  Source       : {info.source}")
    size_str = f"{info.size_gb:.1f} GB" if info.size_gb > 0 else "N/A"
    print(f"  Size         : {size_str}")
    print(f"  Articles     : {info.article_count:,}")
    print(f"  File pattern : {info.filename_glob}")


@benchmark_app.command(name="download")
def download_dataset(
    name: str = typer.Argument(..., help="Dataset name (e.g. PMC_sample_1943)"),
    data_dir: str | None = typer.Option(None, "--data-dir", "-d", help="Local cache directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-download even if cached"),
) -> None:
    """Download a benchmark dataset to local cache."""
    dataset = BenchmarkDataset(name, data_dir=data_dir)
    if dataset.is_downloaded and not force:
        print(f"Dataset {name!r} already downloaded at {dataset._local_dir}")
        print(f"  {len(list(dataset.iter_articles()))} XML files available")
        print("Use --force to re-download.")
        return

    print(f"Downloading {name!r}...")
    try:
        dataset.download(force=force)
    except Exception as e:
        print(f"Download failed: {e}")
        raise typer.Exit(code=1) from None

    xml_count = len(list(dataset.iter_articles()))
    print(f"Download complete: {xml_count} XML files at {dataset._local_dir}")


# ---------------------------------------------------------------------------
# Benchmark run commands
# ---------------------------------------------------------------------------


@benchmark_app.command(name="run")
def run_benchmark(
    dataset_name: str = typer.Argument(..., help="Dataset name or 'local' for a directory"),
    data_dir: str | None = typer.Option(None, "--data-dir", "-d", help="Data directory"),
    local_path: str | None = typer.Option(None, "--local-path", "-l", help="Local XML dir path"),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Limit number of articles"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save report JSON"),
    profile: bool = typer.Option(False, "--profile", "-p", help="Enable function-level profiling"),
    profile_memory_flag: bool = typer.Option(
        False, "--profile-memory", "-m", help="Enable memory profiling"
    ),
    skip_errors: bool = typer.Option(
        True, "--skip-errors", "-s", help="Skip articles that fail to parse"
    ),
) -> None:
    """Run the full benchmark suite on a dataset."""
    # Resolve dataset
    if dataset_name == "local":
        if not local_path:
            print("Error: --local-path is required when dataset='local'")
            raise typer.Exit(code=1)
        dataset = BenchmarkDataset("local", local_path=local_path)
    else:
        dataset = BenchmarkDataset(dataset_name, data_dir=data_dir)
        if not dataset.is_downloaded:
            print(f"Dataset {dataset_name!r} not downloaded yet.")
            yn = input("Download now? [Y/n]: ").strip().lower()
            if yn not in ("", "y", "yes"):
                print("Aborting.")
                raise typer.Exit(code=1)
            dataset.download()

    # Run benchmark
    print(f"\nRunning benchmark on dataset: {dataset_name}")
    print(f"  Articles available: {sum(1 for _ in dataset.iter_articles())}")
    if limit:
        print(f"  Limit: {limit} articles")
    if profile:
        print("  Function-level profiling: enabled")
    if profile_memory_flag:
        print("  Memory profiling: enabled")
    print()

    runner = BenchmarkRunner(
        dataset,
        limit=limit,
        skip_errors=skip_errors,
        profile=profile,
        profile_memory=profile_memory_flag,
    )
    report = runner.run_all()

    # Display summary
    overall = report.aggregate_overall()
    print(f"\n{'=' * 60}")
    print(f"  Benchmark Results: {dataset_name}")
    print(f"{'=' * 60}")
    cs = overall.get("composite_score", "N/A")
    if isinstance(cs, dict):
        print(f"  Composite score  : {cs.get('mean', 'N/A'):.3f} (mean)")
    elif isinstance(cs, int | float):
        print(f"  Composite score  : {cs:.3f}")
    else:
        print(f"  Composite score  : {cs}")
    if "per_metric" in overall:
        for metric, score in sorted(overall["per_metric"].items()):
            if isinstance(score, dict):
                print(f"    {metric:30s}: {score.get('mean', 'N/A'):.4f}")
            else:
                print(f"    {metric:30s}: {score:.4f}")
    print(
        f"  Articles {runner.stats['successful']}/{runner.stats['total_articles']} "
        f"successful ({runner.stats['failed']} errors)"
    )
    print(f"  Total parse time: {runner.stats['total_parse_time_s']:.2f}s")

    # Profile summary
    if profile or profile_memory_flag:
        runner.print_profile_summary(report)

    # Save to file
    if output:
        out_path = Path(output)
        report.save_json(out_path)
        print(f"\nReport saved to: {out_path}")


@benchmark_app.command(name="run-file")
def run_file(
    filepath: str = typer.Argument(..., help="Path to a JATS XML file"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save results as JSON"),
) -> None:
    """Run all metrics on a single XML file."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {path}")
        raise typer.Exit(code=1)

    xml_content = path.read_text(encoding="utf-8")
    parser = FullTextXMLParser(xml_content)
    metrics = compute_all_metrics(parser, xml_content)

    print(f"\n{'=' * 60}")
    print(f"  Benchmark Results: {path.name}")
    print(f"{'=' * 60}")
    print(f"  Composite score  : {metrics['composite_score']:.4f}")
    print("  Per-metric scores:")
    for metric, score in sorted(metrics.get("per_metric", {}).items()):
        print(f"    {metric:30s}: {score:.4f}")
    print()

    if output:
        Path(output).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Results saved to: {output}")


# ---------------------------------------------------------------------------
# Profiling commands
# ---------------------------------------------------------------------------


@benchmark_app.command(name="profile")
def profile_file(
    filepath: str = typer.Argument(..., help="Path to a JATS XML file"),
    top_n: int = typer.Option(20, "--top", "-t", help="Show top N functions"),
) -> None:
    """Profile function-level timing of the full parsing pipeline on a single file."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {path}")
        raise typer.Exit(code=1)

    xml_content = path.read_text(encoding="utf-8")
    prof = profile_text(xml_content)

    print(f"\n{'=' * 60}")
    print(f"  Function-Level Profile: {path.name}")
    print(f"{'=' * 60}")
    print(f"  Total time: {prof['elapsed_s']:.4f}s ({prof['total_calls']:,} calls)")
    # Sort functions by cumulative time
    by_func = prof.get("by_function", {})
    sorted_funcs = sorted(
        by_func.items(),
        key=lambda item: item[1].get("cumtime_s", 0),
        reverse=True,
    )
    print("\n  Top functions by cumulative time:")
    print(f"  {'Function':45s} {'Calls':>7s} {'Total':>8s} {'Per Call':>9s}")
    print(f"  {'-' * 71}")
    for name, data in sorted_funcs[:top_n]:
        ncalls = data.get("ncalls", 0)
        cumtime = data.get("cumtime_s", 0)
        percall = data.get("percall_s", 0)
        print(f"  {name:45s} {ncalls:>7d} {cumtime:>8.4f} {percall:>9.6f}")
    print()

    # Module-level breakdown by filtering function names
    parser_breakdown = prof.get("parser_breakdown_s", {})
    if parser_breakdown:
        print("  Parser method breakdown:")
        for method, total_s in sorted(parser_breakdown.items(), key=lambda x: -x[1])[:10]:
            print(f"    {method:45s}: {total_s:.4f}s")
        print()


@benchmark_app.command(name="profile-memory")
def profile_memory_cmd(
    filepath: str = typer.Argument(..., help="Path to a JATS XML file"),
    top_n: int = typer.Option(15, "--top", "-t", help="Show top N allocations"),
) -> None:
    """Profile memory allocation of the structured parsing pipeline."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {path}")
        raise typer.Exit(code=1)

    xml_content = path.read_text(encoding="utf-8")
    mem = profile_memory(xml_content)

    print(f"\n{'=' * 60}")
    print(f"  Memory Profile: {path.name}")
    print(f"{'=' * 60}")
    print(f"  Peak memory   : {mem['peak_mib']:.2f} MiB")
    print(f"  Current memory: {mem.get('current_mib', 0):.2f} MiB")
    print(f"  Allocated     : {mem.get('allocated_mib', 0):.2f} MiB")

    top_alloc = mem.get("top_allocations", [])
    if top_alloc:
        print("\n  Top allocations:")
        print(f"  {'Size (KiB)':>10s}  {'Location'}")
        print(f"  {'-' * 50}")
        for alloc in top_alloc[:top_n]:
            print(f"  {alloc.get('size_kib', 0):>10.1f}  {alloc.get('location', 'unknown')}")
        print()

    by_module = mem.get("by_module", {})
    if by_module:
        print("  Allocations by module:")
        for mod, kib in sorted(by_module.items(), key=lambda x: -x[1])[:10]:
            print(f"    {mod:40s}: {kib:.1f} KiB")
        print()


# ---------------------------------------------------------------------------
# Report commands
# ---------------------------------------------------------------------------


@benchmark_app.command(name="report")
def show_report(
    filepath: str = typer.Argument(..., help="Path to a saved benchmark report JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-article details"),
) -> None:
    """Display or inspect a saved benchmark report."""
    path = Path(filepath)
    if not path.exists():
        print(f"Report not found: {path}")
        raise typer.Exit(code=1)

    report = BenchmarkReport.load_json(path)

    print(f"\n{'=' * 60}")
    print(f"  Benchmark Report: {report.title}")
    print(f"{'=' * 60}")

    metadata = report.metadata or {}
    if metadata.get("parser_version"):
        print(f"  Parser version  : {metadata['parser_version']}")
    if metadata.get("date"):
        print(f"  Date            : {metadata['date']}")
    print(f"  Articles        : {len(report.article_results)}")
    if metadata.get("stats"):
        stats = metadata["stats"]
        print(f"  Successful      : {stats.get('successful', 0)}")
        print(f"  Failed          : {stats.get('failed', 0)}")
        print(f"  Parse time      : {stats.get('total_parse_time_s', 0):.2f}s")

    # Per-dataset summaries
    ds_agg = report.aggregate_by_dataset()
    if ds_agg:
        print("\n  Per-dataset summaries:")
        for ds_name, agg in sorted(ds_agg.items()):
            print(f"\n  [{ds_name}]")
            print(f"    Articles       : {agg.get('article_count', 'N/A')}")
            if "parse_time_seconds" in agg:
                pt = agg["parse_time_seconds"]
                print(f"    Parse time     : {pt.get('mean', 'N/A')}s (mean)")
            if "composite_score" in agg:
                print(f"    Composite score: {agg['composite_score']:.4f}")

    # Overall
    overall = report.aggregate_overall()
    if overall:
        print("\n  Overall:")
        print(f"    Composite score: {overall.get('composite_score', 'N/A')}")
        if "per_metric" in overall:
            for metric, score in sorted(overall["per_metric"].items()):
                print(f"      {metric:30s}: {score:.4f}")

    # Verbose: per-article breakdown
    if verbose and report.article_results:
        print("\n  Per-article details:")
        for entry in report.article_results:
            label = entry.get("article_label", "?")
            ds = entry.get("dataset_name", "?")
            metrics = entry.get("metrics", {})
            meta = entry.get("metadata", {})
            pt = meta.get("parse_time_seconds", "?")
            cs = metrics.get("composite_score", "N/A")
            print(f"    {label:30s} [{ds}]  score={cs:.4f}  parse={pt}s")

    print()


# ---------------------------------------------------------------------------
# Fetch XMLs from Europe PMC
# ---------------------------------------------------------------------------


def _collect_pmcids(
    client: Any,
    target: int,
    rate_limit: float,
) -> list[str]:
    """Collect PMCIDs from Europe PMC search API."""
    import time

    pmcids: list[str] = []
    cursor_mark = "*"
    page_size = 100
    query = "(OPEN_ACCESS:y) AND (HAS_FT:y)"
    attempts = 0

    while len(pmcids) < target and attempts < 10:
        attempts += 1
        try:
            result = client.search(
                query,
                resultType="lite",
                pageSize=page_size,
                cursorMark=cursor_mark,
            )
        except Exception as e:
            print(f"  Search error on attempt {attempts}: {e}")
            time.sleep(5)
            continue

        if isinstance(result, str):
            print("  Unexpected: search returned string instead of dict")
            break

        results_list = result.get("resultList", {}).get("result", [])
        next_cursor = result.get("nextCursorMark")

        if not results_list:
            print("  No more results.")
            break

        for article in results_list:
            pmcid = article.get("pmcid", "") or article.get("id", "")
            if pmcid and pmcid.startswith("PMC"):
                pmcid = pmcid[3:]
            if pmcid and pmcid.isdigit() and pmcid not in pmcids:
                pmcids.append(pmcid)
                if len(pmcids) % 10 == 0:
                    print(f"  Collected {len(pmcids)} PMCIDs so far...")

        cursor_mark = next_cursor if next_cursor else "*"
        if len(pmcids) >= target:
            break
        time.sleep(rate_limit)

    return pmcids[:target]


def _download_xmls(
    ft_client: Any,
    pmcids: list[str],
    out_path: Path,
    rate_limit: float,
) -> tuple[list[Path], list[str]]:
    """Download XML files for given PMCIDs. Returns (downloaded, failed)."""
    import time

    downloaded: list[Path] = []
    failed: list[str] = []

    print(f"Downloading {len(pmcids)} XML articles to {out_path}/\n")

    for i, pmcid in enumerate(pmcids, 1):
        output_path = out_path / f"PMC{pmcid}.xml"

        if output_path.exists() and output_path.stat().st_size > 1000:
            print(f"  [{i}/{len(pmcids)}] PMC{pmcid} — already exists, skipping")
            downloaded.append(output_path)
            continue

        try:
            result = ft_client.download_xml_by_pmcid(pmcid, output_path=output_path)
            if result and result.exists() and result.stat().st_size > 100:
                downloaded.append(result)
                print(
                    f"  [{i}/{len(pmcids)}] PMC{pmcid} — "
                    f"OK ({result.stat().st_size / 1024:.0f} KB)"
                )
            else:
                failed.append(pmcid)
                print(f"  [{i}/{len(pmcids)}] PMC{pmcid} — FAILED (no file)")
        except Exception as e:
            failed.append(pmcid)
            print(f"  [{i}/{len(pmcids)}] PMC{pmcid} — ERROR: {e}")

        time.sleep(rate_limit)

    return downloaded, failed


@benchmark_app.command(name="fetch-xmls")
def fetch_xmls(
    target: int = typer.Option(55, "--target", "-t", help="Target number of PMCIDs to collect"),
    output_dir: str = typer.Option(
        "benchmark_xmls/xml", "--output-dir", "-o", help="Directory to save XML files"
    ),
    rate_limit: float = typer.Option(0.5, "--rate-limit", "-r", help="Seconds between API calls"),
) -> None:
    """Download open-access XML articles from Europe PMC for benchmarking.

    Searches for articles with full-text XML available, collects PMCIDs,
    and downloads the XML files to a local directory.
    """
    from pyeuropepmc.clients.fulltext import FullTextClient
    from pyeuropepmc.clients.search import SearchClient

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Collect PMCIDs
    print("Searching for open-access articles with full-text XML...")
    print(f"Target: {target} PMCIDs\n")

    client = SearchClient(rate_limit_delay=rate_limit)
    pmcids = _collect_pmcids(client, target, rate_limit)

    print(f"\nCollected {len(pmcids)} PMCIDs total.\n")

    if len(pmcids) < 50:
        print(f"WARNING: Only got {len(pmcids)} PMCIDs, need at least 50.")
        raise typer.Exit(code=1)

    # Step 2: Download XMLs
    ft_client = FullTextClient(rate_limit_delay=rate_limit)
    downloaded, failed = _download_xmls(ft_client, pmcids, out_path, rate_limit)

    print(f"\nDownloaded: {len(downloaded)}, Failed: {len(failed)}")
    if failed:
        print(f"Failed PMCIDs: {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")

    # Save PMCID list
    list_path = out_path.parent / "pmcid_list.txt"
    with open(list_path, "w") as f:
        for p in sorted(set(p.stem.replace("PMC", "") for p in downloaded)):
            f.write(f"{p}\n")

    print(f"\n{'=' * 60}")
    print(f"Download complete: {len(downloaded)} XML files in {out_path}/")
    print(f"PMCID list saved to: {list_path}")
    print(f"{'=' * 60}")
    print("\nTo run benchmarks:")
    print(f"  pyeuropepmc benchmark run local --local-path {out_path}")
    print(f"  pyeuropepmc benchmark run-extra --xml-dir {out_path}")


# ---------------------------------------------------------------------------
# Extra benchmarks (parse speed + content coverage)
# ---------------------------------------------------------------------------


def _run_parse_speed_benchmark(
    xml_files: list[Path],
    xml_path: Path,
) -> dict[str, Any]:
    """Run parse speed benchmark on XML files and return results."""
    import time

    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    print("=" * 70)
    print("PARSE SPEED BENCHMARK")
    print("=" * 70)

    results: dict[str, float] = {}
    errors = 0

    for i, fpath in enumerate(xml_files, 1):
        label = fpath.stem
        try:
            xml = fpath.read_text(encoding="utf-8", errors="replace")
            start = time.perf_counter()
            parser = FullTextXMLParser(xml)
            _ = parser.extract_metadata()
            _ = parser.get_full_text_sections()
            elapsed = time.perf_counter() - start
            results[label] = elapsed
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(xml_files)}] {label} — ERROR: {e}")

        if i % 10 == 0:
            print(f"  [{i}/{len(xml_files)}] processed...")

    if not results:
        print("No successful parses!")
        raise typer.Exit(code=1)

    sorted_results = sorted(results.items(), key=lambda x: x[1])
    times = list(results.values())
    mean_time = sum(times) / len(times)
    median_time = sorted(times)[len(times) // 2]

    print(f"\nParse speed results ({len(results)} articles, {errors} errors):")
    print(f"  Fastest:  {sorted_results[0][0]} — {sorted_results[0][1]:.3f}s")
    print(f"  Slowest:  {sorted_results[-1][0]} — {sorted_results[-1][1]:.3f}s")
    print(f"  Mean:     {mean_time:.3f}s")
    print(f"  Median:   {median_time:.3f}s")
    print(f"  Throughput: {1 / median_time:.1f} articles/s")

    print("\n  Slowest 5 articles:")
    for label, t in sorted_results[-5:]:
        fpath_xml = xml_path / f"{label}.xml"
        size_kb = fpath_xml.stat().st_size / 1024 if fpath_xml.exists() else 0
        print(f"    {label}: {t:.3f}s ({size_kb:.0f} KB)")

    print("\n  Fastest 5 articles:")
    for label, t in sorted_results[:5]:
        fpath_xml = xml_path / f"{label}.xml"
        size_kb = fpath_xml.stat().st_size / 1024 if fpath_xml.exists() else 0
        print(f"    {label}: {t:.3f}s ({size_kb:.0f} KB)")

    return {
        "count": len(results),
        "errors": errors,
        "mean_seconds": round(mean_time, 4),
        "median_seconds": round(median_time, 4),
        "throughput_articles_per_sec": round(1 / median_time, 2),
        "fastest": {
            "label": sorted_results[0][0],
            "time": round(sorted_results[0][1], 4),
        },
        "slowest": {
            "label": sorted_results[-1][0],
            "time": round(sorted_results[-1][1], 4),
        },
        "all_times": {k: round(v, 4) for k, v in sorted_results},
    }


def _run_content_coverage_benchmark(
    xml_files: list[Path],
) -> dict[str, Any]:
    """Run content coverage benchmark on XML files and return results."""
    from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

    print("\n" + "=" * 70)
    print("CONTENT COVERAGE BENCHMARK")
    print("=" * 70)

    all_types: dict[str, int] = {}
    all_inline_types: dict[str, int] = {}
    total_blocks = 0
    total_sections = 0
    coverage_errors = 0

    for fpath in xml_files:
        try:
            xml = fpath.read_text(encoding="utf-8", errors="replace")
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()
            total_sections += len(sections)
            for sec in sections:
                for block in sec.get("content", []):
                    bt = block.get("type", "unknown")
                    all_types[bt] = all_types.get(bt, 0) + 1
                    total_blocks += 1
                    for inline in block.get("inlines", []):
                        it = inline.get("type", "unknown")
                        all_inline_types[it] = all_inline_types.get(it, 0) + 1
        except Exception:
            coverage_errors += 1

    print(f"\nContent coverage ({len(xml_files)} articles):")
    print(f"  Total sections: {total_sections}")
    print(f"  Total blocks:   {total_blocks}")
    print(f"  Block types:    {len(all_types)}")
    print(f"  Inline types:   {len(all_inline_types)}")
    if coverage_errors:
        print(f"  Errors:         {coverage_errors}")

    print("\n  Block type frequency:")
    for bt, count in sorted(all_types.items(), key=lambda x: -x[1]):
        print(f"    {bt}: {count}")

    print("\n  Inline type frequency:")
    for it, count in sorted(all_inline_types.items(), key=lambda x: -x[1]):
        print(f"    {it}: {count}")

    return {
        "article_count": len(xml_files),
        "total_sections": total_sections,
        "total_blocks": total_blocks,
        "block_types": dict(sorted(all_types.items(), key=lambda x: -x[1])),
        "inline_types": dict(sorted(all_inline_types.items(), key=lambda x: -x[1])),
    }


@benchmark_app.command(name="run-extra")
def run_extra(
    xml_dir: str = typer.Option(
        "benchmark_xmls/xml", "--xml-dir", "-d", help="Directory containing XML files"
    ),
    output: str | None = typer.Option(
        "benchmark_xmls/benchmark_results.json", "--output", "-o", help="Save results JSON"
    ),
) -> None:
    """Run parse speed and content coverage benchmarks on XML files.

    Supplements the standard quality metrics with throughput measurements
    and block-type diversity analysis.
    """
    xml_path = Path(xml_dir)
    if not xml_path.exists():
        print(f"ERROR: XML directory not found: {xml_path}")
        print("Run 'pyeuropepmc benchmark fetch-xmls' first.")
        raise typer.Exit(code=1)

    xml_files = sorted(xml_path.glob("PMC*.xml"))
    if not xml_files:
        print(f"ERROR: No PMC*.xml files found in {xml_path}")
        raise typer.Exit(code=1)

    print(f"Found {len(xml_files)} XML files in {xml_path}\n")

    speed_result = _run_parse_speed_benchmark(xml_files, xml_path)
    coverage_result = _run_content_coverage_benchmark(xml_files)

    # Save combined results
    combined = {
        "parse_speed": speed_result,
        "content_coverage": coverage_result,
    }
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(combined, f, indent=2, default=str)
        print(f"\n{'=' * 70}")
        print(f"Results saved to: {out_path}")
        print(f"{'=' * 70}")
