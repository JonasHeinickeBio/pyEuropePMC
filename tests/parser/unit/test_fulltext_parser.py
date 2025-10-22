"""Unit tests for the FullTextXMLParser module."""

import pytest
from pathlib import Path

from pyeuropepmc.fulltext_parser import FullTextXMLParser
from pyeuropepmc.exceptions import ParsingError


# Sample XML content for testing
SAMPLE_ARTICLE_XML = '''<?xml version="1.0"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD Journal Archiving and Interchange DTD v3.0 20080202//EN" "archivearticle3.dtd">
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front>
<journal-meta>
<journal-title>Test Journal</journal-title>
</journal-meta>
<article-meta>
<article-id pub-id-type="pmcid">1234567</article-id>
<article-id pub-id-type="doi">10.1234/test.2021.001</article-id>
<title-group>
<article-title>Sample Test Article Title</article-title>
</title-group>
<contrib-group>
<contrib contrib-type="author">
<name>
<surname>Smith</surname>
<given-names>John</given-names>
</name>
</contrib>
<contrib contrib-type="author">
<name>
<surname>Doe</surname>
<given-names>Jane</given-names>
</name>
</contrib>
</contrib-group>
<pub-date pub-type="ppub">
<year>2021</year>
<month>12</month>
<day>15</day>
</pub-date>
<volume>10</volume>
<issue>5</issue>
<fpage>100</fpage>
<lpage>110</lpage>
<abstract>
<p>This is a sample abstract for testing purposes.</p>
</abstract>
<kwd-group>
<kwd>keyword1</kwd>
<kwd>keyword2</kwd>
</kwd-group>
</article-meta>
</front>
<body>
<sec>
<title>Introduction</title>
<p>This is the introduction section with some text.</p>
</sec>
<sec>
<title>Methods</title>
<p>This section describes the methods used in the study.</p>
<p>Multiple paragraphs are included here.</p>
</sec>
<sec>
<title>Results</title>
<table-wrap id="t1">
<label>Table 1</label>
<caption><p>Sample data table</p></caption>
<table>
<thead>
<tr>
<th>Column 1</th>
<th>Column 2</th>
</tr>
</thead>
<tbody>
<tr>
<td>Data 1</td>
<td>Data 2</td>
</tr>
<tr>
<td>Data 3</td>
<td>Data 4</td>
</tr>
</tbody>
</table>
</table-wrap>
</sec>
</body>
<back>
<ref-list>
<ref id="ref1">
<label>1</label>
<element-citation>
<person-group person-group-type="author">
<name>
<surname>Author</surname>
<given-names>A</given-names>
</name>
</person-group>
<article-title>Reference Article Title</article-title>
<source>Reference Journal</source>
<year>2020</year>
<volume>5</volume>
<fpage>10</fpage>
<lpage>20</lpage>
</element-citation>
</ref>
</ref-list>
</back>
</article>
'''


class TestFullTextXMLParserInit:
    """Test FullTextXMLParser initialization."""

    def test_init_without_content(self):
        """Test initialization without XML content."""
        parser = FullTextXMLParser()
        assert parser.xml_content is None
        assert parser.root is None

    def test_init_with_content(self):
        """Test initialization with valid XML content."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        assert parser.xml_content == SAMPLE_ARTICLE_XML
        assert parser.root is not None

    def test_init_with_invalid_xml(self):
        """Test initialization with invalid XML content."""
        with pytest.raises(ParsingError):
            FullTextXMLParser("<invalid><xml>")


class TestFullTextXMLParserParse:
    """Test the parse method."""

    def test_parse_valid_xml(self):
        """Test parsing valid XML content."""
        parser = FullTextXMLParser()
        root = parser.parse(SAMPLE_ARTICLE_XML)
        assert root is not None
        assert parser.root is not None
        assert parser.xml_content == SAMPLE_ARTICLE_XML

    def test_parse_empty_string(self):
        """Test parsing empty string raises error."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.parse("")

    def test_parse_none(self):
        """Test parsing None raises error."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.parse(None)  # type: ignore

    def test_parse_malformed_xml(self):
        """Test parsing malformed XML raises error."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.parse("<article><unclosed>")


class TestFullTextXMLParserExtractMetadata:
    """Test metadata extraction."""

    def test_extract_metadata_complete(self):
        """Test extracting all metadata fields."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        metadata = parser.extract_metadata()

        assert metadata["pmcid"] == "1234567"
        assert metadata["doi"] == "10.1234/test.2021.001"
        assert metadata["title"] == "Sample Test Article Title"
        assert len(metadata["authors"]) == 2
        assert "John Smith" in metadata["authors"]
        assert "Jane Doe" in metadata["authors"]
        assert metadata["journal"] == "Test Journal"
        assert metadata["pub_date"] == "2021-12-15"
        assert metadata["volume"] == "10"
        assert metadata["issue"] == "5"
        assert metadata["pages"] == "100-110"
        assert "sample abstract" in metadata["abstract"].lower()
        assert len(metadata["keywords"]) == 2

    def test_extract_metadata_no_parse(self):
        """Test extracting metadata without parsing first."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.extract_metadata()

    def test_extract_metadata_minimal_xml(self):
        """Test extracting metadata from minimal XML."""
        minimal_xml = "<article><front><article-meta></article-meta></front></article>"
        parser = FullTextXMLParser(minimal_xml)
        metadata = parser.extract_metadata()

        # Should return dict with None values for missing fields
        assert metadata["pmcid"] is None
        assert metadata["doi"] is None
        assert metadata["title"] is None


class TestFullTextXMLParserToPlaintext:
    """Test plaintext conversion."""

    def test_to_plaintext(self):
        """Test converting XML to plaintext."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        plaintext = parser.to_plaintext()

        assert "Sample Test Article Title" in plaintext
        assert "John Smith" in plaintext
        assert "Jane Doe" in plaintext
        assert "Introduction" in plaintext
        assert "Methods" in plaintext
        assert "abstract" in plaintext.lower()

    def test_to_plaintext_no_parse(self):
        """Test converting to plaintext without parsing first."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.to_plaintext()

    def test_to_plaintext_structure(self):
        """Test plaintext structure and formatting."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        plaintext = parser.to_plaintext()

        # Check that sections are properly separated
        lines = plaintext.split("\n")
        assert len(lines) > 0

        # Check title comes before authors
        title_idx = plaintext.index("Sample Test Article Title")
        authors_idx = plaintext.index("Authors:")
        assert title_idx < authors_idx


class TestFullTextXMLParserToMarkdown:
    """Test markdown conversion."""

    def test_to_markdown(self):
        """Test converting XML to markdown."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        markdown = parser.to_markdown()

        assert "# Sample Test Article Title" in markdown
        assert "**Authors:**" in markdown
        assert "**Journal:**" in markdown
        assert "**DOI:**" in markdown
        assert "## Abstract" in markdown
        assert "## Introduction" in markdown
        assert "## Methods" in markdown

    def test_to_markdown_no_parse(self):
        """Test converting to markdown without parsing first."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.to_markdown()

    def test_to_markdown_headers(self):
        """Test markdown headers are properly formatted."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        markdown = parser.to_markdown()

        # Check for proper markdown header syntax
        assert markdown.startswith("# ")
        assert "## Abstract" in markdown
        assert "## Introduction" in markdown


class TestFullTextXMLParserExtractTables:
    """Test table extraction."""

    def test_extract_tables(self):
        """Test extracting tables from XML."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        tables = parser.extract_tables()

        assert len(tables) == 1
        table = tables[0]

        assert table["id"] == "t1"
        assert table["label"] == "Table 1"
        assert "Sample data table" in table["caption"]
        assert len(table["headers"]) == 2
        assert "Column 1" in table["headers"]
        assert "Column 2" in table["headers"]
        assert len(table["rows"]) == 2
        assert table["rows"][0] == ["Data 1", "Data 2"]
        assert table["rows"][1] == ["Data 3", "Data 4"]

    def test_extract_tables_no_parse(self):
        """Test extracting tables without parsing first."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.extract_tables()

    def test_extract_tables_no_tables(self):
        """Test extracting tables when none exist."""
        xml_no_tables = "<article><front></front><body></body></article>"
        parser = FullTextXMLParser(xml_no_tables)
        tables = parser.extract_tables()

        assert len(tables) == 0


class TestFullTextXMLParserExtractReferences:
    """Test reference extraction."""

    def test_extract_references(self):
        """Test extracting references from XML."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        references = parser.extract_references()

        assert len(references) == 1
        ref = references[0]

        assert ref["id"] == "ref1"
        assert ref["label"] == "1"
        assert "A Author" in ref["authors"]
        assert ref["title"] == "Reference Article Title"
        assert ref["source"] == "Reference Journal"
        assert ref["year"] == "2020"
        assert ref["volume"] == "5"
        assert ref["pages"] == "10-20"

    def test_extract_references_no_parse(self):
        """Test extracting references without parsing first."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.extract_references()

    def test_extract_references_no_refs(self):
        """Test extracting references when none exist."""
        xml_no_refs = "<article><front></front><body></body><back></back></article>"
        parser = FullTextXMLParser(xml_no_refs)
        references = parser.extract_references()

        assert len(references) == 0


class TestFullTextXMLParserGetFullTextSections:
    """Test section extraction."""

    def test_get_full_text_sections(self):
        """Test extracting full text sections."""
        parser = FullTextXMLParser(SAMPLE_ARTICLE_XML)
        sections = parser.get_full_text_sections()

        assert len(sections) >= 2
        
        # Check Introduction section
        intro = next((s for s in sections if s["title"] == "Introduction"), None)
        assert intro is not None
        assert "introduction section" in intro["content"].lower()

        # Check Methods section
        methods = next((s for s in sections if s["title"] == "Methods"), None)
        assert methods is not None
        assert "methods" in methods["content"].lower()

    def test_get_full_text_sections_no_parse(self):
        """Test getting sections without parsing first."""
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.get_full_text_sections()

    def test_get_full_text_sections_no_body(self):
        """Test getting sections when no body exists."""
        xml_no_body = "<article><front></front></article>"
        parser = FullTextXMLParser(xml_no_body)
        sections = parser.get_full_text_sections()

        assert len(sections) == 0


class TestFullTextXMLParserRealFile:
    """Test with real PMC XML file fixtures."""

    @pytest.fixture
    def fixture_dir(self):
        """Get the fixtures directory."""
        return Path(__file__).parent.parent.parent / "fixtures" / "fulltext_downloads"

    def test_parse_pmc3258128(self, fixture_dir):
        """Test parsing real PMC3258128 XML file."""
        xml_file = fixture_dir / "PMC3258128.xml"
        if not xml_file.exists():
            pytest.skip("Fixture file not found")

        with open(xml_file, "r", encoding="utf-8") as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        
        # Test metadata extraction
        metadata = parser.extract_metadata()
        assert metadata["pmcid"] == "3258128"
        assert metadata["doi"] is not None
        assert metadata["title"] is not None
        assert len(metadata["authors"]) > 0

        # Test plaintext conversion
        plaintext = parser.to_plaintext()
        assert len(plaintext) > 100
        assert metadata["title"] in plaintext

        # Test markdown conversion
        markdown = parser.to_markdown()
        assert len(markdown) > 100
        assert "# " in markdown

        # Test table extraction
        tables = parser.extract_tables()
        assert isinstance(tables, list)

        # Test reference extraction
        references = parser.extract_references()
        assert len(references) > 0

        # Test section extraction
        sections = parser.get_full_text_sections()
        assert len(sections) > 0

    def test_parse_pmc3359999(self, fixture_dir):
        """Test parsing real PMC3359999 XML file."""
        xml_file = fixture_dir / "PMC3359999.xml"
        if not xml_file.exists():
            pytest.skip("Fixture file not found")

        with open(xml_file, "r", encoding="utf-8") as f:
            xml_content = f.read()

        parser = FullTextXMLParser(xml_content)
        
        # Test that basic operations work
        metadata = parser.extract_metadata()
        assert metadata["pmcid"] == "3359999"
        
        plaintext = parser.to_plaintext()
        assert len(plaintext) > 0
        
        markdown = parser.to_markdown()
        assert len(markdown) > 0


class TestFullTextXMLParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_xml_with_namespaces(self):
        """Test parsing XML with namespaces."""
        xml_with_ns = '''<?xml version="1.0"?>
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
        <front><article-meta>
        <article-id pub-id-type="pmcid">123</article-id>
        </article-meta></front>
        </article>'''
        
        parser = FullTextXMLParser(xml_with_ns)
        metadata = parser.extract_metadata()
        assert metadata["pmcid"] == "123"

    def test_get_text_content_with_nested_elements(self):
        """Test extracting text from nested elements."""
        xml = '''<article><front><article-meta>
        <article-title>Title with <italic>italic</italic> and <bold>bold</bold> text</article-title>
        </article-meta></front></article>'''
        
        parser = FullTextXMLParser(xml)
        metadata = parser.extract_metadata()
        assert "italic" in metadata["title"]
        assert "bold" in metadata["title"]

    def test_extract_metadata_with_missing_dates(self):
        """Test extracting metadata when publication date components are missing."""
        xml = '''<article><front><article-meta>
        <pub-date pub-type="ppub"><year>2021</year></pub-date>
        </article-meta></front></article>'''
        
        parser = FullTextXMLParser(xml)
        metadata = parser.extract_metadata()
        assert metadata["pub_date"] == "2021"

    def test_table_without_headers(self):
        """Test parsing table without thead."""
        xml = '''<article><body>
        <table-wrap id="t1">
        <table><tbody>
        <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </tbody></table>
        </table-wrap>
        </body></article>'''
        
        parser = FullTextXMLParser(xml)
        tables = parser.extract_tables()
        assert len(tables) == 1
        assert len(tables[0]["headers"]) == 0
        assert len(tables[0]["rows"]) == 1
