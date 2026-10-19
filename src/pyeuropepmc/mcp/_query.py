"""Parsing, linting, translating and building Europe PMC queries, without any I/O.

Europe PMC does not reject a malformed query, it answers a different one. Checked live in
October 2026:

* an unclosed ``(`` or a stray ``)`` is ignored: ``malaria AND (dengue OR zika`` finds 7,226
  records where ``malaria AND dengue`` finds 26,733;
* a leading or trailing operator is dropped, so ``malaria AND`` is just ``malaria``;
* ``malaria AND dengue OR zika`` returns exactly the records of ``malaria``, and
  ``malaria OR dengue AND zika`` (27,913) matches neither ``a OR (b AND c)`` (312,530) nor
  ``(a OR b) AND c`` (30,156);
* an unknown field (``FOO:malaria``), a flag that is not ``y``/``n`` (``HAS_FT:true``) and a
  date range with a missing or reversed bound all give 0 records and no error;
* a bare leading wildcard (``*malaria``) gives HTTP 503.

An agent that writes such a query gets plausible numbers and no hint. ``lint`` reports each
of these, with its position, before the query is sent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import difflib
import re
from typing import Any

# Searchable fields of GET /europepmc/webservices/rest/fields (October 2026), plus three that
# the search accepts although the endpoint does not list them: AUTHOR, MESH and SUBSET.
KNOWN_FIELDS = frozenset(
    {
        "ABBR",
        "ABSTRACT",
        "ACCESSION_ID",
        "ACCESSION_TYPE",
        "ACK_FUND",
        "AFF",
        "ALL_FIELDS",
        "ANNOTATION_PROVIDER",
        "ANNOTATION_TYPE",
        "APPENDIX",
        "ARXPR_PUBS",
        "AUTH",
        "AUTHORID",
        "AUTHORID_TYPE",
        "AUTHOR_ROLES",
        "AUTH_COLLECTIVE_LIST",
        "AUTH_CON",
        "AUTH_FIRST",
        "AUTH_LAST",
        "AUTH_MAN",
        "AUTH_MAN_ID",
        "BACK",
        "BACK_NOREF",
        "BODY",
        "BOOK_ID",
        "CASE",
        "CHEBITERM",
        "CHEBITERM_ID",
        "CHEBI_PUBS",
        "CHEM",
        "CHEMBL_PUBS",
        "CITED",
        "CITES",
        "COMP_INT",
        "CONCL",
        "CREATION_DATE",
        "DATA_AVAILABILITY",
        "DISCUSS",
        "DISEASE",
        "DISEASE_ID",
        "DOI",
        "ED",
        "EMBARGO_DATE",
        "EMBL_PUBS",
        "EMBL_ROR_ID",
        "EPMC_AUTH_MAN",
        "ESSN",
        "EXPERIMENTAL_METHOD",
        "EXPERIMENTAL_METHOD_ID",
        "EXT_ID",
        "E_PDATE",
        "FIG",
        "FIRST_IDATE",
        "FIRST_IDATE_D",
        "FIRST_PDATE",
        "FT_CDATE",
        "FT_CDATE_D",
        "FT_ID",
        "FUNDER_INITIATIVE",
        "GENE_PROTEIN",
        "GOTERM",
        "GOTERM_ID",
        "GRANT_AGENCY",
        "GRANT_AGENCY_ID",
        "GRANT_ID",
        "HAS_ABSTRACT",
        "HAS_ARXPR",
        "HAS_BOOK",
        "HAS_CHEBI",
        "HAS_CHEMBL",
        "HAS_DATA",
        "HAS_DOI",
        "HAS_EMBL",
        "HAS_FREE_FULLTEXT",
        "HAS_FT",
        "HAS_FULLTEXT",
        "HAS_FULLTEXTDATA",
        "HAS_INTACT",
        "HAS_INTERPRO",
        "HAS_LABSLINKS",
        "HAS_OMIM",
        "HAS_PDB",
        "HAS_PDF",
        "HAS_PREPRINT",
        "HAS_PRIDE",
        "HAS_PUBLISHED_VERSION",
        "HAS_REFLIST",
        "HAS_SUPPL",
        "HAS_TM",
        "HAS_UNIPROT",
        "HAS_VERSION_EVALUATIONS",
        "HAS_XREFS",
        "INDEX_DATE",
        "INTACT_PUBS",
        "INTERPRO_PUBS",
        "INTRO",
        "INVESTIGATOR",
        "IN_EPMC",
        "IN_PMC",
        "ISBN",
        "ISSN",
        "ISSUE",
        "JOURNAL",
        "KEYWORD",
        "KW",
        "LABS_PUBS",
        "LANG",
        "LICENSE",
        "METHODS",
        "NIH_AUTH_MAN",
        "OMIM_PUBS",
        "OPEN_ACCESS",
        "ORGANISM",
        "ORGANISM_ID",
        "ORG_ID",
        "OTHER",
        "PARENT_TITLE",
        "PDB_PUBS",
        "PMCID",
        "PRIDE_PUBS",
        "PUBLISHER",
        "PUB_TYPE",
        "PUB_YEAR",
        "P_PDATE",
        "QN1",
        "QN2",
        "REF",
        "REFFED_BY",
        "RESOURCE_NAME",
        "RESULTS",
        "SERIES_NAME",
        "SHARD",
        "SRC",
        "SUPPL",
        "TABLE",
        "TITLE",
        "TITLE_ABS",
        "UNIPROT_PUBS",
        "UPDATE_DATE",
        "VOLUME",
        "AUTHOR",
        "MESH",
        "SUBSET",
    }
)

#: Fields whose value is ``y`` or ``n``; anything else matches nothing.
FLAG_FIELDS = frozenset(
    {f for f in KNOWN_FIELDS if f.startswith("HAS_")}
    | {"OPEN_ACCESS", "IN_EPMC", "IN_PMC", "AUTH_MAN", "EPMC_AUTH_MAN", "NIH_AUTH_MAN"}
)
DATE_FIELDS = frozenset(f for f in KNOWN_FIELDS if re.search(r"(DATE|PDATE|IDATE|CDATE)(_D)?$", f))
_OPERATORS = ("AND", "OR", "NOT")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_NOT_A_FIELD = frozenset({"http", "https", "ftp"})
_WORD_STOP = frozenset(' \t\r\n()"[{')


@dataclass
class Issue:
    """One thing wrong with, or surprising about, a query."""

    severity: str  # "error": the query will not mean what it says; "warning": check it
    code: str
    message: str
    position: int | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "position": self.position,
            "suggestion": self.suggestion,
        }


class QueryProblem(ValueError):
    """A query that cannot be used; carries the issues that say why."""

    def __init__(self, message: str, issues: list[Issue] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


@dataclass
class Token:
    kind: str  # lparen rparen quoted range word field op
    text: str
    pos: int


@dataclass
class Op:
    text: str  # AND OR NOT, upper-cased
    pos: int
    implicit: bool = False  # two operands side by side mean AND
    written: str = ""  # as typed, to spot lowercase operators


@dataclass
class Term:
    """``FIELD:value`` or a bare value (a token, or a group for ``FIELD:(a OR b)``)."""

    field: str | None
    value: Token | Group
    pos: int


@dataclass
class Group:
    items: list[Term | Group | Op] = field(default_factory=list)
    pos: int = 0


# --------------------------------------------------------------------------- tokenizer


def _emit_word(tokens: list[Token], word: str, pos: int) -> None:
    """Split a run of characters into field prefix, operator and value tokens."""
    if word.startswith("-") and len(word) > 1:  # "-term" is NOT term
        tokens.append(Token("op", "-", pos))
        _emit_word(tokens, word[1:], pos + 1)
        return
    if word.endswith(":") and _IDENT.match(word[:-1]):
        tokens.append(Token("field", word[:-1], pos))
        return
    name, _, rest = word.partition(":")
    if rest and _IDENT.match(name) and name.lower() not in _NOT_A_FIELD:
        tokens.append(Token("field", name, pos))
        tokens.append(Token("word", rest, pos + len(name) + 1))
        return
    kind = "op" if word.upper() in _OPERATORS else "word"
    tokens.append(Token(kind, word, pos))


def _closing(query: str, start: int, closer: str, escape: bool) -> int:
    """Index of the closer for the opener at ``start``, or -1."""
    i = start + 1
    while i < len(query):
        if escape and query[i] == "\\":
            i += 2
            continue
        if query[i] == closer:
            return i
        i += 1
    return -1


def tokenize(query: str) -> tuple[list[Token], list[Issue]]:
    tokens: list[Token] = []
    issues: list[Issue] = []
    i, n = 0, len(query)
    while i < n:
        c = query[i]
        if c.isspace():
            i += 1
        elif c in "()":
            tokens.append(Token("lparen" if c == "(" else "rparen", c, i))
            i += 1
        elif c in '"[{':
            closer = {'"': '"', "[": "]", "{": "}"}[c]
            end = _closing(query, i, closer, escape=(c == '"'))
            kind = "quoted" if c == '"' else "range"
            if end == -1:
                what = "quotation mark" if c == '"' else f"'{c}'"
                issues.append(
                    Issue(
                        "error",
                        "UNCLOSED_QUOTE" if c == '"' else "UNCLOSED_RANGE",
                        f"The {what} at position {i} is never closed. Europe PMC ignores it, "
                        "so the query means something else than what is written.",
                        i,
                    )
                )
                end = n - 1
            tokens.append(Token(kind, query[i : end + 1], i))
            i = end + 1
        else:
            j = i + 1  # always consume at least the character that got us here
            while j < n and query[j] not in _WORD_STOP:
                j += 1
            _emit_word(tokens, query[i:j], i)
            i = j
    return tokens, issues


# --------------------------------------------------------------------------- parser


def parse(query: str) -> tuple[Group, list[Issue]]:
    """Syntax tree of ``query`` and the problems found while reading it."""
    tokens, issues = tokenize(query)
    root = Group([], 0)
    stack = [root]
    pending: Token | None = None

    def missing_value() -> None:
        nonlocal pending
        if pending is not None:
            issues.append(
                Issue(
                    "error",
                    "MISSING_FIELD_VALUE",
                    f"The field {pending.text}: has no value after it.",
                    pending.pos,
                )
            )
            pending = None

    def add(node: Term | Group, pos: int) -> None:
        group = stack[-1]
        if group.items and not isinstance(group.items[-1], Op):
            group.items.append(Op("AND", pos, implicit=True))
        group.items.append(node)

    for tok in tokens:
        if tok.kind == "field":
            missing_value()
            pending = tok
        elif tok.kind == "op":
            missing_value()
            text = "NOT" if tok.text == "-" else tok.text.upper()
            stack[-1].items.append(Op(text, tok.pos, written=tok.text))
        elif tok.kind == "rparen":
            missing_value()
            if len(stack) == 1:
                issues.append(
                    Issue(
                        "error",
                        "UNMATCHED_PAREN",
                        f"The ')' at position {tok.pos} has no matching '('. Europe PMC ignores "
                        "it, so the grouping is not what is written.",
                        tok.pos,
                    )
                )
            else:
                stack.pop()
        elif tok.kind == "lparen":
            group = Group([], tok.pos)
            node: Term | Group = Term(pending.text, group, pending.pos) if pending else group
            pending = None
            add(node, tok.pos)
            stack.append(group)
        else:
            node = Term(
                pending.text if pending else None, tok, pending.pos if pending else tok.pos
            )
            pending = None
            add(node, tok.pos)
    missing_value()
    for group in stack[1:]:
        issues.append(
            Issue(
                "error",
                "UNMATCHED_PAREN",
                f"The '(' at position {group.pos} is never closed. Europe PMC ignores it, so "
                "the grouping is not what is written.",
                group.pos,
            )
        )
    return root, issues


# --------------------------------------------------------------------------- checks


def _suggest(name: str) -> str | None:
    close = difflib.get_close_matches(name.upper(), sorted(KNOWN_FIELDS), n=1, cutoff=0.75)
    return close[0] if close else None


def _parse_bound(text: str, *, end: bool) -> tuple[datetime.date, str] | None:
    """A ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD`` bound as the first or last day it covers."""
    match = _DATE.match(text)
    if not match:
        return None
    year, month, day = int(match[1]), match[2], match[3]
    try:
        if day:
            value = datetime.date(year, int(month), int(day))
        elif month:
            first = datetime.date(year, int(month), 1)
            nxt = datetime.date(year + (int(month) == 12), int(month) % 12 + 1, 1)
            value = nxt - datetime.timedelta(days=1) if end else first
        else:
            value = datetime.date(year, 12, 31) if end else datetime.date(year, 1, 1)
    except ValueError:
        return None
    return value, text


def check_range(text: str, field_name: str | None, pos: int) -> list[Issue]:
    """A ``[A TO B]`` range: both bounds present, valid for the field, and in order."""
    body = text[1:-1] if text[-1:] in "]}" else text[1:]
    match = re.fullmatch(r"\s*(\S+)\s+TO\s+(\S+)\s*", body, re.IGNORECASE)
    if not match:
        return [
            Issue(
                "error",
                "BAD_RANGE",
                f"The range {text} must look like [A TO B]; use * for an open end. A range with "
                "a missing bound matches nothing.",
                pos,
                "[2020 TO *]",
            )
        ]
    low, high = match[1], match[2]
    name = (field_name or "").upper()
    if name in DATE_FIELDS or name == "PUB_YEAR":
        return _check_date_bounds(text, name, low, high, pos)
    if name == "CITED":
        bad = [b for b in (low, high) if b != "*" and not b.isdigit()]
        if bad:
            return [
                Issue("error", "BAD_RANGE", f"CITED takes whole numbers, got {bad[0]!r}.", pos)
            ]
    return []


def _check_date_bounds(text: str, name: str, low: str, high: str, pos: int) -> list[Issue]:
    year_only = name == "PUB_YEAR"
    parsed: list[datetime.date | None] = []
    for bound, is_end in ((low, False), (high, True)):
        if bound == "*":
            parsed.append(None)
            continue
        value = _parse_bound(bound, end=is_end)
        if value is None or (year_only and not re.fullmatch(r"\d{4}", bound)):
            expected = "a four-digit year" if year_only else "YYYY, YYYY-MM or YYYY-MM-DD"
            return [
                Issue(
                    "error",
                    "BAD_RANGE",
                    f"{bound!r} in {text} is not a valid bound for {name}; use {expected} or *. "
                    "Europe PMC matches nothing for it.",
                    pos,
                )
            ]
        parsed.append(value[0])
    if parsed[0] and parsed[1] and parsed[0] > parsed[1]:
        return [
            Issue(
                "error",
                "BAD_RANGE",
                f"The range {text} runs backwards ({low} is after {high}) and matches nothing.",
                pos,
            )
        ]
    return []


def _check_term(term: Term, issues: list[Issue]) -> None:
    name = term.field.upper() if term.field else None
    if term.field and name not in KNOWN_FIELDS:
        hint = _suggest(term.field)
        issues.append(
            Issue(
                "warning",
                "UNKNOWN_FIELD",
                f"{term.field} is not a Europe PMC search field. Europe PMC returns no records "
                "for an unknown field and does not report an error."
                + (f" Did you mean {hint}?" if hint else ""),
                term.pos,
                hint,
            )
        )
    value = term.value
    if isinstance(value, Group):
        return
    if name in FLAG_FIELDS and value.kind == "word" and value.text.lower() not in ("y", "n"):
        issues.append(
            Issue(
                "error",
                "BAD_FLAG_VALUE",
                f"{term.field} takes y or n, not {value.text!r}. Europe PMC matches nothing for "
                "any other value.",
                value.pos,
                f"{name}:y",
            )
        )
    if value.kind == "range" and term.field is None:
        issues.append(
            Issue(
                "warning",
                "BARE_RANGE",
                f"{value.text} has no field in front of it. A [..] after a word is PubMed's "
                "field tag (x[ti]), not Europe PMC syntax: write TITLE:x instead.",
                value.pos,
            )
        )
    elif value.kind == "range":
        issues.extend(check_range(value.text, term.field, value.pos))
    if term.field is None and value.kind == "word" and value.text[:1] in "*?":
        issues.append(
            Issue(
                "warning",
                "LEADING_WILDCARD",
                f"{value.text!r} starts with a wildcard. Europe PMC answers a bare leading "
                "wildcard with HTTP 503; put it behind a field (TITLE:*x) or write the stem.",
                value.pos,
            )
        )


def _check_operators(group: Group, issues: list[Issue], *, root: bool) -> None:
    items = group.items
    operands = [i for i in items if not isinstance(i, Op)]
    if not operands:
        issues.append(
            Issue(
                "error",
                "EMPTY_QUERY" if root else "EMPTY_GROUP",
                "The query has no search terms." if root else "An empty group ().",
                group.pos,
            )
        )
        return
    first = items[0]
    if isinstance(first, Op) and first.text != "NOT":
        issues.append(_op_issue("LEADING_OPERATOR", first, "starts the group with"))
    elif isinstance(first, Op):
        issues.append(
            Issue(
                "warning",
                "LEADING_NOT",
                "NOT at the start matches every record except those that follow it, which is "
                "usually most of Europe PMC.",
                first.pos,
            )
        )
    if isinstance(items[-1], Op):
        issues.append(_op_issue("TRAILING_OPERATOR", items[-1], "ends the group with"))
    for prev, cur in zip(items, items[1:], strict=False):
        if (
            isinstance(prev, Op)
            and isinstance(cur, Op)
            and not (cur.text == "NOT" and prev.text in ("AND", "OR"))
        ):
            issues.append(_op_issue("DOUBLE_OPERATOR", cur, f"follows {prev.text} with"))
    for op in (i for i in items if isinstance(i, Op) and not i.implicit):
        if op.written not in ("-", op.text):
            issues.append(
                Issue(
                    "warning",
                    "LOWERCASE_OPERATOR",
                    f"'{op.written}' is read as {op.text} by Europe PMC, but PubMed and most "
                    "other databases treat it as a word; write it in capitals.",
                    op.pos,
                    op.text,
                )
            )
    joins = {i.text for i in items if isinstance(i, Op) and i.text in ("AND", "OR")}
    if joins == {"AND", "OR"}:
        issues.append(
            Issue(
                "warning",
                "MIXED_OPERATORS",
                "AND and OR are mixed without parentheses. Europe PMC does not read this as "
                "either grouping (a AND b OR c returns just the records of a), so add "
                "parentheses to say what you mean.",
                group.pos,
                "(a AND b) OR c   or   a AND (b OR c)",
            )
        )


def _walk(group: Group, issues: list[Issue], *, root: bool = False) -> None:
    _check_operators(group, issues, root=root)
    for item in group.items:
        if isinstance(item, Group):
            _walk(item, issues)
        elif isinstance(item, Term):
            _check_term(item, issues)
            if isinstance(item.value, Group):
                _walk(item.value, issues)


def _op_issue(code: str, op: Op, how: str) -> Issue:
    return Issue(
        "error",
        code,
        f"The query {how} {op.text} (position {op.pos}). Europe PMC drops the dangling "
        "operator silently, so the query means something else than what is written.",
        op.pos,
    )


# --------------------------------------------------------------------------- rendering


def render(node: Group | Term | Op | Token, *, root: bool = True) -> str:
    """The query as clean text: single spaces, capital operators, explicit AND."""
    if isinstance(node, Token):
        return node.text
    if isinstance(node, Op):
        return node.text
    if isinstance(node, Term):
        value = render(node.value, root=False)
        if node.field is None:
            return value
        name = node.field.upper() if node.field.upper() in KNOWN_FIELDS else node.field
        return f"{name}:{value}"
    inner = " ".join(render(i, root=False) for i in node.items)
    return inner if root else f"({inner})"


@dataclass
class LintResult:
    issues: list[Issue]
    tree: Group
    normalized: str | None = None

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]


def lint(query: str) -> LintResult:
    """Parse and check ``query``; ``normalized`` is set only when it has no errors."""
    if not query or not query.strip():
        issue = Issue("error", "EMPTY_QUERY", "The query is empty.", 0)
        return LintResult([issue], Group())
    tree, issues = parse(query)
    _walk(tree, issues, root=True)
    issues.sort(key=lambda i: (i.position if i.position is not None else -1, i.code))
    result = LintResult(issues, tree)
    if not result.errors:
        result.normalized = render(tree)
    return result


# --------------------------------------------------------------------------- PubMed translation

_PUBMED_TAGS = {
    "TITLE": "ti",
    "ABSTRACT": "ab",
    "AUTH": "au",
    "AUTHOR": "au",
    "JOURNAL": "ta",
    "AFF": "ad",
    "DOI": "doi",
    "EXT_ID": "pmid",
    "MESH": "mh",
    "KW": "ot",
    "KEYWORD": "ot",
    "LANG": "la",
    "PUB_TYPE": "pt",
    "ISSN": "is",
    "TITLE_ABS": "tiab",
}
_PUBMED_DATE_FIELDS = frozenset({"PUB_YEAR", "FIRST_PDATE", "E_PDATE", "P_PDATE"})
_DROP, _DROP_SILENT = object(), object()


@dataclass
class Translation:
    query: str | None
    exact: bool
    warnings: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


class _PubMed:
    """Rewrites a Europe PMC syntax tree as PubMed syntax, recording what does not map."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.dropped: list[str] = []
        self.exact = True
        self.negated = False
        self.dated = False

    def note(self, message: str, *, exact: bool = True) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
        self.exact = self.exact and exact

    def date(self, text: str) -> str:
        return text.strip('"').replace("-", "/")

    def date_term(self, name: str, value: Token) -> str:
        self.dated = True
        if name != "PUB_YEAR":
            self.note(
                f"{name} is Europe PMC's own date; PubMed's [dp] (publication date) can differ "
                "for the same paper.",
                exact=False,
            )
        if value.kind != "range":
            return f"{self.date(value.text)}[dp]"
        match = re.fullmatch(r"\s*(\S+)\s+TO\s+(\S+)\s*", value.text[1:-1], re.IGNORECASE)
        low, high = (match[1], match[2]) if match else ("*", "*")
        low = "1800" if low == "*" else self.date(low)
        high = "3000" if high == "*" else self.date(high)
        return f"{low}:{high}[dp]"

    def flag_term(self, name: str, value: str) -> Any:
        yes = value.lower() == "y"
        if name == "OPEN_ACCESS" and yes:
            self.note(
                "OPEN_ACCESS:y became 'free full text[sb]'; PubMed's free full text is not the "
                "same set as Europe PMC's open-access subset.",
                exact=False,
            )
            return "free full text[sb]"
        if name == "HAS_ABSTRACT":
            return "hasabstract" if yes else "NOT hasabstract"
        return _DROP

    def term(self, name: str | None, value: Token | Group, ctx: str | None) -> Any:
        name = (name or ctx or "").upper() or None
        if isinstance(value, Group):
            return self.group(value, name)
        if name is None:
            return value.text
        if name == "SRC":
            if value.text.upper() == "MED":
                self.note("SRC:MED was dropped: PubMed only contains that source.")
                return _DROP_SILENT
            return _DROP
        if name in _PUBMED_DATE_FIELDS:
            return self.date_term(name, value)
        if name in FLAG_FIELDS and value.kind == "word":
            return self.flag_term(name, value.text)
        tag = _PUBMED_TAGS.get(name)
        if name == "MESH" and tag:
            self.note(
                "MESH:x became x[mh], but Europe PMC's MESH field is not PubMed's MeSH index: "
                "the same heading found about 5,000 records in Europe PMC and 25,000 (or 172,000 "
                "with narrower terms, which [mh] includes) in PubMed.",
                exact=False,
            )
        return f"{value.text}[{tag}]" if tag else _DROP

    def clauses(self, group: Group, ctx: str | None) -> list[tuple[list[str], Any, str]]:
        """``(connectors, translation, original)`` for each operand of ``group``."""
        out: list[tuple[list[str], Any, str]] = []
        connectors: list[str] = []
        for item in group.items:
            if isinstance(item, Op):
                connectors.append(item.text)
                continue
            if isinstance(item, Group):
                piece = self.group(item, ctx)
            else:
                piece = self.term(item.field, item.value, ctx)
            out.append((connectors, piece, render(item, root=False)))
            connectors = []
        return out

    def group(self, group: Group, ctx: str | None = None, *, root: bool = False) -> Any:
        parts: list[str] = []
        for connectors, piece, original in self.clauses(group, ctx):
            self.negated = self.negated or "NOT" in connectors
            if piece is _DROP_SILENT:
                continue
            if piece is _DROP or piece is None:
                self.dropped.append(original)
                narrower = "OR" in connectors
                self.note(
                    f"{original} has no PubMed equivalent and was left out, so the translation "
                    f"is {'narrower' if narrower else 'broader'} than the original.",
                    exact=False,
                )
                continue
            if not parts:
                lead = ["NOT"] if connectors and connectors[-1] == "NOT" else []
                parts.append(" ".join([*lead, piece]))
            else:
                parts.append(" ".join([*(connectors or ["AND"]), piece]))
        if not parts:
            return None
        text = " ".join(parts)
        return text if root else f"({text})"


def translate_pubmed(query: str) -> Translation:
    """Europe PMC syntax -> PubMed syntax for the constructs that map, with warnings for the rest.

    Raises ``QueryProblem`` when the query has errors: a translation of a misread query is a
    translation of something nobody asked for.
    """
    result = lint(query)
    if result.errors:
        raise QueryProblem("The query has errors; fix them before translating.", result.issues)
    rewriter = _PubMed()
    text = rewriter.group(result.tree, root=True)
    if text is None:
        rewriter.note("Nothing in the query has a PubMed equivalent.", exact=False)
    if rewriter.negated and rewriter.dated:
        rewriter.note(
            "NOT combined with a date filter: in testing PubMed returned the same count for "
            "'a AND NOT b AND 2020[dp]' as for 'a AND b AND 2020[dp]' (without the date it "
            "behaved as expected), so check the result in PubMed.",
            exact=False,
        )
    return Translation(
        text, rewriter.exact and text is not None, rewriter.warnings, rewriter.dropped
    )


# --------------------------------------------------------------------------- building


def check_date(value: str, label: str) -> str:
    """``value`` if it is a real ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD``; else raise."""
    if value and _parse_bound(value, end=False) is None:
        raise QueryProblem(f"{label} must be YYYY, YYYY-MM or YYYY-MM-DD, got {value!r}")
    return value


def check_date_order(date_from: str, date_to: str) -> None:
    if date_from and date_to:
        start, end = _parse_bound(date_from, end=False), _parse_bound(date_to, end=True)
        if start and end and start[0] > end[0]:
            raise QueryProblem(f"date_from {date_from} is after date_to {date_to}")


def _builder() -> Any:
    from pyeuropepmc.features.literature.query_builder import QueryBuilder

    return QueryBuilder()


def filter_clauses(
    *,
    date_from: str = "",
    date_to: str = "",
    open_access: bool = False,
    has_fulltext: bool = False,
    source: str = "",
    cites: str = "",
) -> list[str]:
    """Filter clauses in a fixed order, each rendered by ``QueryBuilder`` where it can.

    ``QueryBuilder.date_range`` takes whole years only and renders PUB_YEAR, so first
    publication dates, which have day precision, are written out here.
    """
    check_date(date_from, "date_from")
    check_date(date_to, "date_to")
    check_date_order(date_from, date_to)
    clauses: list[str] = []
    if date_from or date_to:
        clauses.append(f"FIRST_PDATE:[{date_from or '*'} TO {date_to or '*'}]")
    if open_access:
        clauses.append(str(_builder().field("open_access", True).build(validate=False)))
    if has_fulltext:
        clauses.append(str(_builder().field("has_ft", True).build(validate=False)))
    if source:
        if not re.fullmatch(r"[A-Za-z]{2,5}", source):
            raise QueryProblem(
                f"source must be a short code such as MED, PMC or PPR, got {source!r}"
            )
        clauses.append(str(_builder().source(source).build(validate=False)))
    if cites:
        # CITES: lists the records that cite a MED record; for a PMC id it matches nothing
        # (CITES:PMC3525259_PMC: 0 records, checked live), so only a PMID is accepted.
        if not cites.strip().isdigit():
            raise QueryProblem(f"cites must be a PMID (digits only), got {cites!r}")
        clauses.append(str(_builder().cites(cites.strip(), "MED").build(validate=False)))
    return clauses


def apply_filters(query: str, **filters: Any) -> str:
    """``query`` AND-ed with the filter clauses; unchanged when there are none."""
    clauses = filter_clauses(**filters)
    if not clauses:
        return query
    return " AND ".join([f"({query})", *clauses])


_EXPRESSION = re.compile(r'[:"()\[\]]|\b(?:AND|OR|NOT)\b')


def _term(text: str) -> str:
    """A plain word or phrase is searched as given; anything with syntax in it is kept as
    written, so ``TITLE:crispr`` and ``"heart attack"`` mean what they say."""
    text = text.strip()
    if not text:
        raise QueryProblem("an empty search term")
    if _EXPRESSION.search(text):
        return f"({text})" if re.search(r"\b(?:AND|OR|NOT)\b", text) else text
    return str(_builder().keyword(text).build(validate=False))


def build(
    all_of: list[str],
    any_of: list[str],
    none_of: list[str],
    **filters: Any,
) -> tuple[str, str]:
    """A query and a plain-language explanation of it, from structured input."""
    positive: list[str] = [_term(t) for t in all_of]
    said: list[str] = []
    if all_of:
        said.append("contain all of: " + ", ".join(t.strip() for t in all_of))
    if any_of:
        positive.append("(" + " OR ".join(_term(t) for t in any_of) + ")")
        said.append("contain at least one of: " + ", ".join(t.strip() for t in any_of))
    positive.extend(filter_clauses(**filters))
    negative = [f"NOT {_term(t)}" for t in none_of]
    if none_of:
        said.append("contain none of: " + ", ".join(t.strip() for t in none_of))
    if not positive:
        raise QueryProblem(
            "give at least one of all_of, any_of or a filter"
            + ("; none_of alone matches almost everything" if none_of else "")
        )
    return " AND ".join([*positive, *negative]), _explain(said, filters)


def _explain(said: list[str], f: dict[str, Any]) -> str:
    """One sentence saying what the query asks for, from the structured input."""
    clauses = list(said)
    if f.get("date_from") or f.get("date_to"):
        clauses.append(
            f"were first published {f.get('date_from') or 'at any time'} "
            f"to {f.get('date_to') or 'today'}"
        )
    if f.get("open_access"):
        clauses.append("are open access")
    if f.get("has_fulltext"):
        clauses.append("have full text")
    if f.get("source"):
        clauses.append(f"come from source {f['source'].upper()}")
    if f.get("cites"):
        clauses.append(f"cite PMID {f['cites']}")
    return "Records that " + "; ".join(clauses) + "."
