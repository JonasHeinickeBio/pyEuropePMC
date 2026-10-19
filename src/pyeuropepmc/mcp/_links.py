"""Shaping of Europe PMC's link services for MCP responses.

Pure functions, no I/O. ``datalinks`` answers in a Scholix-style nesting of
``Category -> Section -> Linklist -> Link`` in which every link says ``"Type": "dataset"``,
even an Altmetric page or a cited article's DOI; the category and the section tag are what
tell a data accession from an attention score. ``labsLinks`` groups links by provider.
Both services answer ``hitCount: 0`` with HTTP 200 for an identifier they do not know, and
both ignore a ``pageSize`` or ``providerId`` parameter, so limits and filters live here.
"""

from __future__ import annotations

import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")

#: ``ObtainedBy`` value -> what it means for the reader.
_ORIGIN = {
    "tm_accession": "text_mined",  # Europe PMC found the accession number in the full text
    "ext_links": "provider",  # supplied by an external provider
}


def _list(value: Any) -> list[Any]:
    """A JSON field that is a list, a single object or missing, as a list."""
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, dict) else []


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _TAG_RE.sub("", value).strip()
    return cleaned or None


def _name(value: Any) -> str | None:
    return _text(value.get("Name")) if isinstance(value, dict) else None


def _link(
    link: dict[str, Any], category: str, kind: str | None, origin: str | None
) -> dict[str, Any]:
    target = _obj(link.get("Target"))
    ident = _obj(target.get("Identifier"))
    target_id = _text(ident.get("ID"))
    title = _text(target.get("Title"))
    mentions = link.get("Frequency")
    return {
        "category": category,
        "kind": kind,
        "relationship": _name(link.get("RelationshipType")),
        "scheme": _text(ident.get("IDScheme")),
        "id": target_id,
        "url": _text(ident.get("IDURL")),
        # The title of an accession link is the accession number again.
        "title": title if title != target_id else None,
        "provider": _name(target.get("Publisher")),
        "origin": _ORIGIN.get(str(link.get("ObtainedBy") or origin or ""), origin),
        "mentions": mentions if isinstance(mentions, int) else None,
    }


def flatten_data_links(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Every link of a ``datalinks`` response as one flat record, in the service's order."""
    out: list[dict[str, Any]] = []
    listing = response.get("dataLinkList")
    for category in _list(listing.get("Category") if isinstance(listing, dict) else None):
        if not isinstance(category, dict):
            continue
        category_name = _text(category.get("Name")) or "Unknown"
        for section in _list(category.get("Section")):
            if not isinstance(section, dict):
                continue
            tags = [t for t in _list(section.get("Tags")) if isinstance(t, str)]
            kind = tags[0] if tags else None
            origin = section.get("ObtainedBy")
            linklist = section.get("Linklist")
            for link in _list(linklist.get("Link") if isinstance(linklist, dict) else None):
                if isinstance(link, dict):
                    out.append(_link(link, category_name, kind, origin))
    return out


def select(
    links: list[dict[str, Any]], *, category: str = "", scheme: str = ""
) -> list[dict[str, Any]]:
    """Links in a category and/or with an identifier scheme (case-insensitive, exact)."""
    category, scheme = category.strip().lower(), scheme.strip().lower()
    return [
        link
        for link in links
        if (not category or str(link["category"]).lower() == category)
        and (not scheme or str(link["scheme"] or "").lower() == scheme)
    ]


def count_by(links: list[dict[str, Any]], key: str) -> dict[str, int]:
    """``key`` -> number of links, most frequent first."""
    counts: dict[str, int] = {}
    for link in links:
        value = str(link.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def flatten_lab_links(response: dict[str, Any], *, provider: str = "") -> list[dict[str, Any]]:
    """Providers of a ``labsLinks`` response with their links.

    ``provider`` keeps providers whose name contains the text (case-insensitive) or whose
    numeric id equals it; the service itself ignores a provider filter.
    """
    wanted = provider.strip().lower()
    container = response.get("providers")
    out: list[dict[str, Any]] = []
    for item in _list(container.get("provider") if isinstance(container, dict) else None):
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name")) or ""
        provider_id = item.get("id")
        if wanted and wanted not in name.lower() and wanted != str(provider_id):
            continue
        links = [
            {
                "title": _text(link.get("title")),
                "url": _text(link.get("url")),
                "image_url": _text(link.get("imgUrl")),
            }
            for link in _list(item.get("link"))
            if isinstance(link, dict)
        ]
        out.append(
            {
                "provider_id": provider_id if isinstance(provider_id, int) else None,
                "provider": name,
                "description": _text(item.get("description")),
                "links": links,
            }
        )
    return out
