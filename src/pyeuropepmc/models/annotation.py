"""
Annotation entity model for representing text-mining annotations.

This module provides entity models for representing annotations extracted
from scientific literature, following the W3C Open Annotation Data Model.
"""

from dataclasses import dataclass, field
from typing import Any

from pyeuropepmc.models.base import BaseEntity

__all__ = ["AnnotationEntity", "EntityAnnotation", "RelationshipAnnotation"]


@dataclass
class AnnotationEntity(BaseEntity):
    """
    Base entity representing a text-mining annotation.

    This class represents annotations extracted from scientific literature
    following the W3C Open Annotation Data Model.

    Attributes
    ----------
    exact : Optional[str]
        The exact text being annotated
    prefix : Optional[str]
        Text before the annotation
    postfix : Optional[str]
        Text after the annotation
    section : Optional[str]
        Section where annotation appears (abstract, body, etc.)
    provider : Optional[str]
        Annotation provider (e.g., "Europe PMC", "Pubtator")
    article_id : Optional[str]
        PMC ID of the article containing this annotation
    position : Optional[dict[str, int]]
        Start and end position in text
    annotation_type : Optional[str]
        Type of annotation (entity, sentence, relationship)

    Examples
    --------
    >>> annotation = AnnotationEntity(
    ...     exact="malaria",
    ...     section="abstract",
    ...     provider="Europe PMC",
    ...     annotation_type="entity"
    ... )
    """

    exact: str | None = None
    prefix: str | None = None
    postfix: str | None = None
    section: str | None = None
    provider: str | None = None
    article_id: str | None = None
    position: dict[str, int] | None = None
    annotation_type: str | None = None

    types: list[str] = field(
        default_factory=lambda: ["oa:Annotation", "nif:String"],
        init=False,
    )

    def validate(self) -> None:
        """
        Validate the annotation entity.

        Raises
        ------
        ValueError
            If required fields are missing
        """
        super().validate()
        if not self.exact:
            raise ValueError("Annotation must have 'exact' text")


@dataclass
class EntityAnnotation(AnnotationEntity):
    """
    Entity representing a named entity annotation (gene, disease, chemical, etc.).

    Attributes
    ----------
    entity_id : Optional[str]
        Entity identifier (e.g., "CHEBI:16236", "DOID:12365")
    entity_name : Optional[str]
        Name of the entity
    entity_type : Optional[str]
        Type of entity (Gene, Disease, Chemical, etc.)
    confidence : Optional[float]
        Confidence score for the annotation

    Examples
    --------
    >>> entity = EntityAnnotation(
    ...     exact="malaria",
    ...     entity_id="DOID:12365",
    ...     entity_name="malaria",
    ...     entity_type="Disease",
    ...     section="abstract",
    ...     provider="Europe PMC"
    ... )
    """

    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    confidence: float | None = None

    types: list[str] = field(
        default_factory=lambda: ["oa:Annotation", "nif:String", "oa:SpecificResource"],
        init=False,
    )

    def validate(self) -> None:
        """
        Validate the entity annotation.

        Raises
        ------
        ValueError
            If required fields are missing
        """
        super().validate()
        if not self.entity_id and not self.entity_name:
            raise ValueError("EntityAnnotation must have entity_id or entity_name")


@dataclass
class RelationshipAnnotation(AnnotationEntity):
    """
    Entity representing a relationship between two entities.

    Attributes
    ----------
    subject_id : Optional[str]
        ID of the subject entity
    subject_name : Optional[str]
        Name of the subject entity
    subject_type : Optional[str]
        Type of the subject entity
    predicate : Optional[str]
        Relationship predicate (e.g., "associated_with", "inhibits")
    object_id : Optional[str]
        ID of the object entity
    object_name : Optional[str]
        Name of the object entity
    object_type : Optional[str]
        Type of the object entity

    Examples
    --------
    >>> relationship = RelationshipAnnotation(
    ...     exact="TP53 is associated with cancer",
    ...     subject_id="GENE:7157",
    ...     subject_name="TP53",
    ...     subject_type="Gene",
    ...     predicate="associated_with",
    ...     object_id="DOID:162",
    ...     object_name="cancer",
    ...     object_type="Disease",
    ...     section="body"
    ... )
    """

    subject_id: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    predicate: str | None = None
    object_id: str | None = None
    object_name: str | None = None
    object_type: str | None = None

    types: list[str] = field(
        default_factory=lambda: ["oa:Annotation", "nif:String", "rdf:Statement"],
        init=False,
    )

    def validate(self) -> None:
        """
        Validate the relationship annotation.

        Raises
        ------
        ValueError
            If required fields are missing
        """
        super().validate()
        if not (self.subject_id or self.subject_name):
            raise ValueError("RelationshipAnnotation must have subject_id or subject_name")
        if not (self.object_id or self.object_name):
            raise ValueError("RelationshipAnnotation must have object_id or object_name")
