"""Unit tests for pyeuropepmc.models.scholarly_work.ScholarlyWorkEntity."""

from __future__ import annotations

import pytest

from pyeuropepmc.models.scholarly_work import ScholarlyWorkEntity


class TestNormalize:
    def test_normalizes_fields(self):
        entity = ScholarlyWorkEntity(
            doi="  https://doi.org/10.1234/TEST  ",
            title="  A Title  ",
            pages=" 1-10 ",
            abstract="  An abstract.  ",
            pmcid="123456",
            pmid="  123456  ",
        )
        entity.normalize()
        assert entity.doi == "10.1234/test"
        assert entity.title == "A Title"
        assert entity.pages == "1-10"
        assert entity.abstract == "An abstract."
        assert entity.pmcid == "PMC123456"
        assert entity.pmid == "123456"

    def test_journal_string_normalized(self):
        entity = ScholarlyWorkEntity(journal="  Nature  ")
        entity.normalize()
        assert entity.journal == "Nature"

    def test_journal_non_string_untouched(self):
        class FakeJournal:
            pass

        journal = FakeJournal()
        entity = ScholarlyWorkEntity(journal=journal)
        entity.normalize()
        assert entity.journal is journal


class TestValidate:
    def test_valid_entity_does_not_raise(self):
        entity = ScholarlyWorkEntity(publication_year=2020, citation_count=5)
        entity.validate()

    def test_negative_citation_count_raises(self):
        entity = ScholarlyWorkEntity(citation_count=-1)
        with pytest.raises(ValueError, match="non-negative"):
            entity.validate()

    def test_none_citation_count_ok(self):
        entity = ScholarlyWorkEntity(citation_count=None)
        entity.validate()


class TestFromLinkml:
    def test_basic_fields(self):
        entity = ScholarlyWorkEntity.from_linkml(
            {
                "doi": "10.1234/x",
                "title": "T",
                "source": "pubmed",
                "source_id": "1",
                "citation_count": 5,
            }
        )
        assert entity.doi == "10.1234/x"
        assert entity.citation_count == 5

    def test_authors_dicts_normalized(self):
        entity = ScholarlyWorkEntity.from_linkml(
            {
                "authors": [
                    {"name": "Jane Doe", "orcid": "0000-1", "affiliation": "MIT"},
                ]
            }
        )
        assert entity.authors == [
            {"name": "Jane Doe", "orcid": "0000-1", "affiliation": "MIT", "institution": None}
        ]

    def test_authors_non_dict_passthrough(self):
        entity = ScholarlyWorkEntity.from_linkml({"authors": ["Smith J, Doe A"]})
        assert entity.authors == ["Smith J, Doe A"]

    def test_no_authors_defaults_to_none(self):
        entity = ScholarlyWorkEntity.from_linkml({})
        assert entity.authors is None
