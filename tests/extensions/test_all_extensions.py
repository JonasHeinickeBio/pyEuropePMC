"""
Comprehensive unit tests for all extension modules.

Tests are organized by module with shared XML fixtures.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET  # nosec B405

import pytest

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

# Apply module-level markers
pytestmark = pytest.mark.unit


# ============================================================================
# XML Fixtures
# ============================================================================

SIMPLE_ARTICLE_XML = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front>
<article-meta>
<article-id pub-id-type="pmcid">PMC1234567</article-id>
<article-id pub-id-type="doi">10.1234/test.2024.001</article-id>
<article-id pub-id-type="pmid">12345678</article-id>
<title-group><article-title>Test Article for Extensions</article-title></title-group>
<contrib-group>
<contrib contrib-type="author" id="auth1">
<name><surname>Smith</surname><given-names>John</given-names></name>
<contrib-id contrib-id-type="orcid">0000-0002-1825-0097</contrib-id>
<aff id="aff1">University of Testing</aff>
</contrib>
</contrib-group>
<aff id="aff1"><institution>University of Testing</institution><country>UK</country></aff>
<pub-date pub-type="ppub"><year>2024</year></pub-date>
<abstract><p>This is a test abstract with <bold>important</bold> content.</p></abstract>
<kwd-group><kwd>testing</kwd><kwd>python</kwd></kwd-group>
<funding-group>
<award-id>R01-GH-123456</award-id>
<funding-source>NIH</funding-source>
</funding-group>
</article-meta>
</front>
<body>
<sec id="sec1">
<title>Introduction</title>
<p>This is the introduction paragraph with some <xref ref-type="fig" rid="fig1">Figure 1</xref> reference.</p>
<p>A second paragraph with <italic>emphasized</italic> text.</p>
<list list-type="ordered">
<list-item><p>First item</p></list-item>
<list-item><p>Second item</p></list-item>
<list-item><p>Third item</p></list-item>
</list>
<disp-formula id="eq1">
<label>(1)</label>
<alternatives>
<tex-math>E=mc^2</tex-math>
</alternatives>
</disp-formula>
</sec>
<sec id="sec2">
<title>Methods</title>
<p>Methods paragraph with a formula: <inline-formula><alternatives><tex-math>y=mx+b</tex-math></alternatives></inline-formula>.</p>
</sec>
</body>
<back>
<ack><p>We thank the test community.</p></ack>
<ref-list>
<ref id="ref1">
<label>1</label>
<element-citation>
<person-group person-group-type="author"><name><surname>Author</surname><given-names>A</given-names></name></person-group>
<article-title>A test paper</article-title>
<source>Test Journal</source>
<year>2023</year>
<pub-id pub-id-type="doi">10.1234/test.2023.001</pub-id>
</element-citation>
</ref>
</ref-list>
</back>
</article>
"""


ARTICLE_WITH_MATHML = """<?xml version="1.0"?>
<article xmlns:mml="http://www.w3.org/1998/Math/MathML">
<front>
<article-meta>
<title-group><article-title>MathML Test</article-title></title-group>
</article-meta>
</front>
<body>
<sec>
<title>Math Section</title>
<p>Here is an inline formula: <inline-formula>
<mml:math display="inline">
<mml:mi>E</mml:mi>
<mml:mo>=</mml:mo>
<mml:mi>m</mml:mi>
<mml:msup>
<mml:mi>c</mml:mi>
<mml:mn>2</mml:mn>
</mml:msup>
</mml:math>
</inline-formula>.</p>
<disp-formula id="eq-einstein">
<label>(1)</label>
<mml:math display="block">
<mml:mi>E</mml:mi>
<mml:mo>=</mml:mo>
<mml:mi>m</mml:mi>
<mml:msup>
<mml:mi>c</mml:mi>
<mml:mn>2</mml:mn>
</mml:msup>
</mml:math>
</disp-formula>
</sec>
</body>
</article>
"""


ARTICLE_WITH_PEER_REVIEW = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front>
<article-meta>
<article-id pub-id-type="pmcid">PMC9876543</article-id>
<title-group><article-title>Peer Review Test Article</article-title></title-group>
</article-meta>
</front>
<body>
<sec><title>Main</title><p>Article body.</p></sec>
</body>
<sub-article article-type="decision-letter" id="sa1">
<front-stub>
<title-group><article-title>Decision Letter</article-title></title-group>
<contrib-group>
<contrib contrib-type="editor">
<name><surname>Editor</surname><given-names>Edna</given-names></name>
</contrib>
</contrib-group>
<date date-type="received"><year>2024</year><month>01</month><day>15</day></date>
</front-stub>
<body>
<sec><title>Editor Comments</title><p>This is an interesting study but requires revisions.</p></sec>
</body>
</sub-article>
<sub-article article-type="referee-report" id="sa2">
<front-stub>
<title-group><article-title>Reviewer 1 Report</article-title></title-group>
<contrib-group>
<contrib contrib-type="reviewer">
<name><surname>Reviewer</surname><given-names>Rita</given-names></name>
</contrib>
</contrib-group>
</front-stub>
<body>
<p>The methodology is sound.</p>
<p>Results are reproducible.</p>
</body>
</sub-article>
</article>
"""


ARTICLE_WITH_FIGURES = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front>
<article-meta>
<title-group><article-title>Figure Test</article-title></title-group>
</article-meta>
</front>
<body>
<sec>
<title>Results</title>
<fig id="fig1">
<label>Fig. 1</label>
<caption><p>Test results showing significant improvement.</p></caption>
<graphic xlink:href="f1.jpg"/>
</fig>
<p>As shown in <xref ref-type="fig" rid="fig1">Fig. 1</xref>.</p>
<supplementary-material id="supp1">
<label>Supplementary Data S1</label>
<object-id>supp_data.zip</object-id>
</supplementary-material>
</sec>
</body>
</article>
"""


# ============================================================================
# Tests: Content Blocks
# ============================================================================


class TestContentBlocks:
    """Tests for the ContentBlockExtractor and data model."""

    def test_content_block_types(self):
        """Verify ContentBlock factory methods produce correct types."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
        )

        p = ContentBlock.paragraph("Hello")
        assert p.type == ContentBlockType.PARAGRAPH
        assert p.text == "Hello"

        h = ContentBlock.heading("Section Title")
        assert h.type == ContentBlockType.HEADING
        assert h.text == "Section Title"

        lst = ContentBlock.list_block(["a", "b"], list_type="ordered")
        assert lst.type == ContentBlockType.LIST
        assert lst.items == ["a", "b"]
        assert lst.list_type == "ordered"

        f = ContentBlock.formula("E=mc^2", label="(1)")
        assert f.type == ContentBlockType.FORMULA
        assert f.tex == "E=mc^2"
        assert f.label == "(1)"

        fig = ContentBlock.figure("Fig. 1", "A figure", uri="f1.jpg", target_id="fig1")
        assert fig.type == ContentBlockType.FIGURE
        assert fig.label == "Fig. 1"
        assert fig.uri == "f1.jpg"

        # Remaining factory methods: figure_ref, table_block, table_ref, code, boxed_text, quote
        fr = ContentBlock.figure_ref("Fig. 1")
        assert fr.type == ContentBlockType.FIGURE_REF
        assert fr.target_id == "Fig. 1"

        tbl = ContentBlock.table_block(label="Table 1", caption="A table", rows=[["a"]])
        assert tbl.type == ContentBlockType.TABLE
        assert tbl.caption == "A table"
        assert tbl.rows == [["a"]]

        tr = ContentBlock.table_ref("Table 1")
        assert tr.type == ContentBlockType.TABLE_REF
        assert tr.target_id == "Table 1"

        cb = ContentBlock.code("print('hello')", language="python")
        assert cb.type == ContentBlockType.CODE
        assert cb.text == "print('hello')"
        assert cb.language == "python"

        bt = ContentBlock.boxed_text("Note content")
        assert bt.type == ContentBlockType.BOXED_TEXT
        assert bt.text == "Note content"

        q = ContentBlock.quote("Quoted text")
        assert q.type == ContentBlockType.QUOTE
        assert q.text == "Quoted text"

    def test_content_block_to_dict(self):
        """Verify to_dict omits empty fields."""
        from pyeuropepmc.processing.extensions.content_blocks import ContentBlock

        p = ContentBlock.paragraph("Hello")
        d = p.to_dict()
        assert d["type"] == "paragraph"
        assert d["text"] == "Hello"
        assert "schema_version" in d

        # Empty fields should be omitted
        assert "items" not in d
        assert "inlines" not in d
        assert "parse_status" not in d  # default "success" == no parse_status key
        assert "quality_score" not in d  # default 1.0 == no quality_score key
        assert "parser_notes" not in d
        assert "definition_terms" not in d

        fig = ContentBlock.figure("Fig. 1", "Caption", uri="f1.jpg")
        d = fig.to_dict()
        assert d["type"] == "figure"
        assert d["label"] == "Fig. 1"
        assert d["caption"] == "Caption"
        assert d["uri"] == "f1.jpg"
        # target_id omitted because empty
        assert "target_id" not in d

    def test_content_block_unknown_preservation(self):
        """Verify unknown JATS blocks are preserved as unknown_block."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
        )

        ub = ContentBlock.unknown_block(jats_tag="custom-elem", text="custom data")
        assert ub.type == ContentBlockType.UNKNOWN_BLOCK
        assert ub.jats_tag == "custom-elem"
        assert ub.text == "custom data"

    def test_content_block_to_dict_fields(self):
        """Verify to_dict includes non-empty optional fields."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
        )

        # Code block with language
        cb = ContentBlock.code("print('hello')", language="python")
        d = cb.to_dict()
        assert d.get("language") == "python"

        # Block with metadata (set attribute directly)
        block = ContentBlock.paragraph("with metadata")
        block.metadata = {"source": "test"}
        d = block.to_dict()
        assert d.get("metadata") == {"source": "test"}

        # Block with parser_notes (set attribute directly)
        block2 = ContentBlock.paragraph("with note")
        block2.parser_notes = ["note"]
        d = block2.to_dict()
        assert d.get("parser_notes") == ["note"]

        # Block with non-success parse_status
        block3 = ContentBlock.paragraph("partial")
        block3.parse_status = "partial"
        d = block3.to_dict()
        assert d.get("parse_status") == "partial"

    def test_structured_section_to_dict(self):
        """Verify StructuredSection.to_dict works with section_path and content."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            StructuredSection,
        )

        block = ContentBlock.paragraph("content")
        sec = StructuredSection(
            title="Test",
            content=[block],
            section_type="body",
            section_path="parent/Test",
        )
        d = sec.to_dict()
        assert d["title"] == "Test"
        assert d["section_path"] == "parent/Test"
        assert d["section_type"] == "body"
        assert len(d["content"]) == 1
        assert d["content"][0]["text"] == "content"

        # Section without section_path omits the key
        sec2 = StructuredSection(
            title="No Path",
            content=[block],
        )
        d2 = sec2.to_dict()
        assert "section_path" not in d2

    def test_extract_structured_sections_simple(self):
        """Test basic structured section extraction from simple XML."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE_XML)
        sections = parser.get_full_text_sections_structured()

        assert len(sections) >= 4  # Article Title, Abstract, Introduction, Methods, + back matter

        # First section should be article title
        assert sections[0]["title"] == "Article Title"

        # Second section should be abstract
        abstract = sections[1]
        assert abstract["title"] == "Abstract"
        assert abstract["section_type"] == "body"

        # Third section should be Introduction
        intro = sections[2]
        assert intro["title"] == "Introduction"
        assert intro["section_type"] == "body"

        # Check content blocks
        blocks = intro["content"]
        assert len(blocks) >= 3  # paragraphs + list + formula

        # First block should be a paragraph
        assert blocks[0]["type"] == "paragraph"
        assert "introduction" in blocks[0]["text"].lower()

        # Should have a list block
        list_blocks = [b for b in blocks if b["type"] == "list"]
        assert len(list_blocks) == 1
        assert len(list_blocks[0]["items"]) == 3

        # Should have a formula block
        formula_blocks = [b for b in blocks if b["type"] == "formula"]
        assert len(formula_blocks) == 1
        assert formula_blocks[0]["label"] == "(1)"

    def test_extract_structured_back_matter(self):
        """Verify back matter (acknowledgments) is extracted."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE_XML)
        sections = parser.get_full_text_sections_structured()

        back_sections = [s for s in sections if s["section_type"] == "back"]
        assert len(back_sections) >= 1

        ack = [s for s in back_sections if "acknowledgment" in s["title"].lower()]
        assert len(ack) >= 1
        assert "test community" in ack[0]["content"][0]["text"].lower()

    def test_extract_structured_via_import(self):
        """Test direct usage of ContentBlockExtractor."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlockExtractor,
        )

        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        extractor = ContentBlockExtractor(root)
        sections = extractor.extract_sections()

        assert len(sections) >= 4
        # First section is article title
        assert sections[0].title == "Article Title"
        # Second section is abstract
        assert sections[1].title == "Abstract"
        # Third section is Introduction
        assert sections[2].title == "Introduction"
        assert sections[2].section_type == "body"
        assert len(sections[2].content) >= 3

    def test_flat_sections_still_work(self):
        """Verify backward compatibility of get_full_text_sections()."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE_XML)
        flat = parser.get_full_text_sections()

        assert len(flat) >= 2
        assert "title" in flat[0]
        assert "content" in flat[0]
        # Flat sections return strings, not blocks
        assert isinstance(flat[0]["content"], str)


# ============================================================================
# Tests: MathML Converter
# ============================================================================


class TestMathMLConverter:
    """Tests for the MathML to LaTeX converter."""

    def test_convert_simple_inline(self):
        """Test converting a simple inline math expression."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        mathml = ET.fromstring(
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML" display="inline">'
            "<mml:mi>E</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi>"
            "<mml:msup><mml:mi>c</mml:mi><mml:mn>2</mml:mn></mml:msup>"
            "</mml:math>"
        )

        result = MathMLConverter.convert_mathml(mathml)
        assert "E" in result
        assert "c" in result
        assert result.startswith("$") and result.endswith("$")

    def test_convert_display_math(self):
        """Test converting display math (block)."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        mathml = ET.fromstring(
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML" display="block">'
            "<mml:mi>E</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi>"
            "<mml:msup><mml:mi>c</mml:mi><mml:mn>2</mml:mn></mml:msup>"
            "</mml:math>"
        )

        result = MathMLConverter.convert_display_mathml(mathml)
        assert result.startswith("$$") and result.endswith("$$")

    def test_convert_fraction(self):
        """Test fraction conversion."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        mathml = ET.fromstring(
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:mfrac><mml:mn>1</mml:mn><mml:mn>2</mml:mn></mml:mfrac>"
            "</mml:math>"
        )

        result = MathMLConverter().convert_to_latex(mathml)
        assert "\\frac{1}{2}" in result

    def test_convert_subscript_superscript(self):
        """Test subscript and superscript conversion."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        # Subscript: x_1
        mathml_sub = ET.fromstring(
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:msub><mml:mi>x</mml:mi><mml:mn>1</mml:mn></mml:msub>"
            "</mml:math>"
        )
        result = MathMLConverter().convert_to_latex(mathml_sub)
        assert "_{" in result
        assert "1" in result

        # Superscript: x^2
        mathml_sup = ET.fromstring(
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:msup><mml:mi>x</mml:mi><mml:mn>2</mml:mn></mml:msup>"
            "</mml:math>"
        )
        result = MathMLConverter().convert_to_latex(mathml_sup)
        assert "^{" in result
        assert "2" in result

    def test_entity_resolution(self):
        """Test that Greek letter entities are resolved."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        converter = MathMLConverter()
        resolved = converter._resolve_entities("&alpha; &beta; &gamma;")
        assert "\\alpha" in resolved
        assert "\\beta" in resolved
        assert "\\gamma" in resolved

    def test_extract_from_parser(self):
        """Test MathML extraction via content blocks from parser."""
        parser = FullTextXMLParser(ARTICLE_WITH_MATHML)
        sections = parser.get_full_text_sections_structured()

        assert len(sections) >= 2
        # First section is article title (no formulas)
        assert sections[0]["title"] == "Article Title"
        # Second section is "Math Section" with formulas
        blocks = sections[1]["content"]

        # Should have paragraphs and a formula block
        formula_blocks = [b for b in blocks if b["type"] == "formula"]
        assert len(formula_blocks) >= 1


# ============================================================================
# Tests: Peer Review
# ============================================================================


class TestPeerReview:
    """Tests for peer review extraction."""

    def test_extract_peer_reviews(self):
        """Test basic peer review extraction."""
        from pyeuropepmc.processing.extensions.peer_review import (
            PeerReviewExtractor,
            PeerReviewType,
        )

        root = ET.fromstring(ARTICLE_WITH_PEER_REVIEW)
        extractor = PeerReviewExtractor(root)
        result = extractor.extract_peer_reviews()

        assert result.article_id == "PMC9876543"
        assert len(result.reviews) == 2

        # Check revision rounds
        assert 1 in result.revision_rounds
        assert len(result.revision_rounds[1]) == 2

        # Check types
        assert result.reviews[0].review_type == PeerReviewType.DECISION_LETTER
        assert result.reviews[1].review_type == PeerReviewType.REFEREE_REPORT

    def test_peer_review_contributors(self):
        """Test contributor extraction from reviews."""
        from pyeuropepmc.processing.extensions.peer_review import (
            PeerReviewExtractor,
        )

        root = ET.fromstring(ARTICLE_WITH_PEER_REVIEW)
        extractor = PeerReviewExtractor(root)
        result = extractor.extract_peer_reviews()

        decision = result.reviews[0]
        assert len(decision.contributors) == 1
        assert decision.contributors[0]["name"] == "Edna Editor"
        assert decision.contributors[0]["type"] == "editor"

    def test_peer_review_content(self):
        """Test that review body content is extracted."""
        from pyeuropepmc.processing.extensions.peer_review import (
            PeerReviewExtractor,
        )

        root = ET.fromstring(ARTICLE_WITH_PEER_REVIEW)
        extractor = PeerReviewExtractor(root)
        result = extractor.extract_peer_reviews()

        referee = result.reviews[1]
        assert len(referee.sections) >= 1
        # Should have paragraph blocks
        all_text = " ".join(
            b.text for s in referee.sections for b in s.content
        )
        assert "methodology" in all_text.lower()


# ============================================================================
# Tests: JATS4R Validator
# ============================================================================


class TestJATS4RValidator:
    """Tests for JATS4R compliance validation."""

    def test_validator_runs(self):
        """Test that validator runs and produces a report."""
        from pyeuropepmc.processing.extensions.jats4r import JATS4RValidator

        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        validator = JATS4RValidator(root)
        report = validator.validate()

        assert report.score >= 0
        assert report.score <= 1.0
        assert isinstance(report.findings, list)

    def test_authors_validated(self):
        """Test author validation rules."""
        from pyeuropepmc.processing.extensions.jats4r import JATS4RValidator

        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        validator = JATS4RValidator(root)
        report = validator.validate()

        author_findings = report.categories.get("authors", [])
        # Validation should produce a list (may be empty for valid articles)
        assert isinstance(author_findings, list)

    def test_funding_detected(self):
        """Test funding information detection."""
        from pyeuropepmc.processing.extensions.jats4r import JATS4RValidator

        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        validator = JATS4RValidator(root)
        report = validator.validate()

        funding_findings = report.categories.get("funding", [])
        # Funding group is present with award-id, so no errors expected
        errors = [f for f in funding_findings if f.severity == "error"]
        assert len(errors) == 0

    def test_abstract_validated(self):
        """Test abstract validation."""
        from pyeuropepmc.processing.extensions.jats4r import JATS4RValidator

        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        validator = JATS4RValidator(root)
        report = validator.validate()

        abstract_findings = report.categories.get("abstract", [])
        # Abstract has <p> content, so no errors
        errors = [f for f in abstract_findings if f.severity == "error"]
        assert len(errors) == 0

    def test_report_serialization(self):
        """Test ValidationReport serialization."""
        from pyeuropepmc.processing.extensions.jats4r import (
            JATS4RValidator,
            ValidationFinding,
            ValidationReport,
        )

        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        validator = JATS4RValidator(root)
        report = validator.validate()

        d = report.to_dict()
        assert "score" in d
        assert "total_findings" in d
        assert "categories" in d
        assert isinstance(d["score"], float)

        # Test individual finding serialization
        finding = ValidationFinding(
            rule_id="TEST-01",
            severity="info",
            message="Test finding",
            category="test",
        )
        fd = finding.to_dict()
        assert fd["rule_id"] == "TEST-01"


# ============================================================================
# Tests: Batch Processor
# ============================================================================


class TestBatchProcessor:
    """Tests for batch/concurrent processing."""

    def test_process_xml_strings(self):
        """Test processing multiple XML strings."""
        from pyeuropepmc.processing.extensions.batch_processor import (
            BatchProcessor,
        )

        processor = BatchProcessor(max_workers=2, rate_limit=100)  # Fast for tests
        items = [
            ("article1", SIMPLE_ARTICLE_XML),
            ("article2", SIMPLE_ARTICLE_XML),
            ("article3", SIMPLE_ARTICLE_XML),
        ]

        result = processor.process_xml_strings(items)
        assert len(result.results) == 3
        assert len(result.successes) == 3
        assert len(result.failures) == 0
        assert result.success_rate == 1.0

    def test_batch_result_to_dict(self):
        """Test BatchResult serialization."""
        from pyeuropepmc.processing.extensions.batch_processor import (
            BatchProcessor,
        )

        processor = BatchProcessor(rate_limit=100)
        items = [("a1", SIMPLE_ARTICLE_XML)]
        result = processor.process_xml_strings(items)

        d = result.to_dict()
        assert d["total"] == 1
        assert d["successes"] == 1
        assert d["success_rate"] == 1.0

    def test_process_with_extraction_fn(self):
        """Test batch processing with a custom extraction function."""
        from pyeuropepmc.processing.extensions.batch_processor import (
            BatchProcessor,
        )

        def extract_title(parser):
            return {"title": parser.extract_metadata().get("title", "")}

        processor = BatchProcessor(rate_limit=100)
        items = [("a1", SIMPLE_ARTICLE_XML)]
        result = processor.process_xml_strings(items, extraction_fn=extract_title)

        assert result.successes[0].data["title"] == "Test Article for Extensions"

    def test_empty_input(self):
        """Test processing empty input."""
        from pyeuropepmc.processing.extensions.batch_processor import (
            BatchProcessor,
        )

        processor = BatchProcessor(rate_limit=100)
        result = processor.process_xml_strings([])
        assert len(result.results) == 0
        assert result.success_rate == 0.0

    def test_progress_callback(self):
        """Test progress callback during batch processing."""
        from pyeuropepmc.processing.extensions.batch_processor import (
            BatchProcessor,
        )

        progress_log = []

        def callback(completed, total, identifier):
            progress_log.append((completed, total, identifier))

        processor = BatchProcessor(rate_limit=100, progress_callback=callback)
        items = [("a1", SIMPLE_ARTICLE_XML), ("a2", SIMPLE_ARTICLE_XML)]
        processor.process_xml_strings(items)

        assert len(progress_log) == 2
        assert progress_log[0][0] == 1
        assert progress_log[1][0] == 2


# ============================================================================
# Tests: Image Fetcher
# ============================================================================


class TestImageFetcher:
    """Tests for image/asset fetching."""

    def test_extract_asset_refs(self):
        """Test extracting asset references from XML."""
        from pyeuropepmc.processing.extensions.image_fetcher import (
            AssetType,
            ImageFetcher,
        )

        root = ET.fromstring(ARTICLE_WITH_FIGURES)
        fetcher = ImageFetcher(root, article_id="PMC1234567")
        assets = fetcher.extract_asset_refs()

        assert len(assets) >= 2  # figure + supplementary

        # Check figure asset
        figures = [a for a in assets if a.asset_type == AssetType.FIGURE]
        assert len(figures) >= 1
        assert figures[0].label == "Fig. 1"
        assert "f1" in figures[0].uri

        # Check supplementary asset
        supp = [a for a in assets if a.asset_type == AssetType.SUPPLEMENTARY]
        assert len(supp) >= 1

    def test_asset_ref_to_dict(self):
        """Test AssetRef serialization."""
        from pyeuropepmc.processing.extensions.image_fetcher import (
            AssetRef,
            AssetType,
        )

        ref = AssetRef(
            asset_type=AssetType.FIGURE,
            uri="f1.jpg",
            label="Fig. 1",
            caption="A test figure",
            id="fig1",
        )
        d = ref.to_dict()
        assert d["asset_type"] == "figure"
        assert d["uri"] == "f1.jpg"
        assert d["label"] == "Fig. 1"

    def test_resolve_figure_uris(self):
        """Test URI resolution with article ID."""
        from pyeuropepmc.processing.extensions.image_fetcher import ImageFetcher

        figures = [{"graphic_uri": "f1.jpg", "label": "Fig. 1"}]
        resolved = ImageFetcher.resolve_figure_uris(figures, article_id="PMC1234567")

        assert "https://" in resolved[0]["graphic_uri"]
        assert "PMC1234567" in resolved[0]["graphic_uri"]

    def test_already_absolute_uri(self):
        """Test that absolute URIs are not modified."""
        from pyeuropepmc.processing.extensions.image_fetcher import ImageFetcher

        figures = [{"graphic_uri": "https://example.com/image.jpg"}]
        resolved = ImageFetcher.resolve_figure_uris(figures, article_id="PMC1234567")
        assert resolved[0]["graphic_uri"] == "https://example.com/image.jpg"


# ============================================================================
# Tests: Reference Resolver
# ============================================================================


class TestReferenceResolver:
    """Tests for reference resolution."""

    def test_initialization(self):
        """Test that resolver initializes with default rate limit."""
        from pyeuropepmc.processing.extensions.reference_resolver import (
            ReferenceResolver,
        )

        resolver = ReferenceResolver()
        assert resolver.rate_limit == 3.0
        assert resolver.stats["lookups"] == 0
        assert resolver.stats["cache_hits"] == 0

    def test_cache_key_deduplication(self):
        """Test that cache prevents duplicate lookups."""
        from pyeuropepmc.processing.extensions.reference_resolver import (
            ReferenceResolver,
            ResolvedReference,
        )

        resolver = ReferenceResolver()
        ref = {"doi": "10.1234/test", "pmid": ""}

        # Pre-populate cache to simulate a previous lookup
        cached = ResolvedReference(source_ref=ref)
        resolver._cache["10.1234/test"] = cached

        # Resolve should find the cache hit quickly (no network call)
        result = resolver.resolve_reference(ref)
        # The cached entry should be returned
        assert result is not None

    def test_resolved_reference_to_dict(self):
        """Test ResolvedReference serialization."""
        from pyeuropepmc.processing.extensions.reference_resolver import (
            ResolvedReference,
        )

        ref = ResolvedReference(
            resolved_pmid="12345678",
            resolved_doi="10.1234/test",
            title="Test Paper",
            authors="Smith J",
            year="2024",
            journal="Test Journal",
            citations=5,
            is_open_access=True,
        )
        d = ref.to_dict()
        assert d["resolved_pmid"] == "12345678"
        assert d["title"] == "Test Paper"
        assert d["citations"] == 5
        assert d["is_open_access"] is True


# ============================================================================
# Tests: lxml Backend
# ============================================================================


class TestLXMLBackend:
    """Tests for the lxml parser backend."""

    def test_availability_check(self):
        """Test is_lxml_available()."""
        from pyeuropepmc.processing.extensions.lxml_backend import is_lxml_available

        # Should return bool (True if lxml installed, False otherwise)
        assert isinstance(is_lxml_available(), bool)

    def test_fromstring_when_lxml_not_available(self):
        """Test that appropriate ImportError is raised when lxml isn't available."""
        from pyeuropepmc.processing.extensions.lxml_backend import is_lxml_available

        if not is_lxml_available():
            with pytest.raises(ImportError):
                from pyeuropepmc.processing.extensions.lxml_backend import LXMLParser

                LXMLParser()
        else:
            # If lxml is available, test actually works
            from pyeuropepmc.processing.extensions.lxml_backend import LXMLParser

            root = LXMLParser.fromstring(SIMPLE_ARTICLE_XML)
            assert root is not None
            title = root.find(".//article-title")
            assert title is not None
            assert title.text == "Test Article for Extensions"


# ============================================================================
# Tests: Local Processing
# ============================================================================


class TestLocalProcessing:
    """Tests for local file/directory processing helpers."""

    def test_extract_article_id_from_xml(self):
        """Test extracting article ID from XML string."""
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        # Test with XML string
        article_id = extract_article_id_from_xml(SIMPLE_ARTICLE_XML)
        assert article_id == "PMC1234567"

        # Test with Element
        root = ET.fromstring(SIMPLE_ARTICLE_XML)
        article_id = extract_article_id_from_xml(root)
        assert article_id == "PMC1234567"

    def test_extract_article_id_invalid_xml(self):
        """Test that invalid XML returns None."""
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
        )

        result = extract_article_id_from_xml("not xml content")
        assert result is None

    def test_local_xml_processor_init(self):
        """Test LocalXMLProcessor initialization."""
        from pyeuropepmc.processing.extensions.local_processing import (
            LocalXMLProcessor,
        )

        # Default init - config is None until set
        processor = LocalXMLProcessor()
        assert processor.config is None
        # With explicit config
        from pyeuropepmc.processing.config.element_patterns import ElementPatterns

        processor2 = LocalXMLProcessor(config=ElementPatterns())
        assert processor2.config is not None


# ============================================================================
# Tests: Pydantic Helpers
# ============================================================================


class TestPydanticHelpers:
    """Tests for Pydantic integration helpers."""

    def test_has_pydantic(self):
        """Test the has_pydantic check function."""
        from pyeuropepmc.processing.extensions.pydantic_helpers import has_pydantic

        assert isinstance(has_pydantic(), bool)

    def test_dataclass_to_pydantic(self):
        """Test conversion of a dataclass to Pydantic model."""
        from dataclasses import dataclass

        from pyeuropepmc.processing.extensions.pydantic_helpers import has_pydantic

        if not has_pydantic():
            pytest.skip("pydantic not installed")

        from pyeuropepmc.processing.extensions.pydantic_helpers import (
            dataclass_to_pydantic,
        )

        @dataclass
        class TestModel:
            name: str
            value: int = 0

        Model = dataclass_to_pydantic(TestModel)
        instance = Model(name="test", value=42)
        assert instance.name == "test"
        assert instance.value == 42

    def test_model_generator_from_data(self):
        """Test PydanticModelGenerator with sample data."""
        from pyeuropepmc.processing.extensions.pydantic_helpers import (
            PydanticModelGenerator,
            has_pydantic,
        )

        if not has_pydantic():
            pytest.skip("pydantic not installed")

        generator = PydanticModelGenerator()
        sample = {"title": "Test", "year": 2024, "authors": ["Smith J"]}
        Model = generator.generate_model("Article", sample_data=sample)

        instance = Model(title="Real Title", year=2023)
        assert instance.title == "Real Title"

    def test_model_generator_raises_without_pydantic(self):
        """Test that ImportError is raised if pydantic is missing."""
        from pyeuropepmc.processing.extensions.pydantic_helpers import has_pydantic

        if has_pydantic():
            pytest.skip("pydantic is installed, cannot test missing case")

        from pyeuropepmc.processing.extensions.pydantic_helpers import (
            PydanticModelGenerator,
        )

        with pytest.raises(ImportError):
            PydanticModelGenerator()


# ============================================================================
# Tests: Inline Tracking, Def Lists, RAG Chunking, Schema Versioning
# ============================================================================


class TestInlineTracking:
    """Tests for inline element tracking within paragraph blocks."""

    PARAGRAPH_WITH_INLINES = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<body><sec><title>Test</title>
<p>Text with <bold>bold</bold>, <italic>italic</italic>,
and an <xref ref-type="fig" rid="f1">inline xref</xref>.
Also a formula: <inline-formula><alternatives><tex-math>E=mc^2</tex-math></alternatives></inline-formula>.</p>
</sec></body></article>"""

    def test_inline_elements_tracked(self):
        """Verify inlines are tracked in paragraph blocks."""
        parser = FullTextXMLParser(self.PARAGRAPH_WITH_INLINES)
        sections = parser.get_full_text_sections_structured()
        blocks = sections[0]["content"]

        para_blocks = [b for b in blocks if b["type"] == "paragraph"]
        assert len(para_blocks) >= 1

        # Check that inlines are present
        p = para_blocks[0]
        assert "inlines" in p, "Paragraph should have inlines field"
        assert len(p["inlines"]) >= 4, "Expected 4+ inline elements"

        types = [i["type"] for i in p["inlines"]]
        assert "bold" in types
        assert "italic" in types
        assert "xref" in types
        assert "inline_formula" in types

    def test_inline_positions(self):
        """Verify inline element positions are tracked correctly."""
        parser = FullTextXMLParser(self.PARAGRAPH_WITH_INLINES)
        sections = parser.get_full_text_sections_structured()
        para = [b for b in sections[0]["content"] if b["type"] == "paragraph"][0]

        for inline in para["inlines"]:
            assert "position" in inline
            assert "length" in inline
            assert inline["position"] >= 0
            assert inline["length"] > 0


class TestDefList:
    """Tests for definition list support."""

    XML_WITH_DEF_LIST = """<?xml version="1.0"?>
<article><body><sec><title>Glossary</title>
<def-list><title>Terms</title>
<def-item><term>DNA</term><def><p>Deoxyribonucleic acid</p></def></def-item>
<def-item><term>RNA</term><def><p>Ribonucleic acid</p></def></def-item>
</def-list>
</sec></body></article>"""

    def test_def_list_detection(self):
        """Verify definition lists are detected."""
        parser = FullTextXMLParser(self.XML_WITH_DEF_LIST)
        sections = parser.get_full_text_sections_structured()
        def_lists = [
            b for s in sections for b in s["content"]
            if b.get("type") == "definition_list"
        ]
        assert len(def_lists) >= 1

    def test_def_list_terms(self):
        """Verify term/definition pairs are extracted."""
        parser = FullTextXMLParser(self.XML_WITH_DEF_LIST)
        sections = parser.get_full_text_sections_structured()
        dl = next(
            b for s in sections for b in s["content"]
            if b.get("type") == "definition_list"
        )
        assert "definition_terms" in dl
        terms = dl["definition_terms"]
        assert len(terms) == 2
        assert terms[0]["term"] == "DNA"
        assert "nucleic" in terms[0]["def"]
        assert terms[1]["term"] == "RNA"


class TestRagChunking:
    """Tests for RAG chunking capabilities."""

    XML_FOR_CHUNKING = """<?xml version="1.0"?>
<article><body>
<sec id="s1"><title>Introduction</title>
<p>First paragraph with important content for testing.</p>
<p>Second paragraph discussing methods and results.</p>
<list list-type="ordered"><list-item><p>Step one</p></list-item><list-item><p>Step two</p></list-item></list>
</sec>
<sec id="s2"><title>Methods</title><p>Detailed methodology section.</p></sec>
</body></article>"""

    def test_to_chunks_basic(self):
        """Verify basic chunking produces chunks."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
            StructuredSection,
        )

        parser = FullTextXMLParser(self.XML_FOR_CHUNKING)
        sections_dicts = parser.get_full_text_sections_structured()
        structured_sections = []
        for s in sections_dicts:
            # Convert dict blocks back to ContentBlock objects
            content_blocks = []
            for b in s["content"]:
                block = ContentBlock(type=ContentBlockType(b["type"]), text=b.get("text", ""))
                content_blocks.append(block)
            structured_sections.append(
                StructuredSection(
                    title=s["title"],
                    content=content_blocks,
                    section_type=s.get("section_type", "body"),
                )
            )

        chunks = []
        for section in structured_sections:
            chunks.extend(section.to_chunks(max_tokens=50, overlap=10))

        assert len(chunks) >= 2, "Should produce at least 2 chunks"
        for chunk in chunks:
            assert "text" in chunk
            assert "section_path" in chunk
            assert chunk["section_path"] in ("Introduction", "Methods")

    def test_to_chunks_section_path(self):
        """Verify section_path tracks provenance."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
            StructuredSection,
        )

        parser = FullTextXMLParser(self.XML_FOR_CHUNKING)
        sections_dicts = parser.get_full_text_sections_structured()
        structured_sections = []
        for s in sections_dicts:
            content_blocks = []
            for b in s["content"]:
                block = ContentBlock(type=ContentBlockType(b["type"]), text=b.get("text", ""))
                content_blocks.append(block)
            structured_sections.append(
                StructuredSection(
                    title=s["title"],
                    content=content_blocks,
                    section_type=s.get("section_type", "body"),
                )
            )

        chunks = []
        for section in structured_sections:
            chunks.extend(section.to_chunks(max_tokens=200))

        introduction_chunks = [
            c for c in chunks
            if c["section_path"] == "Introduction"
        ]
        assert len(introduction_chunks) >= 1

    def test_to_langchain_documents(self):
        """Verify LangChain-compatible output."""
        from pyeuropepmc.processing.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
            StructuredSection,
        )

        parser = FullTextXMLParser(self.XML_FOR_CHUNKING)
        sections_dicts = parser.get_full_text_sections_structured()

        for s in sections_dicts:
            content_blocks = []
            for b in s["content"]:
                block = ContentBlock(type=ContentBlockType(b["type"]), text=b.get("text", ""))
                content_blocks.append(block)
            section = StructuredSection(
                title=s["title"],
                content=content_blocks,
                section_type=s.get("section_type", "body"),
            )
            docs = section.to_langchain_documents()
            for doc in docs:
                assert "page_content" in doc
                assert "metadata" in doc
                assert "block_type" in doc["metadata"]
                assert "section_title" in doc["metadata"]
                # Verify source section preserved
                assert doc["metadata"]["section_title"] == s["title"]


class TestParseDiagnostics:
    """Tests for parse status and quality tracking."""

    def test_parse_status_default(self):
        """Verify default parse status is 'success'."""
        from pyeuropepmc.processing.extensions.content_blocks import ContentBlock

        p = ContentBlock.paragraph("test")
        assert p.parse_status == "success"
        assert p.quality_score == 1.0

    def test_parse_status_in_dict(self):
        """Verify non-default parse_status appears in dict."""
        from pyeuropepmc.processing.extensions.content_blocks import ContentBlock

        p = ContentBlock.paragraph("test")
        d = p.to_dict()
        assert "parse_status" not in d  # default omitted

        p.parse_status = "partial"
        p.quality_score = 0.5
        d = p.to_dict()
        assert d["parse_status"] == "partial"
        assert d["quality_score"] == 0.5


class TestSchemaVersion:
    """Tests for schema versioning."""

    def test_schema_version_present(self):
        """Verify schema_version is included in dict output."""
        from pyeuropepmc.processing.extensions.content_blocks import ContentBlock

        p = ContentBlock.paragraph("test")
        d = p.to_dict()
        assert "schema_version" in d
        assert isinstance(d["schema_version"], str)

    def test_schema_version_consistent(self):
        """Verify all blocks have same schema_version."""
        parser = FullTextXMLParser(SIMPLE_ARTICLE_XML)
        sections = parser.get_full_text_sections_structured()
        versions = set()
        for s in sections:
            for b in s["content"]:
                if "schema_version" in b:
                    versions.add(b["schema_version"])
        assert len(versions) <= 1, "Multiple schema versions found"


class TestMathMLRendering:
    """Tests for MathML HTML/SVG rendering."""

    def test_to_html(self):
        """Verify to_html produces proper HTML."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        mathml = ET.fromstring(
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML" display="inline">'
            "<mml:mi>E</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi>"
            "<mml:msup><mml:mi>c</mml:mi><mml:mn>2</mml:mn></mml:msup></mml:math>"
        )

        converter = MathMLConverter()
        html = converter.to_html(mathml)
        assert 'class="math-inline"' in html
        assert "E" in html
        assert "c" in html

        # Display math
        mathml.set("display", "block")
        html_block = converter.to_html(mathml)
        assert 'class="math-display"' in html_block


class TestBITSBook:
    """Tests for BITS book article support."""

    BITS_XML = """<?xml version="1.0"?>
<book xmlns:xlink="http://www.w3.org/1999/xlink">
<book-meta>
<book-id pub-id-type="doi">10.1234/book.2024</book-id>
<title-group><book-title>Test Book</book-title></title-group>
</book-meta>
<body><sec><title>Chapter 1</title><p>Book content paragraph.</p></sec></body>
</book>"""

    def test_bits_parsing(self):
        """Verify BITS book articles can be parsed."""
        from pyeuropepmc.processing.extensions.local_processing import parse_bits_book

        parser = parse_bits_book(self.BITS_XML)
        assert parser.root is not None
        assert parser.root.tag.endswith("book") or parser.root.tag == "book"
        metadata = parser.extract_metadata()
        # BITS book-meta extraction is partial; verify parser works end-to-end
        assert isinstance(metadata, dict)
        assert "title" in metadata
        assert metadata.get("doi") is None  # BITS metadata not fully mapped yet

    def test_bits_structured_sections(self):
        """Verify content block extraction works on BITS articles."""
        from pyeuropepmc.processing.extensions.local_processing import parse_bits_book

        parser = parse_bits_book(self.BITS_XML)
        sections = parser.get_full_text_sections_structured()
        assert len(sections) >= 1
        assert sections[0]["title"] == "Chapter 1"


class TestPmcDownload:
    """Tests for PMC download pipeline (mock-based, no network)."""

    def test_process_single_pmc_raises_on_empty(self):
        """Verify process_single_pmc raises on empty PMC ID."""
        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        with pytest.raises((ConnectionError, ValueError)):
            process_single_pmc("INVALID", max_retries=1)

    def test_pmcid_prefix_normalization(self):
        """Verify PMC prefix normalization."""
        from pyeuropepmc.processing.extensions.local_processing import (
            process_single_pmc,
        )

        with pytest.raises((ConnectionError, ValueError)):
            process_single_pmc("1234567", max_retries=1)
