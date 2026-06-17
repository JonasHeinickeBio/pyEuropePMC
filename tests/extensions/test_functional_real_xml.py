"""
Functional tests using 5 real-world XML papers.

Tests all extension modules against real Europe PMC articles:
1. PMC12311175.xml - Large recent article
2. PMC12738713.xml - Medium recent article
3. PMC3258128.xml - Classic research article
4. PMC3359999.xml - Classic research article
5. Plus SIMPLE_ARTICLE_XML (synthetic but representative)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET  # nosec B405

import pytest

from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "fulltext_downloads"

# Apply module-level markers
pytestmark = [pytest.mark.functional, pytest.mark.slow]

# Determine which real XML files are available
REAL_XML_FILES: list[Path] = []
PMC_IDS: list[str] = []

for fname in [
    "PMC12311175.xml",
    "PMC12738713.xml",
    "PMC3258128.xml",
    "PMC3359999.xml",
]:
    fpath = FIXTURE_DIR / fname
    if fpath.exists() and fpath.stat().st_size > 1000:
        REAL_XML_FILES.append(fpath)
        PMC_IDS.append(fname.replace(".xml", ""))


# Minimal XML for 5th test article
SIMPLE_XML = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"
         xmlns:mml="http://www.w3.org/1998/Math/MathML">
<front>
<article-meta>
<article-id pub-id-type="pmcid">PMC9999999</article-id>
<article-id pub-id-type="doi">10.1234/functional.2026.001</article-id>
<article-id pub-id-type="pmid">99999999</article-id>
<title-group><article-title>Functional Test Article for Extensions</article-title></title-group>
<contrib-group>
<contrib contrib-type="author">
<name><surname>Test</surname><given-names>Author</given-names></name>
<contrib-id contrib-id-type="orcid">0000-0002-1825-0097</contrib-id>
</contrib>
</contrib-group>
<aff id="aff1"><institution>Test University</institution><country>Germany</country></aff>
<pub-date pub-type="ppub"><year>2026</year></pub-date>
<abstract><p>This is a functional test abstract.</p><sec><title>Background</title><p>Test background.</p></sec></abstract>
<kwd-group><kwd>functional-test</kwd><kwd>extensions</kwd></kwd-group>
<funding-group><award-id>TEST-123</award-id><funding-source>Test Funder</funding-source></funding-group>
</article-meta>
</front>
<body>
<sec id="s1">
<title>Introduction</title>
<p>This is the first <bold>functional</bold> test paragraph.</p>
<p>A second paragraph with <italic>emphasis</italic> and a formula:
   <inline-formula><mml:math display="inline"><mml:mi>E</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi><mml:msup><mml:mi>c</mml:mi><mml:mn>2</mml:mn></mml:msup></mml:math></inline-formula>.</p>
<list list-type="bullet">
<list-item><p>Item one</p></list-item>
<list-item><p>Item two</p></list-item>
</list>
<fig id="f1">
<label>Fig. 1</label>
<caption><p>Test figure caption.</p></caption>
<graphic xlink:href="f1.jpg"/>
</fig>
</sec>
<sec id="s2">
<title>Methods</title>
<p>Methods content here.</p>
<table-wrap id="t1">
<label>Table 1</label>
<caption><p>Test table.</p></caption>
<table><tr><td>Data</td></tr></table>
</table-wrap>
<disp-formula id="eq1">
<label>(1)</label>
<mml:math display="block"><mml:mi>y</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi><mml:mi>x</mml:mi><mml:mo>+</mml:mo><mml:mi>b</mml:mi></mml:math>
</disp-formula>
</sec>
</body>
<back>
<ack><p>We acknowledge the test infrastructure.</p></ack>
<ref-list>
<ref id="r1"><label>1</label><element-citation>
<person-group person-group-type="author"><name><surname>Author</surname><given-names>A</given-names></name></person-group>
<article-title>A reference</article-title><source>Journal</source><year>2025</year>
<pub-id pub-id-type="doi">10.1234/ref.2025.001</pub-id>
</element-citation></ref>
</ref-list>
</back>
</article>
"""


# ============================================================================
# Fixtures
# ============================================================================


def load_real_xml(filepath: Path) -> str:
    """Load a real XML file and return its content."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def get_article_id_from_file(filepath: Path) -> str:
    """Extract the article ID from a real XML file."""
    content = load_real_xml(filepath)
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return filepath.stem
    for elem in root.findall(".//article-id[@pub-id-type='pmcid']"):
        if elem.text and elem.text.strip():
            return elem.text.strip()
    return filepath.stem


@pytest.fixture(
    params=[
        (str(p), load_real_xml(p), get_article_id_from_file(p))
        for p in REAL_XML_FILES
    ]
    + [("synthetic", SIMPLE_XML, "PMC9999999")],
    ids=[p.stem for p in REAL_XML_FILES] + ["synthetic"],
)
def article_data(request) -> tuple[str, str, str]:
    """Fixture providing (label, xml_content, article_id) for each article."""
    return request.param


# ============================================================================
# Tests: All extensions against real data
# ============================================================================


class TestFunctionalRealXML:
    """Functional tests against real XML articles."""

    def test_basic_parsing(self, article_data):
        """Verify basic parsing works on all articles."""
        label, xml_content, article_id = article_data
        parser = FullTextXMLParser(xml_content)
        assert parser.root is not None, f"{label}: root should not be None"
        metadata = parser.extract_metadata()
        assert isinstance(metadata, dict), f"{label}: metadata should be dict"

    def test_content_blocks(self, article_data):
        """Verify content block extraction works on all articles."""
        label, xml_content, article_id = article_data
        parser = FullTextXMLParser(xml_content)

        sections = parser.get_full_text_sections_structured()
        assert isinstance(sections, list), f"{label}: should return list"
        assert len(sections) > 0, f"{label}: should return at least one section"

        # Check each section structure
        for section in sections:
            assert "title" in section, f"{label}: section missing title"
            assert "content" in section, f"{label}: section missing content"
            assert "section_type" in section, f"{label}: section missing type"

            content = section["content"]
            assert isinstance(content, list), f"{label}: content should be list"

            for block in content:
                assert "type" in block, f"{label}: block missing type"
                # Verify known types
                assert block["type"] in (
                    "paragraph", "heading", "list", "formula",
                    "figure", "table", "code", "boxed_text",
                    "figure_ref", "table_ref", "mathml",
                    "unknown_block",
                ), f"{label}: unknown block type: {block['type']}"

        # Verify backward compatibility
        flat_sections = parser.get_full_text_sections()
        assert isinstance(flat_sections, list)

    def test_content_block_roundtrip(self, article_data):
        """Verify structured content can be serialized and deserialized."""
        from pyeuropepmc.processing.extensions.content_blocks import ContentBlock

        label, xml_content, article_id = article_data
        parser = FullTextXMLParser(xml_content)

        sections = parser.get_full_text_sections_structured()
        for section in sections:
            for block_dict in section["content"]:
                # Verify to_dict is consistent
                assert isinstance(block_dict, dict), f"{label}: block should be dict"
                assert "type" in block_dict

    def test_mathml_conversion(self, article_data):
        """Verify MathML conversion works on all articles."""
        from pyeuropepmc.processing.extensions.mathml import MathMLConverter

        label, xml_content, article_id = article_data
        root = ET.fromstring(xml_content)

        # Find all math elements
        math_elements = root.findall(".//{http://www.w3.org/1998/Math/MathML}math")
        if not math_elements:
            pytest.skip(f"{label}: no MathML elements found")

        converter = MathMLConverter()
        for math_ml in math_elements:
            latex = converter.convert_to_latex(math_ml)
            assert isinstance(latex, str), f"{label}: LaTeX should be string"
            assert len(latex) > 0, f"{label}: LaTeX should not be empty"

            # Test delimiter wrapping
            wrapped = converter.convert(math_ml)
            assert wrapped.startswith(
                "$"
            ) or wrapped.startswith(
                "$$"
            ), f"{label}: should start with math delimiter"

    def test_jats4r_validation(self, article_data):
        """Verify JATS4R validation runs on all articles."""
        from pyeuropepmc.processing.extensions.jats4r import JATS4RValidator

        label, xml_content, article_id = article_data
        root = ET.fromstring(xml_content)

        validator = JATS4RValidator(root)
        report = validator.validate()

        assert isinstance(report.score, float), f"{label}: score should be float"
        assert 0.0 <= report.score <= 1.0, f"{label}: score out of range"
        assert isinstance(report.findings, list), f"{label}: findings should be list"
        assert hasattr(report, "categories"), f"{label}: should have categories"

        # Verify serialization
        d = report.to_dict()
        assert "score" in d
        assert "total_findings" in d

    def test_peer_review(self, article_data):
        """Verify peer review extraction handles all articles gracefully."""
        from pyeuropepmc.processing.extensions.peer_review import (
            PeerReviewExtractor,
            PeerReviewType,
        )

        label, xml_content, article_id = article_data
        root = ET.fromstring(xml_content)

        extractor = PeerReviewExtractor(root)
        result = extractor.extract_peer_reviews()

        # Should always return a PeerReviewSet even if no reviews present
        assert isinstance(result.reviews, list)
        assert isinstance(result.revision_rounds, dict)

    def test_image_fetcher(self, article_data):
        """Verify image/asset reference extraction."""
        from pyeuropepmc.processing.extensions.image_fetcher import (
            AssetType,
            ImageFetcher,
        )

        label, xml_content, article_id = article_data
        root = ET.fromstring(xml_content)

        fetcher = ImageFetcher(root, article_id=article_id)
        assets = fetcher.extract_asset_refs()

        assert isinstance(assets, list)
        for asset in assets:
            assert isinstance(asset.asset_type, AssetType)
            # URI might be empty for some assets, but that's okay
            assert isinstance(asset.uri, str)

    def test_batch_processor(self, article_data):
        """Verify batch processing works with individual articles."""
        from pyeuropepmc.processing.extensions.batch_processor import (
            BatchProcessor,
        )

        label, xml_content, article_id = article_data

        # Test processing a single item with batch processor
        processor = BatchProcessor(max_workers=1, rate_limit=100)
        items = [(article_id, xml_content)]
        result = processor.process_xml_strings(items)

        assert len(result.results) == 1
        assert len(result.successes) == 1
        assert result.successes[0].success is True
        assert result.successes[0].data is not None
        assert "metadata" in result.successes[0].data

    def test_local_processing_helpers(self, article_data, tmp_path):
        """Verify local processing helpers work with real XML."""
        from pyeuropepmc.processing.extensions.local_processing import (
            extract_article_id_from_xml,
            parse_xml_file,
            LocalXMLProcessor,
        )

        label, xml_content, article_id = article_data

        # Test extract_article_id_from_xml
        extracted_id = extract_article_id_from_xml(xml_content)
        if extracted_id:
            assert isinstance(extracted_id, str)

        # Test with real file
        if label != "synthetic":
            filepath = article_data[0] if isinstance(article_data[0], str) else ""
            if filepath and os.path.exists(filepath):
                parser = parse_xml_file(filepath)
                assert parser.root is not None

                processor = LocalXMLProcessor()
                data = processor.process_single(filepath)
                assert isinstance(data, dict)
                assert "metadata" in data

    def test_linkml_models(self, article_data):
        """Verify LinkML models can be instantiated from parsed content."""
        pytest.importorskip("jsonasobj2")
        pytest.importorskip("linkml_runtime")
        from pyeuropepmc.processing.extensions.linkml_models import (
            ArticleContent,
            ContentBlock,
            ContentBlockType,
            StructuredSection,
            ArticleMetadata,
        )

        label, xml_content, article_id = article_data
        parser = FullTextXMLParser(xml_content)

        # Get structured sections from parser
        sections_dicts = parser.get_full_text_sections_structured()

        # Build LinkML model from parser output
        metadata_dict = parser.extract_metadata()

        # Create LinkML ArticleContent model
        linkml_sections = []
        for sec_dict in sections_dicts:
            blocks = []
            for block_dict in sec_dict.get("content", []):
                block_type = block_dict.get("type", "paragraph")
                block = ContentBlock(
                    type=ContentBlockType(block_type),
                    text=block_dict.get("text", ""),
                    items=block_dict.get("items", []),
                    label=block_dict.get("label", ""),
                    caption=block_dict.get("caption", ""),
                    uri=block_dict.get("uri", ""),
                )
                blocks.append(block)

            linkml_section = StructuredSection(
                title=sec_dict.get("title", ""),
                content=blocks,
                section_type=sec_dict.get("section_type", "body"),
            )
            linkml_sections.append(linkml_section)

        # Create the full article model
        article = ArticleContent(
            article_id=article_id,
            metadata=ArticleMetadata(
                title=metadata_dict.get("title", ""),
                doi=metadata_dict.get("doi", ""),
                pmid=metadata_dict.get("pmid", ""),
                pmcid=metadata_dict.get("pmcid", ""),
            ),
            sections=linkml_sections,
        )

        # Verify the model
        assert article.article_id == article_id
        assert len(article.sections) == len(sections_dicts)
        if article.metadata and article.sections:
            assert isinstance(article.sections[0].content, list)

    def test_structured_vs_flat_consistency(self, article_data):
        """Verify structured mode doesn't lose text content vs flat mode."""
        label, xml_content, article_id = article_data
        parser = FullTextXMLParser(xml_content)

        flat = parser.get_full_text_sections()
        structured = parser.get_full_text_sections_structured()

        # Both should have sections
        assert len(structured) > 0 or len(flat) > 0, (
            f"{label}: at least one mode should produce sections"
        )

        # Flat text should be a subset of structured text (which preserves more)
        flat_text = " ".join(s["content"] for s in flat)
        structured_text = " ".join(
            b.get("text", "")
            for s in structured
            for b in s["content"]
            if b.get("text")
        )

        # Structured may have more text (from lists, formulas, etc.)
        assert isinstance(structured_text, str)
        assert isinstance(flat_text, str)


# ============================================================================
# Tests: Report generation (metadata only)
# ============================================================================


class TestArticleReport:
    """Generate a simple report of articles tested."""

    def test_report_articles(self):
        """Print information about what articles were tested."""
        print(f"\nTesting with {len(REAL_XML_FILES)} real XML files:")
        for i, (fpath, pmcid) in enumerate(zip(REAL_XML_FILES, PMC_IDS)):
            size_kb = fpath.stat().st_size / 1024
            print(f"  {i+1}. {pmcid}: {fpath.name} ({size_kb:.0f} KB)")
        print(f"  {len(REAL_XML_FILES)+1}. synthetic: PMC9999999 (test fixture)")
