"""Unit tests for the auto-generated LinkML models (article_content_schema).

Exercises the real validation logic each ``__post_init__`` performs
(required-field checks, type coercion, enum coercion, list normalization) —
this is generated code, but the generated ``__post_init__`` bodies are not.
"""

from __future__ import annotations

import pytest

pytest.importorskip("linkml_runtime")

from linkml_runtime.utils.yamlutils import YAMLRoot

from pyeuropepmc.features.fulltext.extensions.linkml_models import (
    ArticleContent,
    ArticleMetadata,
    AssetRef,
    ContentBlock,
    ContentBlockType,
    ListStyle,
    PeerReview,
    SectionType,
    StructuredSection,
)


class TestContentBlock:
    def test_minimal_paragraph(self):
        block = ContentBlock(type="paragraph", text="Hello world.")
        assert str(block.type) == "paragraph"
        assert block.text == "Hello world."
        assert block.items == []

    def test_missing_type_raises(self):
        with pytest.raises(ValueError):
            ContentBlock(text="no type given")

    def test_type_accepts_already_coerced_enum_instance(self):
        first = ContentBlock(type="heading", text="A Heading")
        second = ContentBlock(type=first.type, text="Another Heading")
        assert str(second.type) == "heading"

    def test_non_string_text_coerced(self):
        block = ContentBlock(type="paragraph", text=123)
        assert block.text == "123"

    def test_items_single_value_wrapped_in_list(self):
        block = ContentBlock(type="list", items="one item")
        assert block.items == ["one item"]

    def test_items_list_coerced_to_strings(self):
        block = ContentBlock(type="list", items=[1, 2, "three"])
        assert block.items == ["1", "2", "three"]

    def test_list_type_coerced_to_enum(self):
        block = ContentBlock(type="list", list_type="ordered")
        assert str(block.list_type) == "ordered"

    def test_optional_fields_coerced_to_str(self):
        block = ContentBlock(
            type="figure",
            label=1,
            target_id=2,
            language=3,
            tex=4,
            mathml=5,
            caption=6,
            uri=7,
            jats_tag=8,
            metadata=9,
        )
        for field in (
            "label",
            "target_id",
            "language",
            "tex",
            "mathml",
            "caption",
            "uri",
            "jats_tag",
            "metadata",
        ):
            assert isinstance(getattr(block, field), str)


class TestStructuredSection:
    def test_minimal(self):
        block = ContentBlock(type="paragraph", text="body text")
        section = StructuredSection(title="Introduction", content=[block])
        assert section.title == "Introduction"
        assert len(section.content) == 1
        assert isinstance(section.content[0], ContentBlock)

    def test_missing_title_raises(self):
        with pytest.raises(ValueError):
            StructuredSection(title=None, content=[{"type": "paragraph", "text": "x"}])

    def test_missing_content_raises(self):
        with pytest.raises(ValueError):
            StructuredSection(title="T", content=None)

    def test_content_dict_normalized_to_content_block(self):
        section = StructuredSection(
            title="Results", content=[{"type": "paragraph", "text": "Some results."}]
        )
        assert isinstance(section.content[0], ContentBlock)
        assert section.content[0].text == "Some results."

    def test_section_type_coerced_to_enum(self):
        section = StructuredSection(
            title="Back matter",
            content=[{"type": "paragraph", "text": "x"}],
            section_type="back",
        )
        assert str(section.section_type) == "back"

    def test_title_coerced_to_str(self):
        section = StructuredSection(title=42, content=[{"type": "paragraph", "text": "x"}])
        assert section.title == "42"


class TestArticleMetadata:
    def test_all_optional_fields_default_empty(self):
        meta = ArticleMetadata()
        assert meta.authors == []
        assert meta.keywords == []
        assert meta.pmid is None

    def test_field_type_coercion(self):
        meta = ArticleMetadata(pmid=123, pmcid=456, publication_year="2020")
        assert meta.pmid == "123"
        assert meta.pmcid == "456"
        assert meta.publication_year == 2020

    def test_authors_and_keywords_normalized_to_str_list(self):
        meta = ArticleMetadata(authors="Solo Author", keywords=[1, "two"])
        assert meta.authors == ["Solo Author"]
        assert meta.keywords == ["1", "two"]


class TestAssetRef:
    def test_minimal(self):
        asset = AssetRef(asset_type="figure")
        assert asset.asset_type == "figure"

    def test_missing_asset_type_raises(self):
        with pytest.raises(ValueError):
            AssetRef(asset_type=None)

    def test_field_coercion(self):
        asset = AssetRef(asset_type="table", uri=1, label=2, caption=3, mime_type=4)
        assert asset.uri == "1"
        assert asset.mime_type == "4"


class TestPeerReview:
    def test_minimal(self):
        review = PeerReview(review_type="referee_report")
        assert review.review_type == "referee_report"
        assert review.sections == []

    def test_missing_review_type_raises(self):
        with pytest.raises(ValueError):
            PeerReview(review_type=None)

    def test_revision_round_coerced_to_int(self):
        review = PeerReview(review_type="referee_report", revision_round="2")
        assert review.revision_round == 2

    def test_sections_normalized(self):
        review = PeerReview(
            review_type="referee_report",
            sections=[{"title": "Comments", "content": [{"type": "paragraph", "text": "x"}]}],
        )
        assert isinstance(review.sections[0], StructuredSection)


class TestArticleContent:
    def test_minimal(self):
        article = ArticleContent(article_id="PMC123")
        assert str(article.article_id) == "PMC123"
        assert article.sections == []
        assert article.assets == []
        assert article.peer_reviews == []

    def test_missing_article_id_raises(self):
        with pytest.raises(ValueError):
            ArticleContent(article_id=None)

    def test_metadata_dict_normalized(self):
        article = ArticleContent(article_id="PMC1", metadata={"pmid": "1", "title": "T"})
        assert isinstance(article.metadata, ArticleMetadata)
        assert article.metadata.title == "T"

    def test_full_construction(self):
        article = ArticleContent(
            article_id="PMC1",
            metadata={"pmid": "1", "title": "T"},
            sections=[
                {"title": "Intro", "content": [{"type": "paragraph", "text": "hi"}]},
            ],
            assets=[{"asset_type": "figure", "uri": "http://x/fig1.png"}],
            peer_reviews=[{"review_type": "referee_report", "title": "Round 1"}],
        )
        assert isinstance(article.sections[0], StructuredSection)
        assert isinstance(article.assets[0], AssetRef)
        assert isinstance(article.peer_reviews[0], PeerReview)


class TestEnums:
    def test_content_block_type_permissible_values(self):
        assert ContentBlockType.paragraph.text == "paragraph"
        assert ContentBlockType.unknown_block.text == "unknown_block"

    def test_section_type_permissible_values(self):
        assert SectionType.front.text == "front"
        assert SectionType.body.text == "body"
        assert SectionType.peer_review.text == "peer_review"

    def test_list_style_permissible_values(self):
        assert ListStyle.ordered.text == "ordered"
        assert ListStyle.simple.text == "simple"


def test_models_inherit_yamlroot():
    block = ContentBlock(type="paragraph", text="x")
    assert isinstance(block, YAMLRoot)
