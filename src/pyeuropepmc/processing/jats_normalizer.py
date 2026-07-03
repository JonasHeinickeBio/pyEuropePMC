"""
JATS XML Normalizer for text mining pipelines.

Provides a configurable normalization pipeline for JATS/NLM XML documents,
implementing best practices from the text mining literature:

- Entity normalization (XML entities, Unicode, dashes, hyphens)
- Display markup stripping (bold, italic, sup, sub, xref, etc.)
- Section type canonicalization (PMC-style regex mapping)
- Metadata & identifier normalization (ORCID, ROR, pub-id-type)
- Whitespace & text scatter normalization
- Optional BioC JSON output format

The normalizer operates on ``xml.etree.ElementTree`` objects (the same
format used throughout PyEuropePMC) and produces either a normalized
tree or structured Python dicts for downstream processing.

References
----------
- JATS4R Recommendations: https://jats4r.org/
- PMC BioC: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4954965/
- JATSdecoder (R): https://github.com/JensKeilwagen/JATSdecoder
- TurkuNLP PubMed parses: https://github.com/TurkuNLP/parsed_pmc

Examples
--------
>>> from pyeuropepmc.processing.jats_normalizer import JATSNormalizer
>>> normalizer = JATSNormalizer(section_types=True, strip_markdown=True)
>>> result = normalizer.normalize_xml(xml_string)
>>> result["normalized_root"]  # ElementTree root
>>> result["sections"][0]  # {"type": "methods", "title": "...", "text": "..."}
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import html
import logging
import re
from typing import Any
import unicodedata
from xml.etree import ElementTree as ET  # nosec B405

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section type canonicalization (PMC-style)
# ---------------------------------------------------------------------------

# Maps normalized lowercase heading text → canonical section type.
# Ordered by specificity; first match wins.
SECTION_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Introduction
    (re.compile(r"^(?:introduction|general\s+introduction)", re.I), "intro"),
    # Methods
    (
        re.compile(
            r"^(?:materials?\s+and\s+methods?|methods?|methodology|experimental(?:\s+(?:procedures?|section|design|setup))?|study\s+(?:design|population|participants?|sample|data)|statistical\s+(?:analysis|methods?)|data\s+(?:collection|analysis|extraction|sources?)|search\s+(?:strategy|strategy|methods?)|inclusion\s+and\s+exclusion|eligibility\s+criteria|ethical|protocol|procedure|techniques?|approach|computational)",
            re.I,
        ),
        "methods",
    ),
    # Results
    (
        re.compile(
            r"^(?:results?(?:\s+and\s+discussion)?|findings?|observations?|outcome(?:s|s\s+data)?|main\s+results?|statistical\s+results?|clinical\s+results?|experimental\s+results?)",
            re.I,
        ),
        "results",
    ),
    # Discussion
    (
        re.compile(
            r"^(?:discussion|interpretation|comment|implications?|considerations?|limitations?|general\s+discussion)",
            re.I,
        ),
        "discussion",
    ),
    # Conclusion
    (
        re.compile(
            r"^(?:conclusions?|summary|concluding\s+(?:remarks?|comments?)|final\s+remarks?|closing|wrap[\s-]?up)",
            re.I,
        ),
        "conclusion",
    ),
    # Abstract
    (
        re.compile(
            r"^(?:abstract|summary\s+abstract|graphical\s+abstract|structured\s+abstract)", re.I
        ),
        "abstract",
    ),
    # Background
    (re.compile(r"^(?:background|context|rationale)", re.I), "background"),
    # Acknowledgments
    (re.compile(r"^(?:acknowledgment(?:s)?|acknowledgement(?:s)?)", re.I), "ack"),
    # References
    (
        re.compile(r"^(?:references?|bibliography|literature\s+cited|works?\s+cited)", re.I),
        "references",
    ),
    # Supplementary
    (
        re.compile(
            r"^(?:supplementary|supplement(?:al|ary)?\s+(?:materials?|data|information|file|appendix))",
            re.I,
        ),
        "supplementary",
    ),
    # Appendices
    (re.compile(r"^(?:appendix|appendices|annex(?:e|es)?)", re.I), "appendix"),
    # Author contributions
    (
        re.compile(
            r"^(?:author\s+(?:contributions?|contributions?|information)|contributor\s+ship)", re.I
        ),
        "author_contributions",
    ),
    # Data availability
    (
        re.compile(
            r"^(?:data\s+(?:availability|access|sharing|statement)|data\s+resources)", re.I
        ),
        "data_availability",
    ),
    # Funding
    (
        re.compile(
            r"^(?:funding|financial\s+(?:support|disclosure|declaration)|grant(?:s|ed\s+by)?)",
            re.I,
        ),
        "funding",
    ),
    # Ethics / conflict of interest
    (
        re.compile(
            r"^(?:ethics|competing\s+interests?|conflict(?:s)?\s+of\s+interest|disclosure|declarations?|consent)",
            re.I,
        ),
        "ethics",
    ),
    # Figure/table captions — structural
    (
        re.compile(r"^(?:figure|fig(?:ure)?\.?\s*\d|table|supplementary\s+(?:fig|table))", re.I),
        "caption",
    ),
]


# ---------------------------------------------------------------------------
# Unicode normalization tables
# ---------------------------------------------------------------------------

# Various Unicode representations of dashes, hyphens, and minus signs
_DASH_CHARS: dict[str, str] = {
    "\u2010": "-",  # HYPHEN
    "\u2011": "-",  # NON-BREAKING HYPHEN
    "\u2012": "-",  # FIGURE DASH
    "\u2013": "-",  # EN DASH
    "\u2014": "-",  # EM DASH
    "\u2015": "-",  # HORIZONTAL BAR / QUOTATION DASH
    "\u2053": "-",  # SWUNG DASH
    "\u2212": "-",  # MINUS SIGN
    "\ufe58": "-",  # SMALL EM DASH
    "\ufe63": "-",  # SMALL HYPHEN-MINUS
    "\uff0d": "-",  # FULLWIDTH HYPHEN-MINUS
}

# Various Unicode representations of spaces → ASCII space
_SPACE_CHARS: dict[str, str] = {
    "\u00a0": " ",  # NO-BREAK SPACE
    "\u2000": " ",  # EN QUAD
    "\u2001": " ",  # EM QUAD
    "\u2002": " ",  # EN SPACE
    "\u2003": " ",  # EM SPACE
    "\u2004": " ",  # THREE-PER-EM SPACE
    "\u2005": " ",  # FOUR-PER-EM SPACE
    "\u2006": " ",  # SIX-PER-EM SPACE
    "\u2007": " ",  # FIGURE SPACE
    "\u2008": " ",  # PUNCTUATION SPACE
    "\u2009": " ",  # THIN SPACE
    "\u200a": " ",  # HAIR SPACE
    "\u200b": "",  # ZERO WIDTH SPACE → remove
    "\u200c": "",  # ZERO WIDTH NON-JOINER → remove
    "\u200d": "",  # ZERO WIDTH JOINER → remove
    "\u202f": " ",  # NARROW NO-BREAK SPACE
    "\u205f": " ",  # MEDIUM MATHEMATICAL SPACE
    "\u2060": "",  # WORD JOINER → remove
    "\u2061": "",  # FUNCTION APPLICATION → remove
    "\u2062": "",  # INVISIBLE TIMES → remove
    "\u2063": "",  # INVISIBLE SEPARATOR → remove
    "\u2064": "",  # INVISIBLE PLUS → remove
    "\ufeff": "",  # BOM / ZERO WIDTH NO-BREAK SPACE → remove
}

# XML entity name → Unicode character (common JATS entities)
_XML_ENTITY_MAP: dict[str, str] = {
    "&alpha;": "α",
    "&beta;": "β",
    "&gamma;": "γ",
    "&delta;": "δ",
    "&epsilon;": "ε",
    "&zeta;": "ζ",
    "&eta;": "η",
    "&theta;": "θ",
    "&iota;": "ι",
    "&kappa;": "κ",
    "&lambda;": "λ",
    "&mu;": "μ",
    "&nu;": "ν",
    "&xi;": "ξ",
    "&pi;": "π",
    "&rho;": "ρ",
    "&sigma;": "σ",
    "&tau;": "τ",
    "&upsilon;": "υ",
    "&phi;": "φ",
    "&chi;": "χ",
    "&psi;": "ψ",
    "&omega;": "ω",
    "&Alpha;": "Α",
    "&Beta;": "Β",
    "&Gamma;": "Γ",
    "&Delta;": "Δ",
    "&Epsilon;": "Ε",
    "&Zeta;": "Ζ",
    "&Eta;": "Η",
    "&Theta;": "Θ",
    "&Iota;": "Ι",
    "&Kappa;": "Κ",
    "&Lambda;": "Λ",
    "&Mu;": "Μ",
    "&Nu;": "Ν",
    "&Xi;": "Ξ",
    "&Pi;": "Π",
    "&Rho;": "Ρ",
    "&Sigma;": "Σ",
    "&Tau;": "Τ",
    "&Upsilon;": "Υ",
    "&Phi;": "Φ",
    "&Chi;": "Χ",
    "&Psi;": "Ψ",
    "&Omega;": "Ω",
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "&quot;": '"',
    "&apos;": "'",
    "&ensp;": " ",
    "&emsp;": " ",
    "&nbsp;": " ",
    "&thinsp;": " ",
    "&mdash;": "-",
    "&ndash;": "-",
    "&hellip;": "...",
    "&laquo;": "«",
    "&raquo;": "»",
    "&lsquo;": "'",
    "&rsquo;": "'",
    "&ldquo;": '"',
    "&rdquo;": '"',
    "&times;": "×",
    "&div;": "÷",
    "&plusmn;": "±",
    "&micro;": "μ",
    "&para;": "¶",
    "&sect;": "§",
    "&deg;": "°",
    "&trade;": "™",
    "&copy;": "©",
    "&reg;": "®",
    "&cent;": "¢",
    "&pound;": "£",
    "&yen;": "¥",
    "&euro;": "€",
    "&currency;": "¤",
    "&larr;": "←",
    "&rarr;": "→",
    "&uarr;": "↑",
    "&darr;": "↓",
    "&ne;": "≠",
    "&le;": "≤",
    "&ge;": "≥",
    "&sim;": "∼",
    "&cong;": "≅",
    "&approx;": "≈",
    "&infin;": "∞",
    "&part;": "∂",
    "&nabla;": "∇",
    "&forall;": "∀",
    "&exist;": "∃",
    "&empty;": "∅",
    "&isin;": "∈",
    "&notin;": "∉",
    "&sub;": "⊂",
    "&sup;": "⊃",
    "&cup;": "∪",
    "&cap;": "∩",
}

# Inline display tags to strip (preserve text content only)
_INLINE_TAGS: frozenset[str] = frozenset(
    {
        "bold",
        "italic",
        "underline",
        "strike",
        "sc",
        "sub",
        "sup",
        "monospace",
        "roman",
        "sans-serif",
        "styled-content",
        "named-content",
        "overline",
    }
)

# Tags whose text content should be kept but the element removed
_FLATTEN_TAGS: frozenset[str] = frozenset(
    {
        "xref",
        "ext-link",
        "uri",
        "email",
    }
)

# Tags to remove entirely (including their text content) from body text
_REMOVE_TAGS: frozenset[str] = frozenset(
    {
        "fig",
        "fig-group",
        "table-wrap",
        "table-wrap-foot",
        "graphic",
        "media",
        "supplementary-material",
        "supplementary",
        "boxed-text",
        "disp-formula",
        "chem-struct-wrap",
    }
)

# Tags to extract separately (not in running text)
_STRUCTURAL_TAGS: frozenset[str] = frozenset(
    {
        "fig",
        "fig-group",
        "table-wrap",
        "graphic",
        "media",
        "supplementary-material",
        "supplementary",
    }
)


@dataclass
class NormalizationConfig:
    """Configuration for the JATS normalization pipeline.

    Parameters
    ----------
    strip_display_markup : bool
        Strip inline display tags (bold, italic, sup, sub, etc.),
        preserving text content. Default True.
    flatten_xrefs : bool
        Flatten xref/ext-link/uri elements to their text or ID.
        Default True.
    remove_structural : bool
        Remove block-level structural elements (fig, table-wrap,
        supplementary-material) from running text. Default True.
    section_types : bool
        Canonicalize section headings to PMC-style type labels.
        Default True.
    normalize_entities : bool
        Resolve XML named entities and Unicode characters.
        Default True.
    normalize_whitespace : bool
        Normalize Unicode whitespace, fix spacing artifacts.
        Default True.
    normalize_dashes : bool
        Normalize all dash/hyphen/minus variants to ASCII hyphen.
        Default True.
    normalize_identifiers : bool
        Normalize ORCID, DOI, PMCID formats. Default True.
    bio_c_output : bool
        Generate BioC JSON output alongside normalized tree.
        Default False.
    drop_mathml : bool
        Drop MathML elements (keep inline formula text only).
        Default True.
    """

    strip_display_markup: bool = True
    flatten_xrefs: bool = True
    remove_structural: bool = True
    section_types: bool = True
    normalize_entities: bool = True
    normalize_whitespace: bool = True
    normalize_dashes: bool = True
    normalize_identifiers: bool = True
    bio_c_output: bool = False
    drop_mathml: bool = True


class JATSNormalizer:
    """JATS XML normalizer implementing text-mining best practices.

    Applies a configurable pipeline of normalization layers to a JATS XML
    document, producing clean text suitable for NLP/ML pipelines while
    preserving structural information (sections, inline references, etc.).

    Parameters
    ----------
    strip_display_markup : bool
        Strip bold/italic/sup/sub etc. (text preserved). Default True.
    flatten_xrefs : bool
        Flatten xref elements to text/ID. Default True.
    remove_structural : bool
        Remove fig/table-wrap/supplementary from body text. Default True.
    section_types : bool
        Canonicalize section headings. Default True.
    normalize_entities : bool
        Resolve XML entities. Default True.
    normalize_whitespace : bool
        Normalize whitespace. Default True.
    normalize_dashes : bool
        Normalize dashes to ASCII. Default True.
    normalize_identifiers : bool
        Normalize ORCID/DOI/PMCID. Default True.
    bio_c_output : bool
        Generate BioC JSON output. Default False.
    drop_mathml : bool
        Drop MathML, keep formula text. Default True.

    Examples
    --------
    >>> normalizer = JATSNormalizer(section_types=True)
    >>> result = normalizer.normalize_xml(xml_string)
    >>> for section in result["sections"]:
    ...     print(f"{section['type']}: {section['title'][:50]}")
    """

    def __init__(self, **kwargs: bool) -> None:
        self.config = NormalizationConfig(**kwargs)

    def normalize_xml(self, xml_content: str | bytes) -> dict[str, Any]:
        """Normalize a JATS XML document.

        Applies the full normalization pipeline and returns a dict with:
        - ``normalized_root``: the cleaned ElementTree root
        - ``sections``: list of section dicts with canonical type labels
        - ``metadata``: normalized article metadata
        - ``body_text``: full normalized body text
        - ``bio_c``: BioC JSON (if enabled)

        Parameters
        ----------
        xml_content : str or bytes
            Raw JATS XML content.

        Returns
        -------
        dict
            Normalization results.
        """
        # Pre-resolve XML entities that ET.fromstring can't handle
        if isinstance(xml_content, bytes):
            xml_content = xml_content.decode("utf-8")
        xml_content = self._pre_resolve_entities(xml_content)

        root = ET.fromstring(xml_content)  # nosec B314

        # Deep copy to avoid mutating original
        root = copy.deepcopy(root)

        # Strip namespace prefixes for easier processing
        root = self._strip_namespaces(root)

        result: dict[str, Any] = {
            "original_root": root,
            "normalized_root": root,
            "sections": [],
            "metadata": {},
            "body_text": "",
        }

        # Layer 1: Entity normalization (on text nodes)
        if self.config.normalize_entities:
            self._normalize_entities_in_tree(root)

        # Layer 2: Display markup stripping
        if self.config.strip_display_markup or self.config.flatten_xrefs:
            self._strip_display_tags(root)

        # Layer 3: Remove structural elements from body
        if self.config.remove_structural:
            self._remove_structural_elements(root)

        # Layer 4: Drop MathML
        if self.config.drop_mathml:
            self._drop_mathml(root)

        # Layer 5: Section type canonicalization
        if self.config.section_types:
            result["sections"] = self._canonicalize_sections(root)

        # Layer 6: Whitespace normalization
        if self.config.normalize_whitespace:
            self._normalize_whitespace(root)

        # Layer 7: Dash normalization
        if self.config.normalize_dashes:
            self._normalize_dashes(root)

        # Layer 8: Identifier normalization
        if self.config.normalize_identifiers:
            result["metadata"] = self._normalize_metadata(root)
        else:
            result["metadata"] = self._extract_metadata(root)

        # Layer 9: Extract body text
        result["body_text"] = self._extract_body_text(root)

        # Layer 10: BioC output
        if self.config.bio_c_output:
            result["bio_c"] = self._to_bioc(result)

        return result

    def normalize_text(self, xml_content: str | bytes) -> str:
        """Return just the normalized body text as a string.

        Convenience method for text-mining pipelines that only need
        the plain text output.

        Parameters
        ----------
        xml_content : str or bytes
            Raw JATS XML content.

        Returns
        -------
        str
            Normalized body text.
        """
        result = self.normalize_xml(xml_content)
        body_text: str = result["body_text"]
        return body_text

    def normalize_sections(self, xml_content: str | bytes) -> list[dict[str, Any]]:
        """Return normalized sections with canonical type labels.

        Parameters
        ----------
        xml_content : str or bytes
            Raw JATS XML content.

        Returns
        -------
        list of dict
            Each dict has keys: ``type``, ``title``, ``level``, ``text``, ``passages``.
        """
        result = self.normalize_xml(xml_content)
        sections: list[dict[str, Any]] = result["sections"]
        return sections

    # ------------------------------------------------------------------
    # Entity pre-resolution (before XML parsing)
    # ------------------------------------------------------------------

    @staticmethod
    def _pre_resolve_entities(xml_text: str) -> str:
        """Pre-resolve XML entities that ET.fromstring can't handle.

        Resolves named entities like ``&alpha;`` to their Unicode characters
        before the XML parser sees them. Also handles numeric character
        references.

        Skips standard XML entities (&amp; &lt; &gt; &quot; &apos;) that
        the XML parser handles natively.
        """
        # Standard XML entities — must NOT be replaced (parser handles them)
        _SKIP_ENTITIES = {"&amp;", "&lt;", "&gt;", "&quot;", "&apos;"}

        # Named entities
        for entity, char in _XML_ENTITY_MAP.items():
            if entity in _SKIP_ENTITIES:
                continue
            entity_name = entity[1:-1]  # strip & and ;
            xml_text = xml_text.replace(f"&{entity_name};", char)

        # Numeric character references: &#xHHHH; and &#DDDD;
        def _replace_numeric(match: re.Match[str]) -> str:
            if match.group(1):
                # Hex: &#xHHHH;
                return chr(int(match.group(1), 16))
            # Decimal: &#DDDD;
            return chr(int(match.group(2)))

        xml_text = re.sub(r"&#x([0-9a-fA-F]+);|&#(\d+);", _replace_numeric, xml_text)

        return xml_text

    # ------------------------------------------------------------------
    # Layer 1: Namespace stripping
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_namespaces(root: ET.Element) -> ET.Element:
        """Remove namespace prefixes from element tags for uniform processing."""
        for elem in root.iter():
            # Remove namespace from tag
            tag = elem.tag
            if "}" in tag:
                elem.tag = tag.split("}", 1)[1]
        return root

    # ------------------------------------------------------------------
    # Layer 2: Entity normalization
    # ------------------------------------------------------------------

    def _normalize_entities_in_tree(self, root: ET.Element) -> None:
        """Walk tree and normalize text nodes."""
        for elem in root.iter():
            if elem.text:
                elem.text = self._normalize_text_entities(elem.text)
            if elem.tail:
                elem.tail = self._normalize_text_entities(elem.tail)

    def _normalize_text_entities(self, text: str) -> str:
        """Resolve XML entities and normalize Unicode in a text string."""
        # Decode HTML entities (handles &amp; &lt; &gt; etc.)
        text = html.unescape(text)

        # Replace known named entities
        for entity, char in _XML_ENTITY_MAP.items():
            entity_name = entity[1:-1]  # strip & and ;
            text = text.replace(f"&{entity_name};", char)

        # Unicode normalization (NFC form)
        text = unicodedata.normalize("NFC", text)

        return text

    # ------------------------------------------------------------------
    # Layer 3: Display markup stripping
    # ------------------------------------------------------------------

    def _strip_display_tags(self, root: ET.Element) -> None:
        """Strip inline display tags, preserving text content.

        For ``_INLINE_TAGS`` (bold, italic, etc.): remove the element
        wrapper but keep the text and tail.

        For ``_FLATTEN_TAGS`` (xref, ext-link, uri): replace with
        text content (or rid/href if text is empty).
        """
        body = self._find_body(root)
        if body is None:
            return

        self._walk_and_strip(body)

    def _walk_and_strip(self, elem: ET.Element) -> None:
        """Recursively strip display tags from element tree."""
        children_to_process = list(elem)
        for child in children_to_process:
            local_tag = child.tag

            if local_tag in _INLINE_TAGS:
                # Strip inline tag: merge text/tail into parent
                self._merge_element_text_into_parent(elem, child)
            elif local_tag in _FLATTEN_TAGS:
                # Flatten xref/ext-link: use text or rid/href
                self._flatten_element(elem, child)
            else:
                # Recurse into remaining elements
                self._walk_and_strip(child)

    def _merge_element_text_into_parent(self, parent: ET.Element, child: ET.Element) -> None:
        """Remove an inline element but preserve its text in the parent."""
        idx = list(parent).index(child)

        # Combine: parent's tail-before + child.text + child.tail
        before = parent[idx - 1].tail if idx > 0 else parent.text
        before = before or ""

        child_text = self._get_all_text(child)
        child_tail = child.tail or ""

        combined = before + child_text + child_tail

        # Update parent
        if idx > 0:
            parent[idx - 1].tail = combined
        else:
            parent.text = combined

        parent.remove(child)

    def _flatten_element(self, parent: ET.Element, child: ET.Element) -> None:
        """Flatten a xref/ext-link to text content (or ID fallback)."""
        idx = list(parent).index(child)

        # Get display text
        text = self._get_all_text(child)
        if not text:
            # Fallback to rid or href
            text = child.get("rid", "") or child.get("href", "")

        before = parent[idx - 1].tail if idx > 0 else parent.text
        before = before or ""
        child_tail = child.tail or ""

        combined = before + text + child_tail

        if idx > 0:
            parent[idx - 1].tail = combined
        else:
            parent.text = combined

        parent.remove(child)

    def _remove_structural_elements(self, root: ET.Element) -> None:
        """Remove structural elements (fig, table-wrap, etc.) from body."""
        body = self._find_body(root)
        if body is None:
            return

        self._remove_tags_recursive(body, _REMOVE_TAGS)

    def _remove_tags_recursive(self, elem: ET.Element, tags: frozenset[str]) -> None:
        """Recursively remove elements with specified tags."""
        children = list(elem)
        for child in children:
            if child.tag in tags:
                elem.remove(child)
            else:
                self._remove_tags_recursive(child, tags)

    # ------------------------------------------------------------------
    # Layer 4: MathML handling
    # ------------------------------------------------------------------

    def _drop_mathml(self, root: ET.Element) -> None:
        """Remove MathML elements, keeping inline formula text."""
        for math_tag in ("math", "mml:math"):
            for elem in root.iter(math_tag):
                # Get text content before removing
                text = self._get_all_text(elem)
                parent = self._find_parent(root, elem)
                if parent is not None:
                    # Try to preserve text in parent
                    if elem.text:
                        parent.text = (parent.text or "") + text + (elem.tail or "")
                    parent.remove(elem)

    # ------------------------------------------------------------------
    # Layer 5: Section type canonicalization
    # ------------------------------------------------------------------

    def _canonicalize_sections(self, root: ET.Element) -> list[dict[str, Any]]:
        """Extract sections with canonical type labels.

        Returns
        -------
        list of dict
            Each dict: ``type``, ``title``, ``level``, ``text``, ``passages``.
        """
        sections: list[dict[str, Any]] = []
        body = self._find_body(root)
        if body is None:
            return sections

        self._extract_sections_recursive(body, sections, depth=0)
        # Reverse to restore document order (children were appended before parents)
        sections.reverse()
        return sections

    def _extract_sections_recursive(
        self,
        parent: ET.Element,
        sections: list[dict[str, Any]],
        depth: int,
    ) -> None:
        """Recursively extract sections with canonical types.

        When called with a parent element, iterates its children.
        For each ``<sec>`` child, extracts text and type, appends it
        to sections, then recurses into it for subsections.
        """
        # If parent itself is a sec, process it first
        if parent.tag == "sec":
            self._process_sec(parent, sections, depth)
        else:
            # parent is body or another container — find sec children
            for child in parent:
                if child.tag == "sec":
                    self._process_sec(child, sections, depth)

    def _process_sec(
        self,
        sec_elem: ET.Element,
        sections: list[dict[str, Any]],
        depth: int,
    ) -> None:
        """Process a single ``<sec>`` element and its subsections."""
        title_elem = sec_elem.find("title")
        title = self._get_all_text(title_elem) if title_elem is not None else ""

        # Canonicalize section type
        sec_type = self._classify_section_type(title)

        # Get section text (direct paragraph content, not subsections)
        text_parts: list[str] = []
        passages: list[dict[str, str]] = []

        for sub_elem in sec_elem:
            if sub_elem.tag == "title":
                continue
            if sub_elem.tag == "sec":
                # Recurse into subsection
                self._process_sec(sub_elem, sections, depth + 1)
            elif sub_elem.tag == "p":
                p_text = self._get_all_text(sub_elem)
                if p_text.strip():
                    text_parts.append(p_text.strip())
                    passages.append({"type": "paragraph", "text": p_text.strip()})
            elif sub_elem.tag == "list":
                list_text = self._get_all_text(sub_elem)
                if list_text.strip():
                    text_parts.append(list_text.strip())
                    passages.append({"type": "list", "text": list_text.strip()})

        sections.append(
            {
                "type": sec_type,
                "title": title,
                "level": depth,
                "text": "\n".join(text_parts),
                "passages": passages,
            }
        )

    @staticmethod
    def _classify_section_type(title: str) -> str:
        """Classify a section heading into a canonical type.

        Parameters
        ----------
        title : str
            Section heading text.

        Returns
        -------
        str
            Canonical section type (e.g., ``"methods"``, ``"results"``).
        """
        normalized = title.strip().lower()
        # Remove leading numbers/dots: "1. Methods" → "Methods"
        normalized = re.sub(r"^\d+[\.\)]\s*", "", normalized)
        # Remove numbering like "2.3.1" → "sub-subsection"
        normalized = re.sub(r"^[\d\.]+\s*", "", normalized)
        # Remove parenthesized numbers: "(3) Discussion" → "Discussion"
        normalized = re.sub(r"^\(\d+\)\s*", "", normalized)

        for pattern, sec_type in SECTION_TYPE_PATTERNS:
            if pattern.match(normalized):
                return sec_type

        return "other"

    # ------------------------------------------------------------------
    # Layer 6: Whitespace normalization
    # ------------------------------------------------------------------

    def _normalize_whitespace(self, root: ET.Element) -> None:
        """Normalize whitespace in all text nodes."""
        for elem in root.iter():
            if elem.text:
                elem.text = self._normalize_text_whitespace(elem.text)
            if elem.tail:
                elem.tail = self._normalize_text_whitespace(elem.tail)

    def _normalize_text_whitespace(self, text: str) -> str:
        """Normalize Unicode whitespace and fix spacing artifacts."""
        # Replace Unicode space characters
        for char, replacement in _SPACE_CHARS.items():
            text = text.replace(char, replacement)

        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    # ------------------------------------------------------------------
    # Layer 7: Dash normalization
    # ------------------------------------------------------------------

    def _normalize_dashes(self, root: ET.Element) -> None:
        """Normalize all dash/hyphen/minus variants to ASCII hyphen."""
        for elem in root.iter():
            if elem.text:
                elem.text = self._normalize_text_dashes(elem.text)
            if elem.tail:
                elem.tail = self._normalize_text_dashes(elem.tail)

    def _normalize_text_dashes(self, text: str) -> str:
        """Replace Unicode dash characters with ASCII hyphen."""
        for char, replacement in _DASH_CHARS.items():
            text = text.replace(char, replacement)
        return text

    # ------------------------------------------------------------------
    # Layer 8: Identifier normalization
    # ------------------------------------------------------------------

    def _normalize_metadata(self, root: ET.Element) -> dict[str, Any]:
        """Extract and normalize article metadata."""
        meta = self._extract_metadata(root)

        # Normalize ORCIDs
        if "authors" in meta:
            for author in meta["authors"]:
                if "orcid" in author:
                    author["orcid"] = self._normalize_orcid(author["orcid"])

        # Normalize DOIs
        for field_name in ("doi", "pmcid", "pmid"):
            if field_name in meta and meta[field_name]:
                meta[field_name] = self._normalize_identifier_value(meta[field_name], field_name)

        return meta

    def _extract_metadata(self, root: ET.Element) -> dict[str, Any]:
        """Extract metadata without normalization."""
        meta: dict[str, Any] = {}

        # Title
        title_elem = root.find(".//article-title")
        if title_elem is not None:
            meta["title"] = self._get_all_text(title_elem)

        # Identifiers
        self._extract_identifiers(root, meta)

        # Article type
        self._extract_article_type(root, meta)

        # Authors
        self._extract_authors(root, meta)

        # Journal
        journal_elem = root.find(".//journal-title")
        if journal_elem is not None:
            meta["journal"] = (journal_elem.text or "").strip()

        # License
        self._extract_license(root, meta)

        return meta

    def _extract_identifiers(self, root: ET.Element, meta: dict[str, Any]) -> None:
        """Extract article identifiers (DOI, PMCID, PMID) into meta."""
        for id_elem in root.iter("article-id"):
            id_type = id_elem.get("pub-id-type", "")
            id_val = (id_elem.text or "").strip()
            if id_type == "doi":
                meta["doi"] = id_val
            elif id_type == "pmcid":
                meta["pmcid"] = id_val
            elif id_type == "pmid":
                meta["pmid"] = id_val

    def _extract_article_type(self, root: ET.Element, meta: dict[str, Any]) -> None:
        """Extract article type into meta."""
        article_elem = root.find(".//article")
        if article_elem is None and root.tag == "article":
            article_elem = root
        if article_elem is not None:
            meta["article_type"] = (
                (article_elem.get("article-type", "") or "").lower().replace("_", "-")
            )

    def _extract_authors(self, root: ET.Element, meta: dict[str, Any]) -> None:
        """Extract author names and ORCIDs into meta."""
        authors: list[dict[str, str]] = []
        for contrib in root.iter("contrib"):
            if contrib.get("contrib-type") != "author":
                continue
            name = contrib.find("name")
            if name is None:
                continue
            surname = (name.findtext("surname") or "").strip()
            given = (name.findtext("given-names") or "").strip()
            author_name = f"{given} {surname}".strip()
            if not author_name:
                continue
            author_entry: dict[str, str] = {"name": author_name}
            for cid in contrib.iter("contrib-id"):
                if cid.get("contrib-id-type") == "orcid":
                    author_entry["orcid"] = (cid.text or "").strip()
            authors.append(author_entry)
        if authors:
            meta["authors"] = authors

    def _extract_license(self, root: ET.Element, meta: dict[str, Any]) -> None:
        """Extract license information into meta."""
        license_elem = root.find(".//license")
        if license_elem is not None:
            lic_p = license_elem.find("license-p")
            if lic_p is not None:
                meta["license"] = self._get_all_text(lic_p)
            else:
                meta["license"] = license_elem.get("license-type", "") or ""

    @staticmethod
    def _normalize_orcid(orcid: str) -> str:
        """Normalize ORCID to standard format (0000-0000-0000-0000)."""
        if not orcid:
            return ""
        # Strip URL prefix if present
        orcid = re.sub(r"^https?://orcid\.org/", "", orcid)
        # Remove hyphens and re-add
        digits = re.sub(r"[^0-9X]", "", orcid.upper())
        if len(digits) == 16:
            return f"{digits[:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:]}"
        return orcid

    @staticmethod
    def _normalize_identifier_value(value: str, id_type: str) -> str:
        """Normalize identifier values."""
        value = value.strip()
        if id_type == "doi":
            # Lowercase DOI, strip prefix
            value = re.sub(r"^doi:\s*", "", value, flags=re.I)
            value = re.sub(r"^https?://doi\.org/", "", value)
            value = value.lower()
        elif id_type == "pmcid":
            # Ensure PMC prefix
            value = value.upper()
            if not value.startswith("PMC"):
                value = f"PMC{value}"
        elif id_type == "pmid":
            # Numeric only
            value = re.sub(r"[^\d]", "", value)
        return value

    # ------------------------------------------------------------------
    # Layer 9: Body text extraction
    # ------------------------------------------------------------------

    def _extract_body_text(self, root: ET.Element) -> str:
        """Extract normalized body text as a single string."""
        body = self._find_body(root)
        if body is None:
            return ""

        parts: list[str] = []
        self._collect_text(body, parts)
        return "\n".join(parts)

    def _collect_text(self, elem: ET.Element, parts: list[str]) -> None:
        """Recursively collect text from an element."""
        if elem.text:
            text = elem.text.strip()
            if text:
                parts.append(text)

        for child in elem:
            self._collect_text(child, parts)
            if child.tail:
                text = child.tail.strip()
                if text:
                    parts.append(text)

    # ------------------------------------------------------------------
    # Layer 10: BioC JSON output
    # ------------------------------------------------------------------

    def _to_bioc(self, result: dict[str, Any]) -> dict[str, Any]:
        """Convert normalized result to BioC JSON format.

        BioC is a standardized format for representing biomedical
        annotated documents: https://bioc.sourceforge.net/

        Returns
        -------
        dict
            BioC JSON document structure.
        """
        doc: dict[str, Any] = {
            "source": "pyeuropepmc",
            "date": "",
            "key": "",
            "infons": {},
            "documents": [],
        }

        # Document-level infons
        meta = result.get("metadata", {})
        if meta.get("doi"):
            doc["infons"]["doi"] = meta["doi"]
        if meta.get("pmcid"):
            doc["infons"]["pmcid"] = meta["pmcid"]
        if meta.get("article_type"):
            doc["infons"]["article_type"] = meta["article_type"]

        # Create document
        document: dict[str, Any] = {
            "id": meta.get("pmcid", meta.get("doi", "unknown")),
            "infons": doc["infons"],
            "passages": [],
        }

        # Add sections as passages
        offset = 0
        for section in result.get("sections", []):
            text = section.get("text", "")
            if text:
                passage: dict[str, Any] = {
                    "offset": offset,
                    "infons": {
                        "section_type": section.get("type", "other"),
                        "section_title": section.get("title", ""),
                    },
                    "text": text,
                    "annotations": [],
                }
                document["passages"].append(passage)
                offset += len(text) + 1  # +1 for newline

        doc["documents"].append(document)
        return doc

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def _find_body(root: ET.Element) -> ET.Element | None:
        """Find the <body> element in the article tree."""
        # Try direct child of article
        body = root.find(".//body")
        if body is not None:
            return body
        # Try article/body
        article = root.find(".//article")
        if article is not None:
            body = article.find("body")
            if body is not None:
                return body
        return None

    @staticmethod
    def _get_all_text(elem: ET.Element | None) -> str:
        """Get all text content from element and descendants."""
        if elem is None:
            return ""
        parts: list[str] = []
        if elem.text:
            parts.append(elem.text)
        for child in elem:
            parts.append(JATSNormalizer._get_all_text(child))
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    @staticmethod
    def _find_parent(root: ET.Element, target: ET.Element) -> ET.Element | None:
        """Find the parent of a target element in the tree."""
        for parent in root.iter():
            for child in parent:
                if child is target:
                    return parent
        return None


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def normalize_jats_xml(
    xml_content: str | bytes,
    *,
    strip_display_markup: bool = True,
    flatten_xrefs: bool = True,
    section_types: bool = True,
    normalize_entities: bool = True,
    normalize_whitespace: bool = True,
    normalize_dashes: bool = True,
    normalize_identifiers: bool = True,
    bio_c_output: bool = False,
) -> dict[str, Any]:
    """Normalize a JATS XML document with default settings.

    Convenience function wrapping :class:`JATSNormalizer`.

    Parameters
    ----------
    xml_content : str or bytes
        Raw JATS XML content.
    strip_display_markup : bool
        Strip bold/italic/sup/sub tags. Default True.
    flatten_xrefs : bool
        Flatten xref elements. Default True.
    section_types : bool
        Canonicalize section headings. Default True.
    normalize_entities : bool
        Resolve XML entities. Default True.
    normalize_whitespace : bool
        Normalize whitespace. Default True.
    normalize_dashes : bool
        Normalize dashes. Default True.
    normalize_identifiers : bool
        Normalize identifiers. Default True.
    bio_c_output : bool
        Generate BioC JSON. Default False.

    Returns
    -------
    dict
        Normalized document with ``sections``, ``metadata``, ``body_text``.

    Examples
    --------
    >>> result = normalize_jats_xml(xml_string)
    >>> print(result["body_text"][:200])
    """
    normalizer = JATSNormalizer(
        strip_display_markup=strip_display_markup,
        flatten_xrefs=flatten_xrefs,
        section_types=section_types,
        normalize_entities=normalize_entities,
        normalize_whitespace=normalize_whitespace,
        normalize_dashes=normalize_dashes,
        normalize_identifiers=normalize_identifiers,
        bio_c_output=bio_c_output,
    )
    return normalizer.normalize_xml(xml_content)


def normalize_jats_text(xml_content: str | bytes) -> str:
    """Return just the normalized body text from a JATS XML document.

    Parameters
    ----------
    xml_content : str or bytes
        Raw JATS XML content.

    Returns
    -------
    str
        Clean normalized body text.
    """
    normalizer = JATSNormalizer()
    return normalizer.normalize_text(xml_content)


def classify_section(heading: str) -> str:
    """Classify a section heading to a canonical type.

    Parameters
    ----------
    heading : str
        Section heading text.

    Returns
    -------
    str
        Canonical type (``"methods"``, ``"results"``, ``"intro"``, etc.).

    Examples
    --------
    >>> classify_section("Materials and Methods")
    'methods'
    >>> classify_section("3. Results and Discussion")
    'results'
    """
    return JATSNormalizer._classify_section_type(heading)
