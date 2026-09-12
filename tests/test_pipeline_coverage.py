"""Coverage for PaperProcessingPipeline's internal helpers: _download_xml,
_get_search_data, _get_pmcid_from_doi, _enrich_paper,
_update_authors_with_enrichment, _convert_to_rdf, _save_rdf, and _parse_xml's
search-data-lookup exception path.
"""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.models import AuthorEntity, PaperEntity
from pyeuropepmc.pipeline import PaperProcessingPipeline, PipelineConfig


@pytest.fixture
def pipeline():
    config = PipelineConfig(
        enable_cache=False, enable_enrichment=False, output_dir=tempfile.gettempdir()
    )
    p = PaperProcessingPipeline(config)
    yield p
    if p.enricher:
        p.enricher.close()


def _epmc_search_result(pmcid: str | None = "PMC1"):
    paper = {"pmcid": pmcid} if pmcid else {}
    return {"resultList": {"result": [paper]}}


class TestDownloadXml:
    def test_by_pmcid(self, pipeline):
        with patch.object(
            pipeline.fulltext_client, "get_fulltext_content", return_value="<xml/>"
        ) as mock_get:
            result = pipeline._download_xml(doi=None, pmcid="PMC1")
        assert result == "<xml/>"
        mock_get.assert_called_once_with("PMC1", format_type="xml")

    def test_by_doi_resolves_pmcid(self, pipeline):
        with (
            patch.object(pipeline, "_get_pmcid_from_doi", return_value="PMC2"),
            patch.object(
                pipeline.fulltext_client, "get_fulltext_content", return_value="<xml/>"
            ) as mock_get,
        ):
            result = pipeline._download_xml(doi="10.1/x", pmcid=None)
        assert result == "<xml/>"
        mock_get.assert_called_once_with("PMC2", format_type="xml")

    def test_by_doi_no_pmcid_found_returns_none(self, pipeline):
        with patch.object(pipeline, "_get_pmcid_from_doi", return_value=None):
            assert pipeline._download_xml(doi="10.1/x", pmcid=None) is None

    def test_neither_doi_nor_pmcid_returns_none(self, pipeline):
        assert pipeline._download_xml(doi=None, pmcid=None) is None

    def test_exception_returns_none(self, pipeline):
        with patch.object(
            pipeline.fulltext_client, "get_fulltext_content", side_effect=RuntimeError("boom")
        ):
            assert pipeline._download_xml(doi=None, pmcid="PMC1") is None


class TestGetPmcidFromDoi:
    def test_success(self, pipeline):
        with patch.object(
            pipeline.search_client, "search", return_value=_epmc_search_result("PMC1")
        ):
            assert pipeline._get_pmcid_from_doi("10.1/x") == "PMC1"

    def test_no_pmcid_in_result(self, pipeline):
        with patch.object(
            pipeline.search_client, "search", return_value=_epmc_search_result(None)
        ):
            assert pipeline._get_pmcid_from_doi("10.1/x") is None

    def test_empty_result_list(self, pipeline):
        with patch.object(
            pipeline.search_client,
            "search",
            return_value={"resultList": {"result": []}},
        ):
            assert pipeline._get_pmcid_from_doi("10.1/x") is None

    def test_malformed_response(self, pipeline):
        with patch.object(pipeline.search_client, "search", return_value={"unexpected": True}):
            assert pipeline._get_pmcid_from_doi("10.1/x") is None

    def test_exception_returns_none(self, pipeline):
        with patch.object(
            pipeline.search_client, "search", side_effect=RuntimeError("boom")
        ):
            assert pipeline._get_pmcid_from_doi("10.1/x") is None


class TestGetSearchData:
    def test_doi_identifier(self, pipeline):
        with patch.object(
            pipeline.search_client, "search", return_value=_epmc_search_result("PMC1")
        ) as mock_search:
            data = pipeline._get_search_data("10.1/x")
        assert data == {"pmcid": "PMC1"}
        args, _ = mock_search.call_args
        assert args[0] == "DOI:10.1/x"

    def test_pmcid_identifier(self, pipeline):
        with patch.object(
            pipeline.search_client, "search", return_value=_epmc_search_result("PMC1")
        ) as mock_search:
            pipeline._get_search_data("PMC1")
        args, _ = mock_search.call_args
        assert args[0] == "PMCID:PMC1"

    def test_no_results(self, pipeline):
        with patch.object(
            pipeline.search_client, "search", return_value={"resultList": {"result": []}}
        ):
            assert pipeline._get_search_data("PMC1") is None

    def test_exception_returns_none(self, pipeline):
        with patch.object(pipeline.search_client, "search", side_effect=RuntimeError("boom")):
            assert pipeline._get_search_data("PMC1") is None


class TestParseXmlSearchDataFailure:
    def test_search_data_lookup_exception_is_swallowed(self, pipeline):
        with (
            patch.object(pipeline.parser, "parse"),
            patch.object(pipeline, "_get_search_data", side_effect=RuntimeError("boom")),
            patch("pyeuropepmc.pipeline.build_paper_entities") as mock_build,
        ):
            paper = PaperEntity(pmcid="PMC1", title="T")
            mock_build.return_value = (paper, [], [], [], [], [])
            result = pipeline._parse_xml("<xml/>", doi="10.1/x")
        assert result["paper"] is paper


class TestEnrichPaper:
    def test_no_enricher_returns_none(self, pipeline):
        pipeline.enricher = None
        assert pipeline._enrich_paper(PaperEntity(doi="10.1/x")) is None

    def test_no_identifier_returns_none(self, pipeline):
        pipeline.enricher = MagicMock()
        assert pipeline._enrich_paper(PaperEntity()) is None

    def test_success_updates_paper_fields(self, pipeline):
        pipeline.enricher = MagicMock()
        pipeline.enricher.enrich_paper.return_value = {
            "citation_count": 10,
            "influential_citation_count": 3,
            "fields_of_study": ["Biology"],
        }
        paper = PaperEntity(doi="10.1/x")
        result = pipeline._enrich_paper(paper)
        assert result["citation_count"] == 10
        assert paper.citation_count == 10
        assert paper.fields_of_study == ["Biology"]

    def test_success_updates_authors(self, pipeline):
        pipeline.enricher = MagicMock()
        author = AuthorEntity(id="a1", full_name="Jane Doe")
        pipeline.enricher.enrich_paper.return_value = {
            "citation_count": 1,
            "authors": [{"name": "Jane Doe", "orcid": "0000-0001"}],
        }
        paper = PaperEntity(doi="10.1/x", authors=[author])
        pipeline._enrich_paper(paper)
        assert author.orcid == "0000-0001"

    def test_enrich_returns_none_data(self, pipeline):
        pipeline.enricher = MagicMock()
        pipeline.enricher.enrich_paper.return_value = None
        assert pipeline._enrich_paper(PaperEntity(doi="10.1/x")) is None

    def test_exception_returns_none(self, pipeline):
        pipeline.enricher = MagicMock()
        pipeline.enricher.enrich_paper.side_effect = RuntimeError("boom")
        assert pipeline._enrich_paper(PaperEntity(doi="10.1/x")) is None


class TestUpdateAuthorsWithEnrichment:
    def test_matches_by_name_and_fills_missing_fields(self, pipeline):
        author = AuthorEntity(id="a1", full_name="Jane Doe")
        pipeline._update_authors_with_enrichment(
            [author],
            [{"name": "Jane Doe", "orcid": "0000-1", "openalex_id": "A1", "semantic_scholar_id": "S1"}],
        )
        assert author.orcid == "0000-1"
        assert author.openalex_id == "A1"
        assert author.semantic_scholar_id == "S1"

    def test_does_not_overwrite_existing_values(self, pipeline):
        author = AuthorEntity(id="a1", full_name="Jane Doe", orcid="existing")
        pipeline._update_authors_with_enrichment(
            [author], [{"name": "Jane Doe", "orcid": "new"}]
        )
        assert author.orcid == "existing"

    def test_no_match_leaves_author_unchanged(self, pipeline):
        author = AuthorEntity(id="a1", full_name="Jane Doe")
        pipeline._update_authors_with_enrichment([author], [{"name": "Someone Else"}])
        assert author.orcid is None


class TestNamesMatch:
    def test_exact_match(self, pipeline):
        assert pipeline._names_match("Jane Doe", "Jane Doe")

    def test_case_insensitive(self, pipeline):
        assert pipeline._names_match("JANE DOE", "jane doe")

    def test_titles_stripped(self, pipeline):
        assert pipeline._names_match("Dr. Jane Doe", "Jane Doe")

    def test_no_match(self, pipeline):
        assert not pipeline._names_match("Jane Doe", "John Smith")


class TestConvertToRdf:
    def test_basic_conversion(self, pipeline):
        paper = MagicMock()
        paper.pmcid = "1234567"
        paper.to_rdf.return_value = "paper-uri"
        entities = {
            "paper": paper,
            "authors": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }
        result = pipeline._convert_to_rdf(entities)
        assert result["paper_uri"] == "paper-uri"
        assert result["triple_count"] == 0
        assert paper.pmcid == "PMC1234567"

    def test_pmcid_already_prefixed_untouched(self, pipeline):
        paper = MagicMock()
        paper.pmcid = "PMC1234567"
        paper.to_rdf.return_value = "uri"
        entities = {
            "paper": paper,
            "authors": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }
        pipeline._convert_to_rdf(entities)
        assert paper.pmcid == "PMC1234567"

    def test_with_enrichment_data_bumps_quality_score(self, pipeline):
        paper = MagicMock()
        paper.pmcid = None
        paper.to_rdf.return_value = "uri"
        entities = {
            "paper": paper,
            "authors": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }
        pipeline._convert_to_rdf(entities, enrichment_data={"citation_count": 1})
        call_kwargs = paper.to_rdf.call_args.kwargs
        assert call_kwargs["extraction_info"]["quality"]["completeness_score"] == 0.98

    def test_with_annotations_data(self, pipeline):
        from rdflib import Graph as RDFGraph
        from rdflib.term import URIRef

        paper = MagicMock()
        paper.pmcid = None
        paper.to_rdf.return_value = "uri"
        entities = {
            "paper": paper,
            "authors": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "references": [],
        }
        annotation_ds = MagicMock()
        annotation_ds.quads.return_value = [
            (URIRef("http://x/s"), URIRef("http://x/p"), URIRef("http://x/o"), URIRef("http://x/g"))
        ]
        with patch(
            "pyeuropepmc.pipeline.convert_annotations_to_rdf", return_value=annotation_ds
        ):
            result = pipeline._convert_to_rdf(entities, annotations_data=[{"a": 1}])
        assert result["triple_count"] == 1


class TestSaveRdf:
    def test_turtle_extension(self, pipeline):
        graph = MagicMock()
        with patch.object(pipeline.rdf_mapper, "serialize_graph") as mock_serialize:
            path = pipeline._save_rdf(graph, "10.1234/x.y")
        assert path.suffix == ".ttl"
        mock_serialize.assert_called_once()

    def test_identifier_sanitized_in_filename(self, pipeline):
        graph = MagicMock()
        with patch.object(pipeline.rdf_mapper, "serialize_graph"):
            path = pipeline._save_rdf(graph, "10.1234/x.y:z")
        assert "/" not in path.name.replace(str(pipeline.output_dir), "")
        assert ":" not in path.stem

    def test_prefix_applied(self, pipeline):
        graph = MagicMock()
        with patch.object(pipeline.rdf_mapper, "serialize_graph"):
            path = pipeline._save_rdf(graph, "PMC1", prefix="paper_")
        assert path.name.startswith("paper_")

    def test_non_turtle_format(self, pipeline):
        pipeline.config.output_format = "xml"
        graph = MagicMock()
        with patch.object(pipeline.rdf_mapper, "serialize_graph"):
            path = pipeline._save_rdf(graph, "PMC1")
        assert path.suffix == ".xml"
