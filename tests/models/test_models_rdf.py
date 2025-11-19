"""Unit tests for data models and RDF serialization."""

import pytest
from rdflib import Graph, Namespace

from pyeuropepmc.mappers import RDFMapper
from pyeuropepmc.models import (
    AuthorEntity,
    BaseEntity,
    PaperEntity,
    ReferenceEntity,
    SectionEntity,
    TableEntity,
    TableRowEntity,
)

# Test namespaces
BIBO = Namespace("http://purl.org/ontology/bibo/")
DCT = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")


class TestBaseEntity:
    """Tests for BaseEntity."""

    def test_base_entity_creation(self):
        """Test basic entity creation."""
        entity = BaseEntity(id="test-123", label="Test Entity")
        assert entity.id == "test-123"
        assert entity.label == "Test Entity"

    def test_mint_uri(self):
        """Test URI minting."""
        entity = BaseEntity(id="test-123")
        uri = entity.mint_uri("entity")
        assert "test-123" in str(uri)
        assert "entity" in str(uri)

    def test_mint_uri_without_id(self):
        """Test URI minting generates UUID when no ID."""
        entity = BaseEntity()
        uri = entity.mint_uri("entity")
        assert "entity" in str(uri)
        # Should contain a UUID-like string
        assert len(str(uri)) > 40

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entity = BaseEntity(id="test", label="Test")
        data = entity.to_dict()
        assert data["id"] == "test"
        assert data["label"] == "Test"

    def test_validate(self):
        """Test default validate does nothing."""
        entity = BaseEntity()
        entity.validate()  # Should not raise

    def test_normalize(self):
        """Test default normalize does nothing."""
        entity = BaseEntity()
        entity.normalize()  # Should not raise


class TestAuthorEntity:
    """Tests for AuthorEntity."""

    def test_author_creation(self):
        """Test author entity creation."""
        author = AuthorEntity(
            full_name="John Smith",
            first_name="John",
            last_name="Smith",
            orcid="0000-0001-2345-6789",
        )
        assert author.full_name == "John Smith"
        assert author.first_name == "John"
        assert author.last_name == "Smith"
        assert author.orcid == "0000-0001-2345-6789"

    def test_author_post_init(self):
        """Test author post-initialization."""
        author = AuthorEntity(full_name="John Smith")
        assert "foaf:Person" in author.types
        assert author.label == "John Smith"

    def test_author_validate_success(self):
        """Test author validation with valid data."""
        author = AuthorEntity(full_name="John Smith")
        author.validate()  # Should not raise

    def test_author_validate_failure(self):
        """Test author validation with invalid data."""
        author = AuthorEntity(full_name="")
        with pytest.raises(ValueError, match="must have a full_name"):
            author.validate()

    def test_author_normalize(self):
        """Test author normalization."""
        author = AuthorEntity(
            full_name="  John Smith  ",
            first_name="  John  ",
            last_name="  Smith  ",
        )
        author.normalize()
        assert author.full_name == "John Smith"
        assert author.first_name == "John"
        assert author.last_name == "Smith"

    def test_author_to_rdf(self):
        """Test author RDF serialization."""
        mapper = RDFMapper()
        g = Graph()
        author = AuthorEntity(full_name="John Smith", first_name="John", last_name="Smith")
        uri = author.to_rdf(g, mapper=mapper)

        # Check that triples were added
        assert len(g) > 0
        # Check for name
        name_values = list(g.objects(uri, FOAF.name))
        assert len(name_values) == 1
        assert str(name_values[0]) == "John Smith"


class TestPaperEntity:
    """Tests for PaperEntity."""

    def test_paper_creation(self):
        """Test paper entity creation."""
        paper = PaperEntity(
            pmcid="PMC1234567",
            doi="10.1234/test.2021.001",
            title="Test Article",
        )
        assert paper.pmcid == "PMC1234567"
        assert paper.doi == "10.1234/test.2021.001"
        assert paper.title == "Test Article"

    def test_paper_post_init(self):
        """Test paper post-initialization."""
        paper = PaperEntity(title="Test Article")
        assert "bibo:AcademicArticle" in paper.types
        assert paper.label == "Test Article"

    def test_paper_validate_success(self):
        """Test paper validation with valid data."""
        paper = PaperEntity(title="Test Article")
        paper.validate()  # Should not raise

    def test_paper_validate_failure(self):
        """Test paper validation with invalid data."""
        paper = PaperEntity()
        with pytest.raises(ValueError, match="must have at least one"):
            paper.validate()

    def test_paper_normalize(self):
        """Test paper normalization."""
        paper = PaperEntity(
            doi="HTTPS://DOI.ORG/10.1234/TEST.2021.001",
            title="  Test Article  ",
        )
        paper.normalize()
        assert paper.doi == "10.1234/test.2021.001"
        assert paper.title == "Test Article"

    def test_paper_to_rdf(self):
        """Test paper RDF serialization."""
        mapper = RDFMapper()
        g = Graph()
        paper = PaperEntity(
            pmcid="PMC1234567",
            title="Test Article",
            doi="10.1234/test.2021.001",
        )
        uri = paper.to_rdf(g, mapper=mapper)

        # Check that triples were added
        assert len(g) > 0
        # Check for title
        title_values = list(g.objects(uri, DCT.title))
        assert len(title_values) == 1
        assert str(title_values[0]) == "Test Article"


class TestSectionEntity:
    """Tests for SectionEntity."""

    def test_section_creation(self):
        """Test section entity creation."""
        section = SectionEntity(
            title="Introduction",
            content="This is the introduction...",
        )
        assert section.title == "Introduction"
        assert section.content == "This is the introduction..."

    def test_section_post_init(self):
        """Test section post-initialization."""
        section = SectionEntity(title="Introduction", content="Text")
        assert "bibo:DocumentPart" in section.types
        assert "nif:Context" in section.types
        assert section.label == "Introduction"

    def test_section_validate_success(self):
        """Test section validation with valid data."""
        section = SectionEntity(content="Text")
        section.validate()  # Should not raise

    def test_section_validate_failure(self):
        """Test section validation with invalid data."""
        section = SectionEntity()
        with pytest.raises(ValueError, match="must have content"):
            section.validate()

    def test_section_normalize(self):
        """Test section normalization."""
        section = SectionEntity(
            title="  Introduction  ",
            content="  This is the introduction...  ",
        )
        section.normalize()
        assert section.title == "Introduction"
        assert section.content == "This is the introduction..."

    def test_section_to_rdf(self):
        """Test section RDF serialization."""
        mapper = RDFMapper()
        g = Graph()
        section = SectionEntity(
            title="Introduction",
            content="This is the introduction...",
        )
        uri = section.to_rdf(g, mapper=mapper)

        # Check that triples were added
        assert len(g) > 0
        # Check for content
        content_values = list(g.objects(uri, NIF.isString))
        assert len(content_values) == 1
        assert "introduction" in str(content_values[0]).lower()


class TestTableEntity:
    """Tests for TableEntity."""

    def test_table_creation(self):
        """Test table entity creation."""
        table = TableEntity(
            table_label="Table 1",
            caption="Sample data",
        )
        assert table.table_label == "Table 1"
        assert table.caption == "Sample data"

    def test_table_post_init(self):
        """Test table post-initialization."""
        table = TableEntity(table_label="Table 1")
        assert "bibo:Table" in table.types
        assert table.label == "Table 1"

    def test_table_normalize(self):
        """Test table normalization."""
        table = TableEntity(
            table_label="  Table 1  ",
            caption="  Sample data  ",
        )
        table.normalize()
        assert table.table_label == "Table 1"
        assert table.caption == "Sample data"


class TestTableRowEntity:
    """Tests for TableRowEntity."""

    def test_row_creation(self):
        """Test table row entity creation."""
        row = TableRowEntity(
            cells=["Val1", "Val2"],
        )
        assert row.cells == ["Val1", "Val2"]

    def test_row_post_init(self):
        """Test row post-initialization."""
        row = TableRowEntity(cells=["Val1", "Val2"])
        assert "bibo:Row" in row.types

    def test_row_validate_success(self):
        """Test row validation with valid data."""
        row = TableRowEntity(cells=["Val1"])
        row.validate()  # Should not raise

    def test_row_validate_failure(self):
        """Test row validation with invalid data."""
        row = TableRowEntity()
        with pytest.raises(ValueError, match="must have cells"):
            row.validate()

    def test_row_normalize(self):
        """Test row normalization."""
        row = TableRowEntity(
            cells=["  Val1  ", "  Val2  "],
        )
        row.normalize()
        assert row.cells == ["Val1", "Val2"]


class TestReferenceEntity:
    """Tests for ReferenceEntity."""

    def test_reference_creation(self):
        """Test reference entity creation."""
        ref = ReferenceEntity(
            title="Sample Article",
            source="Nature",
            year="2021",
            doi="10.1038/nature12345",
        )
        assert ref.title == "Sample Article"
        assert ref.source == "Nature"
        assert ref.year == "2021"
        assert ref.doi == "10.1038/nature12345"

    def test_reference_post_init(self):
        """Test reference post-initialization."""
        ref = ReferenceEntity(title="Sample Article")
        assert "bibo:Document" in ref.types
        assert ref.label == "Sample Article"

    def test_reference_normalize(self):
        """Test reference normalization."""
        ref = ReferenceEntity(
            doi="HTTPS://DOI.ORG/10.1038/NATURE12345",
            title="  Sample Article  ",
        )
        ref.normalize()
        assert ref.doi == "10.1038/nature12345"
        assert ref.title == "Sample Article"

    def test_reference_to_rdf(self):
        """Test reference RDF serialization."""
        mapper = RDFMapper()
        g = Graph()
        ref = ReferenceEntity(
            title="Sample Article",
            doi="10.1038/nature12345",
        )
        uri = ref.to_rdf(g, mapper=mapper)

        # Check that triples were added
        assert len(g) > 0
        # Check for title
        title_values = list(g.objects(uri, DCT.title))
        assert len(title_values) == 1
        assert str(title_values[0]) == "Sample Article"
