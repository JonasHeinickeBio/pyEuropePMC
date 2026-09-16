"""Figures and tables kept in ``<floats-group>``, on a real document.

NIH author manuscripts place every figure and table in ``<floats-group>``, a
sibling of ``<body>``, and cite them from the text. Every output walked only
the body, so PMC5393345's figure and table reached ``extract_figures()`` and
``extract_tables()`` and nothing else: not the structured sections, not
``to_plaintext()``, ``to_markdown()`` or ``get_full_text_sections()``.
"""

from __future__ import annotations

import pathlib
import re
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.features.fulltext.utils.flat_blocks import FLOATS_TITLE

from .conftest import squash, unescape_markdown

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"
DOCUMENTS = sorted(FIXTURE_DIR.glob("PMC*.xml"))

pytestmark = [pytest.mark.unit]


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child(element: ET.Element, tag: str) -> ET.Element | None:
    return next((c for c in element if _local(c.tag) == tag), None)


def _text(element: ET.Element | None) -> str:
    return squash("".join(element.itertext())) if element is not None else ""


class _Parsed:
    def __init__(self, path: pathlib.Path) -> None:
        raw = path.read_text(encoding="utf-8")
        self.pmcid = path.stem
        self.root = DefusedET.fromstring(raw.encode("utf-8"))
        parser = FullTextXMLParser(raw)
        self.structured = parser.get_full_text_sections_structured()
        self.flat = parser.get_full_text_sections()
        self.renderings = {
            "to_plaintext": squash(parser.to_plaintext()),
            "to_markdown": squash(unescape_markdown(parser.to_markdown()).replace("**", "")),
            "get_full_text_sections": squash("\n".join(s["content"] for s in self.flat)),
        }
        groups = [c for c in self.root if _local(c.tag) == "floats-group"]
        self.floats = [f for g in groups for f in g if _local(f.tag) in ("fig", "table-wrap")]


@pytest.fixture(scope="module", params=DOCUMENTS, ids=lambda p: p.stem)
def doc(request: pytest.FixtureRequest) -> _Parsed:
    parsed = _Parsed(request.param)
    if not parsed.floats:
        pytest.skip(f"{parsed.pmcid} has no <floats-group>")
    return parsed


def test_a_fixture_keeps_its_floats_outside_the_body() -> None:
    """Without one every check below would be skipped."""
    count = sum(
        1
        for path in DOCUMENTS
        for child in DefusedET.fromstring(path.read_bytes())
        if _local(child.tag) == "floats-group"
    )
    assert count >= 1


class TestStructuredSections:
    def test_a_floats_section_holds_a_block_for_each_float(self, doc: _Parsed) -> None:
        sections = [s for s in doc.structured if s["title"] == FLOATS_TITLE]
        assert len(sections) == 1
        section = sections[0]
        # Body content wherever the XML stores it: a body filter keeps it.
        assert section["section_type"] == "body"
        kinds = [b["type"] for b in section["content"] if b["type"] in ("figure", "table")]
        expected = ["figure" if _local(f.tag) == "fig" else "table" for f in doc.floats]
        assert kinds == expected

    def test_each_block_carries_label_caption_and_cells(self, doc: _Parsed) -> None:
        section = next(s for s in doc.structured if s["title"] == FLOATS_TITLE)
        blocks = [b for b in section["content"] if b["type"] in ("figure", "table")]
        for element, block in zip(doc.floats, blocks, strict=True):
            assert squash(block.get("label")) == _text(_child(element, "label"))
            assert squash(block.get("caption")) == _text(_child(element, "caption"))
            if block["type"] == "table":
                cells = [_text(c) for c in element.iter() if _local(c.tag) in ("td", "th")]
                placed = [squash(c) for row in block["rows"] for c in row if c]
                assert [c for c in placed if not c.startswith("[graphic:")] == [
                    c for c in cells if c
                ]

    def test_the_floats_come_after_the_body_and_before_the_back_matter(self, doc: _Parsed) -> None:
        index = next(i for i, s in enumerate(doc.structured) if s["title"] == FLOATS_TITLE)
        assert all(s["section_type"] in ("front", "body") for s in doc.structured[:index])
        assert all(s["section_type"] != "body" for s in doc.structured[index + 1 :])


@pytest.mark.parametrize("rendering", ["to_plaintext", "to_markdown", "get_full_text_sections"])
class TestRenderings:
    def test_every_float_label_and_caption(self, doc: _Parsed, rendering: str) -> None:
        text = doc.renderings[rendering]
        for element in doc.floats:
            opening = (_text(_child(element, "label")) + _text(_child(element, "caption")))[:60]
            assert opening in text, f"{doc.pmcid}: {rendering}() lacks {opening!r}"

    def test_every_table_cell(self, doc: _Parsed, rendering: str) -> None:
        text = doc.renderings[rendering]
        for element in doc.floats:
            for cell in element.iter():
                if _local(cell.tag) in ("td", "th") and len(_text(cell)) >= 3:
                    assert _text(cell) in text, f"{doc.pmcid}: cell {_text(cell)!r} absent"

    def test_under_their_own_heading(self, doc: _Parsed, rendering: str) -> None:
        if rendering == "get_full_text_sections":
            pytest.skip("the heading is the entry's title; see the test below")
        assert squash(FLOATS_TITLE) in doc.renderings[rendering]


def test_get_full_text_sections_gives_the_floats_one_untyped_entry(doc: _Parsed) -> None:
    entries = [s for s in doc.flat if s["title"] == FLOATS_TITLE]
    assert len(entries) == 1
    assert "type" not in entries[0]
    assert re.search(r"\S", entries[0]["content"])
