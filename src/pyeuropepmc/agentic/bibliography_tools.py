"""
Agentic tool registration for all bibliography operations.

This module registers BibTeX parsing, reference resolution, format conversion,
and Zotero tools on a ``ToolRegistry`` for use by the agentic framework.
"""

from __future__ import annotations

import logging
from typing import Any

from pyeuropepmc.agentic.registry import ToolRegistry, ToolType
from pyeuropepmc.features.bibliography import (
    BibLibrary,
    BibtexManager,
    CitationConverter,
    ReferenceResolver,
)
from pyeuropepmc.features.bibliography.bibtex import is_bibtex_content
from pyeuropepmc.features.bibliography.zotero import ZoteroClient

logger = logging.getLogger(__name__)

bibliography_registry = ToolRegistry(name="bibliography")


# ---------------------------------------------------------------------------
# BibTeX Tools
# ---------------------------------------------------------------------------


@bibliography_registry.register(
    name="bib_parse_string",
    description="Parse a BibTeX string into a serialized library dict with entry count and key list.",
    tool_type=ToolType.EXTRACTION,
)
def bib_parse_string(content: str) -> dict:
    """Parse a BibTeX string into a serialized library.

    Parameters
    ----------
    content : str
        BibTeX-formatted string.

    Returns
    -------
    dict
        ``{"entries": [...], "entries_count": int, "keys": [str,...]}``
        or ``{"error": str}`` on failure.
    """
    try:
        manager = BibtexManager()
        library = manager.parse_string(content)
        return {
            "entries": library.to_dict(),
            "entries_count": len(library.entries),
            "keys": [e.citation_key for e in library.entries],
        }
    except Exception as exc:
        logger.error("bib_parse_string failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="bib_parse_file",
    description="Parse a .bib file into a serialized library dict.",
    tool_type=ToolType.EXTRACTION,
)
def bib_parse_file(path: str) -> dict:
    """Parse a ``.bib`` file into a serialized library.

    Parameters
    ----------
    path : str
        Filesystem path to the ``.bib`` file.

    Returns
    -------
    dict
        ``{"entries": [...], "entries_count": int, "keys": [str,...], "file_path": str}``
        or ``{"error": str}`` on failure.
    """
    try:
        manager = BibtexManager()
        library = manager.parse_file(path)
        return {
            "entries": library.to_dict(),
            "entries_count": len(library.entries),
            "keys": [e.citation_key for e in library.entries],
            "file_path": str(library.file_path),
        }
    except Exception as exc:
        logger.error("bib_parse_file failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="bib_write_string",
    description="Serialize a library dict back to a BibTeX-formatted string.",
    tool_type=ToolType.CONVERSION,
)
def bib_write_string(library_dict: dict) -> dict:
    """Serialize a library dict to a BibTeX string.

    Parameters
    ----------
    library_dict : dict
        Dict with ``"entries"`` key containing a list of entry dicts
        (as returned by ``bib_parse_*``).

    Returns
    -------
    dict
        ``{"bibtex": str, "entries_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        manager = BibtexManager()
        library = BibLibrary.from_dict(library_dict.get("entries", []))
        bibtex = manager.write_string(library)
        return {"bibtex": bibtex, "entries_count": len(library.entries)}
    except Exception as exc:
        logger.error("bib_write_string failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="bib_write_file",
    description="Write a library dict to a .bib file on disk.",
    tool_type=ToolType.CONVERSION,
)
def bib_write_file(library_dict: dict, path: str) -> dict:
    """Write a library dict to a ``.bib`` file.

    Parameters
    ----------
    library_dict : dict
        Dict with ``"entries"`` key containing a list of entry dicts.
    path : str
        Destination file path.

    Returns
    -------
    dict
        ``{"path": str, "entries_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        manager = BibtexManager()
        library = BibLibrary.from_dict(library_dict.get("entries", []))
        result_path = manager.write_file(library, path)
        return {"path": str(result_path), "entries_count": len(library.entries)}
    except Exception as exc:
        logger.error("bib_write_file failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="bib_validate",
    description="Validate BibTeX entries and return a list of issues (warnings/errors).",
    tool_type=ToolType.VALIDATION,
)
def bib_validate(library_dict: dict) -> dict:
    """Validate entries in a library dict.

    Parameters
    ----------
    library_dict : dict
        Dict with ``"entries"`` key containing a list of entry dicts.

    Returns
    -------
    dict
        ``{"issues": [dict,...], "issues_count": int, "entries_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        manager = BibtexManager()
        library = BibLibrary.from_dict(library_dict.get("entries", []))
        issues = manager.validate(library)
        return {
            "issues": issues,
            "issues_count": len(issues),
            "entries_count": len(library.entries),
        }
    except Exception as exc:
        logger.error("bib_validate failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="bib_merge",
    description="Merge multiple library dicts into one, deduplicating by DOI.",
    tool_type=ToolType.UTILITY,
)
def bib_merge(libraries: list[dict]) -> dict:
    """Merge multiple library dicts with deduplication.

    Parameters
    ----------
    libraries : list[dict]
        List of library dicts, each with an ``"entries"`` key.

    Returns
    -------
    dict
        ``{"entries": [...], "entries_count": int, "keys": [str,...], "deduplicated": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        manager = BibtexManager()
        bib_libraries = [BibLibrary.from_dict(lib.get("entries", [])) for lib in libraries]
        total_before = sum(len(lib.entries) for lib in bib_libraries)
        merged = manager.merge(bib_libraries)
        deduped = total_before - len(merged.entries)
        return {
            "entries": merged.to_dict(),
            "entries_count": len(merged.entries),
            "keys": [e.citation_key for e in merged.entries],
            "deduplicated": deduped,
        }
    except Exception as exc:
        logger.error("bib_merge failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Reference Resolution Tools
# ---------------------------------------------------------------------------


@bibliography_registry.register(
    name="ref_resolve_doi",
    description="Resolve a DOI to a bibliographic reference via CrossRef.",
    tool_type=ToolType.SEARCH,
)
def ref_resolve_doi(doi: str) -> dict:
    """Resolve a DOI to a ``Reference`` dict.

    Parameters
    ----------
    doi : str
        Digital Object Identifier (e.g. ``"10.1038/nature14539"``).

    Returns
    -------
    dict
        ``{"reference": {...}, "source": str}``
        or ``{"error": str}`` on failure.
    """
    try:
        resolver = ReferenceResolver()
        ref = resolver.resolve_doi(doi)
        if ref is None:
            return {"error": f"Could not resolve DOI: {doi}"}
        return {"reference": ref.to_dict(), "source": ref.source}
    except Exception as exc:
        logger.error("ref_resolve_doi failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="ref_resolve_pmid",
    description="Resolve a PubMed ID to a bibliographic reference via Europe PMC.",
    tool_type=ToolType.SEARCH,
)
def ref_resolve_pmid(pmid: str) -> dict:
    """Resolve a PubMed ID to a ``Reference`` dict.

    Parameters
    ----------
    pmid : str
        PubMed ID (e.g. ``"25686660"``).

    Returns
    -------
    dict
        ``{"reference": {...}, "source": str}``
        or ``{"error": str}`` on failure.
    """
    try:
        resolver = ReferenceResolver()
        ref = resolver.resolve_pmid(pmid)
        if ref is None:
            return {"error": f"Could not resolve PMID: {pmid}"}
        return {"reference": ref.to_dict(), "source": ref.source}
    except Exception as exc:
        logger.error("ref_resolve_pmid failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="ref_resolve_arxiv",
    description="Resolve an arXiv ID to a bibliographic reference.",
    tool_type=ToolType.SEARCH,
)
def ref_resolve_arxiv(arxiv_id: str) -> dict:
    """Resolve an arXiv ID to a ``Reference`` dict.

    Parameters
    ----------
    arxiv_id : str
        arXiv identifier (e.g. ``"2301.12345"`` or ``"arXiv:2301.12345"``).

    Returns
    -------
    dict
        ``{"reference": {...}, "source": str}``
        or ``{"error": str}`` on failure.
    """
    try:
        resolver = ReferenceResolver()
        ref = resolver.resolve_arxiv(arxiv_id)
        if ref is None:
            return {"error": f"Could not resolve arXiv ID: {arxiv_id}"}
        return {"reference": ref.to_dict(), "source": ref.source}
    except Exception as exc:
        logger.error("ref_resolve_arxiv failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Conversion Tools
# ---------------------------------------------------------------------------


@bibliography_registry.register(
    name="convert_to_ris",
    description="Convert a BibLibrary dict to a RIS-format string.",
    tool_type=ToolType.CONVERSION,
)
def convert_to_ris(library_dict: dict) -> dict:
    """Convert a BibLibrary to a RIS format string.

    Parameters
    ----------
    library_dict : dict
        Dict with ``"entries"`` key containing a list of entry dicts.

    Returns
    -------
    dict
        ``{"ris": str, "entries_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        converter = CitationConverter()
        library = BibLibrary.from_dict(library_dict.get("entries", []))
        ris_entries: list[str] = []
        for entry in library.entries:
            ris_entries.append(converter.to_ris(entry))
        return {"ris": "\n\n".join(ris_entries), "entries_count": len(ris_entries)}
    except Exception as exc:
        logger.error("convert_to_ris failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="convert_to_csl",
    description="Convert a BibLibrary dict to a CSL-JSON list.",
    tool_type=ToolType.CONVERSION,
)
def convert_to_csl(library_dict: dict) -> dict:
    """Convert a BibLibrary to a CSL-JSON list.

    Parameters
    ----------
    library_dict : dict
        Dict with ``"entries"`` key containing a list of entry dicts.

    Returns
    -------
    dict
        ``{"csl_json": [dict,...], "entries_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        converter = CitationConverter()
        library = BibLibrary.from_dict(library_dict.get("entries", []))
        csl_items: list[dict[str, Any]] = []
        for entry in library.entries:
            csl_items.append(converter.to_csl_json(entry))
        return {"csl_json": csl_items, "entries_count": len(csl_items)}
    except Exception as exc:
        logger.error("convert_to_csl failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Zotero Tools
# ---------------------------------------------------------------------------


@bibliography_registry.register(
    name="zotero_list_collections",
    description="List all collections in a Zotero library.",
    tool_type=ToolType.SEARCH,
)
def zotero_list_collections(
    api_key: str,
    library_id: str,
    library_type: str = "user",
) -> dict:
    """List Zotero collections.

    Parameters
    ----------
    api_key : str
        Zotero API key.
    library_id : str
        Zotero library ID.
    library_type : str, optional
        ``"user"`` (default) or ``"group"``.

    Returns
    -------
    dict
        ``{"collections": [dict,...], "collections_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        client = ZoteroClient(
            api_key=api_key,
            library_id=library_id,
            library_type=library_type,
        )
        collections = client.get_collections()
        return {"collections": collections, "collections_count": len(collections)}
    except Exception as exc:
        logger.error("zotero_list_collections failed: %s", exc)
        return {"error": str(exc)}


@bibliography_registry.register(
    name="zotero_export_collection",
    description="Export all items in a Zotero collection as BibTeX.",
    tool_type=ToolType.EXTRACTION,
)
def zotero_export_collection(
    api_key: str,
    library_id: str,
    collection_key: str,
    library_type: str = "user",
) -> dict:
    """Export a Zotero collection as BibTeX.

    Parameters
    ----------
    api_key : str
        Zotero API key.
    library_id : str
        Zotero library ID.
    collection_key : str
        Key of the collection to export.
    library_type : str, optional
        ``"user"`` (default) or ``"group"``.

    Returns
    -------
    dict
        ``{"bibtex": str, "items_count": int}``
        or ``{"error": str}`` on failure.
    """
    try:
        client = ZoteroClient(
            api_key=api_key,
            library_id=library_id,
            library_type=library_type,
        )
        items = client.search(collection_key=collection_key)
        bibtex_parts: list[str] = []
        for item in items:
            item_key = item.get("key")
            if item_key:
                try:
                    bib = client.get_bibtex(item_key)
                    if bib:
                        bibtex_parts.append(bib)
                except Exception:
                    logger.debug("Skipping item %s in collection export", item_key)
        return {
            "bibtex": "\n\n".join(bibtex_parts),
            "items_count": len(items),
        }
    except Exception as exc:
        logger.error("zotero_export_collection failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


@bibliography_registry.register(
    name="bib_is_bibtex",
    description="Quick heuristic check if a text string appears to be BibTeX.",
    tool_type=ToolType.VALIDATION,
)
def bib_is_bibtex(content: str) -> dict:
    """Check if a text string looks like BibTeX using a heuristic pattern.

    Parameters
    ----------
    content : str
        Text to check.

    Returns
    -------
    dict
        ``{"is_bibtex": bool, "match_found": bool}``
        or ``{"error": str}`` on failure.
    """
    try:
        result = is_bibtex_content(content)
        return {"is_bibtex": result, "match_found": result}
    except Exception as exc:
        logger.error("bib_is_bibtex failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

__all__ = ["bibliography_registry", "register_all_bibliography_tools"]


def register_all_bibliography_tools(
    target_registry: ToolRegistry | None = None,
) -> ToolRegistry:
    """Register all bibliography tools into a target registry (or return standalone).

    Parameters
    ----------
    target_registry : ToolRegistry or None
        If provided, copies all tool definitions from the module-level
        ``bibliography_registry`` into ``target_registry``.

    Returns
    -------
    ToolRegistry
        The (possibly populated) target registry, or the module-level registry.
    """
    reg = target_registry or bibliography_registry
    if target_registry:
        for info in bibliography_registry.list_all():
            reg.register(name=info.name, description=info.description, tool_type=info.tool_type)(
                info.func
            )
    return reg
