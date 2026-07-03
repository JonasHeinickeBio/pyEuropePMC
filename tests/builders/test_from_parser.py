"""Integration tests for builder layer."""

import pytest

from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.builders.from_parser import _build_author_entity, _create_grant_entities
from pyeuropepmc.models import AuthorEntity, GrantEntity, JournalEntity
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
        paper, authors, sections, tables, figures, references = build_paper_entities(parser)

        # Check paper entity
        assert paper.pmcid == "1234567"
        assert paper.doi == "10.1234/test.2021.001"
        assert paper.title == "Sample Test Article Title"
        assert isinstance(paper.journal, JournalEntity)
        # Journal entity stores title as a string
        assert paper.journal.title == "Test Journal"
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
        assert references[0].journal == "Nature"

    def test_build_entities_normalizes_data(self):
        """Test that built entities can be normalized."""
        parser = FullTextXMLParser(SAMPLE_XML)
        paper, authors, sections, tables, figures, references = build_paper_entities(parser)

        # Normalize
        paper.normalize()
        for author in authors:
            author.normalize()
        # Normalize journal if it exists
        if paper.journal and hasattr(paper.journal, "normalize"):
            paper.journal.normalize()

        # Check normalization worked
        assert paper.doi == "10.1234/test.2021.001"  # Should be lowercase

    def test_build_entities_validates(self):
        """Test that built entities can be validated."""
        parser = FullTextXMLParser(SAMPLE_XML)
        paper, authors, sections, tables, figures, references = build_paper_entities(parser)

        # Validate journal first if it exists
        if paper.journal and hasattr(paper.journal, "validate"):
            paper.journal.validate()

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
        paper, authors, sections, tables, figures, references = build_paper_entities(parser)

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
        paper, authors, sections, tables, figures, references = build_paper_entities(parser)

        assert paper.pmcid == "TEST123"
        assert paper.title == "Minimal Article"
        # May have empty lists but should not raise
        assert isinstance(authors, list)
        assert isinstance(sections, list)
        assert isinstance(tables, list)
        assert isinstance(references, list)


class TestCreateGrantEntities:
    """Tests for _create_grant_entities helper."""

    def test_create_grant_entities_none(self):
        """Test with None funding data."""
        assert _create_grant_entities(None) is None

    def test_create_grant_entities_empty(self):
        """Test with empty funding data."""
        assert _create_grant_entities([]) is None

    def test_create_grant_entities_with_recipients(self):
        """Test creating grant entities with recipients."""
        funding_data = [
            {
                "fundref_doi": "10.13039/100000001",
                "source": "NSF",
                "award_id": "12345",
                "recipients": [
                    {"full_name": "Dr. Smith", "given_names": "John", "surname": "Smith"}
                ],
            }
        ]
        grants = _create_grant_entities(funding_data)
        assert grants is not None
        assert len(grants) == 1
        grant = grants[0]
        assert isinstance(grant, GrantEntity)
        assert grant.funding_source == "NSF"
        assert grant.award_id == "12345"
        assert grant.recipients is not None
        assert len(grant.recipients) == 1
        assert grant.recipients[0].full_name == "Dr. Smith"

    def test_create_grant_entities_no_recipients(self):
        """Test creating grant entities without recipients."""
        funding_data = [
            {"fundref_doi": "10.13039/100000002", "source": "NIH", "award_id": "67890"}
        ]
        grants = _create_grant_entities(funding_data)
        assert grants is not None
        assert len(grants) == 1
        assert grants[0].recipients is None

    def test_create_grant_entities_recipient_string_fallback(self):
        """Test fallback to recipient_full/recipient_name for legacy data."""
        funding_data = [
            {"source": "Wellcome Trust", "recipient_full": "Dr. Jane Doe"}
        ]
        grants = _create_grant_entities(funding_data)
        assert grants is not None
        assert grants[0].recipient == "Dr. Jane Doe"

    def test_create_grant_entities_malformed_funder(self):
        """Test malformed funder (not a dict) is skipped."""
        funding_data = [None, {"source": "Valid"}]
        grants = _create_grant_entities(funding_data)
        assert grants is not None
        assert len(grants) == 1
        assert grants[0].funding_source == "Valid"


class TestBuildAuthorEntity:
    """Tests for _build_author_entity helper."""

    def test_build_author_string(self):
        """Test building author from string (backward compat)."""
        author = _build_author_entity("John Smith", [])
        assert isinstance(author, AuthorEntity)
        assert author.full_name == "John Smith"

    def test_build_author_with_affiliations(self):
        """Test building author with affiliation references."""
        author_data = {
            "full_name": "John Smith",
            "given_names": "John",
            "surname": "Smith",
            "orcid": "https://orcid.org/0000-0003-3442-7216",
            "affiliation_refs": ["aff1", "aff2"],
        }
        affiliations = [
            {
                "id": "aff1",
                "institution": "University of Test",
                "institution_text": "Dept of Biology, University of Test, City",
                "city": "City",
                "country": "USA",
                "text": "Dept of Biology, University of Test, City, USA",
            },
            {
                "id": "aff2",
                "institution": "Research Lab",
                "text": "Research Lab, Other City",
            },
        ]
        author = _build_author_entity(author_data, affiliations)
        assert author.full_name == "John Smith"
        assert author.first_name == "John"
        assert author.last_name == "Smith"
        assert author.orcid == "https://orcid.org/0000-0003-3442-7216"
        assert author.affiliation_text is not None
        assert "University of Test" in author.affiliation_text
        assert "Research Lab" in author.affiliation_text
        assert author.institutions is not None
        assert len(author.institutions) == 2

    def test_build_author_missing_name_raises(self):
        """Test that missing full_name raises ValueError."""
        with pytest.raises(ValueError, match="Author data must contain full_name"):
            _build_author_entity({"given_names": "John"}, [])

    def test_build_author_no_affiliations(self):
        """Test building author with no affiliation refs."""
        author_data = {
            "full_name": "Jane Doe",
            "orcid": "0000-0003-3442-7216",
        }
        author = _build_author_entity(author_data, [])
        assert author.affiliation_text is None
        assert author.institutions is None or author.institutions == []


class TestBuildPaperEntitiesExtended:
    """Extended tests for build_paper_entities."""

    def test_build_with_search_data(self):
        """Test building entities with search API data merged in."""
        parser = FullTextXMLParser(SAMPLE_XML)
        search_data = {
            "pmid": "12345678",
            "citedByCount": 42,
            "pubType": "journal article",
            "journalIssn": "1234-5678",
            "isOpenAccess": "Y",
            "inEPMC": "Y",
            "inPMC": "Y",
            "hasPDF": "Y",
            "hasSuppl": "Y",
            "hasReferences": "Y",
            "hasTextMinedTerms": "Y",
            "hasDbCrossReferences": "N",
            "hasLabsLinks": "Y",
            "hasTMAccessionNumbers": "Y",
            "firstIndexDate": "2021-01-01",
            "firstPublicationDate": "2021-01-15",
            "pubYear": "2021",
        }
        paper, authors, sections, tables, figures, references = build_paper_entities(
            parser, search_data
        )
        assert paper.pmid == "12345678"
        assert paper.cited_by_count == 42
        assert paper.pub_type == "journal article"
        assert paper.is_oa is True
        assert paper.in_epmc is True
        assert paper.in_pmc is True
        assert paper.has_pdf is True
        assert paper.has_supplementary is True
        assert paper.has_references is True
        assert paper.has_text_mined_terms is True
        # NOTE: the code sets has_db_cross_references = True when hasDbCrossReferences == "N"
        # (see comment in from_parser.py about API using "N" for no)
        assert paper.has_db_cross_references is True
        assert paper.first_index_date == "2021-01-01"
        assert paper.publication_year == 2021
