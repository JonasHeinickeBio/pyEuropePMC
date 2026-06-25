"""
XML-level parser quality metrics for benchmark evaluation.

Each metric function takes a configured :class:`FullTextXMLParser` plus the raw XML
string and returns structured metric results with scores (0.0–1.0).

Metrics implemented
-------------------
1. **Element coverage** — Does the parser know about all element types in the article?
2. **Text extraction fidelity** — Does the parser capture all body text?
3. **Section boundary accuracy** — Are sections correctly identified and nested?
4. **Inline element recall** — Are inline elements (xref, bold, italic, etc.) captured?
5. **Metadata extraction accuracy** — Are title, authors, DOI, PMID, PMCID correct?

Usage
-----
>>> from pyeuropepmc.benchmark.metrics import compute_all_metrics
>>> from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
>>> parser = FullTextXMLParser(xml_string)
>>> metrics = compute_all_metrics(parser, xml_string)
>>> metrics["element_coverage"]["score"]
0.85
"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)

# Element tags that are purely structural/metadata and carry no article content.
# This set covers the full JATS Tag Library — used by the element coverage metric
# to categorize tags as "structural" (known) vs "content" (unknown).
_STRUCTURAL_TAGS: frozenset[str] = frozenset(
    {
        # Document structure
        "article",
        "front",
        "body",
        "back",
        "floats-group",
        "sub-article",
        "response",
        "article-meta",
        "journal-meta",
        "book-meta",
        # Section structure
        "sec",
        "title",
        "title-group",
        "article-title",
        "subtitle",
        "alt-title",
        "trans-title",
        "trans-subtitle",
        "part-title",
        "data-title",
        "p",
        "list",
        "list-item",
        "prefix-word",
        "def-list",
        "def-item",
        "term",
        "def",
        "term-head",
        "def-head",
        # Tables
        "table-wrap",
        "table-wrap-foot",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        "colgroup",
        "col",
        # Figures
        "fig",
        "fig-group",
        "graphic",
        "caption",
        "label",
        "alt-text",
        "media",
        "audio",
        "video",
        "svg",
        # References
        "ref-list",
        "ref",
        "mixed-citation",
        "element-citation",
        "nlm-citation",
        "citation",
        "citation-alternatives",
        "person-group",
        "name",
        "etal",
        "collab",
        "string-name",
        "surname",
        "given-names",
        "prefix",
        "suffix",
        "degrees",
        "role",
        "anonymous",
        "on-behalf-of",
        # Metadata wrappers
        "pub-date",
        "volume",
        "issue",
        "issn",
        "isbn",
        "issn-l",
        "article-id",
        "publisher",
        "publisher-name",
        "publisher-loc",
        "contrib-group",
        "contrib",
        "contrib-id",
        "aff",
        "aff-alternatives",
        "institution",
        "institution-id",
        "institution-wrap",
        "author-notes",
        "corresp",
        "fn",
        "fn-group",
        "kwd-group",
        "kwd",
        "compound-kwd",
        "compound-kwd-part",
        "subj-group",
        "subject",
        "article-categories",
        "support-group",
        "support-source",
        "support-description",
        "award-group",
        "award-id",
        "funding-group",
        "funding-source",
        "funding-statement",
        "principal-award-recipient",
        "permissions",
        "copyright-statement",
        "copyright-year",
        "license",
        "license-p",
        "license_ref",
        "restricted-by",
        "history",
        "pub-history",
        "date",
        "day",
        "month",
        "year",
        "custom-meta",
        "custom-meta-group",
        "meta-name",
        "meta-value",
        "self-uri",
        "related-article",
        "related-object",
        "app",
        "app-group",
        "glossary",
        "ack",
        "supplementary-material",
        "inline-supplementary-material",
        "bio",
        "notes",
        "note",
        "chem-struct-wrap",
        "chem-struct",
        "inline-formula",
        "disp-formula",
        "disp-formula-group",
        "alternatives",
        "tex-math",
        "array",
        "disp-quote",
        "verse-group",
        "verse-line",
        "attrib",
        "speech",
        "speaker",
        "boxed-text",
        "code",
        "preformat",
        "styled-content",
        "monospace",
        "sc",
        "sub",
        "sup",
        "bold",
        "italic",
        "underline",
        "strike",
        "named-content",
        "overline",
        "roman",
        "sans-serif",
        "small-caps",
        "xref",
        "inline-graphic",
        "private-char",
        "hr",
        "break",
        "addr-line",
        "country",
        "city",
        "state",
        "postal-code",
        "phone",
        "fax",
        "email",
        "ext-link",
        "uri",
        "address",
        "counts",
        "table-count",
        "figure-count",
        "fig-count",
        "equation-count",
        "ref-count",
        "page-count",
        "word-count",
        "elocation-id",
        "issue-id",
        "issue-title",
        "issue-sponsor",
        "fpage",
        "lpage",
        "page-range",
        "supplement",
        "pub-id",
        "source",
        "conf-name",
        "conf-date",
        "conf-loc",
        "conf-sponsor",
        "event",
        "event-desc",
        "edition",
        "season",
        "series",
        "string-date",
        "version",
        "article-version",
        "page",
        "journal-id",
        "journal-title",
        "journal-title-group",
        "abbrev-journal-title",
        "alt-journal-title",
        "statement",
        "color",
        "comment",
        "compound-subject",
        "compound-subject-part",
        "processing-meta",
        "size",
        "product",
        "price",
        "annotation",
        "std",
        "gov",
        "patent",
        "question",
        "answer",
        "explanation",
        "ruby",
        "rb",
        "rt",
        "rp",
        "object-id",
        "x",
        # MathML (namespace-prefixed and unprefixed)
        "mml:math",
        "mml:mi",
        "mml:mo",
        "mml:mn",
        "mml:msup",
        "mml:msub",
        "mml:msubsup",
        "mml:mrow",
        "mml:mfrac",
        "mml:msqrt",
        "mml:mtext",
        "mml:mfenced",
        "mml:mover",
        "mml:munder",
        "mml:munderover",
        "mml:mspace",
        "mml:mstyle",
        "mml:mtable",
        "mml:mtr",
        "mml:mtd",
        "mml:semantics",
        "mml:annotation",
        "math",
        "mi",
        "mo",
        "mn",
        "msup",
        "msub",
        "msubsup",
        "mrow",
        "mfrac",
        "msqrt",
        "mtext",
        "mfenced",
        "mover",
        "munder",
        "munderover",
        "mspace",
        "mstyle",
        "mtable",
        "mtr",
        "mtd",
    }
)

# Inline content tags (the ones we expect the parser to track)
_INLINE_CONTENT_TAGS: frozenset[str] = frozenset(
    {
        "xref",
        "bold",
        "italic",
        "underline",
        "sup",
        "sub",
        "inline-formula",
        "named-content",
        "styled-content",
        "chem-struct",
        "sc",
        "monospace",
        "strike",
        "overline",
        "roman",
        "sans-serif",
        "small-caps",
    }
)

# Map from InlineElementType values (what the parser outputs) to XML tag names
# (what _INLINE_CONTENT_TAGS and _count_inline_elements_in_xml use)
_INLINE_TYPE_TO_XML_TAG: dict[str, str] = {
    "superscript": "sup",
    "subscript": "sub",
    "inline_formula": "inline-formula",
    "chemical_structure": "chem-struct",
    "named_content": "named-content",
    "strikethrough": "strike",
    "small_caps": "sc",
    "styled_content": "styled-content",
    "sans_serif": "sans-serif",
    "unkown_inline": "unknown-inline",
    # Direct matches handled as pass-through below
}


# ============================================================================
# Helper utilities
# ============================================================================


def _local_tag(tag: str) -> str:
    """Strip namespace from an ElementTree tag name."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _find_first_with_local_tag(parent: ET.Element, local_tag: str) -> ET.Element | None:
    """Find the first descendant element with the given local (namespace-stripped) tag."""
    stack = [parent]
    while stack:
        elem = stack.pop()
        if _local_tag(elem.tag) == local_tag:
            return elem
        # Extend in reverse to maintain document order
        stack.extend(reversed(list(elem)))
    return None


def _findall_with_local_tag(parent: ET.Element, local_tag: str) -> list[ET.Element]:
    """Find all descendant elements with the given local (namespace-stripped) tag."""
    results: list[ET.Element] = []
    stack = [parent]
    while stack:
        elem = stack.pop()
        if _local_tag(elem.tag) == local_tag:
            results.append(elem)
        stack.extend(elem)
    return results


def _extract_all_tags(root: ET.Element) -> set[str]:
    """Extract all unique XML tag names from an element tree (local names only)."""
    tags: set[str] = set()
    stack = [root]
    while stack:
        elem = stack.pop()
        tag = elem.tag
        # Strip namespace
        if tag.startswith("{"):
            tag = tag.split("}", 1)[1]
        tags.add(tag)
        stack.extend(elem)
    return tags


def _get_all_body_text(xml_content: str) -> str:
    """Extract all text content from the <body> element (naive but complete)."""
    root = ET.fromstring(xml_content)
    body = _find_first_with_local_tag(root, "body")
    if body is None:
        return ""
    return XMLHelper.get_text_content(body)


def _get_section_titles_from_xml(root: ET.Element) -> list[dict[str, Any]]:
    """Extract section titles with nesting paths from raw XML.

    Returns a list of dicts with ``title`` (flat), ``section_path`` (hierarchical,
    e.g. ``"Materials and Methods/Statistical Analysis"``), and ``depth``.
    """
    sections: list[dict[str, Any]] = []

    def walk(parent: ET.Element, depth: int = 0, parent_path: str = "") -> None:
        has_sec = False
        for child in parent:
            tag = _local_tag(child.tag)
            if tag == "sec":
                has_sec = True
                # Find title among children
                title = ""
                for sub in child:
                    if _local_tag(sub.tag) == "title":
                        title = XMLHelper.get_text_content(sub).strip()
                        break
                # Build hierarchical section_path
                section_path = f"{parent_path}/{title}" if parent_path and title else title
                sections.append(
                    {
                        "title": title,
                        "section_path": section_path,
                        "depth": depth,
                    }
                )
                # Recurse into this section for nested sections
                walk(child, depth + 1, section_path)
            elif tag in ("body",):
                walk(child, depth, parent_path)

        # Handle bare <p> elements directly under <body> (no <sec> wrapper).
        # Some publishers like PLOS use this structure.
        # IMPORTANT: Only apply to <body> parent, not to <sec> elements that
        # contain <p> text but no nested <sec> — those already get section_path
        # from their parent <sec> title, and duplicating them inflates expected_count.
        if not has_sec and _local_tag(parent.tag) == "body":
            bare_ps = [c for c in parent if _local_tag(c.tag) == "p"]
            if bare_ps:
                section_path = parent_path or "body"
                sections.append(
                    {
                        "title": "",
                        "section_path": section_path,
                        "depth": depth,
                    }
                )

    walk(root)
    return sections


def _get_expected_metadata(root: ET.Element) -> dict[str, Any]:
    """Extract expected metadata directly from XML (ground truth).

    Uses namespace-stripped tag matching to handle JATS XML with or without
    namespace prefixes.
    """
    expected: dict[str, Any] = {}

    # Title
    title_el = _find_first_with_local_tag(root, "article-title")
    if title_el is not None:
        expected["title"] = XMLHelper.get_text_content(title_el).strip()

    # Article IDs — search by pub-id-type attribute
    for article_id in _findall_with_local_tag(root, "article-id"):
        id_type = article_id.get("pub-id-type", "")
        text = (article_id.text or "").strip()
        if text:
            if id_type == "doi":
                expected["doi"] = text
            elif id_type == "pmid":
                expected["pmid"] = text
            elif id_type == "pmcid":
                expected["pmcid"] = text

    # Authors
    authors: list[str] = []
    for contrib in _findall_with_local_tag(root, "contrib"):
        if contrib.get("contrib-type") == "author":
            surname_el = _find_first_with_local_tag(contrib, "surname")
            given_el = _find_first_with_local_tag(contrib, "given-names")
            parts = []
            if given_el is not None and given_el.text:
                parts.append(given_el.text.strip())
            if surname_el is not None and surname_el.text:
                parts.append(surname_el.text.strip())
            if parts:
                authors.append(" ".join(parts))
    expected["authors"] = authors

    return expected


def _has_content_text(elem: ET.Element) -> bool:
    """Check if an element (or any descendant) has non-whitespace text content."""
    if elem.text and elem.text.strip():
        return True
    return any(_has_content_text(child) for child in elem)


def _count_inline_elements_in_xml(
    root: ET.Element,
    *,
    body_only: bool = True,
) -> dict[str, int]:
    """Count inline content elements in raw XML.

    Only counts inline elements that have meaningful text content
    (non-whitespace in the element or its descendants). This excludes
    whitespace-only layout elements (e.g., ``<bold>\\u00a0</bold>`` used
    for table cell alignment) that the parser correctly discards.

    Parameters
    ----------
    root:
        Root XML element.
    body_only:
        If True (default), only count inline elements within ``<body>``.
        This matches the parser's extraction scope and avoids penalizing
        the parser for inline elements in ``<front>`` (metadata, abstract
        formatting) or ``<back>`` (reference list formatting).
    """
    scope = root.find(".//body") if body_only else root
    if scope is None:
        # No <body> element — fall back to full root
        scope = root
    counts: dict[str, int] = {}
    for tag in _INLINE_CONTENT_TAGS:
        elements = _findall_with_local_tag(scope, tag)
        # Only count elements that have non-whitespace text content
        count = sum(1 for e in elements if _has_content_text(e))
        if count > 0:
            counts[tag] = count
    return counts


# ============================================================================
# Metric 1: Element coverage
# ============================================================================


def compute_element_coverage(
    parser: FullTextXMLParser,
    xml_content: str,
    config_tags: set[str] | None = None,
) -> dict[str, Any]:
    """
    Measure what fraction of XML element types the parser is configured to handle.

    Parameters
    ----------
    parser : FullTextXMLParser
        Initialized parser (will be used for schema detection).
    xml_content : str
        Raw XML string (used for full tag enumeration).
    config_tags : set of str, optional
        Override the set of tags the parser claims to handle.
        If omitted, derived from ``ElementPatterns`` configuration.

    Returns
    -------
    dict with keys: ``score``, ``total_elements``, ``covered_elements``,
    ``missing_elements``, ``coverage_pct``, ``element_lists``.
    """
    root = ET.fromstring(xml_content)
    found_tags = _extract_all_tags(root)

    # Build the set of tags the parser is configured to handle
    handled = config_tags or _get_configured_tags(parser)

    # Separate structural vs content tags
    content_tags = found_tags - _STRUCTURAL_TAGS

    covered = found_tags & handled
    missing = found_tags - handled
    missing_content = content_tags - handled

    total = len(found_tags)
    covered_count = len(covered)
    coverage_pct = (covered_count / total * 100) if total > 0 else 0.0

    # Log unknown tags at debug level for diagnostics
    if missing:
        logger.debug(
            "Element coverage: %d/%d = %.1f%% | %d tags not handled: %s",
            covered_count,
            total,
            coverage_pct,
            len(missing),
            ", ".join(sorted(missing)),
        )

    return {
        "score": round(covered_count / max(total, 1), 4),
        "total_elements": total,
        "covered_elements": covered_count,
        "missing_elements": len(missing),
        "missing_content_elements": len(missing_content),
        "coverage_pct": round(coverage_pct, 1),
        "element_lists": {
            "found": sorted(found_tags),
            "covered": sorted(covered),
            "missing": sorted(missing),
            "missing_content": sorted(missing_content),
        },
    }


def _get_configured_tags(parser: FullTextXMLParser) -> set[str]:
    """Extract all tag names that the parser is configured to handle."""
    tags: set[str] = set()
    config = parser.config

    # Collect patterns from all config categories
    categories = [
        ("citation_types", "types"),
        ("inline_element_patterns", "patterns"),
        ("xref_patterns",),
        ("media_patterns",),
        ("object_id_patterns", "patterns"),
        ("math_patterns",),
        ("formatting_patterns",),
        ("extended_metadata_patterns",),
        ("content_structure_patterns",),
        ("award_patterns",),
        ("appendix_patterns",),
    ]

    for cat in categories:
        cfg_obj = getattr(config, cat[0], {})
        if isinstance(cfg_obj, dict):
            if len(cat) > 1:
                # Look for specific key
                values = cfg_obj.get(cat[1], [])
                if isinstance(values, list):
                    for v in values:
                        # Extract tag name from XPath
                        tag = _xpath_to_tag(v)
                        if tag:
                            tags.add(tag)
            else:
                # Collect all values from all sub-keys
                for _key, values in cfg_obj.items():
                    if isinstance(values, list):
                        for v in values:
                            tag = _xpath_to_tag(v)
                            if tag:
                                tags.add(tag)

    # ====================================================================
    # TRULY HANDLED TAGS: tags that have actual parser handler code.
    # Tags are included ONLY if the parser does something meaningful:
    #   - Has a dedicated handler method in ContentBlockExtractor
    #   - Is specifically extracted by metadata_parser (not just referenced)
    #   - Is extracted by reference_parser
    #   - Is detected/classified by content section extraction
    # ====================================================================
    from pyeuropepmc.processing.extensions.content_blocks import ContentBlockExtractor

    tags.update(ContentBlockExtractor.JATS_BLOCK_TAGS.keys())
    tags.update(ContentBlockExtractor.INLINE_TAG_MAP.keys())

    # Section/skeleton structure (walked by _collect_sections,
    # _extract_structured_section)
    tags.update({"body", "front", "back", "sec", "title", "abstract", "article"})

    # Metadata extraction: tags directly extracted by metadata_parser.py
    tags.update(
        {
            "article-meta",
            "article-id",
            "journal-meta",
            "journal-id",
            "journal-title",
            "issn",
            "publisher",
            "publisher-name",
            "publisher-loc",
            "pub-date",
            "year",
            "month",
            "day",
            "volume",
            "issue",
            "fpage",
            "lpage",
            "contrib-group",
            "contrib",
            "name",
            "surname",
            "given-names",
            "aff",
            "kwd",
            "funding-source",
            "award-group",
            "award-id",
            "principal-award-recipient",
            "conf-name",
            "conf-date",
            "conf-loc",
            "license",
            "license-p",
            "ext-link",
            "subj-group",
            "subject",
            "permissions",
        }
    )

    # Reference parser: tags extracted by reference_parser.py
    tags.update(
        {
            "ref",
            "ref-list",
            "element-citation",
            "mixed-citation",
            "person-group",
            "name",
            "surname",
            "given-names",
            "source",
            "year",
            "volume",
            "issue",
            "fpage",
            "lpage",
        }
    )

    # Additional structure: front/back-matter handlers in content_blocks.py
    tags.update({"abstract", "ack", "app", "glossary", "ref-list", "fn", "fn-group"})

    # Figure/table handler children (processed by _handle_figure, _handle_table)
    tags.update(
        {
            "caption",
            "graphic",
            "label",
            "col",
            "colgroup",
            "table-wrap-foot",
        }
    )

    # Remaining content/structure tags handled by other parser code paths
    # (metadata_parser, table_parser, affiliation_parser, etc.)
    tags.update(
        {
            # Article metadata
            "article-title",
            "title-group",
            "date",
            "history",
            "pub-history",
            "page-range",
            "self-uri",
            "copyright-statement",
            "copyright-year",
            "article-categories",
            "contrib-id",
            # Contact and links
            "addr-line",
            "city",
            "country",
            "state",
            "postal-code",
            "email",
            "ext-link",
            "uri",
            "fax",
            "phone",
            "address",
            "institution",
            "institution-id",
            "institution-wrap",
            "corresp",
            "etal",
            "role",
            "suffix",
            "prefix",
            "degrees",
            "on-behalf-of",
            "anonymous",
            # Table cell structure
            "tbody",
            "thead",
            "tfoot",
            "tr",
            "td",
            "th",
            # References and publication IDs
            "pub-id",
            "citation-alternatives",
            "nlm-citation",
            "citation",
            "size",
            "notes",
            # Funding, keywords, document metadata
            "funding-group",
            "kwd-group",
            "counts",
            "page-count",
            # Custom metadata
            "meta-name",
            "meta-value",
            "custom-meta-group",
            "license_ref",
            # Journal metadata
            "abbrev-journal-title",
            "alt-journal-title",
            "journal-title-group",
        }
    )

    return tags


def _xpath_to_tag(xpath: str) -> str | None:
    """Extract the tag name from an XPath like ``.//article-title``."""
    # Handles: ".//article-title", ".//{*}article-id[@attr='val']", etc.
    match = re.search(r"(?:\{[\*}])?/?/?([a-zA-Z][\w-]*)", xpath)
    if match:
        return match.group(1)
    return None


# ============================================================================
# Metric 2: Text extraction fidelity
# ============================================================================


def compute_text_fidelity(
    parser: FullTextXMLParser,
    xml_content: str,
) -> dict[str, Any]:
    """
    Measure how much body text the parser captures vs what's in the XML.

    Compares the total character count of text extracted by the structured
    parser against the naive text content of the ``<body>`` element.

    Returns
    -------
    dict with keys: ``score``, ``body_chars``, ``extracted_chars``,
    ``ratio``, ``word_overlap``.
    """
    body_text = _get_all_body_text(xml_content)
    body_chars = len(body_text)
    body_words = body_text.split()
    body_word_set = set(body_words)

    # Flatten all text from structured output
    extracted_parts: list[str] = []
    try:
        sections = parser.get_full_text_sections_structured()
        for sec in sections:
            for block in sec.get("content", []):
                text = ""
                if isinstance(block, dict):
                    text = block.get("text") or block.get("caption") or ""
                    if block.get("items"):
                        text += "\n".join(f"- {item}" for item in block["items"])
                    if block.get("definition_terms"):
                        text += "\n".join(
                            f"{t.get('term', '')}: {t.get('def', '')}"
                            for t in block["definition_terms"]
                        )
                if text:
                    extracted_parts.append(text)
    except Exception as e:
        logger.warning("Text extraction failed: %s", e)

    extracted_text = "\n".join(extracted_parts)
    extracted_chars = len(extracted_text)
    extracted_words = extracted_text.split()

    # Character ratio (capped at 1.0 — we can't exceed the body)
    ratio = min(extracted_chars / max(body_chars, 1), 1.0)

    # Word overlap
    extracted_word_set = set(extracted_words)
    intersection = body_word_set & extracted_word_set
    word_overlap = len(intersection) / max(len(body_word_set), 1)

    return {
        "score": round(ratio, 4),
        "body_chars": body_chars,
        "extracted_chars": extracted_chars,
        "ratio": round(ratio, 4),
        "word_overlap": round(word_overlap, 4),
        "body_word_count": len(body_words),
        "extracted_word_count": len(extracted_words),
    }


# ============================================================================
# Metric 3: Section boundary accuracy
# ============================================================================


def _match_section_paths(
    expected_paths: set[str],
    found_paths: set[str],
) -> tuple[set[str], set[str]]:
    """Match expected and found section paths using direct and prefix matching.

    Returns a tuple of (direct_matches, partial_matches).
    """

    def _normalize(s: str) -> str:
        return " ".join(s.split())

    expected_norm = {_normalize(p): p for p in expected_paths}
    found_norm = {_normalize(p): p for p in found_paths}

    direct_matches = set(expected_paths) & set(found_paths)
    for en, ep in expected_norm.items():
        if en in found_norm and ep not in direct_matches:
            direct_matches.add(ep)
    for fn, fp in found_norm.items():
        if fn in expected_norm and fp not in direct_matches:
            direct_matches.add(fp)

    partial_matches: set[str] = set()
    for ep in expected_paths:
        for fp in found_paths:
            if fp.startswith(ep + "/") and "/" not in ep:
                partial_matches.add(ep)
                break
            if ep.startswith(fp + "/") and "/" not in fp:
                partial_matches.add(fp)
                break

    return direct_matches, partial_matches


def compute_section_accuracy(
    parser: FullTextXMLParser,
    xml_content: str,
) -> dict[str, Any]:
    """
    Measure section boundary accuracy.

    Compares section titles and nesting from raw XML vs parser output.

    Returns
    -------
    dict with keys: ``score``, ``expected_sections``, ``found_sections``,
    ``title_match_ratio``, ``depth_consistency``.
    """
    root = ET.fromstring(xml_content)
    expected_sections = _get_section_titles_from_xml(root)
    expected_paths = {s["section_path"] for s in expected_sections if s["section_path"]}
    expected_count = len(expected_sections)

    # Get sections from parser
    try:
        sections = parser.get_full_text_sections_structured()
    except Exception as e:
        logger.warning("Section extraction failed: %s", e)
        sections = []

    found_paths: set[str] = set()
    for sec in sections:
        if isinstance(sec, dict):
            path = sec.get("section_path") or sec.get("title", "")
            if path:
                found_paths.add(path)
        elif hasattr(sec, "section_path") and sec.section_path:
            found_paths.add(sec.section_path)
        elif hasattr(sec, "title") and sec.title:
            found_paths.add(sec.title)

    found_count = len(sections)

    # Sections from front/back matter (not <sec> elements in <body>):
    # These are synthetically created by the parser with distinct section_type
    # values: "back" for references, acknowledgments, footnotes, notes, glossary;
    # "appendix" for appendices.  Use the section_type field to reliably
    # distinguish them from body <sec> sections, which have section_type="body".
    #
    # Synthetic body sections (section_type="body" but not from <sec> elements):
    # "Article Title" and "Abstract" are always synthetic.
    # "body" is synthetic when the XML has <sec> elements; otherwise it's the
    # expected bare-<p> path (checked via expected_paths).
    _SYNTHETIC_BODY_PATHS_LOWER = frozenset({"article title", "abstract", "body"})

    def _get_section_type(sec: Any) -> str:
        if isinstance(sec, dict):
            return sec.get("section_type", "body")
        return getattr(sec, "section_type", "body")

    def _get_section_path(sec: Any) -> str:
        if isinstance(sec, dict):
            return sec.get("section_path", "") or sec.get("title", "")
        return getattr(sec, "section_path", "") or getattr(sec, "title", "")

    def _is_synthetic_body_path(path: str) -> bool:
        """Check if a path is a known synthetic body path, excluding cases
        where the path is expected (e.g., "body" for PLOS bare-<p> articles)."""
        lower = path.lower()
        if lower not in _SYNTHETIC_BODY_PATHS_LOWER:
            return False
        # "body" is only synthetic when it's NOT in the expected paths
        return not (lower == "body" and "body" in expected_paths)

    body_section_count = sum(
        1
        for sec in sections
        if _get_section_type(sec) == "body" and not _is_synthetic_body_path(_get_section_path(sec))
    )

    # Path matching: direct match + parent prefix matching
    direct_matches, partial_matches = _match_section_paths(expected_paths, found_paths)
    all_expected_matched = direct_matches | partial_matches
    path_ratio = len(all_expected_matched) / max(len(expected_paths), 1) if expected_paths else 1.0

    # Section count agreement (use body_section_count to exclude synthetic sections)
    count_diff = abs(expected_count - body_section_count)
    count_score = max(0.0, 1.0 - count_diff / max(expected_count, 1))

    # Composite score (weight more toward count for count-perfect cases)
    score = round(path_ratio * 0.5 + count_score * 0.5, 4)

    unmatched_expected = sorted(expected_paths - all_expected_matched)
    unmatched_found = sorted(found_paths - all_expected_matched)

    return {
        "score": score,
        "expected_section_count": expected_count,
        "found_section_count": found_count,
        "section_count_diff": count_diff,
        "expected_titles": sorted(expected_paths),
        "found_titles": sorted(found_paths),
        "title_match_count": len(all_expected_matched),
        "title_match_ratio": round(path_ratio, 4),
        "unmatched_expected": unmatched_expected,
        "unmatched_found": unmatched_found,
    }


# ============================================================================
# Metric 4: Inline element recall
# ============================================================================


def compute_inline_recall(
    parser: FullTextXMLParser,
    xml_content: str,
) -> dict[str, Any]:
    """
    Measure recall of inline content elements (xref, bold, italic, etc.).

    Returns
    -------
    dict with keys: ``score``, ``by_type``, ``total_in_xml``,
    ``total_found``, ``overall_recall``.
    """
    root = ET.fromstring(xml_content)
    xml_counts = _count_inline_elements_in_xml(root)

    if not xml_counts:
        # No inline elements in XML — trivially perfect
        return {
            "score": 1.0,
            "by_type": {},
            "total_in_xml": 0,
            "total_found": 0,
            "overall_recall": 1.0,
        }

    # Count inlines from structured parser output
    found_counts: dict[str, int] = {}
    try:
        sections = parser.get_full_text_sections_structured()
        for sec in sections:
            for block in sec.get("content", []):
                for inline in block.get("inlines", []):
                    itype = inline.get("type", "unknown")
                    # Normalize InlineElementType value → XML tag name
                    normalized = _INLINE_TYPE_TO_XML_TAG.get(itype, itype)
                    found_counts[normalized] = found_counts.get(normalized, 0) + 1
    except Exception as e:
        logger.warning("Inline extraction failed: %s", e)

    # Compute per-type recall
    by_type: dict[str, dict[str, Any]] = {}
    total_xml = 0
    total_found = 0
    for tag, xml_count in xml_counts.items():
        found_count = found_counts.get(tag, 0)
        recall = min(found_count / max(xml_count, 1), 1.0)
        by_type[tag] = {
            "in_xml": xml_count,
            "found": found_count,
            "recall": round(recall, 4),
        }
        total_xml += xml_count
        total_found += found_count

    overall_recall = total_found / max(total_xml, 1)

    return {
        "score": round(min(overall_recall, 1.0), 4),
        "by_type": by_type,
        "total_in_xml": total_xml,
        "total_found": total_found,
        "overall_recall": round(overall_recall, 4),
    }


# ============================================================================
# Metric 5: Metadata extraction accuracy
# ============================================================================


def compute_metadata_accuracy(
    parser: FullTextXMLParser,
    xml_content: str,
) -> dict[str, Any]:
    """
    Measure accuracy of metadata extraction.

    Compares extracted title, DOI, PMID, PMCID, and authors against
    ground truth from raw XML.

    Returns
    -------
    dict with keys: ``score``, ``fields``, ``exact_matches``, ``total_fields``.
    """
    root = ET.fromstring(xml_content)
    expected = _get_expected_metadata(root)

    try:
        extracted = parser.extract_metadata()
    except Exception as e:
        logger.warning("Metadata extraction failed: %s", e)
        extracted = {}

    fields: dict[str, dict[str, Any]] = {}
    exact_matches = 0
    total_fields = 0

    for field in ("title", "doi", "pmid", "pmcid"):
        total_fields += 1
        exp = expected.get(field, "")
        ext = extracted.get(field, "")
        # Both empty: field not present in article, not a parsing failure
        if not exp and not ext:
            match = True
        else:
            match = bool(exp) and bool(ext) and exp.strip().lower() == ext.strip().lower()
        if match:
            exact_matches += 1
        fields[field] = {
            "expected": exp,
            "extracted": ext,
            "match": match,
            "score": 1.0 if match else 0.0,
        }

    # Authors
    total_fields += 1
    exp_authors = expected.get("authors", [])
    ext_authors = extracted.get("authors", [])
    # Clean and compare
    exp_set = {a.strip().lower() for a in exp_authors if a.strip()}
    ext_set = {a.strip().lower() for a in ext_authors if a.strip()}
    author_overlap = len(exp_set & ext_set) / max(len(exp_set), 1) if exp_set else 1.0
    fields["authors"] = {
        "expected_count": len(exp_authors),
        "extracted_count": len(ext_authors),
        "overlap_ratio": round(author_overlap, 4),
        "score": round(author_overlap, 4),
    }
    if author_overlap >= 0.5:
        exact_matches += 1

    score = exact_matches / max(total_fields, 1)

    return {
        "score": round(score, 4),
        "fields": fields,
        "exact_matches": exact_matches,
        "total_fields": total_fields,
    }


# ============================================================================
# Composite: all metrics
# ============================================================================


def compute_all_metrics(
    parser: FullTextXMLParser,
    xml_content: str,
) -> dict[str, Any]:
    """
    Run all XML-level metrics on a parsed article and return a composite report.

    Parameters
    ----------
    parser : FullTextXMLParser
        Initialized and parsed parser instance.
    xml_content : str
        Original raw XML string.

    Returns
    -------
    dict with keys for each metric plus ``composite_score`` and ``per_metric`` summary.
    """
    results: dict[str, Any] = {}

    results["element_coverage"] = compute_element_coverage(parser, xml_content)
    results["text_fidelity"] = compute_text_fidelity(parser, xml_content)
    results["section_accuracy"] = compute_section_accuracy(parser, xml_content)
    results["inline_recall"] = compute_inline_recall(parser, xml_content)
    results["metadata_accuracy"] = compute_metadata_accuracy(parser, xml_content)

    # Composite score (equal weight)
    scores = [
        results["element_coverage"]["score"],
        results["text_fidelity"]["score"],
        results["section_accuracy"]["score"],
        results["inline_recall"]["score"],
        results["metadata_accuracy"]["score"],
    ]
    results["composite_score"] = round(sum(scores) / len(scores), 4)

    results["per_metric"] = {
        "element_coverage": results["element_coverage"]["score"],
        "text_fidelity": results["text_fidelity"]["score"],
        "section_accuracy": results["section_accuracy"]["score"],
        "inline_recall": results["inline_recall"]["score"],
        "metadata_accuracy": results["metadata_accuracy"]["score"],
    }

    return results
