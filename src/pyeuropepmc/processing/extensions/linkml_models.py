# ruff: noqa: E501, UP045, UP007
# mypy: ignore-errors
# Auto generated from article_content_schema.yaml by pythongen.py version: 0.0.1
# Generation date: 2026-06-17T14:08:08
# Schema: pyeuropepmc-article-content
#
# id: https://github.com/JonasHeinickeBio/pyEuropePMC/schemas/linkml/article_content
# description: LinkML schema for structured article content extracted from Europe PMC JATS XML.
#
#   Defines the ContentBlock model (typed content blocks preserving document structure)
#   and StructuredSection for RAG/LLM-ready article representation.
#
#   This schema integrates with the biomedical-knowledge-lookup annotation pipeline:
#   - ContentBlock.text provides the text for sentence-level annotation
#   - StructuredSection preserves the document context for annotations
#   - ArticleContent ties everything together with metadata
#
#   Based on JATS4R recommendations and pmcgrab content block approach.
#
# license:

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Optional, Union

from jsonasobj2 import as_dict
from linkml_runtime.linkml_model.meta import EnumDefinition, PermissibleValue
from linkml_runtime.utils.curienamespace import CurieNamespace
from linkml_runtime.utils.enumerations import EnumDefinitionImpl
from linkml_runtime.utils.metamodelcore import empty_list
from linkml_runtime.utils.slot import Slot
from linkml_runtime.utils.yamlutils import YAMLRoot, extended_str
from rdflib import URIRef

metamodel_version = "1.7.0"
version = None

# Namespaces
LINKML = CurieNamespace("linkml", "https://w3id.org/linkml/")
PCM = CurieNamespace("pcm", "https://github.com/JonasHeinickeBio/pyEuropePMC/schemas/linkml/")
XSD = CurieNamespace("xsd", "http://www.w3.org/2001/XMLSchema#")
DEFAULT_ = PCM


# Types
class String(str):
    type_class_uri = XSD["string"]
    type_class_curie = "xsd:string"
    type_name = "string"
    type_model_uri = PCM.String


class Integer(int):
    type_class_uri = XSD["integer"]
    type_class_curie = "xsd:integer"
    type_name = "integer"
    type_model_uri = PCM.Integer


class Float(float):
    type_class_uri = XSD["float"]
    type_class_curie = "xsd:float"
    type_name = "float"
    type_model_uri = PCM.Float


class Boolean(int):
    """Boolean type - inherits from int for compat, validates truthiness."""

    type_class_uri = XSD["boolean"]
    type_class_curie = "xsd:boolean"
    type_name = "boolean"
    type_model_uri = PCM.Boolean

    def __new__(cls, value):
        return super().__new__(cls, 1 if value else 0)


class Datetime(datetime):
    type_class_uri = XSD["dateTime"]
    type_class_curie = "xsd:dateTime"
    type_name = "datetime"
    type_model_uri = PCM.Datetime


class Uri(str):
    type_class_uri = XSD["anyURI"]
    type_class_curie = "xsd:anyURI"
    type_name = "uri"
    type_model_uri = PCM.Uri


class JsonString(str):
    """JSON-serialized string for complex nested data"""

    type_class_uri = XSD["string"]
    type_class_curie = "xsd:string"
    type_name = "json_string"
    type_model_uri = PCM.JsonString


# Class references
class ArticleContentArticleId(extended_str):
    pass


@dataclass(repr=False)
class ContentBlock(YAMLRoot):
    """
    A single typed content block within a document section. Each block carries a type identifier and type-specific
    fields. Unknown JATS blocks are preserved as unknown_block instead of dropped.
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = PCM["ContentBlock"]
    class_class_curie: ClassVar[str] = "pcm:ContentBlock"
    class_name: ClassVar[str] = "ContentBlock"
    class_model_uri: ClassVar[URIRef] = PCM.ContentBlock

    type: Union[str, "ContentBlockType"] = None
    text: str | None = None
    items: str | list[str] | None = empty_list()
    list_type: Union[str, "ListStyle"] | None = None
    label: str | None = None
    target_id: str | None = None
    language: str | None = None
    tex: str | None = None
    mathml: str | None = None
    caption: str | None = None
    uri: str | None = None
    jats_tag: str | None = None
    metadata: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.type):
            self.MissingRequiredField("type")
        if not isinstance(self.type, ContentBlockType):
            self.type = ContentBlockType(self.type)

        if self.text is not None and not isinstance(self.text, str):
            self.text = str(self.text)

        if not isinstance(self.items, list):
            self.items = [self.items] if self.items is not None else []
        self.items = [v if isinstance(v, str) else str(v) for v in self.items]

        if self.list_type is not None and not isinstance(self.list_type, ListStyle):
            self.list_type = ListStyle(self.list_type)

        if self.label is not None and not isinstance(self.label, str):
            self.label = str(self.label)

        if self.target_id is not None and not isinstance(self.target_id, str):
            self.target_id = str(self.target_id)

        if self.language is not None and not isinstance(self.language, str):
            self.language = str(self.language)

        if self.tex is not None and not isinstance(self.tex, str):
            self.tex = str(self.tex)

        if self.mathml is not None and not isinstance(self.mathml, str):
            self.mathml = str(self.mathml)

        if self.caption is not None and not isinstance(self.caption, str):
            self.caption = str(self.caption)

        if self.uri is not None and not isinstance(self.uri, str):
            self.uri = str(self.uri)

        if self.jats_tag is not None and not isinstance(self.jats_tag, str):
            self.jats_tag = str(self.jats_tag)

        if self.metadata is not None and not isinstance(self.metadata, str):
            self.metadata = str(self.metadata)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class StructuredSection(YAMLRoot):
    """
    A document section containing ordered typed content blocks. Preserves the document structure for RAG/LLM pipelines.
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = PCM["StructuredSection"]
    class_class_curie: ClassVar[str] = "pcm:StructuredSection"
    class_name: ClassVar[str] = "StructuredSection"
    class_model_uri: ClassVar[URIRef] = PCM.StructuredSection

    title: str = None
    content: dict | ContentBlock | list[dict | ContentBlock] = None
    section_type: Union[str, "SectionType"] | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self._is_empty(self.content):
            self.MissingRequiredField("content")
        self._normalize_inlined_as_list(
            slot_name="content", slot_type=ContentBlock, key_name="type", keyed=False
        )

        if self.section_type is not None and not isinstance(self.section_type, SectionType):
            self.section_type = SectionType(self.section_type)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class ArticleMetadata(YAMLRoot):
    """
    Key metadata extracted from the article XML.
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = PCM["ArticleMetadata"]
    class_class_curie: ClassVar[str] = "pcm:ArticleMetadata"
    class_name: ClassVar[str] = "ArticleMetadata"
    class_model_uri: ClassVar[URIRef] = PCM.ArticleMetadata

    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str | None = None
    journal: str | None = None
    publication_year: int | None = None
    authors: str | list[str] | None = empty_list()
    keywords: str | list[str] | None = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.pmid is not None and not isinstance(self.pmid, str):
            self.pmid = str(self.pmid)

        if self.pmcid is not None and not isinstance(self.pmcid, str):
            self.pmcid = str(self.pmcid)

        if self.doi is not None and not isinstance(self.doi, str):
            self.doi = str(self.doi)

        if self.title is not None and not isinstance(self.title, str):
            self.title = str(self.title)

        if self.journal is not None and not isinstance(self.journal, str):
            self.journal = str(self.journal)

        if self.publication_year is not None and not isinstance(self.publication_year, int):
            self.publication_year = int(self.publication_year)

        if not isinstance(self.authors, list):
            self.authors = [self.authors] if self.authors is not None else []
        self.authors = [v if isinstance(v, str) else str(v) for v in self.authors]

        if not isinstance(self.keywords, list):
            self.keywords = [self.keywords] if self.keywords is not None else []
        self.keywords = [v if isinstance(v, str) else str(v) for v in self.keywords]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class ArticleContent(YAMLRoot):
    """
    Complete structured representation of a Europe PMC article with typed content blocks. This is the top-level
    container that ties metadata, structured sections, and assets together.
    Designed to integrate with the biomedical-knowledge-lookup annotation pipeline where ContentBlock.text values are
    fed into MultiSourceAnnotationResult for concept detection.
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = PCM["ArticleContent"]
    class_class_curie: ClassVar[str] = "pcm:ArticleContent"
    class_name: ClassVar[str] = "ArticleContent"
    class_model_uri: ClassVar[URIRef] = PCM.ArticleContent

    article_id: str | ArticleContentArticleId = None
    metadata: dict | ArticleMetadata | None = None
    sections: dict | StructuredSection | list[dict | StructuredSection] | None = empty_list()
    assets: Union[dict, "AssetRef"] | list[Union[dict, "AssetRef"]] | None = empty_list()
    peer_reviews: Union[dict, "PeerReview"] | list[Union[dict, "PeerReview"]] | None = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.article_id):
            self.MissingRequiredField("article_id")
        if not isinstance(self.article_id, ArticleContentArticleId):
            self.article_id = ArticleContentArticleId(self.article_id)

        if self.metadata is not None and not isinstance(self.metadata, ArticleMetadata):
            self.metadata = ArticleMetadata(**as_dict(self.metadata))

        self._normalize_inlined_as_list(
            slot_name="sections", slot_type=StructuredSection, key_name="title", keyed=False
        )

        self._normalize_inlined_as_list(
            slot_name="assets", slot_type=AssetRef, key_name="asset_type", keyed=False
        )

        self._normalize_inlined_as_list(
            slot_name="peer_reviews", slot_type=PeerReview, key_name="review_type", keyed=False
        )

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class AssetRef(YAMLRoot):
    """
    Reference to an external asset (figure, supplementary material).
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = PCM["AssetRef"]
    class_class_curie: ClassVar[str] = "pcm:AssetRef"
    class_name: ClassVar[str] = "AssetRef"
    class_model_uri: ClassVar[URIRef] = PCM.AssetRef

    asset_type: str = None
    uri: str | None = None
    label: str | None = None
    caption: str | None = None
    mime_type: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.asset_type):
            self.MissingRequiredField("asset_type")
        if not isinstance(self.asset_type, str):
            self.asset_type = str(self.asset_type)

        if self.uri is not None and not isinstance(self.uri, str):
            self.uri = str(self.uri)

        if self.label is not None and not isinstance(self.label, str):
            self.label = str(self.label)

        if self.caption is not None and not isinstance(self.caption, str):
            self.caption = str(self.caption)

        if self.mime_type is not None and not isinstance(self.mime_type, str):
            self.mime_type = str(self.mime_type)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class PeerReview(YAMLRoot):
    """
    A single peer review item extracted from sub-articles.
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = PCM["PeerReview"]
    class_class_curie: ClassVar[str] = "pcm:PeerReview"
    class_name: ClassVar[str] = "PeerReview"
    class_model_uri: ClassVar[URIRef] = PCM.PeerReview

    review_type: str = None
    title: str | None = None
    contributors: str | None = None
    revision_round: int | None = None
    sections: dict | StructuredSection | list[dict | StructuredSection] | None = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.review_type):
            self.MissingRequiredField("review_type")
        if not isinstance(self.review_type, str):
            self.review_type = str(self.review_type)

        if self.title is not None and not isinstance(self.title, str):
            self.title = str(self.title)

        if self.contributors is not None and not isinstance(self.contributors, str):
            self.contributors = str(self.contributors)

        if self.revision_round is not None and not isinstance(self.revision_round, int):
            self.revision_round = int(self.revision_round)

        self._normalize_inlined_as_list(
            slot_name="sections", slot_type=StructuredSection, key_name="title", keyed=False
        )

        super().__post_init__(**kwargs)


# Enumerations
class ContentBlockType(EnumDefinitionImpl):
    """
    Semantic type of a content block. Preserves the original JATS element type so downstream consumers can handle each
    block appropriately.
    """

    paragraph = PermissibleValue(text="paragraph", description="A plain text paragraph (<p>)")
    heading = PermissibleValue(text="heading", description="A section/subsection heading")
    list = PermissibleValue(text="list", description="An ordered or unordered list (<list>)")
    formula = PermissibleValue(
        text="formula",
        description="A mathematical formula/equation (<disp-formula>, <inline-formula>)",
    )
    figure_ref = PermissibleValue(
        text="figure_ref", description="A reference/citation to a figure"
    )
    table_ref = PermissibleValue(text="table_ref", description="A reference/citation to a table")
    code = PermissibleValue(
        text="code", description="A code/preformatted block (<code>, <preformat>)"
    )
    boxed_text = PermissibleValue(
        text="boxed_text", description="A boxed/highlighted text block (<boxed-text>)"
    )
    figure = PermissibleValue(
        text="figure", description="A figure with caption and graphic URI (<fig>)"
    )
    table = PermissibleValue(text="table", description="A table with caption (<table-wrap>)")
    mathml = PermissibleValue(text="mathml", description="A MathML expression")
    peer_review = PermissibleValue(
        text="peer_review", description="Peer review content from sub-articles"
    )
    unknown_block = PermissibleValue(
        text="unknown_block", description="An unrecognized JATS element preserved as-is"
    )

    _defn = EnumDefinition(
        name="ContentBlockType",
        description="""Semantic type of a content block. Preserves the original JATS element type so downstream consumers can handle each block appropriately.""",
    )


class SectionType(EnumDefinitionImpl):
    """
    Structural type of a document section.
    """

    body = PermissibleValue(text="body", description="Main article body section")
    back = PermissibleValue(text="back", description="Back matter (acknowledgments, glossary)")
    appendix = PermissibleValue(
        text="appendix", description="Appendix/Supplementary material section"
    )
    peer_review = PermissibleValue(
        text="peer_review", description="Peer review sub-article section"
    )

    _defn = EnumDefinition(
        name="SectionType",
        description="Structural type of a document section.",
    )


class ListStyle(EnumDefinitionImpl):
    """
    Style of a list block.
    """

    ordered = PermissibleValue(text="ordered", description="Numbered list")
    unordered = PermissibleValue(text="unordered", description="Bullet list")
    simple = PermissibleValue(text="simple", description="Simple list without markers")

    _defn = EnumDefinition(
        name="ListStyle",
        description="Style of a list block.",
    )


# Slots
class slots:
    pass


slots.contentBlock__type = Slot(
    uri=PCM.type,
    name="contentBlock__type",
    curie=PCM.curie("type"),
    model_uri=PCM.contentBlock__type,
    domain=None,
    range=Union[str, "ContentBlockType"],
)

slots.contentBlock__text = Slot(
    uri=PCM.text,
    name="contentBlock__text",
    curie=PCM.curie("text"),
    model_uri=PCM.contentBlock__text,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__items = Slot(
    uri=PCM.items,
    name="contentBlock__items",
    curie=PCM.curie("items"),
    model_uri=PCM.contentBlock__items,
    domain=None,
    range=Optional[str | list[str]],
)

slots.contentBlock__list_type = Slot(
    uri=PCM.list_type,
    name="contentBlock__list_type",
    curie=PCM.curie("list_type"),
    model_uri=PCM.contentBlock__list_type,
    domain=None,
    range=Optional[Union[str, "ListStyle"]],
)

slots.contentBlock__label = Slot(
    uri=PCM.label,
    name="contentBlock__label",
    curie=PCM.curie("label"),
    model_uri=PCM.contentBlock__label,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__target_id = Slot(
    uri=PCM.target_id,
    name="contentBlock__target_id",
    curie=PCM.curie("target_id"),
    model_uri=PCM.contentBlock__target_id,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__language = Slot(
    uri=PCM.language,
    name="contentBlock__language",
    curie=PCM.curie("language"),
    model_uri=PCM.contentBlock__language,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__tex = Slot(
    uri=PCM.tex,
    name="contentBlock__tex",
    curie=PCM.curie("tex"),
    model_uri=PCM.contentBlock__tex,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__mathml = Slot(
    uri=PCM.mathml,
    name="contentBlock__mathml",
    curie=PCM.curie("mathml"),
    model_uri=PCM.contentBlock__mathml,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__caption = Slot(
    uri=PCM.caption,
    name="contentBlock__caption",
    curie=PCM.curie("caption"),
    model_uri=PCM.contentBlock__caption,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__uri = Slot(
    uri=PCM.uri,
    name="contentBlock__uri",
    curie=PCM.curie("uri"),
    model_uri=PCM.contentBlock__uri,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__jats_tag = Slot(
    uri=PCM.jats_tag,
    name="contentBlock__jats_tag",
    curie=PCM.curie("jats_tag"),
    model_uri=PCM.contentBlock__jats_tag,
    domain=None,
    range=Optional[str],
)

slots.contentBlock__metadata = Slot(
    uri=PCM.metadata,
    name="contentBlock__metadata",
    curie=PCM.curie("metadata"),
    model_uri=PCM.contentBlock__metadata,
    domain=None,
    range=Optional[str],
)

slots.structuredSection__title = Slot(
    uri=PCM.title,
    name="structuredSection__title",
    curie=PCM.curie("title"),
    model_uri=PCM.structuredSection__title,
    domain=None,
    range=str,
)

slots.structuredSection__content = Slot(
    uri=PCM.content,
    name="structuredSection__content",
    curie=PCM.curie("content"),
    model_uri=PCM.structuredSection__content,
    domain=None,
    range=Union[dict | ContentBlock, list[dict | ContentBlock]],
)

slots.structuredSection__section_type = Slot(
    uri=PCM.section_type,
    name="structuredSection__section_type",
    curie=PCM.curie("section_type"),
    model_uri=PCM.structuredSection__section_type,
    domain=None,
    range=Optional[Union[str, "SectionType"]],
)

slots.articleMetadata__pmid = Slot(
    uri=PCM.pmid,
    name="articleMetadata__pmid",
    curie=PCM.curie("pmid"),
    model_uri=PCM.articleMetadata__pmid,
    domain=None,
    range=Optional[str],
)

slots.articleMetadata__pmcid = Slot(
    uri=PCM.pmcid,
    name="articleMetadata__pmcid",
    curie=PCM.curie("pmcid"),
    model_uri=PCM.articleMetadata__pmcid,
    domain=None,
    range=Optional[str],
)

slots.articleMetadata__doi = Slot(
    uri=PCM.doi,
    name="articleMetadata__doi",
    curie=PCM.curie("doi"),
    model_uri=PCM.articleMetadata__doi,
    domain=None,
    range=Optional[str],
)

slots.articleMetadata__title = Slot(
    uri=PCM.title,
    name="articleMetadata__title",
    curie=PCM.curie("title"),
    model_uri=PCM.articleMetadata__title,
    domain=None,
    range=Optional[str],
)

slots.articleMetadata__journal = Slot(
    uri=PCM.journal,
    name="articleMetadata__journal",
    curie=PCM.curie("journal"),
    model_uri=PCM.articleMetadata__journal,
    domain=None,
    range=Optional[str],
)

slots.articleMetadata__publication_year = Slot(
    uri=PCM.publication_year,
    name="articleMetadata__publication_year",
    curie=PCM.curie("publication_year"),
    model_uri=PCM.articleMetadata__publication_year,
    domain=None,
    range=Optional[int],
)

slots.articleMetadata__authors = Slot(
    uri=PCM.authors,
    name="articleMetadata__authors",
    curie=PCM.curie("authors"),
    model_uri=PCM.articleMetadata__authors,
    domain=None,
    range=Optional[str | list[str]],
)

slots.articleMetadata__keywords = Slot(
    uri=PCM.keywords,
    name="articleMetadata__keywords",
    curie=PCM.curie("keywords"),
    model_uri=PCM.articleMetadata__keywords,
    domain=None,
    range=Optional[str | list[str]],
)

slots.articleContent__article_id = Slot(
    uri=PCM.article_id,
    name="articleContent__article_id",
    curie=PCM.curie("article_id"),
    model_uri=PCM.articleContent__article_id,
    domain=None,
    range=URIRef,
)

slots.articleContent__metadata = Slot(
    uri=PCM.metadata,
    name="articleContent__metadata",
    curie=PCM.curie("metadata"),
    model_uri=PCM.articleContent__metadata,
    domain=None,
    range=Optional[dict | ArticleMetadata],
)

slots.articleContent__sections = Slot(
    uri=PCM.sections,
    name="articleContent__sections",
    curie=PCM.curie("sections"),
    model_uri=PCM.articleContent__sections,
    domain=None,
    range=Optional[dict | StructuredSection | list[dict | StructuredSection]],
)

slots.articleContent__assets = Slot(
    uri=PCM.assets,
    name="articleContent__assets",
    curie=PCM.curie("assets"),
    model_uri=PCM.articleContent__assets,
    domain=None,
    range=Optional[dict | AssetRef | list[dict | AssetRef]],
)

slots.articleContent__peer_reviews = Slot(
    uri=PCM.peer_reviews,
    name="articleContent__peer_reviews",
    curie=PCM.curie("peer_reviews"),
    model_uri=PCM.articleContent__peer_reviews,
    domain=None,
    range=Optional[dict | PeerReview | list[dict | PeerReview]],
)

slots.assetRef__asset_type = Slot(
    uri=PCM.asset_type,
    name="assetRef__asset_type",
    curie=PCM.curie("asset_type"),
    model_uri=PCM.assetRef__asset_type,
    domain=None,
    range=str,
)

slots.assetRef__uri = Slot(
    uri=PCM.uri,
    name="assetRef__uri",
    curie=PCM.curie("uri"),
    model_uri=PCM.assetRef__uri,
    domain=None,
    range=Optional[str],
)

slots.assetRef__label = Slot(
    uri=PCM.label,
    name="assetRef__label",
    curie=PCM.curie("label"),
    model_uri=PCM.assetRef__label,
    domain=None,
    range=Optional[str],
)

slots.assetRef__caption = Slot(
    uri=PCM.caption,
    name="assetRef__caption",
    curie=PCM.curie("caption"),
    model_uri=PCM.assetRef__caption,
    domain=None,
    range=Optional[str],
)

slots.assetRef__mime_type = Slot(
    uri=PCM.mime_type,
    name="assetRef__mime_type",
    curie=PCM.curie("mime_type"),
    model_uri=PCM.assetRef__mime_type,
    domain=None,
    range=Optional[str],
)

slots.peerReview__review_type = Slot(
    uri=PCM.review_type,
    name="peerReview__review_type",
    curie=PCM.curie("review_type"),
    model_uri=PCM.peerReview__review_type,
    domain=None,
    range=str,
)

slots.peerReview__title = Slot(
    uri=PCM.title,
    name="peerReview__title",
    curie=PCM.curie("title"),
    model_uri=PCM.peerReview__title,
    domain=None,
    range=Optional[str],
)

slots.peerReview__contributors = Slot(
    uri=PCM.contributors,
    name="peerReview__contributors",
    curie=PCM.curie("contributors"),
    model_uri=PCM.peerReview__contributors,
    domain=None,
    range=Optional[str],
)

slots.peerReview__revision_round = Slot(
    uri=PCM.revision_round,
    name="peerReview__revision_round",
    curie=PCM.curie("revision_round"),
    model_uri=PCM.peerReview__revision_round,
    domain=None,
    range=Optional[int],
)

slots.peerReview__sections = Slot(
    uri=PCM.sections,
    name="peerReview__sections",
    curie=PCM.curie("sections"),
    model_uri=PCM.peerReview__sections,
    domain=None,
    range=Optional[dict | StructuredSection | list[dict | StructuredSection]],
)
