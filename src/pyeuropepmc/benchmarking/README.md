# PyEuropePMC Benchmarking Module

A professional, scalable benchmarking system for measuring, analyzing, and optimizing the performance of PyEuropePMC operations.

## Features

- **Modular Design**: Separate components for testing, execution, analysis, and reporting
- **Scalable Testing**: Handle single operations to thousands of requests
- **Detailed Analysis**: Statistical analysis and bottleneck detection
- **Multiple Report Formats**: JSON, CSV, text, and HTML reports
- **Integration**: Works seamlessly with existing PyEuropePMC clients and components

## Components

### 1. Test Data Generator (`test_data.py`)
Generates realistic test data for benchmarking:

```python
from pyeuropepmc.benchmarking import TestDataGenerator

generator = TestDataGenerator()

# Generate search queries
queries = generator.generate_test_queries(10, complexity="simple")

# Generate test paper identifiers
identifiers = generator.generate_test_identifiers(100)

# Generate test paper metadata
papers = generator.generate_test_papers(50)
```

### 2. Benchmark Runner (`benchmark_runner.py`)
Executes benchmarks and collects metrics:

```python
from pyeuropepmc.benchmarking import BenchmarkRunner

runner = BenchmarkRunner(warmup_runs=1, repetitions=5)

# Benchmark search operations
results = runner.benchmark_search_operations(search_client, queries)

# Benchmark article retrieval
results = runner.benchmark_article_operations(article_client, identifiers)

# Get statistics
stats = runner.get_statistics()
runner.print_summary()
```

### 3. Analyzers (`analyzers.py`)
Statistical analysis and bottleneck detection:

```python
from pyeuropepmc.benchmarking import BottleneckDetector

detector = BottleneckDetector(results)

# Detect various bottleneck types
bottlenecks = detector.detect_all_bottlenecks()

# Get top bottlenecks by severity
top = detector.get_top_bottlenecks(n=10)

# Generate bottleneck report
report = detector.generate_report()
detector.print_report()
```

### 4. Report Generators (`report_generators.py`)
Export results in multiple formats:

```python
from pyeuropepmc.benchmarking import JSONReportGenerator, HTMLReportGenerator

# Generate JSON report
json_gen = JSONReportGenerator(results)
json_gen.save("benchmark_results.json")

# Generate HTML report
html_gen = HTMLReportGenerator(results)
html_gen.save("benchmark_results.html")

# Generate comprehensive reports
from pyeuropepmc.benchmarking import generate_comprehensive_report

reports = generate_comprehensive_report(
    results,
    output_dir="reports",
    formats=["json", "csv", "html", "text"]
)
```

### 5. Real API Tester (`real_api_tester.py`) ⭐ NEW
Performs actual API calls to Europe PMC with real data:

```python
from pyeuropepmc.benchmarking import RealAPITester

tester = RealAPITester()

# Run real search with real data
result = tester.test_real_search("cancer treatment")

# Run full benchmark suite
summary = tester.run_full_benchmark()

# Run scalability tests
results = tester.run_scalability_test(sizes=[10, 50, 100, 500])

# Save results
reports = tester.save_results(tester.benchmark_runner.results, "my_benchmark")
```

## Real API Testing Features

The `RealAPITester` provides comprehensive testing with actual Europe PMC API:

### Available Test Methods:

- **`test_real_search(query)`** - Single search with real data
- **`test_real_article_retrieval(pmid)`** - Single article retrieval
- **`test_real_fulltext_retrieval(pmcid)`** - Full-text XML retrieval
- **`test_real_batch_search(queries)`** - Multiple searches
- **`test_real_article_bulk(count)`** - Bulk article retrieval
- **`test_real_search_pagination(pages, per_page)`** - Pagination testing
- **`test_real_search_with_filters()`** - Filter combinations
- **`test_real_search_author()`** - Author-specific searches
- **`test_real_search_journal()`** - Journal-specific searches
- **`test_real_citation_retrieval()`** - Citation retrieval
- **`test_real_reference_retrieval()`** - Reference retrieval
- **`test_real_doi_lookup(doi)`** - DOI-based lookup
- **`run_full_benchmark()`** - Complete benchmark suite
- **`run_scalability_test(sizes)`** - Scalability analysis

### Example Real API Test:

```python
from pyeuropepmc.benchmarking import RealAPITester

tester = RealAPITester()

# Run a real search with actual Europe PMC API
result = tester.test_real_search("cancer treatment precision medicine")

print(f"Query: {result.metadata['query']}")
print(f"Time: {result.avg_time:.6f}s")
print(f"Success Rate: {result.success_rate * 100:.2f}%")

# Run full benchmark suite
summary = tester.run_full_benchmark()
```

## Usage Example

```python
from pyeuropepmc import ArticleClient, SearchClient
from pyeuropepmc.benchmarking import (
    BenchmarkRunner,
    TestDataGenerator,
    BottleneckDetector,
)

# Initialize
article_client = ArticleClient()
search_client = SearchClient()
runner = BenchmarkRunner(warmup_runs=1, repetitions=5)
generator = TestDataGenerator()

# Generate test data
queries = generator.generate_test_queries(10)
identifiers = [("MED", pmid) for pmid in generator.generate_test_identifiers(10)]

# Run benchmarks
search_results = runner.benchmark_search_operations(search_client, queries)
article_results = runner.benchmark_article_operations(article_client, identifiers)

# Analyze
all_results = search_results + article_results
detector = BottleneckDetector([r.to_dict() for r in all_results])

# Get bottleneck analysis
bottlenecks = detector.detect_all_bottlenecks()
top_bottlenecks = detector.get_top_bottlenecks(n=5)

# Generate reports
from pyeuropepmc.benchmarking import JSONReportGenerator
json_gen = JSONReportGenerator([r.to_dict() for r in all_results])
    json_gen.save("benchmark_results.json")

    # Print summary
    runner.print_summary()
    detector.print_report()
```

## Real API Testing Examples

See `real_api_examples.py` for comprehensive examples:

```bash
# Run real API testing examples
python src/pyeuropepmc/benchmarking/real_api_examples.py
```

This will perform actual searches, retrieve real papers, and generate detailed reports.

## Scaling to Large Workloads

For benchmarking thousands of operations:

```python
# Generate large test datasets
generator = TestDataGenerator()
queries = generator.generate_test_queries(1000)
papers = generator.generate_test_papers(500)

# Run benchmarks
results = runner.benchmark_search_operations(search_client, queries)

# Analyze scalability
detector = BottleneckDetector([r.to_dict() for r in results])
scaling_bottlenecks = detector.detect_scaling_bottlenecks()
```

## Troubleshooting

### Slow Benchmarks
- Increase warmup runs for JIT compilation
- Use more repetitions for stable measurements
- Consider caching for I/O-bound operations

### Inconsistent Results
- Check network conditions (real API tests)
- Verify API rate limits
- Consider resource contention

### High Variance
- Run more repetitions
- Check for background processes
- Consider system load

## Real API vs Synthetic Data

### When to Use Real API Tester:
- **Production performance validation**: Test actual API response times
- **Network latency analysis**: Measure real-world network performance
- **API rate limit testing**: Validate rate limiting behavior
- **Data retrieval benchmarks**: Test actual data processing
- **Integration testing**: Verify end-to-end performance

### When to Use Synthetic Data:
- **Development testing**: No API calls during development
- **High-volume tests**: Generate thousands of operations instantly
- **Reproducible benchmarks**: Consistent test data
- **Offline testing**: No internet connection needed
- **Cost control**: Avoid excessive API usage

### Combining Both Approaches:
```python
# Test with synthetic data first
runner = BenchmarkRunner()
synthetic_results = runner.benchmark_search_operations(
    search_client, synthetic_queries
)

# Validate with real API
tester = RealAPITester()
real_results = tester.test_real_batch_search(real_queries)

# Compare performance
```

## Contributing

To add new benchmark types:

1. Add a new method to `BenchmarkRunner`
2. Include proper input validation
3. Return `BenchmarkResult` objects
4. Update documentation

## License

Part of PyEuropePMC - MIT License
