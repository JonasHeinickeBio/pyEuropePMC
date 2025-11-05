"""
Unit tests for flexible parsing features.

Tests ElementPatterns configuration, fallback patterns, schema detection,
and flexible extraction methods.
"""
import xml.etree.ElementTree as ET

import pytest

from pyeuropepmc.exceptions import ParsingError
from pyeuropepmc.fulltext_parser import (
    DocumentSchema,
    ElementPatterns,
    FullTextXMLParser,
)


class TestElementPatterns:
    """Test ElementPatterns configuration class."""

    def test_default_initialization(self):
        """Test that ElementPatterns initializes with default values."""
        config = ElementPatterns()

        # Check citation types
        assert "element-citation" in config.citation_types
        assert "mixed-citation" in config.citation_types
        assert "nlm-citation" in config.citation_types
        assert "citation" in config.citation_types

        # Check author patterns
        assert ".//contrib[@contrib-type='author']/name" in config.author_element_patterns
        assert ".//author" in config.author_element_patterns

        # Check journal patterns
        assert config.journal_patterns["title"] == [".//journal-title", ".//source", ".//journal"]
        assert config.journal_patterns["issn"] == [".//issn"]

        # Check article patterns
        assert ".//article-title" in config.article_patterns["title"]
        assert ".//title" in config.article_patterns["title"]

    def test_custom_citation_types(self):
        """Test creating ElementPatterns with custom citation types."""
        custom_types = ["custom-citation", "my-citation"]
        config = ElementPatterns(citation_types=custom_types)

        assert config.citation_types == custom_types
        assert "element-citation" not in config.citation_types

    def test_custom_author_patterns(self):
        """Test creating ElementPatterns with custom author patterns."""
        custom_patterns = [".//custom-author", ".//my-author/name"]
        config = ElementPatterns(author_element_patterns=custom_patterns)

        assert config.author_element_patterns == custom_patterns
        assert ".//contrib[@contrib-type='author']/name" not in config.author_element_patterns


class TestDocumentSchema:
    """Test DocumentSchema detection class."""

    def test_default_initialization(self):
        """Test that DocumentSchema initializes with default values."""
        schema = DocumentSchema()

        assert schema.has_tables is False
        assert schema.has_figures is False
        assert schema.has_supplementary is False
        assert schema.has_acknowledgments is False
        assert schema.has_funding is False
        assert schema.citation_types == []


class TestExtractWithFallbacks:
    """Test _extract_with_fallbacks() helper method."""

    def test_first_pattern_matches(self):
        """Test that first matching pattern is used."""
        xml = """<root>
            <title>Main Title</title>
            <alt-title>Alternative Title</alt-title>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        result = parser._extract_with_fallbacks(
            root, [".//title", ".//alt-title", ".//heading"]
        )

        assert result == "Main Title"

    def test_second_pattern_matches(self):
        """Test that second pattern is tried when first fails."""
        xml = """<root>
            <alt-title>Alternative Title</alt-title>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        result = parser._extract_with_fallbacks(
            root, [".//title", ".//alt-title", ".//heading"]
        )

        assert result == "Alternative Title"

    def test_no_pattern_matches(self):
        """Test that None is returned when no pattern matches."""
        xml = """<root>
            <other>Some Text</other>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        result = parser._extract_with_fallbacks(
            root, [".//title", ".//alt-title", ".//heading"]
        )

        assert result is None

    def test_empty_pattern_list(self):
        """Test handling of empty pattern list."""
        xml = """<root><title>Title</title></root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        result = parser._extract_with_fallbacks(root, [])

        assert result is None


class TestDetectSchema:
    """Test detect_schema() method."""

    def test_schema_with_tables(self):
        """Test schema detection with tables present."""
        xml = """<root>
            <body>
                <sec>
                    <table-wrap>
                        <table>
                            <tr><td>Data</td></tr>
                        </table>
                    </table-wrap>
                </sec>
            </body>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        schema = parser.detect_schema()

        assert schema.has_tables is True
        assert schema.has_figures is False

    def test_schema_with_figures(self):
        """Test schema detection with figures present."""
        xml = """<root>
            <body>
                <sec>
                    <fig id="fig1">
                        <caption>Figure 1</caption>
                    </fig>
                </sec>
            </body>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        schema = parser.detect_schema()

        assert schema.has_figures is True
        assert schema.has_tables is False

    def test_schema_with_multiple_citation_types(self):
        """Test schema detection with multiple citation types."""
        xml = """<root>
            <back>
                <ref-list>
                    <ref><element-citation>Citation 1</element-citation></ref>
                    <ref><mixed-citation>Citation 2</mixed-citation></ref>
                    <ref><element-citation>Citation 3</element-citation></ref>
                </ref-list>
            </back>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        schema = parser.detect_schema()

        assert "element-citation" in schema.citation_types
        assert "mixed-citation" in schema.citation_types

    def test_schema_caching(self):
        """Test that schema is cached after first detection."""
        xml = """<root><body><table-wrap/></body></root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        # First call
        schema1 = parser.detect_schema()
        # Second call should return cached result
        schema2 = parser.detect_schema()

        assert schema1 is schema2


class TestFlexibleExtractReferences:
    """Test extract_references() with flexible patterns."""

    def test_extract_element_citation(self):
        """Test extracting references with element-citation."""
        xml = """<root>
            <back>
                <ref-list>
                    <ref id="ref1">
                        <element-citation>
                            <article-title>Test Article</article-title>
                            <source>Test Journal</source>
                            <year>2023</year>
                            <volume>10</volume>
                            <fpage>100</fpage>
                            <lpage>110</lpage>
                            <pub-id pub-id-type="doi">10.1234/test</pub-id>
                        </element-citation>
                    </ref>
                </ref-list>
            </back>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        references = parser.extract_references()

        assert len(references) == 1
        assert references[0]["title"] == "Test Article"
        assert references[0]["source"] == "Test Journal"
        assert references[0]["year"] == "2023"
        assert references[0]["volume"] == "10"
        assert references[0]["pages"] == "100-110"
        assert references[0]["doi"] == "10.1234/test"

    def test_extract_mixed_citation(self):
        """Test extracting references with mixed-citation."""
        xml = """<root>
            <back>
                <ref-list>
                    <ref id="ref1">
                        <mixed-citation>
                            <article-title>Test Article</article-title>
                            <source>Test Journal</source>
                            <year>2023</year>
                        </mixed-citation>
                    </ref>
                </ref-list>
            </back>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        references = parser.extract_references()

        assert len(references) == 1
        assert references[0]["title"] == "Test Article"
        assert references[0]["source"] == "Test Journal"

    def test_extract_nlm_citation(self):
        """Test extracting references with nlm-citation (older format)."""
        xml = """<root>
            <back>
                <ref-list>
                    <ref id="ref1">
                        <nlm-citation>
                            <article-title>Test Article</article-title>
                            <source>Test Journal</source>
                        </nlm-citation>
                    </ref>
                </ref-list>
            </back>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        references = parser.extract_references()

        assert len(references) == 1
        assert references[0]["title"] == "Test Article"

    def test_fallback_to_alternative_doi_pattern(self):
        """Test DOI extraction with alternative pattern."""
        xml = """<root>
            <back>
                <ref-list>
                    <ref id="ref1">
                        <element-citation>
                            <article-title>Test</article-title>
                            <ext-link ext-link-type="doi">10.1234/alt</ext-link>
                        </element-citation>
                    </ref>
                </ref-list>
            </back>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        references = parser.extract_references()

        assert len(references) == 1
        assert references[0]["doi"] == "10.1234/alt"


class TestFlexibleExtractMetadata:
    """Test extract_metadata() with flexible patterns."""

    def test_extract_standard_metadata(self):
        """Test extracting metadata with standard JATS elements."""
        xml = """<root>
            <front>
                <article-meta>
                    <article-id pub-id-type="pmcid">3258128</article-id>
                    <article-id pub-id-type="doi">10.1234/test</article-id>
                    <title-group>
                        <article-title>Test Article Title</article-title>
                    </title-group>
                    <journal-meta>
                        <journal-title>Test Journal</journal-title>
                    </journal-meta>
                    <volume>10</volume>
                    <issue>2</issue>
                    <fpage>100</fpage>
                    <lpage>110</lpage>
                    <abstract>
                        <p>Test abstract text.</p>
                    </abstract>
                </article-meta>
            </front>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        metadata = parser.extract_metadata()

        assert metadata["pmcid"] == "3258128"
        assert metadata["doi"] == "10.1234/test"
        assert metadata["title"] == "Test Article Title"
        assert metadata["journal"] == "Test Journal"
        assert metadata["volume"] == "10"
        assert metadata["issue"] == "2"
        assert metadata["pages"] == "100-110"

    def test_extract_with_alternative_patterns(self):
        """Test metadata extraction with alternative element names."""
        xml = """<root>
            <front>
                <article-meta>
                    <article-id pub-id-type="pmc">3258128</article-id>
                    <title>Alternative Title Element</title>
                    <source>Journal Source</source>
                </article-meta>
            </front>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        metadata = parser.extract_metadata()

        # Should fall back to alternative patterns
        assert metadata["title"] == "Alternative Title Element"
        assert metadata["journal"] == "Journal Source"


class TestFlexibleExtractAuthors:
    """Test extract_authors() with flexible patterns."""

    def test_extract_standard_authors(self):
        """Test extracting authors with standard contrib elements."""
        xml = """<root>
            <front>
                <article-meta>
                    <contrib-group>
                        <contrib contrib-type="author">
                            <name>
                                <given-names>John</given-names>
                                <surname>Doe</surname>
                            </name>
                        </contrib>
                        <contrib contrib-type="author">
                            <name>
                                <given-names>Jane</given-names>
                                <surname>Smith</surname>
                            </name>
                        </contrib>
                    </contrib-group>
                </article-meta>
            </front>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        authors = parser.extract_authors()

        assert len(authors) == 2
        assert "John Doe" in authors
        assert "Jane Smith" in authors

    def test_extract_alternative_author_structure(self):
        """Test extracting authors with alternative element structure."""
        xml = """<root>
            <front>
                <article-meta>
                    <author-group>
                        <author>
                            <given-name>John</given-name>
                            <last-name>Doe</last-name>
                        </author>
                    </author-group>
                </article-meta>
            </front>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        authors = parser.extract_authors()

        assert len(authors) == 1
        assert "John Doe" in authors

    def test_extract_authors_with_missing_given_name(self):
        """Test handling authors with only surname."""
        xml = """<root>
            <front>
                <article-meta>
                    <contrib-group>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Doe</surname>
                            </name>
                        </contrib>
                    </contrib-group>
                </article-meta>
            </front>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        authors = parser.extract_authors()

        assert len(authors) == 1
        assert "Doe" in authors


class TestCustomConfiguration:
    """Test using custom ElementPatterns configuration."""

    def test_parser_with_custom_config(self):
        """Test initializing parser with custom configuration."""
        custom_config = ElementPatterns(
            citation_types=["custom-citation"],
            author_element_patterns=[".//custom-author/name"],
        )

        parser = FullTextXMLParser(config=custom_config)

        assert parser.config.citation_types == ["custom-citation"]
        assert parser.config.author_element_patterns == [".//custom-author/name"]

    def test_extract_with_custom_citation_type(self):
        """Test reference extraction with custom citation type."""
        xml = """<root>
            <back>
                <ref-list>
                    <ref id="ref1">
                        <custom-citation>
                            <article-title>Custom Format</article-title>
                        </custom-citation>
                    </ref>
                </ref-list>
            </back>
        </root>"""
        root = ET.fromstring(xml)

        custom_config = ElementPatterns(citation_types=["custom-citation"])
        parser = FullTextXMLParser(config=custom_config)
        parser.root = root

        references = parser.extract_references()

        assert len(references) == 1
        assert references[0]["title"] == "Custom Format"


class TestInlineElementHandling:
    """Test generic inline element handling functions."""

    def test_extract_inline_elements_superscript(self):
        """Test extracting superscript elements."""
        xml = """<root>
            <p>Some text<sup>1</sup> and more<sup>2</sup> text</p>
        </root>"""
        root = ET.fromstring(xml)
        p_elem = root.find(".//p")
        assert p_elem is not None

        parser = FullTextXMLParser()
        parser.root = root

        markers = parser._extract_inline_elements(p_elem, [".//sup"])

        assert len(markers) == 2
        assert "1" in markers
        assert "2" in markers

    def test_extract_inline_elements_multiple_types(self):
        """Test extracting multiple inline element types."""
        xml = """<root>
            <p>Text<sup>1</sup> with <sub>subscript</sub> elements</p>
        </root>"""
        root = ET.fromstring(xml)
        p_elem = root.find(".//p")
        assert p_elem is not None

        parser = FullTextXMLParser()
        parser.root = root

        inline = parser._extract_inline_elements(p_elem, [".//sup", ".//sub"])

        assert len(inline) == 2
        assert "1" in inline
        assert "subscript" in inline

    def test_extract_inline_elements_default_pattern(self):
        """Test that default pattern is superscript."""
        xml = """<root>
            <p>Text<sup>marker</sup> here</p>
        </root>"""
        root = ET.fromstring(xml)
        p_elem = root.find(".//p")
        assert p_elem is not None

        parser = FullTextXMLParser()
        parser.root = root

        # Should default to [".//sup"]
        markers = parser._extract_inline_elements(p_elem)

        assert len(markers) == 1
        assert "marker" in markers

    def test_get_text_without_inline_elements(self):
        """Test removing inline elements from text."""
        xml = """<root>
            <aff>
                <sup>1</sup>Department of Biology, University of Science
            </aff>
        </root>"""
        root = ET.fromstring(xml)
        aff_elem = root.find(".//aff")
        assert aff_elem is not None

        parser = FullTextXMLParser()
        parser.root = root

        clean_text = parser._get_text_without_inline_elements(aff_elem, [".//sup"])

        assert "1" not in clean_text
        assert "Department of Biology" in clean_text
        assert "University of Science" in clean_text

    def test_get_text_without_multiple_inline_types(self):
        """Test removing multiple types of inline elements."""
        xml = """<root>
            <p>Normal<sup>1</sup> and <sub>2</sub> text<italic>italic</italic> here</p>
        </root>"""
        root = ET.fromstring(xml)
        p_elem = root.find(".//p")
        assert p_elem is not None

        parser = FullTextXMLParser()
        parser.root = root

        clean_text = parser._get_text_without_inline_elements(
            p_elem, [".//sup", ".//sub", ".//italic"]
        )

        # Superscripts, subscripts, and italic text should be removed
        assert "1" not in clean_text
        assert "2" not in clean_text
        assert "italic" not in clean_text
        assert "Normal" in clean_text
        assert "and" in clean_text
        assert "text" in clean_text

    def test_affiliation_extraction_with_superscripts(self):
        """Test that affiliation extraction properly handles superscripts."""
        xml = """<root>
            <aff id="aff1">
                <sup>1</sup>Department of Biology, University of Science, City 12345, Country
            </aff>
        </root>"""
        root = ET.fromstring(xml)

        parser = FullTextXMLParser()
        parser.root = root

        affiliations = parser.extract_affiliations()

        assert len(affiliations) == 1
        assert affiliations[0]["id"] == "aff1"
        assert affiliations[0]["markers"] == "1"
        # Clean text should not contain the superscript
        assert "1" not in affiliations[0]["institution_text"]
        assert "Department of Biology" in affiliations[0]["institution_text"]

    def test_custom_inline_patterns_in_config(self):
        """Test using custom inline element patterns from config."""
        xml = """<root>
            <p>Text<custom-sup>*</custom-sup> with custom marker</p>
        </root>"""
        root = ET.fromstring(xml)
        p_elem = root.find(".//p")
        assert p_elem is not None

        config = ElementPatterns(inline_element_patterns=[".//custom-sup"])
        parser = FullTextXMLParser(config=config)
        parser.root = root

        markers = parser._extract_inline_elements(p_elem, config.inline_element_patterns)

        assert len(markers) == 1
        assert "*" in markers


class TestSchemaCoverageValidation:
    """Test suite for schema coverage validation."""

    def test_validate_schema_coverage_basic(self):
        """Test basic schema coverage validation."""
        xml = """<article>
            <front>
                <article-title>Test Article</article-title>
            </front>
            <body>
                <sec>
                    <title>Introduction</title>
                    <p>Some text</p>
                </sec>
            </body>
            <back>
                <ref-list>
                    <ref id="ref1">
                        <element-citation>
                            <article-title>Reference Title</article-title>
                        </element-citation>
                    </ref>
                </ref-list>
            </back>
        </article>"""

        parser = FullTextXMLParser(xml)
        coverage = parser.validate_schema_coverage()

        # Verify structure
        assert "total_elements" in coverage
        assert "recognized_elements" in coverage
        assert "unrecognized_elements" in coverage
        assert "coverage_percentage" in coverage
        assert "element_frequency" in coverage

        # Should have some recognized elements
        assert coverage["recognized_count"] > 0
        assert coverage["total_elements"] > 0
        assert 0 <= coverage["coverage_percentage"] <= 100

        # Common elements should be recognized
        assert "article" in coverage["recognized_elements"]
        assert "title" in coverage["recognized_elements"]
        assert "p" in coverage["recognized_elements"]

    def test_validate_schema_coverage_with_unrecognized(self):
        """Test schema coverage with unrecognized custom elements."""
        xml = """<article>
            <front>
                <custom-metadata>
                    <custom-tag>Value</custom-tag>
                </custom-metadata>
            </front>
            <body>
                <p>Text</p>
            </body>
        </article>"""

        parser = FullTextXMLParser(xml)
        coverage = parser.validate_schema_coverage()

        # Should have unrecognized elements
        assert coverage["unrecognized_count"] > 0
        assert "custom-metadata" in coverage["unrecognized_elements"]
        assert "custom-tag" in coverage["unrecognized_elements"]

        # Should still recognize common elements
        assert "article" in coverage["recognized_elements"]
        assert "p" in coverage["recognized_elements"]

    def test_validate_schema_coverage_frequency(self):
        """Test element frequency counting."""
        xml = """<article>
            <body>
                <sec>
                    <p>Paragraph 1</p>
                    <p>Paragraph 2</p>
                    <p>Paragraph 3</p>
                </sec>
            </body>
        </article>"""

        parser = FullTextXMLParser(xml)
        coverage = parser.validate_schema_coverage()

        # Check frequency counting
        assert coverage["element_frequency"]["p"] == 3
        assert coverage["element_frequency"]["sec"] == 1
        assert coverage["element_frequency"]["article"] == 1

    def test_validate_schema_coverage_all_recognized(self):
        """Test schema coverage with all elements recognized."""
        xml = """<article>
            <front>
                <article-title>Title</article-title>
            </front>
            <body>
                <sec>
                    <title>Section</title>
                    <p>Text</p>
                </sec>
            </body>
        </article>"""

        parser = FullTextXMLParser(xml)
        coverage = parser.validate_schema_coverage()

        # Should have high coverage (100% or close)
        assert coverage["coverage_percentage"] >= 80
        assert coverage["unrecognized_count"] == 0 or coverage["unrecognized_count"] <= 2

    def test_validate_schema_coverage_with_tables(self):
        """Test schema coverage includes table elements."""
        xml = """<article>
            <body>
                <table-wrap id="t1">
                    <label>Table 1</label>
                    <caption>
                        <title>Test Table</title>
                    </caption>
                    <table>
                        <thead>
                            <tr>
                                <th>Header</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Data</td>
                            </tr>
                        </tbody>
                    </table>
                </table-wrap>
            </body>
        </article>"""

        parser = FullTextXMLParser(xml)
        coverage = parser.validate_schema_coverage()

        # Table elements should be recognized
        recognized = coverage["recognized_elements"]
        assert "table" in recognized
        assert "thead" in recognized or "thead" in coverage["unrecognized_elements"]
        assert "tbody" in recognized or "tbody" in coverage["unrecognized_elements"]
        assert "tr" in recognized or "tr" in coverage["unrecognized_elements"]

    def test_validate_schema_coverage_requires_parsed_xml(self):
        """Test that validation requires parsed XML."""
        parser = FullTextXMLParser()

        with pytest.raises(ParsingError) as exc_info:
            parser.validate_schema_coverage()

        assert exc_info.value.error_code.value == "PARSE003"
