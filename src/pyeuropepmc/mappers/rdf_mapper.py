"""
RDF Mapper for converting entities to RDF triples based on YAML configuration.
"""

import os
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
import yaml

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

    def __init__(self, config_path: str | None = None):
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

        with open(config_path, encoding="utf-8") as f:
            config: dict[str, Any] = yaml.safe_load(f)

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

        # Map multi-value fields
        multi_value_mapping = mapping.get("multi_value_fields", {})
        for field_name, predicate_str in multi_value_mapping.items():
            values = getattr(entity, field_name, None)
            if values is not None and isinstance(values, list):
                predicate = self._resolve_predicate(predicate_str)
                for value in values:
                    if value is not None:
                        g.add((subject, predicate, Literal(value)))

    def map_relationships(
        self,
        g: Graph,
        subject: URIRef,
        entity: Any,
        related_entities: dict[str, list[Any]] | None = None,
    ) -> None:
        """
        Map entity relationships to RDF triples based on configuration.

        Parameters
        ----------
        g : Graph
            RDF graph to add triples to
        subject : URIRef
            Subject URI for the entity
        entity : Any
            Entity instance to map
        related_entities : Optional[dict[str, list[Any]]]
            Dictionary of related entities by relationship name

        Examples
        --------
        >>> from rdflib import Graph, URIRef
        >>> from pyeuropepmc.models import PaperEntity, AuthorEntity
        >>> mapper = RDFMapper()
        >>> paper = PaperEntity(title="Test Article")
        >>> authors = [AuthorEntity(full_name="John Doe")]
        >>> g = Graph()
        >>> subject = URIRef("http://example.org/paper1")
        >>> related = {"authors": authors}
        >>> mapper.map_relationships(g, subject, paper, related)
        """
        entity_class_name = entity.__class__.__name__
        mapping = self.config.get(entity_class_name, {})
        related_entities = related_entities or {}

        # Map relationships
        relationships_mapping = mapping.get("relationships", {})
        for rel_name, rel_config in relationships_mapping.items():
            predicate_str = rel_config.get("predicate")
            inverse_predicate = rel_config.get("inverse")

            if predicate_str and rel_name in related_entities:
                predicate = self._resolve_predicate(predicate_str)
                related_objs = related_entities[rel_name]

                for related_obj in related_objs:
                    # Generate URI for related object
                    related_uri = self._generate_entity_uri(related_obj)

                    # Add relationship triple
                    g.add((subject, predicate, related_uri))

                    # Add inverse relationship if specified
                    if inverse_predicate:
                        inv_predicate = self._resolve_predicate(inverse_predicate)
                        g.add((related_uri, inv_predicate, subject))

    def _normalize_name(self, name: str) -> str | None:
        """
        Normalize an author name for use in URIs.

        Parameters
        ----------
        name : str
            Author full name

        Returns
        -------
        str | None
            Normalized name suitable for URIs, or None if empty
        """
        if not name:
            return None
        import re

        # Remove non-alphanumeric except spaces, lowercase, replace spaces with hyphens
        normalized = re.sub(r"[^a-zA-Z0-9\s]", "", name).lower().strip()
        normalized = re.sub(r"\s+", "-", normalized)
        return normalized if normalized else None

    def _generate_entity_uri(self, entity: Any) -> URIRef:
        """
        Generate a resolvable URI for an entity based on its identifiers.

        Parameters
        ----------
        entity : Any
            Entity instance

        Returns
        -------
        URIRef
            Generated URI for the entity

        Examples
        --------
        >>> from pyeuropepmc.models import PaperEntity
        >>> mapper = RDFMapper()
        >>> paper = PaperEntity(doi="10.1234/test.2021.001", pmcid="PMC1234567")
        >>> uri = mapper._generate_entity_uri(paper)
        >>> print(uri)
        https://doi.org/10.1234/test.2021.001
        """
        entity_class = entity.__class__.__name__

        # DOI-based URIs for papers
        if entity_class == "PaperEntity" and entity.doi:
            return URIRef(f"https://doi.org/{entity.doi}")

        # PMC-based URIs for papers
        if entity_class == "PaperEntity" and entity.pmcid:
            return URIRef(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{entity.pmcid}/")

        # Author URIs
        if entity_class == "AuthorEntity":
            if getattr(entity, "orcid", None):
                return URIRef(f"https://orcid.org/{entity.orcid}")
            elif getattr(entity, "openalex_id", None):
                return URIRef(entity.openalex_id)
            else:
                normalized_name = self._normalize_name(
                    getattr(entity, "full_name", "") or getattr(entity, "name", "")
                )
                if normalized_name:
                    return URIRef(f"http://example.org/data/author/{normalized_name}")

        # Institution URIs
        if entity_class == "InstitutionEntity":
            if getattr(entity, "ror_id", None):
                return URIRef(entity.ror_id)
            elif getattr(entity, "openalex_id", None):
                return URIRef(entity.openalex_id)
            elif getattr(entity, "display_name", None):
                normalized_name = self._normalize_name(entity.display_name)
                if normalized_name:
                    return URIRef(f"http://example.org/data/institution/{normalized_name}")

        # DOI-based URIs for references
        if entity_class == "ReferenceEntity" and getattr(entity, "doi", None):
            return URIRef(f"https://doi.org/{entity.doi}")

        # Fallback to internal URIs
        if hasattr(entity, "mint_uri"):
            return URIRef(entity.mint_uri(entity_class.lower().replace("entity", "")))
        else:
            # Generate UUID-based URI
            import uuid

            entity_id = getattr(entity, "id", None) or str(uuid.uuid4())
            return URIRef(
                f"http://example.org/data/{entity_class.lower().replace('entity', '')}/{entity_id}"
            )

    def add_provenance(
        self, g: Graph, subject: URIRef, entity: Any, extraction_info: dict[str, Any] | None = None
    ) -> None:
        """
        Add provenance information to the RDF graph.

        Parameters
        ----------
        g : Graph
            RDF graph to add triples to
        subject : URIRef
            Subject URI for the entity
        entity : Any
            Entity instance
        extraction_info : Optional[dict[str, Any]]
            Additional extraction metadata

        Examples
        --------
        >>> from rdflib import Graph, URIRef
        >>> from pyeuropepmc.models import PaperEntity
        >>> mapper = RDFMapper()
        >>> paper = PaperEntity(title="Test Article")
        >>> g = Graph()
        >>> subject = URIRef("http://example.org/paper1")
        >>> extraction_info = {"timestamp": "2024-01-01T00:00:00Z", "method": "xml_parser"}
        >>> mapper.add_provenance(g, subject, paper, extraction_info)
        """
        from datetime import datetime

        extraction_info = extraction_info or {}

        # Add extraction timestamp
        timestamp = extraction_info.get("timestamp") or datetime.now().isoformat()
        g.add((subject, self._resolve_predicate("prov:generatedAtTime"), Literal(timestamp)))

        # Add extraction method
        method = extraction_info.get("method", "pyeuropepmc_parser")
        g.add((subject, self._resolve_predicate("prov:wasGeneratedBy"), Literal(method)))

        # Add source information
        if entity.source_uri:
            g.add(
                (
                    subject,
                    self._resolve_predicate("prov:wasDerivedFrom"),
                    URIRef(entity.source_uri),
                )
            )

        # Add enrichment sources if available (from AuthorEntity or PaperEntity)
        if hasattr(entity, "sources") and entity.sources:
            for source in entity.sources:
                g.add((subject, self._resolve_predicate("prov:hadPrimarySource"), Literal(source)))

        # Add confidence score if available
        if hasattr(entity, "confidence") and entity.confidence is not None:
            g.add((subject, self._resolve_predicate("ex:confidence"), Literal(entity.confidence)))

        # Add data quality indicators
        quality_info = extraction_info.get("quality", {})
        if quality_info.get("validation_passed"):
            g.add((subject, self._resolve_predicate("ex:validationStatus"), Literal("passed")))
        if quality_info.get("completeness_score"):
            g.add(
                (
                    subject,
                    self._resolve_predicate("ex:completenessScore"),
                    Literal(quality_info["completeness_score"]),
                )
            )

    def map_ontology_alignments(self, g: Graph, subject: URIRef, entity: Any) -> None:
        """
        Add ontology alignment placeholders and biomedical mappings.

        Parameters
        ----------
        g : Graph
            RDF graph to add triples to
        subject : URIRef
            Subject URI for the entity
        entity : Any
            Entity instance

        Examples
        --------
        >>> from rdflib import Graph, URIRef
        >>> from pyeuropepmc.models import PaperEntity
        >>> mapper = RDFMapper()
        >>> paper = PaperEntity(title="Test Article", keywords=["COVID-19", "SARS-CoV-2"])
        >>> g = Graph()
        >>> subject = URIRef("http://example.org/paper1")
        >>> mapper.map_ontology_alignments(g, subject, paper)
        """
        entity_class_name = entity.__class__.__name__

        if entity_class_name == "PaperEntity":
            self._map_paper_ontology_alignments(g, subject, entity)
        elif entity_class_name == "AuthorEntity":
            self._map_author_ontology_alignments(g, subject, entity)
        elif entity_class_name == "InstitutionEntity":
            self._map_institution_ontology_alignments(g, subject, entity)
        elif entity_class_name == "ReferenceEntity":
            self._map_reference_ontology_alignments(g, subject, entity)

        # Add owl:sameAs links for external identifiers
        self._add_external_identifiers(g, subject, entity)

    def _map_paper_ontology_alignments(self, g: Graph, subject: URIRef, entity: Any) -> None:
        """Map ontology alignments for paper entities."""
        # MeSH terms alignment (placeholder)
        if hasattr(entity, "keywords") and entity.keywords:
            for keyword in entity.keywords:
                g.add((subject, self._resolve_predicate("mesh:hasSubject"), Literal(keyword)))

        # Research domain classification (placeholder)
        if hasattr(entity, "research_domain"):
            g.add(
                (
                    subject,
                    self._resolve_predicate("obo:RO_0000053"),
                    Literal(entity.research_domain),
                )
            )

    def _map_author_ontology_alignments(self, g: Graph, subject: URIRef, entity: Any) -> None:
        """Map ontology alignments for author entities."""
        # Note: Institutions are now handled via relationships instead of literal affiliations
        pass

    def _map_institution_ontology_alignments(
        self, g: Graph, subject: URIRef, entity: Any
    ) -> None:
        """Map ontology alignments for institution entities."""
        # Add geographic coordinates if available
        if hasattr(entity, "latitude") and hasattr(entity, "longitude"):
            if entity.latitude is not None and entity.longitude is not None:
                # Already handled in fields mapping, but can add geo:SpatialThing type
                g.add((subject, self._resolve_predicate("rdf:type"), URIRef("http://www.w3.org/2003/01/geo/wgs84_pos#SpatialThing")))

    def _map_reference_ontology_alignments(self, g: Graph, subject: URIRef, entity: Any) -> None:
        """Map ontology alignments for reference entities."""
        # Currently no specific alignments for references
        pass

    def _add_external_identifiers(self, g: Graph, subject: URIRef, entity: Any) -> None:
        """Add owl:sameAs links for external identifiers."""
        entity_class_name = entity.__class__.__name__

        if entity_class_name == "PaperEntity":
            if entity.doi:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(f"https://doi.org/{entity.doi}"),
                    )
                )
            if entity.pmcid:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{entity.pmcid}/"),
                    )
                )

        elif entity_class_name == "AuthorEntity":
            if hasattr(entity, "orcid") and entity.orcid:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(f"https://orcid.org/{entity.orcid}"),
                    )
                )
            if hasattr(entity, "openalex_id") and entity.openalex_id:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(entity.openalex_id),
                    )
                )

        elif entity_class_name == "InstitutionEntity":
            if hasattr(entity, "ror_id") and entity.ror_id:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(entity.ror_id),
                    )
                )
            if hasattr(entity, "openalex_id") and entity.openalex_id:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(entity.openalex_id),
                    )
                )
            if hasattr(entity, "wikidata_id") and entity.wikidata_id:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(f"https://www.wikidata.org/wiki/{entity.wikidata_id}"),
                    )
                )

        elif entity_class_name == "ReferenceEntity":
            if hasattr(entity, "doi") and entity.doi:
                g.add(
                    (
                        subject,
                        self._resolve_predicate("owl:sameAs"),
                        URIRef(f"https://doi.org/{entity.doi}"),
                    )
                )

    def serialize_graph(
        self, g: Graph, format: str = "turtle", destination: str | None = None
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
            return str(g.serialize(format=format))
