"""Tables and figures inside a paragraph, and front matter, on real documents.

JATS lets a <table-wrap> or <fig> sit inside a <p>: PMC12311175 nests seven
tables and nine figures that way, PMC3258128 five figures. In 2.2.1 the
structured blocks folded each one into its paragraph - no table or figure
block, and the cells run together - and to_plaintext() ran the cells together
as well. The article title and abstract came back labelled as body sections.
"""

from __future__ import annotations

import pathlib

from lxml import etree
import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"
DOCUMENTS = sorted(FIXTURE_DIR.glob("PMC*.xml"))
_XML = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)


def _squash(text: str | None) -> str:
    return " ".join((text or "").split())


def _local(tag: object) -> str:
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else str(tag)


def _text(element) -> str:
    return _squash("".join(element.itertext()))


def _bare(text: str | None) -> str:
    """Whitespace removed: the XML runs a caption's title into its text, a block does not."""
    return "".join((text or "").split())


def _nested(root, tag: str) -> list:
    return [
        el
        for el in root.iter()
        if _local(el.tag) == tag and any(_local(a.tag) == "p" for a in el.iterancestors())
    ]


def _child(element, tag: str):
    return next((c for c in element if _local(c.tag) == tag), None)


def _glued_cells(table) -> list[str]:
    """Adjacent cells written with nothing between them, e.g. ``"10 mg20 mg"``.

    Cells shorter than three characters are left out: two short numbers run
    together ("1" + "2") match text that is genuinely there.
    """
    glued = []
    for row in (el for el in table.iter() if _local(el.tag) == "tr"):
        cells = [_text(c) for c in row if _local(c.tag) in ("td", "th")]
        cells = [c for c in cells if len(c) >= 3]
        glued.extend(a + b for a, b in zip(cells, cells[1:], strict=False))
    return glued


class _Parsed:
    def __init__(self, path: pathlib.Path):
        raw = path.read_text(encoding="utf-8")
        self.pmcid = path.stem
        self.root = etree.fromstring(raw.encode("utf-8"), _XML)
        parser = FullTextXMLParser(raw)
        self.plaintext = _squash(parser.to_plaintext())
        self.sections = parser.get_full_text_sections_structured()
        self.blocks = [block for section in self.sections for block in section["content"]]


@pytest.fixture(scope="module", params=DOCUMENTS, ids=lambda p: p.stem)
def doc(request) -> _Parsed:
    return _Parsed(request.param)


def test_the_fixtures_nest_tables_and_figures_in_paragraphs():
    """Without such documents every check below would pass vacuously."""
    tables = figures = 0
    for path in DOCUMENTS:
        root = etree.fromstring(path.read_bytes(), _XML)
        tables += len(_nested(root, "table-wrap"))
        figures += len(_nested(root, "fig"))
    assert tables >= 7, tables
    assert figures >= 14, figures


class TestStructuredBlocks:
    def test_each_nested_table_has_a_table_block_with_its_rows(self, doc):
        for table in _nested(doc.root, "table-wrap"):
            label = _text(_child(table, "label")) if _child(table, "label") is not None else ""
            expected_rows = sum(
                1
                for part in table.iter()
                if _local(part.tag) in ("thead", "tbody")
                for row in part
                if _local(row.tag) == "tr" and any(_local(c.tag) in ("td", "th") for c in row)
            )
            candidates = [
                b for b in doc.blocks if b["type"] == "table" and _squash(b.get("label")) == label
            ]
            assert candidates, f"{doc.pmcid}: nested table {label!r} has no table block"
            assert any(len(b.get("rows") or []) == expected_rows for b in candidates), (
                f"{doc.pmcid}: table block {label!r} lacks its {expected_rows} rows"
            )

    def test_each_nested_figure_has_a_figure_block(self, doc):
        figure_labels = {_squash(b.get("label")) for b in doc.blocks if b["type"] == "figure"}
        for figure in _nested(doc.root, "fig"):
            label = _text(_child(figure, "label")) if _child(figure, "label") is not None else ""
            assert label in figure_labels, f"{doc.pmcid}: nested figure {label!r} has no block"

    def test_each_nested_block_keeps_its_caption_and_cells(self, doc):
        """The sentence reference in conftest leaves a nested table or figure out of
        its paragraph, so its caption and cells are checked here instead."""
        for tag, block_type in (("table-wrap", "table"), ("fig", "figure")):
            for element in _nested(doc.root, tag):
                label_el, caption_el = _child(element, "label"), _child(element, "caption")
                label = _text(label_el) if label_el is not None else ""
                blocks = [
                    b
                    for b in doc.blocks
                    if b["type"] == block_type and _squash(b.get("label")) == label
                ]
                caption = _bare(_text(caption_el)) if caption_el is not None else ""
                assert any(_bare(b.get("caption")) == caption for b in blocks), (
                    f"{doc.pmcid}: {block_type} block {label!r} does not carry its caption"
                )
                if block_type != "table":
                    continue
                cells = _bare(
                    "".join(_text(c) for c in element.iter() if _local(c.tag) in ("td", "th"))
                )
                assert any(
                    _bare("".join(cell for row in b.get("rows") or [] for cell in row)) == cells
                    for b in blocks
                ), f"{doc.pmcid}: table block {label!r} does not carry all its cell text"

    def test_nested_table_cells_are_not_run_together(self, doc):
        block_text = " ".join(_squash(b.get("text")) for b in doc.blocks)
        glued = [g for t in _nested(doc.root, "table-wrap") for g in _glued_cells(t)]
        found = [g for g in glued if g in block_text]
        assert not found, f"{doc.pmcid}: {len(found)} run-together cells, e.g. {found[0]!r}"

    def test_title_and_abstract_are_not_labelled_body(self, doc):
        body_titles = [s["title"] for s in doc.sections if s["section_type"] == "body"]
        assert "Article Title" not in body_titles
        abstract = next((el for el in doc.root.iter() if _local(el.tag) == "abstract"), None)
        first_paragraph = abstract.find(".//{*}p") if abstract is not None else None
        if first_paragraph is None:
            first_paragraph = abstract.find(".//p") if abstract is not None else None
        if first_paragraph is not None and len(_text(first_paragraph)) >= 80:
            opening = _text(first_paragraph)[:80]
            body_text = " ".join(
                _squash(b.get("text"))
                for s in doc.sections
                if s["section_type"] == "body"
                for b in s["content"]
            )
            assert opening not in body_text, f"{doc.pmcid}: abstract returned as a body section"


class TestPlaintext:
    def test_nested_table_cells_are_not_run_together(self, doc):
        glued = [g for t in _nested(doc.root, "table-wrap") for g in _glued_cells(t)]
        found = [g for g in glued if g in doc.plaintext]
        assert not found, f"{doc.pmcid}: {len(found)} run-together cells, e.g. {found[0]!r}"

    def test_a_nested_figure_label_is_not_run_into_its_caption(self, doc):
        found = []
        for figure in _nested(doc.root, "fig"):
            label, caption = _child(figure, "label"), _child(figure, "caption")
            if label is None or caption is None or not _text(label) or not _text(caption):
                continue
            joined = _text(label) + _text(caption)[:20]
            if joined in doc.plaintext:
                found.append(joined)
        assert not found, f"{doc.pmcid}: label run into caption, e.g. {found[0]!r}"
