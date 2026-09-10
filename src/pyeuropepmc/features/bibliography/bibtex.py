"""
BibTeX file parsing, writing, validation, and merging.

Provides the ``BibtexManager`` class which wraps the ``bibtexparser`` library
(v2 beta) with a stable API for agentic tools and pipeline steps.

Supports:
- Parsing ``.bib`` files and strings into structured ``BibLibrary``
- Writing ``BibLibrary`` back to formatted BibTeX strings/files
- Validation with field-completeness checks and error reporting
- Merging multiple libraries with DOI/key-based deduplication
- Enriching entries with metadata from DOI/PMID resolution
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

from pyeuropepmc.features.bibliography.models import BibEntry, BibLibrary

logger = logging.getLogger(__name__)

# Try importing bibtexparser v2 (preferred) or v1 (fallback)
_BIBTEXPARSER_V2 = False
_BIBTEXPARSER_V1 = False
try:
    import bibtexparser as _bpt_ver

    _ver = tuple(int(x) for x in _bpt_ver.__version__.split(".")[:2])
    _BIBTEXPARSER_V2 = _ver >= (2, 0)
    _BIBTEXPARSER_V1 = not _BIBTEXPARSER_V2
except ImportError:
    pass

__all__ = ["BibtexManager", "BIBTEXPARSER_AVAILABLE"]


BIBTEXPARSER_AVAILABLE = _BIBTEXPARSER_V2 or _BIBTEXPARSER_V1


class BibtexManager:
    """
    High-level manager for BibTeX file operations.

    Wraps ``bibtexparser`` with a simpler API tailored to the agentic framework.

    Parameters
    ----------
    prefer_v2 : bool
        If True (default), try to use bibtexparser v2. Fall back to v1 if v2
        is not installed.

    Examples
    --------
    >>> mgr = BibtexManager()
    >>> lib = mgr.parse_string('@article{key, title = {Hello}}')
    >>> len(lib)
    1
    >>> lib["key"].fields["title"]
    '{Hello}'
    """

    def __init__(self, prefer_v2: bool = True) -> None:
        self._bpt: Any = None
        self._use_v2 = prefer_v2 and _BIBTEXPARSER_V2
        if self._use_v2:
            import bibtexparser as _bpt

            self._bpt = _bpt
            self._parse = self._parse_v2
            self._write = self._write_v2
        elif _BIBTEXPARSER_V1:
            import bibtexparser as _bpt

            self._bpt = _bpt
            self._parse = self._parse_v1
            self._write = self._write_v1
        else:
            logger.warning("bibtexparser not installed — BibTeX operations unavailable")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: str | Path) -> BibLibrary:
        """Parse a ``.bib`` file into a ``BibLibrary``."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        lib = self.parse_string(content)
        lib.file_path = str(path.resolve())
        return lib

    def parse_string(self, content: str) -> BibLibrary:
        """Parse a BibTeX-formatted string into a ``BibLibrary``."""
        return self._parse(content)

    def write_file(self, library: BibLibrary, path: str | Path, **kwargs: Any) -> Path:
        """Write a ``BibLibrary`` to a ``.bib`` file."""
        path = Path(path)
        content = self.write_string(library, **kwargs)
        path.write_text(content, encoding="utf-8")
        logger.info("Wrote %d entries to %s", len(library), path)
        return path

    def write_string(self, library: BibLibrary, **kwargs: Any) -> str:
        """Format a ``BibLibrary`` as a BibTeX string."""
        return self._write(library, **kwargs)

    def validate(self, library: BibLibrary) -> list[dict[str, Any]]:
        """Validate entries and return a list of issues.

        Checks performed:
        - Missing required fields (title, author, year)
        - Duplicate citation keys
        - Unusual field values (empty braces, suspicious patterns)

        Returns
        -------
        list[dict]
            Each dict has keys: ``severity`` (warning/error), ``message``,
            ``entry_key``.
        """
        issues: list[dict[str, Any]] = []
        seen_keys: dict[str, int] = {}

        for entry in library.entries:
            # --- Duplicate keys ---
            seen_keys[entry.citation_key] = seen_keys.get(entry.citation_key, 0) + 1

            # --- Required fields ---
            if not entry.fields.get("title"):
                issues.append(
                    {
                        "severity": "warning",
                        "message": "Missing title",
                        "entry_key": entry.citation_key,
                    }
                )
            if not entry.fields.get("author"):
                issues.append(
                    {
                        "severity": "warning",
                        "message": "Missing author",
                        "entry_key": entry.citation_key,
                    }
                )
            if not entry.fields.get("year"):
                issues.append(
                    {
                        "severity": "warning",
                        "message": "Missing year",
                        "entry_key": entry.citation_key,
                    }
                )

            # --- Suspicious values ---
            for fk, fv in entry.fields.items():
                if fv.strip() in ("{}", ""):
                    issues.append(
                        {
                            "severity": "warning",
                            "message": f"Field '{fk}' is empty",
                            "entry_key": entry.citation_key,
                        }
                    )
                if len(fv) > 2000:
                    issues.append(
                        {
                            "severity": "info",
                            "message": f"Field '{fk}' is very long ({len(fv)} chars)",
                            "entry_key": entry.citation_key,
                        }
                    )

        # Report duplicates
        for key, count in seen_keys.items():
            if count > 1:
                issues.append(
                    {
                        "severity": "error",
                        "message": f"Duplicate citation key: '{key}' ({count}x)",
                        "entry_key": key,
                    }
                )

        return issues

    def merge(self, libraries: list[BibLibrary], deduplicate_by: str = "doi") -> BibLibrary:
        """Merge multiple libraries into one, deduplicating entries.

        Parameters
        ----------
        libraries : list[BibLibrary]
            Libraries to merge.
        deduplicate_by : str
            Field to use for deduplication (``"doi"``, ``"citation_key"``).
            Defaults to ``"doi"``.

        Returns
        -------
        BibLibrary
            Merged library.
        """
        merged = BibLibrary()
        seen_doi: set[str] = set()
        seen_keys: set[str] = set()

        for lib in libraries:
            for entry in lib.entries:
                # Dedup by DOI
                doi = entry.fields.get("doi", "").strip().lower()
                if deduplicate_by == "doi" and doi and doi in seen_doi:
                    continue
                if entry.citation_key in seen_keys:
                    continue

                if doi:
                    seen_doi.add(doi)
                seen_keys.add(entry.citation_key)
                merged.add(entry)

        return merged

    def enrich_entries(self, library: BibLibrary, resolve_doi: bool = True) -> BibLibrary:
        """Enrich library entries by resolving DOIs via CrossRef.

        This is a lightweight enrichment that fills in missing fields
        from resolved metadata. For full enrichment, use the
        ``ReferenceResolver`` in ``pyeuropepmc.features.bibliography.reference``.

        Parameters
        ----------
        library : BibLibrary
            Library to enrich.
        resolve_doi : bool
            Whether to resolve DOIs to fill in missing fields.

        Returns
        -------
        BibLibrary
            New library with enriched entries (original unchanged).
        """
        if not resolve_doi:
            return library

        from pyeuropepmc.features.bibliography.reference import ReferenceResolver

        resolver = ReferenceResolver()
        enriched = BibLibrary(file_path=library.file_path)

        for entry in library.entries:
            doi = entry.fields.get("doi", "").strip("{} ")
            if doi and (not entry.fields.get("title") or not entry.fields.get("author")):
                try:
                    ref = resolver.resolve_doi(doi)
                    if ref and ref.title:
                        # Merge fields, preferring existing values
                        existing = entry.fields
                        bib_entry = ref.to_bib_entry(citation_key=entry.citation_key)
                        bib_entry.fields = {**bib_entry.fields, **existing}
                        bib_entry.tags = entry.tags
                        enriched.add(bib_entry)
                        continue
                except Exception:
                    logger.debug("Could not enrich DOI %s", doi, exc_info=True)
            enriched.add(entry)

        return enriched

    # ------------------------------------------------------------------
    # Internal parsers
    # ------------------------------------------------------------------

    def _parse_v1(self, content: str) -> BibLibrary:
        """Parse using bibtexparser v1."""
        db = self._bpt.loads(content)
        lib = BibLibrary()
        for entry in db.entries:
            fields = {k: str(v) for k, v in entry.items() if k not in ("ID", "ENTRYTYPE")}
            be = BibEntry(
                entry_type=entry.get("ENTRYTYPE", "misc"),
                citation_key=entry.get("ID", "unknown"),
                fields=fields,
            )
            lib.entries.append(be)
        return lib

    def _parse_v2(self, content: str) -> BibLibrary:
        """Parse using bibtexparser v2."""
        lib_parsed = self._bpt.parse_string(content)
        lib = BibLibrary()

        # Collect parse errors
        for block in lib_parsed.blocks:
            if isinstance(block, self._bpt.model.ParsingFailedBlock):
                lib.parse_errors.append(
                    str(block.error) if hasattr(block, "error") else "Parse error"
                )

        for entry in lib_parsed.entries:
            fields = {f.key: f.value for f in entry.fields}
            be = BibEntry(
                entry_type=entry.entry_type,
                citation_key=entry.key,
                fields=fields,
                start_line=entry.start_line,
            )
            lib.entries.append(be)

        # Collect preamble and strings from v2
        if hasattr(lib_parsed, "preamble") and lib_parsed.preamble:
            lib.preamble = str(lib_parsed.preamble)
        if hasattr(lib_parsed, "strings"):
            lib.strings = {s.key: s.value for s in lib_parsed.strings}

        return lib

    def _write_v1(self, library: BibLibrary, **kwargs: Any) -> str:
        """Write using bibtexparser v1."""
        from bibtexparser.bibdatabase import BibDatabase

        db = BibDatabase()
        db.entries = []
        for entry in library.entries:
            d = dict(entry.fields)
            d["ID"] = entry.citation_key
            d["ENTRYTYPE"] = entry.entry_type
            db.entries.append(d)
        out: str = self._bpt.dumps(db)
        return out

    def _write_v2(self, library: BibLibrary, **kwargs: Any) -> str:
        """Write using bibtexparser v2."""
        from bibtexparser.model import Entry, Field

        entries = []
        for entry in library.entries:
            fields = [Field(k, v) for k, v in entry.fields.items()]
            entries.append(Entry(entry.entry_type, entry.citation_key, fields))

        lib = self._bpt.Library(entries)
        out: str = self._bpt.write_string(lib)
        return out


# ------------------------------------------------------------------
# Standalone helper for simple BibTeX detection
# ------------------------------------------------------------------

_BIBTEX_RE = re.compile(r"^\s*@\w+\s*\{", re.MULTILINE)


def is_bibtex_content(text: str) -> bool:
    """Quick heuristic check if a string looks like BibTeX.

    Returns True if the text contains a ``@entrytype{...}`` pattern.
    """
    return bool(_BIBTEX_RE.search(text))
