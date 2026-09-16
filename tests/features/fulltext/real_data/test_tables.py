"""Table layout on real documents.

Four defects, each invisible to a hand-written table with one plain header row:

- ``extract_tables()`` read header labels from ``<th>`` only, so a ``<thead>``
  whose cells are ``<td>`` gave ``headers == []``: all five tables of
  PMC1764484, both of PMC3359999.
- ``colspan`` and ``rowspan`` were ignored everywhere. In PMC12311175's Table 4
  a drug's name and mechanism span every row of its trials, so 110 of 120 body
  rows came back two cells short, their values under the wrong headers.
- The structured table block recorded neither its footer nor where the header
  rows end, and a cell holding only an image - PMC5393345 draws each compound's
  structure that way - came back as an empty string.
- The block's ``inlines`` held positions within each cell, stored against a
  ``text`` for the whole table: 207 of 207 in PMC1764484 pointed at the wrong
  characters.
"""

from __future__ import annotations

from collections import Counter
import pathlib

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"
DOCUMENTS = sorted(FIXTURE_DIR.glob("PMC*.xml"))

pytestmark = [pytest.mark.unit]


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _squash(text: str | None) -> str:
    return " ".join((text or "").split())


class _Parsed:
    def __init__(self, path: pathlib.Path) -> None:
        raw = path.read_text(encoding="utf-8")
        self.pmcid = path.stem
        self.root = DefusedET.fromstring(raw.encode("utf-8"))
        parser = FullTextXMLParser(raw)
        self.tables = parser.extract_tables()
        self.blocks = [
            block
            for section in parser.get_full_text_sections_structured()
            for block in section["content"]
            if block["type"] == "table"
        ]
        self.wraps = [el for el in self.root.iter() if _local(el.tag) == "table-wrap"]


@pytest.fixture(scope="module", params=DOCUMENTS, ids=lambda p: p.stem)
def doc(request: pytest.FixtureRequest) -> _Parsed:
    return _Parsed(request.param)


def test_the_fixtures_have_the_table_shapes_checked_here() -> None:
    """Without them every check below would pass vacuously."""
    td_headers = spans = image_cells = 0
    for path in DOCUMENTS:
        root = DefusedET.fromstring(path.read_bytes())
        for element in root.iter():
            tag = _local(element.tag)
            if tag == "thead":
                cells = [c for row in element for c in row if _local(c.tag) in ("td", "th")]
                td_headers += bool(cells) and all(_local(c.tag) == "td" for c in cells)
            elif tag in ("td", "th"):
                spans += element.get("rowspan", "1") not in ("1", "")
                spans += element.get("colspan", "1") not in ("1", "")
                image_cells += not "".join(element.itertext()).strip() and any(
                    _local(g.tag) == "graphic" for g in element.iter()
                )
    assert td_headers >= 7, td_headers
    assert spans >= 20, spans
    assert image_cells >= 6, image_cells


class TestExtractTables:
    def test_every_thead_gives_header_labels(self, doc: _Parsed) -> None:
        for wrap, table in zip(doc.wraps, doc.tables, strict=True):
            theads = [el for el in wrap.iter() if _local(el.tag) == "thead"]
            has_text = any("".join(t.itertext()).strip() for t in theads)
            if has_text:
                assert any(table["headers"]), (
                    f"{doc.pmcid}: table {table['label']!r} has a <thead> and no headers"
                )

    def test_every_row_is_as_wide_as_the_table(self, doc: _Parsed) -> None:
        for table in doc.tables:
            rows = table["header_rows"] + table["rows"]
            if not rows:
                continue
            widths = {len(row) for row in rows}
            assert len(widths) == 1, f"{doc.pmcid}: {table['label']!r} rows of widths {widths}"
            if table["headers"]:
                assert len(table["headers"]) == widths.pop()

    def test_every_cell_is_placed_exactly_once(self, doc: _Parsed) -> None:
        """Nothing lost to a span and nothing repeated into the positions it covers."""
        for wrap, table in zip(doc.wraps, doc.tables, strict=True):
            source = Counter(
                _squash("".join(cell.itertext()))
                for cell in wrap.iter()
                if _local(cell.tag) in ("td", "th") and "".join(cell.itertext()).strip()
            )
            placed = Counter(
                cell
                for row in table["header_rows"] + table["rows"]
                for cell in row
                if cell and not cell.startswith("[graphic: ")
            )
            assert placed == source, f"{doc.pmcid}: cells of {table['label']!r} differ"

    def test_spans_match_the_markup(self, doc: _Parsed) -> None:
        for wrap, table in zip(doc.wraps, doc.tables, strict=True):
            declared = sum(
                1
                for cell in wrap.iter()
                if _local(cell.tag) in ("td", "th")
                and (
                    cell.get("rowspan", "1") not in ("1", "")
                    or cell.get("colspan", "1") not in ("1", "")
                )
            )
            # A span clipped to its row group is no span at all, so at most.
            assert len(table["spans"]) <= declared
            if declared:
                assert table["spans"], f"{doc.pmcid}: {table['label']!r} lost its spans"

    def test_an_image_only_cell_references_its_image(self, doc: _Parsed) -> None:
        for table in doc.tables:
            for graphic in table["cell_graphics"]:
                row = (table["header_rows"] + table["rows"])[graphic["row"]]
                cell = row[graphic["column"]]
                assert cell, f"{doc.pmcid}: image cell of {table['label']!r} is empty"


def _bare(text: str | None) -> str:
    """Whitespace removed.

    The structured blocks drop the space after an inline element whose text
    ends in one ("'*' </bold>indicate" reads "'*'indicate"), which
    extract_tables() does not. That is a defect of its own; these checks are
    about layout.
    """
    return "".join((text or "").split())


class TestStructuredTableBlocks:
    def test_rows_agree_with_extract_tables(self, doc: _Parsed) -> None:
        by_label = {_squash(t["label"]): t for t in doc.tables if t["label"]}
        for block in doc.blocks:
            table = by_label.get(_squash(block.get("label")))
            if table is None:
                continue
            expected = [[_bare(c) for c in row] for row in table["header_rows"] + table["rows"]]
            assert [[_bare(c) for c in row] for row in block["rows"]] == expected
            assert block["metadata"]["header_rows"] == len(table["header_rows"])

    def test_the_footer_is_recorded(self, doc: _Parsed) -> None:
        by_label = {_squash(t["label"]): t for t in doc.tables if t["label"]}
        for block in doc.blocks:
            table = by_label.get(_squash(block.get("label")))
            if table is None or not table["footer"]:
                continue
            assert _bare(block["metadata"].get("footer")) == _bare(table["footer"])

    def test_every_inline_indexes_the_block_text(self, doc: _Parsed) -> None:
        checked = 0
        for block in doc.blocks:
            text = block.get("text") or ""
            for inline in block.get("inlines") or []:
                start, length = inline["position"], inline["length"]
                assert text[start : start + length] == inline["text"], (
                    f"{doc.pmcid}: {inline['type']} {inline['text']!r} at {start} reads "
                    f"{text[start : start + length]!r}"
                )
                checked += 1
        if not checked:
            pytest.skip(f"{doc.pmcid} has no inline element in a table block")
