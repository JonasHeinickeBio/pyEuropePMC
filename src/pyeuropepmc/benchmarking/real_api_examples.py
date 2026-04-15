"""
Real API testing examples.

Demonstrates real API usage with actual Europe PMC data.
"""

import logging
from pathlib import Path

from pyeuropepmc.benchmarking import BottleneckDetector, RealAPITester

logging.basicConfig(level=logging.INFO)


def example_basic_real_api():
    """Basic example of real API testing."""
    print("=" * 70)
    print("Example 1: Basic Real API Test")
    print("=" * 70)

    # Initialize tester
    tester = RealAPITester()

    # Run a single real search
    result = tester.test_real_search("cancer treatment precision medicine")

    print("\nSearch Results:")
    print(f"  Query: {result.metadata.get('query')}")
    print(f"  Avg Time: {result.avg_time:.6f}s")
    print(f"  Std Dev: {result.std_dev:.6f}s")
    print(f"  Success Rate: {result.success_rate * 100:.2f}%")

    # Run article retrieval
    article_result = tester.test_real_article_retrieval("25883711")
    print("\nArticle Retrieval Results:")
    print(f"  PMID: {article_result.metadata.get('pmid')}")
    print(f"  Avg Time: {article_result.avg_time:.6f}s")


def example_full_benchmark():
    """Run a full real API benchmark suite."""
    print("\n" + "=" * 70)
    print("Example 2: Full Real API Benchmark")
    print("=" * 70)

    tester = RealAPITester()

    # Run full benchmark
    summary = tester.run_full_benchmark()

    print("\nBenchmark Summary:")
    print(f"  Total Operations: {summary.get('total_benchmarks', 0)}")
    print(f"  Overall Avg Time: {summary.get('overall_avg_time', 0):.6f}s")
    print(f"  Success Rate: {summary.get('success_rate', 0) * 100:.2f}%")


def example_bottleneck_analysis():
    """Example of bottleneck analysis with real API data."""
    print("\n" + "=" * 70)
    print("Example 3: Real API Bottleneck Analysis")
    print("=" * 70)

    tester = RealAPITester()

    # Run batch search
    results = tester.test_real_batch_search(count=5)

    # Analyze for bottlenecks
    results_dict = [r.to_dict() for r in results]
    detector = BottleneckDetector(results_dict)

    bottlenecks = detector.get_top_bottlenecks(n=5)

    if bottlenecks:
        print("\nTop Bottlenecks Found:")
        for i, bottleneck in enumerate(bottlenecks, 1):
            print(f"  {i}. {bottleneck['function']} ({bottleneck['operation_type']})")
            print(f"     Avg Time: {bottleneck['avg_time']:.6f}s")
            print(f"     Severity: {bottleneck['severity']}")
    else:
        print("\nNo significant bottlenecks detected.")

    # Print full bottleneck report
    print("\nFull Bottleneck Report:")
    detector.print_report()


def example_report_generation():
    """Example of report generation with real API data."""
    print("\n" + "=" * 70)
    print("Example 4: Real API Report Generation")
    print("=" * 70)

    tester = RealAPITester()

    # Run some tests
    results = tester.test_real_batch_search(count=5)

    # Save reports
    saved_files = tester.save_results(results, "real_api_benchmark")

    print("\nSaved Reports:")
    for fmt, filepath in saved_files.items():
        print(f"  {fmt.upper()}: {filepath}")

    # Print one of the reports
    if "text" in saved_files:
        print(f"\nText Report Preview ({saved_files['text']}):")
        print("-" * 50)
        content = Path(saved_files["text"]).read_text()
        print(content[:1000] + "..." if len(content) > 1000 else content)


def example_scalability():
    """Example of scalability testing."""
    print("\n" + "=" * 70)
    print("Example 5: Scalability Testing")
    print("=" * 70)

    tester = RealAPITester()

    # Test with different sizes
    sizes = [5, 10, 20]  # Limited for demo
    results = tester.run_scalability_test(sizes)

    print("\nScalability Test Complete")
    print(f"Tested sizes: {list(results.keys())}")


def example_filtered_search():
    """Example of filtered search testing."""
    print("\n" + "=" * 70)
    print("Example 6: Filtered Search Testing")
    print("=" * 70)

    tester = RealAPITester()

    # Test with various filters
    results = tester.test_real_search_with_filters()

    print("\nFiltered Search Results:")
    for i, result in enumerate(results):
        filters = result.metadata.get("filters", {})
        print(f"  Filter Combo {i}: {filters}")
        print(f"    Avg Time: {result.avg_time:.6f}s")

    # Save results
    tester.save_results(results, "filtered_search_benchmark")


def example_author_journal_search():
    """Example of author and journal specific searches."""
    print("\n" + "=" * 70)
    print("Example 7: Author and Journal Search Testing")
    print("=" * 70)

    tester = RealAPITester()

    # Author searches
    print("\nAuthor Searches:")
    author_results = tester.test_real_search_author()
    for result in author_results:
        print(f"  {result.metadata.get('query')}: {result.avg_time:.6f}s")

    # Journal searches
    print("\nJournal Searches:")
    journal_results = tester.test_real_search_journal()
    for result in journal_results:
        print(f"  {result.metadata.get('query')}: {result.avg_time:.6f}s")

    # Save combined
    all_results = author_results + journal_results
    tester.save_results(all_results, "author_journal_search")


def example_citation_reference():
    """Example of citation and reference retrieval testing."""
    print("\n" + "=" * 70)
    print("Example 8: Citation and Reference Retrieval")
    print("=" * 70)

    tester = RealAPITester()

    # Citation retrieval
    citation_result = tester.test_real_citation_retrieval()
    print("\nCitation Retrieval:")
    print(f"  PMID: {citation_result.metadata.get('pmid')}")
    print(f"  Avg Time: {citation_result.avg_time:.6f}s")

    # Reference retrieval
    ref_result = tester.test_real_reference_retrieval()
    print("\nReference Retrieval:")
    print(f"  PMID: {ref_result.metadata.get('pmid')}")
    print(f"  Avg Time: {ref_result.avg_time:.6f}s")

    # Combined
    combined = [citation_result, ref_result]
    tester.save_results(combined, "citation_reference")


def example_doi_lookup():
    """Example of DOI-based lookup testing."""
    print("\n" + "=" * 70)
    print("Example 9: DOI Lookup Testing")
    print("=" * 70)

    tester = RealAPITester()

    # DOI lookup
    result = tester.test_real_doi_lookup("10.1093/nar/gkv112")
    print("\nDOI Lookup:")
    print(f"  DOI: {result.metadata.get('doi')}")
    print(f"  Avg Time: {result.avg_time:.6f}s")

    # Save
    tester.save_results([result], "doi_lookup")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("PyEuropePMC Real API Testing Examples")
    print("=" * 70)
    print("\nThese examples perform real API calls to Europe PMC and retrieve")
    print("actual papers and search results.")
    print("\nNote: Real API calls may take longer due to network latency.")
    print("=" * 70)

    # Run selected examples
    example_basic_real_api()
    example_full_benchmark()
    example_bottleneck_analysis()
    example_report_generation()
    example_scalability()
    example_filtered_search()
    example_author_journal_search()
    example_citation_reference()
    example_doi_lookup()

    print("\n" + "=" * 70)
    print("All Examples Complete!")
    print("=" * 70)
    print("\nCheck the benchmark_results directory for generated reports.")
    print("=" * 70)


if __name__ == "__main__":
    main()
