"""
Content Block Model for structured section parsing.

Provides typed content blocks that preserve document structure for RAG/LLM pipelines.
Instead of flattening sections to {title, content} strings, each section contains
ordered content blocks with explicit types (paragraph, list, formula, figure_ref, etc.).

This is the core data model that other extensions (MathML, peer review, image fetching)
can integrate with by producing content blocks of their respective types.

Extensions beyond pmcgrab:
- Inline element tracking (xref, inline-formula, chem-struct within paragraphs)
- Definition list support
- Parse diagnostics (per-block parse_status / quality_score)
- RAG chunking with section provenance
- LangChain/LlamaIndex adapter
- Schema versioning

Based on patterns from pmcgrab, JATS4R recommendations, and competitive analysis
of docling, pubmed_parser, and ncbijs/jats.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Any, ClassVar
from xml.etree import ElementTree as ET  # nosec B405

from pyeuropepmc.processing.config.element_patterns import ElementPatterns
from pyeuropepmc.processing.parsers.base_parser import BaseParser
from pyeuropepmc.processing.utils.xml_helpers import XMLHelper

logger = logging.getLogger(__name__)

# Schema version for content block output tracking
SCHEMA_VERSION = "0.2.0"


class InlineElementType(str, Enum):
    """Types of inline elements that can appear within a paragraph block."""

    XREF = "xref"
    INLINE_FORMULA = "inline_formula"
    BOLD = "bold"
    ITALIC = "italic"
    SUP = "superscript"
    SUB = "subscript"
    CHEMICAL_STRUCTURE = "chemical_structure"
    NAMED_CONTENT = "named_content"
    STRIKETHROUGH = "strikethrough"
    UNDERLINE = "underline"
    MONOSPACE = "monospace"
    SMALL_CAPS = "small_caps"
    ROMAN = "roman"
    SANS_SERIF = "sans_serif"
    STYLED_CONTENT = "styled_content"
    UNKNOWN_INLINE = "unknown_inline"


@dataclass
class InlineElement:
    """
    An inline element occurring within a content block's text.

    Records the position, type, and target of inline elements (xrefs, formatting,
    inline formulas) so downstream consumers can reconstruct rich text or track
    cross-references.

    Parameters
    ----------
    type : InlineElementType
        The type of inline element.
    text : str
        The rendered text of this inline element.
    ref_type : str, optional
        For xref elements: the reference type (e.g. ``"fig"``, ``"bibr"``, ``"table"``).
    target_id : str, optional
        The ``rid`` attribute of an xref, identifying the target element.
    position : int, optional
        Character offset of this inline element within the parent block text.
    length : int, optional
        Character length of the inline text within the parent block.
    formula_latex : str, optional
        LaTeX representation (for inline formulas).
    language : str, optional
        Language for named_content or monospace elements.
    metadata : dict, optional
        Additional type-specific metadata.
    """

    type: InlineElementType
    text: str = ""
    ref_type: str = ""
    target_id: str = ""
    position: int = 0
    length: int = 0
    formula_latex: str = ""
    language: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary, omitting empty fields."""
        base: dict[str, Any] = {
            "type": self.type.value,
            "text": self.text,
            "position": self.position,
            "length": self.length,
        }
        if self.ref_type:
            base["ref_type"] = self.ref_type
        if self.target_id:
            base["target_id"] = self.target_id
        if self.formula_latex:
            base["formula_latex"] = self.formula_latex
        if self.language:
            base["language"] = self.language
        if self.metadata:
            base["metadata"] = self.metadata
        return base


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
    QUOTE = "quote"
    MATHML = "mathml"
    PEER_REVIEW = "peer_review"
    DEFINITION_LIST = "definition_list"
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
    inlines : list[InlineElement], optional
        Tracked inline elements within this block (xrefs, formatting, inline formulas).
    parse_status : str, optional
        Quality indicator: ``"success"``, ``"partial"``, ``"error"``.
    quality_score : float, optional
        Completeness score 0-1 based on expected vs actual fields populated.
    parser_notes : list[str], optional
        Warning or diagnostic messages from the parser.
    definition_terms : list[dict], optional
        For definition_list: list of {term, def} dicts.
    schema_version : str, optional
        Version of the content block schema used for serialization.
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
    inlines: list[InlineElement] = field(default_factory=list)
    parse_status: str = "success"
    quality_score: float = 1.0
    parser_notes: list[str] = field(default_factory=list)
    definition_terms: list[dict[str, str]] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    # Block types that carry items (list-like structure)
    LIST_TYPES: ClassVar[set[ContentBlockType]] = {
        ContentBlockType.LIST,
    }

    # Block types that carry definition pairs
    DEF_LIST_TYPES: ClassVar[set[ContentBlockType]] = {
        ContentBlockType.DEFINITION_LIST,
    }

    # Block types that carry rich structured data
    RICH_TYPES: ClassVar[set[ContentBlockType]] = {
        ContentBlockType.FIGURE,
        ContentBlockType.TABLE,
        ContentBlockType.FORMULA,
    }

    def to_dict(self) -> dict[str, Any]:  # noqa: C901
        """
        Serialize to a plain dictionary, omitting empty fields.

        Returns
        -------
        dict[str, Any]
            Compact dictionary representation.
        """
        base: dict[str, Any] = {
            "type": self.type.value,
            "schema_version": self.schema_version,
        }
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
        if self.inlines:
            base["inlines"] = [i.to_dict() for i in self.inlines]
        if self.definition_terms:
            base["definition_terms"] = self.definition_terms
        if self.rows:
            base["rows"] = self.rows
        if self.metadata:
            base["metadata"] = self.metadata
        if self.parse_status != "success":
            base["parse_status"] = self.parse_status
        if self.quality_score < 1.0:
            base["quality_score"] = self.quality_score
        if self.parser_notes:
            base["parser_notes"] = self.parser_notes
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
    def quote(cls, text: str, inlines: list[InlineElement] | None = None) -> ContentBlock:
        """Create a quote block (for disp-quote elements)."""
        return cls(type=ContentBlockType.QUOTE, text=text, inlines=inlines or [])

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
    def table_block(
        cls, label: str, caption: str, text: str = "", rows: list[list[str]] | None = None
    ) -> ContentBlock:
        """Create a table block with optional cell structure."""
        return cls(
            type=ContentBlockType.TABLE,
            label=label,
            caption=caption,
            text=text,
            rows=rows or [],
        )

    @classmethod
    def unknown_block(cls, jats_tag: str, text: str = "") -> ContentBlock:
        """Create an unknown block (preserve JATS elements that are not explicitly handled)."""
        return cls(type=ContentBlockType.UNKNOWN_BLOCK, jats_tag=jats_tag, text=text)

    @classmethod
    def definition_list(cls, terms: list[dict[str, str]]) -> ContentBlock:
        """Create a definition list block (term/def pairs).

        Parameters
        ----------
        terms : list[dict[str, str]]
            List of ``{"term": "...", "def": "..."}`` dictionaries.
        """
        return cls(type=ContentBlockType.DEFINITION_LIST, definition_terms=terms)

    @classmethod
    def paragraph_with_inlines(
        cls,
        text: str,
        inlines: list[InlineElement] | None = None,
    ) -> ContentBlock:
        """Create a paragraph block with tracked inline elements."""
        return cls(
            type=ContentBlockType.PARAGRAPH,
            text=text,
            inlines=inlines or [],
        )


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
    section_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary with schema version."""
        result: dict[str, Any] = {
            "title": self.title,
            "content": [block.to_dict() for block in self.content],
            "section_type": self.section_type,
            "schema_version": SCHEMA_VERSION,
        }
        if self.section_path:
            result["section_path"] = self.section_path
        return result

    def to_chunks(
        self,
        max_tokens: int = 512,
        overlap: int = 50,
        approx_chars_per_token: int = 4,
    ) -> list[dict[str, Any]]:
        """
        Split section content into overlapping chunks suitable for RAG/LLM ingestion.

        Each chunk preserves ``section_path`` provenance so downstream retrievers
        can cite the original document location.

        Parameters
        ----------
        max_tokens : int, optional
            Maximum tokens per chunk (default 512).
        overlap : int, optional
            Token overlap between consecutive chunks (default 50).
        approx_chars_per_token : int, optional
            Approximation for token estimation (default 4 for English text).

        Returns
        -------
        list[dict[str, Any]]
            List of chunk dicts with keys: ``text``, ``section_path``,
            ``block_type``, ``section_type``, ``chunk_index``, ``estimated_tokens``.
        """
        chunks: list[dict[str, Any]] = []
        current_chunk: list[str] = []
        current_tokens = 0
        max_chars = max_tokens * approx_chars_per_token

        for block in self.content:
            block_text = self._block_text(block)
            block_chars = len(block_text)
            block_tokens = block_chars // approx_chars_per_token

            # If a single block exceeds max_tokens, split it
            if block_tokens > max_tokens:
                self._split_block_into_chunks(block_text, max_chars, chunks, self.title)
                continue

            # If adding this block would exceed max_tokens, flush current chunk
            if current_tokens + block_tokens > max_tokens and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    {
                        "text": chunk_text,
                        "section_path": self.title,
                        "section_type": self.section_type,
                        "chunk_index": len(chunks),
                        "estimated_tokens": current_tokens,
                    }
                )
                # Keep overlap blocks
                overlap_chars = overlap * approx_chars_per_token
                retained: list[str] = []
                retained_tokens = 0
                for cb in reversed(current_chunk):
                    cb_chars = len(cb)
                    cb_tokens = cb_chars // approx_chars_per_token
                    if retained_tokens + cb_tokens > overlap_chars:
                        break
                    retained.insert(0, cb)
                    retained_tokens += cb_tokens
                current_chunk = retained
                current_tokens = retained_tokens

            current_chunk.append(block_text)
            current_tokens += block_tokens

        # Flush final chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "section_path": self.title,
                    "section_type": self.section_type,
                    "chunk_index": len(chunks),
                    "estimated_tokens": current_tokens,
                }
            )

        return chunks

    @staticmethod
    def _block_text(block: ContentBlock | dict[str, Any]) -> str:
        """Extract the primary text content from a block (object or dict)."""
        if isinstance(block, dict):
            return block.get("text") or ""
        if block.text:
            return block.text
        if block.items:
            return "\n".join(f"- {item}" for item in block.items)
        if block.definition_terms:
            return "\n".join(
                f"{t.get('term', '')}: {t.get('def', '')}" for t in block.definition_terms
            )
        if block.caption:
            return block.caption
        return ""

    @staticmethod
    def _split_block_into_chunks(
        text: str,
        max_chars: int,
        chunks: list[dict[str, Any]],
        section_title: str,
    ) -> None:
        """Split an oversized block into smaller chunks by sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > max_chars and current:
                chunks.append(
                    {
                        "text": current.strip(),
                        "section_path": section_title,
                        "section_type": "",
                        "chunk_index": len(chunks),
                        "estimated_tokens": len(current) // 4,
                    }
                )
                current = sentence
            else:
                current += " " + sentence if current else sentence
        if current:
            chunks.append(
                {
                    "text": current.strip(),
                    "section_path": section_title,
                    "section_type": "",
                    "chunk_index": len(chunks),
                    "estimated_tokens": len(current) // 4,
                }
            )

    def to_langchain_documents(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Convert blocks to LangChain-compatible Document dictionaries.

        Each block becomes a document with ``page_content`` and ``metadata`` fields
        matching LangChain's Document schema. Works with both LangChain and LlamaIndex.

        Parameters
        ----------
        metadata : dict, optional
            Additional metadata to attach to every document (e.g. article_id, source).

        Returns
        -------
        list[dict[str, Any]]
            List of ``{"page_content": str, "metadata": dict}`` dicts.
        """
        docs: list[dict[str, Any]] = []
        base_meta = dict(metadata) if metadata else {}
        base_meta.setdefault("section_title", self.title)
        base_meta.setdefault("section_type", self.section_type)

        for i, block in enumerate(self.content):
            text = self._block_text(block)
            if not text:
                continue
            meta = dict(base_meta)
            meta["block_type"] = block.type.value
            meta["block_index"] = i
            if block.label:
                meta["label"] = block.label
            docs.append({"page_content": text, "metadata": meta})

        return docs


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
        "def-list": "definition_list",
        "disp-formula": "formula",
        "inline-formula": "formula",
        "fig": "figure",
        "table-wrap": "table",
        "code": "code",
        "boxed-text": "boxed_text",
        "sec": "section",
        "table": "table",
        "disp-quote": "quote",
        "preformat": "code",
        "media": "media",
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
            "definition_list": self._handle_def_list,
            "formula": self._handle_formula,
            "figure": self._handle_figure,
            "table": self._handle_table,
            "code": self._handle_code,
            "boxed_text": self._handle_boxed_text,
            "section": self._handle_subsection,
            "media": self._handle_media,
            "quote": self._handle_quote,
        }

    # ------------------------------------------------------------------
    # Inline element tag mapping for paragraph-level tracking
    # ------------------------------------------------------------------
    INLINE_TAG_MAP: ClassVar[dict[str, str]] = {
        "xref": "xref",
        "bold": "bold",
        "italic": "italic",
        "sup": "superscript",
        "sub": "subscript",
        "inline-formula": "inline_formula",
        "chem-struct": "chemical_structure",
        "named-content": "named_content",
        "strike": "strikethrough",
        "underline": "underline",
        "monospace": "monospace",
        "sc": "small_caps",
        "roman": "roman",
        "sans-serif": "sans_serif",
        "styled-content": "styled_content",
    }

    @staticmethod
    def _get_multipart_title(title_elem: ET.Element | None) -> str:
        """
        Reconstruct a section title from its child elements (handles inline formatting).

        Some JATS titles contain ``<italic>``, ``<bold>``, ``<sup>``, etc. inside
        the title element. This captures all text content in document order.
        """
        if title_elem is None:
            return ""
        # Gather text from the element and all descendants in document order
        parts: list[str] = []
        if title_elem.text:
            parts.append(title_elem.text)
        for child in title_elem:
            child_text = XMLHelper.get_text_content(child)
            if child_text.strip():
                parts.append(child_text)
            if child.tail:
                parts.append(child.tail)
        return "".join(parts).strip()

    def extract_sections(self) -> list[StructuredSection]:
        """
        Extract all body sections with structured content blocks.

        Recursively walks nested ``<sec>`` elements, building ``section_path``
        for provenance tracking (e.g. ``"Methods/Statistical Analysis"``).
        Each nested section is returned as its own ``StructuredSection`` in a flat list,
        preserving its ``section_path`` for downstream matching.

        Returns
        -------
        list[StructuredSection]
            Flat list of sections with typed content blocks.
        """
        self._require_root()

        sections: list[StructuredSection] = []

        # Recursively collect all sec elements (including nested)
        if self.root is not None:
            for body_elem in self.root.findall(".//body"):
                self._collect_sections(body_elem, sections)

        # Extract article title section (appears first in output)
        article_title_section = self._extract_article_title()
        if article_title_section is not None:
            sections.insert(0, article_title_section)

        # Extract abstract from front matter (appears after title in output)
        abstract_section = self._extract_abstract()
        if abstract_section is not None:
            sections.insert(1 if article_title_section else 0, abstract_section)

        # Extract footnotes from back matter
        fn_sections = self._extract_footnotes()
        sections.extend(fn_sections)

        # Extract additional content structures
        sections.extend(self._extract_additional_structures())

        logger.debug(f"Extracted {len(sections)} structured sections")
        return sections

    def _collect_sections(
        self,
        parent: ET.Element,
        sections: list[StructuredSection],
        parent_path: str = "",
    ) -> None:
        """
        Recursively walk an element tree, collecting all ``<sec>`` elements
        as ``StructuredSection`` entries into the ``sections`` list.

        Nested sections each get their own entry with a ``section_path``
        that tracks the hierarchy (e.g. ``"Methods/Statistical Analysis"``),
        rather than being flattened into the parent section.
        """
        for child in parent:
            tag = self._get_local_tag(child.tag)
            if tag == "sec":
                section = self._extract_structured_section(child, parent_path)
                if section.content:
                    sections.append(section)
                # Recurse into nested sections
                self._collect_sections(child, sections, section.section_path)
            elif tag == "body":
                # Descend into body elements
                self._collect_sections(child, sections, parent_path)

    def _extract_structured_section(
        self,
        sec_element: ET.Element,
        parent_path: str = "",
    ) -> StructuredSection:
        """Extract a single section as structured content blocks.

        Parameters
        ----------
        sec_element : ET.Element
            The ``<sec>`` element to extract.
        parent_path : str, optional
            Path of the parent section (e.g. ``"Methods"``) for nesting.

        Returns
        -------
        StructuredSection
            Section with typed content blocks and full section_path.
        """
        title_elem = sec_element.find("title")
        title = self._get_multipart_title(title_elem)

        # Build hierarchical section path
        if parent_path and title:
            section_path = f"{parent_path}/{title}"
        elif title:
            section_path = title
        else:
            section_path = parent_path

        content_blocks: list[ContentBlock] = []

        # Iterate through direct children of the section
        for child in sec_element:
            tag = self._get_local_tag(child.tag)
            if tag == "title":
                continue  # Already handled

            # Nested <sec> elements are handled by _collect_sections
            # to preserve them as separate entries with section_path
            if tag == "sec":
                continue

            handler_name = self.JATS_BLOCK_TAGS.get(tag)
            if handler_name and handler_name in self._handler_map:
                blocks = self._handler_map[handler_name](child)
                content_blocks.extend(blocks)
            else:
                extra = self._handle_special_section_child(child, tag)
                content_blocks.extend(extra)

        return StructuredSection(
            title=title,
            content=content_blocks,
            section_type="body",
            section_path=section_path,
        )

    def _handle_special_section_child(self, child: ET.Element, tag: str) -> list[ContentBlock]:
        """Handle section children that are not standard JATS block tags."""
        if tag == "supplementary-material":
            # Traverse into supplementary-material → caption → p
            blocks: list[ContentBlock] = []
            for caption in child.findall("caption"):
                for p_elem in caption.findall(".//p"):
                    blocks.extend(self._handle_paragraph(p_elem))
            return blocks
        if tag == "fn-group":
            return self._extract_fn_group_blocks(child)
        # Preserve unknown blocks as fallback
        text = XMLHelper.get_text_content(child)
        if text.strip():
            return [ContentBlock.unknown_block(jats_tag=tag, text=text.strip())]
        return []

    def _extract_fn_group_blocks(self, fn_group: ET.Element) -> list[ContentBlock]:
        """Extract footnotes from a ``<fn-group>`` with inline tracking."""
        blocks: list[ContentBlock] = []
        for fn in fn_group.findall("fn"):
            fn_text, fn_inlines, _ = self._extract_inlines_recursive(fn, 0)
            joined = "".join(fn_text).strip()
            if not joined:
                continue
            label_elem = fn.find("label")
            prefix = ""
            if label_elem is not None:
                prefix = XMLHelper.get_text_content(label_elem) + " "
            full_text = f"{prefix}{joined}"
            if fn_inlines:
                blocks.append(
                    ContentBlock.paragraph_with_inlines(text=full_text, inlines=fn_inlines)
                )
            else:
                blocks.append(ContentBlock.paragraph(full_text))
        return blocks

    def _handle_paragraph(self, elem: ET.Element) -> list[ContentBlock]:  # noqa: C901
        """
        Handle ``<p>`` elements with inline element tracking.

        Walks child elements to detect xrefs, inline formatting, and inline formulas,
        recording them as ``InlineElement`` entries in the paragraph block.
        """
        # Collect all text and inline elements
        inlines: list[InlineElement] = []
        parts: list[str] = []
        pos = 0

        # Capture text before the first child element (elem.text)
        if elem.text:
            initial_text = self._resolve_entities(elem.text)
            parts.append(initial_text)
            pos += len(initial_text)

        # Walk children in document order to capture inline elements
        for child in elem:
            tag = self._get_local_tag(child.tag)
            inline_handler = self.INLINE_TAG_MAP.get(tag)

            if inline_handler == "xref":
                # Cross-reference
                child_text = self._resolve_entities(XMLHelper.get_text_content(child))
                ref_type = child.get("ref-type", "")
                rid = child.get("rid", "")
                if child_text:
                    parts.append(child_text)
                    inlines.append(
                        InlineElement(
                            type=InlineElementType.XREF,
                            text=child_text,
                            ref_type=ref_type,
                            target_id=rid,
                            position=pos,
                            length=len(child_text),
                        )
                    )
                    # Track nested inlines inside xref (e.g., <sup>1</sup>)
                    nested = self._collect_nested_inlines(child, pos)
                    inlines.extend(nested)
                    pos += len(child_text)

            elif inline_handler == "inline_formula":
                # Inline formula
                child_text = self._resolve_entities(XMLHelper.get_text_content(child))
                formula_latex = self._convert_inline_formula(child)
                display_text = child_text or "[formula]"
                parts.append(display_text)
                inlines.append(
                    InlineElement(
                        type=InlineElementType.INLINE_FORMULA,
                        text=child_text,
                        formula_latex=formula_latex,
                        position=pos,
                        length=len(display_text),
                    )
                )
                pos += len(display_text)

            elif inline_handler in (
                "bold",
                "italic",
                "superscript",
                "subscript",
                "chemical_structure",
                "named_content",
                "strikethrough",
                "underline",
                "monospace",
                "small_caps",
                "roman",
                "sans_serif",
                "styled_content",
            ):
                child_text = self._resolve_entities(XMLHelper.get_text_content(child))
                if child_text:
                    parts.append(child_text)
                    ie_type = {
                        "bold": InlineElementType.BOLD,
                        "italic": InlineElementType.ITALIC,
                        "superscript": InlineElementType.SUP,
                        "subscript": InlineElementType.SUB,
                        "chemical_structure": InlineElementType.CHEMICAL_STRUCTURE,
                        "named_content": InlineElementType.NAMED_CONTENT,
                        "strikethrough": InlineElementType.STRIKETHROUGH,
                        "underline": InlineElementType.UNDERLINE,
                        "monospace": InlineElementType.MONOSPACE,
                        "small_caps": InlineElementType.SMALL_CAPS,
                        "roman": InlineElementType.ROMAN,
                        "sans_serif": InlineElementType.SANS_SERIF,
                        "styled_content": InlineElementType.STYLED_CONTENT,
                    }.get(inline_handler, InlineElementType.UNKNOWN_INLINE)
                    # Extract xml:lang attribute for named-content
                    lang = ""
                    if inline_handler == "named_content":
                        lang = child.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                    inlines.append(
                        InlineElement(
                            type=ie_type,
                            text=child_text,
                            language=lang,
                            position=pos,
                            length=len(child_text),
                        )
                    )
                    # Track nested inlines (e.g., <xref> inside <sup>)
                    nested = self._collect_nested_inlines(child, pos)
                    inlines.extend(nested)
                    pos += len(child_text)

            else:
                # Unknown block element (e.g., <fig> inside <p>) —
                # recursively walk for inline elements instead of flattening
                child_parts, child_inlines, pos = self._extract_inlines_recursive(
                    child, pos, parent_inlines=inlines
                )
                parts.extend(child_parts)
                inlines.extend(child_inlines)

            # Tail text after this child
            if child.tail:
                tail = self._resolve_entities(child.tail)
                parts.append(tail)
                pos += len(tail)

        # If no child elements found, use simple text content
        if not inlines and not parts:
            full_text = XMLHelper.get_text_content(elem)
            if full_text.strip():
                return [ContentBlock.paragraph(full_text.strip())]
            return []

        full_text = "".join(parts).strip()
        if not full_text:
            return []

        block = ContentBlock.paragraph_with_inlines(text=full_text, inlines=inlines)
        return [block]

    def _collect_nested_inlines(
        self,
        elem: ET.Element,
        base_offset: int,
    ) -> list[InlineElement]:
        """
        Walk an element's children to find nested inline elements (e.g., <xref>
        inside <sup>), returning InlineElements with positions relative to
        the paragraph text.

        This is used after a formatting wrapper (bold, sup, etc.) has already
        been tracked — we also need to track any inlines nested within it.
        """
        inlines: list[InlineElement] = []
        inner_pos = 0  # offset within elem's text (relative to elem start)

        # elem.text contributes first
        if elem.text:
            inner_pos += len(elem.text)

        for child in elem:
            tag = self._get_local_tag(child.tag)
            inline_handler = self.INLINE_TAG_MAP.get(tag)

            child_text = self._resolve_entities(XMLHelper.get_text_content(child))

            if inline_handler == "xref" and child_text:
                ref_type = child.get("ref-type", "")
                rid = child.get("rid", "")
                inlines.append(
                    InlineElement(
                        type=InlineElementType.XREF,
                        text=child_text,
                        ref_type=ref_type,
                        target_id=rid,
                        position=base_offset + inner_pos,
                        length=len(child_text),
                    )
                )
                inner_pos += len(child_text)

            elif inline_handler == "inline_formula" and child_text:
                inlines.append(
                    InlineElement(
                        type=InlineElementType.INLINE_FORMULA,
                        text=child_text,
                        position=base_offset + inner_pos,
                        length=len(child_text),
                    )
                )
                inner_pos += len(child_text)

            elif inline_handler == "named_content" and child_text:
                lang = child.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                inlines.append(
                    InlineElement(
                        type=InlineElementType.NAMED_CONTENT,
                        text=child_text,
                        language=lang,
                        position=base_offset + inner_pos,
                        length=len(child_text),
                    )
                )
                inner_pos += len(child_text)

            elif inline_handler in (
                "bold",
                "italic",
                "superscript",
                "subscript",
                "chemical_structure",
                "strikethrough",
                "underline",
                "monospace",
                "small_caps",
                "roman",
                "sans_serif",
                "styled_content",
            ):
                if child_text:
                    ie_type = {
                        "bold": InlineElementType.BOLD,
                        "italic": InlineElementType.ITALIC,
                        "superscript": InlineElementType.SUP,
                        "subscript": InlineElementType.SUB,
                        "chemical_structure": InlineElementType.CHEMICAL_STRUCTURE,
                        "named_content": InlineElementType.NAMED_CONTENT,
                        "strikethrough": InlineElementType.STRIKETHROUGH,
                        "underline": InlineElementType.UNDERLINE,
                        "monospace": InlineElementType.MONOSPACE,
                        "small_caps": InlineElementType.SMALL_CAPS,
                        "roman": InlineElementType.ROMAN,
                        "sans_serif": InlineElementType.SANS_SERIF,
                        "styled_content": InlineElementType.STYLED_CONTENT,
                    }.get(inline_handler, InlineElementType.UNKNOWN_INLINE)
                    inlines.append(
                        InlineElement(
                            type=ie_type,
                            text=child_text,
                            position=base_offset + inner_pos,
                            length=len(child_text),
                        )
                    )
                    # Recurse into this inline wrapper for deeper nesting
                    nested = self._collect_nested_inlines(child, base_offset + inner_pos)
                    inlines.extend(nested)
                    inner_pos += len(child_text)

            else:
                # Unknown child — skip text but recurse
                if child_text:
                    inner_pos += len(child_text)
                inlines.extend(
                    self._collect_nested_inlines(
                        child, base_offset + inner_pos - (len(child_text) if child_text else 0)
                    )
                )

            if child.tail:
                tail_len = len(self._resolve_entities(child.tail))
                inner_pos += tail_len

        return inlines

    def _extract_inlines_recursive(
        self,
        elem: ET.Element,
        pos: int,
        parent_inlines: list[InlineElement] | None = None,
    ) -> tuple[list[str], list[InlineElement], int]:
        """
        Recursively walk an element tree and extract inline elements.

        Used when ``_handle_paragraph`` encounters a block-level element
        (e.g., ``<fig>``) as a child — instead of flattening all descendants
        into an ``UNKNOWN_INLINE``, this tracks nested inlines properly.

        Parameters
        ----------
        elem : ET.Element
            Element to walk recursively.
        pos : int
            Starting character position.
        parent_inlines : list[InlineElement] | None
            Existing inline list for cross-referencing.

        Returns
        -------
        tuple of (parts, inlines, new_pos)
        """
        parts: list[str] = []
        inlines: list[InlineElement] = []

        # Capture elem.text
        if elem.text:
            text = self._resolve_entities(elem.text)
            parts.append(text)
            pos += len(text)

        # Walk children
        for child in elem:
            tag = self._get_local_tag(child.tag)
            inline_handler = self.INLINE_TAG_MAP.get(tag)

            if inline_handler == "xref":
                child_text = self._resolve_entities(XMLHelper.get_text_content(child))
                ref_type = child.get("ref-type", "")
                rid = child.get("rid", "")
                if child_text:
                    parts.append(child_text)
                    inlines.append(
                        InlineElement(
                            type=InlineElementType.XREF,
                            text=child_text,
                            ref_type=ref_type,
                            target_id=rid,
                            position=pos,
                            length=len(child_text),
                        )
                    )
                    # Track nested inlines inside xref (e.g., <sup>1</sup>)
                    nested = self._collect_nested_inlines(child, pos)
                    inlines.extend(nested)
                    pos += len(child_text)

            elif inline_handler == "inline_formula":
                formula_text = self._resolve_entities(XMLHelper.get_text_content(child))
                if formula_text:
                    parts.append(formula_text)
                    inlines.append(
                        InlineElement(
                            type=InlineElementType.INLINE_FORMULA,
                            text=formula_text,
                            position=pos,
                            length=len(formula_text),
                        )
                    )
                    pos += len(formula_text)

            elif inline_handler == "named_content":
                child_text = self._resolve_entities(XMLHelper.get_text_content(child))
                if child_text:
                    parts.append(child_text)
                    lang = child.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                    inlines.append(
                        InlineElement(
                            type=InlineElementType.NAMED_CONTENT,
                            text=child_text,
                            language=lang,
                            position=pos,
                            length=len(child_text),
                        )
                    )
                    nested = self._collect_nested_inlines(child, pos)
                    inlines.extend(nested)
                    pos += len(child_text)

            elif inline_handler in (
                "bold",
                "italic",
                "superscript",
                "subscript",
                "chemical_structure",
                "strikethrough",
                "underline",
                "monospace",
                "small_caps",
                "roman",
                "sans_serif",
                "styled_content",
            ):
                child_text = self._resolve_entities(XMLHelper.get_text_content(child))
                if child_text:
                    parts.append(child_text)
                    ie_type = {
                        "bold": InlineElementType.BOLD,
                        "italic": InlineElementType.ITALIC,
                        "superscript": InlineElementType.SUP,
                        "subscript": InlineElementType.SUB,
                        "chemical_structure": InlineElementType.CHEMICAL_STRUCTURE,
                        "strikethrough": InlineElementType.STRIKETHROUGH,
                        "underline": InlineElementType.UNDERLINE,
                        "monospace": InlineElementType.MONOSPACE,
                        "small_caps": InlineElementType.SMALL_CAPS,
                        "roman": InlineElementType.ROMAN,
                        "sans_serif": InlineElementType.SANS_SERIF,
                        "styled_content": InlineElementType.STYLED_CONTENT,
                    }.get(inline_handler, InlineElementType.UNKNOWN_INLINE)
                    inlines.append(
                        InlineElement(
                            type=ie_type,
                            text=child_text,
                            position=pos,
                            length=len(child_text),
                        )
                    )
                    # Track nested inlines within this wrapper (e.g., <xref> inside <sup>)
                    nested = self._collect_nested_inlines(child, pos)
                    inlines.extend(nested)
                    pos += len(child_text)

            else:
                # Unknown child — recurse into it
                nested_parts, nested_inlines, pos = self._extract_inlines_recursive(
                    child, pos, parent_inlines=inlines
                )
                parts.extend(nested_parts)
                inlines.extend(nested_inlines)

            # Tail text after this child
            if child.tail:
                tail = self._resolve_entities(child.tail)
                parts.append(tail)
                pos += len(tail)

        return parts, inlines, pos

    def _handle_list(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <list> elements with inline-aware item extraction."""
        list_type = elem.get("list-type", "unordered")
        items: list[str] = []
        item_inlines: list[list[dict[str, Any]]] = []
        for item in elem.findall("list-item"):
            parts, inlines, _ = self._extract_inlines_recursive(item, 0)
            text = "".join(parts).strip()
            if text:
                items.append(text)
                if inlines:
                    item_inlines.append([i.to_dict() for i in inlines])
        if items:
            block = ContentBlock.list_block(items=items, list_type=list_type)
            if item_inlines:
                block.metadata = block.metadata or {}
                block.metadata["item_inlines"] = item_inlines
            return [block]
        return []

    def _handle_def_list(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <def-list> elements with inline-aware term/def extraction."""
        terms: list[dict[str, str]] = []
        for def_item in elem.findall("def-item"):
            term_elems = def_item.findall("term")
            def_elems = def_item.findall("def")
            term_text = ""
            if term_elems:
                term_parts, _, _ = self._extract_inlines_recursive(term_elems[0], 0)
                term_text = "".join(term_parts).strip()
            def_text = ""
            if def_elems:
                def_parts, _, _ = self._extract_inlines_recursive(def_elems[0], 0)
                def_text = "".join(def_parts).strip()
            if term_text or def_text:
                terms.append({"term": term_text, "def": def_text})
        if terms:
            return [ContentBlock.definition_list(terms=terms)]
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
        """Handle <fig> elements with inline-aware caption extraction."""
        fig_id = elem.get("id", "")

        label = ""
        label_elem = elem.find("label")
        if label_elem is not None:
            label = XMLHelper.get_text_content(label_elem)

        # Inline-aware caption: walk caption children for inline elements
        caption = ""
        caption_inlines: list[InlineElement] = []
        caption_elem = elem.find("caption")
        if caption_elem is not None:
            # Use recursive extraction for inline tracking within caption
            cap_parts, cap_inlines, _ = self._extract_inlines_recursive(caption_elem, 0)
            if cap_parts:
                caption = "".join(cap_parts).strip()
                caption_inlines = cap_inlines
            else:
                caption = XMLHelper.get_text_content(caption_elem)

        uri = ""
        graphic = elem.find(".//graphic")
        if graphic is not None:
            uri = str(
                graphic.get("{http://www.w3.org/1999/xlink}href", "") or graphic.get("href", "")
            )

        block = ContentBlock.figure(
            label=label,
            caption=caption,
            uri=uri,
            target_id=fig_id,
        )
        if caption_inlines:
            block.inlines = caption_inlines
        return [block]

    def _extract_table_rows(
        self, elem: ET.Element
    ) -> tuple[list[list[str]], list[list[list[dict[str, Any]]]]]:
        """Extract cell rows and inlines from a table element."""
        rows: list[list[str]] = []
        cell_inlines: list[list[list[dict[str, Any]]]] = []
        for tbody in elem.iter():
            if self._get_local_tag(tbody.tag) in ("tbody", "thead"):
                for tr in tbody:
                    if self._get_local_tag(tr.tag) != "tr":
                        continue
                    row_cells: list[str] = []
                    row_inlines: list[list[dict[str, Any]]] = []
                    for cell in tr:
                        tag = self._get_local_tag(cell.tag)
                        if tag in ("td", "th"):
                            cell_parts, cell_ils, _ = self._extract_inlines_recursive(cell, 0)
                            cell_text = "".join(cell_parts).strip()
                            if not cell_text:
                                cell_text = XMLHelper.get_text_content(cell).strip()
                            row_cells.append(cell_text)
                            if cell_ils:
                                row_inlines.append([i.to_dict() for i in cell_ils])
                    if row_cells:
                        rows.append(row_cells)
                        if row_inlines:
                            cell_inlines.append(row_inlines)
        return rows, cell_inlines

    def _handle_table(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <table-wrap> and <table> elements with cell structure."""
        label = ""
        label_elem = elem.find("label")
        if label_elem is not None:
            label = XMLHelper.get_text_content(label_elem)

        caption = ""
        caption_elem = elem.find("caption")
        if caption_elem is not None:
            caption = XMLHelper.get_text_content(caption_elem)

        text = XMLHelper.get_text_content(elem).strip()

        rows, cell_inlines = self._extract_table_rows(elem)

        block = ContentBlock.table_block(label=label, caption=caption, text=text, rows=rows)
        if cell_inlines:
            block.metadata = block.metadata or {}
            block.metadata["cell_inlines"] = cell_inlines
            all_cell_inlines: list[InlineElement] = []
            for row in cell_inlines:
                for cell_inline_list in row:
                    if isinstance(cell_inline_list, list):
                        for cell_inline_dict in cell_inline_list:
                            if isinstance(cell_inline_dict, dict):
                                all_cell_inlines.append(
                                    InlineElement(
                                        type=InlineElementType(
                                            cell_inline_dict.get("type", "unknown_inline")
                                        ),
                                        text=cell_inline_dict.get("text", ""),
                                        position=cell_inline_dict.get("position", 0),
                                        length=cell_inline_dict.get("length", 0),
                                    )
                                )
            block.inlines = all_cell_inlines
        return [block]

    def _handle_code(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <code> and <preformat> elements."""
        language = elem.get("language", elem.get("lang", ""))
        text = XMLHelper.get_text_content(elem)
        if text.strip():
            return [ContentBlock.code(text=text.strip(), language=language)]
        return []

    def _handle_media(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle ``<media>`` elements with inline-aware caption extraction."""
        # Determine MIME type
        mime = elem.get("mimetype", "")
        mime_subtype = elem.get("mime-subtype", "")
        full_mime = f"{mime}/{mime_subtype}" if mime and mime_subtype else mime

        # Extract caption and label
        label = ""
        label_elem = elem.find("label")
        if label_elem is not None:
            label = XMLHelper.get_text_content(label_elem)

        caption_inlines: list[InlineElement] = []
        caption = ""
        caption_elem = elem.find("caption")
        if caption_elem is not None:
            caption_parts, caption_inlines_dicts, _ = self._extract_inlines_recursive(
                caption_elem, 0
            )
            caption = "".join(caption_parts).strip()
            caption_inlines = caption_inlines_dicts
        else:
            caption = XMLHelper.get_text_content(elem).strip()[:200]

        # Extract text description
        text = XMLHelper.get_text_content(elem).strip()

        # Get URI from the element
        uri = ""
        xlink_href = self._get_xlink_href(elem)
        if xlink_href:
            uri = xlink_href

        if not text and not caption and not uri:
            return []

        meta: dict[str, str] = {}
        if full_mime:
            meta["mime_type"] = full_mime
        if uri:
            meta["uri"] = uri

        return [
            ContentBlock(
                type=ContentBlockType.FIGURE,
                label=label,
                caption=caption or text[:200],
                uri=uri,
                metadata=meta,
                inlines=caption_inlines,
            )
        ]

    def _handle_boxed_text(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle <boxed-text> elements with inline-aware text extraction."""
        parts, inlines, _ = self._extract_inlines_recursive(elem, 0)
        text = "".join(parts).strip()
        if text:
            block = ContentBlock(text=text, type=ContentBlockType.UNKNOWN_BLOCK)
            if inlines:
                block.inlines = inlines
            return [block]
        text = XMLHelper.get_text_content(elem).strip()
        if text:
            return [ContentBlock(text=text, type=ContentBlockType.UNKNOWN_BLOCK)]
        return []

    def _handle_quote(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle ``<disp-quote>`` elements as QUOTE blocks with inline tracking."""
        parts, inlines, _ = self._extract_inlines_recursive(elem, 0)
        text = "".join(parts).strip()
        if text:
            return [ContentBlock.quote(text=text, inlines=inlines)]
        text = XMLHelper.get_text_content(elem).strip()
        if text:
            return [ContentBlock.quote(text=text)]
        return []

    def _handle_subsection(self, elem: ET.Element) -> list[ContentBlock]:
        """Handle nested <sec> elements as flat heading + content.

        Note: Main body extraction uses ``_extract_structured_section``
        which recursively handles nested ``<sec>`` with section paths.
        This method is still used for appendix extraction and other
        contexts that need flat block output.
        """
        blocks: list[ContentBlock] = []

        title_elem = elem.find("title")
        title = self._get_multipart_title(title_elem)
        if title:
            blocks.append(ContentBlock.heading(title))

        # Recurse into subsection children
        for child in elem:
            tag = self._get_local_tag(child.tag)
            if tag == "title":
                continue
            handler_name = self.JATS_BLOCK_TAGS.get(tag)
            if handler_name and handler_name in self._handler_map:
                blocks.extend(self._handler_map[handler_name](child))

        return blocks

    def _extract_article_title(self) -> StructuredSection | None:
        """Extract the article title from front matter as a structured section.

        Creates a section with the article title as a heading block,
        providing inline tracking for any formatted elements in the title.
        """
        if self.root is None:
            return None
        for title_group in self.root.findall(".//title-group"):
            title_el = title_group.find("article-title")
            if title_el is not None:
                title_text = "".join(title_el.itertext()).strip()
                if title_text:
                    # Check for inlines in the title
                    inlines: list[InlineElement] = []
                    pos = 0
                    parts: list[str] = []
                    self._walk_inline_children(title_el, parts, inlines, pos)
                    # Only produce heading if title non-empty
                    if title_text:
                        if inlines:
                            block = ContentBlock.paragraph_with_inlines(
                                text=title_text, inlines=inlines
                            )
                        else:
                            block = ContentBlock.heading(title_text)
                        return StructuredSection(
                            title="Article Title",
                            content=[block],
                            section_type="body",
                            section_path="Article Title",
                        )
        return None

    def _walk_inline_children(
        self,
        elem: ET.Element,
        parts: list[str],
        inlines: list[InlineElement],
        pos: int,
    ) -> None:
        """Walk element children to collect text parts and inline elements.

        Used for inline tracking in titles and other non-paragraph contexts.
        """
        # elem.text before first child
        if elem.text:
            parts.append(elem.text)
            pos += len(elem.text)
        for child in elem:
            tag = self._get_local_tag(child.tag)
            inline_type = self.INLINE_TAG_MAP.get(tag)
            child_text = "".join(child.itertext())
            if child_text and inline_type:
                try:
                    ie_type = InlineElementType(inline_type)
                except ValueError:
                    ie_type = InlineElementType.UNKNOWN_INLINE
                inlines.append(
                    InlineElement(
                        type=ie_type,
                        text=child_text,
                        position=pos,
                        length=len(child_text),
                    )
                )
                parts.append(child_text)
                pos += len(child_text)
            elif child_text:
                parts.append(child_text)
                pos += len(child_text)
            # tail text
            if child.tail:
                parts.append(child.tail)
                pos += len(child.tail)

    def _extract_abstract(self) -> StructuredSection | None:
        """Extract abstract from front matter as a structured section."""
        if self.root is None:
            return None
        for abstract in self.root.findall(".//abstract"):
            # Get the title (usually "Abstract" or a structured sub-title)
            title = "Abstract"
            titled = abstract.find("title")
            if titled is not None:
                title = self._get_multipart_title(titled)

            # Extract inlines from all paragraph children
            blocks: list[ContentBlock] = []
            for child in abstract:
                tag = self._get_local_tag(child.tag)
                if tag == "p":
                    # Use _handle_paragraph-like logic
                    text, inlines, _ = self._extract_inlines_recursive(child, 0)
                    joined = "".join(text).strip()
                    if joined:
                        if inlines:
                            blocks.append(
                                ContentBlock.paragraph_with_inlines(text=joined, inlines=inlines)
                            )
                        else:
                            blocks.append(ContentBlock.paragraph(joined))
                elif tag == "sec":
                    # Structured abstract with sub-sections
                    sub_title = ""
                    st = child.find("title")
                    if st is not None:
                        sub_title = self._get_multipart_title(st)
                    for p in child.findall("p"):
                        text, inlines, _ = self._extract_inlines_recursive(p, 0)
                        joined = "".join(text).strip()
                        if joined:
                            prefix = f"{sub_title}: " if sub_title else ""
                            blocks.append(ContentBlock.paragraph(f"{prefix}{joined}"))

            if blocks:
                return StructuredSection(
                    title=title,
                    content=blocks,
                    section_type="body",
                    section_path=title,
                )
        return None

    def _extract_footnotes(self) -> list[StructuredSection]:
        """Extract footnotes (fn-group) from back matter only.

        Fn-groups inside ``<body>`` sections are already extracted by
        ``_extract_structured_section``.  This method only processes
        fn-groups that live outside ``<body>`` (typically in ``<back>``).
        """
        fn_sections: list[StructuredSection] = []
        if self.root is None:
            return fn_sections

        for fn_group in self.root.findall(".//fn-group"):
            # Skip fn-groups that are inside <body> — they are handled
            # by the section extraction (avoid double-counting).
            if self._is_inside_body(fn_group):
                continue
            fn_blocks: list[ContentBlock] = []
            for fn in fn_group.findall("fn"):
                _fn_id = fn.get("id", "")
                fn_label = ""
                label_elem = fn.find("label")
                if label_elem is not None:
                    fn_label = XMLHelper.get_text_content(label_elem)

                text, inlines, _ = self._extract_inlines_recursive(fn, 0)
                joined = "".join(text).strip()
                if joined:
                    prefix = f"{fn_label} " if fn_label else ""
                    full_text = f"{prefix}{joined}"
                    if inlines:
                        fn_blocks.append(
                            ContentBlock.paragraph_with_inlines(text=full_text, inlines=inlines)
                        )
                    else:
                        fn_blocks.append(ContentBlock.paragraph(full_text))

            if fn_blocks:
                fn_sections.append(
                    StructuredSection(
                        title="Footnotes",
                        content=fn_blocks,
                        section_type="back",
                        section_path="Footnotes",
                    )
                )
        return fn_sections

    def _extract_reference_sections(self) -> list[StructuredSection]:
        """Extract references (ref-list) from back matter."""
        structures: list[StructuredSection] = []
        if self.root is None:
            return structures

        for ref_list in self.root.findall(".//ref-list"):
            title = ""
            title_elem = ref_list.find("title")
            if title_elem is not None:
                title = XMLHelper.get_text_content(title_elem)

            ref_blocks: list[ContentBlock] = []
            for ref in ref_list.findall("ref"):
                _ref_id = ref.get("id", "")
                ref_label = ""
                label_elem = ref.find("label")
                if label_elem is not None:
                    ref_label = XMLHelper.get_text_content(label_elem)

                ref_parts, ref_inlines, _ = self._extract_inlines_recursive(ref, 0)
                ref_text = "".join(ref_parts).strip()

                if ref_label:
                    ref_text = f"{ref_label} {ref_text}"
                if ref_text:
                    if ref_inlines:
                        ref_blocks.append(
                            ContentBlock.paragraph_with_inlines(text=ref_text, inlines=ref_inlines)
                        )
                    else:
                        ref_blocks.append(ContentBlock.paragraph(ref_text))

            if ref_blocks:
                structures.append(
                    StructuredSection(
                        title=title or "References",
                        content=ref_blocks,
                        section_type="back",
                        section_path=title or "References",
                    )
                )
        return structures

    def _extract_acknowledgment_sections(self) -> list[StructuredSection]:
        """Extract acknowledgments from back matter."""
        structures: list[StructuredSection] = []
        if self.root is None:
            return structures

        for ack in self.root.findall(".//ack"):
            text = XMLHelper.get_text_content(ack)
            if text.strip():
                structures.append(
                    StructuredSection(
                        title="Acknowledgments",
                        content=[ContentBlock.paragraph(text.strip())],
                        section_type="back",
                        section_path="Acknowledgments",
                    )
                )
        return structures

    def _extract_appendix_sections(self) -> list[StructuredSection]:
        """Extract appendices from back matter."""
        structures: list[StructuredSection] = []
        if self.root is None:
            return structures

        for app in self.root.findall(".//app"):
            title_elem = app.find("title")
            title = self._get_multipart_title(title_elem)
            blocks = self._extract_appendix_blocks(app)
            structures.append(
                StructuredSection(
                    title=title or "Appendix",
                    content=blocks,
                    section_type="appendix",
                )
            )
        return structures

    def _extract_glossary_sections(self) -> list[StructuredSection]:
        """Extract glossary from back matter."""
        structures: list[StructuredSection] = []
        if self.root is None:
            return structures

        for gloss in self.root.findall(".//glossary"):
            title_elem = gloss.find("title")
            title = self._get_multipart_title(title_elem)
            text = XMLHelper.get_text_content(gloss)
            structures.append(
                StructuredSection(
                    title=title or "Glossary",
                    content=([ContentBlock.paragraph(text.strip())] if text.strip() else []),
                    section_type="back",
                    section_path=title or "Glossary",
                )
            )
        return structures

    def _extract_notes_sections(self) -> list[StructuredSection]:
        """Extract notes from back matter."""
        structures: list[StructuredSection] = []
        if self.root is None:
            return structures

        for notes_elem in self.root.findall(".//notes"):
            title_elem = notes_elem.find("title")
            title = self._get_multipart_title(title_elem)
            note_blocks: list[ContentBlock] = []
            for child in notes_elem:
                tag = self._get_local_tag(child.tag)
                if tag == "title":
                    continue
                handler_name = self.JATS_BLOCK_TAGS.get(tag)
                if handler_name and handler_name in self._handler_map:
                    note_blocks.extend(self._handler_map[handler_name](child))
                elif tag not in ("label",):
                    text = XMLHelper.get_text_content(child)
                    if text.strip():
                        note_blocks.append(ContentBlock.paragraph(text.strip()))
            if note_blocks:
                structures.append(
                    StructuredSection(
                        title=title or "Notes",
                        content=note_blocks,
                        section_type="back",
                        section_path=title or "Notes",
                    )
                )
        return structures

    def _extract_additional_structures(self) -> list[StructuredSection]:
        """Extract back-matter structures (references, acknowledgments, appendices, glossary)."""
        structures: list[StructuredSection] = []
        structures.extend(self._extract_reference_sections())
        structures.extend(self._extract_acknowledgment_sections())
        structures.extend(self._extract_appendix_sections())
        structures.extend(self._extract_glossary_sections())
        structures.extend(self._extract_notes_sections())
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

    def _is_inside_body(self, elem: ET.Element) -> bool:
        """Check whether *elem* is a descendant of a ``<body>`` element."""
        if self.root is None:
            return False
        for body in self.root.findall(".//body"):
            for desc in body.iter():
                if desc is elem:
                    return True
        return False

    @staticmethod
    def _get_local_tag(tag: str) -> str:
        """Strip namespace from a tag name."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _get_xlink_href(elem: ET.Element) -> str:
        """Get the xlink:href attribute from an element."""
        return elem.get("{http://www.w3.org/1999/xlink}href") or elem.get("href") or ""

    @staticmethod
    def _get_namespace_map() -> dict[str, str]:
        """Get namespace map for common XML namespaces."""
        return {
            "mml": "http://www.w3.org/1998/Math/MathML",
            "xlink": "http://www.w3.org/1999/xlink",
        }

    @staticmethod
    def _resolve_entities(text: str) -> str:
        """Resolve common HTML/XML entities in text content."""
        entities = {
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&apos;": "'",
            "&nbsp;": " ",
            "&ndash;": "–",
            "&mdash;": "—",
            "&hellip;": "…",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        return text

    @staticmethod
    def _convert_inline_formula(elem: ET.Element) -> str:
        """Attempt to extract LaTeX from an inline formula element."""
        # Try MathML first
        mathml_elem = elem.find(".//mml:math", {"mml": "http://www.w3.org/1998/Math/MathML"})
        if mathml_elem is not None:
            with contextlib.suppress(ImportError, Exception):
                from pyeuropepmc.processing.extensions.mathml import MathMLConverter

                converter = MathMLConverter(inline=True)
                return converter.convert_to_latex(mathml_elem)

        # Fallback: extract plain text
        return XMLHelper.get_text_content(mathml_elem) if mathml_elem is not None else ""
