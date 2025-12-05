"""
SHACL validation utilities for PyEuropePMC RDF conversion.

This module provides functions for adding SHACL validation shapes
to RDF graphs for data quality assurance.
"""

from typing import Any

from rdflib import Literal
from rdflib.namespace import DCTERMS, RDF, XSD

from pyeuropepmc.mappers.config_utils import get_namespace_from_config, load_rdf_config


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
