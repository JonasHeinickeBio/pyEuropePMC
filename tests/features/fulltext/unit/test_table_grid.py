"""Unit tests for pyeuropepmc.features.fulltext.utils.table_grid."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.utils.table_grid import (
    MAX_COLUMNS,
    build_table_grid,
    find_table,
)

pytestmark = [pytest.mark.unit]


def _table(xml: str) -> ET.Element:
    return DefusedET.fromstring(xml)


class TestPlacement:
    def test_plain_table(self):
        grid = build_table_grid(
            _table(
                "<table><tbody><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr>"
                "</tbody></table>"
            )
        )
        assert grid.rows == [["a", "b"], ["c", "d"]]
        assert grid.width == 2
        assert grid.spans() == []

    def test_rowspan_keeps_later_cells_in_their_columns(self):
        """Ignoring rowspan moved "2" and "y" one column left, under the wrong header."""
        grid = build_table_grid(
            _table(
                "<table><tbody>"
                '<tr><td rowspan="2">A</td><td>1</td><td>x</td></tr>'
                "<tr><td>2</td><td>y</td></tr>"
                "</tbody></table>"
            )
        )
        assert grid.rows == [["A", "1", "x"], ["", "2", "y"]]
        assert grid.spans() == [{"row": 0, "column": 0, "rowspan": 2, "colspan": 1}]

    def test_colspan(self):
        grid = build_table_grid(
            _table(
                "<table><tbody>"
                '<tr><td colspan="2">wide</td><td>c</td></tr>'
                "<tr><td>a</td><td>b</td><td>c</td></tr>"
                "</tbody></table>"
            )
        )
        assert grid.rows == [["wide", "", "c"], ["a", "b", "c"]]

    def test_rowspan_and_colspan_together(self):
        grid = build_table_grid(
            _table(
                "<table><tbody>"
                '<tr><td rowspan="2" colspan="2">X</td><td>1</td></tr>'
                "<tr><td>2</td></tr>"
                "<tr><td>a</td><td>b</td><td>c</td></tr>"
                "</tbody></table>"
            )
        )
        assert grid.rows == [["X", "", "1"], ["", "", "2"], ["a", "b", "c"]]

    def test_short_row_is_padded_to_the_table_width(self):
        grid = build_table_grid(
            _table(
                "<table><tbody><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></tbody></table>"
            )
        )
        assert grid.rows == [["a", "b"], ["c", ""]]

    def test_rowspan_does_not_reach_past_its_row_group(self):
        grid = build_table_grid(
            _table(
                '<table><thead><tr><th rowspan="5">H</th><th>I</th></tr></thead>'
                "<tbody><tr><td>a</td><td>b</td></tr></tbody></table>"
            )
        )
        assert grid.rows == [["H", "I"], ["a", "b"]]
        assert grid.spans() == []

    def test_rowspan_zero_reaches_the_end_of_the_group(self):
        grid = build_table_grid(
            _table(
                "<table><tbody>"
                '<tr><td rowspan="0">A</td><td>1</td></tr>'
                "<tr><td>2</td></tr><tr><td>3</td></tr>"
                "</tbody></table>"
            )
        )
        assert [row[1] for row in grid.rows] == ["1", "2", "3"]
        assert grid.cells[0].rowspan == 3

    @pytest.mark.parametrize("value", ["", "abc", "-2"])
    def test_unusable_span_counts_as_one(self, value):
        grid = build_table_grid(
            _table(
                f'<table><tbody><tr><td colspan="{value}">a</td><td>b</td></tr></tbody></table>'
            )
        )
        assert grid.rows == [["a", "b"]]

    def test_a_hostile_colspan_is_clipped(self):
        grid = build_table_grid(
            _table('<table><tbody><tr><td colspan="100000">a</td></tr></tbody></table>')
        )
        assert grid.width == MAX_COLUMNS

    def test_rows_of_a_nested_table_are_not_this_tables(self):
        grid = build_table_grid(
            _table(
                "<table><tbody><tr><td>outer"
                "<table><tbody><tr><td>inner</td></tr></tbody></table>"
                "</td></tr></tbody></table>"
            )
        )
        assert len(grid.rows) == 1

    def test_rows_directly_in_the_table(self):
        grid = build_table_grid(_table("<table><tr><td>a</td></tr><tr><td>b</td></tr></table>"))
        assert grid.rows == [["a"], ["b"]]


class TestHeaders:
    def test_thead_rows_are_header_rows_whatever_their_cells_are(self):
        """PMC1764484 writes every header cell as <td>; all five headers were []."""
        grid = build_table_grid(
            _table(
                "<table><thead><tr><td>Rank</td><td>Peptide</td></tr></thead>"
                "<tbody><tr><td>1</td><td>Dsg3</td></tr></tbody></table>"
            )
        )
        assert grid.header_row_count == 1
        assert grid.header_labels() == ["Rank", "Peptide"]
        assert grid.body_rows == [["1", "Dsg3"]]

    def test_leading_th_rows_without_thead(self):
        grid = build_table_grid(
            _table("<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>")
        )
        assert grid.header_row_count == 1
        assert grid.header_labels() == ["A", "B"]

    def test_a_table_of_only_th_has_no_header(self):
        grid = build_table_grid(_table("<table><tr><th>A</th></tr><tr><th>B</th></tr></table>"))
        assert grid.header_row_count == 0

    def test_multi_row_header_labels_combine_top_to_bottom(self):
        """PMC1764484 Table 4: two colspan="3" groups over their sub-headers."""
        grid = build_table_grid(
            _table(
                "<table><thead>"
                '<tr><td>Rank</td><td colspan="2">DQB1*0503</td><td colspan="2">DRB1*0402</td></tr>'
                '<tr><td/><td colspan="2"><hr/></td><td colspan="2"><hr/></td></tr>'
                "<tr><td/><td>Peptide</td><td>BE</td><td>Peptide</td><td>BE</td></tr>"
                "</thead><tbody><tr><td>1</td><td>a</td><td>b</td><td>c</td><td>d</td></tr>"
                "</tbody></table>"
            )
        )
        assert grid.header_row_count == 3
        assert grid.header_labels() == [
            "Rank",
            "DQB1*0503 / Peptide",
            "DQB1*0503 / BE",
            "DRB1*0402 / Peptide",
            "DRB1*0402 / BE",
        ]

    def test_a_header_spanning_rows_is_not_repeated_in_its_label(self):
        grid = build_table_grid(
            _table(
                "<table><thead>"
                '<tr><th rowspan="2">Name</th><th colspan="2">Score</th></tr>'
                "<tr><th>A</th><th>B</th></tr>"
                "</thead><tbody><tr><td>x</td><td>1</td><td>2</td></tr></tbody></table>"
            )
        )
        assert grid.header_labels() == ["Name", "Score / A", "Score / B"]


class TestCellContent:
    def test_image_only_cell_references_its_graphic(self):
        """PMC5393345 draws each compound's structure as an image in a cell."""
        grid = build_table_grid(
            _table(
                '<table xmlns:xlink="http://www.w3.org/1999/xlink"><tbody><tr>'
                "<td>cocaine</td>"
                '<td><graphic xlink:href="nihms850763t1.jpg"/></td>'
                "</tr></tbody></table>"
            )
        )
        assert grid.rows == [["cocaine", "[graphic: nihms850763t1.jpg]"]]
        assert grid.cell_graphics() == [{"row": 0, "column": 1, "uri": "nihms850763t1.jpg"}]

    def test_text_beside_a_graphic_is_kept_as_it_is(self):
        grid = build_table_grid(
            _table(
                '<table xmlns:xlink="http://www.w3.org/1999/xlink"><tbody><tr>'
                '<td>see <inline-graphic xlink:href="i.gif"/></td></tr></tbody></table>'
            )
        )
        assert grid.rows == [["see"]]
        assert grid.cell_graphics() == [{"row": 0, "column": 0, "uri": "i.gif"}]

    def test_custom_cell_text(self):
        grid = build_table_grid(
            _table("<table><tbody><tr><td>a</td></tr></tbody></table>"),
            cell_text=lambda cell: "X",
        )
        assert grid.rows == [["X"]]


class TestFindTable:
    def test_inside_alternatives(self):
        wrap = _table(
            "<table-wrap><alternatives><graphic/><table><tr><td>a</td></tr></table>"
            "</alternatives></table-wrap>"
        )
        table = find_table(wrap)
        assert table is not None and table.tag == "table"

    def test_the_element_itself(self):
        table = _table("<table/>")
        assert find_table(table) is table

    def test_image_only_table_wrap(self):
        assert find_table(_table("<table-wrap><graphic/></table-wrap>")) is None
