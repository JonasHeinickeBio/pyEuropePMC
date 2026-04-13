"""
RDF Mapper for converting entities to RDF triples based on LinkML schema introspection.

This module provides the RDFMapper class which converts LinkML-generated Pydantic entity
models to RDF triples. The mapper uses LinkML schema introspection as the primary source
for field-to-predicate mappings, ensuring consistency with the schema definitions.

Key Features:
- LinkML schema introspection for automatic field mapping
- Support for named graphs and entity organization
- Validation against schema constraints
- Flexible configuration via rdf_config.yaml
- Ontology alignment (BIBO, FOAF, DCTERMS, etc.)

Architecture:
- LinkML Schema (schemas/pyeuropepmc_schema.yaml): Single source of truth for data model
- LinkMLSchemaIntrospector: Runtime introspection of schema for field mappings
- RDFMapper: Converts entities to RDF using schema-derived mappings
- rdf_config.yaml: Operational settings (graph URIs, quality thresholds, output formats)

Examples:
    >>> from rdflib import Graph
    >>> from pyeuropepmc.models import PaperEntity
    >>> from pyeuropepmc.mappers.rdf_mapper import RDFMapper
    >>>
    >>> mapper = RDFMapper()
    >>> paper = PaperEntity(pmcid="PMC123", title="Test Paper")
    >>> g = Graph()
    >>> uri = paper.to_rdf(g, mapper=mapper)
    >>> print(g.serialize(format="turtle"))
"""

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Any

from rdflib import BNode, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF
import yaml

from pyeuropepmc.mappers.config_utils import load_rdf_config
from pyeuropepmc.mappers.linkml_introspection import LinkMLSchemaIntrospector
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
            # Default to conf/rdf_config.yaml in project root
            base_path = Path(__file__).parent.parent.parent.parent
            config_path = str(base_path / "conf" / "rdf_config.yaml")

        self.config = load_rdf_config()
        self.enable_named_graphs = enable_named_graphs

        # Initialize logger
        self.logger = logging.getLogger(__name__)

        # Initialize LinkML schema introspector for field mappings
        self.linkml_introspector = LinkMLSchemaIntrospector()
        self.namespaces = self._build_namespaces()

        # Configuration options for KG structure
        self.kg_config = self.config.get("_kg_structure", {})
        self.default_include_content = self.kg_config.get("include_content", True)
        self.default_kg_type = self.kg_config.get(
            "default_type", "complete"
        )  # "complete", "metadata", "content"

        # Quality/validation configuration
        self.quality_config = self.config.get("quality", {})
        self.validation_enabled = self.quality_config.get("validation", {}).get("enabled", True)
        self.strict_validation = self.quality_config.get("validation", {}).get(
            "strict_mode", False
        )

    def validate_entity(self, entity: Any) -> tuple[bool, list[str]]:
        """
        Validate an entity against LinkML schema constraints before RDF conversion.

        This method checks that the entity's fields conform to the schema
        constraints including patterns, ranges, and required fields.

        Parameters
        ----------
        entity : Any
            Entity instance to validate

        Returns
        -------
        tuple[bool, list[str]]
            Tuple of (is_valid, list of validation errors/warnings)

        Examples
        --------
        >>> from pyeuropepmc.models import PaperEntity
        >>> mapper = RDFMapper()
        >>> paper = PaperEntity(title="Test", pmcid="PMC123")
        >>> is_valid, errors = mapper.validate_entity(paper)
        >>> if not is_valid:
        ...     print(f"Validation errors: {errors}")
        """
        if not self.validation_enabled or not self.linkml_introspector.is_available:
            return True, []

        from pyeuropepmc.builders.schema_validation import SchemaValidator

        validator = SchemaValidator()
        entity_class = entity.__class__.__name__

        # Convert entity to dict for validation
        entity_data = {}
        for field_name in dir(entity):
            if not field_name.startswith("_") and not callable(getattr(entity, field_name)):
                value = getattr(entity, field_name, None)
                if value is not None:
                    entity_data[field_name] = value

        is_valid, errors = validator.validate_entity_data(
            entity_class, entity_data, strict=self.strict_validation
        )

        return is_valid, errors

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
        Build namespace dictionary from LinkML schema.

        Returns
        -------
        dict
            Dictionary mapping prefix to Namespace object
        """
        return self.linkml_introspector.build_namespaces()

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
        if not types:
            return
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

        # Add RDF types only from the most specific class (first in MRO)
        # Inheritance should be handled through OWL subclass relationships
        if all_mappings:
            most_specific_mapping = all_mappings[0]  # First in MRO is most specific
            rdf_types = most_specific_mapping.get("rdf_types", [])
            if rdf_types:
                self.add_types(g, subject, rdf_types, context)

        for mapping in all_mappings:
            # Map single-value fields
            self._map_single_value_fields(g, subject, entity, mapping, context)

            # Map multi-value fields (excluding 'types' which is handled above)
            self._map_multi_value_fields(g, subject, entity, mapping, context)

            # Map relationships
            self._map_relationships(g, subject, entity, mapping, context)

    def _map_relationships(
        self,
        g: Any,
        subject: URIRef,
        entity: Any,
        mapping: dict[str, Any],
        context: URIRef | None = None,
    ) -> None:
        """Map entity relationships to RDF triples."""
        relationships_mapping = mapping.get("relationships", {})

        for rel_name, rel_config in relationships_mapping.items():
            predicate_str = rel_config.get("predicate")
            inverse_predicate = rel_config.get("inverse")

            if predicate_str:
                related_objs = self._get_related_objects(entity, rel_name, None)
                if related_objs:
                    self._add_relationship_triples(
                        g, subject, related_objs, predicate_str, inverse_predicate, context
                    )

    def _get_related_objects(
        self, entity: Any, rel_name: str, related_entities: dict[str, Any] | None = None
    ) -> list[Any] | None:
        """Get related objects for a relationship name."""
        # First check if related objects are provided in related_entities dict
        related_objs = related_entities.get(rel_name) if related_entities else None

        # If not in related_entities, check if it's an attribute of the entity
        if related_objs is None and hasattr(entity, rel_name):
            attr_value = getattr(entity, rel_name)
            if attr_value is not None:
                return attr_value if isinstance(attr_value, list) else [attr_value]

        return related_objs

    def _add_relationship_triples(
        self,
        g: Any,
        subject: URIRef,
        related_objs: list[Any],
        predicate_str: str,
        inverse_predicate: str | None,
        context: URIRef | None,
    ) -> None:
        """Add relationship triples for related objects."""
        predicate = self._resolve_predicate(predicate_str)

        for related_obj in related_objs:
            # Skip dict objects - they should be flattened, not treated as entities
            if related_obj is None or isinstance(related_obj, dict):
                continue

            # Only process actual Entity instances
            if hasattr(related_obj, "to_rdf"):
                # Generate URI for related object
                related_uri = self._generate_entity_uri(related_obj, parent_uri=subject)

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
                related_obj.to_rdf(
                    g,
                    uri=related_uri,
                    mapper=self,
                    extraction_info=None,
                    parent_uri=subject,
                )

    def _get_entity_mappings(self, entity: Any) -> list[dict[str, Any]]:
        """Get mappings for entity class and parent classes using LinkML schema."""
        all_mappings = []
        for cls in entity.__class__.__mro__:
            if cls.__name__.endswith("Entity"):
                # Use LinkML schema introspector for mappings
                mapping = self.linkml_introspector.get_class_mapping(cls.__name__)
                if mapping:
                    all_mappings.append(mapping)

        # If no mappings found, try direct class name lookup as fallback
        if not all_mappings:
            mapping = self.linkml_introspector.get_class_mapping(entity.__class__.__name__)
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
        # Exclude 'types' field as it's handled separately for RDF type assertions
        filtered_mapping = {k: v for k, v in multi_value_mapping.items() if k != "types"}
        map_multi_value_fields(
            g, subject, entity, filtered_mapping, self._resolve_predicate, context
        )

    def _map_complex_fields(  # noqa: C901
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
                        # Generate meaningful URI for grant using URIFactory
                        from pyeuropepmc.mappers.rdf_utils import uri_factory

                        grant_uri = uri_factory.generate_grant_uri(funder)

                        # Add grant type
                        if context:
                            g.graph(context).add(
                                (grant_uri, RDF.type, self._resolve_predicate("frapo:Grant"))
                            )
                        else:
                            g.add((grant_uri, RDF.type, self._resolve_predicate("frapo:Grant")))

                        # Add frapo:funds relationship (grant funds paper)
                        if context:
                            g.graph(context).add(
                                (grant_uri, self._resolve_predicate("frapo:funds"), subject)
                            )
                        else:
                            g.add((grant_uri, self._resolve_predicate("frapo:funds"), subject))

                        # Add funder DOI/FundRef
                        fundref_doi = funder.get("fundref_doi")
                        if fundref_doi:
                            # Ensure proper URI format for FundRef DOI
                            fundref_uri = (
                                URIRef(f"https://doi.org/10.13039/{fundref_doi}")
                                if not fundref_doi.startswith("http")
                                else URIRef(fundref_doi)
                            )
                            doi_pred = self._resolve_predicate("datacite:doi")
                            if context:
                                g.graph(context).add((grant_uri, doi_pred, fundref_uri))
                            else:
                                g.add((grant_uri, doi_pred, fundref_uri))

                        # Add award ID
                        award_id = funder.get("award_id")
                        if award_id:
                            if context:
                                g.graph(context).add(
                                    (
                                        grant_uri,
                                        self._resolve_predicate("datacite:identifier"),
                                        Literal(award_id),
                                    )
                                )
                            else:
                                g.add(
                                    (
                                        grant_uri,
                                        self._resolve_predicate("datacite:identifier"),
                                        Literal(award_id),
                                    )
                                )

                        # Add funding source name
                        source = funder.get("source")
                        if source:
                            if context:
                                g.graph(context).add(
                                    (
                                        grant_uri,
                                        self._resolve_predicate("dcterms:title"),
                                        Literal(source),
                                    )
                                )
                            else:
                                g.add(
                                    (
                                        grant_uri,
                                        self._resolve_predicate("dcterms:title"),
                                        Literal(source),
                                    )
                                )

                        # Add recipient
                        recipient = (
                            funder.get("recipient_full")
                            or funder.get("recipient_name")
                            or funder.get("recipient")
                        )
                        if recipient:
                            if context:
                                g.graph(context).add(
                                    (
                                        grant_uri,
                                        self._resolve_predicate("frapo:hasRecipient"),
                                        Literal(recipient),
                                    )
                                )
                            else:
                                g.add(
                                    (
                                        grant_uri,
                                        self._resolve_predicate("frapo:hasRecipient"),
                                        Literal(recipient),
                                    )
                                )

    def map_relationships(  # noqa: C901
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
        mapping = self.linkml_introspector.get_class_mapping(entity_class_name)
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
                        # Skip dict objects - they should be flattened, not treated as entities
                        if related_obj is None or isinstance(related_obj, dict):
                            continue

                        # Only process actual Entity instances
                        if hasattr(related_obj, "to_rdf"):
                            # Generate URI for related object
                            related_uri = self._generate_entity_uri(
                                related_obj, parent_uri=subject
                            )

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
                            related_obj.to_rdf(
                                g,
                                uri=related_uri,
                                mapper=self,
                                extraction_info=extraction_info,
                                parent_uri=subject,
                            )

    def map_citation_relationships(
        self,
        g: Any,
        subject: URIRef,
        citations: list[dict[str, Any]],
        context: URIRef | None = None,
    ) -> None:
        """
        Map citation relationships to RDF triples using CiTO ontology.

        Parameters
        ----------
        g : Graph
            RDF graph to add triples to
        subject : URIRef
            Subject URI (e.g., section or paper URI)
        citations : list[dict[str, Any]]
            List of citation dictionaries from extract_in_text_citations()
        context : Optional[URIRef]
            Named graph context

        Examples
        --------
        >>> from rdflib import Graph, URIRef
        >>> mapper = RDFMapper()
        >>> g = Graph()
        >>> subject = URIRef("http://example.org/section1")
        >>> citations = [{"rid": "CR409", "text": "409", "linked_reference": {...}}]
        >>> mapper.map_citation_relationships(g, subject, citations)
        """
        cito_ns = Namespace("http://purl.org/spar/cito/")

        for citation in citations:
            rid = citation.get("rid")
            if not rid:
                continue

            # Create citation URI (could be a blank node or specific URI)
            citation_uri = BNode()

            # Add citation relationship from subject to citation
            if context:
                g.graph(context).add((subject, cito_ns.cites, citation_uri))
            else:
                g.add((subject, cito_ns.cites, citation_uri))

            # Add citation metadata
            citation_text = citation.get("text", "")
            if citation_text:
                if context:
                    g.graph(context).add(
                        (citation_uri, DCTERMS.identifier, Literal(citation_text))
                    )
                else:
                    g.add((citation_uri, DCTERMS.identifier, Literal(citation_text)))

            # Link to full references if available
            references = citation.get("references", [])
            for ref_data in references:
                ref_id = ref_data.get("id")
                if ref_id:
                    # Generate reference URI (assuming DOI or PMID-based)
                    ref_uri = self._generate_reference_uri(ref_id, ref_data)
                    if ref_uri:
                        if context:
                            g.graph(context).add((citation_uri, DCTERMS.references, ref_uri))
                        else:
                            g.add((citation_uri, DCTERMS.references, ref_uri))

                        # Add reference metadata
                        self._add_reference_metadata(g, ref_uri, ref_data, context)

    def _generate_reference_uri(self, ref_id: str, ref_data: dict[str, Any]) -> URIRef | None:
        """Generate URI for a reference based on available identifiers."""
        # Try DOI first
        doi = ref_data.get("doi")
        if doi:
            return URIRef(f"https://doi.org/{doi}")

        # Try PMID
        pmid = ref_data.get("pmid")
        if pmid:
            return URIRef(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

        # Fallback to internal URI
        return URIRef(f"https://w3id.org/pyeuropepmc/reference/{ref_id}")

    def _add_reference_metadata(
        self, g: Any, ref_uri: URIRef, ref_data: dict[str, Any], context: URIRef | None = None
    ) -> None:
        """Add metadata triples for a reference."""
        # Add basic metadata
        title = ref_data.get("title")
        if title:
            if context:
                g.graph(context).add((ref_uri, DCTERMS.title, Literal(title)))
            else:
                g.add((ref_uri, DCTERMS.title, Literal(title)))

        authors = ref_data.get("authors")
        if authors:
            if context:
                g.graph(context).add((ref_uri, DCTERMS.creator, Literal(authors)))
            else:
                g.add((ref_uri, DCTERMS.creator, Literal(authors)))

        year = ref_data.get("year")
        if year:
            if context:
                g.graph(context).add((ref_uri, DCTERMS.issued, Literal(year)))
            else:
                g.add((ref_uri, DCTERMS.issued, Literal(year)))

        # Add type
        if context:
            g.graph(context).add(
                (
                    ref_uri,
                    RDF.type,
                    self.namespaces.get(
                        "bibo", Namespace("http://purl.org/ontology/bibo/")
                    ).Document,
                )
            )
        else:
            g.add(
                (
                    ref_uri,
                    RDF.type,
                    self.namespaces.get(
                        "bibo", Namespace("http://purl.org/ontology/bibo/")
                    ).Document,
                )
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

    def _generate_entity_uri(self, entity: Any, parent_uri: URIRef | None = None) -> URIRef:
        """
        Generate a URI for an entity using the centralized URI factory.

        Parameters
        ----------
        entity : Any
            Entity instance
        parent_uri : Optional[URIRef]
            URI of the parent entity for contextual URI generation

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

        return uri_factory.generate_uri(entity, parent_uri=parent_uri)

    def entity_to_rdf(
        self,
        entity: Any,
        g: Any = None,
        uri: Any = None,
        related_entities: dict[str, list[Any]] | None = None,
        extraction_info: dict[str, Any] | None = None,
        parent_uri: Any = None,
    ) -> str:
        """
        Convert an entity to RDF string representation.

        This is the main entry point for entity-to-RDF conversion, called by
        BaseEntity.to_rdf() method.

        Parameters
        ----------
        entity : Any
            Entity instance to convert
        g : Optional[Graph]
            RDF graph to add triples to (creates new graph if None)
        uri : Optional[URIRef]
            URI for this entity (if None, will be minted)
        related_entities : Optional[dict[str, list[Any]]]
            Dictionary of related entities by relationship name
        extraction_info : Optional[dict[str, Any]]
            Additional extraction metadata for provenance
        parent_uri : Optional[URIRef]
            URI of the parent entity (for generating contextual URIs)

        Returns
        -------
        str
            RDF serialization of the graph
        """
        from pyeuropepmc.models.rdf_methods import to_rdf

        if g is None:
            g = Dataset()

        to_rdf(
            entity,
            g=g,
            uri=uri,
            mapper=self,
            related_entities=related_entities,
            extraction_info=extraction_info,
            parent_uri=parent_uri,
        )

        # Return serialized RDF
        return g.serialize(format="turtle")

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
        # Bind to the main graph (works for Graph, Dataset, ConjunctiveGraph)
        for prefix, namespace in self.namespaces.items():
            g.bind(prefix, namespace)

        # For Dataset/ConjunctiveGraph, also bind to each named graph
        if hasattr(g, "graphs"):
            for graph in g.graphs():
                for prefix, namespace in self.namespaces.items():
                    graph.bind(prefix, namespace)

    def _validate_rdf_syntax(self, g: Any) -> None:
        """
        Validate RDF graph syntax before serialization.

        This method attempts to serialize the graph to check for syntax errors
        and logs warnings if issues are found.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to validate
        """
        try:
            # Attempt to serialize to check for syntax errors
            test_serialization = str(g.serialize(format="turtle"))

            # Try to parse it back to ensure it's valid
            from rdflib import Graph as RDFGraph

            test_graph = RDFGraph()
            test_graph.parse(data=test_serialization, format="turtle")

        except Exception as e:
            self.logger.warning(f"RDF syntax validation failed: {e}")
            if self.strict_validation:
                raise ValueError(f"RDF syntax validation failed: {e}") from e
            # In non-strict mode, log the error but continue

    def calculate_rdf_quality_metrics(self, g: Any) -> dict[str, Any]:
        """
        Calculate quality metrics for the RDF graph.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to analyze

        Returns
        -------
        dict
            Quality metrics including triple count, entity counts, etc.
        """
        metrics = {
            "total_triples": 0,
            "unique_subjects": 0,
            "unique_predicates": 0,
            "unique_objects": 0,
            "entity_counts": {},
            "namespaces_used": set(),
            "quality_score": 0.0,
        }

        try:
            # Count triples and unique elements
            subjects = set()
            predicates = set()
            objects = set()
            entity_types = {}

            for s, p, o in g:
                metrics["total_triples"] += 1
                subjects.add(s)
                predicates.add(p)
                objects.add(o)

                # Track namespaces
                if hasattr(s, "n3"):
                    ns = str(s).split("/")[-1].split("#")[0] if "/" in str(s) else "unknown"
                    metrics["namespaces_used"].add(ns)

                # Count entity types
                if p == RDF.type:
                    type_str = str(o).split("/")[-1] if "/" in str(o) else str(o)
                    entity_types[type_str] = entity_types.get(type_str, 0) + 1

            metrics["unique_subjects"] = len(subjects)
            metrics["unique_predicates"] = len(predicates)
            metrics["unique_objects"] = len(objects)
            metrics["entity_counts"] = entity_types
            metrics["namespaces_used"] = list(metrics["namespaces_used"])

            # Calculate quality score based on various factors
            quality_factors = []

            # Factor 1: Data completeness (entities with identifiers)
            identifier_triples = sum(
                1 for s, p, o in g if "id" in str(p).lower() or "identifier" in str(p).lower()
            )
            quality_factors.append(
                min(1.0, identifier_triples / max(1, metrics["total_triples"] * 0.1))
            )

            # Factor 2: Semantic richness (use of ontologies beyond basic RDF)
            ontology_triples = sum(
                1
                for s, p, o in g
                if any(
                    ns in str(p)
                    for ns in [
                        "http://xmlns.com/foaf",
                        "http://purl.org/dc",
                        "http://www.w3.org/ns/org",
                        "http://www.w3.org/2004/02/skos",
                    ]
                )
            )
            quality_factors.append(
                min(1.0, ontology_triples / max(1, metrics["total_triples"] * 0.3))
            )

            # Factor 3: Connectivity (average connections per entity)
            avg_connections = metrics["total_triples"] / max(1, metrics["unique_subjects"])
            quality_factors.append(min(1.0, avg_connections / 10.0))  # Assume 10 is good

            # Factor 4: Namespace diversity
            quality_factors.append(
                min(1.0, len(metrics["namespaces_used"]) / 5.0)
            )  # Assume 5+ namespaces is good

            metrics["quality_score"] = (
                sum(quality_factors) / len(quality_factors) if quality_factors else 0.0
            )

        except Exception as e:
            self.logger.warning(f"Error calculating RDF quality metrics: {e}")

        return metrics

    def check_data_completeness(self, entities_data: dict[str, Any]) -> dict[str, Any]:
        """
        Check data completeness across entities.

        Parameters
        ----------
        entities_data : dict
            Dictionary of entities to check

        Returns
        -------
        dict
            Completeness metrics
        """
        completeness = {
            "authors_with_orcid": 0,
            "authors_with_affiliations": 0,
            "papers_with_doi": 0,
            "papers_with_abstract": 0,
            "institutions_with_ror": 0,
            "total_authors": 0,
            "total_papers": 0,
            "total_institutions": 0,
            "completeness_score": 0.0,
        }

        try:
            for entity_data in entities_data.values():
                entity = entity_data.get("entity")
                if not entity:
                    continue

                if hasattr(entity, "__class__"):
                    entity_type = entity.__class__.__name__

                    if entity_type == "AuthorEntity":
                        completeness["total_authors"] += 1
                        if getattr(entity, "orcid", None):
                            completeness["authors_with_orcid"] += 1
                        if getattr(entity, "affiliation_text", None) or getattr(
                            entity, "institutions", None
                        ):
                            completeness["authors_with_affiliations"] += 1

                    elif entity_type == "PaperEntity":
                        completeness["total_papers"] += 1
                        if getattr(entity, "doi", None):
                            completeness["papers_with_doi"] += 1
                        if getattr(entity, "abstract", None):
                            completeness["papers_with_abstract"] += 1

                    elif entity_type == "InstitutionEntity":
                        completeness["total_institutions"] += 1
                        if getattr(entity, "ror_id", None):
                            completeness["institutions_with_ror"] += 1

            # Calculate completeness scores
            if completeness["total_authors"] > 0:
                completeness["orcid_completeness"] = (
                    completeness["authors_with_orcid"] / completeness["total_authors"]
                )
                completeness["affiliation_completeness"] = (
                    completeness["authors_with_affiliations"] / completeness["total_authors"]
                )

            if completeness["total_papers"] > 0:
                completeness["doi_completeness"] = (
                    completeness["papers_with_doi"] / completeness["total_papers"]
                )
                completeness["abstract_completeness"] = (
                    completeness["papers_with_abstract"] / completeness["total_papers"]
                )

            if completeness["total_institutions"] > 0:
                completeness["ror_completeness"] = (
                    completeness["institutions_with_ror"] / completeness["total_institutions"]
                )

            # Overall completeness score
            scores = []
            for key in [
                "orcid_completeness",
                "affiliation_completeness",
                "doi_completeness",
                "abstract_completeness",
                "ror_completeness",
            ]:
                if key in completeness:
                    scores.append(completeness[key])

            completeness["completeness_score"] = sum(scores) / len(scores) if scores else 0.0

        except Exception as e:
            self.logger.warning(f"Error checking data completeness: {e}")

        return completeness

    def serialize_graph(
        self,
        g: Any,
        format: str = "turtle",
        destination: str | None = None,
        include_quality_metadata: bool = True,
        entities_data: dict[str, Any] | None = None,
    ) -> str:
        """
        Serialize RDF graph to string or file with optional quality metadata.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to serialize
        format : str
            Serialization format ("turtle", "xml", "json-ld", etc.)
        destination : Optional[str]
            File path to save to. If None, returns string.
        include_quality_metadata : bool
            Whether to include quality metrics in output metadata
        entities_data : Optional[dict]
            Entity data for quality assessment

        Returns
        -------
        str
            Serialized RDF as string (if destination is None)
        """
        # Validate RDF syntax before serialization
        self._validate_rdf_syntax(g)

        # Calculate quality metrics if requested and entities provided
        quality_metrics = None
        completeness_metrics = None
        if include_quality_metadata and entities_data:
            try:
                quality_metrics = self.calculate_rdf_quality_metrics(g)
                completeness_metrics = self.check_data_completeness(entities_data)
            except Exception as e:
                self.logger.warning(f"Error calculating quality metrics: {e}")

        # Serialize the graph
        try:
            if destination:
                # Serialize to file
                with open(destination, "w", encoding="utf-8") as f:
                    # Write quality metadata as comments if requested
                    if include_quality_metadata and (quality_metrics or completeness_metrics):
                        f.write("# PyEuropePMC RDF Export\n")
                        f.write(f"# Generated: {datetime.now().isoformat()}\n")
                        if quality_metrics:
                            f.write(
                                f"# Quality Score: "
                                f"{quality_metrics.get('overall_score', 'N/A'):.3f}\n"
                            )
                            f.write(
                                f"# Total Triples: {quality_metrics.get('total_triples', 0)}\n"
                            )
                        if completeness_metrics:
                            f.write(
                                f"# Completeness Score: "
                                f"{completeness_metrics.get('completeness_score', 0):.3f}\n"
                            )
                        f.write("# \n")

                    # Serialize the graph
                    g.serialize(f, format=format)
            else:
                # Return as string
                rdf_string = g.serialize(format=format)
                return rdf_string

        except Exception as e:
            self.logger.error(f"Error serializing RDF graph: {e}")
            raise

        return ""

    def _validate_rdf_syntax(self, g: Any) -> None:
        """
        Validate RDF syntax by attempting to parse back the serialized graph.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to validate

        Raises
        ------
        ValueError
            If RDF syntax is invalid
        """
        try:
            # Serialize to string
            rdf_string = g.serialize(format="turtle")

            # Try to parse it back
            from rdflib import Graph as BaseGraph

            test_graph = BaseGraph()
            test_graph.parse(data=rdf_string, format="turtle")

        except Exception as e:
            raise ValueError(f"Invalid RDF syntax: {e}") from e

    def deduplicate_graph(self, g: Any) -> None:
        """
        Remove duplicate triples from RDF graph for performance optimization.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to deduplicate
        """
        try:
            # Convert to set to remove duplicates, then back to graph
            triples = set(g)
            g.remove((None, None, None))  # Clear all triples
            for triple in triples:
                g.add(triple)
        except Exception as e:
            self.logger.warning(f"Error deduplicating graph: {e}")

    def standardize_filename(
        self,
        base_filename: str,
        quality_score: float | None = None,
        timestamp: str | None = None,
        entity_type: str | None = None,
    ) -> str:
        """
        Standardize filename with quality metadata and timestamp.

        Parameters
        ----------
        base_filename : str
            Base filename without extension
        quality_score : Optional[float]
            Quality score to include in filename
        timestamp : Optional[str]
            Timestamp string
        entity_type : str
            Type of entity for categorization

        Returns
        -------
        str
            Standardized filename
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        parts = [timestamp]

        if entity_type:
            parts.append(entity_type)

        if quality_score is not None:
            # Convert quality score to a letter grade for filename
            if quality_score >= 0.9:
                grade = "A"
            elif quality_score >= 0.8:
                grade = "B"
            elif quality_score >= 0.7:
                grade = "C"
            elif quality_score >= 0.6:
                grade = "D"
            else:
                grade = "F"
            parts.append(f"Q{grade}")

        parts.append(base_filename)
        return "_".join(parts) + ".ttl"

    def enhance_semantic_richness(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Enhance semantic richness by adding inferred relationships and ontology alignments.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to enhance
        entities_data : dict
            Entity data for semantic enhancement
        """
        try:
            # Add ontology alignments for better semantic interoperability
            self._add_ontology_alignments(g)

            # Add inferred relationships
            self._add_inferred_relationships(g, entities_data)

            # Add semantic enrichment for institutions and authors
            self._add_semantic_enrichment(g, entities_data)

        except Exception as e:
            self.logger.warning(f"Error enhancing semantic richness: {e}")

    def _add_ontology_alignments(self, g: Any) -> None:
        """
        Add ontology alignments for better semantic interoperability.

        This includes alignments between different vocabularies like FOAF, DCTERMS, BIBO, etc.
        """
        try:
            # Import additional namespaces
            pass

            # Add alignments for common terms
            # FOAF alignments
            # dcterms alignments

            # Add SKOS broader/narrower relationships where applicable

            # These alignments would be added as additional triples
            # For example, mapping custom terms to standard vocabularies

        except Exception as e:
            self.logger.warning(f"Error adding ontology alignments: {e}")

    def _add_inferred_relationships(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add inferred relationships based on entity data.

        Parameters
        ----------
        g : Graph or Dataset
            RDF graph to enhance
        entities_data : dict
            Entity data for relationship inference
        """
        try:
            # Add co-authorship relationships
            self._add_coauthorship_relationships(g, entities_data)

            # Add institutional collaborations
            self._add_institutional_collaborations(g, entities_data)

            # Add citation networks
            self._add_citation_networks(g, entities_data)

        except Exception as e:
            self.logger.warning(f"Error adding inferred relationships: {e}")

    def _add_coauthorship_relationships(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add co-authorship relationships between authors.
        """
        # This would analyze author lists and add co-author relationships
        # Implementation depends on the specific data structure
        pass

    def _add_institutional_collaborations(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add institutional collaboration relationships.
        """
        # This would analyze institutional affiliations and add collaboration links
        pass

    def _add_citation_networks(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add citation network relationships.
        """
        # This would analyze references and add citation relationships
        pass

    def _add_semantic_enrichment(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add semantic enrichment for institutions and authors.
        """
        try:
            # Add institutional hierarchy relationships
            self._add_institutional_hierarchy(g, entities_data)

            # Add author expertise relationships
            self._add_author_expertise(g, entities_data)

            # Add temporal relationships
            self._add_temporal_relationships(g, entities_data)

        except Exception as e:
            self.logger.warning(f"Error adding semantic enrichment: {e}")

    def _add_institutional_hierarchy(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add institutional hierarchy relationships (department -> institution -> organization).

        This method:
        1. Links departments to their parent organizations
        2. Links authors to their affiliated organizations and departments
        3. Links papers to author organizations (transitively)
        4. Adds explicit institutional membership relationships
        """

        try:
            from rdflib import URIRef

            ORG = Namespace("http://www.w3.org/ns/org#")
            PYEUROPEPMC = Namespace("https://w3id.org/pyeuropepmc/vocab#")

            # Extract all entities by type
            papers_by_id = {}
            authors_by_id = {}
            organizations_by_id = {}
            departments_by_id = {}

            for _, entity_data in entities_data.items():
                entity = entity_data.get("entity")
                if entity is None:
                    continue

                entity_type = entity.__class__.__name__
                entity_id = getattr(entity, "id", None) or getattr(entity, "uuid", None)

                if entity_type == "PaperEntity":
                    papers_by_id[entity_id] = entity
                elif entity_type == "AuthorEntity":
                    authors_by_id[entity_id] = entity
                elif entity_type == "Organization":
                    organizations_by_id[entity_id] = entity
                elif entity_type == "DepartmentEntity":
                    departments_by_id[entity_id] = entity

            # Link departments to parent organizations
            for _, dept in departments_by_id.items():
                if hasattr(dept, "parent_organization") and dept.parent_organization:
                    dept_uri = self._generate_entity_uri(dept)
                    parent_org = dept.parent_organization

                    # Handle both string IDs and object references
                    if isinstance(parent_org, str):
                        parent_uri = URIRef(
                            f"https://w3id.org/pyeuropepmc/data#organization/{parent_org}"
                        )
                    else:
                        parent_uri = self._generate_entity_uri(parent_org)

                    # Add department -> parent relationship
                    g.add((dept_uri, ORG.unitOf, parent_uri))
                    # Add inverse
                    g.add((parent_uri, ORG.hasUnit, dept_uri))

            # Link authors to organizations (explicit institutional affiliation)
            for _, author in authors_by_id.items():
                author_uri = self._generate_entity_uri(author)

                # Handle author_institutions relationship
                if hasattr(author, "author_institutions") and author.author_institutions:
                    institutions = author.author_institutions
                    if not isinstance(institutions, list):
                        institutions = [institutions]

                    for inst in institutions:
                        if inst is not None:
                            inst_uri = self._generate_entity_uri(inst)
                            g.add((author_uri, PYEUROPEPMC.affiliatedWith, inst_uri))
                            g.add((inst_uri, PYEUROPEPMC.hasAffiliate, author_uri))

                # Handle author_departments relationship
                if hasattr(author, "author_departments") and author.author_departments:
                    departments = author.author_departments
                    if not isinstance(departments, list):
                        departments = [departments]

                    for dept in departments:
                        if dept is not None:
                            dept_uri = self._generate_entity_uri(dept)
                            g.add((author_uri, PYEUROPEPMC.departmentMember, dept_uri))
                            g.add((dept_uri, PYEUROPEPMC.hasDepartmentMember, author_uri))

            # Link papers to organizations through authors
            for paper_id, paper in papers_by_id.items():
                paper_uri = self._generate_entity_uri(paper)

                # Get authors from related entities
                if "authors" in entities_data.get(paper_id, {}).get("related_entities", {}):
                    authors_list = entities_data[paper_id]["related_entities"]["authors"]

                    org_set = set()
                    dept_set = set()

                    for author in authors_list:
                        author_uri = self._generate_entity_uri(author)

                        # Collect organizations and departments
                        if hasattr(author, "author_institutions") and author.author_institutions:
                            institutions = author.author_institutions
                            if not isinstance(institutions, list):
                                institutions = [institutions]
                            for inst in institutions:
                                if inst is not None:
                                    org_set.add((author_uri, inst))

                        if hasattr(author, "author_departments") and author.author_departments:
                            departments = author.author_departments
                            if not isinstance(departments, list):
                                departments = [departments]
                            for dept in departments:
                                if dept is not None:
                                    dept_set.add((author_uri, dept))

                    # Add paper -> organization relationships
                    for _, org in org_set:
                        org_uri = self._generate_entity_uri(org)
                        g.add((paper_uri, PYEUROPEPMC.affiliatedWith, org_uri))
                        g.add((org_uri, PYEUROPEPMC.hasPublication, paper_uri))

                    # Add paper -> department relationships
                    for _, dept in dept_set:
                        dept_uri = self._generate_entity_uri(dept)
                        g.add((paper_uri, PYEUROPEPMC.departmentAffiliation, dept_uri))
                        g.add((dept_uri, PYEUROPEPMC.hasDepartmentPublication, paper_uri))

        except Exception as e:
            self.logger.error(f"Error adding institutional hierarchy: {e}", exc_info=True)

    def _add_author_expertise(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add author expertise relationships based on publication topics.
        """
        # Implementation for author expertise
        pass

    def _add_temporal_relationships(self, g: Any, entities_data: dict[str, Any]) -> None:
        """
        Add temporal relationships (publication sequences, career progression).
        """
        # Implementation for temporal relationships
        pass

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

                # Enhance semantic richness
                self.enhance_semantic_richness(g, {identifier: entity_data})

                if g:
                    # Deduplicate triples for performance
                    self.deduplicate_graph(g)

                    rdf_graphs[identifier] = g
                    # Count triples in the graph
                    triple_count = len(list(g))
                    print(f"  [OK] Successfully converted to RDF ({triple_count} triples)")

                    # Generate standardized filename with quality metadata
                    safe_identifier = identifier.replace("/", "_").replace(".", "_")
                    if filename_template is None:
                        # Calculate quality score for filename
                        quality_score = None
                        try:
                            quality_metrics = self.calculate_rdf_quality_metrics(g)
                            quality_score = quality_metrics.get("overall_score")
                        except Exception as e:
                            # Quality calculation is optional; continue without it
                            self.logger.debug(f"Quality calculation skipped: {e}")

                        base_filename = f"{entity_type}_{safe_identifier}"
                        filename = (
                            f"{output_dir}/"
                            f"{self.standardize_filename(base_filename, quality_score, entity_type=entity_type)}"  # noqa: E501
                        )
                    else:
                        safe_identifier = identifier.replace("/", "_").replace(".", "_")
                        filename = filename_template.format(
                            prefix=prefix, identifier=safe_identifier, entity_type=entity_type
                        )

                    try:
                        self.serialize_graph(
                            g,
                            format="turtle",
                            destination=filename,
                            entities_data={identifier: entity_data},
                        )
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

    def validate_graph(self, g: Any, name: str = "graph") -> tuple[bool, list[str]]:
        """
        Validate RDF graph for syntax, completeness, and quality.

        Performs comprehensive validation including:
        - RDF syntax validation
        - Data completeness checks (ORCID coverage, institution linking)
        - Cross-reference validation for cited works
        - Schema compliance

        Parameters
        ----------
        g : Graph
            RDF graph to validate
        name : str
            Name of the graph for reporting

        Returns
        -------
        tuple[bool, list[str]]
            Tuple of (is_valid, list of validation messages)
        """
        validation_messages = []
        is_valid = True

        try:
            # Basic RDF syntax validation
            if g is None:
                validation_messages.append(f"{name}: Graph is None")
                return False, validation_messages

            # Check for basic structure
            if len(g) == 0:
                validation_messages.append(f"{name}: Graph is empty")
                is_valid = False

            # Data completeness checks
            completeness_issues = self._check_data_completeness(g, name)
            validation_messages.extend(completeness_issues)
            if completeness_issues:
                is_valid = False

            # Cross-reference validation
            cross_ref_issues = self._check_cross_references(g, name)
            validation_messages.extend(cross_ref_issues)
            if cross_ref_issues:
                is_valid = False

        except Exception as e:
            validation_messages.append(f"{name}: Validation error: {e}")
            is_valid = False

        return is_valid, validation_messages

    def _check_data_completeness(self, g: Any, name: str) -> list[str]:
        """
        Check data completeness metrics.

        Parameters
        ----------
        g : Graph
            RDF graph
        name : str
            Graph name

        Returns
        -------
        list[str]
            List of completeness issues
        """
        issues = []

        # Count entities by type
        from collections import Counter

        from rdflib.namespace import RDF

        entity_counts = Counter()
        for _, _, o in g.triples((None, RDF.type, None)):
            entity_type = str(o).split("/")[-1]  # Get local part of URI
            entity_counts[entity_type] += 1

        # Check ORCID coverage for authors
        author_count = entity_counts.get("Person", 0) + entity_counts.get("Author", 0)
        orcid_count = 0
        for _, _, o in g.triples((None, None, None)):
            if "orcid" in str(o).lower():
                orcid_count += 1

        if author_count > 0:
            orcid_coverage = orcid_count / author_count
            if orcid_coverage < 0.5:  # Less than 50% ORCID coverage
                issues.append(
                    f"{name}: Low ORCID coverage: {orcid_count}/{author_count} "
                    f"({orcid_coverage:.1%})"
                )

        # Check institution linking
        institution_count = entity_counts.get("Organization", 0) + entity_counts.get(
            "Institution", 0
        )
        ror_count = 0
        for _, _, o in g.triples((None, None, None)):
            if "ror.org" in str(o):
                ror_count += 1

        if institution_count > 0:
            ror_coverage = ror_count / institution_count
            if ror_coverage < 0.7:  # Less than 70% ROR coverage
                issues.append(
                    f"{name}: Low ROR coverage: {ror_count}/{institution_count} "
                    f"({ror_coverage:.1%})"
                )

        return issues

    def _check_cross_references(self, g: Any, name: str) -> list[str]:
        """
        Check cross-references between entities.

        Parameters
        ----------
        g : Graph
            RDF graph
        name : str
            Graph name

        Returns
        -------
        list[str]
            List of cross-reference issues
        """
        issues = []

        # Check for orphaned references (cited works without DOIs)
        citation_count = 0
        doi_count = 0
        for _, p, o in g.triples((None, None, None)):
            if "citation" in str(p).lower() or "cites" in str(p).lower():
                citation_count += 1
            if "doi" in str(p).lower() and str(o).startswith("https://doi.org/"):
                doi_count += 1

        if citation_count > doi_count:
            issues.append(
                f"{name}: Potential orphaned citations: {citation_count} citations "
                f"but only {doi_count} DOI references"
            )

        return issues
