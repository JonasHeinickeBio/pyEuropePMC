"""Unit tests for all data models."""

import pytest

from pyeuropepmc.models import (
    AuthorEntity,
    BaseEntity,
    FigureEntity,
    PaperEntity,
    ReferenceEntity,
    SectionEntity,
    TableEntity,
    TableRowEntity,
)


class TestBaseEntity:
    """Tests for BaseEntity."""

    def test_creation_with_all_fields(self):
        """Test creating BaseEntity with all fields."""
        entity = BaseEntity(
            id="test-123",
            label="Test Entity",
            source_uri="urn:test:123",
            confidence=0.95,
            types=["ex:TestType"]
        )
        assert entity.id == "test-123"
        assert entity.label == "Test Entity"
        assert entity.source_uri == "urn:test:123"
        assert entity.confidence == 0.95
        assert entity.types == ["ex:TestType"]

    def test_creation_defaults(self):
        """Test creating BaseEntity with defaults."""
        entity = BaseEntity()
        assert entity.id is None
        assert entity.label is None
        assert entity.source_uri is None
        assert entity.confidence is None
        assert entity.types == []

    def test_mint_uri_with_id(self):
        """Test URI minting with ID."""
        entity = BaseEntity(id="test-123")
        uri = entity.mint_uri("entity")
        assert str(uri) == "http://example.org/data/entity/test-123"

    def test_mint_uri_without_id(self):
        """Test URI minting without ID generates UUID."""
        entity = BaseEntity()
        uri = entity.mint_uri("entity")
        assert "entity" in str(uri)
        assert len(str(uri)) > 40  # UUID-like length

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entity = BaseEntity(id="test", label="Test", confidence=0.8)
        data = entity.to_dict()
        assert data["id"] == "test"
        assert data["label"] == "Test"
        assert data["confidence"] == 0.8

    def test_validate_default(self):
        """Test default validate method."""
        entity = BaseEntity()
        entity.validate()  # Should not raise

    def test_normalize_default(self):
        """Test default normalize method."""
        entity = BaseEntity()
        entity.normalize()  # Should not raise

    def test_to_rdf_without_mapper_raises(self):
        """Test to_rdf raises without mapper."""
        entity = BaseEntity()
        with pytest.raises(ValueError, match="RDF mapper required"):
            entity.to_rdf(None)


class TestAuthorEntity:
    """Tests for AuthorEntity."""

    def test_creation_full(self):
        """Test creating AuthorEntity with all fields."""
        author = AuthorEntity(
            full_name="John Smith",
            first_name="John",
            last_name="Smith",
            orcid="0000-0001-2345-6789",
            affiliation_text="Test University"
        )
        assert author.full_name == "John Smith"
        assert author.first_name == "John"
        assert author.last_name == "Smith"
        assert author.orcid == "0000-0001-2345-6789"
        assert author.affiliation_text == "Test University"

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        author = AuthorEntity(full_name="Jane Doe")
        assert "foaf:Person" in author.types
        assert author.label == "Jane Doe"

    def test_post_init_empty_name(self):
        """Test post-init with empty name."""
        author = AuthorEntity()
        assert author.label == ""

    def test_validate_success(self):
        """Test validation with valid data."""
        author = AuthorEntity(full_name="John Smith")
        author.validate()  # Should not raise

    def test_validate_failure_empty_name(self):
        """Test validation fails with empty name."""
        author = AuthorEntity(full_name="")
        with pytest.raises(ValueError, match="AuthorEntity must have either full_name or name"):
            author.validate()

    def test_validate_failure_whitespace_name(self):
        """Test validation fails with whitespace name."""
        author = AuthorEntity(full_name="   ")
        with pytest.raises(ValueError, match="AuthorEntity must have either full_name or name"):
            author.validate()

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace."""
        author = AuthorEntity(
            full_name="  John Smith  ",
            first_name="  John  ",
            last_name="  Smith  ",
            affiliation_text="  University  "
        )
        author.normalize()
        assert author.full_name == "John Smith"
        assert author.first_name == "John"
        assert author.last_name == "Smith"
        assert author.affiliation_text == "University"


class TestFigureEntity:
    """Tests for FigureEntity."""

    def test_creation_full(self):
        """Test creating FigureEntity with all fields."""
        figure = FigureEntity(
            caption="Sample scatter plot showing correlation",
            figure_label="Figure 1",
            graphic_uri="https://example.com/figure1.png"
        )
        assert figure.caption == "Sample scatter plot showing correlation"
        assert figure.figure_label == "Figure 1"
        assert figure.graphic_uri == "https://example.com/figure1.png"

    def test_creation_minimal(self):
        """Test creating FigureEntity with minimal data."""
        figure = FigureEntity()
        assert figure.caption is None
        assert figure.figure_label is None
        assert figure.graphic_uri is None

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        figure = FigureEntity(figure_label="Figure 2")
        assert "bibo:Image" in figure.types
        assert figure.label == "Figure 2"

    def test_post_init_default_label(self):
        """Test post-init with default label."""
        figure = FigureEntity()
        assert figure.label == "Untitled Figure"

    def test_validate_always_passes(self):
        """Test that validate always passes (no validation rules)."""
        figure = FigureEntity()
        figure.validate()  # Should not raise

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace."""
        figure = FigureEntity(
            caption="  Sample plot  ",
            figure_label="  Figure 1  ",
            graphic_uri="  https://example.com/fig.png  "
        )
        figure.normalize()
        assert figure.caption == "Sample plot"
        assert figure.figure_label == "Figure 1"
        assert figure.graphic_uri == "https://example.com/fig.png"


class TestPaperEntity:
    """Tests for PaperEntity."""

    def test_creation_full(self):
        """Test creating PaperEntity with all fields."""
        paper = PaperEntity(
            pmcid="PMC1234567",
            doi="10.1234/test.2021.001",
            title="Test Article Title",
            journal="Test Journal",
            volume="10",
            issue="5",
            pages="100-110",
            pub_date="2021-01-01",
            keywords=["test", "article"]
        )
        assert paper.pmcid == "PMC1234567"
        assert paper.doi == "10.1234/test.2021.001"
        assert paper.title == "Test Article Title"
        assert paper.journal == "Test Journal"
        assert paper.volume == "10"
        assert paper.issue == "5"
        assert paper.pages == "100-110"
        assert paper.pub_date == "2021-01-01"
        assert paper.keywords == ["test", "article"]

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        paper = PaperEntity(title="Test Paper")
        assert "bibo:AcademicArticle" in paper.types
        assert paper.label == "Test Paper"

    def test_post_init_label_fallbacks(self):
        """Test label fallback logic."""
        # Title first
        paper1 = PaperEntity(title="Title")
        assert paper1.label == "Title"

        # DOI fallback
        paper2 = PaperEntity(doi="10.1234/test")
        assert paper2.label == "10.1234/test"

        # PMCID fallback
        paper3 = PaperEntity(pmcid="PMC123")
        assert paper3.label == "PMC123"

        # Empty fallback
        paper4 = PaperEntity()
        assert paper4.label == ""

    def test_validate_success_single_identifier(self):
        """Test validation passes with any single identifier."""
        PaperEntity(title="Test").validate()
        PaperEntity(doi="10.1234/test").validate()
        PaperEntity(pmcid="PMC123").validate()

    def test_validate_failure_no_identifiers(self):
        """Test validation fails with no identifiers."""
        paper = PaperEntity()
        with pytest.raises(ValueError, match="must have at least one"):
            paper.validate()

    def test_normalize_doi_and_whitespace(self):
        """Test DOI normalization and whitespace trimming."""
        paper = PaperEntity(
            doi="HTTPS://DOI.ORG/10.1234/TEST.2021.001",
            title="  Test Article  ",
            journal="  Journal  ",
            pmcid="  PMC123  "
        )
        paper.normalize()
        assert paper.doi == "10.1234/test.2021.001"
        assert paper.title == "Test Article"
        assert paper.journal == "Journal"
        assert paper.pmcid == "PMC123"


class TestReferenceEntity:
    """Tests for ReferenceEntity."""

    def test_creation_full(self):
        """Test creating ReferenceEntity with all fields."""
        ref = ReferenceEntity(
            title="Cited Article",
            source="Nature",
            year="2021",
            volume="590",
            pages="123-456",
            doi="10.1038/nature12345",
            authors="Smith J, Doe J"
        )
        assert ref.title == "Cited Article"
        assert ref.source == "Nature"
        assert ref.year == "2021"
        assert ref.volume == "590"
        assert ref.pages == "123-456"
        assert ref.doi == "10.1038/nature12345"
        assert ref.authors == "Smith J, Doe J"

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        ref = ReferenceEntity(title="Test Reference")
        assert "bibo:Document" in ref.types
        assert ref.label == "Test Reference"

    def test_post_init_empty_title(self):
        """Test post-init with empty title."""
        ref = ReferenceEntity()
        assert ref.label == "Untitled Reference"

    def test_validate_always_passes(self):
        """Test that validate always passes (no validation rules)."""
        ref = ReferenceEntity()
        ref.validate()  # Should not raise

    def test_normalize_doi_and_whitespace(self):
        """Test DOI normalization and whitespace trimming."""
        ref = ReferenceEntity(
            doi="HTTPS://DOI.ORG/10.1038/NATURE12345",
            title="  Cited Article  ",
            source="  Nature  ",
            authors="  Smith J  "
        )
        ref.normalize()
        assert ref.doi == "10.1038/nature12345"
        assert ref.title == "Cited Article"
        assert ref.source == "Nature"
        assert ref.authors == "  Smith J  "  # authors not normalized


class TestSectionEntity:
    """Tests for SectionEntity."""

    def test_creation_full(self):
        """Test creating SectionEntity with all fields."""
        section = SectionEntity(
            title="Introduction",
            content="This is the introduction section content.",
            begin_index=0,
            end_index=50
        )
        assert section.title == "Introduction"
        assert section.content == "This is the introduction section content."
        assert section.begin_index == 0
        assert section.end_index == 50

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        section = SectionEntity(title="Methods")
        assert "bibo:DocumentPart" in section.types
        assert "nif:Context" in section.types
        assert section.label == "Methods"

    def test_post_init_empty_title(self):
        """Test post-init with empty title."""
        section = SectionEntity(content="Content")
        assert section.label == "Untitled Section"

    def test_validate_success_with_content(self):
        """Test validation passes with content."""
        section = SectionEntity(content="Some content")
        section.validate()  # Should not raise

    def test_validate_failure_no_content(self):
        """Test validation fails without content."""
        section = SectionEntity(title="Empty")
        with pytest.raises(ValueError, match="must have content"):
            section.validate()

    def test_validate_failure_empty_content(self):
        """Test validation fails with None content."""
        section = SectionEntity(content=None)
        with pytest.raises(ValueError, match="must have content"):
            section.validate()

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace."""
        section = SectionEntity(
            title="  Introduction  ",
            content="  This is content.  ",
            begin_index=0,
            end_index=50
        )
        section.normalize()
        assert section.title == "Introduction"
        assert section.content == "This is content."


class TestTableEntity:
    """Tests for TableEntity."""

    def test_creation_full(self):
        """Test creating TableEntity with all fields."""
        rows = [TableRowEntity(cells=["A", "1"]), TableRowEntity(cells=["B", "2"])]
        table = TableEntity(
            table_label="Table 1",
            caption="Sample data table",
            headers=["Name", "Value"],
            rows=rows
        )
        assert table.table_label == "Table 1"
        assert table.caption == "Sample data table"
        assert table.headers == ["Name", "Value"]
        assert len(table.rows) == 2

    def test_creation_minimal(self):
        """Test creating TableEntity with minimal data."""
        table = TableEntity()
        assert table.table_label is None
        assert table.caption is None
        assert table.headers == []
        assert table.rows == []

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        table = TableEntity(table_label="Table 2")
        assert "bibo:Table" in table.types
        assert table.label == "Table 2"

    def test_post_init_default_label(self):
        """Test post-init with default label."""
        table = TableEntity()
        assert table.label == "Untitled Table"

    def test_validate_success_consistent_columns(self):
        """Test validation passes with consistent column counts."""
        rows = [
            TableRowEntity(cells=["A", "1"]),
            TableRowEntity(cells=["B", "2"])
        ]
        table = TableEntity(headers=["Name", "Value"], rows=rows)
        table.validate()  # Should not raise

    def test_validate_success_no_headers(self):
        """Test validation passes without headers."""
        rows = [TableRowEntity(cells=["A", "1"])]
        table = TableEntity(rows=rows)
        table.validate()  # Should not raise

    def test_validate_failure_inconsistent_columns(self):
        """Test validation fails with inconsistent column counts."""
        rows = [
            TableRowEntity(cells=["A", "1"]),
            TableRowEntity(cells=["B", "2", "extra"])
        ]
        table = TableEntity(rows=rows)
        with pytest.raises(ValueError, match="must have the same number of columns"):
            table.validate()

    def test_validate_failure_headers_mismatch(self):
        """Test validation fails when headers don't match row length."""
        rows = [TableRowEntity(cells=["A", "1"])]
        table = TableEntity(headers=["Name"], rows=rows)  # 1 header, 2 cells
        with pytest.raises(ValueError, match="must match number of columns"):
            table.validate()

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace."""
        rows = [TableRowEntity(cells=["  A  ", "  1  "])]
        table = TableEntity(
            table_label="  Table 1  ",
            caption="  Sample table  ",
            headers=["  Name  ", "  Value  "],
            rows=rows
        )
        table.normalize()
        assert table.table_label == "Table 1"
        assert table.caption == "Sample table"
        assert table.headers == ["Name", "Value"]
        assert table.rows[0].cells == ["A", "1"]


class TestTableRowEntity:
    """Tests for TableRowEntity."""

    def test_creation_with_cells(self):
        """Test creating TableRowEntity with cells."""
        row = TableRowEntity(cells=["Value 1", "Value 2", "Value 3"])
        assert row.cells == ["Value 1", "Value 2", "Value 3"]

    def test_creation_empty(self):
        """Test creating empty TableRowEntity."""
        row = TableRowEntity()
        assert row.cells == []

    def test_post_init_sets_types_and_label(self):
        """Test post-init sets correct types and label."""
        row = TableRowEntity(cells=["A", "B"])
        assert "bibo:Row" in row.types
        assert row.label == "Row with 2 cells"

    def test_post_init_empty_cells(self):
        """Test post-init with empty cells."""
        row = TableRowEntity()
        assert row.label == "Row with 0 cells"

    def test_validate_success_with_cells(self):
        """Test validation passes with cells."""
        row = TableRowEntity(cells=["Value"])
        row.validate()  # Should not raise

    def test_validate_failure_empty_cells(self):
        """Test validation fails with empty cells."""
        row = TableRowEntity()
        with pytest.raises(ValueError, match="must have cells"):
            row.validate()

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace from cells."""
        row = TableRowEntity(cells=["  Value 1  ", "  Value 2  "])
        row.normalize()
        assert row.cells == ["Value 1", "Value 2"]
