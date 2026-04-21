# QA Toolset for TTL Validation

A comprehensive quality assurance toolset for validating TTL (Turtle RDF) output files in the pyEuropePMC project. This toolset provides schema validation, data quality metrics, SPARQL query testing, consistency checks, and comparison tools.

## Features

### 1. Schema Validation
Validate TTL files against the LinkML schema (`pyeuropepmc_schema.yaml`):
- Required field checking
- Datatype validation
- Pattern matching
- Severity classification (error/warning/info)

### 2. Data Quality Metrics
Calculate comprehensive quality metrics:
- Triple counts and statistics
- Entity counts by type
- Completeness metrics for papers, authors, and journals
- Duplicate detection (URIs and literal values)
- Namespace coverage analysis

### 3. SPARQL Query Testing
Run predefined and custom SPARQL queries:
- Paper, author, and journal validation queries
- Orphan entity detection
- Duplicate entity detection
- Date and literal type analysis
- Entity type distribution

### 4. Consistency Checks
Verify data consistency:
- Orphan detection (authors, journals, papers without parents)
- Relationship validation
- Entity relationship integrity
- Field requirement compliance

### 5. Comparison Tools
Detect regressions between TTL files:
- Triple-level comparison
- Entity-level changes
- Namespace usage analysis
- Change scoring

### 6. Flexible Output
Support for multiple output formats:
- Human-readable text reports
- Machine-parsable JSON
- Command-line interface
- Programmatic API

## Quick Start

### Command Line Interface

```bash
# Validate a single TTL file
python tests/qa_toolset/validate_ttl.py test_output/sample.ttl

# Validate multiple files
python tests/qa_toolset/validate_ttl.py test_output/*.ttl

# Validate with schema
python tests/qa_toolset/validate_ttl.py test_output/*.ttl -s schemas/pyeuropepmc_schema.yaml

# Compare with a reference file
python tests/qa_toolset/validate_ttl.py test_output/*.ttl --compare test_output/reference.ttl

# JSON output
python tests/qa_toolset/validate_ttl.py test_output/*.ttl -f json -o results.json
```

### Comprehensive QA Runner

```bash
# Run full QA on directory
python tests/qa_toolset/run_qa.py test_output/ -s schemas/pyeuropepmc_schema.yaml

# Compare against reference
python tests/qa_toolset/run_qa.py test_output/ --compare test_output/reference.ttl

# Text output
python tests/qa_toolset/run_qa.py test_output/ -f text
```

## Modules

### `validate_ttl.py`
Main CLI script for TTL validation with fine-grained control:
- `-s, --schema`: Path to LinkML schema
- `-o, --output`: Output file
- `-f, --format`: Output format (text/json)
- `--no-schema`, `--no-sparql`, `--no-consistency`, `--no-metrics`: Skip specific checks
- `--compare`: Compare against reference file

### `run_qa.py`
Comprehensive QA runner with summary reports:
- Directory-based validation
- Summary statistics
- Status breakdowns
- Average metrics

### `metrics.py`
Data quality metrics calculator:
- `RDFMetricsCalculator`: Main class for calculating metrics
- Methods: `calculate_all_metrics()`, `calculate_completeness_metrics()`, etc.

### `sparql_queries.py`
SPARQL query validation:
- `SPARQLValidator`: Main class for running SPARQL queries
- Predefined queries for papers, authors, journals
- Custom query support

### `schema_validation.py`
LinkML schema validation:
- `SchemaValidator`: Main class for schema validation
- Validates against LinkML schema constraints

### `consistency_checks.py`
Consistency checking:
- `ConsistencyChecker`: Main class for consistency checks
- Orphan detection, relationship validation, integrity checks

### `compare_outputs.py`
File comparison:
- `OutputComparator`: Main class for comparing TTL files
- Methods: `compare_files()`, `compare_graphs()`, `compare_multiple_files()`

## Usage Examples

### Python API

```python
from qa_toolset.validate_ttl import TTLValidator

# Initialize validator
validator = TTLValidator(schema_path='schemas/pyeuropepmc_schema.yaml')

# Validate a single file
result = validator.validate_file(
    'test_output/sample.ttl',
    run_schema=True,
    run_sparql=True,
    run_consistency=True,
    run_metrics=True
)

print(f"Status: {result['status']}")
print(f"Completeness: {result['metrics']['overall_completeness']:.1%}")
```

### Comprehensive QA

```python
from qa_toolset.run_qa import QARunner

runner = QARunner(schema_path='schemas/pyeuropepmc_schema.yaml')

# Run QA on directory
output = runner.run_qa_on_directory(
    'test_output/',
    output_format='json',
    compare_with='test_output/reference.ttl'
)

print(output)
```

### Custom SPARQL Queries

```python
from qa_toolset.sparql_queries import SPARQLValidator

validator = SPARQLValidator()

custom_query = """
SELECT ?paper ?title WHERE {
    ?paper a <http://purl.org/ontology/bibo/Article> ;
           <http://purl.org/dc/terms/title> ?title .
}
"""

results = validator.run_custom_query(graph, custom_query, 'custom')
```

### File Comparison

```python
from qa_toolset.compare_outputs import OutputComparator

comparator = OutputComparator()
result = comparator.compare_files('file1.ttl', 'file2.ttl')

print(f"Change score: {result.overall_change_score:.1%}")
print(f"Added triples: {result.added_triples}")
```

## Output Formats

### JSON Output
```json
{
  "file": "test_output/sample.ttl",
  "status": "passed",
  "metrics": {
    "overall_completeness": 0.85,
    "triple_counts": {
      "total_triples": 1234
    }
  },
  "sparql": {
    "papers_with_identifiers": {"passed": true, "count": 10}
  }
}
```

### Text Output
```
============================================================
TTL VALIDATION SUMMARY
============================================================
Total files:    1
Passed:         1
Failed:         0
Pass rate:      100%
Total errors:   0
Total warnings: 1
============================================================

File: sample.ttl
Status: PASSED
  Metrics: 85% complete
```

## Configuration

### Skip Checks
Use command-line flags to skip specific checks:
- `--no-schema`: Skip schema validation
- `--no-sparql`: Skip SPARQL validation
- `--no-consistency`: Skip consistency checks
- `--no-metrics`: Skip metrics calculation

### Custom Schema
Specify a custom LinkML schema:
```bash
python tests/qa_toolset/validate_ttl.py test_output/*.ttl -s path/to/schema.yaml
```

## Testing

Run unit tests:
```bash
pytest tests/test_qa_toolset.py -v
```

Test metrics calculation:
```bash
pytest tests/test_qa_toolset.py::TestRDFMetricsCalculator -v
```

Test specific module:
```bash
pytest tests/test_qa_toolset.py::TestSPARQLValidator -v
```

## Integration with Existing Code

The QA toolset integrates with existing project structure:

```
pyEuropePMC_project/
├── src/pyeuropepmc/
│   └── mappers/rdf_mapper.py
├── schemas/pyeuropepmc_schema.yaml
├── tests/
│   ├── fixtures/
│   ├── test_qa_toolset.py
│   └── qa_toolset/
│       ├── __init__.py
│       ├── validate_ttl.py
│       ├── run_qa.py
│       ├── metrics.py
│       ├── sparql_queries.py
│       ├── schema_validation.py
│       ├── consistency_checks.py
│       ├── compare_outputs.py
│       └── README.md
└── test_output/
```

## Troubleshooting

### Parse Error
Ensure TTL files are valid Turtle syntax:
```bash
python -c "from rdflib import Graph; Graph().parse('file.ttl', format='turtle')"
```

### Schema Path
Verify schema path is correct:
```bash
python tests/qa_toolset/validate_ttl.py test_output/*.ttl -s schemas/pyeuropepmc_schema.yaml
```

### Empty Results
Check for valid RDF data in TTL files:
```bash
python -c "from rdflib import Graph; g = Graph(); g.parse('file.ttl'); print(len(g), 'triples')"
```

## Contributing

1. Add new validation checks in appropriate modules
2. Follow existing code patterns
3. Add unit tests for new functionality
4. Update this documentation
5. Run `pytest tests/test_qa_toolset.py -v` before committing

## License

MIT License - see LICENSE file for details.
