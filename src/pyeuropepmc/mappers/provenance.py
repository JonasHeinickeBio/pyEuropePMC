"""
Provenance utilities for PyEuropePMC RDF conversion.

This module provides functions for adding provenance information and metadata
to RDF graphs.
"""

from datetime import datetime
from typing import Any

from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

from pyeuropepmc.mappers.config_utils import get_namespace_from_config, load_rdf_config
from pyeuropepmc.mappers.quality_metrics import (
    calculate_author_quality_score,
    calculate_paper_quality_score,
    get_confidence_level,
)


def add_provenance_and_metadata(
    dataset: Any, named_graph_uris: dict[str, Any], extraction_info: dict[str, Any] | None = None
) -> None:
    """Add provenance information and metadata."""
    provenance_context = named_graph_uris["provenance"]

    # Load config for namespaces
    config = load_rdf_config()
    PYEUROPEPMC = get_namespace_from_config(config, "pyeuropepmc")
    EX = get_namespace_from_config(config, "ex")

    # Dataset version information
    dataset_uri = PYEUROPEPMC["dataset-v1"]
    dataset.graph(provenance_context).add(
        (dataset_uri, RDF.type, URIRef("http://www.w3.org/ns/prov#Entity"))
    )
    dataset.graph(provenance_context).add(
        (
            dataset_uri,
            URIRef("http://www.w3.org/ns/prov#generatedAtTime"),
            Literal(datetime.now().isoformat(), datatype=XSD.dateTime),
        )
    )
    dataset.graph(provenance_context).add(
        (
            dataset_uri,
            URIRef("http://www.w3.org/ns/prov#wasGeneratedBy"),
            PYEUROPEPMC.rdfGenerator,
        )
    )
    dataset.graph(provenance_context).add(
        (
            dataset_uri,
            DCTERMS.description,
            Literal("PyEuropePMC RDF dataset with semantic relationships"),
        )
    )
    dataset.graph(provenance_context).add((dataset_uri, EX.versionInfo, Literal("1.0.0")))

    # RDF generator activity
    generator_uri = PYEUROPEPMC["rdf-generator"]
    dataset.graph(provenance_context).add(
        (generator_uri, RDF.type, URIRef("http://www.w3.org/ns/prov#SoftwareAgent"))
    )
    dataset.graph(provenance_context).add(
        (
            generator_uri,
            DCTERMS.description,
            Literal("PyEuropePMC RDF generator with semantic enrichment"),
        )
    )


def add_paper_metadata(paper_entity: Any, publications_graph: Any, paper_uri: URIRef) -> None:
    """Add paper metadata to paper entities."""
    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    EUROPEPMC = get_namespace_from_config(config, "europepmc")

    # Add data source attribution
    publications_graph.add((paper_uri, EX.dataSource, URIRef(str(EUROPEPMC))))

    # Add quality metrics
    quality_score = calculate_paper_quality_score(paper_entity)
    publications_graph.add(
        (paper_uri, EX.qualityScore, Literal(quality_score, datatype=XSD.decimal))
    )
    publications_graph.add(
        (paper_uri, EX.confidenceLevel, Literal(get_confidence_level(quality_score)))
    )

    # Add temporal information
    publications_graph.add(
        (paper_uri, EX.lastUpdated, Literal(datetime.now().isoformat(), datatype=XSD.dateTime))
    )

    # Add citation relationships if available
    if hasattr(paper_entity, "cited_by_count") and paper_entity.cited_by_count:
        publications_graph.add(
            (
                paper_uri,
                EX.citedByCount,
                Literal(paper_entity.cited_by_count, datatype=XSD.integer),
            )
        )


def add_author_metadata(author_entity: Any, authors_graph: Any, author_uri: URIRef) -> None:
    """Add author metadata to author entities."""
    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    EUROPEPMC = get_namespace_from_config(config, "europepmc")

    # Add data source attribution
    authors_graph.add((author_uri, EX.dataSource, URIRef(str(EUROPEPMC))))

    # Add quality metrics
    quality_score = calculate_author_quality_score(author_entity)
    authors_graph.add((author_uri, EX.qualityScore, Literal(quality_score, datatype=XSD.decimal)))
    authors_graph.add(
        (author_uri, EX.confidenceLevel, Literal(get_confidence_level(quality_score)))
    )

    # Add temporal information
    authors_graph.add(
        (author_uri, EX.lastUpdated, Literal(datetime.now().isoformat(), datatype=XSD.dateTime))
    )


def add_quality_metrics(dataset: Any, named_graph_uris: dict[str, Any]) -> None:
    """Add comprehensive quality metrics to all entities."""
    provenance_context = named_graph_uris["provenance"]

    # Load config for namespaces
    config = load_rdf_config()
    PYEUROPEPMC = get_namespace_from_config(config, "pyeuropepmc")

    # Add quality assessment metadata
    quality_uri = PYEUROPEPMC["quality-assessment"]
    dataset.graph(provenance_context).add(
        (quality_uri, RDF.type, URIRef("http://www.w3.org/ns/prov#Activity"))
    )
    dataset.graph(provenance_context).add(
        (
            quality_uri,
            URIRef("http://www.w3.org/ns/prov#startedAtTime"),
            Literal(datetime.now().isoformat(), datatype=XSD.dateTime),
        )
    )
    dataset.graph(provenance_context).add(
        (quality_uri, DCTERMS.description, Literal("Automated quality assessment of RDF entities"))
    )
