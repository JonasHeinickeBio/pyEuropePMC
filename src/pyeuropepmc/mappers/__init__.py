"""
RDF mapping functionality for converting entities to RDF graphs.
"""

from pyeuropepmc.mappers.converters import (
    RDFConversionError,
    convert_enrichment_to_rdf,
    convert_incremental_to_rdf,
    convert_pipeline_to_rdf,
    convert_search_to_rdf,
    convert_xml_to_rdf,
)
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.mappers.rdf_utils import (
    add_external_identifiers,
    generate_entity_uri,
    map_ontology_alignments,
    normalize_name,
)
from pyeuropepmc.mappers.rml_rdfizer import RDFIZER_AVAILABLE, RMLRDFizer

__all__ = [
    "RDFMapper",
    "RMLRDFizer",
    "RDFIZER_AVAILABLE",
    "RDFConversionError",
    "add_external_identifiers",
    "convert_enrichment_to_rdf",
    "convert_incremental_to_rdf",
    "convert_pipeline_to_rdf",
    "convert_search_to_rdf",
    "convert_xml_to_rdf",
    "generate_entity_uri",
    "map_ontology_alignments",
    "normalize_name",
]
