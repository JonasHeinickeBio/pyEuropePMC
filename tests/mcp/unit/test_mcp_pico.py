"""Unit tests for the PICO decomposition tool and its helpers.

``tests/fixtures/pico`` holds gold questions in three sets: ``dev`` (used while the rules were
written), ``held_out`` (written before the rules and not looked at until they were done) and
``harder`` (phrased outside the patterns, to show where the rules stop). The first two are
asserted exactly; ``harder`` only has to stay above a floor and never invent anything. Nothing
here touches the network.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import random
import string

import pytest

from pyeuropepmc.mcp import _pico as pc, _query as qm, server as srv
from pyeuropepmc.mcp.server import ToolError

FIXTURES = Path(__file__).parents[2] / "fixtures" / "pico"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["questions"]


def _run(coro):
    return asyncio.run(coro)


def _got(question: str, framework: str) -> dict[str, str]:
    return {k: v.text for k, v in pc.decompose(question, framework).elements.items()}


class TestGoldQuestions:
    @pytest.mark.parametrize("item", _load("dev") + _load("held_out"), ids=lambda i: i["id"])
    def test_every_element_matches_the_gold(self, item):
        got = _got(item["question"], item["framework"])
        for element, gold in item["gold"].items():
            assert got.get(element, "").lower() == gold.lower(), f"{item['id']} {element}"
        # nothing beyond the gold elements was produced
        assert set(got) <= {k for k, v in item["gold"].items() if v}

    @pytest.mark.parametrize("name", ["dev", "held_out", "harder"])
    def test_nothing_is_invented_or_fabricated(self, name):
        for item in _load(name):
            decomposition = pc.decompose(item["question"], item["framework"])
            for element, span in decomposition.elements.items():
                # a verbatim piece of the question, at the position it claims
                assert item["question"][span.start : span.end] == span.text, item["id"]
                # and an element is only reported when the gold says the question states it
                assert item["gold"].get(element), f"{item['id']} invented {element}: {span.text}"

    def test_the_harder_questions_stay_above_a_floor(self):
        stated = found = 0
        for item in _load("harder"):
            got = _got(item["question"], item["framework"])
            for element, gold in item["gold"].items():
                if gold:
                    stated += 1
                    found += got.get(element, "").lower() == gold.lower()
        assert found / stated >= 0.35  # measured: 11 of 28; the tool says these are not covered


class TestMissingElements:
    def test_a_missing_comparison_is_optional(self):
        d = pc.decompose("In adults with asthma, does exercise reduce attacks?")
        assert d.complete and d.missing == [] and d.optional_missing == ["comparison"]

    def test_missing_required_elements_are_listed(self):
        d = pc.decompose("Patients with chronic kidney disease treated with SGLT2 inhibitors")
        assert not d.complete
        assert d.missing == ["outcome"]
        assert d.elements["population"].text == "Patients with chronic kidney disease"

    def test_a_non_clinical_question_yields_nothing_and_says_why(self):
        d = pc.decompose("What is the best programming language for web development?")
        assert d.elements == {} and not d.complete
        assert d.missing == ["population", "intervention", "outcome"]
        assert "no known question pattern" in d.notes[0]

    def test_picos_needs_a_study_design_and_pico_t_a_time_frame(self):
        q = "Does yoga improve sleep in women?"
        assert pc.decompose(q, "PICO").complete
        assert pc.decompose(q, "PICOS").missing == ["study_design"]
        assert pc.decompose(q, "PICOT").missing == ["time_frame"]
        with_both = (
            "Does yoga improve sleep in women in a randomized controlled trial at 6 months?"
        )
        assert pc.decompose(with_both, "PICOS").complete
        assert pc.decompose(with_both, "PICOT").complete

    def test_the_relation_and_gerund_are_separated_from_the_outcome(self):
        d = pc.decompose("Is metformin effective for reducing hospitalisation in adults?")
        assert d.elements["outcome"].text == "hospitalisation"
        assert d.relation is not None and d.relation.text == "reducing"
        d = pc.decompose("Does aspirin prevent stroke?")
        assert d.relation is not None and d.relation.text == "prevent"

    def test_an_effective_for_question_notes_how_it_read_the_outcome(self):
        d = pc.decompose("Is yoga effective for back pain in adults?")
        assert any("effective for X" in n for n in d.notes)

    def test_an_association_question_is_marked(self):
        d = pc.decompose("Is smoking associated with lung cancer in men?")
        assert d.elements["intervention"].text == "smoking"
        assert any("exposure" in n for n in d.notes)


class TestPositions:
    def test_the_relation_span_is_exact_when_several_spaces_follow_the_gerund(self):
        q = "Is metformin effective for reducing  hospitalisation in adults?"
        relation = pc.decompose(q).relation
        assert relation is not None and relation.text == "reducing"
        assert q[relation.start : relation.end] == "reducing"

    @pytest.mark.parametrize("pad", ["   ", "\n\t ", " "])
    def test_positions_refer_to_the_question_as_sent_leading_space_included(self, pad):
        q = pad + "In adults with asthma, does exercise reduce attacks compared with usual care?"
        d = pc.decompose(q)
        assert {k: v.text for k, v in d.elements.items()} == {
            "population": "adults with asthma",
            "intervention": "exercise",
            "comparison": "usual care",
            "outcome": "attacks",
        }
        for span in [*d.elements.values(), d.relation]:
            assert span is not None and q[span.start : span.end] == span.text

    def test_the_tool_reports_positions_in_the_caller_s_string(self):
        q = "  Does yoga improve sleep in women?  "
        for span in _run(srv.pico_decompose(question=q))["elements"].values():
            assert q[span["start"] : span["end"]] == span["text"]

    def test_spider_positions_too(self):
        q = "  What are the experiences of nurses during the pandemic?"
        for span in pc.decompose(q, "SPIDER").elements.values():
            assert q[span.start : span.end] == span.text


class TestSpider:
    def test_qualitative_question(self):
        d = pc.decompose(
            "What are the experiences of nurses working in intensive care during the pandemic?",
            "SPIDER",
        )
        assert {k: v.text for k, v in d.elements.items()} == {
            "evaluation": "experiences",
            "sample": "nurses working in intensive care",
            "phenomenon_of_interest": "the pandemic",
        }
        assert d.complete
        assert d.optional_missing == ["design", "research_type"]

    def test_design_and_research_type_are_found_by_keyword(self):
        d = pc.decompose(
            "What are the views of teachers using focus groups in a qualitative study?", "SPIDER"
        )
        assert d.elements["design"].text == "focus groups"
        assert d.elements["research_type"].text.lower().startswith("qualitative")

    def test_a_question_that_is_not_qualitative_is_not_understood(self):
        d = pc.decompose("Does aspirin prevent stroke?", "SPIDER")
        assert not d.complete and d.notes


class TestValidation:
    def test_an_unknown_framework_is_refused(self):
        with pytest.raises(ValueError, match="unknown framework"):
            pc.decompose("Does X help Y?", "PEO")

    def test_framework_is_case_insensitive(self):
        assert pc.decompose("Does yoga help sleep in women?", " pico ").framework == "PICO"

    @pytest.mark.parametrize("question", ["", "   "])
    def test_an_empty_question_is_refused(self, question):
        with pytest.raises(ValueError, match="empty"):
            pc.decompose(question)

    def test_an_overlong_question_is_refused(self):
        with pytest.raises(ValueError, match="limit"):
            pc.decompose("x " * 2000)

    def test_arbitrary_text_never_raises(self):
        rng = random.Random(7)
        alphabet = string.ascii_letters + string.digits + " ,;:?.()\"'-/"
        words = ["in", "among", "does", "reduce", "compared with", "versus", "patients", "for"]
        for _ in range(400):
            text = " ".join(
                rng.choice(words)
                if rng.random() < 0.4
                else "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 8)))
                for _ in range(rng.randint(1, 14))
            )
            if text.strip():
                d = pc.decompose(text, rng.choice(pc.FRAMEWORKS))
                for span in d.elements.values():
                    assert text[span.start : span.end] == span.text


class TestQuery:
    def test_concepts_take_the_condition_of_a_population(self):
        assert pc.concepts("population", "adults with type 2 diabetes") == ["type 2 diabetes"]
        assert pc.concepts("population", "older adults") == ["older adults"]
        assert pc.concepts("population", "women who have PCOS") == ["PCOS"]

    def test_concepts_split_alternatives_and_drop_syntax(self):
        assert pc.concepts("intervention", "statins or aspirin") == ["statins", "aspirin"]
        assert pc.concepts("intervention", 'the "wonder" drug (X)') == ["wonder drug X"]
        assert pc.concepts("intervention", "statins, statins") == ["statins"]

    def test_phrase_quotes_only_multi_word_terms(self):
        assert pc.phrase("metformin") == "metformin"
        assert pc.phrase("type 2 diabetes") == '"type 2 diabetes"'
        assert pc.phrase("DPP-4") == '"DPP-4"'

    def test_the_default_query_is_population_and_intervention(self):
        d = pc.decompose("In adults with type 2 diabetes, does metformin reduce mortality?")
        query, used = pc.build_query(d)
        assert query == '"type 2 diabetes" AND metformin'
        assert used == ["population", "intervention"]

    def test_chosen_elements_and_alternatives(self):
        d = pc.decompose("Do statins or aspirin prevent stroke in adults with diabetes?")
        query, used = pc.build_query(d, ("intervention", "outcome"))
        assert query == "(statins OR aspirin) AND stroke"
        assert used == ["intervention", "outcome"]

    def test_expand_replaces_known_terms_only(self):
        d = pc.decompose("Does metformin reduce pain in adults with unknownitis?")
        query, _ = pc.build_query(d, expand=lambda t: "(EXPANDED)" if t == "metformin" else None)
        assert query == "unknownitis AND (EXPANDED)"

    def test_nothing_to_search_gives_an_empty_query(self):
        d = pc.decompose("What is the best programming language for web development?")
        assert pc.build_query(d) == ("", [])

    @pytest.mark.parametrize("item", _load("dev") + _load("held_out") + _load("harder"))
    def test_every_generated_query_passes_the_linter(self, item):
        d = pc.decompose(item["question"], item["framework"])
        for use in (("population", "intervention"), tuple(pc.ELEMENTS[d.framework])):
            query, _ = pc.build_query(d, use)
            if query:
                assert not qm.lint(query).errors, query


def _no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the offline path made a request")

    monkeypatch.setattr(srv.requests, "get", fail)
    monkeypatch.setattr(srv, "_nlm_get", fail)


class TestTool:
    def test_default_call(self, monkeypatch):
        _no_network(monkeypatch)
        result = _run(
            srv.pico_decompose(
                question="In adults with type 2 diabetes, does metformin reduce "
                "cardiovascular mortality compared with placebo?"
            )
        )
        assert result["framework"] == "PICO" and result["complete"] is True
        assert result["elements"]["population"]["text"] == "adults with type 2 diabetes"
        assert result["missing"] == [] and result["optional_missing"] == []
        assert result["relation"]["text"] == "reduce"
        assert result["query"] == '"type 2 diabetes" AND metformin'
        assert result["query_built_from"] == ["population", "intervention"]
        assert result["query_check"] == {"valid": True, "problems": [], "warnings": []}
        assert result["method"] == "rules"

    def test_positions_point_into_the_question(self):
        question = "Does yoga improve sleep in women?"
        result = _run(srv.pico_decompose(question=question))
        for span in result["elements"].values():
            assert question[span["start"] : span["end"]] == span["text"]

    def test_an_incomplete_question_reports_what_is_missing(self):
        result = _run(srv.pico_decompose(question="What is the best programming language?"))
        assert result["complete"] is False
        assert result["missing"] == ["population", "intervention", "outcome"]
        assert result["query"] == "" and result["query_check"] is None
        assert result["notes"]

    def test_query_elements_choose_what_the_query_is_built_from(self):
        result = _run(
            srv.pico_decompose(
                question="Does yoga improve sleep in women?",
                query_elements=["outcome"],
            )
        )
        assert result["query"] == "sleep" and result["query_built_from"] == ["outcome"]

    def test_spider_builds_from_sample_and_phenomenon(self):
        result = _run(
            srv.pico_decompose(
                question="What are the experiences of nurses during the pandemic?",
                framework="SPIDER",
            )
        )
        assert result["query_built_from"] == ["sample", "phenomenon_of_interest"]
        assert result["query"] == "nurses AND pandemic"

    def test_mesh_expands_known_terms_from_the_snapshot_without_a_request(self, monkeypatch):
        _no_network(monkeypatch)
        result = _run(
            srv.pico_decompose(
                question="In adults with type 2 diabetes, does metformin reduce mortality?",
                mesh=True,
            )
        )
        assert 'MESH:"Diabetes Mellitus, Type 2"' in result["query"]
        assert 'MESH:"Metformin"' in result["query"]
        assert result["query_check"]["valid"] is True

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"question": "Does X help Y?", "framework": "PEO"},
            {"question": "Does X help Y?", "query_elements": ["population", "sample"]},
            {"question": "   "},
            {"question": "x " * 2000},
        ],
    )
    def test_bad_input_is_a_tool_error(self, kwargs):
        with pytest.raises(ToolError):
            _run(srv.pico_decompose(**kwargs))

    def test_the_tool_is_local_and_read_only(self):
        from mcp_wire import hint

        tools = {t.name: t for t in _run(srv.mcp.list_tools())}
        annotations = tools["pico_decompose"].annotations
        assert hint(annotations, "readOnlyHint") is True
        assert hint(annotations, "openWorldHint") is False

    def test_the_description_states_the_limits(self):
        description = srv.pico_decompose.__doc__ or ""
        assert "Rule-based" in description and "verbatim" in description
        assert "never filled in" in description and "phrased differently" in description
