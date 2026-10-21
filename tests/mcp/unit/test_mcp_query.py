"""Unit tests for the query tools and the pure module behind them (hermetic).

Most expectations below were measured against the live Europe PMC search in October 2026
(hit counts in the comments). The point of the linter is that Europe PMC answers a malformed
query with a different, plausible-looking result instead of an error; the cases are the
malformations that were actually observed to do that.
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import MagicMock

from mcp_wire import hint, schema_of
import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError
from pyeuropepmc.mcp import _query as qm, server as srv
from pyeuropepmc.mcp.server import ToolError


def _run(coro):
    return asyncio.run(coro)


def codes(query):
    return [i.code for i in qm.lint(query).issues]


@pytest.fixture(autouse=True)
def _reset_cache():
    srv._client_cache.reset()
    yield
    srv._client_cache.reset()


class TestLintSilentFailures:
    """Each query here returned a result on Europe PMC, with no error."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            # 7,226 hits; the same query closed finds 26,733
            ("malaria AND (dengue OR zika", ["UNMATCHED_PAREN"]),
            # the stray ")" is ignored
            ("malaria AND dengue)", ["UNMATCHED_PAREN"]),
            # "malaria AND" finds exactly what "malaria" finds
            ("malaria AND", ["TRAILING_OPERATOR"]),
            ("AND malaria", ["LEADING_OPERATOR"]),
            ("malaria AND AND dengue", ["DOUBLE_OPERATOR"]),
            ("malaria OR OR dengue", ["DOUBLE_OPERATOR"]),
            ("malaria AND ()", ["EMPTY_GROUP"]),
            # 0 hits, no error
            ("FOO:malaria", ["UNKNOWN_FIELD"]),
            ("HAS_FT:true", ["BAD_FLAG_VALUE"]),
            ("OPEN_ACCESS:yes", ["BAD_FLAG_VALUE"]),
            ("FIRST_PDATE:[2020 TO ]", ["BAD_RANGE"]),
            ("FIRST_PDATE:[2023 TO 2020]", ["BAD_RANGE"]),
            ("FIRST_PDATE:[20-20 TO 2023]", ["BAD_RANGE"]),
            # HTTP 503 from Europe PMC
            ("*malaria", ["LEADING_WILDCARD"]),
            # returns just the records of "malaria"
            ("malaria AND dengue OR zika", ["MIXED_OPERATORS"]),
            ("malaria OR dengue AND zika", ["MIXED_OPERATORS"]),
        ],
    )
    def test_the_observed_cases(self, query, expected):
        assert codes(query) == expected

    @pytest.mark.parametrize(
        "query",
        [
            "malaria AND dengue",
            "malaria dengue",
            "malaria AND (dengue OR zika)",
            "(malaria AND dengue) OR zika",
            "malaria AND dengue NOT zika",
            "malaria AND NOT dengue",
            "malaria -dengue",
            "TITLE:*malaria",  # 66,608 hits: a wildcard behind a field is fine
            "mal*",
            "mal?ria",
            "title:crispr",  # lower-case field names work
            'AUTH:"Smith J" AND PUB_YEAR:[2020 TO 2023]',
            "FIRST_PDATE:[2020-06 TO 2020-12]",
            "FIRST_PDATE:[* TO 2020]",
            "CITED:[100 TO *]",
            "OPEN_ACCESS:y AND HAS_FT:Y AND IN_EPMC:n",
            "TITLE:(crispr OR cas9)",
            "DOI:10.1186/1479-7364-2-2-138",
            "CITES:22745249_med",
            "MESH:Neoplasms AND AUTHOR:smith AND SUBSET:Preprints",
        ],
    )
    def test_valid_queries_have_no_issues(self, query):
        assert codes(query) == []

    def test_a_valid_query_is_valid_and_normalised(self):
        result = qm.lint("title:crispr  and ( a OR   b )")
        assert not result.errors
        assert result.normalized == "TITLE:crispr AND (a OR b)"
        assert [i.code for i in result.warnings] == ["LOWERCASE_OPERATOR"]


class TestTokenizerRobustness:
    """Stray brackets once sent the tokenizer into an endless loop."""

    @pytest.mark.parametrize(
        "query", ["a]", "]", "}", "x ] y", "PUB_YEAR:2020 TO 2021]", "a } b", "]]]", "{a}"]
    )
    def test_stray_closers_terminate(self, query):
        qm.lint(query)  # must return

    def test_every_character_makes_progress(self):
        chars = "()[]{}\"':*?- \t\nAaZ09_/.~^"
        for a in chars:
            for b in chars:
                qm.lint(a + b)

    def test_pubmed_field_tags_are_called_out(self):
        result = qm.lint("crispr[ti] AND 2020[dp]")
        assert [i.code for i in result.warnings] == ["BARE_RANGE", "BARE_RANGE"]
        assert "TITLE:x" in result.warnings[0].message


class TestLintDetails:
    def test_positions_point_at_the_problem(self):
        result = qm.lint("malaria AND (dengue OR zika")
        assert result.errors[0].position == 12
        assert qm.lint("a AND AND b").errors[0].position == 6
        assert qm.lint("x HAS_FT:true").errors[0].position == 9

    def test_errors_withhold_the_normalised_form(self):
        assert qm.lint("a AND").normalized is None

    @pytest.mark.parametrize(
        ("query", "hint"),
        [("TTILE:crispr", "TITLE"), ("JOURNL:nature", "JOURNAL"), ("FOOBARBAZ:x", None)],
    )
    def test_unknown_fields_get_a_suggestion_when_one_is_close(self, query, hint):
        issue = qm.lint(query).issues[0]
        assert issue.code == "UNKNOWN_FIELD"
        assert issue.suggestion == hint
        assert (hint is None) or (hint in issue.message)

    def test_empty_queries(self):
        for query in ("", "   ", "()", "AND"):
            assert any(i.severity == "error" for i in qm.lint(query).issues), query

    def test_missing_field_value(self):
        assert "MISSING_FIELD_VALUE" in codes("TITLE: AND malaria")
        assert "MISSING_FIELD_VALUE" in codes("malaria AND TITLE:")

    def test_unclosed_quote_and_range(self):
        assert codes('TITLE:"malaria') == ["UNCLOSED_QUOTE"]
        assert "UNCLOSED_RANGE" in codes("FIRST_PDATE:[2020 TO 2023")

    def test_escaped_quote_inside_a_phrase(self):
        assert codes(r'TITLE:"say \"hi\" now" AND x') == []

    def test_leading_not_is_a_warning_not_an_error(self):
        result = qm.lint("NOT malaria")
        assert not result.errors
        assert [i.code for i in result.warnings] == ["LEADING_NOT"]

    def test_lowercase_operators_are_read_but_flagged(self):
        result = qm.lint("malaria and dengue")
        assert not result.errors
        assert result.normalized == "malaria AND dengue"
        assert [i.code for i in result.warnings] == ["LOWERCASE_OPERATOR"]

    def test_mixing_is_checked_per_group(self):
        assert codes("(a AND b) OR (c AND d)") == []
        assert codes("x AND (a OR b AND c)") == ["MIXED_OPERATORS"]

    def test_two_terms_side_by_side_count_as_and_for_mixing(self):
        assert codes("a b OR c") == ["MIXED_OPERATORS"]

    def test_group_values_are_checked(self):
        assert codes("TITLE:(a OR FOO:b)") == ["UNKNOWN_FIELD"]
        assert codes("TITLE:(a AND)") == ["TRAILING_OPERATOR"]

    def test_a_url_is_not_a_field(self):
        assert codes("https://example.org/x") == []

    @pytest.mark.parametrize(
        ("query", "code"),
        [
            ("PUB_YEAR:[2020 TO 2021-01]", "BAD_RANGE"),
            ("PUB_YEAR:[20 TO 2021]", "BAD_RANGE"),
            ("FIRST_PDATE:[2020-13 TO 2021]", "BAD_RANGE"),
            ("FIRST_PDATE:[2021-02-30 TO 2021-03-01]", "BAD_RANGE"),
            ("CITED:[many TO *]", "BAD_RANGE"),
            ("FIRST_PDATE:[2020]", "BAD_RANGE"),
        ],
    )
    def test_range_bounds(self, query, code):
        found = codes(query)
        if code is None:
            return
        assert code in found

    def test_a_month_bound_covers_the_whole_month(self):
        assert codes("FIRST_PDATE:[2020-06 TO 2020-06]") == []
        assert codes("FIRST_PDATE:[2020-06-15 TO 2020-06]") == []
        assert codes("FIRST_PDATE:[2020-07 TO 2020-06-30]") == ["BAD_RANGE"]

    def test_every_issue_serialises(self):
        for issue in qm.lint("a AND (b OR FOO:c").issues:
            data = issue.to_dict()
            assert set(data) == {"severity", "code", "message", "position", "suggestion"}


class TestFieldLists:
    def test_the_snapshot_matches_the_library_where_they_overlap(self):
        from pyeuropepmc.features.literature.query_builder import FIELD_METADATA

        library = {api for api, _ in FIELD_METADATA.values()}
        # fields the library names that Europe PMC does not accept (0 hits in testing)
        not_searchable = {"HAS_TEXT", "PAGE_INFO", "HAS_CRD", "CRD_LINKS", "EMBARGOED_MAN"}
        unexpected = {f for f in library - qm.KNOWN_FIELDS if re.fullmatch(r"[A-Z][A-Z_0-9]*", f)}
        assert unexpected - not_searchable == set()

    def test_flag_and_date_fields_are_derived(self):
        assert {"HAS_FT", "OPEN_ACCESS", "IN_EPMC", "AUTH_MAN"} <= qm.FLAG_FIELDS
        assert {"FIRST_PDATE", "E_PDATE", "FT_CDATE_D", "UPDATE_DATE"} <= qm.DATE_FIELDS
        assert "PUB_YEAR" not in qm.DATE_FIELDS


class TestTranslatePubmed:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            # PubMed counts matched Europe PMC (MED) within a few percent when this was checked
            ("TITLE:crispr AND PUB_YEAR:[2020 TO 2022]", "crispr[ti] AND 2020:2022[dp]"),
            ('AUTH:"Doudna JA" AND PUB_YEAR:2020', '"Doudna JA"[au] AND 2020[dp]'),
            ('TITLE:malaria AND JOURNAL:"Lancet"', 'malaria[ti] AND "Lancet"[ta]'),
            ("TITLE:(crispr OR cas9) AND PUB_YEAR:2021", "(crispr[ti] OR cas9[ti]) AND 2021[dp]"),
            ("DOI:10.1186/1479-7364-2-2-138", "10.1186/1479-7364-2-2-138[doi]"),
            ("EXT_ID:16004729", "16004729[pmid]"),
            ("ISSN:1471-2164 AND PUB_YEAR:2019", "1471-2164[is] AND 2019[dp]"),
            ('AFF:"Helmholtz"', '"Helmholtz"[ad]'),
            ("ABSTRACT:x AND LANG:eng", "x[ab] AND eng[la]"),
            ("TITLE_ABS:crispr", "crispr[tiab]"),
            ("KW:crispr OR PUB_TYPE:review", "crispr[ot] OR review[pt]"),
            ("malaria AND dengue", "malaria AND dengue"),
            ("malaria -dengue", "malaria NOT dengue"),
            ("title:crispr", "crispr[ti]"),
        ],
    )
    def test_mapped_fields(self, source, expected):
        translation = qm.translate_pubmed(source)
        assert translation.query == expected
        assert translation.exact is True
        assert translation.dropped == []

    def test_dates(self):
        t = qm.translate_pubmed("TITLE:zika AND FIRST_PDATE:[2016-01-01 TO 2016-12-31]")
        assert t.query == "zika[ti] AND 2016/01/01:2016/12/31[dp]"
        assert t.exact is False  # FIRST_PDATE is not PubMed's [dp]
        assert any("FIRST_PDATE" in w for w in t.warnings)
        assert qm.translate_pubmed("PUB_YEAR:[2020 TO *]").query == "2020:3000[dp]"
        assert qm.translate_pubmed("PUB_YEAR:[* TO 2020]").query == "1800:2020[dp]"
        assert qm.translate_pubmed("PUB_YEAR:[2020 TO 2021]").exact is True

    def test_open_access_is_an_approximation(self):
        t = qm.translate_pubmed("TITLE:covid AND OPEN_ACCESS:y")
        assert t.query == "covid[ti] AND free full text[sb]"
        assert t.exact is False
        assert any("free full text" in w for w in t.warnings)

    def test_has_abstract(self):
        assert qm.translate_pubmed("x AND HAS_ABSTRACT:y").query == "x AND hasabstract"
        assert qm.translate_pubmed("x AND HAS_ABSTRACT:n").query == "x AND NOT hasabstract"

    def test_mesh_is_flagged_as_not_the_same_index(self):
        t = qm.translate_pubmed('MESH:"Neoplasms"')
        assert t.query == '"Neoplasms"[mh]'
        assert t.exact is False
        assert "172,000" in t.warnings[0]

    def test_src_med_is_implied_by_pubmed(self):
        t = qm.translate_pubmed("TITLE:x AND SRC:MED")
        assert t.query == "x[ti]"
        assert t.exact is True
        assert t.dropped == []
        assert qm.translate_pubmed("TITLE:x AND SRC:PPR").exact is False

    def test_a_dropped_term_is_named_and_the_direction_is_given(self):
        t = qm.translate_pubmed("TITLE:crispr AND CITES:22745249_MED AND HAS_FT:y")
        assert t.query == "crispr[ti]"
        assert t.dropped == ["CITES:22745249_MED", "HAS_FT:y"]
        assert t.exact is False
        assert all("broader" in w for w in t.warnings)

    def test_dropping_from_an_or_narrows(self):
        t = qm.translate_pubmed("AUTH:smith OR CITED:[5 TO *]")
        assert t.query == "smith[au]"
        assert "narrower" in t.warnings[0]

    @pytest.mark.parametrize(
        ("source", "query", "direction"),
        [
            ("CITES:1_MED OR AUTH:smith", "smith[au]", "narrower"),  # first clause of an OR
            ("AUTH:smith OR CITES:1_MED", "smith[au]", "narrower"),
            ("CITES:1_MED AND AUTH:smith", "smith[au]", "broader"),
            ("AUTH:smith AND CITES:1_MED", "smith[au]", "broader"),
            ("AUTH:smith AND NOT HAS_FT:y", "smith[au]", "broader"),  # an exclusion goes
            ("(CITES:1_MED OR x) AND y", "(x) AND y", "narrower"),
        ],
    )
    def test_the_direction_of_a_dropped_clause(self, source, query, direction):
        t = qm.translate_pubmed(source)
        assert t.query == query
        assert t.warnings[0].endswith(f"is {direction} than the original.")

    def test_no_direction_is_claimed_inside_a_negated_group(self):
        t = qm.translate_pubmed("a AND NOT (b OR HAS_FT:y)")
        assert t.query == "a AND NOT (b)"
        assert "inside a NOT" in t.warnings[0]
        assert "not stated" in t.warnings[0]
        assert "is broader than" not in t.warnings[0]
        assert "is narrower than" not in t.warnings[0]

    def test_an_exclusive_range_is_not_an_exact_translation(self):
        t = qm.translate_pubmed("PUB_YEAR:{2020 TO 2022}")
        assert t.query == "2020:2022[dp]"
        assert t.exact is False
        assert "excludes its bounds" in t.warnings[0]
        assert qm.translate_pubmed("PUB_YEAR:[2020 TO 2022]").exact is True

    def test_dropping_the_first_clause_keeps_a_following_not(self):
        t = qm.translate_pubmed("CITES:1_MED AND NOT TITLE:x")
        assert t.query == "NOT x[ti]"

    def test_nothing_translatable(self):
        t = qm.translate_pubmed("HAS_FT:y")
        assert t.query is None
        assert t.exact is False
        assert any("Nothing" in w for w in t.warnings)

    def test_not_with_a_date_is_flagged(self):
        t = qm.translate_pubmed('TITLE:"cancer" AND NOT TITLE:"breast" AND PUB_YEAR:2020')
        assert t.query == '"cancer"[ti] AND NOT "breast"[ti] AND 2020[dp]'
        assert t.exact is False
        assert any("NOT combined with a date" in w for w in t.warnings)
        assert qm.translate_pubmed("TITLE:a AND NOT TITLE:b").exact is True

    def test_a_query_with_errors_is_refused_with_its_issues(self):
        with pytest.raises(qm.QueryProblem) as raised:
            qm.translate_pubmed("malaria AND (dengue")
        assert raised.value.issues[0].code == "UNMATCHED_PAREN"


class TestBuild:
    def test_filters_in_a_fixed_order(self):
        assert qm.filter_clauses(
            date_from="2020",
            date_to="2023-06",
            open_access=True,
            has_fulltext=True,
            source="med",
            cites="22745249",
        ) == [
            "FIRST_PDATE:[2020 TO 2023-06]",
            "OPEN_ACCESS:y",
            "HAS_FT:y",
            "SRC:MED",
            "CITES:22745249_med",
        ]

    def test_apply_filters_keeps_the_established_shape(self):
        assert qm.apply_filters("malaria") == "malaria"
        assert (
            qm.apply_filters("malaria OR dengue", date_from="2020", open_access=True)
            == "(malaria OR dengue) AND FIRST_PDATE:[2020 TO *] AND OPEN_ACCESS:y"
        )

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"date_from": "2020/01"}, "date_from must be"),
            ({"date_to": "2020-13"}, "date_to must be"),
            ({"date_from": "2021", "date_to": "2020"}, "is after date_to"),
            ({"source": "MED OR"}, "source must be"),
            ({"cites": "PMC3525259"}, "cites must be a PMID"),
            ({"cites": "abc"}, "cites must be a PMID"),
        ],
    )
    def test_bad_filters(self, kwargs, message):
        with pytest.raises(qm.QueryProblem, match=message):
            qm.filter_clauses(**kwargs)

    def test_terms_phrases_and_expressions(self):
        query, _ = qm.build(["heart attack", "TITLE:crispr", "a OR b"], ["x", "y z"], ["bad"])
        assert query == (
            '"heart attack" AND TITLE:crispr AND (a OR b) AND (x OR "y z") AND NOT bad'
        )
        assert not qm.lint(query).errors

    def test_not_comes_last_so_it_is_never_a_leading_not(self):
        query, _ = qm.build([], [], ["x"], open_access=True)
        assert query == "OPEN_ACCESS:y AND NOT x"
        assert codes(query) == []

    def test_a_term_with_syntax_in_it_is_kept_as_written(self):
        query, _ = qm.build(['"two words"', "AUTH:smith"], [], [])
        assert query == '"two words" AND AUTH:smith'

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (([], [], []), "at least one of"),
            (([], [], ["x"]), "none_of alone"),
            ((["  "], [], []), "empty search term"),
        ],
    )
    def test_input_that_asks_for_nothing(self, args, message):
        with pytest.raises(qm.QueryProblem, match=message):
            qm.build(*args)

    def test_the_explanation(self):
        _, text = qm.build(
            ["a"], ["b", "c"], ["d"], date_from="2020", open_access=True, source="med"
        )
        assert text == (
            "Records that contain all of: a; contain at least one of: b, c; contain none of: d; "
            "were first published 2020 to today; are open access; come from source MED."
        )

    def test_the_search_filter_helper_is_the_same_code(self):
        assert srv._with_filters(
            "x",
            date_from="2020",
            date_to="2021",
            open_access=True,
            has_fulltext=True,
            source="PMC",
        ) == qm.apply_filters(
            "x",
            date_from="2020",
            date_to="2021",
            open_access=True,
            has_fulltext=True,
            source="PMC",
        )
        with pytest.raises(ToolError, match="date_from"):
            srv._with_filters("x", date_from="soon")


class TestValidateQueryTool:
    def test_valid(self):
        out = _run(srv.validate_query("title:crispr and (a OR b)"))
        assert out["valid"] is True
        assert out["problems"] == []
        assert out["normalized"] == "TITLE:crispr AND (a OR b)"
        assert out["warnings"][0]["code"] == "LOWERCASE_OPERATOR"

    def test_invalid(self):
        out = _run(srv.validate_query("malaria AND (dengue OR"))
        assert out["valid"] is False
        assert {p["code"] for p in out["problems"]} == {"UNMATCHED_PAREN", "TRAILING_OPERATOR"}
        assert out["normalized"] is None


class TestBuildQueryTool:
    def test_builds_and_explains(self):
        out = _run(
            srv.build_query(
                all_of=["heart attack"], date_from="2020", open_access=True, cites="22745249"
            )
        )
        assert out["query"] == (
            '"heart attack" AND FIRST_PDATE:[2020 TO *] AND OPEN_ACCESS:y AND CITES:22745249_med'
        )
        assert out["explanation"].startswith("Records that contain all of: heart attack")
        assert out["warnings"] == []

    def test_a_term_that_breaks_the_query_is_refused(self):
        with pytest.raises(ToolError, match="not valid"):
            _run(srv.build_query(all_of=['TITLE:"unclosed']))

    def test_problems_become_tool_errors(self):
        with pytest.raises(ToolError, match="at least one of"):
            _run(srv.build_query())
        with pytest.raises(ToolError, match="cites must be a PMID"):
            _run(srv.build_query(all_of=["x"], cites="PMC1"))

    def test_the_tool_is_local_and_read_only(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        for name in ("validate_query", "build_query", "translate_query"):
            assert hint(tools[name].annotations, "readOnlyHint") is True
            assert hint(tools[name].annotations, "openWorldHint") is False


class TestTranslateQueryTool:
    def test_pubmed(self):
        out = _run(srv.translate_query("TITLE:crispr AND CITES:1_MED"))
        assert out["target"] == "pubmed"
        assert out["query"] == "crispr[ti]"
        assert out["exact"] is False
        assert out["dropped"] == ["CITES:1_MED"]

    def test_free_text_targets_are_never_exact(self):
        out = _run(srv.translate_query('TITLE:crispr AND (cas9 OR "base editing")', "arxiv"))
        assert out["query"] == 'all:"crispr cas9 base editing"'
        assert out["exact"] is False
        assert "free text" in out["warnings"][0]

    def test_a_query_with_errors_is_refused(self):
        with pytest.raises(ToolError, match="Fix the query first"):
            _run(srv.translate_query("malaria AND"))


def _search(records_by_query):
    """A search_all that answers from a function of the query text."""
    client = MagicMock()

    def search_all(query, **kwargs):
        return records_by_query(query)

    client.search_all.side_effect = search_all
    client.get_hit_count.return_value = 12345
    srv._client_cache.set(client)
    return client


def _known(*pmids):
    return {p: {"id": p, "source": "MED", "pmid": p} for p in pmids}


class TestEvaluateQueryTool:
    def _answers(self, known, matching):
        def records(query):
            asked = [p for p in known if f"EXT_ID:{p} " in query]
            if not query.startswith("((EXT_ID"):  # "(query) AND (seeds)", not just the seeds
                asked = [p for p in asked if p in matching]
            return [known[p] for p in asked]

        return records

    def test_recall_misses_and_excluded_hits(self):
        known = _known("1", "2", "3", "10", "11")
        _search(self._answers(known, matching={"1", "2", "10"}))

        out = _run(
            srv.evaluate_query("malaria", ["1", "2", "3", "999"], excluded_pmids=["10", "11"])
        )

        assert out["total_hits"] == 12345
        assert out["included"] == {
            "known": 3,
            "matched": 2,
            "recall": pytest.approx(2 / 3),
            "missed": ["3"],
            "unknown_to_europepmc": ["999"],
        }
        assert out["excluded"]["matched_pmids"] == ["10"]
        assert out["precision_on_seeds"] == pytest.approx(2 / 3)
        assert out["f1_on_seeds"] == pytest.approx(2 / 3)

    def test_without_excluded_papers_precision_is_one_when_anything_matches(self):
        known = _known("1", "2")
        _search(self._answers(known, matching={"1"}))
        out = _run(srv.evaluate_query("x", ["1", "2"]))
        assert out["excluded"]["known"] == 0
        assert out["precision_on_seeds"] == 1.0
        assert out["f1_on_seeds"] == pytest.approx(2 * 1.0 * 0.5 / 1.5)

    def test_a_query_that_finds_nothing(self):
        known = _known("1", "2")
        _search(self._answers(known, matching=set()))
        out = _run(srv.evaluate_query("x", ["1", "2"]))
        assert out["included"]["recall"] == 0.0
        assert out["precision_on_seeds"] is None
        assert out["f1_on_seeds"] is None

    def test_seeds_are_checked_in_chunks_of_fifty(self):
        pmids = [str(i) for i in range(1, 121)]
        client = _search(self._answers(_known(*pmids), matching=set(pmids)))
        out = _run(srv.evaluate_query("x", pmids))
        assert out["included"]["matched"] == 120
        # 3 chunks, each asked twice (known, matched)
        assert client.search_all.call_count == 6
        assert all(c.kwargs["resultType"] == "idlist" for c in client.search_all.call_args_list)

    def test_duplicates_are_counted_once(self):
        known = _known("1")
        _search(self._answers(known, matching={"1"}))
        out = _run(srv.evaluate_query("x", ["1", "1", " 1 "]))
        assert out["included"]["known"] == 1

    def test_unknown_seeds_do_not_count_against_recall(self):
        _search(lambda query: [])
        out = _run(srv.evaluate_query("x", ["5", "6"]))
        assert out["included"]["recall"] is None
        assert out["included"]["unknown_to_europepmc"] == ["5", "6"]

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"query": "malaria AND"}, "Fix the query first"),
            ({"query": "x", "included_pmids": ["PMC1"]}, "PMIDs"),
            ({"query": "x", "included_pmids": ["1"], "excluded_pmids": ["a"]}, "excluded_pmids"),
        ],
    )
    def test_refused_input_never_reaches_europepmc(self, kwargs, message):
        client = _search(lambda q: [])
        kwargs.setdefault("included_pmids", ["1"])
        with pytest.raises(ToolError, match=message):
            _run(srv.evaluate_query(**kwargs))
        client.search_all.assert_not_called()

    def test_a_europepmc_failure_is_a_tool_error(self):
        client = MagicMock()
        client.search_all.side_effect = APIClientError(ErrorCodes.NET001, {"error": "boom"})
        srv._client_cache.set(client)
        with pytest.raises(ToolError):
            _run(srv.evaluate_query("x", ["1"]))

    def test_warnings_about_the_query_are_passed_on(self):
        _search(lambda q: [])
        out = _run(srv.evaluate_query("a AND b OR c", ["1"]))
        assert out["warnings"][0]["code"] == "MIXED_OPERATORS"

    def test_the_seed_lists_are_bounded_in_the_schema(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        props = schema_of(tools["evaluate_query"])["properties"]
        assert (props["included_pmids"]["minItems"], props["included_pmids"]["maxItems"]) == (
            1,
            200,
        )
