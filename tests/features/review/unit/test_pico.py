"""Unit tests for pyeuropepmc.features.review.pico (pure logic, no network)."""

from __future__ import annotations

from pyeuropepmc.features.review.pico import (
    PICOElements,
    PICOParser,
    PICOSDecomposer,
    PICOTDecomposer,
    SPIDERDecomposer,
    pico_decompose,
    pico_to_pubmed_query,
    pico_to_query,
)

QUESTION = (
    "In adult patients with type 2 diabetes, does metformin treated with "
    "lifestyle changes compared with placebo reduce cardiovascular mortality "
    "over 12 months?"
)


class TestPICOElements:
    def test_is_complete_true(self):
        pico = PICOElements(population="adults", intervention="metformin", outcome="mortality")
        assert pico.is_complete()

    def test_is_complete_false(self):
        pico = PICOElements(population="adults")
        assert not pico.is_complete()

    def test_to_dict_roundtrip(self):
        pico = PICOElements(population="p", intervention="i", outcome="o", confidence=0.5)
        d = pico.to_dict()
        assert d["population"] == "p"
        assert d["confidence"] == 0.5
        assert "original_question" in d

    def test_repr_includes_present_fields_only(self):
        pico = PICOElements(population="adults", outcome="mortality")
        text = repr(pico)
        assert "P: adults" in text
        assert "O: mortality" in text
        assert "I:" not in text

    def test_repr_empty(self):
        pico = PICOElements()
        assert repr(pico) == "PICOElements()"


class TestPICOParser:
    def test_parse_extracts_elements(self):
        parser = PICOParser()
        pico = parser.parse(QUESTION)
        assert pico.original_question == QUESTION
        assert 0.0 <= pico.confidence <= 1.0
        assert isinstance(pico.identifiers_used, dict)

    def test_parse_with_custom_patterns(self):
        import re

        patterns = {"population": re.compile(r"(patients)\s+([^.]+)", re.IGNORECASE)}
        parser = PICOParser(patterns=patterns)
        pico = parser.parse("patients with asthma need care.")
        assert pico.population

    def test_clean_question_strips_starters_and_marks(self):
        parser = PICOParser()
        cleaned = parser._clean_question("Does metformin help?")
        assert not cleaned.lower().startswith("does")
        assert not cleaned.endswith("?")

    def test_infer_population_pattern_match(self):
        parser = PICOParser()
        pop = parser._infer_population("patients with Diabetes need monitoring")
        assert "diabetes" in pop.lower() or pop

    def test_infer_population_no_match(self):
        parser = PICOParser()
        assert parser._infer_population("nothing matches here") == ""

    def test_infer_outcome_pattern_match(self):
        parser = PICOParser()
        outcome = parser._infer_outcome("this drug will reduce blood pressure significantly")
        assert "reduce" in outcome.lower()

    def test_infer_outcome_no_match(self):
        parser = PICOParser()
        assert parser._infer_outcome("nothing to infer") == ""

    def test_calculate_confidence_full(self):
        parser = PICOParser()
        pico = PICOElements(population="p", intervention="i", outcome="o", comparison="c")
        assert parser._calculate_confidence(pico) == 1.0

    def test_calculate_confidence_empty(self):
        parser = PICOParser()
        assert parser._calculate_confidence(PICOElements()) == 0.0

    def test_parse_empty_question_yields_low_confidence(self):
        parser = PICOParser()
        pico = parser.parse("")
        assert pico.confidence < 1.0


class TestVariantDecomposers:
    def test_picos_decomposer(self):
        pico = PICOSDecomposer().parse(QUESTION + " This was a randomized controlled trial.")
        assert isinstance(pico, PICOElements)

    def test_picot_decomposer(self):
        pico = PICOTDecomposer().parse(QUESTION)
        assert isinstance(pico, PICOElements)

    def test_time_pattern_fills_time_frame(self):
        pico = PICOTDecomposer().parse(
            "In adults with sepsis, does early antibiotics reduce mortality within 30 days?"
        )
        assert pico.time_frame == "30 days"
        assert pico.identifiers_used["time_frame"] == ["30 days"]
        assert not hasattr(pico, "time"), "the match must not land on a stray attribute"

    def test_time_frame_reaches_to_dict_and_query(self):
        pico = PICOParser().parse(QUESTION)
        assert pico.time_frame == "12 months"
        assert pico.to_dict()["time_frame"] == "12 months"
        assert pico_to_query(pico).endswith("12 months")

    def test_custom_pattern_named_time_still_fills_time_frame(self):
        import re

        parser = PICOParser(patterns={"time": re.compile(r"\b(after)\s+(\d+\s+weeks)")})
        assert parser.parse("pain after 6 weeks").time_frame == "6 weeks"

    def test_spider_decomposer(self):
        result = SPIDERDecomposer().parse(
            "What is the experience of nurses regarding burnout in a qualitative study?"
        )
        assert result["original_question"]
        assert "design" in result or "phenomenon_of_interest" in result

    def test_spider_decomposer_no_matches(self):
        result = SPIDERDecomposer().parse("xyzzy nothing matches")
        assert result == {"original_question": "xyzzy nothing matches"}


class TestModuleFunctions:
    def test_pico_decompose(self):
        pico = pico_decompose(QUESTION)
        assert isinstance(pico, PICOElements)

    def test_pico_to_query_boolean(self):
        pico = PICOElements(population="adult diabetes patients", intervention="metformin drug")
        query = pico_to_query(pico, use_boolean=True)
        assert "AND" in query
        assert "OR" in query

    def test_pico_to_query_non_boolean(self):
        pico = PICOElements(population="adults", outcome="mortality")
        query = pico_to_query(pico, use_boolean=False)
        assert "adults" in query and "mortality" in query

    def test_pico_to_query_empty(self):
        assert pico_to_query(PICOElements()) == ""

    def test_pico_to_pubmed_query_mesh(self):
        pico = PICOElements(population="diabetes", intervention="metformin")
        query = pico_to_pubmed_query(pico, use_mesh=True)
        assert "[MeSH]" in query

    def test_pico_to_pubmed_query_tiab(self):
        pico = PICOElements(population="diabetes", comparison="placebo")
        query = pico_to_pubmed_query(pico, use_mesh=False)
        assert "[tiab]" in query
