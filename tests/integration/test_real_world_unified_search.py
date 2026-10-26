"""Real-world checks of UnifiedSearch diagnostics and limits against the live services.

These pin down behaviour that only shows up against real providers: that every source is
reported honestly (a provider that blocks or rejects us is an ``error``, not an empty source),
that a source outside the configured set can be named in a call, and that the delay between
requests really is applied. Providers come and go, so the assertions are about invariants, not
about what a given provider answers today.

Usage:
    pytest tests/integration/test_real_world_unified_search.py --run-integration -v
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time

import pytest

from pyeuropepmc.features.search import UnifiedSearch

pytestmark = pytest.mark.integration

STATUSES = {"ok", "empty", "error", "rate_limited", "unavailable"}


class TestEverySourceIsReportedHonestly:
    SOURCES = [
        "europepmc",
        "pubmed",
        "openalex",
        "semantic_scholar",
        "clinicaltrials",
        "core",
        "doaj",
        "hal",
        "zenodo",
        "dblp",
        "arxiv",
    ]

    @pytest.fixture(scope="class")
    def run(self):
        # only Europe PMC and PubMed are configured: the others are named in the call
        with UnifiedSearch(sources=["europepmc", "pubmed"]) as searcher:
            results, report = searcher.search(
                "long covid fatigue", limit=5, sources=self.SOURCES, diagnostics=True
            )
        return results, report.metadata["source_status"], report

    def test_every_named_source_has_a_status(self, run):
        _, status, _ = run
        assert set(status) == set(self.SOURCES)
        assert all(row["status"] in STATUSES for row in status.values())

    def test_a_source_outside_the_configured_set_is_not_silently_skipped(self, run):
        _, status, _ = run
        assert status["europepmc"]["status"] == "ok"
        assert not any(
            row["status"] == "unavailable" and "not initialised" in str(row["error"])
            for row in status.values()
        )
        working = [n for n, row in status.items() if row["status"] == "ok"]
        assert len(working) >= 4, status  # several independent providers answer

    def test_a_source_that_did_not_deliver_says_why(self, run):
        _, status, _ = run
        for name, row in status.items():
            if row["status"] in {"error", "rate_limited", "unavailable"}:
                assert row["error"] and row["error"]["message"], (name, row)
            if row["status"] == "empty":
                assert row["error"] is None, (name, row)

    def test_matched_sources_are_real_and_include_the_winner(self, run):
        results, status, _ = run
        for record in results:
            assert record.source in record.matched_sources
            assert set(record.matched_sources) <= set(status)

    def test_independent_providers_return_some_of_the_same_papers(self, run):
        results, _, _ = run
        assert any(len(r.matched_sources) > 1 for r in results)

    def test_the_limits_that_applied_are_recorded(self, run):
        _, _, report = run
        limits = report.metadata["effective_limits"]
        assert set(limits) == set(self.SOURCES)
        assert limits["arxiv"]["rate_limit_delay"] >= 3.0


class TestTheDelayIsReallyApplied:
    def test_overlapping_searches_reach_arxiv_a_delay_apart(self):
        delay = 1.5
        searcher = UnifiedSearch(sources=["arxiv"], primary=None, rate_limits={"arxiv": delay})
        client = searcher._get_or_init_clients()["arxiv"]
        starts: list[float] = []
        original = client.session.get

        def traced(*args, **kwargs):
            starts.append(time.monotonic())
            return original(*args, **kwargs)

        client.session.get = traced
        queries = ["graph neural network", "protein folding", "quantum error correction"]
        try:
            with ThreadPoolExecutor(3) as pool:
                outcomes = list(
                    pool.map(lambda q: searcher.search(q, limit=2, diagnostics=True), queries)
                )
        finally:
            searcher.close()
        gaps = [b - a for a, b in zip(sorted(starts), sorted(starts)[1:], strict=False)]
        assert len(starts) == 3 and all(g >= delay - 0.1 for g in gaps), gaps
        rows = [o[1].metadata["source_status"]["arxiv"] for o in outcomes]
        assert all(r["status"] in {"ok", "rate_limited"} for r in rows)
        assert max(r["waited_seconds"] for r in rows) > 0  # the later calls queued
