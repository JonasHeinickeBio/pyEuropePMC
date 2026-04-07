"""
Schema-driven validation utilities for builders.

This module provides validation functions that check parser outputs against
the LinkML schema constraints before entity creation, ensuring data quality
and early error detection.
"""

import logging
import re
from typing import Any

from pyeuropepmc.mappers.linkml_introspection import LinkMLSchemaIntrospector

logger = logging.getLogger(__name__)

__all__ = [
    "SchemaValidator",
    "validate_field_value",
    "validate_entity_data",
    "sanitize_field_value",
]


class SchemaValidator:
    """
    Validator that uses LinkML schema to validate entity data.

    This class provides methods to validate field values against
    schema constraints including patterns, ranges, and types.
    """

    def __init__(self):
        """Initialize the schema validator."""
        self.introspector = LinkMLSchemaIntrospector()
        self._pattern_cache: dict[str, re.Pattern] = {}

    def validate_entity_data(
        self, entity_class: str, data: dict[str, Any], strict: bool = False
    ) -> tuple[bool, list[str]]:
        """
        Validate entity data against schema constraints.

        Parameters
        ----------
        entity_class : str
            Name of the entity class (e.g., "PaperEntity")
        data : dict
            Dictionary of field values to validate
        strict : bool
            If True, fail on any validation error. If False, only warn.

        Returns
        -------
        tuple[bool, list[str]]
            Tuple of (is_valid, list of error messages)
        """
        if not self.introspector.is_available:
            logger.warning("LinkML introspection not available, skipping validation")
            return True, []

        errors = []
        class_mapping = self.introspector.get_class_mapping(entity_class)

        if not class_mapping:
            errors.append(f"Unknown entity class: {entity_class}")
            return False, errors

        all_fields = {
            **class_mapping.get("fields", {}),
            **class_mapping.get("multi_value_fields", {}),
            **class_mapping.get("relationships", {}),
        }

        # Validate each field in the data
        for field_name, field_value in data.items():
            if field_value is None:
                continue

            if field_name not in all_fields:
                # Field not in schema - this might be okay for dynamic fields
                logger.debug(f"Field {field_name} not found in schema for {entity_class}")
                continue

            field_mapping = all_fields[field_name]
            is_valid, field_errors = self.validate_field_value(
                field_name, field_value, field_mapping
            )

            if not is_valid:
                errors.extend(field_errors)

        # Check required fields
        for field_name, field_mapping in all_fields.items():
            if field_mapping.get("required") and field_name not in data:
                errors.append(f"Required field '{field_name}' is missing")

        is_valid = len(errors) == 0 if strict else True
        return is_valid, errors

    def validate_field_value(  # noqa: C901
        self, field_name: str, value: Any, field_mapping: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        Validate a single field value against its schema constraints.

        Parameters
        ----------
        field_name : str
            Name of the field
        value : Any
            Value to validate
        field_mapping : dict
            Schema mapping for the field

        Returns
        -------
        tuple[bool, list[str]]
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check pattern constraint
        if "pattern" in field_mapping and value is not None:
            pattern = field_mapping["pattern"]
            if isinstance(value, str):
                if pattern not in self._pattern_cache:
                    self._pattern_cache[pattern] = re.compile(pattern)

                if not self._pattern_cache[pattern].match(value):
                    errors.append(
                        f"Field '{field_name}' value '{value}' does not match pattern '{pattern}'"
                    )

        # Check range constraints for numeric values
        if isinstance(value, int | float):
            if "minimum_value" in field_mapping:
                if value < field_mapping["minimum_value"]:
                    errors.append(
                        f"Field '{field_name}' value {value} is below minimum "
                        f"{field_mapping['minimum_value']}"
                    )

            if "maximum_value" in field_mapping:
                if value > field_mapping["maximum_value"]:
                    errors.append(
                        f"Field '{field_name}' value {value} exceeds maximum "
                        f"{field_mapping['maximum_value']}"
                    )

        # Check multivalued constraint
        if field_mapping.get("multivalued"):
            if not isinstance(value, (list, tuple)):
                errors.append(f"Field '{field_name}' should be a list (multivalued)")

        is_valid = len(errors) == 0
        return is_valid, errors

    def sanitize_field_value(
        self, field_name: str, value: Any, field_mapping: dict[str, Any]
    ) -> Any:
        """
        Sanitize a field value to conform to schema constraints.

        This function attempts to coerce values into the correct format
        rather than rejecting them.

        Parameters
        ----------
        field_name : str
            Name of the field
        value : Any
            Value to sanitize
        field_mapping : dict
            Schema mapping for the field

        Returns
        -------
        Any
            Sanitized value
        """
        if value is None:
            return None

        # Handle multivalued fields
        if field_mapping.get("multivalued"):
            if not isinstance(value, (list, tuple)):
                value = [value]

        # Handle type coercion based on datatype
        datatype = field_mapping.get("datatype")
        if datatype:
            if datatype == "xsd:integer" and not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {field_name} to integer: {value}")

            elif datatype == "xsd:float" and not isinstance(value, float):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {field_name} to float: {value}")

            elif datatype == "xsd:boolean" and not isinstance(value, bool):
                value = bool(value)

            elif datatype == "xsd:string" and not isinstance(value, str):
                value = str(value)

        # Apply range constraints for numeric values
        if isinstance(value, (int, float)):
            if "minimum_value" in field_mapping:
                value = max(value, field_mapping["minimum_value"])
            if "maximum_value" in field_mapping:
                value = min(value, field_mapping["maximum_value"])

        return value


# Module-level convenience functions
_validator = SchemaValidator()


def validate_entity_data(
    entity_class: str, data: dict[str, Any], strict: bool = False
) -> tuple[bool, list[str]]:
    """
    Validate entity data against schema constraints.

    Convenience function that uses a module-level validator instance.
    """
    return _validator.validate_entity_data(entity_class, data, strict)


def validate_field_value(
    field_name: str, value: Any, field_mapping: dict[str, Any]
) -> tuple[bool, list[str]]:
    """
    Validate a single field value.

    Convenience function that uses a module-level validator instance.
    """
    return _validator.validate_field_value(field_name, value, field_mapping)


def sanitize_field_value(field_name: str, value: Any, field_mapping: dict[str, Any]) -> Any:
    """
    Sanitize a field value.

    Convenience function that uses a module-level validator instance.
    """
    return _validator.sanitize_field_value(field_name, value, field_mapping)
