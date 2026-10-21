"""Unit tests for the find_open_access MCP tool and its shaping helpers (hermetic).

``RECORD`` is shaped after the Unpaywall v2 data-format documentation (field names and
nesting), not captured from a live call: Unpaywall asks every caller for a contact
e-mail and none is configured where these tests were written. The live end-to-end test
therefore runs only when ``UNPAYWALL_EMAIL`` is set.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, UnpaywallError
from pyeuropepmc.mcp import _openaccess as oa, server as srv
from pyeuropepmc.mcp.server import ToolError

REPO_COPY = {
    "url": "https://europepmc.org/articles/PMC3525259",
    "url_for_pdf": "https://europepmc.org/articles/PMC3525259?pdf=render",
    "url_for_landing_page": "https://europepmc.org/articles/PMC3525259",
    "license": "cc-by",
    "host_type": "repository",
    "version": "publishedVersion",
    "repository_institution": "pubmedcentral.nih.gov",
    "evidence": "oa repository (via OAI-PMH doi match)",
    "endpoint_id": "b5e840539009389b1a6",
    "pmh_id": "oai:pubmedcentral.nih.gov:3525259",
    "is_best": True,
    "updated": "2026-01-01T00:00:00",
}
RECORD = {
    "doi": "10.1186/1479-7364-2-2-138",
    "title": "Analysis and update of the human aldehyde dehydrogenase (ALDH) gene family",
    "year": 2005,
    "is_oa": True,
    "oa_status": "gold",
    "journal_is_oa": True,
    "best_oa_location": REPO_COPY,
    "oa_locations": [
        REPO_COPY,
        {**REPO_COPY, "url": "https://example.org/a", "is_best": False, "license": None},
        {**REPO_COPY, "url": "https://example.org/b", "is_best": False},
    ],
}


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch):
    for name in ("UNPAYWALL_EMAIL", "CROSSREF_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    for cache in (srv._unpaywall_client_cache, srv._client_cache):
        cache.reset()
    yield
    for cache in (srv._unpaywall_client_cache, srv._client_cache):
        cache.reset()


class TestCleanDoi:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("10.1038/s41586-020-2649-2", "10.1038/s41586-020-2649-2"),
            ("  10.1038/x  ", "10.1038/x"),
            ("doi:10.1038/x", "10.1038/x"),
            ("DOI: 10.1038/x", "10.1038/x"),
            ("https://doi.org/10.1038/x", "10.1038/x"),
            ("http://dx.doi.org/10.1038/x", "10.1038/x"),
            ("10.1002/(SICI)1097-0258(19980815/30)17:15/16<1661::AID-SIM968>3.0.CO;2-2",) * 2,
        ],
    )
    def test_accepts_and_normalises(self, raw, expected):
        assert oa.clean_doi(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abc", "10.12/x", "10.1234/", "11.1234/x", "10.1234/a b"])
    def test_rejects_malformed(self, raw):
        assert oa.clean_doi(raw) == ""


class TestSummarize:
    def test_open_record(self):
        out = oa.summarize(RECORD)
        assert out["is_oa"] is True
        assert out["oa_status"] == "gold"
        assert out["best_location"] == {
            "url": REPO_COPY["url"],
            "pdf_url": REPO_COPY["url_for_pdf"],
            "landing_page_url": REPO_COPY["url_for_landing_page"],
            "license": "cc-by",
            "host_type": "repository",
            "version": "publishedVersion",
            "repository": "pubmedcentral.nih.gov",
        }
        assert out["location_count"] == 3
        assert [a["url"] for a in out["alternatives"]] == [
            "https://example.org/a",
            "https://example.org/b",
        ]
        assert out["title"].startswith("Analysis and update")
        assert out["year"] == 2005

    def test_bookkeeping_is_dropped(self):
        out = oa.summarize(RECORD)
        for key in ("evidence", "endpoint_id", "pmh_id", "updated", "is_best"):
            assert key not in out["best_location"]

    def test_closed_record(self):
        out = oa.summarize(
            {"is_oa": False, "oa_status": "closed", "best_oa_location": None, "oa_locations": None}
        )
        assert out["is_oa"] is False
        assert out["best_location"] is None
        assert out["alternatives"] == []
        assert out["location_count"] == 0

    def test_alternatives_are_capped(self):
        many = {"is_oa": True, "oa_locations": [{"url": f"https://x/{i}"} for i in range(12)]}
        out = oa.summarize(many)
        assert len(out["alternatives"]) == 5
        assert out["location_count"] == 12

    def test_empty_strings_become_none(self):
        out = oa.summarize({"best_oa_location": {"url": "https://x", "license": "  "}})
        assert out["best_location"]["license"] is None

    def test_junk_fields_do_not_crash(self):
        out = oa.summarize(
            {"oa_locations": ["junk", None], "best_oa_location": "junk", "year": "x"}
        )
        assert out["best_location"] is None
        assert out["location_count"] == 0
        assert out["year"] is None


def _setup(*, unpaywall=RECORD, europepmc=None, europepmc_error=None):
    unpaywall_client = MagicMock()
    unpaywall_client.lookup_by_doi.return_value = unpaywall
    srv._unpaywall_client_cache.set(unpaywall_client)
    epmc = MagicMock()
    if europepmc_error:
        epmc.search_all.side_effect = europepmc_error
    else:
        epmc.search_all.return_value = [] if europepmc is None else [europepmc]
    srv._client_cache.set(epmc)
    return unpaywall_client, epmc


OA_RECORD = {"pmcid": "PMC3525259", "isOpenAccess": "Y", "doi": "10.1186/1479-7364-2-2-138"}


class TestFindOpenAccess:
    def test_doi_input_with_europepmc_fulltext(self):
        unpaywall, epmc = _setup(europepmc=OA_RECORD)

        out = _run(srv.find_open_access(doi="https://doi.org/10.1186/1479-7364-2-2-138"))

        unpaywall.lookup_by_doi.assert_called_once_with("10.1186/1479-7364-2-2-138")
        assert epmc.search_all.call_args.args[0] == 'DOI:"10.1186/1479-7364-2-2-138"'
        assert out["found"] is True
        assert out["doi"] == "10.1186/1479-7364-2-2-138"
        assert out["is_oa"] is True
        assert out["best_location"]["pdf_url"]
        assert out["pmcid"] == "PMC3525259"
        assert out["europepmc_fulltext"] is True

    def test_a_single_unpaywall_request_per_call(self):
        unpaywall, _ = _setup(europepmc=OA_RECORD)
        _run(srv.find_open_access(doi="10.1186/1479-7364-2-2-138"))
        assert unpaywall.lookup_by_doi.call_count == 1

    def test_europepmc_fulltext_false_when_not_open_access(self):
        _setup(europepmc={"pmcid": "PMC9", "isOpenAccess": "N"})
        assert _run(srv.find_open_access(doi="10.1234/abcd"))["europepmc_fulltext"] is False
        _setup(europepmc={"isOpenAccess": "Y"})  # open access but not in PMC
        assert _run(srv.find_open_access(doi="10.1234/abcd"))["europepmc_fulltext"] is False

    def test_europepmc_fulltext_unknown_when_the_record_is_missing(self):
        _setup(europepmc=None)
        out = _run(srv.find_open_access(doi="10.1234/abcd"))
        assert out["europepmc_fulltext"] is None
        assert out["pmcid"] is None

    def test_a_failing_europepmc_lookup_does_not_fail_the_tool(self):
        _setup(europepmc_error=APIClientError(ErrorCodes.NET001, {"error": "boom"}))
        out = _run(srv.find_open_access(doi="10.1234/abcd"))
        assert out["is_oa"] is True
        assert out["europepmc_fulltext"] is None

    def test_pmid_is_resolved_to_a_doi(self):
        unpaywall, epmc = _setup(europepmc=OA_RECORD)
        out = _run(srv.find_open_access(pmid="16004729"))
        assert epmc.search_all.call_args.args[0] == "EXT_ID:16004729 AND SRC:MED"
        unpaywall.lookup_by_doi.assert_called_once_with("10.1186/1479-7364-2-2-138")
        assert out["europepmc_fulltext"] is True

    def test_pmcid_is_resolved_to_a_doi(self):
        _, epmc = _setup(europepmc=OA_RECORD)
        _run(srv.find_open_access(pmcid="pmc3525259"))
        assert epmc.search_all.call_args.args[0] == "PMCID:PMC3525259"

    def test_unknown_pmid(self):
        unpaywall, _ = _setup(europepmc=None)
        with pytest.raises(ToolError, match="No Europe PMC record"):
            _run(srv.find_open_access(pmid="1"))
        unpaywall.lookup_by_doi.assert_not_called()

    def test_record_without_a_doi(self):
        unpaywall, _ = _setup(europepmc={"pmcid": "PMC1", "isOpenAccess": "Y"})
        with pytest.raises(ToolError, match="has no DOI"):
            _run(srv.find_open_access(pmcid="PMC1"))
        unpaywall.lookup_by_doi.assert_not_called()

    def test_a_europepmc_failure_is_an_error_when_the_doi_has_to_be_looked_up(self):
        _setup(europepmc_error=APIClientError(ErrorCodes.NET001, {"error": "boom"}))
        with pytest.raises(ToolError):
            _run(srv.find_open_access(pmid="1"))

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"doi": "not-a-doi"}, "doi must look like"),
            ({"pmid": "12a"}, "pmid must be digits"),
            ({"pmcid": "zzz"}, "pmcid must look like"),
            ({}, "One of pmcid, pmid, or doi"),
        ],
    )
    def test_bad_input_never_reaches_a_client(self, kwargs, message):
        unpaywall, epmc = _setup()
        with pytest.raises(ToolError, match=message):
            _run(srv.find_open_access(**kwargs))
        unpaywall.lookup_by_doi.assert_not_called()
        epmc.search_all.assert_not_called()

    def test_closed_paper(self):
        _setup(
            unpaywall={
                "is_oa": False,
                "oa_status": "closed",
                "best_oa_location": None,
                "oa_locations": [],
            }
        )
        out = _run(srv.find_open_access(doi="10.1234/abcd"))
        assert out["found"] is True
        assert out["is_oa"] is False
        assert out["oa_status"] == "closed"
        assert out["best_location"] is None

    def test_unknown_doi_is_not_an_error(self):
        _setup(unpaywall=None)
        out = _run(srv.find_open_access(doi="10.1234/abcd"))
        assert out["found"] is False
        assert out["is_oa"] is False
        assert out["note"] == "Unpaywall does not know this DOI"

    def test_rate_limit_message(self):
        unpaywall, _ = _setup()
        unpaywall.lookup_by_doi.side_effect = UnpaywallError(
            ErrorCodes.NET001, {"message": "HTTP error 429 while looking up DOI 10.1234/abcd"}
        )
        with pytest.raises(ToolError, match="rate limiting.*retry later"):
            _run(srv.find_open_access(doi="10.1234/abcd"))

    def test_other_unpaywall_errors_keep_their_text(self):
        unpaywall, _ = _setup()
        unpaywall.lookup_by_doi.side_effect = UnpaywallError(
            ErrorCodes.NET001, {"message": "HTTP error 500 while looking up DOI 10.1234/abcd"}
        )
        with pytest.raises(ToolError, match="HTTP error 500"):
            _run(srv.find_open_access(doi="10.1234/abcd"))


class TestUnpaywallClientConfiguration:
    def test_missing_email_names_the_variable(self):
        with pytest.raises(ToolError, match="UNPAYWALL_EMAIL"):
            srv._unpaywall_client_cache.get()

    def test_there_is_no_default_address_and_no_network_is_touched_first(self):
        epmc = MagicMock()
        srv._client_cache.set(epmc)
        with pytest.raises(ToolError, match="UNPAYWALL_EMAIL"):
            _run(srv.find_open_access(doi="10.1234/abcd"))
        with pytest.raises(ToolError, match="UNPAYWALL_EMAIL"):
            _run(srv.find_open_access(pmid="16004729"))
        epmc.search_all.assert_not_called()

    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            ({"UNPAYWALL_EMAIL": "me@lab.example"}, "me@lab.example"),
            ({"CROSSREF_EMAIL": "other@lab.example"}, "other@lab.example"),
            ({"UNPAYWALL_EMAIL": " me@lab.example ", "CROSSREF_EMAIL": "x@y.z"}, "me@lab.example"),
        ],
    )
    def test_email_from_the_environment(self, monkeypatch, env, expected):
        import pyeuropepmc.features.enrich.sources.unpaywall_client as module

        fake = MagicMock()
        monkeypatch.setattr(module, "UnpaywallClient", fake)
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        srv._unpaywall_client_cache.get()

        fake.assert_called_once_with(expected)

    def test_an_unusable_email_is_a_tool_error(self, monkeypatch):
        monkeypatch.setenv("UNPAYWALL_EMAIL", "not-an-email")
        with pytest.raises(ToolError, match="not usable"):
            srv._unpaywall_client_cache.get()

    def test_a_failed_construction_is_not_cached(self, monkeypatch):
        with pytest.raises(ToolError):
            srv._unpaywall_client_cache.get()
        monkeypatch.setenv("UNPAYWALL_EMAIL", "me@lab.example")
        assert srv._unpaywall_client_cache.get().email == "me@lab.example"
