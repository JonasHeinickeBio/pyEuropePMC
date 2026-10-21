"""Per-source status, the source filter and the time budget of ``PaperEnricher.enrich_paper``,
and the correction/retraction signal that Crossref and Europe PMC add to the merged record.

Clients are fakes set on ``enricher.clients``; id resolution is stubbed. Nothing touches the
network.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from pyeuropepmc.features.enrich import EnrichmentConfig, PaperEnricher
from pyeuropepmc.features.enrich.data_merger import DataMerger
from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient
from pyeuropepmc.features.enrich.sources.europepmc import EuropePMCEnrichmentClient


class FakeClient:
    def __init__(self, data: Any = None, *, error: Exception | None = None, wait: Any = None):
        self.data, self.error, self.wait = data, error, wait
        self.calls: list[str] = []

    def enrich(self, identifier: str, **kwargs: Any) -> Any:
        self.calls.append(identifier)
        if self.wait is not None:
            self.wait.wait(timeout=10)
        if self.error:
            raise self.error
        return self.data

    def close(self) -> None:
        pass


def _enricher(**clients: FakeClient) -> PaperEnricher:
    config = EnrichmentConfig(enable_ror=False)
    enricher = PaperEnricher(config)
    enricher.close()
    enricher.clients = dict(clients)
    enricher._resolve_ids = lambda ident: {  # type: ignore[method-assign]
        "doi": "10.1234/test",
        "pmid": "99",
        "pmcid": None,
    }
    return enricher


OK = {"source": "x", "title": "T", "citation_count": 3}


class TestSourceStatus:
    def test_every_source_gets_a_status(self):
        enricher = _enricher(
            crossref=FakeClient(OK),
            openalex=FakeClient(None),
            semantic_scholar=FakeClient(error=RuntimeError("HTTP 429 Too Many Requests")),
        )
        result = enricher.enrich_paper("10.1234/test")
        status = result["source_status"]
        assert status["crossref"]["status"] == "ok"
        assert status["crossref"]["seconds"] >= 0
        assert status["openalex"]["status"] == "empty"
        assert status["semantic_scholar"] == {
            "status": "error",
            "error": "RuntimeError: HTTP 429 Too Many Requests",
        }
        assert result["sources"] == ["crossref"]  # unchanged contract

    def test_a_failing_source_does_not_stop_the_others(self):
        enricher = _enricher(crossref=FakeClient(OK), icite=FakeClient(error=ValueError("x")))
        result = enricher.enrich_paper("10.1234/test")
        assert result["merged"]["title"] == "T"
        assert result["source_status"]["icite"]["status"] == "error"

    def test_an_error_message_is_one_short_line(self):
        enricher = _enricher(crossref=FakeClient(error=RuntimeError("a\nb\n" + "x" * 500)))
        error = enricher.enrich_paper("10.1234/test")["source_status"]["crossref"]["error"]
        assert "\n" not in error and len(error) <= 200

    def test_a_source_without_a_usable_identifier_is_skipped(self):
        enricher = _enricher(icite=FakeClient(OK))
        enricher._resolve_ids = lambda ident: {"doi": "10.1/x", "pmid": None, "pmcid": None}  # type: ignore[method-assign]
        status = enricher.enrich_paper("10.1/x")["source_status"]["icite"]
        assert status == {"status": "skipped", "reason": "no usable identifier"}


class TestOnlySources:
    def test_other_sources_are_not_called(self):
        crossref, openalex = FakeClient(OK), FakeClient(OK)
        enricher = _enricher(crossref=crossref, openalex=openalex)
        result = enricher.enrich_paper("10.1234/test", only_sources=["crossref"])
        assert crossref.calls and not openalex.calls
        assert result["source_status"]["openalex"] == {
            "status": "skipped",
            "reason": "not requested",
        }

    def test_default_is_every_source(self):
        crossref, openalex = FakeClient(OK), FakeClient(OK)
        _enricher(crossref=crossref, openalex=openalex).enrich_paper("10.1234/test")
        assert crossref.calls and openalex.calls


class TestTimeBudget:
    def test_a_slow_source_is_reported_and_left_out(self):
        release = threading.Event()
        enricher = _enricher(crossref=FakeClient(OK), openalex=FakeClient(OK, wait=release))
        started = time.monotonic()
        try:
            result = enricher.enrich_paper("10.1234/test", time_budget=0.3)
            elapsed = time.monotonic() - started
        finally:
            release.set()
        assert elapsed < 3
        assert result["source_status"]["crossref"]["status"] == "ok"
        assert result["source_status"]["openalex"]["status"] == "timeout"
        assert result["sources"] == ["crossref"]
        assert result["merged"]["title"] == "T"

    def test_no_budget_waits_for_every_source(self):
        slow = FakeClient(OK, wait=threading.Event())
        slow.wait.set()
        result = _enricher(crossref=slow).enrich_paper("10.1234/test")
        assert result["source_status"]["crossref"]["status"] == "ok"


class TestBoundedWorkers:
    """A source that misses the budget keeps its worker; repeated calls must not pile up threads."""

    def test_slow_sources_cannot_start_more_threads_than_the_cap(self):
        release = threading.Event()
        slow = FakeClient(OK, wait=release)
        enricher = _enricher(openalex=slow)
        enricher._max_workers = 2
        try:
            statuses = [
                enricher.enrich_paper("10.1234/test", time_budget=0.2)["source_status"]["openalex"]
                for _ in range(6)
            ]
            assert len(enricher._get_pool()._threads) <= 2  # this enricher's own threads
            assert len(slow.calls) <= 2  # the other four never got a worker
            assert [s["status"] for s in statuses] == ["timeout"] * 6
            assert any("not started" in s.get("reason", "") for s in statuses[2:])
        finally:
            release.set()

    def test_workers_are_free_again_once_the_slow_requests_end(self):
        release = threading.Event()
        slow = FakeClient(OK, wait=release)
        enricher = _enricher(openalex=slow)
        enricher._max_workers = 1
        enricher.enrich_paper("10.1234/test", time_budget=0.2)
        release.set()
        result = enricher.enrich_paper("10.1234/test", time_budget=5)
        assert result["source_status"]["openalex"]["status"] == "ok"

    def test_the_default_cap_scales_with_the_number_of_sources(self):
        enricher = _enricher(a=FakeClient(OK), b=FakeClient(OK))
        assert enricher._get_pool()._max_workers == 8
        enricher.close()

    def test_enriching_after_close_works(self):
        enricher = _enricher(crossref=FakeClient(OK))
        enricher.enrich_paper("10.1234/test")
        enricher.close()
        enricher.clients = {"crossref": FakeClient(OK)}
        assert enricher.enrich_paper("10.1234/test")["source_status"]["crossref"]["status"] == "ok"


class TestSavingStaysOptIn:
    def test_nothing_is_written_by_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _enricher(crossref=FakeClient(OK)).enrich_paper("10.1234/test")
        assert list(tmp_path.iterdir()) == []

    def test_source_status_is_not_saved_as_a_raw_source_file(self, tmp_path):
        _enricher(crossref=FakeClient(OK)).enrich_paper(
            "10.1234/test", save_responses=True, save_dir=tmp_path
        )
        names = sorted(p.name for p in tmp_path.iterdir())
        assert not any("source_status" in n for n in names)
        assert any(n.startswith("raw_crossref") for n in names)


class FakeRor:
    def __init__(self, delay: float = 0.0, fail: bool = False):
        self.delay, self.fail, self.calls = delay, fail, []

    def _normalize_ror_id(self, value: str) -> str:
        return value.rsplit("/", 1)[-1]

    def enrich(self, identifier: str, **kwargs: Any) -> Any:
        self.calls.append(identifier)
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("ROR down")
        return {"source": "ror", "ror_id": identifier, "city": "London"}

    def close(self) -> None:
        pass


def _with_ror(ror: FakeRor, institutions: int = 3) -> PaperEnricher:
    openalex = FakeSource_with_institutions(institutions)
    enricher = _enricher(openalex=openalex)
    enricher.config.enable_ror = True
    enricher.clients["ror"] = ror
    return enricher


def FakeSource_with_institutions(count: int) -> FakeClient:
    authors = [
        {
            "display_name": "A",
            "institutions": [
                {"display_name": f"I{n}", "ror_id": f"https://ror.org/0abc{n}"}
                for n in range(count)
            ],
        }
    ]
    return FakeClient({"source": "openalex", "title": "T", "authors": authors})


class TestRorStatus:
    def test_ror_reports_ok_with_counts(self):
        ror = FakeRor()
        status = _with_ror(ror).enrich_paper("10.1234/test")["source_status"]["ror"]
        assert status["status"] == "ok"
        assert (status["done"], status["total"]) == (3, 3)
        assert len(ror.calls) == 3

    def test_ror_stops_at_the_time_budget_and_says_how_far_it_got(self):
        ror = FakeRor(delay=0.25)
        result = _with_ror(ror, institutions=8).enrich_paper("10.1234/test", time_budget=0.6)
        status = result["source_status"]["ror"]
        assert status["status"] == "timeout"
        assert 0 < status["done"] < status["total"] == 8
        assert len(ror.calls) == status["done"]

    def test_a_failing_ror_client_is_an_error_status_not_an_exception(self):
        result = _with_ror(FakeRor(fail=True)).enrich_paper("10.1234/test")
        assert result["merged"]["title"] == "T"
        assert result["source_status"]["ror"]["status"] in ("empty", "error")

    def test_without_ror_there_is_no_ror_status(self):
        result = _enricher(openalex=FakeSource_with_institutions(2)).enrich_paper("10.1/x")
        assert "ror" not in result["source_status"]


class TestRorIsLookedUpOnce:
    @pytest.mark.parametrize("enabled", [True, False])
    def test_openalex_never_fetches_ror_itself(self, enabled):
        """The enricher's own ROR step (deduplicated, budgeted) is the only lookup."""
        enricher = PaperEnricher(EnrichmentConfig(enable_ror=enabled))
        try:
            assert enricher.clients["openalex"].enable_ror_enrichment is False
            assert enricher.clients["openalex"].ror_client is None
            assert ("ror" in enricher.clients) is enabled
        finally:
            enricher.close()


CROSSREF_UPDATES = {
    "updated-by": [
        {
            "DOI": "10.1016/s0140-6736(10)60175-4",
            "type": "retraction",
            "label": "Retraction",
            "source": "retraction-watch",
            "updated": {"date-time": "2010-02-02T00:00:00Z"},
        },
        {"DOI": "10.1016/s0140-6736(04)15715-2", "type": "correction", "label": "Correction"},
    ],
    "update-to": [{"DOI": "10.1/orig", "type": "correction", "label": "Correction"}],
}


class TestCrossrefUpdates:
    def test_updated_by_and_update_to_are_listed(self):
        updates = CrossRefClient._extract_updates(CROSSREF_UPDATES)
        assert [(u["direction"], u["type"], u["doi"]) for u in updates] == [
            ("updated_by", "retraction", "10.1016/s0140-6736(10)60175-4"),
            ("updated_by", "correction", "10.1016/s0140-6736(04)15715-2"),
            ("update_to", "correction", "10.1/orig"),
        ]
        assert updates[0]["date"] == "2010-02-02T00:00:00Z"

    @pytest.mark.parametrize("message", [{}, {"updated-by": None}, {"updated-by": ["x", 3]}])
    def test_missing_or_odd_fields_give_nothing(self, message):
        assert CrossRefClient._extract_updates(message) == []


class TestEuropePmcCorrections:
    RECORD = {
        "id": "9500320",
        "source": "MED",
        "title": "T",
        "pubTypeList": {"pubType": ["Retracted Publication", "Journal Article"]},
        "commentCorrectionList": {
            "commentCorrection": [
                {"source": "MED", "id": "9500313", "type": "Comment in", "reference": "Lancet"},
                {"source": "MED", "id": "20137807", "type": "Retraction in", "reference": "L"},
                {"source": "MED", "id": "14982", "type": "Expression of concern in"},
            ]
        },
    }

    def test_notices_are_kept_and_comments_dropped(self):
        out = EuropePMCEnrichmentClient._normalize(self.RECORD)
        assert [c["type"] for c in out["corrections"]] == [
            "Retraction in",
            "Expression of concern in",
        ]
        assert out["is_retracted"] is True

    def test_an_ordinary_record_is_not_retracted(self):
        out = EuropePMCEnrichmentClient._normalize({"id": "1", "title": "T"})
        assert out["is_retracted"] is False and out["corrections"] is None


class TestMergedUpdates:
    def test_both_sources_are_combined_and_the_paper_is_retracted(self):
        merged = DataMerger().merge_results(
            {
                "crossref": {
                    "title": "T",
                    "updates": CrossRefClient._extract_updates(CROSSREF_UPDATES),
                },
                "europepmc": EuropePMCEnrichmentClient._normalize(TestEuropePmcCorrections.RECORD),
            }
        )
        assert merged["is_retracted"] is True
        assert {u["from"] for u in merged["updates"]} == {"crossref", "europepmc"}

    def test_a_correction_alone_is_not_a_retraction(self):
        updates = [
            {"direction": "updated_by", "type": "correction", "doi": "10.1/c"},
        ]
        merged = DataMerger().merge_results({"crossref": {"title": "T", "updates": updates}})
        assert merged["is_retracted"] is False
        assert len(merged["updates"]) == 1

    def test_a_retraction_notice_is_not_itself_retracted(self):
        updates = [{"direction": "update_to", "type": "retraction", "doi": "10.1/orig"}]
        merged = DataMerger().merge_results({"crossref": {"title": "T", "updates": updates}})
        assert merged["is_retracted"] is False

    def test_without_crossref_and_europe_pmc_nothing_is_claimed(self):
        merged = DataMerger().merge_results({"openalex": {"title": "T"}})
        assert "is_retracted" not in merged and "updates" not in merged

    def test_the_same_notice_from_one_source_is_listed_once(self):
        entry = {"direction": "updated_by", "type": "retraction", "doi": "10.1/R"}
        merged = DataMerger().merge_results(
            {"crossref": {"title": "T", "updates": [entry, entry]}}
        )
        assert len(merged["updates"]) == 1
