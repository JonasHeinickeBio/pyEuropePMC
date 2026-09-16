"""
MathML to LaTeX conversion module.

Converts MathML expressions found in JATS XML articles to LaTeX representation
for better rendering and downstream use in scientific documentation, RAG pipelines,
and export formats.

Supported conversions:
- Basic inline math (``<mml:math display="inline">``)
- Display math (``<mml:math display="block">``)
- Common operators: +, -, *, /, =, <, >, ±, ×, ÷, ∑, ∏, ∫
- Greek letters (via named entities or ``<mi>`` elements)
- Subscripts and superscripts (``<msub>``, ``<msup>``, ``<msubsup>``)
- Fractions (``<mfrac>``)
- Square roots (``<msqrt>``)
- Token elements: ``<mi>``, ``<mo>``, ``<mn>``, ``<mtext>``
- MathML entities encoded in XML text content

Reference
---------
- MathML specification: https://www.w3.org/TR/MathML3/
- Docling handles MathML via pandoc; this module provides a lightweight alternative
"""

from __future__ import annotations

import copy
import logging
import re
from xml.etree import ElementTree as ET  # nosec B405

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named entity mapping (subset of common MathML entities)
# ---------------------------------------------------------------------------
MATHML_ENTITIES: dict[str, str] = {
    "&alpha;": r"\alpha",
    "&beta;": r"\beta",
    "&gamma;": r"\gamma",
    "&delta;": r"\delta",
    "&epsilon;": r"\epsilon",
    "&zeta;": r"\zeta",
    "&eta;": r"\eta",
    "&theta;": r"\theta",
    "&iota;": r"\iota",
    "&kappa;": r"\kappa",
    "&lambda;": r"\lambda",
    "&mu;": r"\mu",
    "&nu;": r"\nu",
    "&xi;": r"\xi",
    "&omicron;": r"o",
    "&pi;": r"\pi",
    "&rho;": r"\rho",
    "&sigma;": r"\sigma",
    "&tau;": r"\tau",
    "&upsilon;": r"\upsilon",
    "&phi;": r"\phi",
    "&chi;": r"\chi",
    "&psi;": r"\psi",
    "&omega;": r"\omega",
    "&Alpha;": r"A",
    "&Beta;": r"B",
    "&Gamma;": r"\Gamma",
    "&Delta;": r"\Delta",
    "&Theta;": r"\Theta",
    "&Lambda;": r"\Lambda",
    "&Xi;": r"\Xi",
    "&Pi;": r"\Pi",
    "&Sigma;": r"\Sigma",
    "&Phi;": r"\Phi",
    "&Psi;": r"\Psi",
    "&Omega;": r"\Omega",
    "&infin;": r"\infty",
    "&infty;": r"\infty",
    "&sum;": r"\sum",
    "&prod;": r"\prod",
    "&int;": r"\int",
    "&iint;": r"\iint",
    "&iiint;": r"\iiint",
    "&oint;": r"\oint",
    "&nabla;": r"\nabla",
    "&part;": r"\partial",
    "&sqrt;": r"\sqrt",
    "&radic;": r"\sqrt",
    "&frac;": r"\frac",
    "&plusmn;": r"\pm",
    "&times;": r"\times",
    "&div;": r"\div",
    "&le;": r"\le",
    "&ge;": r"\ge",
    "&ne;": r"\ne",
    "&equiv;": r"\equiv",
    "&approx;": r"\approx",
    "&sim;": r"\sim",
    "&cong;": r"\cong",
    "&prop;": r"\propto",
    "&forall;": r"\forall",
    "&exist;": r"\exists",
    "&empty;": r"\emptyset",
    "&isin;": r"\in",
    "&notin;": r"\notin",
    "&sub;": r"\subset",
    "&sup;": r"\supset",
    "&sube;": r"\subseteq",
    "&supe;": r"\supseteq",
    "&union;": r"\cup",
    "&intersect;": r"\cap",
    "&and;": r"\land",
    "&or;": r"\lor",
    "&larr;": r"\leftarrow",
    "&rarr;": r"\rightarrow",
    "&harr;": r"\leftrightarrow",
    "&mapsto;": r"\mapsto",
    "&circ;": r"\circ",
    "&bull;": r"\cdot",
    "&hellip;": r"\ldots",
    "&prime;": r"'",
    "&Prime;": r"''",
}

# Special function names that should be roman (not italic)
KNOWN_FUNCTIONS: set[str] = {
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "sinh",
    "cosh",
    "tanh",
    "coth",
    "arcsin",
    "arccos",
    "arctan",
    "log",
    "ln",
    "lg",
    "exp",
    "det",
    "dim",
    "ker",
    "hom",
    "lim",
    "max",
    "min",
    "sup",
    "inf",
    "gcd",
    "lcm",
    "mod",
    "Pr",
    "var",
    "cov",
    "corr",
}

# ---------------------------------------------------------------------------
# Unicode -> LaTeX
# ---------------------------------------------------------------------------
# A parsed document carries the resolved character, not the entity name: an
# <mi> holds "θ", never "&theta;". Passing it through produced LaTeX that only
# compiles under a Unicode-aware engine, and a ``\theta`` a reader can type is
# the point of converting at all.
UNICODE_LETTERS: dict[str, str] = {
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ε": r"\varepsilon",
    "ϵ": r"\epsilon",
    "ζ": r"\zeta",
    "η": r"\eta",
    "θ": r"\theta",
    "ϑ": r"\vartheta",
    "ι": r"\iota",
    "κ": r"\kappa",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "ξ": r"\xi",
    "π": r"\pi",
    "ϖ": r"\varpi",
    "ρ": r"\rho",
    "ϱ": r"\varrho",
    "σ": r"\sigma",
    "ς": r"\varsigma",
    "τ": r"\tau",
    "υ": r"\upsilon",
    "φ": r"\varphi",
    "ϕ": r"\phi",
    "χ": r"\chi",
    "ψ": r"\psi",
    "ω": r"\omega",
    "Γ": r"\Gamma",
    "Δ": r"\Delta",
    "Θ": r"\Theta",
    "Λ": r"\Lambda",
    "Ξ": r"\Xi",
    "Π": r"\Pi",
    "Σ": r"\Sigma",
    "Υ": r"\Upsilon",
    "Φ": r"\Phi",
    "Ψ": r"\Psi",
    "Ω": r"\Omega",
    "ℓ": r"\ell",
    "ℏ": r"\hbar",
    "ℜ": r"\Re",
    "ℑ": r"\Im",
    "℘": r"\wp",
    "∅": r"\emptyset",
    "∞": r"\infty",
    "∂": r"\partial",
    "∇": r"\nabla",
}

UNICODE_OPERATORS: dict[str, str] = {
    "∑": r"\sum",
    "∏": r"\prod",
    "∐": r"\coprod",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "⋀": r"\bigwedge",
    "⋁": r"\bigvee",
    "⋂": r"\bigcap",
    "⋃": r"\bigcup",
    "∇": r"\nabla",
    "∂": r"\partial",
    "±": r"\pm",
    "∓": r"\mp",
    "×": r"\times",
    "÷": r"\div",
    "⋅": r"\cdot",
    "∗": r"\ast",
    "∘": r"\circ",
    "≤": r"\le",
    "≥": r"\ge",
    "≠": r"\ne",
    "≈": r"\approx",
    "≅": r"\cong",
    "≡": r"\equiv",
    "∼": r"\sim",
    "≃": r"\simeq",
    "≪": r"\ll",
    "≫": r"\gg",
    "∝": r"\propto",
    "∞": r"\infty",
    "→": r"\rightarrow",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow",
    "⇐": r"\Leftarrow",
    "⇔": r"\Leftrightarrow",
    "↦": r"\mapsto",
    "∈": r"\in",
    "∉": r"\notin",
    "∋": r"\ni",
    "⊂": r"\subset",
    "⊃": r"\supset",
    "⊆": r"\subseteq",
    "⊇": r"\supseteq",
    "∪": r"\cup",
    "∩": r"\cap",
    "∧": r"\land",
    "∨": r"\lor",
    "¬": r"\neg",
    "∀": r"\forall",
    "∃": r"\exists",
    "∄": r"\nexists",
    "∅": r"\emptyset",
    "∠": r"\angle",
    "⊥": r"\perp",
    "∥": r"\parallel",
    "…": r"\ldots",
    "⋯": r"\cdots",
    "⋮": r"\vdots",
    "⋱": r"\ddots",
    "′": "'",
    "−": "-",
    "–": "-",
    "—": "-",
    "⁢": "",  # invisible times
    "⁡": "",  # function application
    "⁣": "",  # invisible separator
    " ": r"\ ",
}

#: An accent above or below the base rather than a script position.
#: ``<mover><mi>η</mi><mo>¯</mo></mover>`` is "eta bar", not "eta to the power
#: of a macron": the old ``{\eta}^{¯}`` was both unreadable and uncompilable.
OVER_ACCENTS: dict[str, str] = {
    "¯": r"\bar",
    "‾": r"\overline",
    "ˉ": r"\bar",
    "^": r"\hat",
    "ˆ": r"\hat",
    "~": r"\tilde",
    "˜": r"\tilde",
    "∼": r"\tilde",
    "˙": r"\dot",
    "¨": r"\ddot",
    "⃛": r"\dddot",
    "→": r"\vec",
    "⇀": r"\vec",
    "ˇ": r"\check",
    "˘": r"\breve",
    "´": r"\acute",
    "`": r"\grave",
    "⏞": r"\overbrace",
    "⏜": r"\overbrace",
}

UNDER_ACCENTS: dict[str, str] = {
    "_": r"\underline",
    "―": r"\underline",
    "‾": r"\underline",
    "¯": r"\underline",
    "⏟": r"\underbrace",
    "⏝": r"\underbrace",
}

#: Operators that take their limits above and below rather than beside.
BIG_OPERATORS: frozenset[str] = frozenset(
    {
        r"\sum",
        r"\prod",
        r"\coprod",
        r"\int",
        r"\iint",
        r"\iiint",
        r"\oint",
        r"\bigcup",
        r"\bigcap",
        r"\bigvee",
        r"\bigwedge",
        r"\lim",
        r"\max",
        r"\min",
        r"\sup",
        r"\inf",
        r"\limsup",
        r"\liminf",
    }
)

#: Operators that read as a binary or relational sign and want air around
#: them. Fences and punctuation do not: ``( x )`` and ``\theta ,`` are worse
#: than ``(x)`` and ``\theta,``.
SPACED_OPERATORS: frozenset[str] = frozenset(
    {
        "+",
        "-",
        "=",
        "<",
        ">",
        r"\pm",
        r"\mp",
        r"\times",
        r"\div",
        r"\cdot",
        r"\ast",
        r"\le",
        r"\ge",
        r"\ne",
        r"\approx",
        r"\cong",
        r"\equiv",
        r"\sim",
        r"\simeq",
        r"\ll",
        r"\gg",
        r"\propto",
        r"\rightarrow",
        r"\leftarrow",
        r"\leftrightarrow",
        r"\Rightarrow",
        r"\Leftarrow",
        r"\Leftrightarrow",
        r"\mapsto",
        r"\in",
        r"\notin",
        r"\ni",
        r"\subset",
        r"\supset",
        r"\subseteq",
        r"\supseteq",
        r"\cup",
        r"\cap",
        r"\land",
        r"\lor",
    }
)

#: ``mathvariant`` values mapped to the LaTeX font command that carries them.
MATH_VARIANTS: dict[str, str] = {
    "bold": r"\mathbf",
    "italic": r"\mathit",
    "bold-italic": r"\boldsymbol",
    "double-struck": r"\mathbb",
    "fraktur": r"\mathfrak",
    "bold-fraktur": r"\mathfrak",
    "script": r"\mathcal",
    "bold-script": r"\mathcal",
    "sans-serif": r"\mathsf",
    "bold-sans-serif": r"\mathsf",
    "monospace": r"\mathtt",
    "normal": r"\mathrm",
}

#: The MathML namespace, and the prefix a serialized fragment should carry.
MATHML_NS = "http://www.w3.org/1998/Math/MathML"

#: A LaTeX control word at the very end of a string: "\alpha" followed by "x"
#: must not be written "\alphax".
_TRAILING_COMMAND = re.compile(r"\\[A-Za-z]+$")

#: A single LaTeX atom: one character, one control word, or a control word
#: with its braced argument. A script binds to the whole of one of these, so
#: ``\dot{x}_{i}`` needs no braces of its own.
_ATOM = re.compile(r"\A(?:.|\\[A-Za-z]+(?:\{[^{}]*\})?|\{[^{}]*\})\Z")


def _is_atom(latex: str) -> bool:
    """Whether ``latex`` binds as a single unit under a sub- or superscript."""
    return bool(_ATOM.match(latex))


def serialize_mathml(element: ET.Element) -> str:
    """Serialize a MathML element as a standalone, prefix-free fragment.

    ``ET.tostring`` invents a prefix for every namespace it meets, so a
    ``<mml:math>`` lifted out of a Europe PMC document came back as
    ``<ns0:math xmlns:ns0="...">`` - valid XML that no MathML renderer is
    obliged to accept and that no two documents spell the same way. Declaring
    MathML as the default namespace gives the form every renderer takes.

    Falls back to a plain serialization for a tree whose tags are not
    namespaced, which is what a hand-written fixture and a namespace-stripped
    document both produce.
    """
    copied = copy.deepcopy(element)
    namespaced = False
    prefix = f"{{{MATHML_NS}}}"
    for node in copied.iter():
        if isinstance(node.tag, str) and node.tag.startswith(prefix):
            node.tag = node.tag[len(prefix) :]
            namespaced = True

    xml = ET.tostring(copied, encoding="unicode")
    if not namespaced:
        return xml
    # ElementTree writes no xmlns for a tag it does not consider namespaced,
    # so the declaration is added to the opening tag by hand.
    head, sep, tail = xml.partition(">")
    if not sep:  # pragma: no cover - tostring always emits a start tag
        return xml
    closing = "/" if head.rstrip().endswith("/") else ""
    if closing:
        head = head.rstrip()[:-1].rstrip()
    return f'{head} xmlns="{MATHML_NS}"{closing}{sep}{tail}'


class MathMLConverter:
    """
    Converts MathML elements to LaTeX representation.

    Parameters
    ----------
    inline : bool, optional
        Whether the math is inline (``$...$``) or display (``$$...$$``).
        Auto-detected from MathML ``display`` attribute by default.
    """

    def __init__(self, inline: bool | None = None):
        self._force_inline = inline

    def convert(self, mathml_element: ET.Element) -> str:
        """
        Convert a MathML element to LaTeX.

        Parameters
        ----------
        mathml_element : ET.Element
            The ``<mml:math>`` element or any MathML token element.

        Returns
        -------
        str
            LaTeX representation of the math expression.
        """
        display = mathml_element.get("display", "")
        is_inline = (
            self._force_inline
            if self._force_inline is not None
            else (display == "inline" or display == "")
        )
        delimiter = "$" if is_inline else "$$"

        latex = self._convert_children(mathml_element)

        return f"{delimiter}{latex}{delimiter}"

    def convert_to_latex(self, mathml_element: ET.Element) -> str:
        """
        Convert to LaTeX without delimiter wrapping.

        Useful when the caller wants to handle delimiters themselves.

        Parameters
        ----------
        mathml_element : ET.Element
            The MathML element to convert.

        Returns
        -------
        str
            Raw LaTeX string.
        """
        return self._convert_children(mathml_element)

    def _convert_children(self, parent: ET.Element) -> str:
        r"""Convert the children of a MathML element to LaTeX.

        Parts are joined by ``_join``, not by a space between every one:
        ``( x )`` and ``\theta ,`` are worse than ``(x)`` and ``\theta,``,
        while ``\alpha`` followed by ``x`` genuinely needs the gap.
        """
        parts: list[tuple[str, str]] = []
        for child in parent:
            if not isinstance(child.tag, str):  # comment or processing instruction
                continue
            tag = self._local_tag(child.tag)
            handler = getattr(self, f"_handle_{tag}", None)
            if handler:
                parts.append((tag, handler(child)))
            else:
                # Unknown element: keep whatever text it holds rather than
                # dropping the subtree.
                parts.append((tag, self._resolve_entities("".join(child.itertext()).strip())))
            if child.tail and child.tail.strip():
                parts.append(("", self._resolve_entities(child.tail.strip())))
        if not parts:
            # A token element with no children of its own.
            return self._resolve_entities((parent.text or "").strip())
        return self._join(parts)

    @staticmethod
    def _join(parts: list[tuple[str, str]]) -> str:
        """Concatenate ``(tag, latex)`` pairs, spacing only where LaTeX needs it."""
        pieces: list[str] = []
        previous_tag = ""
        previous_latex = ""
        for tag, latex in parts:
            if not latex:
                continue
            if pieces and MathMLConverter._needs_space(previous_tag, previous_latex, tag, latex):
                pieces.append(" ")
            pieces.append(latex)
            previous_tag, previous_latex = tag, latex
        return "".join(pieces).strip()

    @staticmethod
    def _needs_space(left_tag: str, left: str, right_tag: str, right: str) -> bool:
        """Whether a space belongs between two adjacent LaTeX fragments."""
        # "\alpha" then "x" would read as one control word.
        if _TRAILING_COMMAND.search(left) and (right[0].isalnum() or right[0] == "\\"):
            return True
        # Binary and relational signs read better with air; fences and
        # punctuation do not.
        return (left_tag == "mo" and left in SPACED_OPERATORS) or (
            right_tag == "mo" and right in SPACED_OPERATORS
        )

    # ------------------------------------------------------------------
    # Element handlers
    # ------------------------------------------------------------------

    def _handle_mi(self, elem: ET.Element) -> str:
        """Identifier (variable, function name, symbol)."""
        text = self._get_elem_text(elem)
        if not text:
            return ""

        text = self._resolve_entities(text)
        variant = elem.get("mathvariant", "")

        if len(text) == 1:
            symbol = UNICODE_LETTERS.get(text, UNICODE_OPERATORS.get(text, text))
            return self._apply_variant(symbol, variant)

        # Multi-character identifiers are usually function or operator names.
        if text.lower() in KNOWN_FUNCTIONS:
            return f"\\{text}" if text.islower() else f"\\operatorname{{{text}}}"
        if variant:
            return self._apply_variant(text, variant)
        return f"\\operatorname{{{text}}}"

    def _handle_mn(self, elem: ET.Element) -> str:
        """Number."""
        text = self._resolve_entities(self._get_elem_text(elem))
        return self._apply_variant(text, elem.get("mathvariant", "")) if text else ""

    def _handle_mo(self, elem: ET.Element) -> str:
        """Operator."""
        text = self._resolve_entities(self._get_elem_text(elem))
        if not text:
            return ""
        if text in UNICODE_OPERATORS:
            return UNICODE_OPERATORS[text]
        if len(text) == 1 and text in UNICODE_LETTERS:
            return UNICODE_LETTERS[text]
        return self._escape_text(text) if text.isalnum() else text

    def _handle_mtext(self, elem: ET.Element) -> str:
        r"""Text.

        ``mathvariant`` is honoured here rather than dropped: PLOS writes a
        vector as ``<mtext mathvariant="bold">y</mtext>``, and rendering that
        as ``\text{y}`` loses the only thing that distinguishes it from the
        scalar ``y`` in the same equation.
        """
        text = self._resolve_entities(self._get_elem_text(elem))
        if not text:
            return ""
        variant = elem.get("mathvariant", "")
        if variant and variant in MATH_VARIANTS:
            return self._apply_variant(text, variant)
        return f"\\text{{{text}}}"

    def _handle_mspace(self, elem: ET.Element) -> str:
        """Explicit space."""
        return "\\ "

    def _handle_msup(self, elem: ET.Element) -> str:
        """Superscript."""
        children = self._element_children(elem)
        if len(children) >= 2:
            base = self._script_base(children[0])
            sup = self._convert_children_of(children[1])
            return f"{base}^{{{sup}}}"
        return self._convert_children(elem)

    def _handle_msub(self, elem: ET.Element) -> str:
        """Subscript."""
        children = self._element_children(elem)
        if len(children) >= 2:
            base = self._script_base(children[0])
            sub = self._convert_children_of(children[1])
            return f"{base}_{{{sub}}}"
        return self._convert_children(elem)

    def _handle_msubsup(self, elem: ET.Element) -> str:
        """Subscript and superscript."""
        children = self._element_children(elem)
        if len(children) >= 3:
            base = self._script_base(children[0])
            sub = self._convert_children_of(children[1])
            sup = self._convert_children_of(children[2])
            return f"{base}_{{{sub}}}^{{{sup}}}"
        return self._convert_children(elem)

    def _handle_mfrac(self, elem: ET.Element) -> str:
        """Fraction."""
        children = self._element_children(elem)
        if len(children) >= 2:
            num = self._convert_children_of(children[0])
            den = self._convert_children_of(children[1])
            if elem.get("bevelled") == "true":
                return f"{{{num}}}/{{{den}}}"
            return f"\\frac{{{num}}}{{{den}}}"
        return self._convert_children(elem)

    def _handle_msqrt(self, elem: ET.Element) -> str:
        """Square root."""
        content = self._convert_children(elem)
        return f"\\sqrt{{{content}}}"

    def _handle_mroot(self, elem: ET.Element) -> str:
        """n-th root."""
        children = self._element_children(elem)
        if len(children) >= 2:
            radicand = self._convert_children_of(children[0])
            degree = self._convert_children_of(children[1])
            return f"\\sqrt[{degree}]{{{radicand}}}"
        return self._convert_children(elem)

    def _handle_mrow(self, elem: ET.Element) -> str:
        """Row (grouping)."""
        return self._convert_children(elem)

    def _handle_merror(self, elem: ET.Element) -> str:
        """Error - just render children."""
        return self._convert_children(elem)

    def _handle_mpadded(self, elem: ET.Element) -> str:
        """Padded - just render children."""
        return self._convert_children(elem)

    def _handle_mphantom(self, elem: ET.Element) -> str:
        """Phantom (invisible)."""
        content = self._convert_children(elem)
        return f"\\phantom{{{content}}}"

    def _handle_mstyle(self, elem: ET.Element) -> str:
        """Style wrapper."""
        content = self._convert_children(elem)
        return self._apply_variant(content, elem.get("mathvariant", ""), wrap=False)

    def _handle_mfenced(self, elem: ET.Element) -> str:
        """Fenced expression (deprecated in MathML 3, still widely emitted)."""
        opener = elem.get("open", "(")
        closer = elem.get("close", ")")
        separator = elem.get("separators", ",").strip() or ","
        pieces = [self._convert_children_of(child) for child in self._element_children(elem)]
        inner = separator.join(p for p in pieces if p)
        return f"\\left{opener or '.'}{inner}\\right{closer or '.'}"

    def _handle_menclose(self, elem: ET.Element) -> str:
        """Enclosed expression."""
        notation = elem.get("notation", "longdiv")
        content = self._convert_children(elem)
        # Handle common notations
        if notation == "box":
            return f"\\boxed{{{content}}}"
        if notation in ("circle", "roundedbox"):
            return f"\\boxed{{{content}}}"
        return content

    def _handle_munder(self, elem: ET.Element) -> str:
        """Underscript, an under-accent, or the lower limit of a big operator."""
        children = self._element_children(elem)
        if len(children) < 2:
            return self._convert_children(elem)
        base = self._convert_children_of(children[0])
        under_raw = self._raw_token_text(children[1])
        if under_raw in UNDER_ACCENTS:
            return f"{UNDER_ACCENTS[under_raw]}{{{base}}}"
        under = self._convert_children_of(children[1])
        if base in BIG_OPERATORS:
            return f"{base}_{{{under}}}"
        return f"\\underset{{{under}}}{{{base}}}"

    def _handle_mover(self, elem: ET.Element) -> str:
        """Overscript, an accent, or the upper limit of a big operator."""
        children = self._element_children(elem)
        if len(children) < 2:
            return self._convert_children(elem)
        base = self._convert_children_of(children[0])
        over_raw = self._raw_token_text(children[1])
        if over_raw in OVER_ACCENTS:
            return f"{OVER_ACCENTS[over_raw]}{{{base}}}"
        over = self._convert_children_of(children[1])
        if base in BIG_OPERATORS:
            return f"{base}^{{{over}}}"
        return f"\\overset{{{over}}}{{{base}}}"

    def _handle_munderover(self, elem: ET.Element) -> str:
        """Underscript and overscript - the limits of a sum, product or integral."""
        children = self._element_children(elem)
        if len(children) >= 3:
            base = self._convert_children_of(children[0])
            under = self._convert_children_of(children[1])
            over = self._convert_children_of(children[2])
            if base in BIG_OPERATORS:
                return f"{base}_{{{under}}}^{{{over}}}"
            return f"\\underset{{{under}}}{{\\overset{{{over}}}{{{base}}}}}"
        return self._convert_children(elem)

    def _handle_mmultiscripts(self, elem: ET.Element) -> str:
        """Multi-scripts (tensor notation)."""
        # Basic handling - just process children
        return self._convert_children(elem)

    def _handle_semantics(self, elem: ET.Element) -> str:
        """Presentation MathML paired with an annotation.

        A ``<annotation encoding="application/x-tex">`` is the author's own
        LaTeX for the expression. Nothing this module derives can beat it, so
        it wins when it is there.
        """
        for child in elem:
            if not isinstance(child.tag, str):
                continue
            if self._local_tag(child.tag) != "annotation":
                continue
            encoding = child.get("encoding", "").lower()
            if encoding in ("application/x-tex", "application/x-latex", "text/x-tex"):
                annotation = (child.text or "").strip()
                if annotation:
                    return annotation
        return self._convert_children(elem)

    def _handle_annotation(self, elem: ET.Element) -> str:
        """A bare annotation outside <semantics>: its text is not presentation."""
        return ""

    def _handle_annotation_xml(self, elem: ET.Element) -> str:
        """``<annotation-xml>`` holds Content MathML, not presentation."""
        return ""

    def _handle_mtable(self, elem: ET.Element) -> str:
        """Matrix, equation array, or a single-cell layout wrapper.

        ``findall("mtr")`` matched nothing on a namespaced document - which is
        every document Europe PMC serves - so every table returned "" and with
        it every PLOS display formula, all of which wrap their content in a
        one-row ``<mtable>``. Rows are found by local name now, and a wrapper
        holding a single cell unwraps instead of becoming a 1x1 array.
        """
        rows: list[str] = []
        for row in self._element_children(elem):
            if self._local_tag(row.tag) not in ("mtr", "mlabeledtr"):
                continue
            cells = [
                self._convert_children_of(cell)
                for cell in self._element_children(row)
                if self._local_tag(cell.tag) == "mtd"
            ]
            if cells:
                rows.append(" & ".join(cells))
        if not rows:
            return self._convert_children(elem)
        if len(rows) == 1 and " & " not in rows[0]:
            return rows[0]
        num_cols = max(len(r.split(" & ")) for r in rows)
        align = "c" * num_cols
        body = " \\\\ ".join(rows)
        return f"\\begin{{array}}{{{align}}} {body} \\end{{array}}"

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _element_children(elem: ET.Element) -> list[ET.Element]:
        """Child elements, skipping comments and processing instructions."""
        return [child for child in elem if isinstance(child.tag, str)]

    def _convert_children_of(self, elem: ET.Element) -> str:
        """LaTeX for one element, whether it is a token or a container."""
        tag = self._local_tag(elem.tag)
        handler = getattr(self, f"_handle_{tag}", None)
        if handler:
            return str(handler(elem))
        return self._convert_children(elem)

    def _script_base(self, elem: ET.Element) -> str:
        r"""The base of a script, braced only when the script would mis-bind.

        ``{x}^{2}`` and ``x^{2}`` render alike, but the braces multiply with
        nesting: a subscripted accent came out as ``{{\dot{x}}}_{i}``.
        """
        base = self._convert_children_of(elem)
        if _is_atom(base):
            return base
        return f"{{{base}}}"

    def _raw_token_text(self, elem: ET.Element) -> str:
        """The literal character of a token element, for accent lookup."""
        if self._local_tag(elem.tag) not in ("mo", "mi", "mtext"):
            return ""
        return "".join(elem.itertext()).strip()

    @staticmethod
    def _apply_variant(content: str, variant: str, wrap: bool = True) -> str:
        """Wrap ``content`` in the LaTeX font command for a ``mathvariant``."""
        command = MATH_VARIANTS.get(variant)
        if not command:
            return content
        if not wrap and not content:
            return content
        return f"{command}{{{content}}}"

    @staticmethod
    def _escape_text(text: str) -> str:
        """An alphanumeric operator is a word, and words are upright in math."""
        return f"\\operatorname{{{text}}}"

    @staticmethod
    def _get_elem_text(elem: ET.Element) -> str:
        """Get the text content of an element, including tail text of children."""
        parts: list[str] = []
        if elem.text:
            parts.append(elem.text.strip())
        for child in elem:
            if child.tail:
                parts.append(child.tail.strip())
        return " ".join(p for p in parts if p).strip()

    @staticmethod
    def _resolve_entities(text: str) -> str:
        """Resolve XML/HTML entities to LaTeX commands."""
        if not text:
            return ""

        # Replace known MathML entities
        for entity, latex in MATHML_ENTITIES.items():
            text = text.replace(entity, latex)

        # Handle numeric entities like &#x3B1; or &#945;
        text = re.sub(
            r"&#(\d+);",
            lambda m: chr(int(m.group(1))),
            text,
        )
        text = re.sub(
            r"&#x([0-9a-fA-F]+);",
            lambda m: chr(int(m.group(1), 16)),
            text,
        )

        return text

    @staticmethod
    def _local_tag(tag: str) -> str:
        """Strip namespace from a tag name."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def convert_mathml(cls, mathml_element: ET.Element) -> str:
        """
        Quick conversion of a MathML element to LaTeX (inline).

        Parameters
        ----------
        mathml_element : ET.Element
            The MathML element to convert.

        Returns
        -------
        str
            LaTeX math string wrapped in ``$...$``.
        """
        return cls().convert(mathml_element)

    @classmethod
    def convert_display_mathml(cls, mathml_element: ET.Element) -> str:
        """
        Quick conversion of a MathML element to display LaTeX.

        Parameters
        ----------
        mathml_element : ET.Element
            The MathML element to convert.

        Returns
        -------
        str
            LaTeX math string wrapped in ``$$...$$``.
        """
        return cls(inline=False).convert(mathml_element)

    def to_html(self, mathml_element: ET.Element) -> str:
        """
        Convert MathML to HTML with MathJax-compatible LaTeX.

        Parameters
        ----------
        mathml_element : ET.Element
            The MathML element to convert.

        Returns
        -------
        str
            HTML fragment with the math rendered via MathJax-compatible LaTeX.
        """
        latex = self.convert_to_latex(mathml_element)
        display = mathml_element.get("display", "")
        is_inline = (
            self._force_inline
            if self._force_inline is not None
            else (display == "inline" or display == "")
        )

        if is_inline:
            return f'<span class="math-inline">\\({latex}\\)</span>'
        return f'<div class="math-display">\\[{latex}\\]</div>'

    def to_svg(self, mathml_element: ET.Element) -> str:
        """
        Convert MathML to SVG using latex + dvisvgm (requires system LaTeX).

        .. note::
           This method requires ``latex`` and ``dvisvgm`` to be installed on the
           system PATH. If they are not available, a ``RuntimeError`` is raised.

        Parameters
        ----------
        mathml_element : ET.Element
            The MathML element to convert.

        Returns
        -------
        str
            SVG string of the rendered math expression.

        Raises
        ------
        RuntimeError
            If system LaTeX tools are not installed.
        """
        import subprocess  # nosec B404
        import tempfile

        latex_str = self.convert_to_latex(mathml_element)
        display = mathml_element.get("display", "")
        is_inline = (
            self._force_inline
            if self._force_inline is not None
            else (display == "inline" or display == "")
        )

        # Build a minimal LaTeX document
        if is_inline:
            doc = (
                "\\documentclass[preview]{standalone}\\begin{document}"
                f"${latex_str}$\\end{{document}}"
            )
        else:
            doc = (
                "\\documentclass[preview]{standalone}\\begin{document}"
                f"\\[{latex_str}\\]\\end{{document}}"
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = f"{tmpdir}/math.tex"
            with open(tex_path, "w") as f:
                f.write(doc)

            # Run latex -> dvi
            try:
                subprocess.run(  # nosec B603, B607
                    ["latex", "-interaction=nonstopmode", "-output-directory", tmpdir, "math.tex"],
                    capture_output=True,
                    timeout=30,
                    check=True,
                )
            except FileNotFoundError as e:
                raise RuntimeError(
                    "System LaTeX (latex) not found. Install TeX Live or similar."
                ) from e
            except subprocess.CalledProcessError as e:
                logger.warning(f"LaTeX compilation failed: {e.stderr.decode()}")
                raise RuntimeError(f"LaTeX compilation failed: {e.stderr.decode()}") from e

            # Run dvisvgm -> svg
            try:
                result = subprocess.run(  # nosec B603, B607
                    ["dvisvgm", "--no-fonts", "--stdout", f"{tmpdir}/math.dvi"],
                    capture_output=True,
                    timeout=30,
                    check=True,
                )
                return result.stdout.decode("utf-8")
            except FileNotFoundError as e:
                raise RuntimeError(
                    "dvisvgm not found. Install it (e.g., apt install dvisvgm)."
                ) from e
            except subprocess.CalledProcessError as e:
                logger.warning(f"dvisvgm conversion failed: {e.stderr.decode()}")
                raise RuntimeError(f"SVG conversion failed: {e.stderr.decode()}") from e
