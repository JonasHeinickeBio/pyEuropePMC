"""
The blocks of a section, in document order, for the flat renderings.

``to_plaintext()``, ``to_markdown()`` and ``get_full_text_sections()`` each
collected a section's ``<p>`` elements and not much else. Anything that is not
a paragraph reached them only if a ``<p>`` happened to sit inside it:

- a ``<fig>`` placed directly in a section lost its label and caption title,
  since only the caption's ``<p>`` was found;
- a ``<table-wrap>`` lost its label and every cell not wrapped in a ``<p>`` -
  most cells - in ``to_markdown()`` and ``get_full_text_sections()``;
- a ``<preformat>`` code listing, a ``<def-list>`` and a supplementary item's
  title reached none of the three.

And what each rendering did find came out of document order: to_plaintext()
emitted a section's paragraphs, then its lists, then its tables.

:func:`iter_flat_blocks` walks a container once, in order, and hands every
element to exactly one kind of block, so a caption or cell is rendered once and
by the block that owns it. A table, figure, formula, list or listing inside a
``<p>`` cuts the paragraph in two, as it does in the structured blocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import re
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.utils.table_grid import TableGrid, build_table_grid, find_table
from pyeuropepmc.features.fulltext.utils.xml_helpers import BLOCK_LEVEL_TAGS, XMLHelper

#: Elements rendered as a block of their own, by kind - also where they sit
#: inside a ``<p>``, which they then cut in two.
PARAGRAPH_CUTS: dict[str, str] = {
    "list": "list",
    "def-list": "definition_list",
    "table-wrap": "table",
    "table": "table",
    "fig": "figure",
    "disp-formula": "formula",
    "preformat": "code",
    "code": "code",
}

#: Rendered as a block of their own where they stand in a section. Inside a
#: ``<p>`` their text stays in the paragraph, as it always did.
BLOCK_KINDS: dict[str, str] = {
    **PARAGRAPH_CUTS,
    "supplementary-material": "supplementary",
    "media": "supplementary",
}

#: Never rendered by the walk: the caller renders a section's title (and its
#: nested sections); the rest carry no prose.
SKIPPED: frozenset[str] = frozenset(
    {"title", "label", "sec", "ref-list", "object-id", "inline-graphic", "alt-text"}
)


#: The title under which every rendering places the content of
#: ``<floats-group>``: the figures and tables an article keeps outside its body.
FLOATS_TITLE = "Figures and Tables"


@dataclass
class FlatBlock:
    """One block of a section.

    ``text`` is filled for paragraphs only: the text of this run of the
    ``<p>``, which may be all of it or the part between two nested blocks.
    Every other kind is rendered from ``element``.
    """

    kind: str
    element: ET.Element
    text: str = ""


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _raw_text(node: ET.Element, parts: list[str]) -> None:
    """Text of ``node`` into ``parts``, as ``XMLHelper.get_text_content`` walks it."""
    if node.text:
        parts.append(node.text)
    for child in node:
        if not isinstance(child.tag, str):
            if child.tail:
                parts.append(child.tail)
            continue
        block = _local(child.tag) in BLOCK_LEVEL_TAGS
        if block:
            parts.append(" ")
        _raw_text(child, parts)
        if block:
            parts.append(" ")
        if child.tail:
            parts.append(child.tail)


def iter_flat_blocks(container: ET.Element) -> Iterator[FlatBlock]:
    """The blocks ``container`` owns, in document order.

    Stops at a nested ``<sec>``, whose content belongs to that section, and
    descends through any other wrapper - ``<boxed-text>``, ``<disp-quote>``,
    ``<fn-group>`` and the like - so a paragraph inside one is still found.
    """
    for child in container:
        tag = _local(child.tag)
        if not tag or tag in SKIPPED:
            continue
        if tag == "p":
            yield from _paragraph_blocks(child)
        elif tag in BLOCK_KINDS:
            yield FlatBlock(BLOCK_KINDS[tag], child)
        elif tag == "graphic":
            # A graphic can carry a caption of its own; one without is a picture.
            if _child(child, "caption") is not None:
                yield FlatBlock("supplementary", child)
        else:
            yield from iter_flat_blocks(child)


def _paragraph_blocks(paragraph: ET.Element) -> Iterator[FlatBlock]:
    """A ``<p>``, cut wherever a block of its own sits inside it."""
    parts: list[str] = []
    if paragraph.text:
        parts.append(paragraph.text)
    for child in paragraph:
        tag = _local(child.tag)
        if tag in PARAGRAPH_CUTS:
            text = _collapse("".join(parts))
            if text:
                yield FlatBlock("paragraph", paragraph, text)
            parts = []
            yield FlatBlock(PARAGRAPH_CUTS[tag], child)
        elif isinstance(child.tag, str):
            block = tag in BLOCK_LEVEL_TAGS
            if block:
                parts.append(" ")
            _raw_text(child, parts)
            if block:
                parts.append(" ")
        if child.tail:
            parts.append(child.tail)
    text = _collapse("".join(parts))
    if text:
        yield FlatBlock("paragraph", paragraph, text)


# ---------------------------------------------------------------------------
# The parts of each kind of block, shared by every rendering
# ---------------------------------------------------------------------------


def _child(element: ET.Element, tag: str) -> ET.Element | None:
    return next((c for c in element if _local(c.tag) == tag), None)


def label_of(element: ET.Element) -> str:
    return XMLHelper.get_text_content(_child(element, "label"))


def caption_of(element: ET.Element) -> str:
    """The whole caption, its ``<title>`` included."""
    return XMLHelper.get_text_content(_child(element, "caption"))


#: Children of a figure or supplementary item that carry no prose of their own.
_FLOAT_NON_TEXT = frozenset(
    {"label", "caption", "graphic", "media", "alt-text", "long-desc", "object-id", "permissions"}
)


def float_text(element: ET.Element) -> str:
    """A figure or supplementary item as one line: label, caption, then anything else.

    Anything else is what a ``<fig>`` can hold besides its picture - a
    ``<disp-quote>``, an ``<attrib>``, a stray ``<p>``. A supplementary item
    often keeps its caption on a ``<media>`` inside it, which is rendered the
    same way.
    """
    rest = [
        float_text(child) if _local(child.tag) == "media" else XMLHelper.get_text_content(child)
        for child in element
        if isinstance(child.tag, str)
        and (_local(child.tag) == "media" or _local(child.tag) not in _FLOAT_NON_TEXT)
    ]
    parts = [label_of(element), caption_of(element), *rest]
    return " ".join(part for part in parts if part)


def float_parts(element: ET.Element) -> tuple[str, str]:
    """``(label, the rest)`` of a figure or supplementary item."""
    label = label_of(element)
    text = float_text(element)
    if label and text.startswith(label):
        text = text[len(label) :].lstrip()
    return label, text


def formula_text(formula: ET.Element) -> str:
    """A ``<disp-formula>`` as one line of plain text, label last."""
    body = XMLHelper.get_text_content(formula, exclude_tags=frozenset({"label"}))
    return " ".join(part for part in (body, label_of(formula)) if part).strip()


def code_text(element: ET.Element) -> str:
    """A code listing with its line breaks and indentation intact.

    Every other text here is collapsed to single spaces, which turned a
    fourteen-line listing into one line of run-together statements.
    """
    lines = "".join(element.itertext()).expandtabs(4).splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(line.rstrip() for line in lines)


def list_items(element: ET.Element) -> list[str]:
    """The text of each item of a ``<list>``, a nested list included in its item."""
    return [
        text
        for item in element
        if _local(item.tag) == "list-item" and (text := XMLHelper.get_text_content(item))
    ]


def definition_items(element: ET.Element) -> list[tuple[str, str]]:
    """``(term, definition)`` for each ``<def-item>`` of a ``<def-list>``."""
    items: list[tuple[str, str]] = []
    for item in element:
        if _local(item.tag) != "def-item":
            continue
        term = XMLHelper.get_text_content(_child(item, "term"))
        definition = XMLHelper.get_text_content(_child(item, "def"))
        if term or definition:
            items.append((term, definition))
    return items


@dataclass
class TableParts:
    """What a table renders: its heading line, its layout, and the rest."""

    label: str
    caption: str
    grid: TableGrid | None
    footer: str
    other: str


#: Children of a ``<table-wrap>`` - or of a bare ``<table>`` - that a table
#: rendering already covers.
_TABLE_OWN = frozenset(
    {
        "label",
        "caption",
        "table",
        "alternatives",
        "table-wrap-foot",
        "object-id",
        "graphic",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "colgroup",
        "col",
    }
)


def table_parts(element: ET.Element) -> TableParts:
    table = find_table(element)
    footers = [
        XMLHelper.get_text_content(child)
        for child in element
        if _local(child.tag) == "table-wrap-foot"
    ]
    other = [
        XMLHelper.get_text_content(child)
        for child in element
        if isinstance(child.tag, str) and _local(child.tag) not in _TABLE_OWN
    ]
    return TableParts(
        label=label_of(element) if _local(element.tag) != "table" else "",
        caption=caption_of(element),
        grid=build_table_grid(table) if table is not None else None,
        footer=" ".join(f for f in footers if f),
        other=" ".join(o for o in other if o),
    )


def plain_text(block: FlatBlock) -> str:
    """A block as plain text: the form ``to_plaintext()`` and sections share."""
    kind = block.kind
    if kind == "paragraph":
        return block.text
    if kind in ("figure", "supplementary"):
        return float_text(block.element)
    if kind == "formula":
        return formula_text(block.element)
    if kind == "code":
        return code_text(block.element)
    if kind == "list":
        return "\n".join(
            f"{marker}{item}" for marker, item in list_markers(block.element, numbered="{}. ")
        )
    if kind == "definition_list":
        return "\n".join(
            f"{term}: {definition}" if term and definition else term or definition
            for term, definition in definition_items(block.element)
        )
    if kind == "table":
        return table_plain_text(block.element)
    return XMLHelper.get_text_content(block.element)


#: ``list-type`` values that number their items with digits.
_ORDERED_LIST_TYPES = frozenset({"order", "ordered"})


def list_markers(element: ET.Element, numbered: str, bullet: str = "• ") -> list[tuple[str, str]]:
    """``(marker, text)`` for each item of a ``<list>``.

    An item with its own ``<label>`` ("a)", "(i)") already starts with it, so
    it gets no marker of ours.
    """
    ordered = element.get("list-type", "") in _ORDERED_LIST_TYPES
    result: list[tuple[str, str]] = []
    number = 0
    for item in element:
        if _local(item.tag) != "list-item":
            continue
        text = XMLHelper.get_text_content(item)
        if not text:
            continue
        number += 1
        if _child(item, "label") is not None:
            marker = ""
        elif ordered:
            marker = numbered.format(number)
        else:
            marker = bullet
        result.append((marker, text))
    return result


def table_plain_text(element: ET.Element) -> str:
    """A table as plain text: heading line, one line per row, then the footer."""
    parts = table_parts(element)
    lines: list[str] = []
    if parts.label or parts.caption:
        heading = " ".join(p for p in (parts.label, parts.caption) if p)
        lines.append(heading if parts.label else f"Table: {parts.caption}")
    if parts.grid is not None:
        for row in parts.grid.rows:
            cells = [cell for cell in row if cell]
            if cells:
                lines.append(" | ".join(cells))
    lines.extend(p for p in (parts.footer, parts.other) if p)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

#: Characters that change what a CommonMark or GFM renderer does with text
#: wherever they stand. ``$`` is here because GitHub renders ``$...$`` as math.
_MARKDOWN_INLINE = re.compile(r"([\\`*_\[\]<>~|$])")

#: Characters that change the meaning of a line only at its start.
_MARKDOWN_LINE_START = re.compile(r"^(\s*)([#+\-=]|\d+(?=[.)](?:\s|$)))")


def escape_markdown(text: str) -> str:
    """Escape ``text`` so a Markdown renderer shows it as written.

    ``to_markdown()`` escaped nothing, so "DRB1*0402 ... DQB1*0503" opened an
    emphasis that ran to the next asterisk, and "<node>" was passed through as
    an HTML tag: 49 of PMC1764484's 127 body sentences rendered as something
    other than the article's text.
    """
    escaped = _MARKDOWN_INLINE.sub(r"\\\1", text)
    match = _MARKDOWN_LINE_START.match(escaped)
    if match:
        lead, token = match.group(1), match.group(2)
        if token.isdigit():
            # "1. Introduction" must not become an ordered list.
            rest = escaped[len(lead) + len(token) :]
            escaped = f"{lead}{token}\\{rest}"
        else:
            escaped = f"{lead}\\{escaped[len(lead) :]}"
    return escaped


def code_fence(code: str) -> str:
    """A fence longer than any run of backticks inside ``code``."""
    longest = max((len(run) for run in re.findall(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)


def markdown_table(grid: TableGrid) -> str:
    """A GFM pipe table. A table without a header row gets an empty one."""
    if not grid.width:
        return ""

    def cell(text: str) -> str:
        return escape_markdown(" ".join(text.split())) or " "

    header = grid.header_labels() if grid.header_row_count else [""] * grid.width
    lines = [
        "| " + " | ".join(cell(text) for text in header) + " |",
        "|" + "|".join(" --- " for _ in range(grid.width)) + "|",
    ]
    lines.extend("| " + " | ".join(cell(text) for text in row) + " |" for row in grid.body_rows)
    return "\n".join(lines)
