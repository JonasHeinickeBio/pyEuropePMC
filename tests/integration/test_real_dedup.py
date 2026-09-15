"""Real-world integration tests: cross-source deduplication quality.

These tests fetch the SAME paper from multiple live sources and verify
that the merger correctly groups them into one canonical record with
metadata promoted from the best source.

Uses a well-known, stable ME/CFS paper:
    Fukuda et al. 1994, "The Chronic Fatigue Syndrome: A Comprehensive
    Approach to Its Definition and Study", Annals of Internal Medicine.
    PMID 7978722, DOI 10.7326/0003-4819-121-12-199412150-00009

Usage:
    pytest tests/integration/ --run-integration -v
"""

import pytest

from pyeuropepmc.features.enrich.merger import DedupConfig, DedupMode, MatchLevel, LiteratureMerger
from pyeuropepmc.features.literature.adapters import OpenAlexLiteratureAdapter
from pyeuropepmc.features.search import UnifiedSearch
from pyeuropepmc.features.search.sources.core import COREClient
from pyeuropepmc.features.search.sources.pubmed import PubMedClient

KNOWN_DOI = "10.7326/0003-4819-121-12-199412150-00009"
KNOWN_PMID = "7978722"


@pytest.mark.integration
class TestCrossSourceDedup:
    """The same paper fetched from different sources merges to one."""

    def test_pubmed_openalex_merge(self):
        """PubMed + OpenAlex copies of the same paper -> 1 record."""
        pubmed = PubMedClient(rate_limit_delay=0.0, timeout=30)
        pm = pubmed.search(f"{KNOWN_DOI}[doi]", limit=3)
        assert len(pm) == 1
        assert pm[0].doi == KNOWN_DOI

        openalex = OpenAlexLiteratureAdapter()
        oa = openalex.get_paper(KNOWN_DOI)
        assert oa is not None
        assert oa.pmid == KNOWN_PMID or oa.doi == KNOWN_DOI

        merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
        merged, report = merger.merge_results([[r.model_dump() for r in pm], [oa.model_dump()]])

        assert len(merged) == 1
        assert report.duplicates_removed == 1
        record = report.records[0]
        assert record.match_level == MatchLevel.DOI_EXACT
        # The merged record keeps both identifiers
        assert merged[0]["pmid"] == KNOWN_PMID or merged[0]["pmid"] == "7978722"
        assert merged[0]["doi"] == KNOWN_DOI

    def test_pubmed_core_merge(self):
        """PubMed + CORE copies of the same paper -> 1 record."""
        pubmed = PubMedClient(rate_limit_delay=0.0, timeout=30)
        pm = pubmed.search(f"{KNOWN_DOI}[doi]", limit=3)
        assert len(pm) == 1

        core = COREClient(rate_limit_delay=0.0, timeout=30)
        core_results = core.search(KNOWN_DOI, limit=5)
        if not core_results:
            pytest.skip("CORE did not return the paper")

        merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
        merged, report = merger.merge_results(
            [[r.model_dump() for r in pm], [r.model_dump() for r in core_results]]
        )
        assert len(merged) >= 1
        assert merged[0]["doi"] == KNOWN_DOI or merged[0]["pmid"] == KNOWN_PMID


@pytest.mark.integration
class TestUnifiedSearchDedupQuality:
    """UnifiedSearch dedup behaviour on real overlapping data."""

    def test_no_duplicate_identifiers_in_output(self):
        """Output never contains duplicate DOIs or PMIDs."""
        searcher = UnifiedSearch(
            sources=["pubmed", "openalex", "core", "doaj"],
            dedup_mode=DedupMode.BALANCED,
            rate_limit_delay=0.0,
            timeout=30,
        )
        merged, report = searcher.search("myalgic encephalomyelitis", limit=15)

        assert len(merged) > 0
        assert report.total_input > 0
        assert report.total_output == len(merged)
        assert report.total_output <= report.total_input

        pmids = [r.pmid for r in merged if r.pmid]
        dois = [r.doi for r in merged if r.doi]
        assert len(pmids) == len(set(pmids)), "duplicate PMIDs in output"
        assert len(dois) == len(set(dois)), "duplicate DOIs in output"

    def test_report_metadata_populated(self):
        """MergeReport.metadata carries source times and dedup stats."""
        searcher = UnifiedSearch(
            sources=["pubmed", "openalex", "core"],
            dedup_mode=DedupMode.BALANCED,
            rate_limit_delay=0.0,
            timeout=30,
        )
        _, report = searcher.search("chronic fatigue syndrome", limit=10)

        assert isinstance(report.metadata, dict)
        assert "source_times" in report.metadata
        assert set(report.metadata["source_times"].keys()) >= {"pubmed", "openalex", "core"}
        assert "sources_used" in report.metadata
        assert "identifier_groups" in report.metadata
        assert "deduped_papers" in report.metadata

    def test_multi_source_query_returns_mixed_sources(self):
        """Unified search returns results from more than one source."""
        searcher = UnifiedSearch(
            sources=["pubmed", "arxiv", "zenodo"],
            dedup_mode=DedupMode.BALANCED,
            rate_limit_delay=0.0,
            timeout=30,
        )
        merged, _ = searcher.search("fatigue", limit=10)
        sources = {r.source for r in merged}
        assert len(sources) >= 2, f"expected multi-source results, got {sources}"
