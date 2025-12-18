"""
Configuration utilities for RDF mapping in PyEuropePMC.

This module provides functions for loading RDF configuration from YAML files
and managing namespaces for RDF graphs.

Configuration Sources (in order of priority):
1. LinkML schema (schemas/pyeuropepmc_schema.yaml) - Source of truth for data models
2. Runtime config (conf/rdf_config.yaml) - Operational settings
3. Legacy config (conf/rdf_map.yml) - Backward compatibility (deprecated)
"""

import logging
import os
import warnings
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph, Namespace
import yaml

logger = logging.getLogger(__name__)


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


def _load_linkml_namespaces() -> dict[str, str]:
    """
    Load namespace prefixes from the LinkML schema (source of truth).

    Returns
    -------
    dict[str, str]
        Dictionary mapping prefix to URI from LinkML schema.
    """
    try:
        from pyeuropepmc.mappers.linkml_introspection import (
            LINKML_AVAILABLE,
            LinkMLSchemaIntrospector,
        )

        if LINKML_AVAILABLE:
            introspector = LinkMLSchemaIntrospector()
            return introspector.get_namespaces()
    except Exception as e:
        logger.debug(f"Could not load LinkML namespaces: {e}")
    return {}


def _load_runtime_config() -> dict[str, Any]:
    """
    Load runtime configuration from rdf_config.yaml.

    Returns
    -------
    dict[str, Any]
        Runtime configuration dictionary.
    """
    config_path = _get_project_root() / "conf" / "rdf_config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_legacy_config() -> dict[str, Any]:
    """
    Load legacy configuration from rdf_map.yml (deprecated).

    Returns
    -------
    dict[str, Any]
        Legacy configuration dictionary.
    """
    config_path = _get_project_root() / "conf" / "rdf_map.yml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_rdf_config() -> dict[str, Any]:
    """
    Load RDF configuration from multiple sources.

    Configuration is loaded in this priority order:
    1. LinkML schema for namespace prefixes (source of truth)
    2. Runtime config (rdf_config.yaml) for operational settings
    3. Legacy config (rdf_map.yml) for backward compatibility

    Returns
    -------
    dict[str, Any]
        RDF configuration including named graphs, ontologies, and settings
    """
    try:
        # Load from all sources
        linkml_namespaces = _load_linkml_namespaces()
        runtime_config = _load_runtime_config()
        legacy_config = _load_legacy_config()

        # Prefer LinkML namespaces, then legacy _@prefix
        prefix_config = linkml_namespaces or legacy_config.get("_@prefix", {})

        # Get named graphs from runtime config first, then legacy
        named_graphs_config = runtime_config.get("named_graphs", {})
        if not named_graphs_config or named_graphs_config.get("enabled") is False:
            named_graphs_config = legacy_config.get("_named_graphs", {})

        # Filter enabled named graphs
        enabled_named_graphs = {}
        for graph_name, graph_config in named_graphs_config.items():
            if graph_name == "enabled":
                continue
            if isinstance(graph_config, dict) and graph_config.get("enabled", True):
                enabled_named_graphs[graph_name] = graph_config

        # Get KG structure from runtime config first, then legacy
        kg_structure = runtime_config.get("kg_structure", {})
        if not kg_structure:
            kg_structure = legacy_config.get("_kg_structure", {})

        # Build base URI
        uri_config = runtime_config.get("uri", {})
        base_uri = uri_config.get("base", legacy_config.get("_base_uri", "https://w3id.org/pyeuropepmc/"))

        # Create ontologies dict for backwards compatibility
        ontologies = dict(prefix_config)
        additional_ontologies = {
            "pyeuropepmc": "https://w3id.org/pyeuropepmc/vocab#",
            "europepmc": "https://europepmc.org/",
            "ex": base_uri,
        }
        ontologies.update(additional_ontologies)

        # Get required named graphs
        required_named_graphs = runtime_config.get(
            "required_named_graphs",
            legacy_config.get("_required_named_graphs", [])
        )

        # Get quality thresholds
        quality_config = runtime_config.get("quality", {})
        quality_thresholds = quality_config.get(
            "thresholds",
            legacy_config.get("_quality_thresholds", {"high": 0.8, "medium": 0.6, "low": 0.0})
        )

        return {
            "kg_structure": kg_structure,
            "named_graphs": enabled_named_graphs,
            "required_named_graphs": required_named_graphs,
            "_@prefix": prefix_config,
            "ontologies": ontologies,
            "base_uri": base_uri,
            "defaults": kg_structure,  # Map kg_structure to defaults for compatibility
            "quality_thresholds": quality_thresholds,
            # New runtime config sections
            "schema": runtime_config.get("schema", {}),
            "uri": uri_config,
            "performance": runtime_config.get("performance", {}),
            "output": runtime_config.get("output", {}),
            "debugging": runtime_config.get("debugging", {}),
        }
    except Exception as e:
        logger.warning(f"Failed to load RDF config: {e}, using defaults")
        return _get_default_rdf_config()


def _get_default_rdf_config() -> dict[str, Any]:
    """Get default RDF configuration."""
    return {
        "named_graphs": {
            "authors": {
                "title": "Author Entities and Relationships",
                "description": (
                    "Contains all author entities, their affiliations, "
                    "collaborations, and quality metrics"
                ),
                "uri_base": "https://github.com/JonasHeinickeBio/pyeuropepmc#authors",
            },
            "institutions": {
                "title": "Institutional Entities and Hierarchies",
                "description": (
                    "Contains institutional entities, hierarchies, and "
                    "organizational relationships"
                ),
                "uri_base": "https://github.com/JonasHeinickeBio/pyeuropepmc#institutions",
            },
            "publications": {
                "title": "Publication Entities and Citations",
                "description": (
                    "Contains publication entities, citation networks, and "
                    "bibliographic relationships"
                ),
                "uri_base": "https://github.com/JonasHeinickeBio/pyeuropepmc#publications",
            },
            "provenance": {
                "title": "Provenance and Quality Metrics",
                "description": (
                    "Contains provenance information, quality scores, and temporal metadata"
                ),
                "uri_base": "https://github.com/JonasHeinickeBio/pyeuropepmc#provenance",
            },
        },
        "required_named_graphs": ["publications", "authors", "institutions", "provenance"],
        "ontologies": {
            "pyeuropepmc": "https://github.com/JonasHeinickeBio/pyeuropepmc#",
            "europepmc": "https://europepmc.org/",
            "ex": "http://example.org/data/",
            "cito": "http://purl.org/spar/cito/",
            "vivo": "http://vivoweb.org/ontology/core#",
            "fabio": "http://purl.org/spar/fabio/",
            "datacite": "http://purl.org/spar/datacite/",
            "sh": "http://www.w3.org/ns/shacl#",
            "org": "http://www.w3.org/ns/org#",
        },
        "base_uri": "http://example.org/data/",
        "defaults": {
            "include_content": True,
            "enable_citation_networks": True,
            "enable_collaboration_networks": True,
            "enable_institutional_hierarchies": True,
            "enable_quality_metrics": True,
            "enable_shacl_validation": False,
        },
        "quality_thresholds": {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.0,
        },
    }


def get_namespace_from_config(config: dict[str, Any], prefix: str) -> Namespace:
    """Get namespace object from configuration."""
    # Read from _@prefix section in rdf_map.yml (SOURCE OF TRUTH)
    uri = config.get("_@prefix", {}).get(prefix)
    if uri:
        return Namespace(uri)
    # Fallback to standard namespaces
    return Namespace(f"http://example.org/{prefix}#")


def rebind_namespaces(g: Graph | Dataset) -> None:
    """
    Rebind all namespaces from rdf_map.yml to ensure proper prefix usage.

    Call this before serializing a graph to ensure the turtle serializer
    uses the correct prefixes from rdf_map.yml instead of generic ns1, ns2, etc.

    Parameters
    ----------
    g : Graph or Dataset
        RDF graph or dataset to rebind namespaces to

    Examples
    --------
    >>> from rdflib import Dataset
    >>> g = Dataset()
    >>> # ... add triples ...
    >>> rebind_namespaces(g)  # Ensure proper prefixes before serializing
    >>> g.serialize("output.ttl", format="turtle")
    """
    try:
        config = load_rdf_config()
        prefix_config = config.get("_@prefix", {})

        # Bind to main graph/dataset
        for prefix, uri in prefix_config.items():
            g.bind(prefix, Namespace(uri), override=True, replace=True)

        # For Dataset, also bind to default graph
        if hasattr(g, "default_graph"):
            for prefix, uri in prefix_config.items():
                g.default_graph.bind(prefix, Namespace(uri), override=True, replace=True)

        # For Dataset, also bind to all named graphs
        if hasattr(g, "graphs"):
            for graph in g.graphs():
                for prefix, uri in prefix_config.items():
                    graph.bind(prefix, Namespace(uri), override=True, replace=True)
    except Exception as e:
        print(f"Failed to rebind namespaces: {e}")


def setup_graph(namespaces: dict[str, str] | None = None) -> Graph:
    """
    Create and configure a new RDF graph with standard namespaces.

    Binds namespaces from rdf_map.yml (SOURCE OF TRUTH) to ensure proper
    prefix usage in serialized output.

    Parameters
    ----------
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind (prefix -> URI)

    Returns
    -------
    Graph
        Configured RDF graph
    """
    g = Graph()

    # Load namespaces from RDF mapping configuration
    try:
        config = load_rdf_config()
        # Read from _@prefix section in rdf_map.yml (SOURCE OF TRUTH)
        prefix_config = config.get("_@prefix", {})

        for prefix, uri in prefix_config.items():
            g.bind(prefix, Namespace(uri), override=True, replace=True)
    except Exception as e:
        print(f"Failed to load RDF mapping config: {e}, using fallback namespaces")
        _bind_fallback_namespaces(g)

    # Bind additional namespaces if provided
    if namespaces:
        for prefix, uri in namespaces.items():
            g.bind(prefix, Namespace(uri), override=True, replace=True)

    return g


def setup_dataset(namespaces: dict[str, str] | None = None) -> Dataset:
    """
    Create and configure a new RDF dataset with standard namespaces.

    Binds namespaces from rdf_map.yml (SOURCE OF TRUTH) to ensure proper
    prefix usage in serialized output.

    Parameters
    ----------
    namespaces : Optional[Dict[str, str]]
        Additional namespaces to bind (prefix -> URI)

    Returns
    -------
    Dataset
        Configured RDF dataset
    """
    from rdflib import Dataset

    g = Dataset()

    # Load namespaces from RDF mapping configuration
    try:
        config = load_rdf_config()
        # Read from _@prefix section in rdf_map.yml (SOURCE OF TRUTH)
        prefix_config = config.get("_@prefix", {})

        # Bind to main dataset
        for prefix, uri in prefix_config.items():
            g.bind(prefix, Namespace(uri), override=True, replace=True)

        # Also bind to default graph to ensure proper serialization
        for prefix, uri in prefix_config.items():
            g.default_graph.bind(prefix, Namespace(uri), override=True, replace=True)

    except Exception as e:
        print(f"Failed to load RDF mapping config: {e}, using fallback namespaces")
        _bind_fallback_namespaces(g)

    # Bind additional namespaces if provided
    if namespaces:
        for prefix, uri in namespaces.items():
            g.bind(prefix, Namespace(uri), override=True, replace=True)
            g.default_graph.bind(prefix, Namespace(uri), override=True, replace=True)

    return g


def _bind_fallback_namespaces(g: Graph) -> None:
    """
    Bind fallback namespaces when config file cannot be loaded.
    These match the namespaces defined in rdf_map.yml _@prefix section.

    Parameters
    ----------
    g : Graph
        RDF graph to bind namespaces to
    """
    # Fallback namespaces matching rdf_map.yml
    fallback_namespaces = {
        "dcterms": "http://purl.org/dc/terms/",
        "foaf": "http://xmlns.com/foaf/0.1/",
        "bibo": "http://purl.org/ontology/bibo/",
        "prov": "http://www.w3.org/ns/prov#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "nif": "http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "mesh": "http://id.nlm.nih.gov/mesh/",
        "meshv": "http://id.nlm.nih.gov/mesh/vocab#",
        "obo": "http://purl.obolibrary.org/obo/",
        "org": "http://www.w3.org/ns/org#",
        "cito": "http://purl.org/spar/cito/",
        "datacite": "http://purl.org/spar/datacite/",
        "frapo": "http://purl.org/cerif/frapo/",
        "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "ror": "https://ror.org/vocab#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "pyeuropepmc": "https://w3id.org/pyeuropepmc/vocab#",
        "pyeuropepmcdata": "https://w3id.org/pyeuropepmc/data#",
    }

    for prefix, uri in fallback_namespaces.items():
        g.bind(prefix, Namespace(uri))


def create_named_graph(name: str, title: str, description: str) -> Graph:
    """
    Create a named graph for better organization of RDF data.

    Parameters
    ----------
    name : str
        Name identifier for the graph
    title : str
        Human-readable title
    description : str
        Description of the graph's contents

    Returns
    -------
    Graph
        Configured named graph
    """
    ng = Graph()

    # Load RDF config for ontologies
    config = load_rdf_config()
    ontologies = config.get("ontologies", {})

    # Bind ontologies from config
    for prefix, uri in ontologies.items():
        ng.bind(prefix, Namespace(uri))

    # Bind standard namespaces
    from rdflib.namespace import RDF, RDFS, XSD

    ng.bind("rdf", RDF)
    ng.bind("rdfs", RDFS)
    ng.bind("xsd", XSD)

    return ng
