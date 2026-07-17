"""
Bibliographic reference management for pyEuropePMC.

This module provides tools for working with BibTeX files, Zotero libraries,
and citation format conversion. It integrates with the agentic framework
via ``ToolRegistry`` tools and ``ResearchPipeline`` stages.

Submodules
----------
models
    Typed dataclasses for BibEntry, BibLibrary, Reference, etc.
bibtex
    BibTeX parse/write/validate/merge via ``BibtexManager``.
reference
    DOI/PMID/arXiv resolution via ``ReferenceResolver``.
conversion
    Format conversion (BibTeX ↔ RIS ↔ CSL-JSON).
zotero
    Zotero library access via ``ZoteroClient`` (requires pyzotero).

Optional dependencies
---------------------
- ``bibtexparser`` — BibTeX parsing/writing (``pip install pyeuropepmc[bibliography]``)
- ``pyzotero`` — Zotero API client (``pip install pyeuropepmc[zotero]``)
"""

from pyeuropepmc.features.bibliography import models
from pyeuropepmc.features.bibliography.bibtex import BIBTEXPARSER_AVAILABLE, BibtexManager
from pyeuropepmc.features.bibliography.conversion import CitationConverter
from pyeuropepmc.features.bibliography.models import (
    BibEntry,
    BibLibrary,
    CitationFormat,
    Reference,
    VerificationResult,
    VerificationStatus,
)
from pyeuropepmc.features.bibliography.reference import (
    IdentifierType,
    ReferenceResolver,
    detect_identifier_type,
)
from pyeuropepmc.features.bibliography.zotero import ZOTERO_AVAILABLE, ZoteroClient

__all__ = [
    # Models
    "BibEntry",
    "BibLibrary",
    "CitationFormat",
    "Reference",
    "VerificationResult",
    "VerificationStatus",
    # BibTeX
    "BibtexManager",
    "BIBTEXPARSER_AVAILABLE",
    # Reference resolution
    "ReferenceResolver",
    "IdentifierType",
    "detect_identifier_type",
    # Conversion
    "CitationConverter",
    # Zotero
    "ZoteroClient",
    "ZOTERO_AVAILABLE",
]
