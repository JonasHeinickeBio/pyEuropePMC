"""Integration tests for builder layer."""

from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser

# Sample XML for testing
SAMPLE_XML = """<?xml version="1.0"?>
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
<article-title>Referenced Article Title</article-title>
<source>Nature</source>
<year>2020</year>
<volume>580</volume>
<fpage>123</fpage>
<lpage>127</lpage>
<pub-id pub-id-type="doi">10.1038/s41586-020-1234-5</pub-id>
</element-citation>
</ref>
</ref-list>
</back>
</article>
"""


class TestBuildPaperEntities:
    """Tests for build_paper_entities function."""

    def test_build_paper_entities(self):
        """Test building entities from parser."""
        parser = FullTextXMLParser(SAMPLE_XML)
        paper, authors, sections, tables, references = build_paper_entities(parser)

        # Check paper entity
        assert paper.pmcid == "1234567"
        assert paper.doi == "10.1234/test.2021.001"
        assert paper.title == "Sample Test Article Title"
        assert paper.journal == "Test Journal"
        assert paper.volume == "10"
        assert paper.issue == "5"
        assert paper.pages == "100-110"
        assert len(paper.keywords) == 2

        # Check authors
        assert len(authors) == 2
        assert "John" in authors[0].full_name
        assert "Jane" in authors[1].full_name

        # Check sections
        assert len(sections) >= 2
        section_titles = [s.title for s in sections]
        assert "Introduction" in section_titles
        assert "Methods" in section_titles

        # Check references
        assert len(references) >= 1
        assert references[0].source == "Nature"

    def test_build_entities_normalizes_data(self):
        """Test that built entities can be normalized."""
        parser = FullTextXMLParser(SAMPLE_XML)
        paper, authors, sections, tables, references = build_paper_entities(parser)

        # Normalize
        paper.normalize()
        for author in authors:
            author.normalize()

        # Check normalization worked
        assert paper.doi == "10.1234/test.2021.001"  # Should be lowercase

    def test_build_entities_validates(self):
        """Test that built entities can be validated."""
        parser = FullTextXMLParser(SAMPLE_XML)
        paper, authors, sections, tables, references = build_paper_entities(parser)

        # Validate - should not raise
        paper.validate()
        for author in authors:
            author.validate()
        for section in sections:
            section.validate()

    def test_build_entities_to_rdf(self):
        """Test that built entities can be converted to RDF."""
        from rdflib import Graph

        from pyeuropepmc.mappers import RDFMapper

        parser = FullTextXMLParser(SAMPLE_XML)
        paper, authors, sections, tables, references = build_paper_entities(parser)

        mapper = RDFMapper()
        g = Graph()

        # Convert to RDF - should not raise
        paper_uri = paper.to_rdf(g, mapper=mapper)
        assert paper_uri is not None

        for author in authors:
            author.to_rdf(g, mapper=mapper)

        for section in sections:
            section.to_rdf(g, mapper=mapper)

        # Check graph has triples
        assert len(g) > 0

    def test_build_entities_empty_sections(self):
        """Test building entities with minimal XML."""
        minimal_xml = """<?xml version="1.0"?>
        <article>
        <front>
        <article-meta>
        <article-id pub-id-type="pmcid">TEST123</article-id>
        <title-group>
        <article-title>Minimal Article</article-title>
        </title-group>
        </article-meta>
        </front>
        </article>
        """
        parser = FullTextXMLParser(minimal_xml)
        paper, authors, sections, tables, references = build_paper_entities(parser)

        assert paper.pmcid == "TEST123"
        assert paper.title == "Minimal Article"
        # May have empty lists but should not raise
        assert isinstance(authors, list)
        assert isinstance(sections, list)
        assert isinstance(tables, list)
        assert isinstance(references, list)
