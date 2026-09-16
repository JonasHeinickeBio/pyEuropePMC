"""Unit tests for pyeuropepmc.features.fulltext.extensions.mathml (pure XML->LaTeX)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.mathml import MathMLConverter, serialize_mathml


def _mml(xml: str) -> ET.Element:
    return DefusedET.fromstring(xml)


@pytest.fixture
def conv():
    return MathMLConverter()


class TestConvert:
    def test_inline_default(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        assert conv.convert(elem) == "$x$"

    def test_display_attribute_respected(self, conv):
        elem = _mml('<math display="block"><mi>x</mi></math>')
        assert conv.convert(elem) == "$$x$$"

    def test_forced_inline_overrides_display_attr(self):
        conv = MathMLConverter(inline=True)
        elem = _mml('<math display="block"><mi>x</mi></math>')
        assert conv.convert(elem).startswith("$") and not conv.convert(elem).startswith("$$")

    def test_convert_to_latex_no_delimiters(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        assert conv.convert_to_latex(elem) == "x"

    def test_empty_element_uses_raw_text(self, conv):
        elem = _mml("<mrow> raw text </mrow>")
        assert conv._convert_children(elem) == "raw text"


class TestHandlers:
    def test_mi_single_char(self, conv):
        elem = _mml("<mi>x</mi>")
        assert conv._handle_mi(elem) == "x"

    def test_mi_known_function_lowercase(self, conv):
        elem = _mml("<mi>sin</mi>")
        assert conv._handle_mi(elem) == "\\sin"

    def test_mi_multichar_unknown_uses_operatorname(self, conv):
        elem = _mml("<mi>foo</mi>")
        assert conv._handle_mi(elem) == "\\operatorname{foo}"

    def test_mi_empty_text(self, conv):
        elem = _mml("<mi></mi>")
        assert conv._handle_mi(elem) == ""

    def test_mn(self, conv):
        elem = _mml("<mn>42</mn>")
        assert conv._handle_mn(elem) == "42"

    def test_mo_known_operator(self, conv):
        elem = _mml("<mo>≤</mo>")
        assert conv._handle_mo(elem) == "\\le"

    def test_mo_unknown_operator_passthrough(self, conv):
        elem = _mml("<mo>+</mo>")
        assert conv._handle_mo(elem) == "+"

    def test_mtext(self, conv):
        elem = _mml("<mtext>hello</mtext>")
        assert conv._handle_mtext(elem) == "\\text{hello}"

    def test_mtext_empty(self, conv):
        elem = _mml("<mtext></mtext>")
        assert conv._handle_mtext(elem) == ""

    def test_msup(self, conv):
        elem = _mml("<msup><mi>x</mi><mn>2</mn></msup>")
        assert conv._handle_msup(elem) == "x^{2}"

    def test_msup_missing_children_falls_back(self, conv):
        elem = _mml("<msup><mi>x</mi></msup>")
        assert conv._handle_msup(elem) == "x"

    def test_msub(self, conv):
        elem = _mml("<msub><mi>x</mi><mn>1</mn></msub>")
        assert conv._handle_msub(elem) == "x_{1}"

    def test_msubsup(self, conv):
        elem = _mml("<msubsup><mi>x</mi><mn>1</mn><mn>2</mn></msubsup>")
        assert conv._handle_msubsup(elem) == "x_{1}^{2}"

    def test_mfrac(self, conv):
        elem = _mml("<mfrac><mn>1</mn><mn>2</mn></mfrac>")
        assert conv._handle_mfrac(elem) == "\\frac{1}{2}"

    def test_msqrt(self, conv):
        elem = _mml("<msqrt><mi>x</mi></msqrt>")
        assert conv._handle_msqrt(elem) == "\\sqrt{x}"

    def test_mroot(self, conv):
        elem = _mml("<mroot><mi>x</mi><mn>3</mn></mroot>")
        assert conv._handle_mroot(elem) == "\\sqrt[3]{x}"

    def test_mrow(self, conv):
        elem = _mml("<mrow><mi>x</mi><mo>+</mo><mi>y</mi></mrow>")
        assert conv._handle_mrow(elem) == "x + y"

    def test_merror(self, conv):
        elem = _mml("<merror><mi>x</mi></merror>")
        assert conv._handle_merror(elem) == "x"

    def test_mpadded(self, conv):
        elem = _mml("<mpadded><mi>x</mi></mpadded>")
        assert conv._handle_mpadded(elem) == "x"

    def test_mphantom(self, conv):
        elem = _mml("<mphantom><mi>x</mi></mphantom>")
        assert conv._handle_mphantom(elem) == "\\phantom{x}"

    def test_mstyle(self, conv):
        elem = _mml("<mstyle><mi>x</mi></mstyle>")
        assert conv._handle_mstyle(elem) == "x"

    def test_menclose_box(self, conv):
        elem = _mml('<menclose notation="box"><mi>x</mi></menclose>')
        assert conv._handle_menclose(elem) == "\\boxed{x}"

    def test_menclose_default_notation(self, conv):
        elem = _mml("<menclose><mi>x</mi></menclose>")
        assert conv._handle_menclose(elem) == "x"

    def test_munder_is_an_underscript_not_a_subscript(self, conv):
        elem = _mml("<munder><mi>x</mi><mi>y</mi></munder>")
        assert conv._handle_munder(elem) == "\\underset{y}{x}"

    def test_mover_is_an_overscript_not_a_superscript(self, conv):
        elem = _mml("<mover><mi>x</mi><mi>y</mi></mover>")
        assert conv._handle_mover(elem) == "\\overset{y}{x}"

    def test_munderover(self, conv):
        elem = _mml("<munderover><mi>x</mi><mi>a</mi><mi>b</mi></munderover>")
        assert conv._handle_munderover(elem) == "\\underset{a}{\\overset{b}{x}}"

    def test_munderover_on_a_big_operator_is_its_limits(self, conv):
        elem = _mml("<munderover><mo>\u2211</mo><mi>a</mi><mi>b</mi></munderover>")
        assert conv._handle_munderover(elem) == "\\sum_{a}^{b}"

    def test_mmultiscripts(self, conv):
        elem = _mml("<mmultiscripts><mi>x</mi></mmultiscripts>")
        assert conv._handle_mmultiscripts(elem) == "x"

    def test_mtable(self, conv):
        elem = _mml(
            "<mtable><mtr><mtd><mn>1</mn></mtd><mtd><mn>2</mn></mtd></mtr>"
            "<mtr><mtd><mn>3</mn></mtd><mtd><mn>4</mn></mtd></mtr></mtable>"
        )
        result = conv._handle_mtable(elem)
        assert "\\begin{array}{cc}" in result
        assert "1 & 2" in result
        assert "3 & 4" in result

    def test_mtable_empty_returns_empty_string(self, conv):
        elem = _mml("<mtable></mtable>")
        assert conv._handle_mtable(elem) == ""

    def test_unknown_tag_falls_back_to_text(self, conv):
        elem = _mml("<mrow><munknown>xyz</munknown></mrow>")
        assert "xyz" in conv._handle_mrow(elem)


class TestUtilities:
    def test_get_elem_text_includes_tail(self, conv):
        elem = _mml("<mi>x<sub>tail</sub></mi>")
        # tail of <sub> child is included
        text = MathMLConverter._get_elem_text(elem)
        assert "x" in text

    def test_resolve_entities_numeric_decimal(self, conv):
        assert MathMLConverter._resolve_entities("&#945;") == "α"

    def test_resolve_entities_numeric_hex(self, conv):
        assert MathMLConverter._resolve_entities("&#x3B1;") == "α"

    def test_resolve_entities_empty(self, conv):
        assert MathMLConverter._resolve_entities("") == ""

    def test_local_tag_strips_namespace(self, conv):
        assert MathMLConverter._local_tag("{http://www.w3.org/1998/Math/MathML}mi") == "mi"

    def test_local_tag_no_namespace(self, conv):
        assert MathMLConverter._local_tag("mi") == "mi"


class TestClassmethods:
    def test_convert_mathml_inline(self):
        elem = _mml("<math><mi>x</mi></math>")
        assert MathMLConverter.convert_mathml(elem) == "$x$"

    def test_convert_display_mathml(self):
        elem = _mml("<math><mi>x</mi></math>")
        assert MathMLConverter.convert_display_mathml(elem) == "$$x$$"


class TestToHtml:
    def test_inline(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        html = conv.to_html(elem)
        assert 'class="math-inline"' in html
        assert "\\(x\\)" in html

    def test_display(self):
        conv = MathMLConverter(inline=False)
        elem = _mml("<math><mi>x</mi></math>")
        html = conv.to_html(elem)
        assert 'class="math-display"' in html
        assert "\\[x\\]" in html


class TestToSvg:
    def test_latex_not_found_raises(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        with (
            patch("subprocess.run", side_effect=FileNotFoundError()),
            pytest.raises(RuntimeError, match="System LaTeX"),
        ):
            conv.to_svg(elem)

    def test_latex_compilation_failure_raises(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        err = subprocess.CalledProcessError(1, "latex", stderr=b"bad tex")
        with (
            patch("subprocess.run", side_effect=err),
            pytest.raises(RuntimeError, match="LaTeX compilation failed"),
        ):
            conv.to_svg(elem)

    def test_dvisvgm_not_found_raises(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        latex_ok = MagicMock()
        with (
            patch("subprocess.run", side_effect=[latex_ok, FileNotFoundError()]),
            pytest.raises(RuntimeError, match="dvisvgm not found"),
        ):
            conv.to_svg(elem)

    def test_dvisvgm_failure_raises(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        latex_ok = MagicMock()
        dvisvgm_err = subprocess.CalledProcessError(1, "dvisvgm", stderr=b"svg fail")
        with (
            patch("subprocess.run", side_effect=[latex_ok, dvisvgm_err]),
            pytest.raises(RuntimeError, match="SVG conversion failed"),
        ):
            conv.to_svg(elem)

    def test_success_returns_svg(self, conv):
        elem = _mml("<math><mi>x</mi></math>")
        latex_ok = MagicMock()
        svg_result = MagicMock(stdout=b"<svg>ok</svg>")
        with patch("subprocess.run", side_effect=[latex_ok, svg_result]):
            result = conv.to_svg(elem)
        assert result == "<svg>ok</svg>"


MML = "http://www.w3.org/1998/Math/MathML"


def _namespaced(inner: str) -> ET.Element:
    """A fragment in the MathML namespace, as Europe PMC actually serves it."""
    return DefusedET.fromstring(f'<math xmlns="{MML}">{inner}</math>')


class TestNamespacedDocuments:
    """Every Europe PMC document puts MathML in its own namespace."""

    def test_mtable_rows_are_found_when_namespaced(self, conv):
        elem = _namespaced(
            "<mtable><mtr><mtd><mn>1</mn></mtd><mtd><mn>2</mn></mtd></mtr>"
            "<mtr><mtd><mn>3</mn></mtd><mtd><mn>4</mn></mtd></mtr></mtable>"
        )
        latex = conv.convert_to_latex(elem)
        assert "\\begin{array}{cc}" in latex
        assert "1 & 2 \\\\ 3 & 4" in latex

    def test_a_namespaced_formula_is_not_empty(self, conv):
        """PLOS wraps every display formula in a one-row <mtable>; all 11 in
        PMC10775981 converted to "" because findall("mtr") ignores namespaces."""
        elem = _namespaced(
            "<mtable><mtr><mtd><mrow><mi>x</mi><mo>=</mo><mn>1</mn></mrow></mtd></mtr></mtable>"
        )
        assert conv.convert_to_latex(elem) == "x = 1"

    def test_single_cell_table_does_not_become_an_array(self, conv):
        elem = _namespaced("<mtable><mtr><mtd><mi>x</mi></mtd></mtr></mtable>")
        assert conv.convert_to_latex(elem) == "x"

    def test_rows_are_separated_by_a_latex_row_break(self, conv):
        elem = _mml(
            "<mtable><mtr><mtd><mn>1</mn></mtd></mtr><mtr><mtd><mn>2</mn></mtd></mtr></mtable>"
        )
        # A bare newline is not a row separator in a LaTeX array.
        assert "1 \\\\ 2" in conv._handle_mtable(elem)


class TestAccents:
    """``<mover>`` over a combining mark is an accent, not a superscript."""

    def test_macron_is_a_bar(self, conv):
        elem = _mml('<mover accent="true"><mi>η</mi><mo>¯</mo></mover>')
        assert conv._handle_mover(elem) == "\\bar{\\eta}"

    def test_dot_above_is_a_derivative(self, conv):
        elem = _mml('<mover accent="true"><mi>x</mi><mo>˙</mo></mover>')
        assert conv._handle_mover(elem) == "\\dot{x}"

    def test_hat(self, conv):
        elem = _mml("<mover><mi>p</mi><mo>^</mo></mover>")
        assert conv._handle_mover(elem) == "\\hat{p}"

    def test_arrow_above_is_a_vector(self, conv):
        elem = _mml("<mover><mi>v</mi><mo>→</mo></mover>")
        assert conv._handle_mover(elem) == "\\vec{v}"

    def test_underbrace(self, conv):
        elem = _mml("<munder><mi>x</mi><mo>⏟</mo></munder>")
        assert conv._handle_munder(elem) == "\\underbrace{x}"

    def test_an_accented_base_takes_a_script_without_extra_braces(self, conv):
        elem = _mml('<msub><mover accent="true"><mi>x</mi><mo>˙</mo></mover><mi>i</mi></msub>')
        assert conv._handle_msub(elem) == "\\dot{x}_{i}"

    def test_a_compound_base_is_braced(self, conv):
        elem = _mml("<msup><mrow><mo>(</mo><mi>x</mi><mo>)</mo></mrow><mn>2</mn></msup>")
        assert conv._handle_msup(elem) == "{(x)}^{2}"


class TestBigOperators:
    def test_sum_limits(self, conv):
        elem = _mml(
            "<munderover><mo>∑</mo><mrow><mi>j</mi><mo>=</mo><mn>1</mn></mrow>"
            "<mi>N</mi></munderover>"
        )
        assert conv._handle_munderover(elem) == "\\sum_{j = 1}^{N}"

    def test_integral_lower_limit_only(self, conv):
        elem = _mml("<munder><mo>∫</mo><mi>a</mi></munder>")
        assert conv._handle_munder(elem) == "\\int_{a}"


class TestUnicodeSymbols:
    def test_greek_identifier_becomes_a_command(self, conv):
        assert conv._handle_mi(_mml("<mi>θ</mi>")) == "\\theta"

    def test_greek_is_separated_from_the_letter_after_it(self, conv):
        elem = _mml("<mrow><mi>α</mi><mi>x</mi></mrow>")
        # "\alphax" is a different, undefined control word.
        assert conv._handle_mrow(elem) == "\\alpha x"

    def test_invisible_times_is_dropped(self, conv):
        elem = _mml("<mrow><mi>a</mi><mo>⁢</mo><mi>b</mi></mrow>")
        assert conv._handle_mrow(elem) == "ab"

    def test_fences_and_punctuation_are_not_padded(self, conv):
        elem = _mml("<mrow><mo>(</mo><mi>x</mi><mo>)</mo><mo>,</mo></mrow>")
        assert conv._handle_mrow(elem) == "(x),"


class TestMathVariant:
    def test_bold_mtext_is_not_flattened_to_text(self, conv):
        """PLOS writes a vector as <mtext mathvariant="bold">y</mtext>; \\text{y}
        loses the only thing separating it from the scalar y beside it."""
        assert conv._handle_mtext(_mml('<mtext mathvariant="bold">y</mtext>')) == "\\mathbf{y}"

    def test_plain_mtext_is_still_text(self, conv):
        assert conv._handle_mtext(_mml("<mtext>if</mtext>")) == "\\text{if}"

    def test_double_struck_identifier(self, conv):
        assert conv._handle_mi(_mml('<mi mathvariant="double-struck">R</mi>')) == "\\mathbb{R}"


class TestSemanticAnnotation:
    def test_author_supplied_tex_wins(self, conv):
        xml = (
            "<semantics><mrow><mi>x</mi></mrow>"
            '<annotation encoding="application/x-tex">\\frac{1}{2}</annotation></semantics>'
        )
        assert conv._handle_semantics(_mml(xml)) == "\\frac{1}{2}"

    def test_presentation_is_used_without_a_tex_annotation(self, conv):
        xml = (
            "<semantics><mrow><mi>x</mi></mrow>"
            '<annotation encoding="application/mathml-content">?</annotation></semantics>'
        )
        assert conv._handle_semantics(_mml(xml)) == "x"


class TestFenced:
    def test_mfenced_defaults_to_parentheses(self, conv):
        assert conv._handle_mfenced(_mml("<mfenced><mi>x</mi></mfenced>")) == "\\left(x\\right)"

    def test_mfenced_honours_open_and_close(self, conv):
        elem = _mml('<mfenced open="[" close="]"><mi>x</mi><mi>y</mi></mfenced>')
        assert conv._handle_mfenced(elem) == "\\left[x,y\\right]"


class TestSerializeMathml:
    def test_namespaced_math_is_serialized_without_an_invented_prefix(self):
        elem = _namespaced("<mi>x</mi>")
        xml = serialize_mathml(elem)
        assert xml.startswith("<math")
        assert f'xmlns="{MML}"' in xml
        assert "ns0:" not in xml
        assert "<mi>x</mi>" in xml

    def test_round_trips(self):
        elem = _namespaced("<mrow><mi>x</mi></mrow>")
        reparsed = DefusedET.fromstring(serialize_mathml(elem))
        assert reparsed.tag == f"{{{MML}}}math"

    def test_unnamespaced_math_is_left_alone(self):
        elem = _mml("<math><mi>x</mi></math>")
        assert serialize_mathml(elem) == "<math><mi>x</mi></math>"

    def test_self_closing_root_keeps_its_declaration(self):
        elem = DefusedET.fromstring(f'<math xmlns="{MML}"/>')
        xml = serialize_mathml(elem)
        assert xml in (f'<math xmlns="{MML}" />', f'<math xmlns="{MML}"/>')
