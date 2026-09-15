"""Unit tests for pyeuropepmc.models.literature (Author, LiteratureResult,
LiteratureSearchResponse)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyeuropepmc.models.literature import (
    Author,
    LiteratureResult,
    LiteratureSearchResponse,
)


class TestAuthor:
    def test_basic(self):
        a = Author(name="Smith, Jane")
        assert a.name == "Smith, Jane"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            Author(name="   ")

    def test_orcid_url_normalized(self):
        a = Author(name="Jane Doe", orcid="https://orcid.org/0000-0001-2345-6789")
        assert a.orcid == "0000-0001-2345-6789"

    def test_orcid_trailing_slash_stripped(self):
        a = Author(name="Jane Doe", orcid="https://orcid.org/0000-0001-2345-6789/")
        assert a.orcid == "0000-0001-2345-6789"

    def test_invalid_orcid_raises(self):
        with pytest.raises(ValidationError, match="Invalid ORCID format"):
            Author(name="Jane Doe", orcid="not an orcid!!")

    def test_orcid_none_is_valid(self):
        a = Author(name="Jane Doe")
        assert a.orcid is None


class TestLiteratureResultValidators:
    def test_doi_normalized_lowercase_and_stripped(self):
        r = LiteratureResult(doi="https://doi.org/10.1234/ABC", source="pubmed", source_id="1")
        assert r.doi == "10.1234/abc"

    def test_doi_none(self):
        r = LiteratureResult(source="pubmed", source_id="1")
        assert r.doi is None

    def test_title_stripped(self):
        r = LiteratureResult(title="  Hello  ", source="pubmed", source_id="1")
        assert r.title == "Hello"

    def test_title_none(self):
        r = LiteratureResult(source="pubmed", source_id="1")
        assert r.title is None

    def test_journal_stripped(self):
        r = LiteratureResult(journal="  Nature  ", source="pubmed", source_id="1")
        assert r.journal == "Nature"

    def test_abstract_stripped(self):
        r = LiteratureResult(abstract="  text  ", source="pubmed", source_id="1")
        assert r.abstract == "text"

    def test_invalid_source_raises(self):
        with pytest.raises(ValidationError):
            LiteratureResult(source="not_a_real_source", source_id="1")

    def test_valid_sources_accepted(self):
        for src in [
            "europepmc",
            "pubmed",
            "semanticscholar",
            "openalex",
            "crossref",
            "unpaywall",
            "arxiv",
            "clinicaltrials",
            "zenodo",
            "doaj",
            "dblp",
            "hal",
            "core",
            "icite",
        ]:
            LiteratureResult(source=src, source_id="1")

    def test_serialize_year(self):
        r = LiteratureResult(source="pubmed", source_id="1", publication_year=2020)
        assert r.model_dump()["publication_year"] == 2020


class TestToPaperEntity:
    def test_basic_conversion(self):
        r = LiteratureResult(
            title="A Paper",
            doi="10.1234/x",
            pmid="1",
            pmcid="PMC1",
            journal="Nature",
            publication_year=2020,
            abstract="Abstract text",
            citation_count=5,
            source="openalex",
            source_id="W123",
        )
        paper = r.to_paper_entity()
        assert paper.title == "A Paper"
        assert paper.journal.title == "Nature"
        assert paper.openalex_id == "W123"
        assert paper.semantic_scholar_id is None

    def test_semantic_scholar_id_set(self):
        r = LiteratureResult(source="semanticscholar", source_id="S1", title="T")
        paper = r.to_paper_entity()
        assert paper.semantic_scholar_id == "S1"
        assert paper.openalex_id is None

    def test_no_journal_leaves_journal_none(self):
        r = LiteratureResult(source="pubmed", source_id="1", title="T")
        paper = r.to_paper_entity()
        assert paper.journal is None

    def test_authors_converted(self):
        r = LiteratureResult(
            source="pubmed",
            source_id="1",
            title="T",
            authors=[
                Author(name="Jane Doe", orcid="0000-0001-2345-6789", affiliation="MIT"),
                Author(name="John Smith", institution="Harvard"),
            ],
        )
        paper = r.to_paper_entity()
        assert len(paper.authors) == 2
        assert paper.authors[0]["orcid"] == "0000-0001-2345-6789"
        assert paper.authors[0]["affiliation"] == "MIT"
        assert paper.authors[1]["institution"] == "Harvard"

    def test_no_authors_is_none(self):
        r = LiteratureResult(source="pubmed", source_id="1", title="T")
        paper = r.to_paper_entity()
        assert paper.authors is None


class TestMerge:
    def test_merge_prefers_self_values(self):
        r1 = LiteratureResult(source="pubmed", source_id="1", title="From R1")
        r2 = LiteratureResult(source="openalex", source_id="2", title="From R2", journal="J")
        merged = r1.merge(r2)
        assert merged.title == "From R1"
        assert merged.journal == "J"

    def test_merge_fills_missing_fields_from_other(self):
        r1 = LiteratureResult(source="pubmed", source_id="1")
        r2 = LiteratureResult(source="openalex", source_id="2", abstract="From R2")
        merged = r1.merge(r2)
        assert merged.abstract == "From R2"


class TestLiteratureSearchResponse:
    def test_iteration(self):
        results = [
            LiteratureResult(source="pubmed", source_id="1", title="A"),
            LiteratureResult(source="pubmed", source_id="2", title="B"),
        ]
        response = LiteratureSearchResponse(results=results)
        assert [r.title for r in response] == ["A", "B"]

    def test_len(self):
        results = [LiteratureResult(source="pubmed", source_id="1")]
        response = LiteratureSearchResponse(results=results)
        assert len(response) == 1

    def test_getitem(self):
        results = [
            LiteratureResult(source="pubmed", source_id="1", title="A"),
            LiteratureResult(source="pubmed", source_id="2", title="B"),
        ]
        response = LiteratureSearchResponse(results=results)
        assert response[1].title == "B"

    def test_optional_fields(self):
        response = LiteratureSearchResponse(
            results=[], total_results=100, page=1, page_size=25, query="cancer"
        )
        assert response.total_results == 100
        assert response.query == "cancer"
