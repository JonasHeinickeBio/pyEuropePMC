"""Unit tests for the MeSH expansion tool, the bundled snapshot and the NLM service path.

The default path reads ``data/mesh_common.json`` and makes no request; the ``use_api`` path is
tested with a fake fetch function that answers like the NLM service. Nothing here touches the
network.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import pytest
import requests

from pyeuropepmc.mcp import _mesh as mm, _query as qm, server as srv
from pyeuropepmc.mcp.server import ToolError


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("a request was made")

    monkeypatch.setattr(srv.requests, "get", fail)
    monkeypatch.setattr(srv, "_nlm_get", fail)


class TestSnapshot:
    def test_it_is_a_real_size_and_well_formed(self):
        snap = mm.snapshot()
        assert len(snap.descriptors) >= 200
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", snap.built)
        url = re.search(r"https://[^\s,)]+", snap.source)
        assert url is not None and urlparse(url.group()).hostname == "id.nlm.nih.gov"
        for d in snap.descriptors:
            assert re.fullmatch(r"D\d{6,9}", d.ui), d
            assert d.heading and d.trees, d
            assert all(re.fullmatch(r"[A-Z]\d{2}(\.\d{3})*", t) for t in d.trees), d
            assert mm.normalise(d.heading) not in {mm.normalise(e) for e in d.entry_terms}

    def test_headings_and_descriptor_ids_are_unique(self):
        headings = [mm.normalise(d.heading) for d in mm.snapshot().descriptors]
        uis = [d.ui for d in mm.snapshot().descriptors]
        assert len(set(headings)) == len(headings) and len(set(uis)) == len(uis)

    def test_known_facts_as_nlm_publishes_them(self):
        d = mm.snapshot().lookup("Diabetes Mellitus, Type 2").descriptor
        assert d is not None and d.ui == "D003924"
        assert set(d.trees) == {"C18.452.394.750.149", "C19.246.300"}
        assert "NIDDM" in d.entry_terms
        assert mm.snapshot().lookup("Metformin").descriptor.trees == ("D02.078.370.141.450",)

    def test_every_fragment_passes_the_linter(self):
        for descriptor in mm.snapshot().descriptors:
            match = mm.Match(descriptor.heading, descriptor, "heading")
            for limit in (0, 6, 20):
                query = mm.fragment(match, limit)
                assert not qm.lint(query).errors, query


class TestLookup:
    @pytest.mark.parametrize(
        ("term", "heading", "how"),
        [
            ("Diabetes Mellitus, Type 2", "Diabetes Mellitus, Type 2", "heading"),
            ("diabetes mellitus, type 2", "Diabetes Mellitus, Type 2", "heading"),
            ("  METFORMIN  ", "Metformin", "heading"),
            ("heart attack", "Myocardial Infarction", "entry term"),
            ('"heart attack"', "Myocardial Infarction", "entry term"),
            ("type 2 diabetes", "Diabetes Mellitus, Type 2", "entry term"),
            ("heart attacks", "Myocardial Infarction", "plural form"),
        ],
    )
    def test_matches(self, term, heading, how):
        match = mm.snapshot().lookup(term)
        assert match.descriptor is not None and match.descriptor.heading == heading
        assert match.matched_on == how and match.source == "snapshot"

    @pytest.mark.parametrize("term", ["", "  ", "some unknown thing", "zzzzz"])
    def test_unknown_terms_are_not_guessed(self, term):
        match = mm.snapshot().lookup(term)
        assert match.descriptor is None and match.matched_on is None

    def test_a_term_for_several_headings_names_the_others(self):
        snap = mm.snapshot()
        shared = [k for k, v in snap._by_entry.items() if len(v) > 1]
        if shared:  # which terms are shared depends on the snapshot; assert the contract if any
            match = snap.lookup(shared[0])
            assert match.also and match.descriptor.heading not in match.also


class TestFragment:
    def test_matched_term_has_the_mesh_field_the_heading_and_entry_terms(self):
        match = mm.snapshot().lookup("heart attack")
        fragment = mm.fragment(match)
        assert fragment.startswith('(MESH:"Myocardial Infarction" OR "Myocardial Infarction"')
        assert '"heart attack"' in fragment  # the caller's wording, written once
        assert fragment.endswith(")")

    def test_the_wording_is_not_repeated_when_it_is_the_heading(self):
        fragment = mm.fragment(mm.snapshot().lookup("Metformin"))
        assert fragment.count('"Metformin"') == 2  # once in MESH:, once as a phrase

    def test_the_entry_term_cap_counts_only_added_terms(self):
        match = mm.snapshot().lookup("type 2 diabetes")
        few, many = mm.fragment(match, 1), mm.fragment(match, 20)
        assert few.count(" OR ") == 3 and many.count(" OR ") > few.count(" OR ")
        assert mm.fragment(match, 0).count(" OR ") == 2

    def test_shortest_entry_terms_come_first(self):
        match = mm.snapshot().lookup("Diabetes Mellitus, Type 2")
        assert '"NIDDM"' in mm.fragment(match, 1)

    def test_an_unmatched_term_is_a_phrase_and_quotes_are_neutralised(self):
        assert mm.fragment(mm.Match("some thing", None)) == '"some thing"'
        assert mm.fragment(mm.Match('a "b" \\ c', None)) == '"a b c"'


class FakeNlm:
    """Answers like id.nlm.nih.gov for a few requests and records what was asked."""

    def __init__(self, descriptor_hits=None, term_hits=None, near=None, details=True):
        self.calls: list[tuple[str, dict]] = []
        self.descriptor_hits = descriptor_hits or {}
        self.term_hits = term_hits or {}
        self.near = near or []
        self.details = details

    def __call__(self, url, params, timeout):
        self.calls.append((url, params))
        assert timeout > 0
        if url.endswith("/lookup/descriptor"):
            if params["match"] == "exact":
                ui = self.descriptor_hits.get(params["label"].lower())
                return (
                    [{"resource": f"http://id.nlm.nih.gov/mesh/{ui}", "label": "x"}] if ui else []
                )
            return [
                {"resource": "http://id.nlm.nih.gov/mesh/D000001", "label": n} for n in self.near
            ]
        if url.endswith("/lookup/term"):
            t = self.term_hits.get(params["label"].lower())
            return [{"resource": f"http://id.nlm.nih.gov/mesh/{t}", "label": "x"}] if t else []
        assert url == mm.SPARQL_URL
        query = params["query"]
        if "?c meshv:term mesh:" in query:  # term -> descriptor
            return {
                "results": {"bindings": [{"d": {"value": "http://id.nlm.nih.gov/mesh/D012507"}}]}
            }
        if not self.details:
            return {"results": {"bindings": []}}
        return {
            "results": {
                "bindings": [
                    {
                        "label": {"value": "Sarcoidosis"},
                        "tree": {"value": "http://x/C08.381.483.800"},
                        "entry": {"value": "Boeck Sarcoid"},
                    },
                    {
                        "label": {"value": "Sarcoidosis"},
                        "tree": {"value": "http://x/C15.604.250.800"},
                        "entry": {"value": "Besnier-Boeck-Schaumann Disease"},
                    },
                    {
                        "label": {"value": "Sarcoidosis"},
                        "tree": {"value": "http://x/C08.381.483.800"},
                        "entry": {"value": "Sarcoidosis"},
                    },
                ]
            }
        }


class TestNlmPath:
    def test_a_heading_is_found_and_described(self):
        fetch = FakeNlm(descriptor_hits={"sarcoidosis": "D012507"})
        match = mm.lookup_api("Sarcoidosis", fetch)
        assert match.source == "nlm" and match.matched_on == "heading"
        d = match.descriptor
        assert d is not None and d.ui == "D012507" and d.heading == "Sarcoidosis"
        assert d.trees == ("C08.381.483.800", "C15.604.250.800")
        assert d.entry_terms == ("Besnier-Boeck-Schaumann Disease", "Boeck Sarcoid")
        assert [u.rsplit("/", 1)[-1] for u, _ in fetch.calls][:2] == ["descriptor", "sparql"]

    def test_an_entry_term_goes_through_the_term_lookup(self):
        fetch = FakeNlm(term_hits={"boeck sarcoid": "T000001"})
        match = mm.lookup_api("Boeck Sarcoid", fetch)
        assert match.matched_on == "entry term" and match.descriptor.heading == "Sarcoidosis"

    def test_no_match_gives_suggestions_and_no_guess(self):
        match = mm.lookup_api("sarcoid", FakeNlm(near=["Sarcoidosis", "Sarcoma"]))
        assert match.descriptor is None
        assert match.suggestions == ["Sarcoidosis", "Sarcoma"]

    def test_a_descriptor_without_details_is_not_a_match(self):
        fetch = FakeNlm(descriptor_hits={"x": "D012507"}, details=False)
        assert mm.lookup_api("x", fetch).descriptor is None

    def test_an_odd_identifier_never_reaches_a_query(self):
        fetch = FakeNlm(descriptor_hits={"x": "D1} UNION {?s ?p ?o"})
        with pytest.raises(ValueError, match="unexpected MeSH identifier"):
            mm.lookup_api("x", fetch)
        assert all(u != mm.SPARQL_URL for u, _ in fetch.calls)


class TestTool:
    def test_default_is_offline_and_describes_each_term(self):
        result = _run(srv.mesh_expand(terms=["type 2 diabetes", "metformin", "no such thing"]))
        assert result["source"] == "snapshot"
        assert result["snapshot"] == {
            "built": mm.snapshot().built,
            "headings": len(mm.snapshot().descriptors),
        }
        first, second, third = result["terms"]
        assert first["matched"] and first["matched_on"] == "entry term"
        assert first["descriptor"]["heading"] == "Diabetes Mellitus, Type 2"
        assert first["descriptor"]["tree_numbers"] and first["descriptor"]["ui"] == "D003924"
        assert second["descriptor"]["heading"] == "Metformin"
        assert third == {
            "term": "no such thing",
            "matched": False,
            "source": "snapshot",
            "fragment": '"no such thing"',
        }
        assert result["unmatched"] == ["no such thing"]

    def test_terms_are_anded_by_default_and_the_query_is_checked(self):
        result = _run(srv.mesh_expand(terms=["metformin", "heart attack"]))
        assert ") AND (" in result["query"]
        assert result["query_check"] == {"valid": True, "problems": [], "warnings": []}
        assert (
            ") OR ("
            in _run(srv.mesh_expand(terms=["metformin", "heart attack"], combine="or"))["query"]
        )

    def test_max_entry_terms_changes_the_fragment(self):
        short = _run(srv.mesh_expand(terms=["type 2 diabetes"], max_entry_terms=0))["query"]
        long = _run(srv.mesh_expand(terms=["type 2 diabetes"], max_entry_terms=15))["query"]
        assert len(long) > len(short)

    def test_use_api_uses_the_service_and_a_failure_is_reported_per_term(self, monkeypatch):
        fetch = FakeNlm(descriptor_hits={"sarcoidosis": "D012507"})

        def flaky(url, params, timeout):
            if params.get("label") == "boom":
                raise requests.ConnectionError("down")
            return fetch(url, params, timeout)

        monkeypatch.setattr(srv, "_nlm_get", flaky)
        result = _run(srv.mesh_expand(terms=["Sarcoidosis", "boom"], use_api=True))
        assert result["source"] == "nlm" and "snapshot" not in result
        ok, bad = result["terms"]
        assert ok["matched"] and ok["source"] == "nlm" and ok["descriptor"]["ui"] == "D012507"
        assert bad["matched"] is False and "ConnectionError" in bad["error"]
        assert bad["fragment"] == '"boom"'
        assert result["unmatched"] == ["boom"]
        assert result["query_check"]["valid"] is True

    def test_terms_after_the_time_budget_are_skipped_not_dropped(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr(srv, "_now", lambda: clock["now"])
        calls: list[tuple[str, float]] = []

        def slow(url, params, timeout):
            calls.append((url, timeout))
            clock["now"] += 12.0  # every request takes 12 seconds
            if url.endswith("/lookup/descriptor") and params["match"] == "exact":
                return [{"resource": "http://id.nlm.nih.gov/mesh/D012507", "label": "x"}]
            if url == mm.SPARQL_URL:
                return {"results": {"bindings": [{"label": {"value": "Sarcoidosis"}}]}}
            return []

        monkeypatch.setattr(srv, "_nlm_get", slow)
        result = _run(srv.mesh_expand(terms=["a", "b", "c", "d"], use_api=True, time_budget=30))
        done = [t for t in result["terms"] if t.get("matched")]
        skipped = [
            t for t in result["terms"] if t.get("error") == "skipped: time budget exhausted"
        ]
        assert [t["term"] for t in result["terms"]] == ["a", "b", "c", "d"]  # none dropped
        assert len(done) == 1 and len(skipped) == 3
        assert result["unmatched"] == ["b", "c", "d"]
        assert all(t["fragment"] == f'"{t["term"]}"' for t in skipped)
        assert len(calls) == 3  # no request started after the budget ran out
        assert all(timeout <= 15 for _, timeout in calls)
        assert calls[-1][1] == pytest.approx(6.0)  # and none may run past the deadline
        assert result["query_check"]["valid"] is True

    def test_the_budget_does_not_apply_offline_and_is_bounded_in_the_schema(self, monkeypatch):
        from mcp_wire import schema_of

        monkeypatch.setattr(srv, "_now", lambda: pytest.fail("the clock was read offline"))
        assert _run(srv.mesh_expand(terms=["metformin"], time_budget=2))["terms"][0]["matched"]
        tools = {t.name: t for t in _run(srv.mcp.list_tools())}
        budget = schema_of(tools["mesh_expand"])["properties"]["time_budget"]
        assert (budget["minimum"], budget["maximum"], budget["default"]) == (2, 120, 30)

    def test_the_default_never_calls_the_service(self, monkeypatch):
        monkeypatch.setattr(srv, "_nlm_get", lambda *a, **k: pytest.fail("service called"))
        _run(srv.mesh_expand(terms=["metformin"]))

    @pytest.mark.parametrize(
        "kwargs",
        [{"terms": ["x"], "combine": "xor"}, {"terms": ["  ", ""]}],
    )
    def test_bad_input_is_a_tool_error(self, kwargs):
        with pytest.raises(ToolError):
            _run(srv.mesh_expand(**kwargs))

    def test_the_schema_bounds_the_number_of_terms(self):
        from mcp_wire import hint, schema_of

        tools = {t.name: t for t in _run(srv.mcp.list_tools())}
        terms = schema_of(tools["mesh_expand"])["properties"]["terms"]
        assert terms["minItems"] == 1 and terms["maxItems"] == mm.MAX_TERMS
        assert hint(tools["mesh_expand"].annotations, "readOnlyHint") is True
        # use_api sends the terms to id.nlm.nih.gov, so the tool is open-world
        assert hint(tools["mesh_expand"].annotations, "openWorldHint") is True

    def test_the_description_states_the_default_and_the_network_option(self):
        text = " ".join((srv.mesh_expand.__doc__ or "").split())
        assert "offline" in text and "use_api" in text and "network" in text
        assert "never guessed" in text
