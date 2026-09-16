"""Shared access to the real Europe PMC documents in tests/fixtures."""

from __future__ import annotations

import pathlib
import re
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"

#: Sentence-ish split. Good enough to compare a document against its own
#: rendering; not a linguistic claim.
SENTENCE = re.compile(r"(?<=[.!?])\s+")

#: Rendered as blocks of their own even where JATS places them inside a <p>.
OWN_BLOCKS = frozenset({"fig", "table-wrap", "table", "disp-formula"})


def squash(text: str | None) -> str:
    """Whitespace-insensitive form, for comparing text across renderings."""
    return re.sub(r"\s+", "", text or "")


def unescape_markdown(text: str | None) -> str:
    """The text a CommonMark renderer shows for Markdown source.

    Only backslash escapes are resolved: ``DRB1\\*0402`` reads ``DRB1*0402``.
    ``to_markdown()`` escapes every character that would otherwise change
    what a renderer does with the text, so comparing the article's sentences
    against the raw source would report each escape as lost text.
    """
    return re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", text or "")


def normalise(text: str | None) -> str:
    return " ".join((text or "").split())


def paragraph_segments(para: ET.Element) -> list[str]:
    """The runs of prose in ``para``, cut where a block of its own interrupts.

    JATS lets a <fig>, <table-wrap> or <disp-formula> sit inside a <p>. Each
    is rendered as a block in its own right, so the paragraph around it is
    genuinely two runs of prose, not one: PMC10775981 writes "models of the
    form", then equation (1), then "with N-dimensional state-vector y". No
    correct rendering can place those two halves next to each other, so they
    are checked as separate runs rather than joined.

    Joining them across the gap is what the earlier version did, and it also
    made "sentences" of a paragraph's last sentence run into a figure label
    ("...malignant cells.15,16 Fig.") and of a label run into its caption
    ("Figure 1. Affinity..."). They matched only because 2.2.1 folded the
    figure into the paragraph. The blocks' own text is checked in
    test_nested_blocks.py and test_formulas.py.
    """
    segments: list[str] = []
    parts: list[str] = []

    def cut() -> None:
        segments.append("".join(parts))
        parts.clear()

    def walk(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            if child.tag in OWN_BLOCKS:
                cut()
            else:
                walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(para)
    cut()
    return [s for s in segments if s.strip()]


def sentences(element: ET.Element) -> dict[str, int]:
    """Sentences of every <p> beneath ``element``, with their multiplicity.

    Sentences rather than whole paragraphs: a paragraph that wraps a rendered
    <list> is legitimately split apart in the output, so whole-paragraph
    matching would report a loss that is really a regrouping.
    """
    counts: dict[str, int] = {}
    for para in element.findall(".//p"):
        for segment in paragraph_segments(para):
            raw = normalise(segment)
            for part in SENTENCE.split(raw):
                key = squash(part)
                if len(key) > 60:
                    counts[key] = counts.get(key, 0) + 1
    return counts


def _block_text(block: dict) -> list[str]:
    """Every distinct string a content block carries, counted once.

    A table block's ``text`` is the whole rendering - caption and cells
    included - so adding ``caption`` and ``rows`` on top of it counts the same
    words twice and reports the parser as duplicating text it emitted once.
    Take ``text`` when it is there, and assemble from the parts only when it
    is not.
    """
    text = block.get("text") or ""
    if text:
        return [text]

    parts = [block.get("caption") or ""]
    parts.extend(block.get("items") or [])
    for term in block.get("definition_terms") or []:
        parts.extend([term.get("term") or "", term.get("def") or ""])
    for row in block.get("rows") or []:
        cells = row if isinstance(row, list) else [row]
        parts.extend(str(cell) for cell in cells)
    return [p for p in parts if p]


def fixture_paths() -> list[pathlib.Path]:
    return sorted(FIXTURE_DIR.glob("PMC*.xml"))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "document" in metafunc.fixturenames:
        paths = fixture_paths()
        metafunc.parametrize(
            "document", paths, ids=[p.stem for p in paths], indirect=True, scope="module"
        )


@pytest.fixture(scope="module")
def document(request: pytest.FixtureRequest):
    """A parsed real document, plus the raw tree and its renderings.

    Module-scoped: the largest fixture is ~800 KB and every rendering is
    computed once rather than per test.
    """
    from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

    path = request.param
    text = path.read_text(encoding="utf-8", errors="replace")
    root = DefusedET.fromstring(text.encode("utf-8"))
    parser = FullTextXMLParser(text)

    class Document:
        def __init__(self) -> None:
            self.pmcid = path.stem
            self.path = path
            self.root = root
            self.parser = parser
            self.body = root.find("./body")
            self.sections = parser.get_full_text_sections()
            self.plaintext = parser.to_plaintext()
            self.markdown = parser.to_markdown()
            self.structured = parser.get_full_text_sections_structured()

        @property
        def section_text(self) -> str:
            return squash("\n".join(s["content"] for s in self.sections))

        @property
        def structured_text(self) -> str:
            parts = []
            for section in self.structured:
                for block in section["content"]:
                    parts.extend(_block_text(block))
            return squash("\n".join(p for p in parts if p))

    return Document()
