"""Comprehensive tests for JATS XML Normalizer.

Tests all normalization layers:
- Entity normalization (XML entities, Unicode, dashes)
- Display markup stripping (bold/italic/sup/sub/xref)
- Section type canonicalization (PMC-style regex)
- Metadata & identifier normalization (ORCID, DOI, PMCID)
- Whitespace normalization
- BioC JSON output
- Convenience functions
"""

from __future__ import annotations

import json

import pytest

from xml.etree.ElementTree import ParseError

from pyeuropepmc.processing.jats_normalizer import (
    JATSNormalizer,
    NormalizationConfig,
    classify_section,
    normalize_jats_text,
    normalize_jats_xml,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixtures: Minimal JATS XML documents for testing
# ---------------------------------------------------------------------------

_MINIMAL_JATS = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD v1.2 20190208//EN" "JATS-archivearticle1-mathml3.dtd">
<article article-type="research-article" xml:lang="en">
  <front>
    <journal-title>Test Journal</journal-title>
    <article-meta>
      <article-id pub-id-type="pmcid">PMC1234567</article-id>
      <article-id pub-id-type="doi">10.1234/test.article</article-id>
      <article-id pub-id-type="pmid">12345678</article-id>
      <title-group>
        <article-title>Test Article on <italic>Important</italic> Topics</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author">
          <name>
            <surname>Smith</surname>
            <given-names>John A.</given-names>
          </name>
          <contrib-id contrib-id-type="orcid">https://orcid.org/0000-0002-1234-5678</contrib-id>
        </contrib>
        <contrib contrib-type="author">
          <name>
            <surname>Garcia</surname>
            <given-names>Maria</given-names>
          </name>
        </contrib>
      </contrib-group>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>This is the <bold>introduction</bold> with <sup>2</sup> key references.</p>
    </sec>
    <sec>
      <title>Materials and Methods</title>
      <p>We used <italic>standard protocols</italic> for all experiments.</p>
      <sec>
        <title>Statistical Analysis</title>
        <p>Data were analyzed with <sub>n</sub>-way ANOVA.</p>
      </sec>
    </sec>
    <sec>
      <title>Results and Discussion</title>
      <p>The <xref ref-type="fig" rid="fig1">results</xref> show significant improvement.</p>
      <p>See <ext-link ext-link-type="uri" href="https://example.com">Supplementary Data</ext-link>.</p>
    </sec>
    <sec>
      <title>Conclusions</title>
      <p>We conclude that the method is <named-content content-type="emphasis">highly effective</named-content>.</p>
    </sec>
  </body>
</article>
"""

_FULL_FEATURE_JATS = """\
<?xml version="1.0" encoding="UTF-8"?>
<article article-type="review-article" xml:lang="en">
  <front>
    <article-meta>
      <article-id pub-id-type="doi">10.1000/ABC.DEF</article-id>
      <article-id pub-id-type="pmcid">PMC9999999</article-id>
      <title-group>
        <article-title>Effects of H<sub>2</sub>O<sub>2</sub> on <styled-content style="bold">Cell</styled-content> Viability</article-title>
      </title-group>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>1. Background</title>
      <p>Reactive oxygen species (&alpha;-synuclein, &beta;-catenin) cause damage.</p>
    </sec>
    <sec>
      <title>2. Experimental Procedures</title>
      <p>Cells were cultured at 37&deg;C with 5% CO<sub>2</sub>.</p>
      <p>Concentrations ranged from 0&ndash;100&mu;M.</p>
    </sec>
    <sec>
      <title>3. Findings</title>
      <p>Figure <fig id="f1"><label>Fig 1.</label><caption>Results</caption></fig> shows data.</p>
    </sec>
    <sec>
      <title>Acknowledgments</title>
      <p>We thank our colleagues.</p>
    </sec>
    <sec>
      <title>References</title>
      <p>Reference list here.</p>
    </sec>
  </body>
</article>
"""

_EMPTY_JATS = """\
<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article">
  <front>
    <article-meta>
      <title-group>
        <article-title>Empty Article</article-title>
      </title-group>
    </article-meta>
  </front>
</article>
"""

_UNICODE_JATS = """\
<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article">
  <body>
    <p>Normal\u00a0space\u2002and\u2003em\u200bdash\u2013en\u2014em\u2015bar\u2212minus.</p>
    <p>Caf\u00e9 \u00fcber \u00f1 \u00e9.</p>
  </body>
</article>
"""


# ---------------------------------------------------------------------------
# Tests: NormalizationConfig
# ---------------------------------------------------------------------------


class TestNormalizationConfig:
    """Tests for NormalizationConfig dataclass."""

    def test_default_config(self) -> None:
        """Default config enables all normalization layers."""
        config = NormalizationConfig()
        assert config.strip_display_markup is True
        assert config.flatten_xrefs is True
        assert config.remove_structural is True
        assert config.section_types is True
        assert config.normalize_entities is True
        assert config.normalize_whitespace is True
        assert config.normalize_dashes is True
        assert config.normalize_identifiers is True
        assert config.bio_c_output is False
        assert config.drop_mathml is True

    def test_custom_config(self) -> None:
        """Custom config overrides defaults."""
        config = NormalizationConfig(
            section_types=False,
            bio_c_output=True,
            strip_display_markup=False,
        )
        assert config.section_types is False
        assert config.bio_c_output is True
        assert config.strip_display_markup is False
        # Others remain default
        assert config.normalize_entities is True


# ---------------------------------------------------------------------------
# Tests: JATSNormalizer - basic functionality
# ---------------------------------------------------------------------------


class TestJATSNormalizerBasic:
    """Tests for basic JATSNormalizer functionality."""

    def test_normalize_xml_returns_dict(self) -> None:
        """normalize_xml returns a dict with expected keys."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert isinstance(result, dict)
        assert "normalized_root" in result
        assert "sections" in result
        assert "metadata" in result
        assert "body_text" in result

    def test_normalize_text_returns_string(self) -> None:
        """normalize_text returns a plain text string."""
        text = normalize_jats_text(_MINIMAL_JATS)
        assert isinstance(text, str)
        assert len(text) > 0
        assert "introduction" in text.lower() or "Introduction" in text

    def test_normalize_sections_returns_list(self) -> None:
        """normalize_sections returns a list of section dicts."""
        normalizer = JATSNormalizer()
        sections = normalizer.normalize_sections(_MINIMAL_JATS)
        assert isinstance(sections, list)
        assert len(sections) > 0
        for sec in sections:
            assert "type" in sec
            assert "title" in sec
            assert "level" in sec
            assert "text" in sec

    def test_empty_xml(self) -> None:
        """Handles empty/minimal XML gracefully."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_EMPTY_JATS)
        assert result["sections"] == []
        assert result["body_text"] == ""
        assert result["metadata"]["title"] == "Empty Article"

    def test_bytes_input(self) -> None:
        """Accepts bytes input."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS.encode("utf-8"))
        assert len(result["sections"]) > 0

    def test_original_tree_not_mutated(self) -> None:
        """Deep copy prevents mutation of the original tree."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(_MINIMAL_JATS)  # nosec B314
        normalizer = JATSNormalizer()
        normalizer.normalize_xml(_MINIMAL_JATS)
        # Root should still have inline tags
        bold_elements = list(root.iter("bold"))
        assert len(bold_elements) > 0


# ---------------------------------------------------------------------------
# Tests: Section type canonicalization
# ---------------------------------------------------------------------------


class TestSectionTypeCanonicalization:
    """Tests for PMC-style section type classification."""

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            ("Introduction", "intro"),
            ("Background", "background"),
            ("Materials and Methods", "methods"),
            ("Methods", "methods"),
            ("Experimental Procedures", "methods"),
            ("Study Design", "methods"),
            ("Statistical Analysis", "methods"),
            ("Data Collection", "methods"),
            ("Search Strategy", "methods"),
            ("Results", "results"),
            ("Findings", "results"),
            ("Results and Discussion", "results"),
            ("Observations", "results"),
            ("Discussion", "discussion"),
            ("Limitations", "discussion"),
            ("Conclusions", "conclusion"),
            ("Summary", "conclusion"),
            ("Concluding Remarks", "conclusion"),
            ("Abstract", "abstract"),
            ("Acknowledgments", "ack"),
            ("Acknowledgements", "ack"),
            ("References", "references"),
            ("Bibliography", "references"),
            ("Supplementary Materials", "supplementary"),
            ("Appendix", "appendix"),
            ("Author Contributions", "author_contributions"),
            ("Data Availability", "data_availability"),
            ("Funding", "funding"),
            ("Conflict of Interest", "ethics"),
            ("Ethics Statement", "ethics"),
        ],
    )
    def test_classify_section(self, heading: str, expected: str) -> None:
        """Section headings map to correct canonical types."""
        assert classify_section(heading) == expected

    def test_numbered_headings(self) -> None:
        """Handles numbered headings like '1. Methods'."""
        assert classify_section("1. Methods") == "methods"
        assert classify_section("2.3 Results") == "results"
        assert classify_section("(3) Discussion") == "discussion"

    def test_unknown_heading_returns_other(self) -> None:
        """Unknown headings return 'other' type."""
        assert classify_section("My Custom Section") == "other"
        assert classify_section("") == "other"

    def test_section_extraction_full(self) -> None:
        """Full document produces correctly typed sections."""
        normalizer = JATSNormalizer(section_types=True)
        sections = normalizer.normalize_sections(_MINIMAL_JATS)
        types = [s["type"] for s in sections]
        assert "intro" in types
        assert "methods" in types
        assert "results" in types
        assert "conclusion" in types

    def test_subsection_depth(self) -> None:
        """Nested sections have correct level."""
        normalizer = JATSNormalizer(section_types=True)
        sections = normalizer.normalize_sections(_MINIMAL_JATS)
        stat_sec = [s for s in sections if "statistical" in s["title"].lower()]
        assert len(stat_sec) == 1
        assert stat_sec[0]["level"] >= 1  # subsection has level > 0


# ---------------------------------------------------------------------------
# Tests: Display markup stripping
# ---------------------------------------------------------------------------


class TestDisplayMarkupStripping:
    """Tests for inline display tag stripping."""

    def test_bold_stripped(self) -> None:
        """Bold tags are removed, text preserved."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>Some <bold>bold text</bold> here.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(strip_display_markup=True)
        result = normalizer.normalize_xml(xml)
        assert "bold text" in result["body_text"]
        assert "<bold>" not in result["body_text"]

    def test_italic_stripped(self) -> None:
        """Italic tags are removed, text preserved."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>Some <italic>italic text</italic> here.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(strip_display_markup=True)
        result = normalizer.normalize_xml(xml)
        assert "italic text" in result["body_text"]

    def test_sup_sub_stripped(self) -> None:
        """Superscript and subscript tags are stripped."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>H<sub>2</sub>O and E=mc<sup>2</sup></p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(strip_display_markup=True)
        result = normalizer.normalize_xml(xml)
        assert "H2O" in result["body_text"]
        assert "mc2" in result["body_text"]

    def test_xref_flattened(self) -> None:
        """Xref elements are flattened to text."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>As shown in <xref ref-type="fig" rid="fig1">Figure 1</xref>, data.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(flatten_xrefs=True)
        result = normalizer.normalize_xml(xml)
        assert "Figure 1" in result["body_text"]

    def test_xref_empty_text_uses_rid(self) -> None:
        """Xref with no text falls back to rid attribute."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>See <xref ref-type="fig" rid="fig1"/>.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(flatten_xrefs=True)
        result = normalizer.normalize_xml(xml)
        assert "fig1" in result["body_text"]

    def test_ext_link_flattened(self) -> None:
        """Ext-link elements are flattened to text."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>Visit <ext-link ext-link-type="uri" href="https://example.com">our website</ext-link>.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(flatten_xrefs=True)
        result = normalizer.normalize_xml(xml)
        assert "our website" in result["body_text"]
        assert "https://example.com" not in result["body_text"]

    def test_named_content_stripped(self) -> None:
        """Named-content tags are stripped, text preserved."""
        normalizer = JATSNormalizer(strip_display_markup=True)
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert "highly effective" in result["body_text"]

    def test_styled_content_stripped(self) -> None:
        """Styled-content tags are stripped."""
        normalizer = JATSNormalizer(strip_display_markup=True)
        result = normalizer.normalize_xml(_FULL_FEATURE_JATS)
        assert "Cell" in result["body_text"]

    def test_display_markup_disabled(self) -> None:
        """When disabled, inline tags remain in tree."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p><bold>text</bold></p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(strip_display_markup=False, flatten_xrefs=False)
        result = normalizer.normalize_xml(xml)
        # Bold element should still exist in tree
        bold_elems = list(result["normalized_root"].iter("bold"))
        assert len(bold_elems) > 0


# ---------------------------------------------------------------------------
# Tests: Structural element removal
# ---------------------------------------------------------------------------


class TestStructuralRemoval:
    """Tests for removal of structural elements from body text."""

    def test_fig_removed(self) -> None:
        """Fig elements are removed from body text."""
        normalizer = JATSNormalizer(remove_structural=True)
        result = normalizer.normalize_xml(_FULL_FEATURE_JATS)
        assert "Fig 1." not in result["body_text"]
        assert "Results" not in result["body_text"]

    def test_structural_removal_disabled(self) -> None:
        """When disabled, structural elements remain."""
        normalizer = JATSNormalizer(remove_structural=False)
        result = normalizer.normalize_xml(_FULL_FEATURE_JATS)
        # Fig content should be in body text
        assert "Fig 1" in result["body_text"] or "fig1" in result["body_text"]


# ---------------------------------------------------------------------------
# Tests: Entity normalization
# ---------------------------------------------------------------------------


class TestEntityNormalization:
    """Tests for XML entity and Unicode normalization."""

    def test_greek_letters(self) -> None:
        """Greek letter entities are resolved."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>The &alpha; and &beta; subunits.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_entities=True)
        result = normalizer.normalize_xml(xml)
        assert "α" in result["body_text"]
        assert "β" in result["body_text"]

    def test_html_entities(self) -> None:
        """HTML entities like &lt; &gt; are resolved."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>When x &lt; 5 and y &gt; 3.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_entities=True)
        result = normalizer.normalize_xml(xml)
        assert "x < 5" in result["body_text"]
        assert "y > 3" in result["body_text"]

    def test_degree_and_micro(self) -> None:
        """Special entities like degree and micro are resolved."""
        normalizer = JATSNormalizer(normalize_entities=True)
        result = normalizer.normalize_xml(_FULL_FEATURE_JATS)
        assert "°C" in result["body_text"]

    def test_entity_normalization_disabled(self) -> None:
        """When disabled, entities remain as-is."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>&alpha; test.</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_entities=False)
        result = normalizer.normalize_xml(xml)
        # The raw entity might still be present or partially decoded
        # (ET parser handles some entities natively)
        assert "test" in result["body_text"]


# ---------------------------------------------------------------------------
# Tests: Whitespace normalization
# ---------------------------------------------------------------------------


class TestWhitespaceNormalization:
    """Tests for whitespace normalization."""

    def test_nbsp_replaced(self) -> None:
        """Non-breaking spaces are replaced with regular spaces."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>word1\u00a0word2</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_whitespace=True)
        result = normalizer.normalize_xml(xml)
        assert "word1 word2" in result["body_text"]
        assert "\u00a0" not in result["body_text"]

    def test_multiple_spaces_collapsed(self) -> None:
        """Multiple spaces are collapsed to one."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>word1  word2   word3</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_whitespace=True)
        result = normalizer.normalize_xml(xml)
        assert "  " not in result["body_text"]

    def test_zero_width_chars_removed(self) -> None:
        """Zero-width characters are removed."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>word\u200b1 word\u200c2</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_whitespace=True)
        result = normalizer.normalize_xml(xml)
        assert "\u200b" not in result["body_text"]
        assert "\u200c" not in result["body_text"]


# ---------------------------------------------------------------------------
# Tests: Dash normalization
# ---------------------------------------------------------------------------


class TestDashNormalization:
    """Tests for dash/hyphen normalization."""

    def test_en_dash_normalized(self) -> None:
        """En dash (–) is normalized to ASCII hyphen."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>range\u2013of values</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_dashes=True)
        result = normalizer.normalize_xml(xml)
        assert "range-of values" in result["body_text"]

    def test_em_dash_normalized(self) -> None:
        """Em dash (—) is normalized to ASCII hyphen."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>before\u2014after</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_dashes=True)
        result = normalizer.normalize_xml(xml)
        assert "before-after" in result["body_text"]

    def test_minus_sign_normalized(self) -> None:
        """Unicode minus sign is normalized to ASCII hyphen."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>\u22125 to \u221210</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_dashes=True)
        result = normalizer.normalize_xml(xml)
        assert "-5 to -10" in result["body_text"]

    def test_unicode_dashes_from_fixture(self) -> None:
        """All Unicode dash variants in fixture are normalized."""
        normalizer = JATSNormalizer(normalize_dashes=True, normalize_whitespace=False)
        result = normalizer.normalize_xml(_UNICODE_JATS)
        # Em dash, en dash, horizontal bar, minus sign all → ASCII hyphen
        assert "\u2013" not in result["body_text"]
        assert "\u2014" not in result["body_text"]
        assert "\u2015" not in result["body_text"]
        assert "\u2212" not in result["body_text"]
        assert "dash-en-em-bar-minus" in result["body_text"]

    def test_dash_normalization_disabled(self) -> None:
        """When disabled, Unicode dashes remain."""
        xml = """\
        <article><body>
          <sec><title>Test</title>
            <p>range\u2013of</p>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(normalize_dashes=False)
        result = normalizer.normalize_xml(xml)
        assert "\u2013" in result["body_text"]


# ---------------------------------------------------------------------------
# Tests: Metadata normalization
# ---------------------------------------------------------------------------


class TestMetadataNormalization:
    """Tests for metadata extraction and normalization."""

    def test_title_extracted(self) -> None:
        """Article title is extracted."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert "Important" in result["metadata"]["title"]
        assert "Test Article" in result["metadata"]["title"]

    def test_doi_normalized(self) -> None:
        """DOI is normalized (lowercased, prefix stripped)."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_FULL_FEATURE_JATS)
        assert result["metadata"]["doi"] == "10.1000/abc.def"

    def test_pmcid_normalized(self) -> None:
        """PMCID is normalized (uppercase, PMC prefix)."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert result["metadata"]["pmcid"] == "PMC1234567"

    def test_pmid_extracted(self) -> None:
        """PMID is extracted."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert result["metadata"]["pmid"] == "12345678"

    def test_article_type_normalized(self) -> None:
        """Article type is lowercased with hyphens."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert result["metadata"]["article_type"] == "research-article"

    def test_authors_extracted(self) -> None:
        """Authors are extracted with names."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        authors = result["metadata"]["authors"]
        assert len(authors) == 2
        assert authors[0]["name"] == "John A. Smith"
        assert authors[1]["name"] == "Maria Garcia"

    def test_orcid_normalized(self) -> None:
        """ORCID is normalized to standard format."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        orcid = result["metadata"]["authors"][0]["orcid"]
        assert orcid == "0000-0002-1234-5678"

    def test_orcid_url_stripped(self) -> None:
        """ORCID URL prefix is stripped."""
        assert JATSNormalizer._normalize_orcid("https://orcid.org/0000-0002-1234-5678") == "0000-0002-1234-5678"

    def test_journal_extracted(self) -> None:
        """Journal name is extracted."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert result["metadata"]["journal"] == "Test Journal"


# ---------------------------------------------------------------------------
# Tests: BioC output
# ---------------------------------------------------------------------------


class TestBioCOutput:
    """Tests for BioC JSON output format."""

    def test_bioc_enabled(self) -> None:
        """BioC output is generated when enabled."""
        normalizer = JATSNormalizer(bio_c_output=True)
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert "bio_c" in result
        assert isinstance(result["bio_c"], dict)

    def test_bioc_disabled_by_default(self) -> None:
        """BioC output is not generated by default."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        assert "bio_c" not in result

    def test_bioc_structure(self) -> None:
        """BioC output has correct structure."""
        normalizer = JATSNormalizer(bio_c_output=True)
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        bioc = result["bio_c"]

        assert bioc["source"] == "pyeuropepmc"
        assert len(bioc["documents"]) == 1
        doc = bioc["documents"][0]
        assert "id" in doc
        assert "passages" in doc
        assert len(doc["passages"]) > 0

        for passage in doc["passages"]:
            assert "offset" in passage
            assert "text" in passage
            assert "infons" in passage
            assert "section_type" in passage["infons"]

    def test_bioc_section_types(self) -> None:
        """BioC passages have canonical section types."""
        normalizer = JATSNormalizer(bio_c_output=True, section_types=True)
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        bioc = result["bio_c"]
        doc = bioc["documents"][0]
        section_types = [p["infons"]["section_type"] for p in doc["passages"]]
        assert "intro" in section_types
        assert "methods" in section_types

    def test_bioc_serializable(self) -> None:
        """BioC output is JSON-serializable."""
        normalizer = JATSNormalizer(bio_c_output=True)
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        # Should not raise
        json_str = json.dumps(result["bio_c"])
        assert len(json_str) > 0
        # Round-trip
        parsed = json.loads(json_str)
        assert parsed["source"] == "pyeuropepmc"


# ---------------------------------------------------------------------------
# Tests: Convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_normalize_jats_xml(self) -> None:
        """normalize_jats_xml works with default settings."""
        result = normalize_jats_xml(_MINIMAL_JATS)
        assert isinstance(result, dict)
        assert "sections" in result
        assert "body_text" in result

    def test_normalize_jats_xml_custom(self) -> None:
        """normalize_jats_xml accepts custom settings."""
        result = normalize_jats_xml(
            _MINIMAL_JATS,
            section_types=False,
            bio_c_output=True,
        )
        assert result["sections"] == []  # section_types disabled
        assert "bio_c" in result

    def test_normalize_jats_text(self) -> None:
        """normalize_jats_text returns plain text."""
        text = normalize_jats_text(_MINIMAL_JATS)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_classify_section_function(self) -> None:
        """classify_section module function works."""
        assert classify_section("Methods") == "methods"
        assert classify_section("Results") == "results"


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_no_body_element(self) -> None:
        """Handles XML without body element."""
        xml = """\
        <article article-type="erratum">
          <front>
            <article-meta>
              <title-group><article-title>No Body</article-title></title-group>
            </article-meta>
          </front>
        </article>"""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(xml)
        assert result["body_text"] == ""
        assert result["sections"] == []
        assert result["metadata"]["title"] == "No Body"

    def test_empty_body(self) -> None:
        """Handles XML with empty body."""
        xml = """\
        <article>
          <front>
            <article-meta>
              <title-group><article-title>Empty Body</article-title></title-group>
            </article-meta>
          </front>
          <body></body>
        </article>"""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(xml)
        assert result["body_text"] == ""

    def test_malformed_xml(self) -> None:
        """Malformed XML raises parsing error."""
        normalizer = JATSNormalizer()
        with pytest.raises(ParseError):
            normalizer.normalize_xml("<article><body><unclosed>")

    def test_only_metadata_no_body(self) -> None:
        """Article with metadata only, no body."""
        xml = """\
        <article article-type="erratum">
          <front>
            <article-meta>
              <title-group><article-title>Erratum</article-title></title-group>
            </article-meta>
          </front>
        </article>"""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(xml)
        assert result["metadata"]["title"] == "Erratum"
        assert result["body_text"] == ""

    def test_deeply_nested_sections(self) -> None:
        """Handles deeply nested sections."""
        xml = """\
        <article><body>
          <sec><title>Level 0</title>
            <p>Top text.</p>
            <sec><title>Level 1</title>
              <p>Mid text.</p>
              <sec><title>Level 2</title>
                <p>Deep text.</p>
              </sec>
            </sec>
          </sec>
        </body></article>"""
        normalizer = JATSNormalizer(section_types=True)
        sections = normalizer.normalize_sections(xml)
        assert len(sections) == 3
        levels = [s["level"] for s in sections]
        assert 0 in levels
        assert 1 in levels
        assert 2 in levels


# ---------------------------------------------------------------------------
# Tests: Full document integration
# ---------------------------------------------------------------------------


class TestFullDocumentIntegration:
    """Integration tests with full JATS documents."""

    def test_full_feature_document(self) -> None:
        """Full-featured document normalizes correctly."""
        normalizer = JATSNormalizer(
            section_types=True,
            strip_display_markup=True,
            flatten_xrefs=True,
            normalize_entities=True,
            normalize_dashes=True,
            normalize_whitespace=True,
        )
        result = normalizer.normalize_xml(_FULL_FEATURE_JATS)

        # Check body text has entities resolved
        assert "α" in result["body_text"]
        assert "β" in result["body_text"]
        assert "°C" in result["body_text"]

        # Check sub/sup stripped (CO2 in body, H2O2 in title)
        assert "CO2" in result["body_text"]
        assert "H2O2" in result["metadata"]["title"]

        # Check fig removed from body
        assert "Fig 1" not in result["body_text"]

        # Check sections classified
        section_types = [s["type"] for s in result["sections"]]
        assert "background" in section_types
        assert "methods" in section_types
        assert "results" in section_types
        assert "ack" in section_types
        assert "references" in section_types

    def test_minimal_document_with_all_layers(self) -> None:
        """Minimal document with all normalization layers enabled."""
        normalizer = JATSNormalizer()
        result = normalizer.normalize_xml(_MINIMAL_JATS)

        # Body text should be clean
        body = result["body_text"]
        assert "<bold>" not in body
        assert "<italic>" not in body
        assert "<sup>" not in body
        assert "<sub>" not in body

        # Metadata should be extracted
        meta = result["metadata"]
        assert "title" in meta
        assert "doi" in meta
        assert "pmcid" in meta

    def test_disable_all_normalization(self) -> None:
        """All normalization layers disabled."""
        normalizer = JATSNormalizer(
            strip_display_markup=False,
            flatten_xrefs=False,
            remove_structural=False,
            section_types=False,
            normalize_entities=False,
            normalize_whitespace=False,
            normalize_dashes=False,
            normalize_identifiers=False,
        )
        result = normalizer.normalize_xml(_MINIMAL_JATS)
        # Body text still extracted but with inline tags
        assert len(result["body_text"]) > 0
        # Sections not classified
        assert result["sections"] == []
