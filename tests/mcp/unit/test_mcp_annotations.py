"""Unit tests for the text-mined annotation MCP tools and their aggregation helpers.

The fixtures under ``tests/fixtures/annotations`` are real Europe PMC Annotations API
responses (an abstract-only article lookup and an entity search), so the record shapes
the helpers rely on are the API's own. The client is mocked; nothing here touches the
network.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from mcp_wire import schema_of
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.mcp import _annotations as ann, server as srv
from pyeuropepmc.mcp.server import ToolError

FIXTURES = Path(__file__).parents[2] / "fixtures" / "annotations"
BY_ARTICLE = json.loads(
    (FIXTURES / "by_article_abstract_MED_16004729.json").read_text(encoding="utf-8")
)
BY_ENTITY = json.loads((FIXTURES / "by_entity_CHEBI_16236.json").read_text(encoding="utf-8"))


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_caches():
    for cache in (srv._annotations_client_cache, srv._client_cache):
        cache.reset()
    yield
    for cache in (srv._annotations_client_cache, srv._client_cache):
        cache.reset()


def _mention(kind, name, *, uri="", exact="", section="Results (http://x/y)", provider="P", **kw):
    return {
        "type": kind,
        "exact": exact or name,
        "tags": [{"name": name, "uri": uri or f"http://e/{name}"}],
        "section": section,
        "provider": provider,
        **kw,
    }


class TestSectionName:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Abstract (http://purl.org/dc/terms/abstract)", "Abstract"),
            ("Results", "Results"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_strips_the_ontology_uri(self, raw, expected):
        assert ann.section_name(raw) == expected


class TestMatches:
    def test_type_match_ignores_case_and_underscores(self):
        m = _mention("Gene_Proteins", "BRCA1")
        assert ann.matches(m, annotation_type="gene proteins")
        assert ann.matches(m, annotation_type="GENE_PROTEINS")
        assert not ann.matches(m, annotation_type="Diseases")

    def test_section_is_a_case_insensitive_prefix(self):
        m = _mention("Chemicals", "x", section="Materials and Methods (http://x)")
        assert ann.matches(m, section="materials")
        assert not ann.matches(m, section="Results")

    def test_provider(self):
        m = _mention("Chemicals", "x", provider="Europe PMC")
        assert ann.matches(m, provider="europe pmc")
        assert not ann.matches(m, provider="OntoGene")

    def test_no_filter_matches_everything(self):
        assert ann.matches({})


class TestCollect:
    def test_groups_mentions_into_entities_most_mentioned_first(self):
        mentions = [
            _mention("Gene_Proteins", "ALDH1A1", exact="ALDH1A1"),
            _mention("Gene_Proteins", "ALDH1A1", exact="aldh1a1", section="Abstract (x)"),
            _mention("Gene_Proteins", "ALDH2"),
            _mention("Diseases", "cancer"),
        ]
        out = ann.collect(mentions)
        assert out["annotation_count"] == 4
        first = out["entities"][0]
        assert (first["name"], first["mentions"]) == ("ALDH1A1", 2)
        assert first["sections"] == {"Results": 1, "Abstract": 1}
        assert first["examples"] == ["ALDH1A1", "aldh1a1"]
        # ties are ordered by type, then name, so the output is deterministic
        assert [e["name"] for e in out["entities"]] == ["ALDH1A1", "cancer", "ALDH2"]

    def test_same_name_with_different_uri_or_type_stays_separate(self):
        out = ann.collect(
            [
                _mention("Gene_Proteins", "p53", uri="http://a"),
                _mention("Gene_Proteins", "p53", uri="http://b"),
                _mention("Diseases", "p53", uri="http://a"),
            ]
        )
        assert out["entities"][0]["mentions"] == 1
        assert len(out["entities"]) == 3

    def test_frequency_counts_as_that_many_mentions(self):
        out = ann.collect([_mention("Accession Numbers", "X", frequency=4)])
        assert out["annotation_count"] == 4
        assert out["entities"][0]["mentions"] == 4

    def test_untagged_mention_falls_back_to_its_text(self):
        out = ann.collect([{"type": "Resources", "exact": "UniProt", "section": "Results"}])
        assert out["entities"][0]["name"] == "UniProt"

    def test_examples_are_capped_and_shortened(self):
        long = "x" * 300
        out = ann.collect([_mention("Chemicals", "e", exact=f"{i}{long}") for i in range(5)])
        examples = out["entities"][0]["examples"]
        assert len(examples) == 2
        assert all(len(e) <= 120 for e in examples)
        assert examples[0].endswith("…")

    def test_filters_apply_but_available_types_do_not(self):
        out = ann.collect(
            [_mention("Gene_Proteins", "a"), _mention("Diseases", "b")], annotation_type="Diseases"
        )
        assert [e["name"] for e in out["entities"]] == ["b"]
        assert out["available_types"] == {"Gene_Proteins": 1, "Diseases": 1}

    def test_providers_are_collected(self):
        out = ann.collect(
            [_mention("Chemicals", "e", provider="A"), _mention("Chemicals", "e", provider="B")]
        )
        assert out["entities"][0]["providers"] == ["A", "B"]

    def test_on_a_real_response(self):
        out = ann.collect(BY_ARTICLE[0]["annotations"])
        assert out["annotation_count"] == len(BY_ARTICLE[0]["annotations"]) > 10
        assert out["entities"][0]["mentions"] >= out["entities"][-1]["mentions"]
        assert set(out["available_types"]) >= {"Diseases", "Organisms"}
        diseases = ann.collect(BY_ARTICLE[0]["annotations"], annotation_type="diseases")
        assert {e["type"] for e in diseases["entities"]} == {"Diseases"}

    def test_ignores_non_dict_items(self):
        assert ann.collect(["junk", None, 3])["annotation_count"] == 0  # type: ignore[list-item]


class TestSummarizeArticle:
    def test_counts_sections_types_and_examples(self):
        out = ann.summarize_article(
            [
                _mention("Chemicals", "e", section="Abstract (x)", exact="ethanol"),
                _mention("Chemicals", "e", section="Results (x)", exact="EtOH"),
                _mention("Clinical Drug", "e", section="Results (x)", exact="ethanol"),
            ]
        )
        assert out["mentions"] == 3
        assert out["sections"] == {"Results": 2, "Abstract": 1}
        assert out["types"] == {"Chemicals": 2, "Clinical Drug": 1}
        assert out["examples"] == ["ethanol", "EtOH"]

    def test_filter_leaves_zero_mentions(self):
        out = ann.summarize_article([_mention("Chemicals", "e")], annotation_type="Diseases")
        assert out["mentions"] == 0


class TestNextCursor:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(-1.0, None), (-1, None), (None, None), ("x", None), (1.717932057, "1.717932057")],
    )
    def test_cursor(self, raw, expected):
        assert ann.next_cursor(raw) == expected


class TestAnnotationArticleId:
    def test_pmcid_gets_the_source_prefix(self):
        assert _run(srv._annotation_article_id("pmc3525259", "", "")) == "PMC:PMC3525259"
        assert _run(srv._annotation_article_id("3525259", "", "")) == "PMC:PMC3525259"

    def test_pmid(self):
        assert _run(srv._annotation_article_id("", " 16004729 ", "")) == "MED:16004729"

    def test_doi_is_resolved_through_search(self):
        client = MagicMock()
        client.search_all.return_value = [{"source": "MED", "id": "16004729"}]
        srv._client_cache.set(client)
        assert _run(srv._annotation_article_id("", "", "10.1/x")) == "MED:16004729"
        assert client.search_all.call_args.args[0] == 'DOI:"10.1/x"'

    @pytest.mark.parametrize(
        ("record", "expected"),
        [
            ({"id": " 42 "}, "MED:42"),
            ({"source": "PPR", "id": "PPR1"}, "PPR:PPR1"),
            ({"source": "", "id": "7"}, "MED:7"),
        ],
    )
    def test_doi_record_source_defaults_to_med(self, record, expected):
        client = MagicMock()
        client.search_all.return_value = [record]
        srv._client_cache.set(client)
        assert _run(srv._annotation_article_id("", "", "10.1/x")) == expected

    @pytest.mark.parametrize("record", [{}, {"source": "MED"}, {"id": "  "}, {"id": None}])
    def test_doi_record_without_an_id_is_an_error(self, record):
        client = MagicMock()
        client.search_all.return_value = [record]
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="has no id"):
            _run(srv._annotation_article_id("", "", "10.1/x"))

    def test_unknown_doi(self):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        with pytest.raises(ToolError, match="No Europe PMC record"):
            _run(srv._annotation_article_id("", "", "10.1/none"))

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (("nope", "", ""), "pmcid must look like"),
            (("", "12a", ""), "pmid must be digits"),
            (("", "", ""), "One of pmcid, pmid, or doi"),
        ],
    )
    def test_bad_input(self, args, message):
        with pytest.raises(ToolError, match=message):
            _run(srv._annotation_article_id(*args))


def _annotations_client(raw):
    client = MagicMock()
    client.get_annotations_by_article_ids.return_value = {"raw": raw, "valid": True}
    client.get_annotations_by_entity.return_value = {"raw": raw, "valid": True}
    srv._annotations_client_cache.set(client)
    return client


class TestGetPaperAnnotations:
    def test_real_response_becomes_an_entity_list(self):
        client = _annotations_client(BY_ARTICLE)

        result = _run(srv.get_paper_annotations(pmid="16004729"))

        client.get_annotations_by_article_ids.assert_called_once_with(
            ["MED:16004729"], format="JSON"
        )
        assert result["found"] is True
        assert result["article"] == {"id": "MED:16004729", "source": "MED", "pmcid": "PMC3525259"}
        assert result["entity_count"] == len(result["entities"]) > 0
        assert sum(result["by_type"].values()) == result["entity_count"]
        assert result["truncated"] is False
        assert len(json.dumps(result)) < len(json.dumps(BY_ARTICLE))

    def test_limit_truncates_and_says_so(self):
        _annotations_client(BY_ARTICLE)
        result = _run(srv.get_paper_annotations(pmid="16004729", limit=3))
        assert len(result["entities"]) == 3
        assert result["truncated"] is True
        assert result["entity_count"] > 3

    def test_filters(self):
        _annotations_client(BY_ARTICLE)
        result = _run(srv.get_paper_annotations(pmid="16004729", annotation_type="diseases"))
        assert set(result["by_type"]) == {"Diseases"}
        assert "Organisms" in result["available_types"]

    def test_no_match_still_lists_what_exists(self):
        _annotations_client(BY_ARTICLE)
        result = _run(srv.get_paper_annotations(pmid="16004729", annotation_type="Nonsense"))
        assert result["entities"] == []
        assert result["found"] is True
        assert result["available_types"]

    def test_unknown_article(self):
        _annotations_client([])
        result = _run(srv.get_paper_annotations(pmid="99999999999"))
        assert result["found"] is False
        assert result["entities"] == []

    def test_api_error_becomes_tool_error(self):
        client = MagicMock()
        client.get_annotations_by_article_ids.side_effect = APIClientError(
            ErrorCodes.NET001, {"error": "boom"}
        )
        srv._annotations_client_cache.set(client)
        with pytest.raises(ToolError):
            _run(srv.get_paper_annotations(pmid="1"))

    def test_bad_identifier_never_reaches_the_client(self):
        client = _annotations_client([])
        with pytest.raises(ToolError):
            _run(srv.get_paper_annotations(pmid="abc"))
        client.get_annotations_by_article_ids.assert_not_called()


class TestFindPapersByEntity:
    def test_real_response_becomes_article_summaries(self):
        client = _annotations_client(BY_ENTITY)

        result = _run(srv.find_papers_by_entity(entity=" CHEBI:16236 ", limit=3))

        client.get_annotations_by_entity.assert_called_once_with(
            "CHEBI:16236", page_size=3, format="JSON", cursor_mark=None
        )
        assert result["entity"] == "CHEBI:16236"
        assert result["article_count"] == len(BY_ENTITY["articles"]) == 3
        first = result["articles"][0]
        assert first["id"] == "32387679"
        assert first["pmcid"] == "PMC7306473"
        assert first["mentions"] >= 4
        assert first["sections"] == {"Supplementary material": 4}
        assert result["next_cursor"] == "1.717932057"

    def test_last_page_has_no_cursor(self):
        _annotations_client({"nextCursorMark": -1.0, "articles": []})
        assert _run(srv.find_papers_by_entity(entity="x"))["next_cursor"] is None

    def test_cursor_is_passed_on(self):
        client = _annotations_client({"nextCursorMark": -1.0, "articles": []})
        _run(srv.find_papers_by_entity(entity="x", cursor="497.7"))
        assert client.get_annotations_by_entity.call_args.kwargs["cursor_mark"] == "497.7"

    def test_filters_apply_to_mentions_and_count_dropped_articles(self):
        _annotations_client(BY_ENTITY)
        result = _run(srv.find_papers_by_entity(entity="CHEBI:16236", annotation_type="Diseases"))
        assert result["article_count"] == 0
        assert result["articles_filtered_out"] == 3

    def test_empty_entity(self):
        client = _annotations_client({})
        with pytest.raises(ToolError, match="must not be empty"):
            _run(srv.find_papers_by_entity(entity="  "))
        client.get_annotations_by_entity.assert_not_called()

    def test_limit_is_bounded_by_the_apis_page_size(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        assert schema_of(tools["find_papers_by_entity"])["properties"]["limit"]["maximum"] == 8

    def test_api_error_becomes_tool_error(self):
        client = MagicMock()
        client.get_annotations_by_entity.side_effect = APIClientError(
            ErrorCodes.NET001, {"error": "boom"}
        )
        srv._annotations_client_cache.set(client)
        with pytest.raises(ToolError):
            _run(srv.find_papers_by_entity(entity="x"))
