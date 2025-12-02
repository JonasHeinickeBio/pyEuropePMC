"""
Data models for structured parsing of Europe PMC articles.

This package provides typed data models that wrap the outputs of FullTextXMLParser
and enable RDF serialization aligned to ontologies (AID-PAIS, BIBO, FOAF, PROV, etc.).
"""

from pyeuropepmc.models.author import AuthorEntity
from pyeuropepmc.models.base import BaseEntity
from pyeuropepmc.models.figure import FigureEntity
from pyeuropepmc.models.institution import InstitutionEntity
from pyeuropepmc.models.journal import JournalEntity
from pyeuropepmc.models.mesh import MeSHHeadingEntity, MeSHQualifierEntity
from pyeuropepmc.models.paper import PaperEntity
from pyeuropepmc.models.reference import ReferenceEntity
from pyeuropepmc.models.scholarly_work import ScholarlyWorkEntity
from pyeuropepmc.models.section import SectionEntity
from pyeuropepmc.models.table import TableEntity, TableRowEntity

__all__ = [
    "BaseEntity",
    "ScholarlyWorkEntity",
    "AuthorEntity",
    "InstitutionEntity",
    "JournalEntity",
    "MeSHHeadingEntity",
    "MeSHQualifierEntity",
    "PaperEntity",
    "SectionEntity",
    "TableEntity",
    "TableRowEntity",
    "FigureEntity",
    "ReferenceEntity",
]
