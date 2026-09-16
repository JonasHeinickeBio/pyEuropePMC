"""What the three flat renderings carry besides paragraphs, on real documents.

Measured on the previous release of this code:

- to_markdown() and get_full_text_sections() lacked 225 of PMC1764484's 247
  distinct table cells, and to_plaintext() 228 of the 248 in PMC11687933's
  appendix table;
- figure labels with their caption titles, and table labels, reached none of
  the three when the float sat directly in a section;
- all 14 of PMC10775981's code listings were missing from all three, and the
  structured code blocks ran each listing onto one line;
- to_markdown() escaped nothing: 49 of PMC1764484's 127 body sentences rendered
  as something else once "DRB1*0402 ... DQB1*0503" opened an emphasis.
"""

from __future__ import annotations

import html
import pathlib
import re
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

from .conftest import sentences, squash, unescape_markdown

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"
DOCUMENTS = sorted(FIXTURE_DIR.glob("PMC*.xml"))

pytestmark = [pytest.mark.unit]


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _norm(text: str | None) -> str:
    return " ".join((text or "").split())


def _child(element: ET.Element, tag: str) -> ET.Element | None:
    return next((c for c in element if _local(c.tag) == tag), None)


def _text(element: ET.Element | None) -> str:
    return _norm("".join(element.itertext())) if element is not None else ""


class _Parsed:
    def __init__(self, path: pathlib.Path) -> None:
        raw = path.read_text(encoding="utf-8")
        self.pmcid = path.stem
        self.root = DefusedET.fromstring(raw.encode("utf-8"))
        parser = FullTextXMLParser(raw)
        self.markdown_source = parser.to_markdown()
        self.renderings = {
            "to_plaintext": _norm(parser.to_plaintext()),
            # What a reader sees: escapes resolved, the bold around a label removed.
            "to_markdown": _norm(unescape_markdown(self.markdown_source).replace("**", "")),
            "get_full_text_sections": _norm(
                "\n\n".join(s["content"] for s in parser.get_full_text_sections())
            ),
        }
        self.structured = parser.get_full_text_sections_structured()
        # The article's own body and back matter: what the renderings cover.
        self.scope = [child for child in self.root if _local(child.tag) in ("body", "back")]

    def elements(self, tag: str) -> list[ET.Element]:
        return [el for part in self.scope for el in part.iter() if _local(el.tag) == tag]


@pytest.fixture(scope="module", params=DOCUMENTS, ids=lambda p: p.stem)
def doc(request: pytest.FixtureRequest) -> _Parsed:
    return _Parsed(request.param)


RENDERINGS = ("to_plaintext", "to_markdown", "get_full_text_sections")


@pytest.mark.parametrize("rendering", RENDERINGS)
class TestNothingButParagraphsWasRendered:
    def test_every_table_cell(self, doc: _Parsed, rendering: str) -> None:
        text = doc.renderings[rendering]
        cells = {_text(c) for c in doc.elements("td") + doc.elements("th")}
        missing = sorted(c for c in cells if len(c) >= 3 and c not in text)
        assert not missing, (
            f"{doc.pmcid}: {len(missing)} cells absent from {rendering}(), e.g. {missing[0]!r}"
        )

    # Compared with whitespace removed: itertext() runs a caption's <title>
    # into its <p> with nothing between, which the renderings rightly do not.
    def test_every_figure_label_with_its_caption(self, doc: _Parsed, rendering: str) -> None:
        text = squash(doc.renderings[rendering])
        for figure in doc.elements("fig"):
            label, caption = _text(_child(figure, "label")), _child(figure, "caption")
            if not label or caption is None or not _text(caption):
                continue
            opening = squash(label + _text(caption))[:40]
            assert opening in text, f"{doc.pmcid}: {rendering}() lacks {opening!r}"

    def test_every_table_label_with_its_caption(self, doc: _Parsed, rendering: str) -> None:
        text = squash(doc.renderings[rendering])
        for table in doc.elements("table-wrap"):
            label, caption = _text(_child(table, "label")), _child(table, "caption")
            if not label:
                continue
            opening = squash(label + _text(caption))[:40]
            assert opening in text, f"{doc.pmcid}: {rendering}() lacks {opening!r}"

    def test_every_code_listing(self, doc: _Parsed, rendering: str) -> None:
        listings = doc.elements("preformat") + doc.elements("code")
        if not listings:
            pytest.skip(f"{doc.pmcid} has no code listing")
        text = doc.renderings[rendering]
        for listing in listings:
            assert _text(listing) in text, f"{doc.pmcid}: listing absent from {rendering}()"


class TestCodeKeepsItsLines:
    def test_structured_code_blocks(self, doc: _Parsed) -> None:
        listings = doc.elements("preformat")
        if not listings:
            pytest.skip(f"{doc.pmcid} has no <preformat>")
        blocks = [b for s in doc.structured for b in s["content"] if b["type"] == "code"]
        by_text = {squash(b["text"]): b["text"] for b in blocks}
        for listing in listings:
            source_lines = [
                line.rstrip() for line in "".join(listing.itertext()).strip("\n").splitlines()
            ]
            block = by_text.get(squash("".join(listing.itertext())))
            assert block is not None, f"{doc.pmcid}: no code block for a listing"
            assert block.splitlines() == source_lines

    def test_markdown_fences_each_listing(self, doc: _Parsed) -> None:
        listings = doc.elements("preformat")
        if not listings:
            pytest.skip(f"{doc.pmcid} has no <preformat>")
        fenced = re.findall(r"^(`{3,})[^\n]*\n(.*?)\n\1$", doc.markdown_source, flags=re.M | re.S)
        bodies = {squash(body) for _, body in fenced}
        for listing in listings:
            assert squash("".join(listing.itertext())) in bodies


class TestMarkdownRendersAsWritten:
    def test_rendered_markdown_carries_every_body_sentence(self, doc: _Parsed) -> None:
        """Rendered with a CommonMark implementation, not compared as source."""
        markdown_it = pytest.importorskip("markdown_it")
        renderer = markdown_it.MarkdownIt("commonmark").enable("table").enable("strikethrough")
        rendered = squash(
            html.unescape(re.sub(r"<[^>]+>", " ", renderer.render(doc.markdown_source)))
        )
        body = doc.root.find("./body")
        missing = [s for s in sentences(body) if s not in rendered] if body is not None else []
        assert not missing, (
            f"{doc.pmcid}: {len(missing)} body sentences render as something else, "
            f"e.g. {missing[0][:80]!r}"
        )

    def test_no_markup_character_is_left_bare(self, doc: _Parsed) -> None:
        """The same check without a renderer: outside code and our own bold markers,
        every character that means something to Markdown is escaped."""
        prose = re.sub(r"^(`{3,})[^\n]*\n.*?\n\1$", "", doc.markdown_source, flags=re.M | re.S)
        prose = re.sub(r"\*\*(?=\S)|(?<=\S)\*\*", "", prose)  # **label**
        prose = re.sub(
            r"^\|.*\|$", lambda m: m.group(0).strip("|").replace(" | ", " "), prose, flags=re.M
        )
        prose = re.sub(r"^\| ?(---|---- )[| -]*$", "", prose, flags=re.M)
        prose = re.sub(r"^#{1,6} ", "", prose, flags=re.M)
        prose = re.sub(r"^(- |\d+\. )", "", prose, flags=re.M)
        bare = re.findall(r"(?<!\\)(?:\\\\)*([*_`<>\[\]~$])", prose)
        assert not bare, f"{doc.pmcid}: unescaped {sorted(set(bare))} in to_markdown()"
