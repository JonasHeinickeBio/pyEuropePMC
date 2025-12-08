"""
RDF mapping functionality for converting entities to RDF graphs.

This module provides:
- RDFMapper: Main mapper using YAML configuration
- LinkML schema introspection for single source of truth
- Runtime configuration management
- Converters for various data sources
"""

from pyeuropepmc.mappers.config_utils import rebind_namespaces
from pyeuropepmc.mappers.converters import (
    RDFConversionError,
    convert_enrichment_to_rdf,
    convert_incremental_to_rdf,
    convert_pipeline_to_rdf,
    convert_search_to_rdf,
    convert_xml_to_rdf,
)
from pyeuropepmc.mappers.linkml_introspection import (
    LINKML_AVAILABLE,
    LinkMLSchemaIntrospector,
    get_class_mapping,
    get_schema_view,
    get_slot_mapping,
)
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.mappers.rdf_utils import (
    add_external_identifiers,
    generate_entity_uri,
    map_ontology_alignments,
    normalize_name,
)
from pyeuropepmc.mappers.rml_rdfizer import RDFIZER_AVAILABLE, RMLRDFizer
from pyeuropepmc.mappers.runtime_config import (
    RuntimeConfig,
    get_config,
    load_runtime_config,
)

__all__ = [
    # Main mapper
    "RDFMapper",
    "RMLRDFizer",
    "RDFIZER_AVAILABLE",
    # LinkML introspection
    "LINKML_AVAILABLE",
    "LinkMLSchemaIntrospector",
    "get_class_mapping",
    "get_schema_view",
    "get_slot_mapping",
    # Runtime configuration
    "RuntimeConfig",
    "get_config",
    "load_runtime_config",
    # Converters
    "RDFConversionError",
    "convert_enrichment_to_rdf",
    "convert_incremental_to_rdf",
    "convert_pipeline_to_rdf",
    "convert_search_to_rdf",
    "convert_xml_to_rdf",
    # Utilities
    "add_external_identifiers",
    "generate_entity_uri",
    "map_ontology_alignments",
    "normalize_name",
    "rebind_namespaces",
]
