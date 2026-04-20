"""
Example script demonstrating benchmarking capabilities.

Run with: python benchmarking_example.py
"""

from pyeuropepmc import ArticleClient, SearchClient
from pyeuropepmc.benchmarking import (
    BenchmarkRunner,
    BottleneckDetector,
    JSONReportGenerator,
    TestDataGenerator,
    TextReportGenerator,
)
from pyeuropepmc.enrichment import EnrichmentConfig, PaperEnricher


def main() -> None:
    """Run benchmarking examples."""
    print("=" * 70)
    print("PyEuropePMC Benchmarking Example")
    print("=" * 70)

    # Initialize clients
    article_client = ArticleClient()
    search_client = SearchClient()

    # Example 1: Simple search benchmark
    print("\n[Example 1] Benchmarking Search Operations")
    print("-" * 70)

    runner = BenchmarkRunner(warmup_runs=1, repetitions=3)
    generator = TestDataGenerator()

    # Generate test queries
    queries = generator.generate_test_queries(3, complexity="simple")
    print(f"Generated {len(queries)} test queries")

    # Run benchmarks
    search_results = runner.benchmark_search_operations(search_client, queries)

    # Print summary
    runner.get_statistics()

    # Example 2: Article retrieval benchmark
    print("\n[Example 2] Benchmarking Article Retrieval")
    print("-" * 70)

    # Get test identifiers
    identifiers = [("MED", generator.generate_random_pmid()) for _ in range(3)]
    article_results = runner.benchmark_article_operations(article_client, identifiers)

    # Analyze results
    all_results = search_results + article_results
    results_dict = [r.to_dict() for r in all_results]

    detector = BottleneckDetector(results_dict)
    bottlenecks = detector.get_top_bottlenecks(n=5)

    if bottlenecks:
        print("\nTop Bottlenecks Found:")
        for i, bottleneck in enumerate(bottlenecks, 1):
            print(
                f"  {i}. {bottleneck['function']} - "
                f"{bottleneck['avg_time']:.6f}s (severity: {bottleneck['severity']})"
            )

    # Example 3: Report generation
    print("\n[Example 3] Generating Reports")
    print("-" * 70)

    # Generate text report
    text_gen = TextReportGenerator(results_dict)
    text_report = text_gen.generate()
    print("\nText Report Preview:")
    print(text_report[:500] + "...")

    # Save JSON report
    json_gen = JSONReportGenerator(results_dict)
    json_gen.save("benchmark_results.json")
    print("\nJSON report saved to benchmark_results.json")

    # Example 4: Batch operations benchmark
    print("\n[Example 4] Benchmarking Batch Operations")
    print("-" * 70)

    # Setup enrichment config (with minimal enabled for speed)
    config = EnrichmentConfig(
        enable_crossref=False,
        enable_semantic_scholar=False,
    )
    enricher = PaperEnricher(config)

    # Generate test papers
    _ = generator.generate_test_papers(2)
    batch_results = runner.benchmark_batch_operations(enricher, batch_size=2)

    # Print results
    for result in batch_results:
        print(f"\nBatch enrichment (size={result.input_size}):")
        print(f"  Average time: {result.avg_time:.6f}s")
        print(f"  Success rate: {result.success_rate * 100:.2f}%")

    print("\n" + "=" * 70)
    print("Benchmarking Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
