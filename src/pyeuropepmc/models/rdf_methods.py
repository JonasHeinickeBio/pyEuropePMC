"""
RDF serialization methods for PyEuropePMC entities.

This module contains the RDF serialization methods that are attached to
generated LinkML entities.
"""

from typing import Any

from rdflib import URIRef


def to_rdf(
    self,
    g: Any,
    uri: URIRef | None = None,
    mapper: Any = None,
    related_entities: dict[str, list[Any]] | None = None,
    extraction_info: dict[str, Any] | None = None,
    parent_uri: URIRef | None = None,
) -> URIRef:
    """
    Serialize entity to RDF graph using a mapper.

    Parameters
    ----------
    g : Graph
        RDF graph to add triples to
    uri : Optional[URIRef]
        URI for this entity (if None, will be minted)
    mapper : Optional[Any]
        RDF mapper instance to use for serialization
    related_entities : Optional[dict[str, list[Any]]]
        Dictionary of related entities by relationship name
    extraction_info : Optional[dict[str, Any]]
        Additional extraction metadata for provenance
    parent_uri : Optional[URIRef]
        URI of the parent entity (for generating contextual URIs)

    Returns
    -------
    URIRef
        Subject URI for this entity

    Raises
    ------
    ValueError
        If mapper is not provided
    """
    if mapper is None:
        raise ValueError("RDF mapper required")

    # Use mapper's URI generation logic for consistency
    subject = uri or mapper._generate_entity_uri(self)

    # Determine named graph context for this entity type
    entity_type = self.__class__.__name__.lower().replace("entity", "")
    context = mapper._get_named_graph_uri(entity_type)

    # Add RDF types
    mapper.add_types(g, subject, self.types, context)

    # Map dataclass fields using the mapper configuration
    mapper.map_fields(g, subject, self, context)

    # Map relationships (always call, even if no related_entities provided)
    # This allows entities to have relationships defined as attributes
    mapper.map_relationships(g, subject, self, related_entities, extraction_info, context)

    # Add provenance information
    mapper.add_provenance(g, subject, self, extraction_info, context)

    # Add ontology alignments and biomedical mappings
    mapper.map_ontology_alignments(g, subject, self, context)

    return subject
