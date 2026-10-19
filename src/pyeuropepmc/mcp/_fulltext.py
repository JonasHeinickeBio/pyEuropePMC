"""Shaping of structured full text for MCP responses.

Pure functions, no I/O. ``FullTextXMLParser.get_full_text_sections_structured()`` is
faithful but heavy: every block repeats ``schema_version`` and a ``inlines`` markup
list, and a table carries its content three times (``text``, ``rows``, ``inlines``).
A 60 KB paper comes out as roughly 50 KB of JSON, which is too much for one tool
result. The helpers here select the sections an agent asked for, drop the repeated
bookkeeping, render markdown, and cut the result at a block boundary.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Callable
import json
import threading
from typing import Any

# Keys that repeat on every block and carry no content an agent can use.
_DROP_KEYS = frozenset({"schema_version", "inlines", "target_id"})
# The title is returned as metadata; as a section it would only repeat it.
_SKIPPED_TITLES = frozenset({"article title"})
_TABLE_KEYS = ("type", "label", "caption", "rows")


class XmlCache:
    """Small thread-safe LRU of full-text XML, keyed by PMCID.

    A paper is usually asked for several times in a row (text, then figures, then
    references), and one fetch takes seconds. It has the ``reset`` method of the
    server's other lazy singletons so tests can clear it the same way.
    """

    def __init__(self, maxsize: int = 8) -> None:
        self._maxsize = maxsize
        self._items: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._maxsize:
                self._items.popitem(last=False)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()


def _strip(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in _DROP_KEYS}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def slim_block(block: dict[str, Any]) -> dict[str, Any]:
    """A block without its repeated bookkeeping; a table keeps only its rows and caption."""
    if block.get("type") == "table":
        return {k: block[k] for k in _TABLE_KEYS if k in block}
    stripped = _strip(block)
    return stripped if isinstance(stripped, dict) else {}


def _path_text(section: dict[str, Any]) -> str:
    path = section.get("section_path")
    if isinstance(path, list | tuple):
        return " / ".join(str(p) for p in path)
    return str(path or "")


def select_sections(
    sections: list[dict[str, Any]], wanted: list[str] | None = None
) -> list[dict[str, Any]]:
    """Sections to return: the title-only section is dropped, and ``wanted`` (case-insensitive
    substrings of a section's title or path, so ``"methods"`` also matches
    ``"Materials and Methods"``) keeps only the matching ones."""
    needles = [w.strip().lower() for w in wanted or [] if w and w.strip()]
    chosen = []
    for section in sections:
        title = str(section.get("title", ""))
        if title.strip().lower() in _SKIPPED_TITLES:
            continue
        if needles:
            haystack = f"{title} {_path_text(section)}".lower()
            if not any(n in haystack for n in needles):
                continue
        chosen.append(section)
    return chosen


def _depth(section: dict[str, Any]) -> int:
    """Nesting level of a section: 0 for a top-level one, 1 for its subsection, ..."""
    return max(_path_text(section).count("/"), 0)


def section_titles(sections: list[dict[str, Any]]) -> list[str]:
    return [str(s.get("title", "")) for s in select_sections(sections)]


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _table_md(block: dict[str, Any]) -> str:
    head = " ".join(p for p in (block.get("label"), block.get("caption")) if p)
    lines = [f"**{head}**"] if head else []
    rows = [r for r in block.get("rows") or [] if isinstance(r, list)]
    if rows:
        width = max(len(r) for r in rows)
        padded = [[*r, *[""] * (width - len(r))] for r in rows]
        lines.append("| " + " | ".join(_cell(c) for c in padded[0]) + " |")
        lines.append("|" + " --- |" * width)
        lines.extend("| " + " | ".join(_cell(c) for c in r) + " |" for r in padded[1:])
    return "\n".join(lines)


def block_to_markdown(block: dict[str, Any]) -> str:
    kind = block.get("type")
    if kind == "heading":
        return f"### {block.get('text', '')}"
    if kind == "table":
        return _table_md(block)
    if kind == "figure":
        head = ": ".join(p for p in (block.get("label"), block.get("caption")) if p)
        return f"*{head}*" if head else ""
    if kind == "list":
        items = block.get("items") or []
        return "\n".join(f"- {i.get('text', '') if isinstance(i, dict) else i}" for i in items)
    return str(block.get("text") or "")


def render_units(sections: list[dict[str, Any]], fmt: str) -> list[tuple[int, int | None, str]]:
    """Flatten sections into ``(section index, block index or None, text)`` units.

    A unit is the smallest piece that is cut or kept as a whole: a section heading or
    one block. ``None`` as the block index marks a heading. The text is what that unit
    contributes to the response, so its length is what the size limit counts.
    """
    units: list[tuple[int, int | None, str]] = []
    for si, section in enumerate(sections):
        if fmt == "markdown":
            hashes = "#" * min(2 + _depth(section), 6)
            units.append((si, None, f"{hashes} {section.get('title', '')}"))
        for bi, block in enumerate(section.get("content") or []):
            if fmt == "markdown":
                text = block_to_markdown(block)
                if text:
                    units.append((si, bi, text))
            else:
                units.append((si, bi, json.dumps(slim_block(block), separators=(",", ":"))))
    return units


Unit = tuple[int, int | None, str]


def _dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"))


def shrink_block_json(text: str, budget: int) -> str | None:
    """Re-serialise one block so it fits ``budget`` characters and is still valid JSON.

    Cutting the JSON string itself would leave something nobody can parse. A table
    loses trailing rows (``truncated_rows`` says how many), a block with text has its
    text cut (``truncated`` is set), a list loses trailing items. ``None`` means the
    block cannot be made to fit, and the caller leaves it out.
    """
    block = json.loads(text)
    if len(text) <= budget:
        return text
    kind = block.get("type")
    if kind == "table" and isinstance(block.get("rows"), list):
        rows = block["rows"]
        lo, hi = 0, len(rows)
        while lo < hi:  # most rows that still fit
            mid = (lo + hi + 1) // 2
            if (
                len(_dumps({**block, "rows": rows[:mid], "truncated_rows": len(rows) - mid}))
                <= budget
            ):
                lo = mid
            else:
                hi = mid - 1
        shrunk = _dumps({**block, "rows": rows[:lo], "truncated_rows": len(rows) - lo})
        return shrunk if len(shrunk) <= budget else None
    if kind == "list" and isinstance(block.get("items"), list):
        items = block["items"]
        for keep in range(len(items), -1, -1):
            candidate = _dumps({**block, "items": items[:keep], "truncated": True})
            if len(candidate) <= budget:
                return candidate
        return None
    for key in ("text", "caption"):
        if isinstance(block.get(key), str):
            value = block[key]
            lo, hi = 0, len(value)
            while lo < hi:  # longest prefix that still fits once JSON-escaped
                mid = (lo + hi + 1) // 2
                if len(_dumps({**block, key: value[:mid], "truncated": True})) <= budget:
                    lo = mid
                else:
                    hi = mid - 1
            cut = _dumps({**block, key: value[:lo], "truncated": True})
            return cut if lo > 0 and len(cut) <= budget else None
    return None


def take_within(
    units: list[Unit],
    max_chars: int,
    sep_len: int = 2,
    fit_first: Callable[[str, int], str | None] | None = None,
) -> tuple[list[Unit], int, bool]:
    """The longest prefix of ``units`` that fits ``max_chars``, with the total size and
    whether anything was left out.

    The first *block* is always attempted, so one oversized paragraph or table does not leave
    the caller with a bare section heading, or nothing at all: plain text is cut at the
    limit; with ``fit_first`` (JSON units, which must stay parseable) that function shrinks
    it, and a unit it cannot shrink is left out. A heading unit has ``None`` as its block
    index and never counts as the first block.
    """
    total = sum(len(u[2]) + sep_len for u in units)
    kept: list[Unit] = []
    used = 0
    truncated = False
    have_block = False
    for si, bi, text in units:
        cost = len(text) + sep_len
        if used + cost <= max_chars:
            kept.append((si, bi, text))
            used += cost
            have_block = have_block or bi is not None
            continue
        truncated = True
        if bi is not None and not have_block:
            budget = max(max_chars - used - sep_len, 0)
            fitted = fit_first(text, budget) if fit_first else text[:budget]
            if fitted:
                kept.append((si, bi, fitted))
        break
    return kept, total, truncated


def units_to_markdown(units: list[tuple[int, int | None, str]]) -> str:
    return "\n\n".join(u[2] for u in units)


def units_to_sections(sections: list[dict[str, Any]], units: list[Unit]) -> list[dict[str, Any]]:
    """Rebuild the structured sections from the kept block units.

    Each block is parsed back from its unit's text, not copied from ``sections``: the text
    is what was measured against the size limit, and it may be a shrunken version of the
    original."""
    out: dict[int, dict[str, Any]] = {}
    for si, bi, text in units:
        if bi is None:
            continue
        section = sections[si]
        entry = out.setdefault(
            si,
            {
                "title": section.get("title", ""),
                "section_type": section.get("section_type", ""),
                "section_path": section.get("section_path", ""),
                "content": [],
            },
        )
        entry["content"].append(json.loads(text))
    return [out[i] for i in sorted(out)]


def outline(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Titles, block-type counts and text size per section: enough to decide what to ask for."""
    result = []
    for section in sections:
        blocks = section.get("content") or []
        result.append(
            {
                "title": section.get("title", ""),
                "section_type": section.get("section_type", ""),
                "blocks": dict(Counter(b.get("type", "") for b in blocks)),
                "chars": sum(len(block_to_markdown(b)) for b in blocks),
            }
        )
    return result
