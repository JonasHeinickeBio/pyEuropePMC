"""
Real API benchmark for Europe PMC operations.

Performs actual API calls to Europe PMC and retrieves real papers
for realistic performance benchmarking.
"""

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any

from pyeuropepmc import ArticleClient, SearchClient
from pyeuropepmc.benchmarking.benchmark_runner import BenchmarkResult, BenchmarkRunner
from pyeuropepmc.benchmarking.test_data import TestDataGenerator
from pyeuropepmc.clients.fulltext import FullTextClient


@dataclass
class RealAPIBenchmarkResult:
    """Result of a real API benchmark run with actual paper data."""

    benchmark_result: BenchmarkResult
    paper_data: dict[str, Any] | None = None
    paper_count: int = 0
    api_url: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            **self.benchmark_result.to_dict(),
            "paper_count": self.paper_count,
            "api_url": self.api_url,
            "timestamp": self.timestamp,
        }
        if self.paper_data:
            result["paper_data_sample"] = {
                "id": self.paper_data.get("id", "N/A"),
                "title": self.paper_data.get("title", "N/A")[:100] + "..."
                if self.paper_data.get("title", "")
                else "N/A",
                "source": self.paper_data.get("source", "N/A"),
            }
        return result


class RealAPIBenchmarkRunner(BenchmarkRunner):
    """
    Benchmark runner that performs actual API calls to Europe PMC.

    Retrieves real papers and performs real searches for authentic
    performance measurement.
    """

    def __init__(self, warmup_runs: int = 1, repetitions: int = 3, **kwargs):
        """
        Initialize the real API benchmark runner.

        Args:
            warmup_runs: Number of warmup runs before measurement
            repetitions: Number of times to repeat each benchmark
            **kwargs: Additional arguments for BenchmarkRunner
        """
        super().__init__(warmup_runs=warmup_runs, repetitions=repetitions, **kwargs)
        self.search_client = SearchClient()
        self.article_client = ArticleClient()
        self.fulltext_client = FullTextClient()

    def benchmark_real_search(
        self, query: str | None = None, max_results: int = 25
    ) -> RealAPIBenchmarkResult:
        """
        Benchmark real search operations with actual API calls.

        Args:
            query: Search query (generates if None)
            max_results: Maximum results to fetch

        Returns:
            RealAPIBenchmarkResult with paper data
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        if query is None:
            queries = TestDataGenerator.generate_test_queries(1, complexity="realistic")
            query = queries[0]

        def search_func(q: str) -> dict:
            return self.search_client.search(
                query=q,
                resultType="core",
                limit=max_results,
            )

        # Warmup run
        for _ in range(self.warmup_runs):
            with contextlib.suppress(Exception):  # nosec B110
                search_func(query)

        # Measurement runs
        times = []
        papers = None
        error_messages = []
        success_count = 0

        for _i in range(self.repetitions):
            start = time.perf_counter()
            try:
                papers = search_func(query)
                times.append(time.perf_counter() - start)
                success_count += 1
            except Exception as e:
                times.append(0.0)
                error_messages.append(str(e))

        success_count / self.repetitions if self.repetitions > 0 else 0.0

        benchmark_result = BenchmarkResult(
            function_name="real_search",
            operation_type="real_api_search",
            input_size=len(query),
            execution_times=times,
            error_messages=error_messages,
            metadata={
                "query": query,
                "max_results": max_results,
                "success_count": success_count,
                "total_repetitions": self.repetitions,
            },
        )

        self.results.append(benchmark_result)

        paper_data = None
        paper_count = 0
        if papers and "results" in papers:
            paper_count = len(papers["results"])
            if paper_count > 0:
                paper_data = papers["results"][0]

        return RealAPIBenchmarkResult(
            benchmark_result=benchmark_result,
            paper_data=paper_data,
            paper_count=paper_count,
            api_url=f"https://europepmc.org/search?query={query}",
        )

    def benchmark_real_article_retrieval(self, pmid: str | None = None) -> RealAPIBenchmarkResult:
        """
        Benchmark real article retrieval with actual API calls.

        Args:
            pmid: PubMed ID (generates if None)

        Returns:
            RealAPIBenchmarkResult with paper data
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        if pmid is None:
            pmid = TestDataGenerator.generate_random_pmid()

        def article_func(source: str, article_id: str) -> dict:
            return self.article_client.get_article_details(
                source=source,
                article_id=article_id,
                resultType="core",
                format="json",
            )

        # Warmup run
        for _ in range(self.warmup_runs):
            with contextlib.suppress(Exception):  # nosec B110
                article_func("MED", pmid)

        # Measurement runs
        times = []
        paper = None
        error_messages = []
        success_count = 0

        for _i in range(self.repetitions):
            start = time.perf_counter()
            try:
                paper = article_func("MED", pmid)
                times.append(time.perf_counter() - start)
                success_count += 1
            except Exception as e:
                times.append(0.0)
                error_messages.append(str(e))

        success_count / self.repetitions if self.repetitions > 0 else 0.0

        benchmark_result = BenchmarkResult(
            function_name="real_article_retrieval",
            operation_type="real_api_article_retrieval",
            input_size=len(pmid),
            execution_times=times,
            error_messages=error_messages,
            metadata={
                "source": "MED",
                "pmid": pmid,
                "success_count": success_count,
                "total_repetitions": self.repetitions,
            },
        )

        self.results.append(benchmark_result)

        paper_data = None
        if paper and "response" in paper:
            paper_data = paper["response"]

        return RealAPIBenchmarkResult(
            benchmark_result=benchmark_result,
            paper_data=paper_data,
            paper_count=1 if paper_data else 0,
            api_url=f"https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/{pmid}",
        )

    def benchmark_real_fulltext_retrieval(
        self, pmcid: str | None = None
    ) -> RealAPIBenchmarkResult:
        """
        Benchmark real full-text retrieval with actual API calls.

        Args:
            pmcid: PubMed Central ID (generates if None)

        Returns:
            RealAPIBenchmarkResult with full-text data
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        if pmcid is None:
            pmcid = TestDataGenerator.generate_random_pmcid()

        def fulltext_func(pmcid: str) -> str:
            return self.fulltext_client.get_fulltext_content(
                pmcid=pmcid,
                format_type="xml",
            )

        # Warmup run
        for _ in range(self.warmup_runs):
            with contextlib.suppress(Exception):  # nosec B110
                fulltext_func(pmcid)

        # Measurement runs
        times = []
        fulltext = None
        error_messages = []
        success_count = 0

        for _i in range(self.repetitions):
            start = time.perf_counter()
            try:
                fulltext = fulltext_func(pmcid)
                times.append(time.perf_counter() - start)
                success_count += 1
            except Exception as e:
                times.append(0.0)
                error_messages.append(str(e))

        success_count / self.repetitions if self.repetitions > 0 else 0.0

        benchmark_result = BenchmarkResult(
            function_name="real_fulltext_retrieval",
            operation_type="real_api_fulltext_retrieval",
            input_size=len(pmcid),
            execution_times=times,
            error_messages=error_messages,
            metadata={
                "pmcid": pmcid,
                "success_count": success_count,
                "total_repetitions": self.repetitions,
            },
        )

        self.results.append(benchmark_result)

        return RealAPIBenchmarkResult(
            benchmark_result=benchmark_result,
            paper_data={"pmcid": pmcid, "has_fulltext": fulltext is not None},
            paper_count=1 if fulltext else 0,
            api_url=f"https://www.ebi.ac.uk/europepmc/webservices/rest/article/PMC/{pmcid}/fullTextXML",
        )

    def benchmark_multiple_real_papers(self, count: int = 10) -> list[RealAPIBenchmarkResult]:
        """
        Benchmark multiple real paper retrievals.

        Args:
            count: Number of papers to retrieve

        Returns:
            List of RealAPIBenchmarkResult objects
        """
        results = []
        for _i in range(count):
            pmid = TestDataGenerator.generate_random_pmid()
            result = self.benchmark_real_article_retrieval(pmid)
            results.append(result)

        return results

    def print_real_api_summary(self) -> None:
        """Print summary of real API benchmarks."""
        print("\n" + "=" * 70)
        print("REAL API BENCHMARK SUMMARY")
        print("=" * 70)

        real_api_results = [
            r for r in self.results if "real_api" in getattr(r, "operation_type", "")
        ]

        if not real_api_results:
            print("\nNo real API benchmarks found.")
            return

        print(f"\nTotal real API benchmarks: {len(real_api_results)}")

        for result in real_api_results:
            print(f"\n{result.function_name}:")
            print(f"  Avg time: {result.avg_time:.6f}s")
            print(f"  Success rate: {result.success_rate * 100:.2f}%")
            if hasattr(result, "metadata"):
                if "query" in result.metadata:
                    print(f"  Query: {result.metadata['query'][:60]}...")
                if "pmid" in result.metadata:
                    print(f"  PMID: {result.metadata['pmid']}")
                if "pmcid" in result.metadata:
                    print(f"  PMCID: {result.metadata['pmcid']}")

        print("\n" + "=" * 70)


def main():
    """Run real API benchmarks."""
    print("=" * 70)
    print("Real API Benchmark - Europe PMC")
    print("=" * 70)

    runner = RealAPIBenchmarkRunner(warmup_runs=1, repetitions=2)

    # Real search benchmark
    print("\n[1] Benchmarking Real Search Operations")
    print("-" * 70)
    search_result = runner.benchmark_real_search(
        query="cancer immunotherapy",
        max_results=25,
    )
    print(f"Search query: {search_result.benchmark_result.metadata['query']}")
    print(f"Results returned: {search_result.paper_count}")
    print(f"Average time: {search_result.benchmark_result.avg_time:.6f}s")
    print(f"Success rate: {search_result.benchmark_result.success_rate * 100:.2f}%")

    if search_result.paper_data:
        print("\nSample paper:")
        if search_result.paper_data.get("title"):
            title = search_result.paper_data["title"]
            print(f"  Title: {title[:100]}..." if len(title) > 100 else f"  Title: {title}")
        if search_result.paper_data.get("source"):
            print(f"  Source: {search_result.paper_data['source']}")
        if search_result.paper_data.get("pmid"):
            print(f"  PMID: {search_result.paper_data['pmid']}")

    # Real article retrieval benchmark
    print("\n[2] Benchmarking Real Article Retrieval")
    print("-" * 70)

    # Use a known valid PMID
    known_pmid = "29038167"  # A known paper in Europe PMC
    article_result = runner.benchmark_real_article_retrieval(known_pmid)
    print(f"Retrieved PMID: {known_pmid}")
    print(f"Average time: {article_result.benchmark_result.avg_time:.6f}s")
    print(f"Success rate: {article_result.benchmark_result.success_rate * 100:.2f}%")

    if article_result.paper_data:
        print("\nPaper details:")
        if article_result.paper_data.get("title"):
            title = article_result.paper_data["title"]
            print(f"  Title: {title[:100]}..." if len(title) > 100 else f"  Title: {title}")
        if article_result.paper_data.get("authorList"):
            authors = article_result.paper_data["authorList"].get("author", [])
            print(f"  Authors: {len(authors)}")
        if article_result.paper_data.get("journalInfo"):
            print(f"  Journal: {article_result.paper_data['journalInfo']}")

    # Multiple papers benchmark
    print("\n[3] Benchmarking Multiple Real Paper Retrievals")
    print("-" * 70)
    multi_results = runner.benchmark_multiple_real_papers(count=5)

    avg_time = sum(r.benchmark_result.avg_time for r in multi_results) / len(multi_results)
    print(f"Retrieved {len(multi_results)} papers")
    print(f"Average time per paper: {avg_time:.6f}s")
    success_rate = (
        sum(r.benchmark_result.success_rate for r in multi_results) / len(multi_results) * 100
    )
    print(f"Overall success rate: {success_rate:.2f}%")

    # Print full summary
    runner.print_real_api_summary()

    print("\nReal API Benchmarking Complete!")


if __name__ == "__main__":
    main()
