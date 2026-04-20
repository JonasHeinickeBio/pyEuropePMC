"""
SHACL validation utilities for PyEuropePMC RDF conversion.

This module provides functions for adding SHACL validation shapes
to RDF graphs for data quality assurance.
"""

from typing import Any

from rdflib import Literal
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

from pyeuropepmc.mappers.config_utils import get_namespace_from_config, load_rdf_config


def add_owl_subclass_relationships(dataset: Any, named_graph_uris: dict[str, Any]) -> None:
    """Add OWL subclass relationships based on LinkML schema inheritance."""
    from pyeuropepmc.mappers.linkml_introspection import LinkMLSchemaIntrospector

    provenance_context = named_graph_uris["provenance"]

    # Load config for namespaces
    config = load_rdf_config()
    _ = get_namespace_from_config(config, "pyeuropepmc")

    # Get LinkML schema introspector
    _ = LinkMLSchemaIntrospector()

    # Define inheritance relationships based on LinkML schema
    inheritance_map = {
        # PaperEntity hierarchy
        "bibo:AcademicArticle": ["bibo:Document", "pyeuropepmc:BaseEntity"],
        "bibo:Document": ["pyeuropepmc:BaseEntity"],
        # AuthorEntity hierarchy
        "foaf:Person": ["pyeuropepmc:BaseEntity"],
        # Other entities
        "bibo:DocumentPart": ["pyeuropepmc:BaseEntity"],
        "cito:Citation": ["pyeuropepmc:BaseEntity"],
        "bibo:Table": ["pyeuropepmc:BaseEntity"],
        "bibo:Row": ["pyeuropepmc:BaseEntity"],
        "bibo:Article": ["bibo:Document", "pyeuropepmc:BaseEntity"],
        "org:Organization": ["pyeuropepmc:BaseEntity"],
        "bibo:Journal": ["pyeuropepmc:BaseEntity"],
        "frapo:Grant": ["pyeuropepmc:BaseEntity"],
        "bibo:Image": ["pyeuropepmc:BaseEntity"],
    }

    # Add subclass relationships
    for subclass_curie, parent_curies in inheritance_map.items():
        subclass_uri = _resolve_curie_to_uri(subclass_curie, config)
        for parent_curie in parent_curies:
            parent_uri = _resolve_curie_to_uri(parent_curie, config)
            dataset.graph(provenance_context).add((subclass_uri, RDFS.subClassOf, parent_uri))


def _resolve_curie_to_uri(curie: str, config: dict[str, Any]) -> str | None:
    """Resolve a CURIE to a URI using the config namespaces."""
    if ":" not in curie:
        return None

    prefix, local = curie.split(":", 1)
    namespace = get_namespace_from_config(config, prefix)
    if namespace:
        uri = namespace[local]
        return uri if isinstance(uri, str) else None
    return None


def add_shacl_validation_shapes(dataset: Any, named_graph_uris: dict[str, Any]) -> None:
    """Add SHACL validation shapes for data quality assurance."""
    provenance_context = named_graph_uris["provenance"]

    # Load config for namespaces
    config = load_rdf_config()
    PYEUROPEPMC = get_namespace_from_config(config, "pyeuropepmc")
    SH = get_namespace_from_config(config, "sh")
    FABIO = get_namespace_from_config(config, "fabio")
    EX = get_namespace_from_config(config, "ex")

    # Paper shape
    paper_shape = PYEUROPEPMC["PaperShape"]
    dataset.graph(provenance_context).add((paper_shape, RDF.type, SH.NodeShape))
    dataset.graph(provenance_context).add((paper_shape, SH.targetClass, FABIO.ResearchPaper))
    dataset.graph(provenance_context).add((paper_shape, SH.property, PYEUROPEPMC["titleProperty"]))
    dataset.graph(provenance_context).add((paper_shape, SH.property, PYEUROPEPMC["doiProperty"]))

    # Title property constraint
    title_prop = PYEUROPEPMC["titleProperty"]
    dataset.graph(provenance_context).add((title_prop, SH.path, DCTERMS.title))
    dataset.graph(provenance_context).add((title_prop, SH.minCount, Literal(1)))
    dataset.graph(provenance_context).add((title_prop, SH.datatype, XSD.string))

    # DOI property constraint
    doi_prop = PYEUROPEPMC["doiProperty"]
    dataset.graph(provenance_context).add((doi_prop, SH.path, EX.doi))
    dataset.graph(provenance_context).add((doi_prop, SH.minCount, Literal(0)))
    dataset.graph(provenance_context).add((doi_prop, SH.datatype, XSD.string))
