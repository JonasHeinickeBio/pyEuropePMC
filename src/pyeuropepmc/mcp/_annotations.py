"""Aggregation of Europe PMC text-mined annotations for MCP responses.

Pure functions, no I/O. The Annotations API returns one record per *mention*: a
review with a few hundred gene mentions is 150 KB, and a single article found by an
entity search can carry several hundred mentions of that entity (two articles for
"ethanol" were 424 KB). An agent wants the entities and how often they occur, not the
mentions, so these helpers group mentions into entities and keep a few examples.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

_EXAMPLES_PER_ENTITY = 2
_EXAMPLE_CHARS = 120


def section_name(raw: Any) -> str:
    """``"Abstract (http://purl.org/dc/terms/abstract)"`` -> ``"Abstract"``."""
    return str(raw or "").split(" (", 1)[0].strip()


def _norm(value: Any) -> str:
    """Case- and separator-insensitive form, so ``gene_proteins`` matches ``Gene_Proteins``."""
    return str(value or "").strip().lower().replace("_", " ")


def _mentions(annotation: dict[str, Any]) -> int:
    """One annotation is usually one mention; some carry a ``frequency`` instead."""
    freq = annotation.get("frequency")
    return freq if isinstance(freq, int) and freq > 0 else 1


def matches(
    annotation: dict[str, Any],
    *,
    annotation_type: str = "",
    section: str = "",
    provider: str = "",
) -> bool:
    if annotation_type and _norm(annotation.get("type")) != _norm(annotation_type):
        return False
    if provider and _norm(annotation.get("provider")) != _norm(provider):
        return False
    return not (
        section and not _norm(section_name(annotation.get("section"))).startswith(_norm(section))
    )


def _tags(annotation: dict[str, Any]) -> list[tuple[str, str]]:
    """``(name, uri)`` of every entity a mention points at; the surface text when untagged."""
    tags = [
        (str(t.get("name") or ""), str(t.get("uri") or ""))
        for t in annotation.get("tags") or []
        if isinstance(t, dict)
    ]
    tags = [t for t in tags if t[0] or t[1]]
    return tags or [(str(annotation.get("exact") or ""), "")]


def _example(annotation: dict[str, Any]) -> str:
    text = str(annotation.get("exact") or "").strip()
    return text if len(text) <= _EXAMPLE_CHARS else text[: _EXAMPLE_CHARS - 1] + "…"


def collect(
    annotations: list[dict[str, Any]],
    *,
    annotation_type: str = "",
    section: str = "",
    provider: str = "",
) -> dict[str, Any]:
    """Group mentions into entities.

    Returns every entity (the caller applies the size limit) in descending order of
    mentions, plus the mention total and the entity types present *before* filtering,
    so an empty result can say what the article does have.
    """
    available = Counter(str(a.get("type") or "") for a in annotations if isinstance(a, dict))
    entities: dict[tuple[str, str], dict[str, Any]] = {}
    total = 0
    for annotation in annotations:
        if not isinstance(annotation, dict) or not matches(
            annotation, annotation_type=annotation_type, section=section, provider=provider
        ):
            continue
        count = _mentions(annotation)
        total += count
        kind = str(annotation.get("type") or "")
        sec = section_name(annotation.get("section"))
        for name, uri in _tags(annotation):
            entity = entities.setdefault(
                (kind, uri or name),
                {
                    "type": kind,
                    "name": name,
                    "uri": uri,
                    "mentions": 0,
                    "sections": Counter(),
                    "providers": set(),
                    "examples": [],
                },
            )
            entity["mentions"] += count
            if sec:
                entity["sections"][sec] += count
            if annotation.get("provider"):
                entity["providers"].add(str(annotation["provider"]))
            example = _example(annotation)
            if (
                example
                and example not in entity["examples"]
                and len(entity["examples"]) < _EXAMPLES_PER_ENTITY
            ):
                entity["examples"].append(example)
    ordered = sorted(entities.values(), key=lambda e: (-e["mentions"], e["type"], e["name"]))
    for entity in ordered:
        entity["sections"] = dict(entity["sections"].most_common())
        entity["providers"] = sorted(entity["providers"])
    return {
        "annotation_count": total,
        "entities": ordered,
        "available_types": dict(available.most_common()),
    }


def summarize_article(
    annotations: list[dict[str, Any]],
    *,
    annotation_type: str = "",
    section: str = "",
    provider: str = "",
) -> dict[str, Any]:
    """Per-article view for entity searches: how often, where, and a couple of examples."""
    kept = [
        a
        for a in annotations
        if isinstance(a, dict)
        and matches(a, annotation_type=annotation_type, section=section, provider=provider)
    ]
    sections: Counter[str] = Counter()
    types: Counter[str] = Counter()
    examples: list[str] = []
    mentions = 0
    for annotation in kept:
        count = _mentions(annotation)
        mentions += count
        sections[section_name(annotation.get("section"))] += count
        types[str(annotation.get("type") or "")] += count
        example = _example(annotation)
        if example and example not in examples and len(examples) < _EXAMPLES_PER_ENTITY:
            examples.append(example)
    return {
        "mentions": mentions,
        "sections": {k: v for k, v in sections.most_common() if k},
        "types": dict(types.most_common()),
        "examples": examples,
    }


def next_cursor(value: Any) -> str | None:
    """The API's ``nextCursorMark``; ``-1`` (or nothing) means the last page."""
    if value is None:
        return None
    try:
        if float(value) < 0:
            return None
    except (TypeError, ValueError):
        return None
    return str(value)
