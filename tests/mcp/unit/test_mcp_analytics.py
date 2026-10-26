"""Unit tests for ``analyze_search``: aggregates over a search, each labelled exact or sample.

Nothing here touches the network. A fake client answers hit counts by evaluating the clauses
the tool adds (``FIRST_PDATE``, ``OPEN_ACCESS``, ``CITED``) against a fixed record set, so the
counted metrics are checked against what the records say, and ``search_all`` returns slices of
that set like the real one.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import SearchError
from pyeuropepmc.mcp import _analytics as am, server as srv
from pyeuropepmc.mcp.server import ToolError

pd = pytest.importorskip("pandas")


def _run(coro):
    return asyncio.run(coro)


def _record(
    ident: str,
    date: str,
    journal: str,
    authors: str,
    pub_type: str,
    open_access: str,
    cited: int,
    affiliation: str = "",
    funders: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": ident,
        "firstPublicationDate": date,
        "pubYear": date[:4] or None,
        "journalTitle": journal,
        "authorString": authors,
        "pubType": pub_type,
        "isOpenAccess": open_access,
        "citedByCount": cited,
        "affiliation": affiliation,
        "grantsList": {"grant": [{"agency": f} for f in funders]},
    }


RECORDS = [
    _record("A", "2019-05-01", "Lancet", "Smith J, Doe A", "Journal Article", "Y", 10,
            "University of Oxford, Oxford, UK.", ("Wellcome Trust",)),
    _record("B", "2019-11-02", "Lancet", "Smith J", "Review", "N", 0,
            "Harvard Medical School, Boston, USA."),
    _record("C", "2020-01-03", "BMJ", "Doe A, Roe B", "Journal Article", "Y", 4,
            "Institut Pasteur, Paris, France.; Univ Oxford, Oxford, U.K.",
            ("Wellcome Trust", "NIH")),
    _record("D", "2021-03-04", "BMJ", "Roe B", "Journal Article", "Y", 2,
            "Univ Cape Town, Cape Town, South Africa."),
    _record("E", "2021-07-08", "PLoS One", "Lee K", "Review", "N", 0),
    _record("F", "", "PLoS One", "Lee K, Kim H", "Journal Article", "N", 1),
]  # fmt: skip


def _clause_range(query: str) -> list[tuple[int | None, int | None]]:
    return [
        (None if lo == "*" else int(lo), None if hi == "*" else int(hi))
        for lo, hi in re.findall(r"FIRST_PDATE:\[(\S+) TO (\S+)\]", query)
    ]


def _matches(record: dict[str, Any], query: str) -> bool:
    """Does the record satisfy every clause the tool added? (The base query matches all.)"""
    year = int(record["pubYear"]) if record["pubYear"] else None
    for lo, hi in _clause_range(query):
        if year is None or (lo is not None and year < lo) or (hi is not None and year > hi):
            return False
    if "OPEN_ACCESS:y" in query and record["isOpenAccess"] != "Y":
        return False
    return all(
        record["citedByCount"] >= int(n) for n in re.findall(r"CITED:\[(\d+) TO \*\]", query)
    )


class FakeClient:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.counted: list[str] = []
        self.searched: list[tuple[str, dict[str, Any]]] = []

    def close(self) -> None:
        pass

    def get_hit_count(self, query: str, **kwargs: Any) -> int:
        self.counted.append(query)
        return sum(_matches(r, query) for r in self.records)

    def search_all(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.searched.append((query, kwargs))
        rows = [r for r in self.records if _matches(r, query)]
        sort = kwargs.get("sort", "")
        if sort.startswith("FIRST_PDATE_D"):
            rows = sorted(
                (r for r in rows if r["firstPublicationDate"]),
                key=lambda r: r["firstPublicationDate"],
                reverse=sort.endswith("desc"),
            )
        return [dict(r) for r in rows[: kwargs["max_results"]]]


@pytest.fixture(autouse=True)
def _fresh_client():
    srv._client_cache.reset()
    yield
    srv._client_cache.reset()


@pytest.fixture
def client(monkeypatch) -> FakeClient:
    fake = FakeClient(RECORDS)
    srv._client_cache.set(fake)
    monkeypatch.setattr(srv, "_new_counting_client", lambda: fake)  # the workers' clients
    return fake


def _analyze(**kwargs: Any) -> dict[str, Any]:
    return _run(srv.analyze_search(**{"query": "anything", **kwargs}))


class TestChecks:
    def test_all_metrics_by_default_and_repeats_dropped(self):
        assert am.check_metrics(None) == list(am.METRICS)
        assert am.check_metrics([]) == list(am.METRICS)
        assert am.check_metrics(["types", "by_year", "types"]) == ["types", "by_year"]

    def test_an_unknown_metric_is_named(self):
        with pytest.raises(ValueError, match="'journal'"):
            am.check_metrics(["by_year", "journal"])

    def test_every_metric_is_either_counted_or_read_off_records(self):
        assert set(am.METRICS) == am.COUNTED | am.FROM_RECORDS
        assert not am.COUNTED & am.FROM_RECORDS
        assert am.NEEDS_CORE <= am.FROM_RECORDS


class TestCounting:
    def test_years_open_access_and_citation_thresholds_match_the_records(self, client):
        out = _analyze(metrics=["by_year", "open_access"], limit=5)["metrics"]
        assert out["by_year"]["basis"] == "exact"
        assert out["by_year"]["years"] == [
            {"year": 2019, "count": 2},
            {"year": 2020, "count": 1},
            {"year": 2021, "count": 2},
        ]
        assert out["by_year"]["undated"] == 1  # F has no first publication date
        assert out["by_year"]["before"] is None and out["by_year"]["after"] is None
        assert out["open_access"] == {
            "basis": "exact",
            "open_access": 3,
            "not_open_access": 3,
            "share_open_access": 0.5,
        }

    def test_years_plus_undated_are_the_hit_count(self, client):
        result = _analyze(metrics=["by_year"])
        year = result["metrics"]["by_year"]
        assert sum(y["count"] for y in year["years"]) + year["undated"] == result["hit_count"]

    def test_one_count_per_year_and_none_for_records(self, client):
        _analyze(metrics=["by_year"])
        year_queries = [q for q in client.counted if "FIRST_PDATE:[20" in q]
        assert sorted(year_queries) == [
            f"(anything) AND FIRST_PDATE:[{y} TO {y}]" for y in (2019, 2020, 2021)
        ]
        assert [kw["sort"] for _, kw in client.searched] == [
            "FIRST_PDATE_D asc",
            "FIRST_PDATE_D desc",
        ]

    def test_a_long_span_counts_the_latest_years_and_one_bucket_before(self):
        asked: list[str] = []

        def count(query: str) -> int:
            asked.append(query)
            return 1

        out = am.year_counts(
            "q", 500, count, lambda _q, order: 1900 if order == "asc" else 2025, this_year=2025
        )
        assert len(out["years"]) == am.MAX_YEARS
        assert out["years"][0]["year"] == 2025 - am.MAX_YEARS + 1
        assert out["before"] == {"year": 2025 - am.MAX_YEARS, "count": 1}
        assert "(q) AND FIRST_PDATE:[* TO 1965]" in asked
        assert out["undated"] == 500 - am.MAX_YEARS - 1

    def test_records_dated_in_the_future_do_not_push_the_window_out_of_range(self):
        """Live: the newest record of a search for 'cancer' was dated 2096."""
        asked: list[str] = []

        def count(query: str) -> int:
            asked.append(query)
            return 7 if "TO *]" in query and "2027" in query else 1

        out = am.year_counts(
            "q", 100, count, lambda _q, order: 1900 if order == "asc" else 2096, this_year=2026
        )
        assert out["years"][-1]["year"] == 2026 and len(out["years"]) == am.MAX_YEARS
        assert out["after"] == {"year": 2027, "count": 7}
        assert "(q) AND FIRST_PDATE:[2027 TO *]" in asked
        assert not any("2096" in q for q in asked)
        parts = sum(y["count"] for y in out["years"]) + out["before"]["count"] + 7
        assert out["undated"] == 100 - parts

    def test_a_result_set_dated_only_in_the_future_is_one_bucket(self):
        out = am.year_counts("q", 9, lambda _q: 9, lambda _q, _o: 2090, this_year=2026)
        assert out["years"] == [] and out["after"] == {"year": 2027, "count": 9}
        assert out["undated"] == 0

    def test_a_young_result_set_has_no_buckets(self):
        out = am.year_counts(
            "q", 10, lambda _q: 5, lambda _q, o: 2024 if o == "asc" else 2025, this_year=2026
        )
        assert [y["year"] for y in out["years"]] == [2024, 2025]
        assert out["before"] is None and out["after"] is None

    def test_no_records_means_no_years(self):
        out = am.year_counts("q", 0, lambda _q: 0, lambda _q, _o: None)
        assert out == {"basis": "exact", "years": [], "before": None, "after": None, "undated": 0}

    def test_citation_thresholds_are_counted_and_exact(self, client):
        entry = _analyze(metrics=["citations"], limit=5)["metrics"]["citations"]
        assert entry["thresholds"] == {
            "basis": "exact",
            "at_least": {"1": 4, "10": 1, "100": 0, "1000": 0},
            "never_cited": 2,
        }

    def test_counted_metrics_need_no_analytics_extra(self, client, monkeypatch):
        monkeypatch.setattr(srv, "ANALYTICS_AVAILABLE", False)
        out = _analyze(metrics=["by_year", "open_access"])["metrics"]
        assert set(out) == {"by_year", "open_access"}
        assert client.searched  # only the two year-edge lookups
        assert all(kw["max_results"] == 1 for _, kw in client.searched)


class TestSampleMetrics:
    def test_each_metric_from_a_fixed_record_set(self, client):
        out = _analyze(limit=6, top_n=5)["metrics"]
        stats = out["citations"]["statistics"]
        assert (stats["total_papers"], stats["total_citations"], stats["max_citations"]) == (
            6,
            17,
            10,
        )
        assert stats["median_citations"] == 1.5
        assert (stats["papers_with_citations"], stats["papers_without_citations"]) == (4, 2)
        assert {j["name"]: j["count"] for j in out["journals"]["top_journals"]} == {
            "Lancet": 2,
            "BMJ": 2,
            "PLoS One": 2,
        }
        assert out["types"]["types"] == [
            {"name": "Journal Article", "count": 4},
            {"name": "Review", "count": 2},
        ]
        assert out["authors"]["total_author_mentions"] == 9
        assert out["authors"]["total_authors"] == 5
        assert out["authors"]["single_author_papers"] == 3
        assert {a["name"]: a["count"] for a in out["authors"]["top_authors"]}["Smith J"] == 2

    def test_countries_come_from_the_last_part_of_each_affiliation(self, client):
        entry = _analyze(metrics=["countries"], limit=6)["metrics"]["countries"]
        assert {c["name"]: c["count"] for c in entry["top_countries"]} == {
            "United Kingdom": 2,  # "UK." and "U.K." are one country, once per paper
            "United States": 1,
            "France": 1,
            "South Africa": 1,
        }
        # E and F have no affiliation: they are not counted as having one
        assert entry["papers_with_affiliation"] == 4
        assert entry["international_collaboration_percent"] == 25.0  # only C names two countries
        assert "top_institutions" not in entry

    def test_funders(self, client):
        entry = _analyze(metrics=["funders"], limit=6)["metrics"]["funders"]
        assert entry["total_funded_papers"] == 2
        assert entry["multi_funder_papers"] == 1
        assert {f["name"]: f["count"] for f in entry["top_funders"]} == {
            "Wellcome Trust": 2,
            "NIH": 1,
        }

    def test_nothing_in_a_response_is_a_pandas_or_numpy_object(self, client):
        import json

        json.dumps(_analyze(limit=6))  # raises on a Series, DataFrame or numpy scalar

    def test_top_n_limits_the_rankings(self, client):
        out = _analyze(metrics=["journals", "authors"], limit=6, top_n=1)["metrics"]
        assert len(out["journals"]["top_journals"]) == 1
        assert len(out["authors"]["top_authors"]) == 1


class TestBasis:
    def test_records_beyond_the_limit_make_a_labelled_sample(self, client):
        result = _analyze(metrics=["journals", "by_year", "citations"], limit=3)
        assert (result["hit_count"], result["limit"], result["records_read"]) == (6, 3, 3)
        journals = result["metrics"]["journals"]
        assert journals["basis"] == "sample"
        assert journals["records"] == 3
        assert "first 3 of 6" in result["sample_note"]
        assert "not a random sample" in result["sample_note"]
        assert result["metrics"]["by_year"]["basis"] == "exact"
        citations = result["metrics"]["citations"]
        assert citations["basis"] == "sample"
        assert citations["thresholds"]["basis"] == "exact"  # counted over all 6, not the 3

    def test_the_sample_is_the_first_records_in_the_order_asked_for(self, client):
        _analyze(metrics=["journals"], limit=2, sort="CITED desc")
        _, kwargs = client.searched[-1]
        assert kwargs["sort"] == "CITED desc"
        assert kwargs["max_results"] == 2

    def test_a_limit_that_covers_the_result_makes_the_metrics_exact(self, client):
        result = _analyze(metrics=["journals", "types"], limit=500)
        assert result["records_read"] == 6
        assert "sample_note" not in result
        assert all(entry["basis"] == "exact" for entry in result["metrics"].values())

    def test_every_metric_has_a_basis(self, client):
        for limit in (2, 6):
            for name, entry in _analyze(limit=limit)["metrics"].items():
                assert entry["basis"] in {"exact", "sample"}, name

    def test_no_match_reads_nothing(self, client):
        result = _analyze(query="x", date_from="1990", date_to="1991", limit=10)
        assert result["hit_count"] == 0 and result["records_read"] == 0
        assert not any(kw.get("max_results") == 10 for _, kw in client.searched)
        assert result["metrics"]["by_year"]["years"] == []
        assert result["metrics"]["journals"]["basis"] == "exact"
        assert result["metrics"]["journals"]["top_journals"] == []

    def test_lite_records_unless_affiliations_or_grants_are_wanted(self, client):
        _analyze(metrics=["journals"], limit=6)
        assert client.searched[-1][1]["resultType"] == "lite"
        _analyze(metrics=["journals", "funders"], limit=6)
        assert client.searched[-1][1]["resultType"] == "core"
        _analyze(metrics=["countries"], limit=6)
        assert client.searched[-1][1]["resultType"] == "core"


class TestToolContract:
    def test_filters_are_applied_to_every_count(self, client):
        result = _analyze(
            query="malaria",
            metrics=["open_access", "citations"],
            date_from="2019",
            open_access=True,
            source="MED",
            limit=6,
        )
        base = "(malaria) AND FIRST_PDATE:[2019 TO *] AND OPEN_ACCESS:y AND SRC:MED"
        assert result["query"] == base
        assert client.counted[0] == base
        assert all(q.startswith(f"({base}) AND ") for q in client.counted[1:])

    def test_an_unknown_metric_is_a_tool_error_before_any_request(self, client):
        with pytest.raises(ToolError, match="unknown metric"):
            _analyze(metrics=["by_year", "impact"])
        assert not client.counted and not client.searched

    def test_a_bad_filter_is_a_tool_error(self, client):
        with pytest.raises(ToolError):
            _analyze(date_from="2025", date_to="2020")

    def test_a_missing_extra_says_what_to_install_and_makes_no_request(self, client, monkeypatch):
        monkeypatch.setattr(srv, "ANALYTICS_AVAILABLE", False)
        with pytest.raises(ToolError, match=r"pip install pyeuropepmc\[analytics\]"):
            _analyze(metrics=["by_year", "journals"])
        assert not client.counted and not client.searched

    def test_without_the_extra_the_default_set_still_answers_what_it_can(
        self, client, monkeypatch
    ):
        """A plain ``uvx pyeuropepmc mcp`` has no pandas: the call with no ``metrics`` must not fail."""
        monkeypatch.setattr(srv, "ANALYTICS_AVAILABLE", False)
        result = _analyze()
        metrics = result["metrics"]
        assert (
            metrics["by_year"]["basis"] == "exact" and metrics["open_access"]["basis"] == "exact"
        )
        for name in ("journals", "authors", "types", "countries", "funders", "citations"):
            assert metrics[name]["basis"] == "unavailable"
            assert "pip install pyeuropepmc[analytics]" in metrics[name]["error"]
        assert result["records_read"] == 0 and not client.searched[2:]  # only the year edges

    def test_naming_a_metric_that_needs_the_extra_still_fails_with_the_hint(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(srv, "ANALYTICS_AVAILABLE", False)
        with pytest.raises(ToolError, match=r"pip install pyeuropepmc\[analytics\]"):
            _analyze(metrics=["by_year", "journals"])

    def test_the_counts_are_made_by_clients_of_the_workers_own(self, client, monkeypatch):
        made: list[FakeClient] = []

        def new():
            fake = FakeClient(RECORDS)
            made.append(fake)
            return fake

        monkeypatch.setattr(srv, "_new_counting_client", new)
        _analyze(metrics=["by_year"])
        assert 1 <= len(made) <= am.WORKERS
        assert all(c.counted for c in made)

    def test_a_failed_request_is_a_tool_error(self, monkeypatch):
        fake = FakeClient(RECORDS)

        def fail(query: str, **kwargs: Any) -> int:
            raise SearchError(ErrorCodes.SEARCH003, {"query": query})

        monkeypatch.setattr(fake, "get_hit_count", fail)
        srv._client_cache.set(fake)
        monkeypatch.setattr(srv, "_new_counting_client", lambda: fake)
        with pytest.raises(ToolError):
            _analyze()

    def test_limit_is_bounded_by_the_schema(self):
        props = _run(srv.mcp.list_tools())
        tool = next(t for t in props if t.name == "analyze_search")
        from mcp_wire import hint, schema_of

        limit = schema_of(tool)["properties"]["limit"]
        assert (limit["minimum"], limit["maximum"], limit["default"]) == (1, 1000, 500)
        assert hint(tool.annotations, "readOnlyHint") is True
        assert hint(tool.annotations, "openWorldHint") is True
