"""Tests for PlaintextConverter."""
import pytest
from xml.etree import ElementTree as ET

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.processing.converters.plaintext_converter import PlaintextConverter


class TestPlaintextConverter:
    """Tests for PlaintextConverter."""

    def test_to_plaintext_basic_article(self):
        """Test basic article conversion."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test Article</article-title>
</article-meta>
</front>
<body>
<sec><title>Introduction</title><p>This is the intro.</p></sec>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Test Article" in result
        assert "Introduction" in result
        assert "This is the intro." in result

    def test_to_plaintext_with_authors(self):
        """Test article with authors."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
<contrib-group>
<contrib contrib-type="author">
<name><surname>Smith</surname><given-names>John</given-names></name>
</contrib>
</contrib-group>
</article-meta>
</front>
<body/>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Authors" in result

    def test_to_plaintext_with_abstract(self):
        """Test article with abstract."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
</article-meta>
</front>
<body/>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        # Should not fail even though no abstract
        result = converter.to_plaintext()
        assert "Abstract" not in result

    def test_to_plaintext_with_acknowledgments(self):
        """Test article with acknowledgments."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
</article-meta>
</front>
<body/>
<back>
<ack><p>Thanks to everyone.</p></ack>
</back>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Acknowledgments" in result
        assert "Thanks" in result

    def test_to_plaintext_with_appendix(self):
        """Test article with appendix."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
</article-meta>
</front>
<body/>
<back>
<app><title>Supplementary Data</title><p>Extra content here.</p></app>
</back>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Appendix" in result
        assert "Supplementary Data" in result

    def test_to_plaintext_appendix_no_title(self):
        """Test appendix without title."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
</article-meta>
</front>
<body/>
<back>
<app><p>No title here.</p></app>
</back>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Appendix" in result

    def test_to_plaintext_with_glossary(self):
        """Test article with glossary."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
</article-meta>
</front>
<body/>
<back>
<glossary><p>Terms and definitions.</p></glossary>
</back>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Glossary" in result

    def test_bare_p_under_body_plos_style(self):
        """Test bare <p> elements directly under <body> (PLOS style)."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>PLOS Test</article-title>
</article-meta>
</front>
<body>
<p>First paragraph without sec.</p>
<p>Second paragraph.</p>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_section_with_ordered_list(self):
        """Test section with ordered list."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>List Test</article-title>
</article-meta>
</front>
<body>
<sec><title>Methods</title>
<list list-type="ordered">
<list-item><p>Step one</p></list-item>
<list-item><p>Step two</p></list-item>
</list>
</sec>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "1. Step one" in result
        assert "2. Step two" in result

    def test_section_with_unordered_list(self):
        """Test section with unordered list."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>List Test</article-title>
</article-meta>
</front>
<body>
<sec><title>Items</title>
<list>
<list-item><p>Item A</p></list-item>
<list-item><p>Item B</p></list-item>
</list>
</sec>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Item A" in result
        assert "Item B" in result

    def test_section_with_table(self):
        """Test section with table."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Table Test</article-title>
</article-meta>
</front>
<body>
<sec><title>Data</title>
<table>
<caption><p>Sample Data</p></caption>
<tr><th>Name</th><th>Value</th></tr>
<tr><td>A</td><td>1</td></tr>
</table>
</sec>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Table: Sample Data" in result
        assert "Name | Value" in result
        assert "A | 1" in result

    def test_table_without_rows(self):
        """Test table element without rows."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Table Test</article-title>
</article-meta>
</front>
<body>
<sec><title>Data</title>
<table>
<caption><p>Empty Table</p></caption>
</table>
</sec>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        result = converter.to_plaintext()
        assert "Table: Empty Table" in result

    def test_no_root_error(self):
        """Test that to_plaintext raises error without root."""
        converter = PlaintextConverter()
        with pytest.raises(ParsingError, match="PARSE003"):
            converter.to_plaintext()

    def test_author_parser_property(self):
        """Test author_parser property creates parser lazily."""
        converter = PlaintextConverter()
        assert converter._author_parser is None
        # Accessing the property should not fail even without root
        # (it will fail when trying to actually parse)
        parser = converter.author_parser
        assert parser is not None
        assert converter._author_parser is not None

    def test_process_formatting_in_text(self):
        """Test _process_formatting_in_text returns text unchanged."""
        xml = """<?xml version="1.0"?>
<article>
<front>
<article-meta>
<article-title>Test</article-title>
</article-meta>
</front>
<body>
<sec><title>S</title><p>Regular text</p></sec>
</body>
</article>"""
        root = ET.fromstring(xml)
        converter = PlaintextConverter(root)
        # The method is trivial but should not modify text
        result = converter._process_formatting_in_text("some text")
        assert result == "some text"
