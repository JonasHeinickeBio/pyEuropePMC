# PyEuropePMC Benchmarking Suite

A comprehensive, modular benchmarking system for testing the complete PyEuropePMC pipeline from search to RDF Knowledge Graph generation.

## Overview

This benchmarking suite provides structured performance testing for the PyEuropePMC library with:

- **Modular Components**: Reusable classes for each pipeline step
- **Comprehensive Metrics**: Timing, data sizes, and performance rates
- **Configurable Workflows**: Multiple predefined configurations
- **Bulk Processing**: Handles thousands of papers efficiently
- **Detailed Reporting**: JSON results and human-readable summaries

## Pipeline Steps

1. **Search**: Query Europe PMC for papers matching criteria
2. **Download**: Bulk download XML full-text content
3. **Parse**: Extract structured data from XML files
4. **Transform**: Convert to RDF Knowledge Graphs

## Quick Start

### Run Default Benchmark (1000 papers)

```bash
python benchmark_runner.py
```

### Run Smaller Test (50 papers)

```bash
python benchmark_runner.py --config small_test
```

### List Available Configurations

```bash
python benchmark_runner.py --list-configs
```

## Available Configurations

| Configuration | Papers | Query Focus | Use Case |
|---------------|--------|-------------|----------|
| `small_test` | 50 | Cancer research | Quick testing |
| `medium_benchmark` | 500 | General OA papers | Medium-scale testing |
| `full_benchmark` | 1000 | General OA papers | Full pipeline testing |
| `cancer_focused` | 200 | Cancer immunotherapy | Domain-specific testing |
| `recent_papers` | 300 | 2020-2025 papers | Recent literature |

## Custom Configuration

### Create Configuration Template

```bash
python benchmark_runner.py --create-template my_config.json
```

### Edit Configuration

```json
{
  "query": "(OPEN_ACCESS:y) AND (CITED:[5 TO *])",
  "target_paper_count": 1000,
  "search_page_size": 100,
  "max_concurrent_downloads": 5,
  "output_dir": "benchmark_output",
  "xml_cache_dir": "benchmark_cache/xml",
  "enable_citation_networks": true,
  "enable_collaboration_networks": true,
  "enable_institutional_hierarchies": true
}
```

### Run Custom Configuration

```bash
python benchmark_runner.py --config-file my_config.json
```

## Command Line Options

```
usage: benchmark_runner.py [-h] [--config {small_test,medium_benchmark,full_benchmark,cancer_focused,recent_papers}]
                          [--config-file CONFIG_FILE] [--create-template CREATE_TEMPLATE]
                          [--list-configs] [--papers PAPERS] [--query QUERY]
                          [--output-dir OUTPUT_DIR] [--no-cache]

PyEuropePMC Benchmark Runner

optional arguments:
  -h, --help            show this help message and exit
  --config {small_test,medium_benchmark,full_benchmark,cancer_focused,recent_papers}
                        Use a predefined configuration
  --config-file CONFIG_FILE
                        Load configuration from JSON file
  --create-template CREATE_TEMPLATE
                        Create a configuration template file and exit
  --list-configs        List available default configurations and exit
  --papers PAPERS       Override target paper count
  --query QUERY         Override search query
  --output-dir OUTPUT_DIR
                        Override output directory
  --no-cache            Disable XML caching (re-download all files)
```

## Output Structure

```
benchmark_output/
├── benchmark_knowledge_graph.ttl    # RDF Knowledge Graph
├── benchmark_results.json           # Detailed metrics
└── xml_element_types.txt            # All unique XML tags found

benchmark_cache/
└── xml/                             # Downloaded XML files
    ├── PMC1234567.xml
    ├── PMC2345678.xml
    └── ...
```

## Metrics Collected

### Timing Metrics
- Search time
- Download time
- Parse time
- RDF conversion time
- Total pipeline time

### Data Size Metrics
- Papers found vs target
- XML files downloaded
- Total XML size
- Average XML file size
- Unique XML element types
- RDF triples generated
- RDF file size

### Performance Rates
- Search rate (papers/second)
- Download rate (MB/second)
- Parse rate (papers/second)
- RDF conversion rate (triples/second)

### Error Tracking
- Errors and warnings from each step
- Failed downloads/parsers
- Data quality issues

## Example Output

```
🚀 Starting PyEuropePMC Bulk Benchmarking Pipeline
============================================================
🔍 Searching for 1000 papers...
   Query: (OPEN_ACCESS:y) AND (CITED:[5 TO *])
   Page 1: Found 100 papers (total: 100)
   ...
✅ Found 1000 papers (987 with PMC IDs)
   Search time: 45.23 seconds (22.1 papers/sec)
   Found 987 papers with PMC IDs

📥 Downloading XML for 987 papers...
   [1/987] Downloading XML: PMC1234567
   ...
✅ Downloaded 987 XML files
   Download time: 234.56 seconds (45.2 MB/s)
   Total size: 89.4 MB (avg: 92.1 KB)

🔬 Parsing 987 XML files...
   [1/987] Parsing: PMC1234567.xml
   ...
✅ Parsed 987 XML files
   Parse time: 156.78 seconds (6.3 papers/sec)
   Found 143 unique XML element types

🔄 Converting to RDF Knowledge Graph...
✅ Generated RDF Knowledge Graph
   Triples: 456,789
   File size: 23.4 MB
   Conversion time: 67.89 seconds (6,723 triples/sec)
   Named graphs: ['citations', 'collaborations', 'institutions']

============================================================
✅ Benchmarking Pipeline Complete!
   Total time: 504.46 seconds

📊 Benchmark Summary:
   Papers Found: 1000 (987 with PMC IDs)
   XML Files: 987
   XML Size: 89.4 MB (avg: 92.1 KB)
   Unique XML Tags: 143
   RDF Triples: 456,789
   RDF Size: 23.4 MB

⏱️  Performance:
   Search: 22.1 papers/sec
   Download: 45.2 MB/sec
   Parse: 6.3 papers/sec
   RDF Conversion: 6,723 triples/sec
```

## Advanced Usage

### Programmatic Usage

```python
from benchmark_pipeline import BenchmarkConfig, BenchmarkRunner
from pathlib import Path

# Create custom configuration
config = BenchmarkConfig(
    query='(OPEN_ACCESS:y) AND "machine learning" AND (CITED:[10 TO *])',
    target_paper_count=500,
    output_dir=Path("ml_benchmark_output")
)

# Run benchmark
runner = BenchmarkRunner(config)
metrics = runner.run_full_pipeline()

# Access detailed metrics
print(f"Total time: {metrics.total_time:.2f} seconds")
print(f"Triples generated: {metrics.rdf_triples_generated}")
```

### Custom Components

The benchmarking system is modular - you can extend or replace components:

```python
from benchmark_pipeline import BulkSearchLoader, BenchmarkConfig

class CustomSearchLoader(BulkSearchLoader):
    """Custom search implementation."""
    def search_papers(self):
        # Your custom search logic
        pass
```

## Requirements

- Python 3.10+
- PyEuropePMC library
- Internet connection for API access
- Sufficient disk space for XML cache and RDF output

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Europe PMC API has rate limits. The system includes automatic retry logic.

2. **Memory Usage**: Large paper counts may require significant RAM. Monitor system resources.

3. **Disk Space**: XML files and RDF output can be large. Ensure adequate storage.

4. **Network Timeouts**: Downloads may timeout. The system includes retry logic and can resume interrupted downloads.

### Configuration Tuning

- Reduce `target_paper_count` for faster testing
- Increase `batch_size` for better performance on fast systems
- Adjust `max_concurrent_downloads` based on network capacity
- Use `skip_existing_xml=True` to avoid re-downloading

## Contributing

To add new benchmark configurations or components:

1. Add configuration to `create_default_configs()` in `benchmark_runner.py`
2. Extend existing classes or create new ones following the modular pattern
3. Update this README with new features
4. Test with small configurations first
