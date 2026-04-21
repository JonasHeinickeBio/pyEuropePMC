# QA Toolset for TTL Files

A comprehensive quality assurance toolset for validating TTL (Turtle RDF) output files in the pyEuropePMC project.

## Features

1. **Schema Validation** - Validate against LinkML schema
2. **Data Quality Metrics** - Triple counts, entity counts, completeness
3. **SPARQL Query Testing** - Run predefined and custom queries
4. **Consistency Checks** - Orphan detection, relationship validation
5. **Comparison Tools** - Detect regressions between files

## Usage

### Command Line

```bash
# Run comprehensive QA on all TTL files in a directory
python qa_ttl.py test_output/ -s schemas/pyeuropepmc_schema.yaml

# Get JSON output
python qa_ttl.py test_output/ -s schemas/pyeuropepmc_schema.yaml -f json

# Compare against a reference file
python qa_ttl.py test_output/ --compare test_output/reference.ttl

# Skip specific checks
python qa_ttl.py test_output/ --no-schema --no-consistency

# Text output
python qa_ttl.py test_output/ -f text
```

### Python API

```python
from tests.qa_toolset.run_qa import QARunner

runner = QARunner(schema_path='schemas/pyeuropepmc_schema.yaml')
output = runner.run_qa_on_directory('test_output/')
print(output)
```

### Unit Tests

```bash
python -m pytest tests/test_qa_toolset.py -v
```

## Output

The QA tool generates comprehensive reports including:

- File-level status (passed/failed/error)
- Completeness metrics
- Triple/entity counts
- Orphan detection
- SPARQL query results
- Comparison with reference files

## File Structure

```
tests/qa_toolset/
├── __init__.py              # Package initialization
├── validate_ttl.py          # Main validation CLI
├── run_qa.py                # Comprehensive QA runner
├── metrics.py               # Data quality metrics
├── sparql_queries.py        # SPARQL query validation
├── schema_validation.py     # LinkML schema validation
├── consistency_checks.py    # Consistency checking
├── compare_outputs.py       # File comparison
└── README.md                # This file
```
