#!/usr/bin/env python3
"""
Benchmark Configuration and Runner

This script provides a flexible way to run PyEuropePMC benchmarks with different
configurations and parameters.
"""

import argparse
import json
from pathlib import Path

from benchmark_pipeline import BenchmarkConfig, BenchmarkRunner


def load_config_from_file(config_file: Path) -> BenchmarkConfig:
    """Load benchmark configuration from JSON file."""
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with open(config_file, encoding="utf-8") as f:
        config_data = json.load(f)

    # Create config object from dict
    config = BenchmarkConfig()
    for key, value in config_data.items():
        if hasattr(config, key):
            # Convert string paths to Path objects
            if key.endswith("_dir") and isinstance(value, str):
                value = Path(value)
            setattr(config, key, value)

    return config


def create_default_configs() -> dict[str, BenchmarkConfig]:
    """Create a set of default benchmark configurations."""
    return {
        "small_test": BenchmarkConfig(
            query='(OPEN_ACCESS:y) AND "cancer" AND (CITED:[5 TO *])',
            target_paper_count=50,
            search_page_size=25,
            output_dir=Path("benchmark_output/small_test"),
            xml_cache_dir=Path("benchmark_cache/xml_small"),
            results_file="small_test_results.json",
        ),
        "medium_benchmark": BenchmarkConfig(
            query="(OPEN_ACCESS:y) AND (CITED:[5 TO *])",
            target_paper_count=500,
            search_page_size=50,
            output_dir=Path("benchmark_output/medium_benchmark"),
            xml_cache_dir=Path("benchmark_cache/xml_medium"),
            results_file="medium_benchmark_results.json",
        ),
        "full_benchmark": BenchmarkConfig(
            query="(OPEN_ACCESS:y) AND (CITED:[5 TO *])",
            target_paper_count=1000,
            search_page_size=100,
            output_dir=Path("benchmark_output/full_benchmark"),
            xml_cache_dir=Path("benchmark_cache/xml_full"),
            results_file="full_benchmark_results.json",
        ),
        "cancer_focused": BenchmarkConfig(
            query='(OPEN_ACCESS:y) AND "cancer immunotherapy" AND (CITED:[10 TO *])',
            target_paper_count=200,
            search_page_size=50,
            output_dir=Path("benchmark_output/cancer_focused"),
            xml_cache_dir=Path("benchmark_cache/xml_cancer"),
            results_file="cancer_focused_results.json",
        ),
        "recent_papers": BenchmarkConfig(
            query="(OPEN_ACCESS:y) AND (CITED:[5 TO *]) AND (PUB_YEAR:[2020 TO 2025])",
            target_paper_count=300,
            search_page_size=50,
            output_dir=Path("benchmark_output/recent_papers"),
            xml_cache_dir=Path("benchmark_cache/xml_recent"),
            results_file="recent_papers_results.json",
        ),
    }


def save_config_template(output_file: Path) -> None:
    """Save a configuration template file."""
    template = {
        "query": "(OPEN_ACCESS:y) AND (CITED:[5 TO *])",
        "target_paper_count": 1000,
        "search_page_size": 100,
        "max_concurrent_downloads": 5,
        "download_timeout_seconds": 30,
        "skip_existing_xml": True,
        "batch_size": 50,
        "enable_enrichment": False,
        "output_dir": "benchmark_output",
        "xml_cache_dir": "benchmark_cache/xml",
        "results_file": "benchmark_results.json",
        "rdf_format": "turtle",
        "enable_citation_networks": True,
        "enable_collaboration_networks": True,
        "enable_institutional_hierarchies": True,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)

    print(f"Configuration template saved to {output_file}")


def list_available_configs() -> None:
    """List all available default configurations."""
    configs = create_default_configs()

    print("Available Benchmark Configurations:")
    print("=" * 50)

    for name, config in configs.items():
        print(f"\n🔧 {name}:")
        print(f"   Query: {config.query}")
        print(f"   Target Papers: {config.target_paper_count}")
        print(f"   Output Dir: {config.output_dir}")
        print(f"   XML Cache: {config.xml_cache_dir}")


def main() -> None:
    """Main entry point for benchmark runner."""
    parser = argparse.ArgumentParser(
        description="PyEuropePMC Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run default full benchmark
  python benchmark_runner.py

  # Run a specific default configuration
  python benchmark_runner.py --config full_benchmark

  # Run with custom configuration file
  python benchmark_runner.py --config-file my_config.json

  # Create a configuration template
  python benchmark_runner.py --create-template config_template.json

  # List available configurations
  python benchmark_runner.py --list-configs

  # Run with custom parameters
  python benchmark_runner.py --papers 200 --query "(OPEN_ACCESS:y) AND cancer"
        """,
    )

    parser.add_argument(
        "--config",
        choices=list(create_default_configs().keys()),
        help="Use a predefined configuration",
    )

    parser.add_argument("--config-file", type=Path, help="Load configuration from JSON file")

    parser.add_argument(
        "--create-template", type=Path, help="Create a configuration template file and exit"
    )

    parser.add_argument(
        "--list-configs",
        action="store_true",
        help="List available default configurations and exit",
    )

    parser.add_argument("--papers", type=int, help="Override target paper count")

    parser.add_argument("--query", help="Override search query")

    parser.add_argument("--output-dir", type=Path, help="Override output directory")

    parser.add_argument(
        "--no-cache", action="store_true", help="Disable XML caching (re-download all files)"
    )

    args = parser.parse_args()

    # Handle special actions
    if args.create_template:
        save_config_template(args.create_template)
        return

    if args.list_configs:
        list_available_configs()
        return

    # Determine configuration
    if args.config_file:
        print(f"Loading configuration from {args.config_file}")
        config = load_config_from_file(args.config_file)
    elif args.config:
        print(f"Using predefined configuration: {args.config}")
        configs = create_default_configs()
        config = configs[args.config]
    else:
        print("Using default full benchmark configuration")
        configs = create_default_configs()
        config = configs["full_benchmark"]

    # Apply command-line overrides
    if args.papers:
        config.target_paper_count = args.papers
        print(f"Overriding paper count to {args.papers}")

    if args.query:
        config.query = args.query
        print(f"Overriding query to: {args.query}")

    if args.output_dir:
        config.output_dir = args.output_dir
        print(f"Overriding output directory to: {args.output_dir}")

    if args.no_cache:
        config.skip_existing_xml = False
        print("Disabling XML caching")

    # Run the benchmark
    runner = BenchmarkRunner(config)
    metrics = runner.run_full_pipeline()

    # Return appropriate exit code
    exit(1 if metrics.errors else 0)


if __name__ == "__main__":
    main()
