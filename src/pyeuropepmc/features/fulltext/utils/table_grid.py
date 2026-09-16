"""
Table layout for JATS tables: rows, header rows and spanning cells.

JATS tables follow the XHTML table model. A cell's ``colspan`` and ``rowspan``
decide which columns it occupies, and a cell in a later row is placed in the
first column no earlier cell still covers. Reading cells in document order and
ignoring both attributes - which is what every extractor here did - shifts every
cell after a spanning one into the wrong column. In PMC12311175's Table 4 each
drug's name and mechanism span every row of its trials - up to 40 - so 110 of
the table's 120 body rows came back two cells short, their values two columns
left of their headers. PMC1764484's Table 4 groups its columns under two
``colspan="3"`` header cells, whose labels came back as two strings for seven
columns.

:func:`build_table_grid` places the cells, and every table output in the
package reads the result: :meth:`TableParser.extract_tables`, the structured
``table`` block, and the plain-text and Markdown renderings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

#: The widest table the grid will lay out. A ``colspan`` that would reach past
#: it is clipped: no article table comes near, and a corrupt or hostile
#: ``colspan="100000"`` must not allocate a row of that width for every row.
MAX_COLUMNS = 256

_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _span(value: str | None) -> int:
    """A ``colspan``/``rowspan`` value; anything unusable counts as 1."""
    try:
        number = int((value or "1").strip())
    except ValueError:
        return 1
    return number if number >= 0 else 1


@dataclass
class GridCell:
    """One ``<td>`` or ``<th>``, placed on the grid.

    Parameters
    ----------
    element : ET.Element
        The cell element.
    row, column : int
        The top-left grid position the cell occupies.
    rowspan, colspan : int
        How many rows and columns it covers, after clipping to the table.
    header : bool
        Whether the cell belongs to a header row.
    text : str
        The cell's text. A cell whose only content is an image holds a
        ``[graphic: <file>]`` reference instead of the empty string.
    graphics : list[str]
        File references of every ``<graphic>`` or ``<inline-graphic>`` in it.
    """

    element: ET.Element
    row: int
    column: int
    rowspan: int
    colspan: int
    header: bool
    text: str
    graphics: list[str] = field(default_factory=list)


@dataclass
class TableGrid:
    """A table laid out on a rectangular grid.

    ``rows`` has one list per ``<tr>``, each ``width`` long. A spanning cell's
    text stands at its top-left position; the other positions it covers hold
    ``""``. Header rows come first, and ``header_row_count`` says how many
    there are.
    """

    cells: list[GridCell]
    rows: list[list[str]]
    header_row_count: int
    width: int
    covering: dict[tuple[int, int], GridCell] = field(default_factory=dict, repr=False)

    def spans(self) -> list[dict[str, int]]:
        """Every cell covering more than one position, as ``row``/``column``/span dicts."""
        return [
            {
                "row": cell.row,
                "column": cell.column,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
            }
            for cell in self.cells
            if cell.rowspan > 1 or cell.colspan > 1
        ]

    def cell_graphics(self) -> list[dict[str, object]]:
        """Images inside cells, as ``row``/``column``/``uri`` dicts."""
        return [
            {"row": cell.row, "column": cell.column, "uri": uri}
            for cell in self.cells
            for uri in cell.graphics
        ]

    def header_labels(self) -> list[str]:
        """One label per column, combined from every header row.

        A header cell spanning several columns labels each of them, and the
        rows are joined top to bottom with " / ": a two-row header of
        "Inhibition" over "DAT" and "NET" gives "Inhibition / DAT" and
        "Inhibition / NET". Empty when the table has no header row.
        """
        if not self.header_row_count:
            return []
        labels: list[str] = []
        for column in range(self.width):
            parts: list[str] = []
            for row in range(self.header_row_count):
                cell = self.covering.get((row, column))
                text = cell.text if cell is not None else ""
                if text and (not parts or parts[-1] != text):
                    parts.append(text)
            labels.append(" / ".join(parts))
        return labels

    @property
    def header_rows(self) -> list[list[str]]:
        return self.rows[: self.header_row_count]

    @property
    def body_rows(self) -> list[list[str]]:
        return self.rows[self.header_row_count :]


def find_table(container: ET.Element) -> ET.Element | None:
    """The first ``<table>`` in ``container``, or ``container`` itself if it is one."""
    if _local(container.tag) == "table":
        return container
    for element in container.iter():
        if _local(element.tag) == "table":
            return element
    return None


def _table_rows(table: ET.Element) -> list[tuple[ET.Element, bool, int]]:
    """``(tr, in_thead, group)`` for every row of ``table``, in document order.

    Rows inside a cell belong to a nested table and are not this table's.
    ``group`` numbers the row group (``<thead>``, ``<tbody>``, ``<tfoot>``, or
    rows placed directly in the table), which bounds how far a rowspan reaches.
    """
    rows: list[tuple[ET.Element, bool, int]] = []
    group = 0
    loose = False
    for child in table:
        tag = _local(child.tag)
        if tag in ("thead", "tbody", "tfoot"):
            group += 1
            loose = False
            rows.extend((tr, tag == "thead", group) for tr in child if _local(tr.tag) == "tr")
        elif tag == "tr":
            if not loose:
                group += 1
                loose = True
            rows.append((child, False, group))
    return rows


def _graphics(cell: ET.Element) -> list[str]:
    return [
        str(element.get(_XLINK_HREF) or element.get("href") or "")
        for element in cell.iter()
        if _local(element.tag) in ("graphic", "inline-graphic")
        and (element.get(_XLINK_HREF) or element.get("href"))
    ]


def build_table_grid(
    table: ET.Element,
    cell_text: Callable[[ET.Element], str] | None = None,
) -> TableGrid:
    """Lay out ``table`` (a ``<table>``) on a rectangular grid.

    Parameters
    ----------
    table : ET.Element
        The ``<table>`` element.
    cell_text : callable, optional
        Returns the text of one cell. Defaults to
        :meth:`XMLHelper.get_text_content`.

    Returns
    -------
    TableGrid
        The placed cells and the grid of their text.
    """
    text_of = cell_text or XMLHelper.get_text_content
    table_rows = _table_rows(table)
    group_end: dict[int, int] = {}
    for index, (_tr, _thead, group) in enumerate(table_rows):
        group_end[group] = index

    covering: dict[tuple[int, int], GridCell] = {}
    cells: list[GridCell] = []
    width = 0

    for row, (tr, in_thead, group) in enumerate(table_rows):
        column = 0
        for element in tr:
            tag = _local(element.tag)
            if tag not in ("td", "th"):
                continue
            while (row, column) in covering and column < MAX_COLUMNS:
                column += 1
            if column >= MAX_COLUMNS:
                break
            colspan = min(max(_span(element.get("colspan")), 1), MAX_COLUMNS - column)
            rowspan = _span(element.get("rowspan"))
            last_row = group_end[group]
            # rowspan="0" reaches to the end of the row group, as in HTML.
            rowspan = last_row - row + 1 if rowspan == 0 else min(rowspan, last_row - row + 1)

            graphics = _graphics(element)
            text = text_of(element).strip()
            if not text and graphics:
                text = " ".join(f"[graphic: {uri}]" for uri in graphics)

            cell = GridCell(
                element=element,
                row=row,
                column=column,
                rowspan=rowspan,
                colspan=colspan,
                header=in_thead or tag == "th",
                text=text,
                graphics=graphics,
            )
            cells.append(cell)
            for covered_row in range(row, row + rowspan):
                for covered_column in range(column, column + colspan):
                    covering.setdefault((covered_row, covered_column), cell)
            column += colspan
            width = max(width, column)

    grid_rows = [["" for _ in range(width)] for _ in table_rows]
    for cell in cells:
        grid_rows[cell.row][cell.column] = cell.text

    return TableGrid(
        cells=cells,
        rows=grid_rows,
        header_row_count=_header_row_count(table_rows, cells),
        width=width,
        covering=covering,
    )


def _header_row_count(
    table_rows: list[tuple[ET.Element, bool, int]], cells: list[GridCell]
) -> int:
    """How many leading rows are header rows.

    The rows of a ``<thead>``; failing that, leading rows made only of
    ``<th>``, which is how a table without a ``<thead>`` marks its header.
    """
    count = 0
    for _tr, in_thead, _group in table_rows:
        if not in_thead:
            break
        count += 1
    if count:
        return count
    tags_by_row: dict[int, set[str]] = {}
    for cell in cells:
        tags_by_row.setdefault(cell.row, set()).add(_local(cell.element.tag))
    for index in range(len(table_rows)):
        if tags_by_row.get(index) != {"th"}:
            break
        count += 1
    # A table made of nothing but <th> has no body for a header to label.
    return count if count < len(table_rows) else 0
