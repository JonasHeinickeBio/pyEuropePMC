"""
LinkML Schema Introspection Module for PyEuropePMC.

This module provides programmatic access to the LinkML schema, enabling:
- Dynamic field-to-predicate mapping extraction
- Schema validation before RDF conversion
- Runtime schema introspection for converters

This replaces direct rdf_map.yml reads with LinkML schema introspection,
establishing the LinkML schema as the single source of truth.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from rdflib import Namespace

logger = logging.getLogger(__name__)

# Try to import LinkML runtime
try:
    from linkml_runtime.utils.schemaview import SchemaView

    LINKML_AVAILABLE = True
except ImportError:
    LINKML_AVAILABLE = False
    logger.warning(
        "linkml_runtime not available. "
        "Install with: pip install linkml-runtime. "
        "Falling back to legacy rdf_map.yml."
    )

__all__ = [
    "LinkMLSchemaIntrospector",
    "get_schema_view",
    "get_slot_mapping",
    "get_class_mapping",
    "LINKML_AVAILABLE",
]


def _get_default_schema_path() -> Path:
    """Get the default path to the LinkML schema."""
    base_path = Path(__file__).parent.parent.parent.parent
    return base_path / "schemas" / "pyeuropepmc_schema.yaml"


@lru_cache(maxsize=1)
def get_schema_view(schema_path: str | None = None) -> "SchemaView | None":
    """
    Get a cached SchemaView instance for the LinkML schema.

    This function caches the SchemaView for performance, as loading
    the schema can be expensive for repeated operations.

    Parameters
    ----------
    schema_path : Optional[str]
        Path to the LinkML schema file. If None, uses default location.

    Returns
    -------
    SchemaView or None
        The SchemaView instance, or None if LinkML is not available.
    """
    if not LINKML_AVAILABLE:
        return None

    if schema_path is None:
        schema_path = str(_get_default_schema_path())

    try:
        return SchemaView(schema_path)
    except Exception as e:
        logger.error(f"Failed to load LinkML schema: {e}")
        return None


class LinkMLSchemaIntrospector:
    """
    Introspector for LinkML schema to extract mappings and validate data.

    This class provides methods to:
    - Extract field-to-predicate mappings from slot definitions
    - Get class URIs and types
    - Handle complex relationships and cardinality
    - Support custom annotations for RDF-specific metadata

    Examples
    --------
    >>> introspector = LinkMLSchemaIntrospector()
    >>> mapping = introspector.get_class_mapping("PaperEntity")
    >>> print(mapping["class_uri"])
    bibo:AcademicArticle
    """

    def __init__(self, schema_path: str | None = None):
        """
        Initialize the schema introspector.

        Parameters
        ----------
        schema_path : Optional[str]
            Path to the LinkML schema file. If None, uses default location.
        """
        self.schema_path = schema_path or str(_get_default_schema_path())
        self._schema_view: SchemaView | None = None
        self._namespace_cache: dict[str, Namespace] = {}

    @property
    def schema_view(self) -> "SchemaView | None":
        """Get the SchemaView instance, loading if necessary."""
        if self._schema_view is None:
            self._schema_view = get_schema_view(self.schema_path)
        return self._schema_view

    @property
    def is_available(self) -> bool:
        """Check if LinkML introspection is available."""
        return LINKML_AVAILABLE and self.schema_view is not None

    def get_all_classes(self) -> list[str]:
        """
        Get all class names defined in the schema.

        Returns
        -------
        list[str]
            List of class names.
        """
        if not self.is_available:
            return []
        return list(self.schema_view.all_classes())

    def get_class_mapping(self, class_name: str) -> dict[str, Any]:
        """
        Get the complete mapping for a class including all slots.

        Parameters
        ----------
        class_name : str
            Name of the class (e.g., "PaperEntity")

        Returns
        -------
        dict[str, Any]
            Dictionary containing class_uri, rdf_types, fields, 
            multi_value_fields, and relationships.
        """
        if not self.is_available:
            return {}

        try:
            cls = self.schema_view.get_class(class_name)
            if cls is None:
                return {}

            slots = self.schema_view.class_slots(class_name)

            mapping = {
                "class_uri": str(cls.class_uri) if cls.class_uri else None,
                "rdf_types": [str(cls.class_uri)] if cls.class_uri else [],
                "is_a": cls.is_a,
                "abstract": cls.abstract,
                "fields": {},
                "multi_value_fields": {},
                "relationships": {},
            }

            for slot_name in slots:
                slot_mapping = self.get_slot_mapping(slot_name, class_name)
                if slot_mapping:
                    if slot_mapping.get("is_relationship"):
                        mapping["relationships"][slot_name] = slot_mapping
                    elif slot_mapping.get("multivalued"):
                        mapping["multi_value_fields"][slot_name] = slot_mapping
                    else:
                        mapping["fields"][slot_name] = slot_mapping

            return mapping

        except Exception as e:
            logger.error(f"Error getting class mapping for {class_name}: {e}")
            return {}

    def get_slot_mapping(
        self, slot_name: str, class_name: str | None = None
    ) -> dict[str, Any]:
        """
        Get the mapping for a specific slot.

        Parameters
        ----------
        slot_name : str
            Name of the slot
        class_name : Optional[str]
            Name of the class to get slot usage from

        Returns
        -------
        dict[str, Any]
            Dictionary containing predicate, datatype, range, etc.
        """
        if not self.is_available:
            return {}

        try:
            slot = self.schema_view.get_slot(slot_name)
            if slot is None:
                return {}

            # Check for class-specific slot usage
            slot_usage = None
            if class_name:
                cls = self.schema_view.get_class(class_name)
                if cls and cls.slot_usage and slot_name in cls.slot_usage:
                    slot_usage = cls.slot_usage[slot_name]

            slot_uri = slot.slot_uri
            slot_range = slot.range
            is_multivalued = slot.multivalued or False

            # Check if this is a relationship (range is another class)
            is_relationship = slot_range and slot_range in self.schema_view.all_classes()

            # Get datatype for non-relationship slots
            datatype = None
            if not is_relationship:
                datatype = self._get_xsd_datatype(slot_range)

            # Build mapping dict
            mapping = {
                "predicate": str(slot_uri) if slot_uri else None,
                "range": str(slot_range) if slot_range else None,
                "datatype": datatype,
                "multivalued": is_multivalued,
                "is_relationship": is_relationship,
                "required": slot_usage.required if slot_usage else (slot.required or False),
                "description": slot.description,
            }

            # Add constraints
            if slot.minimum_value is not None:
                mapping["minimum_value"] = slot.minimum_value
            if slot.maximum_value is not None:
                mapping["maximum_value"] = slot.maximum_value
            if slot.pattern:
                mapping["pattern"] = slot.pattern

            # Add relationship-specific info
            if is_relationship:
                if hasattr(slot, "inverse") and slot.inverse:
                    mapping["inverse"] = slot.inverse
                mapping["target_class"] = slot_range

            return mapping

        except Exception as e:
            logger.error(f"Error getting slot mapping for {slot_name}: {e}")
            return {}

    def _get_xsd_datatype(self, linkml_range: str | None) -> str | None:
        """
        Convert LinkML range to XSD datatype.

        Parameters
        ----------
        linkml_range : Optional[str]
            LinkML range type

        Returns
        -------
        Optional[str]
            XSD datatype URI or None
        """
        if not linkml_range:
            return None

        xsd_mapping = {
            "string": "xsd:string",
            "integer": "xsd:integer",
            "float": "xsd:float",
            "double": "xsd:double",
            "decimal": "xsd:decimal",
            "boolean": "xsd:boolean",
            "date": "xsd:date",
            "datetime": "xsd:dateTime",
            "time": "xsd:time",
            "uri": "xsd:anyURI",
            "uriorcurie": "xsd:anyURI",
            "ncname": "xsd:NCName",
        }

        return xsd_mapping.get(linkml_range.lower())

    def get_namespaces(self) -> dict[str, str]:
        """
        Get all namespace prefixes from the schema.

        Returns
        -------
        dict[str, str]
            Dictionary mapping prefix to URI.
        """
        if not self.is_available:
            return {}

        try:
            prefixes = self.schema_view.schema.prefixes
            return {
                prefix: str(prefix_obj.prefix_reference)
                for prefix, prefix_obj in prefixes.items()
            }
        except Exception as e:
            logger.error(f"Error getting namespaces: {e}")
            return {}

    def get_namespace(self, prefix: str) -> Namespace | None:
        """
        Get a Namespace object for a given prefix.

        Parameters
        ----------
        prefix : str
            Namespace prefix (e.g., "dcterms")

        Returns
        -------
        Namespace or None
            RDFLib Namespace object.
        """
        if prefix in self._namespace_cache:
            return self._namespace_cache[prefix]

        namespaces = self.get_namespaces()
        uri = namespaces.get(prefix)
        if uri:
            ns = Namespace(uri)
            self._namespace_cache[prefix] = ns
            return ns
        return None

    def build_namespaces(self) -> dict[str, Namespace]:
        """
        Build a dictionary of Namespace objects from schema prefixes.

        Returns
        -------
        dict[str, Namespace]
            Dictionary mapping prefix to Namespace object.
        """
        namespaces = self.get_namespaces()
        return {prefix: Namespace(uri) for prefix, uri in namespaces.items()}

    def resolve_predicate(self, predicate_str: str) -> str | None:
        """
        Resolve a CURIE predicate to a full URI.

        Parameters
        ----------
        predicate_str : str
            Predicate in CURIE format (e.g., "dcterms:title")

        Returns
        -------
        Optional[str]
            Full URI string, or None if resolution fails.
        """
        if not predicate_str:
            return None

        if ":" in predicate_str and not predicate_str.startswith("http"):
            prefix, local = predicate_str.split(":", 1)
            ns = self.get_namespace(prefix)
            if ns:
                return str(ns[local])

        return predicate_str

    def get_entity_types(self, class_name: str) -> list[str]:
        """
        Get the RDF types for an entity class.

        Parameters
        ----------
        class_name : str
            Name of the class

        Returns
        -------
        list[str]
            List of RDF type URIs.
        """
        mapping = self.get_class_mapping(class_name)
        return mapping.get("rdf_types", [])

    def get_inheritance_chain(self, class_name: str) -> list[str]:
        """
        Get the inheritance chain for a class (including the class itself).

        Parameters
        ----------
        class_name : str
            Name of the class

        Returns
        -------
        list[str]
            List of class names from the class to its root ancestor.
        """
        if not self.is_available:
            return [class_name]

        chain = []
        current = class_name
        while current:
            chain.append(current)
            cls = self.schema_view.get_class(current)
            if cls and cls.is_a:
                current = cls.is_a
            else:
                break
        return chain

    def get_all_slots_for_class(self, class_name: str) -> dict[str, dict[str, Any]]:
        """
        Get all slots for a class including inherited slots.

        Parameters
        ----------
        class_name : str
            Name of the class

        Returns
        -------
        dict[str, dict[str, Any]]
            Dictionary mapping slot name to slot mapping.
        """
        if not self.is_available:
            return {}

        all_slots = {}
        inheritance_chain = self.get_inheritance_chain(class_name)

        # Process from root to leaf to allow overrides
        for cls_name in reversed(inheritance_chain):
            mapping = self.get_class_mapping(cls_name)
            all_slots.update(mapping.get("fields", {}))
            all_slots.update(mapping.get("multi_value_fields", {}))
            all_slots.update(mapping.get("relationships", {}))

        return all_slots

    def validate_entity(self, entity: Any, class_name: str | None = None) -> list[str]:
        """
        Validate an entity against the schema.

        Parameters
        ----------
        entity : Any
            Entity instance to validate
        class_name : Optional[str]
            Class name to validate against (inferred from entity if not provided)

        Returns
        -------
        list[str]
            List of validation error messages (empty if valid).
        """
        if not self.is_available:
            return []

        if class_name is None:
            class_name = entity.__class__.__name__

        errors = []
        mapping = self.get_class_mapping(class_name)

        if not mapping:
            errors.append(f"Unknown class: {class_name}")
            return errors

        # Check required fields
        for field_name, field_mapping in mapping.get("fields", {}).items():
            if field_mapping.get("required"):
                value = getattr(entity, field_name, None)
                if value is None:
                    errors.append(f"Required field '{field_name}' is missing")

        # Check patterns
        for field_name, field_mapping in mapping.get("fields", {}).items():
            pattern = field_mapping.get("pattern")
            if pattern:
                value = getattr(entity, field_name, None)
                if value is not None:
                    import re
                    if not re.match(pattern, str(value)):
                        errors.append(
                            f"Field '{field_name}' does not match pattern: {pattern}"
                        )

        # Check value constraints
        for field_name, field_mapping in mapping.get("fields", {}).items():
            value = getattr(entity, field_name, None)
            if value is not None:
                min_val = field_mapping.get("minimum_value")
                max_val = field_mapping.get("maximum_value")
                if min_val is not None and value < min_val:
                    errors.append(
                        f"Field '{field_name}' value {value} is below minimum {min_val}"
                    )
                if max_val is not None and value > max_val:
                    errors.append(
                        f"Field '{field_name}' value {value} is above maximum {max_val}"
                    )

        return errors


# Convenience functions for common operations


def get_slot_mapping(slot_name: str, class_name: str | None = None) -> dict[str, Any]:
    """
    Convenience function to get slot mapping using default schema.

    Parameters
    ----------
    slot_name : str
        Name of the slot
    class_name : Optional[str]
        Name of the class for slot usage

    Returns
    -------
    dict[str, Any]
        Slot mapping dictionary.
    """
    introspector = LinkMLSchemaIntrospector()
    return introspector.get_slot_mapping(slot_name, class_name)


def get_class_mapping(class_name: str) -> dict[str, Any]:
    """
    Convenience function to get class mapping using default schema.

    Parameters
    ----------
    class_name : str
        Name of the class

    Returns
    -------
    dict[str, Any]
        Class mapping dictionary.
    """
    introspector = LinkMLSchemaIntrospector()
    return introspector.get_class_mapping(class_name)
