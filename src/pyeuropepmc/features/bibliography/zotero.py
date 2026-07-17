"""
Zotero API client for bibliographic library access.

Wraps the ``pyzotero`` library with the pyEuropePMC conventions for
logging, error handling, and model conversion.

Requires ``pyzotero`` (install with ``pip install pyeuropepmc[zotero]``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pyeuropepmc._optional_imports import check_dependencies
from pyeuropepmc.features.bibliography.models import BibEntry, Reference

logger = logging.getLogger(__name__)

__all__ = ["ZoteroClient", "ZOTERO_AVAILABLE"]

try:
    check_dependencies(["pyzotero"], "Zotero integration", "zotero")
    from pyzotero import Zotero as _PyZotero

    ZOTERO_AVAILABLE = True
except Exception:
    _PyZotero = None  # type: ignore[assignment]
    ZOTERO_AVAILABLE = False


class ZoteroClient:
    """
    Client for accessing Zotero libraries.

    Supports both local (read-only) and remote API access.

    Parameters
    ----------
    library_id : str, optional
        Zotero library ID. If None, reads from ``ZOTERO_LIBRARY_ID`` env var.
    library_type : str, optional
        ``"user"`` (default) or ``"group"``.
    api_key : str, optional
        Zotero API key. If None, reads from ``ZOTERO_API_KEY`` env var.
    local : bool, optional
        If True, connect to local Zotero desktop API (read-only, no API key needed).
        Default: False (uses web API).
    """

    def __init__(
        self,
        library_id: str | None = None,
        library_type: str = "user",
        api_key: str | None = None,
        local: bool = False,
    ) -> None:
        if not ZOTERO_AVAILABLE:
            raise ImportError(
                "pyzotero is required for Zotero integration. "
                "Install with: pip install pyeuropepmc[zotero]"
            )

        self._library_id = library_id or os.getenv("ZOTERO_LIBRARY_ID", "")
        self._library_type = library_type
        self._api_key = api_key or os.getenv("ZOTERO_API_KEY", "")
        self._local = local or os.getenv("ZOTERO_LOCAL", "").lower() in ("1", "true")

        if not self._local and not self._api_key:
            logger.warning(
                "No Zotero API key provided. "
                "Set ZOTERO_API_KEY env var or pass api_key. "
                "For local read-only access, set local=True."
            )

        self._zot: _PyZotero | None = None

    @property
    def _client(self) -> _PyZotero:
        if self._zot is None:
            self._zot = _PyZotero(
                library_id=self._library_id,
                library_type=self._library_type,
                api_key=self._api_key if not self._local else None,
                local=self._local,
            )
        return self._zot

    # ------------------------------------------------------------------
    # Search & retrieval
    # ------------------------------------------------------------------

    def search(
        self,
        query: str | None = None,
        limit: int = 25,
        item_type: str | None = None,
        tag: str | list[str] | None = None,
        qmode: str = "titleCreatorYear",
        collection_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search the Zotero library.

        Parameters
        ----------
        query : str, optional
            Search terms. Searches title, creators, and year by default.
        limit : int
            Maximum results (default: 25).
        item_type : str, optional
            Filter by item type (e.g. ``"journalArticle"``, ``"book"``).
        tag : str or list, optional
            Filter by tag(s).
        qmode : str
            Search mode: ``"titleCreatorYear"`` (default) or ``"everything"``.
        collection_key : str, optional
            Restrict search to a specific collection.

        Returns
        -------
        list[dict]
            Zotero API item dicts.
        """
        self._client.add_parameters(limit=min(limit, 100))
        if query:
            self._client.add_parameters(q=query, qmode=qmode)
        if item_type:
            self._client.add_parameters(itemType=item_type)
        if tag:
            self._client.add_parameters(tag=tag if isinstance(tag, str) else " ".join(tag))

        if collection_key:
            return self._client.collection_items(collection_key)  # type: ignore[no-any-return]
        if query or item_type or tag:
            return list(self._client.items())  # type: ignore[arg-type]
        return list(self._client.top(limit=limit))  # type: ignore[arg-type]

    def get_item(self, item_key: str) -> dict[str, Any] | None:
        """Get a single item by its Zotero item key."""
        items = self._client.items(itemKey=item_key)  # type: ignore[arg-type]
        return items[0] if items else None

    def get_collections(self) -> list[dict[str, Any]]:
        """List all collections in the library."""
        return list(self._client.collections())  # type: ignore[no-any-return]

    def get_tags(self, collection_key: str | None = None) -> list[str]:
        """List all tags, optionally filtered by collection."""
        if collection_key:
            return list(self._client.tags(collectionKey=collection_key))  # type: ignore[no-any-return]
        return list(self._client.tags())  # type: ignore[no-any-return]

    def get_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        """Get recently added items."""
        self._client.add_parameters(sort="dateAdded", direction="desc", limit=min(limit, 100))
        return list(self._client.top())  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Export / conversion
    # ------------------------------------------------------------------

    def get_bibtex(self, item_key: str | list[str], **kwargs: Any) -> str:
        """Export Zotero item(s) as BibTeX.

        Parameters
        ----------
        item_key : str or list[str]
            Single item key or list of keys.

        Returns
        -------
        str
            BibTeX-formatted string.
        """
        keys = item_key if isinstance(item_key, list) else [item_key]
        self._client.add_parameters(format="bibtex", **kwargs)
        results = self._client.items(itemKey=",".join(keys))  # type: ignore[arg-type]
        if isinstance(results, list):
            return "\n\n".join(str(r) for r in results)
        return str(results)

    def item_to_reference(self, item: dict[str, Any]) -> Reference:
        """Convert a Zotero API item dict to a ``Reference``."""
        data = item.get("data", item)
        ref = Reference(source="zotero")
        ref.title = data.get("title")
        ref.doi = data.get("DOI")
        ref.pmid = self._extract_pmid(data)
        ref.isbn = data.get("ISBN")
        ref.url = data.get("url")
        ref.abstract = data.get("abstractNote")
        ref.entry_type = self._zotero_type_to_bibtex(data.get("itemType", "journalArticle"))
        ref.year = self._extract_year(data)
        ref.journal = data.get("publicationTitle") or data.get("journalName")
        ref.volume = data.get("volume")
        ref.issue = data.get("issue")
        ref.pages = data.get("pages")
        ref.publisher = data.get("publisher")

        # Authors / creators
        creators = data.get("creators", [])
        for c in creators:
            if isinstance(c, dict):
                name = c.get("name") or f"{c.get('lastName', '')}, {c.get('firstName', '')}".strip(
                    ", "
                )
                if name:
                    ref.authors.append(name)

        return ref

    def item_to_bibentry(self, item: dict[str, Any], citation_key: str | None = None) -> BibEntry:
        """Convert a Zotero item dict to a ``BibEntry``."""
        ref = self.item_to_reference(item)
        return ref.to_bib_entry(citation_key=citation_key)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_paper(
        self,
        doi: str | None = None,
        title: str | None = None,
        arxiv_id: str | None = None,
        collection_key: str | None = None,
    ) -> dict[str, Any] | None:
        """Add a paper to the Zotero library.

        Parameters
        ----------
        doi : str, optional
            DOI of the paper.
        title : str, optional
            Title (used if DOI not provided).
        arxiv_id : str, optional
            arXiv ID.
        collection_key : str, optional
            Collection key to add the item to.

        Returns
        -------
        dict or None
            Created item dict, or None if failed.
        """
        if self._local:
            logger.warning("Cannot write to local Zotero API (read-only)")
            return None

        # Resolve metadata
        from pyeuropepmc.features.bibliography.reference import ReferenceResolver

        resolver = ReferenceResolver()
        ref = None
        if doi:
            ref = resolver.resolve_doi(doi)
        elif arxiv_id:
            ref = resolver.resolve_arxiv(arxiv_id)
        elif title:
            matches = resolver.search_by_title(title, limit=1)
            ref = matches[0] if matches else None

        if not ref:
            logger.warning("Could not resolve metadata for paper")
            return None

        # Build Zotero item template
        zotero_item = self._build_item_template(ref)

        try:
            response = self._client.create_items([zotero_item])  # type: ignore[arg-type]
            items_created = response.get("successful", {}) if isinstance(response, dict) else {}
            if items_created and collection_key:
                first_key = (
                    list(items_created.values())[0] if isinstance(items_created, dict) else None
                )
                if first_key:
                    self._client.add_to_collection(collection_key, first_key)  # type: ignore[arg-type]
            return response  # type: ignore[no-any-return]
        except Exception as exc:
            logger.error("Failed to add paper to Zotero: %s", exc)
            return None

    def _build_item_template(self, ref: Reference) -> dict[str, Any]:
        """Build a Zotero API item template from a Reference."""
        item_type = self._bibtex_to_zotero_type(ref.entry_type)
        creators = []
        for author in ref.authors:
            parts = author.split(", ", 1)
            if len(parts) == 2:
                creators.append(
                    {"creatorType": "author", "lastName": parts[0], "firstName": parts[1]}
                )
            else:
                creators.append({"creatorType": "author", "name": author})

        template: dict[str, Any] = {
            "itemType": item_type,
            "title": ref.title or "",
            "creators": creators,
            "abstractNote": ref.abstract or "",
            "publicationTitle": ref.journal or "",
            "volume": ref.volume or "",
            "issue": ref.issue or "",
            "pages": ref.pages or "",
            "date": str(ref.year) if ref.year else "",
            "DOI": ref.doi or "",
            "url": ref.url or "",
            "ISBN": ref.isbn or "",
            "extra": f"PMID: {ref.pmid}" if ref.pmid else "",
        }
        return template

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pmid(data: dict[str, Any]) -> str | None:
        """Extract PMID from Zotero item's extra field or URL."""
        extra = data.get("extra", "")
        if "PMID:" in extra:
            for line in extra.split("\n"):
                if line.startswith("PMID:"):
                    return line.split(":", 1)[1].strip()
        return None

    @staticmethod
    def _extract_year(data: dict[str, Any]) -> int | None:
        """Extract year from Zotero's date field."""
        date_str = data.get("date", "")
        if not date_str:
            return None
        # Try first 4-digit number
        for token in date_str.replace("-", " ").split():
            try:
                val = int(token)
                if 1000 <= val <= 2099:
                    return val
            except ValueError:
                continue
        return None

    @staticmethod
    def _zotero_type_to_bibtex(ztype: str) -> str:
        mapping = {
            "journalArticle": "article",
            "conferencePaper": "inproceedings",
            "bookSection": "incollection",
            "book": "book",
            "thesis": "phdthesis",
            "report": "techreport",
            "computerProgram": "misc",
            "dataset": "misc",
            "preprint": "misc",
        }
        return mapping.get(ztype, "misc")

    @staticmethod
    def _bibtex_to_zotero_type(btype: str) -> str:
        mapping = {
            "article": "journalArticle",
            "inproceedings": "conferencePaper",
            "incollection": "bookSection",
            "book": "book",
            "phdthesis": "thesis",
            "techreport": "report",
            "misc": "document",
        }
        return mapping.get(btype, "document")
