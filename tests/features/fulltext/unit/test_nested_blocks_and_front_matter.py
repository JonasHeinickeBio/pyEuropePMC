"""Tables and figures nested in a paragraph, and front matter in structured output.

Reported against 2.2.1:

- A <table-wrap> or <fig> inside a <p> was folded into the paragraph block's
  text, with nothing between its cells and no table or figure block of its own,
  so a consumer could not recover the rows or the caption.
- The article title and the abstract came back from the structured sections
  with section_type "body", so filtering on it could not keep them out.
- to_plaintext() ran the cells of such a table together; 2.0.0 kept them apart.
"""

import xml.etree.ElementTree as ET

from pyeuropepmc.features.fulltext.extensions.content_blocks import (
    ContentBlock,
    ContentBlockExtractor,
    ContentBlockType,
    InlineElementType,
)
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

TABLE = (
    '<table-wrap id="t1"><label>Table 1</label>'
    "<caption><title>Doses</title><p>Per group.</p></caption>"
    "<table><thead><tr><th>Group</th><th>Dose</th></tr></thead>"
    "<tbody><tr><td>A</td><td>10 mg</td></tr><tr><td>B</td><td>20 mg</td></tr></tbody>"
    "</table></table-wrap>"
)

FIGURE = (
    '<fig id="f1"><label>Fig. 1</label>'
    "<caption><title>Mechanism</title><p>Binding in vitro.</p></caption>"
    '<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="f1.jpg"/></fig>'
)

PARAGRAPH = ContentBlockType.PARAGRAPH
TABLE_BLOCK = ContentBlockType.TABLE
FIGURE_BLOCK = ContentBlockType.FIGURE


def _article(section_body: str) -> str:
    return (
        "<article><front><article-meta>"
        "<title-group><article-title>A study</article-title></title-group>"
        "<abstract><p>Short abstract.</p></abstract>"
        "</article-meta></front>"
        f"<body><sec><title>Results</title>{section_body}</sec></body></article>"
    )


def _extractor() -> ContentBlockExtractor:
    return ContentBlockExtractor(ET.fromstring("<article/>"))


def _paragraph_blocks(xml: str) -> list[ContentBlock]:
    return _extractor()._handle_paragraph(ET.fromstring(xml))


def _squash(text: str) -> str:
    return " ".join(text.split())


class TestTableInsideParagraph:
    """A <table-wrap> inside a <p> becomes a table block between paragraph blocks."""

    def test_the_table_becomes_a_block_between_the_paragraph_text(self) -> None:
        blocks = _paragraph_blocks(f"<p>Doses are listed below.{TABLE}They were tolerated.</p>")
        assert [b.type for b in blocks] == [PARAGRAPH, TABLE_BLOCK, PARAGRAPH]
        assert blocks[0].text == "Doses are listed below."
        assert blocks[2].text == "They were tolerated."

    def test_the_table_block_keeps_label_caption_and_rows(self) -> None:
        table = _paragraph_blocks(f"<p>See {TABLE}</p>")[1]
        assert table.label == "Table 1"
        assert table.caption == "Doses Per group."
        assert table.rows == [["Group", "Dose"], ["A", "10 mg"], ["B", "20 mg"]]

    def test_no_cell_text_is_left_in_the_paragraphs(self) -> None:
        blocks = _paragraph_blocks(f"<p>See {TABLE} for details.</p>")
        assert " ".join(b.text for b in blocks if b.type == PARAGRAPH) == "See for details."

    def test_a_paragraph_holding_only_a_table_yields_only_the_table(self) -> None:
        assert [b.type for b in _paragraph_blocks(f"<p>{TABLE}</p>")] == [TABLE_BLOCK]

    def test_inline_positions_after_the_table_index_the_new_paragraph(self) -> None:
        blocks = _paragraph_blocks(f"<p>Before.{TABLE} Then <bold>bold</bold> text.</p>")
        after = blocks[-1]
        assert after.text == "Then bold text."
        bold = next(i for i in after.inlines if i.type == InlineElementType.BOLD)
        assert after.text[bold.position : bold.position + bold.length] == "bold"


class TestFigureInsideParagraph:
    """A <fig> inside a <p> becomes a figure block between paragraph blocks."""

    def test_the_figure_becomes_a_block_between_the_paragraph_text(self) -> None:
        blocks = _paragraph_blocks(f"<p>Binding is shown in{FIGURE}and quantified below.</p>")
        assert [b.type for b in blocks] == [PARAGRAPH, FIGURE_BLOCK, PARAGRAPH]
        assert blocks[0].text == "Binding is shown in"
        assert blocks[2].text == "and quantified below."

    def test_the_figure_block_keeps_label_caption_and_graphic(self) -> None:
        figure = _paragraph_blocks(f"<p>{FIGURE}</p>")[0]
        assert (figure.label, figure.caption, figure.uri) == (
            "Fig. 1",
            "Mechanism Binding in vitro.",
            "f1.jpg",
        )


class TestOtherChildrenOfAParagraph:
    """Children other than tables and figures stay in the paragraph."""

    def test_an_unrecognised_wrapper_is_still_walked_for_inlines(self) -> None:
        blocks = _paragraph_blocks("<p>Before <foo>inner <bold>x</bold></foo> after.</p>")
        assert [b.type for b in blocks] == [PARAGRAPH]
        assert blocks[0].text == "Before inner x after."
        bold = next(i for i in blocks[0].inlines if i.type == InlineElementType.BOLD)
        assert blocks[0].text[bold.position : bold.position + bold.length] == "x"


class TestCaptionParts:
    """A caption's title and paragraph are kept apart."""

    def test_a_caption_title_is_not_run_into_its_paragraph(self) -> None:
        """Was "MechanismBinding in vitro." for every figure, nested or not."""
        figure = _extractor()._handle_figure(ET.fromstring(FIGURE))[0]
        assert figure.caption == "Mechanism Binding in vitro."


class TestFrontMatterSections:
    """The article title and abstract are front matter, not body sections."""

    def test_title_and_abstract_are_front_and_the_body_is_body(self) -> None:
        parser = FullTextXMLParser(_article("<p>Body text.</p>"))
        types = {s["title"]: s["section_type"] for s in parser.get_full_text_sections_structured()}
        assert types["Article Title"] == "front"
        assert types["Abstract"] == "front"
        assert types["Results"] == "body"

    def test_keeping_only_body_sections_leaves_title_and_abstract_out(self) -> None:
        parser = FullTextXMLParser(_article("<p>Body text.</p>"))
        body = [
            block["text"]
            for section in parser.get_full_text_sections_structured()
            if section["section_type"] == "body"
            for block in section["content"]
        ]
        assert body == ["Body text."]


class TestPlaintext:
    """to_plaintext() keeps nested table cells, and a figure label, apart."""

    def test_the_cells_of_a_table_inside_a_paragraph_stay_apart(self) -> None:
        text = _squash(FullTextXMLParser(_article(f"<p>Doses:{TABLE}</p>")).to_plaintext())
        assert "Group Dose A 10 mg B 20 mg" in text

    def test_a_figure_label_stays_apart_from_its_caption(self) -> None:
        text = _squash(FullTextXMLParser(_article(f"<p>See{FIGURE}</p>")).to_plaintext())
        assert "See Fig. 1 Mechanism Binding in vitro." in text
