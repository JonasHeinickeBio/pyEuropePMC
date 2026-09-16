"""Unit tests for pyeuropepmc.features.fulltext.utils.flat_blocks."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.utils.flat_blocks import (
    FlatBlock,
    code_fence,
    code_text,
    escape_markdown,
    float_parts,
    iter_flat_blocks,
    list_markers,
    markdown_table,
    plain_text,
    table_plain_text,
)
from pyeuropepmc.features.fulltext.utils.table_grid import build_table_grid

pytestmark = [pytest.mark.unit]

XLINK = 'xmlns:xlink="http://www.w3.org/1999/xlink"'


def _xml(text: str) -> ET.Element:
    return DefusedET.fromstring(text)


def _kinds(xml: str) -> list[tuple[str, str]]:
    return [(b.kind, b.text) for b in iter_flat_blocks(_xml(xml))]


class TestWalk:
    def test_blocks_come_in_document_order(self):
        """to_plaintext() emitted paragraphs, then lists, then tables."""
        xml = (
            "<sec><title>T</title><p>one</p>"
            "<table-wrap><table><tr><td>c</td></tr></table></table-wrap>"
            "<p>two</p><list><list-item><p>i</p></list-item></list><p>three</p></sec>"
        )
        assert [k for k, _ in _kinds(xml)] == [
            "paragraph",
            "table",
            "paragraph",
            "list",
            "paragraph",
        ]

    def test_a_nested_section_is_not_the_sections_own(self):
        xml = "<sec><p>own</p><sec><title>Sub</title><p>theirs</p></sec></sec>"
        assert _kinds(xml) == [("paragraph", "own")]

    def test_wrappers_are_walked_through(self):
        xml = "<sec><boxed-text><p>boxed</p></boxed-text><fn-group><fn><p>note</p></fn></fn-group></sec>"
        assert _kinds(xml) == [("paragraph", "boxed"), ("paragraph", "note")]

    def test_a_block_inside_a_paragraph_cuts_it(self):
        xml = (
            "<sec><p>models of the form <disp-formula>x=1</disp-formula> with state y, and "
            "<fig><label>Fig. 1</label></fig> more.</p></sec>"
        )
        assert _kinds(xml) == [
            ("paragraph", "models of the form"),
            ("formula", ""),
            ("paragraph", "with state y, and"),
            ("figure", ""),
            ("paragraph", "more."),
        ]

    def test_supplementary_material_inside_a_paragraph_stays_in_it(self):
        xml = "<sec><p>See <supplementary-material><label>S1</label></supplementary-material> here.</p></sec>"
        assert _kinds(xml) == [("paragraph", "See S1 here.")]

    def test_supplementary_material_in_a_section_is_a_block(self):
        xml = "<sec><supplementary-material><label>S1</label></supplementary-material></sec>"
        assert [k for k, _ in _kinds(xml)] == ["supplementary"]

    def test_a_graphic_is_a_block_only_when_it_has_a_caption(self):
        xml = f"<sec {XLINK}><graphic xlink:href='a.jpg'/><graphic><caption><p>Map</p></caption></graphic></sec>"
        blocks = list(iter_flat_blocks(_xml(xml)))
        assert [b.kind for b in blocks] == ["supplementary"]
        assert plain_text(blocks[0]) == "Map"

    def test_inline_spacing_follows_the_source(self):
        xml = "<sec><p>PM<sub>2.5</sub> and <italic>E. coli</italic>.</p></sec>"
        assert _kinds(xml) == [("paragraph", "PM2.5 and E. coli.")]


class TestPlainText:
    def test_figure_keeps_label_and_caption_title(self):
        """A figure directly in a section lost both: only the caption's <p> was found."""
        xml = (
            "<fig><label>Figure 1</label><caption><title>Design.</title><p>The model.</p>"
            "</caption><graphic/></fig>"
        )
        assert plain_text(FlatBlock("figure", _xml(xml))) == "Figure 1 Design. The model."

    def test_supplementary_caption_on_a_nested_media(self):
        xml = (
            "<supplementary-material><label>S1 Data</label>"
            "<media><caption><title>Raw counts.</title></caption></media></supplementary-material>"
        )
        assert float_parts(_xml(xml)) == ("S1 Data", "Raw counts.")

    def test_formula_puts_its_label_last(self):
        xml = "<disp-formula><label>(1)</label>x=1</disp-formula>"
        assert plain_text(FlatBlock("formula", _xml(xml))) == "x=1 (1)"

    def test_table_with_label_spans_and_footer(self):
        xml = (
            "<table-wrap><label>Table 1</label><caption><p>Doses.</p></caption><table>"
            '<thead><tr><th>Name</th><th colspan="2">Dose</th></tr></thead>'
            '<tbody><tr><td rowspan="2">A</td><td>1</td><td>2</td></tr><tr><td>3</td><td>4</td></tr>'
            "</tbody></table><table-wrap-foot><p>In mg.</p></table-wrap-foot></table-wrap>"
        )
        assert table_plain_text(_xml(xml)) == (
            "Table 1 Doses.\nName | Dose\nA | 1 | 2\n3 | 4\nIn mg."
        )

    def test_table_without_label_keeps_the_old_heading(self):
        xml = "<table><caption><p>Sample</p></caption><tr><td>a</td></tr></table>"
        assert table_plain_text(_xml(xml)) == "Table: Sample\na"

    def test_definition_list(self):
        xml = "<def-list><def-item><term>BMI</term><def><p>body mass index</p></def></def-item></def-list>"
        assert plain_text(FlatBlock("definition_list", _xml(xml))) == "BMI: body mass index"


class TestLists:
    def test_bullets_and_numbers(self):
        bullet = _xml(
            "<list><list-item><p>a</p></list-item><list-item><p>b</p></list-item></list>"
        )
        ordered = _xml('<list list-type="order"><list-item><p>a</p></list-item></list>')
        assert list_markers(bullet, numbered="{}. ") == [("• ", "a"), ("• ", "b")]
        assert list_markers(ordered, numbered="{}. ") == [("1. ", "a")]

    def test_an_item_with_its_own_label_gets_no_marker(self):
        element = _xml("<list><list-item><label>(i)</label><p>first</p></list-item></list>")
        assert list_markers(element, numbered="{}. ") == [("", "(i) first")]


class TestCode:
    def test_line_breaks_and_indentation_survive(self):
        xml = (
            '<preformat xml:space="preserve">\n1    op = Operator(\n2        name="lv",\n'
            "3    )\n</preformat>"
        )
        assert code_text(_xml(xml)) == '1    op = Operator(\n2        name="lv",\n3    )'

    def test_fence_is_longer_than_any_backtick_run(self):
        assert code_fence("plain") == "```"
        assert code_fence("a ```` b") == "`````"


class TestEscapeMarkdown:
    @pytest.mark.parametrize(
        ("text", "escaped"),
        [
            ("DRB1*0402 and DQB1*0503", "DRB1\\*0402 and DQB1\\*0503"),
            ("<node>/<op>", "\\<node\\>/\\<op\\>"),
            ("snake_case and `tick`", "snake\\_case and \\`tick\\`"),
            ("[1] and ~x~ and a|b and $5", "\\[1\\] and \\~x\\~ and a\\|b and \\$5"),
            ("C:\\path", "C:\\\\path"),
            ("# not a heading", "\\# not a heading"),
            ("- not a list", "\\- not a list"),
            ("+ not a list", "\\+ not a list"),
            ("1. Introduction", "1\\. Introduction"),
            ("2) Methods", "2\\) Methods"),
            ("2019 was a year", "2019 was a year"),
            ("plain text.", "plain text."),
        ],
    )
    def test_escapes(self, text, escaped):
        assert escape_markdown(text) == escaped


class TestMarkdownTable:
    def test_header_labels_and_escaped_cells(self):
        table = _xml(
            "<table><thead><tr><th>Allele</th><th>n</th></tr></thead>"
            "<tbody><tr><td>DRB1*0402</td><td>a|b</td></tr></tbody></table>"
        )
        assert markdown_table(build_table_grid(table)) == (
            "| Allele | n |\n| --- | --- |\n| DRB1\\*0402 | a\\|b |"
        )

    def test_a_table_without_header_gets_an_empty_one(self):
        table = _xml("<table><tr><td>a</td><td>b</td></tr></table>")
        assert markdown_table(build_table_grid(table)) == "|   |   |\n| --- | --- |\n| a | b |"

    def test_an_empty_table(self):
        assert markdown_table(build_table_grid(_xml("<table/>"))) == ""
