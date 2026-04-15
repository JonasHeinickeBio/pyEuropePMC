"""
Real API tests for PyEuropePMC benchmarking.

Performs actual searches and retrieves real papers from Europe PMC API
for realistic performance measurement.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pyeuropepmc.benchmarking.benchmark_runner import BenchmarkResult, BenchmarkRunner
from pyeuropepmc.benchmarking.test_data import TestDataGenerator

logger = logging.getLogger(__name__)


class RealAPITester:
    """
    Tests real API operations using actual Europe PMC requests.

    This class performs genuine API calls to Europe PMC and measures
    performance with realistic data.
    """

    def __init__(
        self,
        search_client=None,
        article_client=None,
        fulltext_client=None,
        output_dir: str | Path | None = None,
    ):
        """
        Initialize the real API tester.

        Args:
            search_client: SearchClient instance (optional)
            article_client: ArticleClient instance (optional)
            fulltext_client: FullTextClient instance (optional)
            output_dir: Directory to save test results (optional)
        """
        from pyeuropepmc import ArticleClient, FullTextClient, SearchClient

        self.search_client = search_client or SearchClient()
        self.article_client = article_client or ArticleClient()
        self.fulltext_client = fulltext_client or FullTextClient()
        self.output_dir = Path(output_dir) if output_dir else Path("benchmark_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.benchmark_runner = BenchmarkRunner(warmup_runs=1, repetitions=3)

        logger.info("RealAPITester initialized")
        logger.info(f"Output directory: {self.output_dir}")

    def test_real_search(self, query: str | None = None) -> dict[str, Any]:
        """
        Perform a real search and benchmark it.

        Args:
            query: Search query (uses default if None)

        Returns:
            Benchmark results dictionary
        """
        if query is None:
            query = "cancer treatment precision medicine"

        logger.info(f"Testing real search with query: {query}")

        result = self.benchmark_runner.benchmark_function(
            self.search_client.search,
            "real_search",
            input_data=query,
            input_size=len(query),
            resultType="core",
            limit=25,
        )

        # Save raw API response for analysis
        result.metadata["query"] = query

        return result

    def test_real_article_retrieval(self, pmid: str | None = None) -> dict[str, Any]:
        """
        Retrieve a real article and benchmark it.

        Args:
            pmid: PMID to retrieve (uses known valid PMID if None)

        Returns:
            Benchmark results dictionary
        """
        if pmid is None:
            pmid = "25883711"  # Known valid PMID

        logger.info(f"Testing real article retrieval with PMID: {pmid}")

        result = self.benchmark_runner.benchmark_function(
            self.article_client.get_article_details,
            "real_article_retrieval",
            input_data=pmid,
            input_size=len(pmid),
            resultType="core",
            format="json",
        )

        result.metadata["pmid"] = pmid

        return result

    def test_real_fulltext_retrieval(self, pmcid: str | None = None) -> dict[str, Any]:
        """
        Retrieve full text and benchmark it.

        Args:
            pmcid: PMCID to retrieve (uses known valid PMCID if None)

        Returns:
            Benchmark results dictionary
        """
        if pmcid is None:
            pmcid = "PMC4590001"  # Known valid PMCID

        logger.info(f"Testing real fulltext retrieval with PMCID: {pmcid}")

        result = self.benchmark_runner.benchmark_function(
            self.fulltext_client.get_fulltext,
            "real_fulltext_retrieval",
            input_data=pmcid,
            input_size=len(pmcid),
            format="XML",
        )

        result.metadata["pmcid"] = pmcid

        return result

    def test_real_batch_search(
        self, queries: list[str] | None = None, count: int = 10
    ) -> list[dict[str, Any]]:
        """
        Perform multiple real searches in batch.

        Args:
            queries: List of queries (generates if None)
            count: Number of queries if generating

        Returns:
            List of benchmark results
        """
        if queries is None:
            generator = TestDataGenerator()
            queries = generator.generate_test_queries(count, complexity="simple")

        logger.info(f"Testing real batch search with {len(queries)} queries")

        results = []
        for i, query in enumerate(queries):
            result = self.benchmark_runner.benchmark_function(
                self.search_client.search,
                "real_batch_search",
                input_data=query,
                input_size=len(query),
                resultType="core",
                limit=25,
            )
            result.metadata["query"] = query
            result.metadata["query_index"] = i
            results.append(result)

        return results

    def test_real_article_bulk(self, count: int = 10) -> list[dict[str, Any]]:
        """
        Retrieve multiple real articles in bulk.

        Args:
            count: Number of articles to retrieve

        Returns:
            List of benchmark results
        """
        # Use a few known valid PMIDs and repeat
        known_pmids = [
            "25883711",
            "25777971",
            "25666075",
            "25572492",
            "25471057",
            "25380133",
            "25286638",
            "25186639",
            "25086290",
            "24985647",
        ]

        # Repeat if needed
        pmids = (known_pmids * (count // len(known_pmids) + 1))[:count]

        logger.info(f"Testing real bulk article retrieval with {len(pmids)} articles")

        results = []
        for i, pmid in enumerate(pmids):
            result = self.benchmark_runner.benchmark_function(
                self.article_client.get_article_details,
                "real_bulk_article",
                input_data=pmid,
                input_size=len(pmid),
                resultType="core",
                format="json",
            )
            result.metadata["pmid"] = pmid
            result.metadata["article_index"] = i
            results.append(result)

        return results

    def test_real_search_pagination(
        self, query: str | None = None, pages: int = 5, per_page: int = 25
    ) -> list[dict[str, Any]]:
        """
        Test search with pagination.

        Args:
            query: Search query
            pages: Number of pages to retrieve
            per_page: Results per page

        Returns:
            List of benchmark results for each page
        """
        if query is None:
            query = "cancer treatment"

        logger.info(f"Testing real search pagination: {pages} pages, {per_page} per page")

        results = []
        for page in range(pages):
            # Calculate cursor mark for pagination

            result = self.benchmark_runner.benchmark_function(
                self.search_client.search,
                "real_search_pagination",
                input_data=query,
                input_size=len(query),
                resultType="core",
                limit=per_page,
            )
            result.metadata["query"] = query
            result.metadata["page"] = page
            result.metadata["per_page"] = per_page
            results.append(result)

        return results

    def test_real_search_with_filters(self) -> list[dict[str, Any]]:
        """
        Test search with various filter combinations.

        Returns:
            List of benchmark results for filtered searches
        """
        filter_combinations = [
            {"query": "cancer", "filters": {"open_access": "Y"}},
            {"query": "cancer", "filters": {"has_abstract": "Y"}},
            {"query": "cancer", "filters": {"open_access": "Y", "has_abstract": "Y"}},
            {"query": "precision medicine", "filters": {"open_access": "Y"}},
        ]

        results = []
        for i, combo in enumerate(filter_combinations):
            filters = combo["filters"]
            result = self.benchmark_runner.benchmark_function(
                self.search_client.search,
                "real_search_filtered",
                input_data=combo["query"],
                input_size=len(combo["query"]),
                resultType="core",
                limit=25,
                **filters,  # type: ignore[arg-type]
            )
            result.metadata["query"] = combo["query"]
            result.metadata["filters"] = combo["filters"]
            result.metadata["filter_combo_index"] = i
            results.append(result)

        return results

    def test_real_search_author(self) -> list[dict[str, Any]]:
        """
        Test search by author names.

        Returns:
            List of benchmark results for author searches
        """
        author_queries = [
            "Smith J[Author]",
            "Johnson M[Author]",
            "Williams R[Author]",
        ]

        results = []
        for query in author_queries:
            result = self.benchmark_runner.benchmark_function(
                self.search_client.search,
                "real_search_author",
                input_data=query,
                input_size=len(query),
                resultType="core",
                limit=25,
            )
            result.metadata["query"] = query
            results.append(result)

        return results

    def test_real_search_journal(self) -> list[dict[str, Any]]:
        """
        Test search by journal names.

        Returns:
            List of benchmark results for journal searches
        """
        journal_queries = [
            '("Nucleic Acids Research"[Journal])',
            '("Nature"[Journal])',
            '("Cell"[Journal])',
        ]

        results = []
        for query in journal_queries:
            result = self.benchmark_runner.benchmark_function(
                self.search_client.search,
                "real_search_journal",
                input_data=query,
                input_size=len(query),
                resultType="core",
                limit=25,
            )
            result.metadata["query"] = query
            results.append(result)

        return results

    def test_real_citation_retrieval(self) -> dict[str, Any]:
        """
        Test citation retrieval for a real article.

        Returns:
            Benchmark results dictionary
        """
        pmid = "25883711"  # Article with known citations

        logger.info(f"Testing real citation retrieval for PMID: {pmid}")

        result = self.benchmark_runner.benchmark_function(
            self.article_client.get_citations,
            "real_citation_retrieval",
            input_data=pmid,
            input_size=len(pmid),
            resultType="core",
            limit=25,
        )

        result.metadata["pmid"] = pmid

        return result

    def test_real_reference_retrieval(self) -> dict[str, Any]:
        """
        Test reference retrieval for a real article.

        Returns:
            Benchmark results dictionary
        """
        pmid = "25883711"  # Article with known references

        logger.info(f"Testing real reference retrieval for PMID: {pmid}")

        result = self.benchmark_runner.benchmark_function(
            self.article_client.get_references,
            "real_reference_retrieval",
            input_data=pmid,
            input_size=len(pmid),
            resultType="core",
            limit=25,
        )

        result.metadata["pmid"] = pmid

        return result

    def test_real_doi_lookup(self, doi: str | None = None) -> dict[str, Any]:
        """
        Test DOI-based article lookup.

        Args:
            doi: DOI to look up

        Returns:
            Benchmark results dictionary
        """
        if doi is None:
            # Use a known DOI
            doi = "10.1093/nar/gkv112"

        logger.info(f"Testing real DOI lookup: {doi}")

        result = self.benchmark_runner.benchmark_function(
            self.article_client.get_article_details,
            "real_doi_lookup",
            input_data=("DOI", doi),
            input_size=len(doi),
            resultType="core",
            format="json",
        )

        result.metadata["doi"] = doi
        result.metadata["source"] = "DOI"

        return result

    def run_full_benchmark(self) -> dict[str, Any]:
        """
        Run a comprehensive real API benchmark suite.

        Returns:
            Complete benchmark results dictionary
        """
        logger.info("=" * 70)
        logger.info("Running Full Real API Benchmark Suite")
        logger.info("=" * 70)

        all_results = []

        # Test 1: Simple search
        logger.info("\n[Test 1] Simple Search")
        result = self.test_real_search()
        all_results.append(result)

        # Test 2: Article retrieval
        logger.info("\n[Test 2] Article Retrieval")
        result = self.test_real_article_retrieval()
        all_results.append(result)

        # Test 3: Batch search (small)
        logger.info("\n[Test 3] Batch Search (5 queries)")
        results = self.test_real_batch_search(count=5)
        all_results.extend(results)

        # Test 4: Bulk article retrieval (small)
        logger.info("\n[Test 4] Bulk Article Retrieval (5 articles)")
        results = self.test_real_article_bulk(count=5)
        all_results.extend(results)

        # Test 5: Filtered search
        logger.info("\n[Test 5] Filtered Search")
        results = self.test_real_search_with_filters()
        all_results.extend(results)

        # Test 6: Citation retrieval
        logger.info("\n[Test 6] Citation Retrieval")
        result = self.test_real_citation_retrieval()
        all_results.append(result)

        # Test 7: DOI lookup
        logger.info("\n[Test 7] DOI Lookup")
        result = self.test_real_doi_lookup()
        all_results.append(result)

        # Generate summary statistics
        self.benchmark_runner.results = all_results
        summary = self.benchmark_runner.get_statistics()

        # Print summary
        self.benchmark_runner.print_summary()

        # Save results
        self.save_results(all_results, "full_benchmark")

        logger.info("=" * 70)
        logger.info("Full Benchmark Complete")
        logger.info("=" * 70)

        return summary

    def save_results(self, results: list, name: str = "benchmark_results") -> dict[str, str]:
        """
        Save benchmark results to files.

        Args:
            results: List of BenchmarkResult objects
            name: Base name for output files

        Returns:
            Dictionary of saved file paths
        """
        from pyeuropepmc.benchmarking.report_generators import (
            CSVReportGenerator,
            JSONReportGenerator,
            TextReportGenerator,
        )

        results_dict = [r.to_dict() for r in results]

        saved = {}

        # JSON
        json_path = self.output_dir / f"{name}.json"
        json_gen = JSONReportGenerator(results_dict)
        json_gen.save(json_path)
        saved["json"] = str(json_path)
        logger.info(f"Saved JSON report to: {json_path}")

        # CSV
        csv_path = self.output_dir / f"{name}.csv"
        csv_gen = CSVReportGenerator(results_dict)
        csv_gen.save(csv_path)
        saved["csv"] = str(csv_path)
        logger.info(f"Saved CSV report to: {csv_path}")

        # Text
        text_path = self.output_dir / f"{name}.txt"
        text_gen = TextReportGenerator(results_dict)
        text_gen.save(text_path)
        saved["text"] = str(text_path)
        logger.info(f"Saved text report to: {text_path}")

        # Save raw results metadata
        metadata_path = self.output_dir / f"{name}_metadata.json"
        metadata = {
            "timestamp": self.benchmark_runner._get_timestamp(),
            "total_results": len(results),
            "operations": {},
        }

        for result in results:
            op_type = result.operation_type
            if op_type not in metadata["operations"]:
                metadata["operations"][op_type] = []
            metadata["operations"][op_type].append(
                {
                    "function": result.function_name,
                    "avg_time": result.avg_time,
                    "input_size": result.input_size,
                    "success_rate": result.success_rate,
                    "metadata": result.metadata,
                }
            )

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        saved["metadata"] = str(metadata_path)
        logger.info(f"Saved metadata to: {metadata_path}")

        return saved

    def run_scalability_test(self, sizes: list[int] = None) -> dict[str, list[BenchmarkResult]]:
        """
        Run scalability tests with different input sizes.

        Args:
            sizes: List of input sizes to test

        Returns:
            Dictionary mapping size to benchmark results
        """
        if sizes is None:
            sizes = [10, 50, 100, 500, 1000]
        logger.info("=" * 70)
        logger.info("Running Scalability Tests")
        logger.info("=" * 70)

        all_results = {}

        for size in sizes:
            logger.info(f"\n[Scale Test] Size: {size}")

            # Run batch search
            generator = TestDataGenerator()
            queries = generator.generate_test_queries(size, complexity="simple")

            results = []
            for i, query in enumerate(queries):
                result = self.benchmark_runner.benchmark_function(
                    self.search_client.search,
                    "scalability_test",
                    input_data=query,
                    input_size=len(query),
                    resultType="core",
                    limit=25,
                )
                result.metadata["query_index"] = i
                results.append(result)

            all_results[size] = results

        # Generate scalability report
        self._generate_scalability_report(all_results)  # type: ignore[arg-type]

        return all_results

    def _generate_scalability_report(
        self, results_by_size: dict[int, list[BenchmarkResult]]
    ) -> None:
        """Generate a scalability analysis report."""
        import statistics

        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("SCALABILITY ANALYSIS REPORT")
        report_lines.append("=" * 70)
        report_lines.append("")

        sizes = sorted(results_by_size.keys())

        report_lines.append(
            "Size         Avg Time (s)   Std Dev      Min          Max          Success Rate   "
        )
        report_lines.append("-" * 70)

        for size in sizes:
            results = results_by_size[size]
            times = [r.avg_time for r in results]
            success_rates = [r.success_rate for r in results]

            avg = statistics.mean(times)
            std = statistics.stdev(times) if len(times) > 1 else 0
            success = statistics.mean(success_rates)

            report_lines.append(
                f"{size:<10} {avg:<15.6f} {std:<12.6f} {min(times):<10.6f} "
                f"{max(times):<10.6f} {success * 100:.2f}%"
            )

        report_path = self.output_dir / "scalability_report.txt"
        report_path.write_text("\n".join(report_lines))
        logger.info(f"Saved scalability report to: {report_path}")

        print("\n" + "\n".join(report_lines))
