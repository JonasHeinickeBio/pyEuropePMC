"""
Benchmarking workflow for ArticleClient and related classes.

This test suite uses pytest-benchmark, py-spy, and memory-profiler to generate performance and memory usage reports.

Run with:
    pytest --benchmark-only --benchmark-save=benchmark_results
    # For memory profiling:
    pytest --maxfail=1 --disable-warnings --tb=short --memory-profiler
    # For py-spy profiling:
    py-spy record -o profile.svg -- pytest tests/benchmark_article_client.py

Reports can be uploaded to GitHub as SVG, HTML, or Markdown.
"""
import pytest


# Import all main client classes here
from pyeuropepmc.article import ArticleClient
# from pyeuropepmc.search import SearchClient
# from pyeuropepmc.parser import EuropePMCParser
# Add more as needed

CLIENT_CLASSES = [
    ArticleClient,
    # SearchClient,
    # EuropePMCParser,
    # Add more client classes here
]

class BenchmarkRunner:
    """
    Reusable benchmarking runner for API client classes.
    """
    def __init__(self, client_class):
        self.client = client_class()

    def benchmark_get_article_details(self, benchmark):
        if hasattr(self.client, "get_article_details"):
            source = "MED"
            article_id = "34308300"
            result = benchmark(self.client.get_article_details, source, article_id)
            assert "result" in result

    def benchmark_get_citations(self, benchmark):
        if hasattr(self.client, "get_citations"):
            source = "MED"
            article_id = "34308300"
            result = benchmark(self.client.get_citations, source, article_id)
            assert "citationList" in result or "jsonp_response" in result

    def benchmark_get_references(self, benchmark):
        if hasattr(self.client, "get_references"):
            source = "MED"
            article_id = "34308300"
            result = benchmark(self.client.get_references, source, article_id)
            assert "referenceList" in result or "jsonp_response" in result

    def benchmark_get_database_links(self, benchmark):
        if hasattr(self.client, "get_database_links"):
            source = "MED"
            article_id = "34308300"
            result = benchmark(self.client.get_database_links, source, article_id)
            if not ("dbCrossReferenceList" in result or "jsonp_response" in result):
                print(f"Warning: Expected keys not found in response: {list(result.keys())}")
            assert isinstance(result, dict) and "request" in result

    def memory_profile_get_article_details(self):
        import memory_profiler
        if hasattr(self.client, "get_article_details"):
            source = "MED"
            article_id = "34308300"
            mem_usage = memory_profiler.memory_usage((self.client.get_article_details, (source, article_id)), interval=0.1)
            print(f"Memory usage: {mem_usage}")
            assert max(mem_usage) < 200  # MB, adjust as needed


@pytest.fixture(params=CLIENT_CLASSES, scope="module")
def benchmark_runner(request):
    return BenchmarkRunner(request.param)



@pytest.mark.benchmark(group="get_article_details")
def test_get_article_details_benchmark(benchmark, benchmark_runner):
    benchmark_runner.benchmark_get_article_details(benchmark)



@pytest.mark.benchmark(group="get_citations")
def test_get_citations_benchmark(benchmark, benchmark_runner):
    benchmark_runner.benchmark_get_citations(benchmark)



@pytest.mark.benchmark(group="get_references")
def test_get_references_benchmark(benchmark, benchmark_runner):
    benchmark_runner.benchmark_get_references(benchmark)



@pytest.mark.benchmark(group="get_database_links")
def test_get_database_links_benchmark(benchmark, benchmark_runner):
    benchmark_runner.benchmark_get_database_links(benchmark)



# Memory profiling example (for all clients)
def test_get_article_details_memory(benchmark_runner):
    benchmark_runner.memory_profile_get_article_details()

# Py-spy usage: run externally for flamegraph
# py-spy record -o profile.svg -- pytest tests/benchmark_article_client.py

# To generate a Markdown/HTML report for GitHub:
# pytest --benchmark-only --benchmark-save=benchmark_results
# pytest-benchmark compare --markdown benchmark_results > BENCHMARK_REPORT.md
# pytest-benchmark compare --csv benchmark_results > BENCHMARK_REPORT.csv
# pytest-benchmark compare --histogram benchmark_results > BENCHMARK_REPORT.html

# For more advanced profiling, add more test cases and parameterize inputs.
