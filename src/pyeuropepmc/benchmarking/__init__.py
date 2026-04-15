"""
Complete benchmarking module.

Example usage:
    from pyeuropepmc import ArticleClient, SearchClient
    from pyeuropepmc.benchmarking import (
        BenchmarkRunner,
        TestDataGenerator,
        RealAPITester,
        BottleneckDetector,
        JSONReportGenerator,
    )

    # Test with real API
    tester = RealAPITester()

    # Run real search with real data
    result = tester.test_real_search("cancer treatment")

    # Run full benchmark suite
    summary = tester.run_full_benchmark()

    # Generate reports
    reports = tester.save_results(tester.benchmark_runner.results, "my_benchmark")
"""

from pyeuropepmc.benchmarking.analyzers import (
    BottleneckDetector,
    PerformanceAnalyzer,
)
from pyeuropepmc.benchmarking.benchmark_runner import BenchmarkRunner
from pyeuropepmc.benchmarking.decorators import measure_time, profile_function
from pyeuropepmc.benchmarking.real_api_benchmark import RealAPIBenchmarkRunner
from pyeuropepmc.benchmarking.real_api_tester import RealAPITester
from pyeuropepmc.benchmarking.report_generators import (
    CSVReportGenerator,
    HTMLReportGenerator,
    JSONReportGenerator,
    ReportGenerator,
    TextReportGenerator,
    generate_comprehensive_report,
)

__all__ = [
    "BenchmarkRunner",
    "measure_time",
    "profile_function",
    "PerformanceAnalyzer",
    "BottleneckDetector",
    "TestDataGenerator",
    "RealAPIBenchmarkRunner",
    "RealAPITester",
    "ReportGenerator",
    "CSVReportGenerator",
    "JSONReportGenerator",
    "TextReportGenerator",
    "HTMLReportGenerator",
    "generate_comprehensive_report",
]
