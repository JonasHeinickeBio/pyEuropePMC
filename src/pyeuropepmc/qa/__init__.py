"""
PyEuropePMC QA Toolset

A comprehensive quality assurance toolset for validating TTL (Turtle RDF) output files
in the pyEuropePMC project. This toolset provides schema validation, data quality metrics,
SPARQL query testing, consistency checks, and comparison tools.

This package provides:
- Schema validation against LinkML schema
- Data quality metrics
- SPARQL query testing
- Consistency checks
- Comparison tools for regression detection
- Detailed error reporting

Usage:
    python -m pyeuropepmc.qa.run_qa --directory test_output/ --output reports/

    from pyeuropepmc.qa import QARunner, TTLValidator

    runner = QARunner(schema_path='schemas/pyeuropepmc_schema.yaml')
    output = runner.run_qa_on_directory('test_output/')

Attributes:
    __version__ (str): The version of the QA toolset
    __author__ (str): The author of the QA toolset
    PROJECT_ROOT (Path): The root directory of the pyEuropePMC project
    TEST_OUTPUT_DIR (Path): The default directory for test output files
    SCHEMA_PATH (Path): The default path to the LinkML schema
    QA_DIR (Path): The path to the QA toolset directory
"""

__version__ = "1.0.0"
__author__ = "PyEuropePMC Team"

from pathlib import Path

from .compare_outputs import OutputComparator
from .consistency_checks import ConsistencyChecker
from .metrics import RDFMetricsCalculator
from .run_qa import QARunner
from .schema_validation import SchemaValidator
from .sparql_queries import SPARQLValidator
from .validate_ttl import TTLValidator

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_OUTPUT_DIR = PROJECT_ROOT / "test_output"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "pyeuropepmc_schema.yaml"
QA_DIR = Path(__file__).parent

__all__ = [
    "__version__",
    "__author__",
    "PROJECT_ROOT",
    "TEST_OUTPUT_DIR",
    "SCHEMA_PATH",
    "QA_DIR",
    "RDFMetricsCalculator",
    "SPARQLValidator",
    "SchemaValidator",
    "ConsistencyChecker",
    "OutputComparator",
    "QARunner",
    "TTLValidator",
]
