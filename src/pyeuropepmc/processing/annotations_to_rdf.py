"""
Utilities for converting annotations to RDF graphs.

This module provides helper functions to convert annotation data
from the Annotations API into RDF graphs using the W3C Open Annotation
Data Model.
"""

from typing import Any

from rdflib import Graph, Namespace, URIRef

from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models.annotation import (
    AnnotationEntity,
    EntityAnnotation,
    RelationshipAnnotation,
)

__all__ = [
    "annotations_to_entities",
    "annotations_to_rdf",
    "entity_annotation_to_model",
    "relationship_annotation_to_model",
]


def entity_annotation_to_model(entity_dict: dict[str, Any]) -> EntityAnnotation:
    """
    Convert an entity annotation dictionary to an EntityAnnotation model.

    Args:
        entity_dict: Dictionary containing entity annotation data

    Returns:
        EntityAnnotation instance

    Examples:
        >>> entity_dict = {
        ...     "id": "CHEBI:16236",
        ...     "name": "ethanol",
        ...     "type": "Chemical",
        ...     "exact": "ethanol",
        ...     "section": "abstract",
        ...     "provider": "Europe PMC"
        ... }
        >>> entity = entity_annotation_to_model(entity_dict)
        >>> print(entity.entity_name)
        ethanol
    """
    return EntityAnnotation(
        entity_id=entity_dict.get("id"),
        entity_name=entity_dict.get("name"),
        entity_type=entity_dict.get("type"),
        exact=entity_dict.get("exact"),
        prefix=entity_dict.get("prefix"),
        postfix=entity_dict.get("postfix"),
        section=entity_dict.get("section"),
        provider=entity_dict.get("provider"),
        confidence=entity_dict.get("confidence"),
        position=entity_dict.get("position"),
        annotation_type="entity",
    )


def relationship_annotation_to_model(
    relationship_dict: dict[str, Any]
) -> RelationshipAnnotation:
    """
    Convert a relationship annotation dictionary to a RelationshipAnnotation model.

    Args:
        relationship_dict: Dictionary containing relationship annotation data

    Returns:
        RelationshipAnnotation instance

    Examples:
        >>> rel_dict = {
        ...     "subject": {"id": "GENE:7157", "name": "TP53", "type": "Gene"},
        ...     "predicate": "associated_with",
        ...     "object": {"id": "DOID:162", "name": "cancer", "type": "Disease"},
        ...     "sentence": "TP53 is associated with cancer",
        ...     "section": "body"
        ... }
        >>> rel = relationship_annotation_to_model(rel_dict)
        >>> print(rel.predicate)
        associated_with
    """
    subject = relationship_dict.get("subject", {})
    obj = relationship_dict.get("object", {})

    return RelationshipAnnotation(
        subject_id=subject.get("id"),
        subject_name=subject.get("name"),
        subject_type=subject.get("type"),
        predicate=relationship_dict.get("predicate"),
        object_id=obj.get("id"),
        object_name=obj.get("name"),
        object_type=obj.get("type"),
        exact=relationship_dict.get("sentence"),
        section=relationship_dict.get("section"),
        provider=relationship_dict.get("provider"),
        annotation_type="relationship",
    )


def annotations_to_entities(
    parsed_annotations: dict[str, Any]
) -> list[EntityAnnotation | RelationshipAnnotation]:
    """
    Convert parsed annotation data to entity models.

    Args:
        parsed_annotations: Output from AnnotationParser.parse_annotations()

    Returns:
        List of EntityAnnotation and RelationshipAnnotation instances

    Examples:
        >>> from pyeuropepmc.processing.annotation_parser import parse_annotations
        >>> parsed = parse_annotations(raw_annotations)
        >>> entities = annotations_to_entities(parsed)
        >>> print(f"Converted {len(entities)} annotations to entity models")
    """
    entities: list[EntityAnnotation | RelationshipAnnotation] = []

    # Convert entity annotations
    for entity_dict in parsed_annotations.get("entities", []):
        try:
            entity = entity_annotation_to_model(entity_dict)
            entities.append(entity)
        except Exception as e:
            # Log warning but continue processing
            import logging

            logging.warning(f"Failed to convert entity annotation: {e}")

    # Convert relationship annotations
    for rel_dict in parsed_annotations.get("relationships", []):
        try:
            relationship = relationship_annotation_to_model(rel_dict)
            entities.append(relationship)
        except Exception as e:
            # Log warning but continue processing
            import logging

            logging.warning(f"Failed to convert relationship annotation: {e}")

    return entities


def annotations_to_rdf(
    parsed_annotations: dict[str, Any],
    graph: Graph | None = None,
    mapper: RDFMapper | None = None,
    base_uri: str = "http://example.org/annotations/",
) -> Graph:
    """
    Convert parsed annotations to an RDF graph.

    This function converts annotations from the Europe PMC Annotations API
    into RDF triples following the W3C Open Annotation Data Model.

    Args:
        parsed_annotations: Output from AnnotationParser.parse_annotations()
        graph: Existing RDF graph to add to (creates new if None)
        mapper: RDF mapper instance (creates default if None)
        base_uri: Base URI for generating annotation URIs

    Returns:
        RDF graph containing annotation triples

    Examples:
        >>> from pyeuropepmc import AnnotationsClient, parse_annotations
        >>> from pyeuropepmc.processing.annotations_to_rdf import annotations_to_rdf
        >>>
        >>> # Fetch and parse annotations
        >>> with AnnotationsClient() as client:
        ...     raw = client.get_annotations_by_article_ids(["PMC3359311"])
        >>> parsed = parse_annotations(raw)
        >>>
        >>> # Convert to RDF
        >>> g = annotations_to_rdf(parsed)
        >>> print(f"Created RDF graph with {len(g)} triples")
        >>>
        >>> # Serialize to Turtle format
        >>> turtle = g.serialize(format="turtle")
        >>> print(turtle)
    """
    # Create graph if not provided
    if graph is None:
        graph = Graph()

    # Create mapper if not provided
    if mapper is None:
        mapper = RDFMapper()

    # Bind namespaces to the graph
    OA = Namespace("http://www.w3.org/ns/oa#")
    NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")
    graph.bind("oa", OA)
    graph.bind("nif", NIF)

    # Convert annotations to entity models
    entities = annotations_to_entities(parsed_annotations)

    # Add each entity to the RDF graph
    for idx, entity in enumerate(entities):
        # Generate unique URI for this annotation
        uri = URIRef(f"{base_uri}{idx + 1}")

        try:
            # Use the entity's to_rdf method to add it to the graph
            entity.to_rdf(graph, uri=uri, mapper=mapper)
        except Exception as e:
            # Log warning but continue processing
            import logging

            logging.warning(f"Failed to add annotation to RDF: {e}")

    return graph
