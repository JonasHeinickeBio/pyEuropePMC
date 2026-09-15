"""Unit tests for pyeuropepmc.mappers.rdf_utils.URIFactory (pure logic, no I/O).

Entities are plain SimpleNamespace objects with a `.__class__.__name__`
matching the real entity class name where dispatch depends on it
(generate_uri's `self.generators` lookup); URIFactory itself only ever
duck-types via getattr(), so no real model classes are needed.
"""

from __future__ import annotations

import pytest
from rdflib import URIRef

from pyeuropepmc.mappers.rdf_utils import (
    URIFactory,
    generate_author_uri,
    generate_entity_uri,
    generate_fallback_uri,
    generate_institution_uri,
    generate_paper_uri,
    generate_reference_uri,
    normalize_name,
)


def _entity(class_name: str, **attrs):
    cls = type(class_name, (object,), {})
    obj = cls()
    for key, value in attrs.items():
        setattr(obj, key, value)
    return obj


@pytest.fixture
def factory():
    return URIFactory()


class TestNormalizeName:
    def test_basic(self, factory):
        assert factory._normalize_name("Jane Doe") == "jane-doe"

    def test_strips_punctuation(self, factory):
        assert factory._normalize_name("O'Brien, Jane!") == "obrien-jane"

    def test_empty_returns_none(self, factory):
        assert factory._normalize_name("") is None

    def test_only_punctuation_returns_none(self, factory):
        assert factory._normalize_name("!!!") is None

    def test_module_level_wrapper(self):
        assert normalize_name("Jane Doe") == "jane-doe"


class TestCompactInstitutionId:
    def test_strips_trailing_country(self, factory):
        result = factory._generate_compact_institution_id("BC Cancer, Victoria, BC, Canada")
        assert "canada" not in result

    def test_strips_leading_the(self, factory):
        result = factory._generate_compact_institution_id("The Ohio State University")
        assert not result.startswith("the")

    def test_strips_institution_suffix(self, factory):
        result = factory._generate_compact_institution_id("Dana-Farber Cancer Institute")
        assert "institute" not in result

    def test_empty_returns_short_uuid(self, factory):
        result = factory._generate_compact_institution_id("")
        assert len(result) == 8

    def test_long_name_hashed(self, factory):
        long_name = "A" * 200
        result = factory._generate_compact_institution_id(long_name)
        assert len(result) == 12  # md5[:12] fallback for names that stay too long

    def test_limits_to_four_words(self, factory):
        result = factory._generate_compact_institution_id("One Two Three Four Five University")
        assert result.count("-") <= 3


class TestGeneratePaperUri:
    def test_prefers_pmid(self, factory):
        uri = factory._generate_paper_uri(_entity("PaperEntity", pmid="12345", doi="10.1/x"))
        assert str(uri) == "https://pubmed.ncbi.nlm.nih.gov/12345/"

    def test_falls_back_to_doi(self, factory):
        uri = factory._generate_paper_uri(_entity("PaperEntity", doi="10.1234/x"))
        assert str(uri) == "https://doi.org/10.1234/x"

    def test_falls_back_to_pmcid(self, factory):
        uri = factory._generate_paper_uri(_entity("PaperEntity", pmcid="PMC123"))
        assert "PMC123" in str(uri)

    def test_falls_back_to_author_year_journal(self, factory):
        entity = _entity(
            "PaperEntity",
            authors=[{"last_name": "Smith"}],
            publication_year=2020,
            journal="Nature Reviews",
        )
        uri = factory._generate_paper_uri(entity)
        assert "smith" in str(uri)
        assert "2020" in str(uri)

    def test_module_level_wrapper(self):
        uri = generate_paper_uri(_entity("PaperEntity", pmid="1"))
        assert isinstance(uri, URIRef)


class TestGenerateAuthorUri:
    def test_prefers_normalized_full_name(self, factory):
        uri = factory._generate_author_uri(_entity("AuthorEntity", full_name="Jane Doe"))
        assert "author/jane-doe" in str(uri)

    def test_falls_back_to_name_attr(self, factory):
        uri = factory._generate_author_uri(_entity("AuthorEntity", full_name="", name="Jane Doe"))
        assert "jane-doe" in str(uri)

    def test_falls_back_to_orcid(self, factory):
        uri = factory._generate_author_uri(
            _entity("AuthorEntity", full_name="", name="", orcid="0000-0001-2345-6789")
        )
        assert str(uri) == "https://orcid.org/0000-0001-2345-6789"

    def test_falls_back_to_openalex_id(self, factory):
        uri = factory._generate_author_uri(
            _entity(
                "AuthorEntity",
                full_name="",
                name="",
                orcid=None,
                openalex_id="https://openalex.org/A1",
            )
        )
        assert str(uri) == "https://openalex.org/A1"

    def test_falls_back_to_uuid(self, factory):
        uri = factory._generate_author_uri(
            _entity("AuthorEntity", full_name="", name="", orcid=None, openalex_id=None)
        )
        assert "author" in str(uri)

    def test_module_level_wrapper(self):
        uri = generate_author_uri(_entity("AuthorEntity", full_name="Jane Doe"))
        assert isinstance(uri, URIRef)


class TestGenerateInstitutionUri:
    def test_prefers_ror_id(self, factory):
        uri = factory._generate_institution_uri(
            _entity("InstitutionEntity", ror_id="https://ror.org/12345")
        )
        assert str(uri) == "https://ror.org/12345"

    def test_falls_back_to_openalex_id(self, factory):
        uri = factory._generate_institution_uri(
            _entity("InstitutionEntity", ror_id=None, openalex_id="https://openalex.org/I1")
        )
        assert str(uri) == "https://openalex.org/I1"

    def test_falls_back_to_display_name(self, factory):
        uri = factory._generate_institution_uri(
            _entity(
                "InstitutionEntity",
                ror_id=None,
                openalex_id=None,
                display_name="Harvard University",
            )
        )
        assert "institution/harvard" in str(uri)

    def test_module_level_wrapper(self):
        uri = generate_institution_uri(_entity("InstitutionEntity", ror_id="https://ror.org/1"))
        assert isinstance(uri, URIRef)


class TestGenerateReferenceUri:
    def test_prefers_pmid(self, factory):
        uri = factory._generate_reference_uri(_entity("ReferenceEntity", pmid="1"))
        assert "pubmed" in str(uri)

    def test_pmcid_gets_prefixed(self, factory):
        uri = factory._generate_reference_uri(_entity("ReferenceEntity", pmid=None, pmcid="12345"))
        assert "PMC12345" in str(uri)

    def test_pmcid_already_prefixed_untouched(self, factory):
        uri = factory._generate_reference_uri(
            _entity("ReferenceEntity", pmid=None, pmcid="PMC12345")
        )
        assert "PMC12345" in str(uri)
        assert "PMCPMC" not in str(uri)

    def test_falls_back_to_doi(self, factory):
        uri = factory._generate_reference_uri(
            _entity("ReferenceEntity", pmid=None, pmcid=None, doi="10.1/x")
        )
        assert str(uri) == "https://doi.org/10.1/x"

    def test_fallback_with_authors_dict(self, factory):
        entity = _entity(
            "ReferenceEntity",
            pmid=None,
            pmcid=None,
            doi=None,
            authors=[{"last_name": "Smith"}],
            year=2019,
            title="A great paper",
        )
        uri = factory._generate_reference_uri(entity)
        assert "smith-2019" in str(uri)

    def test_fallback_with_authors_string(self, factory):
        entity = _entity(
            "ReferenceEntity",
            pmid=None,
            pmcid=None,
            doi=None,
            authors="Smith J, Doe A",
            year=2019,
        )
        uri = factory._generate_reference_uri(entity)
        assert "smith" in str(uri)  # first token of "Smith J"

    def test_fallback_no_components_uses_uuid(self, factory):
        entity = _entity(
            "ReferenceEntity", pmid=None, pmcid=None, doi=None, authors=None, year=None
        )
        uri = factory._generate_reference_uri(entity)
        assert "reference/" in str(uri)

    def test_module_level_wrapper(self):
        uri = generate_reference_uri(_entity("ReferenceEntity", pmid="1"))
        assert isinstance(uri, URIRef)


class TestGenerateJournalUri:
    def test_prefers_medline_abbreviation(self, factory):
        uri = factory._generate_journal_uri(
            _entity("JournalEntity", medline_abbreviation="J Gene Ed.")
        )
        assert "journal/j-gene-ed" in str(uri)

    def test_falls_back_to_iso_abbreviation(self, factory):
        uri = factory._generate_journal_uri(
            _entity("JournalEntity", medline_abbreviation=None, iso_abbreviation="J. Gene. Ed.")
        )
        assert "journal/" in str(uri)

    def test_falls_back_to_title(self, factory):
        uri = factory._generate_journal_uri(
            _entity(
                "JournalEntity",
                medline_abbreviation=None,
                iso_abbreviation=None,
                title="Nature",
            )
        )
        assert "journal/nature" in str(uri)

    def test_falls_back_to_nlmid(self, factory):
        uri = factory._generate_journal_uri(
            _entity(
                "JournalEntity",
                medline_abbreviation=None,
                iso_abbreviation=None,
                title=None,
                nlmid="ABC123",
            )
        )
        assert "journal/abc123" in str(uri)

    def test_falls_back_to_uuid(self, factory):
        uri = factory._generate_journal_uri(
            _entity(
                "JournalEntity",
                medline_abbreviation=None,
                iso_abbreviation=None,
                title=None,
                nlmid=None,
            )
        )
        assert "journal" in str(uri)


class TestExtractPaperIdentifier:
    def test_from_pubmed_url(self, factory):
        assert (
            factory._extract_paper_identifier("https://pubmed.ncbi.nlm.nih.gov/12345/") == "12345"
        )

    def test_from_doi_url(self, factory):
        result = factory._extract_paper_identifier("https://doi.org/10.1234/x.y")
        assert result == "10-1234-x-y"

    def test_from_pmc_url(self, factory):
        assert factory._extract_paper_identifier("https://x/PMC12345/") == "12345"

    def test_none_returns_none(self, factory):
        assert factory._extract_paper_identifier(None) is None

    def test_unrecognized_format_returns_none(self, factory):
        assert factory._extract_paper_identifier("http://example.org/foo") is None


class TestGenerateSectionTableFigureUri:
    def test_section_uses_title_with_paper_id(self, factory):
        uri = factory._generate_section_uri(
            _entity("SectionEntity", title="Introduction"),
            parent_uri="https://pubmed.ncbi.nlm.nih.gov/1/",
        )
        assert "section/1/introduction" in str(uri)

    def test_section_falls_back_to_label_without_paper_id(self, factory):
        uri = factory._generate_section_uri(_entity("SectionEntity", title=None, label="Methods"))
        assert "section/methods" in str(uri)

    def test_section_falls_back_to_uuid(self, factory):
        uri = factory._generate_section_uri(_entity("SectionEntity", title=None, label=None))
        assert "section" in str(uri)

    def test_table_uses_table_label(self, factory):
        uri = factory._generate_table_uri(_entity("TableEntity", table_label="Table 1"))
        assert "table/table-1" in str(uri)

    def test_table_falls_back_to_caption(self, factory):
        uri = factory._generate_table_uri(
            _entity("TableEntity", table_label=None, caption="A" * 80)
        )
        assert "table/" in str(uri)

    def test_table_ignores_untitled_label(self, factory):
        uri = factory._generate_table_uri(
            _entity("TableEntity", table_label=None, caption=None, label="Untitled Table")
        )
        assert "table" in str(uri)

    def test_figure_uses_figure_label(self, factory):
        uri = factory._generate_figure_uri(_entity("FigureEntity", figure_label="Figure 1"))
        assert "figure/figure-1" in str(uri)

    def test_figure_falls_back_to_caption(self, factory):
        uri = factory._generate_figure_uri(
            _entity("FigureEntity", figure_label=None, caption="A caption")
        )
        assert "figure/a-caption" in str(uri)


class TestGenerateGrantUri:
    def test_from_fundref_and_award_id(self, factory):
        uri = factory.generate_grant_uri(
            {"fundref_doi": "https://doi.org/10.13039/501100001809", "award_id": "82170974"}
        )
        assert "grant/501100001809-82170974" in str(uri)

    def test_award_id_only(self, factory):
        uri = factory.generate_grant_uri({"award_id": "R01/12345"})
        assert "grant/r01-12345" in str(uri)

    def test_falls_back_to_source(self, factory):
        uri = factory.generate_grant_uri({"source": "National Institutes of Health"})
        assert "grant/national-institutes-of-health" in str(uri)

    def test_falls_back_to_uuid(self, factory):
        uri = factory.generate_grant_uri({})
        assert "grant/" in str(uri)

    def test_entity_wrapper(self, factory):
        entity = _entity("GrantEntity", fundref_doi=None, award_id="R01-1", funding_source=None)
        uri = factory._generate_grant_uri(entity)
        assert "grant/r01-1" in str(uri)


class TestGenerateAnnotationUri:
    def test_uses_url_id_verbatim(self, factory):
        uri = factory._generate_annotation_uri(
            _entity("AnnotationEntity", id="https://example.org/ann/1")
        )
        assert str(uri) == "https://example.org/ann/1"

    def test_uses_normalized_id(self, factory):
        uri = factory._generate_annotation_uri(_entity("AnnotationEntity", id="Ann 123"))
        assert "annotation/ann-123" in str(uri)

    def test_uses_article_id_and_entity_kind(self, factory):
        entity = _entity(
            "EntityAnnotation", id=None, article_id="PMC1", exact="BRCA1", entity_name=None
        )
        uri = factory._generate_annotation_uri(entity)
        # entity_kind strips the literal substring "Entity" from the class name
        assert "annotation/annotation/pmc1/brca1" in str(uri).lower()

    def test_article_id_without_exact_value(self, factory):
        entity = _entity(
            "EntityAnnotation", id=None, article_id="PMC1", exact=None, entity_name=None
        )
        uri = factory._generate_annotation_uri(entity)
        assert "pmc1" in str(uri).lower()

    def test_falls_back_to_uuid(self, factory):
        entity = _entity("AnnotationEntity", id=None, article_id=None)
        uri = factory._generate_annotation_uri(entity)
        assert "annotation" in str(uri)


class TestGenerateFallbackUri:
    def test_dict_with_type(self, factory):
        uri = factory._generate_fallback_uri({"type": "Book Chapter"})
        assert "book-chapter" in str(uri)

    def test_dict_with_id_only(self, factory):
        uri = factory._generate_fallback_uri({"id": "1"})
        assert "resource" in str(uri)

    def test_dict_with_neither(self, factory):
        uri = factory._generate_fallback_uri({})
        assert "object" in str(uri)

    def test_entity_class_name_used(self, factory):
        uri = factory._generate_fallback_uri(_entity("WidgetEntity"))
        assert "widget" in str(uri)

    def test_module_level_wrapper(self):
        uri = generate_fallback_uri(_entity("WidgetEntity"))
        assert isinstance(uri, URIRef)


class TestGenerateUriDispatch:
    def test_dispatches_by_class_name(self, factory):
        uri = factory.generate_uri(_entity("PaperEntity", pmid="1"))
        assert "pubmed" in str(uri)

    def test_unknown_class_uses_fallback(self, factory):
        uri = factory.generate_uri(_entity("SomeUnknownEntity"))
        assert "someunknown" in str(uri)

    def test_module_level_generate_entity_uri(self):
        uri = generate_entity_uri(_entity("PaperEntity", pmid="1"))
        assert isinstance(uri, URIRef)


class TestNormalizeJournalAndGrantId:
    def test_normalize_journal_abbr(self, factory):
        assert factory._normalize_journal_abbr("J. Cell Biol.") == "j-cell-biol"

    def test_normalize_journal_abbr_empty(self, factory):
        assert factory._normalize_journal_abbr("") is None

    def test_normalize_grant_id(self, factory):
        assert factory._normalize_grant_id("R01 CA/123456") == "r01ca-123456"

    def test_normalize_grant_id_empty(self, factory):
        assert factory._normalize_grant_id("") is None
