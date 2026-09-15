"""Integration tests for live UnifiedSearch across multiple sources.

Usage:
    pytest tests/integration/ --run-integration -v
"""

import pytest

from pyeuropepmc.features.search import UnifiedSearch


@pytest.mark.integration
class TestUnifiedSearchLive:
    """End-to-end unified search hitting real APIs."""

    @pytest.fixture(scope="class")
    def searcher(self) -> UnifiedSearch:
        return UnifiedSearch()

    def test_search_pubmed_arxiv(self, searcher: UnifiedSearch) -> None:
        """Search PubMed + arXiv for a broad topic."""
        results, report = searcher.search("attention mechanism transformer", limit=10)
        assert len(results) > 0, "No results from unified search"
        assert report.total_input >= len(results)
        assert report.duplicates_removed >= 0
        # Should have results from at least one source
        sources = {r.source for r in results}
        assert len(sources) >= 1

    def test_search_with_custom_sources(self, searcher: UnifiedSearch) -> None:
        """Restrict to specific sources."""
        results, report = searcher.search("machine learning", sources=["arxiv"], limit=5)
        assert len(results) > 0
        for r in results:
            assert r.source == "arxiv"

    def test_search_all_sources(self, searcher: UnifiedSearch) -> None:
        """Use search_all to get per-source breakdown."""
        per_source, errors = searcher.search_all("climate change", limit=5)
        assert isinstance(per_source, dict)
        assert isinstance(errors, dict)
        assert len(per_source) > 0
        for _source_name, source_results in per_source.items():
            assert isinstance(source_results, list)

    def test_dedup_across_sources(self, searcher: UnifiedSearch) -> None:
        """Papers found in multiple sources should be deduplicated."""
        results, report = searcher.search(
            "chronic fatigue syndrome", sources=["pubmed", "semantic_scholar"], limit=15
        )
        # If dedup worked, output ≤ input
        assert len(results) <= report.total_input
        # There should be at least some results
        assert len(results) > 0
        # No duplicate PMIDs or DOIs
        pmids = {r.pmid for r in results if r.pmid}
        dois = {r.doi for r in results if r.doi}
        assert len(pmids) == sum(1 for r in results if r.pmid)
        assert len(dois) == sum(1 for r in results if r.doi)

    def test_empty_query(self, searcher: UnifiedSearch) -> None:
        """Empty query is handled gracefully."""
        results, report = searcher.search("", limit=5)
        assert len(results) == 0

    def test_search_respects_limit(self, searcher: UnifiedSearch) -> None:
        """Overall limit is respected across sources."""
        for limit in [3, 10]:
            results, _ = searcher.search("deep learning", limit=limit)
            assert len(results) <= limit * 3, f"limit={limit} returned {len(results)}"

    def test_search_structure(self, searcher: UnifiedSearch) -> None:
        """Results have the expected LiteratureResult structure."""
        results, report = searcher.search("COVID-19 treatment", limit=8)
        assert len(results) > 0
        for r in results:
            # Every result must have at least a title and source
            assert r.title, "Missing title"
            assert r.source, "Missing source"
            assert r.source in (
                "pubmed",
                "arxiv",
                "semantic_scholar",
                "openalex",
                "clinicaltrials",
            )
        # MergeReport fields are populated
        assert report.total_input > 0
        assert report.total_output == len(results)
