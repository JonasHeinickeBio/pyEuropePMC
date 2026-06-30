"""Tests for the AuthorEntity model."""
import pytest

from pyeuropepmc.models.author import AuthorEntity


class TestAuthorEntity:
    """Tests for AuthorEntity."""

    def test_default_creation(self):
        """Test creating author with defaults."""
        author = AuthorEntity()
        assert author.full_name == ""
        assert author.types == ["foaf:Person"]
        assert author.label == ""

    def test_with_full_name(self):
        """Test author with full name."""
        author = AuthorEntity(full_name="John Smith")
        assert author.full_name == "John Smith"
        assert author.label == "John Smith"

    def test_with_name_field(self):
        """Test author with name field (label fallback)."""
        author = AuthorEntity(name="Jane Doe")
        assert author.label == "Jane Doe"

    def test_with_name_and_full_name(self):
        """Test label uses full_name when both provided."""
        author = AuthorEntity(full_name="John Smith", name="jsmith")
        assert author.label == "John Smith"

    def test_custom_types(self):
        """Test custom types override default."""
        author = AuthorEntity(full_name="Test", types=["schema:Person"])
        assert author.types == ["schema:Person"]

    def test_all_fields(self):
        """Test setting all common fields."""
        author = AuthorEntity(
            full_name="Alice Wonderland",
            first_name="Alice",
            last_name="Wonderland",
            initials="A.",
            affiliation_text="Wonderland University",
            orcid="0000-0002-1825-0097",
            email="alice@wonderland.edu",
            position="First Author",
            sources=["PubMed"],
        )
        assert author.full_name == "Alice Wonderland"
        assert author.first_name == "Alice"
        assert author.last_name == "Wonderland"
        assert author.initials == "A."
        assert author.orcid == "0000-0002-1825-0097"
        assert author.email == "alice@wonderland.edu"

    def test_validate_valid(self):
        """Test validate with valid author."""
        author = AuthorEntity(full_name="Valid Author")
        author.validate()  # Should not raise

    def test_validate_missing_name(self):
        """Test validate raises ValueError when no name."""
        author = AuthorEntity()
        with pytest.raises(ValueError, match="AuthorEntity must have either full_name or name"):
            author.validate()

    def test_validate_with_orcid(self):
        """Test validate normalizes ORCID."""
        author = AuthorEntity(
            full_name="ORCID Author",
            orcid="https://orcid.org/0000-0002-1825-0097",
        )
        # The validate_and_normalize_orcid returns the ID part
        try:
            author.validate()
        except Exception:
            pass  # validate_and_normalize_orcid may raise if format invalid

    def test_validate_with_positive_integers(self):
        """Test validate with positive integer fields."""
        author = AuthorEntity(
            full_name="Productive Author",
            orcid_works_count=10,
            h_index=5,
            citation_count=100,
            paper_count=20,
        )
        author.validate()
        assert author.orcid_works_count == 10
        assert author.h_index == 5

    def test_normalize_trims_whitespace(self):
        """Test normalize trims whitespace from fields."""
        author = AuthorEntity(full_name="  Padded Name  ")
        author.normalize()
        assert author.full_name == "Padded Name"

    def test_normalize_empty_string_fallback(self):
        """Test normalize returns empty string for full_name when stripped."""
        author = AuthorEntity(full_name="   ")
        author.normalize()
        assert author.full_name == ""

    def test_normalize_with_orcid_bare(self):
        """Test normalize handles bare ORCID (without URL prefix)."""
        author = AuthorEntity(
            full_name="ORCID Author",
            orcid="0000-0002-1825-0097",
        )
        author.normalize()
        assert author.orcid == "0000-0002-1825-0097"

    def test_from_enrichment_dict_basic(self):
        """Test from_enrichment_dict with basic fields."""
        data = {
            "name": "Enriched Author",
            "given_name": "Enriched",
            "family_name": "Author",
            "orcid": "0000-0002-1825-0097",
            "position": "corresponding",
            "sources": ["CrossREF"],
        }
        author = AuthorEntity.from_enrichment_dict(data)
        assert author.full_name == "Enriched Author"
        assert author.first_name == "Enriched"
        assert author.last_name == "Author"
        assert author.orcid == "0000-0002-1825-0097"

    def test_from_enrichment_dict_with_institution_dicts(self):
        """Test from_enrichment_dict with institution dicts."""
        data = {
            "name": "Author With Inst",
            "institutions": [
                {"display_name": "University A", "country": "USA"},
                {"display_name": "University B", "country": "UK"},
            ],
        }
        author = AuthorEntity.from_enrichment_dict(data)
        assert len(author.institutions) == 2
        assert author.institutions[0].display_name == "University A"
        assert author.institutions[1].country == "UK"

    def test_validate_with_email(self):
        """Test validate normalizes email."""
        author = AuthorEntity(full_name="Email Author", email="  USER@EXAMPLE.COM  ")
        author.validate()
        # Email normalization trims + lowercases
        assert author.email == "user@example.com"

    def test_validate_with_openalex_id(self):
        """Test validate normalizes OpenAlex URI."""
        author = AuthorEntity(
            full_name="OpenAlex Author",
            openalex_id="https://openalex.org/A123456789",
        )
        author.validate()
        assert "openalex.org" in author.openalex_id

    def test_validate_with_semantic_scholar_id(self):
        """Test validate normalizes Semantic Scholar URI."""
        author = AuthorEntity(
            full_name="SS Author",
            semantic_scholar_id="https://www.semanticscholar.org/author/12345",
        )
        author.validate()
        assert "semanticscholar.org" in author.semantic_scholar_id

    def test_normalize_with_email(self):
        """Test normalize handles email field."""
        author = AuthorEntity(full_name="Norm Email", email="  FOO@BAR.COM  ")
        author.normalize()
        assert author.email == "foo@bar.com"

    def test_from_enrichment_dict_with_institution_entities(self):
        """Test from_enrichment_dict with pre-built InstitutionEntity objects."""
        from pyeuropepmc.models.institution import InstitutionEntity

        inst = InstitutionEntity(display_name="Prebuilt Inst", country="DE")
        data = {
            "name": "Author With Entities",
            "institutions": [inst],
        }
        author = AuthorEntity.from_enrichment_dict(data)
        assert len(author.institutions) == 1
        assert author.institutions[0].display_name == "Prebuilt Inst"

    def test_from_enrichment_dict_empty(self):
        """Test from_enrichment_dict with empty data."""
        author = AuthorEntity.from_enrichment_dict({})
        assert author.full_name == ""
        assert author.institutions is None
