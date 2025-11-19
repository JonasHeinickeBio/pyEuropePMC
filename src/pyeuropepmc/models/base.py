"""
Base entity class for all data models.

This module provides the foundational BaseEntity class that all other entities inherit from,
with support for RDF serialization, validation, and normalization.
"""

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

from rdflib import Graph, Literal, Namespace, URIRef

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
        _id = self.id or str(uuid.uuid4())
        return URIRef(f"{DATA}{path}/{_id}")

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

    def to_rdf(
        self,
        g: Graph,
        uri: URIRef | None = None,
        mapper: Any | None = None,
        related_entities: dict[str, list[Any]] | None = None,
        extraction_info: dict[str, Any] | None = None,
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

        # Add RDF types
        mapper.add_types(g, subject, self.types)

        # Map dataclass fields using the mapper configuration
        mapper.map_fields(g, subject, self)

        # Map relationships if provided
        if related_entities:
            mapper.map_relationships(g, subject, self, related_entities)

        # Add provenance information
        mapper.add_provenance(g, subject, self, extraction_info)

        # Add ontology alignments and biomedical mappings
        mapper.map_ontology_alignments(g, subject, self)

        # Add common provenance and metadata (legacy support)
        if self.source_uri:
            g.add((subject, PROV.wasDerivedFrom, URIRef(self.source_uri)))

        if self.label:
            g.add((subject, RDFS.label, Literal(self.label)))

        if self.confidence is not None:
            g.add((subject, EX.confidence, Literal(self.confidence)))

        return subject
