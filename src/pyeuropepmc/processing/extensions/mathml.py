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
        """Convert children of a MathML element to LaTeX."""
        parts: list[str] = []
        for child in parent:
            tag = self._local_tag(child.tag)
            handler = getattr(self, f"_handle_{tag}", None)
            if handler:
                parts.append(handler(child))
            else:
                # Fallback: treat unknown tags as plain text
                text = child.text or ""
                parts.append(self._resolve_entities(text))
            # Include tail text
            if child.tail:
                parts.append(self._resolve_entities(child.tail.strip()))
        if not parts:
            # No child elements - get raw text content
            text = parent.text or ""
            parts.append(self._resolve_entities(text.strip()))
        return " ".join(parts).strip()

    # ------------------------------------------------------------------
    # Element handlers
    # ------------------------------------------------------------------

    def _handle_mi(self, elem: ET.Element) -> str:
        """Identifier (variable, function name, symbol)."""
        text = self._get_elem_text(elem)
        if not text:
            return ""

        text = self._resolve_entities(text)

        # Multi-character identifiers are usually function names -> roman
        if len(text) > 1 and text.lower() in KNOWN_FUNCTIONS:
            return f"\\{text}" if text.islower() else f"\\operatorname{{{text}}}"
        if len(text) > 1:
            return f"\\operatorname{{{text}}}"
        return text

    def _handle_mn(self, elem: ET.Element) -> str:
        """Number."""
        text = self._resolve_entities(self._get_elem_text(elem))
        return text

    def _handle_mo(self, elem: ET.Element) -> str:
        """Operator."""
        text = self._get_elem_text(elem)
        text = self._resolve_entities(text)

        # Map common operators to LaTeX
        op_map = {
            "∑": r"\sum",
            "∏": r"\prod",
            "∫": r"\int",
            "∇": r"\nabla",
            "∂": r"\partial",
            "±": r"\pm",
            "×": r"\times",
            "÷": r"\div",
            "≤": r"\le",
            "≥": r"\ge",
            "≠": r"\ne",
            "≈": r"\approx",
            "≡": r"\equiv",
            "∞": r"\infty",
            "→": r"\rightarrow",
            "←": r"\leftarrow",
            "↔": r"\leftrightarrow",
            "⇒": r"\Rightarrow",
            "⇔": r"\Leftrightarrow",
            "∈": r"\in",
            "∉": r"\notin",
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
            "∅": r"\emptyset",
            "′": "'",
            "″": "''",
        }
        return op_map.get(text, text)

    def _handle_mtext(self, elem: ET.Element) -> str:
        """Text."""
        text = self._resolve_entities(self._get_elem_text(elem))
        return f"\\text{{{text}}}" if text else ""

    def _handle_msup(self, elem: ET.Element) -> str:
        """Superscript."""
        children = list(elem)
        if len(children) >= 2:
            base = self._convert_children(children[0])
            sup = self._convert_children(children[1])
            return f"{{{base}}}^{{{sup}}}"
        return self._convert_children(elem)

    def _handle_msub(self, elem: ET.Element) -> str:
        """Subscript."""
        children = list(elem)
        if len(children) >= 2:
            base = self._convert_children(children[0])
            sub = self._convert_children(children[1])
            return f"{{{base}}}_{{{sub}}}"
        return self._convert_children(elem)

    def _handle_msubsup(self, elem: ET.Element) -> str:
        """Subscript and superscript."""
        children = list(elem)
        if len(children) >= 3:
            base = self._convert_children(children[0])
            sub = self._convert_children(children[1])
            sup = self._convert_children(children[2])
            return f"{{{base}}}_{{{sub}}}^{{{sup}}}"
        return self._convert_children(elem)

    def _handle_mfrac(self, elem: ET.Element) -> str:
        """Fraction."""
        children = list(elem)
        if len(children) >= 2:
            num = self._convert_children(children[0])
            den = self._convert_children(children[1])
            return f"\\frac{{{num}}}{{{den}}}"
        return self._convert_children(elem)

    def _handle_msqrt(self, elem: ET.Element) -> str:
        """Square root."""
        content = self._convert_children(elem)
        return f"\\sqrt{{{content}}}"

    def _handle_mroot(self, elem: ET.Element) -> str:
        """n-th root."""
        children = list(elem)
        if len(children) >= 2:
            radicand = self._convert_children(children[0])
            degree = self._convert_children(children[1])
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
        """Style wrapper - just render children."""
        return self._convert_children(elem)

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
        """Underscript."""
        children = list(elem)
        if len(children) >= 2:
            base = self._convert_children(children[0])
            under = self._convert_children(children[1])
            return f"{{{base}}}_{{{under}}}"
        return self._convert_children(elem)

    def _handle_mover(self, elem: ET.Element) -> str:
        """Overscript."""
        children = list(elem)
        if len(children) >= 2:
            base = self._convert_children(children[0])
            over = self._convert_children(children[1])
            return f"{{{base}}}^{{{over}}}"
        return self._convert_children(elem)

    def _handle_munderover(self, elem: ET.Element) -> str:
        """Underscript and overscript."""
        children = list(elem)
        if len(children) >= 3:
            base = self._convert_children(children[0])
            under = self._convert_children(children[1])
            over = self._convert_children(children[2])
            return f"{{{base}}}_{{{under}}}^{{{over}}}"
        return self._convert_children(elem)

    def _handle_mmultiscripts(self, elem: ET.Element) -> str:
        """Multi-scripts (tensor notation)."""
        # Basic handling - just process children
        return self._convert_children(elem)

    def _handle_mtable(self, elem: ET.Element) -> str:
        """Matrix/table."""
        rows: list[str] = []
        for row in elem.findall("mtr") or elem.findall("mlabeledtr"):
            cells: list[str] = []
            for cell in row.findall("mtd"):
                cell_content = self._convert_children(cell)
                cells.append(cell_content)
            if cells:  # Skip empty rows
                rows.append(" & ".join(cells))
        if not rows:
            return ""
        num_cols = max(len(r.split(" & ")) for r in rows)
        align = "c" * num_cols
        return f"\\begin{{array}}{{{align}}} {chr(10).join(rows)} \\end{{array}}"

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _get_elem_text(elem: ET.Element) -> str:
        """Get the text content of an element, including tail text of children."""
        parts: list[str] = []
        if elem.text:
            parts.append(elem.text.strip())
        for child in elem:
            if child.tail:
                parts.append(child.tail.strip())
        return " ".join(parts).strip()

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
