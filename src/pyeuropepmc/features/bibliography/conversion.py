"""
Citation format conversion.

Converts between BibTeX, RIS, and CSL-JSON formats.
This module does NOT require ``bibtexparser`` — it builds BibTeX/RIS strings
directly from the ``Reference`` and ``BibEntry`` models.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pyeuropepmc.features.bibliography.bibtex import BibtexManager, is_bibtex_content
from pyeuropepmc.features.bibliography.models import BibEntry, BibLibrary, CitationFormat, Reference

logger = logging.getLogger(__name__)

__all__ = ["CitationConverter"]


class CitationConverter:
    """
    Convert bibliographic references between citation formats.

    Supports BibTeX, RIS, and CSL-JSON. Can also auto-detect input format.
    """

    # ------------------------------------------------------------------
    # To BibTeX
    # ------------------------------------------------------------------

    def to_bibtex(self, source: Reference | BibEntry | BibLibrary, **kwargs: Any) -> str:
        """Convert a Reference, BibEntry, or BibLibrary to a BibTeX string.

        Parameters
        ----------
        source : Reference | BibEntry | BibLibrary
            The source object(s) to convert.

        Returns
        -------
        str
            BibTeX-formatted string.
        """
        if isinstance(source, BibLibrary):
            mgr = BibtexManager()
            return mgr.write_string(source, **kwargs)
        if isinstance(source, BibEntry):
            lib = BibLibrary(entries=[source])
            mgr = BibtexManager()
            return mgr.write_string(lib, **kwargs)
        if isinstance(source, Reference):
            entry = source.to_bib_entry()
            lib = BibLibrary(entries=[entry])
            mgr = BibtexManager()
            return mgr.write_string(lib, **kwargs)
        raise TypeError(f"Unexpected type: {type(source)}")

    # ------------------------------------------------------------------
    # To RIS
    # ------------------------------------------------------------------

    def to_ris(self, source: Reference | BibEntry) -> str:
        """Convert a Reference or BibEntry to RIS format.

        Parameters
        ----------
        source : Reference | BibEntry
            The source object to convert.

        Returns
        -------
        str
            RIS-formatted string.
        """
        lines: list[str] = ["TY  - JOUR"]

        if isinstance(source, BibEntry):
            return self._bibentry_to_ris(source)
        if isinstance(source, Reference):
            return self._reference_to_ris(source)
        raise TypeError(f"Unexpected type: {type(source)}")

    def _reference_to_ris(self, ref: Reference) -> str:
        lines: list[str] = []
        lines.append(self._ris_type_line(ref.entry_type))

        if ref.authors:
            for author in ref.authors:
                lines.append(f"AU  - {author}")
        if ref.title:
            lines.append(f"TI  - {ref.title}")
        if ref.year:
            lines.append(f"PY  - {ref.year}")
        if ref.journal:
            lines.append(f"JO  - {ref.journal}")
        if ref.volume:
            lines.append(f"VL  - {ref.volume}")
        if ref.issue:
            lines.append(f"IS  - {ref.issue}")
        if ref.pages:
            lines.append(f"SP  - {ref.pages}")
        if ref.doi:
            lines.append(f"DO  - {ref.doi}")
        if ref.pmid:
            lines.append(f"N1  - PMID: {ref.pmid}")
        if ref.abstract:
            lines.append(f"AB  - {ref.abstract}")
        if ref.url:
            lines.append(f"UR  - {ref.url}")
        if ref.isbn:
            lines.append(f"SN  - {ref.isbn}")

        lines.append("ER  - ")
        return "\n".join(lines)

    def _bibentry_to_ris(self, entry: BibEntry) -> str:
        ref = Reference(
            title=entry.fields.get("title", "").strip("{} "),
            authors=[
                a.strip()
                for a in entry.fields.get("author", "").strip("{} ").split(" and ")
                if a.strip()
            ],
            year=self._safe_int(entry.fields.get("year")),
            journal=entry.fields.get("journal", "").strip("{} "),
            volume=entry.fields.get("volume"),
            issue=entry.fields.get("number"),
            pages=entry.fields.get("pages"),
            doi=entry.fields.get("doi"),
            pmid=entry.fields.get("pmid"),
            abstract=entry.fields.get("abstract", "").strip("{} "),
            entry_type=entry.entry_type,
        )
        return self._reference_to_ris(ref)

    def _ris_type_line(self, entry_type: str) -> str:
        """Map BibTeX entry types to RIS type codes."""
        mapping = {
            "article": "TY  - JOUR",
            "inproceedings": "TY  - CONF",
            "incollection": "TY  - CHAP",
            "book": "TY  - BOOK",
            "phdthesis": "TY  - THES",
            "techreport": "TY  - RPRT",
            "misc": "TY  - GEN",
        }
        return mapping.get(entry_type, "TY  - JOUR")

    # ------------------------------------------------------------------
    # To CSL-JSON
    # ------------------------------------------------------------------

    def to_csl_json(self, source: Reference | BibEntry) -> dict[str, Any]:
        """Convert a Reference or BibEntry to CSL-JSON format.

        Parameters
        ----------
        source : Reference | BibEntry
            The source object to convert.

        Returns
        -------
        dict
            CSL-JSON item.
        """
        if isinstance(source, Reference):
            return self._reference_to_csl(source)
        if isinstance(source, BibEntry):
            ref = Reference(
                title=source.fields.get("title", "").strip("{} "),
                authors=[
                    a.strip()
                    for a in source.fields.get("author", "").strip("{} ").split(" and ")
                    if a.strip()
                ],
                year=self._safe_int(source.fields.get("year")),
                journal=source.fields.get("journal", "").strip("{} "),
                volume=source.fields.get("volume"),
                issue=source.fields.get("number"),
                pages=source.fields.get("pages"),
                doi=source.fields.get("doi"),
                pmid=source.fields.get("pmid"),
                url=source.fields.get("url"),
                entry_type=source.entry_type,
            )
            return self._reference_to_csl(ref)
        raise TypeError(f"Unexpected type: {type(source)}")

    def _reference_to_csl(self, ref: Reference) -> dict[str, Any]:
        csl: dict[str, Any] = {
            "type": self._csl_type(ref.entry_type),
        }
        if ref.title:
            csl["title"] = ref.title
        if ref.authors:
            csl["author"] = []
            for author in ref.authors:
                parts = author.split(", ", 1)
                if len(parts) == 2:
                    csl["author"].append({"family": parts[0], "given": parts[1]})
                else:
                    csl["author"].append({"literal": author})
        if ref.year:
            csl["issued"] = {"date-parts": [[ref.year]]}
        if ref.journal:
            csl["container-title"] = ref.journal
        if ref.volume:
            csl["volume"] = ref.volume
        if ref.issue:
            csl["issue"] = ref.issue
        if ref.pages:
            csl["page"] = ref.pages
        if ref.doi:
            csl["DOI"] = ref.doi
        if ref.pmid:
            csl["PMID"] = ref.pmid
        if ref.abstract:
            csl["abstract"] = ref.abstract
        if ref.url:
            csl["URL"] = ref.url
        if ref.isbn:
            csl["ISBN"] = ref.isbn
        if ref.publisher:
            csl["publisher"] = ref.publisher
        return csl

    # ------------------------------------------------------------------
    # From any format
    # ------------------------------------------------------------------

    def from_bibtex(self, text: str) -> BibLibrary:
        """Parse a BibTeX string into a BibLibrary."""
        mgr = BibtexManager()
        return mgr.parse_string(text)

    def from_ris(self, text: str) -> Reference:
        """Parse a basic RIS string into a Reference (best-effort)."""
        ref = Reference()
        for line in text.strip().split("\n"):
            line = line.strip()
            if len(line) < 6:
                continue
            tag = line[:2].strip()
            value = line[5:].strip() if len(line) > 5 else ""

            if tag == "TI":
                ref.title = value
            elif tag == "AU":
                ref.authors.append(value)
            elif tag == "PY":
                ref.year = self._safe_int(value)
            elif tag == "JO":
                ref.journal = value
            elif tag in ("VL", "VO"):
                ref.volume = value
            elif tag == "IS":
                ref.issue = value
            elif tag in ("SP", "BP"):
                if ref.pages:
                    ref.pages = f"{ref.pages}-{value}"
                else:
                    ref.pages = value
            elif tag == "DO":
                ref.doi = value
            elif tag == "AB":
                ref.abstract = value
            elif tag == "UR":
                ref.url = value
        return ref

    def from_csl_json(self, data: dict[str, Any]) -> Reference:
        """Parse a CSL-JSON dict into a Reference."""
        ref = Reference()
        ref.title = data.get("title")
        ref.doi = data.get("DOI")
        ref.pmid = data.get("PMID")
        ref.abstract = data.get("abstract")
        ref.url = data.get("URL")
        ref.isbn = data.get("ISBN")
        ref.publisher = data.get("publisher")
        ref.volume = data.get("volume")
        ref.issue = data.get("issue")
        ref.pages = data.get("page")
        ref.journal = data.get("container-title") or data.get("journal")
        ref.entry_type = self._csl_to_bibtex_type(data.get("type", "article"))

        # Date
        issued = data.get("issued", {})
        parts = issued.get("date-parts", [])
        if parts and len(parts[0]) > 0:
            ref.year = self._safe_int(parts[0][0])

        # Authors
        authors = data.get("author", [])
        for a in authors:
            if isinstance(a, dict):
                family = a.get("family", "")
                given = a.get("given", "")
                if family and given:
                    ref.authors.append(f"{family}, {given}")
                elif a.get("literal"):
                    ref.authors.append(a["literal"])

        return ref

    # ------------------------------------------------------------------
    # Auto-detect and convert
    # ------------------------------------------------------------------

    def detect_format(self, text: str) -> str:
        """Detect the citation format of a text string.

        Returns
        -------
        str
            One of ``CitationFormat`` values.
        """
        if is_bibtex_content(text):
            return CitationFormat.BIBTEX
        if text.strip().startswith("TY  -"):
            return CitationFormat.RIS
        try:
            data = json.loads(text)
            if isinstance(data, dict) and ("title" in data or "DOI" in data or "type" in data):
                return CitationFormat.CSL_JSON
        except (json.JSONDecodeError, ValueError):
            pass
        return CitationFormat.BIBTEX  # best guess

    def convert(
        self,
        source_text: str,
        target_format: str,
        input_format: str | None = None,
    ) -> str:
        """Auto-detect input format and convert to target format.

        Parameters
        ----------
        source_text : str
            The citation text to convert.
        target_format : str
            One of ``CitationFormat`` (e.g. ``"bibtex"``, ``"ris"``, ``"csl-json"``).
        input_format : str, optional
            If provided, skips auto-detection.

        Returns
        -------
        str
            Converted citation string.
        """
        fmt = input_format or self.detect_format(source_text)

        # Parse to intermediate representation
        if fmt == CitationFormat.BIBTEX:
            lib = self.from_bibtex(source_text)
            if not lib.entries:
                return ""
            entry = lib.entries[0]
        elif fmt == CitationFormat.RIS:
            entry = self.from_ris(source_text)
        elif fmt == CitationFormat.CSL_JSON:
            data = json.loads(source_text)
            entry = self.from_csl_json(data)
        else:
            raise ValueError(f"Unknown input format: {fmt}")

        # Convert to target
        if target_format == CitationFormat.BIBTEX:
            return self.to_bibtex(entry)
        elif target_format == CitationFormat.RIS:
            return self.to_ris(entry)
        elif target_format == CitationFormat.CSL_JSON:
            return json.dumps(self.to_csl_json(entry), indent=2)
        else:
            raise ValueError(f"Unknown target format: {target_format}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _csl_type(bibtex_type: str) -> str:
        """Map BibTeX types to CSL types."""
        mapping = {
            "article": "article-journal",
            "inproceedings": "paper-conference",
            "incollection": "chapter",
            "book": "book",
            "phdthesis": "thesis",
            "techreport": "report",
            "misc": "document",
        }
        return mapping.get(bibtex_type, "article-journal")

    @staticmethod
    def _csl_to_bibtex_type(csl_type: str) -> str:
        """Map CSL types to BibTeX types."""
        mapping = {
            "article-journal": "article",
            "paper-conference": "inproceedings",
            "chapter": "incollection",
            "book": "book",
            "thesis": "phdthesis",
            "report": "techreport",
            "document": "misc",
        }
        return mapping.get(csl_type, "misc")

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
