"""MeSH expansion for search terms: a bundled snapshot, and the NLM service on request.

The default path is offline and deterministic: ``data/mesh_common.json`` holds 244 common
clinical headings (descriptor ID, heading, tree numbers and entry terms exactly as NLM publishes
them; ``scripts/build_mesh_snapshot.py`` rebuilds it). A term is matched against the headings
and entry terms there. A term that is not in the snapshot is reported as not matched, never
guessed. With ``use_api`` the NLM MeSH service (https://id.nlm.nih.gov/mesh/) is asked instead.

Pure apart from reading the snapshot and, for ``use_api``, the ``get`` function it is given.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
import json
import re
from typing import Any

LOOKUP_URL = "https://id.nlm.nih.gov/mesh/lookup"
SPARQL_URL = "https://id.nlm.nih.gov/mesh/sparql"
MAX_TERMS = 20
DEFAULT_ENTRY_TERMS = 6
MAX_SUGGESTIONS = 5

#: ``get(url, params, timeout)`` returning parsed JSON; injected so the API path is testable.
Fetch = Callable[[str, dict[str, Any], float], Any]


@dataclass(frozen=True)
class Descriptor:
    ui: str
    heading: str
    trees: tuple[str, ...]
    entry_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ui": self.ui,
            "heading": self.heading,
            "tree_numbers": list(self.trees),
            "entry_terms": list(self.entry_terms),
        }


@dataclass
class Match:
    term: str
    descriptor: Descriptor | None
    matched_on: str | None = None  # "heading" | "entry term" | "plural form" | "NLM lookup"
    source: str = "snapshot"  # "snapshot" | "nlm"
    also: list[str] = field(default_factory=list)  # other headings the same term could mean
    suggestions: list[str] = field(default_factory=list)  # API only: near misses, not chosen


def normalise(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().strip("\"'").lower())


def _variants(key: str) -> list[tuple[str, str]]:
    """The key as written, then simple singular forms (``statins`` -> ``statin``)."""
    forms = [(key, "")]
    if key.endswith("ies") and len(key) > 4:
        forms.append((key[:-3] + "y", "plural form"))
    if key.endswith("s") and not key.endswith("ss") and len(key) > 3:
        forms.append((key[:-1], "plural form"))
    return forms


@dataclass
class Snapshot:
    built: str
    source: str
    descriptors: list[Descriptor]
    _by_heading: dict[str, Descriptor] = field(default_factory=dict, repr=False)
    _by_entry: dict[str, list[Descriptor]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for descriptor in self.descriptors:
            self._by_heading[normalise(descriptor.heading)] = descriptor
            for entry in descriptor.entry_terms:
                self._by_entry.setdefault(normalise(entry), []).append(descriptor)

    def lookup(self, term: str) -> Match:
        key = normalise(term)
        for form, note in _variants(key):
            if form in self._by_heading:
                return Match(term, self._by_heading[form], note or "heading")
            if form in self._by_entry:
                candidates = self._by_entry[form]
                return Match(
                    term,
                    candidates[0],
                    note or "entry term",
                    also=[d.heading for d in candidates[1:]],
                )
        return Match(term, None)


@lru_cache(maxsize=1)
def snapshot() -> Snapshot:
    raw = json.loads(
        resources.files("pyeuropepmc.mcp").joinpath("data/mesh_common.json").read_text("utf-8")
    )
    descriptors = [
        Descriptor(d["ui"], d["heading"], tuple(d["trees"]), tuple(d["entry_terms"]))
        for d in raw["descriptors"]
    ]
    return Snapshot(raw["built"], raw["source"], descriptors)


# ---------------------------------------------------------------------------
# Query fragment
# ---------------------------------------------------------------------------


def _quoted(text: str) -> str:
    return '"' + " ".join(re.sub(r'["\\]', " ", text).split()) + '"'


def fragment(match: Match, max_entry_terms: int = DEFAULT_ENTRY_TERMS) -> str:
    """``(MESH:"Heading" OR "entry term" OR ...)`` for a matched term, else the term as a phrase.

    Europe PMC's ``MESH:`` field is narrower than PubMed's MeSH index, so the heading and the
    shortest entry terms are also searched as phrases, as is the wording the caller used.
    """
    if match.descriptor is None:
        return _quoted(match.term)
    descriptor = match.descriptor
    parts = [f"MESH:{_quoted(descriptor.heading)}", _quoted(descriptor.heading)]
    wording = _quoted(match.term)
    seen = {normalise(descriptor.heading)}
    if normalise(match.term) not in seen:
        parts.append(wording)
        seen.add(normalise(match.term))
    added = 0
    for entry in sorted(descriptor.entry_terms, key=lambda t: (len(t), t.lower())):
        if added >= max_entry_terms:
            break
        if normalise(entry) not in seen:
            parts.append(_quoted(entry))
            seen.add(normalise(entry))
            added += 1
    return "(" + " OR ".join(parts) + ")"


# ---------------------------------------------------------------------------
# NLM service (use_api)
# ---------------------------------------------------------------------------


_UI = re.compile(r"^[A-Z]\d{4,9}$")


def _last(resource: str) -> str:
    return resource.rsplit("/", 1)[-1]


def _ui(resource: str) -> str:
    """The identifier of a descriptor, term or concept, checked before it goes into a query."""
    ui = _last(resource)
    if not _UI.match(ui):
        raise ValueError(f"unexpected MeSH identifier {ui!r}")
    return ui


def _sparql_details(fetch: Fetch, ui: str, timeout: float) -> Descriptor | None:
    ui = _ui(ui)
    query = f"""
    PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
    SELECT ?label ?tree ?entry WHERE {{
      mesh:{ui} rdfs:label ?label .
      OPTIONAL {{ mesh:{ui} meshv:treeNumber ?tree }}
      OPTIONAL {{
        {{ mesh:{ui} meshv:preferredConcept ?c }} UNION {{ mesh:{ui} meshv:concept ?c }}
        ?c meshv:term ?t . ?t meshv:prefLabel ?entry
      }}
    }}"""
    rows = fetch(SPARQL_URL, {"query": query, "format": "JSON", "limit": 2000}, timeout)
    bindings = rows["results"]["bindings"]
    if not bindings:
        return None
    heading = bindings[0]["label"]["value"]
    trees: dict[str, None] = {}
    entries: dict[str, str] = {}
    for row in bindings:
        if "tree" in row:
            trees[_last(row["tree"]["value"])] = None
        if "entry" in row:
            entries.setdefault(row["entry"]["value"].lower(), row["entry"]["value"])
    terms = [t for k, t in entries.items() if k != heading.lower()]
    return Descriptor(ui, heading, tuple(sorted(trees)), tuple(sorted(terms, key=str.lower)))


def _descriptor_for_term(fetch: Fetch, term_resource: str, timeout: float) -> str | None:
    query = f"""
    PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
    PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
    SELECT ?d WHERE {{
      ?c meshv:term mesh:{_ui(term_resource)} .
      {{ ?d meshv:preferredConcept ?c }} UNION {{ ?d meshv:concept ?c }}
    }} LIMIT 1"""
    rows = fetch(SPARQL_URL, {"query": query, "format": "JSON"}, timeout)
    bindings = rows["results"]["bindings"]
    return _ui(bindings[0]["d"]["value"]) if bindings else None


def lookup_api(term: str, fetch: Fetch, timeout: float = 15.0) -> Match:
    """Ask NLM: a heading of that name, else an entry term of that name, else near misses."""
    found = fetch(
        LOOKUP_URL + "/descriptor", {"label": term, "match": "exact", "limit": 1}, timeout
    )
    ui = _ui(found[0]["resource"]) if found else None
    matched_on = "heading"
    if ui is None:
        entry = fetch(LOOKUP_URL + "/term", {"label": term, "match": "exact", "limit": 1}, timeout)
        if entry:
            ui = _descriptor_for_term(fetch, entry[0]["resource"], timeout)
            matched_on = "entry term"
    if ui is not None:
        descriptor = _sparql_details(fetch, ui, timeout)
        if descriptor is not None:
            return Match(term, descriptor, matched_on, source="nlm")
    near = fetch(
        LOOKUP_URL + "/descriptor",
        {"label": term, "match": "contains", "limit": MAX_SUGGESTIONS},
        timeout,
    )
    return Match(term, None, source="nlm", suggestions=[n["label"] for n in near or []])
