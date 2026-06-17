"""
Content Block Model for structured section parsing.

Provides typed content blocks that preserve document structure for RAG/LLM pipelines.
Instead of flattening sections to {title, content} strings, each section contains
ordered content blocks with explicit types (paragraph, list, formula, figure_ref, etc.).

This is the core data model that other extensions (MathML, peer review, image fetching)
can integrate with by producing content blocks of their respective types.

Based on patterns from pmcgrab and JATS4R recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, ClassVar
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)


class ContentBlockType(str, Enum):
    """Typed content blocks that preserve document structure."""

    PARAGRAPH = "paragraph"
    LIST = "list"
    FORMULA = "formula"
    FIGURE_REF = "figure_ref"
    TABLE_REF = "table_ref"
    CODE = "code"
    BOXED_TEXT = "boxed_text"
    HEADING = "heading"
    FIGURE = "figure"
    TABLE = "table"
    MATHML = "mathml"
    PEER_REVIEW = "peer_review"
    UNKNOWN_BLOCK = "unknown_block"


@dataclass
class ContentBlock:
    """
    A single typed content block within a section.

    Each block carries a type identifier and type-specific fields.
    Unknown JATS blocks are preserved as ``unknown_block`` instead of being dropped.

    Parameters
    ----------
    type : ContentBlockType
        The semantic type of this content block.
    text : str, optional
        Plain text content (for paragraphs, headings, etc.).
    items : list[str], optional
        List items (for ordered/unordered lists).
    list_type : str, optional
        List style: ``"ordered"`` or ``"unordered"``.
    label : str, optional
        A display label (e.g. ``"Fig. 1"``, ``"Eq. 1"``).
    target_id : str, optional
        Reference target identifier (e.g. ``"fig1"``, ``"tab1"``).
    language : str, optional
        Programming language for code blocks.
    tex : str, optional
        LaTeX representation (for formulas).
    mathml : str, optional
        Raw MathML XML string.
    caption : str, optional
        Caption text (for figures, tables).
    uri : str, optional
        External URI (for graphics/images).
    jats_tag : str, optional
        Original JATS tag name (for unknown blocks).
    metadata : dict[str, Any], optional
        Additional type-specific metadata.
    """

    type: ContentBlockType
    text: str = ""
    items: list[str] = field(default_factory=list)
    list_type: str = ""
    label: str = ""
    target_id: str = ""
    language: str = ""
    tex: str = ""
    mathml: str = ""
    caption: str = ""
    uri: str = ""
    jats_tag: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Block types that carry items (list-like structure)
    LIST_TYPES: ClassVar[set[ContentBlockType]] = {ContentBlockType.LIST}

    # Block types that carry rich structured data
    RICH_TYPES: ClassVar[set[ContentBlockType]] = {
        ContentBlockType.FIGURE,
        ContentBlockType.TABLE,
        ContentBlockType.FORMULA,
    }

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize to a plain dictionary, omitting empty fields.

        Returns
        -------
        dict[str, Any]
            Compact dictionary representation.
        """
        base: dict[str, Any] = {"type": self.type.value}
        if self.text:
            base["text"] = self.text
        if self.items:
            base["items"] = self.items
        if self.list_type:
            base["list_type"] = self.list_type
        if self.label:
            base["label"] = self.label
        if self.target_id:
            base["target_id"] = self.target_id
        if self.language:
            base["language"] = self.language
        if self.tex:
            base["tex"] = self.tex
        if self.mathml:
            base["mathml"] = self.mathml
        if self.caption:
            base["caption"] = self.caption
        if self.uri:
            base["uri"] = self.uri
        if self.jats_tag:
            base["jats_tag"] = self.jats_tag
        if self.metadata:
            base["metadata"] = self.metadata
        return base

    @classmethod
    def paragraph(cls, text: str) -> ContentBlock:
        """Create a paragraph block."""
        return cls(type=ContentBlockType.PARAGRAPH, text=text)

    @classmethod
    def heading(cls, text: str) -> ContentBlock:
        """Create a heading block (section title within structured content)."""
        return cls(type=ContentBlockType.HEADING, text=text)

    @classmethod
    def list_block(cls, items: list[str], list_type: str = "unordered") -> ContentBlock:
        """Create a list block."""
        return cls(type=ContentBlockType.LIST, items=items, list_type=list_type)

    @classmethod
    def formula(cls, tex: str, label: str = "") -> ContentBlock:
        """Create a formula block."""
        return cls(type=ContentBlockType.FORMULA, tex=tex, label=label)

    @classmethod
    def figure_ref(cls, target_id: str, label: str = "") -> ContentBlock:
        """Create a figure reference block."""
        return cls(type=ContentBlockType.FIGURE_REF, target_id=target_id, label=label)

    @classmethod
    def table_ref(cls, target_id: str, label: str = "") -> ContentBlock:
        """Create a table reference block."""
        return cls(type=ContentBlockType.TABLE_REF, target_id=target_id, label=label)

    @classmethod
    def code(cls, text: str, language: str = "") -> ContentBlock:
        """Create a code block."""
        return cls(type=ContentBlockType.CODE, text=text, language=language)

    @classmethod
    def boxed_text(cls, text: str) -> ContentBlock:
        """Create a boxed text block."""
        return cls(type=ContentBlockType.BOXED_TEXT, text=text)

    @classmethod
    def figure(cls, label: str, caption: str, uri: str = "", target_id: str = "") -> ContentBlock:
        """Create a figure block."""
        return cls(
            type=ContentBlockType.FIGURE,
            label=label,
            caption=caption,
            uri=uri,
            target_id=target_id,
        )

    @classmethod
    def table_block(cls, label: str, caption: str, text: str = "") -> ContentBlock:
        """Create a table block."""
        return cls(
            type=ContentBlockType.TABLE,
            label=label,
            caption=caption,
            text=text,
        )

    @classmethod
    def unknown_block(cls, jats_tag: str, text: str = "") -> ContentBlock:
        """Create an unknown block (preserve JATS elements that are not explicitly handled)."""
        return cls(type=ContentBlockType.UNKNOWN_BLOCK, jats_tag=jats_tag, text=text)


@dataclass
class StructuredSection:
    """
    A document section containing ordered typed content blocks.

    Parameters
    ----------
    title : str
        Section title (may be empty for untitled sections).
    content : list[ContentBlock]
        Ordered sequence of content blocks in this section.
    section_type : str, optional
        Section type hint (e.g. ``"body"``, ``"back"``, ``"appendix"``).
    """

    title: str
    content: list[ContentBlock] = field(default_factory=list)
    section_type: str = "body"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "title": self.title,
            "content": [block.to_dict() for block in self.content],
            "section_type": self.section_type,
        }


class ContentBlockExtractor(BaseParser):
    """
    Extracts structured content blocks from JATS XML sections.

    Walks the children of each ``<sec>`` element and produces typed ``ContentBlock``
    instances, preserving the order and structure of the original document.

    Integrates with the existing ``SectionParser`` via the ``structured=True`` kwarg
    on ``get_full_text_sections()``.

    Parameters
    ----------
    root : ET.Element, optional
        Root element of the parsed XML.
    config : ElementPatterns, optional
        Configuration for element pattern matching.
    """

    # JATS block-level tags mapped to handler methods
    JATS_BLOCK_TAGS: ClassVar[dict[str, str]] = {
        "p": "paragraph",
        "list": "list",
        "list-item": "list",
        "disp-formula": "formula",
        "inline-formula": "formula",
        "fig": "figure",
        "table-wrap": "table",
        "code": "code",
        "boxed-text": "boxed_text",
        "sec": "section",
        "table": "table",
        "disp-quote": "paragraph",
        "preformat": "code",
    }

    def __init__(
        self,
        root: ET.Element | None = None,
        config: ElementPatterns | None = None,
    ):
        """Initialize the content block extractor."""
        super().__init__(root, config)
        self._handler_map = {
            "paragraph": self._handle_paragraph,
            "list": self._handle_list,
            "formula": self._handle_formula,
            "figure": self._handle_figure,
            "table": self._handle_table,
            "code": self._handle_code,
            "boxed_text": self._handle_boxed_text,
            "section": self._handle_subsection,
        }

    def extract_sections(self) -> list[StructuredSection]:
        """
        Extract all body sections with structured content blocks.

        Returns
        -------
        list[StructuredSection]
            List of sections with typed content blocks preserving document structure.
        """
        self._require_root()

        sections: list[StructuredSection] = []

        # Extract from main body
        if self.root is not None:
            for body_elem in self.root.findall(".//body"):
                for sec in body_elem.findall(".//sec"):
                    structured_sec = self._extract_structured_section(sec)
                    if structured_sec.content:
                        sections.append(structured_sec)

        # Extract additional content structures
        sections.extend(self._extract_additional_structures())

        logger.debug(f"Extracted {len(sections)} structured sections")
        return sections

    def _extract_structured_section(self, sec_element: ET.Element) -> StructuredSection:
        """Extract a single section as structured content blocks."""
        title = ""
        title_elem = sec_element.find("title")
        if title_elem is not None:
            title = XMLHelper.get_text_content(title_elem)

        content_blocks: list[ContentBlock] = []

        # Iterate through direct children of the section
        for child in sec_element:
            tag = self._get_local_tag(child.tag)
            if tag == "title":
                continue  # Already handled

            handler_name = self.JATS_BLOCK_TAGS.get(tag)
            if handler_name and handler_name in self._handler_map:
                blocks = self._handler_map[handler_name](child)
                content_blocks.extend(blocks)
            else:
                # Preserve unknown blocks as fallback
                text = XMLHelper.get_text_content(child)
                if text.strip():
                    content_blocks.append(
                        ContentBlock.unknown_block(jats_tag=tag, text=text.strip())
                    )

        return StructuredSection(
            title=title,
            content=content_blocks,
            section_type="body",
        )

    def _handle_paragraph(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <p> elements and similar text blocks."""
        text = XMLHelper.get_text_content(elem)
        if text.strip():
            return [ContentBlock.paragraph(text.strip())]
        return []

    def _handle_list(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <list> elements."""
        list_type = elem.get("list-type", "unordered")
        items: list[str] = []
        for item in elem.findall("list-item"):
            item_text = XMLHelper.get_text_content(item)
            if item_text.strip():
                items.append(item_text.strip())
        if items:
            return [ContentBlock.list_block(items=items, list_type=list_type)]
        return []

    def _handle_formula(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <disp-formula> and <inline-formula> elements."""
        label = ""
        label_elem = elem.find("label")
        if label_elem is not None:
            label = XMLHelper.get_text_content(label_elem)

        # Try to extract MathML first
        mathml_elem = elem.find(".//mml:math", self._get_namespace_map())
        tex = ""
        mathml_str = ""

        if mathml_elem is not None:
            mathml_str = ET.tostring(mathml_elem, encoding="unicode")
            # Basic MathML -> plain text fallback
            tex = XMLHelper.get_text_content(mathml_elem)

        # Fallback to alt-text or plain text
        if not tex.strip():
            alt_text = elem.find("alt-text")
            if alt_text is not None:
                tex = XMLHelper.get_text_content(alt_text)
            else:
                tex = XMLHelper.get_text_content(elem)

        block = ContentBlock.formula(tex=tex.strip(), label=label)
        if mathml_str:
            block.mathml = mathml_str
        return [block]

    def _handle_figure(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <fig> elements."""
        fig_id = elem.get("id", "")

        label = ""
        label_elem = elem.find("label")
        if label_elem is not None:
            label = XMLHelper.get_text_content(label_elem)

        caption = ""
        caption_elem = elem.find("caption")
        if caption_elem is not None:
            caption = XMLHelper.get_text_content(caption_elem)

        uri = ""
        graphic = elem.find(".//graphic")
        if graphic is not None:
            uri = str(
                graphic.get("{http://www.w3.org/1999/xlink}href", "") or graphic.get("href", "")
            )

        return [
            ContentBlock.figure(
                label=label,
                caption=caption,
                uri=uri,
                target_id=fig_id,
            )
        ]

    def _handle_table(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <table-wrap> and <table> elements."""
        label = ""
        label_elem = elem.find("label")
        if label_elem is not None:
            label = XMLHelper.get_text_content(label_elem)

        caption = ""
        caption_elem = elem.find("caption")
        if caption_elem is not None:
            caption = XMLHelper.get_text_content(caption_elem)

        text = XMLHelper.get_text_content(elem).strip()

        return [ContentBlock.table_block(label=label, caption=caption, text=text)]

    def _handle_code(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <code> and <preformat> elements."""
        language = elem.get("language", elem.get("lang", ""))
        text = XMLHelper.get_text_content(elem)
        if text.strip():
            return [ContentBlock.code(text=text.strip(), language=language)]
        return []

    def _handle_boxed_text(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <boxed-text> elements."""
        text = XMLHelper.get_text_content(elem)
        if text.strip():
            return [ContentBlock.boxed_text(text.strip())]
        return []

    def _handle_subsection(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle nested <sec> elements as a flat heading + content."""
        blocks: list[ContentBlock] = []

        title_elem = elem.find("title")
        if title_elem is not None:
            title_text = XMLHelper.get_text_content(title_elem)
            if title_text.strip():
                blocks.append(ContentBlock.heading(title_text.strip()))

        # Recurse into subsection children
        for child in elem:
            tag = self._get_local_tag(child.tag)
            if tag == "title":
                continue
            handler_name = self.JATS_BLOCK_TAGS.get(tag)
            if handler_name and handler_name in self._handler_map:
                blocks.extend(self._handler_map[handler_name](child))

        return blocks

    def _extract_additional_structures(self) -> list[StructuredSection]:
        """Extract back-matter structures (acknowledgments, appendices, glossary)."""
        structures: list[StructuredSection] = []
        if self.root is None:
            return structures

        # Acknowledgments
        for ack in self.root.findall(".//ack"):
            text = XMLHelper.get_text_content(ack)
            if text.strip():
                structures.append(
                    StructuredSection(
                        title="Acknowledgments",
                        content=[ContentBlock.paragraph(text.strip())],
                        section_type="back",
                    )
                )

        # Appendices
        for app in self.root.findall(".//app"):
            title = ""
            title_elem = app.find("title")
            if title_elem is not None:
                title = XMLHelper.get_text_content(title_elem)
            blocks = self._extract_appendix_blocks(app)
            structures.append(
                StructuredSection(
                    title=title or "Appendix",
                    content=blocks,
                    section_type="appendix",
                )
            )

        # Glossary
        for gloss in self.root.findall(".//glossary"):
            title = ""
            title_elem = gloss.find("title")
            if title_elem is not None:
                title = XMLHelper.get_text_content(title_elem)
            text = XMLHelper.get_text_content(gloss)
            structures.append(
                StructuredSection(
                    title=title or "Glossary",
                    content=[ContentBlock.paragraph(text.strip())] if text.strip() else [],
                    section_type="back",
                )
            )

        return structures

    def _extract_appendix_blocks(self, app_elem: ET.Element) -> list[ContentBlock]:
        """Extract content blocks from an appendix element."""
        blocks: list[ContentBlock] = []
        for child in app_elem:
            tag = self._get_local_tag(child.tag)
            handler_name = self.JATS_BLOCK_TAGS.get(tag)
            if handler_name and handler_name in self._handler_map:
                blocks.extend(self._handler_map[handler_name](child))
            elif tag not in ("title",):
                text = XMLHelper.get_text_content(child)
                if text.strip():
                    blocks.append(ContentBlock.paragraph(text.strip()))
        return blocks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_local_tag(tag: str) -> str:
        """Strip namespace from a tag name."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _get_namespace_map() -> dict[str, str]:
        """Get namespace map for common XML namespaces."""
        return {
            "mml": "http://www.w3.org/1998/Math/MathML",
            "xlink": "http://www.w3.org/1999/xlink",
        }
