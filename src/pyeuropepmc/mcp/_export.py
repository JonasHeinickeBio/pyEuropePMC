"""Turning Europe PMC records into BibTeX, RIS, CSL-JSON, CSV, JSON and Markdown (no I/O).

A record is first normalised into a :class:`Paper` (people split into family and given name,
page ranges into start and end, markup stripped from titles and abstracts, keywords listed);
every format is then written from that one structure.

BibTeX goes through ``BibtexManager`` so that the output reads back with ``bib_parse_string``.
RIS and CSL-JSON are written here instead of through ``CitationConverter``, because the
converter is built for round trips of BibTeX entries and loses what a Europe PMC record has:
it splits ``{GBD 2019 Diseases and Injuries Collaborators}`` into two authors at the "and" in
the name, emits ``others`` as an author, writes ``SP - 1204-1222`` without an ``EP`` line and
drops keywords, the PMCID and the month.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import html
import io
import json
import re
from typing import Any

from pyeuropepmc.mcp import _batch as bm

#: A BibTeX entry with more authors than this ends in ``and others``; RIS and CSL-JSON stop
#: at the limit. Consortium papers list thousands.
MAX_AUTHORS = 100

_BLOCK = re.compile(
    r"</?(?:p|h\d|br|li|ul|ol|div|sec|title|tr|td|th|table)\b[^>]*>", re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_PAGES = re.compile(r"^([A-Za-z]?\d+)\s*[-–—]+\s*([A-Za-z]?\d+)$")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "using",
        "via",
        "with",
    ]
)


@dataclass
class Person:
    family: str = ""
    given: str = ""
    literal: str = ""  # a collective author, e.g. a consortium

    @property
    def is_collective(self) -> bool:
        return bool(self.literal)

    def bibtex(self) -> str:
        if self.literal:
            return "{" + tex_escape(self.literal) + "}"
        family, given = tex_escape(self.family), tex_escape(self.given)
        return f"{family}, {given}" if given else family

    def ris(self) -> str:
        if self.literal:
            return self.literal
        return f"{self.family}, {self.given}" if self.given else self.family

    def csl(self) -> dict[str, str]:
        if self.literal:
            return {"literal": self.literal}
        out = {"family": self.family}
        if self.given:
            out["given"] = self.given
        return out


@dataclass
class Paper:
    """One record in the shape every writer reads."""

    key: str = ""
    source: str = ""
    id: str = ""
    kind: str = "article"  # article | misc | book
    title: str = ""
    authors: list[Person] = field(default_factory=list)
    journal: str = ""
    journal_short: str = ""
    year: int | None = None
    month: int | None = None
    volume: str = ""
    issue: str = ""
    pages: str = ""
    start_page: str = ""
    end_page: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    url: str = ""
    authors_omitted: int = 0


# --------------------------------------------------------------------------- normalising


def clean_text(value: Any) -> str:
    """Plain text: markup removed, entities decoded, whitespace collapsed."""
    if not isinstance(value, str):
        return ""
    # A structured abstract is <h4>Background</h4><p>In an era...</p>: removing the block tags
    # without a space would glue the heading to the text. Inline tags (<i>, <sub>) vanish.
    text = _TAG.sub("", _BLOCK.sub(" ", value))
    return _SPACE.sub(" ", html.unescape(text)).strip()


def identifier(value: Any) -> str:
    """A DOI, PMID or PMCID exactly as given, only trimmed. It must not go through
    ``clean_text``: old DOIs such as ``10.1002/(SICI)1097-0258(19980815/30)17:15/16<1661::AID-
    SIM968>3.0.CO;2-2`` contain ``<...>``, which would be read as markup and deleted."""
    return value.strip() if isinstance(value, str) else ""


def _strip_final_period(title: str) -> str:
    return title[:-1].rstrip() if title.endswith(".") and not title.endswith("..") else title


def _person(entry: dict[str, Any]) -> Person | None:
    collective = clean_text(entry.get("collectiveName"))
    if collective:
        return Person(literal=collective)
    family = clean_text(entry.get("lastName"))
    given = clean_text(entry.get("firstName") or entry.get("initials"))
    if not family:
        return _from_full_name(clean_text(entry.get("fullName")))
    return Person(family=family, given=given)


def _from_full_name(text: str) -> Person | None:
    """``"Vasiliou V"`` -> family ``Vasiliou``, given ``V``; a name without initials is literal."""
    text = text.rstrip(".").strip()
    if not text:
        return None
    head, _, tail = text.rpartition(" ")
    if head and re.fullmatch(r"[A-Z]{1,4}", tail):
        return Person(family=head, given=tail)
    return Person(literal=text)


def authors_of(record: dict[str, Any]) -> list[Person]:
    """The people behind a record: the structured list if there is one, else ``authorString``."""
    listed = (record.get("authorList") or {}).get("author")
    if isinstance(listed, list):
        people = [p for p in (_person(a) for a in listed if isinstance(a, dict)) if p]
        if people:
            return people
    text = clean_text(record.get("authorString"))
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return [p for p in (_from_full_name(part) for part in parts) if p]


def split_pages(pages: str) -> tuple[str, str]:
    """``"138-143"`` -> ``("138", "143")``; ``"138-43"`` (NLM style) -> ``("138", "143")``;
    an article number such as ``"e12345"`` is only a start."""
    match = _PAGES.match(pages.strip())
    if not match:
        return pages.strip(), ""
    start, end = match.groups()
    if start.isdigit() and end.isdigit() and len(end) < len(start):
        end = start[: len(start) - len(end)] + end
    return start, end


def _journal(record: dict[str, Any]) -> tuple[str, str]:
    info = record.get("journalInfo")
    journal = info.get("journal") if isinstance(info, dict) else None
    if isinstance(journal, dict):
        title = clean_text(journal.get("title"))
        short = clean_text(journal.get("medlineAbbreviation"))
        if title:
            return title, short
    return clean_text(record.get("journalTitle")), ""


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _kind(record: dict[str, Any], journal: str) -> str:
    if str(record.get("source")) == "PPR":
        return "misc"
    types = record.get("pubTypeList")
    names = types.get("pubType") if isinstance(types, dict) else None
    if isinstance(names, list) and any("book" in str(n).lower() for n in names) and not journal:
        return "book"
    return "article" if journal else "misc"


def to_paper(record: dict[str, Any]) -> Paper:
    """Normalise a lite or core Europe PMC record; the key is assigned later."""
    journal, short = _journal(record)
    raw_info = record.get("journalInfo")
    info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
    pages = clean_text(record.get("pageInfo"))
    start, end = split_pages(pages)
    people = authors_of(record)
    keywords = (record.get("keywordList") or {}).get("keyword")
    source, ident = str(record.get("source") or ""), str(record.get("id") or "")
    return Paper(
        source=source,
        id=ident,
        kind=_kind(record, journal),
        title=_strip_final_period(clean_text(record.get("title"))),
        authors=people[:MAX_AUTHORS],
        authors_omitted=max(len(people) - MAX_AUTHORS, 0),
        journal=journal,
        journal_short=short,
        year=_int(record.get("pubYear")) or _int(info.get("yearOfPublication")),
        month=_int(info.get("monthOfPublication")),
        volume=clean_text(record.get("journalVolume") or info.get("volume")),
        issue=clean_text(record.get("issue") or info.get("issue")),
        pages=f"{start}-{end}" if end else start,
        start_page=start,
        end_page=end,
        doi=identifier(record.get("doi")),
        pmid=identifier(record.get("pmid")),
        pmcid=identifier(record.get("pmcid")),
        abstract=clean_text(record.get("abstractText")),
        keywords=[k for k in (clean_text(x) for x in keywords or []) if k]
        if isinstance(keywords, list)
        else [],
        url=f"https://europepmc.org/article/{source}/{ident}" if source and ident else "",
    )


# --------------------------------------------------------------------------- keys


def _fold(text: str, *, digits: bool = False) -> str:
    """Lower-case ASCII, accents removed: a key must survive any editor."""
    import unicodedata

    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]" if digits else r"[^a-z]", "", folded.lower())


def key_base(paper: Paper) -> str:
    """``firstauthorYYYYword``: the first author's family name, the year, the first word of
    the title that is not a stopword. Anything missing is ``anon``, ``nd`` or left out."""
    first = paper.authors[0] if paper.authors else None
    name = (first.literal.split()[0] if first and first.literal else first.family) if first else ""
    author = _fold(name) or "anon"
    year = str(paper.year) if paper.year else "nd"
    words = (_fold(t, digits=True) for t in re.split(r"[\s\-/]+", paper.title))
    word = next((w for w in words if len(w) > 2 and not w.isdigit() and w not in _STOPWORDS), "")
    return f"{author}{year}{word}"


def _letters(n: int) -> str:
    """1 -> a, 2 -> b, ... 26 -> z, 27 -> aa."""
    out = ""
    while n:
        n, rest = divmod(n - 1, 26)
        out = chr(97 + rest) + out
    return out


def assign_keys(papers: list[Paper]) -> None:
    """Unique keys in input order. The first paper with a given base keeps it bare; the
    next ones get ``a``, ``b``, ... (``smith2020deep``, ``smith2020deepa``, ``smith2020deepb``).
    Keys are assigned before any export is cut to a size, so they do not depend on it."""
    used: set[str] = set()
    for paper in papers:
        base = key_base(paper)
        key, n = base, 0
        while key in used:
            n += 1
            key = f"{base}{_letters(n)}"
        used.add(key)
        paper.key = key


# --------------------------------------------------------------------------- BibTeX

_TEX = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    """Escape what LaTeX reads as syntax inside a BibTeX field. Applied to titles, names,
    journals and abstracts; not to ``doi`` and ``url``, where those characters are literal."""
    return "".join(_TEX.get(c, c) for c in text)


def bibtex_fields(paper: Paper) -> dict[str, str]:
    people = [p.bibtex() for p in paper.authors]
    if paper.authors_omitted:
        people.append("others")
    fields = {
        "author": " and ".join(people),
        "title": tex_escape(paper.title),
        "journal": tex_escape(paper.journal),
        "year": str(paper.year or ""),
        "volume": paper.volume,
        "number": paper.issue,
        "pages": paper.pages.replace("-", "--"),
        "doi": paper.doi,
        "pmid": paper.pmid,
        "pmcid": paper.pmcid,
        "url": paper.url,
        "keywords": tex_escape(", ".join(paper.keywords)),
        "abstract": tex_escape(paper.abstract),
    }
    return {k: v for k, v in fields.items() if v}


def bibtex_entry(paper: Paper) -> str:
    """One entry. ``BibtexManager`` writes a library sorted by key, which would lose the order
    the papers were asked for in, so each entry is written alone and joined in input order."""
    from pyeuropepmc.features.bibliography.bibtex import BibtexManager
    from pyeuropepmc.features.bibliography.models import BibEntry, BibLibrary

    entry = BibEntry(paper.kind, paper.key, bibtex_fields(paper))
    return str(BibtexManager().write_string(BibLibrary(entries=[entry]))).strip()


def to_bibtex(papers: list[Paper]) -> str:
    return "\n\n".join(bibtex_entry(p) for p in papers)


# --------------------------------------------------------------------------- RIS

_RIS_TYPE = {"article": "JOUR", "misc": "GEN", "book": "BOOK"}


def _ris_value(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def ris_entry(paper: Paper) -> str:
    lines = [f"TY  - {_RIS_TYPE.get(paper.kind, 'GEN')}"]

    def add(tag: str, value: str) -> None:
        if value:
            lines.append(f"{tag}  - {_ris_value(value)}")

    add("TI", paper.title)
    for person in paper.authors:
        add("AU", person.ris())
    add("JF", paper.journal)
    add("JO", paper.journal_short)
    if paper.year:
        add("PY", str(paper.year))
        if paper.month:
            add("DA", f"{paper.year}/{paper.month:02d}")
    add("VL", paper.volume)
    add("IS", paper.issue)
    add("SP", paper.start_page)
    add("EP", paper.end_page)
    add("DO", paper.doi)
    add("AN", paper.pmid)
    add("N1", f"PMCID: {paper.pmcid}" if paper.pmcid else "")
    add("AB", paper.abstract)
    for keyword in paper.keywords:
        add("KW", keyword)
    add("UR", paper.url)
    lines.append("ER  - ")
    return "\n".join(lines)


def to_ris(papers: list[Paper]) -> str:
    return "\n\n".join(ris_entry(p) for p in papers)


# --------------------------------------------------------------------------- CSL-JSON

_CSL_TYPE = {"article": "article-journal", "misc": "article", "book": "book"}


def csl_item(paper: Paper) -> dict[str, Any]:
    item: dict[str, Any] = {"id": paper.key, "type": _CSL_TYPE.get(paper.kind, "article")}
    if paper.title:
        item["title"] = paper.title
    if paper.authors:
        item["author"] = [p.csl() for p in paper.authors]
    if paper.year:
        parts = [paper.year, paper.month] if paper.month else [paper.year]
        item["issued"] = {"date-parts": [parts]}
    optional = {
        "container-title": paper.journal,
        "container-title-short": paper.journal_short,
        "volume": paper.volume,
        "issue": paper.issue,
        "page": paper.pages,
        "DOI": paper.doi,
        "PMID": paper.pmid,
        "PMCID": paper.pmcid,
        "URL": paper.url,
        "abstract": paper.abstract,
        "keyword": ", ".join(paper.keywords),
    }
    item.update({k: v for k, v in optional.items() if v})
    return item


def csl_text(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False)


# --------------------------------------------------------------------------- tables


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def csv_row(values: list[Any]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow([_cell(v) for v in values])
    return buffer.getvalue()


def markdown_row(values: list[Any]) -> str:
    cells = [_SPACE.sub(" ", _cell(v)).replace("|", "\\|") for v in values]
    return "| " + " | ".join(cells) + " |"


def markdown_header(fields: tuple[str, ...]) -> str:
    return markdown_row(list(fields)) + "\n|" + " --- |" * len(fields)


_TEXT_COLUMNS = ("title", "authors", "journal", "abstract")


def table_rows(records: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """The requested columns of each record. Text columns lose markup (a title can carry
    ``<i>`` or ``<sub>``, an abstract ``<h4>``); identifiers and numbers are left as they are."""
    rows = []
    for record in records:
        row = bm.project(record, fields)
        for column in _TEXT_COLUMNS:
            if column in row:
                row[column] = clean_text(row[column])
        rows.append(row)
    return rows
