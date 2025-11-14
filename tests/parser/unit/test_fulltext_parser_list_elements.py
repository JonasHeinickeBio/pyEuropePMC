import pytest
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.core.exceptions import ParsingError

SAMPLE_XML = '''<article><front><article-meta><article-id pub-id-type="pmcid">123</article-id></article-meta></front><body><sec><title>Intro</title><p>Text</p></sec><sec><title>Methods</title><p>Text</p></sec></body><back><custom/></back></article>'''

class TestFullTextXMLParserListElementTypes:
    def test_list_element_types_basic(self):
        parser = FullTextXMLParser(SAMPLE_XML)
        element_types = parser.list_element_types()
        # Should include all unique tags, no namespace
        assert set(element_types) >= {"article", "front", "article-meta", "article-id", "body", "sec", "title", "p", "back", "custom"}
        assert element_types == sorted(element_types)

    def test_list_element_types_no_parse(self):
        parser = FullTextXMLParser()
        with pytest.raises(ParsingError):
            parser.list_element_types()

    def test_list_element_types_with_namespace(self):
        xml = '''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="pmcid">123</article-id></article-meta></front><body><sec><title>Intro</title><p>Text</p></sec></body></article>'''
        parser = FullTextXMLParser(xml)
        element_types = parser.list_element_types()
        # Should not include namespace in tag names
        assert "article" in element_types
        assert all("{" not in tag for tag in element_types)
