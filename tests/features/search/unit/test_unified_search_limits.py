"""UnifiedSearch rate limits: per-source delays, concurrency caps and the effective limits."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time
from typing import Any
from unittest.mock import patch

import pytest

from pyeuropepmc.features.search import UnifiedSearch, registry
from pyeuropepmc.features.search.unified_search import DEFAULT_RATE_LIMIT_DELAY, SOURCE_MIN_DELAY
from pyeuropepmc.models.literature import LiteratureResult


class Probe:
    """A source client that records how many calls are inside ``search`` at once."""

    def __init__(self, hold: float = 0.05, error: Exception | None = None) -> None:
        self.hold, self.error = hold, error
        self.inside = self.peak = 0
        self.guard = threading.Lock()

    def search(self, query: str, limit: int = 25) -> list[LiteratureResult]:
        with self.guard:
            self.inside += 1
            self.peak = max(self.peak, self.inside)
        try:
            time.sleep(self.hold)
            if self.error:
                raise self.error
            return [LiteratureResult(source="pubmed", source_id=query, title=query)]
        finally:
            with self.guard:
                self.inside -= 1


def _searcher(clients: dict[str, Any], **kwargs: Any) -> UnifiedSearch:
    searcher = UnifiedSearch(sources=list(clients), primary=None, **kwargs)
    searcher._clients = clients
    return searcher


def _concurrently(searcher: UnifiedSearch, callers: int = 4, **kwargs: Any):
    with ThreadPoolExecutor(max_workers=callers) as pool:
        futures = [pool.submit(searcher.search, f"q{i}", **kwargs) for i in range(callers)]
        return [f.result() for f in futures]


class TestDelays:
    def test_the_default_is_1_2_seconds_but_never_faster_than_a_provider_allows(self):
        searcher = UnifiedSearch(sources=["europepmc", "pubmed", "arxiv", "dblp", "zenodo"])
        assert searcher.rate_limit_delay == DEFAULT_RATE_LIMIT_DELAY == 1.2
        assert {s: searcher.delay_for(s) for s in searcher.sources} == {
            "europepmc": 1.2,
            "pubmed": 1.2,
            "arxiv": 3.0,
            "dblp": 3.0,
            "zenodo": 3.0,
        }
        assert SOURCE_MIN_DELAY == {"arxiv": 3.0, "dblp": 3.0, "zenodo": 3.0}

    def test_an_explicit_delay_applies_to_every_source_as_before(self):
        searcher = UnifiedSearch(sources=["pubmed", "arxiv"], rate_limit_delay=0.5)
        assert searcher.delay_for("pubmed") == searcher.delay_for("arxiv") == 0.5

    def test_a_per_source_entry_wins_over_both(self):
        searcher = UnifiedSearch(
            sources=["pubmed", "arxiv"], rate_limit_delay=0.5, rate_limits={"arxiv": 5.0}
        )
        assert (searcher.delay_for("pubmed"), searcher.delay_for("arxiv")) == (0.5, 5.0)
        assert UnifiedSearch(sources=["arxiv"], rate_limits={"arxiv": 0}).delay_for("arxiv") == 0

    def test_each_client_is_built_with_its_own_delay(self):
        built: dict[str, float] = {}

        def load(name, **kwargs):
            built[name] = kwargs["rate_limit_delay"]
            return object()

        searcher = UnifiedSearch(
            sources=["pubmed", "arxiv", "openalex"], rate_limits={"openalex": 0.2}
        )
        with patch.object(registry, "load_source", load):
            searcher._get_or_init_clients()
        assert built == {"pubmed": 1.2, "arxiv": 3.0, "openalex": 0.2}

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"rate_limits": {"arxiv": 1.0}}, "not in sources"),
            ({"rate_limits": {"pubmed": -1}}, "must not be negative"),
            ({"rate_limit_delay": -0.1}, "must not be negative"),
            ({"source_concurrency": 0}, "at least 1"),
            ({"source_concurrency": {"pubmed": 1.5}}, "at least 1"),
            ({"source_concurrency": {"arxiv": 2}}, "not in sources"),
        ],
    )
    def test_a_bad_configuration_is_refused_at_construction(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            UnifiedSearch(sources=["pubmed"], **kwargs)


class TestEffectiveLimits:
    def test_the_limits_property(self):
        searcher = UnifiedSearch(
            sources=["pubmed", "arxiv"],
            rate_limits={"pubmed": 0.4},
            source_concurrency={"pubmed": 3},
        )
        assert searcher.limits == {
            "pubmed": {"rate_limit_delay": 0.4, "max_concurrency": 3},
            "arxiv": {"rate_limit_delay": 3.0, "max_concurrency": 1},
        }

    def test_every_result_says_which_limits_applied_to_the_sources_it_queried(self):
        searcher = _searcher({"pubmed": Probe(0), "arxiv": Probe(0)}, rate_limits={"arxiv": 4.0})
        _, report = searcher.search("x", sources=["arxiv"])
        assert report.metadata["effective_limits"] == {
            "arxiv": {"rate_limit_delay": 4.0, "max_concurrency": 1}
        }

    def test_the_limits_are_reported_when_nothing_was_found_too(self):
        searcher = _searcher({"pubmed": Probe(0, error=RuntimeError("down"))})
        results, report = searcher.search("x")
        assert results == [] and "pubmed" in report.metadata["effective_limits"]

    def test_diagnostics_rows_carry_the_limits_and_the_time_spent_queued(self):
        searcher = _searcher({"pubmed": Probe(0), "doaj": None}, rate_limits={"pubmed": 0.7})
        _, report = searcher.search("x", diagnostics=True)
        row = report.metadata["source_status"]["pubmed"]
        assert (row["rate_limit_delay"], row["max_concurrency"]) == (0.7, 1)
        assert row["waited_seconds"] >= 0
        assert report.metadata["source_status"]["doaj"]["max_concurrency"] == 1


class TestConcurrency:
    def test_one_call_per_source_at_a_time_by_default(self):
        probe = Probe()
        _concurrently(_searcher({"pubmed": probe}), callers=4)
        assert probe.peak == 1

    def test_a_higher_cap_lets_that_many_through(self):
        probe = Probe(hold=0.15)
        _concurrently(_searcher({"pubmed": probe}, source_concurrency=2), callers=4)
        assert probe.peak == 2

    def test_a_cap_given_as_a_number_applies_to_every_source(self):
        first, second = Probe(0.15), Probe(0.15)
        searcher = _searcher({"pubmed": first, "arxiv": second}, source_concurrency=3)
        _concurrently(searcher, callers=6)
        assert (first.peak, second.peak) == (3, 3)

    def test_sources_do_not_wait_for_each_other(self):
        first, second = Probe(0.2), Probe(0.2)
        searcher = _searcher({"pubmed": first, "arxiv": second})
        started = time.monotonic()
        searcher.search("x")
        assert time.monotonic() - started < 0.35  # in parallel, not 0.4 one after the other

    def test_a_caller_that_had_to_wait_is_told_how_long(self):
        searcher = _searcher({"pubmed": Probe(0.2)})
        results = _concurrently(searcher, callers=2, diagnostics=True)
        waited = sorted(
            r[1].metadata["source_status"]["pubmed"]["waited_seconds"] for r in results
        )
        assert waited[0] < 0.1 < 0.15 < waited[1]

    def test_a_failing_call_gives_its_place_back(self):
        probe = Probe(0, error=RuntimeError("boom"))
        searcher = _searcher({"pubmed": probe})
        for _ in range(3):  # a leaked slot would hang the second call
            _, report = searcher.search("x")
            assert "pubmed" in report.metadata["source_errors"]
        assert probe.inside == 0

    def test_search_all_is_gated_too(self):
        probe = Probe()
        searcher = _searcher({"pubmed": probe})
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda i: searcher.search_all(f"q{i}"), range(3)))
        assert probe.peak == 1
