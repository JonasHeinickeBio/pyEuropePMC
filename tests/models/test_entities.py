"""Tests for model entities: BaseEntity, GrantEntity, MeSH entities, SectionEntity."""
import pytest

from pyeuropepmc.models import GrantEntity
from pyeuropepmc.models.base import BaseEntity
from pyeuropepmc.models.mesh import MeSHHeadingEntity, MeSHQualifierEntity
from pyeuropepmc.models.section import SectionEntity


# ── BaseEntity ──


class TestBaseEntity:
    """Tests for BaseEntity."""

    def test_merge_from_source_basic(self):
        """merge_from_source tracks data source and sets timestamp."""
        entity = BaseEntity(id="test-1", label="Original")
        source_data = {"label": "Updated"}
        entity.merge_from_source(source_data, "search_api")
        assert "search_api" in entity.data_sources
        assert entity.last_updated is not None
        assert entity.last_updated.endswith("Z")

    def test_merge_from_source_only_updates_none(self):
        """merge_from_source only overwrites when current value is None."""
        entity = BaseEntity(label="Existing")
        entity.merge_from_source({"label": "New"}, "source")
        assert entity.label == "Existing"  # Not overwritten

    def test_merge_from_source_overwrites_empty_string(self):
        """merge_from_source overwrites empty string values."""
        entity = BaseEntity(label="")
        entity.merge_from_source({"label": "NonEmpty"}, "source")
        assert entity.label == "NonEmpty"

    def test_merge_from_source_overwrites_whitespace(self):
        """merge_from_source overwrites whitespace-only string values."""
        entity = BaseEntity(label="   ")
        entity.merge_from_source({"label": "Clean"}, "source")
        assert entity.label == "Clean"

    def test_merge_from_source_skips_none_values(self):
        """merge_from_source skips keys where value is None."""
        entity = BaseEntity(label="Keep")
        entity.merge_from_source({"label": None, "source_uri": "http://example.com"}, "source")
        assert entity.label == "Keep"  # Not overwritten by None
        assert entity.source_uri == "http://example.com"  # Set by non-None value

    def test_merge_from_source_skips_unknown_attr(self):
        """merge_from_source silently skips non-existent attributes."""
        entity = BaseEntity()
        entity.merge_from_source({"nonexistent": "value"}, "source")
        # Should not raise, data_sources still tracked
        assert "source" in entity.data_sources

    def test_is_valid_uri_scheme_required(self):
        """_is_valid_uri requires a scheme (://)."""
        assert BaseEntity._is_valid_uri("http://example.com") is True
        assert BaseEntity._is_valid_uri("https://example.org/path") is True
        assert BaseEntity._is_valid_uri("ftp://files.example.com") is True
        assert BaseEntity._is_valid_uri("no-scheme-string") is False

    def test_is_valid_uri_empty_or_non_string(self):
        """_is_valid_uri returns False for empty or non-string input."""
        assert BaseEntity._is_valid_uri("") is False
        assert BaseEntity._is_valid_uri(None) is False
        assert BaseEntity._is_valid_uri(12345) is False

    def test_mint_uri_generates_id(self):
        """mint_uri generates UUID when id is None."""
        entity = BaseEntity()
        uri = entity.mint_uri("paper")
        assert str(uri).startswith("http://example.org/data/paper/")
        assert entity.id is not None  # UUID assigned

    def test_mint_uri_uses_existing_id(self):
        """mint_uri uses existing id when available."""
        entity = BaseEntity(id="abc-123")
        uri = entity.mint_uri("author")
        assert str(uri) == "http://example.org/data/author/abc-123"

    def test_to_dict(self):
        """to_dict returns dataclass fields."""
        entity = BaseEntity(id="x", label="Test", confidence=0.9)
        d = entity.to_dict()
        assert d["id"] == "x"
        assert d["label"] == "Test"
        assert d["confidence"] == 0.9

    def test_validate_noop(self):
        """validate is a no-op for BaseEntity."""
        entity = BaseEntity()
        entity.validate()  # Should not raise

    def test_normalize_noop(self):
        """normalize is a no-op for BaseEntity."""
        entity = BaseEntity()
        entity.normalize()  # Should not raise


# ── GrantEntity ──


class TestGrantEntity:
    """Tests for GrantEntity."""

    def test_default_types_and_label(self):
        """__post_init__ sets default types and label."""
        grant = GrantEntity()
        assert "frapo:Grant" in grant.types
        assert grant.label == "Grant"

    def test_label_from_award_id(self):
        """Label falls back to award_id."""
        grant = GrantEntity(award_id="R01-12345")
        assert grant.label == "R01-12345"

    def test_label_from_funding_source(self):
        """Label falls back to funding_source."""
        grant = GrantEntity(funding_source="NIH")
        assert grant.label == "NIH"

    def test_normalize_strips_fields(self):
        """normalize strips whitespace from all fields."""
        grant = GrantEntity(
            fundref_doi=" 10.13039/100000001 ",
            funding_source=" NIH ",
            award_id=" R01 ",
            recipient=" Dr. Smith ",
        )
        grant.normalize()
        assert grant.fundref_doi == "10.13039/100000001"
        assert grant.funding_source == "NIH"
        assert grant.award_id == "R01"
        assert grant.recipient == "Dr. Smith"

    def test_normalize_none_fields(self):
        """normalize handles None fields without error."""
        grant = GrantEntity()
        # Should not raise
        grant.normalize()

    def test_normalize_recipients(self):
        """normalize calls normalize on each recipient."""
        from pyeuropepmc.models.author import AuthorEntity

        recipient = AuthorEntity(full_name=" Dr. Smith ", first_name=" John ")
        grant = GrantEntity(
            recipients=[recipient],
        )
        grant.normalize()
        assert recipient.full_name == "Dr. Smith"
        assert recipient.first_name == "John"

    def test_to_dict_with_recipients(self):
        """to_dict includes recipient dicts when recipients exist."""
        grant = GrantEntity(
            fundref_doi="10.13039/100000001",
            recipients=[
                type('AuthorEntity', (), {'to_dict': lambda s: {'name': 'Dr. Smith'}})()
            ],
        )
        result = grant.to_dict()
        assert result["recipients"] == [{"name": "Dr. Smith"}]

    def test_to_dict_without_recipients(self):
        """to_dict returns None for recipients when empty."""
        grant = GrantEntity()
        result = grant.to_dict()
        assert result["recipients"] is None

    def test_from_dict_with_recipients(self):
        """from_dict creates GrantEntity with recipients."""
        data = {
            "fundref_doi": "10.13039/100000001",
            "funding_source": "NIH",
            "award_id": "R01",
            "recipients": [{"full_name": "Dr. Smith"}],
        }
        from pyeuropepmc.models.author import AuthorEntity

        grant = GrantEntity.from_dict(data)
        assert grant.funding_source == "NIH"
        assert grant.recipients is not None
        assert len(grant.recipients) == 1
        assert isinstance(grant.recipients[0], AuthorEntity)
        assert grant.recipients[0].full_name == "Dr. Smith"

    def test_from_dict_without_recipients(self):
        """from_dict handles missing recipients."""
        data = {"funding_source": "NSF"}
        grant = GrantEntity.from_dict(data)
        assert grant.recipients is None

    def test_validate_positive_integer(self):
        """GrantEntity doesn't have validate, but ensure it inherits from BaseEntity."""
        assert hasattr(GrantEntity, "validate")

    def test_to_rdf_not_implemented(self):
        """GrantEntity should have to_rdf method from BaseEntity."""
        assert hasattr(GrantEntity, "to_rdf")


# ── MeSHQualifierEntity ──


class TestMeSHQualifierEntity:
    """Tests for MeSHQualifierEntity."""

    def test_from_dict_basic(self):
        """Create qualifier from API response dict."""
        data = {
            "qualifierName": "therapy",
            "abbreviation": "TH",
            "majorTopic_YN": "Y",
        }
        qual = MeSHQualifierEntity.from_dict(data)
        assert qual.qualifier_name == "therapy"
        assert qual.abbreviation == "TH"
        assert qual.major_topic is True

    def test_from_dict_no_abbreviation(self):
        """Create qualifier without abbreviation."""
        data = {"qualifierName": "diagnosis", "majorTopic_YN": "N"}
        qual = MeSHQualifierEntity.from_dict(data)
        assert qual.qualifier_name == "diagnosis"
        assert qual.abbreviation is None
        assert qual.major_topic is False

    def test_from_dict_missing_name(self):
        """Create qualifier with missing qualifierName."""
        data = {}
        qual = MeSHQualifierEntity.from_dict(data)
        assert qual.qualifier_name == ""


# ── MeSHHeadingEntity ──


class TestMeSHHeadingEntity:
    """Tests for MeSHHeadingEntity."""

    def test_from_dict_basic(self):
        """Create heading from API response dict."""
        data = {
            "descriptorName": "Neoplasms",
            "majorTopic_YN": "Y",
            "descriptorUI": "D000001",
        }
        heading = MeSHHeadingEntity.from_dict(data)
        assert heading.descriptor_name == "Neoplasms"
        assert heading.major_topic is True
        assert heading.descriptor_ui == "D000001"
        assert heading.qualifiers == []

    def test_from_dict_with_qualifiers(self):
        """Create heading with qualifiers from API response."""
        data = {
            "descriptorName": "Neoplasms",
            "majorTopic_YN": "Y",
            "meshQualifierList": {
                "meshQualifier": [
                    {"qualifierName": "therapy", "abbreviation": "TH", "majorTopic_YN": "N"},
                    {"qualifierName": "diagnosis", "majorTopic_YN": "N"},
                ]
            },
        }
        heading = MeSHHeadingEntity.from_dict(data)
        assert len(heading.qualifiers) == 2
        assert heading.qualifiers[0].qualifier_name == "therapy"
        assert heading.qualifiers[1].qualifier_name == "diagnosis"
        assert heading.qualifiers[0].abbreviation == "TH"

    def test_get_full_term_no_qualifiers(self):
        """get_full_term returns descriptor name only."""
        heading = MeSHHeadingEntity(descriptor_name="Humans")
        assert heading.get_full_term() == "Humans"

    def test_get_full_term_with_qualifiers(self):
        """get_full_term includes qualifiers."""
        heading = MeSHHeadingEntity(
            descriptor_name="Neoplasms",
            qualifiers=[
                MeSHQualifierEntity("therapy", "TH"),
                MeSHQualifierEntity("diagnosis", "DI"),
            ],
        )
        assert heading.get_full_term() == "Neoplasms/therapy/diagnosis"

    def test_to_dict(self):
        """to_dict returns correct dictionary structure."""
        heading = MeSHHeadingEntity(
            descriptor_name="Neoplasms",
            major_topic=True,
            qualifiers=[MeSHQualifierEntity("therapy", "TH", False)],
            descriptor_ui="D000001",
        )
        result = heading.to_dict()
        assert result["descriptor_name"] == "Neoplasms"
        assert result["major_topic"] is True
        assert len(result["qualifiers"]) == 1
        assert result["qualifiers"][0]["qualifier_name"] == "therapy"
        assert result["descriptor_ui"] == "D000001"

    def test_to_dict_empty_qualifiers(self):
        """to_dict handles empty qualifiers list."""
        heading = MeSHHeadingEntity(descriptor_name="Humans")
        result = heading.to_dict()
        assert result["qualifiers"] == []


# ── SectionEntity ──


class TestSectionEntity:
    """Tests for SectionEntity."""

    def test_default_types_and_label(self):
        """__post_init__ sets default types and label."""
        section = SectionEntity()
        assert "bibo:DocumentPart" in section.types
        assert section.label == "Untitled Section"

    def test_label_from_title(self):
        """Label falls back to title."""
        section = SectionEntity(title="Introduction")
        assert section.label == "Introduction"

    def test_validate_missing_content(self):
        """validate raises for missing content."""
        section = SectionEntity()
        with pytest.raises(ValueError, match="must have content"):
            section.validate()

    def test_validate_with_content(self):
        """validate passes with valid content."""
        section = SectionEntity(title="Intro", content="Some text.")
        # Should not raise
        section.validate()

    def test_validate_begin_end_index(self):
        """validate with begin < end indices passes."""
        section = SectionEntity(title="Intro", content="Text.", begin_index=0, end_index=10)
        section.validate()

    def test_validate_begin_gte_end_index_raises(self):
        """validate raises when begin_index >= end_index."""
        section = SectionEntity(title="Intro", content="Text.", begin_index=10, end_index=5)
        with pytest.raises(ValueError, match="begin_index must be less than end_index"):
            section.validate()

    def test_validate_begin_equal_end_index_raises(self):
        """validate raises when begin_index == end_index."""
        section = SectionEntity(title="Intro", content="Text.", begin_index=5, end_index=5)
        with pytest.raises(ValueError, match="begin_index must be less than end_index"):
            section.validate()

    def test_normalize_trims_fields(self):
        """normalize strips whitespace from title and content."""
        section = SectionEntity(title="  Title  ", content="  Content  ")
        section.normalize()
        assert section.title == "Title"
        assert section.content == "Content"
