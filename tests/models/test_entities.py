"""Tests for model entities: GrantEntity, MeSH entities, SectionEntity."""
import pytest

from pyeuropepmc.models import GrantEntity
from pyeuropepmc.models.mesh import MeSHHeadingEntity, MeSHQualifierEntity
from pyeuropepmc.models.section import SectionEntity


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
