"""
Configuration utilities for RDF mapping in PyEuropePMC.

This module provides functions for loading RDF configuration from YAML files
and managing namespaces for RDF graphs.
"""

import os
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph, Namespace
import yaml


def load_rdf_config() -> dict[str, Any]:
    """
    Load RDF configuration from YAML file.

    Returns
    -------
    dict[str, Any]
        RDF configuration including named graphs, ontologies, and settings
    """
    try:
        # Default to conf/rdf_map.yml in project root
        base_path = Path(__file__).parent.parent.parent.parent
        config_path = str(base_path / "conf" / "rdf_map.yml")

        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Extract configuration sections
            kg_structure = config.get("_kg_structure", {})
            named_graphs_config = config.get("_named_graphs", {})
            required_named_graphs = config.get("_required_named_graphs", [])
            prefix_config = config.get("_@prefix", {})  # SOURCE OF TRUTH for namespaces
            base_uri = config.get("_base_uri", "http://example.org/data/")

            # Filter enabled named graphs
            enabled_named_graphs = {}
            for graph_name, graph_config in named_graphs_config.items():
                if graph_config.get("enabled", True):
                    enabled_named_graphs[graph_name] = graph_config

            # Create ontologies dict for backwards compatibility
            ontologies = dict(prefix_config)  # Copy prefix_config

            # Add additional ontologies that might not be in _@prefix
            additional_ontologies = {
                "pyeuropepmc": "https://github.com/JonasHeinickeBio/pyeuropepmc#",
                "europepmc": "https://europepmc.org/",
                "ex": base_uri,
            }
            ontologies.update(additional_ontologies)

            return {
                "kg_structure": kg_structure,
                "named_graphs": enabled_named_graphs,  # Only enabled graphs
                "required_named_graphs": required_named_graphs,
                "_@prefix": prefix_config,  # Keep original key for namespace lookups
                "ontologies": ontologies,  # Backwards compatibility
                "base_uri": base_uri,
                "defaults": config.get("_defaults", {}),
                "quality_thresholds": config.get("_quality_thresholds", {}),
            }
        else:
            return _get_default_rdf_config()
    except Exception as e:
        print(f"Failed to load RDF config: {e}, using defaults")
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

        # For Dataset, also bind to default context
        if hasattr(g, "default_context"):
            for prefix, uri in prefix_config.items():
                g.default_context.bind(prefix, Namespace(uri), override=True, replace=True)

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
            g.default_context.bind(prefix, Namespace(uri), override=True, replace=True)

    except Exception as e:
        print(f"Failed to load RDF mapping config: {e}, using fallback namespaces")
        _bind_fallback_namespaces(g)

    # Bind additional namespaces if provided
    if namespaces:
        for prefix, uri in namespaces.items():
            g.bind(prefix, Namespace(uri), override=True, replace=True)
            g.default_context.bind(prefix, Namespace(uri), override=True, replace=True)

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
