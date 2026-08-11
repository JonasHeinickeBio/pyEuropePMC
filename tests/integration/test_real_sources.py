"""Real-world integration tests: each literature source hit live.

These tests verify that every search source client actually returns
structured results from its live API (PubMed/EuropePMC, arXiv, OpenAlex,
Zenodo, DOAJ, DBLP, HAL, CORE, ClinicalTrials.gov, Semantic Scholar).

Usage:
    pytest tests/integration/ --run-integration -v
"""

import pytest

from pyeuropepmc.features.literature.adapters import (
    OpenAlexLiteratureAdapter,
    SemanticScholarLiteratureAdapter,
)
from pyeuropepmc.features.search.sources.arxiv import ArxivClient
from pyeuropepmc.features.search.sources.clinicaltrials import ClinicalTrialsClient
from pyeuropepmc.features.search.sources.core import COREClient
from pyeuropepmc.features.search.sources.dblp import DBLPClient
from pyeuropepmc.features.search.sources.doaj import DOAJClient
from pyeuropepmc.features.search.sources.hal import HALClient
from pyeuropepmc.features.search.sources.pubmed import PubMedClient
from pyeuropepmc.features.search.sources.zenodo import ZenodoClient


@pytest.mark.integration
class TestSourcesLive:
    """Every source returns structured results from its real API."""

    def test_pubmed(self):
        client = PubMedClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("chronic fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "pubmed"
        assert r.source_id  # PMID or DOI fallback
        assert r.title

    def test_arxiv(self):
        client = ArxivClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("fatigue detection", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "arxiv"
        assert r.source_id
        assert r.title

    def test_openalex(self):
        adapter = OpenAlexLiteratureAdapter()
        results = adapter.search("chronic fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "openalex"
        assert r.source_id  # OpenAlex work ID (W...)
        assert r.title

    def test_zenodo(self):
        client = ZenodoClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("chronic fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "zenodo"
        assert r.source_id
        assert r.title

    def test_doaj(self):
        client = DOAJClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("chronic fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "doaj"
        assert r.source_id
        assert r.title
        assert r.doi  # DOAJ records are scholarly with DOIs

    def test_dblp(self):
        client = DBLPClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("fatigue", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "dblp"
        assert r.source_id
        assert r.title

    def test_hal(self):
        client = HALClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "hal"
        assert r.source_id
        assert r.title

    def test_core(self):
        client = COREClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("chronic fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "core"
        assert r.source_id
        assert r.title

    def test_clinicaltrials(self):
        client = ClinicalTrialsClient(rate_limit_delay=0.0, timeout=30)
        results = client.search("chronic fatigue syndrome", limit=5)
        assert len(results) > 0
        r = results[0]
        assert r.source == "clinicaltrials"
        assert r.source_id  # NCT id
        assert r.title

    def test_semantic_scholar(self):
        """Semantic Scholar may be rate-limited without an API key."""
        adapter = SemanticScholarLiteratureAdapter()
        results = adapter.search("chronic fatigue syndrome", limit=5)
        if not results:
            pytest.skip("Semantic Scholar rate-limited without API key")
        r = results[0]
        assert r.source == "semanticscholar"
        assert r.source_id
        assert r.title
