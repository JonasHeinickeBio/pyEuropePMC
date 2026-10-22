"""Unit tests for the MCP resources (paper full text, references, outline) and the prompts.

A resource runs the code of the tool behind it, so it is tested the way that tool is: the real
parser on a small JATS document with only the two network steps replaced. Reads go through
``mcp.read_resource`` and prompts through ``mcp.get_prompt``, the calls a client's requests
end up in, and the errors are checked as the SDK reports them. Nothing here uses the network.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

from mcp_wire import schema_of
import pytest
from test_mcp_fulltext import JATS

from pyeuropepmc.mcp import _fulltext as ft, _prompts as pr, server as srv

_URIS = {
    "paper_fulltext": "epmc://paper/{pmcid}",
    "paper_references": "epmc://paper/{pmcid}/references",
    "paper_outline": "epmc://paper/{pmcid}/outline",
}


def _run(coro):
    return asyncio.run(coro)


def _read(uri: str) -> tuple[str, str]:
    """``(text, mime type)`` of a resource, read the way a client's request is."""
    (item,) = list(_run(srv.mcp.read_resource(uri)))
    content = item.content
    return (content.decode() if isinstance(content, bytes) else content), item.mime_type


def _prompt_text(name: str, **arguments: Any) -> str:
    result = _run(srv.mcp.get_prompt(name, arguments))
    return "\n".join(m.content.text for m in result.messages)


@pytest.fixture(autouse=True)
def _reset_caches():
    for cache in (srv._client_cache, srv._fulltext_client_cache, srv._fulltext_xml_cache):
        cache.reset()
    yield
    for cache in (srv._client_cache, srv._fulltext_client_cache, srv._fulltext_xml_cache):
        cache.reset()


@pytest.fixture
def paper(monkeypatch):
    seen: list[dict[str, str]] = []

    async def locate(pmcid="", pmid="", doi=""):
        seen.append({"pmcid": pmcid, "pmid": pmid, "doi": doi})
        return "PMC42", {"pmcid": "PMC42", "pmid": "123", "doi": "10.1/test", "title": "T"}

    async def xml(pmcid):
        return JATS

    monkeypatch.setattr(srv, "_locate_fulltext", locate)
    monkeypatch.setattr(srv, "_fulltext_xml", xml)
    return seen


class TestRegistration:
    def test_the_three_uri_templates_are_listed(self):
        templates = _run(srv.mcp.list_resource_templates())
        found = {t.name: getattr(t, "uri_template", None) or t.uriTemplate for t in templates}
        assert found == _URIS
        assert {t.mime_type if hasattr(t, "mime_type") else t.mimeType for t in templates} == {
            "text/markdown",
            "application/json",
        }

    def test_the_templates_are_not_concrete_resources(self):
        assert _run(srv.mcp.list_resources()) == []

    def test_the_three_prompts_are_listed_with_their_arguments(self):
        prompts = {p.name: p for p in _run(srv.mcp.list_prompts())}
        assert set(prompts) == {"literature_review", "critical_appraisal", "citation_trace"}
        required = {
            name: sorted(a.name for a in p.arguments or [] if a.required)
            for name, p in prompts.items()
        }
        assert required == {
            "literature_review": ["topic"],
            "critical_appraisal": ["pmcid"],
            "citation_trace": ["pmid"],
        }
        assert [a.name for a in prompts["literature_review"].arguments] == [
            "topic",
            "years",
            "max_papers",
        ]


class TestPaperResource:
    def test_it_is_the_tool_output_as_markdown(self, paper):
        text, mime = _read("epmc://paper/PMC42")
        tool = _run(srv.get_paper_fulltext(pmcid="PMC42"))
        assert mime == "text/markdown"
        assert text.startswith("# A test article\n\n")
        assert tool["content"] in text
        assert "Method text." in text and "| ALDH1 | 9q21 |" in text
        assert "Shown" not in text  # nothing was cut

    def test_a_bare_number_resolves_like_the_tool(self, paper):
        _read("epmc://paper/42")
        assert paper[-1]["pmcid"] == "PMC42"

    def test_the_payload_is_bounded_like_the_tool_and_says_how_to_get_the_rest(
        self, paper, monkeypatch
    ):
        long_xml = JATS.replace("Intro text.", "word " * 20000)

        async def xml(pmcid):
            return long_xml

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        text, _ = _read("epmc://paper/PMC42")
        tool = _run(srv.get_paper_fulltext(pmcid="PMC42"))
        assert tool["truncated"] is True
        assert len(text) < tool["returned_chars"] + 500
        assert len(text) < 31_000
        assert f"Shown {tool['returned_chars']} of {tool['total_chars']} characters" in text
        assert 'get_paper_fulltext(pmcid="PMC42", sections=' in text


class TestOutlineResource:
    def test_titles_block_counts_and_sizes(self, paper):
        text, mime = _read("epmc://paper/PMC42/outline")
        data = json.loads(text)
        assert mime == "application/json"
        assert (data["pmcid"], data["title"]) == ("PMC42", "A test article")
        titles = [s["title"] for s in data["sections"]]
        assert {"Introduction", "Methods", "Results"} <= set(titles)
        results = next(s for s in data["sections"] if s["title"] == "Results")
        assert results["blocks"]["figure"] == 1 and results["chars"] > 0
        assert data["total_chars"] == sum(s["chars"] for s in data["sections"]) > 0

    def test_it_matches_the_tool(self, paper):
        data = json.loads(_read("epmc://paper/PMC42/outline")[0])
        assert (
            data["sections"]
            == _run(srv.get_paper_fulltext(pmcid="PMC42", format="outline"))["content"]
        )


class TestReferencesResource:
    def test_the_parsed_references_as_json(self, paper):
        text, mime = _read("epmc://paper/PMC42/references")
        data = json.loads(text)
        tool = _run(srv.get_paper_fulltext(pmcid="PMC42", include_references=True))
        assert mime == "application/json"
        assert data["pmcid"] == "PMC42"
        assert data["reference_count"] == tool["reference_count"] == 1
        assert data["returned"] == 1 and data["truncated"] is False
        assert data["references"] == json.loads(json.dumps(tool["references"]))

    def test_a_long_list_is_cut_at_an_entry_and_says_so(self, paper, monkeypatch):
        refs = "".join(
            f'<ref id="B{i}"><mixed-citation>{"Reference text " * 20}{i}</mixed-citation></ref>'
            for i in range(200)
        )
        long_xml = JATS.replace(
            '<ref id="B1"><mixed-citation>Ref one</mixed-citation></ref>', refs
        )

        async def xml(pmcid):
            return long_xml

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        monkeypatch.setattr(srv, "RESOURCE_REFERENCES_MAX_CHARS", 5000)
        data = json.loads(_read("epmc://paper/PMC42/references")[0])
        assert data["reference_count"] == 200
        assert 0 < data["returned"] < 200 == data["reference_count"]
        assert data["truncated"] is True
        assert len(data["references"]) == data["returned"]
        assert len(json.dumps(data["references"], separators=(",", ":"))) <= 5000

    def test_take_references(self):
        items = [{"t": "x" * 10}] * 5
        size = len(json.dumps(items[0], separators=(",", ":"))) + 1
        assert ft.take_references(items, size * 3) == (items[:3], True)
        assert ft.take_references(items, size * 5) == (items, False)
        assert ft.take_references([], 10) == ([], False)


class TestResourceErrors:
    @pytest.mark.parametrize(
        "uri",
        ["epmc://paper/notanid", "epmc://paper/PMC42x/outline", "epmc://paper/PMC/references"],
    )
    def test_a_bad_pmcid_says_what_a_pmcid_looks_like(self, uri):
        with pytest.raises(Exception, match="pmcid must look like PMC1234567"):
            _read(uri)

    @pytest.mark.parametrize("suffix", ["", "/outline", "/references"])
    def test_a_paper_that_is_not_open_access_gets_the_tools_error(self, suffix):
        client = MagicMock()
        client.search_all.return_value = [{"pmcid": "PMC9", "isOpenAccess": "N"}]
        srv._client_cache.set(client)
        with pytest.raises(Exception, match="PMC9 is not Open Access"):
            _read(f"epmc://paper/PMC9{suffix}")

    def test_an_unknown_paper_gets_the_tools_error(self):
        client = MagicMock()
        client.search_all.return_value = []
        srv._client_cache.set(client)
        with pytest.raises(Exception, match="No Europe PMC record found"):
            _read("epmc://paper/PMC1")

    def test_an_unknown_uri_is_not_found(self):
        with pytest.raises(Exception, match=r"epmc://paper/PMC1/figures|Unknown resource"):
            _read("epmc://paper/PMC1/figures")


class TestPromptRendering:
    def test_literature_review_with_only_the_topic(self):
        text = _prompt_text("literature_review", topic="statins and dementia")
        assert "review of: statins and dementia" in text
        assert "any year" in text and "at most 20 papers" in text
        assert 'count_papers(query="statins and dementia")' in text
        assert "date_from" not in text.split("1.")[1].split("2.")[0]
        assert "limit=60" in text

    def test_literature_review_with_years_and_max_papers(self):
        text = _prompt_text(
            "literature_review", topic="long covid", years="2019-2024", max_papers="5"
        )
        assert "published 2019 to 2024" in text
        assert 'count_papers(query="long covid", date_from="2019", date_to="2024")' in text
        assert "at most 5 papers" in text and "limit=15" in text

    def test_a_single_year(self):
        text = pr.literature_review("x", years="2021")
        assert "published 2021;" in text and 'date_from="2021", date_to="2021"' in text

    def test_the_topic_cannot_break_out_of_its_quotes(self):
        text = pr.literature_review('a "b" \n c')
        assert "query=\"a 'b' c\"" in text

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"topic": "  "}, "topic must not be empty"),
            ({"topic": "x", "years": "twenty"}, "years must look like"),
            ({"topic": "x", "years": "2024-2019"}, "years run backwards"),
            ({"topic": "x", "max_papers": 0}, "max_papers must be between"),
            ({"topic": "x", "max_papers": 101}, "max_papers must be between"),
        ],
    )
    def test_bad_arguments_say_why(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            pr.literature_review(**kwargs)

    def test_a_bad_argument_reaches_the_client_with_its_reason(self):
        with pytest.raises(Exception, match="years must look like"):
            _prompt_text("literature_review", topic="x", years="soon")

    def test_critical_appraisal_normalises_the_pmcid(self):
        for given in ("PMC3525259", "pmc3525259", "3525259"):
            text = _prompt_text("critical_appraisal", pmcid=given)
            assert 'get_paper_fulltext(pmcid="PMC3525259", format="outline")' in text
            assert 'sections=["methods"]' in text and 'sections=["results"]' in text
        with pytest.raises(Exception, match="pmcid must look like"):
            _prompt_text("critical_appraisal", pmcid="PMID123")

    @pytest.mark.parametrize(
        ("direction", "backward", "forward", "snowball"),
        [
            ("both", True, True, True),
            ("forward", False, True, False),
            ("backward", True, False, False),
        ],
    )
    def test_citation_trace_directions(self, direction, backward, forward, snowball):
        text = _prompt_text("citation_trace", pmid="22745249", direction=direction)
        assert ("get_paper_references(" in text) is backward
        assert ("get_paper_citations(" in text) is forward
        assert ("citation_snowball(" in text) is snowball
        assert "get_paper_details(" in text

    def test_citation_trace_defaults_to_both(self):
        assert _prompt_text("citation_trace", pmid="1") == pr.citation_trace("1", "both")

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"pmid": "PMC1"}, "pmid must be digits"),
            ({"pmid": "1", "direction": "sideways"}, "direction must be one of"),
        ],
    )
    def test_citation_trace_bad_arguments(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            pr.citation_trace(**kwargs)

    def test_the_steps_are_numbered_without_gaps(self):
        import re

        for text in (
            pr.literature_review("x"),
            pr.critical_appraisal("PMC1"),
            pr.citation_trace("1", "both"),
            pr.citation_trace("1", "forward"),
        ):
            numbers = [int(n) for n in re.findall(r"^(\d+)\. ", text, re.MULTILINE)]
            assert numbers == list(range(1, len(numbers) + 1))


ALL_PROMPTS = {
    "literature_review": pr.literature_review("heart failure", "2020-2023", 10),
    "critical_appraisal": pr.critical_appraisal("PMC1234567"),
    "citation_trace both": pr.citation_trace("22745249", "both"),
    "citation_trace forward": pr.citation_trace("22745249", "forward"),
    "citation_trace backward": pr.citation_trace("22745249", "backward"),
}


class TestPromptsOnlyUseRealTools:
    """A prompt that names a tool or a parameter the server does not have sends the model into
    an error. Every call written in a prompt is checked against ``mcp.list_tools()``."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, set[str]]:
        return {t.name: set(schema_of(t)["properties"]) for t in _run(srv.mcp.list_tools())}

    @pytest.mark.parametrize("name", ALL_PROMPTS)
    def test_every_tool_and_parameter_exists(self, name, schemas):
        calls = pr.tool_calls(ALL_PROMPTS[name])
        assert calls, "the prompt names no tool calls"
        for tool, params in calls:
            assert tool in schemas, f"{name}: no tool {tool!r}"
            assert set(params) <= schemas[tool], (
                f"{name}: {tool} has no parameter {sorted(set(params) - schemas[tool])}"
            )

    def test_the_tools_named_in_prose_exist_too(self, schemas):
        import re

        for name, text in ALL_PROMPTS.items():
            for tool in re.findall(r"`([a-z]+(?:_[a-z]+)+)`", text):
                assert tool in schemas, f"{name}: no tool {tool!r}"

    def test_the_workflows_use_the_tools_the_issue_names(self):
        review = {t for t, _ in pr.tool_calls(ALL_PROMPTS["literature_review"])}
        assert {"count_papers", "search_papers", "get_paper_fulltext"} <= review
        appraisal = {t for t, _ in pr.tool_calls(ALL_PROMPTS["critical_appraisal"])}
        assert {"get_paper_fulltext"} <= appraisal
        trace = {t for t, _ in pr.tool_calls(ALL_PROMPTS["citation_trace both"])}
        assert {"get_paper_references", "get_paper_citations"} <= trace

    def test_the_checker_catches_a_wrong_name(self, schemas):
        (call,) = pr.tool_calls('Run `count_paper(query="x")` and `count_papers(quer="x")`.')[:1]
        assert call[0] not in schemas
        assert not set(pr.tool_calls('`count_papers(quer="x")`')[0][1]) <= schemas["count_papers"]
