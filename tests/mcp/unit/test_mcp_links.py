"""Unit tests for the data-link and lab-link MCP tools and their shaping helpers.

The fixtures under ``tests/fixtures/links`` are real Europe PMC ``datalinks`` and
``labsLinks`` responses: a paper with text-mined SNP accessions, cited DOIs, Altmetric and
BioStudies links, a yeast paper with model-organism database links, and an article without
any link. The client is mocked; nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.mcp import _links as lk, server as srv

FIXTURES = Path(__file__).parents[2] / "fixtures" / "links"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


SNPS = _load("data_MED_32257953.json")
YEAST = _load("data_PMC_PMC3257301.json")
EMPTY = _load("data_MED_25883711_empty.json")
LABS_YEAST = _load("labs_PMC_PMC3257301.json")
LABS_BIOSTUDIES = _load("labs_MED_28166208.json")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_caches():
    for cache in (srv._article_client_cache, srv._client_cache):
        cache.reset()
    yield
    for cache in (srv._article_client_cache, srv._client_cache):
        cache.reset()


def _article_client(data=None, labs=None) -> MagicMock:
    client = MagicMock()
    client.get_data_links.return_value = data if data is not None else {}
    client.get_lab_links.return_value = labs if labs is not None else {}
    srv._article_client_cache.set(client)
    return client


class TestFlattenDataLinks:
    def test_every_link_of_the_real_response_is_flattened(self):
        links = lk.flatten_data_links(SNPS)
        assert len(links) == SNPS["hitCount"] == 20

    def test_a_text_mined_accession(self):
        snp = next(link for link in lk.flatten_data_links(SNPS) if link["id"] == "rs25487")
        assert snp == {
            "category": "SNPs",
            "kind": "supporting_data",
            "relationship": "References",
            "scheme": "dbSNP",
            "id": "rs25487",
            "url": "http://identifiers.org/dbsnp:rs25487",
            "title": None,  # the title was the accession again
            "provider": "Europe PMC",
            "origin": "text_mined",
            "mentions": 8,
        }

    def test_a_provider_link_keeps_its_title_without_markup(self):
        links = lk.flatten_data_links(SNPS)
        biostudies = next(link for link in links if link["category"].startswith("BioStudies"))
        assert biostudies["origin"] == "provider"
        assert biostudies["kind"] == "supporting_data"
        assert biostudies["title"] and "<" not in biostudies["title"]
        assert biostudies["mentions"] is None

    def test_altmetric_is_not_mistaken_for_data(self):
        links = lk.flatten_data_links(YEAST)
        altmetric = [link for link in links if link["category"] == "Altmetric"]
        assert [link["kind"] for link in altmetric] == ["altmetrics"]

    def test_no_links_is_an_empty_list(self):
        assert lk.flatten_data_links(EMPTY) == []
        assert lk.flatten_data_links({}) == []

    @pytest.mark.parametrize(
        "response",
        [
            {"dataLinkList": None},
            {"dataLinkList": {"Category": None}},
            {"dataLinkList": {"Category": [{"Name": "X", "Section": None}]}},
            {"dataLinkList": {"Category": [{"Section": [{"Linklist": {"Link": None}}]}]}},
            {"dataLinkList": {"Category": [{"Section": [{"Linklist": []}]}]}},
        ],
    )
    def test_odd_shapes_do_not_raise(self, response):
        assert lk.flatten_data_links(response) == []

    def test_a_single_object_instead_of_a_list_is_accepted(self):
        link = {"Target": {"Identifier": {"ID": "x", "IDScheme": "S"}}}
        response = {
            "dataLinkList": {
                "Category": {"Name": "C", "Section": {"Linklist": {"Link": link}}},
            }
        }
        [flat] = lk.flatten_data_links(response)
        assert (flat["category"], flat["scheme"], flat["id"]) == ("C", "S", "x")


class TestSelectAndCount:
    def test_category_and_scheme_are_case_insensitive(self):
        links = lk.flatten_data_links(SNPS)
        assert len(lk.select(links, category="snps")) == 17
        assert len(lk.select(links, scheme="DBSNP")) == 17
        assert lk.select(links, category="snps", scheme="doi") == []
        assert lk.select(links) == links

    def test_counts_most_frequent_first(self):
        counts = lk.count_by(lk.flatten_data_links(SNPS), "category")
        assert list(counts)[0] == "SNPs"
        assert counts["SNPs"] == 17
        assert sum(counts.values()) == 20


class TestFlattenLabLinks:
    def test_providers_with_links(self):
        providers = lk.flatten_lab_links(LABS_YEAST)
        assert {p["provider"] for p in providers} == {
            "Saccharomyces Genome Database",
            "Altmetric",
            "GOA Project",
            "Faculty Opinions",
        }
        altmetric = next(p for p in providers if p["provider"] == "Altmetric")
        assert altmetric["provider_id"] == 1562
        assert altmetric["links"][0]["url"].startswith("https://www.altmetric.com/details/")
        assert altmetric["links"][0]["image_url"].endswith(".png")

    def test_filter_by_name_part_or_id(self):
        assert [
            p["provider"] for p in lk.flatten_lab_links(LABS_BIOSTUDIES, provider="biostudies")
        ] == ["BioStudies: supplemental material and supporting data"]
        assert [p["provider"] for p in lk.flatten_lab_links(LABS_YEAST, provider="1562")] == [
            "Altmetric"
        ]
        assert lk.flatten_lab_links(LABS_YEAST, provider="nope") == []

    def test_a_missing_provider_list_is_empty(self):
        assert lk.flatten_lab_links({"hitCount": 0}) == []
        assert lk.flatten_lab_links({"providers": {"provider": None}}) == []


class TestGetPaperDataLinks:
    def test_real_response_with_summary(self):
        client = _article_client(data=SNPS)
        result = _run(srv.get_paper_data_links(pmid="32257953", limit=5))
        client.get_data_links.assert_called_once_with("MED", "32257953")
        assert result["article"] == {"source": "MED", "id": "32257953"}
        assert (result["total"], result["matching"]) == (20, 20)
        assert len(result["links"]) == 5
        assert result["truncated"] is True
        assert result["categories"]["SNPs"] == 17
        assert result["schemes"]["dbSNP"] == 17

    def test_category_filter_applies_before_the_limit(self):
        _article_client(data=SNPS)
        result = _run(srv.get_paper_data_links(pmid="1", category="Data Citations", limit=100))
        assert result["matching"] == 1
        assert result["total"] == 20
        assert result["truncated"] is False
        assert result["links"][0]["scheme"] == "DOI"

    def test_pmcid_uses_the_pmc_source(self):
        client = _article_client(data=YEAST)
        result = _run(srv.get_paper_data_links(pmcid="PMC3257301"))
        client.get_data_links.assert_called_once_with("PMC", "PMC3257301")
        assert result["total"] == 5

    def test_a_paper_without_links_is_a_valid_empty_answer(self):
        _article_client(data=EMPTY)
        result = _run(srv.get_paper_data_links(pmid="25883711"))
        assert (result["total"], result["links"], result["truncated"]) == (0, [], False)

    def test_api_error_becomes_tool_error(self):
        client = MagicMock()
        client.get_data_links.side_effect = APIClientError(ErrorCodes.NET001, {"error": "boom"})
        srv._article_client_cache.set(client)
        with pytest.raises(ToolError):
            _run(srv.get_paper_data_links(pmid="1"))

    @pytest.mark.parametrize("kwargs", [{"pmid": "abc"}, {"pmcid": "xyz"}, {}])
    def test_bad_identifier_never_reaches_the_client(self, kwargs):
        client = _article_client(data=EMPTY)
        with pytest.raises(ToolError):
            _run(srv.get_paper_data_links(**kwargs))
        client.get_data_links.assert_not_called()


class TestGetPaperLabLinks:
    def test_real_response(self):
        client = _article_client(labs=LABS_YEAST)
        result = _run(srv.get_paper_lab_links(pmcid="PMC3257301"))
        client.get_lab_links.assert_called_once_with("PMC", "PMC3257301")
        assert result["link_count"] == 5
        assert len(result["providers"]) == 4
        assert "GOA Project" in result["available_providers"]

    def test_provider_filter_is_applied_locally(self):
        client = _article_client(labs=LABS_YEAST)
        result = _run(srv.get_paper_lab_links(pmcid="PMC3257301", provider="faculty"))
        assert [p["provider"] for p in result["providers"]] == ["Faculty Opinions"]
        assert result["link_count"] == 2
        # all providers stay listed, so an agent can see what else exists
        assert len(result["available_providers"]) == 4
        # the service ignores providerId, so it is not sent
        client.get_lab_links.assert_called_once_with("PMC", "PMC3257301")

    def test_empty_response(self):
        _article_client(labs={"hitCount": 0})
        result = _run(srv.get_paper_lab_links(pmid="25883711"))
        assert (result["link_count"], result["providers"]) == (0, [])


def test_tools_are_read_only_and_listed():
    tools = {t.name: t for t in _run(srv.mcp.list_tools())}
    for name in ("get_paper_data_links", "get_paper_lab_links"):
        assert tools[name].annotations.readOnlyHint is True
        assert tools[name].inputSchema["properties"]["pmid"]
    assert tools["get_paper_data_links"].inputSchema["properties"]["limit"]["maximum"] == 1000
