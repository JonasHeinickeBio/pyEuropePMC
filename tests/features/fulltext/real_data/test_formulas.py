"""Display formulas on real documents.

JATS lets a ``<disp-formula>`` sit inside a ``<p>``, and PLOS always does. In
2.2.1 that formula was flattened into the sentence introducing it - PMC10775981
has eleven display formulas and produced no formula block at all, only
paragraphs reading "models of the form y˙=F(y(t),θ,t,…), (1) with N-dimensional
state-vector y".

The MathML was worse than absent. Every PLOS display formula wraps its content
in a ``<mml:mtable>``, and the converter looked for rows with
``findall("mtr")``, which matches nothing once the document declares a
namespace - so all eleven converted to the empty string. What reached the
``tex`` field instead was the flattened plain text, which is not LaTeX.
"""

from __future__ import annotations

import pathlib
import re
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"
DOCUMENTS = sorted(FIXTURE_DIR.glob("PMC*.xml"))

pytestmark = [pytest.mark.unit]


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _squash(text: str | None) -> str:
    return "".join((text or "").split())


def _unescape_markdown(text: str) -> str:
    """What a CommonMark renderer shows for a backslash escape: the character."""
    return re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", text)


def _display_formulas(root: ET.Element) -> list[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == "disp-formula"]


def _body_display_formulas(root: ET.Element) -> list[ET.Element]:
    """Display formulas of the article's own body, which is what is rendered."""
    body = root.find("./body")
    return _display_formulas(body) if body is not None else []


def _expression(formula: ET.Element) -> str:
    """The formula without its label, which is carried separately.

    A label sits before the expression in some documents and after it in
    others; the parser always puts it last, so comparing against the source's
    own order would be comparing against the publisher's typesetting.
    """
    parts: list[str] = []
    for child in formula:
        if _local(child.tag) == "label":
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)
    return _squash((formula.text or "") + "".join(parts))


class _Parsed:
    def __init__(self, path: pathlib.Path) -> None:
        raw = path.read_text(encoding="utf-8")
        self.pmcid = path.stem
        self.root = DefusedET.fromstring(raw.encode("utf-8"))
        parser = FullTextXMLParser(raw)
        self.sections = parser.get_full_text_sections_structured()
        self.blocks = [block for section in self.sections for block in section["content"]]
        self.formulas = [b for b in self.blocks if b["type"] == "formula"]
        self.plaintext_raw = parser.to_plaintext()
        self.markdown_raw = parser.to_markdown()
        self.flat_raw = "\n\n".join(s["content"] for s in parser.get_full_text_sections())
        self.plaintext = _squash(self.plaintext_raw)
        self.markdown = _squash(_unescape_markdown(self.markdown_raw))
        self.flat = _squash(self.flat_raw)


@pytest.fixture(scope="module", params=DOCUMENTS, ids=lambda p: p.stem)
def doc(request: pytest.FixtureRequest) -> _Parsed:
    return _Parsed(request.param)


def test_the_fixtures_have_display_formulas_inside_paragraphs() -> None:
    """Without such a document every check below would pass vacuously."""
    nested = 0
    for path in DOCUMENTS:
        root = DefusedET.fromstring(path.read_bytes())
        for para in root.iter():
            if _local(para.tag) != "p":
                continue
            nested += len(_display_formulas(para))
    assert nested >= 11, nested


class TestFormulaBlocks:
    def test_every_display_formula_becomes_a_formula_block(self, doc: _Parsed) -> None:
        expected = len(_body_display_formulas(doc.root))
        if not expected:
            pytest.skip(f"{doc.pmcid} has no display formula in its body")
        assert len(doc.formulas) >= expected, (
            f"{doc.pmcid}: {expected} <disp-formula> in the body, "
            f"{len(doc.formulas)} formula blocks"
        )

    def test_a_formula_block_carries_the_expression_as_text(self, doc: _Parsed) -> None:
        """Without ``text`` a plain-text consumer loses the equation entirely."""
        texts = {_squash(b.get("text")) for b in doc.formulas}
        for formula in _body_display_formulas(doc.root):
            expected = _expression(formula)
            if not expected:
                continue
            assert expected in texts, f"{doc.pmcid}: no formula block holds {expected[:60]!r}"

    def test_the_label_is_kept_out_of_the_expression(self, doc: _Parsed) -> None:
        """A label such as "(1)" belongs in ``label``, not at either end of it."""
        for block in doc.formulas:
            label = _squash(block.get("label"))
            text = _squash(block.get("text"))
            if not label or not text:
                continue
            assert not text.startswith(label) and not text.endswith(label), (
                f"{doc.pmcid}: label {label!r} is inside the expression {text[:60]!r}"
            )

    def test_tex_is_latex_and_not_the_flattened_text(self, doc: _Parsed) -> None:
        converted = [b for b in doc.formulas if b.get("mathml")]
        if not converted:
            pytest.skip(f"{doc.pmcid} has no MathML display formula")
        # The flattened text has no backslash in it; LaTeX for a real equation
        # always does. All 11 of PMC10775981's came back as the flattened text.
        with_latex = [b for b in converted if "\\" in (b.get("tex") or "")]
        assert with_latex, f"{doc.pmcid}: no display formula converted to LaTeX"

    def test_mathml_is_kept_and_reparses(self, doc: _Parsed) -> None:
        for block in doc.formulas:
            mathml = block.get("mathml")
            if not mathml:
                continue
            reparsed = DefusedET.fromstring(mathml)
            assert _local(reparsed.tag) == "math"
            # ElementTree invents "ns0" for a namespace it was not told about.
            assert "ns0:" not in mathml


class TestRenderingsAgree:
    def test_the_expression_reaches_every_flat_rendering(self, doc: _Parsed) -> None:
        """A display formula is a block, but its text is still the article's."""
        for formula in _body_display_formulas(doc.root):
            expected = _expression(formula)
            if len(expected) < 8:
                continue
            for name, rendering in (
                ("to_plaintext", doc.plaintext),
                ("to_markdown", doc.markdown),
                ("get_full_text_sections", doc.flat),
            ):
                assert expected in rendering, (
                    f"{doc.pmcid}: {expected[:50]!r} missing from {name}()"
                )

    def test_a_display_formula_stands_on_a_line_of_its_own(self, doc: _Parsed) -> None:
        """Not run into the sentence around it.

        PMC10775981 wrote "models of the form", equation (1), then "with
        N-dimensional state-vector y". Rendered inside that sentence, the
        equation made one that is in no reading of the document; the article
        sets it on a line of its own, and so do the renderings.
        """
        checked = 0
        for formula in _body_display_formulas(doc.root):
            expression = _expression(formula)
            if len(expression) < 8:
                continue
            for name, rendering in (
                ("to_plaintext", doc.plaintext_raw),
                ("to_markdown", _unescape_markdown(doc.markdown_raw)),
                ("get_full_text_sections", doc.flat_raw),
            ):
                lines = [_squash(line) for line in rendering.splitlines()]
                assert any(line.startswith(expression) for line in lines), (
                    f"{doc.pmcid}: {name}() has no line starting with {expression[:50]!r}"
                )
            checked += 1
        if not checked:
            pytest.skip(f"{doc.pmcid} has no display formula in its body")


def _unescaped(latex: str, char: str) -> int:
    """Occurrences of ``char`` not preceded by an odd run of backslashes."""
    count = 0
    for index, found in enumerate(latex):
        if found != char:
            continue
        run = len(latex[:index]) - len(latex[:index].rstrip("\\"))
        if run % 2 == 0:
            count += 1
    return count


_LEFT_RIGHT = re.compile(r"\\(?:left|right)(\\[A-Za-z]+|\\\||.)")
_VALID_DELIMITERS = {
    "(",
    ")",
    "[",
    "]",
    "|",
    ".",
    "/",
    r"\{",
    r"\}",
    r"\|",
    r"\langle",
    r"\rangle",
    r"\lfloor",
    r"\rfloor",
    r"\lceil",
    r"\rceil",
}


class TestLatexIsWellFormed:
    """Checks a LaTeX engine would otherwise make, without needing one installed.

    Measured with pdflatex on 1,654 formulas from 32 Europe PMC papers: 711
    compiled under 2.2.1 and 275 were empty; 1,650 compile here. The four that
    do not use a character outside mathematics (a Latin "ꝏ" for infinity).
    """

    def _latex(self, doc: _Parsed) -> list[str]:
        latex = [b["tex"] for b in doc.formulas if b.get("mathml") and b.get("tex")]
        if not latex:
            pytest.skip(f"{doc.pmcid} has no converted formula")
        return latex

    def test_groups_are_balanced(self, doc: _Parsed) -> None:
        for latex in self._latex(doc):
            assert _unescaped(latex, "{") == _unescaped(latex, "}"), (
                f"{doc.pmcid}: unbalanced group in {latex[:80]!r}"
            )

    def test_left_and_right_take_a_delimiter(self, doc: _Parsed) -> None:
        for latex in self._latex(doc):
            for delimiter in _LEFT_RIGHT.findall(latex):
                assert delimiter in _VALID_DELIMITERS, (
                    f"{doc.pmcid}: \\left/\\right with {delimiter!r} in {latex[:80]!r}"
                )

    def test_greek_and_operators_are_commands(self, doc: _Parsed) -> None:
        """pdflatex stops at the first Greek letter or operator left as Unicode."""
        for latex in self._latex(doc):
            stray = [c for c in latex if not c.isascii()]
            assert not stray, f"{doc.pmcid}: {stray[:3]} left in {latex[:80]!r}"
