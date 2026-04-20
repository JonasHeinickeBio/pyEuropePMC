"""
Benchmark runner for systematic performance measurement.

Provides a flexible framework for running benchmarks on PyEuropePMC components
with detailed metrics and statistics.
"""

# mypy: ignore-errors
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
import statistics
import time
from typing import Any


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    function_name: str
    operation_type: str
    input_size: int
    execution_times: list[float]
    memory_usage: list[float] | None = None
    success_rate: float = 1.0
    error_messages: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def avg_time(self) -> float:
        """Average execution time."""
        return statistics.mean(self.execution_times)

    @property
    def median_time(self) -> float:
        """Median execution time."""
        return statistics.median(self.execution_times)

    @property
    def std_dev(self) -> float:
        """Standard deviation of execution times."""
        if len(self.execution_times) < 2:
            return 0.0
        return statistics.stdev(self.execution_times)

    @property
    def min_time(self) -> float:
        """Minimum execution time."""
        return min(self.execution_times)

    @property
    def max_time(self) -> float:
        """Maximum execution time."""
        return max(self.execution_times)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "function_name": self.function_name,
            "operation_type": self.operation_type,
            "input_size": self.input_size,
            "avg_time": self.avg_time,
            "median_time": self.median_time,
            "std_dev": self.std_dev,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "success_rate": self.success_rate,
            "error_count": len(self.error_messages),
            "metadata": self.metadata,
        }


class BenchmarkRunner:
    """
    Runner for systematic performance benchmarks.

    Provides methods to benchmark different operations and collect
    detailed performance metrics with statistical analysis.
    """

    def __init__(self, warmup_runs: int = 1, repetitions: int = 5):
        """
        Initialize the benchmark runner.

        Args:
            warmup_runs: Number of warmup runs before measurement
            repetitions: Number of times to repeat each benchmark
        """
        self.warmup_runs = warmup_runs
        self.repetitions = repetitions
        self.results: list[BenchmarkResult] = []
        self.operation_timings: dict[str, list[float]] = defaultdict(list)

    def benchmark_function(
        self,
        func: Callable,
        operation_type: str,
        input_data: Any | None = None,
        input_size: int = 1,
        **kwargs,
    ) -> BenchmarkResult:
        """
        Benchmark a single function.

        Args:
            func: Function to benchmark
            operation_type: Type of operation being benchmarked
            input_data: Input data for the function
            input_size: Size of the input (for scalability analysis)
            **kwargs: Additional arguments to pass to the function

        Returns:
            BenchmarkResult with timing and success metrics
        """
        times = []
        errors = []
        success_count = 0

        # Warmup runs
        for _ in range(self.warmup_runs):
            try:
                if input_data is not None:
                    func(input_data, **kwargs)
                else:
                    func(**kwargs)
            except Exception:
                pass  # nosec B110

        # Measurement runs
        for _ in range(self.repetitions):
            start = time.perf_counter()
            try:
                result = func(input_data, **kwargs) if input_data is not None else func(**kwargs)
                times.append(time.perf_counter() - start)
                success_count += 1
            except Exception as e:
                times.append(0.0)  # Record 0 for failed runs
                errors.append(str(e))

        success_count / self.repetitions if self.repetitions > 0 else 0.0

        result = BenchmarkResult(
            function_name=func.__name__,
            operation_type=operation_type,
            input_size=input_size,
            execution_times=times,
            error_messages=errors,
            metadata={
                "function": func.__name__,
                "module": func.__module__,
                "success_count": success_count,
                "total_repetitions": self.repetitions,
                "error_details": errors[:5],  # Keep first 5 errors
            },
        )

        self.results.append(result)
        self.operation_timings[operation_type].extend(times)

        return result

    def benchmark_search_operations(
        self,
        search_client,
        queries: list[str] | None = None,
        max_results: int = 25,
    ) -> list[BenchmarkResult]:
        """
        Benchmark search operations.

        Args:
            search_client: SearchClient instance
            queries: List of search queries (generates if None)
            max_results: Maximum results per query

        Returns:
            List of benchmark results for search operations
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        if queries is None:
            queries = TestDataGenerator.generate_test_queries(10)

        results = []
        for query in queries:
            result = self.benchmark_function(
                search_client.search,
                "search",
                input_data=query,
                input_size=len(query),
                resultType="core",
                limit=max_results,
            )
            result.metadata["query"] = query
            results.append(result)

        return results

    def benchmark_article_operations(
        self,
        article_client,
        identifiers: list[tuple[str, str]] | None = None,
    ) -> list[BenchmarkResult]:
        """
        Benchmark article retrieval operations.

        Args:
            article_client: ArticleClient instance
            identifiers: List of (source, id) tuples (generates if None)

        Returns:
            List of benchmark results for article operations
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        if identifiers is None:
            pmids = TestDataGenerator.generate_test_identifiers(10)
            identifiers = [("MED", pmid) for pmid in pmids]

        results = []
        for source, article_id in identifiers:
            result = self.benchmark_function(
                article_client.get_article_details,
                "article_retrieval",
                input_data=(source, article_id),
                input_size=len(article_id),
                resultType="core",
                format="json",
            )
            result.metadata["source"] = source
            result.metadata["article_id"] = article_id
            results.append(result)

        return results

    def benchmark_fulltext_operations(
        self,
        fulltext_client,
        pmcid: str = "PMC4590001",
    ) -> list[BenchmarkResult]:
        """
        Benchmark full-text retrieval operations.

        Args:
            fulltext_client: FullTextClient instance
            pmcid: PMCID to benchmark

        Returns:
            List of benchmark results for fulltext operations
        """
        result = self.benchmark_function(
            fulltext_client.get_fulltext,
            "fulltext_retrieval",
            input_data=pmcid,
            input_size=len(pmcid),
            format="XML",
        )
        result.metadata["pmcid"] = pmcid
        return [result]

    def benchmark_parser_operations(
        self,
        parser,
        xml_content: str,
        operations: list[str] | None = None,
    ) -> list[BenchmarkResult]:
        """
        Benchmark parsing operations.

        Args:
            parser: Parser instance
            xml_content: XML content to parse
            operations: List of operations to benchmark

        Returns:
            List of benchmark results for parsing operations
        """
        if operations is None:
            operations = ["parse", "extract_authors", "extract_metadata"]

        results = []
        for operation in operations:
            if hasattr(parser, operation):
                func = getattr(parser, operation)
                result = self.benchmark_function(
                    func,
                    "parsing",
                    input_data=xml_content,
                    input_size=len(xml_content),
                )
                result.metadata["operation"] = operation
                results.append(result)

        return results

    def benchmark_enrichment_operations(
        self,
        enricher,
        papers: list[dict] | None = None,
    ) -> list[BenchmarkResult]:
        """
        Benchmark paper enrichment operations.

        Args:
            enricher: PaperEnricher instance
            papers: List of papers to enrich (generates if None)

        Returns:
            List of benchmark results for enrichment operations
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        if papers is None:
            papers = TestDataGenerator.generate_test_papers(5)

        result = self.benchmark_function(
            enricher.enrich_paper,
            "enrichment",
            input_data=papers[0].get("doi", papers[0].get("pmid", "test")),
            input_size=len(papers),
        )
        result.metadata["papers_count"] = len(papers)
        return [result]

    def benchmark_batch_operations(
        self,
        enricher,
        batch_size: int = 10,
    ) -> list[BenchmarkResult]:
        """
        Benchmark batch enrichment operations.

        Args:
            enricher: PaperEnricher instance
            batch_size: Number of papers in batch

        Returns:
            List of benchmark results for batch operations
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        papers = TestDataGenerator.generate_test_papers(batch_size)
        identifiers = [p.get("doi") or p.get("pmid") for p in papers]

        result = self.benchmark_function(
            enricher.enrich_papers,
            "batch_enrichment",
            input_data=identifiers,
            input_size=len(identifiers),
        )
        result.metadata["batch_size"] = batch_size
        return [result]

    def benchmark_query_builder(
        self,
        query_builder,
        complexity: str = "simple",
    ) -> list[BenchmarkResult]:
        """
        Benchmark query building operations.

        Args:
            query_builder: QueryBuilder instance
            complexity: Query complexity level

        Returns:
            List of benchmark results for query building
        """
        from pyeuropepmc.benchmarking.test_data import TestDataGenerator

        queries = TestDataGenerator.generate_test_queries(10, complexity)

        times = []
        for query in queries:
            start = time.perf_counter()
            try:
                # Rebuild query from string
                query_builder.from_string(query)
                times.append(time.perf_counter() - start)
            except Exception:
                times.append(0.0)

        result = BenchmarkResult(
            function_name="query_building",
            operation_type="query_building",
            input_size=len(queries),
            execution_times=times,
            metadata={
                "complexity": complexity,
                "queries_processed": len(queries),
            },
        )

        self.results.append(result)
        return [result]

    def get_statistics(self) -> dict[str, Any]:
        """
        Get aggregate statistics for all benchmarks.

        Returns:
            Dictionary with aggregate statistics
        """
        if not self.results:
            return {}

        stats = {
            "total_benchmarks": len(self.results),
            "total_operations": sum(r.input_size for r in self.results),
            "overall_avg_time": statistics.mean([r.avg_time for r in self.results]),
            "overall_std_dev": statistics.stdev([r.avg_time for r in self.results])
            if len(self.results) > 1
            else 0.0,
            "success_rate": statistics.mean([r.success_rate for r in self.results]),
            "by_operation": {},
        }

        for operation, times in self.operation_timings.items():
            by_op = stats["by_operation"]
            if not isinstance(by_op, dict):
                raise TypeError("by_operation must be a dict")
            by_op[operation] = {
                "count": len(times),
                "avg_time": statistics.mean(times),
                "median_time": statistics.median(times),
                "std_dev": statistics.stdev(times) if len(times) > 1 else 0.0,
                "min_time": min(times),
                "max_time": max(times),
            }

        print("\n" + "=" * 70)
        return stats
