"""
Base parser class for specialized parsers.

This module provides the base class that all specialized parsers inherit from.
"""

import logging
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.config.element_patterns import ElementPatterns
from pyeuropepmc.features.fulltext.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class BaseParser:
    """Base class for specialized XML parsers."""

    def __init__(self, root: ET.Element | None = None, config: ElementPatterns | None = None):
        """
        Initialize the parser.

        Parameters
        ----------
        root : ET.Element, optional
            Root element of the parsed XML
        config : ElementPatterns, optional
            Configuration for element patterns
        """
        self.root = root
        self.config = config or ElementPatterns()
        self._helper = XMLHelper

    def _require_root(self) -> None:
        """Raise an error if no root element is available."""
        if self.root is None:
            raise ParsingError(
                ErrorCodes.PARSE003,
                {"message": "No XML content has been parsed. Call parse() first."},
            )

    def _get_text_content(self, element: ET.Element | None) -> str:
        """Get all text content from an element and its descendants."""
        return self._helper.get_text_content(element)

    @staticmethod
    def _child_sections(parent: ET.Element) -> list[ET.Element]:
        """The outermost <sec> elements beneath ``parent``.

        Descends through non-section wrappers but stops at each <sec>, so a
        subsection is never returned alongside its own parent. Identity is
        never compared - lxml can hand back distinct proxy objects for one
        node, which makes an ``id()``-keyed exclusion set unreliable.
        """
        found: list[ET.Element] = []

        def walk(elem: ET.Element) -> None:
            for child in elem:
                if child.tag == "sec":
                    found.append(child)
                else:
                    walk(child)

        walk(parent)
        return found

    @staticmethod
    def _text_excluding(element: ET.Element, *skip_tags: str) -> str:
        """Full text of ``element`` with the named subtrees left out.

        ``_section_own_elements(..., stop_at=...)`` keeps a container's own
        <p> out of a section's paragraph list, but a <p> that *wraps* a <list>
        or <table-wrap> still carries that content in its own text. A caller
        that renders those containers separately would emit the text twice -
        seven paragraphs in PMC4355508, and three times over in PMC12126031,
        where a table sits inside a paragraph with lists in its cells.
        """
        skip = set(skip_tags)
        parts: list[str] = []

        def walk(elem: ET.Element) -> None:
            if elem.text:
                parts.append(elem.text)
            for child in elem:
                # Comments and processing instructions - lxml keeps them as
                # children with a non-string tag. See XMLHelper.get_text_content.
                if not isinstance(child.tag, str):
                    if child.tail:
                        parts.append(child.tail)
                    continue
                if child.tag not in skip:
                    walk(child)
                if child.tail:
                    parts.append(child.tail)

        walk(element)
        return " ".join("".join(parts).split())

    @staticmethod
    def _own_bodies(root: ET.Element) -> list[ET.Element]:
        """The <body> elements belonging to this article, not to a sub-article.

        Peer-reviewed articles ship the reports as <sub-article>, each with its
        own <body>. A `.//body` search returns all of them, so iterating the
        result mixed reviewer text into the article's own sections: in
        PMC13567752 that turned a 39,374-character body into 94,895 characters
        of "sections", and duplicated the data-availability statement in
        PMC13567818.

        Descends through wrappers but stops at <sub-article> and <response>,
        without comparing element identity - lxml can hand back distinct proxy
        objects for one node.
        """
        found: list[ET.Element] = []

        def walk(elem: ET.Element) -> None:
            for child in elem:
                if child.tag in ("sub-article", "response"):
                    continue
                if child.tag == "body":
                    found.append(child)
                else:
                    walk(child)

        if root.tag == "body":
            return [root]
        walk(root)
        return found

    @staticmethod
    def _section_own_elements(
        section: ET.Element, *tags: str, stop_at: tuple[str, ...] = ()
    ) -> list[ET.Element]:
        """Descendants of ``section`` with these tags that no nested <sec> owns.

        JATS sections nest, and the flat extractors selected descendant content
        with ``.//``: a parent emitted its subsections' paragraphs as well as
        its own, and each subsection then emitted them again - duplicating
        40-60% of the output (#209).

        Content inside a nested <sec> belongs to that subsection. Everything
        else belongs here, including content wrapped in <boxed-text> and
        similar, which a direct-children-only rule would have lost.

        ``stop_at`` names further containers to treat as barriers. A caller
        that renders <list> itself must pass ``stop_at=("list",)`` when asking
        for paragraphs, or a <p> inside a <list-item> is emitted twice - once
        as a paragraph and again as a list item.
        """
        wanted = set(tags)
        barriers = {"sec", *stop_at}
        found: list[ET.Element] = []

        def walk(parent: ET.Element) -> None:
            for child in parent:
                if child.tag in barriers:
                    continue  # a subsection's content, or a container rendered
                    # separately by the caller - not this section's own
                if child.tag in wanted:
                    found.append(child)
                else:
                    walk(child)

        walk(section)
        return found

    def _extract_flat_texts(
        self,
        parent: ET.Element,
        pattern: str,
        filter_empty: bool = True,
        use_full_text: bool = False,
    ) -> list[str]:
        """Extract flat text fields from XML."""
        return self._helper.extract_flat_texts(parent, pattern, filter_empty, use_full_text)

    def _extract_with_fallbacks(
        self, element: ET.Element, patterns: list[str], use_full_text: bool = False
    ) -> str | None:
        """Try multiple element patterns in order until one succeeds."""
        return self._helper.extract_with_fallbacks(element, patterns, use_full_text)

    def _extract_structured_fields(
        self,
        parent: ET.Element,
        field_patterns: dict[str, str],
        first_only: bool = True,
    ) -> dict[str, Any]:
        """Extract multiple fields from a parent element as a structured dict."""
        return self._helper.extract_structured_fields(parent, field_patterns, first_only)

    def extract_elements_by_patterns(
        self,
        patterns: dict[str, str],
        return_type: str = "text",
        first_only: bool = False,
        get_attribute: dict[str, str] | None = None,
    ) -> dict[str, list[Any]]:
        """
        Extract elements from the parsed XML that match user-defined tag patterns.

        Parameters
        ----------
        patterns : dict
            Keys are output field names, values are XPath-like patterns
        return_type : str
            'text': return text content; 'element': return Element; 'attribute': return attribute
        first_only : bool
            If True, only return the first match for each pattern
        get_attribute : dict, optional
            If return_type is 'attribute', a dict mapping field name to attribute name

        Returns
        -------
        dict
            Dictionary where each key is from the input dict and value is list of results
        """
        self._require_root()

        results: dict[str, list[Any]] = {}
        for key, pattern in patterns.items():
            matches = self.root.findall(pattern) if self.root is not None else []
            if not matches:
                results[key] = []
                continue
            values: list[Any]
            if return_type == "text":
                values = [self._get_text_content(elem) for elem in matches]
            elif return_type == "element":
                values = matches
            elif return_type == "attribute":
                attr = get_attribute[key] if get_attribute and key in get_attribute else None
                if attr is None:
                    raise ValueError(f"No attribute specified for key '{key}' in get_attribute.")
                values = [elem.get(attr) for elem in matches]
            else:
                raise ValueError(f"Unknown return_type: {return_type}")
            if first_only:
                results[key] = [values[0]] if values else []
            else:
                results[key] = values
        return results
