"""
Utilities for converting annotations to RDF graphs.

This module provides helper functions to convert annotation data
from the Annotations API into RDF graphs using the W3C Open Annotation
Data Model.
"""

from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from pyeuropepmc.models.annotation import (
    EntityAnnotation,
    RelationshipAnnotation,
)
from pyeuropepmc.processing.annotation_parser import parse_annotations

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
        id=entity_dict.get("annotation_id") or entity_dict.get("id") or entity_dict.get("@id"),
        source_uri=entity_dict.get("article_uri"),
        entity_id=entity_dict.get("id"),
        entity_name=entity_dict.get("name"),
        entity_type=entity_dict.get("type"),
        annotation_category=entity_dict.get("annotation_category"),
        exact=entity_dict.get("exact"),
        prefix=entity_dict.get("prefix"),
        postfix=entity_dict.get("postfix"),
        section=entity_dict.get("section"),
        provider=entity_dict.get("provider"),
        article_id=entity_dict.get("article_id"),
        article_uri=entity_dict.get("article_uri"),
        confidence=entity_dict.get("confidence"),
        position=entity_dict.get("position"),
        annotation_type="entity",
    )


def relationship_annotation_to_model(relationship_dict: dict[str, Any]) -> RelationshipAnnotation:
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
        id=relationship_dict.get("annotation_id")
        or relationship_dict.get("id")
        or relationship_dict.get("@id"),
        source_uri=relationship_dict.get("article_uri"),
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
        article_id=relationship_dict.get("article_id"),
        article_uri=relationship_dict.get("article_uri"),
        annotation_type="relationship",
    )


def annotations_to_entities(
    parsed_annotations: dict[str, Any],
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
    normalized = (
        parsed_annotations
        if "entities" in parsed_annotations
        else parse_annotations(parsed_annotations)
    )

    entities: list[EntityAnnotation | RelationshipAnnotation] = []

    # Convert entity annotations
    for entity_dict in normalized.get("entities", []):
        try:
            entity = entity_annotation_to_model(entity_dict)
            entities.append(entity)
        except Exception as e:
            # Log warning but continue processing
            import logging

            logging.warning(f"Failed to convert entity annotation: {e}")

    # Convert relationship annotations
    for rel_dict in normalized.get("relationships", []):
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

    # Bind namespaces to the graph for clearer Turtle output
    OA = Namespace("http://www.w3.org/ns/oa#")
    NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")
    DCT = Namespace("http://purl.org/dc/terms/")
    PROV = Namespace("http://www.w3.org/ns/prov#")
    VOCAB = Namespace("https://w3id.org/pyeuropepmc/vocab#")
    graph.bind("oa", OA)
    graph.bind("nif", NIF)
    graph.bind("dcterms", DCT)
    graph.bind("prov", PROV)
    graph.bind("pyeuropepmc", VOCAB)
    graph.bind("owl", OWL)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)

    # Convert annotations to entity models
    entities = annotations_to_entities(parsed_annotations)

    # Add each entity to the RDF graph
    from datetime import datetime

    for idx, entity in enumerate(entities):
        # Prefer stable annotation id if present
        subject_uri_str = None
        try:
            subject_uri_str = getattr(entity, "id", None) or getattr(entity, "annotation_id", None)
        except Exception:
            subject_uri_str = None

        if (
            subject_uri_str
            and isinstance(subject_uri_str, str)
            and (subject_uri_str.startswith("http://") or subject_uri_str.startswith("https://"))
        ):
            subject = URIRef(subject_uri_str)
        else:
            # Create deterministic URI using base + article + index
            art = getattr(entity, "article_id", None) or getattr(entity, "article_uri", None) or ""
            safe_art = str(art).replace("/", "_") if art else ""
            subject = URIRef(f"{base_uri}{safe_art}-{idx + 1}")

        try:
            # Skip model-driven serialization via mapper since we handle all triples manually
            # to ensure proper datatype annotations (especially xsd:dateTime for timestamps)
            # if mapper is not None:
            #     try:
            #         entity.to_rdf(graph, uri=subject, mapper=mapper)
            #     except Exception:
            #         pass

            # Manual enrichment for common properties (ensures consistent output)
            # Add rdf:type annotations if available on entity.types
            types = getattr(entity, "types", []) or []
            for t in types:
                try:
                    if isinstance(t, str) and ":" in t:
                        # leave CURIE-like values to mapper; skip adding raw
                        continue
                    graph.add((subject, RDF.type, URIRef(t)))
                except Exception:  # nosec B112
                    continue

            # rdfs:label from entity_name or label
            label = (
                getattr(entity, "entity_name", None)
                or getattr(entity, "label", None)
                or getattr(entity, "name", None)
            )
            if label:
                graph.add((subject, RDFS.label, Literal(str(label))))

            # Link to canonical entity URI (owl:sameAs + oa:hasBody) when available
            ent_uri = getattr(entity, "entity_id", None) or getattr(entity, "id", None)
            if (
                ent_uri
                and isinstance(ent_uri, str)
                and (ent_uri.startswith("http://") or ent_uri.startswith("https://"))
            ):
                graph.add((subject, OWL.sameAs, URIRef(ent_uri)))
                graph.add((subject, OA.hasBody, URIRef(ent_uri)))

            # oa:hasTarget -> article URI (use article_uri when possible)
            art_uri = getattr(entity, "article_uri", None) or getattr(entity, "article_id", None)
            if art_uri and isinstance(art_uri, str):
                # If looks like an HTTP URI, add as typed URI
                if art_uri.startswith("http://") or art_uri.startswith("https://"):
                    graph.add((subject, OA.hasTarget, URIRef(art_uri)))
                    graph.add((subject, PROV.wasDerivedFrom, URIRef(art_uri)))
                else:
                    graph.add((subject, OA.hasTarget, Literal(str(art_uri))))

            # provenance - ensure dateTime is properly typed
            # Format: YYYY-MM-DDTHH:mm:ssZ (without microseconds for XSD compliance)
            gen_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            dt_literal = Literal(gen_time, datatype=XSD.dateTime)
            graph.add((subject, PROV.generatedAtTime, dt_literal))
            provider = getattr(entity, "provider", None)
            if provider:
                graph.add((subject, DCT.creator, Literal(str(provider))))

            # textual context using NIF if available
            # Check exact first (raw annotation text), then entity_name (display name)
            exact = getattr(entity, "exact", None)
            if not exact:
                exact = getattr(entity, "entity_name", None)
            if exact and isinstance(exact, str) and exact.strip():
                graph.add((subject, NIF.anchorOf, Literal(str(exact).strip())))
            prefix = getattr(entity, "prefix", None)
            postfix = getattr(entity, "postfix", None)
            if prefix:
                graph.add((subject, VOCAB.textPrefix, Literal(str(prefix))))
            if postfix:
                graph.add((subject, VOCAB.textPostfix, Literal(str(postfix))))

            # include confidence if present
            conf = getattr(entity, "confidence", None)
            if conf is not None:
                try:
                    graph.add((subject, VOCAB.confidence, Literal(float(conf))))
                except Exception:
                    graph.add((subject, VOCAB.confidence, Literal(str(conf))))

        except Exception as e:
            import logging

            logging.warning(f"Failed to add annotation to RDF: {e}")

    return graph
