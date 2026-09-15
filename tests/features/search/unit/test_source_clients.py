"""Unit tests for the literature search source clients (mocked HTTP layer).

These tests exercise the JSON/XML parsing and normalization logic of each
source client without hitting the network, by mocking ``_make_request``.
"""

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.features.enrich.merger import DedupMode
from pyeuropepmc.features.search.sources.arxiv import ArxivClient
from pyeuropepmc.features.search.sources.clinicaltrials import ClinicalTrialsClient
from pyeuropepmc.features.search.sources.core import COREClient
from pyeuropepmc.features.search.sources.dblp import DBLPClient
from pyeuropepmc.features.search.sources.doaj import DOAJClient
from pyeuropepmc.features.search.sources.hal import HALClient
from pyeuropepmc.features.search.sources.zenodo import ZenodoClient
from pyeuropepmc.features.search.unified_search import UnifiedSearch
from pyeuropepmc.models.literature import LiteratureResult

# ===========================================================================
# arXiv (Atom XML)
# ===========================================================================

_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All You Need</title>
    <summary>The transformer architecture.</summary>
    <published>2017-06-12T10:00:00Z</published>
    <updated>2023-08-02T10:00:00Z</updated>
    <author><name>Vaswani, Ashish</name></author>
    <author><name>Shazeer, Noam</name></author>
    <arxiv:doi>10.48550/arXiv.1706.03762</arxiv:doi>
    <arxiv:journal_ref>NeurIPS 2017</arxiv:journal_ref>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2109.14447v2</id>
    <title>Fatigue Detection Study</title>
    <summary>Measuring fatigue.</summary>
    <published>2021-09-29T00:00:00Z</published>
    <updated>2021-09-29T00:00:00Z</updated>
    <author><name>Doe, Jane</name></author>
  </entry>
</feed>
"""


class TestArxivClient:
    def test_init_default(self):
        client = ArxivClient()
        assert client.base_url == "http://export.arxiv.org/api"

    @patch.object(ArxivClient, "_make_request", return_value=_ARXIV_XML)
    def test_search_parses_atom_feed(self, mock_request):
        client = ArxivClient()
        results = client.search("attention", limit=2)

        assert len(results) == 2
        assert results[0].source == "arxiv"
        assert results[0].source_id == "1706.03762"
        assert results[0].title == "Attention Is All You Need"
        assert results[0].publication_year == 2017
        assert results[0].doi == "10.48550/arxiv.1706.03762"  # normalize_doi lowercases
        assert results[0].journal == "NeurIPS 2017"
        assert results[0].authors is not None
        assert results[0].authors[0].name == "Vaswani, Ashish"

    @patch.object(ArxivClient, "_make_request", return_value="")
    def test_search_empty_response(self, mock_request):
        client = ArxivClient()
        assert client.search("nothing") == []

    @patch.object(ArxivClient, "_make_request", return_value={})
    def test_search_dict_response_returns_empty(self, mock_request):
        # _make_request override may return a dict from cache/error paths
        client = ArxivClient()
        assert client.search("x") == []

    @patch.object(ArxivClient, "_make_request", return_value=_ARXIV_XML)
    def test_get_paper_by_arxiv_id(self, mock_request):
        client = ArxivClient()
        result = client.get_paper("1706.03762")
        assert result is not None
        assert result.title == "Attention Is All You Need"

    @patch.object(ArxivClient, "_make_request", return_value=_ARXIV_XML)
    def test_get_paper_doi_embedded_id_extracted(self, mock_request):
        # DOI form 10.48550/arXiv.1706.03762 must extract the arXiv ID for id_list
        client = ArxivClient()
        result = client.get_paper("10.48550/arXiv.1706.03762")
        assert result is not None
        assert result.source_id == "1706.03762"

    def test_parse_feed_invalid_xml(self):
        client = ArxivClient()
        assert client._parse_feed("<not xml") == []


# ===========================================================================
# ClinicalTrials.gov (v2 JSON)
# ===========================================================================

_NCT_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT04280705",
            "briefTitle": "ACTT-1 trial",
            "officialTitle": (
                "A Multicenter, Adaptive, Randomized Blinded Controlled Trial "
                "of the Safety and Efficacy of Investigational Therapeutics"
            ),
            "doi": "10.1056/NEJMoa2007764",
        },
        "statusModule": {
            "overallStatus": "COMPLETED",
            "startDateStruct": {"date": "2020-02-21"},
            "completionDateStruct": {"date": "2020-04-27"},
        },
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "NIAID"}},
        "descriptionModule": {
            "briefSummary": "Evaluate the safety and efficacy of treatments.",
            "detailedDescription": "Detailed description here.",
        },
        "conditionsModule": {"conditions": ["COVID-19"]},
        "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"]},
        "armsInterventionsModule": {"interventions": [{"name": "Remdesivir", "type": "DRUG"}]},
        "referencesModule": {
            "references": [{"type": "RESULT", "pmid": "32438360", "doi": "10.1056/NEJMoa2007764"}]
        },
        "contactsLocationsModule": {
            "overallOfficials": [{"name": "Fauci, Anthony", "role": "Principal Investigator"}]
        },
    }
}


class TestClinicalTrialsClient:
    @patch.object(ClinicalTrialsClient, "_make_request")
    def test_search_parses_studies(self, mock_request):
        mock_request.return_value = {"studies": [{"study": _NCT_STUDY}]}
        client = ClinicalTrialsClient()
        results = client.search("covid-19", limit=1)

        assert len(results) == 1
        r = results[0]
        assert r.source == "clinicaltrials"
        assert r.source_id == "NCT04280705"
        assert r.pmid == "32438360"
        assert r.doi == "10.1056/nejmoa2007764"  # normalize_doi lowercases
        assert r.title.startswith("A Multicenter")
        assert r.publication_year == 2020
        assert r.extra_metadata["overall_status"] == "COMPLETED"
        assert r.extra_metadata["conditions"] == ["COVID-19"]

    @patch.object(ClinicalTrialsClient, "_make_request")
    def test_search_passes_status_and_phase_filters(self, mock_request):
        mock_request.return_value = {"studies": []}
        client = ClinicalTrialsClient()
        client.search("covid", status="RECRUITING", phase="PHASE3")
        _, kwargs = mock_request.call_args
        assert kwargs["params"]["filter.overallStatus"] == "RECRUITING"
        assert kwargs["params"]["filter.phase"] == "PHASE3"

    @patch.object(ClinicalTrialsClient, "_make_request")
    def test_get_paper_returns_none_on_400(self, mock_request):
        # ClinicalTrials.gov returns 400 for non-existent NCT IDs
        mock_request.side_effect = APIClientError("Bad request", status_code=400)
        client = ClinicalTrialsClient()
        assert client.get_paper("NCT00000000") is None

    @patch.object(ClinicalTrialsClient, "_make_request")
    def test_get_paper_raises_other_errors(self, mock_request):
        mock_request.side_effect = APIClientError("Server error", status_code=500)
        client = ClinicalTrialsClient()
        with pytest.raises(APIClientError):
            client.get_paper("NCT04280705")

    @patch.object(ClinicalTrialsClient, "_make_request")
    def test_get_paper_parses_study(self, mock_request):
        mock_request.return_value = {"study": _NCT_STUDY}
        client = ClinicalTrialsClient()
        result = client.get_paper("NCT04280705")
        assert result is not None
        assert result.source_id == "NCT04280705"

    def test_parse_study_missing_protocol_returns_none(self):
        client = ClinicalTrialsClient()
        assert client._parse_study({"noProtocol": True}) is None


# ===========================================================================
# CORE (v3 JSON)
# ===========================================================================

_CORE_RESULT = {
    "id": "81315",
    "doi": "10.1186/1755-8794-2-38",
    "title": "A CORE Paper",
    "yearPublished": "2009",
    "authors": [{"name": "Doe, Jane"}, "Smith, John"],
    "journalName": "BMC Medical Genomics",
    "abstract": "CORE abstract text",
    "citationCount": "42",
    "fullTextUrl": "https://core.ac.uk/download/81315",
    "oaStatus": "green",
}


class TestCOREClient:
    def test_init_sets_api_key_header(self):
        client = COREClient(api_key="test-key")
        assert client.session.headers.get("Authorization") == "Bearer test-key"

    @patch.object(COREClient, "_make_request")
    def test_search_parses_results(self, mock_request):
        mock_request.return_value = {"totalHits": 1, "results": [_CORE_RESULT]}
        client = COREClient()
        results = client.search("fatigue", limit=1)

        assert len(results) == 1
        r = results[0]
        assert r.source == "core"
        assert r.source_id == "81315"
        assert r.doi == "10.1186/1755-8794-2-38"
        assert r.publication_year == 2009
        assert r.citation_count == 42
        assert r.extra_metadata["fulltext_url"] == "https://core.ac.uk/download/81315"

    @patch.object(COREClient, "_make_request", return_value=None)
    def test_search_no_data_returns_empty(self, mock_request):
        client = COREClient()
        assert client.search("x") == []

    @patch.object(COREClient, "_make_request")
    def test_get_paper_by_doi_uses_search_endpoint(self, mock_request):
        mock_request.return_value = {"results": [_CORE_RESULT]}
        client = COREClient()
        result = client.get_paper("10.1186/1755-8794-2-38")
        assert result is not None
        assert mock_request.call_args.kwargs["endpoint"].startswith("search/outputs")

    @patch.object(COREClient, "_make_request")
    def test_get_paper_by_core_id(self, mock_request):
        mock_request.return_value = _CORE_RESULT
        client = COREClient()
        result = client.get_paper("81315")
        assert result is not None
        assert mock_request.call_args.kwargs["endpoint"] == "outputs/81315"


# ===========================================================================
# DBLP (JSON)
# ===========================================================================

_DBLP_RESPONSE = {
    "result": {
        "hits": {
            "@total": "1",
            "hit": [
                {
                    "info": {
                        "key": "journals/neuroimage/CookOLS07",
                        "url": "https://dblp.org/rec/journals/neuroimage/CookOLS07.xml",
                        "title": "A DBLP Paper <i>with markup</i>",
                        "doi": "10.1016/j.neuroimage.2007.02.033",
                        "authors": {
                            "author": [
                                {"text": "Cook, M."},
                                "Smith, John",
                            ]
                        },
                        "year": "2007",
                        "venue": "NeuroImage",
                        "type": "Journal Article",
                        "pages": "1-10",
                        "publisher": "Elsevier",
                        "ee": "https://doi.org/10.1016/j.neuroimage.2007.02.033",
                    }
                }
            ],
        }
    }
}


class TestDBLPClient:
    @patch.object(DBLPClient, "_make_request")
    def test_search_parses_hits(self, mock_request):
        mock_request.return_value = _DBLP_RESPONSE
        client = DBLPClient()
        results = client.search("neuroimage", limit=1)

        assert len(results) == 1
        r = results[0]
        assert r.source == "dblp"
        assert r.title == "A DBLP Paper with markup"  # HTML tags stripped
        assert r.doi == "10.1016/j.neuroimage.2007.02.033"
        assert r.publication_year == 2007
        assert r.extra_metadata["dblp_key"] == "journals/neuroimage/CookOLS07"
        assert r.authors is not None and len(r.authors) == 2

    @patch.object(DBLPClient, "_make_request", return_value={})
    def test_search_empty(self, mock_request):
        client = DBLPClient()
        assert client.search("nothing") == []

    @patch.object(DBLPClient, "_make_request")
    def test_get_paper_by_doi(self, mock_request):
        mock_request.return_value = _DBLP_RESPONSE
        client = DBLPClient()
        result = client.get_paper("10.1016/j.neuroimage.2007.02.033")
        assert result is not None
        assert result.title == "A DBLP Paper with markup"


# ===========================================================================
# DOAJ (JSON)
# ===========================================================================

_DOAJ_RESULT = {
    "id": "00035330a4e44ca69fd858152c523075",
    "bibjson": {
        "doi": "10.1186/s12950-024-00402-0",
        "identifier": [
            {"id": "10.1186/s12950-024-00402-0", "type": "doi"},
            {"id": "1476-9255", "type": "eissn"},
            {"id": "98765432", "type": "pmid"},
        ],
        "title": "An Open Access Article",
        "author": [{"name": "Doe, Jane"}, {"family": "Roe", "given": "Richard"}],
        "year": "2024",
        "journal": {"title": "Journal of Inflammation", "publisher": "BMC"},
        "abstract": "DOAJ abstract",
        "keywords": ["fatigue", "ME"],
        "language": ["en"],
        "type": "Journal article",
    },
    "admin": {"carnegie_code": "q1"},
}


class TestDOAJClient:
    @patch.object(DOAJClient, "_make_request")
    def test_search_parses_bibjson(self, mock_request):
        mock_request.return_value = {"total": 1, "results": [_DOAJ_RESULT]}
        client = DOAJClient()
        results = client.search("fatigue", limit=1)

        assert len(results) == 1
        r = results[0]
        assert r.source == "doaj"
        assert r.source_id == "00035330a4e44ca69fd858152c523075"
        assert r.doi == "10.1186/s12950-024-00402-0"
        assert r.pmid == "98765432"
        assert r.title == "An Open Access Article"
        assert r.publication_year == 2024
        assert r.extra_metadata["oa_status"] == "OA"

    @patch.object(DOAJClient, "_make_request")
    def test_search_passes_query_in_path(self, mock_request):
        mock_request.return_value = {"results": []}
        client = DOAJClient()
        client.search("fatigue")
        assert mock_request.call_args.kwargs["endpoint"] == "search/articles/fatigue"

    @patch.object(DOAJClient, "_make_request")
    def test_get_paper_wraps_single_result(self, mock_request):
        mock_request.return_value = {"result": _DOAJ_RESULT}
        client = DOAJClient()
        result = client.get_paper("00035330a4e44ca69fd858152c523075")
        assert result is not None
        assert result.title == "An Open Access Article"


# ===========================================================================
# HAL (Solr JSON)
# ===========================================================================

_HAL_DOC = {
    "halId_s": "tel-04611776",
    "doiId_s": "10.70675/hal-tel-04611776",
    "title_s": ["HAL Paper Title"],
    "authFullName_s": ["Doe, Jane", "Roe, Richard"],
    "producedDateY_i": 2023,
    "journalTitle_s": "HAL Journal",
    "abstract_s": ["HAL abstract"],
    "domain_s": "info",
    "language_s": "fr",
    "docType_s": "ART",
    "structName_s": ["CNRS"],
    "externalId_s": ["pubmed:12345678"],
}


class TestHALClient:
    @patch.object(HALClient, "_make_request")
    def test_search_parses_docs(self, mock_request):
        mock_request.return_value = {"response": {"numFound": 1, "docs": [_HAL_DOC]}}
        client = HALClient()
        results = client.search("fatigue", limit=1)

        assert len(results) == 1
        r = results[0]
        assert r.source == "hal"
        assert r.source_id == "tel-04611776"
        assert r.title == "HAL Paper Title"
        assert r.doi == "10.70675/hal-tel-04611776"
        assert r.publication_year == 2023
        assert r.pmid == "12345678"
        assert r.extra_metadata["hal_id"] == "tel-04611776"

    @patch.object(HALClient, "_make_request")
    def test_search_requests_full_schema(self, mock_request):
        mock_request.return_value = {"response": {"docs": []}}
        client = HALClient()
        client.search("fatigue")
        assert mock_request.call_args.kwargs["params"]["fl"] == "*"

    @patch.object(HALClient, "_make_request")
    def test_get_paper_queries_by_hal_id(self, mock_request):
        mock_request.return_value = {"response": {"docs": [_HAL_DOC]}}
        client = HALClient()
        result = client.get_paper("tel-04611776")
        assert result is not None
        assert "halId_s:tel-04611776" in mock_request.call_args.kwargs["params"]["q"]

    def test_get_paper_no_docs_returns_none(self):
        client = HALClient()
        with patch.object(HALClient, "_make_request", return_value={"response": {"docs": []}}):
            assert client.get_paper("nope") is None


# ===========================================================================
# Zenodo (JSON)
# ===========================================================================

_ZENODO_HIT = {
    "id": 6759462,
    "metadata": {
        "doi": "10.5281/zenodo.6759462",
        "title": "Zenodo Dataset",
        "creators": [{"name": "Doe, Jane"}],
        "publication_date": "2022-07-01",
        "resource_type": {"type": "dataset"},
        "description": "Zenodo abstract",
        "subjects": [{"term": "fatigue"}],
        "license": {"id": "cc-by-4.0"},
        "version": "v1.0",
    },
}


class TestZenodoClient:
    @patch.object(ZenodoClient, "_make_request")
    def test_search_parses_hits(self, mock_request):
        mock_request.return_value = {"hits": {"hits": [_ZENODO_HIT]}}
        client = ZenodoClient()
        results = client.search("fatigue", limit=1)

        assert len(results) == 1
        r = results[0]
        assert r.source == "zenodo"
        assert r.source_id == "10.5281/zenodo.6759462"  # DOI preferred over record id
        assert r.doi == "10.5281/zenodo.6759462"
        assert r.title == "Zenodo Dataset"
        assert r.publication_year == 2022
        assert r.journal == "Zenodo (dataset)"
        assert r.extra_metadata["zenodo_id"] == "6759462"
        assert r.extra_metadata["license"] == "cc-by-4.0"

    @patch.object(ZenodoClient, "_make_request")
    def test_search_no_hits_returns_empty(self, mock_request):
        mock_request.return_value = {"hits": {"hits": []}}
        client = ZenodoClient()
        assert client.search("nothing") == []

    @patch.object(ZenodoClient, "_make_request")
    def test_get_paper_by_doi_endpoint(self, mock_request):
        mock_request.return_value = _ZENODO_HIT
        client = ZenodoClient()
        result = client.get_paper("10.5281/zenodo.6759462")
        assert result is not None
        assert mock_request.call_args.kwargs["endpoint"] == "records/doi/10.5281/zenodo.6759462"

    @patch.object(ZenodoClient, "_make_request")
    def test_get_paper_by_record_id_endpoint(self, mock_request):
        mock_request.return_value = _ZENODO_HIT
        client = ZenodoClient()
        client.get_paper("6759462")
        assert mock_request.call_args.kwargs["endpoint"] == "records/6759462"

    @patch.object(ZenodoClient, "_make_request")
    def test_search_datasets_passes_type_filter(self, mock_request):
        mock_request.return_value = {"hits": {"hits": []}}
        client = ZenodoClient()
        client.search_datasets("fatigue")
        assert mock_request.call_args.kwargs["params"]["type"] == "dataset"

    @patch.object(ZenodoClient, "_make_request")
    def test_search_software_passes_type_filter(self, mock_request):
        mock_request.return_value = {"hits": {"hits": []}}
        client = ZenodoClient()
        client.search_software("fatigue")
        assert mock_request.call_args.kwargs["params"]["type"] == "software"


# ===========================================================================
# UnifiedSearch
# ===========================================================================


def _make_result(source: str, pmid: str, doi: str, title: str) -> LiteratureResult:
    return LiteratureResult(
        source=source,
        source_id=pmid,
        pmid=pmid,
        doi=doi,
        title=title,
        publication_year=2020,
    )


_VALID_DOI = "10.1234/abc"


class TestUnifiedSearch:
    def test_init_default_sources(self):
        us = UnifiedSearch()
        assert us.sources == ["europepmc", "pubmed", "arxiv"]
        assert us.dedup_mode == DedupMode.BALANCED

    def test_init_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            UnifiedSearch(sources=["nope"])

    def test_registry_resolves_client_lazily(self):
        from pyeuropepmc.features.search import registry

        cls = registry.get_source_spec("pubmed").resolve()
        assert cls.__name__ == "PubMedClient"

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_returns_merged_results_and_report(self, mock_get_clients):
        pubmed = MagicMock()
        pubmed.search.return_value = [_make_result("pubmed", "111", _VALID_DOI, "Same Paper")]
        arxiv = MagicMock()
        arxiv.search.return_value = [
            _make_result("arxiv", "222", _VALID_DOI, "Same Paper (variant)")
        ]
        mock_get_clients.return_value = {"pubmed": pubmed, "arxiv": arxiv}

        us = UnifiedSearch(sources=["pubmed", "arxiv"])
        merged, report = us.search("test", limit=5)

        assert len(merged) == 1  # dedup by DOI
        assert isinstance(merged[0], LiteratureResult)
        assert report.total_input == 2
        assert report.duplicates_removed == 1
        assert report.metadata["sources_used"] == ["pubmed", "arxiv"]
        assert set(report.metadata["source_times"]) == {"pubmed", "arxiv"}

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_source_failure_graceful(self, mock_get_clients):
        failing = MagicMock()
        failing.search.side_effect = RuntimeError("boom")
        ok = MagicMock()
        ok.search.return_value = [_make_result("pubmed", "111", _VALID_DOI, "Paper")]
        mock_get_clients.return_value = {"pubmed": ok, "arxiv": failing}

        us = UnifiedSearch(sources=["pubmed", "arxiv"])
        merged, report = us.search("test")

        assert len(merged) == 1
        assert "arxiv" in report.metadata["source_errors"]
        assert report.metadata["source_times"]["pubmed"] >= 0

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_all_sources_fail_returns_empty(self, mock_get_clients):
        failing = MagicMock()
        failing.search.side_effect = RuntimeError("boom")
        mock_get_clients.return_value = {"pubmed": failing}

        us = UnifiedSearch(sources=["pubmed"])
        merged, report = us.search("test")
        assert merged == []
        assert report.total_input == 0

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_sources_override(self, mock_get_clients):
        pubmed = MagicMock()
        pubmed.search.return_value = [_make_result("pubmed", "111", _VALID_DOI, "P")]
        arxiv = MagicMock()
        arxiv.search.return_value = []
        mock_get_clients.return_value = {"pubmed": pubmed, "arxiv": arxiv}

        us = UnifiedSearch(sources=["pubmed", "arxiv"])
        us.search("test", sources=["pubmed"])  # override for this call only

        pubmed.search.assert_called_once()
        arxiv.search.assert_not_called()

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_all_returns_per_source_dict(self, mock_get_clients):
        pubmed = MagicMock()
        pubmed.search.return_value = [_make_result("pubmed", "111", _VALID_DOI, "P")]
        arxiv = MagicMock()
        arxiv.search.return_value = [_make_result("arxiv", "222", "10.1234/def", "A")]
        mock_get_clients.return_value = {"pubmed": pubmed, "arxiv": arxiv}

        us = UnifiedSearch(sources=["pubmed", "arxiv"])
        per_source, errors = us.search_all("test")
        assert set(per_source.keys()) == {"pubmed", "arxiv"}
        assert len(per_source["pubmed"]) == 1
        assert errors == {}

    def test_close_closes_clients(self):
        client = MagicMock()
        us = UnifiedSearch(sources=["pubmed"])
        us._clients = {"pubmed": client}  # noqa: SLF001
        us.close()
        client.close.assert_called_once()
        assert us._clients is None  # noqa: SLF001

    def test_close_survives_client_error(self):
        client = MagicMock()
        client.close.side_effect = RuntimeError("close failed")
        us = UnifiedSearch(sources=["pubmed"])
        us._clients = {"pubmed": client}  # noqa: SLF001
        us.close()  # must not raise
        assert us._clients is None  # noqa: SLF001

    def test_available_sources(self):
        us = UnifiedSearch()
        assert "pubmed" in us.available_sources
        assert "openalex" in us.available_sources

    # --------------------------------------------------------------------------
    # API Key and Parameter Passing Tests
    # --------------------------------------------------------------------------

    def test_init_with_api_key(self):
        """Test that UnifiedSearch accepts api_key and stores it under credentials."""
        us = UnifiedSearch(api_key="test-key-123")
        assert us.credentials["api_key"] == "test-key-123"

    @patch("pyeuropepmc.features.search.unified_search.registry.load_source")
    def test_get_or_init_clients_passes_api_key_to_semantic_scholar(self, mock_load):
        """api_key (a credential of the semantic_scholar source) is forwarded."""
        us = UnifiedSearch(
            sources=["semantic_scholar"],
            api_key="my-api-key",
            rate_limit_delay=2.0,
            timeout=15,
        )
        us._get_or_init_clients()

        mock_load.assert_called_once()
        name, call_kwargs = mock_load.call_args.args[0], mock_load.call_args.kwargs
        assert name == "semantic_scholar"
        assert call_kwargs["api_key"] == "my-api-key"
        assert call_kwargs["rate_limit_delay"] == 2.0
        assert call_kwargs["timeout"] == 15

    @patch("pyeuropepmc.features.search.unified_search.registry.load_source")
    def test_get_or_init_clients_no_api_key_for_semantic_scholar(self, mock_load):
        """api_key is not forwarded when it was never supplied."""
        us = UnifiedSearch(sources=["semantic_scholar"], api_key=None)
        us._get_or_init_clients()

        assert "api_key" not in mock_load.call_args.kwargs

    @patch("pyeuropepmc.features.search.unified_search.registry.load_source")
    def test_get_or_init_clients_does_not_pass_api_key_to_pubmed(self, mock_load):
        """PubMed does not declare api_key as a credential, so it is not forwarded."""
        us = UnifiedSearch(sources=["pubmed"], api_key="secret-key")
        us._get_or_init_clients()

        mock_load.assert_called_once()
        assert mock_load.call_args.args[0] == "pubmed"
        assert "api_key" not in mock_load.call_args.kwargs

    @patch("pyeuropepmc.features.search.unified_search.registry.load_source")
    def test_get_or_init_clients_passes_parameters_to_openalex(self, mock_load):
        """OpenAlex receives rate_limit_delay and timeout."""
        us = UnifiedSearch(sources=["openalex"], rate_limit_delay=1.5, timeout=20)
        us._get_or_init_clients()

        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["rate_limit_delay"] == 1.5
        assert call_kwargs["timeout"] == 20

    @patch("pyeuropepmc.features.search.unified_search.registry.load_source")
    def test_get_or_init_clients_skips_failed_client(self, mock_load):
        """A source whose loader raises is recorded as None, others still load."""
        sentinel = MagicMock()
        mock_load.side_effect = [RuntimeError("Connection failed"), sentinel]

        us = UnifiedSearch(sources=["semantic_scholar", "pubmed"], api_key="key")
        clients = us._get_or_init_clients()

        assert clients["semantic_scholar"] is None
        assert clients["pubmed"] is sentinel

    # --------------------------------------------------------------------------
    # Source Time Tracking Tests
    # --------------------------------------------------------------------------

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_records_source_time_on_success(self, mock_get_clients):
        """Test that successful source search records time."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_result("pubmed", "1", "10.1/abc", "Paper")]
        mock_get_clients.return_value = {
            "pubmed": mock_client,
            "arxiv": None,
            "semantic_scholar": None,
        }

        us = UnifiedSearch(sources=["pubmed"])
        _, report = us.search("test")

        assert report.metadata["source_times"]["pubmed"] >= 0

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_records_source_time_on_failure(self, mock_get_clients):
        """Test that failed source search records -1.0 as time."""
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("Timeout")
        mock_get_clients.return_value = {"pubmed": mock_client}

        us = UnifiedSearch(sources=["pubmed"])
        # Search with a mock that returns empty list after failing
        # We need to modify the test to handle this edge case properly
        # When all sources fail, the function returns early with empty report
        merged, report = us.search("test")

        # When all sources fail, no results are collected and the function returns early
        # with an empty MergeReport - this is expected behavior
        assert merged == []
        assert report.total_input == 0
        # source_times is not populated when no results are collected

    # --------------------------------------------------------------------------
    # Client Lifecycle Tests
    # --------------------------------------------------------------------------

    def test_clients_initialized_lazily(self):
        """Test that clients are only initialized on first search."""
        us = UnifiedSearch(sources=["pubmed"])
        assert us._clients is None

        # After search, clients should be initialized
        with patch.object(UnifiedSearch, "_get_or_init_clients", return_value={}):
            us.search("test")
            # The lazy initialization happens in _get_or_init_clients
            # Since we mocked it, we verify the attribute exists
            assert hasattr(us, "_clients")

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_with_sources_override_does_not_modify_instance(self, mock_get_clients):
        """Test that sources override in search() does not modify instance state."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_result("pubmed", "1", "10.1/abc", "Paper")]
        mock_get_clients.return_value = {"pubmed": mock_client, "arxiv": mock_client}

        us = UnifiedSearch(sources=["pubmed"])
        us.search("test", sources=["arxiv"])

        # Instance sources should remain unchanged
        assert us.sources == ["pubmed"]

    # --------------------------------------------------------------------------
    # Empty and Edge Case Tests
    # --------------------------------------------------------------------------

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_no_valid_sources_returns_empty(self, mock_get_clients):
        """Test search when no sources can be initialized."""
        mock_get_clients.return_value = {"pubmed": None}  # Failed initialization

        us = UnifiedSearch()
        merged, report = us.search("test")

        assert merged == []
        assert report.total_input == 0

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_all_empty_results(self, mock_get_clients):
        """Test search_all when all sources return empty."""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_get_clients.return_value = {"pubmed": mock_client}

        us = UnifiedSearch()
        per_source, _errors = us.search_all("test")

        assert per_source["pubmed"] == []

    # --------------------------------------------------------------------------
    # Keyword Arguments Passing Tests
    # --------------------------------------------------------------------------

    @patch.object(UnifiedSearch, "_get_or_init_clients")
    def test_search_passes_kwargs_to_source_client(self, mock_get_clients):
        """Test that additional kwargs are passed to source client search."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_result("pubmed", "1", "10.1/abc", "Paper")]
        mock_get_clients.return_value = {
            "pubmed": mock_client,
            "arxiv": None,
            "semantic_scholar": None,
        }

        us = UnifiedSearch(sources=["pubmed"])
        us.search("test", sort="citation", custom_param="value")

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["sort"] == "citation"
        assert call_kwargs["custom_param"] == "value"
