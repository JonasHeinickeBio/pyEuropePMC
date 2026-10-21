"""Unit tests for the sentence-role tool, its sentence splitter and its rules.

``tests/fixtures/rhetoric/labeled.json`` holds 93 sentences from three open-access papers, labelled
by hand (one annotator) in three sets: ``dev`` (used while the rules were written), ``held_out``
(labelled before the rules and run once afterwards) and ``stress`` (24 more, labelled before the
rules were run on them). The tests pin the measured numbers with a margin so that a rule change
that costs accuracy shows up. Nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import collections
import json
from pathlib import Path
from unittest.mock import MagicMock

from mcp_wire import hint, schema_of
import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.mcp import _fulltext as ft, _rhetoric as rh, server as srv
from pyeuropepmc.mcp.server import ToolError

FIXTURES = Path(__file__).parents[2] / "fixtures" / "rhetoric"
LABELED = [
    r
    for r in json.loads((FIXTURES / "labeled.json").read_text(encoding="utf-8"))["sentences"]
    if r["label"] != "excluded"
]


def _run(coro):
    return asyncio.run(coro)


def _predict(row, with_section=True):
    kind = rh.section_kind(row["section"]) if with_section else None
    return rh.classify(row["text"], kind)


class TestSplitter:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("It rained. It stopped.", ["It rained.", "It stopped."]),
            (
                "Smith et al. (2010) showed an effect. The effect was large.",
                ["Smith et al. (2010) showed an effect.", "The effect was large."],
            ),
            (
                "The study by Lee et al. The authors concluded otherwise.",
                ["The study by Lee et al.", "The authors concluded otherwise."],
            ),
            (
                "As reported by Kim et al. [9], the rate was low.",
                ["As reported by Kim et al. [9], the rate was low."],
            ),
            (
                "We grew E. coli and C. albicans, e.g. in vitro. Fig. 2 shows the data.",
                ["We grew E. coli and C. albicans, e.g. in vitro.", "Fig. 2 shows the data."],
            ),
            (
                "Patients were treated vs. placebo. The mean age was 54.3 years.",
                ["Patients were treated vs. placebo.", "The mean age was 54.3 years."],
            ),
            (
                "Doses of 5.2 mg/kg were given (p = 0.05). Then we waited.",
                ["Doses of 5.2 mg/kg were given (p = 0.05).", "Then we waited."],
            ),
            (
                "J. Smith and A. B. Jones measured it. No. 5 failed.",
                ["J. Smith and A. B. Jones measured it.", "No. 5 failed."],
            ),
            (
                "Was it significant? Yes! See Table 1. The rest follows.",
                ["Was it significant?", "Yes!", "See Table 1.", "The rest follows."],
            ),
            (
                'He said "it works." Then it broke (Fig. 3). However, p53 was up.',
                ['He said "it works."', "Then it broke (Fig. 3).", "However, p53 was up."],
            ),
            ("one sentence without a stop", ["one sentence without a stop"]),
            ("", []),
            ("   ", []),
        ],
    )
    def test_scientific_text(self, text, expected):
        assert [s.text for s in rh.split_sentences(text)] == expected

    def test_offsets_index_the_original_text(self):
        text = "  First one.   Second one (Fig. 1).  Third. "
        for sentence in rh.split_sentences(text):
            assert text[sentence.start : sentence.end] == sentence.text
        assert len(rh.split_sentences(text)) == 3

    def test_text_after_a_stop_in_lower_case_or_digits_stays_in_the_sentence(self):
        assert len(rh.split_sentences("It was 3 vs. 5. 12 patients stayed.")) == 1


class TestSectionKind:
    @pytest.mark.parametrize(
        ("path", "kind"),
        [
            ("INTRODUCTION", "introduction"),
            ("1. Introduction", "introduction"),
            ("Background", "introduction"),
            ("MATERIALS AND METHODS/Radiotherapy", "methods"),
            ("2. Materials and Methods/2.5. Assessment Procedure/2.5.1. Pain", "methods"),
            ("Patients and Methods", "methods"),
            ("Methods/Statistical analysis", "methods"),
            ("Results/Yeast carbonic anhydrases are expressed", "results"),
            ("3. Results/3.1. Post-Needling Soreness", "results"),
            ("Findings", "results"),
            ("Results and Discussion", "results_discussion"),
            ("DISCUSSION", "discussion"),
            ("4. Discussion/4.1. Comparison with Previous Studies", "discussion"),
            ("5. Conclusions", "conclusion"),
            ("Conclusion", "conclusion"),
            ("4. Discussion/4.3. Strengths and Limitations", "limitation"),
            ("Limitations of the study", "limitation"),
            ("Something unrelated", None),
            ("", None),
        ],
    )
    def test_kinds(self, path, kind):
        assert rh.section_kind(path) == kind

    def test_a_methods_subsection_called_results_does_not_turn_methods_into_results(self):
        assert rh.section_kind("Methods/Results of pilot work") == "methods"


PASSAGE = [
    ("Introduction", "Asthma affects millions of children worldwide [1]."),
    ("Introduction", "However, the optimal dose remains unclear."),
    ("Methods", "Patients were randomized to two groups."),
    ("Methods", "Blood samples were collected at baseline."),
    ("Results", "Mean pain fell from 6.1 to 3.2 (p < 0.01)."),
    ("Discussion", "Smith et al. reported a similar reduction [4]."),
    ("Discussion", "Our results were in line with these findings."),
    ("Discussion", "This suggests that the effect is mediated by sleep."),
    ("Discussion", "In conclusion, exercise reduced pain."),
    ("Discussion/Limitations", "The small number of patients may limit the conclusion."),
    ("Conclusions", "Exercise is an effective treatment."),
]


class TestRules:
    @pytest.mark.parametrize(
        ("section", "text", "role"),
        [
            ("Introduction", "Asthma affects millions of children worldwide [1].", "background"),
            ("Introduction", "However, the optimal dose remains unclear.", "motivation"),
            ("Introduction", "We aimed to compare two exercise programmes.", "motivation"),
            ("Methods", "Patients were randomized to two groups.", "method"),
            ("Results", "Mean pain fell from 6.1 to 3.2 (p < 0.01).", "result"),
            ("Results", "To assess this, we constructed a deletion strain.", "method"),
            ("Results", "In summary, our data show a conserved factor.", "conclusion"),
            ("Discussion", "Smith et al. reported a similar reduction [4].", "background"),
            ("Discussion", "Our results were in line with these findings.", "claim"),
            ("Discussion", "This suggests that the effect is mediated by sleep.", "claim"),
            ("Discussion", "All groups experienced a decrease in pain.", "result"),
            ("Discussion", "In conclusion, exercise reduced pain.", "conclusion"),
            ("Discussion", "The small number of patients may limit the conclusion.", "limitation"),
            ("Discussion/Limitations", "Pain was assessed by self-report.", "limitation"),
            ("Conclusions", "Exercise is an effective treatment.", "conclusion"),
        ],
    )
    def test_each_role_in_a_fixed_passage(self, section, text, role):
        assert rh.classify(text, rh.section_kind(section))[0] == role

    def test_a_discussion_sentence_without_any_cue_is_unknown_not_a_guess(self):
        assert rh.classify("Regarding the course of PPT, each group differed.", "discussion") == (
            rh.UNKNOWN,
            0.0,
        )

    def test_without_a_section_only_reliable_roles_are_returned(self):
        results = {
            rh.classify(r["text"], None)[0] for r in LABELED if r["label"] in ("result", "claim")
        }
        assert results <= {"background", "method", "conclusion", rh.UNKNOWN}
        assert rh.classify("In conclusion, X works.", None)[0] == "conclusion"
        assert rh.classify("Samples were collected using the kit.", None)[0] == "method"
        assert rh.classify("It has been reported by Lee et al. [3].", None)[0] == "background"

    def test_roles_are_the_documented_set(self):
        assert set(rh.ROLES) == {
            "background",
            "motivation",
            "method",
            "result",
            "claim",
            "limitation",
            "conclusion",
        }
        every = {rh.classify(text, k)[0] for _, text in PASSAGE for k in (None, *rh._KINDS_NAMES)}
        assert every <= {*rh.ROLES, rh.UNKNOWN}


class TestMeasuredAccuracy:
    @staticmethod
    def accuracy(rows, with_section=True):
        return sum(_predict(r, with_section)[0] == r["label"] for r in rows) / len(rows)

    def test_the_labelled_set_is_the_documented_size(self):
        assert len(LABELED) == 93
        assert collections.Counter(r["set"] for r in LABELED) == {
            "dev": 46,
            "held_out": 23,
            "stress": 24,
        }
        assert len({r["paper"] for r in LABELED}) == 3

    @pytest.mark.parametrize(
        ("name", "floor"), [("dev", 0.90), ("held_out", 0.90), ("stress", 0.65)]
    )
    def test_with_sections(self, name, floor):
        rows = [r for r in LABELED if r["set"] == name]
        assert self.accuracy(rows) >= floor

    def test_every_role_the_rules_return_is_precise_enough(self):
        predicted = collections.Counter()
        correct = collections.Counter()
        for row in LABELED:
            role = _predict(row)[0]
            predicted[role] += 1
            correct[role] += role == row["label"]
        for role in rh.ROLES:
            assert predicted[role] >= 3
            assert correct[role] / predicted[role] >= 0.8, role

    def test_without_sections_the_returned_roles_are_precise_and_the_rest_unknown(self):
        predicted = collections.Counter()
        correct = collections.Counter()
        for row in LABELED:
            role = _predict(row, with_section=False)[0]
            predicted[role] += 1
            correct[role] += role == row["label"]
        for role in ("background", "method", "conclusion"):
            assert correct[role] / predicted[role] >= 0.7, role
        assert predicted[rh.UNKNOWN] >= 0.5 * len(LABELED)  # honest, not guessed
        assert set(predicted) <= {"background", "method", "conclusion", rh.UNKNOWN}

    def test_the_older_highlighter_is_not_used_by_default(self):
        from pyeuropepmc.features.fulltext.rhetorical import RhetoricalHighlighter

        old = RhetoricalHighlighter()
        right = sum(old._classify_sentence(r["text"])[0].value == r["label"] for r in LABELED)
        assert right / len(LABELED) < 0.25  # measured 0.14: why the tool has its own rules


JATS = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article"><front>
<journal-meta><journal-title-group><journal-title>Test Journal</journal-title>
</journal-title-group></journal-meta>
<article-meta><article-id pub-id-type="pmid">123</article-id>
<article-id pub-id-type="pmcid">PMC42</article-id><article-id pub-id-type="doi">10.1/test</article-id>
<title-group><article-title>A test article</article-title></title-group>
<abstract><p>Abstract sentence that must not be tagged.</p></abstract></article-meta></front>
<body>
<sec><title>Introduction</title><p>Asthma affects millions of children worldwide [1]. However,
the optimal dose remains unclear.</p></sec>
<sec><title>Methods</title><p>Patients were randomized to two groups. Blood samples were
collected at baseline (Fig. 1 shows the flow).</p></sec>
<sec><title>Results</title><p>Mean pain fell from 6.1 to 3.2 (p &lt; 0.01).</p>
<fig id="F1"><label>Figure 1</label><caption><p>A figure caption sentence.</p></caption></fig>
<table-wrap id="T1"><label>Table 1</label><caption><p>A table caption.</p></caption>
<table><tbody><tr><td>x</td></tr></tbody></table></table-wrap></sec>
<sec><title>Discussion</title><p>Smith et al. reported a similar reduction [4]. Our results were in
line with these findings. This suggests that the effect is mediated by sleep.</p>
<sec><title>Limitations</title><p>The small number of patients may limit the conclusion.</p></sec></sec>
<sec><title>Conclusions</title><p>Exercise is an effective treatment.</p></sec>
<sec><title>Acknowledgments</title><p>We thank the nurses.</p></sec>
<sec><title>Funding</title><p>This work was funded by a grant.</p></sec>
</body><back><ref-list><ref id="B1"><mixed-citation>Ref one. Journal.</mixed-citation></ref></ref-list>
</back></article>"""


@pytest.fixture(scope="module")
def sections():
    return FullTextXMLParser(JATS).get_full_text_sections_structured()


class TestBodySentences:
    def test_front_references_administrative_and_captions_are_left_out(self, sections):
        texts = [s.text for s in rh.body_sentences(sections)]
        joined = " ".join(texts)
        for absent in ("Abstract sentence", "caption", "Ref one", "thank the nurses", "grant"):
            assert absent not in joined
        assert texts[0].startswith("Asthma affects")
        assert texts[-1] == "Exercise is an effective treatment."

    def test_reading_order_sections_and_indices(self, sections):
        sentences = rh.body_sentences(sections)
        assert [s.index for s in sentences] == list(range(len(sentences)))
        assert [s.top for s in sentences][:2] == ["Introduction", "Introduction"]
        assert sentences[-2].section == "Discussion/Limitations"

    def test_the_abbreviation_in_a_method_sentence_does_not_split_it(self, sections):
        methods = [s.text for s in rh.body_sentences(sections) if s.top == "Methods"]
        assert methods == [
            "Patients were randomized to two groups.",
            "Blood samples were collected at baseline (Fig. 1 shows the flow).",
        ]

    @pytest.mark.parametrize(
        "title",
        ["Acknowledgments", "FUNDING", "Conflict of Interest", "Competing interests",
         "Author Contributions", "Supplementary Data", "Supporting Information", "References",
         "Institutional Review Board Statement", "Informed Consent Statement",
         "Data Availability Statement", "Abbreviations"],
    )  # fmt: skip
    def test_administrative_titles(self, title):
        assert rh.is_administrative(title)

    @pytest.mark.parametrize(
        "title", ["Methods", "Ethical approval", "Study design", "Discussion"]
    )
    def test_argument_titles_are_kept(self, title):
        assert not rh.is_administrative(title)


class TestTagging:
    def tagged(self, sections, min_confidence=0.3):
        return rh.tag(rh.body_sentences(sections), min_confidence)

    def test_roles_of_the_fixed_article(self, sections):
        assert [(t.sentence.text, t.role) for t in self.tagged(sections)] == [
            ("Asthma affects millions of children worldwide [1].", "background"),
            ("However, the optimal dose remains unclear.", "motivation"),
            ("Patients were randomized to two groups.", "method"),
            ("Blood samples were collected at baseline (Fig. 1 shows the flow).", "method"),
            ("Mean pain fell from 6.1 to 3.2 (p < 0.01).", "result"),
            ("Smith et al. reported a similar reduction [4].", "background"),
            ("Our results were in line with these findings.", "claim"),
            ("This suggests that the effect is mediated by sleep.", "claim"),
            ("The small number of patients may limit the conclusion.", "limitation"),
            ("Exercise is an effective treatment.", "conclusion"),
        ]

    def test_min_confidence_turns_unsure_sentences_into_unknown(self, sections):
        loose = self.tagged(sections, 0.0)
        strict = self.tagged(sections, 0.95)
        assert all(t.role == rh.UNKNOWN for t in strict)
        assert any(t.role != rh.UNKNOWN for t in loose)
        assert all(0 <= t.confidence <= 1 for t in loose)

    def test_statistics_count_every_sentence(self, sections):
        stats = rh.statistics(self.tagged(sections))
        assert stats["sentences"] == 10
        assert sum(stats["by_role"].values()) == 10
        assert stats["unknown_share"] == 0.0
        assert set(stats["by_section_kind"]) == {
            "introduction",
            "methods",
            "results",
            "discussion",
            "limitation",
            "conclusion",
        }
        assert rh.statistics([]) == {
            "sentences": 0,
            "by_role": {},
            "unknown_share": 0.0,
            "by_section_kind": {},
        }

    def test_fit_never_cuts_a_sentence_and_keeps_at_least_one(self, sections):
        tagged = self.tagged(sections)
        kept, total, truncated = rh.fit(tagged, 100)
        assert truncated and 1 <= len(kept) < len(tagged)
        assert kept == tagged[: len(kept)]  # reading order
        assert total == sum(len(t.sentence.text) for t in tagged)
        first, _, truncated = rh.fit(tagged, 1)
        assert len(first) == 1 and truncated
        everything, _, truncated = rh.fit(tagged, 10_000)
        assert everything == tagged and not truncated
        assert rh.fit([], 100) == ([], 0, False)

    def test_group_orders_roles_and_keeps_reading_order(self, sections):
        grouped = rh.group(self.tagged(sections))
        assert list(grouped) == [
            "background",
            "motivation",
            "method",
            "result",
            "claim",
            "limitation",
            "conclusion",
        ]
        assert [x["text"][:7] for x in grouped["method"]] == ["Patient", "Blood s"]
        assert set(grouped["method"][0]) == {"text", "section", "confidence"}

    def test_validate_roles(self):
        assert rh.validate_roles(None) is None and rh.validate_roles([]) is None
        assert rh.validate_roles([" Method ", "result", "method"]) == ("method", "result")
        assert rh.validate_roles(["unknown"]) == ("unknown",)
        with pytest.raises(ValueError, match=r"unknown role\(s\) \['claims'\].*background"):
            rh.validate_roles(["claims"])


@pytest.fixture(autouse=True)
def _reset_caches():
    caches = (srv._client_cache, srv._fulltext_client_cache, srv._fulltext_xml_cache)
    for cache in caches:
        cache.reset()
    yield
    for cache in caches:
        cache.reset()


@pytest.fixture
def paper(monkeypatch):
    async def locate(pmcid="", pmid="", doi=""):
        return "PMC42", {"pmcid": "PMC42", "pmid": "123", "doi": "10.1/test", "title": "T"}

    async def xml(pmcid):
        return JATS

    monkeypatch.setattr(srv, "_locate_fulltext", locate)
    monkeypatch.setattr(srv, "_fulltext_xml", xml)


class TestTool:
    def test_default_call(self, paper):
        result = _run(srv.tag_paper_sentences(pmcid="PMC42"))
        assert (result["pmcid"], result["pmid"], result["doi"]) == ("PMC42", "123", "10.1/test")
        assert result["title"] == "A test article"
        assert list(result["roles"]) == [
            "background",
            "motivation",
            "method",
            "result",
            "claim",
            "limitation",
            "conclusion",
        ]
        assert result["statistics"]["sentences"] == 10
        assert result["sentences_matching"] == result["sentences_returned"] == 10
        assert result["truncated"] is False and result["method"] == "rules"
        assert result["returned_chars"] == result["total_chars"]
        assert "notes" not in result and "llm" not in result
        assert result["roles"]["result"][0] == {
            "text": "Mean pain fell from 6.1 to 3.2 (p < 0.01).",
            "section": "Results",
            "confidence": 0.8,
        }

    def test_roles_filter_returns_only_those_groups_but_counts_everything(self, paper):
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", roles=["method", "limitation"]))
        assert list(result["roles"]) == ["method", "limitation"]
        assert result["sentences_returned"] == 3
        assert result["statistics"]["sentences"] == 10

    def test_sections_filter(self, paper):
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", sections=["methods"]))
        assert list(result["roles"]) == ["method"]
        assert result["statistics"]["sentences"] == 2

    def test_no_matching_section_names_the_available_ones(self, paper):
        with pytest.raises(ToolError, match=r"No section matches.*Introduction"):
            _run(srv.tag_paper_sentences(pmcid="PMC42", sections=["nonsense"]))

    def test_truncation_is_reported_and_whole_sentences_are_kept(self, paper):
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", max_chars=1000))
        assert result["truncated"] is False  # the fixture is shorter than 1000
        long_xml = JATS.replace("However,", "However, " + "word " * 150 + ".")

        async def xml(pmcid):
            return long_xml

        srv._fulltext_xml = xml  # the autouse fixture restores the module state per test
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", max_chars=1000))
        assert result["truncated"] is True
        assert result["sentences_returned"] < result["sentences_matching"]
        assert result["returned_chars"] <= result["total_chars"]
        for items in result["roles"].values():
            for item in items:
                assert item["text"].endswith((".", ")", "]", "?", "!"))

    def test_min_confidence_is_applied(self, paper):
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", min_confidence=0.95))
        assert list(result["roles"]) == ["unknown"]

    def test_a_paper_without_headings_gets_a_note_and_mostly_unknown(self, paper, monkeypatch):
        headless = """<?xml version="1.0"?><article><front><article-meta>
<article-id pub-id-type="pmcid">PMC42</article-id><title-group><article-title>T</article-title>
</title-group></article-meta></front><body>
<sec><title>Part one</title><p>Samples were collected using the kit. Mean pain fell (p &lt; 0.01).
It has been reported by Lee et al. [3].</p></sec></body></article>"""

        async def xml(pmcid):
            return headless

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        result = _run(srv.tag_paper_sentences(pmcid="PMC42"))
        assert result["notes"] and "no recognisable section headings" in result["notes"][0]
        assert set(result["roles"]) == {"method", "unknown", "background"}

    def test_a_paper_with_no_body_text_is_an_error(self, paper, monkeypatch):
        async def xml(pmcid):
            return JATS.replace("<body>", "<body><!--").replace("</body>", "--></body>")

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        with pytest.raises(ToolError, match="no body text"):
            _run(srv.tag_paper_sentences(pmcid="PMC42"))

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"pmcid": "PMC42", "roles": ["claims"]},
            {"pmcid": "PMC42", "min_confidence": 2},
        ],
    )
    def test_bad_input(self, paper, kwargs):
        if "min_confidence" in kwargs:
            schema = schema_of(
                {t.name: t for t in _run(srv.mcp.list_tools())}["tag_paper_sentences"]
            )
            assert schema["properties"]["min_confidence"]["maximum"] == 1
            return
        with pytest.raises(ToolError, match="unknown role"):
            _run(srv.tag_paper_sentences(**kwargs))

    def test_the_xml_is_downloaded_once_for_several_calls(self, monkeypatch):
        calls = []

        class Client:
            def get_fulltext_content(self, pmcid, fmt):
                calls.append(pmcid)
                return JATS

        async def locate(pmcid="", pmid="", doi=""):
            return "PMC42", {"pmcid": "PMC42"}

        monkeypatch.setattr(srv, "_locate_fulltext", locate)
        srv._fulltext_client_cache.set(Client())
        _run(srv.tag_paper_sentences(pmcid="PMC42"))
        _run(srv.tag_paper_sentences(pmcid="PMC42", roles=["method"]))
        _run(srv.get_paper_fulltext(pmcid="PMC42"))
        assert calls == ["PMC42"]  # the same cached XML serves every tool

    def test_the_tool_is_read_only_open_world_and_bounded(self):
        tools = {t.name: t for t in _run(srv.mcp.list_tools())}
        tool = tools["tag_paper_sentences"]
        assert hint(tool.annotations, "readOnlyHint") is True
        assert hint(tool.annotations, "openWorldHint") is True
        props = schema_of(tool)["properties"]
        assert (props["max_chars"]["minimum"], props["max_chars"]["maximum"]) == (1000, 500000)
        assert props["max_chars"]["default"] == 30000 and props["min_confidence"]["default"] == 0.3

    def test_the_description_states_what_it_does_and_does_not_know(self):
        text = " ".join((srv.tag_paper_sentences.__doc__ or "").split())
        for phrase in ("Rule-based", "unknown", "never cut", "truncated", "Front matter"):
            assert phrase in text


class TestLlm:
    """``use_llm`` goes through the same provider check as the other LLM tools."""

    def test_it_needs_a_provider(self, paper, monkeypatch):
        monkeypatch.setattr(srv, "LLM_AVAILABLE", False)
        with pytest.raises(ToolError, match="LLM tools not available"):
            _run(srv.tag_paper_sentences(pmcid="PMC42", use_llm=True))

    def test_it_asks_only_about_open_sentences_and_keeps_only_known_roles(
        self, paper, monkeypatch
    ):
        extra = JATS.replace(
            "Our results were in",
            "Regarding the course of PPT, each group differed. Our results were in",
        )

        async def xml(pmcid):
            return extra

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        client = MagicMock()
        client.chat.return_value = json.dumps({"role": "result", "confidence": 0.9})
        agent = MagicMock()
        agent.llm_client = client
        monkeypatch.setattr(srv, "LLM_AVAILABLE", True)
        monkeypatch.setattr(srv, "_require_llm", lambda: agent)
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", use_llm=True))
        assert result["method"] == "rules+llm"
        assert result["llm"] == {"asked": 1, "failed": 0}
        assert client.chat.call_count == 1
        regarding = next(
            i
            for items in result["roles"].values()
            for i in items
            if i["text"].startswith("Regarding")
        )
        assert regarding["confidence"] == 0.9
        assert "Regarding" in [i["text"] for i in result["roles"]["result"]][0] or any(
            i["text"].startswith("Regarding") for i in result["roles"]["result"]
        )

    def test_an_unsupported_or_failed_answer_leaves_the_rule_result(self, paper, monkeypatch):
        extra = JATS.replace(
            "Our results were in", "Regarding PPT, each group differed. Our results were in"
        )

        async def xml(pmcid):
            return extra

        monkeypatch.setattr(srv, "_fulltext_xml", xml)
        client = MagicMock()
        client.chat.return_value = json.dumps({"role": "supporting_citation", "confidence": 0.99})
        agent = MagicMock()
        agent.llm_client = client
        monkeypatch.setattr(srv, "LLM_AVAILABLE", True)
        monkeypatch.setattr(srv, "_require_llm", lambda: agent)
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", use_llm=True))
        assert any(i["text"].startswith("Regarding") for i in result["roles"]["unknown"])
        client.chat.side_effect = RuntimeError("down")
        result = _run(srv.tag_paper_sentences(pmcid="PMC42", use_llm=True))
        assert result["llm"] == {"asked": 1, "failed": 1}
        assert "unknown" in result["roles"]


def test_select_sections_is_the_same_helper_as_the_full_text_tool():
    assert ft.select_sections is srv.ft.select_sections
