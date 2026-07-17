"""
Typed data models for bibliographic reference management.

Provides structured dataclasses for BibTeX entries, resolved references,
Zotero items, and format specifications used throughout the bibliography module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CitationFormat(str, Enum):
    """Supported citation output formats."""

    BIBTEX = "bibtex"
    RIS = "ris"
    CSL_JSON = "csl-json"


class VerificationStatus(str, Enum):
    """Result of a citation verification check."""

    VERIFIED = "verified"
    PARTIAL_MATCH = "partial_match"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class BibField:
    """A single BibTeX field (key-value pair)."""

    key: str
    value: str
    start_line: int | None = None


@dataclass
class BibEntry:
    r"""A single BibTeX entry (e.g. ``\@article{key, ...}``)."""

    entry_type: str  # e.g. "article", "inproceedings", "book"
    citation_key: str  # e.g. "smith2024ml"
    fields: dict[str, str] = field(default_factory=dict)
    raw: str | None = None
    start_line: int | None = None
    tags: list[str] = field(default_factory=list)
    source: str | None = None  # e.g. "crossref", "manual"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for agentic tool I/O."""
        return {
            "entry_type": self.entry_type,
            "citation_key": self.citation_key,
            "fields": dict(self.fields),
            "tags": list(self.tags),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BibEntry:
        """Create from a plain dict."""
        return cls(
            entry_type=data["entry_type"],
            citation_key=data["citation_key"],
            fields=data.get("fields", {}),
            tags=data.get("tags", []),
            source=data.get("source"),
        )


@dataclass
class BibLibrary:
    """A collection of BibTeX entries, representing a ``.bib`` file."""

    entries: list[BibEntry] = field(default_factory=list)
    file_path: str | None = None
    preamble: str | None = None
    strings: dict[str, str] = field(default_factory=dict)
    comments: list[str] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, key: str) -> BibEntry | None:
        """Look up an entry by citation key."""
        for e in self.entries:
            if e.citation_key == key:
                return e
        return None

    def add(self, entry: BibEntry) -> None:
        """Add an entry, avoiding duplicate citation keys."""
        existing = self[entry.citation_key]
        if existing:
            # Replace that entry
            idx = self.entries.index(existing)
            self.entries[idx] = entry
        else:
            self.entries.append(entry)

    def remove(self, citation_key: str) -> bool:
        """Remove an entry by citation key. Returns True if found."""
        entry = self[citation_key]
        if entry:
            self.entries.remove(entry)
            return True
        return False

    def filter(self, entry_type: str | None = None, **field_filters: str) -> list[BibEntry]:
        """Filter entries by type and/or field values."""
        results = list(self.entries)
        if entry_type:
            results = [e for e in results if e.entry_type == entry_type]
        for field_key, field_val in field_filters.items():
            results = [e for e in results if e.fields.get(field_key) == field_val]
        return results

    def to_dict(self) -> list[dict[str, Any]]:
        """Serialize all entries to plain dicts."""
        return [e.to_dict() for e in self.entries]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> BibLibrary:
        """Create from a list of entry dicts."""
        return cls(entries=[BibEntry.from_dict(d) for d in data])


@dataclass
class Reference:
    """A resolved bibliographic reference from any source."""

    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    url: str | None = None
    abstract: str | None = None
    entry_type: str = "article"
    source: str | None = None  # which API provided the data
    extra: dict[str, Any] = field(default_factory=dict)

    def to_bib_entry(self, citation_key: str | None = None) -> BibEntry:
        """Convert to a BibEntry for export."""
        key = citation_key or self._generate_key()
        fields: dict[str, str] = {}
        if self.title:
            fields["title"] = f"{{{self.title}}}"
        if self.authors:
            fields["author"] = f"{{{' and '.join(self.authors)}}}"
        if self.year:
            fields["year"] = str(self.year)
        if self.journal:
            fields["journal"] = f"{{{self.journal}}}"
        if self.volume:
            fields["volume"] = self.volume
        if self.issue:
            fields["number"] = self.issue
        if self.pages:
            fields["pages"] = self.pages
        if self.doi:
            fields["doi"] = self.doi
        if self.pmid:
            fields["pmid"] = self.pmid
        if self.publisher:
            fields["publisher"] = f"{{{self.publisher}}}"
        if self.url:
            fields["url"] = self.url
        if self.abstract:
            fields["abstract"] = f"{{{self.abstract}}}"

        return BibEntry(
            entry_type=self.entry_type,
            citation_key=key,
            fields=fields,
            source=self.source,
        )

    def _generate_key(self) -> str:
        """Generate a citation key from first author + year + first significant word."""
        last_name = "unknown"
        if self.authors:
            first = self.authors[0].strip()
            # Extract last name (part after last space)
            parts = first.split()
            if parts:
                last_name = parts[-1].lower().replace(",", "")
        year_str = str(self.year) if self.year else "n.d."
        # Get first word of title
        title_word = ""
        if self.title:
            words = self.title.split()
            if words:
                title_word = words[0].lower().replace("{", "").replace("}", "")
        return f"{last_name}{year_str}{title_word[:15]}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "journal": self.journal,
            "doi": self.doi,
            "pmid": self.pmid,
            "pmcid": self.pmcid,
            "arxiv_id": self.arxiv_id,
            "entry_type": self.entry_type,
            "source": self.source,
        }


@dataclass
class VerificationResult:
    """Result of verifying a citation against authoritative sources."""

    status: VerificationStatus
    query: str
    confidence: float = 0.0  # 0.0 - 1.0
    original_reference: str = ""
    matched_reference: Reference | None = None
    corrected_bibtex: str | None = None
    sources_checked: list[str] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "status": self.status.value,
            "query": self.query,
            "confidence": self.confidence,
            "matched": self.matched_reference is not None,
            "sources_checked": list(self.sources_checked),
            "error": self.error_message,
        }
