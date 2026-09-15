"""Unit tests for pyeuropepmc.features.fulltext.extensions.content_blocks.

Covers the ContentBlock/StructuredSection data model (serialization, RAG
chunking, LangChain adapter) and the ContentBlockExtractor's JATS XML
parsing across paragraphs, lists, formulas, figures, tables, code, quotes,
subsections, footnotes, references, and other back-matter structures.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET

from pyeuropepmc.features.fulltext.extensions.content_blocks import (
    ContentBlock,
    ContentBlockExtractor,
    ContentBlockType,
    InlineElement,
    InlineElementType,
    StructuredSection,
)


def _extractor(xml: str) -> ContentBlockExtractor:
    return ContentBlockExtractor(root=DefusedET.fromstring(xml))


def _elem(xml: str) -> ET.Element:
    return DefusedET.fromstring(xml)


class TestInlineElement:
    def test_to_dict_minimal(self):
        ie = InlineElement(type=InlineElementType.BOLD, text="x", position=1, length=1)
        d = ie.to_dict()
        assert d == {"type": "bold", "text": "x", "position": 1, "length": 1}

    def test_to_dict_full(self):
        ie = InlineElement(
            type=InlineElementType.XREF,
            text="1",
            ref_type="bibr",
            target_id="r1",
            position=0,
            length=1,
            formula_latex="x^2",
            language="en",
            metadata={"a": 1},
        )
        d = ie.to_dict()
        assert d["ref_type"] == "bibr"
        assert d["target_id"] == "r1"
        assert d["formula_latex"] == "x^2"
        assert d["language"] == "en"
        assert d["metadata"] == {"a": 1}


class TestContentBlockFactories:
    def test_paragraph(self):
        b = ContentBlock.paragraph("hello")
        assert b.type == ContentBlockType.PARAGRAPH
        assert b.text == "hello"

    def test_heading(self):
        assert ContentBlock.heading("H").type == ContentBlockType.HEADING

    def test_list_block(self):
        b = ContentBlock.list_block(["a", "b"], list_type="ordered")
        assert b.items == ["a", "b"]
        assert b.list_type == "ordered"

    def test_formula(self):
        b = ContentBlock.formula("x=1", label="Eq. 1")
        assert b.tex == "x=1"
        assert b.label == "Eq. 1"

    def test_figure_ref(self):
        b = ContentBlock.figure_ref("fig1", label="Fig. 1")
        assert b.target_id == "fig1"

    def test_table_ref(self):
        b = ContentBlock.table_ref("tab1", label="Table 1")
        assert b.target_id == "tab1"

    def test_code(self):
        b = ContentBlock.code("print(1)", language="python")
        assert b.language == "python"

    def test_boxed_text(self):
        assert ContentBlock.boxed_text("box").type == ContentBlockType.BOXED_TEXT

    def test_quote(self):
        ie = InlineElement(type=InlineElementType.BOLD, text="x")
        b = ContentBlock.quote("q", inlines=[ie])
        assert b.inlines == [ie]

    def test_quote_default_inlines(self):
        assert ContentBlock.quote("q").inlines == []

    def test_figure(self):
        b = ContentBlock.figure("Fig. 1", "caption", uri="http://x", target_id="fig1")
        assert b.uri == "http://x"

    def test_table_block(self):
        b = ContentBlock.table_block("Table 1", "caption", text="t", rows=[["a", "b"]])
        assert b.rows == [["a", "b"]]

    def test_table_block_default_rows(self):
        assert ContentBlock.table_block("T", "c").rows == []

    def test_unknown_block(self):
        b = ContentBlock.unknown_block("custom-tag", text="x")
        assert b.jats_tag == "custom-tag"

    def test_definition_list(self):
        terms = [{"term": "A", "def": "B"}]
        assert ContentBlock.definition_list(terms).definition_terms == terms

    def test_paragraph_with_inlines(self):
        ie = InlineElement(type=InlineElementType.XREF, text="1")
        b = ContentBlock.paragraph_with_inlines("text", inlines=[ie])
        assert b.inlines == [ie]

    def test_paragraph_with_inlines_default(self):
        assert ContentBlock.paragraph_with_inlines("text").inlines == []


class TestContentBlockToDict:
    def test_minimal_paragraph(self):
        b = ContentBlock.paragraph("hi")
        d = b.to_dict()
        assert d == {"type": "paragraph", "schema_version": b.schema_version, "text": "hi"}

    def test_all_optional_fields_present(self):
        ie = InlineElement(type=InlineElementType.BOLD, text="x")
        b = ContentBlock(
            type=ContentBlockType.TABLE,
            text="t",
            items=["a"],
            list_type="ordered",
            label="L",
            target_id="tid",
            language="python",
            tex="x=1",
            mathml="<math/>",
            caption="cap",
            uri="http://x",
            jats_tag="tag",
            metadata={"k": "v"},
            inlines=[ie],
            parse_status="partial",
            quality_score=0.5,
            parser_notes=["note"],
            definition_terms=[{"term": "a", "def": "b"}],
            rows=[["1", "2"]],
        )
        d = b.to_dict()
        assert d["items"] == ["a"]
        assert d["list_type"] == "ordered"
        assert d["label"] == "L"
        assert d["target_id"] == "tid"
        assert d["language"] == "python"
        assert d["tex"] == "x=1"
        assert d["mathml"] == "<math/>"
        assert d["caption"] == "cap"
        assert d["uri"] == "http://x"
        assert d["jats_tag"] == "tag"
        assert d["inlines"] == [ie.to_dict()]
        assert d["definition_terms"] == [{"term": "a", "def": "b"}]
        assert d["rows"] == [["1", "2"]]
        assert d["metadata"] == {"k": "v"}
        assert d["parse_status"] == "partial"
        assert d["quality_score"] == 0.5
        assert d["parser_notes"] == ["note"]


class TestStructuredSectionToDict:
    def test_basic(self):
        section = StructuredSection(
            title="Intro", content=[ContentBlock.paragraph("hi")], section_path="Intro"
        )
        d = section.to_dict()
        assert d["title"] == "Intro"
        assert d["section_type"] == "body"
        assert d["section_path"] == "Intro"
        assert d["content"] == [ContentBlock.paragraph("hi").to_dict()]

    def test_no_section_path(self):
        section = StructuredSection(title="Intro")
        d = section.to_dict()
        assert "section_path" not in d


class TestBlockText:
    def test_dict_with_text(self):
        assert StructuredSection._block_text({"text": "hi"}) == "hi"

    def test_dict_without_text(self):
        assert StructuredSection._block_text({}) == ""

    def test_block_with_text(self):
        assert StructuredSection._block_text(ContentBlock.paragraph("hi")) == "hi"

    def test_block_with_items(self):
        block = ContentBlock.list_block(["a", "b"])
        assert StructuredSection._block_text(block) == "- a\n- b"

    def test_block_with_definition_terms(self):
        block = ContentBlock.definition_list([{"term": "A", "def": "B"}])
        assert StructuredSection._block_text(block) == "A: B"

    def test_block_with_caption(self):
        block = ContentBlock.figure("L", "cap")
        assert StructuredSection._block_text(block) == "cap"

    def test_block_with_nothing(self):
        block = ContentBlock(type=ContentBlockType.UNKNOWN_BLOCK)
        assert StructuredSection._block_text(block) == ""


class TestToChunks:
    def test_empty_section(self):
        section = StructuredSection(title="T")
        assert section.to_chunks() == []

    def test_single_small_block(self):
        section = StructuredSection(title="T", content=[ContentBlock.paragraph("hello world")])
        chunks = section.to_chunks()
        assert len(chunks) == 1
        assert chunks[0]["text"] == "hello world"
        assert chunks[0]["section_path"] == "T"
        assert chunks[0]["chunk_index"] == 0

    def test_multiple_blocks_flush_on_overflow(self):
        section = StructuredSection(
            title="T",
            content=[ContentBlock.paragraph("word " * 50), ContentBlock.paragraph("word " * 50)],
        )
        chunks = section.to_chunks(max_tokens=20, overlap=2)
        assert len(chunks) >= 2

    def test_oversized_block_is_split(self):
        long_text = ("This is a sentence. " * 200).strip()
        section = StructuredSection(title="T", content=[ContentBlock.paragraph(long_text)])
        chunks = section.to_chunks(max_tokens=10)
        assert len(chunks) > 1
        for c in chunks:
            assert c["section_path"] == "T"


class TestSplitBlockIntoChunks:
    def test_splits_by_sentence(self):
        chunks: list[dict] = []
        text = "One. Two. Three. Four. Five."
        StructuredSection._split_block_into_chunks(
            text, max_chars=10, chunks=chunks, section_title="S"
        )
        assert len(chunks) > 1
        assert all(c["section_path"] == "S" for c in chunks)

    def test_single_short_sentence(self):
        chunks: list[dict] = []
        StructuredSection._split_block_into_chunks(
            "Hi.", max_chars=100, chunks=chunks, section_title="S"
        )
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hi."


class TestToLangchainDocuments:
    def test_basic(self):
        section = StructuredSection(
            title="Intro",
            content=[ContentBlock.paragraph("hi"), ContentBlock.paragraph("")],
        )
        docs = section.to_langchain_documents()
        assert len(docs) == 1
        assert docs[0]["page_content"] == "hi"
        assert docs[0]["metadata"]["section_title"] == "Intro"
        assert docs[0]["metadata"]["block_type"] == "paragraph"

    def test_with_metadata_and_label(self):
        block = ContentBlock.figure("Fig. 1", "caption text")
        section = StructuredSection(title="Results", content=[block])
        docs = section.to_langchain_documents(metadata={"article_id": "PMC1"})
        assert docs[0]["metadata"]["article_id"] == "PMC1"
        assert docs[0]["metadata"]["label"] == "Fig. 1"

    def test_skips_empty_blocks(self):
        section = StructuredSection(
            title="T", content=[ContentBlock(type=ContentBlockType.UNKNOWN_BLOCK)]
        )
        assert section.to_langchain_documents() == []


class TestGetMultipartTitle:
    def test_none_returns_empty(self):
        assert ContentBlockExtractor._get_multipart_title(None) == ""

    def test_simple_title(self):
        elem = _elem("<title>Methods</title>")
        assert ContentBlockExtractor._get_multipart_title(elem) == "Methods"


class TestStaticHelpers:
    def test_get_local_tag_with_namespace(self):
        assert ContentBlockExtractor._get_local_tag("{http://x}p") == "p"

    def test_get_local_tag_without_namespace(self):
        assert ContentBlockExtractor._get_local_tag("p") == "p"

    def test_get_xlink_href(self):
        elem = _elem('<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="a.png"/>')
        assert ContentBlockExtractor._get_xlink_href(elem) == "a.png"

    def test_get_xlink_href_plain(self):
        elem = _elem('<graphic href="b.png"/>')
        assert ContentBlockExtractor._get_xlink_href(elem) == "b.png"

    def test_get_xlink_href_missing(self):
        elem = _elem("<graphic/>")
        assert ContentBlockExtractor._get_xlink_href(elem) == ""

    def test_get_namespace_map(self):
        ns = ContentBlockExtractor._get_namespace_map()
        assert ns["mml"] == "http://www.w3.org/1998/Math/MathML"

    def test_resolve_entities(self):
        text = "A &amp; B &lt;x&gt; &ndash; &hellip;"
        resolved = ContentBlockExtractor._resolve_entities(text)
        assert resolved == "A & B <x> – …"

    def test_convert_inline_formula_no_mathml(self):
        elem = _elem("<inline-formula>x=1</inline-formula>")
        assert ContentBlockExtractor._convert_inline_formula(elem) == ""

    def test_convert_inline_formula_with_mathml(self):
        xml = (
            '<inline-formula xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:math><mml:mi>x</mml:mi></mml:math></inline-formula>"
        )
        elem = _elem(xml)
        result = ContentBlockExtractor._convert_inline_formula(elem)
        assert isinstance(result, str)


class TestHandleParagraph:
    def test_plain_text(self):
        extractor = _extractor("<root/>")
        elem = _elem("<p>Simple text.</p>")
        blocks = extractor._handle_paragraph(elem)
        assert len(blocks) == 1
        assert blocks[0].text == "Simple text."
        assert blocks[0].inlines == []

    def test_empty_paragraph_returns_nothing(self):
        extractor = _extractor("<root/>")
        blocks = extractor._handle_paragraph(_elem("<p></p>"))
        assert blocks == []

    def test_xref_tracked(self):
        extractor = _extractor("<root/>")
        elem = _elem('<p>See <xref ref-type="bibr" rid="r1">1</xref> for details.</p>')
        blocks = extractor._handle_paragraph(elem)
        assert len(blocks) == 1
        assert "1" in blocks[0].text
        xrefs = [i for i in blocks[0].inlines if i.type == InlineElementType.XREF]
        assert len(xrefs) == 1
        assert xrefs[0].target_id == "r1"
        assert xrefs[0].ref_type == "bibr"

    def test_inline_formula_tracked(self):
        extractor = _extractor("<root/>")
        elem = _elem("<p>Value <inline-formula>x=1</inline-formula> here.</p>")
        blocks = extractor._handle_paragraph(elem)
        formulas = [i for i in blocks[0].inlines if i.type == InlineElementType.INLINE_FORMULA]
        assert len(formulas) == 1

    def test_formatting_tags_tracked(self):
        extractor = _extractor("<root/>")
        elem = _elem(
            "<p><bold>B</bold> <italic>I</italic> <sup>1</sup> <sub>2</sub> "
            "<underline>U</underline></p>"
        )
        blocks = extractor._handle_paragraph(elem)
        types = {i.type for i in blocks[0].inlines}
        assert InlineElementType.BOLD in types
        assert InlineElementType.ITALIC in types
        assert InlineElementType.SUP in types
        assert InlineElementType.SUB in types
        assert InlineElementType.UNDERLINE in types

    def test_named_content_language(self):
        extractor = _extractor("<root/>")
        elem = _elem(
            '<p><named-content xmlns:xml="http://www.w3.org/XML/1998/namespace" '
            'xml:lang="fr">bonjour</named-content></p>'
        )
        blocks = extractor._handle_paragraph(elem)
        nc = [i for i in blocks[0].inlines if i.type == InlineElementType.NAMED_CONTENT][0]
        assert nc.language == "fr"

    def test_unknown_child_recurses(self):
        extractor = _extractor("<root/>")
        elem = _elem("<p>Before <foo><bold>inside</bold></foo> after.</p>")
        blocks = extractor._handle_paragraph(elem)
        assert len(blocks) == 1
        assert blocks[0].text == "Before inside after."

    def test_figure_child_splits_the_paragraph(self):
        extractor = _extractor("<root/>")
        elem = _elem("<p>Before <fig><label>Fig. 1</label></fig> after.</p>")
        blocks = extractor._handle_paragraph(elem)
        assert [b.type.value for b in blocks] == ["paragraph", "figure", "paragraph"]
        assert (blocks[0].text, blocks[2].text) == ("Before", "after.")

    def test_tail_text_after_child(self):
        extractor = _extractor("<root/>")
        elem = _elem("<p><bold>B</bold> tail text.</p>")
        blocks = extractor._handle_paragraph(elem)
        assert "tail text." in blocks[0].text


class TestHandleList:
    def test_unordered_list(self):
        extractor = _extractor("<root/>")
        elem = _elem(
            "<list><list-item><p>One</p></list-item><list-item><p>Two</p></list-item></list>"
        )
        blocks = extractor._handle_list(elem)
        assert len(blocks) == 1
        assert blocks[0].items == ["One", "Two"]
        assert blocks[0].list_type == "unordered"

    def test_ordered_list_type_attr(self):
        extractor = _extractor("<root/>")
        elem = _elem('<list list-type="order"><list-item><p>A</p></list-item></list>')
        blocks = extractor._handle_list(elem)
        assert blocks[0].list_type == "order"

    def test_empty_list_returns_nothing(self):
        extractor = _extractor("<root/>")
        assert extractor._handle_list(_elem("<list/>")) == []

    def test_list_with_inlines_aggregates_metadata(self):
        extractor = _extractor("<root/>")
        elem = _elem(
            "<list><list-item><p>See "
            '<xref ref-type="bibr" rid="r1">1</xref></p></list-item></list>'
        )
        blocks = extractor._handle_list(elem)
        assert "item_inlines" in blocks[0].metadata
        assert len(blocks[0].inlines) == 1


class TestHandleDefList:
    def test_basic(self):
        extractor = _extractor("<root/>")
        elem = _elem(
            "<def-list><def-item><term>Term1</term>"
            "<def><p>Definition 1</p></def></def-item></def-list>"
        )
        blocks = extractor._handle_def_list(elem)
        assert blocks[0].definition_terms == [{"term": "Term1", "def": "Definition 1"}]

    def test_empty_returns_nothing(self):
        extractor = _extractor("<root/>")
        assert extractor._handle_def_list(_elem("<def-list/>")) == []


class TestHandleFormula:
    def test_with_label_and_plain_text(self):
        extractor = _extractor("<root/>")
        elem = _elem("<disp-formula><label>Eq. 1</label>x = y + z</disp-formula>")
        blocks = extractor._handle_formula(elem)
        assert blocks[0].label == "Eq. 1"
        assert "x = y + z" in blocks[0].tex

    def test_with_mathml(self):
        extractor = _extractor("<root/>")
        xml = (
            '<disp-formula xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:math><mml:mi>x</mml:mi></mml:math></disp-formula>"
        )
        blocks = extractor._handle_formula(_elem(xml))
        assert blocks[0].mathml != ""

    def test_alt_text_fallback(self):
        extractor = _extractor("<root/>")
        xml = (
            '<disp-formula xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:math></mml:math><alt-text>alt formula</alt-text></disp-formula>"
        )
        blocks = extractor._handle_formula(_elem(xml))
        assert blocks[0].tex == "alt formula"


class TestHandleFigure:
    def test_full_figure(self):
        extractor = _extractor("<root/>")
        xml = (
            '<fig id="fig1"><label>Fig. 1</label><caption><p>A caption.</p></caption>'
            '<graphic xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="fig1.png"/></fig>'
        )
        blocks = extractor._handle_figure(_elem(xml))
        assert blocks[0].target_id == "fig1"
        assert blocks[0].label == "Fig. 1"
        assert blocks[0].caption == "A caption."
        assert blocks[0].uri == "fig1.png"

    def test_minimal_figure(self):
        extractor = _extractor("<root/>")
        blocks = extractor._handle_figure(_elem("<fig/>"))
        assert blocks[0].target_id == ""
        assert blocks[0].caption == ""


class TestHandleTable:
    def test_full_table(self):
        extractor = _extractor("<root/>")
        xml = (
            "<table-wrap><label>Table 1</label><caption><p>Cap</p></caption>"
            "<table><thead><tr><th>H1</th><th>H2</th></tr></thead>"
            "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
            "<table-wrap-foot><fn><p>Note</p></fn></table-wrap-foot></table-wrap>"
        )
        blocks = extractor._handle_table(_elem(xml))
        block = blocks[0]
        assert block.label == "Table 1"
        assert block.caption == "Cap"
        assert block.rows == [["H1", "H2"], ["1", "2"]]

    def test_table_without_caption_uses_text_fallback(self):
        extractor = _extractor("<root/>")
        xml = "<table-wrap><table><tbody><tr><td>x</td></tr></tbody></table></table-wrap>"
        blocks = extractor._handle_table(_elem(xml))
        assert blocks[0].rows == [["x"]]

    def test_table_with_cell_inlines(self):
        extractor = _extractor("<root/>")
        xml = (
            '<table-wrap><table><tbody><tr><td>See <xref ref-type="bibr" rid="r1">1</xref></td>'
            "</tr></tbody></table></table-wrap>"
        )
        blocks = extractor._handle_table(_elem(xml))
        assert "cell_inlines" in blocks[0].metadata
        assert len(blocks[0].inlines) >= 1


class TestHandleCode:
    def test_with_language(self):
        extractor = _extractor("<root/>")
        elem = _elem('<code language="python">print(1)</code>')
        blocks = extractor._handle_code(elem)
        assert blocks[0].language == "python"
        assert blocks[0].text == "print(1)"

    def test_lang_attr_fallback(self):
        extractor = _extractor("<root/>")
        elem = _elem('<code lang="bash">ls</code>')
        blocks = extractor._handle_code(elem)
        assert blocks[0].language == "bash"

    def test_empty_returns_nothing(self):
        extractor = _extractor("<root/>")
        assert extractor._handle_code(_elem("<code></code>")) == []


class TestHandleMedia:
    def test_full_media(self):
        extractor = _extractor("<root/>")
        xml = (
            '<media mimetype="video" mime-subtype="mp4" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="v.mp4">'
            "<label>Video 1</label><caption><p>desc</p></caption></media>"
        )
        blocks = extractor._handle_media(_elem(xml))
        assert blocks[0].label == "Video 1"
        assert blocks[0].caption == "desc"
        assert blocks[0].uri == "v.mp4"
        assert blocks[0].metadata["mime_type"] == "video/mp4"

    def test_media_without_caption_uses_text(self):
        extractor = _extractor("<root/>")
        elem = _elem("<media>some description text</media>")
        blocks = extractor._handle_media(elem)
        assert blocks[0].caption == "some description text"

    def test_empty_media_returns_nothing(self):
        extractor = _extractor("<root/>")
        assert extractor._handle_media(_elem("<media/>")) == []


class TestHandleBoxedText:
    def test_with_inlines(self):
        extractor = _extractor("<root/>")
        elem = _elem("<boxed-text><p>Some <bold>bold</bold> text.</p></boxed-text>")
        blocks = extractor._handle_boxed_text(elem)
        assert "bold" in blocks[0].text

    def test_empty_returns_nothing(self):
        extractor = _extractor("<root/>")
        assert extractor._handle_boxed_text(_elem("<boxed-text></boxed-text>")) == []


class TestHandleQuote:
    def test_with_text(self):
        extractor = _extractor("<root/>")
        elem = _elem("<disp-quote><p>A quotation.</p></disp-quote>")
        blocks = extractor._handle_quote(elem)
        assert blocks[0].type == ContentBlockType.QUOTE
        assert "A quotation." in blocks[0].text

    def test_empty_returns_nothing(self):
        extractor = _extractor("<root/>")
        assert extractor._handle_quote(_elem("<disp-quote></disp-quote>")) == []


class TestHandleSubsection:
    def test_with_title_and_paragraph(self):
        extractor = _extractor("<root/>")
        elem = _elem("<sec><title>Sub</title><p>Text.</p></sec>")
        blocks = extractor._handle_subsection(elem)
        assert blocks[0].type == ContentBlockType.HEADING
        assert blocks[0].text == "Sub"
        assert blocks[1].text == "Text."

    def test_without_title(self):
        extractor = _extractor("<root/>")
        elem = _elem("<sec><p>Text.</p></sec>")
        blocks = extractor._handle_subsection(elem)
        assert len(blocks) == 1
        assert blocks[0].type == ContentBlockType.PARAGRAPH


class TestExtractSectionsIntegration:
    XML = """<article>
      <front>
        <article-meta>
          <title-group><article-title>My <italic>Great</italic> Paper</article-title></title-group>
          <abstract><p>This is the <bold>abstract</bold>.</p></abstract>
        </article-meta>
      </front>
      <body>
        <sec>
          <title>Introduction</title>
          <p>Intro text with <xref ref-type="bibr" rid="r1">1</xref>.</p>
          <sec>
            <title>Background</title>
            <p>Nested text.</p>
          </sec>
        </sec>
        <sec>
          <title>Methods</title>
          <list><list-item><p>Step one.</p></list-item></list>
          <fig id="fig1"><label>Fig. 1</label><caption><p>Cap.</p></caption></fig>
          <table-wrap><label>Table 1</label>
            <table><tbody><tr><td>a</td></tr></tbody></table>
          </table-wrap>
          <disp-formula><label>Eq. 1</label>x=1</disp-formula>
          <code language="python">print(1)</code>
          <boxed-text><p>Boxed.</p></boxed-text>
          <disp-quote><p>Quoted.</p></disp-quote>
          <def-list><def-item><term>T</term><def><p>D</p></def></def-item></def-list>
          <supplementary-material>
            <caption><title>Supp Title</title><p>Supp text.</p></caption>
          </supplementary-material>
          <fn-group><fn><label>*</label><p>A footnote.</p></fn></fn-group>
          <custom-unknown-tag>Some unknown content.</custom-unknown-tag>
        </sec>
        <p>Bare paragraph directly under body.</p>
      </body>
      <back>
        <fn-group><fn><label>a</label><p>Back footnote.</p></fn></fn-group>
        <ref-list><title>References</title>
          <ref id="ref1"><label>1.</label>Smith J. Some paper.</ref>
        </ref-list>
        <ack><p>Thanks to everyone.</p></ack>
        <app-group>
          <app><title>Appendix A</title><p>Appendix text.</p></app>
        </app-group>
        <glossary><title>Glossary</title><def-list>
          <def-item><term>G</term><def><p>Gdef</p></def></def-item>
        </def-list></glossary>
        <notes><title>Notes</title><p>A note.</p></notes>
      </back>
    </article>"""

    def test_extract_sections_full_pipeline(self):
        extractor = _extractor(self.XML)
        sections = extractor.extract_sections()
        titles = [s.title for s in sections]
        assert "Article Title" in titles
        assert "Abstract" in titles
        assert "Introduction" in titles
        assert "Background" in titles
        assert "Methods" in titles
        assert "Footnotes" in titles
        assert "References" in titles
        assert "Acknowledgments" in titles
        assert "Appendix A" in titles
        assert "Glossary" in titles
        assert "Notes" in titles

    def test_methods_section_has_expected_block_types(self):
        extractor = _extractor(self.XML)
        sections = extractor.extract_sections()
        methods = next(s for s in sections if s.title == "Methods")
        types = {block.type for block in methods.content}
        assert ContentBlockType.LIST in types
        assert ContentBlockType.FIGURE in types
        assert ContentBlockType.TABLE in types
        assert ContentBlockType.FORMULA in types
        assert ContentBlockType.CODE in types
        assert ContentBlockType.QUOTE in types
        assert ContentBlockType.DEFINITION_LIST in types

    def test_bare_paragraph_under_body_collected(self):
        extractor = _extractor(self.XML)
        sections = extractor.extract_sections()
        bare = [s for s in sections if s.title == "" and s.section_type == "body"]
        assert any(
            "Bare paragraph directly under body." in b.text for s in bare for b in s.content
        )

    def test_no_root_raises(self):
        extractor = ContentBlockExtractor()
        import pytest

        from pyeuropepmc.core.exceptions import ParsingError

        with pytest.raises(ParsingError):
            extractor.extract_sections()

    def test_no_body_no_front_matter_returns_empty(self):
        extractor = _extractor("<article/>")
        assert extractor.extract_sections() == []


class TestExtractArticleTitle:
    def test_no_title_group_returns_none(self):
        extractor = _extractor("<article/>")
        assert extractor._extract_article_title() is None

    def test_empty_title_returns_none(self):
        xml = (
            "<article><front><article-meta><title-group>"
            "<article-title>  </article-title>"
            "</title-group></article-meta></front></article>"
        )
        extractor = _extractor(xml)
        assert extractor._extract_article_title() is None


class TestExtractAbstract:
    def test_no_abstract_returns_none(self):
        extractor = _extractor("<article/>")
        assert extractor._extract_abstract() is None

    def test_structured_abstract(self):
        xml = (
            "<article><abstract><sec><title>Background</title>"
            "<p>Some background.</p></sec></abstract></article>"
        )
        extractor = _extractor(xml)
        section = extractor._extract_abstract()
        assert section is not None
        assert "Background: Some background." in section.content[0].text

    def test_abstract_with_custom_title(self):
        xml = "<article><abstract><title>Summary</title><p>Text.</p></abstract></article>"
        extractor = _extractor(xml)
        section = extractor._extract_abstract()
        assert section.title == "Summary"

    def test_abstract_with_no_paragraphs_returns_none(self):
        xml = "<article><abstract><title>Summary</title></abstract></article>"
        extractor = _extractor(xml)
        assert extractor._extract_abstract() is None


class TestExtractFootnotes:
    def test_no_footnotes_returns_empty(self):
        extractor = _extractor("<article/>")
        assert extractor._extract_footnotes() == []

    def test_footnote_inside_body_skipped(self):
        xml = "<article><body><fn-group><fn><p>Inside body.</p></fn></fn-group></body></article>"
        extractor = _extractor(xml)
        assert extractor._extract_footnotes() == []

    def test_footnote_outside_body_collected(self):
        xml = "<article><back><fn-group><fn><p>Outside body.</p></fn></fn-group></back></article>"
        extractor = _extractor(xml)
        sections = extractor._extract_footnotes()
        assert len(sections) == 1
        assert "Outside body." in sections[0].content[0].text


class TestExtractGlossaryAndNotes:
    def test_glossary_no_def_list_uses_text(self):
        xml = "<article><glossary><title>G</title>text here</glossary></article>"
        extractor = _extractor(xml)
        sections = extractor._extract_glossary_sections()
        # get_text_content collects all descendant text, including the title's.
        assert sections[0].content[0].text == "G text here"

    def test_notes_with_label_skipped(self):
        xml = "<article><notes><title>N</title><label>1</label><p>Body.</p></notes></article>"
        extractor = _extractor(xml)
        sections = extractor._extract_notes_sections()
        texts = [b.text for b in sections[0].content]
        assert texts == ["Body."]


class TestIsInsideBody:
    def test_no_root_returns_false(self):
        extractor = ContentBlockExtractor()
        assert extractor._is_inside_body(_elem("<fn/>")) is False

    def test_element_not_in_tree_returns_false(self):
        xml = "<article><body><p>x</p></body></article>"
        extractor = _extractor(xml)
        assert extractor._is_inside_body(_elem("<fn/>")) is False
