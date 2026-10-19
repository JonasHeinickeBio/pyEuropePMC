"""Pure helpers for the batch lookup tools: classify identifiers, build one combined Europe
PMC query, match the unordered records back to the inputs, and project the fields asked for.

No I/O. Europe PMC answers an ``OR`` of identifier clauses with one record per match, in no
particular order, and silently omits identifiers it does not know. Everything an agent needs
to tell "not found" from "malformed" from "answered" therefore has to be reconstructed here.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from pyeuropepmc.mcp import _openaccess as oa

_PMCID_RE = re.compile(r"^PMC(\d{1,10})$", re.IGNORECASE)
_PMID_RE = re.compile(r"^\d{1,9}$")

#: Records per request. A 120-identifier query still answers in one call (checked live);
#: 50 keeps the URL short.
CHUNK_SIZE = 50

# Preference when one DOI names several records (a preprint and its published version).
_SOURCE_RANK = {"MED": 0, "PMC": 1}

#: Field name -> how to read it from a lite record, a core record, or either.
FIELDS = (
    "id",
    "source",
    "pmid",
    "pmcid",
    "doi",
    "title",
    "authors",
    "journal",
    "year",
    "cited_by",
    "is_open_access",
    "pub_types",
    "abstract",
)
DEFAULT_FIELDS = (
    "id",
    "source",
    "pmid",
    "pmcid",
    "doi",
    "title",
    "authors",
    "journal",
    "year",
    "cited_by",
    "is_open_access",
)


@dataclass(frozen=True)
class Entry:
    """One input identifier: what it was, what kind it is, and its normal form."""

    raw: str
    kind: str  # "pmid" | "pmcid" | "doi" | "invalid"
    value: str  # normalised; "" when invalid
    problem: str = ""


def classify(raw: str) -> Entry:
    """Decide what an identifier is. PMCIDs and DOIs are unambiguous; bare digits are a PMID."""
    text = str(raw).strip()
    if not text:
        return Entry(raw, "invalid", "", "empty identifier")
    match = _PMCID_RE.match(text)
    if match:
        return Entry(raw, "pmcid", f"PMC{match.group(1)}")
    doi = oa.clean_doi(text)
    if doi:
        if '"' in doi or "\\" in doi:
            return Entry(raw, "invalid", "", "DOI contains a quote or backslash")
        return Entry(raw, "doi", doi)
    if _PMID_RE.match(text):
        return Entry(raw, "pmid", text)
    return Entry(raw, "invalid", "", "not a PMID, PMCID or DOI")


def clause(entry: Entry) -> str:
    """The query clause that finds the record behind a valid entry."""
    if entry.kind == "pmid":
        return f"(EXT_ID:{entry.value} AND SRC:MED)"
    if entry.kind == "pmcid":
        return f"PMCID:{entry.value}"
    return f'DOI:"{entry.value}"'


def build_query(entries: list[Entry]) -> str:
    """One query for all distinct valid entries, in first-seen order."""
    seen: set[tuple[str, str]] = set()
    clauses = []
    for entry in entries:
        key = (entry.kind, entry.value.lower())
        if entry.kind == "invalid" or key in seen:
            continue
        seen.add(key)
        clauses.append(clause(entry))
    return " OR ".join(clauses)


def distinct_valid(entries: list[Entry]) -> list[Entry]:
    seen: set[tuple[str, str]] = set()
    out = []
    for entry in entries:
        key = (entry.kind, entry.value.lower())
        if entry.kind != "invalid" and key not in seen:
            seen.add(key)
            out.append(entry)
    return out


def chunks(entries: list[Entry], size: int = CHUNK_SIZE) -> list[list[Entry]]:
    unique = distinct_valid(entries)
    return [unique[i : i + size] for i in range(0, len(unique), size)]


def _rank(record: dict[str, Any]) -> int:
    return _SOURCE_RANK.get(str(record.get("source") or ""), 9)


def index_records(records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Index records by ``(kind, normalised id)``; the best-ranked record wins a collision."""
    index: dict[tuple[str, str], dict[str, Any]] = {}

    def put(key: tuple[str, str], record: dict[str, Any]) -> None:
        current = index.get(key)
        if current is None or _rank(record) < _rank(current):
            index[key] = record

    for record in records:
        if record.get("pmid"):
            put(("pmid", str(record["pmid"]).strip()), record)
        if record.get("pmcid"):
            put(("pmcid", str(record["pmcid"]).strip().upper()), record)
        if record.get("doi"):
            put(("doi", str(record["doi"]).strip().lower()), record)
    return index


def lookup(index: dict[tuple[str, str], dict[str, Any]], entry: Entry) -> dict[str, Any] | None:
    """The record for a valid entry, or ``None`` when Europe PMC did not return one."""
    if entry.kind == "invalid":
        return None
    value = entry.value.lower() if entry.kind == "doi" else entry.value.upper()
    if entry.kind == "pmid":
        value = entry.value
    return index.get((entry.kind, value))


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _journal(record: dict[str, Any]) -> str | None:
    title = record.get("journalTitle")
    if isinstance(title, str) and title:
        return title
    info = record.get("journalInfo")
    journal = info.get("journal") if isinstance(info, dict) else None
    value = journal.get("title") if isinstance(journal, dict) else None
    return value if isinstance(value, str) and value else None


def _pub_types(record: dict[str, Any]) -> list[str]:
    listed = record.get("pubTypeList")
    if isinstance(listed, dict) and isinstance(listed.get("pubType"), list):
        return [str(t) for t in listed["pubType"]]
    text = record.get("pubType")
    return [t.strip() for t in text.split(";") if t.strip()] if isinstance(text, str) else []


def project(record: dict[str, Any], fields: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """The requested fields in a stable, flat shape (lite and core records alike)."""
    readers: dict[str, Any] = {
        "id": lambda r: r.get("id"),
        "source": lambda r: r.get("source"),
        "pmid": lambda r: r.get("pmid") or None,
        "pmcid": lambda r: r.get("pmcid") or None,
        "doi": lambda r: r.get("doi") or None,
        "title": lambda r: r.get("title"),
        "authors": lambda r: r.get("authorString"),
        "journal": _journal,
        "year": lambda r: _to_int(r.get("pubYear")),
        "cited_by": lambda r: _to_int(r.get("citedByCount")),
        "is_open_access": lambda r: r.get("isOpenAccess") == "Y",
        "pub_types": _pub_types,
        "abstract": lambda r: r.get("abstractText"),
    }
    return {name: readers[name](record) for name in fields}


def validate_fields(fields: list[str] | None) -> tuple[str, ...]:
    """The fields to return; an unknown name is an error listing the valid ones."""
    if not fields:
        return DEFAULT_FIELDS
    unknown = [f for f in fields if f not in FIELDS]
    if unknown:
        raise ValueError(f"unknown field(s) {unknown}; valid fields: {list(FIELDS)}")
    return tuple(dict.fromkeys(fields))
