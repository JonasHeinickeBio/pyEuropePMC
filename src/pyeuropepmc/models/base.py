"""
Base entity class for all data models.

This module provides the foundational BaseEntity class that all other entities inherit from,
with support for RDF serialization, validation, and normalization.
"""

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

from rdflib import Namespace, URIRef

# RDF namespaces for ontology alignment
EX = Namespace("http://example.org/")
DATA = Namespace("http://example.org/data/")
DCT = Namespace("http://purl.org/dc/terms/")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
PROV = Namespace("http://www.w3.org/ns/prov#")
BIBO = Namespace("http://purl.org/ontology/bibo/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")

__all__ = [
    "BaseEntity",
    "EX",
    "DATA",
    "DCT",
    "RDFS",
    "PROV",
    "BIBO",
    "FOAF",
    "NIF",
]


@dataclass
class BaseEntity:
    """
    Base entity for all data models with RDF serialization support.

    All entities inherit from this base class, which provides common functionality
    for validation, normalization, and RDF export.

    Attributes
    ----------
    id : Optional[str]
        Local identifier (slug/uuid) for the entity
    label : Optional[str]
        Human-readable label for the entity
    source_uri : Optional[str]
        Source URI (e.g., PMC XML file IRI) for provenance tracking
    confidence : Optional[float]
        Confidence score for extracted information (0.0 to 1.0)
    types : list[str]
        RDF types (CURIEs/URIs) for this entity

    Examples
    --------
    >>> entity = BaseEntity(id="test-123", label="Test Entity")
    >>> entity.validate()
    >>> uri = entity.mint_uri("entity")
    >>> print(uri)
    http://example.org/data/entity/test-123
    """

    id: str | None = None
    label: str | None = None
    source_uri: str | None = None
    confidence: float | None = None
    types: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    last_updated: str | None = None

    def mint_uri(self, path: str) -> URIRef:
        """
        Mint a URI for this entity under the DATA namespace.

        Parameters
        ----------
        path : str
            Path component for the URI (e.g., "paper", "author")

        Returns
        -------
        URIRef
            Generated URI for this entity

        Examples
        --------
        >>> entity = BaseEntity(id="12345")
        >>> uri = entity.mint_uri("paper")
        >>> print(uri)
        http://example.org/data/paper/12345
        """
        if self.id is None:
            self.id = str(uuid.uuid4())
        return URIRef(f"{DATA}{path}/{self.id}")

    def validate(self) -> None:
        """
        Validate the entity's data.

        Override in subclasses to add specific validation logic.
        Should raise ValueError for critical validation issues.

        Raises
        ------
        ValueError
            If validation fails
        """
        pass

    def normalize(self) -> None:
        """
        Normalize the entity's data.

        Override in subclasses to add specific normalization logic
        (e.g., lowercase DOI, trim whitespace, standardize formats).
        """
        pass

    def to_dict(self) -> dict[str, Any]:
        """
        Convert entity to dictionary representation.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of the entity

        Examples
        --------
        >>> entity = BaseEntity(id="test", label="Test")
        >>> data = entity.to_dict()
        >>> print(data["label"])
        Test
        """
        return asdict(self)

    def merge_from_source(self, source_data: dict[str, Any], source_name: str) -> None:
        """
        Merge data from a source into this entity, tracking provenance.

        Parameters
        ----------
        source_data : dict[str, Any]
            Data from the source to merge
        source_name : str
            Name of the data source

        Examples
        --------
        >>> entity = BaseEntity()
        >>> entity.merge_from_source({"label": "Test"}, "search_api")
        >>> print(entity.data_sources)
        ['search_api']
        """
        from datetime import datetime

        # Track data source
        if source_name not in self.data_sources:
            self.data_sources.append(source_name)

        # Update last_updated timestamp
        self.last_updated = datetime.now().isoformat() + "Z"

        # Merge data (subclasses should override for specific logic)
        for key, value in source_data.items():
            if hasattr(self, key) and value is not None:
                current_value = getattr(self, key)
                # Only update if current value is None or empty
                if current_value is None or (
                    isinstance(current_value, str) and not current_value.strip()
                ):
                    setattr(self, key, value)

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
        >>> BaseEntity._is_valid_uri("http://example.com")
        True
        >>> BaseEntity._is_valid_uri("BMJ Open Respir Res")
        False
        """
        if not uri_string or not isinstance(uri_string, str):
            return False

        # Basic URI validation - must have scheme (protocol) like http://, https://, ftp://, etc.
        # This is a simple check - rdflib's URIRef will do more thorough validation
        return "://" in uri_string and len(uri_string.split("://", 1)[0]) > 0

    def to_rdf(
        self,
        g: Any,
        uri: URIRef | None = None,
        mapper: Any = None,
        related_entities: dict[str, list[Any]] | None = None,
        extraction_info: dict[str, Any] | None = None,
        parent_uri: URIRef | None = None,
    ) -> URIRef:
        """
        Serialize entity to RDF graph using a mapper.

        Parameters
        ----------
        g : Graph
            RDF graph to add triples to
        uri : Optional[URIRef]
            URI for this entity (if None, will be minted)
        mapper : Optional[Any]
            RDF mapper instance to use for serialization
        related_entities : Optional[dict[str, list[Any]]]
            Dictionary of related entities by relationship name
        extraction_info : Optional[dict[str, Any]]
            Additional extraction metadata for provenance
        parent_uri : Optional[URIRef]
            URI of the parent entity (for generating contextual URIs)

        Returns
        -------
        URIRef
            Subject URI for this entity

        Raises
        ------
        ValueError
            If mapper is not provided

        Examples
        --------
        >>> from rdflib import Graph
        >>> from pyeuropepmc.mappers.rdf_mapper import RDFMapper
        >>> entity = BaseEntity(id="test", label="Test Entity")
        >>> g = Graph()
        >>> mapper = RDFMapper()
        >>> uri = entity.to_rdf(g, mapper=mapper)
        """
        if mapper is None:
            raise ValueError("RDF mapper required")

        # Use mapper's URI generation logic for consistency
        subject = uri or mapper._generate_entity_uri(self)

        # Determine named graph context for this entity type
        entity_type = self.__class__.__name__.lower().replace("entity", "")
        context = mapper._get_named_graph_uri(entity_type)

        # Add RDF types
        mapper.add_types(g, subject, self.types, context)

        # Map dataclass fields using the mapper configuration
        mapper.map_fields(g, subject, self, context)

        # Map relationships (always call, even if no related_entities provided)
        # This allows entities to have relationships defined as attributes
        mapper.map_relationships(g, subject, self, related_entities, extraction_info, context)

        # Add provenance information
        mapper.add_provenance(g, subject, self, extraction_info, context)

        # Add ontology alignments and biomedical mappings
        mapper.map_ontology_alignments(g, subject, self, context)

        return subject
