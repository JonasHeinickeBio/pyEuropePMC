"""Real-world checks that need credentials: Semantic Scholar's key and the polite-pool e-mails.

The credentials come from the environment (``SEMANTIC_SCHOLAR_API_KEY``, ``UNPAYWALL_EMAIL``,
``OPENALEX_EMAIL``, ``CROSSREF_EMAIL``) or, for a developer, from a ``.env`` file in the project
root; only those four names are read from it and no value is ever printed. Without them the tests
are skipped. In CI they are skipped.

Usage:
    pytest tests/integration/test_real_world_credentials.py --run-integration -v
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
import time

import pytest

from pyeuropepmc.features.search import UnifiedSearch

pytestmark = pytest.mark.integration

NAMES = ("SEMANTIC_SCHOLAR_API_KEY", "UNPAYWALL_EMAIL", "OPENALEX_EMAIL", "CROSSREF_EMAIL")


def _from_dotenv() -> None:
    for folder in Path(__file__).resolve().parents:
        path = folder / ".env"
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                found = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
                if found and found.group(1) in NAMES and not os.environ.get(found.group(1)):
                    os.environ[found.group(1)] = found.group(2).strip("'\"")
            return


_from_dotenv()
needs_key = pytest.mark.skipif(
    not os.environ.get("SEMANTIC_SCHOLAR_API_KEY"), reason="SEMANTIC_SCHOLAR_API_KEY is not set"
)
needs_email = pytest.mark.skipif(
    not os.environ.get("UNPAYWALL_EMAIL"), reason="UNPAYWALL_EMAIL is not set"
)


@needs_key
class TestSemanticScholarWithAKey:
    """Semantic Scholar answers HTTP 429 to most requests even with a key; the search must ask
    again instead of reporting a rate limit on the first try (live: 1 of 6 calls got through
    before the retry, 6 of 6 after it)."""

    def test_spaced_searches_mostly_succeed(self):
        with UnifiedSearch(sources=["semantic_scholar"], primary=None) as searcher:
            statuses = []
            for _ in range(4):
                _, report = searcher.search("long covid fatigue", limit=3, diagnostics=True)
                statuses.append(report.metadata["source_status"]["semantic_scholar"]["status"])
                time.sleep(2)
        assert statuses.count("ok") >= 3, statuses
        assert set(statuses) <= {"ok", "rate_limited"}, statuses  # never a silent "empty"

    def test_a_rate_limited_search_says_so_and_names_the_wait(self):
        with UnifiedSearch(sources=["semantic_scholar"], primary=None) as searcher:
            _, report = searcher.search("long covid fatigue", limit=3, diagnostics=True)
        row = report.metadata["source_status"]["semantic_scholar"]
        if row["status"] == "rate_limited":
            assert row["error"]["http_status"] == 429
        else:
            assert row["status"] == "ok" and row["records"] > 0


class TestTheMcpToolsWithCredentials:
    @needs_email
    def test_find_open_access_answers_for_known_and_unknown_dois(self):
        from pyeuropepmc.mcp import server as srv

        async def run():
            known = await srv.find_open_access(doi="10.1186/1479-7364-6-1")
            unknown = await srv.find_open_access(doi="10.0000/does-not-exist-xyz")
            return known, unknown

        srv._unpaywall_client_cache.reset()
        known, unknown = asyncio.run(run())
        assert known["found"] is True and known["is_oa"] is True and known["oa_status"] == "gold"
        assert known["best_location"]["license"]
        assert unknown["found"] is False and unknown["is_oa"] is False

    @needs_email
    @needs_key
    def test_enrich_paper_reaches_every_source_when_they_are_configured(self):
        from pyeuropepmc.mcp import server as srv

        result = asyncio.run(srv.enrich_paper(doi="10.1038/s41579-019-0296-0", time_budget=90))
        status = {name: row.get("status", row) for name, row in result["sources"].items()}
        working = {name for name, state in status.items() if state == "ok"}
        assert {"europepmc", "crossref", "unpaywall"} <= working, status
        assert len(working) >= 5, status
        counts = {c["source"] for c in result["impact"]["citation_counts"]}
        assert len(counts) >= 4, result["impact"]
