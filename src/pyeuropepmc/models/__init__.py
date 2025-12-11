"""
Data models for structured parsing of Europe PMC articles.

This package provides typed data models that wrap the outputs of FullTextXMLParser
and enable RDF serialization aligned to ontologies (AID-PAIS, BIBO, FOAF, PROV, etc.).
It also includes models for text-mining annotations.
"""

from pyeuropepmc.models.annotation import (
    AnnotationEntity,
    EntityAnnotation,
    RelationshipAnnotation,
)
from pyeuropepmc.models.author import AuthorEntity
from pyeuropepmc.models.base import BaseEntity
from pyeuropepmc.models.figure import FigureEntity
from pyeuropepmc.models.paper import PaperEntity
from pyeuropepmc.models.reference import ReferenceEntity
from pyeuropepmc.models.section import SectionEntity
from pyeuropepmc.models.table import TableEntity, TableRowEntity

__all__ = [
    "BaseEntity",
    "AuthorEntity",
    "PaperEntity",
    "SectionEntity",
    "TableEntity",
    "TableRowEntity",
    "FigureEntity",
    "ReferenceEntity",
    "AnnotationEntity",
    "EntityAnnotation",
    "RelationshipAnnotation",
]
