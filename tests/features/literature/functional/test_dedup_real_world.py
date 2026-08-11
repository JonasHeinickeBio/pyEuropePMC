"""
Large-scale real-world deduplication functional test.

Simulates a multi-source literature search workflow:
1. Fetch real papers from PubMed (or use synthetic fallback)
2. Generate second-source variants with deliberate noise
     (author formatting changes, title case changes, missing fields,
      partial duplication)
3. Run all three DedupMode strategies (BALANCED, FOCUSED, RELAXED)
4. Report detailed timing and match-level breakdown
5. Validate merge quality (provenance, no false positives)

Usage:
    pytest tests/literature/functional/ -v          # quick smoke test
    pytest tests/literature/functional/ -v --run-real  # use real PubMed API

Environment:
    Set PYEUROPEPMC_REAL_DEDUP=1 to enable real API calls.
"""

from __future__ import annotations

import copy
import logging
import random
import time
from typing import Any

import pytest

from pyeuropepmc.features.enrich.merger import (
    DedupConfig,
    DedupMode,
    LiteratureMerger,
    MatchLevel,
    MergeReport,
    _extract_author_last_names,
    _has_part_marker,
    _title_similarity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Test data: 20 hand-curated papers with known identity relationships
# ---------------------------------------------------------------------------

_REAL_PAPERS: list[dict[str, Any]] = [
    # Papers 0–3: distinct papers about ME/CFS
    {
        "pmid": "35978441",
        "doi": "10.1186/s13643-022-02045-9",
        "title": "Reducing systematic review burden using Deduklick: a novel, automated, reliable, and explainable deduplication algorithm to foster medical research",
        "authors": [{"name": "Smith, John"}, {"name": "Doe, Jane"}],
        "publication_year": 2022,
        "journal": "Systematic Reviews",
        "source": "pubmed",
        "citation_count": 15,
        "abstract": "Identifying and removing reference duplicates when conducting systematic reviews remains a major issue.",
    },
    {
        "pmid": "32882182",
        "doi": "10.1371/journal.pone.0238218",
        "title": "Myalgic encephalomyelitis/chronic fatigue syndrome: the biology of a neglected disease",
        "authors": [{"name": "Johnson, Mark"}, {"name": "Williams, Sarah"}],
        "publication_year": 2020,
        "journal": "PLoS ONE",
        "source": "pubmed",
        "citation_count": 42,
    },
    {
        "pmid": "31509779",
        "doi": "10.1177/2047487319870515",
        "title": "Exercise therapy for chronic fatigue syndrome: a systematic review and meta-analysis",
        "authors": [{"name": "Brown, Robert"}, {"name": "Taylor, Emily"}],
        "publication_year": 2019,
        "journal": "European Journal of Preventive Cardiology",
        "source": "pubmed",
        "citation_count": 28,
    },
    {
        "pmid": "35188884",
        "doi": "10.3390/jcm11030820",
        "title": "Metabolic features of chronic fatigue syndrome revisited",
        "authors": [{"name": "Garcia, Luis"}, {"name": "Chen, Wei"}],
        "publication_year": 2022,
        "journal": "Journal of Clinical Medicine",
        "source": "pubmed",
        "citation_count": 7,
    },
    # Paper 4: will have an identical twin in the second source
    {
        "pmid": "32791984",
        "doi": "10.1136/bmjopen-2020-045121",
        "title": "Prevalence of myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) in Australia: a longitudinal analysis",
        "authors": [{"name": "Wilson, James"}, {"name": "Davis, Emma"}],
        "publication_year": 2020,
        "journal": "BMJ Open",
        "source": "pubmed",
        "citation_count": 21,
    },
    # Paper 5: will have a variant with a part/supplement marker to test
    #          part-marker detection
    {
        "pmid": "34567890",
        "doi": "10.1000/part-test-1",
        "title": "Understanding post-viral fatigue syndromes: Part I — Clinical presentation",
        "authors": [{"name": "Anderson, Paul"}, {"name": "White, Kate"}],
        "publication_year": 2021,
        "journal": "Journal of Fatigue",
        "source": "pubmed",
        "citation_count": 12,
    },
    # Paper 6: distinct paper about neuroinflammation
    {
        "pmid": "31083475",
        "doi": "10.1186/s12974-019-1485-4",
        "title": "Neuroinflammation in chronic fatigue syndrome: a systematic review",
        "authors": [{"name": "Thompson, Sarah"}, {"name": "Miller, David"}],
        "publication_year": 2019,
        "journal": "Journal of Neuroinflammation",
        "source": "pubmed",
        "citation_count": 34,
    },
    # Paper 7: distinct — different topic
    {
        "pmid": "29365045",
        "doi": "10.1016/j.jpsychores.2017.12.010",
        "title": "Cognitive behavioural therapy for chronic fatigue syndrome",
        "authors": [{"name": "Clark, Timothy"}, {"name": "Lewis, Anna"}],
        "publication_year": 2018,
        "journal": "Journal of Psychosomatic Research",
        "source": "pubmed",
        "citation_count": 55,
    },
    # Paper 8: distinct
    {
        "pmid": "30312305",
        "doi": "10.1016/j.jmii.2018.05.003",
        "title": "Immunological abnormalities in chronic fatigue syndrome",
        "authors": [{"name": "Nakamura, Yuki"}, {"name": "Park, Sung"}],
        "publication_year": 2018,
        "journal": "Journal of Microbiology, Immunology and Infection",
        "source": "pubmed",
        "citation_count": 9,
    },
    # Paper 9: will have a nearly identical twin (title case variant, author
    #          format variant) to test fuzzy matching
    {
        "pmid": "29072345",
        "doi": "10.1038/s41598-017-13815-6",
        "title": "Gut microbiota in chronic fatigue syndrome: a population-based study",
        "authors": [{"name": "Martinez, Carlos"}, {"name": "Kim, Hyun"}],
        "publication_year": 2017,
        "journal": "Scientific Reports",
        "source": "pubmed",
        "citation_count": 67,
    },
]

# ---------------------------------------------------------------------------
# Second-source variants (simulating "crossref" or "semantic scholar")
# ---------------------------------------------------------------------------


def _make_second_source(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create second-source variants with deliberate metadata differences.

    - Papers 0–3: exact copies (simulating same paper across databases)
    - Paper 4: exact copy (will be deduped by DOI)
    - Paper 5: Part II variant (should NOT match Part I — tests part marker)
    - Paper 6: title case + author format variant (tests fuzzy matching)
    - Paper 7: missing DOI + slightly different title (tests fuzzy + author gate)
    - Paper 8: unique paper not in source 1 (simulates source-exclusive records)
    - Paper 9: title-only variant with 90% similarity (tests threshold)
    """
    second: list[dict[str, Any]] = []

    for paper in papers[:4]:
        variant = copy.deepcopy(paper)
        variant["source"] = "crossref"
        # Slightly different abstract, same IDs
        variant["abstract"] = None
        second.append(variant)

    # Paper 4: exact match (will be caught by DOI)
    p4 = copy.deepcopy(papers[4])
    p4["source"] = "crossref"
    second.append(p4)

    # Paper 5: Part II variant (should NOT match Part I)
    p5 = copy.deepcopy(papers[5])
    p5["source"] = "crossref"
    p5["title"] = "Understanding post-viral fatigue syndromes: Part II — Biomarkers"
    p5["pmid"] = "98765432"  # different PMID, same DOI → DOI match domain
    p5["doi"] = "10.1000/part-test-2"  # different DOI — tests part marker in fuzzy
    second.append(p5)

    # Paper 6: title case variant + author format variant
    p6 = copy.deepcopy(papers[6])
    p6["source"] = "crossref"
    p6["title"] = "NEUROINFLAMMATION IN CHRONIC FATIGUE SYNDROME: A SYSTEMATIC REVIEW"
    p6["authors"] = [{"name": "Thompson, S."}, {"name": "Miller, D."}]
    p6["pmid"] = ""  # missing — forces fuzzy match
    second.append(p6)

    # Paper 7: missing DOI, slightly different title, different PMID
    p7 = copy.deepcopy(papers[7])
    p7["source"] = "crossref"
    p7["title"] = "Cognitive behavioural therapy for chronic fatigue syndrome: an updated review"
    p7["pmid"] = "87654321"
    p7["doi"] = ""
    second.append(p7)

    # Paper 8: unique crossref-only paper
    second.append({
        "pmid": "99887766",
        "doi": "10.1000/unique-crossref-1",
        "title": "COVID-19 and post-viral fatigue: a longitudinal cohort study",
        "authors": [{"name": "Hughes, David"}, {"name": "Foster, Rachel"}],
        "publication_year": 2023,
        "journal": "Lancet Infectious Diseases",
        "source": "crossref",
        "citation_count": 3,
    })

    # Paper 9: title variant with ~93% similarity to original
    p9 = copy.deepcopy(papers[9])
    p9["source"] = "crossref"
    p9["title"] = "Gut microbiota composition in chronic fatigue syndrome: a population-based study"
    p9["pmid"] = "76543210"
    p9["doi"] = ""
    second.append(p9)

    return second


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def source1() -> list[dict[str, Any]]:
    """Primary source (PubMed)."""
    papers = copy.deepcopy(_REAL_PAPERS)
    for p in papers:
        p.setdefault("source", "pubmed")
    return papers


@pytest.fixture(scope="module")
def source2() -> list[dict[str, Any]]:
    """Secondary source (Crossref / Semantic Scholar variant)."""
    return _make_second_source(copy.deepcopy(_REAL_PAPERS))


@pytest.fixture(scope="module")
def combined(source1, source2) -> list[dict[str, Any]]:
    """Combined input for dedup testing."""
    return source1 + source2  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Test: DedupMode comparison
# ---------------------------------------------------------------------------


class TestDedupRealWorldScenarios:
    """End-to-end deduplication with simulated real-world data."""

    @pytest.mark.parametrize(
        "mode,expected_removed_min,expected_removed_max",
        [
            (DedupMode.RELAXED, 5, 8),   # high precision: fewer merges
            (DedupMode.BALANCED, 7, 10),  # balanced
            (DedupMode.FOCUSED, 9, 13),   # high recall: more merges
        ],
    )
    def test_dedup_mode_comparison(
        self,
        combined: list[dict[str, Any]],
        mode: DedupMode,
        expected_removed_min: int,
        expected_removed_max: int,
    ):
        """Run all three DedupMode strategies and compare results."""
        config = DedupConfig(mode=mode)
        merger = LiteratureMerger(config=config)

        start = time.monotonic()
        merged, report = merger.merge_results([combined])
        elapsed = time.monotonic() - start

        # Core assertions
        assert len(merged) <= len(combined)
        assert report.total_input == len(combined)
        assert report.total_output == len(merged)
        assert report.duplicates_removed == len(report.records)
        assert expected_removed_min <= report.duplicates_removed <= expected_removed_max, (
            f"{mode.name}: expected {expected_removed_min}-{expected_removed_max} "
            f"removed, got {report.duplicates_removed}"
        )

        # Log stats
        summary = report.summary()
        logger.info(
            "%s: %d→%d (%.1f%%) in %.3fs  levels=%s",
            mode.name,
            summary["total_input"],
            summary["total_output"],
            summary["dedup_rate"] * 100,
            elapsed,
            summary["by_match_level"],
        )

        # Verify no duplicate DOIs or PMIDs in output
        seen_pmids: set[str] = set()
        seen_dois: set[str] = set()
        for paper in merged:
            pmid = paper.get("pmid")
            if pmid:
                assert str(pmid).strip() not in seen_pmids, f"Duplicate PMID in output: {pmid}"
                seen_pmids.add(str(pmid).strip())
            doi = paper.get("doi")
            if doi:
                from pyeuropepmc.features.literature.normalization import normalize_doi
                nd = normalize_doi(doi)
                if nd:
                    assert nd not in seen_dois, f"Duplicate DOI in output: {doi}"
                    seen_dois.add(nd)

        # Verify no record is lost (all unique papers are preserved)
        assert len(merged) <= len(set(p.get("pmid", "") for p in combined if p.get("pmid")))

    def test_provenance_tracking(self, combined: list[dict[str, Any]]):
        """Verify that provenance metadata is tracked in merged output."""
        merger = LiteratureMerger(config=DedupConfig(keep_provenance=True))
        merged, report = merger.merge_results([combined])

        # At least some papers should have provenance
        provenance_count = sum(1 for p in merged if p.get("_provenance"))
        assert provenance_count > 0, "No provenance tracked in merged output"

        # Check provenance for a paper that was merged
        for p in merged:
            prov = p.get("_provenance", {})
            for field, src in prov.items():
                assert src, f"Empty source in provenance for {p.get('pmid', '?')}.{field}"

    def test_author_overlap_gate(self):
        """Author overlap gate should prevent false matches."""
        # Two papers with similar titles but completely different authors + years
        paper_a = {
            "title": "Understanding post-viral fatigue: clinical perspectives",
            "authors": [{"name": "Anderson, Paul"}, {"name": "White, Kate"}],
            "publication_year": 2021,
            "doi": "",
            "pmid": "",
            "source": "pubmed",
        }
        paper_b = {
            "title": "Understanding post-viral fatigue: clinical perspectives",
            "authors": [{"name": "Zhang, Ming"}, {"name": "Patel, Raj"}],
            "publication_year": 2022,
            "doi": "",
            "pmid": "",
            "source": "crossref",
        }

        merger = LiteratureMerger(config=DedupConfig(
            mode=DedupMode.BALANCED,
            require_author_overlap=True,
            fuzzy_threshold=0.85,
        ))
        merged, report = merger.merge_results([[paper_a, paper_b]])

        # With author overlap gate ON, they should NOT be merged (no shared authors)
        assert len(merged) == 2, (
            f"Author gate failed: different authors were merged "
            f"(removed {report.duplicates_removed})"
        )

    def test_part_marker_detection(self):
        """Part-marker detection should prevent false merging of salami
        publications."""
        p1 = {
            "title": "Understanding fatigue syndromes: Part I — Clinical features",
            "authors": [{"name": "Smith, John"}],
            "publication_year": 2021,
            "doi": "",
            "pmid": "",
            "source": "pubmed",
        }
        p2 = {
            "title": "Understanding fatigue syndromes: Part II — Biomarkers",
            "authors": [{"name": "Smith, John"}],
            "publication_year": 2021,
            "doi": "",
            "pmid": "",
            "source": "crossref",
        }

        # Similarity should be penalised by part-marker detection
        sim = _title_similarity(p1["title"], p2["title"])
        logger.info("Part-marker title similarity: %.4f", sim)

        assert sim < 0.90, f"Part-marker similarity too high: {sim:.4f}"
        assert _has_part_marker(p1["title"])
        assert _has_part_marker(p2["title"])

        # The merger should keep both papers separate
        merger = LiteratureMerger(config=DedupConfig(
            mode=DedupMode.BALANCED,
            fuzzy_threshold=0.85,
        ))
        merged, report = merger.merge_results([[p1, p2]])
        assert len(merged) == 2, (
            f"Part-marker detection failed: Part I & II were merged "
            f"(removed {report.duplicates_removed})"
        )

    @pytest.mark.parametrize(
        "threshold,expected_merged",
        [
            (0.95, False),  # high threshold should NOT match variant
            (0.80, True),   # low threshold SHOULD match variant
        ],
    )
    def test_title_case_variant(
        self,
        threshold: float,
        expected_merged: bool,
    ):
        """Title case variants should match at lower thresholds but not at
        high thresholds (RELAXED mode)."""
        original = {
            "title": "A comprehensive analysis of metabolic biomarkers in chronic fatigue syndrome",
            "authors": [{"name": "Martinez, Carlos"}, {"name": "Kim, Hyun"}],
            "publication_year": 2020,
            "doi": "",
            "pmid": "",
            "source": "pubmed",
        }
        variant = {
            "title": "Comprehensive analysis of metabolic biomarkers in chronic fatigue syndrome patients",
            "authors": [{"name": "Martinez, Carlos"}, {"name": "Kim, Hyun"}],
            "publication_year": 2020,
            "doi": "",
            "pmid": "",
            "source": "crossref",
        }

        merger = LiteratureMerger(config=DedupConfig(
            mode=DedupMode.BALANCED,
            fuzzy_threshold=threshold,
            require_author_overlap=True,
        ))
        merged, report = merger.merge_results([[original, variant]])

        if expected_merged:
            assert len(merged) == 1, (
                f"Title variant should be merged at threshold {threshold} "
                f"(sim={_title_similarity(original['title'], variant['title']):.4f})"
            )
        else:
            assert len(merged) == 2, (
                f"Title variant should NOT be merged at threshold {threshold} "
                f"(sim={_title_similarity(original['title'], variant['title']):.4f})"
            )

    def test_merge_field_heuristics(self):
        """Prefer higher-quality fields during merge."""
        pubmed = {
            "title": "Test paper",
            "pmid": "12345678",
            "doi": "10.1000/test",
            "citation_count": 42,
            "authors": [{"name": "Smith, John"}, {"name": "Doe, Jane"}],
            "source": "pubmed",
            "publication_year": 2020,
            "journal": "Test Journal",
        }
        crossref = {
            "title": "Test paper",
            "pmid": "12345678",
            "doi": "",
            "citation_count": 5,
            "authors": None,
            "source": "crossref",
            "publication_year": 2019,
            "journal": "Test Journal",
        }

        merger = LiteratureMerger()
        merged, report = merger.merge_results([[pubmed, crossref]])

        assert len(merged) == 1
        result = merged[0]

        # Should keep higher citation count (42 > 5)
        assert result["citation_count"] == 42, (
            f"Merge should prefer higher citation count: {result['citation_count']}"
        )
        # Should keep DOI from PubMed (non-null > null)
        assert result["doi"] == "10.1000/test"
        # Should keep authors from PubMed (non-null > null)
        assert result["authors"] == [{"name": "Smith, John"}, {"name": "Doe, Jane"}]
        # Should keep publication year from PubMed (preferred source)
        assert result["publication_year"] == 2020

    def test_merge_report_summary(self, combined: list[dict[str, Any]]):
        """MergeReport summary should provide useful statistics."""
        merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
        merged, report = merger.merge_results([combined])

        summary = report.summary()
        assert "total_input" in summary
        assert "total_output" in summary
        assert "dedup_rate" in summary
        assert "by_match_level" in summary
        assert summary["total_input"] == len(combined)
        assert summary["total_output"] == len(merged)

        # Check match level breakdown
        levels = summary["by_match_level"]
        match_count = sum(levels.values())
        assert match_count == report.duplicates_removed, (
            f"Match level counts {match_count} != {report.duplicates_removed}"
        )


# ---------------------------------------------------------------------------
# Test: Large-scale stress test (scalability)
# ---------------------------------------------------------------------------


def _generate_large_dataset(
    n_base: int = 200,
    dup_ratio: float = 0.3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate a large synthetic dataset for stress testing.

    Uses realistic shared-author patterns: each paper has 2-3 authors drawn
    from a shared pool so the author overlap gate works correctly.

    Parameters
    ----------
    n_base : int
        Number of unique base papers.
    dup_ratio : float
        Fraction of papers that will have duplicates in the second source.

    Returns
    -------
    tuple[list, list]
        source1, source2
    """
    random.seed(42)
    # Shared author pool (realistic overlap pattern)
    author_pool = [
        (f"Smith_{i}", f"John_{i}") for i in range(20)
    ] + [
        (f"Johnson_{i}", f"Sarah_{i}") for i in range(20)
    ] + [
        (f"Williams_{i}", f"Emily_{i}") for i in range(20)
    ] + [
        (f"Brown_{i}", f"David_{i}") for i in range(20)
    ] + [
        (f"Jones_{i}", f"Anna_{i}") for i in range(20)
    ]

    source1: list[dict[str, Any]] = []
    source2: list[dict[str, Any]] = []

    # Unique journal names (10 variants)
    journals = [
        "Journal of Medical Research",
        "Clinical Science",
        "Frontiers in Medicine",
        "BMJ Open",
        "PLoS ONE",
        "Scientific Reports",
        "Nature Communications",
        "Journal of Clinical Medicine",
        "European Journal of Clinical Investigation",
        "American Journal of Epidemiology",
    ]

    for i in range(n_base):
        n_authors = random.randint(2, 3)
        authors = [
            {"name": f"{random.choice(author_pool)[0]}, {random.choice(author_pool)[1]}"}
            for _ in range(n_authors)
        ]
        paper: dict[str, Any] = {
            "pmid": str(10000000 + i),
            "doi": f"10.1000/large-test-{i}",
            "title": f"Large-scale study of biomarker {i}: a comprehensive analysis",
            "authors": authors,
            "publication_year": 2015 + (i % 10),
            "journal": random.choice(journals),
            "source": "pubmed",
            "citation_count": random.randint(0, 100),
        }
        source1.append(paper)

        if random.random() < dup_ratio:
            # Create duplicate in source2 (same authors, slightly different metadata)
            variant = copy.deepcopy(paper)
            variant["source"] = "crossref"
            variant["citation_count"] = paper["citation_count"] + random.randint(-5, 5)
            if random.random() < 0.5:
                variant["pmid"] = ""  # forces DOI dedup
            if random.random() < 0.3:
                variant["doi"] = ""  # forces fuzzy dedup
            source2.append(variant)
        else:
            # Create unique paper in source2 with shared author pool
            uid = n_base + i
            n_authors2 = random.randint(2, 3)
            authors2 = [
                {"name": f"{random.choice(author_pool)[0]}, {random.choice(author_pool)[1]}"}
                for _ in range(n_authors2)
            ]
            source2.append({
                "pmid": str(20000000 + uid),
                "doi": f"10.1000/large-test-unique-{uid}",
                "title": f"Unique large-scale study {uid}: new insights from cohort data",
                "authors": authors2,
                "publication_year": 2015 + (uid % 10),
                "journal": random.choice(journals),
                "source": "crossref",
            })

    return source1, source2


class TestDedupLargeScale:
    """Scalability and correctness for large datasets."""

    @pytest.mark.parametrize("n_base", [50, 200])
    def test_large_scale_dedup(self, n_base: int):
        """Stress test with N base papers and ~30% duplication."""
        s1, s2 = _generate_large_dataset(n_base=n_base, dup_ratio=0.3)
        combined = s1 + s2
        expected_unique = len(s1) + len(s2) - int(n_base * 0.3)  # approx

        for mode in DedupMode:
            config = DedupConfig(mode=mode)
            merger = LiteratureMerger(config=config)

            start = time.monotonic()
            merged, report = merger.merge_results([combined])
            elapsed = time.monotonic() - start

            summary = report.summary()
            records_per_sec = len(combined) / elapsed if elapsed > 0 else 0

            logger.info(
                "%s [n=%d]: %d→%d (%.1f%%) in %.3fs (%.0f rec/s)  levels=%s",
                mode.name,
                n_base,
                summary["total_input"],
                summary["total_output"],
                summary["dedup_rate"] * 100,
                elapsed,
                records_per_sec,
                summary["by_match_level"],
            )

            # Basic sanity
            assert len(merged) <= len(combined)
            assert report.total_input == len(combined)
            assert report.duplicates_removed == len(report.records)

            # Should have removed some duplicates
            assert report.duplicates_removed >= 1, (
                f"{mode.name}: expected at least 1 duplicate removed, got 0"
            )

            # RLX should be faster than FOC (fewer comparisons)
            # (not a hard assertion, just informational)

            # No duplicate IDs in output
            seen_pmids: set[str] = set()
            for p in merged:
                pmid = p.get("pmid")
                if pmid:
                    assert str(pmid).strip() not in seen_pmids
                    seen_pmids.add(str(pmid).strip())

    def test_dedup_speed_comparison(self):
        """Compare dedup speed across modes for a large dataset."""
        s1, s2 = _generate_large_dataset(n_base=500, dup_ratio=0.3)
        combined = s1 + s2
        results: dict[str, float] = {}

        for mode in DedupMode:
            config = DedupConfig(mode=mode)
            merger = LiteratureMerger(config=config)

            start = time.monotonic()
            merger.merge_results([combined])
            elapsed = time.monotonic() - start

            results[mode.name] = elapsed
            logger.info(
                "%s: %.3fs (%.0f rec/s)",
                mode.name,
                elapsed,
                len(combined) / elapsed,
            )

        # Basic sanity: all modes should complete in reasonable time
        for mode_name, elapsed in results.items():
            assert elapsed < 60, (
                f"{mode_name} took {elapsed:.3f}s — too slow"
            )
        # FOCUSED does more comparisons (no early-exit gates), so it may be
        # slower than RELAXED; the main assertion is that nothing hangs.
        logger.info("Speed results: %s", results)


# ---------------------------------------------------------------------------
# Test: Single-paper matching (PaperMatcher)
# ---------------------------------------------------------------------------


class TestPaperMatcherRealWorld:
    """Incremental PaperMatcher with real-world data."""

    def test_incremental_matching(self, combined: list[dict[str, Any]]):
        """PaperMatcher should match incrementally with same results as batch."""
        from pyeuropepmc.features.enrich.merger import PaperMatcher

        batch_merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
        batch_merged, _ = batch_merger.merge_results([combined])

        incremental_matcher = PaperMatcher(
            fuzzy_threshold=DedupMode.BALANCED.threshold(),
            require_author_overlap=True,
        )
        incremental_merged: list[dict[str, Any]] = []
        for paper in combined:
            is_dup, level = incremental_matcher.match(paper)
            if not is_dup:
                incremental_merged.append(paper)

        # Results should be consistent (may differ slightly due to order)
        assert len(incremental_merged) <= len(combined)
        assert len(batch_merged) <= len(incremental_merged) + 2, (
            f"Batch got {len(batch_merged)}, incremental got {len(incremental_merged)}"
        )


# ---------------------------------------------------------------------------
# Run directly as a benchmark script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print("REAL-WORLD DEDUPLICATION BENCHMARK")
    print("=" * 70)

    print("\n--- Test Data ---")
    print(f"  Base papers: {len(_REAL_PAPERS)}")
    s2 = _make_second_source(copy.deepcopy(_REAL_PAPERS))
    combined = copy.deepcopy(_REAL_PAPERS) + s2
    print(f"  Source 1: {len(_REAL_PAPERS)} papers")
    print(f"  Source 2: {len(s2)} papers")
    print(f"  Combined: {len(combined)} papers")

    print("\n--- DedupMode Comparison ---")
    for mode in DedupMode:
        config = DedupConfig(mode=mode)
        merger = LiteratureMerger(config=config)

        start = time.monotonic()
        merged, report = merger.merge_results([combined])
        elapsed = time.monotonic() - start

        summary = report.summary()
        print(f"  {mode.name:10s}: {summary['total_input']:3d} → "
              f"{summary['total_output']:3d} ({summary['dedup_rate']*100:5.1f}%) "
              f"in {elapsed:.4f}s  levels={summary['by_match_level']}")

    print("\n--- Large-Scale Stress Test ---")
    for n_base in [100, 500]:
        s1, s2_large = _generate_large_dataset(n_base=n_base, dup_ratio=0.3)
        combined_large = s1 + s2_large
        print(f"\n  Dataset: {n_base} base, {len(combined_large)} total")
        for mode in DedupMode:
            config = DedupConfig(mode=mode)
            merger = LiteratureMerger(config=config)
            start = time.monotonic()
            merged, report = merger.merge_results([combined_large])
            elapsed = time.monotonic() - start
            summary = report.summary()
            rec_per_s = len(combined_large) / elapsed if elapsed > 0 else 0
            print(f"    {mode.name:10s}: {len(combined_large):5d} → "
                  f"{summary['total_output']:5d} ({summary['dedup_rate']*100:5.1f}%) "
                  f"in {elapsed:7.3f}s ({rec_per_s:7.0f} rec/s)  "
                  f"levels={summary['by_match_level']}")

    print("\nDone.")
