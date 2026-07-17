"""
Reference resolution service.

Resolves DOIs, PMIDs, arXiv IDs, and ISBNs to full bibliographic references
by leveraging the existing ``enrichment/`` clients (CrossRef, Semantic Scholar)
and the Europe PMC search client.

This module does NOT require ``bibtexparser`` or ``pyzotero`` — it only depends
on existing pyEuropePMC components.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pyeuropepmc.features.bibliography.models import Reference

logger = logging.getLogger(__name__)

__all__ = ["ReferenceResolver", "IdentifierType", "detect_identifier_type"]


class IdentifierType:
    """Constants for identifier type detection."""

    DOI = "doi"
    PMID = "pmid"
    PMCID = "pmcid"
    ARXIV = "arxiv"
    ISBN = "isbn"
    UNKNOWN = "unknown"


# Patterns for identifier detection
_DOI_PATTERN = re.compile(r"10\.\d{4,}/[-._;()/:a-zA-Z0-9]+")
_PMID_PATTERN = re.compile(r"^\d{1,8}$")
_PMCID_PATTERN = re.compile(r"^PMC\d+$", re.IGNORECASE)
_ARXIV_PATTERN = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE)
_ISBN_PATTERN = re.compile(r"^(?:978|979)?\d{10}(\d{3})?$")


def detect_identifier_type(text: str) -> str:
    """Detect the type of identifier from a text string.

    Parameters
    ----------
    text : str
        The identifier string (e.g. ``"10.1038/nature14539"``).

    Returns
    -------
    str
        One of ``IdentifierType`` constants.
    """
    text = text.strip()
    if _DOI_PATTERN.match(text):
        return IdentifierType.DOI
    if text.upper().startswith("PMC") and _PMCID_PATTERN.match(text):
        return IdentifierType.PMCID
    if text.startswith("arXiv:") or _ARXIV_PATTERN.match(text):
        return IdentifierType.ARXIV
    if _ISBN_PATTERN.match(text.replace("-", "")):
        return IdentifierType.ISBN
    if _PMID_PATTERN.match(text):
        return IdentifierType.PMID
    return IdentifierType.UNKNOWN


class ReferenceResolver:
    """
    Resolve bibliographic identifiers to structured ``Reference`` objects.

    Uses existing pyEuropePMC enrichment clients (CrossRef, Semantic Scholar)
    and the Europe PMC search API.

    Parameters
    ----------
    crossref_email : str, optional
        Email for CrossRef polite pool (better rate limits).
    """

    def __init__(self, crossref_email: str | None = None) -> None:
        self._crossref_email = crossref_email
        self._crossref_client: Any = None
        self._search_client: Any = None

    # ------------------------------------------------------------------
    # Identifier resolution
    # ------------------------------------------------------------------

    def resolve(self, identifier: str) -> Reference | None:
        """Auto-detect identifier type and resolve it.

        Parameters
        ----------
        identifier : str
            DOI, PMID, PMCID, arXiv ID, or ISBN.

        Returns
        -------
        Reference or None
        """
        id_type = detect_identifier_type(identifier)
        method = {
            IdentifierType.DOI: self.resolve_doi,
            IdentifierType.PMID: self.resolve_pmid,
            IdentifierType.PMCID: self.resolve_pmcid,
            IdentifierType.ARXIV: self.resolve_arxiv,
            IdentifierType.ISBN: self.resolve_isbn,
        }.get(id_type)

        if method is None:
            logger.warning("Unknown identifier type: %s", identifier)
            return None

        try:
            return method(identifier)
        except Exception as exc:
            logger.error("Failed to resolve %s (%s): %s", identifier, id_type, exc)
            return None

    def resolve_doi(self, doi: str) -> Reference | None:
        """Resolve a DOI to a full Reference via CrossRef."""
        doi = doi.strip().lower()
        if doi.startswith("doi:"):
            doi = doi[4:]
        try:
            ref = self._resolve_via_crossref(doi)
            if ref:
                return ref
        except Exception:
            logger.debug("CrossRef DOI resolution failed for %s", doi, exc_info=True)

        # Fallback: try Europe PMC search
        return self._resolve_via_pmc(f'DOI:"{doi}"')

    def resolve_pmid(self, pmid: str) -> Reference | None:
        """Resolve a PubMed ID to a full Reference."""
        pmid = pmid.strip()
        return self._resolve_via_pmc(f"EXT_ID:{pmid} AND SRC:MED")

    def resolve_pmcid(self, pmcid: str) -> Reference | None:
        """Resolve a PubMed Central ID to a full Reference."""
        pmcid = pmcid.strip().upper()
        if not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"
        return self._resolve_via_pmc(f"PMCID:{pmcid}")

    def resolve_arxiv(self, arxiv_id: str) -> Reference | None:
        """Resolve an arXiv ID to a Reference."""
        arxiv_id = arxiv_id.strip()
        if arxiv_id.startswith("arXiv:"):
            arxiv_id = arxiv_id[6:]
        # Try Europe PMC first (may have arXiv papers)
        ref = self._resolve_via_pmc(f"{arxiv_id}")
        if ref:
            return ref
        # Fallback: try CrossRef with arXiv DOI
        return self.resolve_doi(f"10.48550/arXiv.{arxiv_id}")

    def resolve_isbn(self, isbn: str) -> Reference | None:
        """Resolve an ISBN to a Reference (book metadata).

        Note
        ----
        Currently a best-effort lookup. Falls back to Europe PMC which
        has limited book coverage.
        """
        isbn_clean = isbn.strip().replace("-", "")
        return self._resolve_via_pmc(isbn_clean)

    # ------------------------------------------------------------------
    # Search by title / author
    # ------------------------------------------------------------------

    def search_by_title(
        self, title: str, limit: int = 5, source: str = "crossref"
    ) -> list[Reference]:
        """Search for references by title or partial citation.

        Parameters
        ----------
        title : str
            Paper title or partial citation text.
        limit : int
            Maximum results (default: 5).
        source : str
            Source to search (``"crossref"`` or ``"pmc"``).

        Returns
        -------
        list[Reference]
            Matched references.
        """
        if source == "crossref":
            return self._search_crossref(title, limit=limit)
        return self._search_pmc(title, limit=limit)

    def resolve_many(self, identifiers: list[str]) -> list[Reference]:
        """Resolve multiple identifiers in batch.

        Parameters
        ----------
        identifiers : list[str]
            List of DOIs, PMIDs, etc.

        Returns
        -------
        list[Reference]
            Resolved references (unresolvable ones are skipped).
        """
        results: list[Reference] = []
        for ident in identifiers:
            ref = self.resolve(ident)
            if ref:
                results.append(ref)
        return results

    # ------------------------------------------------------------------
    # Internal — CrossRef
    # ------------------------------------------------------------------

    def _get_crossref_client(self):
        """Lazy-init the CrossRef enrichment client."""
        if self._crossref_client is None:
            from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient

            self._crossref_client = CrossRefClient(email=self._crossref_email)
        return self._crossref_client

    def _resolve_via_crossref(self, doi: str) -> Reference | None:
        """Resolve DOI via CrossRef client."""
        client = self._get_crossref_client()
        data = client.enrich(doi=doi)
        if not data:
            return None

        ref = Reference(source="crossref")
        ref.doi = doi
        ref.title = self._clean_str(data.get("title"))
        ref.year = self._extract_year(data)
        ref.journal = self._clean_str(data.get("journal"))
        ref.volume = self._clean_str(data.get("volume"))
        ref.issue = self._clean_str(data.get("issue"))
        ref.pages = self._clean_str(data.get("pages"))
        ref.publisher = self._clean_str(data.get("publisher"))

        authors = data.get("authors", [])
        if isinstance(authors, list):
            ref.authors = [
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                if isinstance(a, dict)
                else str(a)
                for a in authors
            ]

        ref.abstract = self._clean_str(data.get("abstract"))
        ref.url = data.get("url")

        # Determine entry type
        ctype = data.get("type", "")
        ref.entry_type = self._crossref_type_to_bibtex(ctype)

        return ref

    def _search_crossref(self, query: str, limit: int = 5) -> list[Reference]:
        """Search CrossRef by title/author."""
        client = self._get_crossref_client()
        results = client.search(query, rows=limit)
        refs: list[Reference] = []

        items = (
            results
            if isinstance(results, list)
            else results.get("message", {}).get("items", [])
            if isinstance(results, dict)
            else []
        )
        for item in items[:limit]:
            doi = item.get("DOI", "") if isinstance(item, dict) else ""
            if doi:
                ref = self.resolve_doi(doi)
                if ref:
                    refs.append(ref)

        return refs

    # ------------------------------------------------------------------
    # Internal — Europe PMC
    # ------------------------------------------------------------------

    def _get_search_client(self):
        """Lazy-init the Europe PMC search client."""
        if self._search_client is None:
            from pyeuropepmc import SearchClient

            self._search_client = SearchClient()
        return self._search_client

    def _resolve_via_pmc(self, query: str) -> Reference | None:
        """Resolve via Europe PMC search."""
        client = self._get_search_client()
        results = client.search(query, pageSize=1)
        papers = (
            results.get("results", [])
            if isinstance(results, dict)
            else list(results)[:1]
            if results
            else []
        )
        if not papers:
            return None

        paper = papers[0] if isinstance(papers, list) else papers
        if isinstance(paper, dict):
            ref = Reference(source="europe_pmc")
            ref.title = paper.get("title")
            ref.doi = paper.get("doi")
            ref.pmid = paper.get("pmid")
            ref.pmcid = paper.get("pmcid")
            ref.year = self._safe_int(paper.get("pubYear"))
            ref.journal = paper.get("journalTitle")
            ref.volume = paper.get("journalVolume")
            ref.issue = paper.get("journalIssue")
            ref.pages = paper.get("pageInfo")
            ref.authors = self._parse_author_string(paper.get("authorString", ""))
            ref.abstract = paper.get("abstractText")
            ref.url = paper.get("fullTextUrl")
            ref.entry_type = "article"
            return ref
        return None

    def _search_pmc(self, query: str, limit: int = 5) -> list[Reference]:
        """Search Europe PMC by title/author."""
        client = self._get_search_client()
        results = client.search(query, pageSize=limit)
        papers = (
            results.get("results", [])
            if isinstance(results, dict)
            else list(results)[:limit]
            if results
            else []
        )
        refs: list[Reference] = []
        for paper in papers:
            if isinstance(paper, dict):
                ref = Reference(source="europe_pmc")
                ref.title = paper.get("title")
                ref.doi = paper.get("doi")
                ref.pmid = paper.get("pmid")
                ref.pmcid = paper.get("pmcid")
                ref.year = self._safe_int(paper.get("pubYear"))
                ref.journal = paper.get("journalTitle")
                ref.authors = self._parse_author_string(paper.get("authorString", ""))
                refs.append(ref)
        return refs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_str(value: Any) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_year(data: dict[str, Any]) -> int | None:
        """Extract year from CrossRef date fields."""
        for key in ("published_print", "published_online", "issued", "created"):
            date = data.get(key, data.get(f"_{key}"))
            if isinstance(date, dict):
                parts = date.get("date-parts", [])
                if parts and len(parts[0]) > 0:
                    try:
                        return int(parts[0][0])
                    except (ValueError, IndexError):
                        pass
        return None

    @staticmethod
    def _parse_author_string(author_str: str) -> list[str]:
        """Parse a Europe PMC author string into a list of names."""
        if not author_str:
            return []
        return [a.strip() for a in author_str.split(",") if a.strip()]

    @staticmethod
    def _crossref_type_to_bibtex(ctype: str) -> str:
        """Map CrossRef types to BibTeX entry types."""
        mapping = {
            "journal-article": "article",
            "proceedings-article": "inproceedings",
            "book-chapter": "incollection",
            "book": "book",
            "edited-book": "book",
            "monograph": "book",
            "report": "techreport",
            "dissertation": "phdthesis",
            "dataset": "misc",
            "posted-content": "misc",
            "reference-book": "book",
            "peer-review": "article",
        }
        return mapping.get(ctype, "misc")
