#!/usr/bin/env python3
"""
CLI for unified search and deduplication testing.

Usage:
    python -m pyeuropepmc.cli.unified_search --help
    python -m pyeuropepmc.cli.unified_search --query "CRISPR cancer" --sources pubmed semantic_scholar openalex arxiv --limit 25
"""

from __future__ import annotations

import json
import sys
from typing import Annotated

from pyeuropepmc._optional_imports import OptionalDependencyError

try:
    import typer
except ImportError:
    raise OptionalDependencyError(
        "typer", "CLI interface", "pip install pyeuropepmc[standard]"
    ) from None

from pyeuropepmc.features.enrich.merger import DedupMode
from pyeuropepmc.features.search import UnifiedSearch

app = typer.Typer(
    name="unified_search",
    help="Unified multi-source literature search with deduplication",
    no_args_is_help=True,
)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query string")],
    sources: Annotated[
        list[str],
        typer.Option(
            "-s",
            "--source",
            help="Sources to search (europepmc, pubmed, arxiv, semantic_scholar, openalex, "
            "clinicaltrials, zenodo, doaj, dblp, hal, core)",
        ),
    ] = ["europepmc", "pubmed", "arxiv"],
    limit: Annotated[int, typer.Option("-l", "--limit", help="Max results per source")] = 25,
    mode: Annotated[
        DedupMode,
        typer.Option(
            "-m",
            "--mode",
            help="Deduplication mode: BALANCED (default), FOCUSED (high recall), RELAXED (high precision)",
        ),
    ] = DedupMode.BALANCED,
    output: Annotated[
        str | None, typer.Option("-o", "--output", help="Output file (JSON)")
    ] = None,
) -> None:
    """Search across multiple sources and deduplicate results."""
    print("=" * 70)
    print("Unified Multi-Source Literature Search")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Limit per source: {limit}")
    print(f"Deduplication mode: {mode.name}")
    print("=" * 70)

    # Initialize searcher
    searcher = UnifiedSearch(sources=sources, dedup_mode=mode)

    try:
        results, report = searcher.search(query, limit=limit)

        # Print summary
        total_input = report.total_input
        total_output = report.total_output
        duplicates = report.duplicates_removed

        print("\n--- Deduplication Summary ---")
        print(f"Total input papers:    {total_input}")
        print(f"Total output papers:   {total_output}")
        print(f"Duplicates removed:    {duplicates}")
        if total_input > 0:
            dedup_rate = (duplicates / total_input) * 100
            reduction_pct = ((total_input - total_output) / total_input) * 100
            print(f"Deduplication rate:    {dedup_rate:.1f}%")
            print(f"Reduction:             {reduction_pct:.1f}%")

        # Print match levels
        print("\n--- Match Levels ---")
        summary = report.summary()
        by_level = summary.get("by_match_level", {})
        if by_level:
            for level, count in sorted(by_level.items(), key=lambda x: -x[1]):
                print(f"  {level}: {count}")
        else:
            print("  No duplicates found")

        # Print source times / errors
        print("\n--- Source Performance ---")
        source_times = report.metadata.get("source_times", {})
        source_errors = report.metadata.get("source_errors", {})
        for source in report.metadata.get("sources_used", sorted(source_times)):
            if source in source_errors:
                print(f"  {source}: FAILED ({source_errors[source]})")
            elif source in source_times:
                print(f"  {source}: {source_times[source]:.2f}s")

        # Print sample results
        print("\n--- Sample Results (first 5) ---")
        for i, result in enumerate(results[:5], 1):
            print(f"\n{i}. [{result.source}] {(result.title or '')[:70]}...")
            if result.doi:
                print(f"   DOI: {result.doi}")
            if result.pmid:
                print(f"   PMID: {result.pmid}")
            if result.publication_year:
                print(f"   Year: {result.publication_year}")

        if len(results) > 5:
            print(f"\n... and {len(results) - 5} more results")

        # Output to file if specified
        if output:
            output_data = {
                "query": query,
                "sources": sources,
                "limit": limit,
                "dedup_mode": mode.name,
                "summary": summary,
                "results": [
                    {
                        "title": r.title,
                        "source": r.source,
                        "doi": r.doi,
                        "pmid": r.pmid,
                        "publication_year": r.publication_year,
                    }
                    for r in results
                ],
            }
            with open(output, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"\nResults saved to: {output}")

        print("\n" + "=" * 70)
        print("Search complete!")
        print("=" * 70)

    except Exception as e:
        print(f"\nError during search: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


@app.command()
def compare_sources(
    query: Annotated[str, typer.Argument(help="Search query string")],
    sources: Annotated[
        list[str],
        typer.Option(
            "-s",
            "--source",
        ),
    ] = ["europepmc", "pubmed", "arxiv"],
    limit: Annotated[int, typer.Option("-l", "--limit")] = 10,
) -> None:
    """Compare per-source results without deduplication."""
    print("=" * 70)
    print("Per-Source Breakdown (no deduplication)")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Limit per source: {limit}")
    print("=" * 70)

    searcher = UnifiedSearch(sources=sources)
    per_source = searcher.search_all(query, limit=limit)

    total = 0
    for source, results in per_source.items():
        count = len(results)
        total += count
        print(f"\n{source.upper()}: {count} results")
        for i, result in enumerate(results[:3], 1):
            print(f"  {i}. {(result.title or '')[:60]}...")
            if result.doi:
                print(f"     DOI: {result.doi}")

    print(f"\nTotal across all sources: {total}")
    print("=" * 70)


if __name__ == "__main__":
    app()
