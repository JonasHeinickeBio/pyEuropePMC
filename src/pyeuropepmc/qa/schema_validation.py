"""
Schema validation module for PyEuropePMC TTL file validation.

This module validates RDF data against the LinkML schema to ensure
data model compliance and consistency.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

try:
    from linkml_runtime.utils.schemaview import SchemaView

    LINKML_AVAILABLE = True
except ImportError:
    LINKML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: str  # "error", "warning", "info"
    category: str  # "schema", "datatype", "relationship", "constraint"
    message: str
    subject: str | None = None
    predicate: str | None = None
    expected: str | None = None
    actual: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "subject": self.subject,
            "predicate": self.predicate,
            "expected": self.expected,
            "actual": self.actual,
            "line": self.line,
        }


@dataclass
class SchemaValidationResult:
    """Result of schema validation."""

    file_name: str
    is_valid: bool
    issues: list[ValidationIssue]
    entities_validated: int = 0
    errors_count: int = 0
    warnings_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_name": self.file_name,
            "is_valid": self.is_valid,
            "entities_validated": self.entities_validated,
            "errors_count": self.errors_count,
            "warnings_count": self.warnings_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Schema Validation Report: {self.file_name}",
            "=" * 60,
            f"Valid: {self.is_valid}",
            f"Entities Validated: {self.entities_validated}",
            f"Errors: {self.errors_count}",
            f"Warnings: {self.warnings_count}",
            "",
            "Issues:",
        ]

        for issue in self.issues:
            lines.append(f"  [{issue.severity.upper()}] {issue.category}: {issue.message}")

        return "\n".join(lines)


class SchemaValidator:
    """Validator that checks RDF data against LinkML schema."""

    def __init__(self, schema_path: str | Path | None = None):
        """
        Initialize the schema validator.

        Args:
            schema_path: Path to the LinkML schema YAML file
        """
        self.schema_path = schema_path

        if LINKML_AVAILABLE and schema_path:
            try:
                self.view = SchemaView(schema_path)
                self.is_available = True
            except Exception as e:
                logger.warning(f"Could not load schema: {e}")
                self.view = None
                self.is_available = False
        else:
            self.view = None
            self.is_available = False

    def validate_graph(self, graph: Graph, file_name: str) -> SchemaValidationResult:
        """
        Validate an RDF graph against the schema.

        Args:
            graph: RDF graph to validate
            file_name: Name of the file being validated

        Returns:
            SchemaValidationResult object
        """
        issues = []

        if not self.is_available:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="schema",
                    message="LinkML schema not available for validation",
                )
            )
            return SchemaValidationResult(
                file_name=file_name,
                is_valid=False,
                issues=issues,
            )

        # Get all entities
        entities = set(graph.subjects(RDF.type))
        entities_validated = 0

        for entity_type_uri in entities:
            entity_type = str(entity_type_uri)

            # Check if entity type is defined in schema
            if not self._is_valid_entity_type(entity_type):
                issues.append(
                    ValidationIssue(
                        severity="info",
                        category="schema",
                        message=f"Entity type not in schema: {entity_type}",
                    )
                )
                continue

            # Validate each entity of this type
            for subject in graph.subjects(RDF.type, entity_type_uri):
                entities_validated += 1
                issues.extend(self._validate_entity(subject, graph, entity_type))

        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        return SchemaValidationResult(
            file_name=file_name,
            is_valid=len(errors) == 0,
            issues=issues,
            entities_validated=entities_validated,
            errors_count=len(errors),
            warnings_count=len(warnings),
        )

    def _is_valid_entity_type(self, entity_type: str) -> bool:
        """Check if entity type is defined in schema."""
        if not self.view:
            return False

        # Check if type is in known classes
        class_name = self._get_class_name(entity_type)
        return class_name in self.view.all_classes()

    def _validate_entity(
        self, subject: URIRef, graph: Graph, entity_type: str
    ) -> list[ValidationIssue]:
        """Validate a single entity."""
        issues = []
        class_name = self._get_class_name(entity_type)

        if not self.view or class_name not in self.view.all_classes():
            return issues

        # Check required slots
        class_obj = self.view.get_class(class_name)
        if class_obj:
            for slot_name in class_obj.slots:
                slot = self.view.get_slot(slot_name)
                if slot and slot.required:
                    predicate = self._get_predicate_for_slot(slot_name)
                    if predicate and (subject, predicate, None) not in graph:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                category="schema",
                                message=f"Required field missing: {slot_name}",
                                subject=str(subject),
                                predicate=str(predicate),
                            )
                        )

        # Check constraints
        for slot_name in class_obj.slots:
            slot = self.view.get_slot(slot_name)
            if slot:
                predicate = self._get_predicate_for_slot(slot_name)
                for obj in graph.objects(subject, predicate):
                    issues.extend(self._validate_value(obj, slot))

        return issues

    def _validate_value(self, value: Any, slot: Any) -> list[ValidationIssue]:
        """Validate a value against slot constraints."""
        issues = []

        # Check datatype
        if slot.range and value:
            expected_type = slot.range
            actual_type = self._get_type(value)

            if not self._types_compatible(actual_type, expected_type):
                msg = f"Type mismatch for slot: expected {expected_type}, got {actual_type}"
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="datatype",
                        message=msg,
                        actual=str(actual_type),
                        expected=str(expected_type),
                    )
                )

        # Check pattern
        if slot.pattern and value:
            import re

            if not re.match(slot.pattern, str(value)):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="constraint",
                        message=f"Value does not match pattern: {slot.pattern}",
                        actual=str(value),
                    )
                )

        return issues

    def _get_class_name(self, uri: str) -> str:
        """Extract class name from URI."""
        if "#" in uri:
            return uri.split("#")[-1]
        elif "/" in uri:
            return uri.split("/")[-1]
        return uri

    def _get_predicate_for_slot(self, slot_name: str) -> URIRef | None:
        """Get predicate URI for a slot name."""
        if not self.view:
            return None

        slot = self.view.get_slot(slot_name)
        if slot and slot.mapping:
            try:
                return URIRef(slot.mapping)
            except Exception:
                return None
        return None

    def _get_type(self, value: Any) -> str:
        """Get the type of a value."""
        if isinstance(value, str):
            return "string"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, bool):
            return "boolean"
        return "unknown"

    def _types_compatible(self, actual: str, expected: str) -> bool:
        """Check if types are compatible."""
        type_mapping = {
            "string": ["xsd:string", "rdfs:Literal"],
            "integer": ["xsd:integer", "xsd:int", "xsd:long"],
            "float": ["xsd:float", "xsd:double", "xsd:decimal"],
            "boolean": ["xsd:boolean"],
        }

        expected_types = type_mapping.get(actual, [])
        return expected in expected_types or actual in expected_types


def validate_schema(
    ttl_file: str | Path, schema_path: str | Path | None = None
) -> SchemaValidationResult:
    """
    Validate a TTL file against the LinkML schema.

    Args:
        ttl_file: Path to the TTL file
        schema_path: Optional path to schema, defaults to project schema

    Returns:
        SchemaValidationResult object
    """
    graph = Graph()
    graph.parse(str(ttl_file), format="turtle")

    if schema_path is None:
        from pyeuropepmc.qa import SCHEMA_PATH

        schema_path = SCHEMA_PATH

    validator = SchemaValidator(schema_path)
    return validator.validate_graph(graph, Path(ttl_file).name)


def validate_schema_directory(
    directory: str | Path, schema_path: str | Path | None = None
) -> dict[str, SchemaValidationResult]:
    """
    Validate all TTL files in a directory against the schema.

    Args:
        directory: Path to directory containing TTL files
        schema_path: Optional path to schema

    Returns:
        Dictionary mapping filenames to validation results
    """
    results = {}
    dir_path = Path(directory)

    for ttl_file in dir_path.glob("*.ttl"):
        result = validate_schema(ttl_file, schema_path)
        results[ttl_file.name] = result

    return results
