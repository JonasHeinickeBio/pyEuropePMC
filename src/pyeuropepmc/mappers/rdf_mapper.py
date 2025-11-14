"""
RDF Mapper for converting entities to RDF triples based on YAML configuration.
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

__all__ = ["RDFMapper"]


class RDFMapper:
    """
    RDF mapper that loads configuration from YAML and maps entity fields to RDF.

    This class handles the conversion of entity dataclass fields to RDF triples
    using a configuration file that defines the mappings between fields and predicates.

    Attributes
    ----------
    config : dict
        Loaded YAML configuration containing mappings
    namespaces : dict
        Dictionary of namespace prefix to Namespace objects

    Examples
    --------
    >>> from rdflib import Graph
    >>> from pyeuropepmc.models import PaperEntity
    >>> mapper = RDFMapper()
    >>> paper = PaperEntity(pmcid="PMC123", title="Test")
    >>> g = Graph()
    >>> uri = paper.to_rdf(g, mapper=mapper)
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the RDF mapper with configuration.

        Parameters
        ----------
        config_path : Optional[str]
            Path to the YAML configuration file. If None, uses default.
        """
        if config_path is None:
            # Default to conf/rdf_map.yml in project root
            base_path = Path(__file__).parent.parent.parent.parent
            config_path = str(base_path / "conf" / "rdf_map.yml")

        self.config = self._load_config(config_path)
        self.namespaces = self._build_namespaces()

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """
        Load YAML configuration file.

        Parameters
        ----------
        config_path : str
            Path to the configuration file

        Returns
        -------
        dict
            Loaded configuration

        Raises
        ------
        FileNotFoundError
            If config file doesn't exist
        yaml.YAMLError
            If config file is invalid YAML
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"RDF mapping config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config

    def _build_namespaces(self) -> dict[str, Namespace]:
        """
        Build namespace dictionary from config.

        Returns
        -------
        dict
            Dictionary mapping prefix to Namespace object
        """
        prefix_config = self.config.get("_@prefix", {})
        namespaces = {}

        for prefix, uri in prefix_config.items():
            namespaces[prefix] = Namespace(uri)

        return namespaces

    def _resolve_predicate(self, predicate_str: str) -> URIRef:
        """
        Resolve a CURIE predicate string to a URIRef.

        Parameters
        ----------
        predicate_str : str
            Predicate in CURIE format (e.g., "dct:title")

        Returns
        -------
        URIRef
            Resolved URIRef for the predicate

        Examples
        --------
        >>> mapper = RDFMapper()
        >>> uri = mapper._resolve_predicate("dct:title")
        >>> print(uri)
        http://purl.org/dc/terms/title
        """
        if ":" in predicate_str:
            prefix, local = predicate_str.split(":", 1)
            if prefix in self.namespaces:
                return self.namespaces[prefix][local]

        # If no prefix or unknown prefix, return as-is wrapped in URIRef
        return URIRef(predicate_str)

    def add_types(self, g: Graph, subject: URIRef, types: list[str]) -> None:
        """
        Add RDF type triples to the graph.

        Parameters
        ----------
        g : Graph
            RDF graph to add to
        subject : URIRef
            Subject URI
        types : list[str]
            List of type CURIEs or URIs

        Examples
        --------
        >>> from rdflib import Graph, URIRef
        >>> mapper = RDFMapper()
        >>> g = Graph()
        >>> subject = URIRef("http://example.org/paper1")
        >>> mapper.add_types(g, subject, ["bibo:AcademicArticle"])
        """
        for type_str in types:
            type_uri = self._resolve_predicate(type_str)
            g.add((subject, RDF.type, type_uri))

    def map_fields(self, g: Graph, subject: URIRef, entity: Any) -> None:
        """
        Map entity fields to RDF triples based on configuration.

        Parameters
        ----------
        g : Graph
            RDF graph to add triples to
        subject : URIRef
            Subject URI for the entity
        entity : Any
            Entity instance to map

        Examples
        --------
        >>> from rdflib import Graph, URIRef
        >>> from pyeuropepmc.models import PaperEntity
        >>> mapper = RDFMapper()
        >>> paper = PaperEntity(title="Test Article")
        >>> g = Graph()
        >>> subject = URIRef("http://example.org/paper1")
        >>> mapper.map_fields(g, subject, paper)
        """
        entity_class_name = entity.__class__.__name__
        mapping = self.config.get(entity_class_name, {})

        # Map single-value fields
        fields_mapping = mapping.get("fields", {})
        for field_name, predicate_str in fields_mapping.items():
            value = getattr(entity, field_name, None)
            if value is not None:
                predicate = self._resolve_predicate(predicate_str)
                g.add((subject, predicate, Literal(value)))

        # Map multi-value fields (lists)
        multi_value_mapping = mapping.get("multi_value_fields", {})
        for field_name, predicate_str in multi_value_mapping.items():
            values = getattr(entity, field_name, [])
            if values:
                predicate = self._resolve_predicate(predicate_str)
                for value in values:
                    g.add((subject, predicate, Literal(value)))

    def serialize_graph(
        self, g: Graph, format: str = "turtle", destination: Optional[str] = None
    ) -> str:
        """
        Serialize RDF graph to string or file.

        Parameters
        ----------
        g : Graph
            RDF graph to serialize
        format : str
            Serialization format (turtle, xml, json-ld, etc.)
        destination : Optional[str]
            File path to write to (if None, returns string)

        Returns
        -------
        str
            Serialized RDF (empty string if written to file)

        Examples
        --------
        >>> from rdflib import Graph
        >>> mapper = RDFMapper()
        >>> g = Graph()
        >>> # ... add triples to g ...
        >>> ttl = mapper.serialize_graph(g, format="turtle")
        """
        if destination:
            g.serialize(destination=destination, format=format)
            return ""
        else:
            return g.serialize(format=format)
