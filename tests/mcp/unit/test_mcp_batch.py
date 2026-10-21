"""Unit tests for the batch lookup tools and their helpers (hermetic).

Europe PMC answers an OR query with unordered records and omits unknown identifiers, so most
of what matters here is bookkeeping: every input gets a result in its own position with an
honest status. The client and the XML download are mocked; nothing touches the network.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from mcp_wire import schema_of
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.mcp import _batch as bm, server as srv
from pyeuropepmc.mcp.server import ToolError

JATS = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article"><front>
<article-meta><article-id pub-id-type="pmcid">PMC{n}</article-id>
<title-group><article-title>Paper {n}</article-title></title-group>
<abstract><p>Abstract {n}.</p></abstract></article-meta></front>
<body>
<sec id="s1"><title>Introduction</title><p>{intro}</p></sec>
<sec id="s2"><title>Results</title><p>{results}</p></sec>
</body><back><ref-list><ref id="B1"><mixed-citation>Ref</mixed-citation></ref></ref-list></back></article>"""


def jats(n, intro="Intro text.", results="Result text."):
    return JATS.format(n=n, intro=intro, results=results)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_caches():
    for cache in (srv._client_cache, srv._fulltext_xml_cache):
        cache.reset()
    yield
    for cache in (srv._client_cache, srv._fulltext_xml_cache):
        cache.reset()


def rec(pmid=None, pmcid=None, doi=None, *, source="MED", oa="Y", **extra):
    out = {"id": pmid or pmcid or doi, "source": source, "isOpenAccess": oa, **extra}
    if pmid:
        out["pmid"] = pmid
    if pmcid:
        out["pmcid"] = pmcid
    if doi:
        out["doi"] = doi
    return out


class TestClassify:
    @pytest.mark.parametrize(
        ("raw", "kind", "value"),
        [
            ("16004729", "pmid", "16004729"),
            (" 16004729 ", "pmid", "16004729"),
            ("PMC3525259", "pmcid", "PMC3525259"),
            ("pmc3525259", "pmcid", "PMC3525259"),
            ("10.1038/s41579-019-0296-0", "doi", "10.1038/s41579-019-0296-0"),
            ("doi:10.1038/X", "doi", "10.1038/X"),
            ("https://doi.org/10.1038/x", "doi", "10.1038/x"),
        ],
    )
    def test_valid(self, raw, kind, value):
        entry = bm.classify(raw)
        assert (entry.kind, entry.value, entry.raw) == (kind, value, raw)

    @pytest.mark.parametrize(
        "raw", ["", "  ", "abc", "10.12/x", "1234567890123", 'doi:10.1234/a"b', "PMC", "12a"]
    )
    def test_invalid(self, raw):
        entry = bm.classify(raw)
        assert entry.kind == "invalid"
        assert entry.value == ""
        assert entry.problem


class TestQuery:
    def test_clauses_by_kind(self):
        entries = [bm.classify(x) for x in ("123", "pmc9", "10.1234/Ab")]
        assert bm.build_query(entries) == (
            '(EXT_ID:123 AND SRC:MED) OR PMCID:PMC9 OR DOI:"10.1234/Ab"'
        )

    def test_duplicates_and_invalid_entries_are_left_out_in_first_seen_order(self):
        entries = [bm.classify(x) for x in ("2", "bad", "1", "2", "10.1234/A", "10.1234/a")]
        assert bm.build_query(entries) == (
            '(EXT_ID:2 AND SRC:MED) OR (EXT_ID:1 AND SRC:MED) OR DOI:"10.1234/A"'
        )

    def test_chunking(self):
        entries = [bm.classify(str(i)) for i in range(1, 121)]
        sizes = [len(c) for c in bm.chunks(entries)]
        assert sizes == [50, 50, 20]

    def test_chunks_skip_duplicates(self):
        entries = [bm.classify(x) for x in ("1", "1", "2", "x")]
        assert [len(c) for c in bm.chunks(entries, size=10)] == [2]


class TestIndexAndLookup:
    def test_each_identifier_finds_the_record(self):
        record = rec("1", "PMC9", "10.1234/AbC")
        index = bm.index_records([record])
        for raw in ("1", "pmc9", "PMC9", "10.1234/abc", "https://doi.org/10.1234/ABC"):
            assert bm.lookup(index, bm.classify(raw)) is record

    def test_missing_and_invalid(self):
        index = bm.index_records([rec("1")])
        assert bm.lookup(index, bm.classify("2")) is None
        assert bm.lookup(index, bm.classify("bad")) is None

    def test_published_version_beats_a_preprint_with_the_same_doi(self):
        preprint = rec(doi="10.1234/x", source="PPR")
        published = rec("5", doi="10.1234/x", source="MED")
        for order in ([preprint, published], [published, preprint]):
            index = bm.index_records(order)
            assert bm.lookup(index, bm.classify("10.1234/x")) is published


class TestProject:
    LITE = {
        "id": "1",
        "source": "MED",
        "pmid": "1",
        "authorString": "A B, C D.",
        "journalTitle": "J Test",
        "pubYear": "2005",
        "citedByCount": 310,
        "isOpenAccess": "Y",
        "pubType": "research-article; journal article",
        "title": "T",
    }
    CORE = {
        "id": "1",
        "source": "MED",
        "journalInfo": {"journal": {"title": "J Core"}},
        "pubTypeList": {"pubType": ["research-article", "Journal Article"]},
        "abstractText": "An abstract.",
        "isOpenAccess": "N",
        "citedByCount": "0",
        "pubYear": "bad",
    }

    def test_lite_record(self):
        out = bm.project(self.LITE, bm.DEFAULT_FIELDS)
        assert out["authors"] == "A B, C D."
        assert out["journal"] == "J Test"
        assert out["year"] == 2005
        assert out["cited_by"] == 310
        assert out["is_open_access"] is True
        assert out["pmcid"] is None
        assert out["doi"] is None

    def test_core_record(self):
        out = bm.project(self.CORE, ["journal", "pub_types", "abstract", "is_open_access", "year"])
        assert out == {
            "journal": "J Core",
            "pub_types": ["research-article", "Journal Article"],
            "abstract": "An abstract.",
            "is_open_access": False,
            "year": None,
        }

    def test_pub_types_from_the_lite_string(self):
        assert bm.project(self.LITE, ["pub_types"])["pub_types"] == [
            "research-article",
            "journal article",
        ]

    def test_only_the_requested_fields_in_the_requested_order(self):
        assert list(bm.project(self.LITE, ["year", "title"])) == ["year", "title"]


class TestValidateFields:
    def test_default(self):
        assert bm.validate_fields(None) == bm.DEFAULT_FIELDS
        assert bm.validate_fields([]) == bm.DEFAULT_FIELDS

    def test_duplicates_are_dropped(self):
        assert bm.validate_fields(["title", "year", "title"]) == ("title", "year")

    def test_unknown_fields_are_listed(self):
        with pytest.raises(ValueError, match=r"unknown field\(s\) \['nope'\].*valid fields"):
            bm.validate_fields(["title", "nope"])


def _client(records):
    client = MagicMock()
    client.search_all.return_value = records
    srv._client_cache.set(client)
    return client


class TestGetPapersBatch:
    def test_one_query_and_a_result_per_input_in_order(self):
        client = _client(
            [
                rec("3", "PMC3", "10.1234/c", title="C", pubYear="2003"),
                rec("1", None, "10.1234/a", title="A", pubYear="2001"),
            ]
        )

        out = _run(srv.get_papers_batch(ids=["1", "pmc3", "999", "junk", "10.1234/A", "1"]))

        client.search_all.assert_called_once()
        assert client.search_all.call_args.args[0] == (
            '(EXT_ID:1 AND SRC:MED) OR PMCID:PMC3 OR (EXT_ID:999 AND SRC:MED) OR DOI:"10.1234/A"'
        )
        assert client.search_all.call_args.kwargs["resultType"] == "lite"
        assert [r["id"] for r in out["results"]] == ["1", "pmc3", "999", "junk", "10.1234/A", "1"]
        assert [r["status"] for r in out["results"]] == [
            "ok",
            "ok",
            "not_found",
            "invalid",
            "ok",
            "ok",
        ]
        assert out["results"][0]["record"]["title"] == "A"
        assert out["results"][1]["record"]["title"] == "C"
        assert out["results"][1]["record"]["year"] == 2003
        assert out["results"][3]["error"]
        assert out["results"][2]["record"] is None
        assert out["results"][5]["record"] == out["results"][0]["record"]
        assert out["by_status"] == {"ok": 4, "not_found": 1, "invalid": 1}
        assert out["requested"] == 6
        assert out["distinct"] == 4

    def test_nothing_valid_makes_no_request(self):
        client = _client([])
        out = _run(srv.get_papers_batch(ids=["junk", "x y"]))
        client.search_all.assert_not_called()
        assert out["by_status"] == {"invalid": 2}

    def test_abstract_switches_to_core(self):
        client = _client([rec("1", abstractText="An abstract.")])
        out = _run(srv.get_papers_batch(ids=["1"], fields=["title", "abstract"]))
        assert client.search_all.call_args.kwargs["resultType"] == "core"
        assert out["results"][0]["record"]["abstract"] == "An abstract."

    def test_unknown_field_is_a_tool_error_before_any_request(self):
        client = _client([])
        with pytest.raises(ToolError, match="unknown field"):
            _run(srv.get_papers_batch(ids=["1"], fields=["bogus"]))
        client.search_all.assert_not_called()

    def test_large_batches_are_split_into_chunks(self):
        client = _client([])
        _run(srv.get_papers_batch(ids=[str(i) for i in range(1, 61)]))
        assert client.search_all.call_count == 2
        sizes = [c.args[0].count(" OR ") + 1 for c in client.search_all.call_args_list]
        assert sizes == [50, 10]

    def test_a_failing_chunk_only_fails_its_own_identifiers(self):
        client = MagicMock()
        client.search_all.side_effect = [
            APIClientError(ErrorCodes.NET001, {"error": "boom"}),
            [rec("51", title="ok")],
        ]
        srv._client_cache.set(client)

        out = _run(srv.get_papers_batch(ids=[str(i) for i in range(1, 52)]))

        statuses = [r["status"] for r in out["results"]]
        assert statuses[:50] == ["error"] * 50
        assert statuses[50] == "ok"
        assert out["results"][0]["error"]

    def test_the_id_list_bounds_are_in_the_schema(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        ids = schema_of(tools["get_papers_batch"])["properties"]["ids"]
        assert (ids["minItems"], ids["maxItems"]) == (1, 100)
        ids = schema_of(tools["get_papers_fulltext_batch"])["properties"]["ids"]
        assert (ids["minItems"], ids["maxItems"]) == (1, 20)


@pytest.fixture
def xml(monkeypatch):
    """Replace the XML download; record which PMCIDs were fetched."""
    fetched: list[str] = []
    documents: dict[str, str | Exception] = {}

    async def fake(pmcid):
        fetched.append(pmcid)
        doc = documents.get(pmcid) or jats(pmcid.removeprefix("PMC"))
        if isinstance(doc, Exception):
            raise doc
        return doc

    monkeypatch.setattr(srv, "_fulltext_xml", fake)
    fake.fetched = fetched  # type: ignore[attr-defined]
    fake.documents = documents  # type: ignore[attr-defined]
    return fake


class TestGetPapersFulltextBatch:
    def test_every_status(self, xml):
        _client(
            [
                rec("1", "PMC1", "10.1234/one"),
                rec("2", "PMC2", oa="N"),
                rec("3", None),
            ]
        )

        out = _run(
            srv.get_papers_fulltext_batch(ids=["PMC1", "2", "3", "99", "junk", "10.1234/one", "1"])
        )

        statuses = {r["id"]: r["status"] for r in out["results"]}
        assert statuses == {
            "PMC1": "ok",
            "2": "not_open_access",
            "3": "not_in_pmc",
            "99": "not_found",
            "junk": "invalid",
            "10.1234/one": "duplicate",
            "1": "duplicate",
        }
        assert out["results"][5]["duplicate_of"] == 0
        assert out["by_status"]["ok"] == 1
        # only the open-access paper was downloaded, once
        assert xml.fetched == ["PMC1"]
        first = out["results"][0]
        assert first["title"] == "Paper 1"
        assert "Intro text." in first["content"]
        assert first["truncated"] is False
        assert first["returned_chars"] == len(first["content"]) + 2

    def test_sections_filter_and_no_matching_section(self, xml):
        _client([rec("1", "PMC1"), rec("2", "PMC2")])
        out = _run(srv.get_papers_fulltext_batch(ids=["PMC1", "PMC2"], sections=["results"]))
        for item in out["results"]:
            assert item["content"].startswith("## Results")
            assert "Intro text." not in item["content"]

        out = _run(srv.get_papers_fulltext_batch(ids=["PMC1"], sections=["nothing"]))
        item = out["results"][0]
        assert item["status"] == "no_matching_section"
        assert "Introduction" in item["sections_available"]
        assert "content" not in item

    def test_per_paper_cap_cuts_and_reports(self, xml):
        _client([rec("1", "PMC1")])
        xml.documents["PMC1"] = jats(1, results="word " * 1000)
        out = _run(
            srv.get_papers_fulltext_batch(
                ids=["PMC1"], sections=["results"], max_chars_per_paper=1000
            )
        )
        item = out["results"][0]
        assert item["truncated"] is True
        assert item["total_chars"] > 4000
        assert 800 < item["returned_chars"] <= 1000
        # the heading is not all that is left
        assert "word word" in item["content"]

    def test_the_total_budget_is_shared_in_order_and_stops_downloads(self, xml):
        ids = [f"PMC{i}" for i in range(1, 9)]
        _client([rec(str(i), f"PMC{i}") for i in range(1, 9)])
        for i in range(1, 9):
            xml.documents[f"PMC{i}"] = jats(i, results="word " * 800)

        out = _run(
            srv.get_papers_fulltext_batch(
                ids=ids, sections=["results"], max_chars_per_paper=1000, max_total_chars=2500
            )
        )

        statuses = [r["status"] for r in out["results"]]
        assert statuses[:3] == ["ok", "ok", "ok"]
        assert out["budget_exhausted"] is True
        assert out["total_chars_returned"] <= 2500
        assert out["total_chars_returned"] == sum(
            r.get("returned_chars", 0) for r in out["results"]
        )
        # later papers were not served, and the second window was never downloaded
        assert "skipped_budget" in statuses[4:]
        assert len(xml.fetched) <= 4
        assert out["by_status"]["skipped_budget"] == statuses.count("skipped_budget")

    def test_a_failed_download_only_fails_that_paper(self, xml):
        _client([rec("1", "PMC1"), rec("2", "PMC2")])
        xml.documents["PMC1"] = ToolError("Europe PMC could not serve PMC1 (HTTP 500)")
        out = _run(srv.get_papers_fulltext_batch(ids=["PMC1", "PMC2"]))
        assert [r["status"] for r in out["results"]] == ["error", "ok"]
        assert "HTTP 500" in out["results"][0]["error"]

    def test_a_failing_lookup_marks_the_papers_as_errors(self, xml):
        client = MagicMock()
        client.search_all.side_effect = APIClientError(ErrorCodes.NET001, {"error": "boom"})
        srv._client_cache.set(client)
        out = _run(srv.get_papers_fulltext_batch(ids=["PMC1", "junk"]))
        assert [r["status"] for r in out["results"]] == ["error", "invalid"]
        assert xml.fetched == []

    def test_the_lookup_is_one_request(self, xml):
        client = _client([rec("1", "PMC1"), rec("2", "PMC2")])
        _run(srv.get_papers_fulltext_batch(ids=["PMC1", "PMC2", "3"]))
        assert client.search_all.call_count == 1

    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "FULLTEXT_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.get_papers_fulltext_batch(ids=["PMC1"]))
