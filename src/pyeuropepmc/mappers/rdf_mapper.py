"""
RDF Mapper for converting entities to RDF triples based on YAML configuration.
"""

import os
from pathlib import Path
from typing import Any

from rdflib import BNode, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF
import yaml

from pyeuropepmc.mappers.rdf_utils import (
    map_multi_value_fields,
    map_ontology_alignments,
    map_single_value_fields,
    normalize_name,
)

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

    def __init__(self, config_path: str | None = None, enable_named_graphs: bool = True):
        """
        Initialize the RDF mapper with configuration.

        Parameters
        ----------
        config_path : Optional[str]
            Path to the YAML configuration file. If None, uses default.
        enable_named_graphs : bool
            Whether to enable named graphs for entity organization. Default True.
        """
        if config_path is None:
            # Default to conf/rdf_map.yml in project root
            base_path = Path(__file__).parent.parent.parent.parent
            config_path = str(base_path / "conf" / "rdf_map.yml")

        self.config = self._load_config(config_path)
        self.enable_named_graphs = enable_named_graphs
        self.namespaces = self._build_namespaces()

        # Configuration options for KG structure
        self.kg_config = self.config.get("_kg_structure", {})
        self.default_include_content = self.kg_config.get("include_content", True)
        self.default_kg_type = self.kg_config.get(
            "default_type", "complete"
        )  # "complete", "metadata", "content"

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

    def _get_named_graph_uri(self, entity_type: str) -> URIRef | None:
        """
        Get the named graph URI for a given entity type.

        Parameters
        ----------
        entity_type : str
            The entity type (e.g., 'author', 'institution', 'paper', 'provenance')

        Returns
        -------
        URIRef or None
            The named graph URI if configured and enabled, None otherwise
        """
        if not self.enable_named_graphs:
            return None

        named_graphs = self.config.get("_named_graphs", {})
        graph_config = named_graphs.get(entity_type)

        if graph_config and graph_config.get("enabled", False):
            uri_base = graph_config.get("uri_base")
            if uri_base:
                return URIRef(uri_base)

        return None

    @staticmethod
    def _is_valid_uri(uri_string: str) -> bool:
        """
        Check if a string looks like a valid URI.

        Parameters
        ----------
        uri_string : str
            String to validate as URI

        Returns
        -------
        bool
            True if string appears to be a valid URI

        Examples
        --------
        >>> RDFMapper._is_valid_uri("http://example.com")
        True
        >>> RDFMapper._is_valid_uri("BMJ Open Respir Res")
        False
        """
        if not uri_string or not isinstance(uri_string, str):
            return False

        # Basic URI validation - must have scheme (protocol) like http://, https://, ftp://, etc.
        # This is a simple check - rdflib's URIRef will do more thorough validation
        return "://" in uri_string and len(uri_string.split("://", 1)[0]) > 0

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

    def add_types(
        self, g: Any, subject: URIRef, types: list[str], context: URIRef | None = None
    ) -> None:
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
        context : Optional[URIRef]
            Named graph context to add triples to (for ConjunctiveGraph)

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
            if context:
                g.graph(context).add((subject, RDF.type, type_uri))
            else:
                g.add((subject, RDF.type, type_uri))

    def map_fields(
        self, g: Any, subject: URIRef, entity: Any, context: URIRef | None = None
    ) -> None:
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
        # Get mappings for this class and all parent classes
        all_mappings = self._get_entity_mappings(entity)

        for mapping in all_mappings:
            # Map single-value fields
            self._map_single_value_fields(g, subject, entity, mapping, context)

            # Map multi-value fields
            self._map_multi_value_fields(g, subject, entity, mapping, context)

            # Map complex fields (dicts, nested structures)
            self._map_complex_fields(g, subject, entity, mapping, context)

    def _get_entity_mappings(self, entity: Any) -> list[dict[str, Any]]:
        """Get mappings for entity class and parent classes."""
        all_mappings = []
        for cls in entity.__class__.__mro__:
            if cls.__name__.endswith("Entity"):
                mapping = self.config.get(cls.__name__, {})
                if mapping:
                    all_mappings.append(mapping)

        # If no mappings found, try direct class name lookup as fallback
        if not all_mappings:
            mapping = self.config.get(entity.__class__.__name__, {})
            all_mappings = [mapping] if mapping else []

        return all_mappings

    def _map_single_value_fields(
        self,
        g: Any,
        subject: URIRef,
        entity: Any,
        mapping: dict[str, Any],
        context: URIRef | None = None,
    ) -> None:
        """Map single-value fields to RDF triples."""
        fields_mapping = mapping.get("fields", {})
        map_single_value_fields(
            g, subject, entity, fields_mapping, self._resolve_predicate, context
        )

    def _map_multi_value_fields(
        self,
        g: Any,
        subject: URIRef,
        entity: Any,
        mapping: dict[str, Any],
        context: URIRef | None = None,
    ) -> None:
        """Map multi-value fields to RDF triples."""
        multi_value_mapping = mapping.get("multi_value_fields", {})
        map_multi_value_fields(
            g, subject, entity, multi_value_mapping, self._resolve_predicate, context
        )

    def _map_complex_fields(
        self,
        g: Any,
        subject: URIRef,
        entity: Any,
        mapping: dict[str, Any],
        context: URIRef | None = None,
    ) -> None:
        """Map complex fields (dicts, nested structures) to RDF triples."""
        from rdflib import XSD, Literal

        complex_mapping = mapping.get("complex_fields", {})

        for field_name, predicate_str in complex_mapping.items():
            value = getattr(entity, field_name, None)
            if value is None:
                continue

            predicate = self._resolve_predicate(predicate_str)

            # Handle external_ids dict (e.g., {'pmcid': '12311175', 'doi': '10.1038/...'})
            if field_name == "external_ids" and isinstance(value, dict):
                for id_type, id_value in value.items():
                    if id_value:
                        # Create a blank node for each identifier
                        id_node = BNode()
                        g.add(
                            (subject, predicate, id_node, context)
                            if context
                            else (subject, predicate, id_node)
                        )
                        g.add(
                            (id_node, DCTERMS.type, Literal(id_type), context)
                            if context
                            else (id_node, DCTERMS.type, Literal(id_type))
                        )
                        g.add(
                            (id_node, RDF.value, Literal(id_value), context)
                            if context
                            else (id_node, RDF.value, Literal(id_value))
                        )

            # Handle license dict (e.g., {'url': 'https://...', 'text': '...'})
            elif field_name == "license" and isinstance(value, dict):
                license_url = value.get("url")
                license_text = value.get("text")

                if license_url:
                    # License URL as direct object
                    g.add(
                        (subject, predicate, URIRef(license_url), context)
                        if context
                        else (subject, predicate, URIRef(license_url))
                    )

                if license_text:
                    # License text as additional property
                    license_text_pred = self._resolve_predicate("dcterms:rights")
                    g.add(
                        (
                            subject,
                            license_text_pred,
                            Literal(license_text, datatype=XSD.string),
                            context,
                        )
                        if context
                        else (
                            subject,
                            license_text_pred,
                            Literal(license_text, datatype=XSD.string),
                        )
                    )

            # Handle funders list (list of dicts with fundref_doi, award_id, etc.)
            elif field_name == "funders" and isinstance(value, list):
                for funder in value:
                    if isinstance(funder, dict):
                        # Create blank node for grant/funding
                        grant_node = BNode()
                        g.add(
                            (subject, predicate, grant_node, context)
                            if context
                            else (subject, predicate, grant_node)
                        )
                        g.add(
                            (grant_node, RDF.type, self._resolve_predicate("frapo:Grant"), context)
                            if context
                            else (grant_node, RDF.type, self._resolve_predicate("frapo:Grant"))
                        )

                        # Add funder DOI/FundRef
                        fundref_doi = funder.get("fundref_doi")
                        if fundref_doi:
                            g.add(
                                (
                                    grant_node,
                                    self._resolve_predicate("datacite:doi"),
                                    URIRef(fundref_doi),
                                    context,
                                )
                                if context
                                else (
                                    grant_node,
                                    self._resolve_predicate("datacite:doi"),
                                    URIRef(fundref_doi),
                                )
                            )

                        # Add award ID
                        award_id = funder.get("award_id")
                        if award_id:
                            g.add(
                                (
                                    grant_node,
                                    self._resolve_predicate("datacite:identifier"),
                                    Literal(award_id),
                                    context,
                                )
                                if context
                                else (
                                    grant_node,
                                    self._resolve_predicate("datacite:identifier"),
                                    Literal(award_id),
                                )
                            )

                        # Add recipient
                        recipient = funder.get("recipient_full") or funder.get("recipient_name")
                        if recipient:
                            g.add(
                                (
                                    grant_node,
                                    self._resolve_predicate("foaf:fundedBy"),
                                    Literal(recipient),
                                    context,
                                )
                                if context
                                else (
                                    grant_node,
                                    self._resolve_predicate("foaf:fundedBy"),
                                    Literal(recipient),
                                )
                            )

    def map_relationships(
        self,
        g: Any,
        subject: URIRef,
        entity: Any,
        related_entities: dict[str, list[Any]] | None = None,
        extraction_info: dict[str, Any] | None = None,
        context: URIRef | None = None,
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
        extraction_info : Optional[dict[str, Any]]
            Additional extraction metadata for provenance

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

            if predicate_str:
                # Check if related objects are provided in related_entities dict
                related_objs = related_entities.get(rel_name) if related_entities else None

                # If not in related_entities, check if it's an attribute of the entity
                if related_objs is None and hasattr(entity, rel_name):
                    attr_value = getattr(entity, rel_name)
                    if attr_value is not None:
                        related_objs = attr_value if isinstance(attr_value, list) else [attr_value]

                if related_objs:
                    predicate = self._resolve_predicate(predicate_str)

                    for related_obj in related_objs:
                        if related_obj is not None:
                            # Generate URI for related object
                            related_uri = self._generate_entity_uri(related_obj)

                            # Add relationship triple
                            if context:
                                g.graph(context).add((subject, predicate, related_uri))
                            else:
                                g.add((subject, predicate, related_uri))

                            # Add inverse relationship if specified
                            if inverse_predicate:
                                inv_predicate = self._resolve_predicate(inverse_predicate)
                                if context:
                                    g.graph(context).add((related_uri, inv_predicate, subject))
                                else:
                                    g.add((related_uri, inv_predicate, subject))

                            # Generate detailed RDF for the related entity
                            if hasattr(related_obj, "to_rdf"):
                                related_obj.to_rdf(
                                    g,
                                    uri=related_uri,
                                    mapper=self,
                                    extraction_info=extraction_info,
                                )

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
        return normalize_name(name)

    def _generate_entity_uri(self, entity: Any) -> URIRef:
        """
        Generate a URI for an entity using the centralized URI factory.

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
        from pyeuropepmc.mappers.rdf_utils import uri_factory

        return uri_factory.generate_uri(entity)

    def generate_uri(self, entity_type: str, entity: Any) -> URIRef:
        """
        Generate a URI for an entity of a specific type.

        This is a convenience method that allows generating URIs by specifying
        the entity type as a string.

        Parameters
        ----------
        entity_type : str
            Type of entity ("paper", "author", "institution", etc.)
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
        >>> paper = PaperEntity(doi="10.1234/test.2021.001")
        >>> uri = mapper.generate_uri("paper", paper)
        >>> print(uri)
        https://doi.org/10.1234/test.2021.001
        """
        return self._generate_entity_uri(entity)

    def add_provenance(
        self,
        g: Any,
        subject: URIRef,
        entity: Any,
        extraction_info: dict[str, Any] | None = None,
        context: URIRef | None = None,
    ) -> None:
        """
        Add provenance information to the RDF graph.

        Only adds provenance if it hasn't been added already for this subject.

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

        # Check if provenance has already been added for this subject
        prov_predicate = self._resolve_predicate("prov:generatedAtTime")
        target_graph = g.graph(context) if context else g

        # If provenance already exists, don't add it again
        if (subject, prov_predicate, None) in target_graph:
            return

        # Add extraction timestamp
        timestamp = extraction_info.get("timestamp") or datetime.now().isoformat()
        target_graph.add((subject, prov_predicate, Literal(timestamp)))

        # Add extraction method
        method = extraction_info.get("method", "pyeuropepmc_parser")
        target_graph.add(
            (subject, self._resolve_predicate("prov:wasGeneratedBy"), Literal(method))
        )

        # Add source information
        if entity.source_uri and self._is_valid_uri(entity.source_uri):
            target_graph.add(
                (
                    subject,
                    self._resolve_predicate("prov:wasDerivedFrom"),
                    URIRef(entity.source_uri),
                )
            )

        # Add enrichment sources if available (from AuthorEntity or PaperEntity)
        if hasattr(entity, "sources") and entity.sources:
            for source in entity.sources:
                target_graph.add(
                    (
                        subject,
                        self._resolve_predicate("prov:hadPrimarySource"),
                        Literal(source),
                    )
                )

        # Add confidence score if available
        if hasattr(entity, "confidence") and entity.confidence is not None:
            target_graph.add(
                (
                    subject,
                    self._resolve_predicate("ex:confidence"),
                    Literal(entity.confidence),
                )
            )

        # Add data quality indicators
        quality_info = extraction_info.get("quality", {})
        if quality_info.get("validation_passed"):
            target_graph.add(
                (subject, self._resolve_predicate("ex:validationStatus"), Literal("passed"))
            )
        if quality_info.get("completeness_score"):
            target_graph.add(
                (
                    subject,
                    self._resolve_predicate("ex:completenessScore"),
                    Literal(quality_info["completeness_score"]),
                )
            )

    def map_ontology_alignments(
        self, g: Any, subject: URIRef, entity: Any, context: URIRef | None = None
    ) -> None:
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
        map_ontology_alignments(g, subject, entity, self._resolve_predicate, context)

    def _bind_namespaces(self, g: Any) -> None:
        """
        Bind namespaces to the graph for proper serialization.

        Parameters
        ----------
        g : Graph
            RDF graph to bind namespaces to
        """
        for prefix, namespace in self.namespaces.items():
            g.bind(prefix, namespace)

    def serialize_graph(
        self, g: Any, format: str = "turtle", destination: str | None = None
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
        # Bind namespaces from configuration to ensure proper prefixes
        self._bind_namespaces(g)

        # Use TriG format for Dataset (named graphs), Turtle for regular Graph
        actual_format = "trig" if hasattr(g, "graphs") else format

        if destination:
            g.serialize(destination=destination, format=actual_format)
            return ""
        else:
            return str(g.serialize(format=actual_format))

    def convert_and_save_entities_to_rdf(
        self,
        entities_data: dict[str, dict[str, Any]],
        output_dir: str = "rdf_output",
        prefix: str = "",
        extraction_info: dict[str, Any] | None = None,
        filename_template: str | None = None,
        include_content: bool = True,
    ) -> dict[str, Any]:
        """
        Convert a dictionary of entities to RDF graphs and save them to files.

        This method is modular and reusable for any type of entity that has a to_rdf method.

        Parameters
        ----------
        entities_data : dict
            Dictionary mapping identifier to entity data. Each value should be a dict
            containing at least 'entity' key, and optionally 'related_entities' key.
            Example: {
                "doi1": {
                    "entity": paper_obj,
                    "related_entities": {"authors": [...], "references": [...]}
                },
                "doi2": {"entity": paper_obj2, "related_entities": {...}}
            }
        output_dir : str
            Directory to save RDF files
        prefix : str
            Prefix for filename (e.g., "enriched_")
        extraction_info : Optional[dict]
            Extraction metadata for provenance
        filename_template : Optional[str]
            Template for filename generation. Can use {prefix}, {identifier}, {entity_type}.
            Default: "{prefix}{entity_type}_{identifier}.ttl"
        include_content : bool
            Whether to include content entities (sections, references, tables, figures).
            If False, only metadata entities (papers, authors, institutions) are included.

        Returns
        -------
        dict
            Dictionary mapping identifier to RDF Graph objects
        """
        from datetime import datetime

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        rdf_graphs = {}

        for identifier, entity_data in entities_data.items():
            try:
                entity = entity_data["entity"]
                related_entities = entity_data.get("related_entities", {})

                # Filter related entities based on include_content flag
                if not include_content:
                    related_entities = self._filter_metadata_entities(related_entities)

                entity_type = entity.__class__.__name__.lower().replace("entity", "")
                print(f"Converting to RDF: {identifier} ({entity_type})")

                # Create RDF graph
                g = Dataset()

                # Bind namespaces immediately to ensure proper prefixes during serialization
                self._bind_namespaces(g)

                # Prepare extraction info for provenance
                current_extraction_info = extraction_info or {
                    "timestamp": datetime.now().isoformat() + "Z",
                    "method": "pyeuropepmc_parser",
                    "quality": {"validation_passed": True, "completeness_score": 0.95},
                }

                # Convert entity to RDF with relationships
                entity.to_rdf(
                    g,
                    mapper=self,
                    related_entities=related_entities,
                    extraction_info=current_extraction_info,
                )

                if g:
                    rdf_graphs[identifier] = g
                    # Count triples in the graph
                    triple_count = len(list(g))
                    print(f"  [OK] Successfully converted to RDF ({triple_count} triples)")

                    # Generate filename
                    if filename_template is None:
                        safe_identifier = identifier.replace("/", "_").replace(".", "_")
                        filename = f"{output_dir}/{prefix}{entity_type}_{safe_identifier}.ttl"
                    else:
                        safe_identifier = identifier.replace("/", "_").replace(".", "_")
                        filename = filename_template.format(
                            prefix=prefix, identifier=safe_identifier, entity_type=entity_type
                        )

                    try:
                        self.serialize_graph(g, format="turtle", destination=filename)
                        print(f"  [OK] Saved to: {filename}")
                    except Exception as e:
                        print(f"  [ERROR] Error saving {filename}: {str(e)}")
                else:
                    print(f"  [ERROR] Failed to convert {identifier} to RDF")

            except Exception as e:
                print(f"  [ERROR] Error converting {identifier}: {str(e)}")

        print(f"Successfully converted {len(rdf_graphs)} entities to RDF")
        return rdf_graphs

    def convert_and_save_papers_to_rdf(
        self,
        papers_dict: dict[str, tuple[Any, list[Any], list[Any], list[Any], list[Any], list[Any]]],
        output_dir: str = "rdf_output",
        prefix: str = "",
        extraction_info: dict[str, Any] | None = None,
        include_content: bool | None = None,
    ) -> dict[str, Graph]:
        """
        Convert a dictionary of papers to RDF graphs and save them to files.

        This is a convenience method for paper-specific conversion that maintains
        backward compatibility.

        Parameters
        ----------
        papers_dict : dict
            Dictionary mapping DOI to (paper, authors, sections, tables, figures, references)
        output_dir : str
            Directory to save RDF files
        prefix : str
            Prefix for filename (e.g., "enriched_")
        extraction_info : Optional[dict]
            Extraction metadata for provenance
        include_content : Optional[bool]
            Whether to include content entities. If None, uses default from config.

        Returns
        -------
        dict
            Dictionary mapping DOI to RDF Graph objects
        """
        # Convert the tuple format to the new dict format
        entities_data = {}
        for doi, (paper, authors, sections, tables, _figures, references) in papers_dict.items():
            entities_data[doi] = {
                "entity": paper,
                "related_entities": {
                    "authors": authors,
                    "sections": sections,
                    "tables": tables,
                    "references": references,
                },
            }

        # Use configured default if include_content is not specified
        if include_content is None:
            include_content = self.default_include_content

        return self.convert_and_save_entities_to_rdf(
            entities_data, output_dir, prefix, extraction_info, include_content=include_content
        )

    def save_rdf(
        self,
        entities_data: dict[str, dict[str, Any]],
        output_dir: str = "rdf_output",
        kg_type: str | None = None,
        extraction_info: dict[str, Any] | None = None,
    ) -> dict[str, Graph]:
        """
        Convert entities to RDF graphs based on configured KG type and save them.

        This is a convenience method that uses the configured default KG structure.

        Parameters
        ----------
        entities_data : dict
            Dictionary mapping identifier to entity data
        output_dir : str
            Directory to save RDF files
        kg_type : Optional[str]
            Type of knowledge graph: "complete", "metadata", "content".
            If None, uses default from config.
        extraction_info : Optional[dict]
            Extraction metadata for provenance

        Returns
        -------
        dict
            Dictionary mapping identifier to RDF Graph objects
        """
        if kg_type is None:
            kg_type = self.default_kg_type

        if kg_type == "metadata":
            return self.save_metadata_rdf(
                entities_data, output_dir, extraction_info=extraction_info
            )
        elif kg_type == "content":
            return self.save_content_rdf(
                entities_data, output_dir, extraction_info=extraction_info
            )
        else:  # "complete" or any other value
            return self.save_complete_rdf(
                entities_data, output_dir, extraction_info=extraction_info
            )

    def _filter_metadata_entities(
        self, related_entities: dict[str, list[Any]]
    ) -> dict[str, list[Any]]:
        """
        Filter related entities to include only metadata entities.

        Metadata entities include: papers, authors, institutions.
        Content entities (sections, references, tables, figures) are excluded.

        Parameters
        ----------
        related_entities : dict[str, list[Any]]
            Dictionary of related entities by relationship name

        Returns
        -------
        dict[str, list[Any]]
            Filtered dictionary containing only metadata entities
        """
        # Define metadata entity types (exclude content entities)
        metadata_entity_types = {"PaperEntity", "AuthorEntity", "InstitutionEntity"}

        filtered_entities = {}
        for rel_name, entities in related_entities.items():
            if entities:
                # Filter entities by type
                filtered_list = [
                    entity
                    for entity in entities
                    if entity.__class__.__name__ in metadata_entity_types
                ]
                if filtered_list:  # Only include non-empty lists
                    filtered_entities[rel_name] = filtered_list

        return filtered_entities

    def save_metadata_rdf(
        self,
        entities_data: dict[str, dict[str, Any]],
        output_dir: str = "rdf_output",
        prefix: str = "metadata_",
        extraction_info: dict[str, Any] | None = None,
        filename_template: str | None = None,
    ) -> dict[str, Graph]:
        """
        Convert entities to RDF graphs containing only metadata entities and save them.

        This creates knowledge graphs focused on bibliographic metadata:
        - Papers (with basic metadata)
        - Authors and their affiliations
        - Institutions
        - Excludes content entities like sections, references, tables, figures

        Parameters
        ----------
        entities_data : dict
            Dictionary mapping identifier to entity data
        output_dir : str
            Directory to save RDF files
        prefix : str
            Prefix for filename (default: "metadata_")
        extraction_info : Optional[dict]
            Extraction metadata for provenance
        filename_template : Optional[str]
            Template for filename generation

        Returns
        -------
        dict
            Dictionary mapping identifier to RDF Graph objects
        """
        return self.convert_and_save_entities_to_rdf(
            entities_data=entities_data,
            output_dir=output_dir,
            prefix=prefix,
            extraction_info=extraction_info,
            filename_template=filename_template,
            include_content=False,
        )

    def save_content_rdf(
        self,
        entities_data: dict[str, dict[str, Any]],
        output_dir: str = "rdf_output",
        prefix: str = "content_",
        extraction_info: dict[str, Any] | None = None,
        filename_template: str | None = None,
    ) -> dict[str, Graph]:
        """
        Convert entities to RDF graphs containing content-focused entities and save them.

        This creates knowledge graphs focused on document content:
        - Papers (as containers for content)
        - Sections and subsections
        - References and citations
        - Tables and table rows
        - Figures
        - Excludes detailed author/institution metadata

        Parameters
        ----------
        entities_data : dict
            Dictionary mapping identifier to entity data
        output_dir : str
            Directory to save RDF files
        prefix : str
            Prefix for filename (default: "content_")
        extraction_info : Optional[dict]
            Extraction metadata for provenance
        filename_template : Optional[str]
            Template for filename generation

        Returns
        -------
        dict
            Dictionary mapping identifier to RDF Graph objects
        """
        # For content KG, include papers but filter their related entities to content-only
        content_entities_data = {}
        for identifier, entity_data in entities_data.items():
            entity = entity_data["entity"]
            related_entities = entity_data.get("related_entities", {})

            # Filter to include only content-related entities
            content_related = self._filter_content_entities_from_related(related_entities)

            # Only include if there are content entities or if it's a content entity itself
            if (
                entity.__class__.__name__
                in {
                    "SectionEntity",
                    "ReferenceEntity",
                    "TableEntity",
                    "TableRowEntity",
                    "FigureEntity",
                }
                or content_related
            ):
                content_entities_data[identifier] = {
                    "entity": entity,
                    "related_entities": content_related,
                }

        return self.convert_and_save_entities_to_rdf(
            entities_data=content_entities_data,
            output_dir=output_dir,
            prefix=prefix,
            extraction_info=extraction_info,
            filename_template=filename_template,
            include_content=True,
        )

    def _filter_content_entities_from_related(
        self, related_entities: dict[str, list[Any]]
    ) -> dict[str, list[Any]]:
        """
        Filter related entities to include only content-related entities.

        Content-related entities include: sections, references, tables, figures.
        Metadata entities (authors, institutions) are excluded.

        Parameters
        ----------
        related_entities : dict[str, list[Any]]
            Dictionary of related entities by relationship name

        Returns
        -------
        dict[str, list[Any]]
            Filtered dictionary containing only content-related entities
        """
        # Define content relationship names (exclude metadata relationships)
        content_relationships = {"sections", "references", "tables", "figures", "rows"}

        filtered_entities = {}
        for rel_name, entities in related_entities.items():
            if rel_name in content_relationships and entities:
                filtered_entities[rel_name] = entities

        return filtered_entities

    def save_complete_rdf(
        self,
        entities_data: dict[str, dict[str, Any]],
        output_dir: str = "rdf_output",
        prefix: str = "",
        extraction_info: dict[str, Any] | None = None,
        filename_template: str | None = None,
    ) -> dict[str, Graph]:
        """
        Convert entities to complete RDF graphs containing all entities and save them.

        This creates full knowledge graphs including both metadata and content entities:
        - Papers, authors, institutions (metadata)
        - Sections, references, tables, figures (content)

        Parameters
        ----------
        entities_data : dict
            Dictionary mapping identifier to entity data
        output_dir : str
            Directory to save RDF files
        prefix : str
            Prefix for filename (default: "")
        extraction_info : Optional[dict]
            Extraction metadata for provenance
        filename_template : Optional[str]
            Template for filename generation

        Returns
        -------
        dict
            Dictionary mapping identifier to RDF Graph objects
        """
        return self.convert_and_save_entities_to_rdf(
            entities_data=entities_data,
            output_dir=output_dir,
            prefix=prefix,
            extraction_info=extraction_info,
            filename_template=filename_template,
            include_content=True,
        )
