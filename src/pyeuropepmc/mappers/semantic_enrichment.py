"""
Semantic enrichment utilities for PyEuropePMC RDF conversion.

This module provides functions for building semantic networks such as
citation networks, collaboration networks, and institutional hierarchies.
"""

from datetime import datetime
import logging
from typing import Any

from rdflib import DCTERMS, RDF, XSD, Literal, URIRef

from pyeuropepmc.mappers.config_utils import get_namespace_from_config, load_rdf_config
from pyeuropepmc.mappers.processors import (
    process_enrichment_data,
    process_search_results,
    process_xml_data,
)
from pyeuropepmc.mappers.quality_metrics import (
    calculate_author_quality_score,
    calculate_institution_quality_score,
    calculate_paper_quality_score,
    get_confidence_level,
)

logger = logging.getLogger(__name__)


def process_search_for_rdf(
    search_results: list[dict[str, Any]] | dict[str, Any],
    dataset: Any,
    named_graph_uris: dict[str, Any],
    mapper: Any,
    extraction_info: dict[str, Any] | None = None,
) -> None:
    """Process search results and add to named graphs."""
    publications_context = named_graph_uris["publications"]
    authors_context = named_graph_uris["authors"]

    # Process search results into entities
    entities_data = process_search_results(search_results)

    for entity_data in entities_data:
        entity = entity_data["entity"]
        related_entities = entity_data.get("related_entities", {})

        try:
            entity.to_rdf(
                dataset,
                mapper=mapper,
                related_entities=related_entities,
                extraction_info=extraction_info,
            )

            # Add author metadata
            if hasattr(entity, "authors"):
                for author in entity.authors:
                    author_uri = mapper.generate_uri("author", author)
                    add_author_metadata(author, dataset, author_uri, authors_context)

            # Add paper metadata
            paper_uri = mapper.generate_uri("paper", entity)
            add_paper_metadata(entity, dataset, paper_uri, publications_context)

        except Exception as e:
            logger.warning(f"Failed to process search entity {entity} to RDF: {e}")
            continue


def process_xml_for_rdf(
    xml_data: dict[str, Any],
    dataset: Any,
    named_graph_uris: dict[str, Any],
    mapper: Any,
    extraction_info: dict[str, Any] | None = None,
) -> None:
    """Process XML data and add to named graphs."""
    publications_context = named_graph_uris["publications"]
    authors_context = named_graph_uris["authors"]

    # Process XML data into entities
    entities_data = process_xml_data(xml_data)

    for entity_data in entities_data:
        entity = entity_data["entity"]
        related_entities = entity_data.get("related_entities", {})

        try:
            entity.to_rdf(
                dataset,
                mapper=mapper,
                related_entities=related_entities,
                extraction_info=extraction_info,
            )

            # Add author metadata
            if hasattr(entity, "authors"):
                for author in entity.authors:
                    author_uri = mapper.generate_uri("author", author)
                    add_author_metadata(author, dataset, author_uri, authors_context)

            # Add paper metadata
            paper_uri = mapper.generate_uri("paper", entity)
            add_paper_metadata(entity, dataset, paper_uri, publications_context)

        except Exception as e:
            logger.warning(f"Failed to process XML entity {entity} to RDF: {e}")
            continue


def process_enrichment_for_rdf(
    enrichment_data: dict[str, Any],
    dataset: Any,
    named_graph_uris: dict[str, Any],
    mapper: Any,
    extraction_info: dict[str, Any] | None = None,
) -> None:
    """Process enrichment data and add to named graphs."""
    publications_context = named_graph_uris["publications"]
    authors_context = named_graph_uris["authors"]

    # Process enrichment data into entities
    entities_data = process_enrichment_data(enrichment_data)

    for entity_data in entities_data:
        entity = entity_data["entity"]
        related_entities = entity_data.get("related_entities", {})

        try:
            entity.to_rdf(
                dataset,
                mapper=mapper,
                related_entities=related_entities,
                extraction_info=extraction_info,
            )

            # Add author metadata
            if hasattr(entity, "authors"):
                for author in entity.authors:
                    author_uri = mapper.generate_uri("author", author)
                    add_author_metadata(author, dataset, author_uri, authors_context)

            # Add paper metadata
            paper_uri = mapper.generate_uri("paper", entity)
            add_paper_metadata(entity, dataset, paper_uri, publications_context)

        except Exception as e:
            logger.warning(f"Failed to process enrichment entity {entity} to RDF: {e}")
            continue


def build_citation_networks(dataset: Any, named_graph_uris: dict[str, Any]) -> None:
    """Build citation networks using CiTO ontology."""
    publications_context = named_graph_uris["publications"]

    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    CITO = get_namespace_from_config(config, "cito")

    # Find all publications with references
    publications = []
    references = []

    for s, p, o in dataset.graph(publications_context):
        if p == EX.citedByCount:
            publications.append(s)
        elif str(p).endswith("cites"):
            references.append((s, o))

    # Add citation relationships
    for citing_pub, cited_pub in references:
        if isinstance(cited_pub, URIRef):
            dataset.graph(publications_context).add((citing_pub, CITO.cites, cited_pub))


def build_collaboration_networks(dataset: Any, named_graph_uris: dict[str, Any]) -> None:
    """Build author collaboration networks using VIVO ontology."""
    authors_context = named_graph_uris["authors"]
    publications_context = named_graph_uris["publications"]

    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    VIVO = get_namespace_from_config(config, "vivo")

    # Build author-publication mapping
    author_publications = {}

    for s, p, o in dataset.graph(publications_context):
        if p == DCTERMS.creator and isinstance(o, URIRef):
            author_id = str(o).split("/")[-1]
            if author_id not in author_publications:
                author_publications[author_id] = []
            author_publications[author_id].append(s)

    # Find co-authors
    for author_id, pubs in author_publications.items():
        author_uri = EX[f"author/{author_id}"]
        co_authors = set()

        for pub_id in pubs:
            # Find all authors of this publication
            pub_authors = []
            for s2, p2, o2 in dataset.graph(publications_context):
                if s2 == pub_id and p2 == DCTERMS.creator and isinstance(o2, URIRef):
                    pub_authors.append(str(o2).split("/")[-1])

            for co_author_id in pub_authors:
                if co_author_id != author_id:
                    co_authors.add(co_author_id)

        # Add collaboration relationships
        for co_author_id in co_authors:
            co_author_uri = EX[f"author/{co_author_id}"]
            dataset.graph(authors_context).add((author_uri, VIVO.coAuthor, co_author_uri))


def build_institutional_hierarchies(dataset: Any, named_graph_uris: dict[str, Any]) -> None:
    """Build institutional hierarchies using ORG ontology."""
    institutions_context = named_graph_uris["institutions"]
    authors_context = named_graph_uris["authors"]

    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    EUROPEPMC = get_namespace_from_config(config, "europepmc")
    ORG = get_namespace_from_config(config, "org")

    # Extract institution information from authors
    institution_members = {}

    for s, p, o in dataset.graph(authors_context):
        if p == EX.affiliation:
            inst_name = str(o)
            if inst_name not in institution_members:
                institution_members[inst_name] = []
            institution_members[inst_name].append(s)

    # Create institution entities and hierarchies
    for inst_name, members in institution_members.items():
        inst_uri = EX[f"institution/{hash(inst_name) % 10000}"]
        dataset.graph(institutions_context).add((inst_uri, RDF.type, ORG.Organization))
        dataset.graph(institutions_context).add((inst_uri, EX.name, Literal(inst_name)))

        # Add members
        for member_uri in members:
            dataset.graph(institutions_context).add((inst_uri, ORG.hasMember, member_uri))

        # Add quality metrics
        quality_score = calculate_institution_quality_score(
            {"name": inst_name, "member_count": len(members)}
        )
        dataset.graph(institutions_context).add(
            (inst_uri, EX.qualityScore, Literal(quality_score, datatype=XSD.decimal))
        )
        dataset.graph(institutions_context).add((inst_uri, EX.dataSource, URIRef(str(EUROPEPMC))))
        dataset.graph(institutions_context).add(
            (inst_uri, EX.lastUpdated, Literal(datetime.now().isoformat(), datatype=XSD.dateTime))
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


def add_paper_metadata(
    paper_entity: Any, dataset: Any, paper_uri: URIRef, publications_context: Any
) -> None:
    """Add paper metadata to paper entities."""
    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    EUROPEPMC = get_namespace_from_config(config, "europepmc")

    # Add data source attribution
    dataset.graph(publications_context).add((paper_uri, EX.dataSource, URIRef(str(EUROPEPMC))))

    # Add quality metrics
    quality_score = calculate_paper_quality_score(paper_entity)
    dataset.graph(publications_context).add(
        (paper_uri, EX.qualityScore, Literal(quality_score, datatype=XSD.decimal))
    )
    dataset.graph(publications_context).add(
        (paper_uri, EX.confidenceLevel, Literal(get_confidence_level(quality_score)))
    )

    # Add temporal information
    dataset.graph(publications_context).add(
        (paper_uri, EX.lastUpdated, Literal(datetime.now().isoformat(), datatype=XSD.dateTime))
    )

    # Add citation relationships if available
    if hasattr(paper_entity, "cited_by_count") and paper_entity.cited_by_count:
        dataset.graph(publications_context).add(
            (
                paper_uri,
                EX.citedByCount,
                Literal(paper_entity.cited_by_count, datatype=XSD.integer),
            )
        )


def add_author_metadata(
    author_entity: Any, dataset: Any, author_uri: URIRef, authors_context: Any
) -> None:
    """Add author metadata to author entities."""
    # Load config for namespaces
    config = load_rdf_config()
    EX = get_namespace_from_config(config, "ex")
    EUROPEPMC = get_namespace_from_config(config, "europepmc")

    # Add data source attribution
    dataset.graph(authors_context).add((author_uri, EX.dataSource, URIRef(str(EUROPEPMC))))

    # Add quality metrics
    quality_score = calculate_author_quality_score(author_entity)
    dataset.graph(authors_context).add(
        (author_uri, EX.qualityScore, Literal(quality_score, datatype=XSD.decimal))
    )
    dataset.graph(authors_context).add(
        (author_uri, EX.confidenceLevel, Literal(get_confidence_level(quality_score)))
    )

    # Add temporal information
    dataset.graph(authors_context).add(
        (author_uri, EX.lastUpdated, Literal(datetime.now().isoformat(), datatype=XSD.dateTime))
    )
