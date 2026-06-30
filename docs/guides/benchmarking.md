# Benchmarking & Profiling

pyEuropePMC includes a comprehensive benchmarking suite for evaluating XML parsing quality and performance. The suite provides standardized datasets, XML-level metrics, function-level profiling, and memory tracking.

## Quick Start

### CLI Commands

```bash
# List known benchmark datasets
pyeuropepmc benchmark list-datasets

# Show dataset information
pyeuropepmc benchmark dataset-info PMC_sample_1943

# Run all metrics on a single XML file
pyeuropepmc benchmark run-file article.xml

# Profile a single file (function-level timing)
pyeuropepmc benchmark profile article.xml

# Profile memory allocation
pyeuropepmc benchmark profile-memory article.xml
```

### Running a Dataset Benchmark

```bash
# Download a dataset first
pyeuropepmc benchmark download PMC_sample_1943

# Run the full benchmark with profiling
pyeuropepmc benchmark run PMC_sample_1943 --profile --profile-memory --output results.json
```

### Using from Python

```python
from pyeuropepmc.benchmark import BenchmarkDataset, BenchmarkRunner

# Download and run
dataset = BenchmarkDataset("PMC_sample_1943")
dataset.download()

runner = BenchmarkRunner(dataset, profile=True, profile_memory=True)
report = runner.run_all()
report.save_json("results.json")
```

## Standard Datasets

The suite supports four GROBID evaluation datasets:

| Dataset | Articles | Size | Source |
|---------|----------|------|--------|
| `PMC_sample_1943` | 1,943 | 1.5 GB | Hugging Face — 1943 journals (2011 PMC snapshot) |
| `PLOS_1000` | 1,000 | 1.3 GB | Hugging Face — PLOS Open Access collection |
| `eLife_984` | 984 | 4.5 GB | Hugging Face — eLife publisher JATS |
| `biorxiv-10k-test-2000` | 2,000 | 5.4 GB | Hugging Face — bioRxiv preprints (NLM XML) |

You can also benchmark a local directory of JATS XML files:

```bash
pyeuropepmc benchmark run local --local-path ./my_xmls
```

## Metrics

The suite evaluates **5 XML-level metrics**, each scoring 0.0–1.0:

### 1. Element Coverage
Percentage of unique XML element types that the parser handles. Measures how many distinct JATS elements (e.g., `<fig>`, `<table>`, `<xref>`) are recognized vs. present in the article.

### 2. Text Extraction Fidelity
Ratio of body text captured by the structured parser vs. total text in the raw XML body. Higher is better — 99.7% on real articles.

### 3. Section Boundary Accuracy
How well section titles and boundaries are preserved. Combines Jaccard similarity for title matching with section count consistency.

### 4. Inline Element Recall
Per-type recall for inline elements within paragraphs: `<xref>`, `<bold>`, `<italic>`, `<inline-formula>`, `<named-content>`, `<chem-struct>`, `<sup>`, `<sub>`.

### 5. Metadata Extraction Accuracy
Exact-match accuracy for title, DOI, PMID, PMCID extraction, plus author overlap.

### Composite Score
Weighted average of all 5 metrics (equal weights).

## Latest Results

Results from the built-in benchmark dataset (55 open-access JATS articles):

| Metric | Mean | Min | Max | Std Dev |
|--------|------|-----|-----|---------|
| **Composite Score** | **0.9506** | 0.8607 | 0.9908 | 0.0250 |
| Metadata Accuracy | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Text Fidelity | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Element Coverage | 0.9925 | 0.9655 | 1.0000 | 0.0087 |
| Section Accuracy | 0.9339 | 0.7692 | 1.0000 | 0.0518 |
| Inline Recall | 0.8267 | 0.4286 | 0.9732 | 0.1140 |

### Parse Speed

| Metric | Value |
|--------|-------|
| Throughput | 48.0 articles/s |
| Mean parse time | 0.024s |
| Median parse time | 0.021s |
| Fastest article | PMC13249065 (0.004s, 28 KB) |
| Slowest article | PMC13255524 (0.076s, 216 KB) |

### Content Coverage (55 articles)

| Metric | Count |
|--------|-------|
| Total sections | 1,452 |
| Total content blocks | 6,735 |
| Block types | 8 |
| Inline types | 9 |

Block type breakdown: paragraphs (5,372), figures (184), tables (129), quotes (69), headings (59), formulas (14), lists (11), unknown (897).

### Reproduce

```bash
# Full quality benchmark
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 55 --output results.json

# Speed + coverage
pyeuropepmc benchmark run-extra --xml-dir benchmark_xmls/xml --output extra.json
```

## Profiling

### Function-Level Profiling (cProfile)

```bash
pyeuropepmc benchmark profile article.xml --top 20
```

Output:
```
Total time: 0.7134s (372,315 calls)

Top functions by cumulative time:
  Function                                     Calls   Total  Per Call
   -----------------------------------------------------------------------
  extract_references                             1    0.5016  0.501600
  get_full_text_sections_structured              1    0.0866  0.086600
  parse                                         1    0.0784  0.078400
  extract_metadata                               1    0.0233  0.023300
  extract_figures                                1    0.0128  0.012800
```

### Memory Profiling (tracemalloc)

```bash
pyeuropepmc benchmark profile-memory article.xml --top 15
```

Output:
```
Peak memory   : 6.27 MiB
Current memory: 4.15 MiB
Allocated     : 39.17 MiB

Top allocations:
  Size (KiB)  Location
  --------------------------------------------------
      783.2  /usr/lib/python3.10/xml/etree/ElementTree.py
      452.0  pyeuropepmc/processing/parsers/base_parser.py
      341.5  pyeuropepmc/processing/fulltext_parser.py
```

### Integrated Benchmarking

Pass `--profile` / `--profile-memory` to the `run` command:

```bash
pyeuropepmc benchmark run my_dataset --profile --profile-memory --limit 10
```

## Benchmark Reports

Results can be saved as JSON and inspected later:

```bash
# Save report
pyeuropepmc benchmark run my_dataset --output report.json

# View report
pyeuropepmc benchmark report report.json

# Verbose per-article breakdown
pyeuropepmc benchmark report report.json --verbose
```

### Report Structure

```json
{
  "title": "pyEuropePMC Benchmark Report",
  "metadata": {
    "parser_version": "1.17.0",
    "date": "2026-06-17T...",
    "stats": {
      "total_articles": 10,
      "successful": 9,
      "failed": 1,
      "total_parse_time_s": 6.42
    }
  },
  "article_results": [...],
  "dataset_summaries": {...}
}
```

## Python API Reference

### BenchmarkDataset

```python
from pyeuropepmc.benchmark import BenchmarkDataset

# Known dataset
ds = BenchmarkDataset("PMC_sample_1943", data_dir="./data")
ds.download()
ds.is_downloaded  # True
list(ds.iter_articles())  # List of Path objects

# Local directory
ds = BenchmarkDataset("local", local_path="./xmls")
```

### BenchmarkRunner

```python
from pyeuropepmc.benchmark import BenchmarkDataset, BenchmarkRunner

runner = BenchmarkRunner(
    dataset,
    limit=100,           # Process only 100 articles
    skip_errors=True,    # Skip problematic files
    profile=True,        # Enable cProfile
    profile_memory=True, # Enable tracemalloc
    profile_top_n=20,    # Top N functions in profile
)
report = runner.run_all()
runner.print_profile_summary(report)
```

### BenchmarkReport

```python
report = BenchmarkReport(title="My Report")
report.add_article_result(...)
report.aggregate_overall()        # dict with composite_score, per_metric
report.aggregate_by_dataset()     # dict keyed by dataset name
report.save_json("results.json")  # JSON serialization

# Load
report = BenchmarkReport.load_json("results.json")
```

### ProfilerContext

```python
from pyeuropepmc.benchmark import ProfilerContext

with ProfilerContext() as prof:
    result = expensive_function()

stats = prof.stats_dict()
# { 'elapsed_s': 1.23, 'total_calls': 5000,
#   'by_function': {...}, 'by_module': {...} }
```

### MemoryTracker

```python
from pyeuropepmc.benchmark import MemoryTracker

tracker = MemoryTracker()
tracker.start()
result = memory_intensive_function()
data = tracker.stop()
# { 'peak_mib': 12.5, 'current_mib': 8.2, ... }
```

### One-Call Helpers

```python
from pyeuropepmc.benchmark import profile_text, profile_memory

prof = profile_text(xml_string)
print(prof["parser_breakdown_s"])  # per-module timing

mem = profile_memory(xml_string)
print(mem["peak_mib"], "MiB")     # peak memory usage
```

## Architecture

```
src/pyeuropepmc/benchmark/
├── __init__.py       # Public API exports
├── dataset.py        # BenchmarkDataset — download, cache, iterate
├── metrics.py        # 5 XML-level metrics
├── report.py         # BenchmarkReport — aggregates, serialization
├── runner.py         # BenchmarkRunner — orchestration + profiling
├── profiler.py       # ProfilerContext — cProfile wrapper
└── memory.py         # MemoryTracker — tracemalloc wrapper
```

## See Also

- [`pyeuropepmc benchmark --help`] — CLI documentation
- [XML Parser Extensions](../reference/xml-parser-extensions.md) — Content blocks, structured sections
- [Performance Benchmarks](../reference/MODULAR_PERFORMANCE_REPORT.md) — Historical benchmark results
