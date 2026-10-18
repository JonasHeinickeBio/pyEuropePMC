"""Unit tests for the full-text MCP tool and its shaping helpers (hermetic).

The handler tests run the real ``FullTextXMLParser`` on a small JATS document, so the
block shapes the helpers rely on are the parser's own, not hand-written guesses. Only
the two network steps (``_locate_fulltext`` / ``_fulltext_xml``) are replaced.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import FullTextError
from pyeuropepmc.mcp import _fulltext as ft, server as srv

JATS = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article"><front>
<journal-meta><journal-title-group><journal-title>Test Journal</journal-title>
</journal-title-group></journal-meta>
<article-meta><article-id pub-id-type="pmid">123</article-id>
<article-id pub-id-type="pmcid">PMC42</article-id><article-id pub-id-type="doi">10.1/test</article-id>
<title-group><article-title>A test article</article-title></title-group>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/">
<license-p><ext-link ext-link-type="uri" xlink:href="https://creativecommons.org/licenses/by/4.0/">CC BY</ext-link></license-p></license></permissions>
<abstract><p>Short abstract.</p></abstract></article-meta></front>
<body>
<sec id="s1"><title>Introduction</title><p>Intro text.</p></sec>
<sec id="s2"><title>Methods</title><p>Method text.</p>
<sec id="s2a"><title>Sampling</title><p>Sampling text with a | pipe.</p></sec></sec>
<sec id="s3"><title>Results</title><p>Result text.</p>
<fig id="F1"><label>Figure 1</label><caption><p>A figure.</p></caption><graphic xlink:href="f1"/></fig>
<table-wrap id="T1"><label>Table 1</label><caption><p>A table.</p></caption>
<table><thead><tr><th>Gene</th><th>Locus</th></tr></thead>
<tbody><tr><td>ALDH1</td><td>9q21</td></tr></tbody></table></table-wrap></sec>
</body><back><ref-list><ref id="B1"><mixed-citation>Ref one</mixed-citation></ref></ref-list>
</back></article>"""


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_caches():
    for cache in (srv._client_cache, srv._fulltext_client_cache, srv._fulltext_xml_cache):
        cache.reset()
    yield
    for cache in (srv._client_cache, srv._fulltext_client_cache, srv._fulltext_xml_cache):
        cache.reset()


@pytest.fixture
def paper(monkeypatch):
    """Replace the two network steps so the tool runs on the JATS above."""

    async def locate(pmcid="", pmid="", doi=""):
        return "PMC42", {"pmcid": "PMC42", "pmid": "123", "doi": "10.1/test", "title": "T"}

    async def xml(pmcid):
        return JATS

    monkeypatch.setattr(srv, "_locate_fulltext", locate)
    monkeypatch.setattr(srv, "_fulltext_xml", xml)


@pytest.fixture(scope="module")
def sections():
    from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

    return FullTextXMLParser(JATS).get_full_text_sections_structured()


class TestXmlCache:
    def test_get_set_and_miss(self):
        cache = ft.XmlCache()
        assert cache.get("PMC1") is None
        cache.set("PMC1", "<a/>")
        assert cache.get("PMC1") == "<a/>"

    def test_evicts_least_recently_used(self):
        cache = ft.XmlCache(maxsize=2)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.get("a")  # a is now the most recent
        cache.set("c", "3")
        assert cache.get("b") is None
        assert cache.get("a") == "1"
        assert cache.get("c") == "3"

    def test_reset_empties(self):
        cache = ft.XmlCache()
        cache.set("a", "1")
        cache.reset()
        assert cache.get("a") is None


class TestSelectSections:
    def test_drops_the_title_only_section(self, sections):
        titles = [s["title"] for s in ft.select_sections(sections)]
        assert "Article Title" not in titles
        assert titles[0] == "Abstract"

    def test_filter_is_case_insensitive_substring(self, sections):
        assert [s["title"] for s in ft.select_sections(sections, ["RESULT"])] == ["Results"]

    def test_parent_filter_keeps_its_subsections(self, sections):
        titles = [s["title"] for s in ft.select_sections(sections, ["methods"])]
        assert titles == ["Methods", "Sampling"]

    def test_blank_filters_are_ignored(self, sections):
        assert len(ft.select_sections(sections, ["", "  "])) == len(ft.select_sections(sections))

    def test_section_titles(self, sections):
        assert ft.section_titles(sections)[:3] == ["Abstract", "Introduction", "Methods"]


class TestSlimBlock:
    def test_drops_repeated_bookkeeping(self):
        block = {
            "type": "paragraph",
            "schema_version": "0.2.0",
            "text": "x",
            "inlines": [{"a": 1}],
        }
        assert ft.slim_block(block) == {"type": "paragraph", "text": "x"}

    def test_table_keeps_only_rows_and_caption(self):
        block = {
            "type": "table",
            "text": "flattened copy",
            "inlines": [],
            "metadata": {"spans": []},
            "label": "Table 1",
            "caption": "c",
            "rows": [["a"]],
        }
        assert ft.slim_block(block) == {
            "type": "table",
            "label": "Table 1",
            "caption": "c",
            "rows": [["a"]],
        }


class TestMarkdown:
    def test_heading_level_follows_nesting(self, sections):
        md = ft.units_to_markdown(
            ft.render_units(ft.select_sections(sections, ["methods"]), "markdown")
        )
        assert "## Methods" in md
        assert "### Sampling" in md

    def test_table_is_a_markdown_table_with_escaped_pipes(self):
        md = ft.block_to_markdown(
            {"type": "table", "label": "T1", "caption": "c", "rows": [["a", "b|c"], ["1"]]}
        )
        assert md.splitlines() == ["**T1 c**", "| a | b\\|c |", "| --- | --- |", "| 1 |  |"]

    def test_figure_and_list_and_unknown_block(self):
        assert (
            ft.block_to_markdown({"type": "figure", "label": "Fig 1", "caption": "c"})
            == "*Fig 1: c*"
        )
        assert ft.block_to_markdown({"type": "list", "items": ["a", {"text": "b"}]}) == "- a\n- b"
        assert ft.block_to_markdown({"type": "code", "text": "x"}) == "x"
        assert ft.block_to_markdown({"type": "formula"}) == ""


class TestTakeWithin:
    UNITS = [(0, None, "## A"), (0, 0, "x" * 10), (0, 1, "y" * 10)]

    def test_everything_fits(self):
        kept, total, truncated = ft.take_within(self.UNITS, 1000)
        assert kept == self.UNITS
        assert total == sum(len(u[2]) + 2 for u in self.UNITS)
        assert truncated is False

    def test_cuts_at_a_unit_boundary(self):
        kept, _total, truncated = ft.take_within(self.UNITS, 20)
        assert kept == self.UNITS[:2]
        assert truncated is True

    def test_first_unit_is_cut_not_dropped(self):
        kept, _total, truncated = ft.take_within([(0, 0, "z" * 100)], 10)
        assert len(kept) == 1
        assert len(kept[0][2]) == 8
        assert truncated is True

    def test_empty(self):
        assert ft.take_within([], 10) == ([], 0, False)


class TestShrinkBlockJson:
    def _table(self, rows=200):
        block = {
            "type": "table",
            "label": "T1",
            "caption": "c",
            "rows": [[f"gene{i}", "locus"] for i in range(rows)],
        }
        return ft.json.dumps(block, separators=(",", ":"))

    def test_fitting_block_is_unchanged(self):
        text = self._table(2)
        assert ft.shrink_block_json(text, len(text)) == text

    def test_table_loses_trailing_rows_and_stays_valid_json(self):
        text = self._table()
        out = ft.shrink_block_json(text, 500)
        block = ft.json.loads(out)
        assert len(out) <= 500
        assert 0 < len(block["rows"]) < 200
        assert block["rows"][0] == ["gene0", "locus"]
        assert block["truncated_rows"] == 200 - len(block["rows"])

    def test_text_block_is_cut_and_marked(self):
        text = ft.json.dumps(
            {"type": "paragraph", "text": 'say "hi"\n' * 400}, separators=(",", ":")
        )
        out = ft.shrink_block_json(text, 300)
        block = ft.json.loads(out)
        assert len(out) <= 300
        assert block["truncated"] is True
        assert block["text"].startswith("say")

    def test_list_loses_items(self):
        text = ft.json.dumps({"type": "list", "items": ["x" * 50] * 20}, separators=(",", ":"))
        block = ft.json.loads(ft.shrink_block_json(text, 200))
        assert block["truncated"] is True
        assert 0 <= len(block["items"]) < 20

    def test_impossible_budget_returns_none(self):
        assert ft.shrink_block_json(self._table(), 10) is None
        assert ft.shrink_block_json('{"type":"figure","uri":"a"}' + " " * 0, 5) is None


class TestTakeWithinFitFirst:
    def test_oversized_json_unit_is_shrunk_not_cut(self):
        text = ft.json.dumps({"type": "table", "rows": [["a", "b"]] * 100}, separators=(",", ":"))
        kept, total, truncated = ft.take_within(
            [(0, 0, text)], 200, fit_first=ft.shrink_block_json
        )
        assert truncated is True
        assert total == len(text) + 2
        assert len(kept[0][2]) + 2 <= 200
        ft.json.loads(kept[0][2])

    def test_unshrinkable_unit_is_left_out(self):
        kept, _total, truncated = ft.take_within(
            [(0, 0, '{"type":"figure","uri":"abc"}')], 5, fit_first=ft.shrink_block_json
        )
        assert kept == []
        assert truncated is True


class TestOutline:
    def test_counts_blocks_and_chars(self, sections):
        outline = {o["title"]: o for o in ft.outline(ft.select_sections(sections))}
        assert outline["Results"]["blocks"] == {"paragraph": 1, "figure": 1, "table": 1}
        assert outline["Introduction"]["chars"] == len("Intro text.")


class TestGetPaperFulltext:
    def test_markdown_by_default_with_metadata(self, paper):
        result = _run(srv.get_paper_fulltext(pmcid="PMC42"))
        assert result["pmcid"] == "PMC42"
        assert result["title"] == "A test article"
        assert result["journal"] == "Test Journal"
        assert result["license"] == "https://creativecommons.org/licenses/by/4.0/"
        assert result["format"] == "markdown"
        assert result["sections_available"] == [
            "Abstract",
            "Introduction",
            "Methods",
            "Sampling",
            "Results",
            "References",
        ]
        assert "Intro text." in result["content"]
        assert "| Gene | Locus |" in result["content"]
        assert result["truncated"] is False
        assert result["reference_count"] == 1
        assert "references" not in result

    def test_section_filter(self, paper):
        result = _run(srv.get_paper_fulltext(pmcid="PMC42", sections=["methods"]))
        assert "Method text." in result["content"]
        assert "Intro text." not in result["content"]
        assert result["sections_available"][0] == "Abstract"  # navigation is never filtered

    def test_sections_format_is_slim_and_typed(self, paper):
        result = _run(
            srv.get_paper_fulltext(pmcid="PMC42", format="sections", sections=["results"])
        )
        blocks = result["content"][0]["content"]
        assert [b["type"] for b in blocks] == ["paragraph", "figure", "table"]
        assert all("schema_version" not in b and "inlines" not in b for b in blocks)
        assert blocks[2]["rows"][0] == ["Gene", "Locus"]
        assert set(blocks[2]) == {"type", "label", "caption", "rows"}

    def test_outline_format(self, paper):
        result = _run(srv.get_paper_fulltext(pmcid="PMC42", format="outline"))
        assert {o["title"] for o in result["content"]} >= {"Introduction", "Results"}
        assert result["truncated"] is False

    def test_truncation_is_reported(self, paper):
        result = _run(srv.get_paper_fulltext(pmcid="PMC42", max_chars=1000))
        assert result["truncated"] is False  # the whole fixture is shorter than 1000
        full = result["total_chars"]
        assert result["returned_chars"] <= full

    def test_truncation_cuts_content(self, paper, monkeypatch):
        long_xml = JATS.replace("Intro text.", "word " * 600)

        async def xml(pmcid):
            return long_xml

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        result = _run(srv.get_paper_fulltext(pmcid="PMC42", max_chars=1000))
        assert result["truncated"] is True
        assert result["total_chars"] > 3000
        assert len(result["content"]) <= 1000

    def test_sections_format_respects_max_chars_for_an_oversized_first_block(
        self, paper, monkeypatch
    ):
        rows = "".join(f"<tr><td>gene{i}</td><td>locus</td></tr>" for i in range(400))
        big = JATS.replace(
            "<tbody><tr><td>ALDH1</td><td>9q21</td></tr></tbody>", f"<tbody>{rows}</tbody>"
        )

        async def xml(pmcid):
            return big

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        result = _run(
            srv.get_paper_fulltext(
                pmcid="PMC42", format="sections", sections=["results"], max_chars=1000
            )
        )
        import json

        counted = sum(
            len(json.dumps(b, separators=(",", ":"))) + 2
            for s in result["content"]
            for b in s["content"]
        )
        assert result["truncated"] is True
        assert result["returned_chars"] == counted
        assert counted <= 1000
        tables = [b for s in result["content"] for b in s["content"] if b["type"] == "table"]
        assert all("truncated_rows" in t for t in tables)

    def test_references_are_opt_in(self, paper):
        result = _run(srv.get_paper_fulltext(pmcid="PMC42", include_references=True))
        assert len(result["references"]) == result["reference_count"] == 1

    def test_unmatched_section_lists_the_available_ones(self, paper):
        with pytest.raises(ToolError, match="Available sections.*Methods"):
            _run(srv.get_paper_fulltext(pmcid="PMC42", sections=["nope"]))

    def test_unavailable(self, monkeypatch):
        monkeypatch.setattr(srv, "FULLTEXT_AVAILABLE", False)
        with pytest.raises(ToolError, match="not available"):
            _run(srv.get_paper_fulltext(pmcid="PMC42"))

    @pytest.mark.parametrize("size", [999, 500001])
    def test_max_chars_bounds_are_in_the_schema(self, size):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        schema = tools["get_paper_fulltext"].inputSchema["properties"]["max_chars"]
        assert schema["minimum"] == 1000
        assert schema["maximum"] == 500000
        assert not (schema["minimum"] <= size <= schema["maximum"])


def _client_returning(records):
    client = MagicMock()
    client.search_all.return_value = records
    srv._client_cache.set(client)
    return client


class TestLocateFulltext:
    OA = {"pmcid": "PMC42", "isOpenAccess": "Y", "pmid": "123"}

    def test_pmcid_query_and_result(self):
        client = _client_returning([self.OA])
        resolved, record = _run(srv._locate_fulltext(pmcid="pmc42"))
        assert resolved == "PMC42"
        assert record["pmid"] == "123"
        client.search_all.assert_called_once_with(
            "PMCID:PMC42", page_size=1, max_results=1, resultType="lite"
        )

    def test_bare_digits_are_a_pmcid(self):
        client = _client_returning([self.OA])
        _run(srv._locate_fulltext(pmcid="42"))
        assert client.search_all.call_args.args[0] == "PMCID:PMC42"

    def test_pmid_and_doi_queries(self):
        client = _client_returning([self.OA])
        _run(srv._locate_fulltext(pmid="123"))
        assert client.search_all.call_args.args[0] == "EXT_ID:123 AND SRC:MED"
        _run(srv._locate_fulltext(doi="10.1/test"))
        assert client.search_all.call_args.args[0] == 'DOI:"10.1/test"'

    def test_pmcid_wins_over_other_ids(self):
        client = _client_returning([self.OA])
        _run(srv._locate_fulltext(pmcid="PMC42", pmid="9", doi="10.1/x"))
        assert client.search_all.call_args.args[0] == "PMCID:PMC42"

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({}, "One of pmcid, pmid, or doi"),
            ({"pmcid": "not-an-id"}, "pmcid must look like"),
            ({"pmid": "12a"}, "pmid must be digits"),
        ],
    )
    def test_bad_identifiers_never_reach_the_client(self, kwargs, message):
        client = _client_returning([])
        with pytest.raises(ToolError, match=message):
            _run(srv._locate_fulltext(**kwargs))
        client.search_all.assert_not_called()

    def test_unknown_record(self):
        _client_returning([])
        with pytest.raises(ToolError, match="No Europe PMC record"):
            _run(srv._locate_fulltext(pmcid="PMC1"))

    def test_record_without_pmcid(self):
        _client_returning([{"pmid": "1", "isOpenAccess": "N"}])
        with pytest.raises(ToolError, match="not in PubMed Central"):
            _run(srv._locate_fulltext(pmid="1"))

    def test_not_open_access_fails_fast_with_the_reason(self):
        _client_returning([{"pmcid": "PMC9", "isOpenAccess": "N"}])
        with pytest.raises(ToolError, match="PMC9 is not Open Access"):
            _run(srv._locate_fulltext(pmcid="PMC9"))


def _full_text_error(code, status=None):
    context = {"status_code": status} if status is not None else None
    return FullTextError(code, context=context, pmcid="42", format_type="xml")


class TestFulltextXml:
    def test_fetches_once_then_serves_from_cache(self):
        client = MagicMock()
        client.get_fulltext_content.return_value = "<article/>"
        srv._fulltext_client_cache.set(client)

        assert _run(srv._fulltext_xml("PMC42")) == "<article/>"
        assert _run(srv._fulltext_xml("PMC42")) == "<article/>"

        client.get_fulltext_content.assert_called_once_with("PMC42", "xml")

    @pytest.mark.parametrize(
        ("code", "status", "message"),
        [
            (ErrorCodes.FULL003, None, "no full-text XML"),
            (ErrorCodes.FULL008, None, "restricted"),
            (ErrorCodes.FULL005, 500, "HTTP 500.*temporary"),
        ],
    )
    def test_errors_get_a_specific_message(self, code, status, message):
        client = MagicMock()
        client.get_fulltext_content.side_effect = _full_text_error(code, status)
        srv._fulltext_client_cache.set(client)
        with pytest.raises(ToolError, match=message):
            _run(srv._fulltext_xml("PMC42"))

    def test_other_errors_keep_their_own_text(self):
        client = MagicMock()
        client.get_fulltext_content.side_effect = _full_text_error(ErrorCodes.FULL005, 400)
        srv._fulltext_client_cache.set(client)
        with pytest.raises(ToolError, match="FULL005"):
            _run(srv._fulltext_xml("PMC42"))

    def test_empty_body_is_an_error_and_is_not_cached(self):
        client = MagicMock()
        client.get_fulltext_content.return_value = ""
        srv._fulltext_client_cache.set(client)
        with pytest.raises(ToolError, match="empty full text"):
            _run(srv._fulltext_xml("PMC42"))
        assert srv._fulltext_xml_cache.get("PMC42") is None
